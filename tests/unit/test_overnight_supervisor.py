import json

from scripts.overnight_supervisor import load_gate_state, save_gate_state


def test_gate_state_round_trip_restores_collected_summary(tmp_path):
    run_id = "run_resume_1"
    summary_dir = tmp_path / run_id
    summary_dir.mkdir()
    summary_path = summary_dir / "summary.json"
    summary = {"run_id": run_id, "result": "victory", "last_wave": 20}
    summary_path.write_text(json.dumps(summary), encoding="utf-8")

    state_path = tmp_path / "gate_state_v71.json"
    save_gate_state(state_path, {"old_run"}, [summary])
    restored = load_gate_state(state_path, {run_id: summary_path})

    assert restored == ({"old_run"}, [summary])
    assert not state_path.with_suffix(".json.tmp").exists()


def test_gate_state_rejects_missing_summary_evidence(tmp_path):
    state_path = tmp_path / "gate_state_v71.json"
    state_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "baseline_run_ids": [],
                "collected_run_ids": ["run_missing"],
            }
        ),
        encoding="utf-8",
    )

    try:
        load_gate_state(state_path, {})
    except RuntimeError as exc:
        assert "run_missing" in str(exc)
    else:
        raise AssertionError("missing gate evidence was accepted")
