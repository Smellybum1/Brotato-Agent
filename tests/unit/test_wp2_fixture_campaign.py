"""Pure-function tests for the unattended fixture campaign driver.

Only pure helpers are covered. The launch/watchdog/restart loop touches the live
game process and %APPDATA%, so it is NOT tested here -- it can only be exercised
live, and a mock of it would assert the mock, not the behaviour.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.wp2_collect_teacher import MOD_VERSION, POLICY_VERSION
from scripts.wp2_fixture_campaign import (
    build_row,
    current_wave_from_tail,
    restart_budget_exhausted,
    should_restart,
)


def _clean_summary(**over):
    summary = {
        "run_id": "run_1",
        "result": "victory",
        "last_wave": 20,
        "damage_taken": 87,
        "duration_ms": 1234,
        "policy_version": POLICY_VERSION,
        "mod_version": MOD_VERSION,
        "telemetry_complete": True,
        "errors": 0,
        "hangs": 0,
        "illegal_actions": 0,
    }
    summary.update(over)
    return summary


def test_build_row_clean_summary_has_empty_fault():
    row = build_row("run_1", _clean_summary())
    assert row == {
        "run_id": "run_1",
        "result": "victory",
        "last_wave": 20,
        "damage_taken": 87,
        "duration_ms": 1234,
        "fault": "",
    }


def test_build_row_records_fault_but_still_returns_a_row():
    row = build_row("run_2", _clean_summary(errors=3, result="defeat", last_wave=14))
    assert row["run_id"] == "run_2"
    assert row["result"] == "defeat"
    assert row["last_wave"] == 14
    assert "errors=3" in row["fault"]


def test_build_row_defeat_is_not_a_fault():
    assert build_row("run_3", _clean_summary(result="defeat"))["fault"] == ""


def test_build_row_mod_mismatch_is_recorded():
    row = build_row("run_4", _clean_summary(mod_version="0.0.1"))
    assert "mod mismatch" in row["fault"]


def test_should_restart_clean_state_returns_empty():
    assert should_restart(True, 3.0, 100.0, stall_sec=180.0, run_timeout_sec=2700.0) == ""


def test_should_restart_game_not_running():
    assert should_restart(False, 1.0, 1.0, 180.0, 2700.0) == "game_not_running"


def test_should_restart_stall():
    reason = should_restart(True, 200.0, 300.0, 180.0, 2700.0)
    assert reason.startswith("telemetry_stale_")


def test_should_restart_run_timeout():
    reason = should_restart(True, 1.0, 3000.0, 180.0, 2700.0)
    assert reason.startswith("run_timeout_")


def test_should_restart_none_ages_are_tolerated():
    assert should_restart(True, None, None, 180.0, 2700.0) == ""


def test_should_restart_not_running_beats_fresh_telemetry():
    assert should_restart(False, 0.0, 0.0, 180.0, 2700.0) == "game_not_running"


def test_restart_budget():
    assert restart_budget_exhausted(0, 20) is False
    assert restart_budget_exhausted(19, 20) is False
    assert restart_budget_exhausted(20, 20) is True
    assert restart_budget_exhausted(21, 20) is True
    assert restart_budget_exhausted(0, 0) is True


def test_current_wave_from_tail_uses_latest_capture():
    lines = [
        json.dumps({"event": "combat_capture", "payload": {"wave": 5}}),
        json.dumps({"event": "run_start", "payload": {}}),
        json.dumps({"event": "combat_capture", "payload": {"wave": 19}}),
        "not json",
    ]
    assert current_wave_from_tail(lines) == 19


def test_current_wave_from_tail_no_captures():
    assert current_wave_from_tail([json.dumps({"event": "run_start"}), ""]) is None


def test_current_wave_from_tail_non_int_wave_is_none():
    lines = [json.dumps({"event": "combat_capture", "payload": {"wave": "x"}})]
    assert current_wave_from_tail(lines) is None


def test_resume_from_save_is_hard_coded_off():
    """The driver must never enable resume_from_save -- it plays full runs."""
    src = (
        Path(__file__).resolve().parents[2] / "scripts" / "wp2_fixture_campaign.py"
    ).read_text(encoding="utf-8")
    assert "resume_from_save=True" not in src
    assert src.count("resume_from_save=False") == 2


def test_driver_never_deploys():
    src = (
        Path(__file__).resolve().parents[2] / "scripts" / "wp2_fixture_campaign.py"
    ).read_text(encoding="utf-8")
    assert "import deploy_mod" not in src
    assert "scripts.deploy_mod" not in src
    assert "deploy_mod.main" not in src


def test_rearm_fires_when_no_new_run_starts():
    """Summary written but the next run never starts.

    With no live run directory there is no events.jsonl to go stale, so the stall
    detector is blind and only the long run timeout would fire. The rearm guard
    covers it.
    """
    # No live run, past the rearm window -> restart.
    assert should_restart(
        running=True, telemetry_age_sec=None, run_elapsed_sec=200.0,
        stall_sec=180.0, run_timeout_sec=2700.0,
        has_live_run=False, rearm_sec=180.0,
    ).startswith("no_new_run_")
    # No live run, still inside the rearm window -> keep going.
    assert should_restart(
        running=True, telemetry_age_sec=None, run_elapsed_sec=100.0,
        stall_sec=180.0, run_timeout_sec=2700.0,
        has_live_run=False, rearm_sec=180.0,
    ) == ""
    # A LIVE run past the rearm window is a normal long run, NOT a rearm case:
    # a full 20-wave run takes ~20 min and must not be killed at 3 min.
    assert should_restart(
        running=True, telemetry_age_sec=1.0, run_elapsed_sec=1200.0,
        stall_sec=180.0, run_timeout_sec=2700.0,
        has_live_run=True, rearm_sec=180.0,
    ) == ""
