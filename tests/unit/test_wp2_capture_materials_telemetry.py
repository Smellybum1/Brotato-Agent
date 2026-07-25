"""v127 material-crediting telemetry: source pins + de-censoring arithmetic.

Settles the open question in reports/wp2/materials_leftover_corrected.md — whether
end-of-wave leftovers are swept and credited immediately (Model A) or carried as a
backlog that pairs with the next wave's pickups (Model B). The capture gains the
three fields that discriminate them:

* ``player.materials``      — spendable counter, same accessor the shop reads.
* ``player.bonus_materials``— the carry-over pool Brotato's clean_up_room() fills.
* ``entities.materials[].value`` — per-entity worth, which de-censors the pile once
  the engine's MAX_GOLDS ceiling stops new entities from spawning.

GDScript is pinned by source assertion (no headless Godot in CI, per the v125/v126
precedent); the arithmetic that consumes the fields is exercised in pure Python.
"""
import hashlib
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
CONTROLLER = ROOT / "mod/mods-unpacked/Tom-BrotatoAgent/runtime/agent_controller.gd"
SCHEMA = ROOT / "configs/wp2/combat_capture_v2.schema.json"
GAME_MAIN = ROOT / "third_party/brotatoai/src/brotato_sources/main.gd"
GOLD = ROOT / "third_party/brotatoai/src/brotato_sources/items/materials/gold.gd"
OBSERVATION = ROOT / "configs/wp2/observation_v1.yaml"

# The hash every existing dataset, encoder pin and model identity was built under.
# v127 changes the capture schema and therefore its hash; see the impact section of
# reports/wp2/v127_change_record.md. Nothing downstream is re-pinned by this change.
LEGACY_CAPTURE_SCHEMA_HASH = "95B6444796A21FD44E94113B75BA2097BC381D5F72ED784F9B9A4A99DD46D951"


def test_player_materials_uses_the_same_accessor_as_the_shop_path():
    controller = CONTROLLER.read_text(encoding="utf-8")
    assert 'payload["player"]["materials"] = _wp2_player_materials()' in controller
    assert "if RunData == null or not RunData.has_method(\"get_player_gold\"):" in controller
    assert "return int(RunData.get_player_gold(0))" in controller
    # Unavailable must be a sentinel, never a plausible-looking empty purse.
    assert controller.count("return -1") >= 2


def test_bonus_materials_probes_method_then_property_and_is_written_on_the_payload():
    controller = CONTROLLER.read_text(encoding="utf-8")
    assert 'payload["player"]["bonus_materials"] = _wp2_bonus_materials()' in controller
    assert 'if RunData.has_method("get_player_bonus_gold"):' in controller
    assert "return int(RunData.get_player_bonus_gold(0))" in controller
    assert 'var value = RunData.get("bonus_gold")' in controller


def test_material_telemetry_never_mutates_the_teacher_state_dict():
    """Both counters are written onto the payload copy, after player.duplicate(true).

    The teacher's decision inputs must be byte-identical to v126 so this version is a
    pure telemetry change: any behaviour delta in the v127 smoke is a real regression,
    not an instrumentation artefact.
    """
    controller = CONTROLLER.read_text(encoding="utf-8")
    duplicate_at = controller.index('"player": player.duplicate(true),')
    for field in ("materials", "bonus_materials"):
        assert controller.index(f'payload["player"]["{field}"]') > duplicate_at
    assert 'state["player"]["materials"]' not in controller


def test_every_material_entity_carries_a_value_and_the_snapshot_is_shared():
    controller = CONTROLLER.read_text(encoding="utf-8")
    # Both _collect_loot branches (the _golds array and the node-tree fallback) go
    # through the same snapshot, so neither can emit valueless materials.
    assert controller.count("loot.append(_material_snapshot(item))") == 2
    assert 'snap["value"] = int(item.value) if ("value" in item) else 1' in controller
    assert 'loot.append(_pickup_snapshot(item, "material", ""))' not in controller


def test_engine_material_cap_is_documented_and_matches_the_game_source():
    """The 50-entity ceiling is Brotato's, not the capture's — pin both sides."""
    controller = CONTROLLER.read_text(encoding="utf-8")
    assert "const _WP2_ENGINE_MAX_GOLDS := 50" in controller
    if not GAME_MAIN.exists():
        # third_party/brotatoai is a submodule; absent in bare worktrees.
        pytest.skip("brotatoai game-source submodule not checked out")
    assert "const MAX_GOLDS = 50" in GAME_MAIN.read_text(encoding="utf-8")
    # And the reason value is not constant: the class default is 1, but the engine
    # grows it on absorption and on bonus-gold boosting at spawn.
    assert "var value: = 1" in GOLD.read_text(encoding="utf-8")


def test_capture_side_imposes_no_limit_on_materials():
    controller = CONTROLLER.read_text(encoding="utf-8")
    assert '"consumables": 0, "crates": 0, "obstacles": 0,' in controller
    assert '"enemies": 0, "bosses": 0, "projectiles": 0, "materials": 0,' in controller
    assert "if limit <= 0 or raw.size() <= limit:" in controller


def test_schema_requires_the_new_fields_and_hash_matches_the_controller():
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    player = schema["$defs"]["player"]
    assert {"materials", "bonus_materials"} <= set(player["required"])
    for field in ("materials", "bonus_materials"):
        assert player["properties"][field] == {"type": "integer", "minimum": -1}
    materials = schema["$defs"]["entities"]["properties"]["materials"]
    assert materials == {"$ref": "#/$defs/material_array"}
    item = schema["$defs"]["material_array"]["items"]
    assert item["required"] == ["value"]
    assert item["properties"]["value"] == {"type": "integer", "minimum": 1}

    digest = hashlib.sha256(SCHEMA.read_bytes()).hexdigest().upper()
    assert digest != LEGACY_CAPTURE_SCHEMA_HASH, "v127 must move the capture hash"
    assert f'const _WP2_CAPTURE_SCHEMA_HASH := "{digest}"' in CONTROLLER.read_text(encoding="utf-8")


def test_observation_pin_and_dataset_manifests_still_agree_with_each_other():
    """v127 does NOT re-pin the encoder or any dataset; they stay mutually consistent.

    Deliberate: re-pinning would invalidate every built dataset and every model
    identity at once. Consequence — v127 captures are teacher-collection-only until a
    separate, reviewed compatibility change lands. See reports/wp2/v127_change_record.md.
    """
    observation = OBSERVATION.read_text(encoding="utf-8")
    assert f"source_capture_schema_hash: {LEGACY_CAPTURE_SCHEMA_HASH}" in observation
    manifests = sorted((ROOT / "datasets").glob("*/manifest.json"))
    assert manifests, "no dataset manifests found"
    for manifest in manifests:
        data = json.loads(manifest.read_text(encoding="utf-8"))
        assert data["source_capture_schema_hash"] == LEGACY_CAPTURE_SCHEMA_HASH, manifest


# ─────────────────────────── consumer-side arithmetic ────────────────────────────

def ground_value(materials: list[dict]) -> int:
    """Total worth of the pile — the uncensored quantity behind a censored count."""
    return sum(int(entity.get("value", 1)) for entity in materials)


def credited_delta(previous: dict, current: dict) -> tuple[int, int]:
    """(spendable delta, backlog delta) between two capture payloads."""
    return (
        int(current["player"]["materials"]) - int(previous["player"]["materials"]),
        int(current["player"]["bonus_materials"]) - int(previous["player"]["bonus_materials"]),
    )


def _capture(materials: list[int], spendable: int, backlog: int) -> dict:
    return {
        "player": {"materials": spendable, "bonus_materials": backlog},
        "entities": {"materials": [{"value": value} for value in materials]},
    }


def test_ground_value_sees_past_the_engine_entity_ceiling():
    # A pile pinned at MAX_GOLDS: 50 entities, but absorption has loaded 30 of them.
    saturated = _capture([1] * 20 + [4] * 30, 0, 0)["entities"]["materials"]
    unabsorbed = _capture([1] * 50, 0, 0)["entities"]["materials"]
    assert len(saturated) == len(unabsorbed) == 50
    # Same count, very different pile — that collapse is the censoring value removes.
    assert ground_value(saturated) == 140
    assert ground_value(unabsorbed) == 50


def test_missing_value_falls_back_to_unit_worth():
    assert ground_value([{"instance_id": 7}]) == 1


def test_model_a_and_model_b_are_distinguishable_across_the_wave_boundary():
    before = _capture([1] * 30, spendable=200, backlog=0)

    # Model A — the sweep credits leftovers straight to the spendable counter.
    model_a = _capture([], spendable=230, backlog=0)
    assert credited_delta(before, model_a) == (30, 0)

    # Model B — the sweep parks them in the carry-over pool instead.
    model_b = _capture([], spendable=200, backlog=30)
    assert credited_delta(before, model_b) == (0, 30)

    assert credited_delta(before, model_a) != credited_delta(before, model_b)


def test_backlog_drain_is_visible_as_boosted_next_wave_drops():
    """Model B's second signature: the pool drains while ground value over-runs drops."""
    wave_start = _capture([], spendable=200, backlog=30)
    # Ten unit drops spawn while the pool is non-empty; each is boosted to 2 and the
    # pool pays 1 per drop (spawn_gold: value += min(value, bonus_gold), then
    # remove_bonus_gold(original)).
    later = _capture([2] * 10, spendable=200, backlog=20)
    assert credited_delta(wave_start, later) == (0, -10)
    assert ground_value([{"value": 2}] * 10) == 20


def test_terminal_wave_strand_is_measurable_at_the_last_live_capture():
    """Terminal waves have no post-timer window, so the strand is the final reading."""
    final = _capture([1] * 18 + [3] * 4, spendable=412, backlog=0)
    assert ground_value(final["entities"]["materials"]) == 30
    assert len(final["entities"]["materials"]) == 22
