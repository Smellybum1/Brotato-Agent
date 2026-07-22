extends Reference
class_name BotConfig

# Constants ported from the Python prototype's config.py.
# Static dictionary -- kept as `const` so it can be read without instantiating.

# ── Experiments (flip these to revert without hunting through profiles) ───────
# true  = WR Gun-class allowlist + bans (see build_profiles); false = base WR profile
const EXPERIMENT_ANY_GUNS := true
const EXPERIMENT_BANNED_WEAPON_IDS := ["weapon_medical_gun", "weapon_rocket_launcher", "weapon_flamethrower"]
# Any gun (except bans). Soft-prefer this ladder over other guns from wave 1.
const EXPERIMENT_WEAPON_PRIORITY_FROM_WAVE := 1
const EXPERIMENT_PRIORITY_WEAPONS_ONLY := false
const EXPERIMENT_WEAPON_PRIORITY_IDS := [
	"weapon_chain_gun",
	"weapon_minigun",
	"weapon_smg",
	"weapon_double_barrel_shotgun",
]
const EXPERIMENT_WEAPON_PRIORITY_BONUSES := [32.0, 28.0, 16.0, 16.0]
# v73: these rare crowd-clear guns are worth one explicit save/buy attempt.
# Brotato exposes tiers zero-indexed here: purple Minigun = 2, red Chain Gun = 3.
const RARE_GUN_MIN_TIERS := {
	"weapon_chain_gun": 3,
	"weapon_minigun": 2,
}
# Soft penalties for non-priority guns (when priority wave is active).
const EXPERIMENT_NON_PRIORITY_WEAPON_PENALTY := 10.0
const EXPERIMENT_NEW_TRASH_FAMILY_PENALTY := 8.0
# Native shop combines have produced reproducible Brotato access violations.
# v51 permits one combine only after a full loadout; the controller then pauses
# and requires a freshly observed inventory change before any further action.
const EXPERIMENT_COMBINE_ASAP := false
# Fill toward this many weapon slots after combines (any gun except bans).
const WEAPON_FILL_TARGET := 6
# Hard RR allowlist only from this wave through 20; earlier waves use soft RR bonus only.
const EXPERIMENT_ROGUERANKER_ITEMS_ONLY := true
const ROGUERANKER_ITEMS_ONLY_FROM_WAVE := 11
# Extra score so T3/T4 shop weapons beat random items / base guns.
const HIGH_TIER_WEAPON_BONUS := 16.0
const MAX_TIER_WEAPON_BONUS := 28.0
# Sell a lower-tier gun to free a slot / bank gold for a higher-tier shop gun.
const TIER_REPLACE_MIN_GAP := 1
const TIER_REPLACE_SCORE_MARGIN := 4.0
# Weapon-over-item shop nudge (0 = off).
const WEAPON_OVER_ITEM_BONUS := 0.0
const WEAPON_OVER_ITEM_THROUGH_WAVE := 10

# ── Potential-field forces ─────────────────────────────────────────────────────
const ENEMY_REPULSION := 600.0
const BOSS_REPULSION := 1800.0
const PROJECTILE_REPULSION := 1000.0
const LOOT_ATTRACTION := 120.0
const CONSUMABLE_ATTRACTION := 100.0
# Item boxes / upgrade crates: chase hard — mid-wave upgrades snowball.
const ITEM_BOX_ATTRACTION := 980.0
const VALUABLE_LOOT_MULT := 2.2
const VALUABLE_CONTACT_ABORT := 0.40
# Early/mid waves: stay greedy + hunt packs through ~wave 15 (snowball gold/XP).
# Greed used to taper to ~1x by wave 13 — agent DPS-camped mid-map and left gold.
const EARLY_LOOT_WAVE := 15
const EARLY_LOOT_MULT := 5.5
# Hold near-max greed through mid waves; only soft-taper after this wave.
const EARLY_LOOT_PLATEAU_WAVE := 12
const EARLY_LOOT_FLOOR := 4.2
const SPARSE_LOOT_ENEMIES := 14
const SPARSE_LOOT_MULT := 2.6
const EARLY_LOOT_SAFETY_FLOOR := 0.92
const EARLY_LOOT_CONTACT_ABORT := 0.28
# Don't dive through a living pack for gold — clear the forward group first.
const LOOT_PACK_ALLOW := 2
const LOOT_PATH_WIDTH := 120.0
const LOOT_PILE_CLEAR_RADIUS := 160.0
# Farm mode: vacuum gold AND hunt packs for kills/XP before the wave timer.
const EARLY_HUNT_WAVE := 15
const EARLY_HUNT_PULL := 0.72
const EARLY_HUNT_CLUSTER := 0.45
# Keep optimal DPS band tight all run (not only early).
const DPS_ENGAGE_SCALE := 0.78
const EARLY_CAUTION_SCALE := 0.85
# When arena is sparse and gold is down, yield combat hard so vacuum wins.
const EARLY_LOOT_VS_HUNT := 0.38
const EARLY_LOOT_HUNT_SCALE := 0.35
const LATE_SOFT_OUTER := 1.20
# Wave 16+: dense packs → skate the border and orbit instead of mid-map hugging.
const LATE_EDGE_KITE_WAVE := 16
const LATE_EDGE_KITE_NEARBY := 10
const EDGE_RAIL_INSET := 180.0
const EDGE_BIAS := 0.85
const EDGE_ORBIT := 1.15
const EDGE_PACK_SHOVE := 2.75
const EDGE_ENGAGE_SCALE := 1.18
const EDGE_CAUTION_SCALE := 1.55
# Dense late waves can carry the edge orbit into a corner where both exits
# collapse.  Keep the rail strategy, but force a decisive inward line once
# two arena boundaries are simultaneously close.
const LATE_CORNER_GUARD_MARGIN := 280.0
const LATE_CORNER_KEEP_MOVE := 0.25
# Waves 17-19 repeatedly produced fatal hit chains even after v66 fixed the
# build's early HP deficit. Once a late-wave hit removes meaningful health,
# disengage promptly into the proven pure-repulsion path until the build
# recovers. Wave 20 is excluded: its dedicated finale controller prioritizes
# central map control, projectile clearance, and corner avoidance.
const LATE_SURVIVAL_WAVE := 17
const LATE_SURVIVAL_HP_RATIO := 0.85
const LATE_SURVIVAL_SMOOTHING := 0.70
# Wave 20 finale: ignore loot and prioritize survival near the arena interior.
# Automatic fire supplies boss damage without a movement-enforced range ring.
const BOSS_FINALE_WAVE := 20
const BOSS_FINALE_PROJ_CAUTION := 2.40
const BOSS_FINALE_PROJ_URGENCY_FLOOR := 0.55
const BOSS_FINALE_PROJ_URGENCY_MULT := 1.35
# v92: v91's 320-unit floor worked when sampled inside it, but three lethal
# 16-damage hits were sampled with the boss at 350-406 units. Begin the direct
# outward correction outside that measured charge envelope while remaining in
# the shortest weapon's live firing range.
const BOSS_FINALE_CONTACT_ESCAPE_DISTANCE := 420.0
# v77: wave-20 vectors were recomputed at 60 Hz and repeatedly reversed under
# symmetric boss/projectile pressure.  Hold commands at 20 Hz, strongly prefer
# an already-open escape lane, and turn across a reversal instead of cancelling.
const BOSS_FINALE_RECOMPUTE_DIVISOR := 3
const BOSS_FINALE_ESCAPE_CONTINUITY := 85.0
const BOSS_FINALE_REVERSE_DOT := -0.35
# v78: direction continuity was not enough: all v77 wave-20 runs translated at
# most 10% of commanded path length. Commit to a lane until actual displacement
# is observed, with a short timeout so a blocked lane can be reconsidered.
const BOSS_FINALE_COMMIT_DISTANCE := 120.0
const BOSS_FINALE_COMMIT_MAX_TICKS := 16
const BOSS_FINALE_COMMIT_DESIRE_BLEND := 0.15
# v93: two captured wave-20 deaths reached a corner while the final command
# continued pointing out of bounds. Start a latched interior recovery on any
# wall before the hard boundary, and enforce the final command after smoothing.
const BOSS_FINALE_WALL_RECOVERY_ENTER := 280.0
const BOSS_FINALE_WALL_RECOVERY_RELEASE := 420.0
const BOSS_FINALE_WALL_HARD_MARGIN := 96.0
# v96: combat decisions persist for roughly 250 ms. Project the final command
# slightly beyond that hold so a command selected just outside the hard margin
# cannot carry the player through it before the next decision.
const BOSS_FINALE_WALL_COMMAND_HORIZON := 0.30
# v100: the hard component clamp can rotate a projectile-safe diagonal into a
# dangerous cardinal command. Require a material clearance gain before a
# wall-safe projectile replan replaces the clamped baseline.
const BOSS_FINALE_PROJECTILE_WALL_MIN_GAIN := 20.0
const BOSS_FINALE_WALL_LOOKAHEAD := 260.0
const BOSS_FINALE_WALL_PATH_SAMPLES := 4
const BOSS_FINALE_WALL_CLEAR_WEIGHT := 4.0
const BOSS_FINALE_WALL_BOSS_WEIGHT := 1.35
const BOSS_FINALE_WALL_PROJECTILE_WEIGHT := 1.75
const BOSS_FINALE_WALL_CENTER_WEIGHT := 110.0
const BOSS_FINALE_WALL_DESIRE_WEIGHT := 25.0
const BOSS_FINALE_WALL_CONTINUITY_WEIGHT := 20.0
# Battlefield: chase/destroy trees for crates through wave 10.
const TREE_PRIORITY_WAVE := 10
const TREE_ATTRACTION := 1450.0
const TREE_COMBAT_MULT := 1.75
const TREE_HUNT_YIELD := 0.50
const TREE_THREAT_ABORT := 0.42
const WALL_REPULSION := 800.0
const ENEMY_INFLUENCE_RADIUS := 500.0
const PROJECTILE_INFLUENCE_RADIUS := 300.0
const WALL_MARGIN := 150.0
const SAFETY_DISTANCE := 280.0
const CIRCLING_STRENGTH := 0.55
# At shortest-weapon max range: stop charging the pack and strafe the clear flank.
const ENGAGE_STRAFE := 1.35
const ENGAGE_STRAFE_INWARD_DAMP := 0.18
const ENGAGE_STRAFE_WALL_WEIGHT := 1.40
const ENGAGE_STRAFE_ENEMY_WEIGHT := 1.20
const ENGAGE_STRAFE_LOOKAHEAD := 220.0

# ── Engagement (weapon-aware kiting) ───────────────────────────────────────────
const CONTACT_DANGER := 130.0
const CONTACT_REPULSION := 9000.0
const MIN_ENGAGE_DISTANCE := 120.0
const SAFE_FALLBACK_DISTANCE := 560.0
# Prefer sitting just inside the shortest weapon range so all guns can DPS.
const OPTIMAL_RANGE_FRAC := 0.90
const OPTIMAL_RANGE_PULL := 0.48
const OUT_OF_RANGE_PULL_THRESH := 1.02
const ENGAGE_PULL := 0.12
const ENGAGE_PULL_THRESHOLD := 1.8
const ENGAGE_SPRING_K := 0.030
const ENGAGE_HP_HIGH := 0.80
const ENGAGE_HP_LOW := 0.30
const DEFAULT_ENGAGE_DISTANCE := 480.0
# Extra pack shove when local enemy density is high (WP1 D0 swarm deaths).
const PACK_DENSITY_RADIUS := 280.0
const PACK_DENSITY_SOFT := 8.0
const PACK_DENSITY_HARD := 22.0
const PACK_REPULSION := 1.8

# ── Sampling-based flee (Pacifist) ─────────────────────────────────────────────
const FLEE_HORIZON := 1.0
const FLEE_TIME_SAMPLES := 6
const FLEE_DIRECTIONS := 36
const FLEE_CROWD_RADIUS := 160.0
const FLEE_CROWD_K := 2.0
const FLEE_WALL_MARGIN := 220.0
const FLEE_WALL_PENALTY := 600.0
const FLEE_CENTER_BIAS := 80.0
const FLEE_STUCK_DIST := 300.0
const FLEE_STUCK_CENTER_MULT := 6.0
const FLEE_MOVE_SMOOTHING := 0.85
const FLEE_ENEMY_SPEED_SAFETY := 1.5
const FLEE_BULLET_DANGER := 70.0
const FLEE_BULLET_K := 10.0
const FLEE_BODY_DANGER := 110.0
const FLEE_BODY_K := 0.25
const FLEE_HYSTERESIS_BONUS := 25.0
const FLEE_REVERSE_PENALTY := 0.0
const FLEE_MAX_TURN_RAD := 3.14
const FLEE_AWAY_PENALTY := 800.0
const FLEE_REPEL_RANGE := 360.0
const FLEE_REPEL_K := 0.018

# ── Orbital flee (Beast Master) ────────────────────────────────────────────────
const ORBIT_RADIUS_FRACTION := 0.28
const ORBIT_INNER_FRACTION := 0.6
const ORBIT_RADIAL_MIX_BASE := 0.15
const ORBIT_RADIAL_MIX_GAIN := 0.85
const ORBIT_RADIAL_MIX_MAX := 0.85
const ORBIT_VEER_DIST := 200.0
const ORBIT_VEER_HORIZON := 1.0
const ORBIT_VEER_STEPS := 6
const ORBIT_VEER_STRENGTH := 0.65
const ORBIT_MIN_TANGENT := 0.3
const ORBIT_TANGENT_BLOCK_RADIAL_NUDGE := 1.0
const ORBIT_CRITICAL_DIST := 120.0
const ORBIT_CRITICAL_RADIAL := 4.0

# ── Pure-repulsion flee (Bull, Wounded) ────────────────────────────────────────
const REPULSION_CENTROID_REACH := 350.0
const REPULSION_CENTROID_K := 10.0
const REPULSION_BULLET_REACH := 250.0
const REPULSION_BULLET_K := 60.0
const REPULSION_CENTER_K := 3.0
const REPULSION_CENTER_INNER := 250.0
const REPULSION_CENTER_SPAN := 500.0
const REPULSION_WALL_MARGIN := 320.0
const REPULSION_WALL_K := 80.0
const PURE_REPULSION_SMOOTHING := 0.15
const PANIC_BODY_REACH := 120.0
const PANIC_BULLET_REACH := 140.0
const PURE_REPULSION_PANIC_SMOOTHING := 0.7
const PANIC_WALL_K := 80.0
const PANIC_MIN_MAGNITUDE := 5.0

# ── Bull-specific ──────────────────────────────────────────────────────────────
const BULL_ATTACK_HP_RATIO := 0.6
const BULL_CLUSTER_MIN := 4
const BULL_CLUSTER_RADIUS := 250.0

# ── Movement smoothing & misc ──────────────────────────────────────────────────
const BOSS_WEIGHT := 2.5
const MOVE_SMOOTHING := 0.30

# ── Stop-and-shoot (Soldier) ───────────────────────────────────────────────────
const STAND_DANGER_DIST := 150.0
const STAND_BULLET_CLEAR := 95.0

# ── Predictive dodging / escape sampling ───────────────────────────────────────
const ENEMY_LOOKAHEAD := 0.25
const PROJ_MAX_HORIZON := 0.9
const PROJ_THREAT_RADIUS := 130.0
const ESCAPE_DIRECTIONS := 24
const ESCAPE_HORIZON := 0.60
const ESCAPE_TIME_SAMPLES := 6
const ESCAPE_SAFE_CLEARANCE := 155.0
const ESCAPE_PANIC_CLEARANCE := 55.0
const ESCAPE_WALL_MARGIN := 90.0
const ESCAPE_WALL_PENALTY := 250.0
const ESCAPE_ALIGN_BONUS := 14.0
const ENEMY_AVOID_DIST := 120.0
const ENEMY_AVOID_PENALTY := 4.0

# ── Combat model (DPS / EHP valuation) ─────────────────────────────────────────
const DPS_PRIORITY := 1.0
const DEF_PRIORITY := 0.55
const SPEED_VALUE := 0.6
const ENEMY_HIT_BASE := 8.0
const ENEMY_HIT_PER_WAVE := 2.5
const MIN_DAMAGE_TAKEN_FRAC := 0.25
const REGEN_WINDOW := 6.0
const DODGE_CAP_DEFAULT := 70.0
const EHP_REF := 50.0

# ── Shop strategy ──────────────────────────────────────────────────────────────
const SHOP_MIN_SCORE := 4.0
const SHOP_GOLD_RESERVE := 0
const SHOP_REROLL_GOLD_FACTOR := 4.0
const CRATE_MIN_SCORE := 0.0
const SHOP_ACTION_INTERVAL := 0.55
const SHOP_PREMIUM_SCORE := 13.0
const SHOP_PREMIUM_REACH := 2.2
# Tighter rerolls: bank gold for T2/T3 weapons + tank instead of burning boards.
const SHOP_REROLL_WORTH := 8.0
const SHOP_RICH_GOLD_BASE := 120
const SHOP_RICH_GOLD_PER_WAVE := 140
const SHOP_RICH_GOLD_MAX := 1000
const SHOP_REROLL_RICH_WORTH := 22.0
const SHOP_MAX_REROLLS := 5
const SHOP_REROLL_GOLD_STEP := 180
const SHOP_MAX_REROLLS_CAP := 28
const SHOP_RICH_MIN_BUY := 1.0
const FINAL_SHOP_WAVE := 19
const FINAL_SHOP_MIN_BUY := 0.0
const SHOP_SELL_MARGIN := 10.0
const SHOP_MED_GOLD_RESERVE := 40
const COMBINE_MIN_WEAPONS := 6
const SHOP_MAX_COMBINES_PER_VISIT := 1
# v61 keeps the safe deferred core transaction and only offers pairs with a
# real upgrades_into path; equal max-tier IDs are not combinable actions.
const SHOP_COMBINES_ENABLED := true
const OFF_BUILD_PENALTY := 16.0
const HEALING_WEAPON_PENALTY := 12.0
const UNKNOWN_EFFECT_WEIGHT := 0.3
# Once we already hold enough base-tier copies, prefer items / upgrades.
const T1_WEAPON_SOFT_CAP := 2
const T1_WEAPON_PENALTY := 22.0
const T2_PLUS_WEAPON_BONUS := 7.0

# ── Tier floors / tag weights ──────────────────────────────────────────────────
const ITEM_TIER_FLOOR := [3.0, 4.0, 8.0, 14.0, 18.0, 24.0, 30.0]
const TAG_STAT_VALUE := 2.0
const TAG_WANTED_BONUS := 3.0
# v78: begin the offense-first pivot in the shop preceding wave 10. v77 could
# already reach 18-27 sustain by wave 9, before the previous pivot activated.
const MID_SHOP_PIVOT_WAVE := 9
const SUSTAIN_CAP_WAVE := 8
const LATE_SHOP_WAVE := 15
const HARVESTING_DEADLINE_WAVE := 14.0
# v69: below-target offense floor (mirror of the v66 below-target HP floor).
# Offense proxy = stat_ranged_damage + stat_percent_damage + stat_attack_speed
# from live build stats. v66-v68 telemetry: offense at wave 18 separates wins
# from losses at d=+2.62 (wins ~137 vs losses ~75) while weapon tier-sums do
# not discriminate — the deficit is offensive stat items/level-ups, with
# losses over-allocating into HP/crit instead.
const OFFENSE_FLOOR_MID := 70.0
const OFFENSE_FLOOR_LATE := 120.0
# v79: v78 died at 199.88 offense after the previous wave reported p90=23 and
# peak=32, while wave 19 exploded to p90=59.5. Keep a larger standing margin,
# react harder to sustained density, and add a separate peak-pressure term.
const OFFENSE_TARGET_MARGIN := 25.0
const OFFENSE_DENSITY_P90_GOAL := 15.0
const OFFENSE_DENSITY_POINTS_PER_ENEMY := 7.0
const OFFENSE_DENSITY_MAX_BONUS := 90.0
const OFFENSE_DENSITY_PEAK_GOAL := 25.0
const OFFENSE_DENSITY_POINTS_PER_PEAK_ENEMY := 2.0
const OFFENSE_DENSITY_MAX_PEAK_BONUS := 30.0
const SHOP_MAX_LOCK_TRANSITIONS_PER_ITEM := 2
# v77 weapon-aware offense calibration.  Estimated loadout DPS is divided by
# this value to remain comparable with the historic 70/120 policy scale.
const OFFENSE_WEAPON_DPS_PER_POINT := 15.0
# v82: winner-trajectory DPS curve recalibrated on 41 victories (v70:2, v71:11,
# v72:18, v73:1, v76:1, v77:5, v79:3) — ground-truth build_metrics for v76+,
# validated reconstruction (6-8% residual error) for v70-v75. The v80 curve was
# over-fit to 8 lean-build wins: late targets sat 18-48% above what the winning
# population actually needed while mid targets sat 17-26% below. This pooled
# winner-median still flags every observed loss (v79 loss w15: 1498 < 1620).
# The EHP curve does NOT separate wins from losses — treat it as a
# demonstrated-sufficient survivability floor, not a discriminator.
const OFFENSE_DPS_TARGETS_BY_WAVE := [
	45.0, 110.0, 175.0, 230.0, 300.0, 380.0, 450.0, 540.0, 645.0, 765.0,
	935.0, 1150.0, 1280.0, 1430.0, 1620.0, 1900.0, 2150.0, 2400.0, 2650.0, 2900.0,
]
const DEFENSE_EHP_TARGETS_BY_WAVE := [
	16.0, 18.0, 28.0, 32.0, 44.0, 54.0, 62.0, 71.0, 78.0, 97.0,
	97.0, 96.0, 98.0, 104.0, 108.0, 110.0, 110.0, 115.0, 126.0, 131.0,
]
# v80/v82: impactful-offense band gate. From this wave, while estimated weapon
# DPS trails the winner-median curve, mandatory offense accepts only weapons
# whose projected marginal effective-DPS gain clears the fractional floor
# (v82 — replaced the v80 tier>=2 proxy: across 436 wave-13+ weapon buys the
# two gates disagreed on 55%; tier-1 buys had HIGHER median dDPS (209) than
# tier-2+ buys (154, p25=0), and the fractional form is wave-stable at ~7-8%
# median while absolutes drift +82%), immediate combine pairs, or items adding
# at least the minimum direct-offense gain; sub-floor filler guns are excluded
# from ordinary scoring while slots are full; reroll pressure increases.
const OFFENSE_BAND_FROM_WAVE := 13
const OFFENSE_IMPACT_MIN_DPS_GAIN_FRAC := 0.05
const OFFENSE_IMPACT_MIN_ITEM_GAIN := 6.0
const OFFENSE_BAND_REROLL_PRESSURE := 8.0
# v80: EHP-index lifesteal weight (EHP points per 1% lifesteal, display only).
const LIFESTEAL_EHP_WEIGHT := 3.0
# v81 Run Strength Index: 100 = tracking the median winning run at this wave.
# Weights reflect discriminative power in v77/v79 telemetry: est-DPS dominates
# (d≈+2.6 late), density control verifies the DPS is real, durability is
# capped at par because excess EHP never separated wins from losses, and
# conversion punishes banking gold in wave-13+ shops while below the DPS band.
const RSI_WEIGHT_POWER := 0.55
const RSI_WEIGHT_CONTROL := 0.20
const RSI_WEIGHT_DURABILITY := 0.15
const RSI_WEIGHT_CONVERSION := 0.10
const RSI_POWER_CAP := 1.3
const RSI_CONTROL_P90_REF := 15.0
# Run-level aggregate window (analysis): wins/losses only separate from w13.
const RSI_WINDOW_FROM_WAVE := 13
const RSI_WINDOW_TO_WAVE := 19

static func offense_dps_target(wave: int) -> float:
	var idx := int(clamp(wave, 1, OFFENSE_DPS_TARGETS_BY_WAVE.size())) - 1
	return float(OFFENSE_DPS_TARGETS_BY_WAVE[idx])

static func defense_ehp_target(wave: int) -> float:
	var idx := int(clamp(wave, 1, DEFENSE_EHP_TARGETS_BY_WAVE.size())) - 1
	return float(DEFENSE_EHP_TARGETS_BY_WAVE[idx])
# v74 mid-game safety floors. Below the offense target, pure additions to an
# already-safe layer lose to DPS from wave 10 onward.
const DEFENSE_ADEQUATE_MID_MAX_HP := 45.0
const DEFENSE_ADEQUATE_MID_ARMOR := 5.0
const DEFENSE_ADEQUATE_MID_SUSTAIN := 8.0
# v72: once an individual late defensive layer is adequate, stop spending the
# remaining shop budget on more of that same layer while offense is still below
# target. v71's all-three-layers conjunction never activated in either
# offense-starved loss: one already had 72 HP and 32 sustain but only 5 armor.
# Layer-local caps preserve purchases for whichever defensive layers are still
# weak while forcing saturated HP/armor/regeneration offers to lose to DPS.
const DEFENSE_ADEQUATE_MAX_HP := 60.0
const DEFENSE_ADEQUATE_ARMOR := 8.0
const DEFENSE_ADEQUATE_SUSTAIN := 10.0
const INDIRECT_SUSTAIN_ITEM_IDS := [
	"item_garden",
	"item_medical_turret",
	"item_doc_moth",
	"item_butterfly",
	"item_plant",
]
# Before the final shop, boss-only damage must not consume scarce money while
# the general offense proxy is still below target. Wave 19 keeps its old value.
const BOSS_ONLY_PRE_FINAL_PENALTY := 45.0

# WR/SMG trap items seen in late-loss buys (range loss / economy / weak trades).
const WR_ITEM_PENALTIES := {
	"item_head_injury": 28.0,
	"item_wheelbarrow": 16.0,
	"item_cake": 8.0,
	"item_bait": 10.0,
	"item_coupon": 7.0,
	"item_plant": 6.0,
}

# Rogue Ranker item tier list (https://rogueranker.com/brotato-tier-list/ Item Tier List).
# Soft buy bias always — S/A prefer, D deprioritize. Unknown ids get 0.
# Hard allowlist only for waves ROGUERANKER_ITEMS_ONLY_FROM_WAVE..20 when experiment on.
const ROGUERANKER_ITEM_TIER_BONUS := {
	"S": 28.0,
	"A": 18.0,
	"B": 10.0,
	"C": 3.0,
	"D": -12.0,
}
# Community tiers describe an item's ceiling, not whether the current build can
# use it. These requirements veto narrow synergy items until their enabler is
# already present; the table is intentionally data-driven for future additions.
const BUILD_AWARE_ROGUERANKER_ENABLED := true
const BUILD_AWARE_ITEM_REQUIREMENTS := {
	# S: excellent only when their defining engine already exists.
	"item_bloody_hand": {"stat": "stat_lifesteal", "min_stat": 8.0},
	"item_greek_fire": {"weapon_flag": "burning"},
	"item_giant_belt": {"stat": "stat_crit_chance", "min_stat": 20.0},
	"item_explosive_shells": {"weapon_set": "set_explosive"},
	"item_retromations_hoodie": {"stat": "stat_dodge", "min_stat": 20.0},
	# A: veto melee/engineering/elemental specialists on an unrelated gun build.
	"item_focus": {"max_distinct_weapon_families": 2},
	"item_mammoth": {"weapon_type": "melee"},
	"item_diploma": {"any": [
		{"max_wave": 10},
		{"weapon_scaling_stat": "stat_engineering"},
	]},
	"item_lucky_coin": {"stat": "stat_crit_chance", "min_stat": 20.0},
	"item_robot_arm": {"any": [
		{"weapon_type": "melee"},
		{"weapon_scaling_stat": "stat_engineering"},
	]},
	"item_estys_couch": {"stat": "stat_speed", "max_stat": 0.0},
	"item_frozen_heart": {"any": [
		{"weapon_flag": "burning"},
		{"weapon_scaling_stat": "stat_elemental_damage"},
	]},
	"item_stone_skin": {"stat": "stat_armor", "min_stat": 10.0},
	# B: scaling cards need enough runway or a live stat engine.
	"item_power_generator": {"stat": "stat_speed", "min_stat": 10.0},
	"item_vigilante_ring": {"max_wave": 14},
	"item_sad_tomato": {"stat": "stat_hp_regeneration", "min_stat": 5.0},
	"item_strange_book": {"all": [
		{"stat": "stat_elemental_damage", "min_stat": 5.0},
		{"weapon_scaling_stat": "stat_engineering"},
	]},
	"item_pile_of_books": {"weapon_scaling_stat": "stat_engineering"},
	"item_snowball": {"all": [
		{"max_wave": 12},
		{"any": [
			{"weapon_flag": "burning"},
			{"weapon_scaling_stat": "stat_elemental_damage"},
		]},
	]},
	"item_crown": {"all": [
		{"stat": "stat_harvesting", "min_stat": 10.0},
		{"max_wave": 12},
	]},
	"item_black_belt": {"any": [
		{"max_wave": 8},
		{"weapon_type": "melee"},
	]},
	"item_mouse": {"stat": "stat_lifesteal", "min_stat": 5.0},
	# C: modest payoffs do not justify a dead or late purchase.
	"item_alien_eyes": {"stat": "stat_max_hp", "min_stat": 50.0},
	"item_handcuffs": {"min_wave": 15},
	"item_metal_detector": {"max_wave": 12},
	"item_ice_cube": {"any": [
		{"weapon_flag": "burning"},
		{"weapon_scaling_stat": "stat_elemental_damage"},
	]},
	"item_regeneration_potion": {"stat": "stat_hp_regeneration", "min_stat": 5.0},
	"item_bean_teacher": {"max_wave": 12},
	"item_peacock": {"never": true},
	# D: unacceptable variance/downside for an 18-of-20 reliability gate.
	"item_weird_ghost": {"never": true},
	"item_hourglass": {"never": true},
	"item_gobblers_hat": {"never": true},
	"item_bait": {"never": true},
	"item_black_flag": {"never": true},
	"item_axolotl": {"never": true},
	# The +40 attack speed is active only while standing still; this agent
	# continuously kites and always pays the unconditional -10 speed cost.
	"item_statue": {"never": true},
	# Forced 1 HP/sec damage consumed roughly a full health bar every wave in
	# all three v63 purchases and contributed to the repaired wave-19 loss.
	"item_blood_donation": {"never": true},
	"item_ashes": {"all": [
		{"min_wave": 16},
		{"stat": "stat_armor", "min_stat": 8.0},
	]},
	# Useful wiki additions that still need timing, economy, or safety context.
	"item_baby_elephant": {"stat": "stat_luck", "min_stat": 20.0},
	"item_bag": {"max_wave": 15},
	"item_community_support": {"stat": "stat_armor", "min_stat": 5.0},
	"item_cyberball": {"stat": "stat_luck", "min_stat": 20.0},
	"item_fertilizer": {"max_wave": 12},
	"item_gambling_token": {"stat": "stat_armor", "min_stat": 3.0},
	"item_glass_cannon": {"stat": "stat_armor", "min_stat": 8.0},
	"item_gummy_berserker": {"stat": "stat_armor", "min_stat": 3.0},
	"item_eyepatch": {"stat": "stat_crit_chance", "min_stat": 15.0},
	"item_hunting_trophy": {"stat": "stat_crit_chance", "min_stat": 20.0},
	"item_injection": {"stat": "stat_max_hp", "min_stat": 25.0},
	"item_little_frog": {"all": [
		{"max_wave": 10},
		{"stat": "stat_dodge", "min_stat": 8.0},
	]},
	"item_piggy_bank": {"max_wave": 12},
	"item_pearl": {"stat": "stat_luck", "min_stat": 20.0},
	"item_propeller_hat": {"max_wave": 12},
	"item_recycling_machine": {"max_wave": 16},
	"item_scar": {"max_wave": 12},
	"item_spyglass": {"max_wave": 16},
	"item_sunglasses": {"stat": "stat_armor", "min_stat": 4.0},
	"item_treasure_map": {"max_wave": 15},
	"item_tree": {"max_wave": 14},
}
const ROGUERANKER_ITEM_TIERS := {
	# S
	"item_bloody_hand": "S",
	"item_greek_fire": "S",
	"item_giant_belt": "S",
	"item_explosive_shells": "S",
	"item_retromations_hoodie": "S",
	"item_potato": "S",
	"item_grinds_magical_leaf": "S",
	# A
	"item_focus": "A",
	"item_spider": "A",
	"item_ball_and_chain": "A",
	"item_heavy_bullets": "A",
	"item_mammoth": "A",
	"item_night_goggles": "A",
	"item_octopus": "A",
	"item_diploma": "A",
	"item_lucky_coin": "A",
	"item_coil": "A",
	"item_exoskeleton": "A",
	"item_robot_arm": "A",
	"item_estys_couch": "A",
	"item_clover": "A",
	"item_frozen_heart": "A",
	"item_stone_skin": "A",
	"item_lure": "A",
	# B
	"item_alloy": "B",
	"item_power_generator": "B",
	"item_vigilante_ring": "B",
	"item_sad_tomato": "B",
	"item_tardigrade": "B",
	"item_candle": "B",
	"item_medikit": "B",
	"item_extra_stomach": "B",
	"item_strange_book": "B",
	"item_pile_of_books": "C",
	"item_snowball": "D",
	"item_ricochet": "B",
	"item_crown": "B",
	"item_black_belt": "B",
	"item_jetpack": "B",
	"item_panda": "B",
	"item_mouse": "B",
	# C
	"item_shackles": "C",
	"item_alien_eyes": "C",
	"item_coupon": "C",
	"item_goblet": "C",
	"item_sunken_bell": "C",
	"item_handcuffs": "C",
	"item_metal_detector": "C",
	"item_sifds_relic": "C",
	"item_cape": "C",
	"item_ice_cube": "D",
	"item_leather_vest": "C",
	"item_regeneration_potion": "C",
	"item_bean_teacher": "C",
	"item_dangerous_bunny": "C",
	"item_fruit_basket": "C",
	"item_peacock": "C",
	# Conditional damage effects are flattened by the current shop snapshot.
	# Keep these buyable, but do not let them outrank clean offense.
	"item_triangle_of_power": "C",
	"item_wisdom": "C",
	# D
	"item_weird_ghost": "D",
	"item_hourglass": "D",
	"item_gobblers_hat": "D",
	"item_bait": "D",
	"item_black_flag": "D",
	"item_knot": "D",
	"item_axolotl": "D",
	"item_ashes": "D",
	"item_whistle": "D",
}

# Agent-specific additions from the complete Brotato Wiki catalogue. These are
# kept separate so they are not misrepresented as RogueRanker placements. The
# letters reuse the same score bonuses and describe usefulness for the current
# Well-Rounded mixed rapid-fire gun build.
const WIKI_USEFUL_ITEM_TIERS := {
	# S: unusually strong gun-build or reliability payoffs.
	"item_anvil": "S",
	"item_catling_gun": "S",
	"item_jellyshield": "S",
	"item_scapegoat": "S",
	"item_seashell": "S",
	"item_white_flag": "S",
	# A: strong direct offense, sustain, mobility, or control.
	"item_adrenaline": "A",
	"item_alien_magic": "A",
	"item_alien_worm": "A",
	"item_baby_with_a_beard": "A",
	"item_bandana": "A",
	"item_banner": "A",
	"item_big_arms": "A",
	"item_blindfold": "A",
	"item_doc_moth": "A",
	"item_fin": "A",
	"item_goldfish": "A",
	"item_improved_tools": "A",
	"item_jelly": "A",
	"item_lantern": "A",
	"item_medal": "A",
	"item_mirror": "A",
	"item_poisonous_tonic": "A",
	"item_reinforced_steel": "A",
	"item_ritual": "A",
	"item_sharp_bullet": "A",
	"item_silver_bullet": "A",
	"item_small_magazine": "A",
	"item_tentacle": "A",
	"item_ugly_tooth": "A",
	"item_wandering_bot": "A",
	"item_warrior_helmet": "A",
	"item_wings": "A",
	# B: credible broadly useful cards; normal effect scoring still decides.
	"item_acid": "A",
	# v83 telemetry-audit additions (416-run offer harvest): gun-build offense
	# with priceable downsides; no reason to be unbuyable late.
	"item_honey": "B",
	"item_pumpkin": "B",
	"item_baby_elephant": "B",
	"item_baby_gecko": "B",
	"item_bag": "B",
	"item_bat": "B",
	"item_beanie": "B",
	"item_blood_leech": "B",
	"item_broken_mouth": "B",
	"item_butterfly": "B",
	"item_cake": "B",
	"item_coffee": "B",
	"item_community_support": "B",
	"item_crystal": "B",
	"item_cyberball": "B",
	"item_cyclops_worm": "B",
	"item_eyepatch": "B",
	"item_feather": "B",
	"item_fertilizer": "B",
	"item_fresh_meat": "B",
	"item_gambling_token": "B",
	"item_garden": "B",
	"item_glass_cannon": "B",
	"item_glasses": "B",
	"item_gummy_berserker": "B",
	"item_head_injury": "B",
	"item_helmet": "B",
	"item_hunting_trophy": "B",
	"item_injection": "B",
	"item_insanity": "B",
	"item_lens": "B",
	"item_lootworm": "B",
	"item_lost_duck": "B",
	"item_lucky_charm": "B",
	"item_medical_turret": "B",
	"item_metal_plate": "B",
	"item_missile": "B",
	"item_mushroom": "B",
	"item_mutation": "B",
	"item_padding": "B",
	"item_pearl": "B",
	"item_plant": "B",
	"item_scope": "B",
	"item_shmoop": "B",
	"item_small_fish": "B",
	"item_snail": "B",
	"item_sunglasses": "B",
	"item_terrified_onion": "B",
	"item_wheat": "B",
	"item_whetstone": "B",
	# C: modest or timing-sensitive utility retained as an option.
	"item_alien_tongue": "C",
	"item_clockwork_wasp": "C",
	"item_lemonade": "C",
	"item_little_frog": "C",
	"item_lumberjack_shirt": "C",
	"item_piggy_bank": "C",
	"item_propeller_hat": "C",
	"item_recycling_machine": "C",
	"item_scar": "C",
	"item_scared_sausage": "C",
	"item_spyglass": "C",
	"item_treasure_map": "C",
	"item_tree": "C",
	"item_weird_food": "C",
}

# ── Level-up reroll ────────────────────────────────────────────────────────────
const LEVELUP_REROLL_WORTH := 5.0
const LEVELUP_REROLL_GOLD_FACTOR := 6.0
const LEVELUP_REROLL_CAP := 2

static func rogueranker_item_on_list(item_id) -> bool:
	if item_id == null:
		return false
	return ROGUERANKER_ITEM_TIERS.has(item_id) or WIKI_USEFUL_ITEM_TIERS.has(item_id)


static func rogueranker_item_allowed(item_id, wave: int = 1) -> bool:
	# Soft RR bonus always applies via rogueranker_item_bonus.
	# Hard allowlist only during waves FROM..20 when the experiment is on.
	if not EXPERIMENT_ROGUERANKER_ITEMS_ONLY:
		return true
	if wave < ROGUERANKER_ITEMS_ONLY_FROM_WAVE or wave > 20:
		return true
	return rogueranker_item_on_list(item_id)


static func rogueranker_item_bonus(item_id) -> float:
	if item_id == null:
		return 0.0
	var tiers: Dictionary = ROGUERANKER_ITEM_TIERS
	if not tiers.has(item_id):
		tiers = WIKI_USEFUL_ITEM_TIERS
		if not tiers.has(item_id):
			return 0.0
	var letter = tiers[item_id]
	var bonus: Dictionary = ROGUERANKER_ITEM_TIER_BONUS
	if bonus.has(letter):
		return float(bonus[letter])
	return 0.0

# ── Per-stat utility weights ───────────────────────────────────────────────────
# Combat stats (HP/armor/dodge/AS/crit/damage) go through the DPS/EHP model in
# combat_model.gd, not this table. Anything else (range, harvesting, structures,
# downsides) is valued here. An item effect's sign decides good/bad.
static func utility_weights() -> Dictionary:
	return {
		"stat_lifesteal": 1.0, "stat_range": 0.25, "stat_harvesting": 0.85,
		"stat_engineering": 0.4, "stat_luck": 0.9, "stat_accuracy": 0.2,
		"piercing": 5.0, "piercing_damage": 0.3, "bounce": 1.5,
		"damage_against_bosses": 0.25, "giant_crit_damage": 0.2,
		"explosion_damage": 0.2, "explosion_size": 1.2, "effect_explode": 2.0,
		"explode_on_death": 1.0, "explode_on_consumable": 0.5,
		"projectiles_on_death": 1.0,
		"effect_burning": 2.0, "burn_chance": 0.4, "burning_spread": 0.5,
		"burning_cooldown_reduction": 0.3,
		"hit_protection": 3.0, "jellyshield_count": 2.0, "consumable_heal": 0.4,
		"hp_regen_bonus": 0.8, "heal_on_crit_kill": 0.5,
		"heal_when_pickup_gold": 0.3, "hp_start_next_wave": 0.2,
		"hp_start_wave": 0.2, "hp_cap": 0.2,
		"xp_gain": 0.15, "free_rerolls": 2.0, "items_price": 0.5,
		"recycling_gains": 0.2, "gold_drops": 0.3, "chance_double_gold": 0.2,
		"gold_on_crit_kill": 0.2, "gain_pct_gold_start_wave": 0.2,
		"instant_gold_attracting": 0.05, "pickup_range": 0.1,
		"harvesting_growth": 0.3, "knockback": 0.0,
		"gain_random_primary_stats_on_go_to_next_wave": 3.0, "wandering_bot": 3.0,
		"tree_turrets": 2.0, "trees": 1.5, "one_shot_trees": 1.0,
		"alien_eyes": 1.0, "item_hourglass": 1.0, "item_box_gold": 1.0,
		"lose_hp_per_second": 3.0, "enemy_damage": 0.6, "enemy_health": 0.5,
		"enemy_speed": 0.55, "enemy_fruit_drops": 0.2, "number_of_enemies": 1.2,
		"extra_enemies_next_wave": 1.6, "extra_elite_next_wave_chance": 0.4,
		"extra_loot_aliens_next_wave": 0.5, "fog_visibility": 0.3,
		"remove_speed": 0.5, "speed_cap": 0.3, "dodge_cap": 0.3,
	}
