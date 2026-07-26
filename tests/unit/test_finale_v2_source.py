"""Source-text pins for the finale controller v2 (reports/wp2/finale_v2_design.md).

The mod GDScript is never parsed by this suite, so source-text assertions are the
only guard available. Each assertion states the mechanism it protects.
"""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "mod/mods-unpacked/Tom-BrotatoAgent/teacher/config.gd"
POTENTIAL_FIELD = ROOT / "mod/mods-unpacked/Tom-BrotatoAgent/teacher/potential_field.gd"
CONTROLLER = ROOT / "mod/mods-unpacked/Tom-BrotatoAgent/runtime/agent_controller.gd"


def _heading_func(potential: str) -> str:
    return potential.split("func _finale_v2_heading", 1)[1].split("\nfunc ", 1)[0]


def test_finale_v2_constants_exist_with_the_designed_values():
    config = CONFIG.read_text(encoding="utf-8")

    # The four v2 parameters replace the tuned BOSS_FINALE_* stack on wave 20.
    assert "const FINALE_V2_HEADINGS := 32" in config
    assert "const FINALE_V2_HORIZON := 0.60" in config
    assert "const FINALE_V2_HYSTERESIS := 12.0" in config
    assert "const FINALE_V2_WALL_PENALTY := 1000.0" in config


def test_finale_v2_does_not_resurrect_the_vetoed_range_ring_names():
    config = CONFIG.read_text(encoding="utf-8")

    # v97 removed the boss-range ring; these names are negative-pinned in
    # test_shop_policy_source.py and must stay absent.
    assert "BOSS_FINALE_RANGE_FRAC" not in config
    assert "BOSS_FINALE_SPRING_K" not in config
    assert "BOSS_FINALE_RECOVERY_RANGE_FRAC" not in config
    assert "BOSS_FINALE_RECOVERY_RING_DEADBAND" not in config


def test_finale_v2_flag_defaults_off_and_the_controller_exists():
    potential = POTENTIAL_FIELD.read_text(encoding="utf-8")

    # Default OFF is what makes the flag-off path byte-identical to v1.
    assert "var finale_v2_enabled: bool = false" in potential
    assert "func _finale_v2_heading" in potential
    # The v2 branch is taken inside the existing finale branch.
    assert "if finale_v2_enabled:" in potential


def test_finale_v2_selects_a_heading_by_closed_form_time_to_collision():
    potential = POTENTIAL_FIELD.read_text(encoding="utf-8")
    heading = _heading_func(potential)

    # v116: discrete time sampling was the systemic root cause of the v84-103
    # collapse. This controller must never take a list of sample times.
    assert "times" not in heading
    # The quadratic |rel_pos + rel_vel*t| = R, smallest non-negative root.
    assert "var c := rel_pos.length_squared() - threat_radius * threat_radius" in heading
    assert "var a := rel_vel.length_squared()" in heading
    assert "var b := 2.0 * rel_pos.dot(rel_vel)" in heading
    assert "var disc := b * b - 4.0 * a * c" in heading
    # Already overlapping -> time zero; no real root or degenerate a -> no hit.
    assert "if c <= 0.0:" in heading
    assert "if disc < 0.0:" in heading
    # Survival score saturates at the horizon; wall penalty dominates it.
    assert "var score := min(t_hit, horizon)" in heading
    assert "score -= BotConfig.FINALE_V2_WALL_PENALTY" in heading
    assert "BotConfig.BOSS_FINALE_WALL_HARD_MARGIN" in heading
    # Hysteresis only breaks ties; it must not outrank survival time.
    assert "score += BotConfig.FINALE_V2_HYSTERESIS * align * 0.001" in heading
    # Strictly greater keeps ties on the lowest k, so selection is deterministic.
    assert "if score > best_score:" in heading


def test_finale_v2_keeps_the_corner_guard_and_the_full_safety_tail():
    potential = POTENTIAL_FIELD.read_text(encoding="utf-8")
    v2_branch = potential.split("if finale_v2_enabled:", 1)[1].split(
        "# v97: survival and central map control", 1
    )[0]

    # The safety tail is shared late-wave code and the audit replay surface;
    # bypassing it would make every finale audit vacuous at 0 violations.
    assert "_late_corner_escape(pos, arena)" in v2_branch
    projectile = v2_branch.index("v2_move = _finale_projectile_safety(")
    wall = v2_branch.index("v2_move = _finale_wall_safety(")
    body = v2_branch.index("v2_move = _finale_body_safety(")
    persist = v2_branch.index("_prev_move = v2_move")
    assert projectile < wall < body < persist

    # The three tail calls still exist for the v1 path too.
    assert "final_move = _finale_projectile_safety(" in potential
    assert "final_move = _finale_wall_safety(" in potential
    assert "final_move = _finale_body_safety(" in potential

    # v118: the dash suppression stays a single call shared by both paths.
    movement = potential.split("func compute_movement", 1)[1].split(
        "func _best_loot_cluster", 1
    )[0]
    assert movement.count('_suppress_loot_dash("suppressed_finale")') == 1


def test_controller_reads_and_propagates_the_finale_v2_flag():
    controller = CONTROLLER.read_text(encoding="utf-8")

    assert "var finale_v2: bool = false" in controller
    # Read from user://brotato_agent/agent_config.json, same shape as resume_from_save.
    assert 'if cfg.has("finale_v2"):' in controller
    assert 'finale_v2 = bool(cfg["finale_v2"])' in controller
    # _ready() must push the flag into the field instance after config load.
    assert "_field.finale_v2_enabled = finale_v2" in controller
    ready = controller.split("func _ready", 1)[1].split("\nfunc ", 1)[0]
    assert ready.index("_load_auto_config()") < ready.index(
        "_field.finale_v2_enabled = finale_v2"
    )


def test_finale_v2_recomputes_at_60hz():
    controller = CONTROLLER.read_text(encoding="utf-8")
    combat = controller.split("func _handle_combat", 1)[1].split(
        "func _record_density_sample", 1
    )[0]

    # v2 drops the 20 Hz recompute throttle but leaves the v1 divisor in place.
    throttle = combat.split("_finale_move_tick += 1", 1)[1].split("\n\tif ", 1)[0]
    assert "if finale_v2:" in throttle
    assert "\t\t\trecompute_move = true" in throttle
    assert throttle.index("if finale_v2:") < throttle.index("recompute_move = true")
    assert throttle.index("recompute_move = true") < throttle.index("\t\telse:")
    # The v1 divisor path survives untouched behind the else.
    assert "_finale_move_tick % _CONFIG_SCRIPT.BOSS_FINALE_RECOMPUTE_DIVISOR" in throttle


def test_finale_v2_captures_stay_on_the_20hz_schedule():
    controller = CONTROLLER.read_text(encoding="utf-8")
    combat = controller.split("func _handle_combat", 1)[1].split(
        "func _record_density_sample", 1
    )[0]

    # THE load-bearing guard. The v117 alignment override sets emit_capture to
    # recompute_move on finale waves. At 60 Hz recompute that would triple
    # wave-20 capture volume and move control_dt_ms from ~50 ms to ~16 ms under
    # a dataset and student path fixed at 20 Hz. It must be gated on not finale_v2.
    assert "var emit_capture := _combat_tick_counter % _WP2_CAPTURE_DIVISOR == 0" in combat
    lines = combat.split("\n")
    override_idx = [
        i for i, line in enumerate(lines)
        if line.strip() == "emit_capture = recompute_move"
    ]
    assert len(override_idx) == 1
    guard_line = lines[override_idx[0] - 1].strip()
    # Written so removing "and not finale_v2" fails: the immediately enclosing
    # guard must carry the exclusion, not merely appear somewhere in the function.
    assert guard_line.startswith("if wave >= _CONFIG_SCRIPT.BOSS_FINALE_WAVE")
    assert "and not finale_v2" in guard_line
    # The rate-only arm also recomputes every tick and must be excluded too.
    assert guard_line.endswith("and not finale_rate_full:")


def test_overlapping_threat_does_not_flatten_every_heading():
    """An already-overlapping threat must not score every heading as doomed.

    rel_pos points from threat to player, so rel_pos.dot(rel_vel) > 0 means the
    gap is opening and that heading is escaping, not colliding. Without this
    branch t_hit is 0.0 for every candidate whenever the player is in contact
    with any enemy -- most of a finale swarm -- and heading selection stops
    discriminating at exactly the moment it matters most.
    """
    fn = _heading_func(POTENTIAL_FIELD.read_text(encoding="utf-8"))
    assert "if rel_pos.dot(rel_vel) > 0.0:" in fn, (
        "the escaping-overlap branch is missing; every heading would score 0 on contact"
    )
    # The escape check must come BEFORE the t_hit = 0.0 assignment it guards.
    assert fn.index("if rel_pos.dot(rel_vel) > 0.0:") < fn.index("t_hit = 0.0")
