import copy
import json
import math
from pathlib import Path

import pytest

from trainer.observation.encoder_v1 import (
    EncodedObservation,
    ObservationError,
    canonical_digest,
    encode_capture,
    load_schema,
)


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "configs/wp2/observation_v1.yaml"
FIXTURE_PATH = ROOT / "tests/fixtures/wp2/combat_capture_golden_v1.json"


@pytest.fixture
def schema():
    return load_schema(SCHEMA_PATH)


@pytest.fixture
def capture():
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_shapes_masks_padding_and_round_trip(schema, capture):
    encoded = encode_capture(capture, schema)
    assert len(schema["global_features"]) == 48
    assert len(schema["entity_features"]) == 15
    assert len(encoded.global_features) == len(schema["global_features"])
    for group, config in schema["groups"].items():
        assert len(encoded.entities[group]) == config["capacity"]
        assert len(encoded.masks[group]) == config["capacity"]
        assert all(len(row) == len(schema["entity_features"]) for row in encoded.entities[group])
        assert sum(encoded.masks[group]) == len(capture["entities"][group])
    assert EncodedObservation.from_dict(encoded.to_dict()) == encoded


def test_threat_ordering_is_deterministic_and_input_order_independent(schema, capture):
    forward = encode_capture(capture, schema)
    reversed_capture = copy.deepcopy(capture)
    reversed_capture["entities"]["enemies"].reverse()
    backward = encode_capture(reversed_capture, schema)
    assert forward.entities["enemies"] == backward.entities["enemies"]
    assert forward.entities["enemies"][0] != forward.entities["enemies"][1]


def test_player_relative_entity_features_are_translation_invariant(schema, capture):
    base = encode_capture(capture, schema)
    shifted = copy.deepcopy(capture)
    shifted["player"]["x"] += 100
    shifted["player"]["y"] += 50
    for group in schema["groups"]:
        for entity in shifted["entities"][group]:
            entity["x"] += 100
            entity["y"] += 50
    moved = encode_capture(shifted, schema)
    assert base.entities == moved.entities


def test_overflow_keeps_imminent_threats_and_counts_drops(schema, capture):
    crowded = copy.deepcopy(capture)
    crowded["entities"]["projectiles"] = [
        {"x": 1000 + index * 10, "y": 400, "vx": 100, "vy": 0, "radius": 8, "instance_id": 100 + index}
        for index in range(40)
    ]
    crowded["entities"]["projectiles"].append(
        {"x": 540, "y": 400, "vx": -500, "vy": 0, "radius": 8, "instance_id": 999, "type_id": "imminent"}
    )
    encoded = encode_capture(crowded, schema)
    assert sum(encoded.masks["projectiles"]) == 32
    assert encoded.dropped_counts["projectiles"] == 9
    contact_index = schema["entity_features"].index("contact_risk")
    assert encoded.entities["projectiles"][0][contact_index] > 0.5


def test_empty_groups_are_inert_and_temporal_gap_is_masked(schema, capture):
    empty = copy.deepcopy(capture)
    empty["entities"] = {group: [] for group in schema["groups"]}
    empty["control_dt_ms"] = 12_000
    encoded = encode_capture(empty, schema)
    assert not encoded.temporal_valid
    for group in schema["groups"]:
        assert sum(encoded.masks[group]) == 0
        assert all(value == 0.0 for row in encoded.entities[group] for value in row)


def test_nonfinite_and_schema_mismatch_are_rejected(schema, capture):
    bad = copy.deepcopy(capture)
    bad["player"]["x"] = math.nan
    with pytest.raises(ObservationError, match="not finite"):
        encode_capture(bad, schema)
    mismatch = copy.deepcopy(capture)
    mismatch["capture_schema_hash"] = "0" * 64
    with pytest.raises(ObservationError, match="schema hash mismatch"):
        encode_capture(mismatch, schema)


def test_action_range_is_clamped(schema, capture):
    out_of_range = copy.deepcopy(capture)
    out_of_range["teacher"]["action"] = {"x": 2.0, "y": -3.0}
    encoded = encode_capture(out_of_range, schema)
    names = schema["global_features"]
    assert encoded.global_features[names.index("teacher_action_x")] == 1.0
    assert encoded.global_features[names.index("teacher_action_y")] == -1.0


def test_golden_digest_is_stable(schema, capture):
    assert canonical_digest(encode_capture(capture, schema)) == "D62D26F3FCAE019A9A6E02A8C617B2C95DA8911983F3342402B645EC47E84F25"
