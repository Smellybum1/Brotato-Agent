import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONTROLLER = ROOT / "mod/mods-unpacked/Tom-BrotatoAgent/runtime/agent_controller.gd"
TELEMETRY = ROOT / "mod/mods-unpacked/Tom-BrotatoAgent/telemetry/telemetry_writer.gd"
SCHEMA = ROOT / "configs/wp2/combat_capture_v2.schema.json"


def test_combat_capture_schema_hash_and_required_groups_are_frozen():
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert schema["properties"]["capture_schema_id"]["const"] == "combat_capture_v2"
    assert set(schema["$defs"]["entities"]["required"]) == {
        "enemies",
        "bosses",
        "projectiles",
        "materials",
        "consumables",
        "crates",
        "obstacles",
    }
    digest = hashlib.sha256(SCHEMA.read_bytes()).hexdigest().upper()
    controller = CONTROLLER.read_text(encoding="utf-8")
    assert f'const _WP2_CAPTURE_SCHEMA_HASH := "{digest}"' in controller


def test_capture_is_additive_and_does_not_replace_v1_events():
    controller = CONTROLLER.read_text(encoding="utf-8")
    telemetry = TELEMETRY.read_text(encoding="utf-8")
    assert 'const SCHEMA_VERSION := "1.0.0"' in telemetry
    assert "func emit_versioned(" in telemetry
    assert '_telem.emit_versioned("combat_capture", payload, _WP2_CAPTURE_SCHEMA_VERSION)' in controller
    assert '_telem.emit("combat_tick", {' in controller
    assert "_WP2_CAPTURE_DIVISOR := 3" in controller


def test_capture_contains_temporal_context_and_untruncated_raw_groups():
    controller = CONTROLLER.read_text(encoding="utf-8")
    assert '"previous_action": {"x": _wp2_previous_action.x' in controller
    assert '"observation_age_ms"' in controller
    assert '"control_dt_ms"' in controller
    assert '"invalid_counts": state.get("invalid_entities", {})' in controller
    assert '"dropped_counts": {' in controller
    for group in ("enemies", "bosses", "projectiles", "materials", "consumables", "crates", "obstacles"):
        assert f'"{group}"' in controller
