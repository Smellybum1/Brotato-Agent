"""Unit tests for scripts.wp2_tail_decomposition.

Synthetic capture dicts only -- no game, no runs dir, no I/O.
"""
from __future__ import annotations

from scripts.wp2_tail_decomposition import (
    binding_constraint,
    charge_readback,
    is_charging,
    margin_vs_penalty,
    nearest_pursuer,
    radial_velocity,
    split_fresh,
    term_magnitudes,
)


def _lane(total, penalty=0.0, wall=0.0):
    return {
        "wall": wall, "boss": 0.0, "projectile": 0.0, "center": 0.0,
        "desire": 0.0, "continuity": 0.0, "enemy_penalty_term": penalty,
        "total": total, "wall_clear": 100.0, "current_wall_clear": 90.0,
    }


def _cap(seq, selected=None, alt=None, wave=17, **block):
    tail = {
        "seq": seq,
        "selected": _lane(*selected) if isinstance(selected, tuple) else (selected or {}),
        "alt": _lane(*alt) if isinstance(alt, tuple) else (alt or {}),
        "sampled": 24, "pool": 6, "body_floor_passed": 3,
        "enemy_filter_passed": 2, "body_floor": 45.0,
        "highest_body_clearance": 60.0, "body_floor_regime": "critical",
        "lowest_enemy_penalty": 1.0, "penalty_min": 1.0,
        "penalty_median": 2.0, "penalty_max": 9.0,
    }
    tail.update(block)
    return {
        "wave": wave, "control_dt_ms": 50,
        "player": {"x": 0.0, "y": 0.0, "speed": 472.0},
        "teacher": {"action": {"x": 1.0, "y": 0.0}, "contributions": {"tail": tail}},
        "entities": {"enemies": []},
    }


# --- 1. staleness ---------------------------------------------------------


def test_repeated_seq_is_dropped_not_averaged():
    caps = [_cap(1, (100.0,)), _cap(1, (999.0,)), _cap(2, (200.0,)),
            _cap(2, (999.0,)), _cap(2, (999.0,)), _cap(3, (300.0,))]
    fr = split_fresh(caps)
    assert fr["captures_total"] == 6
    assert fr["stale_dropped"] == 3
    assert fr["fresh_n"] == 3
    assert fr["distinct_seq"] == 3
    totals = [b["selected"]["total"] for _, b in fr["fresh"]]
    assert totals == [100.0, 200.0, 300.0]   # no 999 survived


def test_missing_block_is_counted_separately_from_stale():
    caps = [_cap(1, (1.0,)), _cap(2, (2.0,))]
    caps[1]["teacher"]["contributions"].pop("tail")
    fr = split_fresh(caps)
    assert fr["blocks_missing"] == 1
    assert fr["stale_dropped"] == 0
    assert fr["fresh_n"] == 1


# --- empty `selected` = center fallback -----------------------------------


def test_empty_selected_is_fallback_not_a_zero_lane():
    caps = [_cap(1, (100.0,)), _cap(2, selected={}), _cap(3, (300.0,))]
    fr = split_fresh(caps)
    assert fr["fresh_n"] == 3
    assert fr["center_fallback_n"] == 1
    assert fr["lane_n"] == 2
    terms = term_magnitudes(fr["lane_ticks"])
    assert terms["n"] == 2
    assert terms["total"]["min"] == 100.0     # the {} tick did not pull it to 0


def test_constant_term_is_flagged():
    caps = [_cap(1, (10.0, 0.0, 5.0)), _cap(2, (20.0, 3.0, 5.0))]
    fr = split_fresh(caps)
    terms = term_magnitudes(fr["lane_ticks"])
    assert "wall" in terms["constant_terms"]
    assert "enemy_penalty_term" not in terms["constant_terms"]


# --- 3. margin vs penalty --------------------------------------------------


def test_margin_vs_penalty_comparison():
    # margin 10, |pen| 4  -> not flippable
    # margin  2, |pen| 7  -> flippable
    caps = [
        _cap(1, (110.0, -4.0), (100.0,)),
        _cap(2, (102.0, -7.0), (100.0,)),
    ]
    fr = split_fresh(caps)
    res = margin_vs_penalty(fr["lane_ticks"])
    assert res["denominator_with_alt"] == 2
    assert [r["margin"] for r in res["rows"]] == [10.0, 2.0]
    assert [r["flippable"] for r in res["rows"]] == [False, True]
    assert res["flippable_fraction"] == 0.5


def test_ticks_without_alt_are_excluded_not_zero_margin():
    caps = [_cap(1, (110.0, -4.0), alt={}), _cap(2, (102.0, -7.0), (100.0,))]
    fr = split_fresh(caps)
    res = margin_vs_penalty(fr["lane_ticks"])
    assert res["ticks_without_alt"] == 1
    assert res["denominator_with_alt"] == 1
    assert res["flippable_fraction"] == 1.0


# --- 4. pool is the denominator -------------------------------------------


def test_pass_rates_use_pool_not_sampled():
    caps = [_cap(1, (1.0,), pool=4, body_floor_passed=2, enemy_filter_passed=1),
            _cap(2, (1.0,), pool=6, body_floor_passed=3, enemy_filter_passed=2)]
    fr = split_fresh(caps)
    b = binding_constraint(fr["fresh"])
    assert b["pool_sum_denominator"] == 10
    assert b["body_floor_pass_rate_over_pool"] == 0.5
    assert b["enemy_filter_pass_rate_over_pool"] == 0.3
    assert b["sampled_is_constant"] is True


def test_pool_zero_ticks_excluded_from_rate():
    caps = [_cap(1, (1.0,), pool=0, body_floor_passed=0, enemy_filter_passed=0),
            _cap(2, (1.0,), pool=2, body_floor_passed=1, enemy_filter_passed=1)]
    b = binding_constraint(split_fresh(caps)["fresh"])
    assert b["pool_zero_ticks"] == 1
    assert b["pool_sum_denominator"] == 2
    assert b["body_floor_pass_rate_over_pool"] == 0.5


def test_regime_fractions():
    caps = [_cap(1, (1.0,), body_floor_regime="relief"),
            _cap(2, (1.0,), body_floor_regime="degraded"),
            _cap(3, (1.0,), body_floor_regime="degraded")]
    b = binding_constraint(split_fresh(caps)["fresh"])
    assert b["regime_counts"] == {"relief": 1, "degraded": 2}
    assert b["regime_fractions"]["degraded"] == 2 / 3


# --- PART 2: charging / walking split -------------------------------------


def _pursuer(x, y, vx, vy, speed=150.0):
    return {
        "x": x, "y": y, "vx": vx, "vy": vy, "speed": speed,
        "type_id": "res://entities/units/enemies/pursuer/pursuer_stats.tres",
        "script_path": "res://entities/units/enemies/pursuer/pursuer.gd",
    }


def _rb_cap(enemies, action=(1.0, 0.0), dt=50):
    return {
        "wave": 17, "control_dt_ms": dt,
        "player": {"x": 0.0, "y": 0.0, "speed": 472.0},
        "teacher": {"action": {"x": action[0], "y": action[1]}, "contributions": {}},
        "entities": {"enemies": enemies},
    }


def test_is_charging_threshold_and_missing_speed():
    assert is_charging(_pursuer(0, 0, 300.0, 0.0)) is True        # 2.0 > 1.5
    assert is_charging(_pursuer(0, 0, 150.0, 0.0)) is False       # 1.0
    assert is_charging({"vx": 1.0, "vy": 0.0}) is True            # no speed -> charging
    assert is_charging(_pursuer(0, 0, 10.0, 0.0, speed=0.0)) is True


def test_radial_velocity_sign_away_is_positive():
    cap = _rb_cap([], action=(-1.0, 0.0))
    enemy = _pursuer(100.0, 0.0, 0.0, 0.0)
    assert radial_velocity(cap, enemy) == 1.0      # enemy at +x, moving -x = away
    cap2 = _rb_cap([], action=(1.0, 0.0))
    assert radial_velocity(cap2, enemy) == -1.0    # closing


def test_nearest_pursuer_respects_radius_and_type():
    non_pursuer = {"x": 10.0, "y": 0.0, "vx": 0, "vy": 0, "speed": 100,
                   "type_id": "res://entities/units/enemies/baby_alien/b.tres",
                   "script_path": "res://entities/units/enemies/baby_alien/b.gd"}
    far = _pursuer(900.0, 0.0, 0.0, 0.0)
    near = _pursuer(200.0, 0.0, 0.0, 0.0)
    cap = _rb_cap([non_pursuer, far, near])
    assert nearest_pursuer(cap) is near
    assert nearest_pursuer(_rb_cap([non_pursuer, far])) is None


def test_charge_readback_split_and_dt_filter():
    caps = [
        # charging (ratio 2.0), enemy at +x, action -x  -> radial +1
        _rb_cap([_pursuer(100.0, 0.0, 300.0, 0.0)], action=(-1.0, 0.0)),
        # walking (ratio 1.0), enemy at +x, action +x   -> radial -1
        _rb_cap([_pursuer(100.0, 0.0, 150.0, 0.0)], action=(1.0, 0.0)),
        # walking, radial 0 (perpendicular)
        _rb_cap([_pursuer(100.0, 0.0, 150.0, 0.0)], action=(0.0, 1.0)),
        # excluded: control_dt_ms below the floor
        _rb_cap([_pursuer(100.0, 0.0, 300.0, 0.0)], action=(1.0, 0.0), dt=4),
        # no pursuer in range
        _rb_cap([_pursuer(5000.0, 0.0, 300.0, 0.0)]),
    ]
    rb = charge_readback(caps)
    assert rb["excluded_low_control_dt"] == 1
    assert rb["no_pursuer_within_radius"] == 1
    assert rb["charging_n"] == 1
    assert rb["walking_n"] == 2
    assert rb["charging_mean_radial"] == 1.0
    assert rb["walking_mean_radial"] == -0.5
    assert rb["differentiation"] == 1.5
