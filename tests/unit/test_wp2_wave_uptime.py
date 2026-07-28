"""Unit tests for scripts/wp2_wave_uptime.py (synthetic payloads only)."""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(
    0,
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "scripts"),
)

from wp2_wave_uptime import (  # noqa: E402
    nominal_dps,
    prepare_wave_payloads,
    surface_distance,
    targetable,
    uptime,
    weapon_dps,
    window_summary,
)


def W(damage=10, cooldown=2, max_range=100, type_="ranged"):
    return {"type": type_, "max_range": max_range, "damage": damage, "cooldown": cooldown}


def E(x=0.0, y=0.0, hp=10.0, radius=0.0):
    return {
        "x": x, "y": y, "hp": hp, "max_hp": 10.0,
        "health_ratio": hp / 10.0, "type_id": 1, "script_path": "s",
        "category": "melee", "speed": 100.0, "armor": 0.0, "radius": radius,
    }


def P(enemies=(), weapons=(), t=1.0, wave=17, px=0.0, py=0.0, valid=True,
      control_dt_ms=16.0, speed=445.0, bosses=()):
    return {
        "wave": wave,
        "valid": valid,
        "control_dt_ms": control_dt_ms,
        "wave_time": {"elapsed_sec": t, "remaining_sec": 60 - t,
                      "duration_sec": 60, "valid": True},
        "player": {"x": px, "y": py, "hp": 50, "max_hp": 100, "armor": 5,
                   "dodge": 0.1, "lifesteal": 0, "hp_regeneration": 1,
                   "speed": speed, "vx": 0, "vy": 0, "measured_vx": 0,
                   "measured_vy": 0, "materials": 0, "bonus_materials": 0,
                   "hp_ratio": 0.5},
        "weapons": list(weapons),
        "entities": {"enemies": list(enemies), "bosses": list(bosses)},
        "arena": {"width": 1000, "height": 1000},
    }


# --- nominal_dps -----------------------------------------------------------

def test_nominal_dps_components_and_total():
    nd = nominal_dps([W(damage=10, cooldown=2), W(damage=30, cooldown=3)])
    assert nd["total"] == pytest.approx(5.0 + 10.0)
    assert nd["n_weapons"] == 2
    assert [c["dps"] for c in nd["components"]] == [5.0, 10.0]


def test_weapon_dps_zero_cooldown_is_zero_not_inf():
    assert weapon_dps(W(damage=10, cooldown=0)) == 0.0


# --- surface vs centre boundary -------------------------------------------

def test_surface_distance_subtracts_radius_and_clamps():
    assert surface_distance(0, 0, E(x=100, radius=20)) == pytest.approx(80.0)
    assert surface_distance(0, 0, E(x=5, radius=20)) == 0.0


def test_boundary_just_inside_and_just_outside_surface():
    w = W(max_range=100)
    # centre 105, radius 20 -> surface 85 -> INSIDE. Under CENTRE distance this
    # would be outside; this is the test that pins the surface convention.
    assert targetable(P(enemies=[E(x=105, radius=20)], weapons=[w]), w) is True
    # centre 130, radius 20 -> surface 110 -> OUTSIDE
    assert targetable(P(enemies=[E(x=130, radius=20)], weapons=[w]), w) is False
    # exactly on the boundary is inclusive: centre 120, radius 20 -> 100
    assert targetable(P(enemies=[E(x=120, radius=20)], weapons=[w]), w) is True


def test_dead_enemy_is_not_targetable():
    w = W(max_range=100)
    assert targetable(P(enemies=[E(x=10, hp=0)], weapons=[w]), w) is False


def test_bosses_excluded_by_default_included_on_request():
    w = W(max_range=100)
    p = P(enemies=[], weapons=[w], bosses=[E(x=10)])
    assert targetable(p, w) is False
    assert targetable(p, w, include_bosses=True) is True


# --- uptime conditioning ---------------------------------------------------

def test_uptime_engaged_ignores_cleared_arena_captures():
    w = W(max_range=100)
    ps = [
        P(enemies=[E(x=10)], weapons=[w], t=1.0),   # target present
        P(enemies=[], weapons=[w], t=2.0),          # arena CLEARED
        P(enemies=[], weapons=[w], t=3.0),          # arena CLEARED
    ]
    r = uptime(ps)
    assert r["uptime_all"] == pytest.approx(1.0 / 3.0)
    assert r["uptime_engaged"] == pytest.approx(1.0)
    assert r["n_captures"] == 3
    assert r["n_captures_engaged"] == 1


def test_uptime_engaged_counts_in_range_misses():
    w = W(max_range=100)
    ps = [
        P(enemies=[E(x=10)], weapons=[w], t=1.0),    # in range
        P(enemies=[E(x=500)], weapons=[w], t=2.0),   # alive but far
    ]
    r = uptime(ps)
    assert r["uptime_all"] == pytest.approx(0.5)
    assert r["uptime_engaged"] == pytest.approx(0.5)


def test_uptime_dps_weighting_two_weapons():
    # short-range weapon dps 5 (hits), long-range weapon dps 20 (also hits)
    short = W(damage=10, cooldown=2, max_range=50)
    long_ = W(damage=40, cooldown=2, max_range=1000)
    # enemy at 200 -> only the long weapon has a target.
    r = uptime([P(enemies=[E(x=200)], weapons=[short, long_])])
    assert r["uptime_all"] == pytest.approx(20.0 / 25.0)
    # swap the weights: the hitting weapon is now the weak one.
    short2 = W(damage=40, cooldown=2, max_range=50)
    long2 = W(damage=10, cooldown=2, max_range=1000)
    r2 = uptime([P(enemies=[E(x=200)], weapons=[short2, long2])])
    assert r2["uptime_all"] == pytest.approx(5.0 / 25.0)


def test_uptime_none_when_no_dps():
    r = uptime([P(enemies=[E(x=10)], weapons=[W(cooldown=0)])])
    assert r["uptime_all"] is None
    assert r["n_zero_dps_captures"] == 1


# --- elapsed_sec reset -----------------------------------------------------

def test_prepare_trims_elapsed_sec_reset():
    w = W()
    ps = [P(weapons=[w], t=t) for t in (1.0, 10.0, 21.87, 0.034, 0.1)]
    kept = [p["wave_time"]["elapsed_sec"] for p in prepare_wave_payloads(ps)]
    assert kept == [1.0, 10.0, 21.87]


def test_prepare_drops_invalid_before_trimming():
    w = W()
    ps = [P(weapons=[w], t=1.0), P(weapons=[w], t=0.5, valid=False),
          P(weapons=[w], t=2.0)]
    kept = [p["wave_time"]["elapsed_sec"] for p in prepare_wave_payloads(ps)]
    assert kept == [1.0, 2.0]


# --- window boundaries -----------------------------------------------------

def test_window_lower_inclusive_upper_exclusive():
    w = W(max_range=100)
    ps = [P(enemies=[E(x=10)], weapons=[w], t=t) for t in (9.99, 10.0, 15.0, 20.0)]
    s = window_summary(ps, 10.0, 20.0)
    assert s["n_captures"] == 2  # 10.0 and 15.0


def test_window_summary_fields():
    w = W(max_range=100)
    ps = [
        P(enemies=[E(x=10, hp=7, radius=5), E(x=400, hp=3)], weapons=[w], t=1.0),
        P(enemies=[E(x=600, hp=4)], weapons=[w], t=2.0),
    ]
    s = window_summary(ps, 0.0, 10.0)
    assert s["n_captures"] == 2
    assert s["max_enemies_alive"] == 2
    assert s["mean_enemies_alive"] == pytest.approx(1.5)
    assert s["mean_enemy_hp_pool"] == pytest.approx((10.0 + 4.0) / 2)
    assert s["mean_nearest_surface_dist"] == pytest.approx((5.0 + 600.0) / 2)
    assert s["uptime_all"] == pytest.approx(0.5)
    assert s["mean_player_speed"] == pytest.approx(445.0)


def test_speed_stat_excludes_startup_dt():
    w = W()
    ps = [P(weapons=[w], t=1.0, control_dt_ms=2.0, speed=99999.0),
          P(weapons=[w], t=2.0, control_dt_ms=16.0, speed=445.0)]
    s = window_summary(ps, 0.0, 10.0)
    assert s["n_speed_samples"] == 1
    assert s["mean_player_speed"] == pytest.approx(445.0)


def test_empty_window_is_none_not_crash():
    s = window_summary([], 0.0, 10.0)
    assert s["n_captures"] == 0
    assert s["uptime_all"] is None
    assert s["mean_enemies_alive"] is None
