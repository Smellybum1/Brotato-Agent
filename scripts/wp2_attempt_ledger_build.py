"""Pass 2: build the attempt-level ledger (.tmp/winrate/ledger.jsonl + ledger.csv).

Reads .tmp/winrate/raw_runs.jsonl (from wp2_attempt_ledger_extract.py) plus
campaign attribution files under .tmp/ and reports/. Pure offline.
"""
from __future__ import annotations

import csv
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, ".tmp/winrate/raw_runs.jsonl")
OUT_JSONL = os.path.join(ROOT, ".tmp/winrate/ledger.jsonl")
OUT_CSV = os.path.join(ROOT, ".tmp/winrate/ledger.csv")
OUT_PROV = os.path.join(ROOT, ".tmp/winrate/mode_provenance.json")

VER_RE = re.compile(r"0\.1\.(\d+)")

# ---------------------------------------------------------------- attribution


def campaign_map() -> tuple[dict, dict]:
    """run_id -> (mode, source_file). Later, more specific sources win."""
    assign: dict[str, tuple[str, str]] = {}
    prov: dict[str, dict] = {}

    def take(path: str, ids, mode: str, priority: int) -> None:
        n = 0
        for rid in ids:
            cur = assign.get(rid)
            if cur is None or priority >= cur[2]:
                assign[rid] = (mode, path, priority)
                n += 1
        prov[path] = {"mode": mode, "n_ids": len(list(ids)), "n_assigned": n,
                      "priority": priority}

    # 1) F2 verdict files: authoritative T/P split (priority 30)
    f2dir = os.path.join(ROOT, "reports/wp2/f2")
    for f in sorted(os.listdir(f2dir)):
        m = re.fullmatch(r"r(\d+)_([TP])\.json", f)
        if not m:
            continue
        d = json.load(open(os.path.join(f2dir, f), encoding="utf-8"))
        ids = [r["run_id"] for r in d.get("results", [])]
        take(f"reports/wp2/f2/{f}", ids,
             "teacher" if m.group(2) == "T" else "residual", 30)

    # 2) collector state / report files with collected_run_ids (priority 20)
    label_rules = [
        (re.compile(r"dagger_r\d", re.I), "student"),
        (re.compile(r"paired_eval", re.I), "student"),
        (re.compile(r"(pi\d|residual|probe)", re.I), "residual"),
        (re.compile(r"(teacher|gate_state|smoke|sentinel|v1\d\d)", re.I), "teacher"),
    ]
    for base in (".tmp", "reports"):
        for dp, dn, fn in os.walk(os.path.join(ROOT, base)):
            dn[:] = [d for d in dn
                     if d != "winrate" and not d.startswith("pytest")
                     and "wp1-clean-bootstrap" not in d and not d.startswith("codex_v")]
            for f in fn:
                if not f.endswith(".json"):
                    continue
                p = os.path.join(dp, f)
                try:
                    d = json.load(open(p, encoding="utf-8"))
                except Exception:
                    continue
                if not (isinstance(d, dict) and d.get("collected_run_ids")):
                    continue
                rel = os.path.relpath(p, ROOT).replace("\\", "/")
                mode = None
                for rx, mo in label_rules:
                    if rx.search(f):
                        mode = mo
                        break
                if mode is None:
                    continue
                take(rel, d["collected_run_ids"], mode, 20)

    return assign, prov


# ---------------------------------------------------------------- ledger


def main() -> None:
    rows = [json.loads(l) for l in open(RAW, encoding="utf-8")]
    assign, prov = campaign_map()

    # explicit operator aborts
    aborted = {}
    ap = os.path.join(ROOT, "reports/wp2/f2/aborted_runs.jsonl")
    if os.path.exists(ap):
        for line in open(ap, encoding="utf-8"):
            line = line.strip()
            if line:
                d = json.loads(line)
                aborted[d["aborted_run_id"]] = d.get("reason", "")

    ledger = []
    for r in rows:
        aid = r["attempt_id"]
        st = r["summary_status"]
        s = r.get("summary") or {}
        scan = r.get("scan") or {}
        rs = scan.get("run_start_payload") or {}
        fe = (r.get("first_event") or {}).get("payload") or {}

        def pick(key):
            if st == "present" and s.get(key) is not None:
                return s.get(key)
            if rs.get(key) is not None:
                return rs.get(key)
            return fe.get(key)

        policy_version = pick("policy_version")
        m = VER_RE.search(policy_version or "")
        version_int = int(m.group(1)) if m else None

        ec = scan.get("event_counts", {})
        probe = r.get("probe") or {}
        student_signal = bool(probe.get("student_tick") or probe.get("student_session")
                              or ec.get("student_tick") or ec.get("student_session"))

        # ---- run_mode
        camp = assign.get(aid)
        if camp:
            run_mode, mode_src = camp[0], camp[1]
        elif student_signal:
            run_mode, mode_src = "student", "events:student_tick"
        elif version_int is not None and version_int <= 124:
            # student inference path first appears empirically at 0.1.125
            run_mode, mode_src = "teacher", "pre-student-cutoff(<=124)"
        else:
            run_mode, mode_src = "unknown", "unresolved"
        if camp and student_signal and run_mode not in ("student", "residual"):
            mode_src += "+student_signal_conflict"

        # ---- terminal class
        result = s.get("result") if st == "present" else None
        evidence = ""
        if st == "present":
            if result == "victory":
                tc, win = "WIN", True
            elif result == "defeat":
                tc, win = "GAMEPLAY_LOSS", False
            elif result == "automation_fault":
                tc, win = "MOD_OR_POLICY_FAILURE", False
            else:
                tc, win = "UNKNOWN", None
            evidence = f"summary.result={result}"
        else:
            # no summary: verified 0/188 have a run_end event
            if aid in aborted:
                tc, win, evidence = "EXTERNAL_ABORT", None, "aborted_runs.jsonl:" + aborted[aid][:80]
            elif scan.get("n_events", 0) <= 2:
                tc, win, evidence = "UNKNOWN", None, f"stream_truncated_at_start n_events={scan.get('n_events')}"
            elif scan.get("min_hp") is not None and scan.get("min_hp") <= 0:
                tc, win, evidence = "GAMEPLAY_LOSS", False, "stream hp<=0 (death signal) but no run_end"
            else:
                tc, win = "UNKNOWN", None
                evidence = (f"no run_end; stream stops mid-wave{scan.get('max_wave')} "
                            f"last_hp={scan.get('last_hp')} last_event={scan.get('tail',[{}])[-1].get('event') if scan.get('tail') else None}")

        final_wave = s.get("last_wave") if st == "present" else scan.get("max_wave")

        ledger.append({
            "attempt_id": aid,
            "start_ts": s.get("start_timestamp") if st == "present" else None,
            "stream_first_ts_ms": scan.get("first_ts_ms"),
            "stream_last_ts_ms": scan.get("last_ts_ms"),
            "policy_version": policy_version,
            "version_int": version_int,
            "mod_version": pick("mod_version"),
            "config_id": pick("config_id"),
            "character": pick("character"),
            "weapon": pick("weapon"),
            "danger": pick("danger"),
            "game_version": pick("game_version"),
            "run_mode": run_mode,
            "run_mode_source": mode_src,
            "student_signal": student_signal,
            "summary_status": st,
            "result_raw": result,
            "failure_category": s.get("failure_category"),
            "terminal_class": tc,
            "terminal_evidence": evidence,
            "win": win,
            "final_wave": final_wave,
            "waves_completed": s.get("waves_completed"),
            "duration_ms": s.get("duration_ms"),
            "damage_taken": s.get("damage_taken"),
            "errors": s.get("errors"),
            "hangs": s.get("hangs"),
            "illegal_actions": s.get("illegal_actions"),
            "recoveries": s.get("recoveries"),
            "telemetry_complete": s.get("telemetry_complete"),
            "n_events": scan.get("n_events"),
            "events_bytes": r.get("events_bytes"),
        })

    ledger.sort(key=lambda x: (x["version_int"] is None, x["version_int"] or 0, x["attempt_id"]))
    os.makedirs(os.path.dirname(OUT_JSONL), exist_ok=True)
    with open(OUT_JSONL, "w", encoding="utf-8") as fh:
        for row in ledger:
            fh.write(json.dumps(row) + "\n")
    with open(OUT_CSV, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(ledger[0].keys()))
        w.writeheader()
        w.writerows(ledger)
    json.dump(prov, open(OUT_PROV, "w", encoding="utf-8"), indent=1)
    print(f"ledger rows={len(ledger)} -> {OUT_JSONL}", file=sys.stderr)


if __name__ == "__main__":
    main()
