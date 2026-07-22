import json
from pathlib import Path

import pytest

from trainer.data.wp1_telemetry_audit import audit_runs, percentile, render_markdown


def test_percentile_interpolates_and_handles_empty():
    assert percentile([], 0.5) is None
    assert percentile([0, 10], 0.5) == 5.0
    assert percentile([1, 2, 3], 0.9) == pytest.approx(2.8)


def test_audit_reports_missing_entity_arrays_without_inventing_capacity(tmp_path: Path):
    run = tmp_path / "run_one"
    run.mkdir()
    events = [
        {"seq": 1, "ts_ms": 0, "event": "run_start", "payload": {}},
        {"seq": 2, "ts_ms": 500, "event": "combat_tick", "payload": {
            "wave": 1, "move": {"x": 1.0, "y": 0.0},
            "debug": {"enemies": 3, "projectiles": 2},
            "hp": 10, "loot": 1, "consumables": 0,
        }},
        {"seq": 3, "ts_ms": 1000, "event": "combat_tick", "payload": {
            "wave": 1, "move": {"x": 0.0, "y": 1.0},
            "debug": {"enemies": 5, "projectiles": 4},
            "hp": 9, "loot": 2, "consumables": 1,
        }},
        {"seq": 4, "ts_ms": 1100, "event": "run_end", "payload": {"result": "victory"}},
    ]
    (run / "events.jsonl").write_text(
        "".join(json.dumps(event) + "\n" for event in events), encoding="utf-8"
    )

    audit = audit_runs(tmp_path)

    assert audit["runs"] == 1
    assert audit["terminal_runs"] == 1
    assert audit["combat_ticks"] == 2
    assert audit["tick_gap_ms"]["p50"] == 500.0
    assert audit["entity_count_percentiles"]["enemies"]["max"] == 5.0
    assert audit["field_availability"]["enemy_entities"]["fraction"] == 0.0
    assert audit["field_availability"]["teacher_action"]["fraction"] == 1.0
    assert "cannot directly produce" in render_markdown(audit)
