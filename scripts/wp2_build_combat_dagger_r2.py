"""Build the ``combat_dagger_r2`` corrective dataset (WP2 M4 DAgger round 2).

Thin round-2 parameterization of ``scripts/wp2_build_combat_dagger_r1.py``:
the identical frozen pipeline and gates, reusing its pure helpers unchanged
(``build_run`` from the frozen ``wp2_build_combat_obs_v1.py`` for Stage-B
encoding; ``compute_aux_and_weights`` for the Stage-C aux labels + 45/30/15/10
event-balanced weights; ``load_included_runs``; ``git_head_commit`` /
``sha256_file``). Round-1 outputs are frozen and never touched.

Round-2 specifics vs round 1:
  * source campaign = the bc_v2_f_s1 round-2 runs (5 collection runs + the
    included bc_v2_f smoke run), read from
    ``reports/wp2/dagger_r2_collection_audit.json``,
  * manifest ``student_policy = bc_v2_f_s1`` and per-run result/wave provenance,
  * NEW: per-run triple-reconciliation stats (proposal/executed/intervention),
    lifted from the Stage-A audit, embedded in the manifest,
  * dataset id ``combat_dagger_r2`` -> ``datasets/combat_dagger_r2/``.

Shards are byte-for-byte combat_obs_v1-compatible (loaded by
``trainer/data/bc_dataset.py`` unchanged). Row label = teacher.action
(counterfactual); prev-action = the student's applied action. Shards are
gitignored; ``manifest.json`` is tracked.

No game, no deploy, no commit. Run with the project ``.venv`` python.

Exit codes: 0 = built, all gates pass; 1 = a build gate failed; 2 = usage / IO
/ unexpected failure.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# Reuse the frozen round-1 build helpers unchanged (they in turn reuse the
# frozen combat_obs_v1 pipeline). Nothing round-1 identity-bearing is imported.
from scripts.wp2_build_combat_dagger_r1 import (  # noqa: E402
    CONTROL_HZ,
    HORIZON_TICKS,
    PRECURSOR_MAX_TICKS,
    PRECURSOR_MIN_TICKS,
    RECOVERY_TICKS,
    RISK_GROUPS,
    RISK_THRESHOLD,
    SEG_NAMES,
    SEG_TARGET_MASS,
    compute_aux_and_weights,
    load_included_runs,
)
from scripts.wp2_build_combat_obs_v1 import (  # noqa: E402
    build_run,
    git_head_commit,
    sha256_file,
)
from trainer.observation.encoder_v1 import load_schema  # noqa: E402

ROOT = _REPO_ROOT
SCHEMA_PATH = ROOT / "configs" / "wp2" / "observation_v1.yaml"
ENCODER_REL = "trainer/observation/encoder_v1.py"
BUILDER_REL = "scripts/wp2_build_combat_dagger_r2.py"
RUNS_ROOT = Path("C:/Users/moxhe/AppData/Roaming/Brotato/brotato_agent/runs")
AUDIT_JSON = ROOT / "reports" / "wp2" / "dagger_r2_collection_audit.json"
STATE_PATH = ROOT / ".tmp" / "dagger_r2_collector_state.json"
SIDECAR_LOG = ROOT / ".tmp" / "student_sidecar_dagger_r2.jsonl"
DATASET_DIR = ROOT / "datasets" / "combat_dagger_r2"
REPORT_MD = ROOT / "reports" / "wp2" / "dagger_r2_dataset_report.md"
REPORT_JSON = ROOT / "reports" / "wp2" / "dagger_r2_dataset_report.json"

STUDENT_POLICY = "bc_v2_f_s1"


def build(
    run_ids: list[str],
    schema: dict[str, Any],
    runs_root: Path,
    dataset_dir: Path,
    audit_by_run: dict[str, Any],
) -> dict[str, Any]:
    contact_idx = list(schema["entity_features"]).index("contact_risk")
    hp_idx = list(schema["global_features"]).index("hp_ratio")
    aux_dir = dataset_dir / "aux_labels"
    weights_dir = dataset_dir / "sample_weights"
    aux_dir.mkdir(parents=True, exist_ok=True)
    weights_dir.mkdir(parents=True, exist_ok=True)

    start = time.time()
    run_entries: list[dict[str, Any]] = []
    for run_id in run_ids:
        events_path = runs_root / run_id / "events.jsonl"
        if not events_path.exists():
            raise FileNotFoundError(f"missing events.jsonl for {run_id}: {events_path}")
        t0 = time.time()
        # Stage B: frozen encode -> shard (reused build_run, byte-identical layout).
        entry = build_run(run_id, events_path, schema, dataset_dir)
        shard_path = dataset_dir / entry["shard_file"]

        # Stage C: aux + weights from the built shard (reused r1 helper).
        with np.load(shard_path) as shard:
            derived = compute_aux_and_weights(shard, contact_idx, hp_idx)
        aux_path = aux_dir / f"{run_id}.npz"
        weights_path = weights_dir / f"{run_id}.npz"
        np.savez_compressed(aux_path, **derived["arrays"])
        np.savez_compressed(weights_path, **derived["weight_arrays"])

        audit = audit_by_run.get(run_id, {})
        entry["build_seconds"] = round(time.time() - t0, 2)
        entry["aux_file"] = f"aux_labels/{run_id}.npz"
        entry["aux_sha256"] = sha256_file(aux_path)
        entry["weights_file"] = f"sample_weights/{run_id}.npz"
        entry["weights_sha256"] = sha256_file(weights_path)
        entry["corrective_stats"] = derived["stats"]
        entry["smoke_run"] = bool(audit.get("smoke_run", False))
        entry["student_control"] = {
            "student_control_fraction": audit.get("student_control_fraction"),
            "student_ticks": audit.get("student_ticks"),
            "fallback_ticks": audit.get("fallback_ticks"),
            "clamp_count": audit.get("clamp_count"),
            "latency_ms": audit.get("latency_ms"),
            "wave_reached": audit.get("wave_reached"),
            "result": audit.get("result"),
        }
        # NEW in round 2: per-run triple-reconciliation stats from Stage A.
        entry["triple_reconciliation"] = audit.get("reconciliation")
        entry["connection"] = audit.get("connection")
        run_entries.append(entry)
        st = derived["stats"]
        print(
            f"  {run_id}: {entry['counts']['total']} rows, "
            f"{entry['counts']['valid_and_temporal_valid']} valid&temporal, "
            f"{st['episodes']} episodes, dmg_rate={st['aux']['aux_damage_base_rate']}, "
            f"{entry['build_seconds']}s",
            flush=True,
        )
    wall = time.time() - start

    agg = {
        "total": sum(e["counts"]["total"] for e in run_entries),
        "valid": sum(e["counts"]["valid"] for e in run_entries),
        "temporal_valid": sum(e["counts"]["temporal_valid"] for e in run_entries),
        "valid_and_temporal_valid": sum(e["counts"]["valid_and_temporal_valid"] for e in run_entries),
        "fault_count": sum(e["fault_count"] for e in run_entries),
        "episodes": sum(e["corrective_stats"]["episodes"] for e in run_entries),
    }
    per_wave_valid: dict[str, int] = {}
    for e in run_entries:
        for wave_str, count in e["per_wave_valid"].items():
            per_wave_valid[wave_str] = per_wave_valid.get(wave_str, 0) + count

    # Aggregate segment / aux stats over eligible rows (identical to r1).
    seg_agg = {SEG_NAMES[s]: 0 for s in SEG_TARGET_MASS}
    horizon_valid = 0
    damage_pos = 0
    margin_weighted_sum = 0.0
    for e in run_entries:
        st = e["corrective_stats"]
        for name, c in st["segment_eligible_counts"].items():
            seg_agg[name] += c
        hv = st["aux"]["horizon_valid_rows"]
        horizon_valid += hv
        damage_pos += int(round(st["aux"]["aux_damage_base_rate"] * hv))
        margin_weighted_sum += st["aux"]["aux_margin_mean"] * hv
    seg_total = sum(seg_agg.values()) or 1
    seg_fractions = {name: round(c / seg_total, 4) for name, c in seg_agg.items()}
    seg_mass_agg = {SEG_NAMES[s]: 0.0 for s in SEG_TARGET_MASS}
    for e in run_entries:
        elig = e["counts"]["valid_and_temporal_valid"]
        for name, frac in e["corrective_stats"]["segment_mass_fractions"].items():
            seg_mass_agg[name] += frac * elig
    mass_total = sum(seg_mass_agg.values()) or 1.0
    seg_mass_fractions = {name: round(v / mass_total, 4) for name, v in seg_mass_agg.items()}
    aux_agg = {
        "horizon_valid_rows": horizon_valid,
        "aux_damage_base_rate": round(damage_pos / horizon_valid, 6) if horizon_valid else 0.0,
        "aux_margin_mean": round(margin_weighted_sum / horizon_valid, 6) if horizon_valid else 1.0,
    }

    # Aggregate triple-reconciliation roll-up.
    recon_agg = {
        "student_ticks": 0,
        "student_matched": 0,
        "student_missing_act": 0,
        "ok_ticks": 0,
        "ok_violations": 0,
        "ok_max_abs_delta": 0.0,
        "clamped_ticks": 0,
        "clamped_violations": 0,
        "clamped_max_dir_diff": 0.0,
        "clamped_max_mag_err": 0.0,
        "timeout_ticks": 0,
        "timeout_with_act": 0,
        "not_connected_ticks": 0,
        "all_reconciliation_ok": True,
    }
    for e in run_entries:
        rc = e.get("triple_reconciliation") or {}
        if not rc:
            continue
        recon_agg["student_ticks"] += rc["student_ticks"]
        recon_agg["student_matched"] += rc["student_matched"]
        recon_agg["student_missing_act"] += rc["student_missing_act"]
        recon_agg["ok_ticks"] += rc["ok"]["ticks"]
        recon_agg["ok_violations"] += rc["ok"]["violations"]
        recon_agg["ok_max_abs_delta"] = max(recon_agg["ok_max_abs_delta"], rc["ok"]["max_abs_delta"])
        recon_agg["clamped_ticks"] += rc["clamped"]["ticks"]
        recon_agg["clamped_violations"] += rc["clamped"]["violations"]
        recon_agg["clamped_max_dir_diff"] = max(recon_agg["clamped_max_dir_diff"], rc["clamped"]["max_dir_diff"])
        recon_agg["clamped_max_mag_err"] = max(recon_agg["clamped_max_mag_err"], rc["clamped"]["max_mag_err"])
        recon_agg["timeout_ticks"] += rc["timeout_ticks"]
        recon_agg["timeout_with_act"] += rc["timeout_with_act"]
        recon_agg["not_connected_ticks"] += rc["not_connected_ticks"]
        recon_agg["all_reconciliation_ok"] &= bool(rc["reconciliation_ok"])
    recon_agg["join_coverage"] = round(
        recon_agg["student_matched"] / recon_agg["student_ticks"], 6
    ) if recon_agg["student_ticks"] else 0.0

    # Gates (identical set to r1).
    fault_count = agg["fault_count"]
    shards_written = len(run_entries)
    gates = [
        {
            "name": "all_shards_written",
            "status": "PASS" if shards_written == len(run_ids) else "FAIL",
            "value": shards_written,
            "threshold": len(run_ids),
            "detail": f"{shards_written}/{len(run_ids)} shards + aux + weights written",
        },
        {
            "name": "zero_encoding_faults",
            "status": "PASS" if fault_count == 0 else "FAIL",
            "value": fault_count,
            "threshold": 0,
            "detail": f"{fault_count} ObservationError faults",
        },
        {
            "name": "valid_and_temporal_positive",
            "status": "PASS" if agg["valid_and_temporal_valid"] > 0 else "FAIL",
            "value": agg["valid_and_temporal_valid"],
            "threshold": 1,
            "detail": f"{agg['valid_and_temporal_valid']} training-eligible rows",
        },
        {
            "name": "aux_weights_aligned",
            "status": "PASS"
            if all(e["corrective_stats"]["rows"] == e["counts"]["total"] for e in run_entries)
            else "FAIL",
            "value": shards_written,
            "threshold": shards_written,
            "detail": "aux/weight arrays length == shard rows for every run",
        },
        {
            "name": "triple_reconciliation_ok",
            "status": "PASS" if recon_agg["all_reconciliation_ok"] else "FAIL",
            "value": recon_agg["join_coverage"],
            "threshold": 1.0,
            "detail": (
                f"join_cov={recon_agg['join_coverage']}, "
                f"ok_viol={recon_agg['ok_violations']}, "
                f"clamp_viol={recon_agg['clamped_violations']}, "
                f"missing_act={recon_agg['student_missing_act']}"
            ),
        },
    ]
    overall = "PASS" if all(g["status"] == "PASS" for g in gates) else "FAIL"

    head = git_head_commit(ROOT)
    dataset_bytes = sum(e["shard_bytes"] for e in run_entries)

    state = {}
    if STATE_PATH.exists():
        state = json.loads(STATE_PATH.read_text(encoding="utf-8"))

    manifest = {
        "dataset_id": "combat_dagger_r2",
        "schema_id": schema["schema_id"],
        "observation_schema_hash": schema["_schema_hash"],
        "source_capture_schema_hash": schema["source_capture_schema_hash"],
        "encoder_path": ENCODER_REL,
        "builder_script": BUILDER_REL,
        "reused_pipeline": "scripts/wp2_build_combat_obs_v1.py::build_run",
        "reused_r1_helpers": "scripts/wp2_build_combat_dagger_r1.py::compute_aux_and_weights",
        "repo_head_commit": head,
        "runs_root": str(runs_root),
        "run_count": len(run_ids),
        "student_policy": STUDENT_POLICY,
        "student_model_sha256": "1AD517B04843B69966841C7B795B927AE86B2727789456224321FC091F29F331",
        "source_campaign": {
            "policy_version": state.get("policy_version"),
            "mod_version": state.get("mod_version"),
            "started_at": state.get("started_at"),
            "stop_reason": state.get("stop_reason"),
            "collector_state_file": str(STATE_PATH),
            "sidecar_log": str(SIDECAR_LOG),
            "audit_report": str(AUDIT_JSON),
        },
        "corrective_config": {
            "control_hz": CONTROL_HZ,
            "aux_horizon_ticks": HORIZON_TICKS,
            "risk_threshold": RISK_THRESHOLD,
            "risk_groups": list(RISK_GROUPS),
            "precursor_ticks": [PRECURSOR_MIN_TICKS, PRECURSOR_MAX_TICKS],
            "recovery_ticks": RECOVERY_TICKS,
            "segment_target_mass": {SEG_NAMES[s]: r for s, r in SEG_TARGET_MASS.items()},
            "onset_cap": "2x mean episode mass (2 * 0.15*M / E)",
            "gap_mask": "temporal_valid (control_dt_ms in (0,250]) over the full horizon",
            "weight_normalization": "mean weight over eligible rows == 1.0",
            "contact_risk_feature_index": contact_idx,
            "hp_ratio_global_index": hp_idx,
        },
        "aggregate": {**agg, "dataset_bytes": int(dataset_bytes)},
        "segment_eligible_counts": seg_agg,
        "segment_eligible_fractions": seg_fractions,
        "segment_mass_fractions": seg_mass_fractions,
        "aux_base_rates": aux_agg,
        "triple_reconciliation_aggregate": recon_agg,
        "gates": gates,
        "overall_status": overall,
        "runs": run_entries,
    }

    report = {
        "dataset_id": "combat_dagger_r2",
        "student_policy": STUDENT_POLICY,
        "observation_schema_hash": schema["_schema_hash"],
        "source_capture_schema_hash": schema["source_capture_schema_hash"],
        "encoder_path": ENCODER_REL,
        "builder_script": BUILDER_REL,
        "repo_head_commit": head,
        "run_count": len(run_ids),
        "build_wall_seconds": round(wall, 2),
        "dataset_bytes": int(dataset_bytes),
        "aggregate": agg,
        "per_wave_valid": per_wave_valid,
        "segment_eligible_counts": seg_agg,
        "segment_eligible_fractions": seg_fractions,
        "segment_mass_fractions": seg_mass_fractions,
        "aux_base_rates": aux_agg,
        "triple_reconciliation_aggregate": recon_agg,
        "gates": gates,
        "overall_status": overall,
        "runs": [
            {
                "run_id": e["run_id"],
                "smoke_run": e["smoke_run"],
                "connection": e["connection"],
                "shard_file": e["shard_file"],
                "shard_sha256": e["shard_sha256"],
                "aux_sha256": e["aux_sha256"],
                "weights_sha256": e["weights_sha256"],
                "counts": e["counts"],
                "corrective_stats": e["corrective_stats"],
                "student_control": e["student_control"],
                "triple_reconciliation": e["triple_reconciliation"],
            }
            for e in run_entries
        ],
    }
    return {"manifest": manifest, "report": report, "wall": wall}


# --------------------------------------------------------------------------- #
# Report rendering (r1 layout + a round-2 reconciliation section)
# --------------------------------------------------------------------------- #
def render_md(report: dict[str, Any], manifest_sha: str) -> str:
    lines: list[str] = []
    lines.append("# combat_dagger_r2 corrective dataset report")
    lines.append("")
    lines.append(f"- student policy: `{report['student_policy']}`")
    lines.append(f"- schema hash: `{report['observation_schema_hash']}`")
    lines.append(f"- encoder: `{report['encoder_path']}` (frozen, reused build_run)")
    lines.append(f"- builder: `{report['builder_script']}` @ `{report['repo_head_commit']}`")
    lines.append(f"- runs: {report['run_count']} | build wall: {report['build_wall_seconds']:.1f}s")
    lines.append(f"- dataset bytes: {report['dataset_bytes']:,}")
    lines.append(f"- manifest sha256: `{manifest_sha}`")
    lines.append("")
    lines.append("## Gates")
    lines.append("")
    lines.append("| gate | status | value | threshold | detail |")
    lines.append("| --- | --- | --- | --- | --- |")
    for g in report["gates"]:
        lines.append(f"| {g['name']} | {g['status']} | {g['value']} | {g['threshold']} | {g['detail']} |")
    lines.append("")
    lines.append(f"Overall: **{report['overall_status']}**")
    lines.append("")
    agg = report["aggregate"]
    lines.append("## Aggregate")
    lines.append("")
    lines.append(f"- total rows: {agg['total']:,}")
    lines.append(f"- valid: {agg['valid']:,}")
    lines.append(f"- valid AND temporal_valid (training-eligible): {agg['valid_and_temporal_valid']:,}")
    lines.append(f"- encoding faults: {agg['fault_count']}")
    lines.append(f"- risk episodes: {agg['episodes']:,}")
    lines.append("")
    lines.append("## Triple reconciliation (aggregate)")
    lines.append("")
    rc = report["triple_reconciliation_aggregate"]
    lines.append(f"- join coverage: {rc['join_coverage']} ({rc['student_matched']:,}/{rc['student_ticks']:,} student ticks)")
    lines.append(f"- ok ticks: {rc['ok_ticks']:,} | violations (>1e-4): {rc['ok_violations']} | max|delta|: {rc['ok_max_abs_delta']:.2e}")
    lines.append(f"- clamped ticks: {rc['clamped_ticks']:,} | violations: {rc['clamped_violations']} | max dir diff: {rc['clamped_max_dir_diff']:.2e} | max |mag-1|: {rc['clamped_max_mag_err']:.2e}")
    lines.append(f"- timeout ticks: {rc['timeout_ticks']} (with act: {rc['timeout_with_act']}) | not_connected: {rc['not_connected_ticks']}")
    lines.append(f"- student ticks missing act: {rc['student_missing_act']} | all reconciliation ok: {rc['all_reconciliation_ok']}")
    lines.append("")
    lines.append("## Aux label base rates (over horizon-valid rows)")
    lines.append("")
    aux = report["aux_base_rates"]
    lines.append(f"- horizon-valid rows: {aux['horizon_valid_rows']:,}")
    lines.append(f"- aux_damage base rate (P hp-drop within 10 ticks): {aux['aux_damage_base_rate']}")
    lines.append(f"- aux_margin mean (1 - max future contact_risk): {aux['aux_margin_mean']}")
    lines.append("")
    lines.append("## Segment distribution (eligible rows)")
    lines.append("")
    lines.append("Target 45/30/15/10 is on WEIGHT MASS (achieved via per-row weights), not row counts.")
    lines.append("")
    lines.append("| segment | rows | row_fraction | mass_fraction (target) |")
    lines.append("| --- | --- | --- | --- |")
    targets = {"background": 0.45, "precursor": 0.30, "onset_episode": 0.15, "recovery": 0.10}
    for name in ("background", "precursor", "onset_episode", "recovery"):
        lines.append(
            f"| {name} | {report['segment_eligible_counts'][name]:,} | "
            f"{report['segment_eligible_fractions'][name]} | "
            f"{report['segment_mass_fractions'][name]} ({targets[name]}) |"
        )
    lines.append("")
    lines.append("## Per-run")
    lines.append("")
    lines.append(
        "| run_id | smoke | rows | valid&temporal | episodes | dmg_rate | ctrl_frac | "
        "join_cov | wave | result | shard sha (16) |"
    )
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for e in report["runs"]:
        st = e["corrective_stats"]
        sc = e["student_control"]
        tr = e.get("triple_reconciliation") or {}
        lines.append(
            f"| {e['run_id']} | {e['smoke_run']} | {e['counts']['total']:,} | "
            f"{e['counts']['valid_and_temporal_valid']:,} | {st['episodes']} | "
            f"{st['aux']['aux_damage_base_rate']} | {sc['student_control_fraction']} | "
            f"{tr.get('join_coverage')} | {sc['wave_reached']} | {sc['result']} | "
            f"{e['shard_sha256'][:16]} |"
        )
    lines.append("")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> int:
    parser = argparse.ArgumentParser(description="Build combat_dagger_r2 corrective dataset")
    parser.add_argument("--audit", type=Path, default=AUDIT_JSON)
    parser.add_argument("--runs-root", type=Path, default=RUNS_ROOT)
    parser.add_argument("--dataset-dir", type=Path, default=DATASET_DIR)
    parser.add_argument("--report-json", type=Path, default=REPORT_JSON)
    parser.add_argument("--report-md", type=Path, default=REPORT_MD)
    parser.add_argument("--smoke", action="store_true", help="build only the first included run into a _smoke dir")
    args = parser.parse_args()

    dataset_dir = args.dataset_dir
    manifest_path = dataset_dir / "manifest.json"
    report_json = args.report_json
    report_md = args.report_md

    try:
        schema = load_schema(SCHEMA_PATH)
        included, audit_by_run = load_included_runs(args.audit)
        if not included:
            print("error: no included runs in audit report", file=sys.stderr, flush=True)
            return 1

        if args.smoke:
            included = included[:1]
            dataset_dir = args.dataset_dir / "_smoke"
            manifest_path = dataset_dir / "manifest.json"
            report_json = report_json.with_suffix(".smoke.json")
            report_md = report_md.with_suffix(".smoke.md")

        print(
            f"Building combat_dagger_r2 over {len(included)} runs -> {dataset_dir} "
            f"(smoke={args.smoke})",
            flush=True,
        )
        result = build(included, schema, args.runs_root, dataset_dir, audit_by_run)

        dataset_dir.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(result["manifest"], indent=2), encoding="utf-8")
        manifest_sha = sha256_file(manifest_path)
        report_json.parent.mkdir(parents=True, exist_ok=True)
        report_json.write_text(json.dumps(result["report"], indent=2), encoding="utf-8")
        report_md.write_text(render_md(result["report"], manifest_sha), encoding="utf-8")

        report = result["report"]
        print("\n=== GATES ===", flush=True)
        for g in report["gates"]:
            print(f"  [{g['status']}] {g['name']}: {g['detail']}", flush=True)
        print(f"\nOverall: {report['overall_status']} (wall {result['wall']:.1f}s)", flush=True)
        print(f"Rows total={report['aggregate']['total']:,} "
              f"valid&temporal={report['aggregate']['valid_and_temporal_valid']:,} "
              f"episodes={report['aggregate']['episodes']:,}", flush=True)
        print(f"Aux dmg_rate={report['aux_base_rates']['aux_damage_base_rate']} "
              f"margin_mean={report['aux_base_rates']['aux_margin_mean']}", flush=True)
        print(f"Segment row_fractions={report['segment_eligible_fractions']}", flush=True)
        print(f"Segment mass_fractions={report['segment_mass_fractions']} (target bg/pre/onset/rec 0.45/0.30/0.15/0.10)", flush=True)
        rc = report["triple_reconciliation_aggregate"]
        print(f"Triple recon join_cov={rc['join_coverage']} ok_viol={rc['ok_violations']} "
              f"clamp_viol={rc['clamped_violations']} missing={rc['student_missing_act']} "
              f"all_ok={rc['all_reconciliation_ok']}", flush=True)
        print(f"Manifest sha256: {manifest_sha}", flush=True)
        print(f"Manifest: {manifest_path}", flush=True)
        return 0 if report["overall_status"] == "PASS" else 1
    except (FileNotFoundError, KeyError, ValueError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr, flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
