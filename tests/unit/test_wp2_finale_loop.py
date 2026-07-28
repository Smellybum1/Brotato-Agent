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
        "finale_v2": False,
        "finale_rate_full": False,
    }
    base.update(overrides)
    return base


def test_valid_trial(tmp_path: Path):
    analysis = analyse_events(_events(tmp_path, [(20, [PREDATOR]), (20, [PREDATOR])]))
    assert analysis["waves"] == [20]
    assert analysis["n_captures"] == 2
    assert analysis["boss_entity"] == "predator"
    assert analysis["boss_capture_count"] == 2
    assert validate_trial(analysis, _summary(), "predator", False) == ""


def test_fresh_run_detected(tmp_path: Path):
    analysis = analyse_events(_events(tmp_path, [(1, []), (2, [])]))
    assert analysis["waves"] == [1, 2]
    assert validate_trial(analysis, _summary(), "predator", False) == "resume_failed_fresh_run"


def test_two_distinct_boss_paths_invalid(tmp_path: Path):
    analysis = analyse_events(_events(tmp_path, [(20, [PREDATOR]), (20, [INVOKER])]))
    assert validate_trial(analysis, _summary(), "predator", False) == "boss_path_count:2"


def test_wrong_mod_version_invalid(tmp_path: Path):
    analysis = analyse_events(_events(tmp_path, [(20, [PREDATOR])]))
    reason = validate_trial(analysis, _summary(mod_version="0.0.1-bogus"), "predator", False)
    assert reason == "mod_mismatch:0.0.1-bogus"


def test_boss_mismatch_invalid(tmp_path: Path):
    analysis = analyse_events(_events(tmp_path, [(20, [INVOKER])]))
    assert validate_trial(analysis, _summary(), "predator", False) == "boss_mismatch:invoker"


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
    write_agent_config(path, auto_start=True, resume_from_save=True, finale_v2=True)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["student_model_sha256"] == "DEADBEEF"
    assert payload["student_enabled"] is True
    assert payload["character"] == "character_crazy"
    assert payload["danger"] == 3
    assert payload["auto_start"] is True
    assert payload["resume_from_save"] is True
    assert payload["finale_v2"] is True

    write_agent_config(path, auto_start=False, resume_from_save=False, finale_v2=False)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["auto_start"] is False
    assert payload["resume_from_save"] is False
    assert payload["finale_v2"] is False
    assert payload["student_model_sha256"] == "DEADBEEF"
    assert payload["student_enabled"] is True


def test_write_agent_config_defaults_when_absent(tmp_path: Path):
    path = tmp_path / "agent_config.json"
    write_agent_config(path, auto_start=True, resume_from_save=True, finale_v2=True)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["character"] == "character_well_rounded"
    assert payload["danger"] == 0
    assert payload["weapon_prefixes"] == ["weapon_smg", "weapon_stick"]
    assert payload["finale_v2"] is True


# --- arm guard: a lost finale_v2 flag must INVALIDATE, not mislabel -----------


def test_finale_arm_matches_both_arms(tmp_path: Path):
    analysis = analyse_events(_events(tmp_path, [(20, [PREDATOR])]))
    assert validate_trial(analysis, _summary(finale_v2=False), "predator", False) == ""
    assert validate_trial(analysis, _summary(finale_v2=True), "predator", True) == ""


def test_finale_arm_mismatch_expected_v2(tmp_path: Path):
    analysis = analyse_events(_events(tmp_path, [(20, [PREDATOR])]))
    reason = validate_trial(analysis, _summary(finale_v2=False), "predator", True)
    assert reason == "finale_arm_mismatch:False"


def test_finale_arm_mismatch_expected_v1(tmp_path: Path):
    analysis = analyse_events(_events(tmp_path, [(20, [PREDATOR])]))
    reason = validate_trial(analysis, _summary(finale_v2=True), "predator", False)
    assert reason == "finale_arm_mismatch:True"


def test_finale_arm_missing_key_treated_as_false(tmp_path: Path):
    analysis = analyse_events(_events(tmp_path, [(20, [PREDATOR])]))
    summary = _summary()
    summary.pop("finale_v2")
    assert validate_trial(analysis, summary, "predator", True) == "finale_arm_mismatch:None"
    assert validate_trial(analysis, summary, "predator", False) == ""


# --- rate-only arm guard ------------------------------------------------------


def test_finale_rate_arm_matches_both_arms(tmp_path: Path):
    analysis = analyse_events(_events(tmp_path, [(20, [PREDATOR])]))
    assert validate_trial(analysis, _summary(), "predator", False, False) == ""
    assert (
        validate_trial(
            analysis, _summary(finale_rate_full=True), "predator", False, True
        )
        == ""
    )


def test_finale_rate_arm_mismatch_expected_rate_full(tmp_path: Path):
    analysis = analyse_events(_events(tmp_path, [(20, [PREDATOR])]))
    reason = validate_trial(analysis, _summary(), "predator", False, True)
    assert reason == "finale_rate_arm_mismatch:False"


def test_finale_rate_arm_mismatch_expected_v1(tmp_path: Path):
    analysis = analyse_events(_events(tmp_path, [(20, [PREDATOR])]))
    reason = validate_trial(
        analysis, _summary(finale_rate_full=True), "predator", False, False
    )
    assert reason == "finale_rate_arm_mismatch:True"


def test_finale_rate_arm_missing_key_treated_as_false(tmp_path: Path):
    analysis = analyse_events(_events(tmp_path, [(20, [PREDATOR])]))
    summary = _summary()
    summary.pop("finale_rate_full")
    assert (
        validate_trial(analysis, summary, "predator", False, True)
        == "finale_rate_arm_mismatch:None"
    )
    assert validate_trial(analysis, summary, "predator", False, False) == ""


def test_write_agent_config_writes_both_finale_flags_every_time(tmp_path: Path):
    path = tmp_path / "agent_config.json"
    write_agent_config(
        path, auto_start=True, resume_from_save=True, finale_v2=False,
        finale_rate_full=True,
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["finale_v2"] is False
    assert payload["finale_rate_full"] is True

    write_agent_config(
        path, auto_start=False, resume_from_save=False, finale_v2=False,
        finale_rate_full=False,
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["finale_rate_full"] is False


def test_loop_source_exposes_finale_rate_full_flag():
    src = (
        Path(__file__).resolve().parents[2] / "scripts/wp2_finale_loop.py"
    ).read_text(encoding="utf-8")
    assert 'ap.add_argument("--finale-rate-full", action="store_true")' in src
    assert "finale_rate_full=args.finale_rate_full," in src
    assert '"finale_rate_full": bool(args.finale_rate_full),' in src
    # The finally block must disarm BOTH flags.
    tail = src.split("    finally:", 1)[1]
    assert "finale_rate_full=False," in tail


# --------------------------------------------------------------------------
# wave-20 dev flags: finale_no_panic / finale_heal_seek / finale_range_keep
# --------------------------------------------------------------------------

DEV_FLAGS = ("finale_no_panic", "finale_heal_seek", "finale_range_keep")


def _dev_summary(**overrides):
    base = _summary()
    for flag in DEV_FLAGS:
        base[flag] = False
    base.update(overrides)
    return base


def test_dev_flag_arms_match_when_requested_and_recorded_agree(tmp_path: Path):
    analysis = analyse_events(_events(tmp_path, [(20, [PREDATOR])]))
    summary = _dev_summary(finale_no_panic=True, finale_heal_seek=True,
                           finale_range_keep=True)
    assert validate_trial(
        analysis, summary, "predator", False, False, True, True, True
    ) == ""


def test_finale_no_panic_mismatch_both_directions(tmp_path: Path):
    analysis = analyse_events(_events(tmp_path, [(20, [PREDATOR])]))
    assert validate_trial(
        analysis, _dev_summary(), "predator", False, False, True
    ) == "finale_no_panic_mismatch:False"
    assert validate_trial(
        analysis, _dev_summary(finale_no_panic=True), "predator", False, False, False
    ) == "finale_no_panic_mismatch:True"


def test_finale_heal_seek_mismatch_both_directions(tmp_path: Path):
    analysis = analyse_events(_events(tmp_path, [(20, [PREDATOR])]))
    assert validate_trial(
        analysis, _dev_summary(), "predator", False, False, False, True
    ) == "finale_heal_seek_mismatch:False"
    assert validate_trial(
        analysis, _dev_summary(finale_heal_seek=True), "predator",
        False, False, False, False
    ) == "finale_heal_seek_mismatch:True"


def test_finale_range_keep_mismatch_both_directions(tmp_path: Path):
    analysis = analyse_events(_events(tmp_path, [(20, [PREDATOR])]))
    assert validate_trial(
        analysis, _dev_summary(), "predator", False, False, False, False, True
    ) == "finale_range_keep_mismatch:False"
    assert validate_trial(
        analysis, _dev_summary(finale_range_keep=True), "predator",
        False, False, False, False, False
    ) == "finale_range_keep_mismatch:True"


def test_dev_flag_missing_key_is_treated_as_false(tmp_path: Path):
    """A build that predates a flag records nothing; asking for it must invalidate."""
    analysis = analyse_events(_events(tmp_path, [(20, [PREDATOR])]))
    summary = _summary()  # carries none of the dev-flag keys
    assert validate_trial(
        analysis, summary, "predator", False, False, True
    ) == "finale_no_panic_mismatch:None"
    # ... but the all-off arm still validates against such a summary.
    assert validate_trial(analysis, summary, "predator", False, False) == ""


def test_write_agent_config_writes_the_dev_flags_unconditionally(tmp_path: Path):
    path = tmp_path / "agent_config.json"
    write_agent_config(
        path, auto_start=True, resume_from_save=True, finale_v2=False,
        finale_rate_full=False, finale_no_panic=True, finale_heal_seek=True,
        finale_range_keep=True,
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    for flag in DEV_FLAGS:
        assert payload[flag] is True

    # deploy_mod.py rewrites this file wholesale, so every key must be written
    # every time -- a setdefault would silently run a stale arm.
    write_agent_config(
        path, auto_start=False, resume_from_save=False, finale_v2=False,
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    for flag in DEV_FLAGS:
        assert payload[flag] is False


def test_loop_source_exposes_the_dev_flag_cli_and_disarms_them():
    src = (
        Path(__file__).resolve().parents[2] / "scripts/wp2_finale_loop.py"
    ).read_text(encoding="utf-8")
    tail = src.split("    finally:", 1)[1]
    for flag in DEV_FLAGS:
        cli = "--" + flag.replace("_", "-")
        assert 'ap.add_argument("%s", action="store_true")' % cli in src
        assert "%s=args.%s," % (flag, flag) in src
        # Recorded on EVERY trial row, so the arm is in the raw data.
        assert '"%s": bool(args.%s),' % (flag, flag) in src
        # An interrupted loop must never leave the machine armed.
        assert "%s=False," % flag in tail


def test_target_wave_17_valid(tmp_path: Path):
    # Wave 17 has no boss; died at 17, so no survival tail.
    analysis = analyse_events(_events(tmp_path, [(17, []), (17, [])]))
    assert analysis["waves"] == [17]
    assert validate_trial(analysis, _summary(), "predator", False, target_wave=17) == ""


def test_target_wave_17_fresh_run_detected(tmp_path: Path):
    analysis = analyse_events(
        _events(tmp_path, [(w, [PREDATOR] if w == 17 else []) for w in range(1, 18)])
    )
    assert analysis["waves"] == list(range(1, 18))
    reason = validate_trial(analysis, _summary(), "predator", False, target_wave=17)
    assert reason == "resume_failed_fresh_run"


def test_target_wave_17_survival_tail_valid(tmp_path: Path):
    analysis = analyse_events(
        _events(tmp_path, [(17, []), (18, []), (19, []), (20, [PREDATOR])])
    )
    assert analysis["waves"] == [17, 18, 19, 20]
    assert validate_trial(analysis, _summary(), "predator", False, target_wave=17) == ""


def test_target_wave_17_died_in_18_valid(tmp_path: Path):
    analysis = analyse_events(_events(tmp_path, [(17, []), (18, [])]))
    assert validate_trial(analysis, _summary(), "predator", False, target_wave=17) == ""


def test_target_wave_17_gap_rejected(tmp_path: Path):
    analysis = analyse_events(_events(tmp_path, [(17, []), (19, [])]))
    reason = validate_trial(analysis, _summary(), "predator", False, target_wave=17)
    assert reason == "wave_gap:[17, 19]"


def test_target_wave_17_missing_target_rejected(tmp_path: Path):
    analysis = analyse_events(_events(tmp_path, [(18, []), (19, []), (20, [PREDATOR])]))
    reason = validate_trial(analysis, _summary(), "predator", False, target_wave=17)
    assert reason == "unexpected_waves:[18, 19, 20]"


def test_target_wave_17_boss_without_wave_20_rejected(tmp_path: Path):
    analysis = analyse_events(_events(tmp_path, [(17, [PREDATOR]), (18, [])]))
    reason = validate_trial(analysis, _summary(), "predator", False, target_wave=17)
    assert reason == "unexpected_boss:['%s']" % PREDATOR


def test_target_wave_17_boss_identity_not_enforced(tmp_path: Path):
    # THE BIAS BUG: at target_wave 17 over a mixed-boss fixture set, a trial that
    # SURVIVES into wave 20 with the "wrong" boss must stay VALID. Rejecting it
    # would discard exactly the surviving (non-random) subset.
    analysis = analyse_events(
        _events(tmp_path, [(17, []), (18, []), (19, []), (20, [INVOKER])])
    )
    assert analysis["boss_entity"] == "invoker"
    assert validate_trial(analysis, _summary(), "predator", False, target_wave=17) == ""


def test_target_wave_20_boss_identity_still_enforced(tmp_path: Path):
    analysis = analyse_events(_events(tmp_path, [(20, [INVOKER])]))
    assert validate_trial(analysis, _summary(), "predator", False, target_wave=20) == (
        "boss_mismatch:invoker"
    )


def test_target_wave_17_multiple_boss_paths_rejected(tmp_path: Path):
    analysis = analyse_events(
        _events(tmp_path, [(17, []), (18, []), (19, []), (20, [INVOKER, PREDATOR])])
    )
    reason = validate_trial(analysis, _summary(), "predator", False, target_wave=17)
    assert reason == "boss_path_count:2"


def test_target_wave_17_no_boss_at_wave_20_allowed(tmp_path: Path):
    # Structural sanity only at target < 20: zero boss paths is not a rejection.
    analysis = analyse_events(_events(tmp_path, [(17, []), (18, []), (19, []), (20, [])]))
    assert validate_trial(analysis, _summary(), "predator", False, target_wave=17) == ""


def test_target_wave_defaults_to_20_and_is_recorded():
    src = Path("scripts/wp2_finale_loop.py").read_text(encoding="utf-8")
    assert 'ap.add_argument("--target-wave", type=int, default=20)' in src
    assert '"target_wave": int(getattr(args, "target_wave", 20)),' in src


def test_target_wave_20_contiguity_equivalent_to_old_equality(tmp_path: Path):
    # Wave 20 ends the run, so nothing above 20 exists: contiguity-from-20
    # admits exactly [20], identical to the previous `waves != [20]` rule.
    analysis = analyse_events(_events(tmp_path, [(20, [PREDATOR])]))
    assert validate_trial(analysis, _summary(), "predator", False) == ""
    analysis = analyse_events(_events(tmp_path, [(19, [])]))
    assert validate_trial(analysis, _summary(), "predator", False) == "resume_failed_fresh_run"
