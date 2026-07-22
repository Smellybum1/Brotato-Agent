import json
from pathlib import Path

from scripts.validate_telemetry import validate_run


def _tmp(name: str) -> Path:
    root = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "_tmp"
    root.mkdir(parents=True, exist_ok=True)
    d = root / name
    d.mkdir(exist_ok=True)
    return d


def test_validate_monotonic_and_terminal():
    d = _tmp("ok")
    p = d / "events.jsonl"
    lines = []
    for i, ev in enumerate(["run_start", "phase_transition", "run_end"], 1):
        lines.append(
            json.dumps(
                {
                    "schema_version": "1.0.0",
                    "run_id": "r1",
                    "seq": i,
                    "ts_ms": i * 10,
                    "event": ev,
                    "payload": {},
                }
            )
        )
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    res = validate_run(p)
    assert res["ok"]


def test_validate_rejects_non_monotonic():
    d = _tmp("bad")
    p = d / "events.jsonl"
    p.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "schema_version": "1.0.0",
                        "run_id": "r",
                        "seq": 2,
                        "ts_ms": 1,
                        "event": "run_start",
                        "payload": {},
                    }
                ),
                json.dumps(
                    {
                        "schema_version": "1.0.0",
                        "run_id": "r",
                        "seq": 1,
                        "ts_ms": 2,
                        "event": "run_end",
                        "payload": {},
                    }
                ),
            ]
        ),
        encoding="utf-8",
    )
    res = validate_run(p)
    assert not res["ok"]


def test_validate_accepts_mixed_v1_and_v2_combat_capture():
    import hashlib

    root = Path(__file__).resolve().parents[2]
    schema_path = root / "configs" / "wp2" / "combat_capture_v2.schema.json"
    schema_hash = hashlib.sha256(schema_path.read_bytes()).hexdigest().upper()
    d = _tmp("mixed_v2")
    p = d / "events.jsonl"
    capture = {
        "capture_schema_id": "combat_capture_v2",
        "capture_schema_hash": schema_hash,
        "capture_seq": 1,
        "observation_ts_ms": 100,
        "observation_age_ms": 1,
        "control_dt_ms": 50,
        "valid": True,
        "wave": 1,
        "wave_time": {"elapsed_sec": 1.0, "remaining_sec": 19.0, "duration_sec": 20.0, "valid": True},
        "player": {},
        "teacher": {
            "action": {"x": 1.0, "y": 0.0},
            "previous_action": {"x": 0.0, "y": 0.0},
            "action_fresh": True,
            "reason": "potential_field",
            "contributions": {},
        },
        "entities": {key: [] for key in ("enemies", "bosses", "projectiles", "materials", "consumables", "crates", "obstacles")},
        "weapons": [],
        "arena": {},
        "invalid_counts": {},
        "dropped_counts": {},
    }
    events = [
        {"schema_version": "1.0.0", "run_id": "r", "seq": 1, "ts_ms": 1, "event": "run_start", "payload": {}},
        {"schema_version": "2.0.0", "run_id": "r", "seq": 2, "ts_ms": 2, "event": "combat_capture", "payload": capture},
        {"schema_version": "1.0.0", "run_id": "r", "seq": 3, "ts_ms": 3, "event": "run_end", "payload": {}},
    ]
    p.write_text("\n".join(json.dumps(event) for event in events) + "\n", encoding="utf-8")
    assert validate_run(p)["ok"]


def test_validate_rejects_combat_capture_schema_hash_mismatch():
    d = _tmp("bad_v2_hash")
    p = d / "events.jsonl"
    capture = {
        "capture_schema_id": "combat_capture_v2",
        "capture_schema_hash": "0" * 64,
        "capture_seq": 1,
        "observation_ts_ms": 1,
        "observation_age_ms": 0,
        "control_dt_ms": 0,
        "valid": True,
        "wave": 1,
        "wave_time": {},
        "player": {},
        "teacher": {"action": {"x": 0, "y": 0}, "previous_action": {"x": 0, "y": 0}},
        "entities": {key: [] for key in ("enemies", "bosses", "projectiles", "materials", "consumables", "crates", "obstacles")},
        "weapons": [],
        "arena": {},
        "invalid_counts": {},
        "dropped_counts": {},
    }
    events = [
        {"schema_version": "1.0.0", "run_id": "r", "seq": 1, "ts_ms": 1, "event": "run_start", "payload": {}},
        {"schema_version": "2.0.0", "run_id": "r", "seq": 2, "ts_ms": 2, "event": "combat_capture", "payload": capture},
        {"schema_version": "1.0.0", "run_id": "r", "seq": 3, "ts_ms": 3, "event": "run_end", "payload": {}},
    ]
    p.write_text("\n".join(json.dumps(event) for event in events) + "\n", encoding="utf-8")
    result = validate_run(p)
    assert not result["ok"]
    assert any("schema hash mismatch" in error for error in result["errors"])
