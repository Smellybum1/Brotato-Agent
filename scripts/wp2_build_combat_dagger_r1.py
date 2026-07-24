"""Build the ``combat_dagger_r1`` corrective dataset (WP2 M4 DAgger round 1).

Stage B: over the runs that passed the Stage A audit
(``reports/wp2/dagger_r1_collection_audit.json``), encode every
``combat_capture`` through the FROZEN encoder by reusing ``build_run`` from
``scripts/wp2_build_combat_obs_v1.py`` unchanged. This produces one NPZ shard
per run whose array layout is byte-for-byte identical to ``combat_obs_v1``
(``global_features``, ``entities_*``, ``mask_*``, ``dropped_*``, ``capture_seq``,
``wave``, ``valid``, ``temporal_valid``), so ``trainer/data/bc_dataset.py`` loads
it without changes. Row label = teacher.action (counterfactual); prev-action =
the student's applied action (both already inside the encoded globals).

Stage C: side files keyed to each shard's row order (aligned 1:1 with the
capture_seq-sorted shard rows), derived from the shard itself (no second events
pass, so the frozen pipeline output is authoritative):
  * ``aux_labels/{run}.npz``  -> aux_damage (+mask), aux_margin (+mask)
  * ``sample_weights/{run}.npz`` -> weight (float32), segment (int8)

The frozen ``combat_obs_v1`` dataset and ``wp2_build_combat_obs_v1.py`` are never
modified; this script only imports from the latter. Shards are gitignored
(``datasets/**/*.npz``); ``manifest.json`` is tracked, matching combat_obs_v1.

No game, no deploy, no commit. Run with the project ``.venv`` python.

Exit codes: 0 = built, all gates pass; 1 = a build gate failed; 2 = usage / IO /
unexpected failure.

Aux + weight definitions (design .tmp/wp2_m4_dagger_design.md sections 3 & 7):
  control_hz = 20  ->  0.5 s = 10 ticks, 1.0 s = 20 ticks.
  Horizon for aux = the next 10 capture ticks (rows t+1 .. t+10).
  Gap mask: a window is valid only if all 10 future rows exist AND every one is
    temporal_valid. temporal_valid is False exactly when control_dt_ms is outside
    (0, 250] ms, i.e. it flags the "control_dt_ms > 250 discontinuity" the design
    calls for (it also flags the control_dt_ms == 0 run-start row).
  aux_damage[t] = 1 iff min(hp_ratio[t+1..t+10]) < hp_ratio[t] (strict drop).
  aux_margin[t] = 1 - max(tick_max_risk[t+1..t+10]); tick_max_risk is the max
    contact_risk over the encoded enemies+bosses+projectiles rows of a tick
    (padded rows are 0.0, so empty groups -> risk 0 -> margin 1.0).
  Risk episode = maximal contiguous run of rows with tick_max_risk >= 0.5.
  Segments (mutually exclusive, precedence episode > precursor > recovery > bg):
    onset+episode = rows inside an episode;
    precursor     = rows 0.5-1.0 s before an onset (offset d in [10, 20] ticks),
                    not inside an episode  [LITERAL reading of the binding
                    "0.5-1.0 s BEFORE": the 0.0-0.5 s immediately pre-onset stays
                    background unless it is itself episode/recovery];
    recovery      = rows within 1.0 s after an episode end (offset d in [1, 20]),
                    not inside an episode;
    background    = everything else.
  Weights (over training-eligible = valid & temporal_valid rows only; ineligible
  rows -> weight 0.0): each segment's rows share that segment's target mass with
  target ratio 45/30/15/10 (bg/precursor/onset/recovery). Within onset the mass
  is water-filled per-episode with a cap = 2x the mean episode mass
  (= 2 * 0.15*M / E) so no single long episode dominates. Final weights are
  renormalized so the mean weight over eligible rows is 1.0 (ratios preserved);
  the 25%-effective-mass corrective calibration is applied later at train time.
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

from scripts.wp2_build_combat_obs_v1 import (  # reuse frozen pipeline, unmodified
    ALL_WAVES,
    build_run,
    git_head_commit,
    sha256_file,
)
from trainer.observation.encoder_v1 import load_schema

ROOT = _REPO_ROOT
SCHEMA_PATH = ROOT / "configs" / "wp2" / "observation_v1.yaml"
ENCODER_REL = "trainer/observation/encoder_v1.py"
BUILDER_REL = "scripts/wp2_build_combat_dagger_r1.py"
RUNS_ROOT = Path("C:/Users/moxhe/AppData/Roaming/Brotato/brotato_agent/runs")
AUDIT_JSON = ROOT / "reports" / "wp2" / "dagger_r1_collection_audit.json"
STATE_PATH = ROOT / ".tmp" / "dagger_r1_collector_state.json"
SIDECAR_LOG = ROOT / ".tmp" / "student_sidecar_dagger_r1.jsonl"
DATASET_DIR = ROOT / "datasets" / "combat_dagger_r1"
REPORT_MD = ROOT / "reports" / "wp2" / "dagger_r1_dataset_report.md"
REPORT_JSON = ROOT / "reports" / "wp2" / "dagger_r1_dataset_report.json"

CONTROL_HZ = 20
HORIZON_TICKS = 10          # aux horizon: next 10 ticks (0.5 s)
PRECURSOR_MIN_TICKS = 10    # 0.5 s before onset
PRECURSOR_MAX_TICKS = 20    # 1.0 s before onset
RECOVERY_TICKS = 20         # 1.0 s after episode end
RISK_THRESHOLD = 0.5
RISK_GROUPS = ("enemies", "bosses", "projectiles")
SEG_BACKGROUND, SEG_PRECURSOR, SEG_ONSET, SEG_RECOVERY = 0, 1, 2, 3
SEG_NAMES = {0: "background", 1: "precursor", 2: "onset_episode", 3: "recovery"}
SEG_TARGET_MASS = {SEG_BACKGROUND: 0.45, SEG_PRECURSOR: 0.30, SEG_ONSET: 0.15, SEG_RECOVERY: 0.10}


# --------------------------------------------------------------------------- #
# Stage C: aux labels + event-balanced weights (from the built shard)
# --------------------------------------------------------------------------- #
def _tick_max_risk(shard: Any, contact_idx: int) -> np.ndarray:
    """Per-row max contact_risk over enemies+bosses+projectiles (padded rows are 0)."""
    parts = []
    for group in RISK_GROUPS:
        ent = np.asarray(shard[f"entities_{group}"], dtype=np.float64)  # [N, cap, 15]
        parts.append(ent[:, :, contact_idx].max(axis=1))  # [N]
    return np.maximum.reduce(parts)


def _find_episodes(risk_hot: np.ndarray) -> list[tuple[int, int]]:
    """Maximal contiguous [start, end] index runs where risk_hot is True."""
    episodes: list[tuple[int, int]] = []
    n = int(risk_hot.shape[0])
    i = 0
    while i < n:
        if risk_hot[i]:
            j = i
            while j + 1 < n and risk_hot[j + 1]:
                j += 1
            episodes.append((i, j))
            i = j + 1
        else:
            i += 1
    return episodes


def _segment_rows(
    risk_hot: np.ndarray, episodes: list[tuple[int, int]]
) -> np.ndarray:
    """Assign each row a segment code (precedence episode > precursor > recovery > bg)."""
    n = int(risk_hot.shape[0])
    seg = np.zeros(n, dtype=np.int8)  # background
    # recovery first (lowest non-bg precedence)
    for _s, e in episodes:
        for d in range(1, RECOVERY_TICKS + 1):
            idx = e + d
            if idx >= n:
                break
            if not risk_hot[idx] and seg[idx] == SEG_BACKGROUND:
                seg[idx] = SEG_RECOVERY
    # precursor (overrides recovery)
    for s, _e in episodes:
        for d in range(PRECURSOR_MIN_TICKS, PRECURSOR_MAX_TICKS + 1):
            idx = s - d
            if idx < 0:
                continue
            if not risk_hot[idx] and seg[idx] in (SEG_BACKGROUND, SEG_RECOVERY):
                seg[idx] = SEG_PRECURSOR
    # episode rows last (highest precedence)
    for s, e in episodes:
        seg[s : e + 1] = SEG_ONSET
    return seg


def _waterfill(lens: np.ndarray, total: float, cap: float) -> np.ndarray:
    """Distribute `total` mass across items proportional to `lens`, each capped at `cap`."""
    lens = np.asarray(lens, dtype=np.float64)
    n = lens.shape[0]
    masses = np.zeros(n, dtype=np.float64)
    capped = np.zeros(n, dtype=bool)
    for _ in range(n + 1):
        active = ~capped
        active_len = lens[active].sum()
        remaining = total - masses[capped].sum()
        if active_len <= 0 or remaining <= 1e-12:
            break
        prop = np.zeros(n, dtype=np.float64)
        prop[active] = remaining * lens[active] / active_len
        exceed = active & (prop > cap)
        if not exceed.any():
            masses[active] = prop[active]
            break
        masses[exceed] = cap
        capped[exceed] = True
    return masses


def compute_aux_and_weights(shard: Any, contact_idx: int, hp_idx: int) -> dict[str, Any]:
    """Compute aux labels, masks, segments and per-row weights aligned to shard rows."""
    hp = np.asarray(shard["global_features"], dtype=np.float64)[:, hp_idx]  # [N]
    tv = np.asarray(shard["temporal_valid"], dtype=bool)
    valid = np.asarray(shard["valid"], dtype=bool)
    eligible = valid & tv
    tick_risk = _tick_max_risk(shard, contact_idx)  # [N]
    n = int(hp.shape[0])
    row_idx = np.arange(n)

    # Sliding horizon (rows t+1 .. t+10): future min hp, future max risk, all-tv.
    future_min_hp = np.full(n, np.inf)
    future_max_risk = np.full(n, -np.inf)
    window_all_tv = np.ones(n, dtype=bool)
    for k in range(1, HORIZON_TICKS + 1):
        idx = row_idx + k
        in_range = idx < n
        src = idx[in_range]
        dst = row_idx[in_range]
        future_min_hp[dst] = np.minimum(future_min_hp[dst], hp[src])
        future_max_risk[dst] = np.maximum(future_max_risk[dst], tick_risk[src])
        window_all_tv[dst] &= tv[src]
    full_window = (row_idx + HORIZON_TICKS) < n
    horizon_mask = full_window & window_all_tv  # both aux labels share this mask

    aux_damage = np.zeros(n, dtype=np.int8)
    aux_damage[horizon_mask] = (future_min_hp[horizon_mask] < hp[horizon_mask]).astype(np.int8)
    aux_margin = np.ones(n, dtype=np.float32)
    aux_margin[horizon_mask] = (1.0 - future_max_risk[horizon_mask]).astype(np.float32)

    # Segments + episodes.
    risk_hot = tick_risk >= RISK_THRESHOLD
    episodes = _find_episodes(risk_hot)
    seg = _segment_rows(risk_hot, episodes)

    # Weights over eligible rows only; target mass ratio 45/30/15/10.
    weight = np.zeros(n, dtype=np.float64)
    total_mass = float(eligible.sum())
    seg_eligible_counts = {s: int(((seg == s) & eligible).sum()) for s in SEG_TARGET_MASS}
    for s, ratio in SEG_TARGET_MASS.items():
        rows = (seg == s) & eligible
        n_s = int(rows.sum())
        if n_s == 0:
            continue
        weight[rows] = (ratio * total_mass) / n_s

    # Per-episode cap inside the onset segment (cap = 2x mean episode mass).
    cap_value = None
    if episodes:
        ep_elig_lens = np.array(
            [int(eligible[s : e + 1].sum()) for s, e in episodes], dtype=np.float64
        )
        active_eps = ep_elig_lens > 0
        n_active = int(active_eps.sum())
        target_onset = SEG_TARGET_MASS[SEG_ONSET] * total_mass
        if n_active > 0 and target_onset > 0:
            cap_value = 2.0 * (target_onset / n_active)
            masses = _waterfill(ep_elig_lens[active_eps], target_onset, cap_value)
            act_idx = np.where(active_eps)[0]
            for local_i, ep_i in enumerate(act_idx):
                s, e = episodes[ep_i]
                elig_rows = np.zeros(n, dtype=bool)
                elig_rows[s : e + 1] = eligible[s : e + 1]
                le = int(elig_rows.sum())
                if le > 0:
                    weight[elig_rows] = masses[local_i] / le

    # Renormalize so mean weight over eligible rows is exactly 1.0 (ratios preserved).
    elig_mass = float(weight[eligible].sum())
    if elig_mass > 0:
        weight[eligible] *= total_mass / elig_mass
    weight = weight.astype(np.float32)

    # Reporting stats.
    damage_rate = (
        float(aux_damage[horizon_mask].mean()) if int(horizon_mask.sum()) else 0.0
    )
    margin_mean = (
        float(aux_margin[horizon_mask].mean()) if int(horizon_mask.sum()) else 1.0
    )
    seg_weight_mean = {}
    seg_mass_fraction = {}
    elig_total_mass = float(weight[eligible].sum()) or 1.0
    for s in SEG_TARGET_MASS:
        rows = (seg == s) & eligible
        seg_weight_mean[SEG_NAMES[s]] = (
            float(weight[rows].mean()) if int(rows.sum()) else 0.0
        )
        seg_mass_fraction[SEG_NAMES[s]] = round(float(weight[rows].sum()) / elig_total_mass, 4)
    elig_w = weight[eligible]
    weight_summary = {
        "min": float(elig_w.min()) if elig_w.size else 0.0,
        "mean": float(elig_w.mean()) if elig_w.size else 0.0,
        "median": float(np.median(elig_w)) if elig_w.size else 0.0,
        "p99": float(np.percentile(elig_w, 99)) if elig_w.size else 0.0,
        "max": float(elig_w.max()) if elig_w.size else 0.0,
    }

    return {
        "arrays": {
            "aux_damage": aux_damage,
            "aux_damage_mask": horizon_mask.astype(bool),
            "aux_margin": aux_margin,
            "aux_margin_mask": horizon_mask.astype(bool),
        },
        "weight_arrays": {
            "weight": weight,
            "segment": seg.astype(np.int8),
        },
        "stats": {
            "rows": n,
            "eligible_rows": int(eligible.sum()),
            "episodes": len(episodes),
            "onset_cap_value": cap_value,
            "aux": {
                "horizon_valid_rows": int(horizon_mask.sum()),
                "aux_damage_base_rate": round(damage_rate, 6),
                "aux_margin_mean": round(margin_mean, 6),
            },
            "segment_eligible_counts": {SEG_NAMES[s]: c for s, c in seg_eligible_counts.items()},
            "segment_all_counts": {
                SEG_NAMES[s]: int((seg == s).sum()) for s in SEG_TARGET_MASS
            },
            "segment_weight_mean": seg_weight_mean,
            "segment_mass_fractions": seg_mass_fraction,
            "weight_summary": weight_summary,
        },
    }


# --------------------------------------------------------------------------- #
# Build
# --------------------------------------------------------------------------- #
def load_included_runs(audit_path: Path) -> tuple[list[str], dict[str, Any]]:
    data = json.loads(Path(audit_path).read_text(encoding="utf-8"))
    included = list(data.get("included_runs", []))
    audit_by_run = {r["run_id"]: r for r in data.get("runs", [])}
    return included, audit_by_run


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

        # Stage C: aux + weights from the built shard.
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
        entry["student_control"] = {
            "student_control_fraction": audit.get("student_control_fraction"),
            "student_ticks": audit.get("student_ticks"),
            "fallback_ticks": audit.get("fallback_ticks"),
            "clamp_count": audit.get("clamp_count"),
            "latency_ms": audit.get("latency_ms"),
            "wave_reached": audit.get("wave_reached"),
            "result": audit.get("result"),
        }
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

    # Aggregate segment / aux stats over eligible rows.
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
    # Achieved weight-mass fractions (the 45/30/15/10 target lives here, not in row counts).
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

    # Gates.
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
    ]
    overall = "PASS" if all(g["status"] == "PASS" for g in gates) else "FAIL"

    head = git_head_commit(ROOT)
    dataset_bytes = sum(e["shard_bytes"] for e in run_entries)

    state = {}
    if STATE_PATH.exists():
        state = json.loads(STATE_PATH.read_text(encoding="utf-8"))

    manifest = {
        "dataset_id": "combat_dagger_r1",
        "schema_id": schema["schema_id"],
        "observation_schema_hash": schema["_schema_hash"],
        "source_capture_schema_hash": schema["source_capture_schema_hash"],
        "encoder_path": ENCODER_REL,
        "builder_script": BUILDER_REL,
        "reused_pipeline": "scripts/wp2_build_combat_obs_v1.py::build_run",
        "repo_head_commit": head,
        "runs_root": str(runs_root),
        "run_count": len(run_ids),
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
        "gates": gates,
        "overall_status": overall,
        "runs": run_entries,
    }

    report = {
        "dataset_id": "combat_dagger_r1",
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
        "gates": gates,
        "overall_status": overall,
        "runs": [
            {
                "run_id": e["run_id"],
                "shard_file": e["shard_file"],
                "shard_sha256": e["shard_sha256"],
                "aux_sha256": e["aux_sha256"],
                "weights_sha256": e["weights_sha256"],
                "counts": e["counts"],
                "corrective_stats": e["corrective_stats"],
                "student_control": e["student_control"],
            }
            for e in run_entries
        ],
    }
    return {"manifest": manifest, "report": report, "wall": wall}


# --------------------------------------------------------------------------- #
# Report rendering
# --------------------------------------------------------------------------- #
def render_md(report: dict[str, Any], manifest_sha: str) -> str:
    lines: list[str] = []
    lines.append("# combat_dagger_r1 corrective dataset report")
    lines.append("")
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
        "| run_id | rows | valid&temporal | episodes | dmg_rate | ctrl_frac | wave | result | shard sha (16) |"
    )
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for e in report["runs"]:
        st = e["corrective_stats"]
        sc = e["student_control"]
        lines.append(
            f"| {e['run_id']} | {e['counts']['total']:,} | "
            f"{e['counts']['valid_and_temporal_valid']:,} | {st['episodes']} | "
            f"{st['aux']['aux_damage_base_rate']} | {sc['student_control_fraction']} | "
            f"{sc['wave_reached']} | {sc['result']} | {e['shard_sha256'][:16]} |"
        )
    lines.append("")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> int:
    parser = argparse.ArgumentParser(description="Build combat_dagger_r1 corrective dataset")
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
            f"Building combat_dagger_r1 over {len(included)} runs -> {dataset_dir} "
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
        print(f"Manifest sha256: {manifest_sha}", flush=True)
        print(f"Manifest: {manifest_path}", flush=True)
        return 0 if report["overall_status"] == "PASS" else 1
    except (FileNotFoundError, KeyError, ValueError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr, flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
