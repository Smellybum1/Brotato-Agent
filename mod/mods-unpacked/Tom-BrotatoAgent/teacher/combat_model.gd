extends Reference
class_name BotCombatModel

# Real DPS / effective-HP formulas, ported from combat_model.py.
# Used by shop / level-up valuation: item worth = % DPS gain + % EHP gain.

# class_name BotConfig isn't visible at parse time when this script lives
# inside a mod zip, so preload the script and treat it as the type alias.
const BotConfig := preload("res://mods-unpacked/Tom-BrotatoAgent/teacher/config.gd")

const _DEFAULT_CRIT_DAMAGE := 2.0

const _DAMAGE_STATS := [
	"stat_percent_damage", "stat_ranged_damage", "stat_melee_damage",
	"stat_elemental_damage", "stat_damage",
]


static func _f(v) -> float:
	# The mod sends untracked stats as null (GDScript Utils.get_stat returns
	# null when a stat is 0/unset); guard every read.
	return float(v) if (typeof(v) == TYPE_INT or typeof(v) == TYPE_REAL) else 0.0


static func weapon_dps(weapon: Dictionary, stats: Dictionary) -> float:
	var flat: float = _f(weapon.get("damage"))
	var scaling = weapon.get("scaling", [])
	for s in scaling:
		if typeof(s) == TYPE_ARRAY and s.size() >= 2:
			flat += _f(stats.get(s[0])) * _f(s[1])
	flat = max(1.0, flat)

	var hit: float = flat * (1.0 + _f(stats.get("stat_percent_damage")) / 100.0)

	var crit_chance: float = _f(weapon.get("crit_chance")) + _f(stats.get("stat_crit_chance")) / 100.0
	crit_chance = clamp(crit_chance, 0.0, 1.0)
	var crit_damage: float = _f(weapon.get("crit_damage"))
	if crit_damage == 0.0:
		crit_damage = _DEFAULT_CRIT_DAMAGE
	crit_damage += _f(stats.get("stat_crit_damage")) / 100.0
	hit *= 1.0 + crit_chance * max(0.0, crit_damage - 1.0)

	var cooldown: float = max(1.0, _f(weapon.get("cooldown")))
	if cooldown == 0.0:
		cooldown = 60.0
	var rate: float = (1.0 + _f(stats.get("stat_attack_speed")) / 100.0) * 60.0 / cooldown
	return hit * rate


static func total_dps(weapons: Array, stats: Dictionary) -> float:
	var sum := 0.0
	for w in weapons:
		sum += weapon_dps(w, stats)
	return sum


# Weapon-aware clear estimate for the HUD and offense adequacy policy.  The
# original DPS helper intentionally models one direct hit per attack; this
# companion estimate also accounts for pellets and repeat-hit mechanics so a
# tiered shotgun/explosive loadout is not rated like six tier-I single shots.
static func effective_weapon_dps(weapon: Dictionary, stats: Dictionary) -> float:
	var direct := weapon_dps(weapon, stats)
	var projectiles := max(1.0, _f(weapon.get("nb_projectiles")))
	var piercing := max(0.0, _f(weapon.get("piercing")))
	var pierce_keep := clamp(1.0 - _f(weapon.get("piercing_dmg_reduction")), 0.0, 1.0)
	var bounce := max(0.0, _f(weapon.get("bounce")))
	var bounce_keep := clamp(1.0 - _f(weapon.get("bounce_dmg_reduction")), 0.0, 1.0)
	var crowd_mult := (1.0
		+ piercing * pierce_keep * 0.35
		+ bounce * bounce_keep * 0.25)
	var sets: Array = weapon.get("sets", [])
	if sets.has("set_explosive"):
		crowd_mult *= 1.15
	if bool(weapon.get("burning", false)):
		crowd_mult *= 1.10
	return direct * projectiles * crowd_mult


static func total_effective_weapon_dps(weapons: Array, stats: Dictionary) -> float:
	var sum := 0.0
	for weapon in weapons:
		sum += effective_weapon_dps(weapon, stats)
	return sum


static func offense_rating(build: Dictionary) -> Dictionary:
	var stats: Dictionary = build.get("stats", {})
	var weapons: Array = build.get("weapons", [])
	var stat_score := (_f(stats.get("stat_ranged_damage"))
		+ _f(stats.get("stat_percent_damage"))
		+ _f(stats.get("stat_attack_speed")))
	var estimated_dps := total_effective_weapon_dps(weapons, stats)
	# Keep the familiar 70/120 scale while translating estimated weapon DPS
	# into equivalent offense points.  max() avoids double-counting the same
	# stats already embedded in the weapon DPS calculation.
	var weapon_score := estimated_dps / BotConfig.OFFENSE_WEAPON_DPS_PER_POINT
	var tier_sum := 0
	for weapon in weapons:
		tier_sum += int(weapon.get("tier", 0)) + 1
	return {
		"stat_score": stat_score,
		"weapon_dps": estimated_dps,
		"weapon_score": weapon_score,
		"weapon_tier_sum": tier_sum,
		"weapon_count": weapons.size(),
		"total": max(stat_score, weapon_score),
	}


static func effective_hp(stats: Dictionary, wave: int, caps: Dictionary = {}) -> float:
	var max_hp: float = max(1.0, _f(stats.get("stat_max_hp")))
	var armor: float = _f(stats.get("stat_armor"))

	var dodge: float = _f(stats.get("stat_dodge")) / 100.0
	var dodge_cap_raw: float = _f(caps.get("stat_dodge"))
	if dodge_cap_raw == 0.0:
		dodge_cap_raw = BotConfig.DODGE_CAP_DEFAULT
	var dodge_cap: float = dodge_cap_raw / 100.0
	dodge = clamp(dodge, 0.0, dodge_cap)

	var enemy_hit: float = BotConfig.ENEMY_HIT_BASE + BotConfig.ENEMY_HIT_PER_WAVE * max(0, wave)
	var taken: float = max(enemy_hit * BotConfig.MIN_DAMAGE_TAKEN_FRAC, max(enemy_hit - armor, 1.0))
	var ehp: float = max_hp * (enemy_hit / taken) / (1.0 - dodge)
	ehp += _f(stats.get("stat_hp_regeneration")) * BotConfig.REGEN_WINDOW
	return ehp


static func defense_ehp_index(stats: Dictionary, wave: int) -> float:
	# v80 HUD/telemetry survivability index: wave-scaled effective HP plus a
	# lifesteal throughput term. Display/telemetry only — policy decisions keep
	# using effective_hp and the per-layer adequacy floors directly.
	return effective_hp(stats, wave) + _f(stats.get("stat_lifesteal")) * BotConfig.LIFESTEAL_EHP_WEIGHT


static func run_strength_index(dps: float, dps_target: float, ehp: float,
		ehp_target: float, p90_density: float, conversion: float) -> Dictionary:
	# v81 Run Strength Index (display/telemetry only): 100 = tracking the
	# median winning run at this wave. Components are normalized against the
	# winner-trajectory curves; durability is hard-capped at par so the index
	# never rewards stacking defense past the demonstrated-sufficient floor.
	var power := clamp(dps / max(dps_target, 1.0), 0.0, BotConfig.RSI_POWER_CAP)
	var control := clamp(
		BotConfig.RSI_CONTROL_P90_REF / max(p90_density, BotConfig.RSI_CONTROL_P90_REF),
		0.0, 1.0)
	var durability := clamp(ehp / max(ehp_target, 1.0), 0.0, 1.0)
	var conv := clamp(conversion, 0.0, 1.0)
	var total := 100.0 * (BotConfig.RSI_WEIGHT_POWER * power
		+ BotConfig.RSI_WEIGHT_CONTROL * control
		+ BotConfig.RSI_WEIGHT_DURABILITY * durability
		+ BotConfig.RSI_WEIGHT_CONVERSION * conv)
	return {
		"power": power,
		"control": control,
		"durability": durability,
		"conversion": conv,
		"total": total,
	}


static func apply_deltas(stats: Dictionary, deltas: Dictionary, gain_mods: Dictionary = {}) -> Dictionary:
	# A character's gain_mods amplify stat GAINS (Ranger: ranged +50%, max_hp -25%).
	var out := stats.duplicate()
	for stat in deltas:
		var gain: float = 1.0 + _f(gain_mods.get(stat)) / 100.0
		out[stat] = _f(out.get(stat)) + _f(deltas[stat]) * max(0.0, gain)
	return out


# Value of a set of stat changes = weighted % improvement in DPS and EHP.
# Percentages give natural diminishing returns.
# profile (optional, BuildProfile) tunes damage-stat valuation:
#   * dps_gain_weight scales the DPS term (Pacifist=0 disables 0->DPS windfall)
#   * flat_damage_value adds per-point bonus for damage stats (Bull explode)
static func combat_value(build: Dictionary, deltas: Dictionary, wave: int, profile = null) -> float:
	var weapons: Array = build.get("weapons", [])
	var stats: Dictionary = build.get("stats", {})
	var gain_mods: Dictionary = build.get("gain_mods", {})
	var caps: Dictionary = build.get("caps", {})

	var new_stats := apply_deltas(stats, deltas, gain_mods)

	var dps0: float = total_dps(weapons, stats)
	var dps1: float = total_dps(weapons, new_stats)
	var ehp0: float = effective_hp(stats, wave, caps)
	var ehp1: float = effective_hp(new_stats, wave, caps)

	var dps_gain: float = 0.0
	if dps0 > 0:
		dps_gain = 100.0 * (dps1 - dps0) / dps0
	elif dps1 > 0:
		dps_gain = 100.0  # from-0 to positive is huge; capped to a constant
	var ehp_gain: float = 100.0 * (ehp1 - ehp0) / max(ehp0, BotConfig.EHP_REF)

	var speed_gain: float = (_f(new_stats.get("stat_speed")) - _f(stats.get("stat_speed"))) * BotConfig.SPEED_VALUE

	var dps_weight: float = 1.0
	var flat_dmg_w: float = 0.0
	var speed_w: float = 1.0
	var ehp_w: float = 1.0
	if profile != null:
		dps_weight = profile.dps_gain_weight
		flat_dmg_w = profile.flat_damage_value
		speed_w = profile.speed_value_multiplier
		ehp_w = profile.ehp_value_multiplier
		# Wave 15+: WR leans harder into DPS + tank for elites/bosses.
		if wave >= BotConfig.LATE_SHOP_WAVE and str(profile.name) == "well_rounded":
			dps_weight *= 1.50
			ehp_w *= 1.35
			flat_dmg_w = max(flat_dmg_w, 0.85)

	var score: float = (BotConfig.DPS_PRIORITY * dps_gain * dps_weight
		+ BotConfig.DEF_PRIORITY * ehp_gain * ehp_w
		+ speed_gain * speed_w)
	if flat_dmg_w != 0.0:
		for s in _DAMAGE_STATS:
			var v: float = _f(deltas.get(s))
			if v != 0.0:
				var gain: float = 1.0 + _f(gain_mods.get(s)) / 100.0
				score += v * max(0.0, gain) * flat_dmg_w
	return score
