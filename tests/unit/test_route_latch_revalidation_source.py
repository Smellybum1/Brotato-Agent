"""Source pins for the §45 default-inert all-exit route instrument."""
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]
FIELD = ROOT / "mod/mods-unpacked/Tom-BrotatoAgent/teacher/potential_field.gd"
CONTROLLER = ROOT / "mod/mods-unpacked/Tom-BrotatoAgent/runtime/agent_controller.gd"
TELEMETRY = ROOT / "mod/mods-unpacked/Tom-BrotatoAgent/telemetry/telemetry_writer.gd"


def test_flag_defaults_false_and_is_plumbed_to_summary_and_ready():
    field = FIELD.read_text(encoding="utf-8")
    controller = CONTROLLER.read_text(encoding="utf-8")
    telemetry = TELEMETRY.read_text(encoding="utf-8")
    assert re.search(r"^var route_latch_revalidation_enabled: bool = false$", field, re.M)
    assert re.search(r"^var route_latch_revalidation_enabled: bool = false$", controller, re.M)
    assert "_field.route_latch_revalidation_enabled = route_latch_revalidation_enabled" in controller
    assert controller.count('"route_latch_revalidation_enabled": route_latch_revalidation_enabled') == 2
    assert 'cfg.has("route_latch_revalidation_enabled")' in controller
    assert 'meta.get(\n\t\t\t"route_latch_revalidation_enabled", false)' in telemetry


def test_disabled_guard_precedes_every_instrument_mutation():
    text = FIELD.read_text(encoding="utf-8")
    start = text.index("func _capture_route_revalidation(")
    end = text.index("\n\nfunc ", start + 10)
    body = text[start:end]
    guard = body.index("if not route_latch_revalidation_enabled:")
    ret = body.index("\t\treturn", guard)
    first_mutation = body.index("_finale_route_revalidation_rows = []")
    assert guard < ret < first_mutation


def test_snapshot_occurs_before_baseline_kept_return_and_before_conversion():
    text = FIELD.read_text(encoding="utf-8")
    capture = text.index("\t_capture_route_revalidation(")
    baseline = text.index('\t\t_finale_route_exit = "baseline_kept"', capture)
    conversion = text.index("\tif (clearance_guarded_conversion_enabled", baseline)
    assert capture < baseline < conversion
    assert '"reason": "ready" if _finale_route_revalidation_ready else _finale_route_exit' in text


def test_reset_prevents_stale_rows_and_debug_is_separate_from_route_scores():
    text = FIELD.read_text(encoding="utf-8")
    reset = text[text.index("func _reset_finale_route"):text.index("func _route_record")]
    assert "_finale_route_revalidation_ready = false" in reset
    assert "_finale_route_revalidation_rows = []" in reset
    debug = text[text.index("func finale_route_debug"):text.index("func finale_translation_debug")]
    assert '"revalidation": _route_revalidation_debug()' in debug
    assert '"scores": _finale_route_scores' in debug


def test_version_bump_is_synchronized():
    manifest = (ROOT / "mod/mods-unpacked/Tom-BrotatoAgent/manifest.json").read_text(encoding="utf-8")
    controller = CONTROLLER.read_text(encoding="utf-8")
    telemetry = TELEMETRY.read_text(encoding="utf-8")
    collector = (ROOT / "scripts/wp2_collect_teacher.py").read_text(encoding="utf-8")
    assert '"version_number": "0.2.81"' in manifest
    assert '"0.2.81-wp2-capture"' in controller
    assert '"0.2.81-wp2-capture"' in telemetry
    assert 'MOD_VERSION = "0.2.81-wp2-capture"' in collector
