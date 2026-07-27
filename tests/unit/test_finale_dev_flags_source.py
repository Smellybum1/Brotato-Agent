"""Source-text pins for the wave-20 dev flags: finale_no_panic, finale_heal_seek,
finale_range_keep, and the range-keeping instrument.

The mod GDScript is never parsed by this suite, so source-text assertions are the
only guard available. Each assertion states the mechanism it protects.
"""

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "mod/mods-unpacked/Tom-BrotatoAgent/teacher/config.gd"
POTENTIAL_FIELD = ROOT / "mod/mods-unpacked/Tom-BrotatoAgent/teacher/potential_field.gd"
CONTROLLER = ROOT / "mod/mods-unpacked/Tom-BrotatoAgent/runtime/agent_controller.gd"
TELEMETRY = ROOT / "mod/mods-unpacked/Tom-BrotatoAgent/telemetry/telemetry_writer.gd"

FLAGS = ("finale_no_panic", "finale_heal_seek", "finale_range_keep")


def _finale_branch(potential: str) -> str:
    """The v1 wave-20 branch: from the v97 comment to the non-finale else."""
    movement = potential.split("func compute_movement", 1)[1]
    start = movement.index("# v97: survival and central map control")
    end = movement.index("\n\telse:\n\t\tdesire = _build_desire", start)
    return movement[start:end]


def _func(potential: str, name: str) -> str:
    return potential.split("func %s" % name, 1)[1].split("\nfunc ", 1)[0]


# --------------------------------------------------------------------------
# flags declared / read / propagated / recorded
# --------------------------------------------------------------------------


def test_flags_declared_on_the_field_and_default_off():
    potential = POTENTIAL_FIELD.read_text(encoding="utf-8")
    # Default OFF is what makes the flag-off path byte-identical.
    for flag in FLAGS:
        assert "var %s_enabled: bool = false" % flag in potential


def test_controller_declares_reads_and_propagates_every_flag():
    controller = CONTROLLER.read_text(encoding="utf-8")
    ready = controller.split("func _ready", 1)[1].split("\nfunc ", 1)[0]
    for flag in FLAGS:
        assert "var %s: bool = false" % flag in controller
        assert 'if cfg.has("%s"):' % flag in controller
        assert '%s = bool(cfg["%s"])' % (flag, flag) in controller
        assert "_field.%s_enabled = %s" % (flag, flag) in controller
        # Config must be loaded before the flag is pushed into the field.
        assert ready.index("_load_auto_config()") < ready.index(
            "_field.%s_enabled = %s" % (flag, flag)
        )


def test_flags_recorded_in_run_meta_and_the_mod_ready_sentinel():
    controller = CONTROLLER.read_text(encoding="utf-8")
    sentinel = _func(controller, "_write_mod_ready")
    start_run = _func(controller, "_start_run")
    for flag in FLAGS:
        # Sentinel: lets a caller assert the arm BEFORE spending a trial.
        assert '"%s": %s,' % (flag, flag) in sentinel
        # Meta: the arm that actually ran must land in summary.json.
        assert '"%s": %s,' % (flag, flag) in start_run


def test_telemetry_allowlist_carries_every_flag():
    telemetry = TELEMETRY.read_text(encoding="utf-8")
    # begin_run's summary dict is an allowlist: an unlisted key is silently
    # dropped and the trial is recorded under the wrong arm.
    for flag in FLAGS:
        assert '"%s": meta.get("%s", false),' % (flag, flag) in telemetry


# --------------------------------------------------------------------------
# change 1 -- finale_no_panic
# --------------------------------------------------------------------------


def test_no_panic_flag_gates_the_panic_block_and_leaves_it_intact():
    branch = _finale_branch(POTENTIAL_FIELD.read_text(encoding="utf-8"))

    # The pure-repulsion desire is what remains when the block is skipped.
    assert "desire = _pure_repulsion_flee(" in branch
    assert "if not finale_no_panic_enabled:" in branch
    gate = branch.index("if not finale_no_panic_enabled:")
    hp_gate = branch.index("if (hp_ratio <= BotConfig.LATE_SURVIVAL_HP_RATIO")
    # The HP gate must be INSIDE the flag gate, otherwise the flag does nothing.
    assert gate < hp_gate
    # ... and the whole panic block, unchanged, is what it guards.
    assert "var finale_survival = _panic_dodge(" in branch
    assert "desire = finale_survival" in branch
    assert branch.index("desire = finale_survival") > hp_gate


def test_waves_17_to_19_late_survival_branch_is_untouched_by_the_flags():
    potential = POTENTIAL_FIELD.read_text(encoding="utf-8")
    movement = potential.split("func compute_movement", 1)[1]
    late = movement[
        movement.index("if (wave >= BotConfig.LATE_SURVIVAL_WAVE"):
        movement.index("var finale = wave >= BotConfig.BOSS_FINALE_WAVE")
    ]
    for flag in FLAGS:
        assert "%s_enabled" % flag not in late


# --------------------------------------------------------------------------
# change 3 -- finale_heal_seek
# --------------------------------------------------------------------------


def test_heal_seek_constants_exist_with_the_operator_defaults():
    config = CONFIG.read_text(encoding="utf-8")
    assert "const BOSS_FINALE_HEAL_SEEK_HP_RATIO := 0.50" in config
    # 1.00 == full commitment: the blend reduces to desire = heal_dir.
    assert "const BOSS_FINALE_HEAL_SEEK_WEIGHT := 1.00" in config
    assert "const BOSS_FINALE_HEAL_SEEK_MAX_DIST := 700.0" in config


def test_heal_seek_function_filters_boxes_and_picks_the_nearest():
    fn = _func(POTENTIAL_FIELD.read_text(encoding="utf-8"), "_finale_heal_seek")

    # Not _consumable_attraction: that one is gated by farming heuristics.
    assert "_loot_greed_mult" not in fn
    assert "BotConfig.EARLY_LOOT_WAVE" not in fn
    assert "_count_nearby_enemies" not in fn
    assert "_nearest_threat_dist" not in fn
    assert "if consumables.empty():" in fn
    assert "BotConfig.BOSS_FINALE_HEAL_SEEK_HP_RATIO" in fn
    assert "if _is_valuable_pickup(cid):" in fn
    assert 'find("item_box") >= 0' in fn
    # Nearest, then the distance cap, then a UNIT direction.
    assert "if best_dist < 0.0 or dist < best_dist:" in fn
    assert "BotConfig.BOSS_FINALE_HEAL_SEEK_MAX_DIST" in fn
    assert "return _normalize(best_diff)" in fn


def test_heal_seek_blend_is_applied_in_the_finale_branch():
    branch = _finale_branch(POTENTIAL_FIELD.read_text(encoding="utf-8"))
    assert "if finale_heal_seek_enabled:" in branch
    assert "var heal_dir = _finale_heal_seek(pos, consumables, player)" in branch
    assert "if heal_dir != Vector2.ZERO:" in branch
    # Kept as a blend expression, NOT special-cased at 1.0, so the constant
    # stays a single dial the operator can turn down without a code change.
    assert "(1.0 - BotConfig.BOSS_FINALE_HEAL_SEEK_WEIGHT)" in branch
    assert "+ heal_dir * BotConfig.BOSS_FINALE_HEAL_SEEK_WEIGHT)" in branch


# --------------------------------------------------------------------------
# change 4 -- finale_range_keep
# --------------------------------------------------------------------------


def test_range_keep_constants_exist_and_are_in_range():
    config = CONFIG.read_text(encoding="utf-8")
    # These are OPERATOR DIALS, retuned during supervised sessions. Pin that they
    # exist and are within a sane range -- pinning an exact value only forces a
    # test edit every time the dial moves, without protecting any mechanism.
    for name, lo, hi in (
        ("BOSS_FINALE_RANGE_KEEP_FRACTION", 0.0, 2.0),
        ("BOSS_FINALE_RANGE_KEEP_WEIGHT", 0.0, 1.0),
    ):
        m = re.search(r"const %s := ([0-9.]+)" % name, config)
        assert m, "%s missing from config.gd" % name
        assert lo <= float(m.group(1)) <= hi, "%s out of range" % name


def test_range_keep_never_pulls_while_already_inside_the_band():
    fn = _func(POTENTIAL_FIELD.read_text(encoding="utf-8"), "_finale_range_keep")

    assert "if bosses.empty():" in fn
    assert "var shortest = _shortest_weapon_range(weapons)" in fn
    assert "if shortest <= 0.0:" in fn
    # THE load-bearing guard: inside the band means ZERO, so the term can never
    # push the agent toward a boss it is already close to, nor away from one.
    assert (
        "if best_dist <= shortest * BotConfig.BOSS_FINALE_RANGE_KEEP_FRACTION:" in fn
    )
    zero_guard = fn.index("BotConfig.BOSS_FINALE_RANGE_KEEP_FRACTION")
    assert fn.index("return Vector2.ZERO", zero_guard) < fn.index(
        "return _normalize(best_diff)"
    )


def test_range_keep_is_applied_after_the_projectile_blend():
    potential = POTENTIAL_FIELD.read_text(encoding="utf-8")
    movement = potential.split("func compute_movement", 1)[1].split(
        "func _best_loot_cluster", 1
    )[0]

    # Range keeping MUST sit after the projectile blend. Applied before it, the
    # term is structurally capped: BOSS_FINALE_PROJ_URGENCY_FLOOR is 0.55, so
    # `desire` contributes at most 45% of the command whenever any escape
    # direction exists -- which against a firing boss is essentially always.
    # Measured: pre-blend it reached 0.414 in-range against a 0.90 target.
    blend = movement.index("combined = _normalize(combined)")
    keep = movement.index("if finale and finale_range_keep_enabled:")
    reversal = movement.index("_finale_turn_without_reversal(")
    assert blend < keep < reversal
    assert "var range_dir = _finale_range_keep(pos, bosses, weapons)" in movement
    assert "(1.0 - BotConfig.BOSS_FINALE_RANGE_KEEP_WEIGHT)" in movement

    # KNOWN CONSEQUENCE, pinned so it cannot drift unnoticed: heal-seek is still
    # applied in the desire stage, so it is now diluted by the same urgency floor
    # and range keeping effectively outranks it. The operator's stated intent is
    # the reverse (heal must win at low HP). Restoring that requires moving
    # heal-seek post-blend too, AFTER range keeping.
    heal = movement.index("if finale_heal_seek_enabled:")
    assert heal < blend, "heal-seek is pre-blend; see comment above"


def test_range_keep_instrument_counters_exist_reset_and_are_emitted():
    controller = CONTROLLER.read_text(encoding="utf-8")
    counters = (
        "finale_boss_ticks",
        "finale_boss_in_short_range_ticks",
        "finale_boss_in_long_range_ticks",
    )
    start_run = _func(controller, "_start_run")
    for name in counters:
        assert "var %s: int = 0" % name in controller
        # Reset per run, else a second run in one process inherits the first.
        assert "\t%s = 0" % name in start_run
        # end_run's extra dict at BOTH call sites; begin_run's dict is an
        # allowlist so it cannot carry them by itself.
        assert controller.count('"%s": %s,' % (name, name)) >= 2

    telemetry = TELEMETRY.read_text(encoding="utf-8")
    for name in counters:
        assert '"%s": 0,' % name in telemetry


def test_range_instrument_is_sampled_on_wave20_ticks_from_the_same_state():
    controller = CONTROLLER.read_text(encoding="utf-8")
    combat = controller.split("func _handle_combat", 1)[1].split("\nfunc ", 1)[0]
    # Sampled inside the wave >= BOSS_FINALE_WAVE block, next to the rate
    # counters, and unconditionally: it must not depend on the flag.
    assert "_record_finale_range_sample(state)" in combat
    assert combat.index("finale_combat_ticks += 1") < combat.index(
        "_record_finale_range_sample(state)"
    )
    assert "finale_range_keep" not in combat

    fn = _func(controller, "_record_finale_range_sample")
    # One source of truth: the distance comes from the state already gathered.
    assert 'state.get("bosses", [])' in fn
    assert 'state.get("player", {})' in fn
    assert 'state.get("weapons", [])' in fn
    assert "finale_boss_ticks += 1" in fn
    assert "if shortest > 0.0 and nearest <= shortest:" in fn
    assert "if longest > 0.0 and nearest <= longest:" in fn


# --------------------------------------------------------------------------
# the safety tail
# --------------------------------------------------------------------------


def test_ordered_safety_tail_still_runs_after_the_new_terms():
    potential = POTENTIAL_FIELD.read_text(encoding="utf-8")
    movement = potential.split("func compute_movement", 1)[1].split(
        "func _best_loot_cluster", 1
    )[0]

    # The tail is the ONLY hard constraint on a heal-seek / range-keep approach:
    # the agent must remain uncommandable into a wall, projectile or contact.
    projectile = movement.index("final_move = _finale_projectile_safety(")
    wall = movement.index("final_move = _finale_wall_safety(")
    body = movement.index("final_move = _finale_body_safety(")
    assert projectile < wall < body
    assert movement.index("if finale_heal_seek_enabled:") < projectile
    assert movement.index("if finale and finale_range_keep_enabled:") < projectile


def test_added_lines_are_pure_ascii():
    # A stray non-ASCII byte in new GDScript is a parse risk and the suite never
    # parses the mod. (The files already contain older non-ASCII comments, so
    # this pins only the identifiers/blocks added for these flags.)
    potential = POTENTIAL_FIELD.read_text(encoding="utf-8")
    controller = CONTROLLER.read_text(encoding="utf-8")
    blocks = [
        _func(potential, "_finale_heal_seek"),
        _func(potential, "_finale_range_keep"),
        _func(controller, "_record_finale_range_sample"),
        _finale_branch(potential),
    ]
    for block in blocks:
        assert block.isascii(), repr([c for c in block if not c.isascii()])
