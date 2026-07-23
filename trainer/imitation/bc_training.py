"""Behavior-cloning training loop for WP2 M2 (Stage D).

Trains :class:`~trainer.models.bc_policy_v1.BCPolicyV1` on the frozen
``combat_obs_v1`` dataset produced by
:func:`~trainer.data.bc_dataset.load_bc_dataset`. The loss, model, split, and
normalization decisions are fixed by ``.tmp/wp2_m2_training_architecture.md``
(esp. §4 loss, §6 normalization, §7 protocol, §8 eval).

This module owns only the *training* concern: it never modifies the loader, the
model, or any config. The pure pieces (risk stratum, wave band, baselines,
nan-aware reductions, early stopping, checkpoint round-trip) are factored out so
they can be unit-tested on CPU with tiny synthetic data.

Key protocol points (per the architecture note and the primary's decisions):
  * Standardize the 40 global inputs with the loader's TRAIN-only stats; entity
    features are identity.
  * ``prev_action_indices`` are asserted from the resolved feature names
    (``[15] == previous_action_x``, ``[16] == previous_action_y``) and passed
    into :class:`BCPolicyConfig` — never assumed from the model default.
  * Per-epoch full-batch validation (chunked to ``batch_size``); nan-aware
    reductions everywhere (angular error is NaN for zero-magnitude labels).
  * Metrics stratified by wave band {1-5,6-10,11-15,16-19,20} and by risk
    stratum (max masked ``contact_risk`` over enemies∪bosses∪projectiles,
    bins [0,0.25),[0.25,0.5),[0.5,0.75),[0.75,∞)). The per-sample risk scalar
    is computed ONCE at load time in numpy, not per epoch.
  * Two sanity-gate baselines computed once at startup: circular-mean of TRAIN
    action angles, and copy-previous (val previous_action_x/y from the
    UNNORMALIZED globals). The trained model must beat both.
"""
from __future__ import annotations

import hashlib
import json
import math
import platform
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import torch
import yaml
from torch import Tensor

from trainer.data.bc_dataset import (
    BCDataset,
    BCSplit,
    load_bc_dataset,
)
from trainer.models.bc_policy_v1 import (
    BCPolicyConfig,
    BCPolicyV1,
    angular_error_deg,
    bc_loss,
    cosine_similarity,
    magnitude_error,
    saturation_fraction,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

# Threat groups whose contact_risk defines the risk stratifier, and the entity
# feature column of contact_risk (schema order; see observation_v1.yaml).
RISK_GROUPS: tuple[str, ...] = ("enemies", "bosses", "projectiles")
CONTACT_RISK_INDEX = 11

# Risk-stratum bin edges: [0,0.25),[0.25,0.5),[0.5,0.75),[0.75,∞) -> 4 bins.
RISK_BIN_EDGES: tuple[float, ...] = (0.25, 0.5, 0.75)
RISK_BIN_LABELS: tuple[str, ...] = ("0.00-0.25", "0.25-0.50", "0.50-0.75", "0.75-inf")

# Wave bands {1-5, 6-10, 11-15, 16-19, 20}.
WAVE_BAND_LABELS: tuple[str, ...] = ("1-5", "6-10", "11-15", "16-19", "20")

PREV_ACTION_X_NAME = "previous_action_x"
PREV_ACTION_Y_NAME = "previous_action_y"


class BCTrainingError(RuntimeError):
    """Raised when the training loop cannot proceed safely."""


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class BCTrainConfig:
    """Resolved training hyper-parameters (see configs/wp2/bc_train_v1.yaml)."""

    seed: int
    batch_size: int
    max_epochs: int
    early_stopping_patience: int
    lr: float
    weight_decay: float
    lr_min: float
    lambda_mag: float
    huber_delta: float
    mag_eps: float
    previous_action_dropout_p: float
    device: str
    data_on_device: bool
    dataset_dir: Path
    split_config: Path
    input_config: Path
    schema: Path
    output_root: Path

    def as_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for key, value in self.__dict__.items():
            out[key] = str(value) if isinstance(value, Path) else value
        return out


def _resolve_path(raw: str) -> Path:
    path = Path(raw)
    return path if path.is_absolute() else (REPO_ROOT / path)


def load_train_config(config_path: str | Path) -> tuple[BCTrainConfig, str]:
    """Load and validate the training config; return (config, sha256_upper)."""
    config_path = Path(config_path)
    raw_bytes = config_path.read_bytes()
    config_hash = hashlib.sha256(raw_bytes).hexdigest().upper()
    data = yaml.safe_load(raw_bytes.decode("utf-8"))
    if not isinstance(data, dict):
        raise BCTrainingError(f"{config_path.name} is not a mapping")

    opt = data.get("optimizer", {}) or {}
    if str(opt.get("name", "adamw")).lower() != "adamw":
        raise BCTrainingError(f"unsupported optimizer {opt.get('name')!r} (only adamw)")
    sched = data.get("lr_schedule", {}) or {}
    if str(sched.get("name", "cosine")).lower() != "cosine":
        raise BCTrainingError(f"unsupported lr_schedule {sched.get('name')!r} (only cosine)")
    loss = data.get("loss", {}) or {}
    paths = data.get("paths", {}) or {}

    config = BCTrainConfig(
        seed=int(data.get("seed", 1)),
        batch_size=int(data["batch_size"]),
        max_epochs=int(data["max_epochs"]),
        early_stopping_patience=int(data["early_stopping_patience"]),
        lr=float(opt["lr"]),
        weight_decay=float(opt["weight_decay"]),
        lr_min=float(sched["min_lr"]),
        lambda_mag=float(loss["lambda_mag"]),
        huber_delta=float(loss["huber_delta"]),
        mag_eps=float(loss["mag_eps"]),
        previous_action_dropout_p=float(data["previous_action_dropout_p"]),
        device=str(data.get("device", "auto")),
        data_on_device=bool(data.get("data_on_device", True)),
        dataset_dir=_resolve_path(str(paths["dataset_dir"])),
        split_config=_resolve_path(str(paths["split_config"])),
        input_config=_resolve_path(str(paths["input_config"])),
        schema=_resolve_path(str(paths["schema"])),
        output_root=_resolve_path(str(data["output_root"])),
    )
    return config, config_hash


# ---------------------------------------------------------------------------
# Pure helpers — stratification, baselines, nan-aware reductions
# ---------------------------------------------------------------------------
def compute_risk_stratum(
    entities: dict[str, np.ndarray],
    masks: dict[str, np.ndarray],
    *,
    groups: tuple[str, ...] = RISK_GROUPS,
    feature_index: int = CONTACT_RISK_INDEX,
) -> np.ndarray:
    """Per-sample risk scalar = max masked ``contact_risk`` over the threat
    groups only. Padded rows are excluded; a sample with no present entity in
    any threat group scores 0 risk. Returns ``[N]`` float32.
    """
    first = entities[groups[0]]
    n = int(first.shape[0])
    # Start at 0: contact_risk is a nonnegative risk measure and an empty threat
    # set means "no risk". Present rows only ever push the max upward.
    risk = np.zeros(n, dtype=np.float32)
    for group in groups:
        ent = entities[group]  # [N, cap, F]
        mask = masks[group] > 0  # [N, cap]
        contact = ent[:, :, feature_index]  # [N, cap]
        masked = np.where(mask, contact, -np.inf)
        group_max = masked.max(axis=1)  # [N]; -inf where the group is empty
        finite = np.where(np.isfinite(group_max), group_max, -np.inf)
        risk = np.maximum(risk, finite.astype(np.float32))
    return risk.astype(np.float32)


def risk_bin_indices(risk: np.ndarray, edges: tuple[float, ...] = RISK_BIN_EDGES) -> np.ndarray:
    """Map risk scalars to bin indices 0..len(edges) via right-open intervals."""
    return np.digitize(risk, np.asarray(edges, dtype=np.float64), right=False).astype(np.int64)


def wave_band_indices(wave: np.ndarray) -> np.ndarray:
    """Map wave numbers to band indices {1-5:0, 6-10:1, 11-15:2, 16-19:3, 20:4}."""
    w = np.asarray(wave)
    return np.select(
        [w <= 5, w <= 10, w <= 15, w <= 19],
        [0, 1, 2, 3],
        default=4,
    ).astype(np.int64)


def circular_mean_direction(actions: Tensor, mag_eps: float = 0.01) -> Tensor:
    """Unit vector at the circular mean of the moving actions' angles -> ``[2]``.

    Zero-magnitude (|a| <= mag_eps) samples carry no direction and are dropped.
    Degenerate (near-cancelling) inputs fall back to +x so the baseline is
    always a valid unit vector.
    """
    mags = actions.norm(dim=-1)
    valid = mags > mag_eps
    if not bool(valid.any()):
        return torch.tensor([1.0, 0.0], dtype=actions.dtype, device=actions.device)
    units = actions[valid] / mags[valid].unsqueeze(-1)
    mean = units.mean(dim=0)
    norm = mean.norm()
    if float(norm) < 1e-8:
        return torch.tensor([1.0, 0.0], dtype=actions.dtype, device=actions.device)
    return mean / norm


def nan_mean(t: Tensor) -> Tensor:
    """Mean over non-NaN entries; NaN if all entries are NaN."""
    values = t[~torch.isnan(t)]
    if values.numel() == 0:
        return t.new_tensor(float("nan"))
    return values.mean()


def nan_median(t: Tensor) -> Tensor:
    """Median over non-NaN entries; NaN if all entries are NaN."""
    values = t[~torch.isnan(t)]
    if values.numel() == 0:
        return t.new_tensor(float("nan"))
    return values.median()


def _f(t: Tensor) -> float:
    return float(t.detach().cpu().item())


def evaluate_predictions(pred: Tensor, target: Tensor, mag_eps: float) -> dict[str, float]:
    """Agreement metrics for a set of predictions vs teacher actions.

    Direction metrics (angular error, cosine) are NaN for zero-magnitude
    targets and reduced nan-aware; magnitude error and saturation cover all
    samples. Returns Python floats.
    """
    ang = angular_error_deg(pred, target, mag_eps)  # NaN where |target| <= mag_eps
    valid = target.norm(dim=-1) > mag_eps
    cos = cosine_similarity(pred, target)
    cos = torch.where(valid, cos, torch.full_like(cos, float("nan")))
    abs_mag_err = magnitude_error(pred, target).abs()
    return {
        "n": int(pred.shape[0]),
        "n_direction": int(valid.sum().item()),
        "median_angular_error_deg": _f(nan_median(ang)),
        "mean_angular_error_deg": _f(nan_mean(ang)),
        "mean_cosine": _f(nan_mean(cos)),
        "mean_abs_magnitude_error": _f(abs_mag_err.mean()),
        "saturation_fraction": _f(saturation_fraction(pred)),
    }


# ---------------------------------------------------------------------------
# Early stopping
# ---------------------------------------------------------------------------
@dataclass
class EarlyStopper:
    """Stop when validation loss has not improved for ``patience`` epochs."""

    patience: int
    min_delta: float = 0.0
    best: float = math.inf
    best_epoch: int = -1
    _since_improved: int = 0

    def update(self, value: float, epoch: int) -> bool:
        """Record ``value`` at ``epoch``; return True on a new best."""
        if value < self.best - self.min_delta:
            self.best = value
            self.best_epoch = epoch
            self._since_improved = 0
            return True
        self._since_improved += 1
        return False

    @property
    def should_stop(self) -> bool:
        return self._since_improved >= self.patience


# ---------------------------------------------------------------------------
# Checkpointing
# ---------------------------------------------------------------------------
def save_checkpoint(
    path: str | Path,
    model: BCPolicyV1,
    config_snapshot: dict[str, Any],
    epoch: int,
    val_metrics: dict[str, Any],
) -> None:
    """Persist model weights + provenance to a torch checkpoint file."""
    torch.save(
        {
            "model_state_dict": model.state_dict(),
            "config": config_snapshot,
            "epoch": epoch,
            "val_metrics": val_metrics,
        },
        str(path),
    )


def load_checkpoint(path: str | Path, model: BCPolicyV1) -> dict[str, Any]:
    """Restore ``model`` weights from a checkpoint; return the payload dict."""
    payload = torch.load(str(path), map_location="cpu", weights_only=False)
    model.load_state_dict(payload["model_state_dict"])
    return payload


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


# ---------------------------------------------------------------------------
# Device-resident split
# ---------------------------------------------------------------------------
@dataclass
class DeviceSplit:
    """One split's tensors, standardized globals, plus precomputed strata.

    ``globals`` are the model input (standardized); ``prev_action`` holds the
    UNNORMALIZED previous_action_x/y columns (for the copy-previous baseline).
    Tensors live on ``device`` when ``data_on_device`` is true, else pinned CPU.
    """

    globals: Tensor  # [N, 40] standardized
    actions: Tensor  # [N, 2]
    entities: dict[str, Tensor]  # group -> [N, cap, 15]
    masks: dict[str, Tensor]  # group -> [N, cap]
    prev_action: Tensor  # [N, 2] UNNORMALIZED
    wave_band: Tensor  # [N] i64
    risk_bin: Tensor  # [N] i64
    resident_device: torch.device

    @property
    def size(self) -> int:
        return int(self.globals.shape[0])


def _build_device_split(
    split: BCSplit,
    normalization,
    group_names: tuple[str, ...],
    prev_action_indices: tuple[int, int],
    resident_device: torch.device,
    pin: bool,
) -> DeviceSplit:
    ix, iy = prev_action_indices
    raw_globals = split.globals  # [N, 40] UNNORMALIZED
    prev_action_np = np.stack([raw_globals[:, ix], raw_globals[:, iy]], axis=1).astype(np.float32)
    std_globals = normalization.apply(raw_globals)  # [N, 40]

    risk = compute_risk_stratum(split.entities, split.masks)
    wave_band = wave_band_indices(split.wave)
    risk_bin = risk_bin_indices(risk)

    def to_dev(arr: np.ndarray) -> Tensor:
        t = torch.from_numpy(np.ascontiguousarray(arr))
        if pin and resident_device.type == "cpu":
            t = t.pin_memory()
        else:
            t = t.to(resident_device)
        return t

    return DeviceSplit(
        globals=to_dev(std_globals),
        actions=to_dev(split.actions.astype(np.float32)),
        entities={g: to_dev(split.entities[g]) for g in group_names},
        masks={g: to_dev(split.masks[g]) for g in group_names},
        prev_action=to_dev(prev_action_np),
        wave_band=to_dev(wave_band),
        risk_bin=to_dev(risk_bin),
        resident_device=resident_device,
    )


# ---------------------------------------------------------------------------
# Trainer
# ---------------------------------------------------------------------------
class BCTrainer:
    """Seeded BC training loop. Construct with a loaded dataset + config.

    File-IO orchestration (checkpoints, JSONL, registry) lives in
    :func:`run_training`; this class owns only the seeded model, optimizer,
    scheduler, epoch step, and evaluation so the numeric core is testable.
    """

    def __init__(
        self,
        dataset: BCDataset,
        config: BCTrainConfig,
        device: torch.device,
    ) -> None:
        self.config = config
        self.device = device
        self._seed_everything(config.seed)

        names = list(dataset.global_feature_names)
        # Assert the prev-action columns rather than trusting the model default.
        try:
            ix = names.index(PREV_ACTION_X_NAME)
            iy = names.index(PREV_ACTION_Y_NAME)
        except ValueError as exc:
            raise BCTrainingError(f"prev-action feature missing from globals: {exc}")
        if ix != 15 or iy != 16:
            raise BCTrainingError(
                f"prev_action indices must be (15, 16); got ({ix}, {iy}) — "
                "feature order disagrees with the frozen schema"
            )
        self.prev_action_indices = (ix, iy)
        self.group_names = tuple(spec.name for spec in BCPolicyConfig().group_specs)

        self.policy_config = BCPolicyConfig(
            global_dim=len(names),
            previous_action_dropout_p=config.previous_action_dropout_p,
            prev_action_indices=(ix, iy),
        )
        self.model = BCPolicyV1(self.policy_config).to(device)

        resident = device if config.data_on_device else torch.device("cpu")
        self.train_split = _build_device_split(
            dataset.train, dataset.normalization, self.group_names,
            self.prev_action_indices, resident, pin=not config.data_on_device,
        )
        self.val_split = _build_device_split(
            dataset.val, dataset.normalization, self.group_names,
            self.prev_action_indices, resident, pin=not config.data_on_device,
        )

        self.optimizer = torch.optim.AdamW(
            self.model.parameters(), lr=config.lr, weight_decay=config.weight_decay
        )
        self.scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
            self.optimizer, T_max=max(config.max_epochs, 1), eta_min=config.lr_min
        )

    # -- seeding ------------------------------------------------------------
    @staticmethod
    def _seed_everything(seed: int) -> None:
        import random

        random.seed(seed)
        np.random.seed(seed)
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)

    # -- batching -----------------------------------------------------------
    def _gather(self, split: DeviceSplit, idx: Tensor) -> tuple[Tensor, dict[str, Tensor], dict[str, Tensor], Tensor]:
        """Index a minibatch and place it on the compute device.

        When the split is already resident on the compute device the index runs
        there directly; when it lives in (pinned) CPU memory we gather on CPU and
        copy the small minibatch across, non-blocking.
        """
        if split.resident_device == self.device:
            i = idx.to(self.device)
            globals_b = split.globals.index_select(0, i)
            entities_b = {g: split.entities[g].index_select(0, i) for g in self.group_names}
            masks_b = {g: split.masks[g].index_select(0, i) for g in self.group_names}
            actions_b = split.actions.index_select(0, i)
            return globals_b, entities_b, masks_b, actions_b

        globals_b = split.globals.index_select(0, idx).to(self.device, non_blocking=True)
        entities_b = {
            g: split.entities[g].index_select(0, idx).to(self.device, non_blocking=True)
            for g in self.group_names
        }
        masks_b = {
            g: split.masks[g].index_select(0, idx).to(self.device, non_blocking=True)
            for g in self.group_names
        }
        actions_b = split.actions.index_select(0, idx).to(self.device, non_blocking=True)
        return globals_b, entities_b, masks_b, actions_b

    # -- one training epoch -------------------------------------------------
    def train_epoch(self, epoch: int) -> dict[str, float]:
        cfg = self.config
        self.model.train()
        n = self.train_split.size
        gen = torch.Generator(device="cpu").manual_seed(cfg.seed + epoch)
        perm = torch.randperm(n, generator=gen)

        total_loss = 0.0
        total_dir = 0.0
        total_mag = 0.0
        seen = 0
        for start in range(0, n, cfg.batch_size):
            idx = perm[start : start + cfg.batch_size]
            globals_b, entities_b, masks_b, actions_b = self._gather(self.train_split, idx)
            pred = self.model(globals_b, entities_b, masks_b)
            loss, comp = bc_loss(
                pred, actions_b, cfg.lambda_mag, cfg.huber_delta, cfg.mag_eps
            )
            self.optimizer.zero_grad(set_to_none=True)
            loss.backward()
            self.optimizer.step()

            bs = int(idx.shape[0])
            total_loss += float(loss.detach().cpu().item()) * bs
            total_dir += float(comp["direction_term"].cpu().item()) * bs
            total_mag += float(comp["magnitude_term"].cpu().item()) * bs
            seen += bs

        return {
            "train_loss": total_loss / max(seen, 1),
            "train_direction_term": total_dir / max(seen, 1),
            "train_magnitude_term": total_mag / max(seen, 1),
            "lr": self.optimizer.param_groups[0]["lr"],
        }

    # -- validation ---------------------------------------------------------
    @torch.no_grad()
    def _predict(self, split: DeviceSplit) -> Tensor:
        self.model.eval()
        n = split.size
        preds: list[Tensor] = []
        for start in range(0, n, self.config.batch_size):
            idx = torch.arange(start, min(start + self.config.batch_size, n))
            globals_b, entities_b, masks_b, _ = self._gather(split, idx)
            preds.append(self.model(globals_b, entities_b, masks_b))
        return torch.cat(preds, dim=0)

    @torch.no_grad()
    def evaluate(self) -> dict[str, Any]:
        cfg = self.config
        split = self.val_split
        pred = self._predict(split)
        target = split.actions.to(pred.device)

        loss, comp = bc_loss(pred, target, cfg.lambda_mag, cfg.huber_delta, cfg.mag_eps)
        metrics: dict[str, Any] = {
            "val_loss": _f(loss),
            "val_direction_term": _f(comp["direction_term"]),
            "val_magnitude_term": _f(comp["magnitude_term"]),
        }
        metrics.update({f"val_{k}": v for k, v in evaluate_predictions(pred, target, cfg.mag_eps).items()})

        # Stratified metrics.
        wave_band = split.wave_band.to(pred.device)
        risk_bin = split.risk_bin.to(pred.device)
        metrics["by_wave_band"] = self._stratify(pred, target, wave_band, len(WAVE_BAND_LABELS), WAVE_BAND_LABELS)
        metrics["by_risk_stratum"] = self._stratify(pred, target, risk_bin, len(RISK_BIN_LABELS), RISK_BIN_LABELS)
        return metrics

    def _stratify(
        self, pred: Tensor, target: Tensor, strata: Tensor, n_bins: int, labels: tuple[str, ...]
    ) -> dict[str, dict[str, float]]:
        out: dict[str, dict[str, float]] = {}
        for b in range(n_bins):
            sel = strata == b
            count = int(sel.sum().item())
            if count == 0:
                out[labels[b]] = {"n": 0}
                continue
            out[labels[b]] = evaluate_predictions(pred[sel], target[sel], self.config.mag_eps)
        return out

    # -- baselines ----------------------------------------------------------
    @torch.no_grad()
    def baselines(self) -> dict[str, Any]:
        cfg = self.config
        val = self.val_split
        target = self.val_split.actions.to(self.device)

        # (a) circular mean of TRAIN action angles, evaluated on val.
        train_actions = self.train_split.actions.to(self.device)
        mean_dir = circular_mean_direction(train_actions, cfg.mag_eps)
        mean_pred = mean_dir.unsqueeze(0).expand(target.shape[0], 2).contiguous()
        mean_metrics = evaluate_predictions(mean_pred, target, cfg.mag_eps)
        mean_metrics["direction"] = [float(mean_dir[0]), float(mean_dir[1])]

        # (b) copy-previous: UNNORMALIZED val previous_action columns.
        prev_pred = val.prev_action.to(self.device)
        prev_metrics = evaluate_predictions(prev_pred, target, cfg.mag_eps)

        return {"mean_direction": mean_metrics, "copy_previous": prev_metrics}

    def step_scheduler(self) -> None:
        self.scheduler.step()


# ---------------------------------------------------------------------------
# Smoke subsampling
# ---------------------------------------------------------------------------
def _subsample_split(split: BCSplit, n: int, seed: int) -> BCSplit:
    total = split.size
    if n >= total:
        return split
    rng = np.random.default_rng(seed)
    idx = np.sort(rng.choice(total, size=n, replace=False))
    return BCSplit(
        globals=split.globals[idx],
        actions=split.actions[idx],
        entities={g: split.entities[g][idx] for g in split.entities},
        masks={g: split.masks[g][idx] for g in split.masks},
        wave=split.wave[idx],
        run_index=split.run_index[idx],
        run_ids=list(split.run_ids),
    )


def _subsample_dataset(dataset: BCDataset, seed: int, train_n: int, val_n: int) -> BCDataset:
    return BCDataset(
        train=_subsample_split(dataset.train, train_n, seed),
        val=_subsample_split(dataset.val, val_n, seed + 1),
        normalization=dataset.normalization,
        schema_hash=dataset.schema_hash,
        split_id=dataset.split_id,
        global_feature_names=list(dataset.global_feature_names),
        input_config_hash=dataset.input_config_hash,
        split_config_hash=dataset.split_config_hash,
    )


# ---------------------------------------------------------------------------
# Device selection + git
# ---------------------------------------------------------------------------
def resolve_device(spec: str) -> torch.device:
    spec = spec.lower()
    if spec == "auto":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if spec == "cuda" and not torch.cuda.is_available():
        raise BCTrainingError("device 'cuda' requested but CUDA is unavailable")
    return torch.device(spec)


def _git_commit() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=True,
        )
        return out.stdout.strip()
    except Exception:  # pragma: no cover - git absent
        return "unknown"


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------
def run_training(
    config: BCTrainConfig,
    config_hash: str,
    *,
    run_name: str | None = None,
    smoke: bool = False,
    smoke_train_n: int = 16384,
    smoke_val_n: int = 8192,
    log: Any = print,
) -> dict[str, Any]:
    """Full training run: load, seed, loop, checkpoint, log, write registry.

    Returns a summary dict (run_name, paths, best/final metrics, baselines).
    """
    device = resolve_device(config.device)
    started = time.time()
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    if run_name is None:
        run_name = f"bc_v1_s{config.seed}_{timestamp}"

    max_epochs = 2 if smoke else config.max_epochs

    log(f"[bc] loading dataset from {config.dataset_dir} ...")
    dataset = load_bc_dataset(
        config.dataset_dir, config.split_config, config.input_config, config.schema
    )
    log(
        f"[bc] loaded split_id={dataset.split_id} "
        f"train={dataset.train.size} val={dataset.val.size} "
        f"global_dim={dataset.train.globals.shape[1]}"
    )
    if smoke:
        dataset = _subsample_dataset(dataset, config.seed, smoke_train_n, smoke_val_n)
        log(f"[bc] SMOKE: subsampled train={dataset.train.size} val={dataset.val.size}, max_epochs={max_epochs}")

    run_dir = config.output_root / run_name
    run_dir.mkdir(parents=True, exist_ok=True)
    metrics_path = run_dir / "metrics.jsonl"
    norm_manifest_path = run_dir / "normalization_manifest.json"
    best_ckpt_path = run_dir / "best.pt"
    last_ckpt_path = run_dir / "last.pt"

    dataset.save_normalization_manifest(norm_manifest_path)
    norm_manifest_hash = _sha256_file(norm_manifest_path)

    trainer = BCTrainer(dataset, config, device)
    log(f"[bc] device={device} params={trainer.model.num_parameters():,} data_on_device={config.data_on_device}")

    baselines = trainer.baselines()
    log(
        "[bc] baseline mean-direction: "
        f"median_ang={baselines['mean_direction']['median_angular_error_deg']:.2f}° "
        f"mean_ang={baselines['mean_direction']['mean_angular_error_deg']:.2f}° | "
        "copy-previous: "
        f"median_ang={baselines['copy_previous']['median_angular_error_deg']:.2f}° "
        f"mean_ang={baselines['copy_previous']['mean_angular_error_deg']:.2f}°"
    )

    config_snapshot = config.as_dict()
    header = {
        "record": "header",
        "run_name": run_name,
        "timestamp": timestamp,
        "device": str(device),
        "smoke": smoke,
        "config": config_snapshot,
        "config_hash": config_hash,
        "split_id": dataset.split_id,
        "schema_hash": dataset.schema_hash,
        "train_size": dataset.train.size,
        "val_size": dataset.val.size,
        "model_parameters": trainer.model.num_parameters(),
        "baselines": baselines,
    }
    with metrics_path.open("w", encoding="utf-8") as handle:
        handle.write(json.dumps(header) + "\n")

    stopper = EarlyStopper(patience=config.early_stopping_patience)
    best_val_metrics: dict[str, Any] = {}
    last_val_metrics: dict[str, Any] = {}
    epochs_run = 0

    for epoch in range(max_epochs):
        epoch_start = time.time()
        train_metrics = trainer.train_epoch(epoch)
        val_metrics = trainer.evaluate()
        trainer.step_scheduler()
        epoch_wall = time.time() - epoch_start
        epochs_run = epoch + 1

        improved = stopper.update(val_metrics["val_loss"], epoch)
        last_val_metrics = val_metrics
        record = {
            "record": "epoch",
            "epoch": epoch,
            "epoch_wall_sec": round(epoch_wall, 3),
            "improved": improved,
            **train_metrics,
            **val_metrics,
        }
        with metrics_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record) + "\n")

        log(
            f"[bc] epoch {epoch:02d} "
            f"train_loss={train_metrics['train_loss']:.4f} "
            f"val_loss={val_metrics['val_loss']:.4f} "
            f"val_med_ang={val_metrics['val_median_angular_error_deg']:.2f}° "
            f"val_cos={val_metrics['val_mean_cosine']:.3f} "
            f"lr={train_metrics['lr']:.2e} "
            f"{'*best' if improved else ''} "
            f"({epoch_wall:.1f}s)"
        )

        save_checkpoint(last_ckpt_path, trainer.model, config_snapshot, epoch, val_metrics)
        if improved:
            best_val_metrics = val_metrics
            save_checkpoint(best_ckpt_path, trainer.model, config_snapshot, epoch, val_metrics)

        if stopper.should_stop:
            log(f"[bc] early stopping at epoch {epoch} (best epoch {stopper.best_epoch})")
            break

    if not best_val_metrics:  # never improved (e.g. 1-epoch runs)
        best_val_metrics = last_val_metrics
        save_checkpoint(best_ckpt_path, trainer.model, config_snapshot, epochs_run - 1, last_val_metrics)

    wall = time.time() - started

    # Registry manifest (tracked; small).
    registry_dir = config.output_root.parent / "registry"
    registry_dir.mkdir(parents=True, exist_ok=True)
    registry_path = registry_dir / f"{run_name}.json"
    manifest_json = (config.dataset_dir / "manifest.json").read_bytes()
    registry = {
        "run_name": run_name,
        "timestamp": timestamp,
        "smoke": smoke,
        "git_commit": _git_commit(),
        "device": str(device),
        "wall_time_sec": round(wall, 2),
        "epochs_run": epochs_run,
        "best_epoch": stopper.best_epoch,
        "config_hash": config_hash,
        "resolved_config": config_snapshot,
        "seed": config.seed,
        "split_id": dataset.split_id,
        "schema_hash": dataset.schema_hash,
        "dataset_manifest_hash": _sha256_bytes(manifest_json),
        "normalization_manifest_hash": norm_manifest_hash,
        "checkpoints": {
            "best": {"path": str(best_ckpt_path), "sha256": _sha256_file(best_ckpt_path)},
            "last": {"path": str(last_ckpt_path), "sha256": _sha256_file(last_ckpt_path)},
        },
        "baselines": baselines,
        "best_val_metrics": best_val_metrics,
        "final_val_metrics": last_val_metrics,
        "environment": {
            "python": platform.python_version(),
            "torch": torch.__version__,
            "numpy": np.__version__,
            "cuda": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        },
    }
    registry_path.write_text(json.dumps(registry, indent=2, sort_keys=True), encoding="utf-8")
    log(f"[bc] wrote registry -> {registry_path}")

    return {
        "run_name": run_name,
        "run_dir": str(run_dir),
        "registry_path": str(registry_path),
        "epochs_run": epochs_run,
        "best_epoch": stopper.best_epoch,
        "wall_time_sec": wall,
        "device": str(device),
        "baselines": baselines,
        "best_val_metrics": best_val_metrics,
        "final_val_metrics": last_val_metrics,
    }
