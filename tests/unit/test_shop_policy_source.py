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


def test_wp2_capture_build_versions_the_v93_wall_safety_policy():
    manifest = MANIFEST.read_text(encoding="utf-8")
    controller = CONTROLLER.read_text(encoding="utf-8")
    telemetry = TELEMETRY.read_text(encoding="utf-8")

    assert '"version_number": "0.2.1"' in manifest
    assert controller.count("teacher_v1-0.1.93-gun-wp1") == 1
    assert controller.count("0.2.1-wp2-capture") == 1
    assert telemetry.count("teacher_v1-0.1.93-gun-wp1") == 1
    assert telemetry.count("0.2.1-wp2-capture") == 1


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


def test_v85_wave20_uses_dedicated_finale_instead_of_generic_low_hp_flee():
    potential = POTENTIAL_FIELD.read_text(encoding="utf-8")
    survival_guard = potential.split(
        "if (wave >= BotConfig.LATE_SURVIVAL_WAVE", 1
    )[1].split(
        "var finale = wave >= BotConfig.BOSS_FINALE_WAVE", 1
    )[0]

    assert "and wave < BotConfig.BOSS_FINALE_WAVE" in survival_guard
    assert "return _prev_move" in survival_guard
    assert "_boss_finale_desire" not in survival_guard
    assert "desire = _boss_finale_desire" in potential
    assert "_projectile_escape" in potential
    assert "_finale_committed_escape" in potential


def test_v92_finale_tightens_the_ring_and_bypasses_commitment_before_contact():
    config = CONFIG.read_text(encoding="utf-8")
    potential = POTENTIAL_FIELD.read_text(encoding="utf-8")
    adapter = ADAPTER.read_text(encoding="utf-8")
    controller = CONTROLLER.read_text(encoding="utf-8")

    assert "const BOSS_FINALE_RECOVERY_RANGE_FRAC := 0.82" in config
    assert "const BOSS_FINALE_RECOVERY_RING_DEADBAND := 50.0" in config
    assert "const BOSS_FINALE_RECOVERY_RADIAL_GAIN := 1.75" in config
    assert "const BOSS_FINALE_RECOVERY_TANGENT_GAIN := 1.85" in config
    assert "const BOSS_FINALE_CRITICAL_HP_RATIO := 0.50" in config
    assert "const BOSS_FINALE_CRITICAL_TANGENT_MULT := 1.35" in config
    assert "const BOSS_FINALE_CONTACT_ESCAPE_DISTANCE := 420.0" in config
    assert "if (hp_ratio <= BotConfig.LATE_SURVIVAL_HP_RATIO" in potential
    assert "var finale_survival = _panic_dodge(" in potential
    assert "finale_survival = _pure_repulsion_flee(" in potential
    assert "desire = _boss_finale_recovery_desire(" in potential
    assert "func _boss_finale_recovery_desire(" in potential
    assert "survival_desire - radial * survival_desire.dot(radial)" in potential
    assert "distance - ideal" in potential
    assert "BOSS_FINALE_RECOVERY_RING_DEADBAND" in potential
    assert "if hp_ratio <= BotConfig.BOSS_FINALE_CRITICAL_HP_RATIO:" in potential
    projectile_blend = potential.index("combined = _normalize(combined)")
    post_escape_projection = potential.index(
        "combined = _boss_finale_recovery_desire(", projectile_blend
    )
    reversal_guard = potential.index(
        "combined = _finale_turn_without_reversal", projectile_blend
    )
    assert projectile_blend < post_escape_projection < reversal_guard
    assert "pos, bosses, weapons, arena, desire, combined, hp_ratio" in potential
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
    assert "const BOSS_FINALE_WALL_RECOVERY_RELEASE := 420.0" in config
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
        "func _finale_committed_escape", 1
    )[0]
    assert "if _finale_wall_recovery_active:" in safety
    assert "wall_distance >= BotConfig.BOSS_FINALE_WALL_RECOVERY_RELEASE" in safety
    assert "wall_distance <= BotConfig.BOSS_FINALE_WALL_RECOVERY_ENTER" in safety
    assert safety.rstrip().endswith(
        "return _clamp_finale_wall_components(pos, safe_desire, arena)"
    )

    hard_projection = potential.split("func _clamp_finale_wall_components", 1)[1].split(
        "func _finale_lane_score", 1
    )[0]
    assert "if pos.x <= margin and out.x < 0.0:" in hard_projection
    assert "elif pos.x >= w - margin and out.x > 0.0:" in hard_projection
    assert "if pos.y <= margin and out.y < 0.0:" in hard_projection
    assert "elif pos.y >= h - margin and out.y > 0.0:" in hard_projection
    assert '"wall_recovery_active": _finale_wall_recovery_active' in potential


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
    assert "const BOSS_FINALE_STRAFE_SWITCH_MARGIN := 1.00" in config
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
