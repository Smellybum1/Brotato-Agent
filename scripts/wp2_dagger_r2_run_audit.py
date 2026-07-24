"""Stage A audit of the WP2 M4 DAgger round-2 student-collection campaign.

Round 2 student policy = ``bc_v2_f_s1`` (model sha 1AD517B0..., registry
``models/registry/bc_v2_f_s1.json``). This audits the 5 round-2 collection runs
PLUS the preceding ``bc_v2_f`` smoke run (same sidecar session, collected
identically under Case-A shielding) as a 6th included run when it clears the
same gates (provenance ``smoke_run=true``).

It reuses the frozen round-1 tooling unchanged where possible: ``iter_events``,
``percentile`` and ``audit_run`` are imported from
``scripts/wp2_dagger_r1_run_audit.py`` (round-1 outputs are frozen and never
touched). This script adds:

  * bc_v2_f_s1 sidecar identity verification (model sha, normalization, schema,
    run name) against the registry manifest,
  * the NEW triple reconciliation now that the sidecar logs per-act raw
    proposals ``{seq, ax, ay}`` (design section 8 round-2 precondition):
      - the sidecar act stream is partitioned by CONNECTION (seq resets per
        game-session handshake: conn 0 = smoke run, conn 1 = the 5 campaign
        runs, seq contiguous within a connection),
      - (a) source=student / cause=ok ticks: logged proposal ~= executed
        (|dx|,|dy| <= 1e-4),
      - (b) source=student / cause=clamped ticks: executed = proposal /
        |proposal| (direction diff <= 1e-3 AND |executed| == 1 within 1e-3),
      - (c) join coverage: every student tick carries a matching act; timeout
        ticks (teacher_fallback) may have an act that was produced but not
        applied -- those are counted, as are orphan acts with no tick at all.

Per-run include/exclude verdict is identical to round 1 (integrity + >=0.95
student-control gate), with a reconciliation failure additionally flagging the
run. Writes ``reports/wp2/dagger_r2_collection_audit.{json,md}`` and prints an
ASCII table. No game, no deploy, no commit; runs directory opened read-only.

Exit codes: 0 = completed, all runs pass integrity + reconciliation + sidecar
identity; 1 = a hard integrity anomaly, reconciliation violation, or sidecar
identity mismatch; 2 = usage / IO / unexpected failure.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# Reuse the frozen round-1 audit primitives unchanged.
from scripts.wp2_dagger_r1_run_audit import (  # noqa: E402
    audit_run,
    iter_events,
    percentile,  # noqa: F401  (kept for parity / downstream reuse)
)

ROOT = _REPO_ROOT
RUNS_ROOT = Path("C:/Users/moxhe/AppData/Roaming/Brotato/brotato_agent/runs")
STATE_PATH = ROOT / ".tmp" / "dagger_r2_collector_state.json"
SIDECAR_LOG = ROOT / ".tmp" / "student_sidecar_dagger_r2.jsonl"
REGISTRY_PATH = ROOT / "models" / "registry" / "bc_v2_f_s1.json"
REPORT_JSON = ROOT / "reports" / "wp2" / "dagger_r2_collection_audit.json"
REPORT_MD = ROOT / "reports" / "wp2" / "dagger_r2_collection_audit.md"

EXPECTED_CAPTURE_SCHEMA_HASH = (
    "95B6444796A21FD44E94113B75BA2097BC381D5F72ED784F9B9A4A99DD46D951"
)
EXPECTED_MODEL_SHA256 = "1AD517B04843B69966841C7B795B927AE86B2727789456224321FC091F29F331"

# Preceding bc_v2_f smoke run (connection 0). Included as a 6th run if it passes.
SMOKE_RUN_ID = "run_1784872256_15901"
# 5 round-2 collection runs (connection 1), in collection order.
CAMPAIGN_RUN_IDS = [
    "run_1784873462_1600",   # defeat w16
    "run_1784874327_52508",  # defeat w20
    "run_1784875463_98163",  # VICTORY w20
    "run_1784876633_43940",  # defeat w17
    "run_1784877573_54783",  # defeat w20
]

STUDENT_CONTROL_GATE = 0.95
# Reconciliation tolerances (design section 8 stage-A triple).
OK_ABS_TOL = 1e-4          # |proposal - executed| for source=student cause=ok
CLAMP_DIR_TOL = 1e-3       # ||proposal_hat - executed|| for cause=clamped
CLAMP_MAG_TOL = 1e-3       # ||executed| - 1| for cause=clamped


# --------------------------------------------------------------------------- #
# Sidecar: connection-partitioned act map + identity
# --------------------------------------------------------------------------- #
def load_sidecar(sidecar_log: Path) -> dict[str, Any]:
    """Parse the sidecar JSONL once: startup identity, per-connection act maps,
    handshake order, serving stats. Connections are delimited by handshake_ok
    (seq resets per connection)."""
    startup: dict[str, Any] | None = None
    handshakes: list[tuple[int, str]] = []
    act_maps: dict[int, dict[int, tuple[float, float]]] = {}
    act_counts: dict[int, int] = {}
    stats_events = 0
    stats_errors_total = 0
    served_max = 0
    model_p99_max = 0.0
    conn = -1

    for line in sidecar_log.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        etype = rec.get("event")
        if etype == "startup" and startup is None:
            startup = rec
        elif etype == "handshake_ok":
            conn += 1
            handshakes.append((conn, str(rec.get("run_id"))))
            act_maps.setdefault(conn, {})
            act_counts.setdefault(conn, 0)
        elif etype == "act":
            if conn < 0:
                continue  # act before any handshake (shouldn't happen)
            seq = int(rec["seq"])
            act_maps[conn][seq] = (float(rec["ax"]), float(rec["ay"]))
            act_counts[conn] = act_counts.get(conn, 0) + 1
        elif etype == "stats":
            stats_events += 1
            stats_errors_total += int(rec.get("errors", 0))
            served_max = max(served_max, int(rec.get("served", 0)))
            model_p99_max = max(model_p99_max, float(rec.get("model_ms_p99", 0.0)))

    return {
        "startup": startup,
        "handshakes": handshakes,
        "act_maps": act_maps,
        "act_counts": act_counts,
        "serving": {
            "stats_events": stats_events,
            "errors_total": stats_errors_total,
            "served_max": served_max,
            "model_ms_p99_max": round(model_p99_max, 4),
            "total_acts": sum(act_counts.values()),
        },
    }


def audit_sidecar_identity(parsed: dict[str, Any], registry_path: Path) -> dict[str, Any]:
    """Verify the torch sidecar startup identity against the bc_v2_f_s1 registry."""
    result: dict[str, Any] = {
        "log_present": True,
        "registry_present": registry_path.exists(),
        "identity_ok": False,
    }
    if not registry_path.exists():
        result["error"] = "registry manifest missing"
        return result
    startup = parsed["startup"]
    if startup is None:
        result["error"] = "no startup record in sidecar log"
        return result

    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    reg_model = str(registry["checkpoints"]["best"]["sha256"]).upper()
    reg_norm = str(registry["normalization_manifest_hash"]).upper()
    reg_schema = str(registry["schema_hash"]).upper()
    reg_name = str(registry["run_name"])

    log_model = str(startup.get("model_sha256", "")).upper()
    log_norm = str(startup.get("normalization_sha256", "")).upper()
    log_schema = str(startup.get("observation_schema_hash", "")).upper()
    log_name = str(startup.get("registry_run_name", ""))

    checks = {
        "model_sha256": log_model == reg_model == EXPECTED_MODEL_SHA256,
        "normalization_sha256": log_norm == reg_norm,
        "observation_schema_hash": log_schema == reg_schema,
        "registry_run_name": log_name == reg_name,
    }
    result.update(
        {
            "identity_ok": all(checks.values()),
            "checks": checks,
            "backend": startup.get("backend"),
            "model_sha256": log_model,
            "registry_run_name": log_name,
            "handshake_run_ids": [rid for _c, rid in parsed["handshakes"]],
            "serving": parsed["serving"],
        }
    )
    return result


# --------------------------------------------------------------------------- #
# Triple reconciliation (per run, against its connection's act map)
# --------------------------------------------------------------------------- #
def reconcile_run(
    run_id: str, runs_root: Path, act_map: dict[int, tuple[float, float]], smoke: bool
) -> dict[str, Any]:
    """Join a run's student_tick stream to the sidecar act proposals by seq."""
    events_path = runs_root / run_id / "events.jsonl"

    ok_ticks = ok_matched = ok_violations = 0
    ok_max_abs_delta = 0.0
    clamp_ticks = clamp_matched = clamp_violations = 0
    clamp_max_dir_diff = 0.0
    clamp_max_mag_err = 0.0
    timeout_ticks = timeout_with_act = 0
    not_connected_ticks = 0
    student_missing_act = 0
    other_ticks = 0
    referenced_seqs: set[int] = set()
    timeout_seqs: set[int] = set()

    from scripts.wp2_dagger_r1_run_audit import SMOKE_CAP_CAPTURES  # smoke cap parity

    seen_captures = 0
    for event in iter_events(events_path):
        etype = event.get("event")
        if smoke and etype == "combat_capture":
            seen_captures += 1
            if seen_captures >= SMOKE_CAP_CAPTURES:
                break
        if etype != "student_tick":
            continue
        pl = event.get("payload", {}) or {}
        seq = pl.get("seq")
        source = str(pl.get("source", "unknown"))
        cause = str(pl.get("cause", "unknown"))
        ex_x = float(pl.get("student", {}).get("x", 0.0))
        ex_y = float(pl.get("student", {}).get("y", 0.0))

        if not isinstance(seq, int) or seq < 1:
            if cause == "not_connected":
                not_connected_ticks += 1
            else:
                other_ticks += 1
            continue

        act = act_map.get(int(seq))

        if source == "student" and cause == "ok":
            ok_ticks += 1
            if act is None:
                student_missing_act += 1
                continue
            referenced_seqs.add(int(seq))
            ok_matched += 1
            d = max(abs(act[0] - ex_x), abs(act[1] - ex_y))
            ok_max_abs_delta = max(ok_max_abs_delta, d)
            if d > OK_ABS_TOL:
                ok_violations += 1
        elif source == "student" and cause == "clamped":
            clamp_ticks += 1
            if act is None:
                student_missing_act += 1
                continue
            referenced_seqs.add(int(seq))
            clamp_matched += 1
            pmag = math.hypot(act[0], act[1])
            if pmag > 0:
                dir_diff = max(abs(act[0] / pmag - ex_x), abs(act[1] / pmag - ex_y))
            else:
                dir_diff = float("inf")
            mag_err = abs(math.hypot(ex_x, ex_y) - 1.0)
            clamp_max_dir_diff = max(clamp_max_dir_diff, dir_diff)
            clamp_max_mag_err = max(clamp_max_mag_err, mag_err)
            if dir_diff > CLAMP_DIR_TOL or mag_err > CLAMP_MAG_TOL:
                clamp_violations += 1
        elif source == "teacher_fallback" and cause == "timeout":
            timeout_ticks += 1
            if act is not None:
                timeout_with_act += 1
                timeout_seqs.add(int(seq))
        else:
            other_ticks += 1

    student_ticks = ok_ticks + clamp_ticks
    student_matched = ok_matched + clamp_matched
    join_coverage = (student_matched / student_ticks) if student_ticks else 0.0
    reconciliation_ok = (
        ok_violations == 0
        and clamp_violations == 0
        and student_missing_act == 0
    )
    return {
        "connection_act_count": len(act_map),
        "student_ticks": student_ticks,
        "student_matched": student_matched,
        "student_missing_act": student_missing_act,
        "join_coverage": round(join_coverage, 6),
        "ok": {
            "ticks": ok_ticks,
            "matched": ok_matched,
            "max_abs_delta": ok_max_abs_delta,
            "violations": ok_violations,
            "tol": OK_ABS_TOL,
        },
        "clamped": {
            "ticks": clamp_ticks,
            "matched": clamp_matched,
            "max_dir_diff": clamp_max_dir_diff,
            "max_mag_err": clamp_max_mag_err,
            "violations": clamp_violations,
            "dir_tol": CLAMP_DIR_TOL,
            "mag_tol": CLAMP_MAG_TOL,
        },
        "timeout_ticks": timeout_ticks,
        "timeout_with_act": timeout_with_act,
        "not_connected_ticks": not_connected_ticks,
        "other_ticks": other_ticks,
        "referenced_seqs": len(referenced_seqs),
        "timeout_seqs": len(timeout_seqs),
        "reconciliation_ok": reconciliation_ok,
    }


def connection_orphans(
    act_map: dict[int, tuple[float, float]],
    run_recs: list[dict[str, Any]],
) -> dict[str, Any]:
    """Connection-level act accounting: acts referenced by a student tick, acts
    referenced only by a timeout, and orphan acts with no applied tick."""
    ref_student: set[int] = set()
    ref_timeout: set[int] = set()
    for rec in run_recs:
        recon = rec["_recon_seqs"]
        ref_student |= recon["referenced"]
        ref_timeout |= recon["timeout"]
    all_seqs = set(act_map.keys())
    timeout_only = (ref_timeout - ref_student) & all_seqs
    orphan = all_seqs - ref_student - ref_timeout
    return {
        "acts_total": len(all_seqs),
        "acts_applied_to_student_tick": len(ref_student & all_seqs),
        "acts_timeout_not_applied": len(timeout_only),
        "acts_orphan_no_tick": len(orphan),
    }


# --------------------------------------------------------------------------- #
# Report rendering
# --------------------------------------------------------------------------- #
def render_md(report: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# DAgger round-2 collection audit (Stage A)")
    lines.append("")
    lines.append(f"- campaign policy: `{report['campaign'].get('policy_version')}`")
    lines.append(f"- mod version: `{report['campaign'].get('mod_version')}`")
    lines.append(f"- student policy: `{report['student_policy']}`")
    lines.append(f"- expected capture schema hash: `{report['expected_capture_schema_hash']}`")
    lines.append(f"- expected model sha256: `{report['expected_model_sha256']}`")
    lines.append(f"- student-control inclusion gate: >= {report['student_control_gate']}")
    lines.append(f"- smoke: {report['smoke']}")
    lines.append("")
    side = report["sidecar_identity"]
    lines.append("## Sidecar identity")
    lines.append("")
    lines.append(f"- identity_ok: **{side.get('identity_ok')}** | backend: `{side.get('backend')}`")
    lines.append(f"- model_sha256: `{side.get('model_sha256')}`")
    lines.append(f"- checks: {side.get('checks')}")
    lines.append(f"- handshake run_ids: {side.get('handshake_run_ids')}")
    lines.append(f"- serving: {side.get('serving')}")
    lines.append("")
    lines.append("## Per-run verdicts")
    lines.append("")
    lines.append(
        "| run_id | smoke | verdict | ctrl_frac | student | fallback | clamp | "
        "lat p50/p99/max | captures | wave | result | errors | hangs | tchr.act miss | schema mism |"
    )
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for r in report["runs"]:
        lat = r["latency_ms"]
        tel = r["telemetry"]
        lines.append(
            f"| {r['run_id']} | {r.get('smoke_run', False)} | {r['verdict']} | "
            f"{r['student_control_fraction']:.4f} | "
            f"{r['student_ticks']} | {r['fallback_ticks']} | {r['clamp_count']} | "
            f"{lat['p50']}/{lat['p99']}/{lat['max']} | {r['capture_count']} | "
            f"{r['wave_reached']} | {r['result']} | {tel['errors']} | {tel['hangs']} | "
            f"{tel['captures_missing_teacher_action']} | {tel['capture_schema_hash_mismatches']} |"
        )
    lines.append("")
    lines.append("## Triple reconciliation (proposal / executed / intervention)")
    lines.append("")
    lines.append(
        "| run_id | conn | join_cov | ok_ticks | ok_maxD | ok_viol | clamp_ticks | "
        "clamp_dirD | clamp_magErr | clamp_viol | tmout(act) | miss | recon_ok |"
    )
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for r in report["runs"]:
        rc = r["reconciliation"]
        lines.append(
            f"| {r['run_id']} | {r['connection']} | {rc['join_coverage']:.4f} | "
            f"{rc['ok']['ticks']} | {rc['ok']['max_abs_delta']:.2e} | {rc['ok']['violations']} | "
            f"{rc['clamped']['ticks']} | {rc['clamped']['max_dir_diff']:.2e} | "
            f"{rc['clamped']['max_mag_err']:.2e} | {rc['clamped']['violations']} | "
            f"{rc['timeout_ticks']}({rc['timeout_with_act']}) | {rc['student_missing_act']} | "
            f"{rc['reconciliation_ok']} |"
        )
    lines.append("")
    lines.append("## Connection-level act accounting")
    lines.append("")
    lines.append("| connection | handshake run | acts_total | applied | timeout_not_applied | orphan_no_tick |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for c in report["connections"]:
        lines.append(
            f"| {c['connection']} | {c['handshake_run']} | {c['acts_total']} | "
            f"{c['acts_applied_to_student_tick']} | {c['acts_timeout_not_applied']} | "
            f"{c['acts_orphan_no_tick']} |"
        )
    lines.append("")
    for r in report["runs"]:
        if r["reasons"]:
            lines.append(f"- **{r['run_id']}** excluded/flagged: {'; '.join(r['reasons'])}")
    lines.append("")
    lines.append(f"Included runs ({len(report['included_runs'])}): {report['included_runs']}")
    lines.append(f"Excluded runs ({len(report['excluded_runs'])}): {report['excluded_runs']}")
    lines.append("")
    lines.append(f"Overall: **{report['overall_status']}**")
    lines.append("")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> int:
    parser = argparse.ArgumentParser(description="Stage A DAgger r2 collection audit")
    parser.add_argument("--runs-root", type=Path, default=RUNS_ROOT)
    parser.add_argument("--sidecar-log", type=Path, default=SIDECAR_LOG)
    parser.add_argument("--registry", type=Path, default=REGISTRY_PATH)
    parser.add_argument("--report-json", type=Path, default=REPORT_JSON)
    parser.add_argument("--report-md", type=Path, default=REPORT_MD)
    parser.add_argument("--smoke", action="store_true", help="cap captures per run for a fast pass")
    args = parser.parse_args()

    report_json = args.report_json
    report_md = args.report_md
    if args.smoke:
        report_json = report_json.with_suffix(".smoke.json")
        report_md = report_md.with_suffix(".smoke.md")

    try:
        state: dict[str, Any] = {}
        if STATE_PATH.exists():
            state = json.loads(STATE_PATH.read_text(encoding="utf-8"))

        if not args.sidecar_log.exists():
            print(f"error: sidecar log missing: {args.sidecar_log}", file=sys.stderr, flush=True)
            return 2
        parsed = load_sidecar(args.sidecar_log)
        sidecar = audit_sidecar_identity(parsed, args.registry)

        # Connection assignment: conn 0 = smoke run, conn 1 = campaign runs.
        act_maps = parsed["act_maps"]
        run_conn: dict[str, int] = {SMOKE_RUN_ID: 0}
        for rid in CAMPAIGN_RUN_IDS:
            run_conn[rid] = 1

        # Audit order: 5 campaign runs, then the smoke run as the 6th.
        ordered = [(rid, False) for rid in CAMPAIGN_RUN_IDS] + [(SMOKE_RUN_ID, True)]

        print(f"Auditing {len(ordered)} DAgger r2 runs (smoke={args.smoke})", flush=True)
        runs: list[dict[str, Any]] = []
        recon_by_conn: dict[int, list[dict[str, Any]]] = {}
        for run_id, is_smoke in ordered:
            print(f"  streaming {run_id} (smoke_run={is_smoke}) ...", flush=True)
            entry = audit_run(run_id, args.runs_root, args.smoke)
            entry["smoke_run"] = is_smoke
            conn = run_conn[run_id]
            entry["connection"] = conn
            act_map = act_maps.get(conn, {})

            recon = reconcile_run(run_id, args.runs_root, act_map, args.smoke)
            entry["reconciliation"] = recon
            # stash raw seq sets for connection-level accounting, then drop.
            recon_by_conn.setdefault(conn, []).append(
                {
                    "_recon_seqs": {
                        "referenced": _referenced_seqs(run_id, args.runs_root, act_map, args.smoke),
                        "timeout": _timeout_seqs(run_id, args.runs_root, act_map, args.smoke),
                    }
                }
            )

            if not recon["reconciliation_ok"]:
                if recon["student_missing_act"]:
                    entry["reasons"].append(
                        f"{recon['student_missing_act']} student ticks missing sidecar act"
                    )
                if recon["ok"]["violations"]:
                    entry["reasons"].append(
                        f"{recon['ok']['violations']} ok-tick proposal!=executed (>1e-4)"
                    )
                if recon["clamped"]["violations"]:
                    entry["reasons"].append(
                        f"{recon['clamped']['violations']} clamped-tick renorm violations"
                    )
                entry["verdict"] = "exclude"

            runs.append(entry)
            print(
                f"    verdict={entry['verdict']} ctrl_frac={entry['student_control_fraction']:.4f} "
                f"captures={entry['capture_count']} wave={entry['wave_reached']} "
                f"result={entry['result']} join_cov={recon['join_coverage']:.4f} "
                f"recon_ok={recon['reconciliation_ok']}",
                flush=True,
            )

        # Connection-level act accounting.
        handshake_run = {c: rid for c, rid in parsed["handshakes"]}
        connections: list[dict[str, Any]] = []
        for conn in sorted(act_maps.keys()):
            acc = connection_orphans(act_maps[conn], recon_by_conn.get(conn, []))
            connections.append(
                {
                    "connection": conn,
                    "handshake_run": handshake_run.get(conn),
                    **acc,
                }
            )

        included = [r["run_id"] for r in runs if r["verdict"] == "include"]
        excluded = [r["run_id"] for r in runs if r["verdict"] == "exclude"]
        any_integrity_fail = any(not r["telemetry"]["integrity_ok"] for r in runs)
        any_recon_fail = any(not r["reconciliation"]["reconciliation_ok"] for r in runs)
        overall = (
            "PASS"
            if (not any_integrity_fail and not any_recon_fail and sidecar.get("identity_ok"))
            else "FLAG"
        )

        report = {
            "stage": "A",
            "round": 2,
            "smoke": bool(args.smoke),
            "student_policy": "bc_v2_f_s1",
            "expected_capture_schema_hash": EXPECTED_CAPTURE_SCHEMA_HASH,
            "expected_model_sha256": EXPECTED_MODEL_SHA256,
            "student_control_gate": STUDENT_CONTROL_GATE,
            "campaign": {
                "policy_version": state.get("policy_version"),
                "mod_version": state.get("mod_version"),
                "started_at": state.get("started_at"),
                "stop_reason": state.get("stop_reason"),
                "collector_state_file": str(STATE_PATH),
                "sidecar_log": str(args.sidecar_log),
                "smoke_run_id": SMOKE_RUN_ID,
                "campaign_run_ids": CAMPAIGN_RUN_IDS,
            },
            "sidecar_identity": sidecar,
            "connections": connections,
            "runs": runs,
            "included_runs": included,
            "excluded_runs": excluded,
            "overall_status": overall,
        }

        report_json.parent.mkdir(parents=True, exist_ok=True)
        report_json.write_text(json.dumps(report, indent=2), encoding="utf-8")
        report_md.write_text(render_md(report), encoding="utf-8")

        print("\n=== SUMMARY ===", flush=True)
        print(f"  included: {included}", flush=True)
        print(f"  excluded: {excluded}", flush=True)
        print(f"  sidecar identity_ok: {sidecar.get('identity_ok')}", flush=True)
        print(f"  reconciliation all-ok: {not any_recon_fail}", flush=True)
        for c in connections:
            print(
                f"  conn {c['connection']} ({c['handshake_run']}): acts={c['acts_total']} "
                f"applied={c['acts_applied_to_student_tick']} "
                f"timeout_unapplied={c['acts_timeout_not_applied']} "
                f"orphan={c['acts_orphan_no_tick']}",
                flush=True,
            )
        print(f"  overall: {overall}", flush=True)
        print(f"  report: {report_json}", flush=True)

        if any_integrity_fail or any_recon_fail or not sidecar.get("identity_ok"):
            return 1
        return 0
    except (FileNotFoundError, KeyError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr, flush=True)
        return 2


# --------------------------------------------------------------------------- #
# Seq-set helpers (single extra pass, cheap; keeps reconcile_run's return small)
# --------------------------------------------------------------------------- #
def _iter_student_ticks(run_id: str, runs_root: Path, smoke: bool):
    from scripts.wp2_dagger_r1_run_audit import SMOKE_CAP_CAPTURES

    events_path = runs_root / run_id / "events.jsonl"
    seen = 0
    for event in iter_events(events_path):
        et = event.get("event")
        if smoke and et == "combat_capture":
            seen += 1
            if seen >= SMOKE_CAP_CAPTURES:
                break
        if et == "student_tick":
            yield event.get("payload", {}) or {}


def _referenced_seqs(run_id, runs_root, act_map, smoke) -> set[int]:
    out: set[int] = set()
    for pl in _iter_student_ticks(run_id, runs_root, smoke):
        seq = pl.get("seq")
        if isinstance(seq, int) and seq >= 1 and str(pl.get("source")) == "student":
            if int(seq) in act_map:
                out.add(int(seq))
    return out


def _timeout_seqs(run_id, runs_root, act_map, smoke) -> set[int]:
    out: set[int] = set()
    for pl in _iter_student_ticks(run_id, runs_root, smoke):
        seq = pl.get("seq")
        if (
            isinstance(seq, int)
            and seq >= 1
            and str(pl.get("source")) == "teacher_fallback"
            and str(pl.get("cause")) == "timeout"
            and int(seq) in act_map
        ):
            out.add(int(seq))
    return out


if __name__ == "__main__":
    raise SystemExit(main())
