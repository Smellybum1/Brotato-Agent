"""Offline behavior-cloning evaluation for WP2 M2 (Stage D, architecture §8).

Independently re-computes every validation metric for one or more trained BC
runs, straight from the frozen ``combat_obs_v1`` dataset and each run's saved
checkpoint + normalization manifest. It NEVER trusts the ``metrics.jsonl``
numbers emitted during training: it rebuilds the model from the registry's
resolved config, loads the checkpoint (verifying its sha256), standardizes with
the run's saved normalization manifest (verifying ITS hash), and recomputes
overall / per-wave-band / per-risk-stratum / per-validation-run metrics plus the
two frozen sanity baselines (mean-direction, copy-previous).

The pure numeric core (risk stratum, wave bands, baselines, nan-aware
reductions, agreement metrics, checkpoint round-trip) is reused verbatim from
:mod:`trainer.imitation.bc_training` and :mod:`trainer.models.bc_policy_v1` —
this module owns only the *evaluation* concern (verification, per-run stratum,
seed variance, inter-seed agreement, report writing) so it can be unit-tested on
CPU with tiny synthetic data.

Findings only: qualification / recommendation is the primary's, not this
script's.
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import torch
import yaml
from torch import Tensor

from trainer.data.bc_dataset import (
    NormalizationStats,
    load_bc_dataset,
)
from trainer.imitation.bc_training import (
    REPO_ROOT,
    _build_device_split,
    _sha256_file,
    circular_mean_direction,
    evaluate_predictions,
    load_checkpoint,
    resolve_device,
    RISK_BIN_LABELS,
    WAVE_BAND_LABELS,
)
from trainer.models.bc_policy_v1 import (
    BCPolicyConfig,
    BCPolicyV1,
    angular_error_deg,
    bc_loss,
)

REGISTRY_DIR = REPO_ROOT / "models" / "registry"
REPORTS_DIR = REPO_ROOT / "reports" / "wp2"

PREV_ACTION_X_NAME = "previous_action_x"
PREV_ACTION_Y_NAME = "previous_action_y"

# Key scalar metrics summarized across seeds (multi-run mode).
SEED_VARIANCE_KEYS: tuple[str, ...] = (
    "val_loss",
    "median_angular_error_deg",
    "mean_angular_error_deg",
    "mean_cosine",
    "mean_abs_magnitude_error",
    "saturation_fraction",
)


class BCOfflineEvalError(RuntimeError):
    """Raised when an offline evaluation cannot proceed safely."""


# ---------------------------------------------------------------------------
# Registry + verification
# ---------------------------------------------------------------------------
def resolve_registry_path(name_or_path: str | Path, registry_dir: Path = REGISTRY_DIR) -> Path:
    """Resolve a registry manifest path or a bare run name under ``registry_dir``."""
    candidate = Path(name_or_path)
    if candidate.is_file():
        return candidate
    stem = candidate.name
    if not stem.endswith(".json"):
        stem = f"{stem}.json"
    resolved = registry_dir / stem
    if resolved.is_file():
        return resolved
    raise BCOfflineEvalError(
        f"registry not found: {name_or_path!r} (looked at {candidate} and {resolved})"
    )


def load_registry(path: str | Path) -> dict[str, Any]:
    """Load a registry manifest JSON; hard error if malformed."""
    path = Path(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise BCOfflineEvalError(f"{path.name} is not a JSON object")
    for key in ("run_name", "resolved_config", "checkpoints", "schema_hash", "split_id"):
        if key not in data:
            raise BCOfflineEvalError(f"registry {path.name} missing required key {key!r}")
    return data


def verify_sha256(path: str | Path, expected: str, label: str) -> str:
    """Verify a file's sha256 (upper hex) against ``expected``; hard error on mismatch."""
    path = Path(path)
    if not path.is_file():
        raise BCOfflineEvalError(f"{label} file missing: {path}")
    actual = _sha256_file(path)
    if actual != str(expected).upper():
        raise BCOfflineEvalError(
            f"{label} sha256 mismatch for {path}: expected {expected}, got {actual}"
        )
    return actual


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


# ---------------------------------------------------------------------------
# Model reconstruction (pure, testable)
# ---------------------------------------------------------------------------
def build_policy_config_from_registry(
    resolved_config: dict[str, Any],
    global_feature_names: list[str],
) -> BCPolicyConfig:
    """Rebuild the model config the run trained with.

    ``global_dim`` and ``prev_action_indices`` are honored from the resolved
    feature names (the prev-action columns are located by NAME, never assumed to
    be the model default); the previous-action dropout probability comes from the
    resolved config snapshot (inert in eval, but kept faithful to the run).
    """
    names = list(global_feature_names)
    try:
        ix = names.index(PREV_ACTION_X_NAME)
        iy = names.index(PREV_ACTION_Y_NAME)
    except ValueError as exc:
        raise BCOfflineEvalError(
            f"prev-action feature missing from resolved globals: {exc}"
        )
    dropout_p = float(resolved_config.get("previous_action_dropout_p", 0.0))
    return BCPolicyConfig(
        global_dim=len(names),
        previous_action_dropout_p=dropout_p,
        prev_action_indices=(ix, iy),
    )


def load_normalization_from_manifest(
    manifest_path: str | Path,
    expected_hash: str,
    feature_names: list[str],
) -> NormalizationStats:
    """Load the run's saved normalization manifest, verify its hash, and return
    a :class:`NormalizationStats`. The saved feature names must match the ones
    resolved from the dataset (order + identity)."""
    manifest_path = Path(manifest_path)
    if not manifest_path.is_file():
        raise BCOfflineEvalError(f"normalization manifest missing: {manifest_path}")
    raw = manifest_path.read_bytes()
    actual = _sha256_bytes(raw)
    if actual != str(expected_hash).upper():
        raise BCOfflineEvalError(
            f"normalization manifest sha256 mismatch: expected {expected_hash}, got {actual}"
        )
    payload = json.loads(raw.decode("utf-8"))
    saved_names = [str(n) for n in payload.get("global_feature_names", [])]
    if saved_names != list(feature_names):
        raise BCOfflineEvalError(
            "normalization manifest feature names disagree with the resolved dataset"
        )
    mean = np.asarray(payload["mean"], dtype=np.float32)
    std = np.asarray(payload["std"], dtype=np.float32)
    if mean.shape != (len(saved_names),) or std.shape != (len(saved_names),):
        raise BCOfflineEvalError("normalization manifest mean/std length mismatch")
    return NormalizationStats(
        feature_names=saved_names,
        mean=mean,
        std=std,
        split_id=str(payload.get("split_id", "unknown")),
        schema_hash=str(payload.get("schema_hash", "")),
        input_config_hash=str(payload.get("input_config_hash", "")),
        split_config_hash=str(payload.get("split_config_hash", "")),
    )


# ---------------------------------------------------------------------------
# Sanity gates (pure, testable)
# ---------------------------------------------------------------------------
def compute_gates(
    model_overall: dict[str, float],
    copy_previous_overall: dict[str, float],
    mean_direction_overall: dict[str, float],
    model_change: dict[str, float],
    copy_previous_change: dict[str, float],
) -> dict[str, Any]:
    """Boolean sanity gates per architecture note §7 (operationalization fixed
    2026-07-24 after the first 3-seed results exposed an ambiguity):

    (a) beat the mean-direction predictor on median AND mean overall validation
        angular error; and
    (b) beat the copy-previous predictor on MEAN overall angular error, AND on
        both median and mean restricted to direction-change frames (teacher
        Δangle ≥ 1° vs the previous tick).

    Beating copy-previous on *overall median* is deliberately NOT a gate: 30.6%
    of labels repeat exactly, where the copier scores 0° by construction, so the
    statistic measures persistence structure, not competence (§7). Lower is
    better throughout; comparisons are strict (a tie does not beat).
    """
    m_med = model_overall["median_angular_error_deg"]
    m_mean = model_overall["mean_angular_error_deg"]
    cp_med = copy_previous_overall["median_angular_error_deg"]
    cp_mean = copy_previous_overall["mean_angular_error_deg"]
    md_med = mean_direction_overall["median_angular_error_deg"]
    md_mean = mean_direction_overall["mean_angular_error_deg"]
    m_ch_med = model_change["median_angular_error_deg"]
    m_ch_mean = model_change["mean_angular_error_deg"]
    cp_ch_med = copy_previous_change["median_angular_error_deg"]
    cp_ch_mean = copy_previous_change["mean_angular_error_deg"]

    # (a) mean-direction gate — overall median AND mean.
    beats_mean_direction_median = m_med < md_med
    beats_mean_direction_mean = m_mean < md_mean
    mean_direction_gate = beats_mean_direction_median and beats_mean_direction_mean

    # (b) copy-previous gate — overall mean AND change-frame median/mean.
    beats_copy_previous_mean_overall = m_mean < cp_mean
    beats_copy_previous_median_change = m_ch_med < cp_ch_med
    beats_copy_previous_mean_change = m_ch_mean < cp_ch_mean
    copy_previous_gate = (
        beats_copy_previous_mean_overall
        and beats_copy_previous_median_change
        and beats_copy_previous_mean_change
    )

    return {
        "mean_direction_gate": bool(mean_direction_gate),
        "copy_previous_gate": bool(copy_previous_gate),
        "overall_pass": bool(mean_direction_gate and copy_previous_gate),
        # mean-direction (a)
        "beats_mean_direction_median": bool(beats_mean_direction_median),
        "beats_mean_direction_mean": bool(beats_mean_direction_mean),
        "mean_direction_median_deg": float(md_med),
        "mean_direction_mean_deg": float(md_mean),
        # copy-previous (b)
        "beats_copy_previous_mean_overall": bool(beats_copy_previous_mean_overall),
        "beats_copy_previous_median_change": bool(beats_copy_previous_median_change),
        "beats_copy_previous_mean_change": bool(beats_copy_previous_mean_change),
        "copy_previous_mean_deg": float(cp_mean),
        "model_change_median_deg": float(m_ch_med),
        "model_change_mean_deg": float(m_ch_mean),
        "copy_previous_change_median_deg": float(cp_ch_med),
        "copy_previous_change_mean_deg": float(cp_ch_mean),
        # model overall
        "model_median_deg": float(m_med),
        "model_mean_deg": float(m_mean),
        # informational — NOT a gate (persistence artifact, §7)
        "informational_overall_median": {
            "model_median_deg": float(m_med),
            "copy_previous_median_deg": float(cp_med),
            "note": "not a gate (persistence artifact — see architecture note §7)",
        },
    }


# ---------------------------------------------------------------------------
# Inter-seed agreement (pure, testable)
# ---------------------------------------------------------------------------
def pairwise_pred_agreement(
    pred_a: Tensor,
    pred_b: Tensor,
    mag_eps: float = 0.01,
    valid_mask: Tensor | None = None,
) -> dict[str, float]:
    """Angular difference (degrees) between two aligned prediction sets.

    Only samples where both predictions are non-degenerate (norm > ``mag_eps``)
    are compared; if ``valid_mask`` is given (e.g. teacher-moving samples), it is
    intersected in. Returns median / mean angular difference and the count.
    """
    if pred_a.shape != pred_b.shape:
        raise BCOfflineEvalError("prediction sets must have identical shape")
    ang = angular_error_deg(pred_a, pred_b, mag_eps)  # NaN where |pred_b| <= eps
    both_moving = (pred_a.norm(dim=-1) > mag_eps) & (pred_b.norm(dim=-1) > mag_eps)
    if valid_mask is not None:
        both_moving = both_moving & valid_mask.bool()
    ang = torch.where(both_moving, ang, torch.full_like(ang, float("nan")))
    finite = ang[~torch.isnan(ang)]
    n = int(finite.numel())
    if n == 0:
        return {"median_angular_diff_deg": float("nan"), "mean_angular_diff_deg": float("nan"), "n": 0}
    return {
        "median_angular_diff_deg": float(finite.median().item()),
        "mean_angular_diff_deg": float(finite.mean().item()),
        "n": n,
    }


# ---------------------------------------------------------------------------
# Seed variance (pure, testable)
# ---------------------------------------------------------------------------
def seed_variance_summary(
    per_run_overall: list[dict[str, float]],
    keys: tuple[str, ...] = SEED_VARIANCE_KEYS,
) -> dict[str, dict[str, float]]:
    """mean/std/min/max of each key metric across runs (population std, ddof=0)."""
    out: dict[str, dict[str, float]] = {}
    for key in keys:
        values = np.array(
            [float(m[key]) for m in per_run_overall if key in m and m[key] == m[key]],
            dtype=np.float64,
        )
        if values.size == 0:
            out[key] = {"mean": float("nan"), "std": float("nan"), "min": float("nan"), "max": float("nan"), "n": 0}
            continue
        out[key] = {
            "mean": float(values.mean()),
            "std": float(values.std()),
            "min": float(values.min()),
            "max": float(values.max()),
            "n": int(values.size),
        }
    return out


# ---------------------------------------------------------------------------
# Prediction
# ---------------------------------------------------------------------------
@torch.no_grad()
def _predict(model: BCPolicyV1, dsplit, group_names: tuple[str, ...], batch_size: int) -> Tensor:
    """Deterministic chunked forward pass over a DeviceSplit (fixed chunk order)."""
    model.eval()
    n = dsplit.size
    device = dsplit.globals.device
    preds: list[Tensor] = []
    for start in range(0, n, batch_size):
        end = min(start + batch_size, n)
        idx = torch.arange(start, end, device=device)
        g = dsplit.globals.index_select(0, idx)
        ent = {grp: dsplit.entities[grp].index_select(0, idx) for grp in group_names}
        msk = {grp: dsplit.masks[grp].index_select(0, idx) for grp in group_names}
        preds.append(model(g, ent, msk))
    return torch.cat(preds, dim=0)


def _val_run_metadata(split_config_path: Path) -> dict[str, dict[str, Any]]:
    """run_id -> {outcome, last_wave} from the split config validation entries."""
    try:
        data = yaml.safe_load(split_config_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    out: dict[str, dict[str, Any]] = {}
    for entry in (data or {}).get("validation", []) or []:
        if isinstance(entry, dict) and "run_id" in entry:
            out[str(entry["run_id"])] = {
                "outcome": entry.get("outcome"),
                "last_wave": entry.get("last_wave"),
            }
    return out


# ---------------------------------------------------------------------------
# Single-run evaluation
# ---------------------------------------------------------------------------
@dataclass
class RunEval:
    """One run's independent evaluation result plus its raw val predictions."""

    summary: dict[str, Any]
    predictions: np.ndarray  # [N_val, 2] on CPU (for inter-seed agreement)
    moving_mask: np.ndarray  # [N_val] bool (teacher moving samples)


def evaluate_run(
    registry_path: str | Path,
    *,
    checkpoint: str = "best",
    device: str = "auto",
) -> RunEval:
    """Independently evaluate one registered BC run on its validation split."""
    if checkpoint not in ("best", "last"):
        raise BCOfflineEvalError(f"checkpoint must be 'best' or 'last', got {checkpoint!r}")
    registry_path = Path(registry_path)
    registry = load_registry(registry_path)
    resolved = registry["resolved_config"]
    torch_device = resolve_device(device)

    # -- checkpoint sha256 verification -------------------------------------
    ckpt_entry = registry["checkpoints"].get(checkpoint)
    if not isinstance(ckpt_entry, dict) or "path" not in ckpt_entry or "sha256" not in ckpt_entry:
        raise BCOfflineEvalError(f"registry has no {checkpoint!r} checkpoint entry")
    ckpt_path = Path(ckpt_entry["path"])
    ckpt_sha = verify_sha256(ckpt_path, ckpt_entry["sha256"], f"{checkpoint} checkpoint")

    # -- dataset (independent load + hash verification) ---------------------
    dataset = load_bc_dataset(
        resolved["dataset_dir"], resolved["split_config"],
        resolved["input_config"], resolved["schema"],
    )
    if dataset.schema_hash != str(registry["schema_hash"]).upper():
        raise BCOfflineEvalError(
            f"schema hash mismatch: dataset {dataset.schema_hash} != registry {registry['schema_hash']}"
        )
    if dataset.split_id != str(registry["split_id"]):
        raise BCOfflineEvalError(
            f"split_id mismatch: dataset {dataset.split_id} != registry {registry['split_id']}"
        )
    manifest_bytes = (Path(resolved["dataset_dir"]) / "manifest.json").read_bytes()
    if "dataset_manifest_hash" in registry:
        got = _sha256_bytes(manifest_bytes)
        if got != str(registry["dataset_manifest_hash"]).upper():
            raise BCOfflineEvalError(
                f"dataset manifest hash mismatch: {got} != registry {registry['dataset_manifest_hash']}"
            )

    feature_names = list(dataset.global_feature_names)

    # -- normalization from the run's saved manifest (hash-verified) --------
    norm_manifest_path = ckpt_path.parent / "normalization_manifest.json"
    normalization = load_normalization_from_manifest(
        norm_manifest_path, registry["normalization_manifest_hash"], feature_names
    )

    # -- model reconstruction + checkpoint load -----------------------------
    policy_config = build_policy_config_from_registry(resolved, feature_names)
    model = BCPolicyV1(policy_config)
    payload = load_checkpoint(ckpt_path, model)
    model.to(torch_device).eval()

    group_names = tuple(spec.name for spec in policy_config.group_specs)
    prev_idx = policy_config.prev_action_indices
    mag_eps = float(resolved.get("mag_eps", 0.01))
    batch_size = int(resolved.get("batch_size", 4096))
    lambda_mag = float(resolved.get("lambda_mag", 0.5))
    huber_delta = float(resolved.get("huber_delta", 0.5))

    val_dsplit = _build_device_split(
        dataset.val, normalization, group_names, prev_idx, torch_device, pin=False
    )
    train_dsplit = _build_device_split(
        dataset.train, normalization, group_names, prev_idx, torch_device, pin=False
    )

    pred = _predict(model, val_dsplit, group_names, batch_size)
    target = val_dsplit.actions.to(pred.device)

    loss, comp = bc_loss(pred, target, lambda_mag, huber_delta, mag_eps)
    overall = evaluate_predictions(pred, target, mag_eps)
    overall["val_loss"] = float(loss.detach().cpu().item())
    overall["val_direction_term"] = float(comp["direction_term"].cpu().item())
    overall["val_magnitude_term"] = float(comp["magnitude_term"].cpu().item())

    # -- stratified: wave band + risk stratum -------------------------------
    def _stratify(strata: Tensor, n_bins: int, labels: tuple[str, ...]) -> dict[str, dict[str, float]]:
        out: dict[str, dict[str, float]] = {}
        for b in range(n_bins):
            sel = strata == b
            if int(sel.sum().item()) == 0:
                out[labels[b]] = {"n": 0}
            else:
                out[labels[b]] = evaluate_predictions(pred[sel], target[sel], mag_eps)
        return out

    by_wave_band = _stratify(val_dsplit.wave_band.to(pred.device), len(WAVE_BAND_LABELS), WAVE_BAND_LABELS)
    by_risk_stratum = _stratify(val_dsplit.risk_bin.to(pred.device), len(RISK_BIN_LABELS), RISK_BIN_LABELS)

    # -- per validation run --------------------------------------------------
    run_meta = _val_run_metadata(Path(resolved["split_config"]))
    run_index = torch.from_numpy(dataset.val.run_index.astype(np.int64)).to(pred.device)
    by_val_run: dict[str, dict[str, Any]] = {}
    for ri, run_id in enumerate(dataset.val.run_ids):
        sel = run_index == ri
        if int(sel.sum().item()) == 0:
            continue
        row = evaluate_predictions(pred[sel], target[sel], mag_eps)
        meta = run_meta.get(run_id, {})
        row["outcome"] = meta.get("outcome")
        row["last_wave"] = meta.get("last_wave")
        by_val_run[run_id] = row

    # -- baselines -----------------------------------------------------------
    train_actions = train_dsplit.actions.to(pred.device)
    mean_dir = circular_mean_direction(train_actions, mag_eps)
    mean_pred = mean_dir.unsqueeze(0).expand(target.shape[0], 2).contiguous()
    mean_metrics = evaluate_predictions(mean_pred, target, mag_eps)
    mean_metrics["direction"] = [float(mean_dir[0]), float(mean_dir[1])]
    prev_pred = val_dsplit.prev_action.to(pred.device)
    copy_metrics = evaluate_predictions(prev_pred, target, mag_eps)
    baselines = {"mean_direction": mean_metrics, "copy_previous": copy_metrics}

    # -- direction-change frames (§7 gate operationalization) ---------------
    # Teacher Δangle vs the previous tick, over frames where BOTH the label and
    # the unnormalized previous_action are moving (magnitudes > mag_eps). The
    # copier scores 0° on exact-repeat frames by construction, so the gate is
    # restricted to frames where the teacher actually changed direction.
    target_moving = target.norm(dim=-1) > mag_eps
    prev_moving = prev_pred.norm(dim=-1) > mag_eps
    both_moving = target_moving & prev_moving
    delta = angular_error_deg(prev_pred, target, mag_eps)  # NaN where |target| <= eps
    delta = torch.where(both_moving, delta, torch.full_like(delta, float("nan")))

    def _change_stratum(threshold: float) -> dict[str, Any]:
        sel = both_moving & (delta >= threshold)
        n = int(sel.sum().item())
        if n == 0:
            return {"n": 0, "threshold_deg": threshold}
        model_m = evaluate_predictions(pred[sel], target[sel], mag_eps)
        copy_m = evaluate_predictions(prev_pred[sel], target[sel], mag_eps)
        return {
            "n": n,
            "threshold_deg": threshold,
            "model_median_deg": model_m["median_angular_error_deg"],
            "model_mean_deg": model_m["mean_angular_error_deg"],
            "copy_previous_median_deg": copy_m["median_angular_error_deg"],
            "copy_previous_mean_deg": copy_m["mean_angular_error_deg"],
        }

    change_1 = _change_stratum(1.0)   # the gating stratum
    change_15 = _change_stratum(15.0)  # diagnostic only
    change_frames = {"threshold_1deg": change_1, "threshold_15deg": change_15}

    # Change-frame metric dicts for the gate (median/mean keys), NaN-safe if empty.
    model_change = {
        "median_angular_error_deg": change_1.get("model_median_deg", float("nan")),
        "mean_angular_error_deg": change_1.get("model_mean_deg", float("nan")),
    }
    copy_change = {
        "median_angular_error_deg": change_1.get("copy_previous_median_deg", float("nan")),
        "mean_angular_error_deg": change_1.get("copy_previous_mean_deg", float("nan")),
    }
    gates = compute_gates(overall, copy_metrics, mean_metrics, model_change, copy_change)
    moving_mask = target_moving.detach().cpu().numpy()

    summary = {
        "run_name": registry["run_name"],
        "registry_path": str(registry_path),
        "checkpoint": checkpoint,
        "checkpoint_path": str(ckpt_path),
        "checkpoint_sha256": ckpt_sha,
        "checkpoint_sha256_verified": True,
        "checkpoint_epoch": payload.get("epoch"),
        "seed": registry.get("seed"),
        "smoke": registry.get("smoke"),
        "device": str(torch_device),
        "split_id": dataset.split_id,
        "schema_hash": dataset.schema_hash,
        "normalization_manifest_hash": str(registry["normalization_manifest_hash"]).upper(),
        "global_dim": policy_config.global_dim,
        "prev_action_indices": list(policy_config.prev_action_indices),
        "model_parameters": model.num_parameters(),
        "train_size": dataset.train.size,
        "val_size": dataset.val.size,
        "n_val_runs": len(dataset.val.run_ids),
        "mag_eps": mag_eps,
        "batch_size": batch_size,
        "overall": overall,
        "by_wave_band": by_wave_band,
        "by_risk_stratum": by_risk_stratum,
        "by_val_run": by_val_run,
        "baselines": baselines,
        "change_frames": change_frames,
        "gates": gates,
    }
    return RunEval(summary=summary, predictions=pred.detach().cpu().numpy(), moving_mask=moving_mask)


# ---------------------------------------------------------------------------
# Multi-run orchestration
# ---------------------------------------------------------------------------
def run_offline_eval(
    registry_names: list[str],
    *,
    checkpoint: str = "best",
    device: str = "auto",
    out_tag: str = "eval",
    reports_dir: Path = REPORTS_DIR,
    registry_dir: Path = REGISTRY_DIR,
    log: Any = print,
) -> dict[str, Any]:
    """Evaluate one or more runs, aggregate, and write JSON + Markdown reports."""
    if not registry_names:
        raise BCOfflineEvalError("no registry names/paths given")

    run_evals: list[RunEval] = []
    for name in registry_names:
        path = resolve_registry_path(name, registry_dir)
        log(f"[eval] evaluating {path.name} (checkpoint={checkpoint}) ...")
        run_evals.append(evaluate_run(path, checkpoint=checkpoint, device=device))

    runs = [re.summary for re in run_evals]

    # Seed variance across runs (key overall metrics).
    variance = seed_variance_summary([r["overall"] for r in runs]) if len(runs) > 1 else None

    # Inter-seed pairwise agreement on val predictions (moving samples only).
    agreement: list[dict[str, Any]] = []
    if len(run_evals) > 1:
        n_val = run_evals[0].predictions.shape[0]
        aligned = all(re.predictions.shape[0] == n_val for re in run_evals)
        if aligned:
            base_mask = run_evals[0].moving_mask
            mask_t = torch.from_numpy(base_mask.astype(bool))
            for i in range(len(run_evals)):
                for j in range(i + 1, len(run_evals)):
                    a = torch.from_numpy(run_evals[i].predictions)
                    b = torch.from_numpy(run_evals[j].predictions)
                    agree = pairwise_pred_agreement(a, b, valid_mask=mask_t)
                    agree["run_a"] = runs[i]["run_name"]
                    agree["run_b"] = runs[j]["run_name"]
                    agreement.append(agree)
        else:
            log("[eval] WARNING: val prediction counts differ across runs; skipping inter-seed agreement")

    payload: dict[str, Any] = {
        "report": "bc_offline_eval",
        "out_tag": out_tag,
        "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "checkpoint": checkpoint,
        "device": device,
        "n_runs": len(runs),
        "runs": runs,
        "seed_variance": variance,
        "inter_seed_agreement": agreement,
    }

    reports_dir.mkdir(parents=True, exist_ok=True)
    json_path = reports_dir / f"bc_offline_eval_{out_tag}.json"
    md_path = reports_dir / f"bc_offline_eval_{out_tag}.md"
    write_json_report(json_path, payload)
    write_markdown_report(md_path, payload)
    log(f"[eval] wrote {json_path}")
    log(f"[eval] wrote {md_path}")

    payload["json_path"] = str(json_path)
    payload["md_path"] = str(md_path)
    return payload


# ---------------------------------------------------------------------------
# Report writers
# ---------------------------------------------------------------------------
def write_json_report(path: str | Path, payload: dict[str, Any]) -> None:
    """Write the full evaluation payload to JSON (predictions excluded)."""
    Path(path).write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _fmt(value: Any, spec: str = ".3f") -> str:
    if value is None:
        return "-"
    if isinstance(value, float) and value != value:  # NaN
        return "nan"
    try:
        return format(float(value), spec)
    except (TypeError, ValueError):
        return str(value)


def _metric_row(label: str, m: dict[str, Any]) -> str:
    if m.get("n", 0) == 0:
        return f"| {label} | 0 | - | - | - | - | - |"
    return (
        f"| {label} | {m.get('n', '-')} | {_fmt(m.get('median_angular_error_deg'), '.2f')} "
        f"| {_fmt(m.get('mean_angular_error_deg'), '.2f')} | {_fmt(m.get('mean_cosine'))} "
        f"| {_fmt(m.get('mean_abs_magnitude_error'))} | {_fmt(m.get('saturation_fraction'), '.4f')} |"
    )


_METRIC_HEADER = (
    "| stratum | n | median ang° | mean ang° | cosine | |mag err| | sat frac |\n"
    "|---|---|---|---|---|---|---|"
)


def write_markdown_report(path: str | Path, payload: dict[str, Any]) -> None:
    """Write a human-readable Markdown evaluation report (findings only)."""
    lines: list[str] = []
    lines.append(f"# BC offline evaluation — `{payload['out_tag']}`")
    lines.append("")
    lines.append(
        f"Generated {payload['generated']} · checkpoint `{payload['checkpoint']}` · "
        f"{payload['n_runs']} run(s). Metrics recomputed independently from the frozen "
        "dataset + saved checkpoints (metrics.jsonl not trusted). Findings only."
    )
    lines.append("")

    runs = payload["runs"]

    # -- gate table ----------------------------------------------------------
    lines.append("## Sanity gates")
    lines.append("")
    lines.append(
        "Operationalization per architecture note §7 (fixed 2026-07-24): (a) beat "
        "mean-direction on overall median AND mean angular error; (b) beat "
        "copy-previous on overall MEAN angular error AND on median AND mean "
        "restricted to direction-change frames (teacher Δangle ≥ 1° vs previous "
        "tick). Overall-median vs copy-previous is deliberately NOT a gate "
        "(persistence artifact — 30.6% of labels repeat exactly)."
    )
    lines.append("")
    lines.append(
        "| run | (a) mean-dir gate | (b) copy-prev gate | overall | model med° | model mean° | mean-dir med° | mean-dir mean° | copy mean° (overall) | model chg med° | model chg mean° | copy chg med° | copy chg mean° |"
    )
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in runs:
        g = r["gates"]
        lines.append(
            f"| {r['run_name']} | {'PASS' if g['mean_direction_gate'] else 'FAIL'} "
            f"| {'PASS' if g['copy_previous_gate'] else 'FAIL'} | {'PASS' if g['overall_pass'] else 'FAIL'} "
            f"| {_fmt(g['model_median_deg'], '.2f')} | {_fmt(g['model_mean_deg'], '.2f')} "
            f"| {_fmt(g['mean_direction_median_deg'], '.2f')} | {_fmt(g['mean_direction_mean_deg'], '.2f')} "
            f"| {_fmt(g['copy_previous_mean_deg'], '.2f')} | {_fmt(g['model_change_median_deg'], '.2f')} "
            f"| {_fmt(g['model_change_mean_deg'], '.2f')} | {_fmt(g['copy_previous_change_median_deg'], '.2f')} "
            f"| {_fmt(g['copy_previous_change_mean_deg'], '.2f')} |"
        )
    lines.append("")
    lines.append(
        "Informational — not a gate (persistence artifact — see architecture note §7):"
    )
    lines.append("")
    lines.append("| run | model overall median° | copy-previous overall median° |")
    lines.append("|---|---|---|")
    for r in runs:
        info = r["gates"]["informational_overall_median"]
        lines.append(
            f"| {r['run_name']} | {_fmt(info['model_median_deg'], '.2f')} "
            f"| {_fmt(info['copy_previous_median_deg'], '.2f')} |"
        )
    lines.append("")

    # -- change-frame stratum ------------------------------------------------
    lines.append("## Direction-change frames (§7 gate stratum + ≥15° diagnostic)")
    lines.append("")
    lines.append(
        "Frames where both the teacher label and the unnormalized previous_action "
        "are moving (|a| > mag_eps) and the teacher Δangle ≥ threshold. The ≥1° row "
        "is the gating stratum; ≥15° is diagnostic only."
    )
    lines.append("")
    lines.append(
        "| run | threshold | n | model median° | model mean° | copy-prev median° | copy-prev mean° |"
    )
    lines.append("|---|---|---|---|---|---|---|")
    for r in runs:
        cf = r["change_frames"]
        for key, tag in (("threshold_1deg", "≥1° (gate)"), ("threshold_15deg", "≥15° (diag)")):
            row = cf.get(key, {})
            if row.get("n", 0) == 0:
                lines.append(f"| {r['run_name']} | {tag} | 0 | - | - | - | - |")
            else:
                lines.append(
                    f"| {r['run_name']} | {tag} | {row['n']} "
                    f"| {_fmt(row['model_median_deg'], '.2f')} | {_fmt(row['model_mean_deg'], '.2f')} "
                    f"| {_fmt(row['copy_previous_median_deg'], '.2f')} | {_fmt(row['copy_previous_mean_deg'], '.2f')} |"
                )
    lines.append("")

    # -- overall table -------------------------------------------------------
    lines.append("## Overall validation metrics")
    lines.append("")
    lines.append(
        "| run | seed | n | val_loss | median ang° | mean ang° | cosine | |mag err| | sat frac |"
    )
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for r in runs:
        o = r["overall"]
        lines.append(
            f"| {r['run_name']} | {r.get('seed', '-')} | {o.get('n', '-')} "
            f"| {_fmt(o.get('val_loss'), '.4f')} | {_fmt(o.get('median_angular_error_deg'), '.2f')} "
            f"| {_fmt(o.get('mean_angular_error_deg'), '.2f')} | {_fmt(o.get('mean_cosine'))} "
            f"| {_fmt(o.get('mean_abs_magnitude_error'))} | {_fmt(o.get('saturation_fraction'), '.4f')} |"
        )
    lines.append("")

    # -- baselines -----------------------------------------------------------
    lines.append("## Baselines (per run)")
    lines.append("")
    for r in runs:
        b = r["baselines"]
        lines.append(f"### {r['run_name']}")
        lines.append("")
        lines.append(_METRIC_HEADER)
        lines.append(_metric_row("mean-direction", b["mean_direction"]))
        lines.append(_metric_row("copy-previous", b["copy_previous"]))
        lines.append("")

    # -- strata --------------------------------------------------------------
    for r in runs:
        lines.append(f"## Strata — {r['run_name']}")
        lines.append("")
        lines.append("### By wave band")
        lines.append("")
        lines.append(_METRIC_HEADER)
        for label in WAVE_BAND_LABELS:
            if label in r["by_wave_band"]:
                lines.append(_metric_row(label, r["by_wave_band"][label]))
        lines.append("")
        lines.append("### By risk stratum")
        lines.append("")
        lines.append(_METRIC_HEADER)
        for label in RISK_BIN_LABELS:
            if label in r["by_risk_stratum"]:
                lines.append(_metric_row(label, r["by_risk_stratum"][label]))
        lines.append("")
        lines.append("### By validation run")
        lines.append("")
        lines.append(
            "| run_id | outcome | last_wave | n | median ang° | mean ang° | cosine | |mag err| | sat frac |"
        )
        lines.append("|---|---|---|---|---|---|---|---|---|")
        for run_id, m in r["by_val_run"].items():
            lines.append(
                f"| {run_id} | {m.get('outcome', '-')} | {m.get('last_wave', '-')} | {m.get('n', '-')} "
                f"| {_fmt(m.get('median_angular_error_deg'), '.2f')} | {_fmt(m.get('mean_angular_error_deg'), '.2f')} "
                f"| {_fmt(m.get('mean_cosine'))} | {_fmt(m.get('mean_abs_magnitude_error'))} "
                f"| {_fmt(m.get('saturation_fraction'), '.4f')} |"
            )
        lines.append("")

    # -- seed variance -------------------------------------------------------
    if payload.get("seed_variance"):
        lines.append("## Seed variance (across runs)")
        lines.append("")
        lines.append("| metric | mean | std | min | max | n |")
        lines.append("|---|---|---|---|---|---|")
        for key, stats in payload["seed_variance"].items():
            lines.append(
                f"| {key} | {_fmt(stats['mean'], '.4f')} | {_fmt(stats['std'], '.4f')} "
                f"| {_fmt(stats['min'], '.4f')} | {_fmt(stats['max'], '.4f')} | {stats['n']} |"
            )
        lines.append("")

    # -- inter-seed agreement ------------------------------------------------
    if payload.get("inter_seed_agreement"):
        lines.append("## Inter-seed agreement (val predictions, moving samples)")
        lines.append("")
        lines.append("| run A | run B | n | median diff° | mean diff° |")
        lines.append("|---|---|---|---|---|")
        for a in payload["inter_seed_agreement"]:
            lines.append(
                f"| {a['run_a']} | {a['run_b']} | {a['n']} "
                f"| {_fmt(a['median_angular_diff_deg'], '.2f')} | {_fmt(a['mean_angular_diff_deg'], '.2f')} |"
            )
        lines.append("")

    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")
