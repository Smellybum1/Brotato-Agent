"""Contract and synthetic state-machine tests for §46."""
from pathlib import Path
import importlib.util
import sys


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/wp2_route_cohort_commitment_gate0.py"


def load_module():
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("s46_gate0", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def capture(module, ts, *, trigger=False, wave=1, threats=None, action=(1.0, 0.0), rows=None, ready=True):
    if threats is None:
        threats = {1: {"x": 700.0, "y": 0.0, "vx": 0.0, "vy": 0.0}}
    if rows is None:
        rows = [
            {"x": 1.0, "y": 0.0, "body": 100.0, "proj": 100.0, "pen": 0.0},
            {"x": -1.0, "y": 0.0, "body": 120.0, "proj": 100.0, "pen": 0.0},
        ]
    return {
        "run_id": "synthetic", "capture_seq": ts // 50, "ts_ms": ts, "wave": wave,
        "route_exit": "conversion" if trigger else "baseline_kept", "trigger": trigger,
        "action": action, "player_x": 0.0, "player_y": 0.0, "player_speed": 100.0,
        "weapon_range": 460.0, "threats": threats, "living_count": len(threats),
        "identity_complete": True, "identity_unique": True, "revalidation_ready": ready,
        "rows": rows, "projectile_floor": 0.0, "body_floor": 0.0,
        "lowest_penalty": 0.0, "reference_body": 100.0,
    }


def test_preregistered_constants_and_controls_precede_results():
    module = load_module()
    assert module.HORIZON_MS == 600
    assert module.FUTURE_TOLERANCE_MS == 75
    text = SCRIPT.read_text(encoding="utf-8")
    assert text.index("STEP 1 —") < text.index("STEP 2 —") < text.index("STEP 3 —")
    assert 'horizon_rate >= 0.25' in text
    assert 'mean_all_advantage >= 0.02' in text


def test_selection_recomputes_heading_and_uses_frozen_ties():
    module = load_module()
    current = capture(module, 50)
    selected, selected_value, recorded_value, complete = module.select_candidate(current, frozenset({1}))
    assert complete is False
    assert module.heading_key((selected["x"], selected["y"])) == (-1.0, 0.0)
    assert selected_value == recorded_value
    current["rows"][0]["body"] = 140.0
    selected, *_ = module.select_candidate(current, frozenset({1}))
    assert module.heading_key((selected["x"], selected["y"])) == (1.0, 0.0)


def test_resolved_cohort_retains_recorded_command_without_override():
    module = load_module()
    current = capture(module, 50, threats={})
    selected, selected_value, recorded_value, complete = module.select_candidate(current, frozenset({1}))
    assert selected is None
    assert complete is True
    assert selected_value == recorded_value == 1.0


def test_horizon_suppression_and_positive_negative_branches():
    module = load_module()
    stream = [capture(module, 0, trigger=True)]
    stream.extend(capture(module, ts, trigger=(ts == 100)) for ts in range(50, 601, 50))
    result = module.simulate_run(stream)
    assert result["counters"]["eligible_episodes"] == 1
    assert result["counters"]["suppressed_triggers"] == 1
    assert result["counters"]["override_steps"] > 0
    assert result["episodes"][0]["reached_horizon"] is True
    assert result["episodes"][0]["duration_sec"] == 0.6


def test_current_tick_revalidation_and_release_branches():
    module = load_module()
    unsafe_rows = [{"x": -1.0, "y": 0.0, "body": 40.0, "proj": 100.0, "pen": 0.0}]
    stream = [capture(module, 0, trigger=True), capture(module, 50, rows=unsafe_rows)]
    stream.extend(capture(module, ts) for ts in range(100, 651, 50))
    result = module.simulate_run(stream)
    assert result["releases"]["no_safe_candidate"] == 1

    missing = [capture(module, 0, trigger=True), capture(module, 50, ready=False)]
    missing.extend(capture(module, ts) for ts in range(100, 651, 50))
    assert module.simulate_run(missing)["releases"]["revalidation_not_ready"] == 1

    # The final synthetic wave-1 row exists only to satisfy trigger eligibility;
    # the intervening wave change must still release immediately.
    wave = [capture(module, 0, trigger=True), capture(module, 50, wave=2), capture(module, 600)]
    assert module.simulate_run(wave)["releases"]["wave_change"] == 1


def test_trigger_exclusions_have_denominators():
    module = load_module()
    stream = [capture(module, 0, trigger=True, threats={})]
    stream.extend(capture(module, ts) for ts in range(50, 651, 50))
    result = module.simulate_run(stream)
    assert result["counters"]["trigger_captures"] == 1
    assert result["counters"]["trigger_exclusion:empty_original_cohort"] == 1
    assert result["counters"]["eligible_episodes"] == 0
