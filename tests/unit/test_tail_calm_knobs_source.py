"""Source-text pins for the two SAFETY-TAIL dev knobs and the tail instrument.

The mod GDScript is never parsed by this suite, so source-text assertions are the
only guard available. Both knobs are FLOAT doses whose 1.0 default is exactly
inert, and both scaled computations sit behind a `!= 1.0` guard so the default
path is unchanged in behaviour AND in cost -- the charge test is not even
evaluated.

Companion to test_calm_threat_mult_source.py, which pins the DESIRE-level knob.
These are deliberately separate names so the two layers stay attributable.
"""

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
POTENTIAL_FIELD = ROOT / "mod/mods-unpacked/Tom-BrotatoAgent/teacher/potential_field.gd"
CONTROLLER = ROOT / "mod/mods-unpacked/Tom-BrotatoAgent/runtime/agent_controller.gd"
TELEMETRY = ROOT / "mod/mods-unpacked/Tom-BrotatoAgent/telemetry/telemetry_writer.gd"
LOOP = ROOT / "scripts/wp2_finale_loop.py"

KNOBS = ("tail_calm_penalty_mult", "tail_calm_clearance_mult")


def _func(text: str, name: str) -> str:
    return text.split("func %s" % name, 1)[1].split("\nfunc ", 1)[0]


def test_declared_on_the_field_with_inert_defaults():
    potential = POTENTIAL_FIELD.read_text(encoding="utf-8")
    for knob in KNOBS:
        assert re.search(
            r"^var %s: float = 1\.0$" % knob, potential, re.M
        ), "%s must be declared float with the inert 1.0 default" % knob


def test_charge_helper_treats_missing_velocity_as_charging():
    potential = POTENTIAL_FIELD.read_text(encoding="utf-8")
    body = _func(potential, "_is_calm_enemy")
    # DEFENSIVE: a state builder without velocity must read as CHARGING, never
    # as calm, or an absent signal makes the agent bolder than shipped.
    assert 'if not (e.has("vx") and e.has("vy")):' in body
    assert "return false" in body
    # Divide-by-zero guard on the enemy's own speed stat.
    assert "if esp <= 0.0:" in body
    assert "BotConfig.CHARGE_RATIO_THRESH" in body


def test_enemy_engagement_force_left_byte_identical():
    """The desire-level path must NOT be refactored onto the helper."""
    potential = POTENTIAL_FIELD.read_text(encoding="utf-8")
    body = _func(potential, "_enemy_engagement_force")
    assert "_is_calm_enemy" not in body
    assert "if calm_threat_mult != 1.0:" in body
    assert 'e.has("vx") and e.has("vy")' in body


def test_penalty_knob_guarded_in_both_penalty_functions():
    potential = POTENTIAL_FIELD.read_text(encoding="utf-8")
    for name in ("_finale_enemy_path_penalty", "_predictive_enemy_path_penalty"):
        body = _func(potential, name)
        # Nothing is computed at all unless the dose is actually non-inert.
        assert "var scale_calm := tail_calm_penalty_mult != 1.0" in body, name
        assert body.index("scale_calm") < body.index("_is_calm_enemy"), name
        assert "avoid_i" in body and "critical_i" in body, name


def test_predictive_enemy_penalty_tags_enemies_so_bosses_stay_unscaled():
    potential = POTENTIAL_FIELD.read_text(encoding="utf-8")
    body = _func(potential, "_predictive_enemy_path_penalty")
    assert "threat_is_enemy.append(true)" in body
    assert "threat_is_enemy.append(false)" in body
    assert "bool(threat_is_enemy[tix])" in body


def test_clearance_knob_credit_is_zero_at_the_default():
    potential = POTENTIAL_FIELD.read_text(encoding="utf-8")
    body = _func(potential, "_predictive_body_path_clearance")
    assert "var credit_calm := tail_calm_clearance_mult != 1.0" in body
    # credit = (1.0 - mult) * BOSS_FINALE_BODY_CRITICAL_CLEARANCE -> 0.0 at 1.0.
    assert "(1.0 - tail_calm_clearance_mult)" in body
    assert "BotConfig.BOSS_FINALE_BODY_CRITICAL_CLEARANCE" in body
    # Bosses are never credited.
    assert "threat_is_enemy.append(true)" in body
    assert "threat_is_enemy.append(false)" in body
    assert "bool(threat_is_enemy[tix])" in body
    # The credit lands on BOTH min() terms for that threat.
    assert body.count("- threat_radius + credit)") == 2


def test_tail_debug_exposed_and_attached_under_debug_tail():
    potential = POTENTIAL_FIELD.read_text(encoding="utf-8")
    assert "func tail_debug() -> Dictionary:" in potential
    body = _func(potential, "tail_debug")
    # seq is ESSENTIAL: _best_finale_interior_lane is not called every tick, so
    # without it a stale decomposition is indistinguishable from a fresh one.
    for key in (
        '"seq"',
        '"selected"',
        '"alt"',
        '"sampled"',
        # pool is the denominator for the two pass counters; sampled (24) is not.
        '"pool"',
        '"body_floor_passed"',
        '"enemy_filter_passed"',
        '"body_floor"',
        '"highest_body_clearance"',
        '"body_floor_regime"',
        '"lowest_enemy_penalty"',
        '"penalty_min"',
        '"penalty_median"',
        '"penalty_max"',
    ):
        assert key in body, key
    # Deliberately ABSENT: _best_finale_interior_lane is only reached with the
    # latch already set, so a wall_recovery_active here would be constant true.
    # finale_translation_debug already carries the real latch.
    assert '"wall_recovery_active"' not in body

    controller = CONTROLLER.read_text(encoding="utf-8")
    assert 'if _field.has_method("tail_debug"):' in controller
    assert "tail_debug = _field.tail_debug()" in controller
    # teacher.contributions is free-form, so this rides the same debug bag as
    # desire/loot_dash and costs no capture-schema or hash change.
    assert '"tail": tail_debug,' in controller
    assert '"desire": desire_debug,' in controller


def test_lane_score_records_all_seven_terms_behind_the_record_flag():
    potential = POTENTIAL_FIELD.read_text(encoding="utf-8")
    body = _func(potential, "_finale_lane_score")
    assert "record := false) -> float:" in body
    assert "if record:" in body
    for term in (
        "term_wall",
        "term_boss",
        "term_projectile",
        "term_center",
        "term_desire",
        "term_continuity",
        "term_enemy",
    ):
        assert term in body, term
    assert "_lane_record = [" in body
    # The recording must not change the return value.
    assert body.rstrip().endswith("return score")


def test_interior_lane_advances_seq_and_clears_stale_state():
    potential = POTENTIAL_FIELD.read_text(encoding="utf-8")
    body = _func(potential, "_best_finale_interior_lane")
    assert "_tail_seq += 1" in body
    assert "_tail_selected = []" in body
    assert "_tail_alt = []" in body
    # Winner and runner-up are both re-scored with recording on.
    assert "_tail_selected = _lane_record" in body
    assert "_tail_alt = _lane_record" in body
    for regime in ('"relief"', '"critical"', '"degraded"'):
        assert regime in body, regime


def test_declared_on_the_controller_and_recorded_in_both_summary_dicts():
    controller = CONTROLLER.read_text(encoding="utf-8")
    telemetry = TELEMETRY.read_text(encoding="utf-8")
    for knob in KNOBS:
        assert re.search(r"^var %s: float = 1\.0$" % knob, controller, re.M), knob
        assert controller.count('"%s": %s,' % (knob, knob)) == 2, knob
        assert "_field.%s = %s" % (knob, knob) in controller, knob
        assert '%s = float(cfg["%s"])' % (knob, knob) in controller, knob
        # ALLOWLIST: a missing key here is silently dropped, which would make
        # arm validation pass on every trial regardless of the actual dose.
        assert 'meta.get("%s", 1.0)' % knob in telemetry, knob


def test_harness_plumbs_both_doses_and_treats_absence_as_failure():
    loop = LOOP.read_text(encoding="utf-8")
    for knob in KNOBS:
        assert '"--%s"' % knob.replace("_", "-") in loop, knob
        # Written EVERY time, never setdefault: a stale dose must not leak.
        assert 'payload["%s"] = float(%s)' % (knob, knob) in loop, knob
        assert '"%s": float(args.%s),' % (knob, knob) in loop, knob
        # ABSENCE IS A FAILURE, NOT A DEFAULT.
        assert 'if "%s" not in summary:' % knob in loop, knob
        assert 'return "%s_absent:stale_build"' % knob in loop, knob
        assert "expected_%s" % knob in loop, knob
