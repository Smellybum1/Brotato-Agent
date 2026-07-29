"""Source-text pins for the calm_threat_mult dev knob.

The mod GDScript is never parsed by this suite, so source-text assertions are the
only guard available. This knob is a FLOAT dose (unlike the bool finale arms):
default 1.0 is a pure weight multiplier and therefore exactly inert -- and the
whole computation is guarded behind `!= 1.0` so the default path is unchanged in
behaviour AND in cost.
"""

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
POTENTIAL_FIELD = ROOT / "mod/mods-unpacked/Tom-BrotatoAgent/teacher/potential_field.gd"
CONTROLLER = ROOT / "mod/mods-unpacked/Tom-BrotatoAgent/runtime/agent_controller.gd"
TELEMETRY = ROOT / "mod/mods-unpacked/Tom-BrotatoAgent/telemetry/telemetry_writer.gd"
CONFIG = ROOT / "mod/mods-unpacked/Tom-BrotatoAgent/teacher/config.gd"
LOOP = ROOT / "scripts/wp2_finale_loop.py"


def _func(text: str, name: str) -> str:
    return text.split("func %s" % name, 1)[1].split("\nfunc ", 1)[0]


def test_charge_threshold_constant():
    config = CONFIG.read_text(encoding="utf-8")
    assert re.search(
        r"^const CHARGE_RATIO_THRESH := 1\.5$", config, re.M
    ), "the charge threshold must live in BotConfig at the measured 1.5"


def test_declared_on_the_field_with_inert_default():
    potential = POTENTIAL_FIELD.read_text(encoding="utf-8")
    assert re.search(
        r"^var calm_threat_mult: float = 1\.0$", potential, re.M
    ), "calm_threat_mult must be declared float with the inert 1.0 default"


def test_weight_computed_in_enemy_loop_behind_the_inert_guard():
    potential = POTENTIAL_FIELD.read_text(encoding="utf-8")
    body = _func(potential, "_enemy_engagement_force")
    loop = body.index("for e in enemies:")
    boss = body.index("for b in bosses:")
    enemy_block = body[loop:boss]
    # The default path must be byte-identical in behaviour and cost: nothing is
    # computed at all unless the dose is actually non-inert.
    assert "if calm_threat_mult != 1.0:" in enemy_block
    assert enemy_block.index("if calm_threat_mult != 1.0:") < enemy_block.index(
        "BotConfig.CHARGE_RATIO_THRESH"
    )
    # DEFENSIVE: a state builder without velocity must read as CHARGING (full
    # weight), never as calm, or an absent signal makes the agent bolder.
    assert 'e.has("vx") and e.has("vy")' in enemy_block
    # Divide-by-zero guard on the enemy's own speed stat.
    assert "esp > 0.0" in enemy_block
    assert "threats.append([e, w])" in enemy_block
    # The boss weight is untouched.
    assert "threats.append([b, BotConfig.BOSS_WEIGHT])" in body


def test_recorded_in_telemetry_allowlist_and_both_summary_dicts():
    telemetry = TELEMETRY.read_text(encoding="utf-8")
    # This dict is an ALLOWLIST: a missing key is silently dropped, which would
    # make arm validation pass on every trial regardless of the actual dose.
    assert 'meta.get("calm_threat_mult", 1.0)' in telemetry

    controller = CONTROLLER.read_text(encoding="utf-8")
    assert re.search(r"^var calm_threat_mult: float = 1\.0$", controller, re.M)
    assert controller.count('"calm_threat_mult": calm_threat_mult,') == 2
    assert "_field.calm_threat_mult = calm_threat_mult" in controller
    assert 'calm_threat_mult = float(cfg["calm_threat_mult"])' in controller


def test_harness_plumbs_the_dose_and_treats_absence_as_failure():
    loop = LOOP.read_text(encoding="utf-8")
    assert '"--calm-threat-mult"' in loop
    # Written EVERY time, never setdefault: a stale dose must not leak.
    assert 'payload["calm_threat_mult"] = float(calm_threat_mult)' in loop
    assert '"calm_threat_mult": float(args.calm_threat_mult),' in loop
    # ABSENCE IS A FAILURE, NOT A DEFAULT.
    assert 'if "calm_threat_mult" not in summary:' in loop
    assert 'return "calm_threat_mult_absent:stale_build"' in loop
    assert "expected_calm_threat_mult" in loop
