import hashlib
import json
from pathlib import Path

import pytest

from trainer.data.combat_capture_audit import audit_capture_runs, percentile, render_markdown


def test_percentile_interpolates():
    assert percentile([1, 2, 3], 0.9) == pytest.approx(2.8)
    assert percentile([], 0.5) is None


def test_audit_capture_counts_and_severe_states(tmp_path: Path):
    schema = tmp_path / "schema.json"
    schema.write_text("{}\n", encoding="utf-8")
    digest = hashlib.sha256(schema.read_bytes()).hexdigest().upper()
    run = tmp_path / "runs" / "run_test"
    run.mkdir(parents=True)
    base_entities = {key: [] for key in ("enemies", "bosses", "projectiles", "materials", "consumables", "crates", "obstacles")}
    base_entities["bosses"] = [{"name": "elite_boss", "attack_path": "charging_attack"}]
    base_entities["projectiles"] = [{} for _ in range(10)]
    payload = {
        "capture_schema_hash": digest,
        "wave": 20,
        "valid": True,
        "control_dt_ms": 50,
        "observation_age_ms": 1,
        "player": {"x": 50, "y": 50, "hp_ratio": 0.2},
        "teacher": {"action": {"x": 1.0, "y": 0.0}, "contributions": {"risk": 2.0}},
        "entities": base_entities,
        "arena": {"width": 1000, "height": 800},
        "invalid_counts": {"enemies": 1},
        "dropped_counts": {"enemies": 0},
    }
    events = [
        {"schema_version": "1.0.0", "event": "run_start", "payload": {}},
        {"schema_version": "2.0.0", "event": "combat_capture", "payload": payload},
        {"schema_version": "1.0.0", "event": "run_end", "payload": {}},
    ]
    (run / "events.jsonl").write_text("\n".join(json.dumps(event) for event in events), encoding="utf-8")
    audit = audit_capture_runs(tmp_path / "runs", schema)
    assert audit["run_count"] == 1
    assert audit["terminal_run_count"] == 1
    assert audit["capture_count"] == 1
    assert audit["entity_counts"]["projectiles"]["max"] == 10
    assert audit["severe_state_counts"] == {
        "boss": 1,
        "charger": 1,
        "corner": 1,
        "dense_projectiles": 1,
        "elite": 1,
        "low_health": 1,
        "near_wall": 1,
    }
    assert audit["teacher_contributions"]["teacher.risk"]["max"] == 2.0
    assert "Capacities remain provisional" in render_markdown(audit)
