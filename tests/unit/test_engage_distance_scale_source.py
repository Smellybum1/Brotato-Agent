"""Source-text pins for the engage_distance_scale dev knob.

The mod GDScript is never parsed by this suite, so source-text assertions are the
only guard available. This knob is a FLOAT dose (unlike the bool finale arms):
default 1.0 is a pure multiplier and therefore exactly inert.
"""

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
POTENTIAL_FIELD = ROOT / "mod/mods-unpacked/Tom-BrotatoAgent/teacher/potential_field.gd"
CONTROLLER = ROOT / "mod/mods-unpacked/Tom-BrotatoAgent/runtime/agent_controller.gd"
TELEMETRY = ROOT / "mod/mods-unpacked/Tom-BrotatoAgent/telemetry/telemetry_writer.gd"


def _func(text: str, name: str) -> str:
    return text.split("func %s" % name, 1)[1].split("\nfunc ", 1)[0]


def test_declared_on_the_field_with_inert_default():
    potential = POTENTIAL_FIELD.read_text(encoding="utf-8")
    assert re.search(
        r"^var engage_distance_scale: float = 1\.0$", potential, re.M
    ), "engage_distance_scale must be declared float with the inert 1.0 default"


def test_multiply_applied_in_build_desire_after_dps_engage_scale():
    potential = POTENTIAL_FIELD.read_text(encoding="utf-8")
    body = _func(potential, "_build_desire")
    dps = body.index("engage *= BotConfig.DPS_ENGAGE_SCALE")
    knob = body.index("engage *= engage_distance_scale")
    assert knob > dps, "the dose must compose AFTER the shipped DPS scale"
    # And before the edge-kite branch, so it is not conditional on late swarms.
    assert knob < body.index("if edge_kite:")
    # No new clamp/floor was introduced alongside the dose.
    between = body[dps:body.index("if edge_kite:")]
    assert "MIN_ENGAGE_DISTANCE" not in between


def test_recorded_in_telemetry_allowlist_and_both_summary_dicts():
    telemetry = TELEMETRY.read_text(encoding="utf-8")
    # This dict is an ALLOWLIST: a missing key is silently dropped, which would
    # make arm validation pass on every trial regardless of the actual dose.
    assert 'meta.get("engage_distance_scale", 1.0)' in telemetry

    controller = CONTROLLER.read_text(encoding="utf-8")
    assert re.search(r"^var engage_distance_scale: float = 1\.0$", controller, re.M)
    assert controller.count('"engage_distance_scale": engage_distance_scale,') == 2
    assert "_field.engage_distance_scale = engage_distance_scale" in controller
    assert 'engage_distance_scale = float(cfg["engage_distance_scale"])' in controller
