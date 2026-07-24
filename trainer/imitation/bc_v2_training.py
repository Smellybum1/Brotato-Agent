"""bc_v2 training loop for WP2 M4 (DAgger round 1).

Trains the two bc_v2 candidates on the composite corpus assembled by
:func:`~trainer.data.bc_v2_dataset.load_composite_dataset`:

  * Candidate A — ``BCPolicyV1`` (unchanged arch), composite weighted training.
  * Candidate B — ``BCPolicyV2`` (base trunk + two aux heads), same weighted
    main loss plus two auxiliary losses on the dagger rows only.

Everything numeric is reused from :mod:`trainer.imitation.bc_training` and
:mod:`trainer.models.bc_policy_v1` — this module owns only the *weighted /
auxiliary* training concern and the bc_v2 orchestration. No existing trainer
file is modified.

Protocol points held identical to bc_v1 (design §4):
  * same optimizer (AdamW), cosine schedule, seed, hyper-parameters;
  * early stopping on the frozen val split's UNWEIGHTED loss (patience 5);
  * validation is the frozen combat_obs_v1 val split, unchanged.

bc_v2-specific:
  * per-row loss weights (base 1.0; dagger event_weight * s), reduced as
    ``sum(w * per_sample) / sum(w)`` so the dagger set carries 25% of the
    effective batch mass;
  * candidate B adds ``lambda_aux`` * (BCE damage + Huber margin) on dagger rows;
  * candidate B's serving export is the base state_dict only (BCPolicyV1-loadable).
"""

from __future__ import annotations

import json
import platform
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import numpy as np
import torch
import torch.nn.functional as F
from torch import Tensor

from trainer.data.bc_v2_dataset import (
    CompositeBCDataset,
    load_composite_dataset,
    load_multi_composite_dataset,
)
from trainer.imitation.bc_training import (
    REPO_ROOT,
    RISK_BIN_LABELS,
    WAVE_BAND_LABELS,
    BCTrainConfig,
    DeviceSplit,
    EarlyStopper,
    _build_device_split,
    _f,
    _git_commit,
    _sha256_bytes,
    _sha256_file,
    circular_mean_direction,
    evaluate_predictions,
    load_train_config,
    resolve_device,
)
from trainer.models.bc_policy_v1 import (
    BCPolicyConfig,
    BCPolicyV1,
    _huber,
    bc_loss,
    cosine_similarity,
)
from trainer.models.bc_policy_v2 import BCPolicyV2

PREV_ACTION_X_NAME = "previous_action_x"
PREV_ACTION_Y_NAME = "previous_action_y"

DEFAULT_DAGGER_DIR = REPO_ROOT / "datasets" / "combat_dagger_r1"
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "models" / "bc_v2"
DEFAULT_LAMBDA_AUX = 0.05


class BCV2TrainingError(RuntimeError):
    """Raised when the bc_v2 training loop cannot proceed safely."""


# ---------------------------------------------------------------------------
# Weighted + auxiliary losses (pure, testable)
# ---------------------------------------------------------------------------
def weighted_bc_loss(
    pred: Tensor,
    target: Tensor,
    weight: Tensor,
    lambda_mag: float = 0.5,
    huber_delta: float = 0.5,
    mag_eps: float = 0.01,
) -> tuple[Tensor, dict[str, Tensor]]:
    """Per-row-weighted direction+magnitude BC loss.

    Identical per-sample term to :func:`bc_loss` (direction masked by zero-mag
    targets + Huber magnitude), reduced as ``sum(w * per_sample) / sum(w)``.
    With all weights equal this reproduces ``bc_loss`` exactly.
    """
    target_mag = target.norm(dim=-1)
    direction_mask = (target_mag > mag_eps).to(pred.dtype)

    cos = cosine_similarity(pred, target)
    direction_term = direction_mask * (1.0 - cos)

    mag_residual = pred.norm(dim=-1) - target_mag
    mag_term = _huber(mag_residual, huber_delta)

    per_sample = direction_term + lambda_mag * mag_term
    wsum = weight.sum().clamp_min(1e-8)
    loss = (weight * per_sample).sum() / wsum

    n_dir = direction_mask.sum().clamp_min(1.0)
    components = {
        "loss": loss.detach(),
        "direction_term": (direction_term.sum() / n_dir).detach(),
        "magnitude_term": mag_term.mean().detach(),
        "weight_sum": wsum.detach(),
    }
    return loss, components


def aux_damage_loss(logit: Tensor, label: Tensor, mask: Tensor) -> Tensor:
    """Masked BCE-with-logits for the imminent-damage head (0 if no rows)."""
    sel = mask.bool()
    if int(sel.sum().item()) == 0:
        return logit.new_zeros(())
    return F.binary_cross_entropy_with_logits(
        logit[sel], label[sel].to(logit.dtype), reduction="mean"
    )


def aux_margin_loss(pred: Tensor, label: Tensor, mask: Tensor, delta: float = 0.5) -> Tensor:
    """Masked Huber on the safety-margin head over [0, 1] (0 if no rows)."""
    sel = mask.bool()
    if int(sel.sum().item()) == 0:
        return pred.new_zeros(())
    return _huber(pred[sel] - label[sel].to(pred.dtype), delta).mean()


def binary_auc(scores: np.ndarray, labels: np.ndarray) -> float:
    """ROC-AUC via the Mann-Whitney U statistic with average ranks for ties."""
    scores = np.asarray(scores, dtype=np.float64)
    labels = np.asarray(labels).astype(np.int64)
    n_pos = int((labels == 1).sum())
    n_neg = int((labels == 0).sum())
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    order = np.argsort(scores, kind="mergesort")
    sorted_scores = scores[order]
    ranks = np.empty(len(scores), dtype=np.float64)
    i = 0
    while i < len(scores):
        j = i
        while j + 1 < len(scores) and sorted_scores[j + 1] == sorted_scores[i]:
            j += 1
        avg_rank = 0.5 * (i + j) + 1.0  # 1-based average rank over the tie block
        ranks[order[i : j + 1]] = avg_rank
        i = j + 1
    rank_sum_pos = ranks[labels == 1].sum()
    auc = (rank_sum_pos - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg)
    return float(auc)


# ---------------------------------------------------------------------------
# Composite device split (standard fields + side arrays)
# ---------------------------------------------------------------------------
@dataclass
class CompositeDeviceSplit:
    base: DeviceSplit
    weight: Tensor  # [N] f32
    is_dagger: Tensor  # [N] bool
    aux_damage: Tensor  # [N] f32
    aux_damage_mask: Tensor  # [N] bool
    aux_margin: Tensor  # [N] f32
    aux_margin_mask: Tensor  # [N] bool

    @property
    def size(self) -> int:
        return self.base.size


def _to_dev(arr: np.ndarray, device: torch.device) -> Tensor:
    return torch.from_numpy(np.ascontiguousarray(arr)).to(device)


# ---------------------------------------------------------------------------
# Trainer
# ---------------------------------------------------------------------------
class BCV2Trainer:
    """bc_v2 training loop for a single candidate (A=BCPolicyV1, B=BCPolicyV2)."""

    def __init__(
        self,
        dataset: CompositeBCDataset,
        config: BCTrainConfig,
        device: torch.device,
        *,
        candidate: str,
        lambda_aux: float = DEFAULT_LAMBDA_AUX,
        init_state_dict: dict[str, Any] | None = None,
    ) -> None:
        candidate = candidate.upper()
        if candidate not in ("A", "B"):
            raise BCV2TrainingError(f"candidate must be 'A' or 'B', got {candidate!r}")
        self.config = config
        self.device = device
        self.candidate = candidate
        self.lambda_aux = lambda_aux
        self.use_aux = candidate == "B"
        self._seed_everything(config.seed)

        names = list(dataset.global_feature_names)
        try:
            ix = names.index(PREV_ACTION_X_NAME)
            iy = names.index(PREV_ACTION_Y_NAME)
        except ValueError as exc:
            raise BCV2TrainingError(f"prev-action feature missing from globals: {exc}")
        if ix != 15 or iy != 16:
            raise BCV2TrainingError(
                f"prev_action indices must be (15, 16); got ({ix}, {iy})"
            )
        self.prev_action_indices = (ix, iy)
        self.policy_config = BCPolicyConfig(
            global_dim=len(names),
            previous_action_dropout_p=config.previous_action_dropout_p,
            prev_action_indices=(ix, iy),
        )
        self.group_names = tuple(spec.name for spec in self.policy_config.group_specs)

        if candidate == "A":
            self.model: BCPolicyV1 | BCPolicyV2 = BCPolicyV1(self.policy_config).to(device)
        else:
            self.model = BCPolicyV2(self.policy_config).to(device)

        # Curriculum init: overwrite the freshly-constructed weights with a prior
        # BCPolicyV1-loadable base state_dict (candidate A only). Loaded strict so
        # any architecture mismatch is a hard error, then trained normally.
        if init_state_dict is not None:
            if candidate != "A":
                raise BCV2TrainingError(
                    "init_state_dict is only supported for candidate A (BCPolicyV1 base)"
                )
            self.model.load_state_dict(init_state_dict, strict=True)

        resident = device if config.data_on_device else torch.device("cpu")
        self.resident = resident
        self.train_split = self._build_composite_split(dataset, resident)
        self.val_split = _build_device_split(
            dataset.val, dataset.normalization, self.group_names,
            self.prev_action_indices, resident, pin=not config.data_on_device,
        )
        self.aux_holdout_split = _build_device_split(
            dataset.aux_holdout, dataset.normalization, self.group_names,
            self.prev_action_indices, resident, pin=not config.data_on_device,
        )
        self.holdout_aux = {
            "aux_damage": _to_dev(dataset.holdout_aux_damage, resident),
            "aux_damage_mask": _to_dev(dataset.holdout_aux_damage_mask, resident),
            "aux_margin": _to_dev(dataset.holdout_aux_margin, resident),
            "aux_margin_mask": _to_dev(dataset.holdout_aux_margin_mask, resident),
        }

        self.optimizer = torch.optim.AdamW(
            self.model.parameters(), lr=config.lr, weight_decay=config.weight_decay
        )
        self.scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
            self.optimizer, T_max=max(config.max_epochs, 1), eta_min=config.lr_min
        )

    @staticmethod
    def _seed_everything(seed: int) -> None:
        import random

        random.seed(seed)
        np.random.seed(seed)
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)

    def _build_composite_split(
        self, dataset: CompositeBCDataset, resident: torch.device
    ) -> CompositeDeviceSplit:
        base = _build_device_split(
            dataset.train, dataset.normalization, self.group_names,
            self.prev_action_indices, resident, pin=not self.config.data_on_device,
        )
        return CompositeDeviceSplit(
            base=base,
            weight=_to_dev(dataset.train_weight, resident),
            is_dagger=_to_dev(dataset.train_is_dagger, resident),
            aux_damage=_to_dev(dataset.train_aux_damage, resident),
            aux_damage_mask=_to_dev(dataset.train_aux_damage_mask, resident),
            aux_margin=_to_dev(dataset.train_aux_margin, resident),
            aux_margin_mask=_to_dev(dataset.train_aux_margin_mask, resident),
        )

    def _gather_train(self, idx: Tensor):
        split = self.train_split
        base = split.base
        i = idx.to(base.globals.device)
        g = base.globals.index_select(0, i)
        ent = {grp: base.entities[grp].index_select(0, i) for grp in self.group_names}
        msk = {grp: base.masks[grp].index_select(0, i) for grp in self.group_names}
        act = base.actions.index_select(0, i)
        w = split.weight.index_select(0, i)
        is_d = split.is_dagger.index_select(0, i)
        ad = split.aux_damage.index_select(0, i)
        adm = split.aux_damage_mask.index_select(0, i)
        am = split.aux_margin.index_select(0, i)
        amm = split.aux_margin_mask.index_select(0, i)
        if base.resident_device != self.device:
            g = g.to(self.device, non_blocking=True)
            ent = {k: v.to(self.device, non_blocking=True) for k, v in ent.items()}
            msk = {k: v.to(self.device, non_blocking=True) for k, v in msk.items()}
            act = act.to(self.device, non_blocking=True)
            w = w.to(self.device, non_blocking=True)
            is_d = is_d.to(self.device, non_blocking=True)
            ad = ad.to(self.device, non_blocking=True)
            adm = adm.to(self.device, non_blocking=True)
            am = am.to(self.device, non_blocking=True)
            amm = amm.to(self.device, non_blocking=True)
        return g, ent, msk, act, w, is_d, ad, adm, am, amm

    def train_epoch(self, epoch: int) -> dict[str, float]:
        cfg = self.config
        self.model.train()
        n = self.train_split.size
        gen = torch.Generator(device="cpu").manual_seed(cfg.seed + epoch)
        perm = torch.randperm(n, generator=gen)

        total_loss = 0.0
        total_main = 0.0
        total_aux_d = 0.0
        total_aux_m = 0.0
        seen = 0
        for start in range(0, n, cfg.batch_size):
            idx = perm[start : start + cfg.batch_size]
            g, ent, msk, act, w, is_d, ad, adm, am, amm = self._gather_train(idx)

            if self.use_aux:
                pred, aux_d_logit, aux_m_pred = self.model.forward_with_aux(g, ent, msk)
            else:
                pred = self.model(g, ent, msk)

            main_loss, _ = weighted_bc_loss(
                pred, act, w, cfg.lambda_mag, cfg.huber_delta, cfg.mag_eps
            )
            loss = main_loss
            aux_d_val = 0.0
            aux_m_val = 0.0
            if self.use_aux:
                d_mask = adm & is_d
                m_mask = amm & is_d
                l_d = aux_damage_loss(aux_d_logit, ad, d_mask)
                l_m = aux_margin_loss(aux_m_pred, am, m_mask, cfg.huber_delta)
                loss = main_loss + self.lambda_aux * l_d + self.lambda_aux * l_m
                aux_d_val = float(l_d.detach().cpu().item())
                aux_m_val = float(l_m.detach().cpu().item())

            self.optimizer.zero_grad(set_to_none=True)
            loss.backward()
            self.optimizer.step()

            bs = int(idx.shape[0])
            total_loss += float(loss.detach().cpu().item()) * bs
            total_main += float(main_loss.detach().cpu().item()) * bs
            total_aux_d += aux_d_val * bs
            total_aux_m += aux_m_val * bs
            seen += bs

        return {
            "train_loss": total_loss / max(seen, 1),
            "train_main_loss": total_main / max(seen, 1),
            "train_aux_damage_loss": total_aux_d / max(seen, 1),
            "train_aux_margin_loss": total_aux_m / max(seen, 1),
            "lr": self.optimizer.param_groups[0]["lr"],
        }

    @torch.no_grad()
    def _predict_actions(self, split: DeviceSplit) -> Tensor:
        self.model.eval()
        n = split.size
        preds: list[Tensor] = []
        for start in range(0, n, self.config.batch_size):
            end = min(start + self.config.batch_size, n)
            idx = torch.arange(start, end, device=split.globals.device)
            g = split.globals.index_select(0, idx)
            ent = {grp: split.entities[grp].index_select(0, idx) for grp in self.group_names}
            msk = {grp: split.masks[grp].index_select(0, idx) for grp in self.group_names}
            if split.resident_device != self.device:
                g = g.to(self.device, non_blocking=True)
                ent = {k: v.to(self.device, non_blocking=True) for k, v in ent.items()}
                msk = {k: v.to(self.device, non_blocking=True) for k, v in msk.items()}
            preds.append(self.model(g, ent, msk))
        return torch.cat(preds, dim=0)

    @torch.no_grad()
    def evaluate(self) -> dict[str, Any]:
        """Val metrics on the frozen val split, mirroring bc_v1 (unweighted)."""
        cfg = self.config
        split = self.val_split
        pred = self._predict_actions(split)
        target = split.actions.to(pred.device)

        loss, comp = bc_loss(pred, target, cfg.lambda_mag, cfg.huber_delta, cfg.mag_eps)
        metrics: dict[str, Any] = {
            "val_loss": _f(loss),
            "val_direction_term": _f(comp["direction_term"]),
            "val_magnitude_term": _f(comp["magnitude_term"]),
        }
        metrics.update({f"val_{k}": v for k, v in evaluate_predictions(pred, target, cfg.mag_eps).items()})
        wave_band = split.wave_band.to(pred.device)
        risk_bin = split.risk_bin.to(pred.device)
        metrics["by_wave_band"] = self._stratify(pred, target, wave_band, len(WAVE_BAND_LABELS), WAVE_BAND_LABELS)
        metrics["by_risk_stratum"] = self._stratify(pred, target, risk_bin, len(RISK_BIN_LABELS), RISK_BIN_LABELS)
        return metrics

    def _stratify(self, pred, target, strata, n_bins, labels):
        out: dict[str, dict[str, float]] = {}
        for b in range(n_bins):
            sel = strata == b
            if int(sel.sum().item()) == 0:
                out[labels[b]] = {"n": 0}
            else:
                out[labels[b]] = evaluate_predictions(pred[sel], target[sel], self.config.mag_eps)
        return out

    @torch.no_grad()
    def baselines(self) -> dict[str, Any]:
        cfg = self.config
        target = self.val_split.actions.to(self.device)
        train_actions = self.train_split.base.actions.to(self.device)
        mean_dir = circular_mean_direction(train_actions, cfg.mag_eps)
        mean_pred = mean_dir.unsqueeze(0).expand(target.shape[0], 2).contiguous()
        mean_metrics = evaluate_predictions(mean_pred, target, cfg.mag_eps)
        mean_metrics["direction"] = [float(mean_dir[0]), float(mean_dir[1])]
        prev_pred = self.val_split.prev_action.to(self.device)
        prev_metrics = evaluate_predictions(prev_pred, target, cfg.mag_eps)
        return {"mean_direction": mean_metrics, "copy_previous": prev_metrics}

    @torch.no_grad()
    def aux_holdout_metrics(self) -> dict[str, Any]:
        """Candidate-B aux-head metrics on the held-out dagger rows."""
        if not self.use_aux:
            return {}
        self.model.eval()
        split = self.aux_holdout_split
        n = split.size
        d_logits: list[Tensor] = []
        m_preds: list[Tensor] = []
        for start in range(0, n, self.config.batch_size):
            end = min(start + self.config.batch_size, n)
            idx = torch.arange(start, end, device=split.globals.device)
            g = split.globals.index_select(0, idx)
            ent = {grp: split.entities[grp].index_select(0, idx) for grp in self.group_names}
            msk = {grp: split.masks[grp].index_select(0, idx) for grp in self.group_names}
            if split.resident_device != self.device:
                g = g.to(self.device, non_blocking=True)
                ent = {k: v.to(self.device, non_blocking=True) for k, v in ent.items()}
                msk = {k: v.to(self.device, non_blocking=True) for k, v in msk.items()}
            _, dl, mp = self.model.forward_with_aux(g, ent, msk)
            d_logits.append(dl.detach().cpu())
            m_preds.append(mp.detach().cpu())
        damage_logit = torch.cat(d_logits).numpy()
        damage_prob = 1.0 / (1.0 + np.exp(-damage_logit))
        margin_pred = torch.cat(m_preds).numpy()

        d_mask = self.holdout_aux["aux_damage_mask"].cpu().numpy().astype(bool)
        d_label = self.holdout_aux["aux_damage"].cpu().numpy()
        m_mask = self.holdout_aux["aux_margin_mask"].cpu().numpy().astype(bool)
        m_label = self.holdout_aux["aux_margin"].cpu().numpy()

        damage: dict[str, Any] = {"n": int(d_mask.sum())}
        if int(d_mask.sum()) > 0:
            dl_lab = d_label[d_mask]
            dl_prob = damage_prob[d_mask]
            eps = 1e-7
            bce = float(-(dl_lab * np.log(dl_prob + eps) + (1 - dl_lab) * np.log(1 - dl_prob + eps)).mean())
            damage.update({
                "auc": binary_auc(dl_prob, dl_lab),
                "bce": bce,
                "base_rate": float(dl_lab.mean()),
                "pred_mean": float(dl_prob.mean()),
                "pred_pos_mean": float(dl_prob[dl_lab == 1].mean()) if (dl_lab == 1).any() else float("nan"),
                "pred_neg_mean": float(dl_prob[dl_lab == 0].mean()) if (dl_lab == 0).any() else float("nan"),
            })

        margin: dict[str, Any] = {"n": int(m_mask.sum())}
        if int(m_mask.sum()) > 0:
            ml_lab = m_label[m_mask]
            ml_pred = margin_pred[m_mask]
            resid = ml_pred - ml_lab
            mae = float(np.abs(resid).mean())
            rmse = float(np.sqrt((resid ** 2).mean()))
            if ml_lab.std() > 1e-9 and ml_pred.std() > 1e-9:
                corr = float(np.corrcoef(ml_pred, ml_lab)[0, 1])
            else:
                corr = float("nan")
            margin.update({
                "mae": mae,
                "rmse": rmse,
                "pearson_r": corr,
                "label_mean": float(ml_lab.mean()),
                "pred_mean": float(ml_pred.mean()),
            })
        return {"aux_damage": damage, "aux_margin": margin}

    def step_scheduler(self) -> None:
        self.scheduler.step()


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------
def _base_checkpoint_payload(
    model: BCPolicyV1 | BCPolicyV2, config_snapshot: dict[str, Any], epoch: int, val_metrics: dict[str, Any]
) -> dict[str, Any]:
    """Serving/eval checkpoint carrying a BCPolicyV1-loadable base state_dict."""
    if isinstance(model, BCPolicyV2):
        state = model.export_base_state_dict()
    else:
        state = model.state_dict()
    return {
        "model_state_dict": state,
        "config": config_snapshot,
        "epoch": epoch,
        "val_metrics": val_metrics,
    }


def run_bc_v2_training(
    config: BCTrainConfig,
    config_hash: str,
    *,
    candidate: str,
    run_name: str,
    dagger_dataset_dir: str | Path = DEFAULT_DAGGER_DIR,
    dagger_dataset_dirs: list[str | Path] | tuple[str | Path, ...] | None = None,
    lambda_aux: float = DEFAULT_LAMBDA_AUX,
    target_mass_ratio: float | None = None,
    init_checkpoint: str | Path | None = None,
    init_checkpoint_sha256: str | None = None,
    smoke: bool = False,
    log: Any = print,
) -> dict[str, Any]:
    """Full bc_v2 training run for one candidate; returns a summary dict.

    ``target_mass_ratio`` overrides the dagger:base effective-mass ratio passed
    to :func:`load_composite_dataset`; ``None`` keeps the loader default
    (0.25/0.75, i.e. a 25% corrective mass fraction — the bc_v2_a setting).

    ``init_checkpoint`` (candidate A only) seeds the model weights from a prior
    BCPolicyV1-loadable base checkpoint before fine-tuning (curriculum init). If
    ``init_checkpoint_sha256`` is given the file's sha256 is verified against it
    (upper-case hex) and a mismatch is a hard error. ``None`` keeps the default
    fresh (random) initialization — fully backward compatible.
    """
    candidate = candidate.upper()
    device = resolve_device(config.device)
    started = time.time()
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    max_epochs = 2 if smoke else config.max_epochs

    # -- resolve + verify the curriculum init checkpoint (candidate A only) ---
    init_state_dict: dict[str, Any] | None = None
    init_provenance: dict[str, Any] | None = None
    if init_checkpoint is not None:
        if candidate != "A":
            raise BCV2TrainingError("init_checkpoint is only supported for candidate A")
        init_path = Path(init_checkpoint)
        if not init_path.is_file():
            raise BCV2TrainingError(f"init checkpoint not found: {init_path}")
        actual_sha = _sha256_file(init_path)
        verified = False
        if init_checkpoint_sha256 is not None:
            expected = str(init_checkpoint_sha256).upper()
            if actual_sha != expected:
                raise BCV2TrainingError(
                    f"init checkpoint sha256 mismatch: file={actual_sha} expected={expected}"
                )
            verified = True
        payload = torch.load(str(init_path), map_location="cpu", weights_only=False)
        if "model_state_dict" not in payload:
            raise BCV2TrainingError(f"init checkpoint has no model_state_dict: {init_path}")
        init_state_dict = payload["model_state_dict"]
        init_provenance = {
            "init_checkpoint": str(init_path),
            "init_checkpoint_sha256": actual_sha,
            "sha256_verified": verified,
            "expected_sha256": (str(init_checkpoint_sha256).upper() if init_checkpoint_sha256 else None),
            "source_epoch": payload.get("epoch"),
        }
        log(
            f"[bcv2] curriculum init from {init_path} sha={actual_sha} "
            f"(verified={verified}, source_epoch={payload.get('epoch')})"
        )

    composite_kwargs: dict[str, Any] = {}
    if target_mass_ratio is not None:
        composite_kwargs["target_mass_ratio"] = float(target_mass_ratio)
    if dagger_dataset_dirs is not None:
        dir_list = list(dagger_dataset_dirs)
        log(
            f"[bcv2] loading MULTI composite dataset (base={config.dataset_dir}, "
            f"dagger_dirs={[str(d) for d in dir_list]}, target_mass_ratio="
            f"{target_mass_ratio if target_mass_ratio is not None else 'default'}) ..."
        )
        dataset = load_multi_composite_dataset(
            config.dataset_dir, dir_list,
            config.split_config, config.input_config, config.schema,
            **composite_kwargs,
        )
        log(
            "[bcv2] per-set corrective breakdown: "
            + ", ".join(
                f"{Path(d).name}(n_train={nt} n_hold={nh} s={s:.6f} wsum={ws:.1f})"
                for d, nt, nh, s, ws in zip(
                    dataset.dagger_dataset_dirs,
                    dataset.per_set_n_train,
                    dataset.per_set_n_holdout,
                    dataset.per_set_s_scalars,
                    dataset.per_set_weight_sums,
                )
            )
        )
        dagger_dataset_dir = dir_list
    else:
        log(
            f"[bcv2] loading composite dataset (base={config.dataset_dir}, "
            f"dagger={dagger_dataset_dir}, target_mass_ratio="
            f"{target_mass_ratio if target_mass_ratio is not None else 'default'}) ..."
        )
        dataset = load_composite_dataset(
            config.dataset_dir, dagger_dataset_dir,
            config.split_config, config.input_config, config.schema,
            **composite_kwargs,
        )
    log(
        f"[bcv2] composite train={dataset.train.size} "
        f"(base={dataset.n_base_train} dagger_train={dataset.n_dagger_train} "
        f"holdout={dataset.n_dagger_holdout}) val={dataset.val.size} | "
        f"s={dataset.s_scalar:.6f} mass_frac={dataset.achieved_mass_fraction:.4f}"
    )

    run_dir = config.output_root / run_name
    run_dir.mkdir(parents=True, exist_ok=True)
    metrics_path = run_dir / "metrics.jsonl"
    norm_manifest_path = run_dir / "normalization_manifest.json"
    best_ckpt_path = run_dir / "best.pt"       # registered (BCPolicyV1-loadable)
    last_ckpt_path = run_dir / "last.pt"        # registered (BCPolicyV1-loadable)
    full_best_path = run_dir / "full_best.pt"   # candidate B: full V2 state (internal)
    full_last_path = run_dir / "full_last.pt"

    dataset.save_normalization_manifest(norm_manifest_path)
    norm_manifest_hash = _sha256_file(norm_manifest_path)

    trainer = BCV2Trainer(
        dataset, config, device, candidate=candidate, lambda_aux=lambda_aux,
        init_state_dict=init_state_dict,
    )
    n_params = trainer.model.num_parameters()
    n_base_params = (
        trainer.model.num_base_parameters()
        if isinstance(trainer.model, BCPolicyV2)
        else n_params
    )
    log(f"[bcv2] candidate={candidate} device={device} params={n_params:,} base_params={n_base_params:,}")

    baselines = trainer.baselines()
    config_snapshot = config.as_dict()
    header = {
        "record": "header",
        "run_name": run_name,
        "candidate": candidate,
        "timestamp": timestamp,
        "device": str(device),
        "smoke": smoke,
        "config": config_snapshot,
        "config_hash": config_hash,
        "lambda_aux": lambda_aux if candidate == "B" else None,
        "init_checkpoint": init_provenance,
        "split_id": dataset.split_id,
        "schema_hash": dataset.schema_hash,
        "train_size": dataset.train.size,
        "val_size": dataset.val.size,
        "composite": {
            "n_base_train": dataset.n_base_train,
            "n_dagger_train": dataset.n_dagger_train,
            "n_dagger_holdout": dataset.n_dagger_holdout,
            "s_scalar": dataset.s_scalar,
            "base_weight_sum": dataset.base_weight_sum,
            "dagger_weight_sum": dataset.dagger_weight_sum,
            "achieved_mass_fraction": dataset.achieved_mass_fraction,
            "aux_base_rates": dataset.aux_base_rates,
        },
        "model_parameters": n_params,
        "model_base_parameters": n_base_params,
        "baselines": baselines,
    }
    with metrics_path.open("w", encoding="utf-8") as handle:
        handle.write(json.dumps(header) + "\n")

    stopper = EarlyStopper(patience=config.early_stopping_patience)
    best_val_metrics: dict[str, Any] = {}
    last_val_metrics: dict[str, Any] = {}
    best_aux: dict[str, Any] = {}
    last_aux: dict[str, Any] = {}
    epochs_run = 0

    for epoch in range(max_epochs):
        epoch_start = time.time()
        train_metrics = trainer.train_epoch(epoch)
        val_metrics = trainer.evaluate()
        aux_metrics = trainer.aux_holdout_metrics()
        trainer.step_scheduler()
        epoch_wall = time.time() - epoch_start
        epochs_run = epoch + 1

        improved = stopper.update(val_metrics["val_loss"], epoch)
        last_val_metrics = val_metrics
        last_aux = aux_metrics
        record = {
            "record": "epoch",
            "epoch": epoch,
            "epoch_wall_sec": round(epoch_wall, 3),
            "improved": improved,
            **train_metrics,
            **val_metrics,
        }
        if aux_metrics:
            record["aux_holdout"] = aux_metrics
        with metrics_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record) + "\n")

        aux_str = ""
        if aux_metrics.get("aux_damage", {}).get("n", 0):
            aux_str = (
                f" aux_dmg_auc={aux_metrics['aux_damage'].get('auc', float('nan')):.3f}"
                f" aux_mgn_mae={aux_metrics['aux_margin'].get('mae', float('nan')):.3f}"
            )
        log(
            f"[bcv2] epoch {epoch:02d} train_loss={train_metrics['train_loss']:.4f} "
            f"val_loss={val_metrics['val_loss']:.4f} "
            f"val_med_ang={val_metrics['val_median_angular_error_deg']:.2f}deg "
            f"lr={train_metrics['lr']:.2e}{aux_str} {'*best' if improved else ''} ({epoch_wall:.1f}s)"
        )

        # Serving/eval checkpoints (BCPolicyV1-loadable base) + full state (B).
        torch.save(_base_checkpoint_payload(trainer.model, config_snapshot, epoch, val_metrics), str(last_ckpt_path))
        if candidate == "B":
            torch.save(
                {"model_state_dict": trainer.model.state_dict(), "config": config_snapshot,
                 "epoch": epoch, "val_metrics": val_metrics},
                str(full_last_path),
            )
        if improved:
            best_val_metrics = val_metrics
            best_aux = aux_metrics
            torch.save(_base_checkpoint_payload(trainer.model, config_snapshot, epoch, val_metrics), str(best_ckpt_path))
            if candidate == "B":
                torch.save(
                    {"model_state_dict": trainer.model.state_dict(), "config": config_snapshot,
                     "epoch": epoch, "val_metrics": val_metrics},
                    str(full_best_path),
                )

        if stopper.should_stop:
            log(f"[bcv2] early stopping at epoch {epoch} (best epoch {stopper.best_epoch})")
            break

    if not best_val_metrics:
        best_val_metrics = last_val_metrics
        best_aux = last_aux
        torch.save(_base_checkpoint_payload(trainer.model, config_snapshot, epochs_run - 1, last_val_metrics), str(best_ckpt_path))

    # -- verify the exported base is strict-loadable as BCPolicyV1 ----------
    _verify_base_export(best_ckpt_path, trainer.policy_config)

    wall = time.time() - started

    registry_dir = REPO_ROOT / "models" / "registry"
    registry_dir.mkdir(parents=True, exist_ok=True)
    registry_path = registry_dir / f"{run_name}.json"
    registry = {
        "run_name": run_name,
        "candidate": candidate,
        "timestamp": timestamp,
        "smoke": smoke,
        "git_commit": _git_commit(),
        "device": str(device),
        "wall_time_sec": round(wall, 2),
        "epochs_run": epochs_run,
        "best_epoch": stopper.best_epoch,
        "config_hash": config_hash,
        "resolved_config": config_snapshot,
        "init_checkpoint": init_provenance,
        "seed": config.seed,
        "split_id": dataset.split_id,
        "schema_hash": dataset.schema_hash,
        # combat_obs_v1 manifest hash: what bc_offline reloads + verifies.
        "dataset_manifest_hash": dataset.base_manifest_hash,
        "normalization_manifest_hash": norm_manifest_hash,
        "checkpoints": {
            "best": {"path": str(best_ckpt_path), "sha256": _sha256_file(best_ckpt_path)},
            "last": {"path": str(last_ckpt_path), "sha256": _sha256_file(last_ckpt_path)},
        },
        "bc_v2_provenance": {
            "lambda_aux": lambda_aux if candidate == "B" else None,
            "dagger_dataset_dir": str(dagger_dataset_dir),
            "dagger_manifest_hash": dataset.dagger_manifest_hash,
            "combat_obs_v1_manifest_hash": dataset.base_manifest_hash,
            "s_scalar": dataset.s_scalar,
            "base_weight_sum": dataset.base_weight_sum,
            "dagger_weight_sum": dataset.dagger_weight_sum,
            "achieved_mass_fraction": dataset.achieved_mass_fraction,
            "n_base_train": dataset.n_base_train,
            "n_dagger_train": dataset.n_dagger_train,
            "n_dagger_holdout": dataset.n_dagger_holdout,
            "aux_base_rates": dataset.aux_base_rates,
            "model_parameters": n_params,
            "model_base_parameters": n_base_params,
            "serving_export": "base_state_dict (BCPolicyV1 strict-load verified)",
            "multi_corrective": (
                {
                    "total_mass_ratio": dataset.total_mass_ratio,
                    "dagger_dataset_dirs": list(dataset.dagger_dataset_dirs),
                    "dagger_manifest_hashes": list(dataset.dagger_manifest_hashes),
                    "per_set_s_scalars": list(dataset.per_set_s_scalars),
                    "per_set_n_train": list(dataset.per_set_n_train),
                    "per_set_n_holdout": list(dataset.per_set_n_holdout),
                    "per_set_event_weight_sums": list(dataset.per_set_event_weight_sums),
                    "per_set_weight_sums": list(dataset.per_set_weight_sums),
                }
                if dataset.dagger_dataset_dirs
                else None
            ),
        },
        "baselines": baselines,
        "best_val_metrics": best_val_metrics,
        "final_val_metrics": last_val_metrics,
        "best_aux_holdout_metrics": best_aux if candidate == "B" else None,
        "final_aux_holdout_metrics": last_aux if candidate == "B" else None,
        "environment": {
            "python": platform.python_version(),
            "torch": torch.__version__,
            "numpy": np.__version__,
            "cuda": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        },
    }
    registry_path.write_text(json.dumps(registry, indent=2, sort_keys=True), encoding="utf-8")
    log(f"[bcv2] wrote registry -> {registry_path}")

    return {
        "run_name": run_name,
        "candidate": candidate,
        "run_dir": str(run_dir),
        "registry_path": str(registry_path),
        "epochs_run": epochs_run,
        "best_epoch": stopper.best_epoch,
        "wall_time_sec": wall,
        "device": str(device),
        "baselines": baselines,
        "best_val_metrics": best_val_metrics,
        "final_val_metrics": last_val_metrics,
        "best_aux_holdout_metrics": best_aux if candidate == "B" else None,
        "composite": header["composite"],
    }


def _verify_base_export(ckpt_path: Path, policy_config: BCPolicyConfig) -> None:
    """Hard-check that the registered checkpoint loads into a fresh BCPolicyV1."""
    payload = torch.load(str(ckpt_path), map_location="cpu", weights_only=False)
    fresh = BCPolicyV1(policy_config)
    missing, unexpected = fresh.load_state_dict(payload["model_state_dict"], strict=False)
    if missing or unexpected:
        raise BCV2TrainingError(
            f"exported base is not BCPolicyV1-compatible: missing={missing} unexpected={unexpected}"
        )
    # strict load must also succeed
    fresh.load_state_dict(payload["model_state_dict"], strict=True)


def load_bc_v2_config(
    config_path: str | Path, output_root: str | Path = DEFAULT_OUTPUT_ROOT
) -> tuple[BCTrainConfig, str]:
    """Load the bc_v1 training config and point its output_root at models/bc_v2."""
    config, config_hash = load_train_config(config_path)
    config = replace(config, output_root=Path(output_root))
    return config, config_hash
