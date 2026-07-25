extends Reference
class_name BotShopStrategy

# Shop / level-up / crate decision engine — port of shop_strategy.py.
# Returns one action Dictionary or {} (caller throttles).

# Preload sibling scripts so we can refer to them without relying on the
# class_name registry being ready at parse time (mod zips parse before
# ModLoader injects class_name entries).
const BotConfig := preload("res://mods-unpacked/Tom-BrotatoAgent/teacher/config.gd")
const BotCombatModel := preload("res://mods-unpacked/Tom-BrotatoAgent/teacher/combat_model.gd")

# Tier→bonus (matches _TIER_BONUS in Python).
const _TIER_BONUS := [0.0, 1.0, 2.5, 5.0, 7.0, 10.0, 14.0]
const _SIGN_POSITIVE := 0
const _SIGN_NEGATIVE := 1
const _SIGN_NEUTRAL := 2
const _SIGN_FROM_VALUE := 3
const _COMBAT_STATS := [
	"stat_percent_damage", "stat_ranged_damage", "stat_melee_damage",
	"stat_elemental_damage", "stat_damage", "stat_attack_speed",
	"stat_crit_chance", "stat_crit_damage", "stat_max_hp", "stat_armor",
	"stat_dodge", "stat_hp_regeneration", "stat_speed",
]
const _DMG_TYPES := ["stat_ranged_damage", "stat_melee_damage", "stat_elemental_damage"]
const _FREEZE_KEYS := ["hp_cap", "speed_cap", "dodge_cap"]

# Per-shop-visit state. Resets each wave.
var _session_wave: int = -1
var _session_rerolls: int = 0
var _session_surplus_rerolls: int = 0
var _session_combines: int = 0
var _session_sold_families := {}
var _session_new_lock_item_ids := {}
var _session_expired_lock_item_ids := {}
var _session_lock_transition_counts := {}
var _session_cycle_blocked_item_ids := {}


# ────────────────────────────── value helpers ─────────────────────────────────

func _tier_bonus(profile, tier: int) -> float:
	var base: float = _TIER_BONUS[tier] if tier >= 0 and tier < _TIER_BONUS.size() else 0.0
	return base * (profile.tier_bonus / 4.0)


func _effect_signed_value(e: Dictionary) -> float:
	var val = e.get("value", 0)
	if val == null: val = 0
	var eff_sign = e.get("sign", _SIGN_FROM_VALUE)
	if eff_sign == _SIGN_POSITIVE: return abs(float(val))
	if eff_sign == _SIGN_NEGATIVE: return -abs(float(val))
	if eff_sign == _SIGN_NEUTRAL: return 0.0
	return float(val)


func _stat_float(stats: Dictionary, key: String) -> float:
	# GDScript's boolean `or` returns a bool, not the original numeric operand.
	# Keep live stat magnitudes intact for offense floors and defense hard caps.
	var value = stats.get(key, 0)
	return 0.0 if value == null else float(value)


func _combat_deltas(effects: Array) -> Dictionary:
	var d := {}
	for e in effects:
		var key = e.get("key", "")
		if _COMBAT_STATS.has(key):
			d[key] = d.get(key, 0.0) + _effect_signed_value(e)
	return d


func _utility_score(effects: Array, wave: int, profile) -> float:
	var overrides: Dictionary = profile.utility_overrides if profile else {}
	var weights := BotConfig.utility_weights()
	var score := 0.0
	for e in effects:
		var key = e.get("key", "")
		if _COMBAT_STATS.has(key) and not overrides.has(key):
			continue
		var w: float
		if overrides.has(key):
			w = overrides[key]
		elif weights.has(key):
			w = weights[key]
		else:
			w = BotConfig.UNKNOWN_EFFECT_WEIGHT
		if key == "stat_harvesting" or key == "harvesting_growth":
			# Economy is early/mid; nearly ignore harvest in the late pivot.
			if wave >= BotConfig.LATE_SHOP_WAVE:
				w *= 0.10
			elif wave >= BotConfig.MID_SHOP_PIVOT_WAVE:
				w *= 0.40
			else:
				w *= max(0.35, (BotConfig.HARVESTING_DEADLINE_WAVE - wave) / BotConfig.HARVESTING_DEADLINE_WAVE)
		elif key == "stat_lifesteal":
			# Keep LS valuable; even more important into elites/bosses.
			if wave >= BotConfig.LATE_SHOP_WAVE:
				w *= 2.35
			elif wave >= BotConfig.MID_SHOP_PIVOT_WAVE:
				w *= 1.90
			elif wave <= 14:
				w *= 1.75
			else:
				w *= 1.25
		elif key == "stat_luck":
			if wave >= BotConfig.LATE_SHOP_WAVE:
				w *= 0.20
			elif wave >= BotConfig.MID_SHOP_PIVOT_WAVE:
				w *= 0.55
			elif wave <= 12:
				w *= 1.35
		elif (key == "number_of_enemies" or key == "extra_enemies_next_wave"
				or key == "extra_loot_aliens_next_wave" or key == "gold_drops"
				or key == "chance_double_gold"):
			if wave >= BotConfig.LATE_SHOP_WAVE:
				w *= 0.15
			elif wave >= BotConfig.MID_SHOP_PIVOT_WAVE:
				w *= 0.50
		elif key == "piercing" or key == "piercing_damage" or key == "bounce":
			if wave >= BotConfig.LATE_SHOP_WAVE:
				w *= 1.90
			elif wave >= BotConfig.MID_SHOP_PIVOT_WAVE:
				w *= 1.40
		elif (key == "explosion_damage" or key == "explosion_size"
				or key == "effect_explode" or key == "explode_on_death"
				or key == "projectiles_on_death" or key == "burning_spread"):
			if wave >= BotConfig.LATE_SHOP_WAVE:
				w *= 2.25
			elif wave >= BotConfig.MID_SHOP_PIVOT_WAVE:
				w *= 1.55
		elif key == "damage_against_bosses":
			if wave >= BotConfig.FINAL_SHOP_WAVE:
				w *= 2.2
			elif wave >= BotConfig.LATE_SHOP_WAVE:
				w *= 0.25
			elif wave >= BotConfig.MID_SHOP_PIVOT_WAVE:
				w *= 0.60
		elif key == "stat_max_hp" or key == "stat_armor" or key == "stat_dodge":
			if wave >= BotConfig.LATE_SHOP_WAVE:
				w *= 1.45
			elif wave >= BotConfig.MID_SHOP_PIVOT_WAVE:
				w *= 1.25
		elif key == "stat_ranged_damage" or key == "stat_attack_speed":
			if wave >= BotConfig.LATE_SHOP_WAVE:
				w *= 1.55
			elif wave >= BotConfig.MID_SHOP_PIVOT_WAVE:
				w *= 1.30
		score += w * _effect_signed_value(e)
	return score


func _effects_value(effects: Array, build: Dictionary, wave: int, profile) -> float:
	if effects.empty():
		return 0.0
	var combat := BotCombatModel.combat_value(build, _combat_deltas(effects), wave, profile)
	return combat + _utility_score(effects, wave, profile)


func _tag_score(tags: Array, profile, wave: int = 1) -> float:
	var overrides: Dictionary = profile.tag_bonus_overrides if profile else {}
	var weights := BotConfig.utility_weights()
	var late = wave >= BotConfig.LATE_SHOP_WAVE
	var mid = wave >= BotConfig.MID_SHOP_PIVOT_WAVE
	var score := 0.0
	for t in tags:
		var tag_add := 0.0
		if profile.wanted_tags.has(t):
			tag_add += BotConfig.TAG_WANTED_BONUS
		if weights.has(t):
			tag_add += weights[t] * BotConfig.TAG_STAT_VALUE
		if overrides.has(t):
			tag_add += overrides[t]
		# Mid/late pivot: economy / swarm tags stop dominating.
		if late and (t == "stat_harvesting" or t == "stat_luck" or t == "more_enemies" or t == "economy"):
			tag_add *= 0.12
		elif mid and (t == "stat_harvesting" or t == "stat_luck" or t == "more_enemies" or t == "economy"):
			tag_add *= 0.45
		elif late and (t == "stat_ranged_damage" or t == "stat_attack_speed" or t == "stat_lifesteal"
				or t == "stat_max_hp" or t == "stat_armor" or t == "stat_dodge" or t == "stat_crit_chance"):
			tag_add *= 1.65
		elif mid and (t == "stat_ranged_damage" or t == "stat_attack_speed" or t == "stat_lifesteal"
				or t == "stat_max_hp" or t == "stat_armor" or t == "stat_dodge"):
			tag_add *= 1.30
		score += tag_add
	return score


# ─────────────────────────── weapon valuation ─────────────────────────────────

func _live_damage_types(build: Dictionary) -> Array:
	var totals := {}
	for w in build.get("weapons", []):
		for s in w.get("scaling", []):
			if typeof(s) == TYPE_ARRAY and s.size() >= 2 and _DMG_TYPES.has(s[0]):
				totals[s[0]] = totals.get(s[0], 0.0) + s[1]
	if not totals.empty():
		var peak: float = 0.0
		for v in totals.values():
			if v > peak:
				peak = v
		var out := []
		for k in totals:
			if totals[k] >= 0.25 * peak:
				out.append(k)
		return out
	var gm: Dictionary = build.get("gain_mods", {})
	var live := []
	for k in _DMG_TYPES:
		if gm.get(k, 0) > 0:
			live.append(k)
	return live if not live.empty() else _DMG_TYPES.duplicate()


func _is_off_build(w: Dictionary, build: Dictionary) -> bool:
	var scaling_types := []
	for s in w.get("scaling", []):
		if typeof(s) == TYPE_ARRAY and s.size() >= 2 and _DMG_TYPES.has(s[0]):
			if not scaling_types.has(s[0]): scaling_types.append(s[0])
	if scaling_types.empty(): return false
	var live = _live_damage_types(build)
	for st in scaling_types:
		if live.has(st):
			return false
	return true


func _set_synergy(sets: Array, owned_weapons: Array, profile) -> float:
	var owned_sets := []
	for w in owned_weapons:
		for s in w.get("sets", []):
			owned_sets.append(s)
	var seen := {}
	var val := 0.0
	for s in sets:
		if seen.has(s): continue
		seen[s] = true
		if profile.preferred_sets.has(s): val += profile.set_synergy * 0.5
		var cnt := 0
		for o in owned_sets:
			if o == s:
				cnt += 1
		val += profile.set_synergy * 0.35 * cnt
	return val


func _weapon_value(item: Dictionary, build: Dictionary, profile, owned_for_synergy: Array, wave: int = 1) -> float:
	var wtype: String = item.get("type", item.get("weapon_type", "ranged"))
	if wtype == "melee" and not profile.allow_melee: return -1e9
	if wtype == "ranged" and not profile.allow_ranged: return -1e9
	if profile.no_weapons: return -1e9
	if not _weapon_matches_allowlist(item, profile, owned_for_synergy): return -1e9

	var stats: Dictionary = build.get("stats", {})
	var weapons: Array = build.get("weapons", [])
	var total: float = BotCombatModel.total_dps(weapons, stats)
	var dps: float = BotCombatModel.weapon_dps(item, stats)
	var score: float = (BotConfig.DPS_PRIORITY * 100.0 * dps / total) if total > 0 else (BotConfig.DPS_PRIORITY * 25.0)

	if _is_off_build(item, build): score -= BotConfig.OFF_BUILD_PENALTY
	if item.get("is_healing", false): score -= BotConfig.HEALING_WEAPON_PENALTY
	score += _tier_bonus(profile, item.get("tier", 0))
	score += _set_synergy(item.get("sets", []), owned_for_synergy, profile)
	# Soft-prefer chain / SMG / DB over other guns (any gun still allowed except bans).
	if BotConfig.EXPERIMENT_ANY_GUNS and wave >= BotConfig.EXPERIMENT_WEAPON_PRIORITY_FROM_WAVE:
		var wid = item.get("weapon_id")
		var prio: Array = BotConfig.EXPERIMENT_WEAPON_PRIORITY_IDS
		var bonuses: Array = BotConfig.EXPERIMENT_WEAPON_PRIORITY_BONUSES
		var pi := prio.find(wid)
		if pi >= 0 and pi < bonuses.size():
			score += float(bonuses[pi])
		elif not BotConfig.EXPERIMENT_PRIORITY_WEAPONS_ONLY:
			score -= BotConfig.EXPERIMENT_NON_PRIORITY_WEAPON_PENALTY
			var owned_family := false
			for w in owned_for_synergy:
				if w.get("weapon_id") == wid:
					owned_family = true
					break
			if not owned_family and owned_for_synergy.size() >= 3:
				score -= BotConfig.EXPERIMENT_NEW_TRASH_FAMILY_PENALTY
	if wtype == "melee": score -= 3.0
	return score


func _weapon_score(item: Dictionary, build: Dictionary, profile, wave: int = 1) -> float:
	var weapons: Array = build.get("weapons", [])
	var slots: int = build.get("weapon_slots", 6)
	var slots_full: bool = weapons.size() >= slots
	var same_id_owned := false
	var family = item.get("weapon_id")
	var family_t1 := 0
	var family_count := 0
	for w in weapons:
		if w.get("id") == item.get("id"):
			same_id_owned = true
		if family != null and w.get("weapon_id") == family:
			family_count += 1
			if int(w.get("tier", 0)) <= 0:
				family_t1 += 1
	if same_id_owned and slots_full and not profile.auto_combine:
		return -1e9
	var score = _weapon_value(item, build, profile, weapons, wave)
	var tier = int(item.get("tier", 0))
	# Prefer T2+ copies; stop flooding the board with extra T1 bases.
	if tier <= 0:
		if family_t1 >= BotConfig.T1_WEAPON_SOFT_CAP and weapons.size() >= BotConfig.COMBINE_MIN_WEAPONS:
			# Allow combine path (same exact id while slots full), else penalize hard.
			if not (slots_full and same_id_owned and item.get("upgrades", false)):
				score -= BotConfig.T1_WEAPON_PENALTY
		elif family_count >= 3 and not (slots_full and same_id_owned):
			score -= BotConfig.T1_WEAPON_PENALTY * 0.65
		# While we still have mergeable duplicates, don't buy more base guns.
		if _has_combinable(weapons) and BotConfig.EXPERIMENT_ANY_GUNS:
			score -= BotConfig.T1_WEAPON_PENALTY * 1.25
	else:
		score += BotConfig.T2_PLUS_WEAPON_BONUS * float(tier)
		# Strongly chase purple/red shop weapons so we fill with maxed guns.
		if tier >= 3:
			score += BotConfig.MAX_TIER_WEAPON_BONUS
		elif tier >= 2:
			score += BotConfig.HIGH_TIER_WEAPON_BONUS
	if item.get("upgrades", false) and same_id_owned:
		score += profile.combine_bonus
	# Matching an owned family at same tier feeds the combine ladder.
	if same_id_owned and profile.auto_combine:
		score += profile.combine_bonus * 0.75
	return score


func _owned_weapon_value(w: Dictionary, build: Dictionary, profile, wave: int = 1) -> float:
	var others := []
	for x in build.get("weapons", []):
		if x != w: others.append(x)
	return _weapon_value(w, build, profile, others, wave)


# ─────────────────────────── item-level helpers ───────────────────────────────

func _item_tier_floor(tier: int) -> float:
	var floors = BotConfig.ITEM_TIER_FLOOR
	return floors[tier] if tier >= 0 and tier < floors.size() else 0.0


func _freezes_stat(item: Dictionary) -> bool:
	for e in item.get("effects", []):
		if _FREEZE_KEYS.has(e.get("key", "")):
			var v = e.get("value", 0)
			if v == null: v = 0
			if v <= 0: return true
	return false


func _locks_weapons(item: Dictionary) -> bool:
	if item.get("locks_weapons", false): return true
	for e in item.get("effects", []):
		if e.get("key") == "lock_current_weapons": return true
	return false


func _blocks_healing(item: Dictionary) -> bool:
	if item.get("blocks_healing", false): return true
	for e in item.get("effects", []):
		var k = e.get("key", "")
		if k == "no_heal" or k == "dmg_when_heal": return true
	return false


func _clips_owned_weapon_cooldown(item: Dictionary, build: Dictionary) -> bool:
	# Ball and Chain-style cooldown floors can erase most of a rapid-fire gun's
	# DPS. Only veto the item when it would actually slow an equipped weapon.
	var cooldown_floor := 0.0
	for e in item.get("effects", []):
		if e.get("key", "") != "minimum_weapon_cooldowns":
			continue
		var value = e.get("value", 0)
		if value == null: value = 0
		cooldown_floor = max(cooldown_floor, float(value))
	if cooldown_floor <= 0.0:
		return false
	for weapon in build.get("weapons", []):
		var cooldown = weapon.get("cooldown", 0)
		if cooldown == null: cooldown = 0
		if float(cooldown) > 0.0 and float(cooldown) < cooldown_floor:
			return true
	return false


func _weapon_family_id(weapon_id: String) -> String:
	var separator := weapon_id.find_last("_")
	if separator < 0:
		return weapon_id
	var suffix := weapon_id.substr(separator + 1)
	if suffix.is_valid_integer():
		return weapon_id.substr(0, separator)
	return weapon_id


func _build_requirement_met(requirement: Dictionary, build: Dictionary, wave: int) -> bool:
	if requirement.get("never", false):
		return false
	if requirement.has("all"):
		for child in requirement["all"]:
			if not _build_requirement_met(child, build, wave):
				return false
	if requirement.has("any"):
		var any_met := false
		for child in requirement["any"]:
			if _build_requirement_met(child, build, wave):
				any_met = true
				break
		if not any_met:
			return false
	if requirement.has("min_wave") and wave < int(requirement["min_wave"]):
		return false
	if requirement.has("max_wave") and wave > int(requirement["max_wave"]):
		return false
	if requirement.has("stat"):
		var stats: Dictionary = build.get("stats", {})
		var stat_value = stats.get(requirement["stat"], 0)
		if stat_value == null: stat_value = 0
		if requirement.has("min_stat") and float(stat_value) < float(requirement["min_stat"]):
			return false
		if requirement.has("max_stat") and float(stat_value) > float(requirement["max_stat"]):
			return false
	if requirement.has("weapon_set"):
		var required_set = requirement["weapon_set"]
		var has_set := false
		for weapon in build.get("weapons", []):
			if weapon.get("sets", []).has(required_set):
				has_set = true
				break
		if not has_set:
			return false
	if requirement.has("weapon_flag"):
		var required_flag = requirement["weapon_flag"]
		var has_flag := false
		for weapon in build.get("weapons", []):
			if weapon.get(required_flag, false):
				has_flag = true
				break
		if not has_flag:
			return false
	if requirement.has("weapon_type"):
		var required_type = requirement["weapon_type"]
		var has_type := false
		for weapon in build.get("weapons", []):
			if weapon.get("type", "") == required_type:
				has_type = true
				break
		if not has_type:
			return false
	if requirement.has("weapon_scaling_stat"):
		var required_scaling = requirement["weapon_scaling_stat"]
		var has_scaling := false
		for weapon in build.get("weapons", []):
			for scaling in weapon.get("scaling", []):
				if scaling.size() >= 1 and scaling[0] == required_scaling:
					has_scaling = true
					break
			if has_scaling:
				break
		if not has_scaling:
			return false
	if requirement.has("max_distinct_weapon_families"):
		var families := {}
		for weapon in build.get("weapons", []):
			var family := _weapon_family_id(str(weapon.get("weapon_id", weapon.get("id", ""))))
			if family != "":
				families[family] = true
		if families.size() > int(requirement["max_distinct_weapon_families"]):
			return false
	return true


func _item_matches_current_build(item: Dictionary, build: Dictionary, wave: int) -> bool:
	if not BotConfig.BUILD_AWARE_ROGUERANKER_ENABLED:
		return true
	var item_id = item.get("id", "")
	if not BotConfig.BUILD_AWARE_ITEM_REQUIREMENTS.has(item_id):
		return true
	var requirement: Dictionary = BotConfig.BUILD_AWARE_ITEM_REQUIREMENTS[item_id]
	return _build_requirement_met(requirement, build, wave)


func _disables_all_healing(item: Dictionary) -> bool:
	for e in item.get("effects", []):
		if e.get("key", "") == "torture":
			var v = e.get("value", 0)
			if v == null: v = 0
			if v > 0: return true
	return false


func _building_healing(build: Dictionary) -> bool:
	var st: Dictionary = build.get("stats", {})
	if (st.get("stat_hp_regeneration", 0) or 0) >= 3: return true
	if (st.get("stat_lifesteal", 0) or 0) >= 3: return true
	for w in build.get("weapons", []):
		if w.get("is_healing", false): return true
	return false


func _arsenal_maxed(build: Dictionary) -> bool:
	var weapons: Array = build.get("weapons", [])
	if weapons.size() < build.get("weapon_slots", 6): return false
	for w in weapons:
		if w.get("upgrades", false):
			return false
	return true


func _is_vetoed(item: Dictionary, build: Dictionary, wave: int) -> bool:
	if _freezes_stat(item): return true
	if _disables_all_healing(item): return true
	if _locks_weapons(item) and not _arsenal_maxed(build): return true
	if _blocks_healing(item) and _building_healing(build): return true
	if _clips_owned_weapon_cooldown(item, build): return true
	if not _item_matches_current_build(item, build, wave): return true
	if _sustain_cap_veto(item, build, wave): return true
	return false


func item_score(item: Dictionary, build: Dictionary, profile, wave: int) -> float:
	if item.get("category") == "weapon":
		var wscore := _weapon_score(item, build, profile, wave)
		# Early only: tip borderline buys toward guns; after wave 10 restore prior balance.
		if wave <= BotConfig.WEAPON_OVER_ITEM_THROUGH_WAVE:
			wscore += BotConfig.WEAPON_OVER_ITEM_BONUS
		return wscore
	if _is_vetoed(item, build, wave): return -1e9
	if not BotConfig.rogueranker_item_allowed(item.get("id"), wave):
		return -1e9
	if not profile.banned_item_ids.empty() and profile.banned_item_ids.has(item.get("id")):
		return -1e9
	var effects: Array = item.get("effects", [])
	var target := _offense_target(wave, build)
	if (target > 0.0 and _offense_proxy(build) < target
			and _increases_enemy_density(effects)
			and _direct_offense_gain(effects) <= 0.0):
		# v75: Mouse-like sustain/utility cannot add enemies to an already
		# offense-starved build without contributing direct DPS or crowd clear.
		return -1e9
	if not profile.forbidden_stats.empty():
		var filtered := []
		for e in effects:
			if not profile.forbidden_stats.has(e.get("key", "")):
				filtered.append(e)
		effects = filtered
	var score := (_effects_value(effects, build, wave, profile)
		+ _tag_score(item.get("tags", []), profile, wave)
		+ _tier_bonus(profile, item.get("tier", 0)))
	score += _late_shop_pivot_bonus(effects, build, wave, profile)
	if (item.get("id", "") == "item_silver_bullet"
			and wave >= BotConfig.LATE_SHOP_WAVE
			and wave < BotConfig.FINAL_SHOP_WAVE
			and _offense_proxy(build) < BotConfig.OFFENSE_FLOOR_LATE):
		score -= BotConfig.BOSS_ONLY_PRE_FINAL_PENALTY
	score -= _wr_trap_penalty(item, wave, profile)
	# Rogue Ranker community item tier list — prefer S/A, soft-penalize D.
	score += BotConfig.rogueranker_item_bonus(item.get("id"))
	if effects.empty():
		return max(score, _item_tier_floor(item.get("tier", 0)))
	return score


func _wr_trap_penalty(item: Dictionary, wave: int, profile) -> float:
	if profile == null or str(profile.name) != "well_rounded":
		return 0.0
	var iid = item.get("id", "")
	if not BotConfig.WR_ITEM_PENALTIES.has(iid):
		return 0.0
	var pen = float(BotConfig.WR_ITEM_PENALTIES[iid])
	# Soft early; full weight once mid/late pivot starts.
	if wave < BotConfig.MID_SHOP_PIVOT_WAVE:
		return pen * 0.45
	if wave < BotConfig.LATE_SHOP_WAVE:
		return pen * 0.85
	return pen


func _offense_proxy(build: Dictionary) -> float:
	return float(BotCombatModel.offense_rating(build).get("total", 0.0))


func _offense_target(wave: int, build: Dictionary = {}) -> float:
	var base := 0.0
	if wave >= BotConfig.LATE_SHOP_WAVE:
		base = BotConfig.OFFENSE_FLOOR_LATE
	elif wave >= BotConfig.MID_SHOP_PIVOT_WAVE:
		base = BotConfig.OFFENSE_FLOOR_MID
	if base <= 0.0:
		return 0.0
	var observed_p90 := float(build.get("previous_wave_p90_density", 0.0))
	var density_bonus := clamp(
		(observed_p90 - BotConfig.OFFENSE_DENSITY_P90_GOAL)
			* BotConfig.OFFENSE_DENSITY_POINTS_PER_ENEMY,
		0.0, BotConfig.OFFENSE_DENSITY_MAX_BONUS)
	var observed_peak := float(build.get("previous_wave_peak_density", 0.0))
	var peak_bonus := clamp(
		(observed_peak - BotConfig.OFFENSE_DENSITY_PEAK_GOAL)
			* BotConfig.OFFENSE_DENSITY_POINTS_PER_PEAK_ENEMY,
		0.0, BotConfig.OFFENSE_DENSITY_MAX_PEAK_BONUS)
	return base + BotConfig.OFFENSE_TARGET_MARGIN + density_bonus + peak_bonus


func _offense_deficient(build: Dictionary, wave: int) -> bool:
	var target := _offense_target(wave, build)
	return target > 0.0 and _offense_proxy(build) < target


func _dps_below_band(build: Dictionary, wave: int) -> bool:
	# v80: winner-trajectory DPS band (BotConfig.OFFENSE_DPS_TARGETS_BY_WAVE).
	if wave < BotConfig.OFFENSE_BAND_FROM_WAVE:
		return false
	var rating: Dictionary = BotCombatModel.offense_rating(build)
	return float(rating.get("weapon_dps", 0.0)) < BotConfig.offense_dps_target(wave)


func _pairs_for_combine(it: Dictionary, weapons: Array) -> bool:
	# A same-id, same-tier owned copy that still upgrades makes this shop weapon
	# immediate combine fodder rather than filler.
	for w in weapons:
		if (str(w.get("id", "")) == str(it.get("id", ""))
				and int(w.get("tier", -1)) == int(it.get("tier", -2))
				and w.get("upgrades", false)):
			return true
	return false


func _projected_weapon_dps_gain(it: Dictionary, build: Dictionary) -> float:
	# v82: marginal effective-DPS change if this shop weapon is taken — full DPS
	# into an empty slot, else replacement of the weakest owned weapon. (The
	# immediate-combine tier-up gain is invisible to this math; callers keep
	# _pairs_for_combine as an explicit exception.)
	var stats: Dictionary = build.get("stats", {})
	var weapons: Array = build.get("weapons", [])
	var candidate := float(BotCombatModel.effective_weapon_dps(it, stats))
	var slots: int = int(build.get("weapon_slots", 6))
	if weapons.size() < slots:
		return candidate
	var weakest := -1.0
	for w in weapons:
		var d := float(BotCombatModel.effective_weapon_dps(w, stats))
		if weakest < 0.0 or d < weakest:
			weakest = d
	return candidate - max(weakest, 0.0)


func _band_impact_floor(build: Dictionary) -> float:
	# v82: a weapon is "impactful" below the band when its marginal gain is at
	# least this fraction of the current loadout's effective DPS (wave-stable
	# ~7-8% median across winning buys; filler clusters below 5%).
	var rating: Dictionary = BotCombatModel.offense_rating(build)
	return BotConfig.OFFENSE_IMPACT_MIN_DPS_GAIN_FRAC * float(rating.get("weapon_dps", 0.0))


func _direct_offense_gain(effects: Array) -> float:
	var gain := 0.0
	for e in effects:
		var key = e.get("key", "")
		var val := _effect_signed_value(e)
		if (key == "stat_ranged_damage" or key == "stat_percent_damage"
				or key == "stat_attack_speed"):
			gain += val
		elif ((key == "piercing" or key == "piercing_damage" or key == "bounce"
				or key == "explosion_damage" or key == "explosion_size"
				or key == "effect_explode" or key == "explode_on_death"
				or key == "projectiles_on_death" or key == "burning_spread")
				and val > 0.0):
			gain += max(1.0, val)
	return gain


func _increases_enemy_density(effects: Array) -> bool:
	for e in effects:
		var key = e.get("key", "")
		if (key == "number_of_enemies" or key == "extra_enemies_next_wave"
				or key == "extra_loot_aliens_next_wave"):
			var raw = e.get("value", 0)
			if raw != null and float(raw) > 0.0:
				return true
	return false


func _sustain_cap_veto(item: Dictionary, build: Dictionary, wave: int) -> bool:
	if wave < BotConfig.SUSTAIN_CAP_WAVE:
		return false
	var st: Dictionary = build.get("stats", {})
	var sustain := (_stat_float(st, "stat_hp_regeneration")
		+ _stat_float(st, "stat_lifesteal"))
	var sustain_floor := (BotConfig.DEFENSE_ADEQUATE_SUSTAIN
		if wave >= BotConfig.LATE_SHOP_WAVE
		else BotConfig.DEFENSE_ADEQUATE_MID_SUSTAIN)
	var sustain_gain := 0.0
	for e in item.get("effects", []):
		var key = e.get("key", "")
		if key == "stat_hp_regeneration" or key == "stat_lifesteal":
			sustain_gain += max(0.0, _effect_signed_value(e))
	if sustain_gain > 0.0 and sustain + sustain_gain >= sustain_floor:
		return true
	# Indirect healing has no stat delta, so it cannot be measured against the
	# numerical cap prospectively. Once the early cap activates, reserve those
	# purchases for offense instead of silently growing another sustain layer.
	return BotConfig.INDIRECT_SUSTAIN_ITEM_IDS.has(str(item.get("id", "")))


func _saturated_defense_only(effects: Array, build: Dictionary, wave: int, profile) -> bool:
	# v76: this is a genuinely hard wave-10+ cap. Direct DPS/crowd-clear keeps a
	# mixed option eligible; otherwise a pure HP/armor/sustain purchase is
	# rejected when it would reach or exceed adequacy. It no longer becomes
	# permissive merely because the offense proxy reports that it reached target.
	if wave < BotConfig.SUSTAIN_CAP_WAVE:
		return false
	var st: Dictionary = build.get("stats", {})
	var late := wave >= BotConfig.LATE_SHOP_WAVE
	var hp_floor := (BotConfig.DEFENSE_ADEQUATE_MAX_HP if late
		else BotConfig.DEFENSE_ADEQUATE_MID_MAX_HP)
	var armor_floor := (BotConfig.DEFENSE_ADEQUATE_ARMOR if late
		else BotConfig.DEFENSE_ADEQUATE_MID_ARMOR)
	var sustain_floor := (BotConfig.DEFENSE_ADEQUATE_SUSTAIN if late
		else BotConfig.DEFENSE_ADEQUATE_MID_SUSTAIN)
	var hp := _stat_float(st, "stat_max_hp")
	var armor := _stat_float(st, "stat_armor")
	var sustain := (_stat_float(st, "stat_hp_regeneration")
		+ _stat_float(st, "stat_lifesteal"))
	var hp_gain := 0.0
	var armor_gain := 0.0
	var sustain_gain := 0.0
	for e in effects:
		var val := _effect_signed_value(e)
		if val <= 0.0:
			continue
		var key = e.get("key", "")
		if key == "stat_max_hp":
			hp_gain += val
		elif key == "stat_armor":
			armor_gain += val
		elif key == "stat_hp_regeneration" or key == "stat_lifesteal":
			sustain_gain += val
	# Sustain is a hard cap even on mixed offense/sustain items. HP/armor retain
	# the direct-offense exception so a good damage item is not rejected merely
	# because it carries a small durability rider.
	if sustain_gain > 0.0 and sustain + sustain_gain >= sustain_floor:
		return true
	if _direct_offense_gain(effects) > 0.0:
		return false
	return ((hp_gain > 0.0 and hp + hp_gain >= hp_floor)
		or (armor_gain > 0.0 and armor + armor_gain >= armor_floor)
		or (sustain_gain > 0.0 and sustain + sustain_gain >= sustain_floor))


func _late_shop_pivot_bonus(effects: Array, build: Dictionary, wave: int, profile) -> float:
	# v74: wave 10+ offense-first ramp. Wave 15+ keeps the economy dump.
	if profile == null or str(profile.name) != "well_rounded":
		return 0.0
	if _saturated_defense_only(effects, build, wave, profile):
		return -1e9
	var st: Dictionary = build.get("stats", {})
	var max_hp = _stat_float(st, "stat_max_hp")
	var armor = _stat_float(st, "stat_armor")
	var dodge = _stat_float(st, "stat_dodge")
	var lifesteal = _stat_float(st, "stat_lifesteal")
	# v69: offense proxy for the below-target offense floor.
	var offense = _offense_proxy(build)
	var sustain = (_stat_float(st, "stat_hp_regeneration")
		+ _stat_float(st, "stat_lifesteal"))
	# v72: layer-local defense saturation. v71 required HP, armor, and sustain
	# to all clear their thresholds before suppressing any defensive filler, so
	# a single weak layer kept already-excessive HP/regeneration attractive.
	# Cap each pure layer independently; hybrid lifesteal remains available for
	# rapid-fire gun sustain, and weak defensive layers retain their old weights.
	var offense_starved_late = (wave >= BotConfig.LATE_SHOP_WAVE
		and offense < BotConfig.OFFENSE_FLOOR_LATE)
	var hp_saturated = (offense_starved_late
		and max_hp >= BotConfig.DEFENSE_ADEQUATE_MAX_HP)
	var armor_saturated = (offense_starved_late
		and armor >= BotConfig.DEFENSE_ADEQUATE_ARMOR)
	var sustain_saturated = (offense_starved_late
		and sustain >= BotConfig.DEFENSE_ADEQUATE_SUSTAIN)
	var defense_layers_adequate = ((hp_saturated and armor_saturated)
		or (hp_saturated and sustain_saturated)
		or (armor_saturated and sustain_saturated))
	var late = wave >= BotConfig.LATE_SHOP_WAVE
	var mid = wave >= BotConfig.MID_SHOP_PIVOT_WAVE
	var bonus := 0.0
	for e in effects:
		var key = e.get("key", "")
		var val = _effect_signed_value(e)
		if val == 0.0:
			continue
		if late:
			# Dump economy leftovers.
			if (key == "stat_harvesting" or key == "harvesting_growth" or key == "stat_luck"
					or key == "number_of_enemies" or key == "extra_enemies_next_wave"
					or key == "extra_loot_aliens_next_wave" or key == "gold_drops"):
				if val > 0.0:
					bonus -= val * 1.45
				continue
			# DPS first for elites/boss clear.
			if key == "stat_ranged_damage" and val > 0.0:
				bonus += val * (2.75 if offense < BotConfig.OFFENSE_FLOOR_LATE else 1.75)
			elif key == "stat_attack_speed" and val > 0.0:
				bonus += val * (2.40 if offense < BotConfig.OFFENSE_FLOOR_LATE else 1.50)
			elif key == "stat_percent_damage" and val > 0.0:
				bonus += val * (2.10 if offense < BotConfig.OFFENSE_FLOOR_LATE else 1.30)
			elif key == "stat_crit_chance" and val > 0.0:
				bonus += val * 0.75
			elif key == "stat_crit_damage" and val > 0.0:
				bonus += val * 0.50
			elif (key == "piercing" or key == "piercing_damage" or key == "bounce") and val > 0.0:
				bonus += val * (3.50 if offense < BotConfig.OFFENSE_FLOOR_LATE else 2.40)
			elif (key == "explosion_damage" or key == "explosion_size"
					or key == "effect_explode" or key == "explode_on_death"
					or key == "projectiles_on_death" or key == "burning_spread") and val > 0.0:
				bonus += val * (2.00 if offense < BotConfig.OFFENSE_FLOOR_LATE else 1.10)
			elif key == "damage_against_bosses" and val > 0.0:
				bonus += val * (2.70 if wave >= BotConfig.FINAL_SHOP_WAVE else 0.10)
			# Survivability for wave 15–20 spike.
			elif key == "stat_max_hp" and val > 0.0:
				bonus += val * (-4.00 if hp_saturated else (0.85 if max_hp < 110.0 else 0.50))
			elif key == "stat_armor" and val > 0.0:
				bonus += val * (-12.00 if armor_saturated else (1.00 if armor < 14.0 else 0.55))
			elif key == "stat_dodge" and val > 0.0 and dodge < 60.0:
				bonus += val * (-4.00 if defense_layers_adequate else 1.65)
			elif key == "stat_lifesteal" and val > 0.0:
				bonus += val * (1.20 if lifesteal < 15.0 else 0.80)
			elif key == "stat_hp_regeneration" and val > 0.0:
				bonus += val * (-8.00 if sustain_saturated else 0.35)
			elif key == "jellyshield_count" and val > 0.0 and defense_layers_adequate:
				bonus -= val * 40.0
			elif key == "wandering_bot" and val > 0.0 and defense_layers_adequate:
				bonus -= val * 30.0
		elif mid:
			# v74: from wave 10, strongly prefer DPS until the mid floor is met.
			if val <= 0.0:
				continue
			if key == "stat_harvesting" or key == "harvesting_growth" or key == "stat_luck":
				bonus -= val * 1.10
			elif key == "number_of_enemies" or key == "extra_enemies_next_wave":
				bonus -= val * 0.40
			elif key == "stat_ranged_damage":
				bonus += val * (2.40 if offense < BotConfig.OFFENSE_FLOOR_MID else 0.95)
			elif key == "stat_attack_speed":
				bonus += val * (2.10 if offense < BotConfig.OFFENSE_FLOOR_MID else 0.85)
			elif key == "stat_percent_damage":
				bonus += val * (1.85 if offense < BotConfig.OFFENSE_FLOOR_MID else 0.70)
			elif key == "piercing" or key == "piercing_damage" or key == "bounce":
				bonus += val * (3.20 if offense < BotConfig.OFFENSE_FLOOR_MID else 1.40)
			elif (key == "explosion_damage" or key == "explosion_size"
					or key == "effect_explode" or key == "explode_on_death"
					or key == "projectiles_on_death" or key == "burning_spread"):
				bonus += val * (1.85 if offense < BotConfig.OFFENSE_FLOOR_MID else 1.10)
			elif key == "stat_max_hp":
				# v66: below-target max HP is the strongest win/loss discriminator in
				# v63-v65 telemetry (d≈1.45 at wave 12); outbid crit/luck/regen fillers.
				bonus += val * (0.45 if offense < BotConfig.OFFENSE_FLOOR_MID else 1.00)
			elif key == "stat_armor":
				bonus += val * (0.35 if offense < BotConfig.OFFENSE_FLOOR_MID else 0.75)
			elif key == "stat_dodge" and dodge < 60.0:
				bonus += val * (0.35 if offense < BotConfig.OFFENSE_FLOOR_MID else 0.90)
			elif key == "stat_lifesteal":
				bonus += val * (0.75 if offense < BotConfig.OFFENSE_FLOOR_MID else 1.00)
		else:
			# Pre-10 soft targets from the WR guide.
			if val <= 0.0:
				continue
			if key == "stat_max_hp":
				# v66: winners average +12 bought HP by wave 9, losses +0.5 (d≈2.1).
				if wave <= 11 and max_hp < 55.0:
					bonus += val * 1.15
			elif key == "stat_armor":
				if wave >= 8 and armor < 10.0:
					bonus += val * 0.70
			elif key == "stat_dodge":
				if wave >= 10 and dodge < 60.0:
					bonus += val * 0.85
			elif key == "stat_ranged_damage" or key == "stat_attack_speed":
				if wave >= 8:
					bonus += val * 0.45
	return bonus


func _combinable_index(weapons: Array) -> int:
	# Equal max-tier weapon IDs are duplicates, but Brotato cannot combine them.
	# Only offer a pair when both copies still have an upgrades_into path.
	var by_id_upgradeable := {}
	for w in weapons:
		var id = w.get("id")
		if id == null:
			continue
		if w.get("upgrades", false):
			if not by_id_upgradeable.has(id):
				by_id_upgradeable[id] = []
			by_id_upgradeable[id].append(w)
	for wid in by_id_upgradeable:
		var group: Array = by_id_upgradeable[wid]
		if group.size() >= 2:
			return int(group[0].get("index", -1))
	return -1


func _has_combinable(weapons: Array) -> bool:
	return _combinable_index(weapons) >= 0


func _lowest_tier_replace_victim(weapons: Array, shop_tier: int, build: Dictionary, profile, wave: int = 1):
	# Weakest lowest-tier owned gun strictly below the shop weapon tier.
	var victim = null
	var victim_tier := 999
	var victim_val := 1e18
	for w in weapons:
		var wt := int(w.get("tier", 0))
		if wt > shop_tier - BotConfig.TIER_REPLACE_MIN_GAP:
			continue
		var v := _owned_weapon_value(w, build, profile, wave)
		if victim == null or wt < victim_tier or (wt == victim_tier and v < victim_val):
			victim = w
			victim_tier = wt
			victim_val = v
	return victim


func _rare_gun_min_tier(item: Dictionary) -> int:
	var wid = item.get("weapon_id")
	if not BotConfig.RARE_GUN_MIN_TIERS.has(wid):
		return -1
	return int(BotConfig.RARE_GUN_MIN_TIERS[wid])


func _rare_gun_action(items: Array, weapons: Array, build: Dictionary, profile,
		gold: int, wave: int, slots_full: bool, can_sell: bool, final_shop: bool) -> Dictionary:
	# v73: Chain Gun IV and Minigun III+ are rare enough that the generic
	# premium-lock reach test missed them. Give the best visible target one
	# explicit buy/save attempt, with the normal one-visit identity lock lifetime.
	var best = null
	var best_score := -1e30
	for it in items:
		var min_tier := _rare_gun_min_tier(it)
		if min_tier < 0 or int(it.get("tier", 0)) < min_tier:
			continue
		if it.get("category") != "weapon" or not it.get("usable", true):
			continue
		if not _weapon_matches_allowlist(it, profile, weapons):
			continue
		var score := _weapon_score(it, build, profile, wave)
		if score > best_score:
			best = it
			best_score = score
	if best == null:
		return {}

	var item_id := str(best.get("id", ""))
	var price := int(best.get("price", 0))
	var affordable := bool(best.get("affordable", false))
	if affordable and best.get("can_buy", true):
		return {"type": "shop_buy", "slot": best["slot"], "score": best_score,
			"item_id": item_id, "rare_gun": true}

	# A rare gun may replace only a strictly lower-tier owned gun. This avoids
	# sacrificing an equally developed weapon merely to chase rarity.
	var victim = _lowest_tier_replace_victim(
		weapons, int(best.get("tier", 0)), build, profile, wave)
	if can_sell and victim != null and (slots_full or not best.get("can_buy", true)):
		if gold + int(victim.get("sell_value", 0)) >= price:
			return {"type": "shop_sell", "index": int(victim.get("index", -1)),
				"score": best_score, "tier_replace": true,
				"replace_with": item_id, "item_id": str(victim.get("id", "")),
				"rare_gun": true}

	if best.get("locked", false):
		if _session_new_lock_item_ids.has(item_id):
			# The lock was created this visit: bank the remaining gold for it.
			return {"type": "shop_go", "score": best_score, "rare_gun_saved": true}
		# An inherited lock got its purchase/sale attempt and remains unreachable.
		_session_expired_lock_item_ids[item_id] = true
		return _guard_lock_transition({"type": "shop_unlock", "slot": best["slot"],
			"score": best_score, "item_id": item_id, "lock_expired": true,
			"rare_gun": true})

	if (not final_shop and not affordable
			and not _session_expired_lock_item_ids.has(item_id)):
		_session_new_lock_item_ids[item_id] = true
		return _guard_lock_transition({"type": "shop_lock", "slot": best["slot"],
			"score": best_score, "item_id": item_id, "rare_gun": true})
	return {}


func _offense_first_item_action(items: Array, build: Dictionary, profile,
		wave: int) -> Dictionary:
	# v75: while materially below the applicable offense target, any affordable
	# safe net-positive direct-DPS/crowd-clear item bypasses the ordinary minimum
	# buy threshold and non-rare premium-lock path.
	var target := _offense_target(wave, build)
	if target <= 0.0 or _offense_proxy(build) >= target:
		return {}
	var band_gate := _dps_below_band(build, wave)
	var impact_floor := _band_impact_floor(build) if band_gate else 0.0
	var best = null
	var best_rank := -1e30
	var best_score := -1e30
	for it in items:
		if it.get("category") == "weapon":
			if (not it.get("affordable", false) or not it.get("can_buy", true)
					or not it.get("usable", true)
					or not _weapon_matches_allowlist(it, profile, build.get("weapons", []))
					or _session_sold_families.has(it.get("weapon_id"))):
				continue
			# v80/v82: below the winner-DPS band only impactful weapons satisfy
			# mandatory offense — a real marginal-DPS gain or an immediate
			# combine pair.
			if (band_gate
					and not _pairs_for_combine(it, build.get("weapons", []))
					and _projected_weapon_dps_gain(it, build) < impact_floor):
				continue
			var weapon_score := _weapon_score(it, build, profile, wave)
			if weapon_score <= -1e8:
				continue
			var weapon_rank := weapon_score + 25.0
			if weapon_rank > best_rank:
				best = it
				best_rank = weapon_rank
				best_score = weapon_score
			continue
		if not it.get("affordable", false) or not it.get("can_buy", true):
			continue
		var gain := _direct_offense_gain(it.get("effects", []))
		if gain <= 0.0:
			continue
		# v80: below the winner-DPS band, marginal trinkets don't satisfy
		# mandatory offense — hold out for a meaningful direct-offense gain.
		if band_gate and gain < BotConfig.OFFENSE_IMPACT_MIN_ITEM_GAIN:
			continue
		var score := item_score(it, build, profile, wave)
		if score <= -1e8:
			continue
		var rank := score + gain * 6.0
		if rank > best_rank:
			best = it
			best_rank = rank
			best_score = score
	if best == null:
		return {}
	return {"type": "shop_buy", "slot": best["slot"], "score": best_score,
		"item_id": str(best.get("id", "")), "offense_first": true}


func _board_has_gate_clearing_offense(items: Array) -> bool:
	# v124: while offense-deficient, an affordable non-weapon offense-stat item
	# that already clears the impact gate must be bought rather than rerolled
	# past. Reuses the exact mandatory-offense definitions — _direct_offense_gain
	# (crit excluded by construction) against OFFENSE_IMPACT_MIN_ITEM_GAIN — plus
	# the existing per-item affordability flag; gold_reserve semantics untouched.
	for it in items:
		if it.get("category") == "weapon":
			continue
		if not it.get("affordable", false) or not it.get("can_buy", true):
			continue
		if _direct_offense_gain(it.get("effects", [])) >= BotConfig.OFFENSE_IMPACT_MIN_ITEM_GAIN:
			return true
	return false


func _try_tier_replace_sell(items: Array, weapons: Array, build: Dictionary, profile, gold: int, wave: int, slots_full: bool, can_sell: bool) -> Dictionary:
	# Slots full / can't buy: sell a lower-tier gun so a higher-tier one can enter.
	if not can_sell or weapons.empty():
		return {}
	var best := {}
	var best_score := -1e30
	for it in items:
		if it.get("category") != "weapon":
			continue
		if not it.get("usable", true):
			continue
		if not _weapon_matches_allowlist(it, profile, weapons):
			continue
		if _session_sold_families.has(it.get("weapon_id")):
			continue
		var shop_tier := int(it.get("tier", 0))
		var victim = _lowest_tier_replace_victim(weapons, shop_tier, build, profile, wave)
		if victim == null:
			continue
		var needs_slot: bool = slots_full or not it.get("can_buy", true)
		var price := int(it.get("price", 0))
		var sell_val := int(victim.get("sell_value", 0))
		var eff_gold: int = gold + sell_val
		var needs_gold: bool = not it.get("affordable", false) and eff_gold >= price
		if not needs_slot and not needs_gold:
			continue
		if eff_gold < price:
			continue
		var s := item_score(it, build, profile, wave)
		s += float(shop_tier - int(victim.get("tier", 0))) * 8.0
		if s <= best_score:
			continue
		best_score = s
		best = {
			"type": "shop_sell",
			"index": int(victim.get("index", -1)),
			"score": s,
			"tier_replace": true,
			"replace_with": str(it.get("id", "")),
			"item_id": str(victim.get("id", "")),
		}
	if not best.empty() and best_score >= BotConfig.TIER_REPLACE_SCORE_MARGIN:
		return best
	return {}


# ─────────────────────────── session reset ────────────────────────────────────

func _reset_session_if_new(state: Dictionary) -> void:
	var w: int = state.get("wave", 0)
	if _session_wave != w:
		_session_wave = w
		_session_rerolls = 0
		_session_surplus_rerolls = 0
		_session_combines = 0
		_session_sold_families = {}
		_session_new_lock_item_ids = {}
		_session_expired_lock_item_ids = {}
		_session_lock_transition_counts = {}
		_session_cycle_blocked_item_ids = {}


func _guard_lock_transition(action: Dictionary) -> Dictionary:
	var action_type := str(action.get("type", ""))
	if action_type != "shop_lock" and action_type != "shop_unlock":
		return action
	var item_id := str(action.get("item_id", ""))
	if item_id == "":
		return action
	var transitions := int(_session_lock_transition_counts.get(item_id, 0)) + 1
	_session_lock_transition_counts[item_id] = transitions
	if transitions <= BotConfig.SHOP_MAX_LOCK_TRANSITIONS_PER_ITEM:
		return action
	_session_cycle_blocked_item_ids[item_id] = true
	_session_expired_lock_item_ids[item_id] = true
	return {
		"type": "shop_go",
		"score": float(action.get("score", 0.0)),
		"shop_cycle_guard": true,
		"blocked_item_id": item_id,
		"blocked_transition": action_type,
	}


func _expired_lock_action(items: Array) -> Dictionary:
	# A lock gets one subsequent shop visit to be purchased. If it is still
	# present after purchase evaluation, release the slot before rerolling.
	# Slots locked during the current visit are protected until the next wave.
	for it in items:
		var slot := int(it.get("slot", -1))
		var item_id := str(it.get("id", ""))
		if (it.get("locked", false)
				and slot >= 0
				and not _session_new_lock_item_ids.has(item_id)):
			_session_expired_lock_item_ids[item_id] = true
			return _guard_lock_transition({
				"type": "shop_unlock",
				"slot": slot,
				"score": 0.0,
				"item_id": item_id,
				"lock_expired": true,
			})
	return {}


func _weapon_matches_allowlist(item: Dictionary, profile, weapons: Array) -> bool:
	# Hard bans (e.g. medical gun) first.
	var wid = item.get("weapon_id")
	if profile.banned_weapon_ids != null and not profile.banned_weapon_ids.empty():
		if profile.banned_weapon_ids.has(wid):
			return false
	# Healing/medical weapons: treat as banned when listed or flagged healing under experiment.
	if item.get("is_healing", false) and BotConfig.EXPERIMENT_ANY_GUNS:
		return false
	# Family id lock (SMG/shotgun) and/or set lock (any gun).
	if profile.allowed_weapon_ids != null:
		if not profile.allowed_weapon_ids.has(wid):
			return false
	if profile.allowed_weapon_sets != null:
		var hit := false
		for s in item.get("sets", []):
			if profile.allowed_weapon_sets.has(s):
				hit = true
				break
		if not hit:
			return false
	return true


func _combine_min_weapons(_profile) -> int:
	return BotConfig.COMBINE_MIN_WEAPONS


func _needs_allowed_weapon_fill(profile, weapons: Array, slots: int) -> bool:
	# WEAPON_FILL_TARGET 0 = never force fill. Otherwise push toward min(slots, target).
	if BotConfig.WEAPON_FILL_TARGET <= 0:
		return false
	var target: int = min(slots, BotConfig.WEAPON_FILL_TARGET)
	if weapons.size() >= target:
		return false
	if profile.allowed_weapon_ids != null or profile.allowed_weapon_sets != null:
		return true
	return false


# ────────────────── v126 bounded surplus-reroll conversion ────────────────────
# Runs ONLY after the buy loop and the v125 reroll path are exhausted, so it is
# structurally incapable of preempting a qualifying buy or of changing any v125
# decision. One reroll at a time; the controller holds the board-signature
# barrier (idempotency + stale-board protection) between rerolls.

func _locked_item_reserve(items: Array) -> int:
	# Gold committed to locked/planned purchases still sitting on the board.
	var reserve := 0
	for it in items:
		if it.get("locked", false):
			reserve += int(it.get("price", 0))
	return reserve


func _material_value_reserve(build: Dictionary, gold: int) -> int:
	# Items whose effect consumes/values the held material stock (piggy_bank
	# class interest): reserve the amount the effect operates on. Fractions all
	# address the same pool, so the reserve is the maximum, never the sum.
	var table: Dictionary = BotConfig.SURPLUS_MATERIAL_VALUE_ITEMS
	var reserve := 0
	for owned in build.get("items", []):
		# Accept either the {"id": ...} entries the controller emits or bare ids.
		var owned_id := ""
		if typeof(owned) == TYPE_DICTIONARY:
			owned_id = str(owned.get("id", ""))
		else:
			owned_id = str(owned)
		if not table.has(owned_id):
			continue
		var entry: Dictionary = table[owned_id]
		var flat := int(entry.get("flat", 0))
		var fraction := float(entry.get("fraction_of_gold", 0.0))
		var scaled := int(round(fraction * float(max(gold, 0))))
		reserve = int(max(reserve, max(flat, scaled)))
	return reserve


func _board_has_safe_positive_item(items: Array, build: Dictionary, profile,
		wave: int) -> bool:
	# An affordable, legally purchasable, non-vetoed, positively scored option.
	# Hard vetoes score -1e9 inside item_score and survive surplus pressure.
	for it in items:
		if not it.get("affordable", false) or not it.get("can_buy", true):
			continue
		if it.get("category") == "weapon" and not it.get("usable", true):
			continue
		if item_score(it, build, profile, wave) > 0.0:
			return true
	return false


func _surplus_state(items: Array, build: Dictionary, profile, wave: int,
		gold: int, reroll_price: int) -> Dictionary:
	# Recomputes the surplus rule from the CURRENT board, gold and actual reroll
	# price (which escalates within a shop). Returns the full arithmetic so the
	# audit can recompute the decision and the reason code from telemetry alone.
	var in_window: bool = (wave >= BotConfig.SURPLUS_MIN_WAVE
		and wave <= BotConfig.SURPLUS_MAX_WAVE)
	var locked_reserve := _locked_item_reserve(items)
	var material_reserve := _material_value_reserve(build, gold)
	var next_shop_reserve := BotConfig.surplus_next_shop_reserve(wave)
	var spendable := gold - locked_reserve - material_reserve - next_shop_reserve
	var out := {
		"in_window": in_window,
		"wave": wave,
		"gold": gold,
		"reroll_price": reroll_price,
		"locked_item_reserve": locked_reserve,
		"material_value_reserve": material_reserve,
		"next_shop_reserve": next_shop_reserve,
		"spendable_surplus": spendable,
		"surplus_rerolls": _session_surplus_rerolls,
		"surplus_rerolls_max": BotConfig.SURPLUS_REROLLS_MAX,
		"reroll": false,
		"exit_reason": BotConfig.SHOP_EXIT_NO_SURPLUS,
	}
	if not in_window:
		return out
	var budget_exhausted: bool = (
		_session_surplus_rerolls >= BotConfig.SURPLUS_REROLLS_MAX
		or _session_rerolls >= BotConfig.SHOP_MAX_REROLLS_CAP)
	if budget_exhausted:
		# The more specific "nothing convertible on this board" reason wins over
		# the bare budget reason when every affordable option is vetoed or
		# non-positive — that is why the surplus could not be converted.
		out["exit_reason"] = (BotConfig.SHOP_EXIT_REROLL_LIMIT
			if _board_has_safe_positive_item(items, build, profile, wave)
			else BotConfig.SHOP_EXIT_NO_SAFE_POSITIVE_ITEM)
		return out
	if spendable - reroll_price > 0:
		out["reroll"] = true
		out["exit_reason"] = ""
		return out
	# The rule failed on arithmetic. Attribute it to the first reserve that is
	# individually binding (removing it alone would let the rule pass).
	if (locked_reserve > 0
			and spendable + locked_reserve - reroll_price > 0):
		out["exit_reason"] = BotConfig.SHOP_EXIT_LOCKED_RESERVE
	elif (material_reserve > 0
			and spendable + material_reserve - reroll_price > 0):
		out["exit_reason"] = BotConfig.SHOP_EXIT_MATERIAL_VALUE_RESERVE
	elif (next_shop_reserve > 0
			and spendable + next_shop_reserve - reroll_price > 0):
		out["exit_reason"] = BotConfig.SHOP_EXIT_NEXT_SHOP_RESERVE
	else:
		out["exit_reason"] = BotConfig.SHOP_EXIT_NO_SURPLUS
	return out


# ─────────────────────────── decide_shop ──────────────────────────────────────

func decide_shop(state: Dictionary, profile) -> Dictionary:
	_reset_session_if_new(state)
	var gold: int = state.get("gold", 0)
	var wave: int = state.get("wave", 1)
	var reroll_price: int = state.get("reroll_price", 0)
	var build: Dictionary = state.get("build", {})
	var items: Array = state.get("shop_items", [])
	var weapons: Array = build.get("weapons", [])
	var slots: int = build.get("weapon_slots", 6)
	var can_sell: bool = build.get("can_sell", true)
	var slots_full: bool = weapons.size() >= slots
	# In non-Endless mode, current_wave 19 is the shop immediately before the
	# terminal wave. Money has no carryover value there.
	var final_shop: bool = wave >= BotConfig.FINAL_SHOP_WAVE and not state.get("is_endless", false)
	# v65 permits the normal single deferred combine in the final shop, but only
	# after the six-slot loadout is established. Pair upgradeability is still
	# enforced by _combinable_index and the per-visit cap remains one.
	var combine_allowed: bool = not final_shop or slots_full
	# v80: from wave 13, trailing the winning runs' median estimated DPS switches
	# shopping to impactful offense only (see OFFENSE_DPS_TARGETS_BY_WAVE).
	var band_gate: bool = _dps_below_band(build, wave)
	var band_impact_floor: float = _band_impact_floor(build) if band_gate else 0.0

	var rich_threshold: int = min(BotConfig.SHOP_RICH_GOLD_BASE + BotConfig.SHOP_RICH_GOLD_PER_WAVE * wave,
		BotConfig.SHOP_RICH_GOLD_MAX)
	var rich: bool = gold >= rich_threshold and not profile.disable_rich_mode
	var min_buy: float = BotConfig.SHOP_RICH_MIN_BUY if rich else profile.min_buy_score
	var reroll_cap: int = BotConfig.SHOP_MAX_REROLLS
	# Keep a consistent five-roll search budget in ordinary shops. Late shops
	# are too important to receive a smaller search budget.
	var gold_reserve: int = max(int(profile.gold_reserve), BotConfig.SHOP_MED_GOLD_RESERVE if wave >= BotConfig.MID_SHOP_PIVOT_WAVE else 0)
	if final_shop:
		min_buy = BotConfig.FINAL_SHOP_MIN_BUY
		reroll_cap = BotConfig.SHOP_MAX_REROLLS_CAP
		gold_reserve = 0

	# 0-combine) Merge duplicates before buying more guns / filling slots.
	if (BotConfig.SHOP_COMBINES_ENABLED and combine_allowed
			and BotConfig.EXPERIMENT_COMBINE_ASAP and profile.auto_combine
			and _session_combines < BotConfig.SHOP_MAX_COMBINES_PER_VISIT):
		var ci0 = _combinable_index(weapons)
		if ci0 >= 0:
			_session_combines += 1
			return {"type": "shop_combine", "index": ci0, "score": 80.0, "combine_count": _session_combines}

	# 0-tier-replace) Higher-tier shop gun + slots full → sell lowest lower-tier gun.
	var rare_gun_action: Dictionary = _rare_gun_action(
		items, weapons, build, profile, gold, wave, slots_full, can_sell, final_shop)
	if not rare_gun_action.empty():
		return rare_gun_action

	var tier_sell: Dictionary = _try_tier_replace_sell(items, weapons, build, profile, gold, wave, slots_full, can_sell)
	if not tier_sell.empty():
		return tier_sell

	# 0a) Fill weapon slots toward WEAPON_FILL_TARGET (after combines).
	if _needs_allowed_weapon_fill(profile, weapons, slots):
		var best_fill = null
		var best_fill_score: float = -1e30
		var has_allowed := false
		for it in items:
			if it.get("category") != "weapon":
				continue
			if not _weapon_matches_allowlist(it, profile, weapons):
				continue
			if not it.get("usable", true):
				continue
			if _session_sold_families.has(it.get("weapon_id")):
				continue
			has_allowed = true
			if not it.get("affordable") or not it.get("can_buy", true):
				continue
			var fs := _weapon_score(it, build, profile, wave)
			if fs > best_fill_score:
				best_fill_score = fs
				best_fill = it
		if best_fill != null and best_fill_score > -1e8:
			return {"type": "shop_buy", "slot": best_fill["slot"], "score": best_fill_score, "item_id": str(best_fill.get("id", ""))}
		if not has_allowed:
			var free0: bool = reroll_price <= 0
			var budget0: bool = free0 or gold >= reroll_price * profile.reroll_gold_factor + gold_reserve
			if _session_rerolls < min(BotConfig.SHOP_MAX_REROLLS_CAP, reroll_cap) and budget0:
				_session_rerolls += 1
				return {"type": "shop_reroll", "score": 0.0}

	# 0b) shop_must_items: target items (Wounded → tardigrade)
	var must_items: Array = profile.shop_must_items
	if not must_items.empty():
		# 0b.1: buy any visible+affordable target
		for it in items:
			if must_items.has(it.get("id")) and it.get("affordable") and it.get("can_buy", true):
				return {"type": "shop_buy", "slot": it["slot"]}
		# 0b.1a: release inherited locks that were not bought this visit.
		var expired_must_lock := _expired_lock_action(items)
		if not expired_must_lock.empty():
			return expired_must_lock
		# 0b.2: lock visible unaffordable target
		if not final_shop:
			for it in items:
				if must_items.has(it.get("id")) and not it.get("affordable") and not it.get("locked", false):
					var must_item_id := str(it.get("id", ""))
					if _session_expired_lock_item_ids.has(must_item_id): continue
					_session_new_lock_item_ids[must_item_id] = true
					return _guard_lock_transition({"type": "shop_lock", "slot": it["slot"],
						"item_id": must_item_id})
		# 0b.3: unlock non-target items
		for it in items:
			if it.get("locked", false) and not must_items.has(it.get("id")):
				var non_target_id := str(it.get("id", ""))
				_session_expired_lock_item_ids[non_target_id] = true
				return _guard_lock_transition({"type": "shop_unlock", "slot": it["slot"],
					"item_id": non_target_id, "lock_expired": true})
		# 0b.4: fill empty weapon slots first
		if weapons.size() < slots:
			for it in items:
				if (it.get("category") == "weapon"
					and it.get("affordable")
					and it.get("can_buy", true)
					and it.get("usable", true)
					and not _session_sold_families.has(it.get("weapon_id"))):
					var s = _weapon_score(it, build, profile, wave)
					if s > 0: return {"type": "shop_buy", "slot": it["slot"]}
		# 0b.5: reroll exhaustively
		var has_aff_tgt := false
		for it in items:
			if must_items.has(it.get("id")) and it.get("affordable"):
				has_aff_tgt = true; break
		if not has_aff_tgt:
			var free_mi: bool = reroll_price <= 0
			var min_keep := 0 if final_shop else 20
			var reroll_factor_mi: float = 1.0 if final_shop else 2.0
			var budget_mi: bool = free_mi or gold >= reroll_price * reroll_factor_mi + min_keep
			if _session_rerolls < reroll_cap and budget_mi:
				_session_rerolls += 1
				return {"type": "shop_reroll", "score": 0.0}

	# 0) shop_must_tag (Beast Master)
	var must_tag: String = profile.shop_must_tag
	if must_tag != "":
		for it in items:
			var tags: Array = it.get("tags", []) if it.get("tags") != null else []
			if tags.has(must_tag) and it.get("affordable") and it.get("can_buy", true):
				return {"type": "shop_buy", "slot": it["slot"]}
		var free_e: bool = reroll_price <= 0
		var budget_e: bool = free_e or gold >= reroll_price * profile.reroll_gold_factor + gold_reserve
		if _session_rerolls < reroll_cap and budget_e:
			_session_rerolls += 1
			return {"type": "shop_reroll", "score": 0.0}
		return {"type": "shop_go", "score": 0.0}

	# 0c) While below target, buy affordable safe direct offense before generic
	# score thresholds or non-rare premium locks can divert the shop.
	if _offense_deficient(build, wave):
		for locked_item in items:
			if (locked_item.get("locked", false)
					and _rare_gun_min_tier(locked_item) < 0
					and locked_item.get("category") != "weapon"
					and _direct_offense_gain(locked_item.get("effects", [])) <= 0.0):
				var utility_item_id := str(locked_item.get("id", ""))
				_session_expired_lock_item_ids[utility_item_id] = true
				return _guard_lock_transition({
					"type": "shop_unlock", "slot": locked_item["slot"],
					"item_id": utility_item_id, "offense_first": true,
					"utility_lock_veto": true, "lock_expired": true})
	var offense_first_action := _offense_first_item_action(items, build, profile, wave)
	if not offense_first_action.empty():
		return offense_first_action

	# 1) Best purchase
	var best_score: float = min_buy
	var best_action := []
	for it in items:
		var is_weapon: bool = it.get("category") == "weapon"
		if is_weapon:
			if not it.get("usable", true): continue
			if _session_sold_families.has(it.get("weapon_id")): continue
			# v80/v82: below the winner-DPS band, filler guns whose marginal
			# gain is under the impact floor and that don't pair for an
			# immediate combine can't compete for gold (slots stay fillable
			# via step 2.5 when a slot is actually empty).
			if (band_gate and slots_full
					and not _pairs_for_combine(it, weapons)
					and _projected_weapon_dps_gain(it, build) < band_impact_floor):
				continue
		elif not it.get("can_buy", true):
			continue
		if not it.get("affordable"): continue
		var s := item_score(it, build, profile, wave)
		if s <= best_score: continue
		if not is_weapon:
			best_score = s; best_action = ["shop_buy", "slot", it["slot"]]; continue
		if it.get("can_buy", true):
			best_score = s; best_action = ["shop_buy", "slot", it["slot"]]
		elif slots_full:
			var combine_idx = _combinable_index(weapons)
			if (BotConfig.SHOP_COMBINES_ENABLED and combine_allowed
					and combine_idx >= 0
					and _session_combines < BotConfig.SHOP_MAX_COMBINES_PER_VISIT):
				best_score = s; best_action = ["shop_combine", "index", combine_idx]
			elif can_sell and not weapons.empty():
				var shop_tier := int(it.get("tier", 0))
				var victim = _lowest_tier_replace_victim(weapons, shop_tier, build, profile, wave)
				var tier_replace: bool = victim != null
				if victim == null and _rare_gun_min_tier(it) >= 0:
					# v73 rare-gun replacement is lower-tier-only.
					continue
				if victim == null:
					victim = weapons[0]
					var weakest_val = _owned_weapon_value(victim, build, profile, wave)
					for w in weapons:
						var v = _owned_weapon_value(w, build, profile, wave)
						if v < weakest_val:
							victim = w
							weakest_val = v
				var weakest_val2 = _owned_weapon_value(victim, build, profile, wave)
				var eff_gold: int = gold + int(victim.get("sell_value", 0))
				if eff_gold >= it.get("price", 0) and (tier_replace or s > weakest_val2 + BotConfig.SHOP_SELL_MARGIN):
					best_score = s
					best_action = ["shop_sell", "index", victim.get("index", -1), tier_replace]
	if not best_action.empty():
		var atype: String = best_action[0]
		var key: String = best_action[1]
		var ref = best_action[2]
		var is_tier_replace: bool = best_action.size() > 3 and best_action[3]
		if atype == "shop_sell" and not is_tier_replace:
			# Don't ban family on tier-replace — we may buy a higher tier of the same gun next.
			for w in weapons:
				if w.get("index", -2) == ref:
					var fam = w.get("weapon_id")
					if fam != null: _session_sold_families[fam] = true
					break
		var bought_id := ""
		if atype == "shop_buy":
			for it2 in items:
				if it2.get("slot") == ref:
					bought_id = str(it2.get("id", ""))
					break
		var out := {"type": atype, key: ref, "score": best_score}
		if atype == "shop_combine":
			_session_combines += 1
			out["combine_count"] = _session_combines
		if bought_id != "":
			out["item_id"] = bought_id
		if is_tier_replace:
			out["tier_replace"] = true
		return out

	# 2) Combine when useful: free a slot, or upgrade once we already have a loadout
	# and nothing better is affordable (not ASAP-at-2).
	if (BotConfig.SHOP_COMBINES_ENABLED and combine_allowed
			and profile.auto_combine
			and _session_combines < BotConfig.SHOP_MAX_COMBINES_PER_VISIT):
		var ci = _combinable_index(weapons)
		if ci >= 0:
			var should_combine := slots_full
			if not should_combine and weapons.size() >= BotConfig.COMBINE_MIN_WEAPONS:
				# Loadout is established and shop has nothing worth buying — upgrade dupes.
				should_combine = true
			if should_combine:
				_session_combines += 1
				return {"type": "shop_combine", "index": ci, "score": 70.0, "combine_count": _session_combines}

	# 2.5) Fill empty weapon slot (prefer T2+; T1 soft-capped via item_score)
	if weapons.size() < slots:
		var best_w = null
		var best_w_score: float = 0.0
		for it in items:
			if it.get("category") != "weapon" or not it.get("usable", true): continue
			if not it.get("affordable") or not it.get("can_buy", true): continue
			if not _weapon_matches_allowlist(it, profile, weapons): continue
			if _session_sold_families.has(it.get("weapon_id")) or _is_off_build(it, build): continue
			var s := item_score(it, build, profile, wave)
			if s > best_w_score:
				best_w_score = s
				best_w = it
		if best_w != null and best_w_score > 0.0:
			return {"type": "shop_buy", "slot": best_w["slot"], "score": best_w_score, "item_id": str(best_w.get("id", ""))}

	# 2.75) Inherited locks had their one purchase opportunity; release them
	# before creating new locks or spending this visit's rerolls.
	var expired_lock := _expired_lock_action(items)
	if not expired_lock.empty():
		return expired_lock

	# 3) Lock unaffordable premium
	if not final_shop:
		var must_s3: Array = profile.shop_must_items
		for it in items:
			if it.get("affordable") or it.get("locked", false): continue
			var lock_item_id := str(it.get("id", ""))
			if _session_expired_lock_item_ids.has(lock_item_id): continue
			if _session_cycle_blocked_item_ids.has(lock_item_id): continue
			if not must_s3.empty() and not must_s3.has(it.get("id")): continue
			if it.get("category") == "weapon" and not profile.lock_weapons: continue
			if (_offense_deficient(build, wave)
					and it.get("category") != "weapon"
					and _direct_offense_gain(it.get("effects", [])) <= 0.0): continue
			if (item_score(it, build, profile, wave) >= BotConfig.SHOP_PREMIUM_SCORE
				and it.get("price", 0) <= gold * BotConfig.SHOP_PREMIUM_REACH + 50):
				_session_new_lock_item_ids[lock_item_id] = true
				return _guard_lock_transition({"type": "shop_lock", "slot": it["slot"],
					"score": item_score(it, build, profile, wave), "item_id": lock_item_id})

	# 4) Reroll when justified — bank medium gold for upgrades/tank.
	var free_reroll: bool = reroll_price <= 0
	var cap: int = reroll_cap
	var reroll_factor: float = 1.0 if final_shop else profile.reroll_gold_factor
	var budget_ok: bool = free_reroll or gold >= reroll_price * reroll_factor + gold_reserve

	if _session_rerolls < cap and budget_ok:
		var best_here: float = -1.0
		for it in items:
			if it.get("affordable") and it.get("can_buy", true):
				var v := item_score(it, build, profile, wave)
				if v > best_here: best_here = v
		var worth: float = BotConfig.SHOP_REROLL_RICH_WORTH if (rich or free_reroll) else BotConfig.SHOP_REROLL_WORTH
		if final_shop:
			# Every positive-value affordable item was already bought above. Keep
			# searching while the next roll is affordable; no future shop exists.
			worth = 1e30
		if wave >= BotConfig.MID_SHOP_PIVOT_WAVE and not free_reroll:
			worth += 1.5
		var offense_target := _offense_target(wave, build)
		if (offense_target > 0.0 and _offense_proxy(build) < offense_target
				and not _board_has_gate_clearing_offense(items)):
			# v74: spend the available search budget instead of settling for
			# utility while the wave-10 or late offense floor is still unmet.
			# v124: but not while an affordable gate-clearing offense item is
			# still on the board — that mandatory-offense buy must not be
			# preempted by the offense-deficient reroll boost.
			worth += 8.0
		if band_gate:
			# v80: still below the winner-DPS band — keep searching for
			# impactful offense instead of settling for the current board.
			worth += BotConfig.OFFENSE_BAND_REROLL_PRESSURE
		var fill_target: int = min(slots, BotConfig.WEAPON_FILL_TARGET) if BotConfig.WEAPON_FILL_TARGET > 0 else 0
		var need_fill: bool = fill_target > 0 and weapons.size() < fill_target
		# v125: hard reroll gate. While offense-deficient with an affordable
		# gate-clearing offense item on the board, the reroll action is disallowed
		# outright — paid AND free (the v124 +8-boost guard above was insufficient:
		# residual worth and especially free rerolls still preempted the buy). The
		# reroll worth and all buy scoring are untouched; if the buy loop bought
		# nothing, the shop-exit below proceeds (exiting with gold beats losing the
		# board). Evidence: reports/wp2/v124_deploy_record.md (run_1784817058_71742).
		var offense_reroll_gate: bool = (offense_target > 0.0
				and _offense_proxy(build) < offense_target
				and _board_has_gate_clearing_offense(items))
		if (best_here < worth or need_fill) and not offense_reroll_gate:
			_session_rerolls += 1
			return {"type": "shop_reroll", "score": best_here}

	# 5) v126 bounded surplus reroll. Everything above has already declined to
	# buy and declined to reroll, so v125 would exit here banking the gold. One
	# reroll at a time while a real spendable surplus survives every reserve;
	# otherwise exit with an explicit reason code.
	var surplus := _surplus_state(items, build, profile, wave, gold, reroll_price)
	if bool(surplus.get("reroll", false)):
		_session_surplus_rerolls += 1
		_session_rerolls += 1
		surplus["surplus_rerolls"] = _session_surplus_rerolls
		return {"type": "shop_reroll", "score": 0.0, "surplus_reroll": true,
			"surplus": surplus}
	if str(surplus.get("exit_reason", "")) != "":
		return {"type": "shop_go", "score": 0.0,
			"exit_reason": surplus["exit_reason"], "surplus": surplus}

	return {"type": "shop_go", "score": 0.0}


# ─────────────────────────── decide_levelup ───────────────────────────────────

func decide_levelup(state: Dictionary, profile, build_override: Dictionary = {}) -> Dictionary:
	var options: Array = state.get("options", [])
	if options.empty():
		return {}
	var build: Dictionary = state.get("build", build_override)
	var wave: int = state.get("wave", 1)
	var forbidden: Array = profile.forbidden_stats
	var target := _offense_target(wave, build)
	if target > 0.0 and _offense_proxy(build) < target:
		var offense_best = null
		var offense_rank := -1e30
		var offense_score := -1e30
		for opt0 in options:
			var effects0: Array = opt0.get("effects", [])
			var blocked0 := false
			for e0 in effects0:
				if forbidden.has(e0.get("key", "")):
					blocked0 = true
					break
			if blocked0:
				continue
			var gain0 := _direct_offense_gain(effects0)
			if gain0 <= 0.0:
				continue
			var score0 := (_effects_value(effects0, build, wave, profile)
				+ _late_shop_pivot_bonus(effects0, build, wave, profile))
			if score0 <= 0.0:
				continue
			var rank0 := score0 + gain0 * 6.0
			if rank0 > offense_rank:
				offense_best = opt0
				offense_rank = rank0
				offense_score = score0
		if offense_best != null:
			return {"type": "levelup_choose", "index": offense_best["index"],
				"score": offense_score, "offense_first": true}
	var best = null
	var best_score: float = -1e30
	for opt in options:
		var effects: Array = opt.get("effects", [])
		var s: float
		var blocked := false
		if not forbidden.empty():
			for e in effects:
				if forbidden.has(e.get("key", "")):
					blocked = true; break
		if blocked:
			s = -1e9
		else:
			s = (_effects_value(effects, build, wave, profile)
				+ _late_shop_pivot_bonus(effects, build, wave, profile))
		if s > best_score:
			best_score = s; best = opt

	var reroll_price: int = state.get("reroll_price", 0)
	if (best_score < BotConfig.LEVELUP_REROLL_WORTH and options.size() > 1
		and reroll_price > 0
		and state.get("gold", 0) >= reroll_price * BotConfig.LEVELUP_REROLL_GOLD_FACTOR
		and state.get("reroll_count", 0) < BotConfig.LEVELUP_REROLL_CAP):
		return {"type": "levelup_reroll"}

	if best == null: return {}
	return {"type": "levelup_choose", "index": best["index"], "score": best_score}


# ─────────────────────────── decide_crate ─────────────────────────────────────

func decide_crate(state: Dictionary, profile, build_override: Dictionary = {}) -> Dictionary:
	var item: Dictionary = state.get("item", {})
	if item.empty(): return {"type": "crate_take"}
	var build: Dictionary = state.get("build", build_override)
	var weapons: Array = build.get("weapons", []) if build != null else []
	if item.get("category") == "weapon":
		if not _weapon_matches_allowlist(item, profile, weapons):
			return {"type": "crate_discard"}
		var wtype: String = item.get("weapon_type", "ranged")
		if wtype == "melee" and not profile.allow_melee:
			return {"type": "crate_discard"}
		return {"type": "crate_take"}
	var wave: int = state.get("wave", 1)
	if _is_vetoed(item, build, wave): return {"type": "crate_discard"}
	if not BotConfig.rogueranker_item_allowed(item.get("id"), wave):
		return {"type": "crate_discard"}
	var score = (_effects_value(item.get("effects", []), build, wave, profile)
		+ _tag_score(item.get("tags", []), profile, wave)
		+ _late_shop_pivot_bonus(item.get("effects", []), build, wave, profile))
	return {"type": "crate_take"} if score >= BotConfig.CRATE_MIN_SCORE else {"type": "crate_discard"}
