"""Pass 1: extract one raw feature record per run dir (642), writing .tmp/winrate/raw_runs.jsonl.

Pure offline. Reads the run store only. No game, no deploy.
"""
from __future__ import annotations

import json
import os
import sys
import time

RUNS = os.environ.get(
    "BROTATO_RUNS",
    r"C:/Users/moxhe/AppData/Roaming/Brotato/brotato_agent/runs",
)
OUT = r"C:/Codex/Brotato Agent/.tmp/winrate/raw_runs.jsonl"

HEAD_BYTES = 4 * 1024 * 1024
TAIL_BYTES = 1 * 1024 * 1024
TAIL_KEEP = 40  # last N parsed events retained for no-summary runs

SUMMARY_KEYS = [
    "run_id", "schema_version", "policy_version", "start_timestamp", "character",
    "weapon", "danger", "endless", "wave_retry", "game_version", "mod_version",
    "config_id", "result", "last_wave", "waves_completed", "recoveries", "errors",
    "hangs", "illegal_actions", "damage_taken", "telemetry_complete",
    "end_timestamp", "duration_ms", "failure_category", "rerolls", "locks",
    "materials_spent",
]


def head_tail_bytes(path: str) -> bytes:
    size = os.path.getsize(path)
    with open(path, "rb") as fh:
        head = fh.read(min(size, HEAD_BYTES))
        if size > HEAD_BYTES + TAIL_BYTES:
            fh.seek(-TAIL_BYTES, os.SEEK_END)
            tail = fh.read()
        else:
            tail = b""
    return head + b"\n" + tail


def scan_full(path: str) -> dict:
    """Full streaming parse. Used for no-summary runs (small: <1GB total)."""
    n_lines = 0
    n_bad = 0
    counts: dict[str, int] = {}
    max_wave = None
    last_hp = None
    min_hp = None
    first_ts = None
    last_ts = None
    tail: list[dict] = []
    run_start = None
    errors: list[str] = []
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            n_lines += 1
            try:
                ev = json.loads(line)
            except Exception:
                n_bad += 1
                continue
            et = ev.get("event")
            counts[et] = counts.get(et, 0) + 1
            ts = ev.get("ts_ms")
            if ts is not None:
                if first_ts is None:
                    first_ts = ts
                last_ts = ts
            pl = ev.get("payload") or {}
            if et == "run_start":
                run_start = pl
            if et == "error" and len(errors) < 10:
                errors.append(json.dumps(pl)[:400])
            if isinstance(pl, dict):
                w = pl.get("wave")
                if isinstance(w, (int, float)):
                    max_wave = w if max_wave is None else max(max_wave, w)
                hp = pl.get("hp")
                if isinstance(hp, (int, float)):
                    last_hp = hp
                    min_hp = hp if min_hp is None else min(min_hp, hp)
            tail.append({"event": et, "ts_ms": ts,
                         "payload_head": json.dumps(pl)[:300]})
            if len(tail) > TAIL_KEEP:
                tail.pop(0)
    return {
        "n_events": n_lines, "n_bad_lines": n_bad, "event_counts": counts,
        "max_wave": max_wave, "last_hp": last_hp, "min_hp": min_hp,
        "first_ts_ms": first_ts, "last_ts_ms": last_ts,
        "run_start_payload": run_start, "tail": tail, "error_payloads": errors,
    }


def main() -> None:
    dirs = sorted(d for d in os.listdir(RUNS) if os.path.isdir(os.path.join(RUNS, d)))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    t0 = time.time()
    with open(OUT, "w", encoding="utf-8") as out:
        for i, d in enumerate(dirs):
            rd = os.path.join(RUNS, d)
            spath = os.path.join(rd, "summary.json")
            epath = os.path.join(rd, "events.jsonl")
            rec: dict = {"attempt_id": d}
            rec["has_events_file"] = os.path.exists(epath)
            rec["events_bytes"] = os.path.getsize(epath) if rec["has_events_file"] else 0
            rec["dir_files"] = sorted(os.listdir(rd))

            if os.path.exists(spath):
                rec["summary_bytes"] = os.path.getsize(spath)
                try:
                    s = json.load(open(spath, encoding="utf-8"))
                    rec["summary_status"] = "present"
                    rec["summary"] = {k: s.get(k) for k in SUMMARY_KEYS}
                    rec["summary_all_keys"] = sorted(s.keys())
                except Exception as exc:
                    rec["summary_status"] = "unparseable"
                    rec["summary_error"] = repr(exc)[:300]
            else:
                rec["summary_status"] = "absent"

            if rec["summary_status"] == "present" and rec["has_events_file"]:
                # cheap substring probe for run-mode signals only
                try:
                    blob = head_tail_bytes(epath)
                    rec["probe"] = {
                        "student_tick": b'"student_tick"' in blob,
                        "student_session": b'"student_session"' in blob,
                        "combat_capture": b'"combat_capture"' in blob,
                        "run_end": b'"run_end"' in blob,
                    }
                    first = blob.split(b"\n", 1)[0]
                    try:
                        rec["first_event"] = json.loads(first.decode("utf-8", "replace"))
                    except Exception:
                        rec["first_event"] = None
                except Exception as exc:
                    rec["probe_error"] = repr(exc)[:300]
            elif rec["has_events_file"]:
                try:
                    rec["scan"] = scan_full(epath)
                except Exception as exc:
                    rec["scan_error"] = repr(exc)[:300]

            out.write(json.dumps(rec) + "\n")
            if (i + 1) % 50 == 0:
                print(f"{i+1}/{len(dirs)} {time.time()-t0:.0f}s", file=sys.stderr, flush=True)
    print(f"wrote {OUT} ({len(dirs)} rows) in {time.time()-t0:.0f}s", file=sys.stderr)


if __name__ == "__main__":
    main()
