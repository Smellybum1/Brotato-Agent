"""Source pins for the §41 clearance-guarded route conversion policy."""

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
POTENTIAL = ROOT / "mod/mods-unpacked/Tom-BrotatoAgent/teacher/potential_field.gd"
CONFIG = ROOT / "mod/mods-unpacked/Tom-BrotatoAgent/teacher/config.gd"
CONTROLLER = ROOT / "mod/mods-unpacked/Tom-BrotatoAgent/runtime/agent_controller.gd"
TELEMETRY = ROOT / "mod/mods-unpacked/Tom-BrotatoAgent/telemetry/telemetry_writer.gd"
LOOP = ROOT / "scripts/wp2_finale_loop.py"


def _func(text: str, name: str) -> str:
    return text.split(f"func {name}", 1)[1].split("\nfunc ", 1)[0]


def test_fixed_gate0_constants_are_exact():
    config = CONFIG.read_text(encoding="utf-8")
    assert "const ROUTE_CONVERSION_PACK_CLEARANCE := 80.0" in config
    assert "const ROUTE_CONVERSION_BODY_RETENTION := 0.80" in config
    assert "const ROUTE_CONVERSION_GAIN_DEADBAND := 0.05" in config
    assert "const ROUTE_CONVERSION_MAX_WAVE := 11" in config


def test_arm_defaults_false_and_is_wired_end_to_end():
    potential = POTENTIAL.read_text(encoding="utf-8")
    controller = CONTROLLER.read_text(encoding="utf-8")
    telemetry = TELEMETRY.read_text(encoding="utf-8")
    loop = LOOP.read_text(encoding="utf-8")
    assert re.search(
        r"^var clearance_guarded_conversion_enabled: bool = false$", potential, re.M
    )
    assert re.search(
        r"^var clearance_guarded_conversion: bool = false$", controller, re.M
    )
    assert (
        "_field.clearance_guarded_conversion_enabled = "
        "clearance_guarded_conversion" in controller
    )
    assert controller.count(
        '"clearance_guarded_conversion": clearance_guarded_conversion,'
    ) == 2
    assert (
        'clearance_guarded_conversion = bool(cfg["clearance_guarded_conversion"])'
        in controller
    )
    assert 'meta.get(\n\t\t\t"clearance_guarded_conversion", false)' in telemetry
    assert '"--clearance-guarded-conversion"' in loop
    assert 'payload["clearance_guarded_conversion"] = ' in loop
    assert "clearance_guarded_conversion_absent:stale_build" in loop


def test_body_safety_receives_weapons_on_every_call_path():
    potential = POTENTIAL.read_text(encoding="utf-8")
    assert "projectiles, profile, weapons, wave" in potential
    movement = _func(potential, "compute_movement")
    assert movement.count("_finale_body_safety(") == 3
    for call in movement.split("_finale_body_safety(")[1:]:
        assert "projectiles, profile, weapons, wave" in call[:220]


def test_live_inrange_matches_the_offline_moving_threat_definition():
    potential = POTENTIAL.read_text(encoding="utf-8")
    body = _func(potential, "_route_inrange_after")
    assert "BotConfig.ESCAPE_HORIZON" in body
    assert 'weapon.get("max_range", 0.0)' in body
    assert "float(threat.get(\"vx\", 0.0))" in body
    assert "float(threat.get(\"vy\", 0.0))" in body
    assert "future_player.distance_to(future_threat) <= max_range" in body
    assert 'float(threat.get("hp", 1.0)) <= 0.0' in body


def test_conversion_runs_after_incumbent_ranking_and_only_through_wave_11():
    potential = POTENTIAL.read_text(encoding="utf-8")
    body = _func(potential, "_finale_body_safety")
    incumbent = body.index("if score > best_score:")
    conversion = body.index("if (clearance_guarded_conversion_enabled")
    final_exit = body.index('if not _finale_route_conversion_applied:')
    assert incumbent < conversion < final_exit
    assert "wave <= BotConfig.ROUTE_CONVERSION_MAX_WAVE" in body[conversion:]
    assert 'conversion_floor = max(' in body[conversion:]
    assert "BotConfig.ROUTE_CONVERSION_PACK_CLEARANCE" in body[conversion:]
    assert '"conversion"' in body[conversion:]


def test_clearance_guard_and_deadband_precede_emission():
    potential = POTENTIAL.read_text(encoding="utf-8")
    body = _func(potential, "_finale_body_safety")
    conversion = body.index("if (clearance_guarded_conversion_enabled")
    guarded = body[conversion:]
    retention = guarded.index("BotConfig.ROUTE_CONVERSION_BODY_RETENTION")
    veto = guarded.index("if conversion_body < guard_floor:", retention)
    deadband = guarded.index("BotConfig.ROUTE_CONVERSION_GAIN_DEADBAND", veto)
    emit = guarded.index("best_dir = conversion_best_dir", deadband)
    assert retention < veto < deadband < emit
    assert "var guard_floor := incumbent_body" in guarded
    assert "BotConfig.BOSS_FINALE_BODY_CRITICAL_CLEARANCE" in guarded
    assert "conversion_projectile < projectile_floor" in guarded


def test_route_debug_proves_delivery_and_guard_engagement():
    potential = POTENTIAL.read_text(encoding="utf-8")
    reset = _func(potential, "_reset_finale_route")
    debug = _func(potential, "finale_route_debug")
    for field in (
        "_finale_route_conversion_applied",
        "_finale_route_conversion_floor",
        "_finale_route_conversion_input_inrange",
        "_finale_route_conversion_selected_inrange",
        "_finale_route_conversion_gain",
        "_finale_route_conversion_input_body",
        "_finale_route_conversion_selected_body",
        "_finale_route_conversion_guard_vetoed",
        "_finale_route_conversion_admitted",
    ):
        assert field in reset
        assert field in debug
    for key in (
        '"conversion_enabled"',
        '"conversion_applied"',
        '"conversion_gain"',
        '"conversion_input_body"',
        '"conversion_selected_body"',
        '"conversion_guard_vetoed"',
        '"conversion_admitted"',
    ):
        assert key in debug
