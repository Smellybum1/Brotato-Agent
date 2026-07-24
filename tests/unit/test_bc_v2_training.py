"""CPU-only unit tests for the bc_v2 training stack.

Covers:
  * the weighted BC loss (uniform-weight equivalence to bc_loss + a known
    weighted reduction);
  * the auxiliary damage/margin losses (masking, empty-mask -> 0);
  * the ROC-AUC helper;
  * the corrective mass scalar solver;
  * the composite dataset loader end-to-end on tiny synthetic base + dagger
    fixtures (weights, achieved mass fraction, val purity = ZERO dagger rows).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
import torch
import yaml

from trainer.data.bc_dataset import ENTITY_GROUPS
from trainer.data.bc_v2_dataset import (
    DEFAULT_TARGET_MASS_RATIO,
    load_composite_dataset,
    load_multi_composite_dataset,
    solve_mass_scalar,
)
from trainer.imitation.bc_v2_training import (
    aux_damage_loss,
    aux_margin_loss,
    binary_auc,
    weighted_bc_loss,
)
from trainer.models.bc_policy_v1 import bc_loss

ROOT = Path(__file__).resolve().parents[2]
REAL_SCHEMA_PATH = ROOT / "configs" / "wp2" / "observation_v1.yaml"

IDX_TEACHER_ACTION_X = 15
IDX_TEACHER_ACTION_Y = 16
IDX_WAVE = 0

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


# ===========================================================================
# Weighted loss
# ===========================================================================
def test_weighted_bc_loss_uniform_equals_bc_loss():
    torch.manual_seed(0)
    pred = torch.randn(32, 2)
    target = torch.randn(32, 2)
    w = torch.ones(32)
    wl, _ = weighted_bc_loss(pred, target, w, 0.5, 0.5, 0.01)
    bl, _ = bc_loss(pred, target, 0.5, 0.5, 0.01)
    assert torch.allclose(wl, bl, atol=1e-6)


def test_weighted_bc_loss_known_reduction():
    # Two samples, one weighted 3x: loss must be the weighted mean of per-sample.
    pred = torch.tensor([[1.0, 0.0], [0.0, 1.0]])
    target = torch.tensor([[1.0, 0.0], [-1.0, 0.0]])  # sample 0 perfect, sample 1 orthogonal
    # per-sample: s0 direction ~0, mag ~0 -> ~0; s1 direction (1-cos)=1, mag 0 -> ~1.
    w = torch.tensor([1.0, 3.0])
    loss, _ = weighted_bc_loss(pred, target, w, 0.5, 0.5, 0.01)
    # per_sample ~ [0, 1]; weighted mean = (1*0 + 3*1)/4 = 0.75.
    assert abs(float(loss) - 0.75) < 1e-4


def test_weighted_bc_loss_upweighting_shifts_loss_toward_heavy_rows():
    pred = torch.tensor([[1.0, 0.0], [0.0, 1.0]])
    target = torch.tensor([[1.0, 0.0], [-1.0, 0.0]])
    light, _ = weighted_bc_loss(pred, target, torch.tensor([1.0, 1.0]), 0.5, 0.5, 0.01)
    heavy, _ = weighted_bc_loss(pred, target, torch.tensor([1.0, 9.0]), 0.5, 0.5, 0.01)
    assert float(heavy) > float(light)  # the bad row dominates when up-weighted


# ===========================================================================
# Aux losses
# ===========================================================================
def test_aux_damage_loss_empty_mask_is_zero():
    logit = torch.randn(10)
    label = torch.randint(0, 2, (10,)).float()
    mask = torch.zeros(10, dtype=torch.bool)
    assert float(aux_damage_loss(logit, label, mask)) == 0.0


def test_aux_damage_loss_masks_to_selected_rows():
    logit = torch.tensor([10.0, -10.0, 0.0])
    label = torch.tensor([1.0, 0.0, 1.0])
    # Only the first two rows selected; both are ~perfectly classified -> ~0 BCE.
    mask = torch.tensor([True, True, False])
    val = float(aux_damage_loss(logit, label, mask))
    assert val < 1e-3
    # Include the ambiguous row -> BCE rises.
    mask_all = torch.tensor([True, True, True])
    assert float(aux_damage_loss(logit, label, mask_all)) > val


def test_aux_margin_loss_masking_and_value():
    pred = torch.tensor([0.5, 0.9, 0.1])
    label = torch.tensor([0.5, 0.4, 0.1])
    mask = torch.tensor([True, False, True])
    # Selected rows have zero residual -> Huber 0.
    assert float(aux_margin_loss(pred, label, mask, 0.5)) == 0.0
    # Empty mask -> 0.
    assert float(aux_margin_loss(pred, label, torch.zeros(3, dtype=torch.bool), 0.5)) == 0.0


def test_aux_margin_loss_nonzero_residual():
    pred = torch.tensor([0.9])
    label = torch.tensor([0.4])
    mask = torch.tensor([True])
    # residual 0.5 == delta -> quad region boundary: 0.5*0.5^2 = 0.125.
    assert abs(float(aux_margin_loss(pred, label, mask, 0.5)) - 0.125) < 1e-6


# ===========================================================================
# AUC
# ===========================================================================
def test_binary_auc_perfect_separation():
    scores = np.array([0.1, 0.2, 0.8, 0.9])
    labels = np.array([0, 0, 1, 1])
    assert abs(binary_auc(scores, labels) - 1.0) < 1e-9


def test_binary_auc_inverted_is_zero():
    scores = np.array([0.9, 0.8, 0.2, 0.1])
    labels = np.array([0, 0, 1, 1])
    assert abs(binary_auc(scores, labels) - 0.0) < 1e-9


def test_binary_auc_ties_half():
    scores = np.array([0.5, 0.5, 0.5, 0.5])
    labels = np.array([0, 1, 0, 1])
    assert abs(binary_auc(scores, labels) - 0.5) < 1e-9


def test_binary_auc_degenerate_single_class_is_nan():
    assert np.isnan(binary_auc(np.array([0.1, 0.2]), np.array([1, 1])))


# ===========================================================================
# Mass scalar
# ===========================================================================
def test_solve_mass_scalar_matches_ratio():
    base_sum = 1000.0
    dagger_event_sum = 200.0
    s = solve_mass_scalar(base_sum, dagger_event_sum, DEFAULT_TARGET_MASS_RATIO)
    dagger_sum = s * dagger_event_sum
    # mass fraction of dagger == 0.25.
    assert abs(dagger_sum / (base_sum + dagger_sum) - 0.25) < 1e-9


# ===========================================================================
# Composite loader (tiny synthetic base + dagger fixtures)
# ===========================================================================
def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _write_obs_shard(path: Path, n: int, *, action_x: float, action_y: float, seed: int,
                     valid=None, temporal=None, global_fill=0.2, wave_value=3):
    rng = np.random.default_rng(seed)
    g = np.full((n, 48), global_fill, dtype=np.float32)
    g[:, IDX_TEACHER_ACTION_X] = action_x
    g[:, IDX_TEACHER_ACTION_Y] = action_y
    g[:, IDX_WAVE] = (global_fill + rng.standard_normal(n) * 0.01).astype(np.float32)
    data = {
        "global_features": g,
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


def _build_base(tmp_path: Path):
    ds = tmp_path / "base"
    ds.mkdir()
    _write_obs_shard(ds / "t1.npz", 60, action_x=0.6, action_y=-0.3, seed=1)
    _write_obs_shard(ds / "t2.npz", 40, action_x=0.6, action_y=-0.3, seed=2)
    _write_obs_shard(ds / "v1.npz", 25, action_x=-0.9, action_y=0.1, seed=3, global_fill=5.0)
    schema_hash = _sha(REAL_SCHEMA_PATH)

    schema_path = tmp_path / "observation_v1.yaml"
    schema_path.write_bytes(REAL_SCHEMA_PATH.read_bytes())
    input_path = tmp_path / "bc_input.yaml"
    input_path.write_text(yaml.safe_dump({
        "schema_id": "combat_obs_v1",
        "observation_schema_hash": schema_hash,
        "excluded_global_features": EXCLUDED,
        "label_features": LABELS,
    }), encoding="utf-8")

    def entry(rid, sf):
        return {"run_id": rid, "shard_file": sf, "shard_sha256": _sha(ds / sf)}

    split_path = tmp_path / "split.yaml"
    split_path.write_text(yaml.safe_dump({
        "split_id": "dataset_split_v1",
        "observation_schema_hash": schema_hash,
        "split_by": "run",
        "train": [entry("run_t1", "t1.npz"), entry("run_t2", "t2.npz")],
        "validation": [entry("run_v1", "v1.npz")],
    }), encoding="utf-8")

    (ds / "manifest.json").write_text(json.dumps({
        "schema_id": "combat_obs_v1",
        "observation_schema_hash": schema_hash,
        "runs": [
            {"run_id": "run_t1", "shard_file": "t1.npz", "shard_sha256": _sha(ds / "t1.npz")},
            {"run_id": "run_t2", "shard_file": "t2.npz", "shard_sha256": _sha(ds / "t2.npz")},
            {"run_id": "run_v1", "shard_file": "v1.npz", "shard_sha256": _sha(ds / "v1.npz")},
        ],
    }, indent=2), encoding="utf-8")
    return ds, schema_path, input_path, split_path, schema_hash


def _write_aux(path: Path, n: int, seed: int):
    rng = np.random.default_rng(seed)
    aux_damage = (rng.random(n) < 0.2).astype(np.int8)
    aux_margin = rng.random(n).astype(np.float32)
    np.savez(
        path,
        aux_damage=aux_damage,
        aux_damage_mask=np.ones(n, dtype=bool),
        aux_margin=aux_margin,
        aux_margin_mask=np.ones(n, dtype=bool),
    )


def _write_weights(path: Path, n: int, seed: int):
    rng = np.random.default_rng(seed)
    w = (0.5 + rng.random(n)).astype(np.float32)  # positive, ~mean 1.0
    seg = np.zeros(n, dtype=np.int8)
    np.savez(path, weight=w, segment=seg)


def _build_dagger(
    tmp_path: Path,
    schema_hash: str,
    *,
    dir_name: str = "dagger",
    dataset_id: str = "combat_dagger_r1",
    runs=(("dag_1", "dag_1.npz", 50), ("dag_2", "dag_2.npz", 30)),
    action_x: float = 0.2,
    action_y: float = 0.2,
):
    ds = tmp_path / dir_name
    (ds / "aux_labels").mkdir(parents=True)
    (ds / "sample_weights").mkdir(parents=True)

    entries = []
    for rid, sf, n in runs:
        # one temporal-invalid row to exercise the keep filter
        temporal = np.ones(n, dtype=bool)
        temporal[0] = False
        _write_obs_shard(
            ds / sf, n, action_x=action_x, action_y=action_y,
            seed=hash(rid) % 1000, temporal=temporal,
        )
        _write_aux(ds / "aux_labels" / sf, n, seed=n)
        _write_weights(ds / "sample_weights" / sf, n, seed=n + 1)
        entries.append({
            "run_id": rid,
            "shard_file": sf,
            "shard_sha256": _sha(ds / sf),
            "aux_file": f"aux_labels/{sf}",
            "aux_sha256": _sha(ds / "aux_labels" / sf),
            "weights_file": f"sample_weights/{sf}",
            "weights_sha256": _sha(ds / "sample_weights" / sf),
        })
    (ds / "manifest.json").write_text(json.dumps({
        "dataset_id": dataset_id,
        "observation_schema_hash": schema_hash,
        "runs": entries,
    }, indent=2), encoding="utf-8")
    return ds


def test_composite_loader_val_purity_and_masses(tmp_path):
    base_ds, schema_path, input_path, split_path, schema_hash = _build_base(tmp_path)
    dagger_ds = _build_dagger(tmp_path, schema_hash)

    comp = load_composite_dataset(
        base_ds, dagger_ds, split_path, input_path, schema_path,
        holdout_frac=0.10, holdout_seed=123,
    )

    # -- val purity: val is exactly the frozen base val (ZERO dagger rows) ----
    assert comp.val.size == 25
    assert set(comp.val.run_ids) == {"run_v1"}
    assert set(comp.val.run_ids).isdisjoint({"dag_1", "dag_2"})

    # -- dagger keep filter: 1 temporal-invalid row dropped per run (2 total) --
    total_dagger = (50 - 1) + (30 - 1)  # 78
    assert comp.n_dagger_train + comp.n_dagger_holdout == total_dagger
    # holdout ~ 10%
    assert comp.n_dagger_holdout == round(total_dagger * 0.10)

    # -- composite train size = base train + dagger train --------------------
    assert comp.n_base_train == 100  # 60 + 40
    assert comp.train.size == comp.n_base_train + comp.n_dagger_train

    # -- weights: base rows == 1.0; dagger rows == event_weight * s ----------
    assert np.allclose(comp.train_weight[: comp.n_base_train], 1.0)
    assert np.all(comp.train_weight[comp.n_base_train :] > 0)
    assert not comp.train_is_dagger[: comp.n_base_train].any()
    assert comp.train_is_dagger[comp.n_base_train :].all()

    # -- achieved corrective mass fraction == 0.25 ---------------------------
    assert abs(comp.achieved_mass_fraction - 0.25) < 1e-6
    # s consistent with solver over the TRAIN dagger event-weight sum.
    dagger_event_sum = comp.dagger_weight_sum / comp.s_scalar
    expected_s = solve_mass_scalar(comp.base_weight_sum, dagger_event_sum)
    assert abs(comp.s_scalar - expected_s) < 1e-6


def test_composite_loader_aux_arrays_aligned(tmp_path):
    base_ds, schema_path, input_path, split_path, schema_hash = _build_base(tmp_path)
    dagger_ds = _build_dagger(tmp_path, schema_hash)
    comp = load_composite_dataset(base_ds, dagger_ds, split_path, input_path, schema_path)

    # Base rows carry no aux labels (masks all False); dagger rows do.
    n_base = comp.n_base_train
    assert not comp.train_aux_damage_mask[:n_base].any()
    assert not comp.train_aux_margin_mask[:n_base].any()
    assert comp.train_aux_damage_mask[n_base:].all()
    assert comp.train_aux_margin_mask[n_base:].all()

    # Aux side arrays length matches the train rows.
    assert comp.train_aux_damage.shape[0] == comp.train.size
    assert comp.train_aux_margin.shape[0] == comp.train.size

    # Holdout split carries aux labels of the right length.
    assert comp.aux_holdout.size == comp.n_dagger_holdout
    assert comp.holdout_aux_damage.shape[0] == comp.n_dagger_holdout
    assert comp.holdout_aux_margin_mask.shape[0] == comp.n_dagger_holdout


def test_composite_loader_normalization_over_composite_train(tmp_path):
    base_ds, schema_path, input_path, split_path, schema_hash = _build_base(tmp_path)
    dagger_ds = _build_dagger(tmp_path, schema_hash)
    comp = load_composite_dataset(base_ds, dagger_ds, split_path, input_path, schema_path)
    # Normalization is over the composite train (no val leakage: base val ~5.0).
    assert comp.normalization.mean.shape == (40,)
    assert float(comp.normalization.mean[0]) < 1.0  # nowhere near the val fill 5.0
    assert comp.normalization.feature_names[0] == "wave"


def test_composite_loader_holdout_deterministic(tmp_path):
    base_ds, schema_path, input_path, split_path, schema_hash = _build_base(tmp_path)
    dagger_ds = _build_dagger(tmp_path, schema_hash)
    a = load_composite_dataset(base_ds, dagger_ds, split_path, input_path, schema_path, holdout_seed=7)
    b = load_composite_dataset(base_ds, dagger_ds, split_path, input_path, schema_path, holdout_seed=7)
    assert a.n_dagger_holdout == b.n_dagger_holdout
    assert np.allclose(a.holdout_aux_margin, b.holdout_aux_margin)


# ===========================================================================
# Multi-corrective composite loader (r1 + r2, single total mass)
# ===========================================================================
def test_multi_composite_single_dir_equals_single_loader(tmp_path):
    """One-dir multi loader must be numerically identical to the single loader."""
    base_ds, schema_path, input_path, split_path, schema_hash = _build_base(tmp_path)
    dagger_ds = _build_dagger(tmp_path, schema_hash)

    single = load_composite_dataset(base_ds, dagger_ds, split_path, input_path, schema_path)
    multi = load_multi_composite_dataset(base_ds, [dagger_ds], split_path, input_path, schema_path)

    assert multi.n_base_train == single.n_base_train
    assert multi.n_dagger_train == single.n_dagger_train
    assert multi.n_dagger_holdout == single.n_dagger_holdout
    assert multi.train.size == single.train.size
    assert np.allclose(multi.train_weight, single.train_weight)
    assert np.array_equal(multi.train_is_dagger, single.train_is_dagger)
    assert np.allclose(multi.train.globals, single.train.globals)
    assert abs(multi.achieved_mass_fraction - single.achieved_mass_fraction) < 1e-9
    # single-dir aggregate scalar == the single loader's s_scalar
    assert abs(multi.s_scalar - single.s_scalar) < 1e-6
    assert multi.per_set_s_scalars[0] == pytest.approx(single.s_scalar, abs=1e-6)
    # holdout rows identical
    assert np.allclose(multi.holdout_aux_margin, single.holdout_aux_margin)
    assert np.allclose(multi.aux_holdout.globals, single.aux_holdout.globals)


def test_multi_composite_two_dirs_mass_and_proportional_split(tmp_path):
    base_ds, schema_path, input_path, split_path, schema_hash = _build_base(tmp_path)
    r1 = _build_dagger(
        tmp_path, schema_hash, dir_name="r1", dataset_id="combat_dagger_r1",
        runs=(("r1a", "r1a.npz", 50), ("r1b", "r1b.npz", 30)),
    )
    r2 = _build_dagger(
        tmp_path, schema_hash, dir_name="r2", dataset_id="combat_dagger_r2",
        runs=(("r2a", "r2a.npz", 70), ("r2b", "r2b.npz", 40), ("r2c", "r2c.npz", 20)),
    )
    M = 0.20
    ratio = M / (1.0 - M)
    multi = load_multi_composite_dataset(
        base_ds, [r1, r2], split_path, input_path, schema_path, target_mass_ratio=ratio,
    )

    # Total achieved corrective mass == M exactly.
    assert abs(multi.achieved_mass_fraction - M) < 1e-6

    # Two sets recorded, in dir order.
    assert len(multi.per_set_n_train) == 2
    assert len(multi.per_set_n_holdout) == 2
    n1_train, n2_train = multi.per_set_n_train
    assert n1_train + n2_train == multi.n_dagger_train

    # Mass split proportional to TRAIN row counts.
    w1, w2 = multi.per_set_weight_sums
    total_w = w1 + w2
    assert w1 / total_w == pytest.approx(n1_train / (n1_train + n2_train), abs=1e-6)
    assert w2 / total_w == pytest.approx(n2_train / (n1_train + n2_train), abs=1e-6)

    # Base rows weight 1.0; all corrective rows positive.
    assert np.allclose(multi.train_weight[: multi.n_base_train], 1.0)
    assert np.all(multi.train_weight[multi.n_base_train :] > 0)
    assert multi.train.size == multi.n_base_train + multi.n_dagger_train


def test_multi_composite_holdouts_reproduce_single_loader(tmp_path):
    """Each set's carved holdout must equal that dir's single-loader holdout."""
    base_ds, schema_path, input_path, split_path, schema_hash = _build_base(tmp_path)
    r1 = _build_dagger(
        tmp_path, schema_hash, dir_name="r1", dataset_id="combat_dagger_r1",
        runs=(("r1a", "r1a.npz", 50), ("r1b", "r1b.npz", 30)),
    )
    r2 = _build_dagger(
        tmp_path, schema_hash, dir_name="r2", dataset_id="combat_dagger_r2",
        runs=(("r2a", "r2a.npz", 70), ("r2b", "r2b.npz", 40), ("r2c", "r2c.npz", 20)),
    )
    multi = load_multi_composite_dataset(base_ds, [r1, r2], split_path, input_path, schema_path)

    single_r1 = load_composite_dataset(base_ds, r1, split_path, input_path, schema_path)
    single_r2 = load_composite_dataset(base_ds, r2, split_path, input_path, schema_path)

    # per_set_holdouts are in dir order [r1, r2] and reproduce the single loader.
    ho1, ho2 = multi.per_set_holdouts
    assert ho1.size == single_r1.n_dagger_holdout
    assert ho2.size == single_r2.n_dagger_holdout
    assert np.allclose(ho1.globals, single_r1.aux_holdout.globals)
    assert np.allclose(ho2.globals, single_r2.aux_holdout.globals)
    # combined holdout aux length == sum of the two.
    assert multi.n_dagger_holdout == single_r1.n_dagger_holdout + single_r2.n_dagger_holdout


def test_multi_composite_rejects_empty_dirs(tmp_path):
    base_ds, schema_path, input_path, split_path, schema_hash = _build_base(tmp_path)
    with pytest.raises(Exception):
        load_multi_composite_dataset(base_ds, [], split_path, input_path, schema_path)
