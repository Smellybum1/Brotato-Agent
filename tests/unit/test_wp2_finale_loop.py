import json
from pathlib import Path

from scripts.wp2_collect_teacher import MOD_VERSION, POLICY_VERSION
from scripts.wp2_finale_loop import (
    analyse_events,
    boss_entity_from_path,
    validate_trial,
    write_agent_config,
)


PREDATOR = "res://entities/units/enemies/predator/predator.gd"
INVOKER = "res://entities/units/enemies/invoker/invoker.gd"


def test_boss_entity_from_path():
    assert boss_entity_from_path(PREDATOR) == "predator"
    assert boss_entity_from_path(INVOKER) == "invoker"


def test_boss_entity_from_path_no_match_returns_raw():
    assert boss_entity_from_path("res://entities/units/boss/weird.gd") == (
        "res://entities/units/boss/weird.gd"
    )
    assert boss_entity_from_path("") == ""


def _events(tmp_path: Path, rows: list[tuple[int, list[str]]]) -> Path:
    path = tmp_path / "events.jsonl"
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        for wave, bosses in rows:
            fh.write(
                json.dumps(
                    {
                        "event": "combat_capture",
                        "payload": {
                            "wave": wave,
                            "entities": {"bosses": [{"script_path": p} for p in bosses]},
                        },
                    }
                )
                + "\n"
            )
        fh.write(json.dumps({"event": "run_end", "payload": {}}) + "\n")
    return path


def _summary(**overrides):
    base = {
        "result": "victory",
        "policy_version": POLICY_VERSION,
        "mod_version": MOD_VERSION,
        "last_wave": 20,
        "damage_taken": 12,
        "duration_ms": 60000,
    }
    base.update(overrides)
    return base


def test_valid_trial(tmp_path: Path):
    analysis = analyse_events(_events(tmp_path, [(20, [PREDATOR]), (20, [PREDATOR])]))
    assert analysis["waves"] == [20]
    assert analysis["n_captures"] == 2
    assert analysis["boss_entity"] == "predator"
    assert analysis["boss_capture_count"] == 2
    assert validate_trial(analysis, _summary(), "predator") == ""


def test_fresh_run_detected(tmp_path: Path):
    analysis = analyse_events(_events(tmp_path, [(1, []), (2, [])]))
    assert analysis["waves"] == [1, 2]
    assert validate_trial(analysis, _summary(), "predator") == "resume_failed_fresh_run"


def test_two_distinct_boss_paths_invalid(tmp_path: Path):
    analysis = analyse_events(_events(tmp_path, [(20, [PREDATOR]), (20, [INVOKER])]))
    assert validate_trial(analysis, _summary(), "predator") == "boss_path_count:2"


def test_wrong_mod_version_invalid(tmp_path: Path):
    analysis = analyse_events(_events(tmp_path, [(20, [PREDATOR])]))
    reason = validate_trial(analysis, _summary(mod_version="0.0.1-bogus"), "predator")
    assert reason == "mod_mismatch:0.0.1-bogus"


def test_boss_mismatch_invalid(tmp_path: Path):
    analysis = analyse_events(_events(tmp_path, [(20, [INVOKER])]))
    assert validate_trial(analysis, _summary(), "predator") == "boss_mismatch:invoker"


def test_write_agent_config_preserves_unrelated_keys(tmp_path: Path):
    path = tmp_path / "agent_config.json"
    path.write_text(
        json.dumps(
            {
                "character": "character_crazy",
                "danger": 3,
                "student_model_sha256": "DEADBEEF",
                "student_enabled": True,
            }
        ),
        encoding="utf-8",
    )
    write_agent_config(path, auto_start=True, resume_from_save=True)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["student_model_sha256"] == "DEADBEEF"
    assert payload["student_enabled"] is True
    assert payload["character"] == "character_crazy"
    assert payload["danger"] == 3
    assert payload["auto_start"] is True
    assert payload["resume_from_save"] is True

    write_agent_config(path, auto_start=False, resume_from_save=False)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["auto_start"] is False
    assert payload["resume_from_save"] is False
    assert payload["student_model_sha256"] == "DEADBEEF"


def test_write_agent_config_defaults_when_absent(tmp_path: Path):
    path = tmp_path / "agent_config.json"
    write_agent_config(path, auto_start=True, resume_from_save=True)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["character"] == "character_well_rounded"
    assert payload["danger"] == 0
    assert payload["weapon_prefixes"] == ["weapon_smg", "weapon_stick"]
