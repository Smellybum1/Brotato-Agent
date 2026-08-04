"""Contract and helper tests for the preregistered §43 diagnostic."""
from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/wp2_route_conversion_persistence.py"


def load_module():
    spec = importlib.util.spec_from_file_location("s43_persistence", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_fixed_runs_and_horizons_match_preregistration():
    module = load_module()
    prereg = (ROOT / "reports/wp2/route_conversion_persistence_prereg.md").read_text(
        encoding="utf-8"
    )
    assert module.HORIZON_MS == 600
    assert module.FUTURE_TOLERANCE_MS == 75
    assert module.EPISODE_MAX_GAP_MS == 100
    assert len(module.RUN_IDS) == 4
    for run_id in module.RUN_IDS:
        assert run_id in prereg


def test_episode_split_uses_every_intervening_capture():
    module = load_module()
    rows = [
        {"ts_ms": 0, "wave": 1, "applied": True},
        {"ts_ms": 50, "wave": 1, "applied": True},
        {"ts_ms": 100, "wave": 1, "applied": False},
        {"ts_ms": 150, "wave": 1, "applied": True},
        {"ts_ms": 251, "wave": 1, "applied": True},
    ]
    assert [len(value) for value in module.split_episodes(rows)] == [2, 1, 1]


def test_future_match_and_rank_controls_reach_both_branches():
    module = load_module()
    captures = [
        {"ts_ms": 0, "wave": 1},
        {"ts_ms": 525, "wave": 1},
        {"ts_ms": 590, "wave": 1},
        {"ts_ms": 680, "wave": 1},
    ]
    stamps = [row["ts_ms"] for row in captures]
    assert module.nearest_future(captures, stamps, 0, 600)["ts_ms"] == 590
    assert module.nearest_future(captures, stamps, 0, 800) is None
    assert module.spearman([1, 2, 3], [1, 2, 3]) == 1.0
    assert module.spearman([1, 2, 3], [3, 2, 1]) == -1.0
    assert module.spearman([1, 1, 1], [1, 2, 3]) is None


def test_identity_counter_has_positive_and_missing_controls():
    module = load_module()
    counters = {
        "living_threats": 0,
        "identified_threats": 0,
        "missing_instance_id": 0,
        "duplicate_id_captures": 0,
    }
    payload = {
        "entities": {
            "enemies": [
                {"hp": 1, "instance_id": 3},
                {"hp": 1},
                {"hp": 0, "instance_id": 9},
            ],
            "bosses": [],
        }
    }
    assert set(module.living_threats(payload, counters)) == {3}
    assert counters == {
        "living_threats": 2,
        "identified_threats": 1,
        "missing_instance_id": 1,
        "duplicate_id_captures": 0,
    }


def test_controls_print_before_diagnostics_and_self_test_passes():
    module = load_module()
    module.self_test()
    text = SCRIPT.read_text(encoding="utf-8")
    controls = text.index("STEP 1 — VALIDITY")
    persistence = text.index("STEP 2 — TEMPORAL")
    execution = text.index("STEP 3 — EXECUTED")
    calibration = text.index("STEP 4 — ORIGINAL")
    decision = text.index("STEP 5 — DIAGNOSTIC")
    assert controls < persistence < execution < calibration < decision
    assert 'duration_q["median"] < 0.30 or fraction_060 < 0.25' in text
    assert 'forward_q["median"] < 0.50' in text
    assert 'median_absolute_error > 0.20' in text
    assert 'rho < 0.30' in text


def test_reported_duration_bands_have_explicit_denominators():
    module = load_module()
    rows = [
        {"duration_sec": 0.10, "projected_gain": 0.1},
        {"duration_sec": 0.30, "projected_gain": 0.2},
        {"duration_sec": 0.59, "projected_gain": 0.3},
        {"duration_sec": 0.60, "projected_gain": 0.4},
    ]
    bands = module.gain_by_duration_band(rows)
    assert bands["lt_030"]["n"] == 1
    assert bands["ge_030_lt_060"]["n"] == 2
    assert bands["ge_060"]["n"] == 1
    assert sum(value["n"] for value in bands.values()) == len(rows)
