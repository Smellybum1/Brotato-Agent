"""Behavior-cloning dataset loader for ``combat_obs_v1`` (WP2 M2, Stage D).

Loads the frozen ``combat_obs_v1`` NPZ shards, applies the named input mask
(``configs/wp2/bc_input_v1.yaml``) and run-level split
(``configs/wp2/dataset_split_v1.yaml``), and returns a ``BCDataset`` with
train/val splits filtered to ``valid & temporal_valid`` samples.

Design mirrors ``trainer/observation/encoder_v1.py``: frozen dataclasses,
explicit hard errors, no silent coercion. numpy-only — the model and training
loop (torch) live in sibling modules.

Verifications, all hard errors on mismatch:
  * the observation schema hash equals the hash recorded in BOTH configs;
  * each shard file's sha256 equals its manifest / split-config entry;
  * the train and val run sets are disjoint and their union equals the
    manifest run set.

Normalization statistics (per-feature mean/std of the 40 global inputs) are
computed from the TRAIN split only, with std floored at ``1e-6``. Entity
features are passed through as identity: they are bounded by construction and
standardizing masked padded rows would corrupt their provable inertness.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import yaml


STD_FLOOR = 1e-6

# Entity groups in schema order, with their capacities. Kept as a module
# constant so the loader can validate NPZ shapes without re-parsing the schema
# groups mapping order (dict order in the schema is authoritative and matched).
ENTITY_GROUPS: tuple[tuple[str, int], ...] = (
    ("enemies", 64),
    ("bosses", 2),
    ("projectiles", 32),
    ("materials", 64),
    ("consumables", 24),
    ("crates", 2),
    ("obstacles", 8),
)

ENTITY_FEATURE_DIM = 15


class BCDatasetError(ValueError):
    """Raised when the BC dataset cannot be assembled safely."""


@dataclass(frozen=True)
class NormalizationStats:
    """Per-feature standardization stats for the 40 global inputs (train-only)."""

    feature_names: list[str]
    mean: np.ndarray  # [40] f32
    std: np.ndarray  # [40] f32, floored at STD_FLOOR
    split_id: str
    schema_hash: str
    input_config_hash: str
    split_config_hash: str

    def apply(self, globals_array: np.ndarray) -> np.ndarray:
        """Standardize a ``[N, 40]`` global array with these stats."""
        return ((globals_array - self.mean) / self.std).astype(np.float32)


@dataclass(frozen=True)
class BCSplit:
    """One split (train or val), fully materialized and filtered."""

    globals: np.ndarray  # [N, 40] f32, schema-ordered minus excluded features
    actions: np.ndarray  # [N, 2] f32, teacher_action_x/y from original 48 cols
    entities: dict[str, np.ndarray]  # group -> [N, cap, 15] f32
    masks: dict[str, np.ndarray]  # group -> [N, cap] f32
    wave: np.ndarray  # [N] i32
    run_index: np.ndarray  # [N] i32, index into run_ids
    run_ids: list[str]

    @property
    def size(self) -> int:
        return int(self.globals.shape[0])


@dataclass(frozen=True)
class BCDataset:
    """Assembled BC dataset: train + val splits plus train-only norm stats."""

    train: BCSplit
    val: BCSplit
    normalization: NormalizationStats
    schema_hash: str
    split_id: str
    global_feature_names: list[str]
    input_config_hash: str
    split_config_hash: str

    def save_normalization_manifest(self, path: str | Path) -> None:
        """Write the train-only normalization stats to JSON."""
        path = Path(path)
        payload = {
            "split_id": self.normalization.split_id,
            "schema_hash": self.normalization.schema_hash,
            "input_config_hash": self.normalization.input_config_hash,
            "split_config_hash": self.normalization.split_config_hash,
            "global_feature_names": self.normalization.feature_names,
            "mean": [float(v) for v in self.normalization.mean],
            "std": [float(v) for v in self.normalization.std],
            "std_floor": STD_FLOOR,
            "entity_features": "identity (bounded by construction; not standardized)",
        }
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _sha256_upper(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _load_yaml(path: Path) -> tuple[dict[str, Any], str]:
    raw = path.read_bytes()
    data = yaml.safe_load(raw.decode("utf-8"))
    if not isinstance(data, dict):
        raise BCDatasetError(f"{path.name} is not a mapping")
    return data, hashlib.sha256(raw).hexdigest().upper()


def _schema_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _global_feature_names(schema: dict[str, Any]) -> list[str]:
    names = schema.get("global_features")
    if not isinstance(names, list) or not names:
        raise BCDatasetError("schema global_features missing or empty")
    return [str(name) for name in names]


def _resolve_indices(
    feature_names: list[str],
    excluded: list[str],
    labels: list[str],
) -> tuple[list[int], list[str], list[int]]:
    """Return (kept_indices, kept_names, label_indices) into the 48 globals."""
    name_to_index = {name: idx for idx, name in enumerate(feature_names)}
    for name in excluded:
        if name not in name_to_index:
            raise BCDatasetError(f"excluded feature {name!r} not in schema globals")
    for name in labels:
        if name not in name_to_index:
            raise BCDatasetError(f"label feature {name!r} not in schema globals")
    excluded_set = set(excluded)
    kept_indices = [idx for idx, name in enumerate(feature_names) if name not in excluded_set]
    kept_names = [feature_names[idx] for idx in kept_indices]
    label_indices = [name_to_index[name] for name in labels]
    return kept_indices, kept_names, label_indices


def _run_entries(config: dict[str, Any], key: str) -> list[dict[str, Any]]:
    entries = config.get(key)
    if not isinstance(entries, list) or not entries:
        raise BCDatasetError(f"split config {key!r} missing or empty")
    for entry in entries:
        if not isinstance(entry, dict) or "run_id" not in entry or "shard_sha256" not in entry:
            raise BCDatasetError(f"split config {key!r} has a malformed entry")
    return entries


def _load_shard_split(
    entries: list[dict[str, Any]],
    dataset_dir: Path,
    manifest_hashes: dict[str, str],
    kept_indices: list[int],
    label_indices: list[int],
) -> BCSplit:
    kept_arr = np.asarray(kept_indices, dtype=np.intp)
    run_ids: list[str] = []
    globals_parts: list[np.ndarray] = []
    actions_parts: list[np.ndarray] = []
    entity_parts: dict[str, list[np.ndarray]] = {g: [] for g, _ in ENTITY_GROUPS}
    mask_parts: dict[str, list[np.ndarray]] = {g: [] for g, _ in ENTITY_GROUPS}
    wave_parts: list[np.ndarray] = []
    run_index_parts: list[np.ndarray] = []

    for run_index, entry in enumerate(entries):
        run_id = str(entry["run_id"])
        expected_hash = str(entry["shard_sha256"]).upper()
        shard_file = str(entry.get("shard_file", f"{run_id}.npz"))
        shard_path = dataset_dir / shard_file
        if not shard_path.is_file():
            raise BCDatasetError(f"shard file missing: {shard_path}")
        # Cross-check the split-config hash against the manifest first (cheap),
        # then verify the file on disk actually matches (authoritative).
        manifest_hash = manifest_hashes.get(run_id)
        if manifest_hash is not None and manifest_hash != expected_hash:
            raise BCDatasetError(
                f"split-config hash for {run_id} disagrees with manifest"
            )
        actual_hash = _sha256_upper(shard_path)
        if actual_hash != expected_hash:
            raise BCDatasetError(
                f"shard sha256 mismatch for {run_id}: "
                f"expected {expected_hash}, got {actual_hash}"
            )

        with np.load(shard_path) as shard:
            valid = np.asarray(shard["valid"], dtype=bool)
            temporal = np.asarray(shard["temporal_valid"], dtype=bool)
            keep = valid & temporal
            n_keep = int(keep.sum())
            if n_keep == 0:
                raise BCDatasetError(f"{run_id} has no valid&temporal samples")

            raw_globals = np.asarray(shard["global_features"], dtype=np.float32)
            if raw_globals.ndim != 2 or raw_globals.shape[1] != 48:
                raise BCDatasetError(
                    f"{run_id} global_features has shape {raw_globals.shape}, expected [N, 48]"
                )
            filtered = raw_globals[keep]
            globals_parts.append(filtered[:, kept_arr])
            actions_parts.append(filtered[:, label_indices])

            for group, capacity in ENTITY_GROUPS:
                ent = np.asarray(shard[f"entities_{group}"], dtype=np.float32)
                msk = np.asarray(shard[f"mask_{group}"], dtype=np.float32)
                if ent.shape[1:] != (capacity, ENTITY_FEATURE_DIM):
                    raise BCDatasetError(
                        f"{run_id} entities_{group} has shape {ent.shape}, "
                        f"expected [N, {capacity}, {ENTITY_FEATURE_DIM}]"
                    )
                if msk.shape[1:] != (capacity,):
                    raise BCDatasetError(
                        f"{run_id} mask_{group} has shape {msk.shape}, expected [N, {capacity}]"
                    )
                entity_parts[group].append(ent[keep])
                mask_parts[group].append(msk[keep])

            wave_parts.append(np.asarray(shard["wave"], dtype=np.int32)[keep])
            run_index_parts.append(np.full(n_keep, run_index, dtype=np.int32))
        run_ids.append(run_id)

    return BCSplit(
        globals=np.concatenate(globals_parts, axis=0),
        actions=np.concatenate(actions_parts, axis=0),
        entities={g: np.concatenate(entity_parts[g], axis=0) for g, _ in ENTITY_GROUPS},
        masks={g: np.concatenate(mask_parts[g], axis=0) for g, _ in ENTITY_GROUPS},
        wave=np.concatenate(wave_parts, axis=0),
        run_index=np.concatenate(run_index_parts, axis=0),
        run_ids=run_ids,
    )


def _compute_train_normalization(
    train: BCSplit,
    feature_names: list[str],
    split_id: str,
    schema_hash: str,
    input_config_hash: str,
    split_config_hash: str,
) -> NormalizationStats:
    mean = train.globals.mean(axis=0).astype(np.float32)
    std = train.globals.std(axis=0).astype(np.float32)
    std = np.maximum(std, np.float32(STD_FLOOR))
    return NormalizationStats(
        feature_names=list(feature_names),
        mean=mean,
        std=std,
        split_id=split_id,
        schema_hash=schema_hash,
        input_config_hash=input_config_hash,
        split_config_hash=split_config_hash,
    )


def load_bc_dataset(
    dataset_dir: str | Path,
    split_config_path: str | Path,
    input_config_path: str | Path,
    schema_path: str | Path,
) -> BCDataset:
    """Assemble the BC dataset from shards + configs, with full verification."""
    dataset_dir = Path(dataset_dir)
    manifest_path = dataset_dir / "manifest.json"
    if not manifest_path.is_file():
        raise BCDatasetError(f"manifest missing: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    schema = yaml.safe_load(Path(schema_path).read_text(encoding="utf-8"))
    if not isinstance(schema, dict):
        raise BCDatasetError("schema is not a mapping")
    schema_hash = _schema_hash(Path(schema_path))
    feature_names = _global_feature_names(schema)
    if len(feature_names) != 48:
        raise BCDatasetError(f"expected 48 global features, schema has {len(feature_names)}")

    input_config, input_config_hash = _load_yaml(Path(input_config_path))
    split_config, split_config_hash = _load_yaml(Path(split_config_path))

    # Schema-hash agreement across the three sources.
    for label, cfg in (("input", input_config), ("split", split_config)):
        cfg_hash = str(cfg.get("observation_schema_hash", "")).upper()
        if cfg_hash != schema_hash:
            raise BCDatasetError(
                f"{label} config observation_schema_hash {cfg_hash} != schema hash {schema_hash}"
            )
    manifest_hash = str(manifest.get("observation_schema_hash", "")).upper()
    if manifest_hash != schema_hash:
        raise BCDatasetError(
            f"manifest observation_schema_hash {manifest_hash} != schema hash {schema_hash}"
        )

    excluded = [str(name) for name in input_config.get("excluded_global_features", [])]
    labels = [str(name) for name in input_config.get("label_features", [])]
    if not labels:
        raise BCDatasetError("input config label_features missing or empty")
    kept_indices, kept_names, label_indices = _resolve_indices(feature_names, excluded, labels)

    manifest_runs = manifest.get("runs")
    if not isinstance(manifest_runs, list) or not manifest_runs:
        raise BCDatasetError("manifest runs missing or empty")
    manifest_hashes = {str(r["run_id"]): str(r["shard_sha256"]).upper() for r in manifest_runs}
    manifest_run_set = set(manifest_hashes)

    train_entries = _run_entries(split_config, "train")
    val_entries = _run_entries(split_config, "validation")
    train_runs = [str(e["run_id"]) for e in train_entries]
    val_runs = [str(e["run_id"]) for e in val_entries]
    train_set, val_set = set(train_runs), set(val_runs)

    if len(train_set) != len(train_runs) or len(val_set) != len(val_runs):
        raise BCDatasetError("duplicate run_id within a split")
    overlap = train_set & val_set
    if overlap:
        raise BCDatasetError(f"train/val run sets overlap: {sorted(overlap)}")
    union = train_set | val_set
    if union != manifest_run_set:
        missing = manifest_run_set - union
        extra = union - manifest_run_set
        raise BCDatasetError(
            f"split run set != manifest run set (missing={sorted(missing)}, extra={sorted(extra)})"
        )

    train = _load_shard_split(train_entries, dataset_dir, manifest_hashes, kept_indices, label_indices)
    val = _load_shard_split(val_entries, dataset_dir, manifest_hashes, kept_indices, label_indices)

    split_id = str(split_config.get("split_id", "unknown"))
    normalization = _compute_train_normalization(
        train, kept_names, split_id, schema_hash, input_config_hash, split_config_hash
    )

    return BCDataset(
        train=train,
        val=val,
        normalization=normalization,
        schema_hash=schema_hash,
        split_id=split_id,
        global_feature_names=kept_names,
        input_config_hash=input_config_hash,
        split_config_hash=split_config_hash,
    )


def _default_paths() -> dict[str, Path]:
    root = Path(__file__).resolve().parents[2]
    return {
        "dataset_dir": root / "datasets" / "combat_obs_v1",
        "split_config_path": root / "configs" / "wp2" / "dataset_split_v1.yaml",
        "input_config_path": root / "configs" / "wp2" / "bc_input_v1.yaml",
        "schema_path": root / "configs" / "wp2" / "observation_v1.yaml",
    }


def _main(argv: list[str] | None = None) -> int:
    defaults = _default_paths()
    parser = argparse.ArgumentParser(description="Load the BC dataset and print split sizes.")
    parser.add_argument("--dataset-dir", default=str(defaults["dataset_dir"]))
    parser.add_argument("--split-config", default=str(defaults["split_config_path"]))
    parser.add_argument("--input-config", default=str(defaults["input_config_path"]))
    parser.add_argument("--schema", default=str(defaults["schema_path"]))
    parser.add_argument("--norm-out", default=None, help="optional path to write the norm manifest")
    args = parser.parse_args(argv)

    try:
        dataset = load_bc_dataset(
            args.dataset_dir, args.split_config, args.input_config, args.schema
        )
    except BCDatasetError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"split_id={dataset.split_id} schema_hash={dataset.schema_hash}")
    print(f"global_dim={dataset.train.globals.shape[1]} runs_train={len(dataset.train.run_ids)} runs_val={len(dataset.val.run_ids)}")
    print(f"train_samples={dataset.train.size}")
    print(f"val_samples={dataset.val.size}")
    if args.norm_out:
        dataset.save_normalization_manifest(args.norm_out)
        print(f"wrote norm manifest -> {args.norm_out}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_main())
