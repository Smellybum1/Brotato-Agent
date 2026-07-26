"""Pure-function tests for scripts/wp2_finale_metrics.compute_metrics.

Synthetic capture payloads only -- no APPDATA, no game, no telemetry files.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.wp2_finale_metrics import compute_metrics  # noqa: E402


def cap(seq, *, wave=20, hp=100, x=0.0, y=0.0, action=(0.0, 0.0),
        vx=0.0, vy=0.0, elapsed=None, fresh=True, bosses=None, dt_ms=50):
    return {
        "wave": wave,
        "capture_seq": seq,
        "control_dt_ms": dt_ms,
        "wave_time": {"elapsed_sec": float(seq) if elapsed is None else elapsed},
        "player": {"hp": hp, "x": x, "y": y, "measured_vx": vx, "measured_vy": vy},
        "teacher": {
            "action": {"x": action[0], "y": action[1]},
            "action_fresh": fresh,
        },
        "entities": {"bosses": bosses or []},
    }


def test_damage_counts_only_decreases_and_ignores_regen():
    caps = [cap(0, hp=100), cap(1, hp=90), cap(2, hp=95), cap(3, hp=85)]
    m = compute_metrics(caps)
    assert m["damage_taken"] == 20.0  # 10 + 10; the +5 regen is excluded, not netted
    assert m["n_hit_events"] == 2
    assert m["hp_start"] == 100
    assert m["hp_end"] == 85
    assert m["hp_min"] == 85


def test_reversal_rate_ignores_zero_actions_and_reports_denominator():
    caps = [
        cap(0, action=(1.0, 0.0)),
        cap(1, action=(0.0, 0.0)),   # zero: pairs (0,1) and (1,2) both skipped
        cap(2, action=(1.0, 0.0)),
        cap(3, action=(-1.0, 0.0)),  # reversal
        cap(4, action=(-1.0, 0.0)),  # same direction
    ]
    m = compute_metrics(caps)
    assert m["n_reversal_pairs"] == 2
    assert m["n_reversals"] == 1
    assert m["reversal_rate"] == 0.5
    assert m["n_action_zero"] == 1
    assert m["action_zero_frac"] == 1 / 5


def test_zero_denominator_yields_null_not_zero():
    # All actions zero -> no reversal pairs; single point -> no path length.
    caps = [cap(0, action=(0.0, 0.0), x=5.0, y=5.0)]
    m = compute_metrics(caps)
    assert m["n_reversal_pairs"] == 0
    assert m["reversal_rate"] is None
    assert m["path_length"] == 0.0
    assert m["straightness"] is None

    empty = compute_metrics([])
    assert empty["n_captures_w20"] == 0
    assert empty["reversal_rate"] is None
    assert empty["straightness"] is None
    assert empty["stationary_frac"] is None
    assert empty["action_zero_frac"] is None
    assert empty["action_fresh_frac"] is None


def test_non_wave20_captures_excluded():
    caps = [
        cap(0, wave=19, hp=100),
        cap(1, wave=19, hp=50),   # would be 50 damage if counted
        cap(2, wave=20, hp=100),
        cap(3, wave=20, hp=95),
        cap(4, wave=1, hp=1),
    ]
    m = compute_metrics(caps)
    assert m["n_captures_w20"] == 2
    assert m["damage_taken"] == 5.0
    assert m["n_hit_events"] == 1


def test_straightness_line_vs_out_and_back():
    line = [cap(i, x=float(i) * 10.0, y=0.0) for i in range(5)]
    m = compute_metrics(line)
    assert m["path_length"] == 40.0
    assert m["net_displacement"] == 40.0
    assert m["straightness"] == 1.0

    back = [cap(0, x=0.0), cap(1, x=10.0), cap(2, x=20.0), cap(3, x=10.0), cap(4, x=0.0)]
    mb = compute_metrics(back)
    assert mb["path_length"] == 40.0
    assert mb["net_displacement"] == 0.0
    assert mb["straightness"] == 0.0
    assert mb["straightness"] < 1.0


def test_stationary_and_fresh_fractions_with_raw_counts():
    caps = [
        cap(0, vx=0.0, vy=0.0, fresh=True),
        cap(1, vx=0.5, vy=0.5, fresh=False),   # hypot ~0.707 < 1.0 -> stationary
        cap(2, vx=100.0, vy=0.0, fresh=True),
        cap(3, vx=0.0, vy=50.0, fresh=True),
    ]
    m = compute_metrics(caps)
    assert m["n_stationary"] == 2
    assert m["stationary_frac"] == 0.5
    assert m["n_action_fresh"] == 3
    assert m["action_fresh_frac"] == 3 / 4
    assert m["n_captures_w20"] == 4


def test_boss_ttk_and_last_health_ratio():
    boss = [{"hp": 100, "max_hp": 200, "health_ratio": 0.5, "x": 1.0, "y": 2.0}]
    caps = [
        cap(0, elapsed=0.0, bosses=boss),
        cap(1, elapsed=5.0, bosses=[{"hp": 10, "max_hp": 200, "health_ratio": 0.05}]),
        cap(2, elapsed=9.0, bosses=[]),  # boss dead
    ]
    m = compute_metrics(caps)
    assert m["boss_ttk_sec"] == 5.0
    assert m["boss_hp_ratio_last"] == 0.05
    assert m["duration_sec"] == 9.0

    no_boss = compute_metrics([cap(0, elapsed=0.0), cap(1, elapsed=3.0)])
    assert no_boss["boss_ttk_sec"] is None
    assert no_boss["boss_hp_ratio_last"] is None


def test_action_accepts_list_shape():
    caps = [
        {**cap(0), "teacher": {"action": [1.0, 0.0], "action_fresh": True}},
        {**cap(1), "teacher": {"action": [-1.0, 0.0], "action_fresh": True}},
    ]
    m = compute_metrics(caps)
    assert m["n_reversal_pairs"] == 1
    assert m["reversal_rate"] == 1.0


def test_captures_sorted_by_capture_seq():
    caps = [cap(2, hp=80), cap(0, hp=100), cap(1, hp=90)]
    m = compute_metrics(caps)
    assert m["hp_start"] == 100
    assert m["hp_end"] == 80
    assert m["damage_taken"] == 20.0


def test_startup_captures_excluded_from_velocity_metrics():
    """measured_v is displacement/dt, so a near-zero dt yields a garbage speed.

    Measured on disk: (11124.9, 0.0) at control_dt_ms=2 against a real speed of
    445. Those captures must not enter the stationary denominator.
    """
    caps = [
        cap(0, vx=0.0, vy=0.0, dt_ms=0),        # startup: excluded entirely
        cap(1, vx=11124.9, vy=0.0, dt_ms=2),    # startup: excluded entirely
        cap(2, vx=0.5, vy=0.5, dt_ms=50),       # real, stationary
        cap(3, vx=400.0, vy=0.0, dt_ms=50),     # real, moving
    ]
    m = compute_metrics(caps)
    assert m["n_velocity_captures"] == 2
    assert m["n_stationary"] == 1
    assert m["stationary_frac"] == 0.5  # 1/2, NOT 1/4


def test_duration_uses_peak_not_last_when_wave_timer_resets():
    """A won wave resets wave_time.elapsed_sec on its final captures.

    Measured: seq 438 -> 21.870, seq 439 -> 0.034, both wave==20. Last-minus-first
    reported 0.076 s for a 21.9 s wave, and only on victories.
    """
    caps = [
        cap(0, elapsed=0.008),
        cap(1, elapsed=10.0),
        cap(2, elapsed=21.87),
        cap(3, elapsed=0.034),   # timer reset
        cap(4, elapsed=0.085),
    ]
    m = compute_metrics(caps)
    assert abs(m["duration_sec"] - 21.862) < 1e-6
    assert m["n_trailing_timer_reset"] == 2
