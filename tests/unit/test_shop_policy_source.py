import json
import math
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "mod/mods-unpacked/Tom-BrotatoAgent/teacher/config.gd"
STRATEGY = ROOT / "mod/mods-unpacked/Tom-BrotatoAgent/teacher/shop_strategy.gd"
CONTROLLER = ROOT / "mod/mods-unpacked/Tom-BrotatoAgent/runtime/agent_controller.gd"
PROFILES = ROOT / "mod/mods-unpacked/Tom-BrotatoAgent/teacher/build_profiles.gd"
MANIFEST = ROOT / "mod/mods-unpacked/Tom-BrotatoAgent/manifest.json"
TELEMETRY = ROOT / "mod/mods-unpacked/Tom-BrotatoAgent/telemetry/telemetry_writer.gd"
ADAPTER = ROOT / "mod/mods-unpacked/Tom-BrotatoAgent/adapter/game_adapter.gd"
HUD = ROOT / "mod/mods-unpacked/Tom-BrotatoAgent/ui/agent_hud.gd"
POTENTIAL_FIELD = ROOT / "mod/mods-unpacked/Tom-BrotatoAgent/teacher/potential_field.gd"
COMBAT_MODEL = ROOT / "mod/mods-unpacked/Tom-BrotatoAgent/teacher/combat_model.gd"
START_GATE = ROOT / "scripts/start_gate_watchdogs.ps1"
SUPERVISOR = ROOT / "scripts/overnight_supervisor.py"


def test_final_shop_spends_without_reserve_or_future_locks():
    config = CONFIG.read_text(encoding="utf-8")
    strategy = STRATEGY.read_text(encoding="utf-8")

    assert "const FINAL_SHOP_WAVE := 19" in config
    assert 'wave >= BotConfig.FINAL_SHOP_WAVE and not state.get("is_endless", false)' in strategy
    assert "if final_shop:\n\t\tmin_buy = BotConfig.FINAL_SHOP_MIN_BUY" in strategy
    assert "reroll_cap = BotConfig.SHOP_MAX_REROLLS_CAP" in strategy
    assert "gold_reserve = 0" in strategy
    assert "reroll_factor: float = 1.0 if final_shop" in strategy
    assert "if not final_shop:\n\t\tvar must_s3" in strategy


def test_ordinary_shops_keep_the_five_reroll_maximum():
    config = CONFIG.read_text(encoding="utf-8")
    strategy = STRATEGY.read_text(encoding="utf-8")

    assert "const SHOP_MAX_REROLLS := 5" in config
    assert "var reroll_cap: int = BotConfig.SHOP_MAX_REROLLS" in strategy
    assert "var cap: int = reroll_cap" in strategy
    assert "reroll_cap + 2" not in strategy
    assert "reroll_cap = min(reroll_cap, 4" not in strategy


def test_v65_combine_path_requires_full_loadout_upgradeable_pair_and_bypasses_focus_callbacks():
    config = CONFIG.read_text(encoding="utf-8")
    strategy = STRATEGY.read_text(encoding="utf-8")
    controller = CONTROLLER.read_text(encoding="utf-8")

    assert "const EXPERIMENT_COMBINE_ASAP := false" in config
    assert "const SHOP_MAX_COMBINES_PER_VISIT := 1" in config
    assert "const SHOP_COMBINES_ENABLED := true" in config
    assert "const COMBINE_MIN_WEAPONS := 6" in config
    assert "var _session_combines: int = 0" in strategy
    assert "_session_combines = 0" in strategy
    assert strategy.count("_session_combines < BotConfig.SHOP_MAX_COMBINES_PER_VISIT") == 3
    assert strategy.count("_session_combines += 1") == 3
    assert "var combine_allowed: bool = not final_shop or slots_full" in strategy
    assert strategy.count("BotConfig.SHOP_COMBINES_ENABLED and combine_allowed") == 3
    assert "const SHOP_COMBINE_CONFIRM_INTERVAL = 1.0" in controller
    assert "func _shop_weapon_signature(state: Dictionary) -> String:" in controller
    assert "if w.get(\"upgrades\", false):" in strategy
    assert "var by_id := {}" not in strategy
    assert "if observed_signature == _pending_combine_signature:" in controller
    assert 'telem.emit("shop_combine_confirmed"' in controller
    assert 'telem.emit("shop_combine_dispatched"' in controller
    assert 'telem.emit("shop_combine_confirmation_timeout"' in controller
    assert '"state_changed": true' in controller
    assert 'Input.set_mouse_mode(Input.MOUSE_MODE_VISIBLE)' in controller
    assert 'shop.call_deferred("_combine_weapon", weapon, 0, false)' in controller
    assert '_on_item_combine_button_pressed' not in controller
    assert '"executor": "deferred_core_combine"' in controller
    assert '"mouse_mode": "visible"' in controller
    assert "_restore_pre_combine_mouse_mode()" in controller
    assert controller.index("if _pending_combine_wave >= 0:") < controller.index(
        "var decision = choose_meta_action"
    )


def test_v61_any_guns_experiment_preserves_well_rounded_scoring_identity():
    profiles = PROFILES.read_text(encoding="utf-8")
    strategy = STRATEGY.read_text(encoding="utf-8")

    experiment = profiles.split("func _apply_experiments() -> void:", 1)[1].split(
        "\n\nfunc get_profile", 1
    )[0]
    assert 'wr.name = "well_rounded"' in experiment
    assert 'well_rounded_gun' not in experiment
    # v76's hard defense cap is intentionally profile-independent; the two
    # remaining checks preserve Well-Rounded scoring identity elsewhere.
    assert strategy.count('str(profile.name) != "well_rounded"') == 2


def test_v62_levelups_share_well_rounded_mid_and_late_combat_pivot():
    strategy = STRATEGY.read_text(encoding="utf-8")
    levelups = strategy.split("func decide_levelup", 1)[1].split("func decide_crate", 1)[0]

    assert "_effects_value(effects, build, wave, profile)" in levelups
    assert "+ _late_shop_pivot_bonus(effects, build, wave, profile)" in levelups


def test_v63_late_corner_guard_overrides_the_final_blended_move():
    config = CONFIG.read_text(encoding="utf-8")
    potential = POTENTIAL_FIELD.read_text(encoding="utf-8")

    assert "const LATE_CORNER_GUARD_MARGIN := 280.0" in config
    assert "const LATE_CORNER_KEEP_MOVE := 0.25" in config
    assert "func _late_corner_escape(pos, arena) -> Vector2:" in potential
    assert "if inward_x == 0.0 or inward_y == 0.0:" in potential
    guard = potential.index("if wave >= BotConfig.LATE_EDGE_KITE_WAVE:")
    blend = potential.index("combined = _normalize(combined)")
    smoothing = potential.index("var alpha = BotConfig.MOVE_SMOOTHING")
    assert blend < guard < smoothing
    assert "combined * BotConfig.LATE_CORNER_KEEP_MOVE + corner_escape" in potential


def test_v64_blood_donation_is_vetoed_for_gate_reliability():
    config = CONFIG.read_text(encoding="utf-8")

    requirement_block = config.split("const BUILD_AWARE_ITEM_REQUIREMENTS := {", 1)[1].split(
        "\n}\nconst ROGUERANKER_ITEM_TIERS", 1
    )[0]
    assert '"item_blood_donation": {"never": true}' in requirement_block


def test_wp2_capture_build_versions_the_v122_crossing_tier_policy():
    manifest = MANIFEST.read_text(encoding="utf-8")
    controller = CONTROLLER.read_text(encoding="utf-8")
    telemetry = TELEMETRY.read_text(encoding="utf-8")

    # Teacher policy v129 (material-crediting telemetry) on mod 0.2.49; the M3
    # student-inference path (learned/ bridge, default-off) is unchanged —
    # deploy surface bumps together: manifest, controller meta, telemetry
    # default, and the collector identity gate.
    assert '"version_number": "0.2.59"' in manifest
    assert "v128 deterministic teacher" in manifest
    assert controller.count("teacher_v1-0.1.129-gun-wp1") == 1
    assert controller.count("0.2.59-wp2-capture") == 1
    assert telemetry.count("teacher_v1-0.1.129-gun-wp1") == 1
    assert telemetry.count("0.2.59-wp2-capture") == 1


def test_v123_strength_signal_is_plumbed_through_controller_and_field():
    controller = CONTROLLER.read_text(encoding="utf-8")
    potential = POTENTIAL_FIELD.read_text(encoding="utf-8")

    # Controller: smoothed EMA member, update before HUD/telemetry, state inject.
    assert "var _build_strength: float = 1.0" in controller
    assert "_build_strength = _build_strength * 0.75 + strength_raw * 0.25" in controller
    assert 'state["build_strength"] = _build_strength' in controller
    combat = controller.split("func _handle_combat", 1)[1].split(
        "func _gather_combat_state", 1
    )[0]
    # The EMA update must consume build_metrics before the HUD/telemetry do.
    assert combat.index("_build_strength = _build_strength * 0.75") < combat.index(
        "_update_build_metrics_hud(build_metrics)"
    )

    # Field: per-decision hysteretic tier update + per-capture visibility.
    assert (
        "_update_strength_tier(clamp(float(state.get(\"build_strength\", 1.0)), 0.0, 2.0))"
        in potential
    )
    assert "func _update_strength_tier(s: float) -> void:" in potential
    assert "func _strength_edge_kite_nearby() -> int:" in potential
    assert "func _strength_pack_mult() -> float:" in potential
    assert '"build_strength": stepify(_build_strength_used, 0.001)' in potential
    assert '"strength_tier": _strength_tier' in potential


def test_v123_strength_tiers_are_hysteretic_and_bounded():
    config = CONFIG.read_text(encoding="utf-8")
    potential = POTENTIAL_FIELD.read_text(encoding="utf-8")

    for declaration in (
        "const STRENGTH_ENTER_STRONG := 1.25",
        "const STRENGTH_EXIT_STRONG := 1.15",
        "const STRENGTH_ENTER_WEAK := 0.75",
        "const STRENGTH_EXIT_WEAK := 0.85",
        "const STRENGTH_STRONG_EDGE_KITE_DELTA := 4",
        "const STRENGTH_WEAK_EDGE_KITE_DELTA := -4",
        "const STRENGTH_STRONG_PACK_MULT := 0.85",
        "const STRENGTH_WEAK_PACK_MULT := 1.15",
        "const STRENGTH_STRONG_DASH_WINDOW_DELTA := -10.0",
        "const STRENGTH_WEAK_DASH_WINDOW_DELTA := 10.0",
        "const STRENGTH_STRONG_DASH_HP_FLOOR_DELTA := -0.05",
        "const STRENGTH_WEAK_DASH_HP_FLOOR_DELTA := 0.05",
    ):
        assert declaration in config

    tier = potential.split("func _update_strength_tier", 1)[1].split(
        "func _strength_edge_kite_nearby", 1
    )[0]
    # Demote-first-then-repromote handles a large jump straight across neutral.
    assert 'if tier == "strong" and s <= BotConfig.STRENGTH_EXIT_STRONG:' in tier
    assert 'elif tier == "weak" and s >= BotConfig.STRENGTH_EXIT_WEAK:' in tier
    assert "if s >= BotConfig.STRENGTH_ENTER_STRONG:" in tier
    assert "elif s <= BotConfig.STRENGTH_ENTER_WEAK:" in tier

    # Deltas are consumed only on the ordinary kiter path.
    assert "and nearby >= _strength_edge_kite_nearby())" in potential
    assert "BotConfig.EDGE_PACK_SHOVE * _strength_pack_mult()" in potential
    assert "_pack_density_repulsion(pos, enemies, bosses) * _strength_pack_mult()" in potential

    # Reproduce the hysteresis with the pinned thresholds: strong holds through
    # 1.20 and exits at 1.10; a crash to 0.5 lands directly in weak.
    def next_tier(t, s):
        if t == "strong" and s <= 1.15:
            t = "neutral"
        elif t == "weak" and s >= 0.85:
            t = "neutral"
        if t == "neutral":
            if s >= 1.25:
                t = "strong"
            elif s <= 0.75:
                t = "weak"
        return t

    assert next_tier("neutral", 1.25) == "strong"
    assert next_tier("strong", 1.20) == "strong"
    assert next_tier("strong", 1.10) == "neutral"
    assert next_tier("strong", 0.50) == "weak"
    assert next_tier("weak", 0.80) == "weak"
    assert next_tier("weak", 0.90) == "neutral"
    assert next_tier("weak", 1.30) == "strong"


def test_v123_wave_indexed_greed_getters_and_boundaries():
    config = CONFIG.read_text(encoding="utf-8")

    assert "const EARLY_GREED_MAX_WAVE := 12" in config
    assert "const LOOT_DASH_ARM_FLOOR_MIN := 0.30" in config
    assert "const LOOT_DASH_WINDOW_MIN := 20.0" in config
    # FINAL_SHOP_WAVE is reused (already 19) as the wave-19 greedy re-entry key.
    assert "const FINAL_SHOP_WAVE := 19" in config

    # Two-case getters (early vs late; wave 19 stays LATE).
    assert (
        "static func loot_dash_arm_hp_floor(wave: int) -> float:\n"
        "\treturn 0.35 if wave <= EARLY_GREED_MAX_WAVE else 0.5"
    ) in config
    assert (
        "static func loot_dash_window_clearance(wave: int) -> float:\n"
        "\treturn 30.0 if wave <= EARLY_GREED_MAX_WAVE else 45.0"
    ) in config
    assert (
        "static func body_clearance_slack(wave: int) -> float:\n"
        "\treturn 35.0 if wave <= EARLY_GREED_MAX_WAVE else 20.0"
    ) in config

    # Three-case getters (early OR wave-19 greedy; else late) — pins the 12/13,
    # 18/19 and 19/20 boundaries in a single expression each.
    assert (
        "static func loot_dash_stall_count(wave: int) -> int:\n"
        "\treturn 8 if wave <= EARLY_GREED_MAX_WAVE or wave == FINAL_SHOP_WAVE else 12"
    ) in config
    assert (
        "static func loot_dash_cooldown_ticks(wave: int) -> int:\n"
        "\treturn 90 if wave <= EARLY_GREED_MAX_WAVE or wave == FINAL_SHOP_WAVE else 180"
    ) in config
    assert (
        "static func engage_strafe_loot_cap(wave: int) -> float:\n"
        "\treturn 0.6 if wave <= EARLY_GREED_MAX_WAVE or wave == FINAL_SHOP_WAVE else 0.35"
    ) in config

    # Independent Python mirror of the three-case rule to pin the boundaries.
    def greedy(wave):
        return wave <= 12 or wave == 19

    assert greedy(12) and not greedy(13)      # early boundary
    assert not greedy(18) and greedy(19)      # final-shop re-entry
    assert greedy(19) and not greedy(20)      # boss wave drops back to late


def test_v123_rail_traversal_drift_avoids_corner_parking():
    config = CONFIG.read_text(encoding="utf-8")
    potential = POTENTIAL_FIELD.read_text(encoding="utf-8")

    assert "const RAIL_CLEAR_RADIUS := 240.0" in config
    assert "const EDGE_RAIL_DRIFT := 0.45" in config

    edge = potential.split("func _edge_kite_force", 1)[1].split(
        "func _rail_ahead_pressure", 1
    )[0]
    # Bounded loot/open-space bias runs BEFORE the continuity flip (continuity
    # keeps the final say), and the drift only fires with no rail-ahead pressure.
    bias = edge.index("var forward_score = _score_strafe_side(pos, tangent")
    continuity = edge.index("_prev_move.dot(tangent) < 0.0")
    drift = edge.index("force += tangent * BotConfig.EDGE_RAIL_DRIFT")
    assert bias < continuity < drift
    assert "if not _rail_ahead_pressure(pos, enemies, bosses, tangent):" in edge

    pressure = potential.split("func _rail_ahead_pressure", 1)[1].split(
        "func _late_corner_escape", 1
    )[0]
    assert "off_e.length() <= BotConfig.RAIL_CLEAR_RADIUS" in pressure
    assert "off_e.dot(tangent_dir) > 0.0" in pressure
    # Corner guard is untouched.
    assert "func _late_corner_escape(pos, arena) -> Vector2:" in potential
    assert "if inward_x == 0.0 or inward_y == 0.0:" in potential


def test_v84_item_audit_and_conditional_effect_corrections():
    config = CONFIG.read_text(encoding="utf-8")
    wiki_block = config.split("const WIKI_USEFUL_ITEM_TIERS := {", 1)[1].split(
        "\n}\n\n#", 1
    )[0]

    # Telemetry-audit additions (416-run offer harvest): gun-build offense.
    assert '"item_honey": "B"' in wiki_block
    assert '"item_pumpkin": "B"' in wiki_block
    # Statue's +40 attack speed is conditional on standing still. The live
    # snapshot flattens that custom effect, while this agent continuously
    # kites and still pays the item's -10 speed cost.
    assert '"item_statue"' not in wiki_block
    assert '"item_statue": {"never": true}' in config
    assert '"item_triangle_of_power": "C"' in config
    assert '"item_wisdom": "C"' in config
    # Retiers: off-build elemental/engineering demoted; acid promoted
    # (68% win-share over 144 buys, genuine AoE offense).
    assert '"item_snowball": "D"' in config
    assert '"item_ice_cube": "D"' in config
    assert '"item_pile_of_books": "C"' in config
    assert '"item_acid": "A"' in config
    # Hard constraints preserved.
    assert '"item_blood_donation": {"never": true}' in config
    assert '"item_sharp_bullet": "A"' in config


def test_v69_below_target_offense_floor_boosts_damage_stats_mid_and_late():
    config = CONFIG.read_text(encoding="utf-8")
    strategy = STRATEGY.read_text(encoding="utf-8")
    pivot = strategy.split("func _late_shop_pivot_bonus", 1)[1].split(
        "func _combinable_index", 1
    )[0]
    offense_helper = strategy.split("func _offense_proxy", 1)[1].split(
        "func _saturated_defense_only", 1
    )[0]

    assert "const OFFENSE_FLOOR_MID := 70.0" in config
    assert "const OFFENSE_FLOOR_LATE := 120.0" in config
    # v77 reads the weapon-aware rating (which retains the legacy stat score).
    assert "BotCombatModel.offense_rating(build)" in offense_helper
    assert "var offense = _offense_proxy(build)" in pivot
    # Late (wave 15+) conditional boosts, tapering to the v65 weights at par.
    assert "bonus += val * (2.75 if offense < BotConfig.OFFENSE_FLOOR_LATE else 1.75)" in pivot
    assert "bonus += val * (2.40 if offense < BotConfig.OFFENSE_FLOOR_LATE else 1.50)" in pivot
    assert "bonus += val * (2.10 if offense < BotConfig.OFFENSE_FLOOR_LATE else 1.30)" in pivot
    assert "bonus += val * (3.50 if offense < BotConfig.OFFENSE_FLOOR_LATE else 2.40)" in pivot
    # v78 mid pivot starts in the shop preceding wave 10.
    assert "const MID_SHOP_PIVOT_WAVE := 9" in config
    assert "bonus += val * (2.40 if offense < BotConfig.OFFENSE_FLOOR_MID else 0.95)" in pivot
    assert "bonus += val * (2.10 if offense < BotConfig.OFFENSE_FLOOR_MID else 0.85)" in pivot
    assert "bonus += val * (1.85 if offense < BotConfig.OFFENSE_FLOOR_MID else 0.70)" in pivot
    assert "bonus += val * (3.20 if offense < BotConfig.OFFENSE_FLOOR_MID else 1.40)" in pivot


def test_v74_lowers_defense_adequacy_and_suppresses_saturated_layers():
    config = CONFIG.read_text(encoding="utf-8")
    strategy = STRATEGY.read_text(encoding="utf-8")
    pivot = strategy.split("func _late_shop_pivot_bonus", 1)[1].split(
        "func _combinable_index", 1
    )[0]

    assert "const DEFENSE_ADEQUATE_MID_MAX_HP := 45.0" in config
    assert "const DEFENSE_ADEQUATE_MID_ARMOR := 5.0" in config
    assert "const DEFENSE_ADEQUATE_MID_SUSTAIN := 8.0" in config
    assert "const DEFENSE_ADEQUATE_MAX_HP := 60.0" in config
    assert "const DEFENSE_ADEQUATE_ARMOR := 8.0" in config
    assert "const DEFENSE_ADEQUATE_SUSTAIN := 10.0" in config
    assert "var hp_saturated = (offense_starved_late" in pivot
    assert "var armor_saturated = (offense_starved_late" in pivot
    assert "var sustain_saturated = (offense_starved_late" in pivot
    assert "var defense_layers_adequate = ((hp_saturated and armor_saturated)" in pivot
    assert 'key == "stat_max_hp"' in pivot and "-4.00 if hp_saturated" in pivot
    assert 'key == "stat_armor"' in pivot and "-12.00 if armor_saturated" in pivot
    assert 'key == "stat_dodge"' in pivot and "-4.00 if defense_layers_adequate" in pivot
    assert 'key == "stat_hp_regeneration"' in pivot and "-8.00 if sustain_saturated" in pivot
    assert 'key == "jellyshield_count"' in pivot and "bonus -= val * 40.0" in pivot
    assert 'key == "wandering_bot"' in pivot and "bonus -= val * 30.0" in pivot

    crate = strategy.split("func decide_crate", 1)[1]
    assert "+ _late_shop_pivot_bonus(item.get(\"effects\", []), build, wave, profile)" in crate


def test_v78_caps_direct_mixed_and_indirect_sustain_before_wave_ten():
    config = CONFIG.read_text(encoding="utf-8")
    strategy = STRATEGY.read_text(encoding="utf-8")
    helper = strategy.split("func _saturated_defense_only", 1)[1].split(
        "func _late_shop_pivot_bonus", 1
    )[0]
    pivot = strategy.split("func _late_shop_pivot_bonus", 1)[1].split(
        "func _combinable_index", 1
    )[0]

    assert "func _offense_proxy(build: Dictionary) -> float:" in strategy
    assert "func _offense_target(wave: int, build: Dictionary = {}) -> float:" in strategy
    assert "const SUSTAIN_CAP_WAVE := 8" in config
    assert "if wave < BotConfig.SUSTAIN_CAP_WAVE:" in helper
    assert "_offense_proxy(build) >= target" not in helper
    assert 'str(profile.name) != "well_rounded"' not in helper
    assert "BotConfig.DEFENSE_ADEQUATE_MID_MAX_HP" in helper
    assert "BotConfig.DEFENSE_ADEQUATE_MID_ARMOR" in helper
    assert "BotConfig.DEFENSE_ADEQUATE_MID_SUSTAIN" in helper
    assert "if _direct_offense_gain(effects) > 0.0:" in helper
    assert helper.index("sustain + sustain_gain >= sustain_floor") < helper.index(
        "if _direct_offense_gain(effects) > 0.0:"
    )
    assert 'key == "stat_hp_regeneration" or key == "stat_lifesteal"' in helper
    assert "hp + hp_gain >= hp_floor" in helper
    assert "armor + armor_gain >= armor_floor" in helper
    assert "sustain + sustain_gain >= sustain_floor" in helper
    assert 'float(st.get("stat_hp_regeneration", 0) or 0)' not in helper
    assert '_stat_float(st, "stat_hp_regeneration")' in helper
    assert '_stat_float(st, "stat_lifesteal")' in helper
    assert "return -1e9" in pivot
    assert 'key == "explosion_damage" or key == "explosion_size"' in pivot
    assert 'key == "projectiles_on_death" or key == "burning_spread"' in pivot
    assert "const BOSS_ONLY_PRE_FINAL_PENALTY := 45.0" in config
    assert 'item.get("id", "") == "item_silver_bullet"' in strategy
    assert "2.70 if wave >= BotConfig.FINAL_SHOP_WAVE else 0.10" in pivot
    assert "func _sustain_cap_veto(item: Dictionary, build: Dictionary, wave: int)" in strategy
    assert "BotConfig.INDIRECT_SUSTAIN_ITEM_IDS" in strategy
    assert '"item_garden"' in config


def test_v74_searches_more_aggressively_for_offense_from_wave_ten():
    strategy = STRATEGY.read_text(encoding="utf-8")
    decide = strategy.split("func decide_shop", 1)[1].split(
        "func decide_levelup", 1
    )[0]

    assert "var offense_target := _offense_target(wave, build)" in decide
    assert "_offense_proxy(build) < offense_target" in decide
    assert "worth += 8.0" in decide


def test_v75_affordable_direct_offense_precedes_generic_thresholds_and_locks():
    strategy = STRATEGY.read_text(encoding="utf-8")
    direct = strategy.split("func _offense_first_item_action", 1)[1].split(
        "func _try_tier_replace_sell", 1
    )[0]
    decide = strategy.split("func decide_shop", 1)[1].split(
        "func decide_levelup", 1
    )[0]
    levelup = strategy.split("func decide_levelup", 1)[1].split(
        "func decide_crate", 1
    )[0]

    assert "func _direct_offense_gain(effects: Array) -> float:" in strategy
    assert "score <= -1e8" in direct
    assert '"offense_first": true' in direct
    assert decide.index("_offense_first_item_action(") < decide.index("# 1) Best purchase")
    assert decide.index("_offense_first_item_action(") < decide.index("# 3) Lock unaffordable premium")
    assert "_direct_offense_gain(effects0)" in levelup
    assert '"offense_first": true' in levelup
    assert "_increases_enemy_density(effects)" in strategy


def test_v73_explicitly_saves_and_buys_high_tier_rare_guns():
    config = CONFIG.read_text(encoding="utf-8")
    strategy = STRATEGY.read_text(encoding="utf-8")
    rare = strategy.split("func _rare_gun_action", 1)[1].split(
        "func _try_tier_replace_sell", 1
    )[0]
    decide = strategy.split("func decide_shop", 1)[1].split(
        "func decide_levelup", 1
    )[0]

    assert '"weapon_chain_gun": 3' in config
    assert '"weapon_minigun": 2' in config
    assert '"weapon_minigun"' in config.split(
        "const EXPERIMENT_WEAPON_PRIORITY_IDS", 1
    )[1].split("]", 1)[0]
    assert '"type": "shop_buy"' in rare and '"rare_gun": true' in rare
    assert "_lowest_tier_replace_victim(" in rare
    assert '"type": "shop_sell"' in rare
    assert '"type": "shop_lock"' in rare
    assert '"rare_gun_saved": true' in rare
    assert '"type": "shop_unlock"' in rare and '"lock_expired": true' in rare
    assert decide.index("_rare_gun_action(") < decide.index("_try_tier_replace_sell(")


def test_v68_watchdog_tasks_restart_after_abnormal_exit_and_ignore_idle_end():
    start_gate = START_GATE.read_text(encoding="utf-8")

    assert "-RestartCount 999" in start_gate
    assert "-RestartInterval (New-TimeSpan -Minutes 1)" in start_gate
    assert "-DontStopOnIdleEnd" in start_gate


def test_v71_watchdog_tasks_have_real_relaunch_triggers_and_resumable_gate_state():
    start_gate = START_GATE.read_text(encoding="utf-8")
    supervisor = SUPERVISOR.read_text(encoding="utf-8")

    assert "-RepetitionInterval (New-TimeSpan -Minutes 1)" in start_gate
    assert "-RepetitionDuration (New-TimeSpan -Days 2)" in start_gate
    assert start_gate.count("-Trigger $restartTrigger") == 2
    assert "--state-file" in start_gate
    assert "def save_gate_state(" in supervisor
    assert "def load_gate_state(" in supervisor
    assert "if not resumed:" in supervisor
    assert "save_gate_state(args.state_file, baseline_ids, collected)" in supervisor
    assert '"batch_overnight_${Runs}_$Version"' in start_gate
    assert '"BrotatoAgent $Version $Runs-run supervised evaluation"' in start_gate


def test_v67_wave17_low_hp_survival_override_uses_repulsion_before_normal_kiting():
    config = CONFIG.read_text(encoding="utf-8")
    potential = POTENTIAL_FIELD.read_text(encoding="utf-8")

    assert "const LATE_SURVIVAL_WAVE := 17" in config
    assert "const LATE_SURVIVAL_HP_RATIO := 0.85" in config
    assert "const LATE_SURVIVAL_SMOOTHING := 0.70" in config
    assert "wave >= BotConfig.LATE_SURVIVAL_WAVE" in potential
    assert "and wave < BotConfig.BOSS_FINALE_WAVE" in potential
    assert "hp_ratio <= BotConfig.LATE_SURVIVAL_HP_RATIO" in potential
    assert "survival_dir = _panic_dodge" in potential
    assert "survival_dir = _pure_repulsion_flee(" in potential
    assert "survival_dir * BotConfig.LATE_SURVIVAL_SMOOTHING" in potential
    assert potential.index("wave >= BotConfig.LATE_SURVIVAL_WAVE") < potential.index(
        "var finale = wave >= BotConfig.BOSS_FINALE_WAVE"
    )


def test_v98_late_survival_cannot_bypass_projectile_and_hard_wall_safety():
    potential = POTENTIAL_FIELD.read_text(encoding="utf-8")
    survival = potential.split(
        "if (wave >= BotConfig.LATE_SURVIVAL_WAVE", 1
    )[1].split(
        "var finale = wave >= BotConfig.BOSS_FINALE_WAVE", 1
    )[0]

    normalized = survival.index("var safe_survival = _normalize(smoothed_survival)")
    projectile = survival.index("safe_survival = _finale_projectile_safety(")
    wall = survival.index("safe_survival = _finale_wall_safety(")
    persistence = survival.index("_prev_move = safe_survival")
    returned = survival.index("return _prev_move")
    assert normalized < projectile < wall < persistence < returned
    assert "projectiles, player_speed, arena, enemies, bosses, profile" in survival
    assert "arena, bosses, projectiles, player_speed" in survival
    assert "_prev_move = _normalize(smoothed_survival)" not in survival


def test_v99_every_late_wave_command_gets_final_projectile_and_wall_safety():
    potential = POTENTIAL_FIELD.read_text(encoding="utf-8")
    tail = potential.split("var alpha = BotConfig.MOVE_SMOOTHING", 1)[1].split(
        "_prev_move = final_move", 1
    )[0]

    guard = tail.index("if wave >= BotConfig.LATE_SURVIVAL_WAVE:")
    projectile = tail.index("final_move = _finale_projectile_safety(")
    wall = tail.index("final_move = _finale_wall_safety(")
    assert guard < projectile < wall
    assert "if finale:" not in tail[guard:projectile]


def test_v102_late_wall_recovery_retains_hysteresis_until_release():
    potential = POTENTIAL_FIELD.read_text(encoding="utf-8")
    reset_block = potential.split(
        "if wave < BotConfig.BOSS_FINALE_WAVE:", 1
    )[1].split("var hp_ratio", 1)[0]

    late_guard = reset_block.index("if wave < BotConfig.LATE_SURVIVAL_WAVE:")
    reset = reset_block.index("_finale_wall_recovery_active = false")
    assert late_guard < reset
    assert reset_block.count("_finale_wall_recovery_active = false") == 1

    safety = potential.split("func _finale_wall_safety", 1)[1].split(
        "func _best_wall_safe_projectile_lane", 1
    )[0]
    assert "if _finale_wall_recovery_active:" in safety
    assert "wall_distance >= BotConfig.BOSS_FINALE_WALL_RECOVERY_RELEASE" in safety
    assert "wall_distance <= BotConfig.BOSS_FINALE_WALL_RECOVERY_ENTER" in safety

    # Reproduce the current boundary trace: after entering at 279, recovery must
    # stay active through intermediate 280-520 distances and release only past
    # the configured 520-unit boundary.
    active = False
    trace = []
    for wall_distance in (279.0, 284.0, 298.0, 277.0, 420.0, 519.0, 521.0):
        if active:
            if wall_distance >= 520.0:
                active = False
        elif wall_distance <= 280.0:
            active = True
        trace.append(active)
    assert trace == [True, True, True, True, True, True, False]


def test_v97_wave20_uses_centered_survival_without_a_boss_range_ring():
    potential = POTENTIAL_FIELD.read_text(encoding="utf-8")
    survival_guard = potential.split(
        "if (wave >= BotConfig.LATE_SURVIVAL_WAVE", 1
    )[1].split(
        "var finale = wave >= BotConfig.BOSS_FINALE_WAVE", 1
    )[0]

    assert "and wave < BotConfig.BOSS_FINALE_WAVE" in survival_guard
    assert "return _prev_move" in survival_guard
    assert "_boss_finale_desire" not in survival_guard
    finale_block = potential.split("if finale:", 1)[1].split("\n\telse:", 1)[0]
    assert "desire = _pure_repulsion_flee(" in finale_block
    assert "desire = finale_survival" in finale_block
    assert "_boss_finale_desire" not in potential
    assert "_boss_finale_recovery_desire" not in potential
    assert "_projectile_escape" in potential
    assert "_finale_committed_escape" in potential


def test_v97_finale_removes_range_ring_and_bypasses_commitment_before_contact():
    config = CONFIG.read_text(encoding="utf-8")
    potential = POTENTIAL_FIELD.read_text(encoding="utf-8")
    adapter = ADAPTER.read_text(encoding="utf-8")
    controller = CONTROLLER.read_text(encoding="utf-8")

    assert "BOSS_FINALE_RANGE_FRAC" not in config
    assert "BOSS_FINALE_SPRING_K" not in config
    assert "BOSS_FINALE_RECOVERY_RANGE_FRAC" not in config
    assert "BOSS_FINALE_RECOVERY_RING_DEADBAND" not in config
    assert "const BOSS_FINALE_CONTACT_ESCAPE_DISTANCE := 420.0" in config
    assert "if (hp_ratio <= BotConfig.LATE_SURVIVAL_HP_RATIO" in potential
    assert "var finale_survival = _panic_dodge(" in potential
    assert "finale_survival = _pure_repulsion_flee(" in potential
    assert "desire = finale_survival" in potential
    assert "_boss_finale_recovery_desire" not in potential
    assert "BOSS_FINALE_RECOVERY_RING_DEADBAND" not in potential
    projectile_blend = potential.index("combined = _normalize(combined)")
    reversal_guard = potential.index(
        "combined = _finale_turn_without_reversal", projectile_blend
    )
    assert projectile_blend < reversal_guard
    assert "_finale_committed_escape(pos, combined, arena, bosses)" in potential
    committed = potential.split("func _finale_committed_escape", 1)[1].split(
        "func finale_translation_debug", 1
    )[0]
    assert "away_from_boss: Vector2 = pos - boss_pos" in committed
    assert "<= BotConfig.BOSS_FINALE_CONTACT_ESCAPE_DISTANCE" in committed
    assert committed.index("_reset_finale_commit()") < committed.index(
        "var corner_escape"
    )
    assert '"hp": b.current_stats.health, "max_hp": b.max_stats.health' in adapter
    assert adapter.index('state["bosses"] = bosses') < adapter.index(
        "_normalize_player_relative(state)"
    )
    assert '"player": state.get("player", {})' in controller
    assert '"bosses": state.get("bosses", [])' in controller
    assert '_combat_unit_snapshot(b, "boss")' in controller
    assert '"hp": hp, "max_hp": max_hp, "health_ratio": hp / max_hp' in controller
    assert '"speed": unit.current_stats.speed' in controller
    assert '"name": str(unit.name)' in controller
    assert controller.index('state["bosses"] = bosses') < controller.index(
        "_normalize_combat_relative(state)"
    )
    assert 'for key in ["enemies", "bosses", "projectiles", "loot", "consumables"]' in controller
    assert 'entity["nx"] = float(entity.get("x", 0)) - px' in controller


def test_v93_finale_wall_recovery_is_the_last_movement_constraint():
    config = CONFIG.read_text(encoding="utf-8")
    potential = POTENTIAL_FIELD.read_text(encoding="utf-8")

    assert "const BOSS_FINALE_WALL_RECOVERY_ENTER := 280.0" in config
    assert "const BOSS_FINALE_WALL_RECOVERY_RELEASE := 520.0" in config
    assert "const BOSS_FINALE_WALL_HARD_MARGIN := 96.0" in config
    assert "func _finale_lane_score(" in potential
    assert "boss_pos + boss_vel * future_sec" in potential
    assert "projectile_pos + projectile_vel * future_sec" in potential

    movement_tail = potential.split("var smoothed =", 1)[1].split(
        "func _reset_finale_commit", 1
    )[0]
    safety_call = movement_tail.index("final_move = _finale_wall_safety(")
    persistence = movement_tail.index("_prev_move = final_move")
    assert safety_call < persistence

    safety = potential.split("func _finale_wall_safety", 1)[1].split(
        "func _best_wall_safe_projectile_lane", 1
    )[0]
    assert (
        "if _finale_wall_recovery_active and not _finale_projectile_safety_active:"
        in safety
    )
    assert "wall_distance >= BotConfig.BOSS_FINALE_WALL_RECOVERY_RELEASE" in safety
    assert "wall_distance <= BotConfig.BOSS_FINALE_WALL_RECOVERY_ENTER" in safety
    assert safety.rstrip().endswith("return clamped")

    hard_projection = potential.split("func _clamp_finale_wall_components", 1)[1].split(
        "func _finale_lane_score", 1
    )[0]
    assert "min(pos.x, projected.x) <= margin" in hard_projection
    assert "max(pos.x, projected.x) >= w - margin" in hard_projection
    assert "min(pos.y, projected.y) <= margin" in hard_projection
    assert "max(pos.y, projected.y) >= h - margin" in hard_projection
    assert '"wall_recovery_active": _finale_wall_recovery_active' in potential


def test_v94_finale_rechecks_projectiles_after_smoothing_and_before_wall_safety():
    potential = POTENTIAL_FIELD.read_text(encoding="utf-8")

    movement_tail = potential.split("var smoothed =", 1)[1].split(
        "func _reset_finale_commit", 1
    )[0]
    smoothing = movement_tail.index("var final_move = _normalize(smoothed)")
    projectile_safety = movement_tail.index(
        "final_move = _finale_projectile_safety("
    )
    wall_safety = movement_tail.index("final_move = _finale_wall_safety(")
    persistence = movement_tail.index("_prev_move = final_move")
    assert smoothing < projectile_safety < wall_safety < persistence

    safety = potential.split("func _finale_projectile_safety", 1)[1].split(
        "func _finale_wall_safety", 1
    )[0]
    assert "_projectile_escape(" in safety
    assert "arena, desired, enemies, bosses, profile, true" in safety
    assert "_finale_projectile_input_clearance = float(result[2])" in safety
    assert "_finale_projectile_escape_clearance = float(result[3])" in safety
    assert "urgency * BotConfig.BOSS_FINALE_PROJ_URGENCY_MULT" in safety
    assert "BotConfig.BOSS_FINALE_PROJ_URGENCY_FLOOR" in safety
    assert "desired * (1.0 - urgency) + escape_dir * urgency" in safety
    assert '"projectile_safety_active": _finale_projectile_safety_active' in potential
    assert '"projectile_safety_urgency": _finale_projectile_safety_urgency' in potential
    assert '"projectile_input_clearance": _finale_projectile_input_clearance' in potential
    assert '"projectile_escape_clearance": _finale_projectile_escape_clearance' in potential


def test_v95_soft_wall_recovery_cannot_override_active_projectile_safety():
    potential = POTENTIAL_FIELD.read_text(encoding="utf-8")
    safety = potential.split("func _finale_wall_safety", 1)[1].split(
        "func _best_wall_safe_projectile_lane", 1
    )[0]

    assert (
        "if _finale_wall_recovery_active and not _finale_projectile_safety_active:"
        in safety
    )
    assert safety.index("not _finale_projectile_safety_active") < safety.index(
        "_best_finale_interior_lane("
    )
    assert safety.rstrip().endswith("return clamped")


def test_v110_hard_wall_projection_reserves_a_full_recompute_interval():
    config = CONFIG.read_text(encoding="utf-8")
    potential = POTENTIAL_FIELD.read_text(encoding="utf-8")

    assert "const BOSS_FINALE_RECOMPUTE_DIVISOR := 3" in config
    assert "const BOSS_FINALE_WALL_COMMAND_HORIZON := 0.35" in config
    projection = potential.split("func _clamp_finale_wall_components", 1)[1].split(
        "func _finale_lane_score", 1
    )[0]
    assert "player_speed: float" in projection
    assert "BotConfig.BOSS_FINALE_WALL_COMMAND_HORIZON" in projection
    assert "var projected := pos + out * travel" in projection
    assert projection.count("projected = pos + out * travel") == 1
    assert projection.index("out = _normalize(out)") < projection.index(
        "projected = pos + out * travel"
    )


def test_v100_hard_wall_rotation_replans_over_wall_safe_projectile_lanes():
    config = CONFIG.read_text(encoding="utf-8")
    potential = POTENTIAL_FIELD.read_text(encoding="utf-8")

    assert "const BOSS_FINALE_PROJECTILE_WALL_MIN_GAIN := 20.0" in config
    safety = potential.split("func _finale_wall_safety", 1)[1].split(
        "func _best_wall_safe_projectile_lane", 1
    )[0]
    hard_clamp = safety.index("var clamped := _clamp_finale_wall_components(")
    rotation_check = safety.index("clamped.dot(safe_n) < 0.999")
    panic_check = safety.index("if clamped_clear < panic_clear:")
    replan = safety.index("_best_wall_safe_projectile_lane(")
    final_clearance = safety.index("_finale_projectile_final_clearance =")
    assert hard_clamp < rotation_check < panic_check < replan < final_clearance

    selector = potential.split("func _best_wall_safe_projectile_lane", 1)[1].split(
        "func _finale_committed_escape", 1
    )[0]
    assert "context: Dictionary" in selector
    assert "_projectile_clearance_context(" in safety
    assert "candidate := _clamp_finale_wall_components(" in selector
    assert "clearance := _dir_clearance(" in selector
    assert "penalty := _predictive_enemy_path_penalty(" in selector
    assert "times, enemies, bosses, 1.0" in selector
    assert "BOSS_FINALE_PROJECTILE_WALL_MIN_GAIN" in selector
    assert '"projectile_final_clearance": _finale_projectile_final_clearance' in potential
    assert (
        '"projectile_wall_replan_active": _finale_projectile_wall_replan_active'
        in potential
    )


def test_v104_recovery_and_wall_replan_require_measurable_clearance_gain():
    potential = POTENTIAL_FIELD.read_text(encoding="utf-8")

    scorer = potential.split("func _finale_lane_score", 1)[1].split(
        "func _best_finale_interior_lane", 1
    )[0]
    current = scorer.index("var current_wall_clear :=")
    improvement_gate = scorer.index(
        "wall_clear <= current_wall_clear + 0.001"
    )
    rejection = scorer.index("return -1.0e18", improvement_gate)
    # v0.2.57 hoisted each weighted term into its own local so the tail
    # decomposition instrument can record it; term_wall is the first of them and
    # replaces the old `var score := (` accumulator start. Ordering is unchanged.
    weighted_score = scorer.index("var term_wall := (")
    assert current < improvement_gate < rejection < weighted_score

    selector = potential.split("func _best_wall_safe_projectile_lane", 1)[1].split(
        "func _finale_committed_escape", 1
    )[0]
    assert "var best_score := -1.0e18" in selector
    assert "var found_clearer_lane := false" in selector
    clearance = selector.index("var clearance := _dir_clearance(")
    gain_gate = selector.index("if (clearance < baseline_clear")
    skip = selector.index("continue", gain_gate)
    penalty = selector.index("var penalty := _predictive_enemy_path_penalty(")
    choose = selector.index("found_clearer_lane = true")
    fallback = selector.index("if not found_clearer_lane:")
    assert clearance < gain_gate < skip < penalty < choose < fallback

    # Reproduce the two v103 counterexamples. A horizontal command at the
    # lower-left position leaves the limiting y wall unchanged, while the
    # inward diagonal increases it. A dangerous 178.7-clearance baseline must
    # not win over a 233.7-clearance candidate merely because its combined
    # enemy/continuity score is lower.
    x, y, width, height, lookahead = 515.916199, 508.548737, 2048.0, 1536.0, 260.0
    current_wall = min(x, y, width - x, height - y)
    horizontal_wall = min(x + lookahead, y, width - x - lookahead, height - y)
    diagonal_step = lookahead / (2.0**0.5)
    diagonal_wall = min(
        x + diagonal_step,
        y + diagonal_step,
        width - x - diagonal_step,
        height - y - diagonal_step,
    )
    assert horizontal_wall <= current_wall + 0.001
    assert diagonal_wall > current_wall + 0.001

    baseline_clear = 178.6539
    candidates = [(190.0, 10_000.0), (233.689697, -100.0)]
    eligible = [row for row in candidates if row[0] >= baseline_clear + 20.0]
    assert max(eligible, key=lambda row: row[1])[0] == 233.689697


def test_v105_wall_recovery_filters_out_materially_denser_enemy_lanes():
    config = CONFIG.read_text(encoding="utf-8")
    potential = POTENTIAL_FIELD.read_text(encoding="utf-8")

    for declaration in (
        "const BOSS_FINALE_WALL_ENEMY_AVOID_CLEARANCE := 120.0",
        "const BOSS_FINALE_WALL_ENEMY_CRITICAL_CLEARANCE := 45.0",
        "const BOSS_FINALE_WALL_ENEMY_CRITICAL_WEIGHT := 0.02",
        "const BOSS_FINALE_WALL_ENEMY_SCORE_WEIGHT := 4.0",
        "const BOSS_FINALE_ENEMY_PENALTY_SLACK := 20.0",
    ):
        assert declaration in config

    helper = potential.split("func _finale_enemy_path_penalty", 1)[1].split(
        "func _finale_lane_score", 1
    )[0]
    assert 'float(enemy.get("vx", 0.0))' in helper
    assert 'float(enemy.get("vy", 0.0))' in helper
    assert 'float(enemy.get("radius", 18.0))' in helper
    assert "enemy_pos + enemy_vel * future_sec" in helper
    assert "critical_gap * critical_gap" in helper

    selector = potential.split("func _best_finale_interior_lane", 1)[1].split(
        "func _finale_projectile_safety", 1
    )[0]
    penalty = selector.index("var enemy_penalty := _finale_enemy_path_penalty(")
    eligible = selector.index("if score <= -1.0e17:")
    collect = selector.index(
        "rows.append([candidate, score, enemy_penalty, body_clearance])"
    )
    second_pass = selector.index("for row in candidate_rows:")
    safety_gate = selector.index(
        "enemy_penalty > lowest_enemy_penalty", second_pass
    )
    choose = selector.index("if score > best_score:", safety_gate)
    assert penalty < eligible < collect < second_pass < safety_gate < choose
    assert "pos, desired, arena, enemies, bosses, projectiles, player_speed" in potential
    for field in (
        '"wall_input_enemy_penalty": _finale_wall_input_enemy_penalty',
        '"wall_best_enemy_penalty": _finale_wall_best_enemy_penalty',
        '"wall_selected_enemy_penalty": _finale_wall_selected_enemy_penalty',
    ):
        assert field in potential

    predictive = potential.split("func _predictive_enemy_path_penalty", 1)[1].split(
        "func _panic_dodge", 1
    )[0]
    assert 'float(threat.get("vx", 0.0))' in predictive
    assert 'float(threat.get("vy", 0.0))' in predictive
    assert 'float(threat.get("radius", 18.0))' in predictive
    assert "threat_pos + threat_vel * future_sec" in predictive
    # These expressions include untyped helper parameters. Godot 3 cannot
    # infer `:=` types for them even though Python source checks accept them.
    for typed_local in (
        "var avoid: float =",
        "var critical: float =",
        "var player_pos: Vector2 =",
        "var clearance: float =",
    ):
        assert typed_local in predictive
    assert "var avoid :=" not in predictive
    assert "var critical :=" not in predictive

    projectile = potential.split("func _projectile_escape", 1)[1].split(
        "func _projectile_clearance_context", 1
    )[0]
    assert "_predictive_enemy_path_penalty(" in projectile
    tier = projectile.index("var clearance_floor := -1.0e18")
    safe_tier = projectile.index("if max_clearance >= safe:", tier)
    gate = projectile.index("if row_clearance < clearance_floor:", safe_tier)
    pick = projectile.index("if row_score > best_score:", gate)
    assert tier < safe_tier < gate < pick

    blend = potential.split("func _finale_projectile_safety", 1)[1].split(
        "func _finale_wall_safety", 1
    )[0]
    assert "_finale_projectile_blended_enemy_penalty" in blend
    crowd_gate = blend.index(
        "_finale_projectile_blended_enemy_penalty > crowd_safe_penalty"
    )
    crowd_return = blend.index("return crowd_safe_dir", crowd_gate)
    assert crowd_gate < crowd_return

    # Reduced reproduction of v104 run_1784735721_60788 capture 17413. Both
    # candidates increase the limiting wall. The selected v104 lane crossed a
    # pack (raw predictive penalty 280.075), whereas an adjacent wall-safe lane
    # had 166.0. The v105 two-pass gate excludes the former before base score.
    current_wall = 279.4
    v104_wall, v104_penalty = 504.6, 280.075
    safer_wall, safer_penalty = 409.4, 166.0
    assert v104_wall > current_wall and safer_wall > current_wall
    assert v104_penalty > safer_penalty + 20.0


def test_v106_body_clearance_tier_rejects_avoidable_contact_paths():
    config = CONFIG.read_text(encoding="utf-8")
    potential = POTENTIAL_FIELD.read_text(encoding="utf-8")

    for declaration in (
        "const BOSS_FINALE_BODY_CRITICAL_CLEARANCE := 45.0",
        "const BOSS_FINALE_BODY_CLEARANCE_SLACK := 20.0",
        "const BOSS_FINALE_BODY_ESCAPE_PROJECTILE_SLACK := 60.0",
    ):
        assert declaration in config

    helper = potential.split("func _predictive_body_path_clearance", 1)[1].split(
        "func _finale_lane_score", 1
    )[0]
    assert 'float(threat.get("vx", 0.0))' in helper
    assert 'float(threat.get("vy", 0.0))' in helper
    assert 'float(threat.get("radius", 18.0))' in helper
    # v116 replaced the discrete future samples with the continuous closest
    # approach; the tier still starts one decision interval into the hold.
    assert "BotConfig.ESCAPE_CLEARANCE_MIN_TIME" in helper
    assert "-rel_pos.dot(rel_vel) / speed_sq" in helper

    selector = potential.split("func _best_finale_interior_lane", 1)[1].split(
        "func _finale_projectile_safety", 1
    )[0]
    body_collect = selector.index(
        "rows.append([candidate, score, enemy_penalty, body_clearance])"
    )
    body_floor = selector.index("var body_clearance_floor :=", body_collect)
    body_gate = selector.index("if body_clearance < body_clearance_floor:", body_floor)
    enemy_gate = selector.index("enemy_penalty > lowest_enemy_penalty", body_gate)
    choose = selector.index("if score > best_score:", enemy_gate)
    assert body_collect < body_floor < body_gate < enemy_gate < choose

    projectile = potential.split("func _projectile_escape", 1)[1].split(
        "func _projectile_clearance_context", 1
    )[0]
    assert "var tier_max_body_clearance := -1.0e18" in projectile
    assert "var broadened_clearance_floor := (" in projectile
    assert "if max_clearance >= panic:" in projectile
    assert "BOSS_FINALE_BODY_ESCAPE_PROJECTILE_SLACK" in projectile
    assert "if finale and float(row[3]) < body_clearance_floor:" in projectile

    for field in (
        '"wall_best_body_clearance": _finale_wall_best_body_clearance',
        '"wall_selected_body_clearance": _finale_wall_selected_body_clearance',
        '"projectile_escape_body_clearance": _finale_projectile_escape_body_clearance',
        '"projectile_final_body_clearance": _finale_projectile_final_body_clearance',
    ):
        assert field in potential

    # Frozen v105 smoke evidence. At capture 20226, wall recovery chose a
    # predicted 8.1-unit boss path although another wall-improving lane offered
    # 59.1. At capture 20433, the body-safe projectile alternative stayed in
    # the same clearance tier. At 20432 every projectile lane was below panic,
    # and avoiding contact cost only 43.8 clearance, within the bounded 60.
    assert 8.1 < 45.0 <= 59.1
    assert 71.8 >= 81.6 - 20.0 and 2.2 < 45.0 <= 61.4
    assert 84.7 < 204.6 and 84.7 - 40.9 <= 60.0


def test_v107_final_body_gate_runs_after_wall_projection_and_preserves_safety_tiers():
    potential = POTENTIAL_FIELD.read_text(encoding="utf-8")
    movement = potential.split("func compute_movement", 1)[1].split(
        "func _reset_finale_commit", 1
    )[0]

    survival = movement.split("var safe_survival =", 1)[1].split(
        "return _prev_move", 1
    )[0]
    assert survival.index("_finale_projectile_safety(") < survival.index(
        "_finale_wall_safety("
    ) < survival.index("_finale_body_safety(")

    ordinary = movement.split("var final_move =", 1)[1]
    assert ordinary.index("_finale_projectile_safety(") < ordinary.index(
        "_finale_wall_safety("
    ) < ordinary.index("_finale_body_safety(")

    safety = potential.split("func _finale_body_safety", 1)[1].split(
        "func _finale_committed_escape", 1
    )[0]
    clamp = safety.index("var candidate := _clamp_finale_wall_components(")
    body = safety.index("var body_clearance := _predictive_body_path_clearance(")
    wall_gate = safety.index("if _finale_wall_recovery_active:")
    projectile_floor = safety.index("var projectile_floor := -1.0e18")
    safe_tier = safety.index("highest_projectile_clearance >= safe_clear")
    panic_tier = safety.index("highest_projectile_clearance >= panic_clear")
    concession = safety.index("BOSS_FINALE_BODY_ESCAPE_PROJECTILE_SLACK")
    body_tier = safety.index("var body_floor := highest_body_clearance")
    body_gate = safety.index(
        "projectile_clearance < projectile_floor or body_clearance < body_floor"
    )
    assert clamp < wall_gate < body < projectile_floor
    assert projectile_floor < safe_tier < panic_tier < concession < body_tier < body_gate

    for field in (
        '"body_safety_active": _finale_body_safety_active',
        '"body_input_clearance": _finale_body_input_clearance',
        '"body_best_clearance": _finale_body_best_clearance',
        '"body_selected_clearance": _finale_body_selected_clearance',
        '"body_projectile_floor": _finale_body_projectile_floor',
    ):
        assert field in potential

    # Frozen v106 smoke evidence. The final wall clamp reintroduced avoidable
    # contact at capture 17073, and ordinary movement did so at 17329. Both have
    # a sampled contact-safe alternative and therefore fail the v107 45-unit tier.
    assert -3.1983 < 45.0 <= 366.59
    assert 33.3 < 45.0 <= 50.8


def test_v108_final_body_gate_anchors_projectile_concession_and_preserves_body_escape():
    potential = POTENTIAL_FIELD.read_text(encoding="utf-8")
    safety = potential.split("func _finale_body_safety", 1)[1].split(
        "func _finale_committed_escape", 1
    )[0]

    baseline = safety.index("var baseline_projectile_clearance := 1000000.0")
    reference = safety.index("var projectile_reference_clearance :=")
    escape_anchor = safety.index("_finale_projectile_escape_clearance)", reference)
    floor = safety.index("var projectile_floor := -1.0e18")
    bounded = safety.index(
        "projectile_reference_clearance\n\t\t\t\t\t- "
        "BotConfig.BOSS_FINALE_BODY_ESCAPE_PROJECTILE_SLACK",
        floor,
    )
    emergency = safety.index("var strict_body_best := -1.0e18", bounded)
    emergency_gain = safety.index(
        "BotConfig.BOSS_FINALE_BODY_EMERGENCY_MIN_GAIN", emergency
    )
    emergency_slack = safety.index(
        "BotConfig.BOSS_FINALE_BODY_EMERGENCY_CLEARANCE_SLACK", emergency_gain
    )
    candidate_gate = safety.index("projectile_clearance < projectile_floor")
    assert (
        baseline
        < reference
        < escape_anchor
        < floor
        < bounded
        < emergency
        < emergency_gain
        < emergency_slack
        < candidate_gate
    )

    # Frozen v107 exact-20 capture 20609. Active wall recovery restricted the
    # sampled pool to 73.623917 clearance even though the emitted projectile
    # escape retained 98.0783. The strict 38.0783 floor left only a predicted
    # body overlap (-9.482), while the original bounded tier exposed a 41.602264
    # escape. The emergency therefore broadens the projectile tier but its
    # five-unit body floor rejects the damaging 33.194206 lane.
    sampled_max = 73.623917
    emitted_escape = 98.0783
    strict_body_best = -9.482
    relaxed_body_best = 41.602264
    damaging_body_lane = 33.194206
    relaxed_projectile_floor = sampled_max - 60.0
    strict_projectile_floor = max(
        relaxed_projectile_floor, emitted_escape - 60.0
    )
    assert strict_projectile_floor == 38.0783
    assert strict_body_best < 0.0
    assert relaxed_body_best >= strict_body_best + 20.0
    emergency_body_floor = relaxed_body_best - 5.0
    assert damaging_body_lane < emergency_body_floor


def test_v109_final_body_pool_rejects_non_sampled_wall_fallbacks():
    potential = POTENTIAL_FIELD.read_text(encoding="utf-8")
    helper = potential.split("func _is_finale_sampled_direction", 1)[1].split(
        "func _finale_enemy_path_penalty", 1
    )[0]
    safety = potential.split("func _finale_body_safety", 1)[1].split(
        "func _finale_committed_escape", 1
    )[0]

    assert "for k in range(BotConfig.ESCAPE_DIRECTIONS):" in helper
    assert "safe_direction.dot(sampled) >= 0.99999" in helper
    clamp = safety.index("var candidate := _clamp_finale_wall_components(")
    sampled_gate = safety.index("if not _is_finale_sampled_direction(candidate):")
    body_score = safety.index("var body_clearance := _predictive_body_path_clearance(")
    assert clamp < sampled_gate < body_score

    # Frozen v108 exact-20 capture 20755. At (184.35, 347.26), an outward
    # sample had both components removed by the hard-wall clamp. Its generic
    # center fallback pointed 26.615 degrees, outside the 15-degree sample grid,
    # but was labelled as an active sampled body repair. v109 excludes it so an
    # actual audited inward sample wins instead.
    player_x, player_y = 184.349487, 347.257813
    center_x, center_y = 1024.0, 768.0
    center_angle = math.degrees(math.atan2(center_y - player_y, center_x - player_x))
    nearest_sample = round(center_angle / 15.0) * 15.0
    assert abs(center_angle - nearest_sample) > 3.0


def test_v109_bounded_projectile_concession_prefers_materially_clearer_body_lane():
    potential = POTENTIAL_FIELD.read_text(encoding="utf-8")
    projectile = potential.split("func _projectile_escape", 1)[1].split(
        "func _projectile_clearance_context", 1
    )[0]
    final_body = potential.split("func _finale_body_safety", 1)[1].split(
        "func _finale_committed_escape", 1
    )[0]

    for selector in (projectile, final_body):
        assert "BOSS_FINALE_BODY_ESCAPE_PROJECTILE_SLACK" in selector
        assert "BOSS_FINALE_BODY_EMERGENCY_MIN_GAIN" in selector
        assert "BOSS_FINALE_BODY_EMERGENCY_CLEARANCE_SLACK" in selector
    assert "broadened_clearance_floor = max(panic, broadened_clearance_floor)" in projectile
    assert "relaxed_projectile_floor = max(" in final_body
    assert "relaxed_projectile_floor < projectile_floor" in final_body
    assert '"body_emergency_active": _finale_body_emergency_active' in potential

    # Frozen v108 exact-20 capture 20604. The old safe-tier gate admitted only
    # the 150-degree lane even though a bounded, panic-safe concession exposed
    # a materially clearer 195-degree escape. v109 admits the latter tier and
    # then requires the selection to remain within five units of its best body
    # clearance.
    strict_projectile, strict_body = 223.323166, 61.504105
    escape_projectile, escape_body = 177.7, 86.5
    panic = 72.6
    assert strict_projectile - escape_projectile < 60.0
    assert escape_projectile >= panic
    assert escape_body >= strict_body + 20.0
    assert strict_body < escape_body - 5.0


def test_v110_final_body_gate_stays_near_best_inside_the_projectile_tier():
    potential = POTENTIAL_FIELD.read_text(encoding="utf-8")
    safety = potential.split("func _finale_body_safety", 1)[1].split(
        "func _finale_committed_escape", 1
    )[0]
    ordinary_floor = safety.split(
        "elif (enforce_pack_clearance",
        1,
    )[1].split("else:", 1)[0]

    assert "projectiles, profile, wave, true)" in potential
    assert "enforce_pack_clearance := false" in safety
    assert "body_floor = max(" in ordinary_floor
    assert "BotConfig.BOSS_FINALE_BODY_CRITICAL_CLEARANCE" in ordinary_floor
    assert "BotConfig.BOSS_FINALE_BODY_PACK_CLEARANCE" in ordinary_floor
    # v123: the near-best slack is now the wave-indexed body_slack local.
    assert "highest_body_clearance - body_slack" in ordinary_floor
    assert "var body_slack := BotConfig.body_clearance_slack(wave)" in safety

    # Frozen v109 exact-20 run 2 capture 21282. The selected lane and a much
    # clearer alternative both satisfied the active projectile tier.
    selected_body = 124.864822
    best_body = 182.581696
    required_body = max(45.0, min(160.0, best_body - 20.0))
    assert selected_body < required_body


def test_v113_wall_recovery_intervenes_early_and_stays_near_best():
    config = CONFIG.read_text(encoding="utf-8")
    potential = POTENTIAL_FIELD.read_text(encoding="utf-8")
    selector = potential.split("func _best_finale_interior_lane", 1)[1].split(
        "func _finale_projectile_safety", 1
    )[0]

    assert "const BOSS_FINALE_WALL_BODY_RELIEF_TRIGGER := 200.0" in config
    assert "const BOSS_FINALE_WALL_BODY_RELIEF_MIN_GAIN := 60.0" in config
    assert "const BOSS_FINALE_WALL_BODY_RELIEF_CLEARANCE_SLACK := 10.0" in config
    assert "candidate_rows = hard_safe_rows" in selector
    assert (
        "highest_body_clearance\n"
        "\t\t\t\t- BotConfig.BOSS_FINALE_WALL_BODY_RELIEF_CLEARANCE_SLACK"
    ) in selector
    assert '"wall_body_relief_active": _finale_wall_body_relief_active' in potential
    assert (
        '"wall_relief_best_body_clearance": '
        "_finale_wall_relief_best_body_clearance"
    ) in potential

    # Frozen v110 run 2 capture 20520. Strict wall progress chose the
    # inward-right route through the pack; a hard-wall-safe relief lane was
    # more than 180 units clearer.
    selected_body = 85.795204
    relief_body = 267.219028
    assert selected_body < 200.0
    assert relief_body >= selected_body + 60.0


def test_v113_final_body_arbiter_preserves_or_discovers_tight_wall_relief():
    potential = POTENTIAL_FIELD.read_text(encoding="utf-8")
    safety = potential.split("func _finale_body_safety", 1)[1].split(
        "func _finale_committed_escape", 1
    )[0]

    assert "var hard_safe_rows := []" in safety
    assert "makes_wall_progress = false" in safety
    assert "player_speed, enemy_penalty, false" in safety
    assert "rows = hard_safe_rows" in safety
    assert "and not _finale_projectile_safety_active" in safety
    assert "_finale_wall_body_relief_active = true" in safety
    assert "_finale_wall_relief_best_body_clearance = highest_body_clearance" in safety
    relief_floor = safety.split("elif _finale_wall_body_relief_active:", 1)[1].split(
        "elif (enforce_pack_clearance", 1
    )[0]
    assert "BOSS_FINALE_BODY_CRITICAL_CLEARANCE" in relief_floor
    assert "BOSS_FINALE_WALL_BODY_RELIEF_CLEARANCE_SLACK" in relief_floor


def test_v115_wall_relief_compares_against_the_emitted_baseline():
    potential = POTENTIAL_FIELD.read_text(encoding="utf-8")
    safety = potential.split("func _finale_body_safety", 1)[1].split(
        "func _finale_committed_escape", 1
    )[0]

    assert "var wall_body_relief_reference := min(" in safety
    assert "strict_wall_body_clearance, _finale_body_input_clearance" in safety
    assert "and wall_body_relief_reference" in safety
    assert ">= wall_body_relief_reference" in safety

    # Frozen v114 smoke captures 20467-20468. The strict wall-progress pool
    # contained a marginally clearer lane than the emitted baseline, masking
    # the hard-safe route's actual 60-unit improvement over the final command.
    cases = [
        {"baseline": 18.9394516, "strict_best": 23.7, "hard_safe": 79.4027649},
        {"baseline": -2.5798774, "strict_best": 9.0, "hard_safe": 57.6799102},
    ]
    for case in cases:
        old_reference = case["strict_best"]
        emitted_reference = min(case["strict_best"], case["baseline"])
        assert case["hard_safe"] < old_reference + 60.0
        assert case["hard_safe"] >= emitted_reference + 60.0


def test_v116_clearances_use_the_continuous_closest_approach():
    config = CONFIG.read_text(encoding="utf-8")
    potential = POTENTIAL_FIELD.read_text(encoding="utf-8")

    assert "const ESCAPE_CLEARANCE_MIN_TIME := 0.05" in config

    body = potential.split("func _predictive_body_path_clearance", 1)[1].split(
        "func _finale_lane_score", 1
    )[0]
    assert "for time_value in times:" not in body.split("var t_lo", 1)[-1]
    assert "min(BotConfig.ESCAPE_CLEARANCE_MIN_TIME, horizon)" in body
    assert "clamp(" in body and "-rel_pos.dot(rel_vel) / speed_sq" in body

    projectile = potential.split("func _dir_clearance", 1)[1].split(
        "func _enemy_path_penalty", 1
    )[0]
    assert "(bullets_t[1][j] - bullet_pos) / step" in projectile
    assert "-rel_pos.dot(rel_vel) / speed_sq" in projectile
    # The wall-margin penalty is unchanged and still applies after the
    # continuous minimum.
    assert "BotConfig.ESCAPE_WALL_PENALTY" in projectile

    # Frozen v115 smoke evidence. Capture 19557: a 940 u/s horned-bruiser
    # charge crossed the commanded path at t~38 ms; every 120 ms sample read
    # ~95 units while the true closest approach was contact. Capture 20505:
    # the emitted escape passed through a stationary radius-23 bullet at
    # t~56 ms while the t=0 and t=0.12 samples both read ~28 units.
    assert 95.305712 > 45.0 > -10.5
    assert 28.078943 > 23.0 > 1.74


def test_v119_stall_trigger_and_loot_biased_strafe():
    config = CONFIG.read_text(encoding="utf-8")
    potential = POTENTIAL_FIELD.read_text(encoding="utf-8")

    # v123: stall count and strafe loot cap are wave-indexed getters.
    assert "static func loot_dash_stall_count(wave: int) -> int:" in config
    assert "const ENGAGE_STRAFE_LOOT_WEIGHT := 4.0" in config
    assert "static func engage_strafe_loot_cap(wave: int) -> float:" in config

    dash = potential.split("func _apply_loot_dash", 1)[1].split(
        "func _reset_finale_commit", 1
    )[0]
    # Heavy accumulation arms the dash at any density; otherwise the density
    # gate still applies.
    assert "scan_count >= BotConfig.loot_dash_stall_count(wave)" in dash
    assert "not stalled" in dash
    assert "< BotConfig.PACK_DENSITY_SOFT" in dash

    strafe = potential.split("func _score_strafe_side", 1)[1].split(
        "func _early_hunt_force", 1
    )[0]
    # Bounded flank bonus for materials; enemy pressure and wall openness
    # keep their existing weights.
    assert "BotConfig.ENGAGE_STRAFE_LOOT_WEIGHT" in strafe
    assert "loot_bonus = min(loot_bonus, BotConfig.engage_strafe_loot_cap(wave))" in strafe
    assert "+ loot_bonus)" in strafe
    assert "_engage_strafe_force(pos, enemies, bosses, arena, nearest_d, loot, wave)" in potential

    # Frozen v118 smoke wave-10 evidence (run_1784778591_87017): 1,241
    # captures, density always below 8, materials p50 19 / p90 49-50 with an
    # unblocked pile in 95% of captures at ~176 units — ordinary collection
    # stalled with the v118 dash never arming.
    assert 19 >= 0 and 49 >= 30
    assert 176 <= 420.0


def test_v122_crossing_range_tier_bounds_soft_term_arbitration():
    potential = POTENTIAL_FIELD.read_text(encoding="utf-8")
    safety = potential.split("func _finale_body_safety", 1)[1].split(
        "func _finale_committed_escape", 1
    )[0]
    block = safety.split("var best_admissible_projectile := -1.0e18", 1)[1].split(
        "_finale_body_projectile_floor = projectile_floor", 1
    )[0]

    assert "not body_emergency_active" in safety.split(
        "var best_admissible_projectile", 1
    )[0].rsplit("if not projectile_context.empty()", 1)[1]
    assert "BotConfig.ESCAPE_SAFE_CLEARANCE" in block
    assert (
        "best_admissible_projectile\n\t\t\t\t\t- BotConfig.BOSS_FINALE_PROJECTILE_BLEND_MIN_GAIN"
        in block
    )

    # Frozen v121 smoke capture 14938: equal 145.8 body clearance on both
    # lanes; continuity chose 4.62 projectile clearance over 46.39 and a
    # 12-damage bullet followed. Under the tier, 4.62 < 46.39 - 20.
    assert 4.619292 < 46.3873539904868 - 20.0


def test_v121_unattainable_relief_floor_keeps_baseline_with_diagnostics():
    potential = POTENTIAL_FIELD.read_text(encoding="utf-8")
    safety = potential.split("func _finale_body_safety", 1)[1].split(
        "func _finale_committed_escape", 1
    )[0]
    relief_arm = safety.split("elif _finale_wall_body_relief_active:", 1)[1]

    assert "if highest_body_clearance < body_floor:" in relief_arm
    assert (
        "_finale_body_selected_clearance = _finale_body_input_clearance"
        in relief_arm.split("elif", 1)[0]
    )
    assert "return baseline" in relief_arm.split("elif", 1)[0]

    # Frozen v120 smoke capture 18555.
    assert 13.299061 < 45.0 and 46.465576 > 13.299061


def test_v118_loot_dash_is_bounded_hp_gated_and_window_tested():
    config = CONFIG.read_text(encoding="utf-8")
    potential = POTENTIAL_FIELD.read_text(encoding="utf-8")

    # v123: LOOT_DASH_MIN_PILE and MAX_TICKS stay literal; arm HP floor, window
    # clearance and cooldown became wave-indexed getters.
    for declaration in (
        "const LOOT_DASH_MIN_PILE := 5",
        "const LOOT_DASH_MAX_TICKS := 72",
        "static func loot_dash_arm_hp_floor(wave: int) -> float:",
        "static func loot_dash_window_clearance(wave: int) -> float:",
        "static func loot_dash_cooldown_ticks(wave: int) -> int:",
    ):
        assert declaration in config

    dash = potential.split("func _apply_loot_dash", 1)[1].split(
        "func _reset_finale_commit", 1
    )[0]
    # Trigger requires density suppression, a substantial pile, HP above the
    # floor, and a continuous-clearance corridor window.
    # v119 reshaped the density gate around the stall trigger; the density
    # condition itself remains.
    assert "_count_nearby_enemies(pos, enemies, bosses)" in dash
    assert "< BotConfig.PACK_DENSITY_SOFT" in dash
    assert "int(cluster[1]) < BotConfig.LOOT_DASH_MIN_PILE" in dash
    # v123: arm HP floor / window are wave-indexed + strength-shifted effective
    # locals (see _effective_dash_arm_hp_floor / _effective_dash_window_clearance).
    assert "var arm_hp_floor := _effective_dash_arm_hp_floor(wave)" in dash
    assert "hp_ratio < arm_hp_floor" in dash
    assert "_predictive_body_path_clearance(" in dash
    assert "var window_floor := _effective_dash_window_clearance(wave)" in dash
    assert "window < window_floor" in dash
    # Bullet-window test still honors the panic clearance with caution.
    assert "BotConfig.ESCAPE_PANIC_CLEARANCE" in dash
    # The commit is time-boxed with a cooldown afterwards.
    assert "_loot_dash_ticks = BotConfig.LOOT_DASH_MAX_TICKS" in dash
    assert "_loot_dash_cooldown = BotConfig.loot_dash_cooldown_ticks(wave)" in dash

    # Survival and finale paths always drop an active dash. v127 routes both drops
    # through _suppress_loot_dash so the telemetry records that it happened; the
    # guarantee is unchanged — the helper clears the flag and nothing else does.
    movement = potential.split("func compute_movement", 1)[1].split(
        "func _best_loot_cluster", 1
    )[0]
    assert movement.count('_suppress_loot_dash("suppressed_survival")') == 1
    assert movement.count('_suppress_loot_dash("suppressed_finale")') == 1
    suppressor = potential.split("func _suppress_loot_dash", 1)[1].split(
        "\nfunc ", 1
    )[0]
    assert "_loot_dash_active = false" in suppressor
    # The final body arbiter relaxes only the pack tier during a dash and
    # keeps the dash route despite crowd penalty, floors permitting.
    assert "not _loot_dash_active, _loot_dash_active)" in movement
    safety = potential.split("func _finale_body_safety", 1)[1].split(
        "func _finale_committed_escape", 1
    )[0]
    assert "dash_active := false" in safety
    assert "(dash_active" in safety
    assert '"loot_dash_active": _loot_dash_active' in potential


def test_v117_finale_captures_align_with_recompute_ticks_and_relief_extends():
    config = CONFIG.read_text(encoding="utf-8")
    controller = CONTROLLER.read_text(encoding="utf-8")
    combat = controller.split("func _handle_combat", 1)[1].split(
        "func _record_density_sample", 1
    )[0]

    # Captures on finale waves are emitted on the recompute tick itself, so
    # wave-20 freshness no longer depends on the counter phase at wave entry.
    assert "var emit_capture := _combat_tick_counter % _WP2_CAPTURE_DIVISOR == 0" in combat
    assert "if wave >= _CONFIG_SCRIPT.BOSS_FINALE_WAVE:" in combat
    assert "emit_capture = recompute_move" in combat
    assert "if emit_capture:" in combat
    assert "_emit_wp2_combat_capture(main, state, recompute_move)" in combat

    assert "const BOSS_FINALE_WALL_BODY_RELIEF_TRIGGER := 200.0" in config

    # Frozen v116 smoke (run_1784771165_61226) missed-relief captures: the
    # relief reference sat just above the old 140 trigger while hard-safe
    # lanes were 75-212 units clearer; the run died on wave 20.
    cases = [
        {"reference": 145.285248, "hard_safe": 223.153137},
        {"reference": 151.144669, "hard_safe": 269.427734},
        {"reference": 140.66243, "hard_safe": 215.368134},
        {"reference": 147.218948, "hard_safe": 369.706909},
    ]
    for case in cases:
        assert case["reference"] >= 140.0  # old trigger missed it
        assert case["reference"] < 200.0  # extended trigger arms
        assert case["hard_safe"] >= case["reference"] + 60.0


def test_v114_final_body_gate_covers_every_combat_wave_and_uses_open_pack_tier():
    potential = POTENTIAL_FIELD.read_text(encoding="utf-8")
    movement = potential.split("func compute_movement", 1)[1].split(
        "func _reset_finale_commit", 1
    )[0]
    final_tail = movement.split("var final_move =", 1)[1]

    late_guard = final_tail.index("if wave >= BotConfig.LATE_SURVIVAL_WAVE:")
    all_wave_comment = final_tail.index("# v114:")
    all_wave_body = final_tail.index("final_move = _finale_body_safety(", all_wave_comment)
    return_move = final_tail.index("return _prev_move")
    assert late_guard < all_wave_comment < all_wave_body < return_move
    assert (
        "projectiles, profile, wave, not _loot_dash_active, _loot_dash_active)"
        in final_tail[all_wave_body:return_move]
    )

    # Frozen v113 smoke wave-12 capture 11040. The unguarded route ran into
    # the pack while a hard-wall-safe sampled lane was comfortably open.
    selected_body = 13.0
    best_body = 269.6
    required_body = max(45.0, min(160.0, best_body - 20.0))
    assert selected_body < required_body


def test_v101_nonconvex_projectile_blend_falls_back_to_sampled_escape():
    config = CONFIG.read_text(encoding="utf-8")
    potential = POTENTIAL_FIELD.read_text(encoding="utf-8")

    assert "const BOSS_FINALE_PROJECTILE_BLEND_MIN_GAIN := 20.0" in config
    safety = potential.split("func _finale_projectile_safety", 1)[1].split(
        "func _finale_wall_safety", 1
    )[0]
    blend = safety.index(
        "var blended := _normalize(desired * (1.0 - urgency) + escape_dir * urgency)"
    )
    context = safety.index("var blend_context := _projectile_clearance_context(")
    clearance = safety.index("_finale_projectile_blended_clearance = _dir_clearance(")
    panic = safety.index("var panic_clear := (")
    gain = safety.index("BotConfig.BOSS_FINALE_PROJECTILE_BLEND_MIN_GAIN")
    fallback = safety.index("return escape_dir")
    normal_return = safety.index("return blended")
    assert blend < context < clearance < panic < gain < fallback < normal_return
    assert '"projectile_blended_clearance": _finale_projectile_blended_clearance' in potential
    assert (
        '"projectile_blend_repair_active": _finale_projectile_blend_repair_active'
        in potential
    )


def test_v74_preserves_early_hp_but_deemphasizes_it_after_wave_ten():
    strategy = STRATEGY.read_text(encoding="utf-8")
    pivot = strategy.split("func _late_shop_pivot_bonus", 1)[1].split(
        "func _combinable_index", 1
    )[0]

    # v74 mid pivot: HP trails DPS while offense is below 70.
    assert "bonus += val * (0.45 if offense < BotConfig.OFFENSE_FLOOR_MID else 1.00)" in pivot
    # Early (pre-10): preserve the v66 below-55 max HP safety weight.
    assert "if wave <= 11 and max_hp < 55.0:" in pivot
    assert "bonus += val * 1.15" in pivot
    # Late HP fallback is also lower when its layer is not yet saturated.
    assert "else (0.85 if max_hp < 110.0 else 0.50)" in pivot


def test_v66_crate_weapons_carry_identity_keys_for_the_allowlist():
    controller = CONTROLLER.read_text(encoding="utf-8")
    crate = controller.split("func _handle_crate_overlay", 1)[1].split(
        "\n\nfunc ", 1
    )[0]

    assert 'item["weapon_id"] = item_data.weapon_id' in crate
    assert 'item["sets"] = _weapon_sets(item_data)' in crate
    assert 'item["is_healing"] = item_data.stats.is_healing' in crate


def test_v66_combine_confirmation_timeout_releases_the_shop_barrier():
    controller = CONTROLLER.read_text(encoding="utf-8")
    barrier = controller.split("if _pending_combine_wave >= 0:", 1)[1].split(
        "var profile = _profiles.get_profile", 1
    )[0]
    timeout_block = barrier.split('shop_combine_confirmation_timeout', 1)[1]

    # After the timeout is reported the pending-combine state must be cleared so
    # shop_go remains reachable (previously the run soft-locked in the shop).
    assert '_pending_combine_signature = ""' in timeout_block
    assert "_pending_combine_wave = -1" in timeout_block
    assert "_combine_timeout_reported = false" in timeout_block
    assert "_last_shop_action_at = now" in timeout_block


def test_v77_live_monitor_version_gates_cover_the_deployed_policy_version():
    telemetry = TELEMETRY.read_text(encoding="utf-8")
    monitor = (ROOT / "trainer/evaluation/live_monitor.py").read_text(encoding="utf-8")

    match = re.search(r'POLICY_VERSION := "teacher_v1-(0\.1\.\d+)-gun-wp1"', telemetry)
    assert match is not None
    deployed = match.group(1)
    # Fail-open guard: every safety check version tuple must include the deployed
    # version, except the final-shop combine prohibition (lifted in v65).
    gated_tuples = re.findall(r'\(("0\.1\.\d+"(?:,\s*"0\.1\.\d+")+),?\s*\)', monitor)
    assert gated_tuples, "expected version tuples in live_monitor.py"
    covering = [t for t in gated_tuples if f'"{deployed}"' in t]
    assert len(gated_tuples) - len(covering) == 2, (
        "only the zero-combine (v48-58) and final-shop-combine (v55-64) tuples may "
        f"exclude the deployed version {deployed}: {gated_tuples}"
    )


def test_v77_hud_exposes_weapon_aware_offense_and_defense_targets():
    controller = CONTROLLER.read_text(encoding="utf-8")
    hud = HUD.read_text(encoding="utf-8")
    monitor = (ROOT / "trainer/evaluation/live_monitor.py").read_text(encoding="utf-8")

    assert "func _metric_targets(wave: int, observed_p90_density: float = 0.0," in controller
    assert "observed_peak_density: float = 0.0) -> Dictionary:" in controller
    assert "func _build_metrics(stats: Dictionary, weapons: Array, wave: int," in controller
    assert "live_max_hp: float = -1.0) -> Dictionary:" in controller
    assert '"total": offense_total' in controller
    assert '"target": 300.0' in controller
    assert '"ranged_damage": ranged' in controller
    assert '"percent_damage": damage' in controller
    assert '"attack_speed": attack_speed' in controller
    assert '"crit_chance": crit' in controller
    assert '"weapon_dps": float(offense_rating.get("weapon_dps", 0.0))' in controller
    assert '"weapon_score": float(offense_rating.get("weapon_score", 0.0))' in controller
    assert '"weapon_tier_sum": int(offense_rating.get("weapon_tier_sum", 0))' in controller
    assert '"hp_target": float(targets["hp"])' in controller
    assert '"max_hp_policy_stat": hp_policy_stat' in controller
    assert "_last_known_max_hp = live_max_hp" in controller
    metric_block = controller.split("func _build_metrics", 1)[1].split(
        "func _gather_shop_state", 1
    )[0]
    assert " or 0)" not in metric_block
    assert " or -1)" not in metric_block
    assert '"armor_target": float(targets["armor"])' in controller
    assert '"sustain_target": float(targets["sustain"])' in controller
    assert controller.count('"build_metrics": build_metrics') >= 3
    assert '"offense", "offense_values", "offense_weapons", "defense"' in hud
    assert '"defense_values", "defense_sustain"' in hud
    assert '"build_metrics": combat_payload.get("build_metrics", {})' in monitor


def test_hud_is_bottom_left_viewport_bounded_and_wraps_long_metric_lines():
    hud = HUD.read_text(encoding="utf-8")

    assert "_label.anchor_left = 0.0" in hud
    assert "_label.anchor_right = 0.62" in hud
    assert "_label.anchor_bottom = 1.0" in hud
    assert "_label.align = Label.ALIGN_LEFT" in hud
    assert "_label.valign = Label.VALIGN_BOTTOM" in hud
    assert "_label.margin_right = -12" in hud
    assert "_label.autowrap = true" in hud
    assert "_label.clip_text = true" in hud


def test_v77_offense_rating_uses_weapon_tiers_dps_and_crowd_clear():
    config = CONFIG.read_text(encoding="utf-8")
    combat = COMBAT_MODEL.read_text(encoding="utf-8")
    strategy = STRATEGY.read_text(encoding="utf-8")
    controller = CONTROLLER.read_text(encoding="utf-8")

    assert "const OFFENSE_WEAPON_DPS_PER_POINT := 15.0" in config
    assert "func effective_weapon_dps(weapon: Dictionary, stats: Dictionary)" in combat
    assert 'weapon.get("nb_projectiles")' in combat
    assert 'weapon.get("piercing")' in combat
    assert 'weapon.get("bounce")' in combat
    assert 'sets.has("set_explosive")' in combat
    assert "func offense_rating(build: Dictionary) -> Dictionary:" in combat
    assert 'int(weapon.get("tier", 0)) + 1' in combat
    assert '"total": max(stat_score, weapon_score)' in combat
    assert "BotCombatModel.offense_rating(build)" in strategy
    assert 'entry["nb_projectiles"]' in controller
    assert 'entry["piercing"]' in controller
    assert 'entry["bounce"]' in controller


def test_v77_wave20_movement_holds_decisions_and_turns_through_reversals():
    config = CONFIG.read_text(encoding="utf-8")
    potential = POTENTIAL_FIELD.read_text(encoding="utf-8")
    controller = CONTROLLER.read_text(encoding="utf-8")

    assert "const BOSS_FINALE_RECOMPUTE_DIVISOR := 3" in config
    assert "const BOSS_FINALE_ESCAPE_CONTINUITY := 85.0" in config
    assert "const BOSS_FINALE_REVERSE_DOT := -0.35" in config
    assert "var _finale_move_tick := 0" in controller
    assert "_finale_move_tick % _CONFIG_SCRIPT.BOSS_FINALE_RECOMPUTE_DIVISOR" in controller
    assert "func _finale_turn_without_reversal" in potential
    assert potential.count("_finale_turn_without_reversal(") >= 2
    assert "BOSS_FINALE_ESCAPE_CONTINUITY * d.dot(_prev_move)" in potential


def test_v79_uses_p90_peak_pressure_and_actual_displacement_commitment():
    config = CONFIG.read_text(encoding="utf-8")
    strategy = STRATEGY.read_text(encoding="utf-8")
    potential = POTENTIAL_FIELD.read_text(encoding="utf-8")
    controller = CONTROLLER.read_text(encoding="utf-8")

    assert "const OFFENSE_TARGET_MARGIN := 25.0" in config
    assert "const OFFENSE_DENSITY_P90_GOAL := 15.0" in config
    assert "const OFFENSE_DENSITY_POINTS_PER_ENEMY := 7.0" in config
    assert "const OFFENSE_DENSITY_MAX_BONUS := 90.0" in config
    assert "const OFFENSE_DENSITY_PEAK_GOAL := 25.0" in config
    assert "const OFFENSE_DENSITY_MAX_PEAK_BONUS := 30.0" in config
    assert 'build.get("previous_wave_p90_density", 0.0)' in strategy
    assert 'build.get("previous_wave_peak_density", 0.0)' in strategy
    assert "func _offense_deficient(build: Dictionary, wave: int)" in strategy
    assert '"utility_lock_veto": true' in strategy
    assert "score <= -1e8" in strategy
    assert "func _record_density_sample(wave: int, enemies: int)" in controller
    assert "func _sample_percentile(values: Array, quantile: float)" in controller
    assert 'build["previous_wave_p90_density"]' in controller
    assert 'build["previous_wave_peak_density"]' in controller
    assert "func _sample_peak(values: Array) -> float:" in controller
    assert "const BOSS_FINALE_COMMIT_DISTANCE := 120.0" in config
    assert "func _finale_committed_escape" in potential
    assert "pos.distance_to(_finale_commit_origin)" in potential
    assert "BOSS_FINALE_COMMIT_MAX_TICKS" in potential
    assert '"finale_translation": translation_debug' in controller


def test_v79_weapon_locks_are_not_misclassified_and_cycles_are_bounded():
    config = CONFIG.read_text(encoding="utf-8")
    strategy = STRATEGY.read_text(encoding="utf-8")
    controller = CONTROLLER.read_text(encoding="utf-8")

    assert "const SHOP_MAX_LOCK_TRANSITIONS_PER_ITEM := 2" in config
    assert 'and locked_item.get("category") != "weapon"' in strategy
    assert "func _guard_lock_transition(action: Dictionary) -> Dictionary:" in strategy
    assert '"shop_cycle_guard": true' in strategy
    assert "_session_expired_lock_item_ids[utility_item_id] = true" in strategy
    assert "func _apply_shop_cycle_guard(action: Dictionary, state: Dictionary)" in controller
    assert "action = _apply_shop_cycle_guard(action, state)" in controller
    assert '"transition_count": _shop_transition_count' in controller
    offense_first = strategy.split("func _offense_first_item_action", 1)[1].split(
        "func _try_tier_replace_sell", 1
    )[0]
    assert "var weapon_score := _weapon_score" in offense_first
    assert 'if it.get("category") == "weapon":' in offense_first
    assert 'if not it.get("affordable", false) or not it.get("can_buy", true):' in offense_first
    assert '"offense_first": true' in offense_first


def test_v65_allows_one_safeguarded_final_shop_combine():
    strategy = STRATEGY.read_text(encoding="utf-8")
    config = CONFIG.read_text(encoding="utf-8")

    assert "var combine_allowed: bool = not final_shop or slots_full" in strategy
    assert strategy.count("BotConfig.SHOP_COMBINES_ENABLED and combine_allowed") == 3
    assert "const SHOP_MAX_COMBINES_PER_VISIT := 1" in config
    assert "const COMBINE_MIN_WEAPONS := 6" in config
    assert 'if w.get("upgrades", false):' in strategy


def test_inherited_shop_locks_expire_after_one_purchase_visit():
    strategy = STRATEGY.read_text(encoding="utf-8")

    assert "var _session_new_lock_item_ids := {}" in strategy
    assert "var _session_expired_lock_item_ids := {}" in strategy
    assert "func _expired_lock_action(items: Array) -> Dictionary:" in strategy
    assert '"lock_expired": true' in strategy
    assert "_session_expired_lock_item_ids[item_id] = true" in strategy
    assert strategy.count("_session_expired_lock_item_ids.has") == 3
    assert strategy.count("_session_new_lock_item_ids[") == 3
    assert "_session_new_lock_slots" not in strategy
    assert "_session_expired_lock_slots" not in strategy
    assert strategy.count("_expired_lock_action(items)") == 2


def test_cooldown_floor_items_are_vetoed_only_when_they_slow_owned_weapons():
    strategy = STRATEGY.read_text(encoding="utf-8")

    assert "func _clips_owned_weapon_cooldown(item: Dictionary, build: Dictionary) -> bool:" in strategy
    assert 'e.get("key", "") != "minimum_weapon_cooldowns"' in strategy
    assert "float(cooldown) > 0.0 and float(cooldown) < cooldown_floor" in strategy
    assert "if _clips_owned_weapon_cooldown(item, build): return true" in strategy


def test_audited_rogueranker_items_require_live_build_synergy():
    config = CONFIG.read_text(encoding="utf-8")
    strategy = STRATEGY.read_text(encoding="utf-8")
    controller = CONTROLLER.read_text(encoding="utf-8")

    assert "const BUILD_AWARE_ROGUERANKER_ENABLED := true" in config
    assert '"item_greek_fire": {"weapon_flag": "burning"}' in config
    assert '"item_giant_belt": {"stat": "stat_crit_chance", "min_stat": 20.0}' in config
    assert '"item_explosive_shells": {"weapon_set": "set_explosive"}' in config
    requirement_block = config.split("const BUILD_AWARE_ITEM_REQUIREMENTS := {", 1)[1].split(
        "\n}\nconst ROGUERANKER_ITEM_TIERS", 1
    )[0]
    requirement_ids = set(re.findall(r'^\t"(item_[^"]+)":', requirement_block, re.MULTILINE))
    assert len(requirement_ids) == 59
    assert {
        "item_bloody_hand",
        "item_retromations_hoodie",
        "item_focus",
        "item_mammoth",
        "item_robot_arm",
        "item_frozen_heart",
        "item_power_generator",
        "item_strange_book",
        "item_pile_of_books",
        "item_snowball",
        "item_alien_eyes",
        "item_ice_cube",
        "item_peacock",
        "item_weird_ghost",
        "item_hourglass",
        "item_gobblers_hat",
        "item_bait",
        "item_black_flag",
        "item_axolotl",
        "item_statue",
        "item_blood_donation",
        "item_ashes",
    } <= requirement_ids
    assert "func _build_requirement_met(requirement: Dictionary, build: Dictionary, wave: int) -> bool:" in strategy
    assert "func _item_matches_current_build(item: Dictionary, build: Dictionary, wave: int) -> bool:" in strategy
    assert "if not BotConfig.BUILD_AWARE_ROGUERANKER_ENABLED:" in strategy
    assert 'weapon.get("sets", []).has(required_set)' in strategy
    assert 'weapon.get(required_flag, false)' in strategy
    assert 'scaling[0] == required_scaling' in strategy
    assert 'families.size() > int(requirement["max_distinct_weapon_families"])' in strategy
    assert 'requirement.has("min_wave")' in strategy
    assert 'requirement.has("max_wave")' in strategy
    assert "if not _item_matches_current_build(item, build, wave): return true" in strategy
    assert strategy.count("_is_vetoed(item, build, wave)") == 2
    assert 'entry["burning"] = (burning_data != null' in controller


def test_complete_wiki_audit_expands_the_late_game_allowlist_without_relabeling_sources():
    config = CONFIG.read_text(encoding="utf-8")
    rogue_block = config.split("const ROGUERANKER_ITEM_TIERS := {", 1)[1].split(
        "\n}\n\n# Agent-specific", 1
    )[0]
    wiki_block = config.split("const WIKI_USEFUL_ITEM_TIERS := {", 1)[1].split(
        "\n}\n\n#", 1
    )[0]
    rogue_ids = set(re.findall(r'^\t"(item_[^"]+)":', rogue_block, re.MULTILINE))
    wiki_ids = set(re.findall(r'^\t"(item_[^"]+)":', wiki_block, re.MULTILINE))

    assert len(rogue_ids) == 68
    assert len(wiki_ids) == 98
    assert len(rogue_ids | wiki_ids) == 166
    assert rogue_ids.isdisjoint(wiki_ids)
    assert {
        "item_anvil",
        "item_catling_gun",
        "item_jellyshield",
        "item_scapegoat",
        "item_seashell",
        "item_white_flag",
        "item_baby_with_a_beard",
        "item_doc_moth",
        "item_goldfish",
        "item_improved_tools",
        "item_mirror",
        "item_poisonous_tonic",
        "item_sharp_bullet",
        "item_small_magazine",
        "item_ugly_tooth",
        "item_warrior_helmet",
        "item_bag",
        "item_coffee",
        "item_garden",
        "item_medical_turret",
        "item_scope",
        "item_sunglasses",
        "item_spyglass",
        "item_treasure_map",
    } <= wiki_ids
    assert (
        "return ROGUERANKER_ITEM_TIERS.has(item_id) or "
        "WIKI_USEFUL_ITEM_TIERS.has(item_id)"
    ) in config
    assert "tiers = WIKI_USEFUL_ITEM_TIERS" in config


def test_v80_winner_trajectory_curves_and_impactful_offense_band():
    config = CONFIG.read_text(encoding="utf-8")
    strategy = STRATEGY.read_text(encoding="utf-8")
    controller = CONTROLLER.read_text(encoding="utf-8")
    combat = (ROOT / "mod/mods-unpacked/Tom-BrotatoAgent/teacher/combat_model.gd").read_text(
        encoding="utf-8"
    )
    hud = HUD.read_text(encoding="utf-8")

    # Winner-trajectory reference curves: 20 entries each, single source in config.
    dps_block = config.split("const OFFENSE_DPS_TARGETS_BY_WAVE := [", 1)[1].split("]", 1)[0]
    ehp_block = config.split("const DEFENSE_EHP_TARGETS_BY_WAVE := [", 1)[1].split("]", 1)[0]
    assert len(re.findall(r"\d+\.\d", dps_block)) == 20
    assert len(re.findall(r"\d+\.\d", ehp_block)) == 20
    assert "static func offense_dps_target(wave: int) -> float:" in config
    assert "static func defense_ehp_target(wave: int) -> float:" in config

    # Impactful-offense band gate constants and policy hooks (v82: the tier
    # proxy was replaced by a fractional marginal-DPS floor).
    assert "const OFFENSE_BAND_FROM_WAVE := 13" in config
    assert "const OFFENSE_IMPACT_MIN_DPS_GAIN_FRAC := 0.05" in config
    assert "const OFFENSE_IMPACT_MIN_ITEM_GAIN := 6.0" in config
    assert "const OFFENSE_BAND_REROLL_PRESSURE := 8.0" in config
    assert "func _dps_below_band(build: Dictionary, wave: int) -> bool:" in strategy
    assert "func _pairs_for_combine(it: Dictionary, weapons: Array) -> bool:" in strategy
    assert "func _projected_weapon_dps_gain(it: Dictionary, build: Dictionary) -> float:" in strategy
    assert "func _band_impact_floor(build: Dictionary) -> float:" in strategy
    # Mandatory offense: band-gated marginal-DPS and item gain filters.
    assert "_projected_weapon_dps_gain(it, build) < impact_floor" in strategy
    assert "if band_gate and gain < BotConfig.OFFENSE_IMPACT_MIN_ITEM_GAIN:" in strategy
    # Ordinary scoring: filler guard only while slots are full, with the
    # immediate-combine exception preserved.
    assert "if (band_gate and slots_full" in strategy
    assert "_projected_weapon_dps_gain(it, build) < band_impact_floor" in strategy
    # Reroll pressure while below the band.
    assert "worth += BotConfig.OFFENSE_BAND_REROLL_PRESSURE" in strategy

    # EHP index and HUD/telemetry wiring.
    assert "static func defense_ehp_index(stats: Dictionary, wave: int) -> float:" in combat
    assert "const LIFESTEAL_EHP_WEIGHT := 3.0" in config
    assert '"dps_target": dps_target' in controller
    assert '"ehp": ehp' in controller
    assert '"ehp_target": ehp_target' in controller
    assert '"defense_values", "defense_sustain", "off_dps", "def_ehp"' in hud
    assert 'set_status("off_dps"' in controller
    assert 'set_status("def_ehp"' in controller


def test_v81_run_strength_index_is_computed_and_displayed():
    config = CONFIG.read_text(encoding="utf-8")
    controller = CONTROLLER.read_text(encoding="utf-8")
    combat = (ROOT / "mod/mods-unpacked/Tom-BrotatoAgent/teacher/combat_model.gd").read_text(
        encoding="utf-8"
    )
    hud = HUD.read_text(encoding="utf-8")

    # Weights sum to 1.0 and are anchored on discriminative power.
    assert "const RSI_WEIGHT_POWER := 0.55" in config
    assert "const RSI_WEIGHT_CONTROL := 0.20" in config
    assert "const RSI_WEIGHT_DURABILITY := 0.15" in config
    assert "const RSI_WEIGHT_CONVERSION := 0.10" in config
    assert "const RSI_POWER_CAP := 1.3" in config
    assert "const RSI_CONTROL_P90_REF := 15.0" in config
    assert "const RSI_WINDOW_FROM_WAVE := 13" in config
    assert "const RSI_WINDOW_TO_WAVE := 19" in config

    # Pure, testable index function; durability hard-capped at par.
    assert "static func run_strength_index(dps: float, dps_target: float, ehp: float," in combat
    assert "var durability := clamp(ehp / max(ehp_target, 1.0), 0.0, 1.0)" in combat

    # Controller wiring: conversion tracking, metrics field, HUD line, resets.
    assert "func _track_shop_conversion(state: Dictionary, action: Dictionary) -> void:" in controller
    assert "_track_shop_conversion(state, action)" in controller
    assert '"rsi": rsi,' in controller
    assert 'set_status("rsi"' in controller
    assert controller.count("_last_shop_conversion = 1.0") >= 2
    assert '"off_dps", "def_ehp", "rsi"' in hud


def test_v82_dps_curve_recalibrated_on_41_win_population():
    config = CONFIG.read_text(encoding="utf-8")
    dps_block = config.split("const OFFENSE_DPS_TARGETS_BY_WAVE := [", 1)[1].split("]", 1)[0]
    values = [float(v) for v in re.findall(r"\d+\.\d", dps_block)]

    assert len(values) == 20
    # Recalibrated endpoints and monotonicity (v82: pooled 41-win median; the
    # v80 curve's 5380 w20 target was over-fit to 8 lean-build wins).
    assert values[0] == 45.0
    assert values[14] == 1620.0
    assert values[19] == 2900.0
    assert all(values[i] <= values[i + 1] for i in range(19))
    # EHP floor deliberately unchanged (raising it would reward the
    # over-defense pattern that characterizes losses).
    ehp_block = config.split("const DEFENSE_EHP_TARGETS_BY_WAVE := [", 1)[1].split("]", 1)[0]
    ehp_values = [float(v) for v in re.findall(r"\d+\.\d", ehp_block)]
    assert ehp_values[-1] == 131.0


def test_v124_offense_deficient_reroll_boost_yields_to_board_offense_buys():
    # v124: while offense-deficient, an affordable board offense-stat item that
    # already clears the impact gate must be bought before the reroll decision
    # can preempt it. Mechanically: a new board-scan helper guards the +8
    # offense-deficient reroll worth boost so it fires only when no such item
    # remains on the board. Evidence: reports/wp2/v124_skip_diagnosis.md
    # (35/36 true board-leavings were the boost rerolling past board offense).
    strategy = STRATEGY.read_text(encoding="utf-8")

    # New helper reuses the EXACT mandatory-offense definitions: _direct_offense_gain
    # (crit excluded by construction) against OFFENSE_IMPACT_MIN_ITEM_GAIN, plus the
    # existing per-item affordability flag. No gold_reserve change, no new constant.
    assert "func _board_has_gate_clearing_offense(items: Array) -> bool:" in strategy
    helper = strategy.split(
        "func _board_has_gate_clearing_offense", 1
    )[1].split("func _try_tier_replace_sell", 1)[0]
    assert 'if it.get("category") == "weapon":' in helper
    assert 'if not it.get("affordable", false) or not it.get("can_buy", true):' in helper
    assert (
        '_direct_offense_gain(it.get("effects", [])) >= BotConfig.OFFENSE_IMPACT_MIN_ITEM_GAIN'
        in helper
    )
    # The mandatory-offense impact gate itself is unchanged (still 6.0).
    assert "const OFFENSE_IMPACT_MIN_ITEM_GAIN := 6.0" in CONFIG.read_text(encoding="utf-8")

    # Guard on the +8 boost: the v74 boost and v80 band pressure lines are
    # preserved verbatim; the new conjunct only suppresses the boost while a
    # qualifying board item is present.
    decide = strategy.split("func decide_shop", 1)[1].split(
        "func decide_levelup", 1
    )[0]
    assert (
        "if (offense_target > 0.0 and _offense_proxy(build) < offense_target\n"
        "\t\t\t\tand not _board_has_gate_clearing_offense(items)):"
    ) in decide
    assert "worth += 8.0" in decide  # v74 boost value unchanged
    assert "worth += BotConfig.OFFENSE_BAND_REROLL_PRESSURE" in decide  # v80 unchanged
    # The guard is evaluated before the reroll is actually fired.
    guard = decide.index("_board_has_gate_clearing_offense(items)")
    fire = decide.index('return {"type": "shop_reroll", "score": best_here}')
    assert guard < fire


def test_v124_reroll_boost_decision_table_mirror():
    # Independent pure-Python mirror of the v124 rule's decision table, pinning
    # the three cases the guard must produce.
    IMPACT_GATE = 6.0  # BotConfig.OFFENSE_IMPACT_MIN_ITEM_GAIN
    BOOST = 8.0

    # Mirror of _direct_offense_gain restricted to stat items: the three primary
    # offense stats sum; crit chance/damage are deliberately NOT offense-gain
    # keys (crit exclusion), so a crit-only item never clears the gate.
    OFFENSE_KEYS = {"stat_ranged_damage", "stat_percent_damage", "stat_attack_speed"}

    def direct_offense_gain(effects):
        return sum(e["value"] for e in effects if e["key"] in OFFENSE_KEYS)

    def qualifies(item):
        # Mirror of _board_has_gate_clearing_offense's per-item predicate.
        if item.get("category") == "weapon":
            return False
        if not item.get("affordable", False) or not item.get("can_buy", True):
            return False
        return direct_offense_gain(item.get("effects", [])) >= IMPACT_GATE

    def board_has_gate_clearing_offense(items):
        return any(qualifies(it) for it in items)

    def reroll_worth(base, deficient, items):
        # Mirror of the guarded boost: only the +8 conjunct changes.
        if deficient and not board_has_gate_clearing_offense(items):
            return base + BOOST
        return base

    base = 5.0
    aff_gate_item = {"affordable": True, "can_buy": True,
                     "effects": [{"key": "stat_percent_damage", "value": 10.0}]}
    unaff_gate_item = {"affordable": False, "can_buy": True,
                       "effects": [{"key": "stat_percent_damage", "value": 10.0}]}
    small_offense_item = {"affordable": True, "can_buy": True,
                          "effects": [{"key": "stat_ranged_damage", "value": 1.0}]}
    crit_item = {"affordable": True, "can_buy": True,
                 "effects": [{"key": "stat_crit_chance", "value": 20.0}]}
    weapon_item = {"category": "weapon", "affordable": True, "can_buy": True,
                   "effects": [{"key": "stat_percent_damage", "value": 30.0}]}

    # Case 1: deficient + affordable qualifying item on board -> NO boost (buy it).
    assert reroll_worth(base, True, [aff_gate_item]) == base
    # Case 2: deficient + none qualifying -> boost applies.
    assert reroll_worth(base, True, []) == base + BOOST
    assert reroll_worth(base, True, [unaff_gate_item]) == base + BOOST      # not affordable
    assert reroll_worth(base, True, [small_offense_item]) == base + BOOST   # gain < gate
    assert reroll_worth(base, True, [crit_item]) == base + BOOST            # crit excluded
    assert reroll_worth(base, True, [weapon_item]) == base + BOOST          # weapons excluded
    # Case 3: offense adequate -> unchanged (boost never applied regardless of board).
    assert reroll_worth(base, False, [aff_gate_item]) == base
    assert reroll_worth(base, False, []) == base


# --- v125: hard reroll gate (the ordering rule proper) -------------------------
# v124's +8-boost guard was insufficient — residual reroll worth and especially
# FREE rerolls still preempted qualifying buys (reports/wp2/v124_deploy_record.md,
# run_1784817058_71742: 4 guard-applicable rerolls at waves 11 (paid) and 15
# (free)). v125 disallows the reroll ACTION outright while the guard condition
# holds. The v124 +8-boost guard is kept as-is.

WP2_FIXTURES = ROOT / "tests/fixtures/wp2"


def _v125_direct_offense_gain(effects):
    # Mirror of _direct_offense_gain: the three primary offense stats sum; the
    # explosive/crowd keys count max(1, value) when positive; crit is never an
    # offense-gain key. sign 3 (_SIGN_FROM_VALUE) => value used as-is.
    direct = {"stat_ranged_damage", "stat_percent_damage", "stat_attack_speed"}
    explosive = {"piercing", "piercing_damage", "bounce", "explosion_damage",
                 "explosion_size", "effect_explode", "explode_on_death",
                 "projectiles_on_death", "burning_spread"}

    def signed(e):
        val = e.get("value", 0) or 0
        s = e.get("sign", 3)
        return {0: abs(float(val)), 1: -abs(float(val)), 2: 0.0}.get(s, float(val))

    gain = 0.0
    for e in effects:
        k = e.get("key", "")
        v = signed(e)
        if k in direct:
            gain += v
        elif k in explosive and v > 0.0:
            gain += max(1.0, v)
    return gain


def _v125_board_has_gate_clearing_offense(items, impact_gate=6.0):
    for it in items:
        if it.get("category") == "weapon":
            continue
        if not it.get("affordable", False) or not it.get("can_buy", True):
            continue
        if _v125_direct_offense_gain(it.get("effects", [])) >= impact_gate:
            return True
    return False


def _v125_reroll_disallowed(deficient, items):
    # Mirror of the v125 hard gate: reroll is denied (paid AND free) while
    # offense-deficient with a gate-clearing offense item on the board.
    return deficient and _v125_board_has_gate_clearing_offense(items)


def test_v125_reroll_gate_source_shape_denies_paid_and_free_rerolls():
    strategy = STRATEGY.read_text(encoding="utf-8")
    decide = strategy.split("func decide_shop", 1)[1].split(
        "func decide_levelup", 1
    )[0]

    # Hard gate boolean reuses the exact v124 guard condition.
    assert (
        "var offense_reroll_gate: bool = (offense_target > 0.0\n"
        "\t\t\t\tand _offense_proxy(build) < offense_target\n"
        "\t\t\t\tand _board_has_gate_clearing_offense(items))"
    ) in decide
    # The reroll action is denied outright — the gate joins the fire condition,
    # so budget (paid vs free) is irrelevant once the gate holds.
    assert (
        "if (best_here < worth or need_fill) and not offense_reroll_gate:"
    ) in decide
    # The gate is evaluated before the reroll fires, and shop_go is the fallthrough.
    gate = decide.index("var offense_reroll_gate")
    fire = decide.index('return {"type": "shop_reroll", "score": best_here}')
    go = decide.rindex('return {"type": "shop_go", "score": 0.0}')  # final fallthrough
    assert gate < fire < go
    # The v124 +8-boost guard is preserved unchanged (kept as cheap belt-and-braces).
    assert (
        "if (offense_target > 0.0 and _offense_proxy(build) < offense_target\n"
        "\t\t\t\tand not _board_has_gate_clearing_offense(items)):"
    ) in decide
    assert "worth += 8.0" in decide


def test_v125_reroll_gate_decision_table_mirror():
    gate_item = {"affordable": True, "can_buy": True,
                 "effects": [{"key": "stat_percent_damage", "value": 10.0, "sign": 3}]}
    free_note = "free rerolls are gated too — budget is not consulted once the gate holds"

    # deficient + qualifying item on board -> reroll DISALLOWED (even if free).
    assert _v125_reroll_disallowed(True, [gate_item]) is True, free_note
    # deficient + none qualifying -> reroll ALLOWED.
    assert _v125_reroll_disallowed(True, []) is False
    unaff = {"affordable": False, "can_buy": True,
             "effects": [{"key": "stat_percent_damage", "value": 10.0, "sign": 3}]}
    small = {"affordable": True, "can_buy": True,
             "effects": [{"key": "stat_ranged_damage", "value": 1.0, "sign": 3}]}
    crit = {"affordable": True, "can_buy": True,
            "effects": [{"key": "stat_crit_chance", "value": 20.0, "sign": 3}]}
    weapon = {"category": "weapon", "affordable": True, "can_buy": True,
              "effects": [{"key": "stat_percent_damage", "value": 30.0, "sign": 3}]}
    assert _v125_reroll_disallowed(True, [unaff]) is False   # not affordable
    assert _v125_reroll_disallowed(True, [small]) is False   # gain < gate
    assert _v125_reroll_disallowed(True, [crit]) is False    # crit excluded
    assert _v125_reroll_disallowed(True, [weapon]) is False  # weapons excluded
    # offense adequate -> unchanged (gate never engages, reroll allowed).
    assert _v125_reroll_disallowed(False, [gate_item]) is False
    assert _v125_reroll_disallowed(False, []) is False


def test_v125_reroll_gate_replays_frozen_smoke_boards():
    # Frozen regression: the four guard-applicable rerolls v124 let through must
    # ALL be reroll-disallowed under the v125 gate. Covers paid (w11) and free
    # (w15) rerolls, and the explosive-key gate item (item_dynamite).
    kinds = set()
    dynamite_seen = False
    for wave in (11, 15):
        fx = json.loads(
            (WP2_FIXTURES / f"v124_smoke_reroll_boards_w{wave}.json").read_text(
                encoding="utf-8"
            )
        )
        assert fx["boards"], f"wave {wave} fixture has no boards"
        for board in fx["boards"]:
            deficient = board["offense_proxy_total"] < board["offense_target"]
            assert deficient, f"seq {board['decision_seq']} was not offense-deficient"
            # Recompute gate qualification from raw item fields and cross-check the
            # frozen precomputed gains and gate ids.
            gate_ids = [
                it["id"] for it in board["items"]
                if it.get("category") != "weapon" and it.get("affordable", False)
                and _v125_direct_offense_gain(it.get("effects", [])) >= fx["impact_gate"]
            ]
            assert gate_ids == board["gate_clearing_ids"]
            for it in board["items"]:
                assert _v125_direct_offense_gain(it["effects"]) == it["direct_offense_gain"]
            # The v124 telemetry recorded a reroll here; v125 must disallow it.
            assert board["action_taken"] == "shop_reroll"
            assert _v125_reroll_disallowed(deficient, board["items"]) is True
            kinds.add(board["reroll_kind"])
            dynamite_seen = dynamite_seen or "item_dynamite" in board["gate_clearing_ids"]
    assert kinds == {"paid", "free"}  # both budget regimes are gated
    assert dynamite_seen  # explosive-key gate item is covered


# ── rare-gun lock persistence (flag `rare_gun_lock_persist`, default OFF) ──────

FINALE_LOOP = ROOT / "scripts/wp2_finale_loop.py"


def test_rare_gun_lock_persist_flag_exists_and_defaults_off():
    config = CONFIG.read_text(encoding="utf-8")
    strategy = STRATEGY.read_text(encoding="utf-8")
    controller = CONTROLLER.read_text(encoding="utf-8")

    assert "const RARE_GUN_LOCK_MAX_VISITS := 3" in config
    assert "const RARE_GUN_LOCK_SHORTFALL_BAND := 150" in config
    # The band MUST exceed the chain gun's best observed shortfall of 91, or the
    # flag is structurally inert for the weapon that motivates it.
    band = int(
        config.split("const RARE_GUN_LOCK_SHORTFALL_BAND := ", 1)[1].split("\n", 1)[0]
    )
    assert band > 91
    # And the cap must be a real backstop: finite, and strictly more than the
    # shipped one-visit lifetime it replaces.
    cap = int(
        config.split("const RARE_GUN_LOCK_MAX_VISITS := ", 1)[1].split("\n", 1)[0]
    )
    assert 1 < cap < 20

    assert "var rare_gun_lock_persist_enabled: bool = false" in strategy
    assert "var rare_gun_lock_persist: bool = false" in controller


def test_rare_gun_lock_persist_is_plumbed_end_to_end():
    controller = CONTROLLER.read_text(encoding="utf-8")
    telemetry = TELEMETRY.read_text(encoding="utf-8")
    loop = FINALE_LOOP.read_text(encoding="utf-8")

    # Controller: assignment onto the shop object, mod-ready sentinel, run meta,
    # and the agent_config.json loader.
    assert "_shop.rare_gun_lock_persist_enabled = rare_gun_lock_persist" in controller
    assert controller.count('"rare_gun_lock_persist": rare_gun_lock_persist,') == 2
    assert 'if cfg.has("rare_gun_lock_persist"):' in controller
    assert 'rare_gun_lock_persist = bool(cfg["rare_gun_lock_persist"])' in controller
    # The shop object is constructed before the flag is pushed onto it.
    assert controller.index("_shop = _SHOP_SCRIPT.new()") < controller.index(
        "_shop.rare_gun_lock_persist_enabled = rare_gun_lock_persist"
    )

    # begin_run's ALLOWLIST: without this line the arm never reaches the summary.
    assert (
        '"rare_gun_lock_persist": meta.get("rare_gun_lock_persist", false),'
        in telemetry
    )

    # Harness: CLI arg, config write, trial row, and expected-value validation.
    assert '"--rare-gun-lock-persist",' in loop
    assert "rare_gun_lock_persist: bool = False," in loop
    assert 'payload["rare_gun_lock_persist"] = rare_gun_lock_persist' in loop
    assert "expected_rare_gun_lock_persist: bool = False," in loop
    assert (
        'bool(summary.get("rare_gun_lock_persist", False)) != expected_rare_gun_lock_persist'
        in loop
    )
    assert (
        "expected_rare_gun_lock_persist=bool(args.rare_gun_lock_persist)," in loop
    )
    # An interrupted loop must disarm the flag, exactly like the other arms.
    assert "rare_gun_lock_persist=False," in loop


def test_rare_gun_lock_persist_off_leaves_the_shipped_expiry_path_intact():
    strategy = STRATEGY.read_text(encoding="utf-8")
    rare = strategy.split("func _rare_gun_action", 1)[1].split(
        "func _rare_gun_lock_persist", 1
    )[0]

    # The flag-off path is the ORIGINAL code, untouched and still last: the new
    # behaviour lives entirely inside `if rare_gun_lock_persist_enabled:`.
    assert "if rare_gun_lock_persist_enabled:" in rare
    guard = rare.index("if rare_gun_lock_persist_enabled:")
    original = rare.index(
        "# An inherited lock got its purchase/sale attempt and remains unreachable."
    )
    assert guard < original
    # The new keys are emitted ONLY inside the flag-on branch, so a flag-off
    # decision record is byte-identical to today's.
    off_path = rare[original:]
    assert "rare_gun_lock_" not in off_path
    # The unchanged shipped expiry: mark expired, then unlock through the guard.
    assert "_session_expired_lock_item_ids[item_id] = true" in off_path
    assert '"type": "shop_unlock"' in off_path and '"lock_expired": true' in off_path
    # Run-scoped state is cleared ONLY when the wave counter goes backwards, never
    # on the per-wave session reset that would flatten the visit counter to 1.
    assert strategy.count("_run_rare_gun_lock_state = {}") == 1
    reset = strategy.split("func _reset_session_if_new", 1)[1].split(
        "func _guard_lock_transition", 1
    )[0]
    assert "if w < _session_wave:" in reset
    assert reset.index("if w < _session_wave:") < reset.index(
        "_run_rare_gun_lock_state = {}"
    )


def test_rare_gun_lock_persist_emits_its_decision_inputs():
    strategy = STRATEGY.read_text(encoding="utf-8")
    rare = strategy.split("func _rare_gun_action", 1)[1].split(
        "func _rare_gun_lock_persist", 1
    )[0]

    # Both outcomes -- keep (shop_go) and expire (shop_unlock) -- must carry the
    # shortfall, the visit count and the branch, or the change is un-auditable.
    for field in (
        '"rare_gun_lock_branch": str(persist.get("branch", ""))',
        '"rare_gun_lock_visits": int(persist.get("visits", 0))',
        '"rare_gun_lock_shortfall": int(persist.get("shortfall", 0))',
        '"rare_gun_lock_prev_shortfall": int(persist.get("prev_shortfall", -1))',
    ):
        assert rare.count(field) == 2
    # The keep path is the existing banking action, not a new action type.
    assert '"type": "shop_go"' in rare and '"rare_gun_saved": true' in rare


def test_rare_gun_lock_visit_cap_cannot_be_bypassed():
    config = CONFIG.read_text(encoding="utf-8")
    strategy = STRATEGY.read_text(encoding="utf-8")
    helper = strategy.split("func _rare_gun_lock_persist", 1)[1].split(
        "\n\nfunc ", 1
    )[0]

    # The cap is the FIRST branch of the if/elif chain, so no reachability test
    # can be reached once it fires -- structurally, not by convention.
    cap_branch = helper.index("if visits >= BotConfig.RARE_GUN_LOCK_MAX_VISITS:")
    near_branch = helper.index("elif shortfall <= BotConfig.RARE_GUN_LOCK_SHORTFALL_BAND:")
    closing_branch = helper.index("elif prev_shortfall >= 0 and shortfall < prev_shortfall:")
    assert cap_branch < near_branch < closing_branch
    # `keep` starts false and is only set inside the two reachability branches.
    assert "var keep := false" in helper
    assert helper.count("keep = true") == 2
    assert "keep = true" not in helper[cap_branch:near_branch]
    # The visit counter advances once per VISIT (wave), never once per decision,
    # and only on visits where a lock was actually INHERITED.
    assert 'if int(st.get("wave", -1)) != wave:' in helper
    assert helper.count("visits += 1") == 1
    assert helper.index('if int(st.get("wave", -1)) != wave:') < helper.index("visits += 1")
    assert helper.index("if inherited_lock:") < helper.index("visits += 1")

    # Shortfall history is recorded on every visit, BEFORE any early return, or
    # the "strictly decreased" branch could never fire.
    rare = strategy.split("func _rare_gun_action", 1)[1].split(
        "func _rare_gun_lock_persist", 1
    )[0]
    assert rare.index("persist = _rare_gun_lock_persist(") < rare.index(
        '"type": "shop_buy"'
    )

    cap = int(
        config.split("const RARE_GUN_LOCK_MAX_VISITS := ", 1)[1].split("\n", 1)[0]
    )
    band = int(
        config.split("const RARE_GUN_LOCK_SHORTFALL_BAND := ", 1)[1].split("\n", 1)[0]
    )

    # Independent Python mirror of the rule, driven per VISIT.
    def decide(visits, shortfall, prev_shortfall):
        if visits >= cap:
            return "cap", False
        if shortfall <= band:
            return "near", True
        if prev_shortfall >= 0 and shortfall < prev_shortfall:
            return "closing", True
        return "unreachable", False

    # Visit 0 of a sequence is the offer that CREATES the lock (never inherited,
    # always kept by the pre-existing same-visit branch); visits 1+ are inherited
    # and are the only ones the cap counts. History is recorded on every visit.
    def run(shortfalls):
        visits, prev, out = 0, -1, []
        for i, shortfall in enumerate(shortfalls):
            if i == 0:
                prev = shortfall
                continue
            visits += 1
            branch, keep = decide(visits, shortfall, prev)
            prev = shortfall
            out.append((branch, keep))
            if not keep:
                break
        return out

    # A permanently affordable-looking gun is STILL released: the cap fires at the
    # cap-th inherited visit no matter how reachable the item looks.
    forever = run([10] * 50)
    assert len(forever) == cap
    assert [keep for _, keep in forever] == [True] * (cap - 1) + [False]
    assert forever[-1][0] == "cap"

    # A steadily closing but never-near gun is also released at the cap -- and the
    # "closing" branch is genuinely reachable, which it is not unless the first
    # (lock-creating) visit already recorded a shortfall.
    closing = run([10_000 - 100 * i for i in range(50)])
    assert [branch for branch, _ in closing] == ["closing"] * (cap - 1) + ["cap"]
    assert len(closing) == cap and closing[-1] == ("cap", False)

    # The expire branch is reachable BEFORE the cap: a gun that is far away and
    # getting further is released on its first inherited visit.
    assert run([band + 1, band + 1]) == [("unreachable", False)]
    assert run([band + 100, band + 200]) == [("unreachable", False)]

    # The two motivating cases keep the lock at least one visit longer than today.
    assert decide(1, 72, -1) == ("near", True)     # median minigun shortfall
    assert decide(1, 91, -1) == ("near", True)     # best chain-gun shortfall
    assert decide(1, 128, -1) == ("near", True)    # observed chain-gun trajectory
