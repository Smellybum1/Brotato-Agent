"""Unit tests for scripts.wp2_enemy_aggregate.

Synthetic payloads only -- no game, no runs dir, no I/O outside tmp_path.
"""
from __future__ import annotations

import json

import pytest

from scripts.wp2_enemy_aggregate import (
    CensoredCaptureError,
    aggregate_at,
    capture_is_censored,
    enemies_alive,
    enemy_hp_pool,
    iter_wave_payloads,
    monotonic_prefix,
)


def _enemy(hp, max_hp=None):
    return {
        "hp": hp,
        "max_hp": max_hp if max_hp is not None else hp,
        "health_ratio": 1.0,
        "type_id": "res://entities/enemies/e.tres",
        "script_path": "res://entities/enemies/enemy.gd",
        "name": "enemy",
        "category": "enemy",
        "speed": 100.0,
        "armor": 0.0,
        "radius": 8.0,
    }


def _payload(wave=17, elapsed=0.0, enemies=(), bosses=(), **extra):
    p = {
        "wave": wave,
        "valid": True,
        "wave_time": {
            "elapsed_sec": elapsed,
            "remaining_sec": 60.0 - elapsed,
            "duration_sec": 60.0,
            "valid": True,
        },
        "entities": {
            "enemies": [_enemy(h) for h in enemies],
            "bosses": [_enemy(h) for h in bosses],
        },
    }
    p.update(extra)
    return p


# --- bosses -----------------------------------------------------------------

def test_bosses_excluded_by_default():
    p = _payload(enemies=[10, 20, 30], bosses=[500])
    assert enemies_alive(p) == 3
    assert enemy_hp_pool(p) == pytest.approx(60.0)


def test_bosses_included_on_request():
    p = _payload(enemies=[10, 20, 30], bosses=[500, 250])
    assert enemies_alive(p, include_bosses=True) == 5
    assert enemy_hp_pool(p, include_bosses=True) == pytest.approx(810.0)


def test_dead_entities_not_counted():
    p = _payload(enemies=[10, 0, -5, 7])
    assert enemies_alive(p) == 2
    assert enemy_hp_pool(p) == pytest.approx(17.0)


# --- empty ------------------------------------------------------------------

def test_empty_enemy_list():
    p = _payload(enemies=[], bosses=[])
    assert enemies_alive(p) == 0
    assert enemy_hp_pool(p) == 0.0
    agg = aggregate_at([p], wave=17, t_sec=0.0)
    assert agg.enemies_alive == 0
    assert agg.enemy_hp_pool == 0.0


def test_missing_entities_key_is_zero():
    p = {"wave": 17, "valid": True, "wave_time": {"elapsed_sec": 1.0, "valid": True}}
    assert enemies_alive(p) == 0
    assert enemy_hp_pool(p) == 0.0


# --- nearest-time selection -------------------------------------------------

def test_nearest_time_selection_and_reported_error():
    ps = [
        _payload(elapsed=10.0, enemies=[1]),
        _payload(elapsed=48.0, enemies=[1, 1]),
        _payload(elapsed=52.5, enemies=[1, 1, 1]),
    ]
    agg = aggregate_at(ps, wave=17, t_sec=50.0)
    assert agg.enemies_alive == 2          # 48.0 is nearer than 52.5
    assert agg.elapsed_sec == pytest.approx(48.0)
    assert agg.requested_sec == pytest.approx(50.0)
    assert agg.time_error_sec == pytest.approx(2.0)
    assert agg.n_candidates == 3


def test_tolerance_rejects_far_capture():
    ps = [_payload(elapsed=5.0, enemies=[1])]
    assert aggregate_at(ps, wave=17, t_sec=50.0, tolerance_sec=1.0) is None
    assert aggregate_at(ps, wave=17, t_sec=50.0, tolerance_sec=100.0) is not None


def test_other_waves_and_invalid_payloads_filtered():
    ps = [
        _payload(wave=16, elapsed=50.0, enemies=[1, 1, 1, 1]),
        _payload(wave=17, elapsed=50.0, enemies=[1, 1], valid=False),
        _payload(wave=17, elapsed=50.2, enemies=[1]),
    ]
    agg = aggregate_at(ps, wave=17, t_sec=50.0)
    assert agg.n_candidates == 1
    assert agg.enemies_alive == 1


def test_no_candidates_returns_none():
    assert aggregate_at([_payload(wave=16)], wave=17, t_sec=10.0) is None


# --- elapsed_sec reset on a won wave ---------------------------------------

def test_elapsed_sec_reset_is_trimmed():
    """On a WON wave the tail captures reset elapsed_sec (21.87 -> 0.034) while
    still reporting the same wave and valid=True. Those belong to the next
    wave's timeline and must not be matched."""
    ps = [
        _payload(elapsed=0.05, enemies=[1]),
        _payload(elapsed=10.0, enemies=[1, 1]),
        _payload(elapsed=21.87, enemies=[1, 1, 1]),
        _payload(elapsed=0.034, enemies=[1] * 9),   # reset: next wave's spawn
        _payload(elapsed=0.10, enemies=[1] * 9),
    ]
    trimmed = monotonic_prefix([(p["wave_time"]["elapsed_sec"], p) for p in ps])
    assert [t for t, _ in trimmed] == pytest.approx([0.05, 10.0, 21.87])

    # A request for t=0 must land on the wave's own first capture, not the reset.
    agg = aggregate_at(ps, wave=17, t_sec=0.0)
    assert agg.elapsed_sec == pytest.approx(0.05)
    assert agg.enemies_alive == 1
    assert agg.n_candidates == 3

    # And the wave-end request lands on 21.87, not on the post-reset tail.
    agg_end = aggregate_at(ps, wave=17, t_sec=25.0)
    assert agg_end.elapsed_sec == pytest.approx(21.87)
    assert agg_end.enemies_alive == 3


# --- censoring --------------------------------------------------------------

def test_censored_capture_raises_by_default():
    p = _payload(elapsed=50.0, enemies=[10, 20], dropped_counts={"enemies": 4})
    assert capture_is_censored(p) is True
    with pytest.raises(CensoredCaptureError):
        aggregate_at([p], wave=17, t_sec=50.0)


def test_censored_capture_surfaced_when_allowed():
    p = _payload(elapsed=50.0, enemies=[10, 20], invalid_counts=2)
    agg = aggregate_at([p], wave=17, t_sec=50.0, allow_censored=True)
    assert agg.censored is True
    assert agg.enemies_alive == 2          # known too low; flag says so
    assert agg.enemy_hp_pool == pytest.approx(30.0)


def test_zero_dropped_counts_is_not_censored():
    p = _payload(elapsed=50.0, enemies=[10], dropped_counts={"enemies": 0}, invalid_counts=[])
    assert capture_is_censored(p) is False
    assert aggregate_at([p], wave=17, t_sec=50.0).censored is False


# --- streaming reader -------------------------------------------------------

def test_iter_wave_payloads_streams_and_filters(tmp_path):
    path = tmp_path / "events.jsonl"
    lines = [
        json.dumps({"schema_version": 1, "run_id": "r", "seq": 1, "ts_ms": 1,
                    "event": "begin_run", "payload": {"wave": 17}}),
        json.dumps({"schema_version": 1, "run_id": "r", "seq": 2, "ts_ms": 2,
                    "event": "combat_capture", "payload": _payload(wave=16, enemies=[1])}),
        json.dumps({"schema_version": 1, "run_id": "r", "seq": 3, "ts_ms": 3,
                    "event": "combat_capture",
                    "payload": _payload(wave=17, elapsed=50.0, enemies=[5, 5])}),
        "not json at all",
        "",
        json.dumps({"schema_version": 1, "run_id": "r", "seq": 4, "ts_ms": 4,
                    "event": "combat_capture",
                    "payload": _payload(wave=17, elapsed=51.0, enemies=[5])}),
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    got = list(iter_wave_payloads(path, 17))
    assert len(got) == 2
    assert [p["wave_time"]["elapsed_sec"] for p in got] == pytest.approx([50.0, 51.0])

    # it is a generator (streaming), not a materialized list
    assert iter_wave_payloads(path, 17).__class__.__name__ == "generator"

    agg = aggregate_at(iter_wave_payloads(path, 17), wave=17, t_sec=50.0)
    assert agg.enemy_hp_pool == pytest.approx(10.0)
