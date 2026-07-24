"""Stage A audit of the WP2 M4 DAgger round-1 student-collection campaign.

Streams ``events.jsonl`` for each of the 5 collected student runs and computes,
without touching the read-only runs directory:

  * student-control fraction over student_tick periods (inclusion gate >= 0.95,
    design .tmp/wp2_m4_dagger_design.md section 2),
  * fallback / clamp cause counts (student_tick.source / .cause),
  * control latency p50 / p99 / max (student_tick.latency_ms),
  * combat_capture count,
  * telemetry integrity: summary.json errors == 0 and hangs == 0, capture
    schema hash matches the frozen source hash on every capture, and
    teacher.action present on every capture,
  * per-run wave reached + result (summary.json).

It also verifies the torch sidecar identity in
``.tmp/student_sidecar_dagger_r1.jsonl`` against the registry manifest
``models/registry/bc_v1_s1_full.json`` (model sha256 BE7E8232...).

Each run gets an include / exclude verdict; excluded runs are recorded with a
reason and are NOT built into the corrective dataset. This script writes
``reports/wp2/dagger_r1_collection_audit.{json,md}`` and prints an ASCII table.

No game, no deploy, no commit; the runs directory is opened read-only. Run with
the project ``.venv`` python.

Exit codes: 0 = completed, all included-eligible runs pass integrity;
1 = at least one run has a hard integrity anomaly (schema-hash mismatch,
missing teacher.action, telemetry errors/hangs) or a sidecar identity mismatch;
2 = usage / IO / unexpected failure.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterator

ROOT = Path(__file__).resolve().parents[1]
RUNS_ROOT = Path("C:/Users/moxhe/AppData/Roaming/Brotato/brotato_agent/runs")
STATE_PATH = ROOT / ".tmp" / "dagger_r1_collector_state.json"
SIDECAR_LOG = ROOT / ".tmp" / "student_sidecar_dagger_r1.jsonl"
REGISTRY_PATH = ROOT / "models" / "registry" / "bc_v1_s1_full.json"
REPORT_JSON = ROOT / "reports" / "wp2" / "dagger_r1_collection_audit.json"
REPORT_MD = ROOT / "reports" / "wp2" / "dagger_r1_collection_audit.md"

EXPECTED_CAPTURE_SCHEMA_HASH = (
    "95B6444796A21FD44E94113B75BA2097BC381D5F72ED784F9B9A4A99DD46D951"
)
EXPECTED_MODEL_SHA256 = "BE7E82326EC8A424A1EDF33134E65A26E06EDA68DA7F22D37705F3C26D6A9F0F"

COLLECTED_RUN_IDS = [
    "run_1784863478_12397",
    "run_1784864302_38172",
    "run_1784865437_64140",
    "run_1784866560_35665",
    "run_1784867357_2622",
]

STUDENT_CONTROL_GATE = 0.95
SMOKE_CAP_CAPTURES = 4000


# --------------------------------------------------------------------------- #
# Streaming helpers
# --------------------------------------------------------------------------- #
def iter_events(events_path: Path) -> Iterator[dict[str, Any]]:
    """Yield decoded JSON objects, one per non-blank line."""
    with open(events_path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def percentile(sorted_vals: list[float], q: float) -> float | None:
    """Nearest-rank percentile of an already-sorted list (q in [0, 1])."""
    if not sorted_vals:
        return None
    if len(sorted_vals) == 1:
        return float(sorted_vals[0])
    rank = q * (len(sorted_vals) - 1)
    lo = int(rank)
    hi = min(lo + 1, len(sorted_vals) - 1)
    frac = rank - lo
    return float(sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * frac)


# --------------------------------------------------------------------------- #
# Per-run audit
# --------------------------------------------------------------------------- #
def audit_run(run_id: str, runs_root: Path, smoke: bool) -> dict[str, Any]:
    """Single streaming pass over one run's events + its summary.json."""
    events_path = runs_root / run_id / "events.jsonl"
    summary_path = runs_root / run_id / "summary.json"
    if not events_path.exists():
        raise FileNotFoundError(f"missing events.jsonl for {run_id}: {events_path}")

    capture_count = 0
    schema_mismatch = 0
    missing_teacher_action = 0
    max_wave = 0

    student_source = 0
    fallback_source = 0
    cause_counts: dict[str, int] = {}
    source_counts: dict[str, int] = {}
    fallback_cause_counts: dict[str, int] = {}
    latencies: list[int] = []

    for event in iter_events(events_path):
        etype = event.get("event")
        if etype == "combat_capture":
            capture_count += 1
            payload = event.get("payload", {}) or {}
            if payload.get("capture_schema_hash") != EXPECTED_CAPTURE_SCHEMA_HASH:
                schema_mismatch += 1
            teacher = payload.get("teacher", {}) or {}
            action = teacher.get("action")
            if (
                not isinstance(action, dict)
                or not isinstance(action.get("x"), (int, float))
                or not isinstance(action.get("y"), (int, float))
            ):
                missing_teacher_action += 1
            wave = int(payload.get("wave") or 0)
            if wave > max_wave:
                max_wave = wave
            if smoke and capture_count >= SMOKE_CAP_CAPTURES:
                break
        elif etype == "student_tick":
            payload = event.get("payload", {}) or {}
            source = str(payload.get("source", "unknown"))
            cause = str(payload.get("cause", "unknown"))
            source_counts[source] = source_counts.get(source, 0) + 1
            cause_counts[cause] = cause_counts.get(cause, 0) + 1
            if source == "student":
                student_source += 1
            else:
                fallback_source += 1
                fallback_cause_counts[cause] = fallback_cause_counts.get(cause, 0) + 1
            lat = payload.get("latency_ms")
            if isinstance(lat, (int, float)):
                latencies.append(int(lat))

    total_ticks = student_source + fallback_source
    control_fraction = (student_source / total_ticks) if total_ticks else 0.0
    clamp_count = int(cause_counts.get("clamped", 0))

    latencies.sort()
    latency = {
        "n": len(latencies),
        "p50": percentile(latencies, 0.50),
        "p99": percentile(latencies, 0.99),
        "max": float(latencies[-1]) if latencies else None,
    }

    # summary.json telemetry integrity
    summary_present = summary_path.exists()
    summary_errors: int | None = None
    summary_hangs: int | None = None
    illegal_actions: int | None = None
    result: str | None = None
    waves_completed: int | None = None
    recoveries: int | None = None
    last_wave: int | None = None
    if summary_present:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        summary_errors = int(summary.get("errors", -1))
        summary_hangs = int(summary.get("hangs", -1))
        illegal_actions = int(summary.get("illegal_actions", -1))
        result = str(summary.get("result", "unknown"))
        waves_completed = int(summary.get("waves_completed", 0))
        recoveries = int(summary.get("recoveries", 0))
        last_wave = int(summary.get("last_wave", 0))

    integrity_ok = (
        summary_present
        and summary_errors == 0
        and summary_hangs == 0
        and schema_mismatch == 0
        and missing_teacher_action == 0
    )

    # Inclusion verdict (integrity failure or below control gate -> exclude).
    reasons: list[str] = []
    if not integrity_ok:
        if not summary_present:
            reasons.append("summary.json missing")
        if summary_errors not in (0, None) and summary_errors != 0:
            reasons.append(f"summary.errors={summary_errors}")
        if summary_hangs not in (0, None) and summary_hangs != 0:
            reasons.append(f"summary.hangs={summary_hangs}")
        if schema_mismatch:
            reasons.append(f"{schema_mismatch} capture schema-hash mismatches")
        if missing_teacher_action:
            reasons.append(f"{missing_teacher_action} captures missing teacher.action")
    if control_fraction < STUDENT_CONTROL_GATE:
        reasons.append(
            f"student-control fraction {control_fraction:.4f} < {STUDENT_CONTROL_GATE}"
        )
    verdict = "include" if not reasons else "exclude"

    return {
        "run_id": run_id,
        "verdict": verdict,
        "reasons": reasons,
        "capture_count": capture_count,
        "student_control_fraction": round(control_fraction, 6),
        "student_ticks": student_source,
        "fallback_ticks": fallback_source,
        "clamp_count": clamp_count,
        "source_counts": source_counts,
        "cause_counts": cause_counts,
        "fallback_cause_counts": fallback_cause_counts,
        "latency_ms": latency,
        "telemetry": {
            "summary_present": summary_present,
            "errors": summary_errors,
            "hangs": summary_hangs,
            "illegal_actions": illegal_actions,
            "capture_schema_hash_mismatches": schema_mismatch,
            "captures_missing_teacher_action": missing_teacher_action,
            "integrity_ok": integrity_ok,
        },
        "wave_reached": max_wave,
        "summary_last_wave": last_wave,
        "waves_completed": waves_completed,
        "recoveries": recoveries,
        "result": result,
        "smoke_truncated": bool(smoke),
    }


# --------------------------------------------------------------------------- #
# Sidecar identity
# --------------------------------------------------------------------------- #
def audit_sidecar(sidecar_log: Path, registry_path: Path) -> dict[str, Any]:
    """Verify the torch sidecar startup identity against the registry manifest."""
    result: dict[str, Any] = {
        "log_present": sidecar_log.exists(),
        "registry_present": registry_path.exists(),
        "identity_ok": False,
    }
    if not sidecar_log.exists() or not registry_path.exists():
        result["error"] = "sidecar log or registry manifest missing"
        return result

    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    reg_model = str(registry["checkpoints"]["best"]["sha256"]).upper()
    reg_norm = str(registry["normalization_manifest_hash"]).upper()
    reg_schema = str(registry["schema_hash"]).upper()
    reg_name = str(registry["run_name"])

    startup = None
    handshakes: list[str] = []
    stats_errors_total = 0
    stats_events = 0
    served_max = 0
    model_p99_max = 0.0
    for line in sidecar_log.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        etype = rec.get("event")
        if etype == "startup" and startup is None:
            startup = rec
        elif etype == "handshake_ok":
            handshakes.append(str(rec.get("run_id")))
        elif etype == "stats":
            stats_events += 1
            stats_errors_total += int(rec.get("errors", 0))
            served_max = max(served_max, int(rec.get("served", 0)))
            model_p99_max = max(model_p99_max, float(rec.get("model_ms_p99", 0.0)))

    if startup is None:
        result["error"] = "no startup record in sidecar log"
        return result

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
            "handshake_run_ids": handshakes,
            "serving": {
                "stats_events": stats_events,
                "errors_total": stats_errors_total,
                "served_max": served_max,
                "model_ms_p99_max": round(model_p99_max, 4),
            },
        }
    )
    return result


# --------------------------------------------------------------------------- #
# Report rendering
# --------------------------------------------------------------------------- #
def render_md(report: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# DAgger round-1 collection audit (Stage A)")
    lines.append("")
    lines.append(f"- campaign policy: `{report['campaign'].get('policy_version')}`")
    lines.append(f"- mod version: `{report['campaign'].get('mod_version')}`")
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
        "| run_id | verdict | ctrl_frac | student | fallback | clamp | "
        "lat p50/p99/max | captures | wave | result | errors | hangs | teacher.action miss | schema mismatch |"
    )
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for r in report["runs"]:
        lat = r["latency_ms"]
        tel = r["telemetry"]
        lines.append(
            f"| {r['run_id']} | {r['verdict']} | {r['student_control_fraction']:.4f} | "
            f"{r['student_ticks']} | {r['fallback_ticks']} | {r['clamp_count']} | "
            f"{lat['p50']}/{lat['p99']}/{lat['max']} | {r['capture_count']} | "
            f"{r['wave_reached']} | {r['result']} | {tel['errors']} | {tel['hangs']} | "
            f"{tel['captures_missing_teacher_action']} | {tel['capture_schema_hash_mismatches']} |"
        )
    lines.append("")
    for r in report["runs"]:
        if r["reasons"]:
            lines.append(f"- **{r['run_id']}** excluded: {'; '.join(r['reasons'])}")
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
    parser = argparse.ArgumentParser(description="Stage A DAgger r1 collection audit")
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
        collected = state.get("collected_run_ids") or COLLECTED_RUN_IDS

        print(f"Auditing {len(collected)} DAgger r1 runs (smoke={args.smoke})", flush=True)
        runs: list[dict[str, Any]] = []
        for run_id in collected:
            print(f"  streaming {run_id} ...", flush=True)
            entry = audit_run(run_id, args.runs_root, args.smoke)
            runs.append(entry)
            print(
                f"    verdict={entry['verdict']} ctrl_frac={entry['student_control_fraction']:.4f} "
                f"captures={entry['capture_count']} wave={entry['wave_reached']} "
                f"result={entry['result']}",
                flush=True,
            )

        sidecar = audit_sidecar(args.sidecar_log, args.registry)

        included = [r["run_id"] for r in runs if r["verdict"] == "include"]
        excluded = [r["run_id"] for r in runs if r["verdict"] == "exclude"]
        any_integrity_fail = any(not r["telemetry"]["integrity_ok"] for r in runs)
        overall = "PASS" if (not any_integrity_fail and sidecar.get("identity_ok")) else "FLAG"

        report = {
            "stage": "A",
            "smoke": bool(args.smoke),
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
            },
            "sidecar_identity": sidecar,
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
        print(f"  overall: {overall}", flush=True)
        print(f"  report: {report_json}", flush=True)

        if any_integrity_fail or not sidecar.get("identity_ok"):
            return 1
        return 0
    except (FileNotFoundError, KeyError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr, flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
