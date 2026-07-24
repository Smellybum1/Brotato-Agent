"""Unit tests for scripts/wp2_residual_checkpoint_compare.py.

Synthetic run fixtures exercise the reward_v2 damage normalization, wave-band /
risk-stratum stratification math, bootstrap CI determinism under a fixed seed,
victory / final-wave extraction, and the learned-minus-control difference sign
convention. No real telemetry, no torch, no game.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

_spec = importlib.util.spec_from_file_location(
    "wp2_residual_checkpoint_compare",
    REPO_ROOT / "scripts" / "wp2_residual_checkpoint_compare.py",
)
cc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cc)

from trainer.rl.replay import RewardConfig, TickTelemetry  # noqa: E402


def _tick(seq, hp, max_hp=100.0, wave=1, source="student", valid=True, dt=50.0):
    return TickTelemetry(
        seq=seq, source=source, valid=valid, wave=wave, hp=hp,
        max_hp=max_hp, control_dt_ms=dt, delta_deg=None,
    )


# ---------------------------------------------------------------------------
# damage_steps: reward_v2 normalization + segmentation
# ---------------------------------------------------------------------------
def test_damage_steps_normalization_and_attribution():
    reward = RewardConfig(w_damage=1.0)
    # Contiguous student ticks: hp 100 -> 90 -> 90 -> 70. max_hp=100.
    ticks = [
        _tick(1, 100.0, wave=3),
        _tick(2, 90.0, wave=3),
        _tick(3, 90.0, wave=4),   # wave increment does NOT enter damage
        _tick(4, 70.0, wave=4),
    ]
    risks = np.array([0.1, 0.6, 0.6, 0.9])
    steps = cc.damage_steps(ticks, risks, reward)
    # 3 consecutive pairs.
    assert steps["norm_damage"].shape[0] == 3
    # step a=0: dmg 10/100=0.10 ; a=1: 0 ; a=2: 20/100=0.20
    np.testing.assert_allclose(steps["norm_damage"], [0.10, 0.0, 0.20])
    np.testing.assert_allclose(steps["raw_damage"], [10.0, 0.0, 20.0])
    # attributed to state a's wave and risk
    np.testing.assert_array_equal(steps["wave"], [3, 3, 4])
    np.testing.assert_allclose(steps["risk"], [0.1, 0.6, 0.6])


def test_damage_steps_heal_clamped_to_zero():
    reward = RewardConfig(w_damage=1.0)
    ticks = [_tick(1, 50.0), _tick(2, 80.0)]  # hp increased -> 0 damage
    risks = np.array([0.0, 0.0])
    steps = cc.damage_steps(ticks, risks, reward)
    np.testing.assert_allclose(steps["norm_damage"], [0.0])


def test_damage_steps_breaks_on_seq_gap_and_fallback():
    reward = RewardConfig(w_damage=1.0)
    # seq gap between tick 2 and tick 5 breaks the segment; a fallback tick
    # (non-student) also breaks it and is not itself usable.
    ticks = [
        _tick(1, 100.0),
        _tick(2, 90.0),
        _tick(5, 80.0),                      # seq gap -> new segment (no pair with prev)
        _tick(6, 60.0),
        _tick(0, 60.0, source="fallback", valid=False, dt=0.0),  # infra fallback (not usable)
        _tick(30, 40.0),                     # seq gap again -> isolated, no pair
    ]
    risks = np.zeros(len(ticks))
    steps = cc.damage_steps(ticks, risks, reward, recovery_ticks=0)
    # usable student pairs: (1->2)=0.10, (5->6)=0.20. The fallback tick is not
    # usable; the seq gaps break the stream so tick(30) is isolated (no pair).
    np.testing.assert_allclose(sorted(steps["norm_damage"]), [0.10, 0.20])


def test_damage_steps_dt_gate_breaks_segment():
    reward = RewardConfig(w_damage=1.0)
    ticks = [
        _tick(1, 100.0, dt=50.0),
        _tick(2, 90.0, dt=9999.0),   # dt over gate -> not contiguous with prev
        _tick(3, 80.0, dt=50.0),
    ]
    risks = np.zeros(3)
    steps = cc.damage_steps(ticks, risks, reward)
    # pair (1->2) broken by dt gate on tick2; pair (2->3) valid = 10/100
    np.testing.assert_allclose(steps["norm_damage"], [0.10])


def test_recovery_window_excludes_ticks_from_rl_usable():
    reward = RewardConfig(w_damage=1.0)
    ticks = [
        _tick(0, 100.0, source="fallback", valid=False, dt=0.0),
        _tick(1, 100.0),   # in recovery window -> not usable
        _tick(2, 90.0),    # in recovery window -> not usable
        _tick(3, 70.0),    # usable
        _tick(4, 50.0),    # usable -> one pair 20/100
    ]
    risks = np.zeros(len(ticks))
    steps = cc.damage_steps(ticks, risks, reward, recovery_ticks=2)
    np.testing.assert_allclose(steps["norm_damage"], [0.20])


# ---------------------------------------------------------------------------
# full_stream_steps: primary damage view (no usability filtering)
# ---------------------------------------------------------------------------
def test_full_stream_steps_counts_every_drop():
    # captures: (hp, max_hp, wave, risk). hp 100 -> 90 -> 95(heal) -> 70.
    captures = [
        (100.0, 100.0, 3, 0.1),
        (90.0, 100.0, 3, 0.6),
        (95.0, 100.0, 4, 0.6),   # heal -> clamped to 0
        (70.0, 100.0, 20, 0.9),  # last capture: no successor -> 0 drop
    ]
    steps = cc.full_stream_steps(captures)
    # one tick per capture (4), last carries 0 drop
    assert steps["norm_damage"].shape[0] == 4
    np.testing.assert_allclose(steps["norm_damage"], [0.10, 0.0, 0.25, 0.0])
    np.testing.assert_allclose(steps["raw_damage"], [10.0, 0.0, 25.0, 0.0])
    np.testing.assert_array_equal(steps["wave"], [3, 3, 4, 20])
    np.testing.assert_allclose(steps["risk"], [0.1, 0.6, 0.6, 0.9])


def test_full_stream_counts_damage_that_rl_usable_drops():
    # A drop that falls entirely inside an RL recovery window: the PRIMARY
    # full-stream view counts it; the rl_usable view does NOT.
    reward = RewardConfig(w_damage=1.0)
    # rl_usable ticks: fallback then two in-recovery student ticks carrying the
    # 100->70 drop, so damage_steps (recovery_ticks=2) yields nothing.
    ticks = [
        _tick(0, 100.0, source="fallback", valid=False, dt=0.0),
        _tick(1, 100.0),
        _tick(2, 70.0),
    ]
    risks = np.zeros(len(ticks))
    rl = cc.damage_steps(ticks, risks, reward, recovery_ticks=2)
    assert rl["norm_damage"].size == 0  # filtered out entirely

    # full stream over the same hp trace still sees the 30 hp drop.
    captures = [(100.0, 100.0, 5, 0.0), (70.0, 100.0, 5, 0.0)]
    full = cc.full_stream_steps(captures)
    assert full["raw_damage"].sum() == pytest.approx(30.0)
    np.testing.assert_allclose(full["norm_damage"], [0.30, 0.0])


# ---------------------------------------------------------------------------
# run_metrics: stratification (PRIMARY full-stream) + victory/final-wave
# ---------------------------------------------------------------------------
def _synthetic_steps(waves, risks, norm):
    return {
        "wave": np.asarray(waves, dtype=np.int64),
        "risk": np.asarray(risks, dtype=np.float64),
        "norm_damage": np.asarray(norm, dtype=np.float64),
        "raw_damage": np.asarray(norm, dtype=np.float64) * 100.0,
    }


def test_run_metrics_stratification_math():
    # waves span bands 1-5(=0), 20(=4); risk spans <0.5 and >=0.5.
    full = _synthetic_steps(
        waves=[3, 3, 20, 20],
        risks=[0.1, 0.1, 0.6, 0.9],
        norm=[0.10, 0.30, 0.40, 0.60],
    )
    rl = _synthetic_steps([3], [0.1], [0.05])
    summary = {"result": "defeat", "last_wave": 20, "waves_completed": 20}
    m = cc.run_metrics("run_x", full, rl, summary, terminal="defeat")
    # PRIMARY overall rate = mean of the four full-stream ticks
    assert m["damage_rate_overall"] == pytest.approx(0.35)
    assert m["damage_rate_by_wave_band"]["1-5"] == pytest.approx(0.20)
    assert m["damage_rate_by_wave_band"]["20"] == pytest.approx(0.50)
    assert m["damage_rate_wave20"] == pytest.approx(0.50)
    assert m["damage_rate_by_risk_stratum"]["0.00-0.25"] == pytest.approx(0.20)
    assert m["damage_rate_risk_ge_0p5"] == pytest.approx(0.50)
    assert m["n_ticks_risk_ge_0p5"] == 2
    assert m["n_ticks_wave20"] == 2
    assert m["n_capture_ticks"] == 4
    assert np.isnan(m["damage_rate_by_wave_band"]["6-10"])
    # rl_usable is present but distinct (a diagnostic view)
    assert m["rl_usable_view"]["damage_rate_overall"] == pytest.approx(0.05)


def test_run_metrics_victory_and_final_wave_extraction():
    full = _synthetic_steps([20], [0.1], [0.05])
    win = cc.run_metrics(
        "w", full, full, {"result": "victory", "last_wave": 20}, terminal="victory"
    )
    assert win["victory"] == 1.0
    assert win["final_wave"] == 20
    loss = cc.run_metrics(
        "l", full, full, {"result": "defeat", "last_wave": 13}, terminal="defeat"
    )
    assert loss["victory"] == 0.0
    assert loss["final_wave"] == 13
    # falls back to terminal / waves_completed when summary keys absent
    fb = cc.run_metrics("f", full, full, {"waves_completed": 8}, terminal="victory")
    assert fb["victory"] == 1.0
    assert fb["final_wave"] == 8


def test_run_metrics_cross_check_mismatch_flag():
    full = _synthetic_steps([3, 3], [0.1, 0.1], [0.10, 0.20])  # raw total 30
    # player_damage agrees within 5 hp -> no mismatch
    ok = cc.run_metrics("ok", full, full, {"last_wave": 3}, None,
                        player_damage_sum=28.0, player_damage_events=3)
    assert ok["capture_drop_sum"] == pytest.approx(30.0)
    assert ok["damage_source_mismatch"] is False
    # off by >5 hp -> mismatch flagged
    bad = cc.run_metrics("bad", full, full, {"last_wave": 3}, None,
                         player_damage_sum=10.0, player_damage_events=1)
    assert bad["damage_source_mismatch"] is True
    assert bad["damage_source_delta"] == pytest.approx(20.0)


def test_run_metrics_risk_nan_excluded_from_risk_strata_only():
    full = _synthetic_steps(
        waves=[3, 3], risks=[np.nan, 0.6], norm=[0.10, 0.40]
    )
    m = cc.run_metrics("r", full, full, {"result": "defeat", "last_wave": 3}, None)
    # overall still includes both
    assert m["damage_rate_overall"] == pytest.approx(0.25)
    # nan-risk step excluded from risk strata; only the 0.6 step counts
    assert m["damage_rate_risk_ge_0p5"] == pytest.approx(0.40)
    assert m["n_ticks_risk_nan"] == 1


# ---------------------------------------------------------------------------
# bootstrap: determinism + sign convention
# ---------------------------------------------------------------------------
def test_bootstrap_ci_determinism_fixed_seed():
    vals = [0.2, 0.25, 0.18, 0.30, 0.22, 0.27]
    a = cc.bootstrap_ci(vals, np.random.default_rng(0), 2000, "mean")
    b = cc.bootstrap_ci(vals, np.random.default_rng(0), 2000, "mean")
    assert a == b
    assert a["lo"] <= a["point"] <= a["hi"]
    # different seed -> different CI bounds (overwhelmingly likely)
    c = cc.bootstrap_ci(vals, np.random.default_rng(999), 2000, "mean")
    assert (a["lo"], a["hi"]) != (c["lo"], c["hi"])


def test_bootstrap_ci_drops_nan():
    vals = [0.2, np.nan, 0.3, np.nan]
    ci = cc.bootstrap_ci(vals, np.random.default_rng(1), 500, "mean")
    assert ci["n"] == 2
    assert ci["point"] == pytest.approx(0.25)


def test_bootstrap_diff_ci_determinism():
    learned = [0.10, 0.12, 0.09, 0.11]
    control = [0.20, 0.22, 0.19, 0.21]
    a = cc.bootstrap_diff_ci(learned, control, np.random.default_rng(0), 2000, "mean")
    b = cc.bootstrap_diff_ci(learned, control, np.random.default_rng(0), 2000, "mean")
    assert a == b


def test_bootstrap_diff_sign_convention():
    # learned takes clearly LESS damage -> difference is negative.
    learned = [0.08, 0.10, 0.09, 0.11]
    control = [0.20, 0.22, 0.19, 0.21]
    d = cc.bootstrap_diff_ci(learned, control, np.random.default_rng(0), 3000, "mean")
    assert d["point"] < 0
    assert d["hi"] < 0          # CI entirely below zero
    assert d["straddles_zero"] is False


def test_bootstrap_diff_straddles_zero_for_equal_arms():
    # Identical arms -> diff point is exactly 0 and the resampled diff
    # distribution is symmetric about 0, so the CI straddles it.
    vals = [0.18, 0.20, 0.22, 0.19, 0.21, 0.20]
    d = cc.bootstrap_diff_ci(vals, list(vals), np.random.default_rng(0), 3000, "mean")
    assert d["point"] == pytest.approx(0.0)
    assert d["lo"] <= 0.0 <= d["hi"]
    assert d["straddles_zero"] is True


def test_diff_point_equals_arm_mean_difference():
    learned = [0.10, 0.20, 0.30]     # mean 0.20
    control = [0.05, 0.15, 0.10]     # mean 0.10
    d = cc.bootstrap_diff_ci(learned, control, np.random.default_rng(3), 500, "mean")
    assert d["point"] == pytest.approx(0.10)


# ---------------------------------------------------------------------------
# arm_block / diff_block end-to-end on synthetic per-run metrics
# ---------------------------------------------------------------------------
def _fake_run(run_id, final_wave, victory, overall, w20, risk_hi):
    return {
        "run_id": run_id,
        "result": "victory" if victory else "defeat",
        "final_wave": final_wave,
        "victory": float(victory),
        "n_damage_steps": 100,
        "norm_damage_total": overall * 100,
        "raw_damage_total": overall * 100 * 100,
        "damage_rate_overall": overall,
        "damage_per_1k_overall": overall * 1000,
        "damage_rate_by_wave_band": {
            lab: (w20 if lab == "20" else overall) for lab in cc.WAVE_BAND_LABELS
        },
        "damage_rate_by_risk_stratum": {
            lab: (risk_hi if lab in cc.RISK_HALF_LABELS else overall)
            for lab in cc.RISK_BIN_LABELS
        },
        "damage_rate_wave20": w20,
        "damage_rate_risk_ge_0p5": risk_hi,
        "n_capture_ticks": 100,
        "n_ticks_wave20": 20,
        "n_ticks_risk_ge_0p5": 30,
        "n_ticks_risk_nan": 0,
        "rl_usable_view": {"damage_rate_overall": overall * 0.5},
    }


def test_arm_and_diff_blocks_structure_and_determinism():
    learned = [
        _fake_run("L1", 20, 1, 0.10, 0.15, 0.18),
        _fake_run("L2", 19, 0, 0.11, 0.16, 0.19),
        _fake_run("L3", 20, 1, 0.09, 0.14, 0.17),
    ]
    control = [
        _fake_run("C1", 15, 0, 0.20, 0.30, 0.35),
        _fake_run("C2", 16, 0, 0.22, 0.32, 0.37),
        _fake_run("C3", 14, 0, 0.19, 0.28, 0.33),
    ]
    arm1 = cc.arm_block(learned, np.random.default_rng(0), 500)
    arm2 = cc.arm_block(learned, np.random.default_rng(0), 500)
    # determinism
    assert arm1["damage_rate_overall"]["mean"] == arm2["damage_rate_overall"]["mean"]
    assert arm1["victory_rate"]["point"] == pytest.approx(2.0 / 3.0)

    d = cc.diff_block(learned, control, np.random.default_rng(0), 500)
    # learned lower damage across every highlighted stratum -> negative diffs
    assert d["damage_rate_overall"]["mean"]["point"] < 0
    assert d["damage_rate_wave20"]["mean"]["point"] < 0
    assert d["damage_rate_by_risk_stratum"]["0.75-inf"]["mean"]["point"] < 0
    # learned reaches further and wins more -> positive
    assert d["final_wave"]["mean"]["point"] > 0
    assert d["victory_rate"]["mean"]["point"] > 0
