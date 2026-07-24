"""WP2 DAgger-holdout offline evaluation (Case A: student-visited distribution).

Evaluates three checkpoints on the DAGGER HOLDOUT rows -- the deterministic 10%
of combat_dagger_r1 that was carved out (seed 20260724) and excluded from
training of BOTH bc_v2 candidates. Each row's label is teacher.action (the
dataset action label). Each model is standardized with ITS OWN normalization
manifest (bc_v1 -> its own; bc_v2_a / bc_v2_b -> the composite-train manifest),
each verified by sha256 against its registry before loading.

Models:
  * bc_v1_s1_full  best.pt          (own normalization manifest)
  * bc_v2_a_s1     best.pt          (composite-train manifest)
  * bc_v2_b_s1     best.pt (exported base; composite-train manifest)

Baselines on the identical holdout rows:
  * copy_previous  -- unnormalized previous_action columns (globals idx 15,16)
  * mean_direction -- bc_v1 registry's fitted circular-mean direction

The holdout split is reproduced by importing the training-stage loader
(load_composite_dataset), NOT by reimplementing the split. Findings only.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import torch

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from trainer.data.bc_v2_dataset import (  # noqa: E402
    DEFAULT_HOLDOUT_FRAC,
    DEFAULT_HOLDOUT_SEED,
    load_composite_dataset,
)
from trainer.imitation.bc_training import (  # noqa: E402
    RISK_BIN_LABELS,
    WAVE_BAND_LABELS,
    _build_device_split,
    evaluate_predictions,
    load_checkpoint,
    resolve_device,
)
from trainer.evaluation.bc_offline import (  # noqa: E402
    build_policy_config_from_registry,
    load_normalization_from_manifest,
    load_registry,
    verify_sha256,
)
from trainer.models.bc_policy_v1 import BCPolicyV1  # noqa: E402

EXPECTED_HOLDOUT_N = 7887

# combat_obs_v1 paths + configs come from the resolved config (shared across
# all three registries; identical dataset/split/input/schema).
REGISTRY_DIR = REPO_ROOT / "models" / "registry"
REPORTS_DIR = REPO_ROOT / "reports" / "wp2"

MODEL_SPECS = (
    ("bc_v1_s1_full", "best"),
    ("bc_v2_a_s1", "best"),
    ("bc_v2_b_s1", "best"),  # best.pt IS the exported BCPolicyV1-loadable base
)

MAG_EPS = 0.01
BATCH_SIZE = 4096


def log(msg: str) -> None:
    print(msg, flush=True)


@torch.no_grad()
def _predict(model: BCPolicyV1, dsplit, group_names, batch_size: int) -> torch.Tensor:
    model.eval()
    n = dsplit.size
    device = dsplit.globals.device
    preds = []
    for start in range(0, n, batch_size):
        end = min(start + batch_size, n)
        idx = torch.arange(start, end, device=device)
        g = dsplit.globals.index_select(0, idx)
        ent = {grp: dsplit.entities[grp].index_select(0, idx) for grp in group_names}
        msk = {grp: dsplit.masks[grp].index_select(0, idx) for grp in group_names}
        preds.append(model(g, ent, msk))
    return torch.cat(preds, dim=0)


def _stratify(pred, target, strata, n_bins, labels) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    for b in range(n_bins):
        sel = strata == b
        if int(sel.sum().item()) == 0:
            out[labels[b]] = {"n": 0}
        else:
            out[labels[b]] = evaluate_predictions(pred[sel], target[sel], MAG_EPS)
    return out


def _all_strata(pred, target, wave_band, risk_bin) -> dict[str, Any]:
    return {
        "overall": evaluate_predictions(pred, target, MAG_EPS),
        "by_risk_stratum": _stratify(pred, target, risk_bin, len(RISK_BIN_LABELS), RISK_BIN_LABELS),
        "by_wave_band": _stratify(pred, target, wave_band, len(WAVE_BAND_LABELS), WAVE_BAND_LABELS),
    }


def main() -> int:
    t0 = time.time()
    device = resolve_device("auto")
    log(f"[dagger-eval] device={device}")

    # -- Reproduce the training-stage holdout split (import, do not reimplement).
    # Pull the resolved dataset/config paths from the bc_v2_a registry (identical
    # across the three; base dataset + split/input/schema are shared).
    ref_registry = load_registry(REGISTRY_DIR / "bc_v2_a_s1.json")
    rc = ref_registry["resolved_config"]
    dagger_dir = Path(ref_registry["bc_v2_provenance"]["dagger_dataset_dir"])

    log(
        f"[dagger-eval] loading composite dataset (holdout_frac={DEFAULT_HOLDOUT_FRAC}, "
        f"holdout_seed={DEFAULT_HOLDOUT_SEED})"
    )
    composite = load_composite_dataset(
        rc["dataset_dir"], dagger_dir,
        rc["split_config"], rc["input_config"], rc["schema"],
    )
    holdout = composite.aux_holdout
    n_holdout = holdout.size
    log(
        f"[dagger-eval] holdout rows n={n_holdout} "
        f"(registry n_dagger_holdout={composite.n_dagger_holdout})"
    )

    # -- Sanity: row count + split reproduction ------------------------------
    anomalies: list[str] = []
    if n_holdout != EXPECTED_HOLDOUT_N:
        anomalies.append(
            f"holdout row count {n_holdout} != expected {EXPECTED_HOLDOUT_N}"
        )
    if composite.n_dagger_holdout != n_holdout:
        anomalies.append(
            f"aux_holdout.size {n_holdout} != n_dagger_holdout {composite.n_dagger_holdout}"
        )

    # Cross-check the exact holdout ROWS reproduce training by matching the
    # holdout aux base rates stored in each bc_v2 registry (these were computed
    # over this identical holdout row set at training time).
    hd_mask = composite.holdout_aux_damage_mask.astype(bool)
    hm_mask = composite.holdout_aux_margin_mask.astype(bool)
    holdout_damage_rate = float(composite.holdout_aux_damage[hd_mask].mean()) if hd_mask.any() else float("nan")
    holdout_margin_mean = float(composite.holdout_aux_margin[hm_mask].mean()) if hm_mask.any() else float("nan")
    reg_rates = ref_registry["bc_v2_provenance"]["aux_base_rates"]
    exp_damage = float(reg_rates["holdout_aux_damage_base_rate"])
    exp_margin = float(reg_rates["holdout_aux_margin_mean"])
    if abs(holdout_damage_rate - exp_damage) > 1e-6:
        anomalies.append(
            f"holdout aux_damage base rate {holdout_damage_rate} != registry {exp_damage} "
            "(holdout rows may not reproduce training split)"
        )
    if abs(holdout_margin_mean - exp_margin) > 1e-6:
        anomalies.append(
            f"holdout aux_margin mean {holdout_margin_mean} != registry {exp_margin} "
            "(holdout rows may not reproduce training split)"
        )
    log(
        f"[dagger-eval] split-repro check: aux_damage_rate={holdout_damage_rate:.9f} "
        f"(exp {exp_damage:.9f}) aux_margin_mean={holdout_margin_mean:.9f} (exp {exp_margin:.9f})"
    )

    feature_names = list(composite.global_feature_names)
    group_names = tuple(spec.name for spec in build_policy_config_from_registry(rc, feature_names).group_specs)
    prev_idx = build_policy_config_from_registry(rc, feature_names).prev_action_indices

    # -- Reference split (for strata + baselines; normalization-independent
    #    fields prev_action / risk_bin / wave_band). Use bc_v1's manifest here;
    #    prev_action and strata do not depend on the standardization stats.
    bc_v1_registry = load_registry(REGISTRY_DIR / "bc_v1_s1_full.json")
    bc_v1_ckpt_path = Path(bc_v1_registry["checkpoints"]["best"]["path"])
    bc_v1_norm_path = bc_v1_ckpt_path.parent / "normalization_manifest.json"
    bc_v1_norm = load_normalization_from_manifest(
        bc_v1_norm_path, bc_v1_registry["normalization_manifest_hash"], feature_names
    )
    ref_split = _build_device_split(
        holdout, bc_v1_norm, group_names, prev_idx, device, pin=False
    )
    wave_band = ref_split.wave_band.to(device)
    risk_bin = ref_split.risk_bin.to(device)
    target = ref_split.actions.to(device)

    # -- Per-stratum n (label set) -------------------------------------------
    stratum_n = {
        "overall": int(target.shape[0]),
        "by_risk_stratum": {
            RISK_BIN_LABELS[b]: int((risk_bin == b).sum().item()) for b in range(len(RISK_BIN_LABELS))
        },
        "by_wave_band": {
            WAVE_BAND_LABELS[b]: int((wave_band == b).sum().item()) for b in range(len(WAVE_BAND_LABELS))
        },
    }

    # -- Evaluate the three checkpoints --------------------------------------
    model_results: dict[str, Any] = {}
    for run_name, ckpt_kind in MODEL_SPECS:
        registry = load_registry(REGISTRY_DIR / f"{run_name}.json")
        ckpt_entry = registry["checkpoints"][ckpt_kind]
        ckpt_path = Path(ckpt_entry["path"])
        sha = verify_sha256(ckpt_path, ckpt_entry["sha256"], f"{run_name}:{ckpt_kind} checkpoint")
        log(f"[dagger-eval] {run_name}: checkpoint sha256 verified ({sha[:16]}...)")

        norm_path = ckpt_path.parent / "normalization_manifest.json"
        normalization = load_normalization_from_manifest(
            norm_path, registry["normalization_manifest_hash"], feature_names
        )
        policy_config = build_policy_config_from_registry(registry["resolved_config"], feature_names)
        model = BCPolicyV1(policy_config)
        load_checkpoint(ckpt_path, model)
        model.to(device).eval()

        dsplit = _build_device_split(holdout, normalization, group_names, prev_idx, device, pin=False)
        pred = _predict(model, dsplit, group_names, BATCH_SIZE)
        tgt = dsplit.actions.to(pred.device)

        res = _all_strata(pred, tgt, dsplit.wave_band.to(pred.device), dsplit.risk_bin.to(pred.device))
        res["checkpoint_path"] = str(ckpt_path)
        res["checkpoint_sha256"] = sha
        res["normalization_manifest"] = str(norm_path)
        res["normalization_manifest_hash"] = str(registry["normalization_manifest_hash"]).upper()
        model_results[run_name] = res
        log(
            f"[dagger-eval] {run_name}: overall median={res['overall']['median_angular_error_deg']:.3f}deg "
            f"mean={res['overall']['mean_angular_error_deg']:.3f}deg cos={res['overall']['mean_cosine']:.4f}"
        )

    # -- Baselines on the identical rows -------------------------------------
    # copy_previous: unnormalized previous_action columns (globals idx 15,16).
    prev_pred = ref_split.prev_action.to(device)
    cp_res = _all_strata(prev_pred, target, wave_band, risk_bin)

    # mean_direction: bc_v1 registry's fitted circular-mean direction (constant).
    mean_dir = bc_v1_registry["baselines"]["mean_direction"]["direction"]
    mean_vec = torch.tensor(mean_dir, dtype=target.dtype, device=device)
    mean_pred = mean_vec.unsqueeze(0).expand(target.shape[0], 2).contiguous()
    md_res = _all_strata(mean_pred, target, wave_band, risk_bin)
    md_res["direction"] = [float(mean_dir[0]), float(mean_dir[1])]

    baselines = {"copy_previous": cp_res, "mean_direction": md_res}
    log(
        f"[dagger-eval] baseline copy_previous overall median="
        f"{cp_res['overall']['median_angular_error_deg']:.3f}deg mean={cp_res['overall']['mean_angular_error_deg']:.3f}deg"
    )
    log(
        f"[dagger-eval] baseline mean_direction overall median="
        f"{md_res['overall']['median_angular_error_deg']:.3f}deg mean={md_res['overall']['mean_angular_error_deg']:.3f}deg"
    )

    payload = {
        "report": "wp2_dagger_holdout_eval",
        "case": "A (student-visited deployment distribution: dagger holdout rows)",
        "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "device": str(device),
        "mag_eps": MAG_EPS,
        "holdout": {
            "n": n_holdout,
            "expected_n": EXPECTED_HOLDOUT_N,
            "n_dagger_holdout_registry": composite.n_dagger_holdout,
            "holdout_frac": DEFAULT_HOLDOUT_FRAC,
            "holdout_seed": DEFAULT_HOLDOUT_SEED,
            "dagger_dataset_dir": str(dagger_dir),
            "dagger_manifest_hash": composite.dagger_manifest_hash,
            "base_manifest_hash": composite.base_manifest_hash,
            "split_reproduction_check": {
                "holdout_aux_damage_base_rate": holdout_damage_rate,
                "registry_holdout_aux_damage_base_rate": exp_damage,
                "holdout_aux_margin_mean": holdout_margin_mean,
                "registry_holdout_aux_margin_mean": exp_margin,
                "reproduces_training_split": len(anomalies) == 0,
            },
        },
        "stratum_n": stratum_n,
        "label": "teacher.action (dataset action label)",
        "models": model_results,
        "baselines": baselines,
        "anomalies": anomalies,
    }

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    json_path = REPORTS_DIR / "dagger_holdout_eval.json"
    md_path = REPORTS_DIR / "dagger_holdout_eval.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    write_markdown(md_path, payload)
    log(f"[dagger-eval] wrote {json_path}")
    log(f"[dagger-eval] wrote {md_path}")

    if anomalies:
        log("[dagger-eval] ANOMALIES:")
        for a in anomalies:
            log(f"  - {a}")
    else:
        log("[dagger-eval] no anomalies")
    log(f"[dagger-eval] done in {time.time() - t0:.1f}s")
    return 0


# ---------------------------------------------------------------------------
# Markdown report
# ---------------------------------------------------------------------------
def _fmt(v: Any, spec: str = ".3f") -> str:
    if v is None:
        return "-"
    if isinstance(v, float) and v != v:
        return "nan"
    try:
        return format(float(v), spec)
    except (TypeError, ValueError):
        return str(v)


def _row(label: str, m: dict[str, Any]) -> str:
    if m.get("n", 0) == 0:
        return f"| {label} | 0 | - | - | - | - |"
    return (
        f"| {label} | {m.get('n', '-')} | {_fmt(m.get('median_angular_error_deg'), '.3f')} "
        f"| {_fmt(m.get('mean_angular_error_deg'), '.3f')} | {_fmt(m.get('mean_cosine'), '.4f')} "
        f"| {_fmt(m.get('mean_abs_magnitude_error'), '.4f')} |"
    )


_HEADER = (
    "| entry | n | median ang deg | mean ang deg | mean cosine | mean |mag err| |\n"
    "|---|---|---|---|---|---|"
)

_ALL_ENTRIES = (
    ("bc_v1_s1_full", "model"),
    ("bc_v2_a_s1", "model"),
    ("bc_v2_b_s1", "model"),
    ("copy_previous", "baseline"),
    ("mean_direction", "baseline"),
)


def _entry_block(payload: dict[str, Any], name: str, kind: str, key: str) -> dict[str, Any]:
    src = payload["models"] if kind == "model" else payload["baselines"]
    return src[name][key]


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines: list[str] = []
    h = payload["holdout"]
    lines.append("# WP2 DAgger-holdout offline evaluation (Case A)")
    lines.append("")
    lines.append(
        f"Generated {payload['generated']} - device `{payload['device']}` - "
        f"mag_eps {payload['mag_eps']}. Findings only."
    )
    lines.append("")
    lines.append(
        f"Case A = student-visited deployment distribution: the deterministic 10% "
        f"dagger holdout (seed {h['holdout_seed']}, frac {h['holdout_frac']}), excluded "
        f"from training of both bc_v2 candidates. Label = {payload['label']}. Each model "
        "standardized with its own normalization manifest (bc_v1 -> own; bc_v2_a/bc_v2_b "
        "-> composite-train)."
    )
    lines.append("")
    lines.append(f"Holdout rows: n = {h['n']} (expected {h['expected_n']}, registry n_dagger_holdout {h['n_dagger_holdout_registry']}).")
    src = h["split_reproduction_check"]
    lines.append("")
    lines.append(
        f"Split reproduction: holdout aux_damage base rate {_fmt(src['holdout_aux_damage_base_rate'], '.9f')} "
        f"(registry {_fmt(src['registry_holdout_aux_damage_base_rate'], '.9f')}), aux_margin mean "
        f"{_fmt(src['holdout_aux_margin_mean'], '.9f')} (registry {_fmt(src['registry_holdout_aux_margin_mean'], '.9f')}) "
        f"-> reproduces training split: {src['reproduces_training_split']}."
    )
    lines.append("")

    # -- overall comparison --------------------------------------------------
    lines.append("## Overall (all holdout rows)")
    lines.append("")
    lines.append(_HEADER)
    for name, kind in _ALL_ENTRIES:
        m = _entry_block(payload, name, kind, "overall")
        tag = name if kind == "model" else f"{name} (baseline)"
        lines.append(_row(tag, m))
    lines.append("")

    # -- per risk stratum ----------------------------------------------------
    lines.append("## By risk stratum")
    lines.append("")
    for label in payload["stratum_n"]["by_risk_stratum"]:
        lines.append(f"### risk {label} (n={payload['stratum_n']['by_risk_stratum'][label]})")
        lines.append("")
        lines.append(_HEADER)
        for name, kind in _ALL_ENTRIES:
            m = _entry_block(payload, name, kind, "by_risk_stratum").get(label, {"n": 0})
            tag = name if kind == "model" else f"{name} (baseline)"
            lines.append(_row(tag, m))
        lines.append("")

    # -- per wave band -------------------------------------------------------
    lines.append("## By wave band")
    lines.append("")
    for label in payload["stratum_n"]["by_wave_band"]:
        lines.append(f"### wave {label} (n={payload['stratum_n']['by_wave_band'][label]})")
        lines.append("")
        lines.append(_HEADER)
        for name, kind in _ALL_ENTRIES:
            m = _entry_block(payload, name, kind, "by_wave_band").get(label, {"n": 0})
            tag = name if kind == "model" else f"{name} (baseline)"
            lines.append(_row(tag, m))
        lines.append("")

    # -- provenance ----------------------------------------------------------
    lines.append("## Checkpoint provenance (sha256 verified against registry)")
    lines.append("")
    lines.append("| model | checkpoint | sha256 | normalization manifest hash |")
    lines.append("|---|---|---|---|")
    for name in ("bc_v1_s1_full", "bc_v2_a_s1", "bc_v2_b_s1"):
        m = payload["models"][name]
        lines.append(
            f"| {name} | `{Path(m['checkpoint_path']).name}` | `{m['checkpoint_sha256'][:16]}...` "
            f"| `{m['normalization_manifest_hash'][:16]}...` |"
        )
    lines.append("")
    if payload["anomalies"]:
        lines.append("## Anomalies")
        lines.append("")
        for a in payload["anomalies"]:
            lines.append(f"- {a}")
        lines.append("")
    else:
        lines.append("No anomalies.")
        lines.append("")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
