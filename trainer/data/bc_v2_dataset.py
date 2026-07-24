"""Composite BC dataset loader for WP2 M4 (DAgger round 1, bc_v2).

Assembles the training corpus for bc_v2 candidates A and B:

  * the frozen ``combat_obs_v1`` TRAIN split, loaded EXACTLY as bc_v1 loaded it
    (same split config, same input mask, same valid&temporal filtering) — every
    base row carries loss weight 1.0;
  * the ``combat_dagger_r1`` corrective shards (all valid&temporal rows), each
    row carrying its build-time event weight scaled by a single scalar ``s`` so
    the corrective set carries 25% of the effective batch mass.

Normalization follows the bc_v1 approach but is recomputed over the COMPOSITE
train globals (base train + dagger train), train-only, globals standardized,
entities identity. Validation is the frozen ``combat_obs_v1`` val split,
UNCHANGED, for direct comparability with bc_v1.

A deterministic 10% of the dagger rows is held out (excluded from training for
BOTH candidates, so A and B train on identical data) and returned separately so
candidate B's aux heads can be scored on rows with real aux labels (the frozen
val split has none).

This module never modifies ``bc_dataset.py`` or the frozen datasets; it reuses
the loader's verified primitives (shard sha256 checks, index resolution, split
dataclasses) and adds the composite/weight/aux concerns on top.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from trainer.data.bc_dataset import (
    ENTITY_FEATURE_DIM,
    ENTITY_GROUPS,
    STD_FLOOR,
    BCDataset,
    BCDatasetError,
    BCSplit,
    NormalizationStats,
    _global_feature_names,
    _load_yaml,
    _resolve_indices,
    _sha256_upper,
    load_bc_dataset,
)

import yaml

# Corrective mass target: dagger effective mass / base effective mass = 0.25/0.75.
# With reduction sum(w*loss)/sum(w), this yields a 25% dagger contribution to the
# per-batch (and expected per-epoch) gradient mass.
DEFAULT_TARGET_MASS_RATIO = 0.25 / 0.75

# Deterministic aux-holdout split (excluded from training for both candidates).
DEFAULT_HOLDOUT_FRAC = 0.10
DEFAULT_HOLDOUT_SEED = 20260724


@dataclass(frozen=True)
class CompositeBCDataset:
    """bc_v2 composite training corpus + frozen val + aux side arrays."""

    # Splits (globals are UNNORMALIZED [N, 40]; entities identity).
    train: BCSplit  # base train ++ dagger train (in that row order)
    val: BCSplit  # frozen combat_obs_v1 val, unchanged
    normalization: NormalizationStats  # computed over composite train globals

    # Per-train-row side arrays, aligned to ``train`` row order.
    train_weight: np.ndarray  # [Ntrain] f32 (base=1.0, dagger=event_weight*s)
    train_is_dagger: np.ndarray  # [Ntrain] bool
    train_aux_damage: np.ndarray  # [Ntrain] f32 (0 for base)
    train_aux_damage_mask: np.ndarray  # [Ntrain] bool (False for base)
    train_aux_margin: np.ndarray  # [Ntrain] f32 (0 for base)
    train_aux_margin_mask: np.ndarray  # [Ntrain] bool (False for base)

    # Aux-holdout dagger rows (excluded from training).
    aux_holdout: BCSplit
    holdout_aux_damage: np.ndarray
    holdout_aux_damage_mask: np.ndarray
    holdout_aux_margin: np.ndarray
    holdout_aux_margin_mask: np.ndarray

    # Provenance / bookkeeping.
    schema_hash: str
    split_id: str
    global_feature_names: list[str]
    input_config_hash: str
    split_config_hash: str
    base_manifest_hash: str
    dagger_manifest_hash: str
    s_scalar: float
    base_weight_sum: float
    dagger_weight_sum: float
    achieved_mass_fraction: float
    n_base_train: int
    n_dagger_train: int
    n_dagger_holdout: int
    aux_base_rates: dict[str, float]

    # -- Multi-corrective provenance (populated only by
    #    ``load_multi_composite_dataset``; empty for the single-set loader so the
    #    single-set path stays byte-identical and every existing test/caller is
    #    unaffected). ``per_set_holdouts`` holds each corrective set's own
    #    deterministic holdout split, in the same order as ``dagger_dataset_dirs``.
    dagger_dataset_dirs: tuple[str, ...] = ()
    dagger_manifest_hashes: tuple[str, ...] = ()
    per_set_s_scalars: tuple[float, ...] = ()
    per_set_n_train: tuple[int, ...] = ()
    per_set_n_holdout: tuple[int, ...] = ()
    per_set_event_weight_sums: tuple[float, ...] = ()
    per_set_weight_sums: tuple[float, ...] = ()
    per_set_holdouts: tuple[BCSplit, ...] = ()
    total_mass_ratio: float | None = None

    def save_normalization_manifest(self, path: str | Path) -> None:
        """Write the composite train-only normalization stats (bc_v1 format)."""
        # Reuse BCDataset's writer verbatim so the manifest schema is identical.
        proxy = BCDataset(
            train=self.train,
            val=self.val,
            normalization=self.normalization,
            schema_hash=self.schema_hash,
            split_id=self.split_id,
            global_feature_names=list(self.global_feature_names),
            input_config_hash=self.input_config_hash,
            split_config_hash=self.split_config_hash,
        )
        proxy.save_normalization_manifest(path)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


# ---------------------------------------------------------------------------
# Dagger shard + aux + weight loading (keep = valid & temporal, aligned)
# ---------------------------------------------------------------------------
def _load_dagger_run(
    run_entry: dict[str, Any],
    dataset_dir: Path,
    kept_indices: np.ndarray,
    label_indices: list[int],
) -> dict[str, Any]:
    """Load one dagger run's shard + aux + weights, filtered to valid&temporal.

    Every sha256 in the manifest entry is verified against the file on disk.
    The shard, aux and weight arrays are filtered with the SAME ``keep`` mask in
    the SAME row order, so their alignment is guaranteed by construction.
    """
    run_id = str(run_entry["run_id"])
    shard_file = str(run_entry.get("shard_file", f"{run_id}.npz"))
    shard_path = dataset_dir / shard_file
    if not shard_path.is_file():
        raise BCDatasetError(f"dagger shard missing: {shard_path}")
    if _sha256_upper(shard_path) != str(run_entry["shard_sha256"]).upper():
        raise BCDatasetError(f"dagger shard sha256 mismatch for {run_id}")

    aux_path = dataset_dir / str(run_entry["aux_file"])
    if not aux_path.is_file():
        raise BCDatasetError(f"dagger aux file missing: {aux_path}")
    if _sha256_upper(aux_path) != str(run_entry["aux_sha256"]).upper():
        raise BCDatasetError(f"dagger aux sha256 mismatch for {run_id}")

    weights_path = dataset_dir / str(run_entry["weights_file"])
    if not weights_path.is_file():
        raise BCDatasetError(f"dagger weights file missing: {weights_path}")
    if _sha256_upper(weights_path) != str(run_entry["weights_sha256"]).upper():
        raise BCDatasetError(f"dagger weights sha256 mismatch for {run_id}")

    with np.load(shard_path) as shard:
        valid = np.asarray(shard["valid"], dtype=bool)
        temporal = np.asarray(shard["temporal_valid"], dtype=bool)
        keep = valid & temporal
        n_keep = int(keep.sum())
        if n_keep == 0:
            raise BCDatasetError(f"dagger {run_id} has no valid&temporal samples")

        raw_globals = np.asarray(shard["global_features"], dtype=np.float32)
        if raw_globals.ndim != 2 or raw_globals.shape[1] != 48:
            raise BCDatasetError(
                f"dagger {run_id} global_features shape {raw_globals.shape}, expected [N, 48]"
            )
        filtered = raw_globals[keep]
        out: dict[str, Any] = {
            "run_id": run_id,
            "n_keep": n_keep,
            "globals": filtered[:, kept_indices],
            "actions": filtered[:, label_indices],
            "entities": {},
            "masks": {},
        }
        for group, capacity in ENTITY_GROUPS:
            ent = np.asarray(shard[f"entities_{group}"], dtype=np.float32)
            msk = np.asarray(shard[f"mask_{group}"], dtype=np.float32)
            if ent.shape[1:] != (capacity, ENTITY_FEATURE_DIM):
                raise BCDatasetError(
                    f"dagger {run_id} entities_{group} shape {ent.shape}, "
                    f"expected [N, {capacity}, {ENTITY_FEATURE_DIM}]"
                )
            if msk.shape[1:] != (capacity,):
                raise BCDatasetError(
                    f"dagger {run_id} mask_{group} shape {msk.shape}, expected [N, {capacity}]"
                )
            out["entities"][group] = ent[keep]
            out["masks"][group] = msk[keep]
        out["wave"] = np.asarray(shard["wave"], dtype=np.int32)[keep]

    with np.load(aux_path) as aux:
        for key in ("aux_damage", "aux_damage_mask", "aux_margin", "aux_margin_mask"):
            arr = np.asarray(aux[key])
            if arr.shape[0] != keep.shape[0]:
                raise BCDatasetError(
                    f"dagger {run_id} aux {key} length {arr.shape[0]} != shard rows {keep.shape[0]}"
                )
        out["aux_damage"] = np.asarray(aux["aux_damage"], dtype=np.float32)[keep]
        out["aux_damage_mask"] = np.asarray(aux["aux_damage_mask"], dtype=bool)[keep]
        out["aux_margin"] = np.asarray(aux["aux_margin"], dtype=np.float32)[keep]
        out["aux_margin_mask"] = np.asarray(aux["aux_margin_mask"], dtype=bool)[keep]

    with np.load(weights_path) as wz:
        weight = np.asarray(wz["weight"])
        if weight.shape[0] != keep.shape[0]:
            raise BCDatasetError(
                f"dagger {run_id} weight length {weight.shape[0]} != shard rows {keep.shape[0]}"
            )
        out["event_weight"] = np.asarray(wz["weight"], dtype=np.float32)[keep]

    return out


def _concat_dagger(runs: list[dict[str, Any]]) -> dict[str, Any]:
    """Concatenate per-run dagger arrays in manifest order."""
    group_names = [g for g, _ in ENTITY_GROUPS]
    agg: dict[str, Any] = {
        "globals": np.concatenate([r["globals"] for r in runs], axis=0),
        "actions": np.concatenate([r["actions"] for r in runs], axis=0),
        "entities": {
            g: np.concatenate([r["entities"][g] for r in runs], axis=0) for g in group_names
        },
        "masks": {
            g: np.concatenate([r["masks"][g] for r in runs], axis=0) for g in group_names
        },
        "wave": np.concatenate([r["wave"] for r in runs], axis=0),
        "aux_damage": np.concatenate([r["aux_damage"] for r in runs], axis=0),
        "aux_damage_mask": np.concatenate([r["aux_damage_mask"] for r in runs], axis=0),
        "aux_margin": np.concatenate([r["aux_margin"] for r in runs], axis=0),
        "aux_margin_mask": np.concatenate([r["aux_margin_mask"] for r in runs], axis=0),
        "event_weight": np.concatenate([r["event_weight"] for r in runs], axis=0),
        "run_ids": [r["run_id"] for r in runs],
        "run_index": np.concatenate(
            [np.full(r["n_keep"], i, dtype=np.int32) for i, r in enumerate(runs)], axis=0
        ),
    }
    return agg


def _index_dagger(agg: dict[str, Any], idx: np.ndarray) -> dict[str, Any]:
    group_names = [g for g, _ in ENTITY_GROUPS]
    return {
        "globals": agg["globals"][idx],
        "actions": agg["actions"][idx],
        "entities": {g: agg["entities"][g][idx] for g in group_names},
        "masks": {g: agg["masks"][g][idx] for g in group_names},
        "wave": agg["wave"][idx],
        "aux_damage": agg["aux_damage"][idx],
        "aux_damage_mask": agg["aux_damage_mask"][idx],
        "aux_margin": agg["aux_margin"][idx],
        "aux_margin_mask": agg["aux_margin_mask"][idx],
        "event_weight": agg["event_weight"][idx],
        "run_index": agg["run_index"][idx],
        "run_ids": list(agg["run_ids"]),
    }


def _deterministic_holdout_split(
    n_rows: int, holdout_frac: float, holdout_seed: int
) -> tuple[np.ndarray, np.ndarray]:
    """Return (train_idx, hold_idx) using the SAME rng logic as the single-set
    loader: permute ``n_rows`` under ``holdout_seed``, hold the first
    ``round(n*frac)``, keep the rest, both sorted ascending. Identical to the
    inline split in :func:`load_composite_dataset` so a corrective set carved out
    here reproduces the single-set loader's holdout rows exactly."""
    rng = np.random.default_rng(holdout_seed)
    perm = rng.permutation(n_rows)
    n_hold = int(round(n_rows * holdout_frac))
    hold_idx = np.sort(perm[:n_hold])
    train_idx = np.sort(perm[n_hold:])
    return train_idx, hold_idx


def solve_mass_scalar(
    base_weight_sum: float,
    dagger_event_weight_sum: float,
    target_mass_ratio: float = DEFAULT_TARGET_MASS_RATIO,
) -> float:
    """Solve ``s`` so ``s * sum(event_weight) == target_ratio * sum(base_weight)``.

    With base rows at weight 1.0, ``sum(base_weight) == N_base`` and the achieved
    dagger:base effective-mass ratio equals ``target_mass_ratio``.
    """
    if dagger_event_weight_sum <= 0.0:
        raise BCDatasetError("dagger event-weight sum must be positive")
    return float(target_mass_ratio * base_weight_sum / dagger_event_weight_sum)


# ---------------------------------------------------------------------------
# Public loader
# ---------------------------------------------------------------------------
def load_composite_dataset(
    base_dataset_dir: str | Path,
    dagger_dataset_dir: str | Path,
    split_config_path: str | Path,
    input_config_path: str | Path,
    schema_path: str | Path,
    *,
    holdout_frac: float = DEFAULT_HOLDOUT_FRAC,
    holdout_seed: int = DEFAULT_HOLDOUT_SEED,
    target_mass_ratio: float = DEFAULT_TARGET_MASS_RATIO,
) -> CompositeBCDataset:
    """Assemble the bc_v2 composite dataset with full verification."""
    base_dataset_dir = Path(base_dataset_dir)
    dagger_dataset_dir = Path(dagger_dataset_dir)

    # -- base (loaded EXACTLY as bc_v1) -------------------------------------
    base = load_bc_dataset(base_dataset_dir, split_config_path, input_config_path, schema_path)
    base_manifest_hash = _sha256_bytes((base_dataset_dir / "manifest.json").read_bytes())

    # -- resolve the same kept/label indices for the dagger shards ----------
    schema = yaml.safe_load(Path(schema_path).read_text(encoding="utf-8"))
    feature_names = _global_feature_names(schema)
    input_config, _ = _load_yaml(Path(input_config_path))
    excluded = [str(n) for n in input_config.get("excluded_global_features", [])]
    labels = [str(n) for n in input_config.get("label_features", [])]
    kept_indices, kept_names, label_indices = _resolve_indices(feature_names, excluded, labels)
    if kept_names != list(base.global_feature_names):
        raise BCDatasetError("dagger kept feature names disagree with the base dataset")
    kept_arr = np.asarray(kept_indices, dtype=np.intp)

    # -- dagger manifest + schema-hash agreement ----------------------------
    dagger_manifest = json.loads((dagger_dataset_dir / "manifest.json").read_text(encoding="utf-8"))
    if str(dagger_manifest.get("observation_schema_hash", "")).upper() != base.schema_hash:
        raise BCDatasetError("dagger manifest schema hash != base schema hash")
    dagger_manifest_hash = _sha256_bytes((dagger_dataset_dir / "manifest.json").read_bytes())
    run_entries = dagger_manifest.get("runs")
    if not isinstance(run_entries, list) or not run_entries:
        raise BCDatasetError("dagger manifest runs missing or empty")

    dagger_runs = [
        _load_dagger_run(entry, dagger_dataset_dir, kept_arr, label_indices)
        for entry in run_entries
    ]
    agg = _concat_dagger(dagger_runs)
    n_dagger = int(agg["globals"].shape[0])

    # -- deterministic aux-holdout split (excluded from training) -----------
    rng = np.random.default_rng(holdout_seed)
    perm = rng.permutation(n_dagger)
    n_hold = int(round(n_dagger * holdout_frac))
    hold_idx = np.sort(perm[:n_hold])
    train_idx = np.sort(perm[n_hold:])
    dagger_train = _index_dagger(agg, train_idx)
    dagger_hold = _index_dagger(agg, hold_idx)
    n_dagger_train = int(train_idx.shape[0])
    n_dagger_holdout = int(hold_idx.shape[0])

    # -- corrective mass scalar (over TRAINING dagger rows) -----------------
    base_weight_sum = float(base.train.size)  # every base row weight 1.0
    dagger_event_sum = float(dagger_train["event_weight"].sum())
    s = solve_mass_scalar(base_weight_sum, dagger_event_sum, target_mass_ratio)
    dagger_train_weight = (dagger_train["event_weight"] * s).astype(np.float32)
    dagger_weight_sum = float(dagger_train_weight.sum())
    achieved_mass_fraction = dagger_weight_sum / (base_weight_sum + dagger_weight_sum)

    # -- composite train split (base ++ dagger train) -----------------------
    group_names = [g for g, _ in ENTITY_GROUPS]
    n_base = int(base.train.size)
    train_globals = np.concatenate([base.train.globals, dagger_train["globals"]], axis=0)
    train_actions = np.concatenate([base.train.actions, dagger_train["actions"]], axis=0)
    train_entities = {
        g: np.concatenate([base.train.entities[g], dagger_train["entities"][g]], axis=0)
        for g in group_names
    }
    train_masks = {
        g: np.concatenate([base.train.masks[g], dagger_train["masks"][g]], axis=0)
        for g in group_names
    }
    train_wave = np.concatenate([base.train.wave, dagger_train["wave"]], axis=0)
    train_run_index = np.concatenate(
        [base.train.run_index, dagger_train["run_index"] + len(base.train.run_ids)], axis=0
    ).astype(np.int32)
    train_run_ids = list(base.train.run_ids) + list(dagger_train["run_ids"])

    composite_train = BCSplit(
        globals=train_globals,
        actions=train_actions,
        entities=train_entities,
        masks=train_masks,
        wave=train_wave,
        run_index=train_run_index,
        run_ids=train_run_ids,
    )

    # -- per-train-row side arrays ------------------------------------------
    train_weight = np.concatenate(
        [np.ones(n_base, dtype=np.float32), dagger_train_weight], axis=0
    )
    train_is_dagger = np.concatenate(
        [np.zeros(n_base, dtype=bool), np.ones(n_dagger_train, dtype=bool)], axis=0
    )
    train_aux_damage = np.concatenate(
        [np.zeros(n_base, dtype=np.float32), dagger_train["aux_damage"]], axis=0
    )
    train_aux_damage_mask = np.concatenate(
        [np.zeros(n_base, dtype=bool), dagger_train["aux_damage_mask"]], axis=0
    )
    train_aux_margin = np.concatenate(
        [np.zeros(n_base, dtype=np.float32), dagger_train["aux_margin"]], axis=0
    )
    train_aux_margin_mask = np.concatenate(
        [np.zeros(n_base, dtype=bool), dagger_train["aux_margin_mask"]], axis=0
    )

    # -- composite normalization (train-only, over the composite train) -----
    mean = train_globals.mean(axis=0).astype(np.float32)
    std = np.maximum(train_globals.std(axis=0).astype(np.float32), np.float32(STD_FLOOR))
    normalization = NormalizationStats(
        feature_names=list(kept_names),
        mean=mean,
        std=std,
        split_id=base.split_id,
        schema_hash=base.schema_hash,
        input_config_hash=base.input_config_hash,
        split_config_hash=base.split_config_hash,
    )

    # -- aux-holdout split ---------------------------------------------------
    aux_holdout = BCSplit(
        globals=dagger_hold["globals"],
        actions=dagger_hold["actions"],
        entities=dagger_hold["entities"],
        masks=dagger_hold["masks"],
        wave=dagger_hold["wave"],
        run_index=dagger_hold["run_index"].astype(np.int32),
        run_ids=list(dagger_hold["run_ids"]),
    )

    aux_base_rates = {
        "train_aux_damage_base_rate": float(
            dagger_train["aux_damage"][dagger_train["aux_damage_mask"]].mean()
        )
        if bool(dagger_train["aux_damage_mask"].any())
        else float("nan"),
        "train_aux_margin_mean": float(
            dagger_train["aux_margin"][dagger_train["aux_margin_mask"]].mean()
        )
        if bool(dagger_train["aux_margin_mask"].any())
        else float("nan"),
        "holdout_aux_damage_base_rate": float(
            dagger_hold["aux_damage"][dagger_hold["aux_damage_mask"]].mean()
        )
        if bool(dagger_hold["aux_damage_mask"].any())
        else float("nan"),
        "holdout_aux_margin_mean": float(
            dagger_hold["aux_margin"][dagger_hold["aux_margin_mask"]].mean()
        )
        if bool(dagger_hold["aux_margin_mask"].any())
        else float("nan"),
    }

    return CompositeBCDataset(
        train=composite_train,
        val=base.val,
        normalization=normalization,
        train_weight=train_weight,
        train_is_dagger=train_is_dagger,
        train_aux_damage=train_aux_damage,
        train_aux_damage_mask=train_aux_damage_mask,
        train_aux_margin=train_aux_margin,
        train_aux_margin_mask=train_aux_margin_mask,
        aux_holdout=aux_holdout,
        holdout_aux_damage=dagger_hold["aux_damage"],
        holdout_aux_damage_mask=dagger_hold["aux_damage_mask"],
        holdout_aux_margin=dagger_hold["aux_margin"],
        holdout_aux_margin_mask=dagger_hold["aux_margin_mask"],
        schema_hash=base.schema_hash,
        split_id=base.split_id,
        global_feature_names=list(kept_names),
        input_config_hash=base.input_config_hash,
        split_config_hash=base.split_config_hash,
        base_manifest_hash=base_manifest_hash,
        dagger_manifest_hash=dagger_manifest_hash,
        s_scalar=s,
        base_weight_sum=base_weight_sum,
        dagger_weight_sum=dagger_weight_sum,
        achieved_mass_fraction=achieved_mass_fraction,
        n_base_train=n_base,
        n_dagger_train=n_dagger_train,
        n_dagger_holdout=n_dagger_holdout,
        aux_base_rates=aux_base_rates,
    )


# ---------------------------------------------------------------------------
# Multi-corrective loader (WP2 M4 round 2: combat_dagger_r1 + combat_dagger_r2)
# ---------------------------------------------------------------------------
def _load_dagger_set(
    dagger_dataset_dir: Path,
    base_schema_hash: str,
    kept_arr: np.ndarray,
    label_indices: list[int],
    holdout_frac: float,
    holdout_seed: int,
) -> dict[str, Any]:
    """Load one corrective dataset dir, carve its OWN deterministic holdout out,
    and return the train/holdout dicts plus provenance for that set. Reuses the
    verified single-set primitives so shard/aux/weight sha256s are checked and
    the holdout rows reproduce :func:`load_composite_dataset` exactly."""
    manifest = json.loads((dagger_dataset_dir / "manifest.json").read_text(encoding="utf-8"))
    if str(manifest.get("observation_schema_hash", "")).upper() != base_schema_hash:
        raise BCDatasetError(
            f"dagger manifest schema hash != base schema hash ({dagger_dataset_dir})"
        )
    manifest_hash = _sha256_bytes((dagger_dataset_dir / "manifest.json").read_bytes())
    run_entries = manifest.get("runs")
    if not isinstance(run_entries, list) or not run_entries:
        raise BCDatasetError(f"dagger manifest runs missing or empty ({dagger_dataset_dir})")

    runs = [
        _load_dagger_run(entry, dagger_dataset_dir, kept_arr, label_indices)
        for entry in run_entries
    ]
    agg = _concat_dagger(runs)
    n_rows = int(agg["globals"].shape[0])
    train_idx, hold_idx = _deterministic_holdout_split(n_rows, holdout_frac, holdout_seed)
    return {
        "dir": str(dagger_dataset_dir),
        "manifest_hash": manifest_hash,
        "agg": agg,
        "train": _index_dagger(agg, train_idx),
        "hold": _index_dagger(agg, hold_idx),
        "n_train": int(train_idx.shape[0]),
        "n_hold": int(hold_idx.shape[0]),
        "n_rows": n_rows,
        "run_ids": list(agg["run_ids"]),
    }


def _dagger_split_from_dict(d: dict[str, Any], run_id_offset: int) -> BCSplit:
    group_names = [g for g, _ in ENTITY_GROUPS]
    return BCSplit(
        globals=d["globals"],
        actions=d["actions"],
        entities={g: d["entities"][g] for g in group_names},
        masks={g: d["masks"][g] for g in group_names},
        wave=d["wave"],
        run_index=(d["run_index"] + run_id_offset).astype(np.int32),
        run_ids=list(d["run_ids"]),
    )


def load_multi_composite_dataset(
    base_dataset_dir: str | Path,
    dagger_dataset_dirs: list[str | Path] | tuple[str | Path, ...],
    split_config_path: str | Path,
    input_config_path: str | Path,
    schema_path: str | Path,
    *,
    holdout_frac: float = DEFAULT_HOLDOUT_FRAC,
    holdout_seed: int = DEFAULT_HOLDOUT_SEED,
    target_mass_ratio: float = DEFAULT_TARGET_MASS_RATIO,
) -> CompositeBCDataset:
    """Assemble a composite corpus over the frozen base + N corrective datasets.

    Each corrective set keeps its OWN build-time event weights and carves its OWN
    deterministic 10% holdout (same seed/logic as the single-set loader, so those
    holdout rows are reproducible via ``load_composite_dataset`` on that dir).
    The single ``target_mass_ratio`` fixes the TOTAL corrective effective mass;
    that mass is split across sets PROPORTIONAL TO their training row counts, and
    within each set distributed by that set's event weights. With one dir this is
    numerically identical to :func:`load_composite_dataset`.

    The returned ``train`` is ``base_train ++ set0_train ++ set1_train ++ ...``.
    The singular provenance fields carry aggregate values; ``per_set_*`` and
    ``per_set_holdouts`` carry the per-set breakdown (in dir order).
    """
    base_dataset_dir = Path(base_dataset_dir)
    dirs = [Path(d) for d in dagger_dataset_dirs]
    if not dirs:
        raise BCDatasetError("dagger_dataset_dirs must be non-empty")

    # -- base (loaded EXACTLY as bc_v1) -------------------------------------
    base = load_bc_dataset(base_dataset_dir, split_config_path, input_config_path, schema_path)
    base_manifest_hash = _sha256_bytes((base_dataset_dir / "manifest.json").read_bytes())

    # -- resolve the same kept/label indices for the dagger shards ----------
    schema = yaml.safe_load(Path(schema_path).read_text(encoding="utf-8"))
    feature_names = _global_feature_names(schema)
    input_config, _ = _load_yaml(Path(input_config_path))
    excluded = [str(n) for n in input_config.get("excluded_global_features", [])]
    labels = [str(n) for n in input_config.get("label_features", [])]
    kept_indices, kept_names, label_indices = _resolve_indices(feature_names, excluded, labels)
    if kept_names != list(base.global_feature_names):
        raise BCDatasetError("dagger kept feature names disagree with the base dataset")
    kept_arr = np.asarray(kept_indices, dtype=np.intp)

    sets = [
        _load_dagger_set(d, base.schema_hash, kept_arr, label_indices, holdout_frac, holdout_seed)
        for d in dirs
    ]

    # -- pool the total corrective mass across sets, proportional to row count
    base_weight_sum = float(base.train.size)  # every base row weight 1.0
    total_target_weight_sum = float(target_mass_ratio) * base_weight_sum
    total_n_train = sum(s["n_train"] for s in sets)
    if total_n_train <= 0:
        raise BCDatasetError("no corrective training rows across all sets")

    for s in sets:
        s["event_weight_sum"] = float(s["train"]["event_weight"].sum())
        if s["event_weight_sum"] <= 0.0:
            raise BCDatasetError(f"corrective set {s['dir']} has non-positive event-weight sum")
        share = s["n_train"] / total_n_train
        s["target_weight_sum"] = total_target_weight_sum * share
        s["s_scalar"] = s["target_weight_sum"] / s["event_weight_sum"]
        s["train_weight"] = (s["train"]["event_weight"] * s["s_scalar"]).astype(np.float32)
        s["weight_sum"] = float(s["train_weight"].sum())

    dagger_weight_sum = float(sum(s["weight_sum"] for s in sets))
    achieved_mass_fraction = dagger_weight_sum / (base_weight_sum + dagger_weight_sum)

    # -- composite train split (base ++ each set's train, in dir order) ------
    group_names = [g for g, _ in ENTITY_GROUPS]
    n_base = int(base.train.size)
    ordered_train = [base.train] + [_dagger_split_from_dict(s["train"], 0) for s in sets]
    # run-id offsets so run_index remains a valid global index into run_ids
    run_ids: list[str] = list(base.train.run_ids)
    train_run_index_parts = [base.train.run_index.astype(np.int32)]
    for s in sets:
        offset = len(run_ids)
        train_run_index_parts.append((s["train"]["run_index"] + offset).astype(np.int32))
        run_ids = run_ids + list(s["train"]["run_ids"])

    train_globals = np.concatenate([sp.globals for sp in ordered_train], axis=0)
    train_actions = np.concatenate([sp.actions for sp in ordered_train], axis=0)
    train_entities = {
        g: np.concatenate([sp.entities[g] for sp in ordered_train], axis=0) for g in group_names
    }
    train_masks = {
        g: np.concatenate([sp.masks[g] for sp in ordered_train], axis=0) for g in group_names
    }
    train_wave = np.concatenate([sp.wave for sp in ordered_train], axis=0)
    train_run_index = np.concatenate(train_run_index_parts, axis=0).astype(np.int32)

    composite_train = BCSplit(
        globals=train_globals,
        actions=train_actions,
        entities=train_entities,
        masks=train_masks,
        wave=train_wave,
        run_index=train_run_index,
        run_ids=run_ids,
    )

    n_dagger_train = int(sum(s["n_train"] for s in sets))

    # -- per-train-row side arrays (base zeros ++ each set's arrays) ---------
    train_weight = np.concatenate(
        [np.ones(n_base, dtype=np.float32)] + [s["train_weight"] for s in sets], axis=0
    )
    train_is_dagger = np.concatenate(
        [np.zeros(n_base, dtype=bool)]
        + [np.ones(s["n_train"], dtype=bool) for s in sets],
        axis=0,
    )
    train_aux_damage = np.concatenate(
        [np.zeros(n_base, dtype=np.float32)] + [s["train"]["aux_damage"] for s in sets], axis=0
    )
    train_aux_damage_mask = np.concatenate(
        [np.zeros(n_base, dtype=bool)] + [s["train"]["aux_damage_mask"] for s in sets], axis=0
    )
    train_aux_margin = np.concatenate(
        [np.zeros(n_base, dtype=np.float32)] + [s["train"]["aux_margin"] for s in sets], axis=0
    )
    train_aux_margin_mask = np.concatenate(
        [np.zeros(n_base, dtype=bool)] + [s["train"]["aux_margin_mask"] for s in sets], axis=0
    )

    # -- composite normalization (train-only, over the composite train) -----
    mean = train_globals.mean(axis=0).astype(np.float32)
    std = np.maximum(train_globals.std(axis=0).astype(np.float32), np.float32(STD_FLOOR))
    normalization = NormalizationStats(
        feature_names=list(kept_names),
        mean=mean,
        std=std,
        split_id=base.split_id,
        schema_hash=base.schema_hash,
        input_config_hash=base.input_config_hash,
        split_config_hash=base.split_config_hash,
    )

    # -- combined aux-holdout (concat of each set's holdout, in dir order) ---
    per_set_holdouts: list[BCSplit] = []
    ho_run_ids: list[str] = []
    for s in sets:
        offset = len(ho_run_ids)
        per_set_holdouts.append(_dagger_split_from_dict(s["hold"], offset))
        ho_run_ids = ho_run_ids + list(s["hold"]["run_ids"])

    hold_globals = np.concatenate([hp.globals for hp in per_set_holdouts], axis=0)
    hold_actions = np.concatenate([hp.actions for hp in per_set_holdouts], axis=0)
    hold_entities = {
        g: np.concatenate([hp.entities[g] for hp in per_set_holdouts], axis=0) for g in group_names
    }
    hold_masks = {
        g: np.concatenate([hp.masks[g] for hp in per_set_holdouts], axis=0) for g in group_names
    }
    hold_wave = np.concatenate([hp.wave for hp in per_set_holdouts], axis=0)
    hold_run_index = np.concatenate([hp.run_index for hp in per_set_holdouts], axis=0).astype(np.int32)
    aux_holdout = BCSplit(
        globals=hold_globals,
        actions=hold_actions,
        entities=hold_entities,
        masks=hold_masks,
        wave=hold_wave,
        run_index=hold_run_index,
        run_ids=ho_run_ids,
    )
    holdout_aux_damage = np.concatenate([s["hold"]["aux_damage"] for s in sets], axis=0)
    holdout_aux_damage_mask = np.concatenate([s["hold"]["aux_damage_mask"] for s in sets], axis=0)
    holdout_aux_margin = np.concatenate([s["hold"]["aux_margin"] for s in sets], axis=0)
    holdout_aux_margin_mask = np.concatenate([s["hold"]["aux_margin_mask"] for s in sets], axis=0)
    n_dagger_holdout = int(sum(s["n_hold"] for s in sets))

    def _rate(vals: np.ndarray, mask: np.ndarray) -> float:
        m = mask.astype(bool)
        return float(vals[m].mean()) if bool(m.any()) else float("nan")

    train_aux_damage_all = np.concatenate([s["train"]["aux_damage"] for s in sets], axis=0)
    train_aux_damage_mask_all = np.concatenate([s["train"]["aux_damage_mask"] for s in sets], axis=0)
    train_aux_margin_all = np.concatenate([s["train"]["aux_margin"] for s in sets], axis=0)
    train_aux_margin_mask_all = np.concatenate([s["train"]["aux_margin_mask"] for s in sets], axis=0)
    aux_base_rates = {
        "train_aux_damage_base_rate": _rate(train_aux_damage_all, train_aux_damage_mask_all),
        "train_aux_margin_mean": _rate(train_aux_margin_all, train_aux_margin_mask_all),
        "holdout_aux_damage_base_rate": _rate(holdout_aux_damage, holdout_aux_damage_mask),
        "holdout_aux_margin_mean": _rate(holdout_aux_margin, holdout_aux_margin_mask),
    }

    # Aggregate singular provenance (per-set detail in the per_set_* tuples).
    combined_event_weight_sum = float(sum(s["event_weight_sum"] for s in sets))
    aggregate_s = dagger_weight_sum / combined_event_weight_sum if combined_event_weight_sum > 0 else float("nan")
    combined_manifest_hash = _sha256_bytes(
        "|".join(s["manifest_hash"] for s in sets).encode("utf-8")
    )

    return CompositeBCDataset(
        train=composite_train,
        val=base.val,
        normalization=normalization,
        train_weight=train_weight,
        train_is_dagger=train_is_dagger,
        train_aux_damage=train_aux_damage,
        train_aux_damage_mask=train_aux_damage_mask,
        train_aux_margin=train_aux_margin,
        train_aux_margin_mask=train_aux_margin_mask,
        aux_holdout=aux_holdout,
        holdout_aux_damage=holdout_aux_damage,
        holdout_aux_damage_mask=holdout_aux_damage_mask,
        holdout_aux_margin=holdout_aux_margin,
        holdout_aux_margin_mask=holdout_aux_margin_mask,
        schema_hash=base.schema_hash,
        split_id=base.split_id,
        global_feature_names=list(kept_names),
        input_config_hash=base.input_config_hash,
        split_config_hash=base.split_config_hash,
        base_manifest_hash=base_manifest_hash,
        dagger_manifest_hash=combined_manifest_hash,
        s_scalar=aggregate_s,
        base_weight_sum=base_weight_sum,
        dagger_weight_sum=dagger_weight_sum,
        achieved_mass_fraction=achieved_mass_fraction,
        n_base_train=n_base,
        n_dagger_train=n_dagger_train,
        n_dagger_holdout=n_dagger_holdout,
        aux_base_rates=aux_base_rates,
        dagger_dataset_dirs=tuple(s["dir"] for s in sets),
        dagger_manifest_hashes=tuple(s["manifest_hash"] for s in sets),
        per_set_s_scalars=tuple(float(s["s_scalar"]) for s in sets),
        per_set_n_train=tuple(int(s["n_train"]) for s in sets),
        per_set_n_holdout=tuple(int(s["n_hold"]) for s in sets),
        per_set_event_weight_sums=tuple(float(s["event_weight_sum"]) for s in sets),
        per_set_weight_sums=tuple(float(s["weight_sum"]) for s in sets),
        per_set_holdouts=tuple(per_set_holdouts),
        total_mass_ratio=float(target_mass_ratio),
    )
