"""CPU-only unit tests for the WP2 BC training loop (trainer/imitation/bc_training).

These exercise the pure pieces with tiny synthetic data — no real dataset, no
GPU. The numeric core (risk stratum, wave band, baselines, nan-aware
reductions, early stopping, checkpoint round-trip, seed determinism) is factored
out of the file-IO orchestration precisely so it can be tested here.
"""
from __future__ import annotations

import math
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
import torch

from trainer.data.bc_dataset import (
    ENTITY_GROUPS,
    BCDataset,
    BCSplit,
    NormalizationStats,
)
from trainer.imitation.bc_training import (
    BCTrainConfig,
    BCTrainer,
    EarlyStopper,
    _build_device_split,
    circular_mean_direction,
    compute_risk_stratum,
    evaluate_predictions,
    load_checkpoint,
    nan_mean,
    nan_median,
    risk_bin_indices,
    save_checkpoint,
    wave_band_indices,
)
from trainer.models.bc_policy_v1 import BCPolicyConfig, BCPolicyV1


GLOBAL_DIM = 40
ENTITY_DIM = 15
PREV_X, PREV_Y = 15, 16


# ---------------------------------------------------------------------------
# Synthetic builders
# ---------------------------------------------------------------------------
def _feature_names() -> list[str]:
    names = [f"g{i}" for i in range(GLOBAL_DIM)]
    names[PREV_X] = "previous_action_x"
    names[PREV_Y] = "previous_action_y"
    return names


def _entities_and_masks(n: int, rng: np.random.Generator):
    entities, masks = {}, {}
    for group, cap in ENTITY_GROUPS:
        entities[group] = rng.standard_normal((n, cap, ENTITY_DIM)).astype(np.float32)
        m = np.zeros((n, cap), dtype=np.float32)
        for i in range(n):
            k = int(rng.integers(0, cap + 1))
            m[i, :k] = 1.0
        masks[group] = m
    return entities, masks


def _make_split(n: int, seed: int) -> BCSplit:
    rng = np.random.default_rng(seed)
    globals_arr = rng.standard_normal((n, GLOBAL_DIM)).astype(np.float32)
    actions = rng.standard_normal((n, 2)).astype(np.float32)
    actions = actions / np.linalg.norm(actions, axis=1, keepdims=True)  # unit
    entities, masks = _entities_and_masks(n, rng)
    wave = rng.integers(1, 21, size=n).astype(np.int32)
    return BCSplit(
        globals=globals_arr,
        actions=actions,
        entities=entities,
        masks=masks,
        wave=wave,
        run_index=np.zeros(n, dtype=np.int32),
        run_ids=["run_synth"],
    )


def _make_norm(seed: int = 0) -> NormalizationStats:
    rng = np.random.default_rng(seed)
    mean = rng.standard_normal(GLOBAL_DIM).astype(np.float32)
    std = (np.abs(rng.standard_normal(GLOBAL_DIM)) + 0.5).astype(np.float32)
    return NormalizationStats(
        feature_names=_feature_names(),
        mean=mean,
        std=std,
        split_id="synth",
        schema_hash="X",
        input_config_hash="X",
        split_config_hash="X",
    )


def _make_dataset(train_n: int, val_n: int, seed: int = 0) -> BCDataset:
    return BCDataset(
        train=_make_split(train_n, seed),
        val=_make_split(val_n, seed + 100),
        normalization=_make_norm(seed),
        schema_hash="X",
        split_id="synth",
        global_feature_names=_feature_names(),
        input_config_hash="X",
        split_config_hash="X",
    )


def _make_config(**overrides) -> BCTrainConfig:
    base = BCTrainConfig(
        seed=1,
        batch_size=16,
        max_epochs=1,
        early_stopping_patience=5,
        lr=3e-4,
        weight_decay=1e-4,
        lr_min=1e-5,
        lambda_mag=0.5,
        huber_delta=0.5,
        mag_eps=0.01,
        previous_action_dropout_p=0.1,
        device="cpu",
        data_on_device=True,
        dataset_dir=Path("."),
        split_config=Path("."),
        input_config=Path("."),
        schema=Path("."),
        output_root=Path("."),
    )
    return replace(base, **overrides)


# ---------------------------------------------------------------------------
# Risk stratum
# ---------------------------------------------------------------------------
def test_risk_stratum_masked_max_over_threat_groups_only():
    n = 3
    cap = 4
    entities, masks = {}, {}
    for group, real_cap in ENTITY_GROUPS:
        entities[group] = np.zeros((n, real_cap, ENTITY_DIM), dtype=np.float32)
        masks[group] = np.zeros((n, real_cap), dtype=np.float32)

    # Sample 0: one present enemy with contact_risk 0.6.
    entities["enemies"][0, 0, 11] = 0.6
    masks["enemies"][0, 0] = 1.0
    # Sample 1: present projectile 0.9 + present boss 0.4 -> max 0.9.
    entities["projectiles"][1, 0, 11] = 0.9
    masks["projectiles"][1, 0] = 1.0
    entities["bosses"][1, 0, 11] = 0.4
    masks["bosses"][1, 0] = 1.0
    # Sample 2: only a MATERIAL present (non-threat group) with huge risk col ->
    # must be ignored, so risk stays 0.
    entities["materials"][2, 0, 11] = 5.0
    masks["materials"][2, 0] = 1.0
    # Also a masked-out (padded) enemy with a big value on sample 0 -> ignored.
    entities["enemies"][0, 3, 11] = 9.0  # mask is 0 there

    risk = compute_risk_stratum(entities, masks)
    assert risk.shape == (n,)
    assert math.isclose(risk[0], 0.6, rel_tol=1e-6)
    assert math.isclose(risk[1], 0.9, rel_tol=1e-6)
    assert risk[2] == 0.0  # empty threat groups -> 0 risk


def test_risk_bin_edges():
    risk = np.array([0.0, 0.24, 0.25, 0.49, 0.5, 0.74, 0.75, 3.0], dtype=np.float32)
    bins = risk_bin_indices(risk)
    assert bins.tolist() == [0, 0, 1, 1, 2, 2, 3, 3]


def test_wave_band_indices():
    wave = np.array([1, 5, 6, 10, 11, 15, 16, 19, 20], dtype=np.int32)
    bands = wave_band_indices(wave)
    assert bands.tolist() == [0, 0, 1, 1, 2, 2, 3, 3, 4]


# ---------------------------------------------------------------------------
# Circular-mean baseline
# ---------------------------------------------------------------------------
def test_circular_mean_direction_symmetric_cancels_to_x_axis():
    # +45° and -45° average to 0° -> unit (1, 0).
    a = torch.tensor([[math.cos(math.radians(45)), math.sin(math.radians(45))],
                      [math.cos(math.radians(-45)), math.sin(math.radians(-45))]])
    d = circular_mean_direction(a)
    assert math.isclose(float(d[0]), 1.0, abs_tol=1e-5)
    assert math.isclose(float(d[1]), 0.0, abs_tol=1e-5)


def test_circular_mean_direction_is_unit_and_ignores_zero_magnitude():
    # Two vectors at 0° and 90° -> mean angle 45°; a zero vector is dropped.
    a = torch.tensor([[1.0, 0.0], [0.0, 1.0], [0.0, 0.0]])
    d = circular_mean_direction(a, mag_eps=0.01)
    assert math.isclose(float(d.norm()), 1.0, abs_tol=1e-6)
    ang = math.degrees(math.atan2(float(d[1]), float(d[0])))
    assert math.isclose(ang, 45.0, abs_tol=1e-4)


# ---------------------------------------------------------------------------
# Copy-previous baseline: uses UNNORMALIZED columns
# ---------------------------------------------------------------------------
def test_copy_previous_uses_unnormalized_prev_action_columns():
    split = _make_split(20, seed=7)
    norm = _make_norm(seed=3)  # nontrivial mean/std that WOULD change the columns
    group_names = tuple(g for g, _ in ENTITY_GROUPS)
    dev = _build_device_split(
        split, norm, group_names, (PREV_X, PREV_Y), torch.device("cpu"), pin=False
    )
    expected = np.stack([split.globals[:, PREV_X], split.globals[:, PREV_Y]], axis=1)
    assert np.allclose(dev.prev_action.numpy(), expected, atol=1e-6)
    # And the standardized globals at those columns are NOT the raw values
    # (proves normalization is applied to the model input but not the baseline).
    std_cols = dev.globals[:, [PREV_X, PREV_Y]].numpy()
    assert not np.allclose(std_cols, expected, atol=1e-3)


# ---------------------------------------------------------------------------
# nan-aware reductions
# ---------------------------------------------------------------------------
def test_nan_reductions_ignore_nans():
    t = torch.tensor([1.0, float("nan"), 3.0, float("nan"), 5.0])
    assert math.isclose(float(nan_mean(t)), 3.0, rel_tol=1e-6)
    assert math.isclose(float(nan_median(t)), 3.0, rel_tol=1e-6)
    all_nan = torch.tensor([float("nan"), float("nan")])
    assert math.isnan(float(nan_mean(all_nan)))
    assert math.isnan(float(nan_median(all_nan)))


def test_zero_magnitude_labels_do_not_poison_angular_median():
    # Three real targets with perfect predictions (0° error) + two zero-mag
    # targets whose angular error is NaN; the median must be 0°, not polluted.
    pred = torch.tensor([[1.0, 0.0], [0.0, 1.0], [0.6, 0.8], [0.7, 0.7], [1.0, 0.0]])
    target = torch.tensor([[1.0, 0.0], [0.0, 1.0], [0.6, 0.8], [0.0, 0.0], [0.0, 0.0]])
    m = evaluate_predictions(pred, target, mag_eps=0.01)
    assert m["n"] == 5
    assert m["n_direction"] == 3
    assert math.isclose(m["median_angular_error_deg"], 0.0, abs_tol=1e-4)
    assert math.isclose(m["mean_angular_error_deg"], 0.0, abs_tol=1e-4)


# ---------------------------------------------------------------------------
# Early stopping
# ---------------------------------------------------------------------------
def test_early_stopping_triggers_after_patience():
    stop = EarlyStopper(patience=2)
    assert stop.update(1.0, 0) is True   # first is best
    assert not stop.should_stop
    assert stop.update(0.5, 1) is True   # improved
    assert not stop.should_stop
    assert stop.update(0.6, 2) is False  # 1 stale
    assert not stop.should_stop
    assert stop.update(0.55, 3) is False  # 2 stale -> stop
    assert stop.should_stop
    assert stop.best_epoch == 1
    assert math.isclose(stop.best, 0.5, rel_tol=1e-9)


def test_early_stopping_resets_on_new_best():
    stop = EarlyStopper(patience=2)
    stop.update(1.0, 0)
    stop.update(1.1, 1)  # stale 1
    assert not stop.should_stop
    assert stop.update(0.9, 2) is True  # new best resets the counter
    stop.update(1.0, 3)  # stale 1 again
    assert not stop.should_stop
    assert stop.best_epoch == 2


# ---------------------------------------------------------------------------
# Checkpoint round-trip
# ---------------------------------------------------------------------------
def test_checkpoint_roundtrip_restores_identical_outputs(tmp_path):
    cfg = BCPolicyConfig(global_dim=GLOBAL_DIM, prev_action_indices=(PREV_X, PREV_Y))
    torch.manual_seed(11)
    model = BCPolicyV1(cfg).eval()

    g = torch.Generator().manual_seed(5)
    globals_t = torch.randn(6, GLOBAL_DIM, generator=g)
    entities, masks = {}, {}
    for spec in cfg.group_specs:
        entities[spec.name] = torch.randn(6, spec.capacity, ENTITY_DIM, generator=g)
        masks[spec.name] = (torch.rand(6, spec.capacity, generator=g) > 0.5).float()
    before = model(globals_t, entities, masks)

    ckpt = tmp_path / "ckpt.pt"
    save_checkpoint(ckpt, model, {"k": "v"}, epoch=3, val_metrics={"val_loss": 0.1})

    fresh = BCPolicyV1(cfg).eval()  # different random init
    assert not torch.equal(fresh(globals_t, entities, masks), before)
    payload = load_checkpoint(ckpt, fresh)
    after = fresh.eval()(globals_t, entities, masks)
    assert torch.equal(after, before)
    assert payload["epoch"] == 3
    assert payload["val_metrics"]["val_loss"] == 0.1


# ---------------------------------------------------------------------------
# Trainer construction + seed determinism
# ---------------------------------------------------------------------------
def test_trainer_asserts_prev_action_indices():
    ds = _make_dataset(32, 16)
    bad_names = ds.global_feature_names.copy()
    bad_names[15], bad_names[17] = bad_names[17], bad_names[15]  # move prev_x off 15
    bad = BCDataset(
        train=ds.train, val=ds.val, normalization=ds.normalization,
        schema_hash="X", split_id="synth", global_feature_names=bad_names,
        input_config_hash="X", split_config_hash="X",
    )
    with pytest.raises(Exception):
        BCTrainer(bad, _make_config(), torch.device("cpu"))


def test_seed_determinism_identical_first_epoch_loss():
    ds = _make_dataset(64, 32, seed=2)
    cfg = _make_config(seed=42, batch_size=16)

    t1 = BCTrainer(ds, cfg, torch.device("cpu"))
    m1 = t1.train_epoch(0)

    t2 = BCTrainer(ds, cfg, torch.device("cpu"))
    m2 = t2.train_epoch(0)

    assert m1["train_loss"] == m2["train_loss"]
    assert m1["train_direction_term"] == m2["train_direction_term"]


def test_seed_difference_changes_first_epoch_loss():
    ds = _make_dataset(64, 32, seed=2)
    a = BCTrainer(ds, _make_config(seed=1), torch.device("cpu")).train_epoch(0)
    b = BCTrainer(ds, _make_config(seed=2), torch.device("cpu")).train_epoch(0)
    assert a["train_loss"] != b["train_loss"]


def test_trainer_evaluate_and_baselines_are_finite():
    ds = _make_dataset(48, 24, seed=5)
    trainer = BCTrainer(ds, _make_config(batch_size=16), torch.device("cpu"))
    metrics = trainer.evaluate()
    assert math.isfinite(metrics["val_loss"])
    assert "by_wave_band" in metrics and "by_risk_stratum" in metrics
    base = trainer.baselines()
    assert math.isfinite(base["mean_direction"]["median_angular_error_deg"])
    assert math.isfinite(base["copy_previous"]["median_angular_error_deg"])
    assert math.isclose(
        float(np.linalg.norm(base["mean_direction"]["direction"])), 1.0, abs_tol=1e-5
    )
