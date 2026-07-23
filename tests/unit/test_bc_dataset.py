"""Unit tests for the WP2 M2 behavior-cloning dataset loader.

Builds SMALL synthetic NPZ shards + a fake manifest + fake input/split configs
in ``tmp_path`` (never touches the real 400 MB dataset). The real observation
schema is copied verbatim so its hash is authentic; shard hashes and config
hashes are computed on the fly and wired into the fixtures, so the loader's
verification paths are exercised end to end.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
import yaml

from trainer.data.bc_dataset import (
    ENTITY_GROUPS,
    STD_FLOOR,
    BCDatasetError,
    load_bc_dataset,
)

ROOT = Path(__file__).resolve().parents[2]
REAL_SCHEMA_PATH = ROOT / "configs" / "wp2" / "observation_v1.yaml"

# Global feature indices (schema order) used to plant known values.
IDX_TEACHER_ACTION_X = 15
IDX_TEACHER_ACTION_Y = 16
IDX_WAVE = 0  # first kept feature; used to plant a train/val distribution gap

EXCLUDED = [
    "teacher_action_x",
    "teacher_action_y",
    "teacher_enemy_count",
    "teacher_projectile_count",
    "finale_commit_distance",
    "finale_commit_ticks",
    "finale_commit_x",
    "finale_commit_y",
]
LABELS = ["teacher_action_x", "teacher_action_y"]


def _sha256_upper(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _schema_hash() -> str:
    return _sha256_upper(REAL_SCHEMA_PATH)


def _write_shard(
    path: Path,
    n: int,
    *,
    global_fill: float,
    action_x: float,
    action_y: float,
    valid: np.ndarray | None = None,
    temporal: np.ndarray | None = None,
    wave_value: int = 3,
    seed: int = 0,
) -> None:
    """Write one synthetic NPZ shard with planted globals/actions/masks."""
    rng = np.random.default_rng(seed)
    globals_arr = np.full((n, 48), global_fill, dtype=np.float32)
    globals_arr[:, IDX_TEACHER_ACTION_X] = action_x
    globals_arr[:, IDX_TEACHER_ACTION_Y] = action_y
    # Give the first (kept) feature a per-sample spread so std is well-defined.
    globals_arr[:, IDX_WAVE] = (global_fill + rng.standard_normal(n) * 0.01).astype(np.float32)

    data: dict[str, np.ndarray] = {
        "global_features": globals_arr,
        "capture_seq": np.arange(1, n + 1, dtype=np.int32),
        "wave": np.full(n, wave_value, dtype=np.int32),
        "valid": np.ones(n, dtype=bool) if valid is None else valid,
        "temporal_valid": np.ones(n, dtype=bool) if temporal is None else temporal,
    }
    for group, cap in ENTITY_GROUPS:
        data[f"entities_{group}"] = np.full((n, cap, 15), 0.5, dtype=np.float32)
        data[f"mask_{group}"] = np.zeros((n, cap), dtype=np.float32)
        data[f"dropped_{group}"] = np.zeros(n, dtype=np.int32)
    np.savez(path, **data)


def _write_configs(
    tmp_path: Path,
    dataset_dir: Path,
    *,
    train_specs: list[tuple[str, str]],
    val_specs: list[tuple[str, str]],
    schema_hash: str,
    split_hash_override: dict[str, str] | None = None,
    input_schema_hash: str | None = None,
    split_schema_hash: str | None = None,
) -> tuple[Path, Path, Path]:
    """Write schema copy, input config, split config; return their paths.

    ``train_specs``/``val_specs`` are lists of (run_id, shard_file). The shard
    hash written into the split config is the true on-disk hash unless
    overridden via ``split_hash_override[run_id]``.
    """
    schema_path = tmp_path / "observation_v1.yaml"
    schema_path.write_bytes(REAL_SCHEMA_PATH.read_bytes())

    input_config = {
        "schema_id": "combat_obs_v1",
        "observation_schema_hash": input_schema_hash or schema_hash,
        "excluded_global_features": EXCLUDED,
        "label_features": LABELS,
    }
    input_path = tmp_path / "bc_input.yaml"
    input_path.write_text(yaml.safe_dump(input_config), encoding="utf-8")

    override = split_hash_override or {}

    def _entry(run_id: str, shard_file: str) -> dict[str, str]:
        true_hash = _sha256_upper(dataset_dir / shard_file)
        return {
            "run_id": run_id,
            "shard_file": shard_file,
            "shard_sha256": override.get(run_id, true_hash),
        }

    split_config = {
        "split_id": "dataset_split_v1",
        "observation_schema_hash": split_schema_hash or schema_hash,
        "split_by": "run",
        "train": [_entry(rid, sf) for rid, sf in train_specs],
        "validation": [_entry(rid, sf) for rid, sf in val_specs],
    }
    split_path = tmp_path / "split.yaml"
    split_path.write_text(yaml.safe_dump(split_config), encoding="utf-8")
    return schema_path, input_path, split_path


def _write_manifest(
    dataset_dir: Path,
    specs: list[tuple[str, str]],
    schema_hash: str,
    *,
    hash_override: dict[str, str] | None = None,
) -> None:
    override = hash_override or {}
    runs = []
    for run_id, shard_file in specs:
        true_hash = _sha256_upper(dataset_dir / shard_file)
        runs.append(
            {
                "run_id": run_id,
                "shard_file": shard_file,
                "shard_sha256": override.get(run_id, true_hash),
            }
        )
    manifest = {
        "schema_id": "combat_obs_v1",
        "observation_schema_hash": schema_hash,
        "runs": runs,
    }
    (dataset_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def _build_standard_dataset(tmp_path: Path, **shard_kwargs) -> Path:
    """Two train shards + one val shard, all hashes consistent. Returns dataset_dir."""
    dataset_dir = tmp_path / "ds"
    dataset_dir.mkdir()
    # Train: distinctly different distribution from val (planted at global_fill).
    _write_shard(dataset_dir / "t1.npz", 40, global_fill=0.2, action_x=0.6, action_y=-0.3, seed=1)
    _write_shard(dataset_dir / "t2.npz", 30, global_fill=0.2, action_x=0.6, action_y=-0.3, seed=2)
    _write_shard(dataset_dir / "v1.npz", 20, global_fill=5.0, action_x=-0.9, action_y=0.1, seed=3, **shard_kwargs)
    schema_hash = _schema_hash()
    specs = [("run_t1", "t1.npz"), ("run_t2", "t2.npz"), ("run_v1", "v1.npz")]
    _write_manifest(dataset_dir, specs, schema_hash)
    schema_path, input_path, split_path = _write_configs(
        tmp_path,
        dataset_dir,
        train_specs=[("run_t1", "t1.npz"), ("run_t2", "t2.npz")],
        val_specs=[("run_v1", "v1.npz")],
        schema_hash=schema_hash,
    )
    # Stash paths for callers on the dataset_dir object via a sidecar dict file.
    (tmp_path / "_paths.json").write_text(
        json.dumps(
            {
                "dataset_dir": str(dataset_dir),
                "schema": str(schema_path),
                "input": str(input_path),
                "split": str(split_path),
            }
        ),
        encoding="utf-8",
    )
    return dataset_dir


def _paths(tmp_path: Path) -> dict[str, str]:
    return json.loads((tmp_path / "_paths.json").read_text(encoding="utf-8"))


def _load(tmp_path: Path):
    p = _paths(tmp_path)
    return load_bc_dataset(p["dataset_dir"], p["split"], p["input"], p["schema"])


def test_loads_and_shapes_are_correct(tmp_path):
    _build_standard_dataset(tmp_path)
    ds = _load(tmp_path)
    assert ds.train.size == 70
    assert ds.val.size == 20
    assert ds.train.globals.shape == (70, 40)
    assert ds.val.globals.shape == (20, 40)
    assert ds.train.actions.shape == (70, 2)
    assert ds.global_feature_names[0] == "wave"
    assert len(ds.global_feature_names) == 40
    for group, cap in ENTITY_GROUPS:
        assert ds.train.entities[group].shape == (70, cap, 15)
        assert ds.train.masks[group].shape == (70, cap)


def test_excluded_features_absent_and_labels_extracted(tmp_path):
    _build_standard_dataset(tmp_path)
    ds = _load(tmp_path)
    for name in EXCLUDED:
        assert name not in ds.global_feature_names
    # Labels come from the ORIGINAL cols 15/16 planted in the val shard.
    assert np.allclose(ds.val.actions[:, 0], -0.9)
    assert np.allclose(ds.val.actions[:, 1], 0.1)
    assert np.allclose(ds.train.actions[:, 0], 0.6)
    assert np.allclose(ds.train.actions[:, 1], -0.3)


def test_overlapping_split_runs_error(tmp_path):
    dataset_dir = tmp_path / "ds"
    dataset_dir.mkdir()
    _write_shard(dataset_dir / "a.npz", 10, global_fill=0.2, action_x=0.1, action_y=0.1, seed=1)
    _write_shard(dataset_dir / "b.npz", 10, global_fill=0.2, action_x=0.1, action_y=0.1, seed=2)
    schema_hash = _schema_hash()
    specs = [("run_a", "a.npz"), ("run_b", "b.npz")]
    _write_manifest(dataset_dir, specs, schema_hash)
    # run_a placed in BOTH splits.
    schema_path, input_path, split_path = _write_configs(
        tmp_path,
        dataset_dir,
        train_specs=[("run_a", "a.npz"), ("run_b", "b.npz")],
        val_specs=[("run_a", "a.npz")],
        schema_hash=schema_hash,
    )
    with pytest.raises(BCDatasetError, match="overlap"):
        load_bc_dataset(dataset_dir, split_path, input_path, schema_path)


def test_union_must_equal_manifest_runs(tmp_path):
    dataset_dir = tmp_path / "ds"
    dataset_dir.mkdir()
    _write_shard(dataset_dir / "a.npz", 10, global_fill=0.2, action_x=0.1, action_y=0.1, seed=1)
    _write_shard(dataset_dir / "b.npz", 10, global_fill=0.2, action_x=0.1, action_y=0.1, seed=2)
    schema_hash = _schema_hash()
    # Manifest lists a third run not present in any split.
    specs = [("run_a", "a.npz"), ("run_b", "b.npz"), ("run_c", "a.npz")]
    _write_manifest(dataset_dir, specs, schema_hash)
    schema_path, input_path, split_path = _write_configs(
        tmp_path,
        dataset_dir,
        train_specs=[("run_a", "a.npz")],
        val_specs=[("run_b", "b.npz")],
        schema_hash=schema_hash,
    )
    with pytest.raises(BCDatasetError, match="manifest run set"):
        load_bc_dataset(dataset_dir, split_path, input_path, schema_path)


def test_shard_hash_mismatch_error(tmp_path):
    _build_standard_dataset(tmp_path)
    p = _paths(tmp_path)
    # Corrupt one train shard on disk after configs were pinned to its true hash.
    _write_shard(Path(p["dataset_dir"]) / "t1.npz", 40, global_fill=9.9, action_x=0.0, action_y=0.0, seed=99)
    with pytest.raises(BCDatasetError, match="sha256 mismatch"):
        load_bc_dataset(p["dataset_dir"], p["split"], p["input"], p["schema"])


def test_split_config_hash_disagrees_with_manifest_error(tmp_path):
    dataset_dir = tmp_path / "ds"
    dataset_dir.mkdir()
    _write_shard(dataset_dir / "t1.npz", 20, global_fill=0.2, action_x=0.1, action_y=0.1, seed=1)
    _write_shard(dataset_dir / "v1.npz", 20, global_fill=0.2, action_x=0.1, action_y=0.1, seed=2)
    schema_hash = _schema_hash()
    specs = [("run_t1", "t1.npz"), ("run_v1", "v1.npz")]
    _write_manifest(dataset_dir, specs, schema_hash)
    bogus = "0" * 64
    schema_path, input_path, split_path = _write_configs(
        tmp_path,
        dataset_dir,
        train_specs=[("run_t1", "t1.npz")],
        val_specs=[("run_v1", "v1.npz")],
        schema_hash=schema_hash,
        split_hash_override={"run_t1": bogus},
    )
    with pytest.raises(BCDatasetError, match="disagrees with manifest"):
        load_bc_dataset(dataset_dir, split_path, input_path, schema_path)


def test_schema_hash_mismatch_in_config_error(tmp_path):
    dataset_dir = tmp_path / "ds"
    dataset_dir.mkdir()
    _write_shard(dataset_dir / "t1.npz", 20, global_fill=0.2, action_x=0.1, action_y=0.1, seed=1)
    _write_shard(dataset_dir / "v1.npz", 20, global_fill=0.2, action_x=0.1, action_y=0.1, seed=2)
    schema_hash = _schema_hash()
    specs = [("run_t1", "t1.npz"), ("run_v1", "v1.npz")]
    _write_manifest(dataset_dir, specs, schema_hash)
    schema_path, input_path, split_path = _write_configs(
        tmp_path,
        dataset_dir,
        train_specs=[("run_t1", "t1.npz")],
        val_specs=[("run_v1", "v1.npz")],
        schema_hash=schema_hash,
        input_schema_hash="DEADBEEF" * 8,  # 64 hex chars, wrong
    )
    with pytest.raises(BCDatasetError, match="observation_schema_hash"):
        load_bc_dataset(dataset_dir, split_path, input_path, schema_path)


def test_valid_and_temporal_filtering(tmp_path):
    dataset_dir = tmp_path / "ds"
    dataset_dir.mkdir()
    n = 20
    valid = np.ones(n, dtype=bool)
    valid[:5] = False  # 5 invalid
    temporal = np.ones(n, dtype=bool)
    temporal[5:8] = False  # 3 more dropped by temporal
    _write_shard(dataset_dir / "t1.npz", n, global_fill=0.2, action_x=0.1, action_y=0.1, valid=valid, temporal=temporal, seed=1)
    _write_shard(dataset_dir / "v1.npz", 12, global_fill=0.2, action_x=0.1, action_y=0.1, seed=2)
    schema_hash = _schema_hash()
    specs = [("run_t1", "t1.npz"), ("run_v1", "v1.npz")]
    _write_manifest(dataset_dir, specs, schema_hash)
    schema_path, input_path, split_path = _write_configs(
        tmp_path,
        dataset_dir,
        train_specs=[("run_t1", "t1.npz")],
        val_specs=[("run_v1", "v1.npz")],
        schema_hash=schema_hash,
    )
    ds = load_bc_dataset(dataset_dir, split_path, input_path, schema_path)
    assert ds.train.size == n - 8  # 12 kept


def test_normalization_from_train_only_no_val_leak(tmp_path):
    # Train globals sit near 0.2; val near 5.0. If val leaked, mean would move.
    _build_standard_dataset(tmp_path)
    ds = _load(tmp_path)
    # First kept feature ('wave') was planted near global_fill.
    assert abs(float(ds.normalization.mean[0]) - 0.2) < 0.05
    # Nowhere near the val fill of 5.0 => no leakage.
    assert float(ds.normalization.mean[0]) < 1.0
    # Mean/std length matches global dim.
    assert ds.normalization.mean.shape == (40,)
    assert ds.normalization.std.shape == (40,)


def test_std_floor_applied(tmp_path):
    _build_standard_dataset(tmp_path)
    ds = _load(tmp_path)
    # Constant-fill features (all but the planted 'wave' feature) had zero
    # variance in train and must be floored, never zero.
    assert np.all(ds.normalization.std >= STD_FLOOR)
    # At least one feature was constant and hit exactly the floor.
    assert np.any(np.isclose(ds.normalization.std, STD_FLOOR))


def test_save_normalization_manifest(tmp_path):
    _build_standard_dataset(tmp_path)
    ds = _load(tmp_path)
    out = tmp_path / "norm.json"
    ds.save_normalization_manifest(out)
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["split_id"] == "dataset_split_v1"
    assert payload["schema_hash"] == _schema_hash()
    assert len(payload["mean"]) == 40
    assert len(payload["std"]) == 40
    assert len(payload["global_feature_names"]) == 40
    assert "teacher_action_x" not in payload["global_feature_names"]
