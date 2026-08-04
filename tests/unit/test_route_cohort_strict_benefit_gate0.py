"""Synthetic and contract tests for the frozen §47 analyzer."""
from pathlib import Path
import importlib.util
import sys


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/wp2_route_cohort_strict_benefit_gate0.py"


def load_module():
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("s47_gate0", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def capture(ts, *, trigger=False, wave=1, threats=None, rows=None, ready=True):
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
        "action": (1.0, 0.0), "player_x": 0.0, "player_y": 0.0, "player_speed": 100.0,
        "weapon_range": 460.0, "threats": threats, "living_count": len(threats),
        "identity_complete": True, "identity_unique": True, "revalidation_ready": ready,
        "rows": rows, "projectile_floor": 0.0, "body_floor": 0.0,
        "lowest_penalty": 0.0, "reference_body": 100.0,
    }


def test_threshold_is_exact_and_not_a_sweep():
    module = load_module()
    assert module.DEADBAND == 0.05
    assert module.strict_benefit(0.049999, 0.0) is False
    assert module.strict_benefit(0.05, 0.0) is True
    assert module.strict_benefit(0.050001, 0.0) is True


def test_controls_and_branches_precede_result():
    text = SCRIPT.read_text(encoding="utf-8")
    assert text.index("STEP 1 —") < text.index("STEP 2 —") < text.index("STEP 3 —")
    assert 'value >= 0.20 for value in strict_rates' in text
    assert 'value >= 0.02 for value in integrated' in text


def test_deadband_retains_state_through_horizon_and_suppresses_trigger():
    module = load_module()
    stream = [capture(0, trigger=True)]
    stream.extend(capture(ts, trigger=(ts == 100)) for ts in range(50, 601, 50))
    result = module.simulate_run(stream)
    assert result["counters"]["eligible_episodes"] == 1
    assert result["counters"]["strict_overrides"] == 0
    assert result["counters"]["deadband_retained"] == 12
    assert result["counters"]["suppressed_triggers"] == 1
    assert result["episodes"][0]["reached_horizon"] is True


def test_positive_branch_and_safety_invariants():
    module = load_module()
    # Moving left projects the player into range; the recorded right command does not.
    threats = {1: {"x": -500.0, "y": 0.0, "vx": 0.0, "vy": 0.0}}
    stream = [capture(0, trigger=True, threats=threats)]
    stream.extend(capture(ts, threats=threats) for ts in range(50, 601, 50))
    result = module.simulate_run(stream)
    assert result["counters"]["strict_overrides"] == 12
    for key in ("projectile_ok", "body_ok", "subcritical_ok", "enemy_ok"):
        assert result["counters"][key] == 12
    assert result["counters"]["deadband_correct"] == result["counters"]["decision_steps"]


def test_release_and_resolved_branches():
    module = load_module()
    unsafe = [{"x": -1.0, "y": 0.0, "body": 40.0, "proj": 100.0, "pen": 0.0}]
    stream = [capture(0, trigger=True), capture(50, rows=unsafe)]
    stream.extend(capture(ts) for ts in range(100, 651, 50))
    assert module.simulate_run(stream)["releases"]["no_safe_candidate"] == 1

    resolved = [capture(0, trigger=True)]
    resolved.extend(capture(ts, threats={}) for ts in range(50, 601, 50))
    result = module.simulate_run(resolved)
    assert result["counters"]["objective_complete_steps"] == 12
    assert result["counters"]["strict_overrides"] == 0

    missing = [capture(0, trigger=True), capture(50, ready=False)]
    missing.extend(capture(ts) for ts in range(100, 651, 50))
    assert module.simulate_run(missing)["releases"]["revalidation_not_ready"] == 1


def test_wave_change_and_zero_denominator_exclusion():
    module = load_module()
    wave = [capture(0, trigger=True), capture(50, wave=2), capture(600)]
    assert module.simulate_run(wave)["releases"]["wave_change"] == 1

    empty = [capture(0, trigger=True, threats={})]
    empty.extend(capture(ts) for ts in range(50, 651, 50))
    result = module.simulate_run(empty)
    assert result["counters"]["trigger_captures"] == 1
    assert result["counters"]["trigger_exclusion:empty_original_cohort"] == 1
    assert result["counters"]["eligible_episodes"] == 0
