extends Reference
class_name BotPotentialField

const BotConfig = preload("res://mods-unpacked/Tom-BrotatoAgent/teacher/config.gd")

# Full-fidelity port of potential_field.py. Routes by profile:
#   * default kiter  -> _build_desire + _projectile_escape
#   * flee_mode + use_pure_repulsion_flee -> _pure_repulsion_flee (+ panic, +bull)
#   * flee_mode + use_orbital_flee        -> _orbital_flee (Beast Master)
#   * flee_mode + (neither)                -> _flee_direction (Pacifist sampling, hysteresis)
# Soldier-style stop-and-shoot supported via state.can_attack_while_moving.

var _prev_move = Vector2.ZERO
# v123: strength + tier actually used for THIS decision, emitted per-capture.
var _build_strength_used := 1.0
var _strength_tier := "neutral"
var _finale_commit_dir = Vector2.ZERO
var _finale_commit_origin = Vector2.ZERO
var _finale_commit_ticks := 0
var _finale_commit_distance := 0.0
var _finale_wall_recovery_active := false
var _finale_projectile_safety_active := false
var _finale_projectile_safety_urgency := 0.0
var _finale_projectile_input_clearance := -1.0
var _finale_projectile_escape_clearance := -1.0
var _finale_projectile_blended_clearance := -1.0
var _finale_projectile_blend_repair_active := false
var _finale_projectile_final_clearance := -1.0
var _finale_projectile_wall_replan_active := false
var _finale_wall_input_enemy_penalty := -1.0
var _finale_wall_best_enemy_penalty := -1.0
var _finale_wall_selected_enemy_penalty := -1.0
var _finale_wall_input_body_clearance := -1.0
var _finale_wall_best_body_clearance := -1.0
var _finale_wall_selected_body_clearance := -1.0
var _finale_wall_body_relief_active := false
var _finale_wall_relief_best_body_clearance := -1.0
var _finale_projectile_input_enemy_penalty := -1.0
var _finale_projectile_escape_enemy_penalty := -1.0
var _finale_projectile_blended_enemy_penalty := -1.0
var _finale_projectile_enemy_blend_repair_active := false
var _finale_projectile_final_enemy_penalty := -1.0
var _finale_projectile_input_body_clearance := -1.0
var _finale_projectile_escape_body_clearance := -1.0
var _finale_projectile_blended_body_clearance := -1.0
var _finale_projectile_final_body_clearance := -1.0
var _finale_body_safety_active := false
var _finale_body_emergency_active := false
var _finale_body_input_clearance := -1.0
var _finale_body_best_clearance := -1.0
var _finale_body_selected_clearance := -1.0
var _finale_body_projectile_floor := -1.0
var _finale_body_selected_projectile_clearance := -1.0
# v129 route telemetry: the per-candidate record of the last body-safety ranking.
# Body clearance is an ADMISSION GATE in that ranking and never a preference --
# it does not appear in the lane score at all -- so no scalar summary can say
# which term decided the route. These are the movement analogue of the shop's
# purchase_decision.board_scores. Default-inert: with route_scores_enabled false
# nothing is appended and the emitted command is byte-identical.
var route_scores_enabled: bool = false
var _finale_route_scores := []
# §45 default-inert all-exit geometry instrument. Unlike route_scores, this
# snapshot is populated before baseline_kept can return so a shadow latch can
# revalidate current safety without changing the selected route.
var route_latch_revalidation_enabled: bool = false
var _finale_route_revalidation_ready := false
var _finale_route_revalidation_rows := []
var _finale_route_revalidation_reference_body := -1.0e18
var _finale_route_revalidation_reference_projectile := -1.0e18
var _finale_route_revalidation_reference := Vector2.ZERO
var _finale_route_revalidation_body_floor := -1.0e18
var _finale_route_revalidation_lowest_penalty := -1.0e18
var _finale_route_exit := ""
var _finale_route_body_floor := -1.0e18
var _finale_route_projectile_floor := -1.0e18
var _finale_route_lowest_enemy_penalty := -1.0
var _finale_route_sampled := -1
var _finale_route_floor_admitted := 0
var _finale_route_baseline_admitted := false
# The lane the ranking actually emitted, plus its score. Without these the block
# would prove DELIVERY (rows exist) but not CORRECTNESS (that the recorded rows
# are the ones the decision was made from). With them the check is exact and
# self-contained: the max-scoring non-skipped row must BE the selected lane --
# the same reconciliation that validated the shop's board_scores.
var _finale_route_selected := Vector2.ZERO
var _finale_route_best_score := -1.0e18
# v130: the incoming command the align term is measured against. Recorded so an
# offline reader can re-derive any lane's score from first principles instead of
# trusting the stored one -- the align term is the only score component that
# cannot otherwise be reconstructed from the per-lane record.
var _finale_route_baseline := Vector2.ZERO
# v131: `_prev_move` AS THE SCORING LOOP SAW IT. Reading `_prev_move` inside
# finale_route_debug() is WRONG: the controller calls that after compute_movement
# has already run `_prev_move = final_move`, so it reports THIS tick's output
# instead of the vector the continuity term was measured against. Measured on the
# §32 runs: the two differ on 27.7% of captures (p90 0.31, max 2.00), and on
# exactly the captures where an offline re-derivation mispicked the lane, the
# deviation was median 0.3874 against 0.0000 overall.
# ⛔ THE FIELD WAS STALE IN 0.2.76 AND 0.2.77. For those builds, recover the true
# vector by inverting cont_i = 85.0 * dot(cand_i, prev) across the admitted lanes.
var _finale_route_prev := Vector2.ZERO
# §41 guarded conversion telemetry. Scalars are always emitted so a treatment
# arm can prove delivery without enabling the expensive per-lane scores array.
var clearance_guarded_conversion_enabled: bool = false
var _finale_route_conversion_applied := false
var _finale_route_conversion_floor := -1.0e18
var _finale_route_conversion_input_inrange := -1.0
var _finale_route_conversion_selected_inrange := -1.0
var _finale_route_conversion_gain := 0.0
var _finale_route_conversion_input_body := -1.0
var _finale_route_conversion_selected_body := -1.0
var _finale_route_conversion_guard_vetoed := 0
var _finale_route_conversion_admitted := 0
# Finale controller v2 flag; the controller propagates agent_config.finale_v2.
var finale_v2_enabled: bool = false
# Wave-20 dev flags; the controller propagates agent_config.finale_no_panic and
# agent_config.finale_heal_seek. Default false -- flag-off is byte-identical.
var finale_no_panic_enabled: bool = false
var finale_heal_seek_enabled: bool = false
var finale_range_keep_enabled: bool = false
# Dev flag: give boss-projectile dodging the FINAL word in the safety tail.
# Off, the tail order is projectile -> wall -> body, so wall and body safety can
# both override a dodge. On, projectile safety runs LAST at wave 20.
var finale_projectile_priority_enabled: bool = false
# Dev flag: strafe around the boss in the SAME direction its projectile ring is
# rotating, lowering the relative speed between player and ring. Requires
# finale_pivot_projectiles -- the ring is not in the state without it, so with
# that flag off this term reads zero orbiters and returns Vector2.ZERO.
var finale_co_rotate_enabled: bool = false
# Dev flag: hold the radius band where the agent can out-rotate the ring. Pairs
# with co-rotation -- direction without radius cannot outrun anything, since at
# the agent's usual 566 u it out-rotates only 7% of the time.
var finale_ring_radius_enabled: bool = false
# Dev knob: multiply the engagement standoff distance after the shipped DPS
# scale. Larger holds farther from enemies, smaller closes in. Pure multiplier,
# so 1.0 is exactly inert -- no clamp or floor is added here on purpose.
var engage_distance_scale: float = 1.0
# Dev knob: dose on the body-clearance requirement used by _finale_body_safety,
# the last body arbiter on the emitted command. Pure multiplier on the
# wave-indexed slack and the pack-clearance cap, so 1.0 is exactly inert. The
# 45-unit hard contact floor is deliberately NOT scaled.
var body_clearance_scale: float = 1.0
# Dev knob: threat weight applied to enemies that are NOT currently charging.
# 1.0 (default) is exactly inert. Below 1.0 the agent respects a walking enemy
# less and can close on it, while a charging enemy keeps full weight.
var calm_threat_mult: float = 1.0
# Dev knob: scale the avoid/critical clearance THRESHOLDS applied to enemies that
# are NOT currently charging, inside the safety tail's enemy path penalty
# (_finale_enemy_path_penalty and _predictive_enemy_path_penalty). 1.0 (default)
# is exactly inert and the charge test is not even evaluated. Below 1.0 a walking
# enemy has to be closer before it costs anything, while a charging enemy keeps
# the shipped thresholds. Deliberately SEPARATE from the desire-level
# calm_threat_mult so the two layers stay attributable.
var tail_calm_penalty_mult: float = 1.0
# Dev knob: grant non-charging ENEMIES (never bosses) a clearance credit inside
# _predictive_body_path_clearance. 1.0 (default) makes the credit exactly 0.0 and
# the charge test is not evaluated at all.
var tail_calm_clearance_mult: float = 1.0


func compute_movement(state, profile) -> Vector2:
	var player = state.get("player", {})
	if player.empty():
		return Vector2.ZERO
	var pos = Vector2(player.get("x", 0.0), player.get("y", 0.0))

	# v123: refresh the strength tier once per decision (hysteretic). Consumes the
	# controller's smoothed build_strength; drives ordinary-path aggression only.
	_update_strength_tier(clamp(float(state.get("build_strength", 1.0)), 0.0, 2.0))

	var enemies = state.get("enemies", [])
	var bosses = state.get("bosses", [])
	var projectiles = state.get("projectiles", [])
	var loot = state.get("loot", [])
	var consumables = state.get("consumables", [])
	var trees = state.get("trees", [])
	var weapons = state.get("weapons", [])
	var arena = state.get("arena", {"width": 2048.0, "height": 1536.0})
	var player_speed = float(player.get("speed", 350.0))
	var can_attack_moving = state.get("can_attack_while_moving", true)
	_finale_projectile_safety_active = false
	_finale_projectile_safety_urgency = 0.0
	_finale_projectile_input_clearance = -1.0
	_finale_projectile_escape_clearance = -1.0
	_finale_projectile_blended_clearance = -1.0
	_finale_projectile_blend_repair_active = false
	_finale_projectile_final_clearance = -1.0
	_finale_projectile_wall_replan_active = false
	_finale_wall_input_enemy_penalty = -1.0
	_finale_wall_best_enemy_penalty = -1.0
	_finale_wall_selected_enemy_penalty = -1.0
	_finale_wall_input_body_clearance = -1.0
	_finale_wall_best_body_clearance = -1.0
	_finale_wall_selected_body_clearance = -1.0
	_finale_wall_body_relief_active = false
	_finale_wall_relief_best_body_clearance = -1.0
	_finale_projectile_input_enemy_penalty = -1.0
	_finale_projectile_escape_enemy_penalty = -1.0
	_finale_projectile_blended_enemy_penalty = -1.0
	_finale_projectile_enemy_blend_repair_active = false
	_finale_projectile_final_enemy_penalty = -1.0
	_finale_projectile_input_body_clearance = -1.0
	_finale_projectile_escape_body_clearance = -1.0
	_finale_projectile_blended_body_clearance = -1.0
	_finale_projectile_final_body_clearance = -1.0
	_finale_body_safety_active = false
	_finale_body_emergency_active = false
	_finale_body_input_clearance = -1.0
	_finale_body_best_clearance = -1.0
	_finale_body_selected_clearance = -1.0
	_finale_body_projectile_floor = -1.0
	_finale_body_selected_projectile_clearance = -1.0
	# Reset here as well as on entry to _finale_body_safety: the FLEE branches
	# below return without ever calling it, so without this a stale block would
	# read exactly like a fresh one. "not_reached" is a value no real ranking can
	# produce, so a missed reset cannot masquerade as data.
	_reset_finale_route()

	# FLEE-mode branches (Pacifist/Beast Master/Bull/Wounded etc).
	if profile.flee_mode:
		var desire_flee: Vector2
		var alpha_flee: float
		if profile.use_pure_repulsion_flee:
			# Pure repulsion + (optional) panic + (optional) bull cluster rush.
			var panic_dir = _panic_dodge(pos, enemies, bosses, projectiles, arena)
			if panic_dir != Vector2.ZERO:
				desire_flee = panic_dir
				alpha_flee = BotConfig.PURE_REPULSION_PANIC_SMOOTHING
			else:
				if profile.bull_mode:
					var hp_ratio = float(player.get("hp", 1)) / max(float(player.get("max_hp", 1)), 1.0)
					if hp_ratio >= BotConfig.BULL_ATTACK_HP_RATIO:
						var rush = _bull_attack_dir(pos, enemies, bosses, arena)
						if rush != Vector2.ZERO:
							desire_flee = rush
							alpha_flee = BotConfig.PURE_REPULSION_SMOOTHING
							var smoothed_bull = _prev_move * (1.0 - alpha_flee) + desire_flee * alpha_flee
							_prev_move = _normalize(smoothed_bull)
							return _prev_move
				desire_flee = _pure_repulsion_flee(pos, enemies, bosses, projectiles, arena, _prev_move)
				alpha_flee = BotConfig.PURE_REPULSION_SMOOTHING
		elif profile.use_orbital_flee:
			desire_flee = _orbital_flee(pos, enemies, bosses, projectiles, arena, _prev_move, player_speed)
			alpha_flee = BotConfig.FLEE_MOVE_SMOOTHING
		else:
			# Pacifist sampling-based flee with hysteresis.
			desire_flee = _flee_direction(pos, enemies, bosses, arena, player_speed, projectiles, _prev_move, profile)
			alpha_flee = BotConfig.FLEE_MOVE_SMOOTHING
		var smoothed_flee = _prev_move * (1.0 - alpha_flee) + desire_flee * alpha_flee
		_prev_move = _normalize(smoothed_flee)
		return _prev_move

	# Standard kiter desire field.
	var wave: int = int(state.get("wave", 1))
	if wave < BotConfig.BOSS_FINALE_WAVE:
		_reset_finale_commit()
		# v103: retain the v102 late-wave latch, now with a wider release buffer.
		# v102 evidence showed that releasing at 420 units let a dense pack pull
		# the agent immediately back into a 285-310 unit reversal stall. The 520
		# unit release boundary keeps recovery committed through that unsafe band.
		# v102: v101 wave-19 evidence showed the late safety tail chattering at
		# the 280-unit entry boundary because this reset discarded the intended
		# 280/520 hysteresis before every waves 17-19 decision. Clear the latch
		# only before late-wave wall safety becomes active; once entered on a
		# late wave, recovery must persist until the 520-unit release boundary.
		if wave < BotConfig.LATE_SURVIVAL_WAVE:
			_finale_wall_recovery_active = false
	var hp_ratio = float(player.get("hp", 1)) / max(float(player.get("max_hp", 1)), 1.0)
	if (wave >= BotConfig.LATE_SURVIVAL_WAVE
		and wave < BotConfig.BOSS_FINALE_WAVE
		and hp_ratio <= BotConfig.LATE_SURVIVAL_HP_RATIO
		and (not enemies.empty() or not bosses.empty() or not projectiles.empty())):
		# v67: all three v66 gate losses reached wave 17 with 67-76 HP, then
		# died to chained hits. On waves 17-19, stop re-engaging at low health
		# and use the battle-tested panic/pure-repulsion path until recovery.
		# Wave 20 instead uses its center-biased finale survival controller.
		# v118: survival always outranks collection; drop any active dash.
		_suppress_loot_dash("suppressed_survival")
		var survival_dir = _panic_dodge(pos, enemies, bosses, projectiles, arena)
		if survival_dir == Vector2.ZERO:
			survival_dir = _pure_repulsion_flee(
				pos, enemies, bosses, projectiles, arena, _prev_move)
		var smoothed_survival = (_prev_move * (1.0 - BotConfig.LATE_SURVIVAL_SMOOTHING)
			+ survival_dir * BotConfig.LATE_SURVIVAL_SMOOTHING)
		# v98: the late-survival branch used to return here before the final
		# projectile and wall constraints. That allowed dense threats to push its
		# command outward while physically pinned inside the hard wall margin.
		# Apply the same ordered safety tail used by the finale before returning.
		var safe_survival = _normalize(smoothed_survival)
		safe_survival = _finale_projectile_safety(
			pos, safe_survival, projectiles, player_speed, arena, enemies, bosses, profile)
		safe_survival = _finale_wall_safety(
			pos, safe_survival, arena, bosses, projectiles, player_speed,
			enemies, profile)
		safe_survival = _finale_body_safety(
			pos, safe_survival, player_speed, arena, enemies, bosses,
			projectiles, profile, weapons, wave, true)
		_prev_move = safe_survival
		return _prev_move
	var finale = wave >= BotConfig.BOSS_FINALE_WAVE
	var desire: Vector2
	if finale:
		# v118: no dashes on the boss wave; survival is the only objective.
		_suppress_loot_dash("suppressed_finale")
		if finale_v2_enabled:
			# Finale v2: heading selection replaces _pure_repulsion_flee /
			# _panic_dodge, the projectile-escape blend, the anti-reversal and
			# commitment patches, and the smoothing blend. The corner guard and
			# the ordered safety tail are deliberately retained unchanged: they
			# are shared late-wave code and the audit replay surface.
			# The wave check on the corner guard is omitted because a finale
			# wave is always >= LATE_EDGE_KITE_WAVE.
			var v2_move = _finale_v2_heading(
				pos, enemies, bosses, projectiles, arena, player_speed, _prev_move)
			var v2_corner = _late_corner_escape(pos, arena)
			if v2_corner != Vector2.ZERO:
				v2_move = _normalize(
					v2_move * BotConfig.LATE_CORNER_KEEP_MOVE + v2_corner)
			v2_move = _finale_projectile_safety(
				pos, v2_move, projectiles, player_speed, arena, enemies, bosses,
				profile)
			v2_move = _finale_wall_safety(
				pos, v2_move, arena, bosses, projectiles, player_speed,
				enemies, profile)
			v2_move = _finale_body_safety(
				pos, v2_move, player_speed, arena, enemies, bosses,
				projectiles, profile, weapons, wave, true)
			_prev_move = v2_move
			return _prev_move
		# v97: survival and central map control are the finale's base objective.
		# Automatic fire does not require movement to preserve a boss-range ring.
		desire = _pure_repulsion_flee(
			pos, enemies, bosses, projectiles, arena, _prev_move)
		# Dev flag finale_no_panic: skip the low-HP panic override entirely and
		# keep the pure-repulsion desire. Flag off, this block is unchanged.
		if not finale_no_panic_enabled:
			if (hp_ratio <= BotConfig.LATE_SURVIVAL_HP_RATIO
				and (not enemies.empty() or not bosses.empty() or not projectiles.empty())):
				var finale_survival = _panic_dodge(
					pos, enemies, bosses, projectiles, arena)
				if finale_survival == Vector2.ZERO:
					finale_survival = _pure_repulsion_flee(
						pos, enemies, bosses, projectiles, arena, _prev_move)
				desire = finale_survival
		# Dev flag finale_heal_seek: below the HP threshold, steer at the nearest
		# ordinary healing consumable. The ordered safety tail still runs after.
		if finale_heal_seek_enabled:
			var heal_dir = _finale_heal_seek(pos, consumables, player)
			if heal_dir != Vector2.ZERO:
				desire = _normalize(desire * (1.0 - BotConfig.BOSS_FINALE_HEAL_SEEK_WEIGHT)
					+ heal_dir * BotConfig.BOSS_FINALE_HEAL_SEEK_WEIGHT)
	else:
		desire = _build_desire(pos, enemies, bosses, loot, consumables, trees, weapons, arena, profile, player, wave)
		# v118: when density suppression has zeroed ordinary loot attraction,
		# allow a bounded opportunistic dash to a substantial nearby pile.
		desire = _apply_loot_dash(
			pos, desire, hp_ratio, enemies, bosses, projectiles, loot,
			player_speed, profile, arena, wave)

	# Projectile-escape: sample candidate directions, pick safest, blend by urgency.
	var escape_dir = Vector2.ZERO
	var urgency = 0.0
	if not projectiles.empty():
		var proj_profile = profile
		var result = _projectile_escape(pos, projectiles, player_speed, arena, desire, enemies, bosses, proj_profile, finale)
		escape_dir = result[0]
		urgency = result[1]
		if finale and escape_dir != Vector2.ZERO:
			urgency = min(1.0, max(urgency * BotConfig.BOSS_FINALE_PROJ_URGENCY_MULT,
				BotConfig.BOSS_FINALE_PROJ_URGENCY_FLOOR))

	# Stop-and-shoot for Soldier (or any character that can't attack while moving).
	if not can_attack_moving:
		if _should_stand(state, pos, enemies, bosses, weapons):
			_prev_move = Vector2.ZERO
			return Vector2.ZERO

	var combined: Vector2
	if urgency > 0.0 and escape_dir != Vector2.ZERO:
		combined = desire * (1.0 - urgency) + escape_dir * urgency
	else:
		combined = desire
	combined = _normalize(combined)
	# Dev flag finale_range_keep: applied AFTER the projectile blend, not before.
	# Pre-blend it was structurally capped: BOSS_FINALE_PROJ_URGENCY_FLOOR is 0.55,
	# so desire contributes at most 45% of the command whenever any escape
	# direction exists -- which against a firing boss is essentially always.
	# The ordered safety tail below is still the only hard constraint.
	if finale and finale_range_keep_enabled:
		var range_dir = _finale_range_keep(pos, bosses, weapons)
		if range_dir != Vector2.ZERO:
			combined = _normalize(combined * (1.0 - BotConfig.BOSS_FINALE_RANGE_KEEP_WEIGHT)
				+ range_dir * BotConfig.BOSS_FINALE_RANGE_KEEP_WEIGHT)
	# Radius BEFORE direction: co-rotation only pays off inside the crossover
	# radius, so closing to the band first is what makes the tangential term
	# meaningful. Applied in this order so the tangent is the last word.
	if finale and finale_ring_radius_enabled:
		var ring_dir = _finale_ring_radius(pos, bosses, projectiles)
		if ring_dir != Vector2.ZERO:
			combined = _normalize(combined * (1.0 - BotConfig.BOSS_FINALE_RING_RADIUS_WEIGHT)
				+ ring_dir * BotConfig.BOSS_FINALE_RING_RADIUS_WEIGHT)
	if finale and finale_co_rotate_enabled:
		var co_dir = _finale_co_rotate(pos, bosses, projectiles)
		if co_dir != Vector2.ZERO:
			combined = _normalize(combined * (1.0 - BotConfig.BOSS_FINALE_CO_ROTATE_WEIGHT)
				+ co_dir * BotConfig.BOSS_FINALE_CO_ROTATE_WEIGHT)
	if finale:
		combined = _finale_turn_without_reversal(_prev_move, combined, pos, arena)

	# Wave 16+ corner guard. Edge-kiting intentionally runs near one wall, but
	# being near two walls removes the lateral escape lane and caused dense-pack
	# oscillation on waves 16/19 plus a visually confirmed wave-20 corner trap.
	# Apply after projectile blending so the final command always opens space.
	if wave >= BotConfig.LATE_EDGE_KITE_WAVE:
		var corner_escape = _late_corner_escape(pos, arena)
		if corner_escape != Vector2.ZERO:
			combined = _normalize(combined * BotConfig.LATE_CORNER_KEEP_MOVE + corner_escape)
	if finale:
		combined = _finale_committed_escape(pos, combined, arena, bosses)

	var alpha = BotConfig.MOVE_SMOOTHING
	var smoothed = _prev_move * (1.0 - alpha) + combined * alpha
	var final_move = _normalize(smoothed)
	# Dev flag finale_projectile_priority: wave 20 only. Off, this is unchanged.
	# On, projectile safety is deferred to AFTER body safety so that dodging has
	# the final word instead of being overridden by wall and body arbitration.
	# RISK, stated deliberately: wall safety exists to stop the agent being
	# commanded into a physical pin, and body safety to stop it walking into
	# contact. Letting a dodge outrank both can re-open the historical corner trap.
	var projectile_last = finale and finale_projectile_priority_enabled
	if wave >= BotConfig.LATE_SURVIVAL_WAVE:
		# v99: every late-wave command must pass the same final safety tail. v98
		# protected the low-health early return, but ordinary full-health movement
		# on waves 17-19 could still project through the hard margin after smoothing.
		# Re-evaluate projectile safety first and predictive wall safety last.
		if not projectile_last:
			final_move = _finale_projectile_safety(
				pos, final_move, projectiles, player_speed, arena, enemies, bosses, profile)
		final_move = _finale_wall_safety(
			pos, final_move, arena, bosses, projectiles, player_speed,
			enemies, profile)
	# v114: the v113 qualification smoke exposed the same avoidable pack-route
	# failure on wave 12 because predictive body safety was still gated to waves
	# 17-20. Apply the last body arbiter on every combat wave, and require an open
	# pack tier whenever the sampled pool exposes one. This remains inert when the
	# incoming route already meets the tier, preserving ordinary farming paths.
	final_move = _finale_body_safety(
		pos, final_move, player_speed, arena, enemies, bosses,
		projectiles, profile, weapons, wave,
		not _loot_dash_active, _loot_dash_active)
	if projectile_last:
		final_move = _finale_projectile_safety(
			pos, final_move, projectiles, player_speed, arena, enemies, bosses, profile)
	_prev_move = final_move
	return _prev_move


var _loot_dash_active := false
var _loot_dash_target := Vector2.ZERO
var _loot_dash_ticks := 0
var _loot_dash_cooldown := 0
# v127 loot-dash observability. Only `active` was ever emitted, which made a dash
# that fires and fails to clear indistinguishable from one the cooldown / HP floor
# / MAX_TICKS bounds suppressed — opposite fixes, same telemetry (see
# reports/wp2/late_wave_collection_mechanism.md). These are plain scalars assigned
# at each decision exit, so the 60 Hz path allocates nothing; loot_dash_debug()
# builds the dict for the consumer. `_loot_dash_state` carries the per-tick outcome
# (including the blocking reason on non-armed ticks, which is what measures
# suppression), while `_loot_dash_seq` advances ONLY on an arm/abort/suppress edge
# so transitions can be recovered by differencing.
const LOOT_DASH_STATES := [
	"idle",                          # no decision recorded yet this run
	"active",                        # dash ongoing, no transition this tick
	"armed",                         # EDGE: dash armed this tick
	"aborted_ticks",                 # EDGE: LOOT_DASH_MAX_TICKS exhausted
	"aborted_pile_gone",             # EDGE: target pile no longer present — cleared
	"aborted_arrived",               # EDGE: inside LOOT_DASH_ARRIVE_RADIUS
	"aborted_hp",                    # EDGE: hp fell under arm floor * 0.8
	"suppressed_survival",           # late-survival branch dropped/blocked the dash
	"suppressed_finale",             # boss finale dropped/blocked the dash
	"not_armed_cooldown",
	"not_armed_hp_floor",
	"not_armed_no_stall",            # neither the stall count nor PACK_DENSITY_SOFT met
	"not_armed_no_pile",             # best cluster under LOOT_DASH_MIN_PILE
	"not_armed_degenerate",          # target coincides with the player
	"not_armed_window_clearance",
	"not_armed_projectile_context",
]
var _loot_dash_state := "idle"
var _loot_dash_seq := 0
var _loot_dash_scan_count := -1  # materials inside the scan radius; -1 = not computed
var _loot_dash_pile := -1        # best-cluster size the check saw; -1 = not computed


func _note_loot_dash_edge(state: String) -> void:
	_loot_dash_state = state
	_loot_dash_seq += 1


func _suppress_loot_dash(state: String) -> void:
	# The late-survival and finale branches drop the dash and return before
	# _apply_loot_dash runs, so without this the debug block would keep reporting
	# the last pre-suppression tick indefinitely. Only an actual drop is an edge;
	# merely being inside a suppressing branch is a per-tick state.
	if _loot_dash_active:
		_loot_dash_active = false
		_loot_dash_seq += 1
	_loot_dash_state = state
	_loot_dash_scan_count = -1
	_loot_dash_pile = -1


func loot_dash_debug() -> Dictionary:
	# Compact per-tick block: seven scalars, no nesting. Dash YIELD is deliberately
	# not computed here — v127 also emits player.materials on every capture, so the
	# material gained across a dash window is an exact downstream difference over
	# the ticks between two _loot_dash_seq edges, at zero runtime cost.
	return {
		"active": _loot_dash_active,
		"state": _loot_dash_state,
		"seq": _loot_dash_seq,
		"ticks": _loot_dash_ticks if _loot_dash_active else 0,
		"cooldown": _loot_dash_cooldown,
		"scan": _loot_dash_scan_count,
		"pile": _loot_dash_pile,
	}


# ───────────────────── desire decomposition (pure instrumentation) ─────────────
# The standoff question: the agent parks at ~1.0x its shortest weapon range and two
# dosed constants were both inert, so the term that actually holds it out is still
# unidentified. _build_desire sums ~12 separately-computed vectors; only the
# normalized total was ever observable. These record each term's RAW (x, y)
# contribution for the tick so a consumer can project them onto arbitrary reference
# directions offline (magnitudes alone cannot answer "which term pushes outward").
#
# Same discipline as the loot-dash block above: the 60 Hz path assigns plain floats
# only, and desire_debug() builds the dict when a consumer asks. Every field is
# zeroed at the top of _build_desire so a term whose branch did not run reads 0
# rather than last tick's value.
#
# _desire_seq is ESSENTIAL: _build_desire is NOT called on the finale or
# late-survival paths, so without it a consumer cannot distinguish a fresh
# decomposition from a stale one. It advances once per _build_desire call.
var _desire_seq := 0
var _t_enemy_engagement_x := 0.0
var _t_enemy_engagement_y := 0.0
var _t_early_hunt_x := 0.0
var _t_early_hunt_y := 0.0
var _t_edge_kite_x := 0.0
var _t_edge_kite_y := 0.0
var _t_pack_density_x := 0.0
var _t_pack_density_y := 0.0
var _t_engage_strafe_x := 0.0
var _t_engage_strafe_y := 0.0
var _t_inward_damp_x := 0.0
var _t_inward_damp_y := 0.0
var _t_circling_x := 0.0
var _t_circling_y := 0.0
var _t_loot_x := 0.0
var _t_loot_y := 0.0
var _t_consumable_x := 0.0
var _t_consumable_y := 0.0
var _t_tree_x := 0.0
var _t_tree_y := 0.0
var _t_wall_x := 0.0
var _t_wall_y := 0.0
var _t_center_x := 0.0
var _t_center_y := 0.0
# enemy_engagement is recorded BEFORE the early-branch `force *= EARLY_LOOT_VS_HUNT`
# rescale; _d_early_force_mult carries that multiplier (1.0 when it did not apply)
# so the realised contribution is recoverable offline.
var _d_early_force_mult := 1.0
var _d_early := false
var _d_edge_kite := false
var _d_out_of_range := false
var _d_at_weapon_range := false
var _d_engage := 0.0
var _d_weapon_max := 0.0
var _d_nearest_d := 0.0
var _d_total_x := 0.0
var _d_total_y := 0.0


func _reset_desire_debug() -> void:
	_desire_seq += 1
	_t_enemy_engagement_x = 0.0
	_t_enemy_engagement_y = 0.0
	_t_early_hunt_x = 0.0
	_t_early_hunt_y = 0.0
	_t_edge_kite_x = 0.0
	_t_edge_kite_y = 0.0
	_t_pack_density_x = 0.0
	_t_pack_density_y = 0.0
	_t_engage_strafe_x = 0.0
	_t_engage_strafe_y = 0.0
	_t_inward_damp_x = 0.0
	_t_inward_damp_y = 0.0
	_t_circling_x = 0.0
	_t_circling_y = 0.0
	_t_loot_x = 0.0
	_t_loot_y = 0.0
	_t_consumable_x = 0.0
	_t_consumable_y = 0.0
	_t_tree_x = 0.0
	_t_tree_y = 0.0
	_t_wall_x = 0.0
	_t_wall_y = 0.0
	_t_center_x = 0.0
	_t_center_y = 0.0
	_d_early_force_mult = 1.0
	_d_early = false
	_d_edge_kite = false
	_d_out_of_range = false
	_d_at_weapon_range = false
	_d_engage = 0.0
	_d_weapon_max = 0.0
	_d_nearest_d = 0.0
	_d_total_x = 0.0
	_d_total_y = 0.0


func desire_debug() -> Dictionary:
	# Built only when a consumer calls it — the per-tick path assigns scalars only.
	return {
		"seq": _desire_seq,
		"enemy_engagement": [_t_enemy_engagement_x, _t_enemy_engagement_y],
		"early_hunt": [_t_early_hunt_x, _t_early_hunt_y],
		"edge_kite": [_t_edge_kite_x, _t_edge_kite_y],
		"pack_density": [_t_pack_density_x, _t_pack_density_y],
		"engage_strafe": [_t_engage_strafe_x, _t_engage_strafe_y],
		"inward_damp": [_t_inward_damp_x, _t_inward_damp_y],
		"circling": [_t_circling_x, _t_circling_y],
		"loot": [_t_loot_x, _t_loot_y],
		"consumable": [_t_consumable_x, _t_consumable_y],
		"tree": [_t_tree_x, _t_tree_y],
		"wall": [_t_wall_x, _t_wall_y],
		"center": [_t_center_x, _t_center_y],
		"early_force_mult": _d_early_force_mult,
		"early": _d_early,
		"edge_kite_branch": _d_edge_kite,
		"out_of_range": _d_out_of_range,
		"at_weapon_range": _d_at_weapon_range,
		"engage": _d_engage,
		"weapon_max": _d_weapon_max,
		"nearest_d": _d_nearest_d,
		"total_x": _d_total_x,
		"total_y": _d_total_y,
	}


# ── safety-tail lane-score decomposition (v0.2.55) ────────────────────────────
# Same contract as the desire decomposition above: the per-tick path assigns
# scalars only and tail_debug() builds the dict when a consumer asks.
#
# _tail_seq is ESSENTIAL: _best_finale_interior_lane is NOT called every tick
# (it runs only on the wall-recovery / projectile-replan paths), so without it a
# stale decomposition is indistinguishable from a fresh one. The desire
# instrument hit exactly this. It advances once per _best_finale_interior_lane
# call.
#
# _lane_record is scratch, written by _finale_lane_score ONLY when its trailing
# `record` param is true. _tail_selected / _tail_alt hold the ten-element rows
# for the chosen lane and the runner-up; both are [] when no lane was admitted
# (the center fallback), which is how a fallback tick is identified.
var _lane_record: Array = []
var _tail_seq := 0
var _tail_selected: Array = []
var _tail_alt: Array = []
var _tail_sampled := 0
# _tail_pool is the DENOMINATOR for the two pass counters below. It is NOT
# _tail_sampled: the pass counters iterate candidate_rows, which is the
# wall-progress pool (or the hard-safe pool under relief), and that is usually
# far smaller than the 24 sampled headings. Reading "n of 24 passed" off
# _tail_sampled would overstate the eligible set -- the vacuous-denominator trap.
var _tail_pool := 0
var _tail_body_floor_passed := 0
var _tail_enemy_filter_passed := 0
var _tail_body_floor := 0.0
var _tail_highest_body_clearance := 0.0
var _tail_body_floor_regime := ""
var _tail_lowest_enemy_penalty := 0.0
var _tail_penalty_min := 0.0
var _tail_penalty_median := 0.0
var _tail_penalty_max := 0.0
# NOTE: no wall_recovery_active here on purpose. _best_finale_interior_lane is
# only ever reached with the latch already set, so the field would be constant
# true and carry no information -- and finale_translation_debug already reports
# the real latch alongside projectile_safety_active and body_safety_active. The
# owning sub-path is derived offline from those three plus this block's seq
# delta (seq unchanged => the interior lane did not run this tick).


func _lane_terms(rec: Array) -> Dictionary:
	if rec.size() < 10:
		return {}
	return {
		"wall": rec[0],
		"boss": rec[1],
		"projectile": rec[2],
		"center": rec[3],
		"desire": rec[4],
		"continuity": rec[5],
		"enemy_penalty_term": rec[6],
		"total": rec[7],
		"wall_clear": rec[8],
		"current_wall_clear": rec[9],
	}


func tail_debug() -> Dictionary:
	# Built only when a consumer calls it — the per-tick path assigns scalars only.
	return {
		"seq": _tail_seq,
		"selected": _lane_terms(_tail_selected),
		"alt": _lane_terms(_tail_alt),
		"sampled": _tail_sampled,
		"pool": _tail_pool,
		"body_floor_passed": _tail_body_floor_passed,
		"enemy_filter_passed": _tail_enemy_filter_passed,
		"body_floor": _tail_body_floor,
		"highest_body_clearance": _tail_highest_body_clearance,
		"body_floor_regime": _tail_body_floor_regime,
		"lowest_enemy_penalty": _tail_lowest_enemy_penalty,
		"penalty_min": _tail_penalty_min,
		"penalty_median": _tail_penalty_median,
		"penalty_max": _tail_penalty_max,
	}


func _best_loot_cluster(pos: Vector2, loot) -> Array:
	# Returns [centroid, count] of the densest material cluster within the
	# dash scan radius, or [Vector2.ZERO, 0].
	var best_count := 0
	var best_centroid := Vector2.ZERO
	for anchor in loot:
		var anchor_pos := Vector2(
			float(anchor.get("x", 0.0)), float(anchor.get("y", 0.0)))
		if (anchor_pos - pos).length() > BotConfig.LOOT_DASH_SCAN_RADIUS:
			continue
		var count := 0
		var centroid := Vector2.ZERO
		for item in loot:
			var item_pos := Vector2(
				float(item.get("x", 0.0)), float(item.get("y", 0.0)))
			if (item_pos - anchor_pos).length() <= BotConfig.LOOT_DASH_CLUSTER_RADIUS:
				count += 1
				centroid += item_pos
		if count > best_count:
			best_count = count
			best_centroid = centroid / float(count)
	return [best_centroid, best_count]


func _apply_loot_dash(pos: Vector2, desire: Vector2, hp_ratio: float,
		enemies, bosses, projectiles, loot, player_speed: float, profile,
		arena, wave: int = 1) -> Vector2:
	# v118: ordinary loot attraction hard-zeroes under local density
	# (PACK_DENSITY_SOFT) and per-pile corridor vetoes, so a pressured agent
	# starves while the ground saturates at the 50-material cap. This bounded
	# dash is the sanctioned exception: substantial pile nearby, HP above
	# half, and a corridor window verified with the continuous
	# closest-approach clearance. The dash desire still passes the full
	# projectile / wall / body safety tail; only the body preference tier is
	# relaxed to the 45-unit contact floor while the dash is active.
	# v123: arm HP floor, window clearance, stall count and cooldown are
	# wave-indexed (early / late / wave-19 tiers) and, for the HP floor and
	# window, further shifted by the strength tier and hard-clamped.
	var arm_hp_floor := _effective_dash_arm_hp_floor(wave)
	var window_floor := _effective_dash_window_clearance(wave)
	if _loot_dash_cooldown > 0:
		_loot_dash_cooldown -= 1
	if _loot_dash_active:
		_loot_dash_ticks -= 1
		var reacquired := _best_loot_cluster(_loot_dash_target, loot)
		var pile_gone: bool = int(reacquired[1]) == 0
		var arrived: bool = (
			pile_gone
			or (pos - _loot_dash_target).length()
				<= BotConfig.LOOT_DASH_ARRIVE_RADIUS)
		_loot_dash_scan_count = -1
		_loot_dash_pile = int(reacquired[1])
		if (_loot_dash_ticks <= 0 or arrived
				or hp_ratio < arm_hp_floor * 0.8):
			# Attribution follows the condition's own short-circuit order, so a
			# tick that satisfies several causes reports the first. `pile` is
			# emitted alongside, so an analyst can still see a zero pile behind an
			# "aborted_ticks" edge rather than having to trust the precedence.
			# pile_gone is split out of `arrived` on purpose: ending because the
			# pile is no longer there means the dash CLEARED it, whereas ending
			# inside the arrive radius with material still present means it did
			# not — that split is the capacity-vs-tuning discriminator.
			if _loot_dash_ticks <= 0:
				_note_loot_dash_edge("aborted_ticks")
			elif pile_gone:
				_note_loot_dash_edge("aborted_pile_gone")
			elif arrived:
				_note_loot_dash_edge("aborted_arrived")
			else:
				_note_loot_dash_edge("aborted_hp")
			_loot_dash_active = false
			_loot_dash_cooldown = BotConfig.loot_dash_cooldown_ticks(wave)
			return desire
		_loot_dash_state = "active"
		if int(reacquired[1]) > 0:
			_loot_dash_target = reacquired[0]
		return _normalize(_loot_dash_target - pos)
	if _loot_dash_cooldown > 0 or hp_ratio < arm_hp_floor:
		# Same short-circuit order as the branch condition above.
		_loot_dash_state = ("not_armed_cooldown" if _loot_dash_cooldown > 0
			else "not_armed_hp_floor")
		_loot_dash_scan_count = -1
		_loot_dash_pile = -1
		return desire
	# v118 armed only under density suppression, but wave-10 live evidence
	# showed the ordinary field starving without it: engagement and strafe
	# forces out-vote the per-item loot pull while material piles accumulate
	# unblocked at kiting range. Heavy accumulation within scan range is
	# treated as a stall signal and arms the dash at any density.
	var scan_count := 0
	for item in loot:
		var item_pos := Vector2(
			float(item.get("x", 0.0)), float(item.get("y", 0.0)))
		if (item_pos - pos).length() <= BotConfig.LOOT_DASH_SCAN_RADIUS:
			scan_count += 1
	_loot_dash_scan_count = scan_count
	var stalled: bool = scan_count >= BotConfig.loot_dash_stall_count(wave)
	if (not stalled
			and _count_nearby_enemies(pos, enemies, bosses)
				< BotConfig.PACK_DENSITY_SOFT):
		_loot_dash_state = "not_armed_no_stall"
		_loot_dash_pile = -1
		return desire
	var cluster := _best_loot_cluster(pos, loot)
	_loot_dash_pile = int(cluster[1])
	if int(cluster[1]) < BotConfig.LOOT_DASH_MIN_PILE:
		_loot_dash_state = "not_armed_no_pile"
		return desire
	var target: Vector2 = cluster[0]
	var direction := _normalize(target - pos)
	if direction == Vector2.ZERO:
		_loot_dash_state = "not_armed_degenerate"
		return desire
	var dash_sec: float = min(
		BotConfig.ESCAPE_HORIZON,
		(target - pos).length() / max(player_speed, 1.0) + 0.1)
	var window := _predictive_body_path_clearance(
		pos, direction, player_speed, [dash_sec], enemies, bosses)
	if window < window_floor:
		_loot_dash_state = "not_armed_window_clearance"
		return desire
	if not projectiles.empty():
		var context := _projectile_clearance_context(
			pos, projectiles, player_speed, profile, false)
		if not context.empty():
			var bullet_clear := _dir_clearance(
				pos, direction, player_speed, context["bullets_t"],
				context["times"], arena)
			if bullet_clear < (BotConfig.ESCAPE_PANIC_CLEARANCE
					* float(context["caution"])):
				_loot_dash_state = "not_armed_projectile_context"
				return desire
	_note_loot_dash_edge("armed")
	_loot_dash_active = true
	_loot_dash_target = target
	_loot_dash_ticks = BotConfig.LOOT_DASH_MAX_TICKS
	return direction


func _reset_finale_commit() -> void:
	_finale_commit_dir = Vector2.ZERO
	_finale_commit_origin = Vector2.ZERO
	_finale_commit_ticks = 0
	_finale_commit_distance = 0.0


func _arena_wall_distance(pos: Vector2, arena) -> float:
	var w := float(arena.get("width", 2048.0))
	var h := float(arena.get("height", 1536.0))
	return min(min(pos.x, w - pos.x), min(pos.y, h - pos.y))


func _clamp_finale_wall_components(pos: Vector2, desired: Vector2, arena,
		player_speed: float) -> Vector2:
	var w := float(arena.get("width", 2048.0))
	var h := float(arena.get("height", 1536.0))
	var margin := BotConfig.BOSS_FINALE_WALL_HARD_MARGIN
	var out := desired
	var travel := max(player_speed, 0.0) * BotConfig.BOSS_FINALE_WALL_COMMAND_HORIZON
	var projected := pos + out * travel
	if out.x < 0.0 and min(pos.x, projected.x) <= margin:
		out.x = 0.0
	elif out.x > 0.0 and max(pos.x, projected.x) >= w - margin:
		out.x = 0.0
	if out.y < 0.0 and min(pos.y, projected.y) <= margin:
		out.y = 0.0
	elif out.y > 0.0 and max(pos.y, projected.y) >= h - margin:
		out.y = 0.0
	if out.length() < 0.1:
		out = Vector2(w * 0.5, h * 0.5) - pos
	# Removing one component changes the normalized magnitude of the other.
	# Recheck that normalized command so the final return cannot reintroduce a
	# crossing on the remaining axis.
	out = _normalize(out)
	projected = pos + out * travel
	if out.x < 0.0 and min(pos.x, projected.x) <= margin:
		out.x = 0.0
	elif out.x > 0.0 and max(pos.x, projected.x) >= w - margin:
		out.x = 0.0
	if out.y < 0.0 and min(pos.y, projected.y) <= margin:
		out.y = 0.0
	elif out.y > 0.0 and max(pos.y, projected.y) >= h - margin:
		out.y = 0.0
	if out.length() < 0.1:
		out = Vector2(w * 0.5, h * 0.5) - pos
	return _normalize(out)


func _is_finale_sampled_direction(direction: Vector2) -> bool:
	var safe_direction := _normalize(direction)
	if safe_direction == Vector2.ZERO:
		return false
	for k in range(BotConfig.ESCAPE_DIRECTIONS):
		var angle := (TAU * k) / float(BotConfig.ESCAPE_DIRECTIONS)
		var sampled := Vector2(cos(angle), sin(angle))
		if safe_direction.dot(sampled) >= 0.99999:
			return true
	return false


func _is_calm_enemy(e) -> bool:
	# Same test as _enemy_engagement_force's shipped inline version, reused by the
	# safety tail. DEFENSIVE: two state builders exist and game_adapter's carries
	# no vx/vy, so a MISSING velocity reads as CHARGING (returns false) -- an
	# absent signal must never make the agent bolder than the shipped policy.
	# Only ever called on entries from the `enemies` array; bosses are never
	# discounted.
	if not (e.has("vx") and e.has("vy")):
		return false
	var esp := float(e.get("speed", 0.0))
	if esp <= 0.0:
		return false
	var ev := Vector2(float(e.get("vx", 0.0)), float(e.get("vy", 0.0))).length()
	return ev / esp <= BotConfig.CHARGE_RATIO_THRESH


func _finale_enemy_path_penalty(pos: Vector2, direction: Vector2, enemies,
		player_speed: float, lookahead: float, samples: int) -> float:
	if enemies.empty():
		return 0.0
	var safe_direction := _normalize(direction)
	if safe_direction == Vector2.ZERO:
		return 1.0e18
	var safe_speed := max(player_speed, 1.0)
	# Guarded so the default path neither changes behaviour nor pays for the
	# charge test: at 1.0 avoid_i/critical_i are the shipped constants exactly.
	var scale_calm := tail_calm_penalty_mult != 1.0
	var penalty := 0.0
	for i in range(1, samples + 1):
		var fraction := float(i) / float(samples)
		var path_pos := pos + safe_direction * (lookahead * fraction)
		var future_sec := (lookahead * fraction) / safe_speed
		for enemy in enemies:
			var enemy_pos := Vector2(
				float(enemy.get("x", 0.0)), float(enemy.get("y", 0.0)))
			var enemy_vel := Vector2(
				float(enemy.get("vx", 0.0)), float(enemy.get("vy", 0.0)))
			var enemy_radius := max(float(enemy.get("radius", 18.0)), 0.0)
			var avoid_i := float(BotConfig.BOSS_FINALE_WALL_ENEMY_AVOID_CLEARANCE)
			var critical_i := float(
				BotConfig.BOSS_FINALE_WALL_ENEMY_CRITICAL_CLEARANCE)
			if scale_calm and _is_calm_enemy(enemy):
				avoid_i = avoid_i * tail_calm_penalty_mult
				critical_i = critical_i * tail_calm_penalty_mult
			var clearance := path_pos.distance_to(
				enemy_pos + enemy_vel * future_sec) - enemy_radius
			if clearance < avoid_i:
				penalty += (avoid_i - clearance)
				if clearance < critical_i:
					var critical_gap := (critical_i - clearance)
					penalty += (critical_gap * critical_gap
						* BotConfig.BOSS_FINALE_WALL_ENEMY_CRITICAL_WEIGHT)
	return penalty / float(max(samples, 1))


func _predictive_body_path_clearance(pos: Vector2, direction: Vector2,
		player_speed: float, times: Array, enemies, bosses) -> float:
	var safe_direction: Vector2 = _normalize(direction)
	if safe_direction == Vector2.ZERO:
		return -1.0e18
	if enemies.empty() and bosses.empty():
		return 1000000.0
	# Dev knob: a non-charging ENEMY (never a boss) gets a positive credit added to
	# its own computed clearance before the min(). DELIBERATE SCALE CHANGE: when
	# tail_calm_clearance_mult != 1.0 the value this function RETURNS is inflated
	# relative to the true geometric clearance, so every body-clearance
	# diagnostic derived from it (wall_best/selected_body_clearance, the body
	# floor, _finale_body_* fields) is on a different scale in a dosed arm and
	# must not be compared against a control arm's numbers. At 1.0 the credit is
	# exactly 0.0 and the charge test is not evaluated.
	var credit_calm := tail_calm_clearance_mult != 1.0
	var calm_credit: float = ((1.0 - tail_calm_clearance_mult)
		* float(BotConfig.BOSS_FINALE_BODY_CRITICAL_CLEARANCE))
	# is_enemy[i] tags which threats came from `enemies`; the two arrays are
	# merged below and bosses must keep the unscaled clearance.
	var threats: Array = []
	var threat_is_enemy: Array = []
	for enemy in enemies:
		threats.append(enemy)
		threat_is_enemy.append(true)
	for boss in bosses:
		threats.append(boss)
		threat_is_enemy.append(false)
	# v116: relative motion is linear over the hold, so the minimum clearance
	# has a closed form. The v115 smoke proved that sampling only at 120 ms
	# steps let a 940 u/s charge (capture 19557) cross the player's path
	# entirely between samples while every tier read ~95 units of clearance.
	# Every direction still shares the current overlap: the window starts one
	# decision interval out so the tier distinguishes escape from deeper
	# penetration, and clamping the closest approach into the window still
	# surfaces any crossing earlier in the hold.
	var horizon: float = 0.0
	for time_value in times:
		horizon = max(horizon, float(time_value))
	var t_lo: float = min(BotConfig.ESCAPE_CLEARANCE_MIN_TIME, horizon)
	var player_vel: Vector2 = safe_direction * max(player_speed, 1.0)
	var clearance: float = 1000000.0
	for tix in range(threats.size()):
		var threat = threats[tix]
		var threat_pos: Vector2 = Vector2(
			float(threat.get("x", 0.0)), float(threat.get("y", 0.0)))
		var threat_vel: Vector2 = Vector2(
			float(threat.get("vx", 0.0)), float(threat.get("vy", 0.0)))
		var threat_radius: float = max(
			float(threat.get("radius", 18.0)), 0.0)
		var credit: float = 0.0
		if credit_calm and bool(threat_is_enemy[tix]) and _is_calm_enemy(threat):
			credit = calm_credit
		var rel_pos: Vector2 = pos - threat_pos
		var rel_vel: Vector2 = player_vel - threat_vel
		var speed_sq: float = rel_vel.length_squared()
		var closest_sec: float = t_lo
		if speed_sq > 1.0e-9:
			closest_sec = clamp(
				-rel_pos.dot(rel_vel) / speed_sq, t_lo, horizon)
		clearance = min(clearance,
			(rel_pos + rel_vel * closest_sec).length() - threat_radius + credit)
		clearance = min(clearance,
			(rel_pos + rel_vel * horizon).length() - threat_radius + credit)
	return clearance


func _finale_lane_score(pos: Vector2, direction: Vector2, desired: Vector2,
		arena, bosses, projectiles, player_speed: float,
		enemy_path_penalty: float, require_wall_progress := true,
		record := false) -> float:
	var w := float(arena.get("width", 2048.0))
	var h := float(arena.get("height", 1536.0))
	var lookahead := BotConfig.BOSS_FINALE_WALL_LOOKAHEAD
	var end_pos := pos + direction * lookahead
	var current_wall_clear := min(min(pos.x, w - pos.x), min(pos.y, h - pos.y))
	var wall_clear := min(min(end_pos.x, w - end_pos.x), min(end_pos.y, h - end_pos.y))
	if wall_clear < BotConfig.BOSS_FINALE_WALL_HARD_MARGIN:
		return -1.0e18
	# v104: an active recovery lane must improve the limiting wall, not merely
	# move toward the arena center on a different axis. v103 captures 22690-22691
	# selected a horizontal lane while the lower wall remained the minimum, so
	# the latch stayed active without creating any additional escape clearance.
	if (require_wall_progress
			and current_wall_clear < BotConfig.BOSS_FINALE_WALL_RECOVERY_RELEASE
			and wall_clear <= current_wall_clear + 0.001):
		return -1.0e18
	var center_dir := (Vector2(w * 0.5, h * 0.5) - pos).normalized()
	var boss_clear := 650.0
	var projectile_clear := 320.0
	var samples := BotConfig.BOSS_FINALE_WALL_PATH_SAMPLES
	var safe_speed := max(player_speed, 1.0)
	for i in range(1, samples + 1):
		var fraction := float(i) / float(samples)
		var path_pos := pos + direction * (lookahead * fraction)
		var future_sec := (lookahead * fraction) / safe_speed
		for boss in bosses:
			var boss_pos := Vector2(
				float(boss.get("x", 0.0)), float(boss.get("y", 0.0)))
			var boss_vel := Vector2(
				float(boss.get("vx", 0.0)), float(boss.get("vy", 0.0)))
			var boss_radius := float(boss.get("radius", 40.0))
			boss_clear = min(
				boss_clear,
				path_pos.distance_to(boss_pos + boss_vel * future_sec) - boss_radius)
		for projectile in projectiles:
			var projectile_pos := Vector2(
				float(projectile.get("x", 0.0)), float(projectile.get("y", 0.0)))
			var projectile_vel := Vector2(
				float(projectile.get("vx", 0.0)), float(projectile.get("vy", 0.0)))
			var projectile_radius := float(projectile.get("radius", 12.0))
			projectile_clear = min(projectile_clear,
				path_pos.distance_to(projectile_pos + projectile_vel * future_sec)
				- projectile_radius)
	# Each term hoisted into a local so it can be recorded; the accumulation order
	# and the operands are unchanged, so the returned score is identical.
	var term_wall := (
		min(wall_clear, BotConfig.BOSS_FINALE_WALL_RECOVERY_RELEASE)
		* BotConfig.BOSS_FINALE_WALL_CLEAR_WEIGHT)
	var term_boss := max(boss_clear, -100.0) * BotConfig.BOSS_FINALE_WALL_BOSS_WEIGHT
	var term_projectile := (
		max(projectile_clear, -100.0)
		* BotConfig.BOSS_FINALE_WALL_PROJECTILE_WEIGHT)
	var term_center := (
		direction.dot(center_dir) * BotConfig.BOSS_FINALE_WALL_CENTER_WEIGHT)
	var term_desire := (
		direction.dot(desired) * BotConfig.BOSS_FINALE_WALL_DESIRE_WEIGHT)
	var term_continuity := (
		direction.dot(_prev_move) * BotConfig.BOSS_FINALE_WALL_CONTINUITY_WEIGHT)
	var term_enemy := (enemy_path_penalty
		* BotConfig.BOSS_FINALE_WALL_ENEMY_SCORE_WEIGHT)
	var score := term_wall
	score += term_boss
	score += term_projectile
	score += term_center
	score += term_desire
	score += term_continuity
	score -= term_enemy
	if record:
		# Fresh Array every time, so the caller can keep a reference without
		# aliasing the next call's scratch.
		_lane_record = [
			term_wall, term_boss, term_projectile, term_center, term_desire,
			term_continuity, term_enemy, score, wall_clear, current_wall_clear,
		]
	return score


func _best_finale_interior_lane(pos: Vector2, desired: Vector2, arena,
		enemies, bosses, projectiles, player_speed: float) -> Vector2:
	# Instrument only: every _tail_* write below is debug state, never read back
	# by any decision. Cleared here so a fallback tick cannot present last call's
	# decomposition as fresh; _tail_seq advances once per call.
	_tail_seq += 1
	_tail_selected = []
	_tail_alt = []
	_tail_sampled = BotConfig.ESCAPE_DIRECTIONS
	_tail_pool = 0
	_tail_body_floor_passed = 0
	_tail_enemy_filter_passed = 0
	_tail_body_floor = 0.0
	_tail_highest_body_clearance = 0.0
	_tail_body_floor_regime = ""
	_tail_lowest_enemy_penalty = 0.0
	_tail_penalty_min = 0.0
	_tail_penalty_median = 0.0
	_tail_penalty_max = 0.0
	var all_penalties := []
	var lookahead := BotConfig.BOSS_FINALE_WALL_LOOKAHEAD
	var samples := BotConfig.BOSS_FINALE_WALL_PATH_SAMPLES
	var desired_n := _normalize(desired)
	var path_times := []
	for i in range(1, samples + 1):
		path_times.append(
			(lookahead * (float(i) / float(samples))) / max(player_speed, 1.0))
	_finale_wall_input_enemy_penalty = _finale_enemy_path_penalty(
		pos, desired_n, enemies, player_speed, lookahead, samples)
	_finale_wall_input_body_clearance = _predictive_body_path_clearance(
		pos, desired_n, player_speed, path_times, enemies, bosses)
	var rows := []
	var hard_safe_rows := []
	var lowest_enemy_penalty := INF
	var highest_body_clearance := -INF
	var hard_safe_highest_body_clearance := -INF
	for k in range(BotConfig.ESCAPE_DIRECTIONS):
		var angle := (TAU * k) / float(BotConfig.ESCAPE_DIRECTIONS)
		var candidate := Vector2(cos(angle), sin(angle))
		var enemy_penalty := _finale_enemy_path_penalty(
			pos, candidate, enemies, player_speed, lookahead, samples)
		all_penalties.append(enemy_penalty)
		var score := _finale_lane_score(
			pos, candidate, desired_n, arena, bosses, projectiles, player_speed,
			enemy_penalty)
		var makes_wall_progress := score > -1.0e17
		if not makes_wall_progress:
			score = _finale_lane_score(
				pos, candidate, desired_n, arena, bosses, projectiles,
				player_speed, enemy_penalty, false)
			if score <= -1.0e17:
				continue
		var body_clearance := _predictive_body_path_clearance(
			pos, candidate, player_speed, path_times, enemies, bosses)
		hard_safe_rows.append([
			candidate, score, enemy_penalty, body_clearance])
		hard_safe_highest_body_clearance = max(
			hard_safe_highest_body_clearance, body_clearance)
		if makes_wall_progress:
			rows.append([candidate, score, enemy_penalty, body_clearance])
			lowest_enemy_penalty = min(lowest_enemy_penalty, enemy_penalty)
			highest_body_clearance = max(highest_body_clearance, body_clearance)
	_finale_wall_relief_best_body_clearance = (
		hard_safe_highest_body_clearance if not hard_safe_rows.empty() else -1.0)
	var candidate_rows := rows
	if (hard_safe_highest_body_clearance
			>= BotConfig.BOSS_FINALE_BODY_CRITICAL_CLEARANCE
			and highest_body_clearance
				< BotConfig.BOSS_FINALE_WALL_BODY_RELIEF_TRIGGER
			and hard_safe_highest_body_clearance
				>= highest_body_clearance
					+ BotConfig.BOSS_FINALE_WALL_BODY_RELIEF_MIN_GAIN):
		# v112: compare against every hard-wall-safe lane, including any strict
		# inward candidate that is also the clearest route. The v111 smoke
		# showed that a non-progress-only pool could understate the available
		# relief and let the final body pass replace it with a pack route.
		candidate_rows = hard_safe_rows
		highest_body_clearance = hard_safe_highest_body_clearance
		_finale_wall_body_relief_active = true
	_finale_wall_best_body_clearance = (
		highest_body_clearance if not candidate_rows.empty() else -1.0)
	var body_clearance_floor := highest_body_clearance
	if _finale_wall_body_relief_active:
		body_clearance_floor = max(
			BotConfig.BOSS_FINALE_BODY_CRITICAL_CLEARANCE,
			highest_body_clearance
				- BotConfig.BOSS_FINALE_WALL_BODY_RELIEF_CLEARANCE_SLACK)
	elif highest_body_clearance >= BotConfig.BOSS_FINALE_BODY_CRITICAL_CLEARANCE:
		body_clearance_floor = BotConfig.BOSS_FINALE_BODY_CRITICAL_CLEARANCE
	else:
		body_clearance_floor = (
			highest_body_clearance - BotConfig.BOSS_FINALE_BODY_CLEARANCE_SLACK)
	# Compare crowd density only inside the accepted body-clearance tier. A
	# contact-dangerous zero-penalty lane must not make every safe lane fail the
	# subsequent v105 crowd-slack gate.
	lowest_enemy_penalty = INF
	for row in candidate_rows:
		if float(row[3]) >= body_clearance_floor:
			lowest_enemy_penalty = min(lowest_enemy_penalty, float(row[2]))
	_finale_wall_best_enemy_penalty = (
		lowest_enemy_penalty if lowest_enemy_penalty < INF else -1.0)
	# Instrument: the three floor/regime readings the campaign needs to decide
	# WHICH term binds. Written before the selection loop; none is read by it.
	_tail_pool = candidate_rows.size()
	_tail_body_floor = body_clearance_floor
	_tail_highest_body_clearance = (
		highest_body_clearance if highest_body_clearance > -INF else -1.0)
	if _finale_wall_body_relief_active:
		_tail_body_floor_regime = "relief"
	elif highest_body_clearance >= BotConfig.BOSS_FINALE_BODY_CRITICAL_CLEARANCE:
		_tail_body_floor_regime = "critical"
	else:
		_tail_body_floor_regime = "degraded"
	_tail_lowest_enemy_penalty = (
		lowest_enemy_penalty if lowest_enemy_penalty < INF else -1.0)
	if not all_penalties.empty():
		var sorted_penalties := []
		for p in all_penalties:
			sorted_penalties.append(float(p))
		sorted_penalties.sort()
		_tail_penalty_min = float(sorted_penalties[0])
		_tail_penalty_max = float(sorted_penalties[sorted_penalties.size() - 1])
		var mid := int(sorted_penalties.size() / 2)
		if sorted_penalties.size() % 2 == 1:
			_tail_penalty_median = float(sorted_penalties[mid])
		else:
			_tail_penalty_median = (
				(float(sorted_penalties[mid - 1]) + float(sorted_penalties[mid]))
				* 0.5)
	var best_dir := Vector2.ZERO
	var best_score := -1.0e18
	# Instrument-only mirrors of the winner and the runner-up.
	var best_row = []
	var alt_row = []
	var alt_score := -1.0e18
	for row in candidate_rows:
		var candidate: Vector2 = row[0]
		var score: float = row[1]
		var enemy_penalty: float = row[2]
		var body_clearance: float = row[3]
		if body_clearance < body_clearance_floor:
			continue
		_tail_body_floor_passed += 1
		if (enemy_penalty > lowest_enemy_penalty
				+ BotConfig.BOSS_FINALE_ENEMY_PENALTY_SLACK):
			continue
		_tail_enemy_filter_passed += 1
		if score > best_score:
			alt_score = best_score
			alt_row = best_row
			best_row = row
			best_score = score
			best_dir = candidate
			_finale_wall_selected_enemy_penalty = enemy_penalty
			_finale_wall_selected_body_clearance = body_clearance
		elif score > alt_score:
			alt_score = score
			alt_row = row
	# Re-score the winner and the runner-up with recording on. _finale_lane_score
	# reads only its arguments, BotConfig and _prev_move, and writes nothing but
	# _lane_record when `record` is true -- so these extra calls cannot change the
	# decision, which has already been made above. The require_wall_progress
	# retry mirrors the sampling loop exactly: an admitted row scored above
	# -1.0e17 under one of the two branches, so _lane_record is always written.
	if not best_row.empty():
		# Clear the scratch FIRST. _finale_lane_score returns early (before the
		# record block) when a candidate fails the hard wall margin, and on that
		# path _lane_record would keep the PREVIOUS call's terms -- a stale
		# decomposition presented as fresh, which is exactly what seq exists to
		# prevent one level up. Cleared, a non-write shows as {} in tail_debug.
		_lane_record = []
		var sel_score := _finale_lane_score(
			pos, best_row[0], desired_n, arena, bosses, projectiles, player_speed,
			float(best_row[2]), true, true)
		if sel_score <= -1.0e17:
			_finale_lane_score(
				pos, best_row[0], desired_n, arena, bosses, projectiles,
				player_speed, float(best_row[2]), false, true)
		_tail_selected = _lane_record
	if not alt_row.empty():
		_lane_record = []
		var alt_rec_score := _finale_lane_score(
			pos, alt_row[0], desired_n, arena, bosses, projectiles, player_speed,
			float(alt_row[2]), true, true)
		if alt_rec_score <= -1.0e17:
			_finale_lane_score(
				pos, alt_row[0], desired_n, arena, bosses, projectiles,
				player_speed, float(alt_row[2]), false, true)
		_tail_alt = _lane_record
	if best_dir == Vector2.ZERO:
		var w := float(arena.get("width", 2048.0))
		var h := float(arena.get("height", 1536.0))
		best_dir = Vector2(w * 0.5, h * 0.5) - pos
		_finale_wall_selected_enemy_penalty = _finale_enemy_path_penalty(
			pos, best_dir, enemies, player_speed, lookahead, samples)
		_finale_wall_selected_body_clearance = _predictive_body_path_clearance(
			pos, best_dir, player_speed, path_times, enemies, bosses)
	return _normalize(best_dir)


func _finale_projectile_safety(pos: Vector2, desired: Vector2, projectiles,
		player_speed: float, arena, enemies, bosses, profile) -> Vector2:
	if projectiles.empty():
		return desired
	var result = _projectile_escape(
		pos, projectiles, player_speed, arena, desired, enemies, bosses, profile, true)
	var escape_dir: Vector2 = result[0]
	var urgency := float(result[1])
	_finale_projectile_input_clearance = float(result[2])
	_finale_projectile_escape_clearance = float(result[3])
	if escape_dir == Vector2.ZERO or urgency <= 0.0:
		return desired
	urgency = min(1.0, max(
		urgency * BotConfig.BOSS_FINALE_PROJ_URGENCY_MULT,
		BotConfig.BOSS_FINALE_PROJ_URGENCY_FLOOR))
	_finale_projectile_safety_active = true
	_finale_projectile_safety_urgency = urgency
	var blended := _normalize(desired * (1.0 - urgency) + escape_dir * urgency)
	# v101: v100 telemetry captured a fresh decision where the 0.55 blend had
	# lower clearance than both endpoints. Validate the actual blended direction
	# in the same projectile context and use the sampled escape when the blend is
	# below panic and the sampled lane is materially safer. Final wall safety still
	# runs afterward and can invoke the v100 wall-safe replan if it rotates this.
	var blend_context := _projectile_clearance_context(
		pos, projectiles, player_speed, profile, true)
	if not blend_context.empty():
		_finale_projectile_blended_clearance = _dir_clearance(
			pos, blended, player_speed, blend_context["bullets_t"],
			blend_context["times"], arena)
		_finale_projectile_input_body_clearance = _predictive_body_path_clearance(
			pos, desired, player_speed, blend_context["times"], enemies, bosses)
		_finale_projectile_escape_body_clearance = _predictive_body_path_clearance(
			pos, escape_dir, player_speed, blend_context["times"], enemies, bosses)
		_finale_projectile_blended_body_clearance = _predictive_body_path_clearance(
			pos, blended, player_speed, blend_context["times"], enemies, bosses)
		var panic_clear := (
			BotConfig.ESCAPE_PANIC_CLEARANCE * float(blend_context["caution"]))
		_finale_projectile_input_enemy_penalty = _predictive_enemy_path_penalty(
			pos, desired, player_speed, blend_context["times"], enemies, bosses,
			float(blend_context["caution"]))
		_finale_projectile_escape_enemy_penalty = _predictive_enemy_path_penalty(
			pos, escape_dir, player_speed, blend_context["times"], enemies, bosses,
			float(blend_context["caution"]))
		_finale_projectile_blended_enemy_penalty = _predictive_enemy_path_penalty(
			pos, blended, player_speed, blend_context["times"], enemies, bosses,
			float(blend_context["caution"]))
		if (_finale_projectile_blended_clearance < panic_clear
				and _finale_projectile_escape_clearance
					>= _finale_projectile_blended_clearance
						+ BotConfig.BOSS_FINALE_PROJECTILE_BLEND_MIN_GAIN):
			_finale_projectile_blend_repair_active = true
			return escape_dir
		# v105: a projectile-clear weighted blend can still rotate back through a
		# moving pack. Prefer the least-crowded endpoint that remains above panic
		# whenever the blend is materially worse than that endpoint.
		var crowd_safe_dir := escape_dir
		var crowd_safe_penalty := _finale_projectile_escape_enemy_penalty
		if (_finale_projectile_input_clearance >= panic_clear
				and _finale_projectile_input_enemy_penalty < crowd_safe_penalty):
			crowd_safe_dir = desired
			crowd_safe_penalty = _finale_projectile_input_enemy_penalty
		if (_finale_projectile_blended_enemy_penalty > crowd_safe_penalty
				+ BotConfig.BOSS_FINALE_ENEMY_PENALTY_SLACK):
			_finale_projectile_enemy_blend_repair_active = true
			return crowd_safe_dir
	return blended


func _finale_wall_safety(pos: Vector2, desired: Vector2, arena, bosses,
		projectiles, player_speed: float, enemies = [], profile = null) -> Vector2:
	var wall_distance := _arena_wall_distance(pos, arena)
	if _finale_wall_recovery_active:
		if wall_distance >= BotConfig.BOSS_FINALE_WALL_RECOVERY_RELEASE:
			_finale_wall_recovery_active = false
	elif wall_distance <= BotConfig.BOSS_FINALE_WALL_RECOVERY_ENTER:
		_finale_wall_recovery_active = true
	var safe_desire := desired
	# v95: the final projectile pass has already selected a safer lane using
	# wall-aware clearance. Do not let the softer center-recovery selector replace
	# that command; the unconditional hard projection below still prevents an
	# active dodge from pointing through the arena boundary.
	if _finale_wall_recovery_active and not _finale_projectile_safety_active:
		safe_desire = _best_finale_interior_lane(
			pos, desired, arena, enemies, bosses, projectiles, player_speed)
	# Hard projection is unconditional and runs after lane selection so no boss,
	# projectile, continuity, or smoothing term can command movement through a wall.
	var clamped := _clamp_finale_wall_components(
		pos, safe_desire, arena, player_speed)
	# v100: v99 telemetry proved that zeroing one unsafe wall component could turn
	# a good diagonal dodge into a dangerous cardinal command. Only when the hard
	# clamp materially rotates an active projectile-safe command, resample the same
	# projectile/enemy objective over directions that survive the hard clamp.
	var safe_n := _normalize(safe_desire)
	var final_context := {}
	if _finale_projectile_safety_active and not projectiles.empty():
		final_context = _projectile_clearance_context(
			pos, projectiles, player_speed, profile, true)
	if (_finale_projectile_safety_active and not projectiles.empty()
			and clamped.dot(safe_n) < 0.999 and not final_context.empty()):
		var clamped_clear := _dir_clearance(
			pos, clamped, player_speed, final_context["bullets_t"],
			final_context["times"], arena)
		var panic_clear := (
			BotConfig.ESCAPE_PANIC_CLEARANCE * float(final_context["caution"]))
		if clamped_clear < panic_clear:
			var replanned := _best_wall_safe_projectile_lane(
				pos, clamped, player_speed, arena, enemies, bosses, final_context)
			if replanned != clamped:
				clamped = replanned
				_finale_projectile_wall_replan_active = true
	if not final_context.empty():
		_finale_projectile_final_clearance = _dir_clearance(
			pos, clamped, player_speed, final_context["bullets_t"],
			final_context["times"], arena)
		_finale_projectile_final_enemy_penalty = _predictive_enemy_path_penalty(
			pos, clamped, player_speed, final_context["times"], enemies, bosses,
			float(final_context["caution"]))
		_finale_projectile_final_body_clearance = _predictive_body_path_clearance(
			pos, clamped, player_speed, final_context["times"], enemies, bosses)
	return clamped


func _best_wall_safe_projectile_lane(pos: Vector2, baseline: Vector2,
		player_speed: float, arena, enemies, bosses, context: Dictionary) -> Vector2:
	if context.empty():
		return baseline
	var times: Array = context["times"]
	var bullets_t: Array = context["bullets_t"]
	var baseline_clear := _dir_clearance(
		pos, baseline, player_speed, bullets_t, times, arena)
	var best_dir := baseline
	var best_score := -1.0e18
	var found_clearer_lane := false
	var baseline_body_clearance := _predictive_body_path_clearance(
		pos, baseline, player_speed, times, enemies, bosses)
	var highest_body_clearance := baseline_body_clearance
	var rows := []
	for k in range(BotConfig.ESCAPE_DIRECTIONS):
		var angle := (TAU * k) / float(BotConfig.ESCAPE_DIRECTIONS)
		var candidate := _clamp_finale_wall_components(
			pos, Vector2(cos(angle), sin(angle)), arena, player_speed)
		var clearance := _dir_clearance(
			pos, candidate, player_speed, bullets_t, times, arena)
		# v104: v103 capture 20841 exposed a panic-level clamped command with
		# 178.7 clearance while a 233.7 wall-safe sampled lane existed. Previously
		# a candidate first had to beat the dangerous baseline's combined score;
		# enemy/continuity penalties could therefore prevent every safety gain from
		# being considered. Restrict the pool to materially clearer lanes first,
		# then use those terms only to choose among the safe improvements.
		if (clearance < baseline_clear
				+ BotConfig.BOSS_FINALE_PROJECTILE_WALL_MIN_GAIN):
			continue
		var penalty := _predictive_enemy_path_penalty(
			pos, candidate, player_speed, times, enemies, bosses, 1.0)
		var body_clearance := _predictive_body_path_clearance(
			pos, candidate, player_speed, times, enemies, bosses)
		var score := clearance - penalty
		score += BotConfig.ESCAPE_ALIGN_BONUS * candidate.dot(baseline)
		if _prev_move.length() > 0.1:
			score += BotConfig.BOSS_FINALE_ESCAPE_CONTINUITY * candidate.dot(_prev_move)
		rows.append([candidate, score, body_clearance])
		highest_body_clearance = max(highest_body_clearance, body_clearance)
	var body_clearance_floor := highest_body_clearance
	if highest_body_clearance >= BotConfig.BOSS_FINALE_BODY_CRITICAL_CLEARANCE:
		body_clearance_floor = BotConfig.BOSS_FINALE_BODY_CRITICAL_CLEARANCE
	else:
		body_clearance_floor = (
			highest_body_clearance - BotConfig.BOSS_FINALE_BODY_CLEARANCE_SLACK)
	for row in rows:
		if float(row[2]) < body_clearance_floor:
			continue
		var row_score: float = row[1]
		if row_score > best_score:
			best_score = row_score
			best_dir = row[0]
			found_clearer_lane = true
	if not found_clearer_lane:
		return baseline
	return best_dir


func _route_inrange_after(pos: Vector2, direction: Vector2, player_speed: float,
		enemies, bosses, weapons) -> float:
	# Exact live counterpart of §§40-41's moving-threat counterfactual: advance
	# the player and every living threat for ESCAPE_HORIZON, then count the
	# fraction inside the longest held weapon range. This is opportunity, not
	# damage dealt; the live screen remains responsible for the low-HP veto.
	var safe_direction := _normalize(direction)
	if safe_direction == Vector2.ZERO:
		return -1.0
	var max_range := -1.0
	for weapon in weapons:
		var weapon_range = weapon.get("max_range", 0.0)
		if weapon_range != null and float(weapon_range) > max_range:
			max_range = float(weapon_range)
	if max_range <= 0.0:
		return -1.0
	var horizon := float(BotConfig.ESCAPE_HORIZON)
	var future_player := pos + safe_direction * player_speed * horizon
	var living := 0
	var in_range := 0
	for threat_group in [enemies, bosses]:
		for threat in threat_group:
			if float(threat.get("hp", 1.0)) <= 0.0:
				continue
			living += 1
			var future_threat := Vector2(
				float(threat.get("x", 0.0)),
				float(threat.get("y", 0.0)))
			future_threat += Vector2(
				float(threat.get("vx", 0.0)),
				float(threat.get("vy", 0.0))) * horizon
			if future_player.distance_to(future_threat) <= max_range:
				in_range += 1
	if living <= 0:
		return -1.0
	return float(in_range) / float(living)


func _finale_body_safety(pos: Vector2, desired: Vector2, player_speed: float,
		arena, enemies, bosses, projectiles, profile, weapons, wave: int,
		enforce_pack_clearance := false, dash_active := false) -> Vector2:
	# v129: clear the route record on ENTRY, never inside the ranking loop. This
	# function has SIX return paths and a loop-scoped clear would emit the
	# PREVIOUS tick's candidates against this decision. An empty array therefore
	# means honestly "the ranking loop was never reached", and route_exit names
	# which return fired.
	_reset_finale_route()
	_finale_route_exit = "entered"
	# v123: the near-best body-preference slack is wave-indexed (35 for wave <= 12,
	# 20 otherwise incl. waves 19/20). The 45-unit contact floor is NOT modulated.
	var body_slack := BotConfig.body_clearance_slack(wave) * body_clearance_scale
	# v107: projectile selection and wall projection each reasoned about body
	# clearance, but the final wall clamp could rotate a safe diagonal back through
	# a pack. Ordinary late movement also had no final body gate at all. Re-sample
	# the emitted command after every other transform, preserving projectile tiers
	# and active wall recovery while rejecting an avoidable predicted body impact.
	var baseline := _clamp_finale_wall_components(
		pos, desired, arena, player_speed)
	_finale_route_baseline = baseline
	if enemies.empty() and bosses.empty():
		_finale_route_exit = "no_threats"
		return baseline
	var times := []
	for i in range(BotConfig.ESCAPE_TIME_SAMPLES):
		times.append(
			(float(i) / max(BotConfig.ESCAPE_TIME_SAMPLES - 1, 1))
			* BotConfig.ESCAPE_HORIZON)
	var projectile_context := _projectile_clearance_context(
		pos, projectiles, player_speed, profile, true)
	_finale_body_input_clearance = _predictive_body_path_clearance(
		pos, baseline, player_speed, times, enemies, bosses)
	var rows := []
	var hard_safe_rows := []
	var strict_wall_body_clearance := -INF
	var hard_safe_wall_body_clearance := -INF
	var highest_projectile_clearance := -1.0e18
	for k in range(BotConfig.ESCAPE_DIRECTIONS):
		var angle := (TAU * k) / float(BotConfig.ESCAPE_DIRECTIONS)
		var sampled_candidate := Vector2(cos(angle), sin(angle))
		var candidate := _clamp_finale_wall_components(
			pos, sampled_candidate, arena, player_speed)
		# v109: when both components of an outward sample cross the hard wall,
		# the clamp deliberately falls back toward arena center. That fallback is
		# not one of the 24 directions whose body/projectile tiers this pass audits.
		# Do not admit it under a sampled-lane diagnostic; an actual inward sample
		# remains available and keeps the emitted repair reproducible.
		if not _is_finale_sampled_direction(candidate):
			continue
		var enemy_penalty := _predictive_enemy_path_penalty(
			pos, candidate, player_speed, times, enemies, bosses, 1.0)
		var makes_wall_progress := true
		if _finale_wall_recovery_active:
			var wall_score := _finale_lane_score(
				pos, candidate, baseline, arena, bosses, projectiles,
				player_speed, enemy_penalty)
			if wall_score <= -1.0e17:
				makes_wall_progress = false
				wall_score = _finale_lane_score(
					pos, candidate, baseline, arena, bosses, projectiles,
					player_speed, enemy_penalty, false)
				if wall_score <= -1.0e17:
					continue
		var body_clearance := _predictive_body_path_clearance(
			pos, candidate, player_speed, times, enemies, bosses)
		var projectile_clearance := 1000000.0
		if not projectile_context.empty():
			projectile_clearance = _dir_clearance(
				pos, candidate, player_speed, projectile_context["bullets_t"],
				projectile_context["times"], arena)
		var row := [
			candidate, body_clearance, projectile_clearance, enemy_penalty]
		hard_safe_rows.append(row)
		hard_safe_wall_body_clearance = max(
			hard_safe_wall_body_clearance, body_clearance)
		if makes_wall_progress:
			rows.append(row)
			strict_wall_body_clearance = max(
				strict_wall_body_clearance, body_clearance)
	# v115: the final body pass is the last movement arbiter. It must preserve a
	# relief selected by wall safety, and it may independently discover the same
	# long-horizon pack conflict that the shorter wall lookahead cannot see. Use
	# the more dangerous of the strict-pool best and the command actually entering
	# this pass as the relief reference. The v114 smoke showed that continuity can
	# select slightly below the strict-pool best and hide a real 60-unit escape.
	var wall_body_relief_reference := min(
		strict_wall_body_clearance, _finale_body_input_clearance)
	if (_finale_wall_recovery_active
			and not _finale_projectile_safety_active
			and (_finale_wall_body_relief_active
				or (hard_safe_wall_body_clearance
						>= BotConfig.BOSS_FINALE_BODY_CRITICAL_CLEARANCE
					and wall_body_relief_reference
						< BotConfig.BOSS_FINALE_WALL_BODY_RELIEF_TRIGGER
					and hard_safe_wall_body_clearance
						>= wall_body_relief_reference
							+ BotConfig.BOSS_FINALE_WALL_BODY_RELIEF_MIN_GAIN))):
		rows = hard_safe_rows
		_finale_wall_body_relief_active = true
	if rows.empty():
		_finale_body_best_clearance = _finale_body_input_clearance
		_finale_body_selected_clearance = _finale_body_input_clearance
		_finale_route_exit = "rows_empty"
		return baseline
	# The active pool may exclude hard-safe relief rows. Anchor projectile tiers
	# only to candidates the final body pass can actually emit.
	highest_projectile_clearance = -1.0e18
	for row in rows:
		highest_projectile_clearance = max(
			highest_projectile_clearance, float(row[2]))
	# v108: the first exact-20 v107 run exposed a gap between the projectile
	# escape chosen before this pass and the sampled pool admitted by active wall
	# recovery. Anchor the ordinary bounded concession to the actual
	# projectile-safe command as well as the sampled pool. If that strict tier
	# predicts a body overlap while the original bounded tier has a materially
	# better escape, permit the body emergency but require the final command to
	# stay very close to the best available body lane. This prevents continuity
	# or soft crowd scoring from choosing a visibly worse path through the pack.
	var baseline_projectile_clearance := 1000000.0
	if not projectile_context.empty():
		baseline_projectile_clearance = _dir_clearance(
			pos, baseline, player_speed, projectile_context["bullets_t"],
			projectile_context["times"], arena)
	var projectile_reference_clearance := highest_projectile_clearance
	if _finale_projectile_safety_active and not projectile_context.empty():
		projectile_reference_clearance = max(
			projectile_reference_clearance, baseline_projectile_clearance)
		if _finale_projectile_escape_clearance >= 0.0:
			projectile_reference_clearance = max(
				projectile_reference_clearance,
				_finale_projectile_escape_clearance)
	var projectile_floor := -1.0e18
	var body_emergency_active := false
	if not projectile_context.empty():
		var caution := float(projectile_context["caution"])
		var safe_clear := BotConfig.ESCAPE_SAFE_CLEARANCE * caution
		var panic_clear := BotConfig.ESCAPE_PANIC_CLEARANCE * caution
		if highest_projectile_clearance >= safe_clear:
			projectile_floor = safe_clear
		elif highest_projectile_clearance >= panic_clear:
			projectile_floor = panic_clear
		else:
			projectile_floor = (highest_projectile_clearance
				- BotConfig.BOSS_FINALE_BODY_ESCAPE_PROJECTILE_SLACK)
		var relaxed_projectile_floor := (
			highest_projectile_clearance
				- BotConfig.BOSS_FINALE_BODY_ESCAPE_PROJECTILE_SLACK)
		if highest_projectile_clearance >= panic_clear:
			relaxed_projectile_floor = max(
				panic_clear, relaxed_projectile_floor)
		if (_finale_projectile_safety_active
				and projectile_reference_clearance > -1.0e17):
			projectile_floor = max(
				projectile_floor,
				projectile_reference_clearance
					- BotConfig.BOSS_FINALE_BODY_ESCAPE_PROJECTILE_SLACK)
			relaxed_projectile_floor = max(
				relaxed_projectile_floor,
				projectile_reference_clearance
					- BotConfig.BOSS_FINALE_BODY_ESCAPE_PROJECTILE_SLACK)
		var strict_body_best := -1.0e18
		var relaxed_body_best := -1.0e18
		for row in rows:
			if float(row[2]) >= projectile_floor:
				strict_body_best = max(strict_body_best, float(row[1]))
			if float(row[2]) >= relaxed_projectile_floor:
				relaxed_body_best = max(relaxed_body_best, float(row[1]))
		if (_finale_projectile_safety_active
				and relaxed_projectile_floor < projectile_floor
				and relaxed_body_best >= strict_body_best
					+ BotConfig.BOSS_FINALE_BODY_EMERGENCY_MIN_GAIN):
			projectile_floor = relaxed_projectile_floor
			body_emergency_active = true
			_finale_body_emergency_active = true
	# v122: within the admitted tier, lane choice weighed continuity (+-85)
	# against raw projectile clearance, so a lane crossing a bullet at 4.6
	# units could beat an equal-body lane at 46.4 (v121 smoke capture 14938,
	# 12 damage). When even the best admissible lane sits below the safe
	# tier, bullets are at crossing range: require candidates to stay within
	# the bounded 20-unit gain of that best lane before soft terms arbitrate.
	# Body emergencies keep their deliberately broadened floor.
	if not projectile_context.empty() and not body_emergency_active:
		var best_admissible_projectile := -1.0e18
		for row in rows:
			if float(row[2]) >= projectile_floor:
				best_admissible_projectile = max(
					best_admissible_projectile, float(row[2]))
		var tier_safe_clear := (
			BotConfig.ESCAPE_SAFE_CLEARANCE * float(projectile_context["caution"]))
		if (best_admissible_projectile > -1.0e17
				and best_admissible_projectile < tier_safe_clear):
			projectile_floor = max(
				projectile_floor,
				best_admissible_projectile
					- BotConfig.BOSS_FINALE_PROJECTILE_BLEND_MIN_GAIN)
	_finale_body_projectile_floor = projectile_floor
	var highest_body_clearance := -1.0e18
	for row in rows:
		if float(row[2]) >= projectile_floor:
			highest_body_clearance = max(
				highest_body_clearance, float(row[1]))
	if highest_body_clearance <= -1.0e17:
		_finale_body_best_clearance = _finale_body_input_clearance
		_finale_body_selected_clearance = _finale_body_input_clearance
		_finale_route_exit = "no_body_tier"
		return baseline
	_finale_body_best_clearance = highest_body_clearance
	if _finale_wall_body_relief_active:
		# Report and enforce the best hard-safe lane that also survived the
		# active projectile tier, so telemetry and the emitted command use the
		# same horizon and candidate population.
		_finale_wall_relief_best_body_clearance = highest_body_clearance
	var body_floor := highest_body_clearance
	if body_emergency_active:
		body_floor = (highest_body_clearance
			- BotConfig.BOSS_FINALE_BODY_EMERGENCY_CLEARANCE_SLACK)
	elif _finale_wall_body_relief_active:
		body_floor = max(
			BotConfig.BOSS_FINALE_BODY_CRITICAL_CLEARANCE,
			highest_body_clearance
				- BotConfig.BOSS_FINALE_WALL_BODY_RELIEF_CLEARANCE_SLACK)
		# v121: the relief floor can exceed every sampled lane in a tight
		# pack (v120 smoke capture 18555: best row 13.3 versus the 45-unit
		# contact tier while the incoming command held 46.5). The selection
		# loop then admits nothing and keeps the baseline, which previously
		# left the selected diagnostic at its -1 sentinel and correctly
		# failed the audit. Make the fallback explicit and diagnosed.
		if highest_body_clearance < body_floor:
			_finale_body_selected_clearance = _finale_body_input_clearance
			_finale_route_exit = "relief_underflow"
			_finale_route_body_floor = body_floor
			return baseline
	elif (enforce_pack_clearance
			and highest_body_clearance
				>= BotConfig.BOSS_FINALE_BODY_CRITICAL_CLEARANCE):
		# v110: once a projectile-tier-safe lane has opened meaningful body
		# clearance on the boss wave, prefer a genuinely open route and stay
		# close to the best lane until the capped clearance is reached. The old
		# fixed 45-unit floor could admit a visibly worse route through a pack.
		# The dose rides ONLY on body_slack, deliberately. Inside this min(),
		# a larger slack LOWERS the floor (more permissive) while a larger pack
		# term RAISES it (more restrictive) -- one scalar on both would push the
		# two halves in opposite directions and make the dose non-monotone, i.e.
		# unreadable at any value but 1.0. The pack term stays unscaled.
		body_floor = max(
			BotConfig.BOSS_FINALE_BODY_CRITICAL_CLEARANCE,
			min(BotConfig.BOSS_FINALE_BODY_PACK_CLEARANCE,
				highest_body_clearance - body_slack))
	elif highest_body_clearance >= BotConfig.BOSS_FINALE_BODY_CRITICAL_CLEARANCE:
		body_floor = BotConfig.BOSS_FINALE_BODY_CRITICAL_CLEARANCE
	else:
		body_floor = (highest_body_clearance - body_slack)
	var lowest_enemy_penalty := INF
	for row in rows:
		if (float(row[2]) >= projectile_floor
				and float(row[1]) >= body_floor):
			lowest_enemy_penalty = min(lowest_enemy_penalty, float(row[3]))
			# Counted on the SAME conditional that computes the minimum, so the
			# count cannot drift from the gate it describes. This is the
			# floor-admitted pool only; the enemy-penalty band is relative to
			# lowest_enemy_penalty and is not knowable until this loop ends, so
			# per-row band admission is recorded in the ranking loop instead.
			_finale_route_floor_admitted += 1
	_finale_route_sampled = rows.size()
	_finale_route_body_floor = body_floor
	_finale_route_projectile_floor = projectile_floor
	if lowest_enemy_penalty < INF:
		_finale_route_lowest_enemy_penalty = lowest_enemy_penalty
	var baseline_enemy_penalty := _predictive_enemy_path_penalty(
		pos, baseline, player_speed, times, enemies, bosses, 1.0)
	if route_latch_revalidation_enabled:
		var revalidation_floor := body_floor
		if body_emergency_active:
			revalidation_floor = (highest_body_clearance
				- BotConfig.BOSS_FINALE_BODY_EMERGENCY_CLEARANCE_SLACK)
		elif _finale_wall_body_relief_active:
			revalidation_floor = max(
				BotConfig.BOSS_FINALE_BODY_CRITICAL_CLEARANCE,
				highest_body_clearance
					- BotConfig.BOSS_FINALE_WALL_BODY_RELIEF_CLEARANCE_SLACK)
		elif (enforce_pack_clearance
				and highest_body_clearance
					>= BotConfig.BOSS_FINALE_BODY_CRITICAL_CLEARANCE):
			revalidation_floor = max(
				BotConfig.BOSS_FINALE_BODY_CRITICAL_CLEARANCE,
				min(BotConfig.ROUTE_CONVERSION_PACK_CLEARANCE,
					highest_body_clearance - body_slack))
		elif highest_body_clearance >= BotConfig.BOSS_FINALE_BODY_CRITICAL_CLEARANCE:
			revalidation_floor = BotConfig.BOSS_FINALE_BODY_CRITICAL_CLEARANCE
		else:
			revalidation_floor = highest_body_clearance - body_slack
		_capture_route_revalidation(
			rows, baseline, _finale_body_input_clearance,
			baseline_projectile_clearance, projectile_floor, revalidation_floor)
	# v118: an active loot dash deliberately accepts crowd pressure; the soft
	# enemy-penalty preference must not replace a dash route that already
	# satisfies the body and projectile floors.
	if (_finale_body_input_clearance >= body_floor
			and baseline_projectile_clearance >= projectile_floor
			and (dash_active
				or baseline_enemy_penalty <= lowest_enemy_penalty
					+ BotConfig.BOSS_FINALE_ENEMY_PENALTY_SLACK)):
		_finale_body_selected_clearance = _finale_body_input_clearance
		_finale_body_selected_projectile_clearance = baseline_projectile_clearance
		if not projectile_context.empty():
			_finale_projectile_final_body_clearance = _finale_body_input_clearance
		_finale_route_exit = "baseline_kept"
		_finale_route_baseline_admitted = true
		return baseline
	var best_dir := baseline
	var best_score := -1.0e18
	# Latched HERE, where the continuity term is about to be measured against it.
	_finale_route_prev = _prev_move
	for row in rows:
		var body_clearance := float(row[1])
		var projectile_clearance := float(row[2])
		var enemy_penalty := float(row[3])
		var candidate: Vector2 = row[0]
		# v130: score EVERY lane, including ones a gate drops. v129 recorded 0.0
		# for the terms of a skipped lane, which made the score of a gated-out
		# lane unrecoverable -- so no counterfactual over the ADMISSION rule
		# ("what would the ranking pick if the floor were lower?") was computable
		# offline. Scoring is pure arithmetic on values already in hand and has no
		# effect on the gates or on the emitted command; only admitted lanes are
		# ever compared against best_score, exactly as before.
		# Accumulation order is unchanged: ((proj - pen) + align) + continuity.
		var align_term := BotConfig.ESCAPE_ALIGN_BONUS * candidate.dot(baseline)
		var continuity_term := 0.0
		if _prev_move.length() > 0.1:
			continuity_term = (BotConfig.BOSS_FINALE_ESCAPE_CONTINUITY
				* candidate.dot(_prev_move))
		var score := projectile_clearance - enemy_penalty
		score += align_term
		score += continuity_term
		# v129: the two floor tests were one `or`; split so the record can name
		# WHICH gate dropped the lane. Both still `continue`, so the emitted
		# command is unchanged.
		if projectile_clearance < projectile_floor:
			_route_record(candidate, body_clearance, projectile_clearance,
				enemy_penalty, "projectile_floor", align_term, continuity_term, score)
			continue
		if body_clearance < body_floor:
			_route_record(candidate, body_clearance, projectile_clearance,
				enemy_penalty, "body_floor", align_term, continuity_term, score)
			continue
		if (enemy_penalty > lowest_enemy_penalty
				+ BotConfig.BOSS_FINALE_ENEMY_PENALTY_SLACK):
			_route_record(candidate, body_clearance, projectile_clearance,
				enemy_penalty, "enemy_slack", align_term, continuity_term, score)
			continue
		_route_record(candidate, body_clearance, projectile_clearance,
			enemy_penalty, "", align_term, continuity_term, score)
		if score > best_score:
			best_score = score
			best_dir = candidate
			_finale_body_selected_clearance = body_clearance
			_finale_body_selected_projectile_clearance = projectile_clearance
	# §41: the incumbent route above remains byte-identical and is the safety
	# reference. Only after it is fully reconstructed may the guarded conversion
	# controller inspect the broader PACK-80 tier. This runs only on the exact
	# `ranked` surface priced offline; every early return above stays untouched.
	# The ranked incumbent, not a later conversion, is the §41 body reference.
	if route_latch_revalidation_enabled:
		_finale_route_revalidation_reference = best_dir
		_finale_route_revalidation_reference_body = _finale_body_selected_clearance
		_finale_route_revalidation_reference_projectile = (
			_finale_body_selected_projectile_clearance)
	if (clearance_guarded_conversion_enabled
			and wave <= BotConfig.ROUTE_CONVERSION_MAX_WAVE
			and best_score > -1.0e17):
		var conversion_floor := body_floor
		if body_emergency_active:
			conversion_floor = (highest_body_clearance
				- BotConfig.BOSS_FINALE_BODY_EMERGENCY_CLEARANCE_SLACK)
		elif _finale_wall_body_relief_active:
			conversion_floor = max(
				BotConfig.BOSS_FINALE_BODY_CRITICAL_CLEARANCE,
				highest_body_clearance
					- BotConfig.BOSS_FINALE_WALL_BODY_RELIEF_CLEARANCE_SLACK)
		elif (enforce_pack_clearance
				and highest_body_clearance
					>= BotConfig.BOSS_FINALE_BODY_CRITICAL_CLEARANCE):
			conversion_floor = max(
				BotConfig.BOSS_FINALE_BODY_CRITICAL_CLEARANCE,
				min(BotConfig.ROUTE_CONVERSION_PACK_CLEARANCE,
					highest_body_clearance - body_slack))
		elif highest_body_clearance >= BotConfig.BOSS_FINALE_BODY_CRITICAL_CLEARANCE:
			conversion_floor = BotConfig.BOSS_FINALE_BODY_CRITICAL_CLEARANCE
		else:
			conversion_floor = highest_body_clearance - body_slack
		_finale_route_conversion_floor = conversion_floor
		var conversion_lowest_enemy_penalty := INF
		for conversion_row in rows:
			if (float(conversion_row[2]) >= projectile_floor
					and float(conversion_row[1]) >= conversion_floor):
				conversion_lowest_enemy_penalty = min(
					conversion_lowest_enemy_penalty, float(conversion_row[3]))
		var incumbent_body := _finale_body_selected_clearance
		_finale_route_conversion_input_body = incumbent_body
		var incumbent_inrange := _route_inrange_after(
			pos, best_dir, player_speed, enemies, bosses, weapons)
		_finale_route_conversion_input_inrange = incumbent_inrange
		var conversion_best_dir := best_dir
		var conversion_best_body := incumbent_body
		var conversion_best_projectile := _finale_body_selected_projectile_clearance
		var conversion_best_score := best_score
		var conversion_best_inrange := incumbent_inrange
		if incumbent_inrange >= 0.0 and conversion_lowest_enemy_penalty < INF:
			for conversion_row in rows:
				var conversion_body := float(conversion_row[1])
				var conversion_projectile := float(conversion_row[2])
				var conversion_penalty := float(conversion_row[3])
				if (conversion_projectile < projectile_floor
						or conversion_body < conversion_floor
						or conversion_penalty > conversion_lowest_enemy_penalty
							+ BotConfig.BOSS_FINALE_ENEMY_PENALTY_SLACK):
					continue
				_finale_route_conversion_admitted += 1
				var guard_floor := incumbent_body
				if incumbent_body >= BotConfig.BOSS_FINALE_BODY_CRITICAL_CLEARANCE:
					guard_floor = max(
						BotConfig.BOSS_FINALE_BODY_CRITICAL_CLEARANCE,
						incumbent_body
							* BotConfig.ROUTE_CONVERSION_BODY_RETENTION)
				if conversion_body < guard_floor:
					_finale_route_conversion_guard_vetoed += 1
					continue
				var conversion_candidate: Vector2 = conversion_row[0]
				var conversion_inrange := _route_inrange_after(
					pos, conversion_candidate, player_speed,
					enemies, bosses, weapons)
				var conversion_align := (
					BotConfig.ESCAPE_ALIGN_BONUS
						* conversion_candidate.dot(baseline))
				var conversion_continuity := 0.0
				if _prev_move.length() > 0.1:
					conversion_continuity = (
						BotConfig.BOSS_FINALE_ESCAPE_CONTINUITY
							* conversion_candidate.dot(_prev_move))
				var conversion_score := conversion_projectile - conversion_penalty
				conversion_score += conversion_align
				conversion_score += conversion_continuity
				if (conversion_inrange > conversion_best_inrange
						or (is_equal_approx(conversion_inrange, conversion_best_inrange)
							and conversion_score > conversion_best_score)):
					conversion_best_dir = conversion_candidate
					conversion_best_body = conversion_body
					conversion_best_projectile = conversion_projectile
					conversion_best_score = conversion_score
					conversion_best_inrange = conversion_inrange
		_finale_route_conversion_selected_inrange = conversion_best_inrange
		_finale_route_conversion_selected_body = conversion_best_body
		_finale_route_conversion_gain = conversion_best_inrange - incumbent_inrange
		if (_finale_route_conversion_gain
				> BotConfig.ROUTE_CONVERSION_GAIN_DEADBAND):
			best_dir = conversion_best_dir
			best_score = conversion_best_score
			_finale_body_selected_clearance = conversion_best_body
			_finale_body_selected_projectile_clearance = conversion_best_projectile
			_finale_route_conversion_applied = true
			_finale_route_exit = "conversion"
	if not _finale_route_conversion_applied:
		_finale_route_exit = "ranked"
	_finale_route_selected = best_dir
	_finale_route_best_score = best_score
	_finale_body_safety_active = best_dir.dot(baseline) < 0.999
	if not projectile_context.empty():
		_finale_projectile_final_clearance = _finale_body_selected_projectile_clearance
		_finale_projectile_final_body_clearance = _finale_body_selected_clearance
	return best_dir


func _finale_committed_escape(pos: Vector2, desired: Vector2, arena, bosses) -> Vector2:
	var boss_pos = _nearest_threat_pos(pos, [], bosses)
	if boss_pos != null:
		var away_from_boss: Vector2 = pos - boss_pos
		if (away_from_boss.length()
				<= BotConfig.BOSS_FINALE_CONTACT_ESCAPE_DISTANCE):
			_reset_finale_commit()
			return away_from_boss.normalized()
	var corner_escape := _late_corner_escape(pos, arena)
	if corner_escape != Vector2.ZERO:
		_finale_commit_dir = corner_escape.normalized()
		_finale_commit_origin = pos
		_finale_commit_ticks = 0
		_finale_commit_distance = 0.0
		return _finale_commit_dir
	var desired_n := desired.normalized() if desired.length() > 0.1 else _prev_move
	if desired_n.length() < 0.1:
		return Vector2.ZERO
	if _finale_commit_dir.length() < 0.1:
		_finale_commit_dir = desired_n
		_finale_commit_origin = pos
		_finale_commit_ticks = 0
	_finale_commit_distance = pos.distance_to(_finale_commit_origin)
	_finale_commit_ticks += 1
	if (_finale_commit_distance >= BotConfig.BOSS_FINALE_COMMIT_DISTANCE
			or _finale_commit_ticks >= BotConfig.BOSS_FINALE_COMMIT_MAX_TICKS):
		_finale_commit_dir = desired_n
		_finale_commit_origin = pos
		_finale_commit_ticks = 0
		_finale_commit_distance = 0.0
	return _normalize(
		_finale_commit_dir * (1.0 - BotConfig.BOSS_FINALE_COMMIT_DESIRE_BLEND)
		+ desired_n * BotConfig.BOSS_FINALE_COMMIT_DESIRE_BLEND)


func _reset_finale_route() -> void:
	# "not_reached" is a value no real ranking can produce, so a stale block can
	# never be mistaken for a fresh one. Counters reset to -1 for the same
	# reason: 0 is a plausible measurement, -1 is not.
	_finale_route_scores = []
	_finale_route_revalidation_ready = false
	_finale_route_revalidation_rows = []
	_finale_route_revalidation_reference_body = -1.0e18
	_finale_route_revalidation_reference_projectile = -1.0e18
	_finale_route_revalidation_reference = Vector2.ZERO
	_finale_route_revalidation_body_floor = -1.0e18
	_finale_route_revalidation_lowest_penalty = -1.0e18
	_finale_route_exit = "not_reached"
	_finale_route_body_floor = -1.0e18
	_finale_route_projectile_floor = -1.0e18
	_finale_route_lowest_enemy_penalty = -1.0
	_finale_route_sampled = -1
	_finale_route_floor_admitted = 0
	_finale_route_baseline_admitted = false
	_finale_route_selected = Vector2.ZERO
	_finale_route_best_score = -1.0e18
	_finale_route_baseline = Vector2.ZERO
	_finale_route_prev = Vector2.ZERO
	_finale_route_conversion_applied = false
	_finale_route_conversion_floor = -1.0e18
	_finale_route_conversion_input_inrange = -1.0
	_finale_route_conversion_selected_inrange = -1.0
	_finale_route_conversion_gain = 0.0
	_finale_route_conversion_input_body = -1.0
	_finale_route_conversion_selected_body = -1.0
	_finale_route_conversion_guard_vetoed = 0
	_finale_route_conversion_admitted = 0


func _route_record(candidate: Vector2, body_clearance: float,
		projectile_clearance: float, enemy_penalty: float, skip: String,
		align_term: float, continuity_term: float, score: float) -> void:
	# Pure observation. The early return is what makes the flag exactly inert:
	# with route_scores_enabled false this function touches no state at all.
	if not route_scores_enabled:
		return
	_finale_route_scores.append({
		"x": stepify(candidate.x, 0.0001),
		"y": stepify(candidate.y, 0.0001),
		"body": stepify(body_clearance, 0.01),
		"proj": stepify(projectile_clearance, 0.01),
		"pen": stepify(enemy_penalty, 0.01),
		"skip": skip,
		"align": stepify(align_term, 0.01),
		"cont": stepify(continuity_term, 0.01),
		"score": stepify(score, 0.01),
	})


func _capture_route_revalidation(rows: Array, reference: Vector2, reference_body: float,
		reference_projectile: float, projectile_floor: float,
		body_floor: float) -> void:
	# Load-bearing default-inert boundary: no allocation, iteration, or record
	# mutation occurs while the §45 instrument is disabled.
	if not route_latch_revalidation_enabled:
		return
	_finale_route_revalidation_rows = []
	for row in rows:
		var candidate: Vector2 = row[0]
		_finale_route_revalidation_rows.append({
			"x": stepify(candidate.x, 0.0001),
			"y": stepify(candidate.y, 0.0001),
			"body": stepify(float(row[1]), 0.01),
			"proj": stepify(float(row[2]), 0.01),
			"pen": stepify(float(row[3]), 0.01),
		})
	_finale_route_revalidation_ready = not _finale_route_revalidation_rows.empty()
	_finale_route_revalidation_reference = reference
	_finale_route_revalidation_reference_body = reference_body
	_finale_route_revalidation_reference_projectile = reference_projectile
	_finale_route_revalidation_body_floor = body_floor
	_finale_route_revalidation_lowest_penalty = INF
	for row in rows:
		if (float(row[2]) >= projectile_floor
				and float(row[1]) >= body_floor):
			_finale_route_revalidation_lowest_penalty = min(
				_finale_route_revalidation_lowest_penalty, float(row[3]))


func _route_revalidation_debug() -> Dictionary:
	if not route_latch_revalidation_enabled:
		return {"enabled": false}
	return {
		"enabled": true,
		"ready": _finale_route_revalidation_ready,
		"reason": "ready" if _finale_route_revalidation_ready else _finale_route_exit,
		"reference_body": stepify(
			_finale_route_revalidation_reference_body, 0.01),
		"reference_x": stepify(_finale_route_revalidation_reference.x, 0.0001),
		"reference_y": stepify(_finale_route_revalidation_reference.y, 0.0001),
		"reference_projectile": stepify(
			_finale_route_revalidation_reference_projectile, 0.01),
		"projectile_floor": stepify(_finale_route_projectile_floor, 0.01),
		"body_floor": stepify(_finale_route_revalidation_body_floor, 0.01),
		"lowest_penalty": stepify(
			_finale_route_revalidation_lowest_penalty, 0.01),
		"rows": _finale_route_revalidation_rows,
	}


func finale_route_debug() -> Dictionary:
	return {
		"exit": _finale_route_exit,
		"enabled": route_scores_enabled,
		"sampled": _finale_route_sampled,
		"floor_admitted": _finale_route_floor_admitted,
		"baseline_admitted": _finale_route_baseline_admitted,
		"body_floor": _finale_route_body_floor,
		"projectile_floor": _finale_route_projectile_floor,
		"lowest_enemy_penalty": _finale_route_lowest_enemy_penalty,
		"prev_x": stepify(_finale_route_prev.x, 0.0001),
		"prev_y": stepify(_finale_route_prev.y, 0.0001),
		"base_x": stepify(_finale_route_baseline.x, 0.0001),
		"base_y": stepify(_finale_route_baseline.y, 0.0001),
		"sel_x": stepify(_finale_route_selected.x, 0.0001),
		"sel_y": stepify(_finale_route_selected.y, 0.0001),
		"best_score": stepify(_finale_route_best_score, 0.01),
		"conversion_enabled": clearance_guarded_conversion_enabled,
		"conversion_applied": _finale_route_conversion_applied,
		"conversion_floor": stepify(_finale_route_conversion_floor, 0.01),
		"conversion_input_inrange": stepify(
			_finale_route_conversion_input_inrange, 0.0001),
		"conversion_selected_inrange": stepify(
			_finale_route_conversion_selected_inrange, 0.0001),
		"conversion_gain": stepify(_finale_route_conversion_gain, 0.0001),
		"conversion_input_body": stepify(
			_finale_route_conversion_input_body, 0.01),
		"conversion_selected_body": stepify(
			_finale_route_conversion_selected_body, 0.01),
		"conversion_guard_vetoed": _finale_route_conversion_guard_vetoed,
		"conversion_admitted": _finale_route_conversion_admitted,
		"revalidation": _route_revalidation_debug(),
		"scores": _finale_route_scores,
	}


func finale_translation_debug() -> Dictionary:
	return {
		"commit_distance": _finale_commit_distance,
		"commit_ticks": _finale_commit_ticks,
		"commit_x": _finale_commit_dir.x,
		"commit_y": _finale_commit_dir.y,
		"wall_recovery_active": _finale_wall_recovery_active,
		"projectile_safety_active": _finale_projectile_safety_active,
		"projectile_safety_urgency": _finale_projectile_safety_urgency,
		"projectile_input_clearance": _finale_projectile_input_clearance,
		"projectile_escape_clearance": _finale_projectile_escape_clearance,
		"projectile_blended_clearance": _finale_projectile_blended_clearance,
		"projectile_blend_repair_active": _finale_projectile_blend_repair_active,
		"projectile_final_clearance": _finale_projectile_final_clearance,
		"projectile_wall_replan_active": _finale_projectile_wall_replan_active,
		"wall_input_enemy_penalty": _finale_wall_input_enemy_penalty,
		"wall_best_enemy_penalty": _finale_wall_best_enemy_penalty,
		"wall_selected_enemy_penalty": _finale_wall_selected_enemy_penalty,
		"wall_input_body_clearance": _finale_wall_input_body_clearance,
		"wall_best_body_clearance": _finale_wall_best_body_clearance,
		"wall_selected_body_clearance": _finale_wall_selected_body_clearance,
		"wall_body_relief_active": _finale_wall_body_relief_active,
		"wall_relief_best_body_clearance": _finale_wall_relief_best_body_clearance,
		"projectile_input_enemy_penalty": _finale_projectile_input_enemy_penalty,
		"projectile_escape_enemy_penalty": _finale_projectile_escape_enemy_penalty,
		"projectile_blended_enemy_penalty": _finale_projectile_blended_enemy_penalty,
		"projectile_enemy_blend_repair_active": _finale_projectile_enemy_blend_repair_active,
		"projectile_final_enemy_penalty": _finale_projectile_final_enemy_penalty,
		"projectile_input_body_clearance": _finale_projectile_input_body_clearance,
		"projectile_escape_body_clearance": _finale_projectile_escape_body_clearance,
		"projectile_blended_body_clearance": _finale_projectile_blended_body_clearance,
		"projectile_final_body_clearance": _finale_projectile_final_body_clearance,
		"body_safety_active": _finale_body_safety_active,
		"body_emergency_active": _finale_body_emergency_active,
		"body_input_clearance": _finale_body_input_clearance,
		"body_best_clearance": _finale_body_best_clearance,
		"body_selected_clearance": _finale_body_selected_clearance,
		"body_projectile_floor": _finale_body_projectile_floor,
		"body_selected_projectile_clearance": _finale_body_selected_projectile_clearance,
		"loot_dash_active": _loot_dash_active,
		"build_strength": stepify(_build_strength_used, 0.001),
		"strength_tier": _strength_tier,
	}


# ─────────────────────── desire field (default kiter) ─────────────────────────

func _finale_turn_without_reversal(prev: Vector2, desired: Vector2,
	pos: Vector2, arena) -> Vector2:
	if prev.length() < 0.1 or desired.length() < 0.1:
		return desired
	var prev_n := prev.normalized()
	var desired_n := desired.normalized()
	if prev_n.dot(desired_n) >= BotConfig.BOSS_FINALE_REVERSE_DOT:
		return desired_n
	# A direct 180-degree command makes the movement component brake in place.
	# Turn through the perpendicular lane that best matches both the requested
	# dodge and the arena center; subsequent held decisions complete the turn.
	var left := Vector2(-prev_n.y, prev_n.x)
	var right := -left
	var w := float(arena.get("width", 2048.0))
	var h := float(arena.get("height", 1536.0))
	var to_center := (Vector2(w * 0.5, h * 0.5) - pos).normalized()
	var left_score := left.dot(desired_n) * 1.5 + left.dot(to_center) * 0.5
	var right_score := right.dot(desired_n) * 1.5 + right.dot(to_center) * 0.5
	return left if left_score >= right_score else right


# ── v123 strength tier + effective dash-gate helpers ────────────────────────────
func _update_strength_tier(s: float) -> void:
	# Hysteretic three-tier assignment; large jumps demote to neutral first then
	# re-promote in the same call, so a crash from strong lands in weak directly.
	_build_strength_used = s
	var tier := _strength_tier
	if tier == "strong" and s <= BotConfig.STRENGTH_EXIT_STRONG:
		tier = "neutral"
	elif tier == "weak" and s >= BotConfig.STRENGTH_EXIT_WEAK:
		tier = "neutral"
	if tier == "neutral":
		if s >= BotConfig.STRENGTH_ENTER_STRONG:
			tier = "strong"
		elif s <= BotConfig.STRENGTH_ENTER_WEAK:
			tier = "weak"
	_strength_tier = tier


func _strength_edge_kite_nearby() -> int:
	if _strength_tier == "strong":
		return BotConfig.LATE_EDGE_KITE_NEARBY + BotConfig.STRENGTH_STRONG_EDGE_KITE_DELTA
	if _strength_tier == "weak":
		return BotConfig.LATE_EDGE_KITE_NEARBY + BotConfig.STRENGTH_WEAK_EDGE_KITE_DELTA
	return BotConfig.LATE_EDGE_KITE_NEARBY


func _strength_pack_mult() -> float:
	if _strength_tier == "strong":
		return BotConfig.STRENGTH_STRONG_PACK_MULT
	if _strength_tier == "weak":
		return BotConfig.STRENGTH_WEAK_PACK_MULT
	return 1.0


func _effective_dash_arm_hp_floor(wave: int) -> float:
	# Stacking rule: wave-indexed base + tier delta, hard-clamped at the config min.
	var floor_value := BotConfig.loot_dash_arm_hp_floor(wave)
	if _strength_tier == "strong":
		floor_value += BotConfig.STRENGTH_STRONG_DASH_HP_FLOOR_DELTA
	elif _strength_tier == "weak":
		floor_value += BotConfig.STRENGTH_WEAK_DASH_HP_FLOOR_DELTA
	return max(floor_value, BotConfig.LOOT_DASH_ARM_FLOOR_MIN)


func _effective_dash_window_clearance(wave: int) -> float:
	var window := BotConfig.loot_dash_window_clearance(wave)
	if _strength_tier == "strong":
		window += BotConfig.STRENGTH_STRONG_DASH_WINDOW_DELTA
	elif _strength_tier == "weak":
		window += BotConfig.STRENGTH_WEAK_DASH_WINDOW_DELTA
	return max(window, BotConfig.LOOT_DASH_WINDOW_MIN)


func _build_desire(pos, enemies, bosses, loot, consumables, trees, weapons, arena, profile, player, wave = 1) -> Vector2:
	_reset_desire_debug()
	var early = wave <= BotConfig.EARLY_HUNT_WAVE
	var nearby = _count_nearby_enemies(pos, enemies, bosses)
	var sparse = nearby <= BotConfig.SPARSE_LOOT_ENEMIES
	var edge_kite = (wave >= BotConfig.LATE_EDGE_KITE_WAVE
		and nearby >= _strength_edge_kite_nearby())
	var weapon_max = _shortest_weapon_range(weapons)
	var engage = _engage_distance(profile, player, weapons)
	# Whole-run DPS band: sit inside shortest weapon range (slightly tight).
	engage *= BotConfig.DPS_ENGAGE_SCALE
	# Dev knob: dose the standoff distance. 1.0 (default) is inert.
	engage *= engage_distance_scale
	# Late swarms: hold a bit farther so we can skate the border without diving.
	if edge_kite:
		engage *= BotConfig.EDGE_ENGAGE_SCALE
	var nearest_d = _nearest_threat_dist(pos, enemies, bosses)
	var out_of_range = nearest_d > engage * BotConfig.OUT_OF_RANGE_PULL_THRESH
	# Reached shortest-weapon max range → stop charging; orbit the clear flank.
	#
	# THIS is the absorbing boundary that actually sets the standoff, not the
	# `engage` spring above. Inside it, the block at "Kill residual charge"
	# strips (1 - ENGAGE_STRAFE_INWARD_DAMP) = 82% of any inward component, so
	# the agent parks just outside weapon_max * 1.02. Measured: the realised
	# nearest-threat / shortest-weapon-range ratio is 1.062 across 272 trials,
	# against 0.631 for a human on the same fixture. Dosing `engage` alone was
	# verified INERT (scale 0.30 vs 2.00 moved the standoff 2.2%), which is why
	# the dev knob is applied here as well.
	var at_weapon_range = (not enemies.empty() or not bosses.empty()) and nearest_d <= weapon_max * 1.02 * engage_distance_scale
	_d_early = early
	_d_edge_kite = edge_kite
	_d_out_of_range = out_of_range
	_d_at_weapon_range = at_weapon_range
	_d_engage = engage
	_d_weapon_max = weapon_max
	_d_nearest_d = nearest_d
	var force = _enemy_engagement_force(pos, enemies, bosses, engage, profile, false, early, edge_kite)
	_t_enemy_engagement_x = force.x
	_t_enemy_engagement_y = force.y
	var tree_focus = (wave <= BotConfig.TREE_PRIORITY_WAVE and not trees.empty()
		and nearby <= BotConfig.SPARSE_LOOT_ENEMIES)
	if early:
		# Hunt packs for kills/XP — only peel for gold when the path is clear.
		var hunt = _early_hunt_force(pos, enemies, bosses)
		var loot_safe = (not loot.empty() and sparse
			and _has_clear_loot_target(pos, enemies, bosses, loot))
		if loot_safe:
			hunt *= BotConfig.EARLY_LOOT_HUNT_SCALE
			force *= BotConfig.EARLY_LOOT_VS_HUNT
			_d_early_force_mult = BotConfig.EARLY_LOOT_VS_HUNT
		# Yield hunt toward trees so we chop them while farming waves 1–10.
		if tree_focus:
			hunt *= BotConfig.TREE_HUNT_YIELD
		_t_early_hunt_x = hunt.x
		_t_early_hunt_y = hunt.y
		force += hunt
	elif edge_kite:
		var ek = _edge_kite_force(pos, enemies, bosses, arena, loot, wave)
		_t_edge_kite_x = ek.x
		_t_edge_kite_y = ek.y
		force += ek
		var pd_edge = (_pack_density_repulsion(pos, enemies, bosses)
			* BotConfig.EDGE_PACK_SHOVE * _strength_pack_mult())
		_t_pack_density_x = pd_edge.x
		_t_pack_density_y = pd_edge.y
		force += pd_edge
	elif not out_of_range:
		# Only shove off dense packs once already in DPS range.
		var pd = _pack_density_repulsion(pos, enemies, bosses) * _strength_pack_mult()
		_t_pack_density_x = pd.x
		_t_pack_density_y = pd.y
		force += pd
	if at_weapon_range and not edge_kite:
		var strafe = _engage_strafe_force(pos, enemies, bosses, arena, nearest_d, loot, wave)
		_t_engage_strafe_x = strafe.x
		_t_engage_strafe_y = strafe.y
		force += strafe
		# Kill residual charge into the pack once inside weapon max range.
		var nearest_target = _nearest_threat_pos(pos, enemies, bosses)
		if nearest_target != null:
			var to_enemy = (nearest_target - pos)
			var td = max(to_enemy.length(), 1.0)
			var dir_in = to_enemy / td
			var inward = force.dot(dir_in)
			if inward > 0.0:
				var damp = dir_in * inward * (1.0 - BotConfig.ENGAGE_STRAFE_INWARD_DAMP)
				# Recorded SIGNED, as the vector actually subtracted, so it sums
				# with the other terms rather than needing a sign convention.
				_t_inward_damp_x = -damp.x
				_t_inward_damp_y = -damp.y
				force -= damp
	elif force.length() > 0.01:
		var perp = Vector2(-force.y, force.x)
		var circle = BotConfig.CIRCLING_STRENGTH
		if early or out_of_range:
			circle *= 0.35
		elif edge_kite:
			circle *= 1.60
		var circ = perp * circle
		_t_circling_x = circ.x
		_t_circling_y = circ.y
		force += circ
	# During edge-kite, deprioritize loot vacuum so we don't run through the pack.
	if not edge_kite:
		var lf = _loot_attraction(pos, enemies, bosses, loot, wave)
		_t_loot_x = lf.x
		_t_loot_y = lf.y
		force += lf
		var cf = _consumable_attraction(pos, consumables, player, enemies, bosses, wave)
		_t_consumable_x = cf.x
		_t_consumable_y = cf.y
		force += cf
		var tf = _tree_attraction(pos, enemies, bosses, trees, wave)
		_t_tree_x = tf.x
		_t_tree_y = tf.y
		force += tf
	else:
		# Still grab nearby crates/boxes if safe; skip gold vacuum mid-swarm.
		var cf_edge = _consumable_attraction(pos, consumables, player, enemies, bosses, wave) * 0.45
		_t_consumable_x = cf_edge.x
		_t_consumable_y = cf_edge.y
		force += cf_edge
	# Soften wall shove while intentionally skating the rail.
	if edge_kite:
		var wf_edge = _wall_repulsion(pos, arena) * 0.35
		_t_wall_x = wf_edge.x
		_t_wall_y = wf_edge.y
		force += wf_edge
	else:
		var wf = _wall_repulsion(pos, arena)
		_t_wall_x = wf.x
		_t_wall_y = wf.y
		force += wf
	# Don't center-hug while out of range or edge-kiting late swarms.
	if not edge_kite and not out_of_range and not (early and (not loot.empty() or not enemies.empty())):
		var cp = _center_pull(pos, arena, enemies, bosses)
		_t_center_x = cp.x
		_t_center_y = cp.y
		force += cp
	_d_total_x = force.x
	_d_total_y = force.y
	return _normalize(force)


func _edge_kite_force(pos, enemies, bosses, arena, loot = [], wave = 1) -> Vector2:
	# Pull onto a border rail and orbit so the swarm approaches from one side.
	var w = float(arena.get("width", 2048.0))
	var h = float(arena.get("height", 1536.0))
	var inset = BotConfig.EDGE_RAIL_INSET
	var left = abs(pos.x - inset)
	var right = abs(pos.x - (w - inset))
	var top = abs(pos.y - inset)
	var bottom = abs(pos.y - (h - inset))
	var rail = Vector2(pos.x, pos.y)
	var tangent = Vector2(0.0, 1.0)
	var best = left
	var edge = "left"
	if right < best:
		best = right
		edge = "right"
	if top < best:
		best = top
		edge = "top"
	if bottom < best:
		best = bottom
		edge = "bottom"
	if edge == "left":
		rail = Vector2(inset, clamp(pos.y, inset, h - inset))
		tangent = Vector2(0.0, 1.0)
	elif edge == "right":
		rail = Vector2(w - inset, clamp(pos.y, inset, h - inset))
		tangent = Vector2(0.0, 1.0)
	elif edge == "top":
		rail = Vector2(clamp(pos.x, inset, w - inset), inset)
		tangent = Vector2(1.0, 0.0)
	else:
		rail = Vector2(clamp(pos.x, inset, w - inset), h - inset)
		tangent = Vector2(1.0, 0.0)

	# Pack centroid — keep lateral orbit continuity vs the swarm.
	var centroid = Vector2.ZERO
	var n = 0
	for e in enemies:
		centroid += Vector2(e.get("x", 0.0), e.get("y", 0.0))
		n += 1
	for b in bosses:
		centroid += Vector2(b.get("x", 0.0), b.get("y", 0.0))
		n += 2
	if n > 0:
		centroid /= float(n)
	var to_pack = centroid - pos
	if to_pack.length() > 1.0:
		var pack_dir = to_pack.normalized()
		# Prefer the tangent less aligned into the pack.
		if abs((-tangent).dot(pack_dir)) < abs(tangent.dot(pack_dir)):
			tangent = -tangent
	# v123: bounded loot/open-space bias BEFORE the continuity flip, so continuity
	# still has the final say. The loot term inside _score_strafe_side is capped by
	# engage_strafe_loot_cap(wave); enemy pressure and wall openness keep their
	# weights, so this cannot steer the orbit into a pack.
	var forward_score = _score_strafe_side(pos, tangent, enemies, bosses, arena, loot, wave)
	var back_score = _score_strafe_side(pos, -tangent, enemies, bosses, arena, loot, wave)
	if back_score > forward_score:
		tangent = -tangent
	if _prev_move.length() > 0.1 and _prev_move.dot(tangent) < 0.0:
		tangent = -tangent

	var force = Vector2.ZERO
	var to_rail = rail - pos
	var rail_d = max(to_rail.length(), 1.0)
	force += (to_rail / rail_d) * BotConfig.EDGE_BIAS
	force += tangent * BotConfig.EDGE_ORBIT
	# v123: anti corner-parking. With no enemy/boss ahead on the rail within
	# RAIL_CLEAR_RADIUS, add a tangential drift so the agent traverses the wall
	# toward open space/materials instead of parking in a corner.
	if not _rail_ahead_pressure(pos, enemies, bosses, tangent):
		force += tangent * BotConfig.EDGE_RAIL_DRIFT
	if n > 0 and to_pack.length() > 1.0:
		force -= to_pack.normalized() * 0.55
	return force


func _rail_ahead_pressure(pos, enemies, bosses, tangent_dir: Vector2) -> bool:
	for e in enemies:
		var off_e = Vector2(e.get("x", 0.0), e.get("y", 0.0)) - pos
		if (off_e.length() <= BotConfig.RAIL_CLEAR_RADIUS
				and off_e.dot(tangent_dir) > 0.0):
			return true
	for b in bosses:
		var off_b = Vector2(b.get("x", 0.0), b.get("y", 0.0)) - pos
		if (off_b.length() <= BotConfig.RAIL_CLEAR_RADIUS
				and off_b.dot(tangent_dir) > 0.0):
			return true
	return false


func _late_corner_escape(pos, arena) -> Vector2:
	var w = float(arena.get("width", 2048.0))
	var h = float(arena.get("height", 1536.0))
	var margin = BotConfig.LATE_CORNER_GUARD_MARGIN
	var inward_x = 0.0
	var inward_y = 0.0
	if pos.x < margin:
		inward_x = 1.0
	elif pos.x > w - margin:
		inward_x = -1.0
	if pos.y < margin:
		inward_y = 1.0
	elif pos.y > h - margin:
		inward_y = -1.0
	if inward_x == 0.0 or inward_y == 0.0:
		return Vector2.ZERO
	return Vector2(inward_x, inward_y).normalized()


func _tree_attraction(pos, enemies, bosses, trees, wave = 1) -> Vector2:
	if trees.empty() or wave > BotConfig.TREE_PRIORITY_WAVE:
		return Vector2.ZERO
	var threat_dist = _nearest_threat_dist(pos, enemies, bosses)
	if threat_dist < BotConfig.CONTACT_DANGER * BotConfig.TREE_THREAT_ABORT:
		return Vector2.ZERO
	var nearest = Vector2.ZERO
	var nearest_d = INF
	for t in trees:
		var tp = Vector2(t.get("x", 0.0), t.get("y", 0.0))
		var d = (tp - pos).length()
		if d < nearest_d:
			nearest_d = d
			nearest = tp
	if nearest_d == INF or nearest_d < 1.0:
		return Vector2.ZERO
	# Softer falloff so mid-map trees still get chased during combat.
	var falloff = pow(max(nearest_d, 30.0), 0.70)
	var weight = BotConfig.TREE_ATTRACTION
	# Boost when enemies exist — chop trees while farming, not only in empty arenas.
	if not enemies.empty() or not bosses.empty():
		weight *= BotConfig.TREE_COMBAT_MULT
	var safety = min(1.0, threat_dist / BotConfig.SAFETY_DISTANCE)
	safety = max(0.55, safety)
	return (nearest - pos) / nearest_d * weight * safety / falloff


func _shortest_weapon_range(weapons) -> float:
	var min_r = INF
	for w in weapons:
		var r = w.get("max_range", 0)
		if r != null and float(r) > 0.0 and float(r) < min_r:
			min_r = float(r)
	if min_r == INF:
		return BotConfig.DEFAULT_ENGAGE_DISTANCE
	return min_r


func _nearest_threat_pos(pos, enemies, bosses):
	var nearest = null
	var nearest_d = INF
	for e in enemies:
		var ep = Vector2(e.get("x", 0.0), e.get("y", 0.0))
		var d = (ep - pos).length()
		if d < nearest_d:
			nearest_d = d
			nearest = ep
	for b in bosses:
		var bp = Vector2(b.get("x", 0.0), b.get("y", 0.0))
		var d = (bp - pos).length()
		if d < nearest_d:
			nearest_d = d
			nearest = bp
	return nearest


func _engage_strafe_force(pos, enemies, bosses, arena, nearest_d, loot = [], wave = 1) -> Vector2:
	# Lateral orbit once inside shortest-weapon max range.
	var target = _nearest_threat_pos(pos, enemies, bosses)
	if target == null:
		return Vector2.ZERO
	var to_enemy = target - pos
	var td = max(to_enemy.length(), 1.0)
	var dir_in = to_enemy / td
	var left = Vector2(-dir_in.y, dir_in.x)
	var right = -left
	var left_score = _score_strafe_side(pos, left, enemies, bosses, arena, loot, wave)
	var right_score = _score_strafe_side(pos, right, enemies, bosses, arena, loot, wave)
	var side = left
	if right_score > left_score:
		side = right
	# Continuity when flanks are similar — don't flicker.
	if _prev_move.length() > 0.1 and abs(left_score - right_score) < 0.55:
		if _prev_move.dot(right) > _prev_move.dot(left):
			side = right
		else:
			side = left
	var band = clamp(1.15 - (nearest_d / max(td, 1.0)) * 0.25, 0.70, 1.30)
	return side * BotConfig.ENGAGE_STRAFE * band


func _score_strafe_side(pos, side: Vector2, enemies, bosses, arena, loot = [], wave = 1) -> float:
	# Higher = better: open wall lane + fewer enemies on that flank.
	# v119: plus a bounded bonus for materials on that flank, so the orbit
	# sweeps over currency instead of the empty side at equal safety.
	var w = float(arena.get("width", 2048.0))
	var h = float(arena.get("height", 1536.0))
	var look = BotConfig.ENGAGE_STRAFE_LOOKAHEAD
	var probe = pos + side * look
	var clear_x = min(probe.x, w - probe.x)
	var clear_y = min(probe.y, h - probe.y)
	var wall_clear = min(clear_x, clear_y)
	# Clamp so deep-center and near-wall are distinguishable.
	var wall_score = clamp(wall_clear / look, 0.0, 1.5)
	var enemy_pressure = 0.0
	var radius = BotConfig.PACK_DENSITY_RADIUS * 1.35
	for e in enemies:
		var ep = Vector2(e.get("x", 0.0), e.get("y", 0.0))
		var diff = ep - pos
		var d = max(diff.length(), 1.0)
		if d > radius:
			continue
		var lateral = diff.dot(side)
		if lateral <= 0.0:
			continue
		enemy_pressure += (lateral / d) * (1.0 / d) * 40.0
	for b in bosses:
		var bp = Vector2(b.get("x", 0.0), b.get("y", 0.0))
		var diff = bp - pos
		var d = max(diff.length(), 1.0)
		if d > radius * 1.4:
			continue
		var lateral = diff.dot(side)
		if lateral <= 0.0:
			continue
		enemy_pressure += (lateral / d) * (1.0 / d) * 80.0
	var loot_bonus = 0.0
	for item in loot:
		var ip = Vector2(item.get("x", 0.0), item.get("y", 0.0))
		var idiff = ip - pos
		var idist = max(idiff.length(), 1.0)
		if idist > radius:
			continue
		var ilateral = idiff.dot(side)
		if ilateral <= 0.0:
			continue
		loot_bonus += (ilateral / idist) * (1.0 / idist) * BotConfig.ENGAGE_STRAFE_LOOT_WEIGHT
	loot_bonus = min(loot_bonus, BotConfig.engage_strafe_loot_cap(wave))
	return (wall_score * BotConfig.ENGAGE_STRAFE_WALL_WEIGHT
		- enemy_pressure * BotConfig.ENGAGE_STRAFE_ENEMY_WEIGHT
		+ loot_bonus)


func _early_hunt_force(pos, enemies, bosses) -> Vector2:
	# Pull toward nearest threat + enemy cluster centroid so we farm kills.
	if enemies.empty() and bosses.empty():
		return Vector2.ZERO
	var nearest = Vector2.ZERO
	var nearest_d = INF
	var centroid = Vector2.ZERO
	var n = 0
	for e in enemies:
		var ep = Vector2(e.get("x", 0.0), e.get("y", 0.0))
		var d = (ep - pos).length()
		if d < nearest_d:
			nearest_d = d
			nearest = ep
		centroid += ep
		n += 1
	for b in bosses:
		var bp = Vector2(b.get("x", 0.0), b.get("y", 0.0))
		var d = (bp - pos).length()
		if d < nearest_d:
			nearest_d = d
			nearest = bp
		centroid += bp
		n += 2
	var force = Vector2.ZERO
	if nearest_d != INF and nearest_d > 1.0:
		force += (nearest - pos) / nearest_d * BotConfig.EARLY_HUNT_PULL
	if n > 0:
		centroid /= float(n)
		var cdiff = centroid - pos
		var cd = max(cdiff.length(), 1.0)
		force += (cdiff / cd) * BotConfig.EARLY_HUNT_CLUSTER
	return force


func _engage_distance(profile, player, weapons) -> float:
	if profile.fixed_engage_distance != null:
		return float(profile.fixed_engage_distance) * profile.engage_scale
	var ranges := []
	for w in weapons:
		var r = w.get("max_range", 0)
		if r != null and r > 0:
			ranges.append(float(r))
	if ranges.empty():
		return BotConfig.DEFAULT_ENGAGE_DISTANCE * profile.engage_scale
	var min_r: float = ranges[0]
	var max_r: float = ranges[0]
	for r in ranges:
		if r < min_r: min_r = r
		if r > max_r: max_r = r
	# Optimal DPS band = shortest weapon range (all weapons can hit).
	var optimal: float = max(min_r * BotConfig.OPTIMAL_RANGE_FRAC, BotConfig.MIN_ENGAGE_DISTANCE)
	var hp = float(player.get("hp", 1))
	var mhp = max(float(player.get("max_hp", 1)), 1.0)
	var hp_ratio = hp / mhp
	# Low HP: allow a slightly longer standoff, but never past longest weapon range.
	if hp_ratio < BotConfig.ENGAGE_HP_LOW:
		var hurt = min(max_r * 0.95, max(optimal * 1.20, BotConfig.MIN_ENGAGE_DISTANCE))
		optimal = hurt
	elif hp_ratio < BotConfig.ENGAGE_HP_HIGH:
		var t = (hp_ratio - BotConfig.ENGAGE_HP_LOW) / max(BotConfig.ENGAGE_HP_HIGH - BotConfig.ENGAGE_HP_LOW, 0.01)
		t = clamp(t, 0.0, 1.0)
		var mid = min(max_r * 0.92, optimal * 1.10)
		optimal = mid * (1.0 - t) + optimal * t
	return optimal * profile.engage_scale


func _enemy_engagement_force(pos, enemies, bosses, engage, profile, flee_only, early = false, edge_kite = false) -> Vector2:
	var force = Vector2.ZERO
	var nearest_d = INF
	var nearest_target = Vector2.ZERO
	var threats = []
	for e in enemies:
		var w := 1.0
		if calm_threat_mult != 1.0:
			# DEFENSIVE: two state builders exist. agent_controller's rich
			# observation (the live path) carries vx/vy; game_adapter's does NOT.
			# Treat a missing velocity as CHARGING so an absent signal never makes
			# the agent bolder than the shipped policy.
			if e.has("vx") and e.has("vy"):
				var esp := float(e.get("speed", 0.0))
				var ev := Vector2(float(e.get("vx", 0.0)), float(e.get("vy", 0.0))).length()
				if esp > 0.0 and ev / esp <= BotConfig.CHARGE_RATIO_THRESH:
					w = calm_threat_mult
		threats.append([e, w])
	for b in bosses:
		threats.append([b, BotConfig.BOSS_WEIGHT])
	var caution = max(float(profile.dodge_caution), 0.5)
	if early:
		caution *= BotConfig.EARLY_CAUTION_SCALE
	if edge_kite:
		caution *= BotConfig.EDGE_CAUTION_SCALE
	var contact_danger = BotConfig.CONTACT_DANGER * caution
	var soft_outer = BotConfig.LATE_SOFT_OUTER
	if early:
		# Tighter soft bubble early — stay on packs instead of backing off.
		soft_outer = 1.15
	elif edge_kite:
		soft_outer = 1.45

	if flee_only:
		var flee_range = max(engage, BotConfig.FLEE_REPEL_RANGE)
		for entry in threats:
			var target = _closest_approach(pos, entry[0])
			var diff = pos - target
			var d = max(diff.length(), 1.0)
			if d < flee_range:
				force += (diff / d) * (flee_range - d) * BotConfig.FLEE_REPEL_K * entry[1]
			if d < contact_danger:
				force += (diff / d) * BotConfig.CONTACT_REPULSION * entry[1] / (d * d)
		return force

	for entry in threats:
		var target = _closest_approach(pos, entry[0])
		var diff = pos - target
		var d = max(diff.length(), 1.0)
		var dir_away = diff / d
		if d < engage:
			force += dir_away * (engage - d) * BotConfig.ENGAGE_SPRING_K * caution * entry[1]
		# Soft bubble outside engage keeps packs from slowly collapsing in.
		elif d < engage * soft_outer:
			var soft_k = BotConfig.ENGAGE_SPRING_K * 0.40
			if early:
				soft_k *= 0.35
			force += dir_away * (engage * soft_outer - d) * soft_k * caution * entry[1]
		if d < contact_danger:
			force += dir_away * BotConfig.CONTACT_REPULSION * caution * entry[1] / (d * d)
		# Extra hard shove in melee range.
		if d < contact_danger * 0.55:
			force += dir_away * BotConfig.CONTACT_REPULSION * 0.55 * caution * entry[1] / max(d, 8.0)
		if d < nearest_d:
			nearest_d = d
			nearest_target = target

	# Keep nearest enemy inside optimal weapon range (maximize DPS) all run.
	# During edge-kite, pull less aggressively into the pack center.
	var pursue = true
	if nearest_d != INF and nearest_d > 1.0:
		var dir_to = (nearest_target - pos) / nearest_d
		if nearest_d > engage * BotConfig.OUT_OF_RANGE_PULL_THRESH:
			var overshoot = (nearest_d - engage) / max(engage, 1.0)
			var pull_k = BotConfig.OPTIMAL_RANGE_PULL
			if early:
				pull_k *= 1.35
			elif edge_kite:
				pull_k *= 0.55
			force += dir_to * pull_k * clamp(overshoot, 0.0, 2.5)
		elif pursue and nearest_d > engage * BotConfig.ENGAGE_PULL_THRESHOLD and not edge_kite:
			force += dir_to * BotConfig.ENGAGE_PULL
	return force


func _pack_density_repulsion(pos, enemies, bosses) -> Vector2:
	# Overnight D0 losses were mostly contact swarms (20–60 nearby enemies).
	var nearby := 0
	var centroid = Vector2.ZERO
	var radius = BotConfig.PACK_DENSITY_RADIUS
	for e in enemies:
		var ep = Vector2(e.get("x", 0.0), e.get("y", 0.0))
		var diff = pos - ep
		if diff.length() <= radius:
			nearby += 1
			centroid += ep
	for b in bosses:
		var bp = Vector2(b.get("x", 0.0), b.get("y", 0.0))
		var diff = pos - bp
		if diff.length() <= radius:
			nearby += 2
			centroid += bp
	if nearby < BotConfig.PACK_DENSITY_SOFT:
		return Vector2.ZERO
	centroid /= float(nearby)
	var away = pos - centroid
	var d = max(away.length(), 1.0)
	var t = (float(nearby) - BotConfig.PACK_DENSITY_SOFT) / max(BotConfig.PACK_DENSITY_HARD - BotConfig.PACK_DENSITY_SOFT, 1.0)
	t = clamp(t, 0.0, 1.5)
	return (away / d) * BotConfig.PACK_REPULSION * t


func _closest_approach(pos, obj) -> Vector2:
	var o_pos = Vector2(obj.get("x", 0.0), obj.get("y", 0.0))
	var speed = float(obj.get("speed", 0.0))
	if speed <= 0.0:
		return o_pos
	var to_player = pos - o_pos
	var dist = to_player.length()
	if dist < 0.001:
		return o_pos
	return o_pos + to_player.normalized() * speed * BotConfig.ENEMY_LOOKAHEAD


# ─────────────────────── projectile escape (default kiter dodge) ──────────────

func _projectile_escape(pos, projectiles, player_speed, arena, desire, enemies, bosses, profile = null, finale = false) -> Array:
	var context := _projectile_clearance_context(
		pos, projectiles, player_speed, profile, finale)
	if context.empty():
		return [Vector2.ZERO, 0.0, -1.0, -1.0]
	var caution := float(context["caution"])
	var times: Array = context["times"]
	var bullets_t: Array = context["bullets_t"]
	var enemy_pts = []
	for e in enemies:
		enemy_pts.append(Vector2(e.get("x", 0.0), e.get("y", 0.0)))
	for b in bosses:
		enemy_pts.append(Vector2(b.get("x", 0.0), b.get("y", 0.0)))
	var n_dirs = BotConfig.ESCAPE_DIRECTIONS
	var best_dir = Vector2.ZERO
	var best_score = -1.0e18
	var best_clearance = -1.0
	var rows := []
	var max_clearance := -1.0e18
	for k in range(n_dirs):
		var ang = (TAU * k) / float(n_dirs)
		var d = Vector2(cos(ang), sin(ang))
		var clearance = _dir_clearance(pos, d, player_speed, bullets_t, times, arena)
		var align = 0.0
		if desire.length() > 0:
			align = d.dot(desire)
		var penalty = _enemy_path_penalty(
			pos, d, player_speed, times, enemy_pts, caution)
		if finale:
			penalty = _predictive_enemy_path_penalty(
				pos, d, player_speed, times, enemies, bosses, caution)
		var body_clearance := _predictive_body_path_clearance(
			pos, d, player_speed, times, enemies, bosses)
		var score = clearance + BotConfig.ESCAPE_ALIGN_BONUS * align - penalty
		if finale and _prev_move.length() > 0.1:
			score += BotConfig.BOSS_FINALE_ESCAPE_CONTINUITY * d.dot(_prev_move)
		rows.append([d, score, clearance, body_clearance])
		max_clearance = max(max_clearance, clearance)
	var safe = BotConfig.ESCAPE_SAFE_CLEARANCE * caution
	var panic = BotConfig.ESCAPE_PANIC_CLEARANCE * caution
	var clearance_floor := -1.0e18
	if finale:
		if max_clearance >= safe:
			clearance_floor = safe
		elif max_clearance >= panic:
			clearance_floor = panic
		else:
			clearance_floor = (
				max_clearance - BotConfig.BOSS_FINALE_PROJECTILE_WALL_MIN_GAIN)
	# v106: choose a future body-clearance tier before the soft crowd score.
	# v109: a single lane barely above the safe projectile threshold must not
	# make every materially clearer body lane inadmissible. Broaden by at most the
	# existing 60-unit concession, never below panic when a panic-safe lane exists,
	# and only when that buys at least 20 units of predicted body clearance.
	var body_clearance_floor := -1.0e18
	if finale:
		var tier_max_body_clearance := -1.0e18
		for row in rows:
			if float(row[2]) >= clearance_floor:
				tier_max_body_clearance = max(
					tier_max_body_clearance, float(row[3]))
		var broadened_clearance_floor := (
			max_clearance - BotConfig.BOSS_FINALE_BODY_ESCAPE_PROJECTILE_SLACK)
		if max_clearance >= panic:
			broadened_clearance_floor = max(panic, broadened_clearance_floor)
		var broadened_max_body_clearance := -1.0e18
		for row in rows:
			if float(row[2]) >= broadened_clearance_floor:
				broadened_max_body_clearance = max(
					broadened_max_body_clearance, float(row[3]))
		if (broadened_clearance_floor < clearance_floor
				and broadened_max_body_clearance >= tier_max_body_clearance
					+ BotConfig.BOSS_FINALE_BODY_EMERGENCY_MIN_GAIN):
			clearance_floor = broadened_clearance_floor
			body_clearance_floor = (broadened_max_body_clearance
				- BotConfig.BOSS_FINALE_BODY_EMERGENCY_CLEARANCE_SLACK)
		elif (tier_max_body_clearance
				>= BotConfig.BOSS_FINALE_BODY_CRITICAL_CLEARANCE):
			body_clearance_floor = BotConfig.BOSS_FINALE_BODY_CRITICAL_CLEARANCE
		else:
			body_clearance_floor = (
				tier_max_body_clearance
					- BotConfig.BOSS_FINALE_BODY_CLEARANCE_SLACK)
	for row in rows:
		var row_dir: Vector2 = row[0]
		var row_score: float = row[1]
		var row_clearance: float = row[2]
		if row_clearance < clearance_floor:
			continue
		if finale and float(row[3]) < body_clearance_floor:
			continue
		if row_score > best_score:
			best_score = row_score
			best_dir = row_dir
			best_clearance = row_clearance
	var default_d = desire if desire.length() > 0 else Vector2.ZERO
	var default_clear = _dir_clearance(pos, default_d, player_speed, bullets_t, times, arena)
	var urgency: float
	if default_clear >= safe:
		urgency = 0.0
	elif default_clear <= panic:
		urgency = 1.0
	else:
		urgency = (safe - default_clear) / max(safe - panic, 1.0)
	return [best_dir, urgency, default_clear, best_clearance]


func _projectile_clearance_context(pos, projectiles, player_speed, profile = null,
		finale = false) -> Dictionary:
	var caution = 1.0
	if profile != null:
		caution = max(float(profile.dodge_caution), 0.5)
	if finale:
		caution *= BotConfig.BOSS_FINALE_PROJ_CAUTION
	var reach = player_speed * BotConfig.ESCAPE_HORIZON
	var threats = _threatening_bullets(pos, projectiles, reach, caution)
	if threats.empty():
		return {}
	var sample_count = BotConfig.ESCAPE_TIME_SAMPLES
	var horizon = BotConfig.ESCAPE_HORIZON
	var times = []
	for i in range(sample_count):
		var t = (float(i) / max(sample_count - 1, 1)) * horizon
		times.append(t)
	var bullets_t = []
	for ti in range(sample_count):
		var ts = times[ti]
		var row = []
		for threat in threats:
			row.append(threat[0] + threat[1] * ts)
		bullets_t.append(row)
	return {
		"caution": caution,
		"times": times,
		"bullets_t": bullets_t,
	}


func _threatening_bullets(pos, projectiles, reach, caution = 1.0) -> Array:
	var margin = BotConfig.PROJ_THREAT_RADIUS * caution + reach
	var horizon = BotConfig.ESCAPE_HORIZON
	var out = []
	for p in projectiles:
		var p_pos = Vector2(p.get("x", 0.0), p.get("y", 0.0))
		var p_vel = Vector2(p.get("vx", 0.0), p.get("vy", 0.0))
		var speed_sq = p_vel.x * p_vel.x + p_vel.y * p_vel.y
		var rel = pos - p_pos
		if speed_sq < 1.0:
			if rel.length() < margin:
				out.append([p_pos, p_vel])
			continue
		var t = rel.dot(p_vel) / speed_sq
		t = clamp(t, 0.0, horizon)
		var closest = p_pos + p_vel * t
		if (pos - closest).length() < margin:
			out.append([p_pos, p_vel])
	return out


func _dir_clearance(pos, d, player_speed, bullets_t, times, arena) -> float:
	# v116: the v115 smoke's four wave-20 hits each chose a lane whose sampled
	# minimum straddled a bullet: capture 20505 reported 28.1 units at the
	# t=0 and t=0.12 samples while the player passed through a stationary
	# radius-23 bullet at t=0.056. Relative motion is linear between samples,
	# so evaluate the continuous closest approach instead. Bullet velocities
	# are recovered exactly from the first two precomputed sample rows.
	var min_d = INF
	var horizon = float(times[times.size() - 1])
	var step = 0.0
	if times.size() > 1:
		step = float(times[1]) - float(times[0])
	var player_vel = d * player_speed
	for j in range(bullets_t[0].size()):
		var bullet_pos: Vector2 = bullets_t[0][j]
		var bullet_vel := Vector2.ZERO
		if step > 0.0:
			bullet_vel = (bullets_t[1][j] - bullet_pos) / step
		var rel_pos: Vector2 = pos - bullet_pos
		var rel_vel: Vector2 = player_vel - bullet_vel
		var speed_sq: float = rel_vel.length_squared()
		var closest_sec := 0.0
		if speed_sq > 1.0e-9:
			closest_sec = clamp(
				-rel_pos.dot(rel_vel) / speed_sq, 0.0, horizon)
		var dist = (rel_pos + rel_vel * closest_sec).length()
		if dist < min_d:
			min_d = dist
	var clearance = min_d
	if d.length() > 0:
		var horizon_t = times[times.size() - 1]
		var end_pt = pos + d * (player_speed * horizon_t)
		var m = BotConfig.ESCAPE_WALL_MARGIN
		var w = arena.get("width", 2048.0)
		var h = arena.get("height", 1536.0)
		if end_pt.x < m or end_pt.x > w - m or end_pt.y < m or end_pt.y > h - m:
			clearance -= BotConfig.ESCAPE_WALL_PENALTY
	return clearance


func _enemy_path_penalty(pos, d, player_speed, times, enemy_pts, caution = 1.0) -> float:
	if enemy_pts.empty():
		return 0.0
	var nearest = INF
	for ti in range(times.size()):
		var p_t = pos + d * (player_speed * times[ti])
		for ep in enemy_pts:
			var dist = (p_t - ep).length()
			if dist < nearest:
				nearest = dist
	var avoid = BotConfig.ENEMY_AVOID_DIST * caution
	if nearest >= avoid:
		return 0.0
	return (avoid - nearest) * BotConfig.ENEMY_AVOID_PENALTY * caution


func _predictive_enemy_path_penalty(pos, d, player_speed, times, enemies,
		bosses, caution = 1.0) -> float:
	if enemies.empty() and bosses.empty():
		return 0.0
	# threat_is_enemy tags which merged entries came from `enemies`; bosses keep
	# the unscaled thresholds.
	var threats: Array = []
	var threat_is_enemy: Array = []
	for enemy in enemies:
		threats.append(enemy)
		threat_is_enemy.append(true)
	for boss in bosses:
		threats.append(boss)
		threat_is_enemy.append(false)
	var avoid: float = float(BotConfig.ENEMY_AVOID_DIST) * float(caution)
	var critical: float = (
		float(BotConfig.BOSS_FINALE_WALL_ENEMY_CRITICAL_CLEARANCE)
		* float(caution))
	# Guarded so the default path neither changes behaviour nor pays for the
	# charge test.
	var scale_calm := tail_calm_penalty_mult != 1.0
	var penalty: float = 0.0
	for ti in range(times.size()):
		var future_sec: float = float(times[ti])
		var player_pos: Vector2 = pos + d * (player_speed * future_sec)
		for tix in range(threats.size()):
			var threat = threats[tix]
			var threat_pos: Vector2 = Vector2(
				float(threat.get("x", 0.0)), float(threat.get("y", 0.0)))
			var threat_vel: Vector2 = Vector2(
				float(threat.get("vx", 0.0)), float(threat.get("vy", 0.0)))
			var threat_radius: float = max(float(threat.get("radius", 18.0)), 0.0)
			var avoid_i: float = avoid
			var critical_i: float = critical
			if (scale_calm and bool(threat_is_enemy[tix])
					and _is_calm_enemy(threat)):
				avoid_i = avoid * tail_calm_penalty_mult
				critical_i = critical * tail_calm_penalty_mult
			var clearance: float = player_pos.distance_to(
				threat_pos + threat_vel * future_sec) - threat_radius
			if clearance < avoid_i:
				penalty += avoid_i - clearance
				if clearance < critical_i:
					var critical_gap: float = critical_i - clearance
					penalty += (critical_gap * critical_gap
						* BotConfig.BOSS_FINALE_WALL_ENEMY_CRITICAL_WEIGHT)
	return (penalty / float(max(times.size(), 1))
		* BotConfig.ENEMY_AVOID_PENALTY * caution)


# ─────────────────────── panic dodge (used by pure_repulsion) ─────────────────

func _panic_dodge(pos, enemies, bosses, projectiles, arena) -> Vector2:
	# Returns ZERO when no panic; otherwise a unit-length direction.
	var panic = Vector2.ZERO
	var fired = false
	var body_r = BotConfig.PANIC_BODY_REACH
	var bullet_r = BotConfig.PANIC_BULLET_REACH
	var threats = []
	for e in enemies:
		threats.append(e)
	for b in bosses:
		threats.append(b)
	for e in threats:
		var ep = Vector2(e.get("x", 0.0), e.get("y", 0.0))
		var diff = pos - ep
		var d = diff.length()
		if d < body_r and d > 1.0:
			panic += (diff / d) * (body_r - d)
			fired = true
	for p in projectiles:
		var pp = Vector2(p.get("x", 0.0), p.get("y", 0.0))
		var diff = pos - pp
		var d = diff.length()
		if d < bullet_r and d > 1.0:
			var pv = Vector2(p.get("vx", 0.0), p.get("vy", 0.0))
			var pv_mag = pv.length()
			if pv_mag > 1.0:
				var perp = Vector2(-pv.y, pv.x) / pv_mag
				var sign_v = 1.0 if diff.dot(perp) > 0 else -1.0
				panic += perp * sign_v * (bullet_r - d) * 1.5
			else:
				panic += (diff / d) * (bullet_r - d) * 1.5
			fired = true
	if not fired:
		return Vector2.ZERO
	var w = arena.get("width", 2048.0)
	var h = arena.get("height", 1536.0)
	var margin = BotConfig.REPULSION_WALL_MARGIN
	var wk = BotConfig.PANIC_WALL_K
	if pos.x < margin:
		panic.x += wk * (margin - pos.x) / margin
	if pos.x > w - margin:
		panic.x -= wk * (pos.x - (w - margin)) / margin
	if pos.y < margin:
		panic.y += wk * (margin - pos.y) / margin
	if pos.y > h - margin:
		panic.y -= wk * (pos.y - (h - margin)) / margin
	var m = panic.length()
	if m > BotConfig.PANIC_MIN_MAGNITUDE:
		return panic / m
	# Forces cancelled (mirror-bullet trap). Pick a direction perpendicular
	# to the threat axis so the bot SLIPS BETWEEN them instead of stalling.
	# This is the missing piece that caused trembling for Wounded/Pacifist
	# when two projectiles approached head-on at the player.
	var threat_axis = _threat_principal_axis(pos, enemies, bosses, projectiles,
		BotConfig.PANIC_BODY_REACH, BotConfig.PANIC_BULLET_REACH)
	if threat_axis.length() > 0.01:
		return _perpendicular_escape(threat_axis, pos, arena)
	# Final fallback: tangent along the dominant wall (original behaviour).
	var near_x_min = pos.x < margin
	var near_x_max = pos.x > w - margin
	var near_y_min = pos.y < margin
	var near_y_max = pos.y > h - margin
	if near_x_min or near_x_max or near_y_min or near_y_max:
		var tangent = Vector2.ZERO
		if near_x_min or near_x_max:
			tangent.y = 1.0 if pos.y < h * 0.5 else -1.0
		if near_y_min or near_y_max:
			tangent.x = 1.0 if pos.x < w * 0.5 else -1.0
		if tangent.length() > 0:
			return tangent.normalized()
	return Vector2.ZERO


# Returns the dominant direction along which nearby threats lie. For two
# bullets approaching head-on (player between), this returns roughly the
# axis connecting them — and we step perpendicular to it to slip out.
func _threat_principal_axis(pos, enemies, bosses, projectiles, body_r, bullet_r) -> Vector2:
	# Sum of (threat_pos - player) for nearby threats, plus second-moment
	# axis when sums cancel. For mirrored threats, sum is zero; we fall back
	# to picking the longest displacement vector.
	var dirs = []
	for e in enemies:
		var ep = Vector2(e.get("x", 0.0), e.get("y", 0.0))
		var d = (ep - pos).length()
		if d < body_r and d > 1.0:
			dirs.append(ep - pos)
	for b in bosses:
		var bp = Vector2(b.get("x", 0.0), b.get("y", 0.0))
		var d = (bp - pos).length()
		if d < body_r and d > 1.0:
			dirs.append(bp - pos)
	for p in projectiles:
		var pp = Vector2(p.get("x", 0.0), p.get("y", 0.0))
		var d = (pp - pos).length()
		if d < bullet_r and d > 1.0:
			dirs.append(pp - pos)
	if dirs.empty():
		return Vector2.ZERO
	# When threats mirror each other, the sum cancels. Pick the LINE that
	# best fits them: use the first vector's direction (or longest).
	var sum_vec = Vector2.ZERO
	for v in dirs:
		sum_vec += v
	if sum_vec.length() > 1.0:
		return sum_vec.normalized()
	# Sum cancelled — pick the longest single displacement.
	var longest = dirs[0]
	for v in dirs:
		if v.length() > longest.length():
			longest = v
	return longest.normalized()


# Given a threat axis, return a unit vector perpendicular to it. Pick the
# perpendicular side that aims toward arena center (more room to manoeuvre).
func _perpendicular_escape(axis, pos, arena) -> Vector2:
	var perp = Vector2(-axis.y, axis.x)
	var w = arena.get("width", 2048.0)
	var h = arena.get("height", 1536.0)
	var center = Vector2(w * 0.5, h * 0.5)
	var to_center = center - pos
	# Choose the perpendicular sign that points toward the center.
	if to_center.dot(perp) < 0:
		perp = -perp
	return perp.normalized()


# ─────────────────────── bull cluster rush ────────────────────────────────────

func _bull_attack_dir(pos, enemies, bosses, arena) -> Vector2:
	var threats = []
	for e in enemies:
		threats.append(e)
	for b in bosses:
		threats.append(b)
	if threats.size() < BotConfig.BULL_CLUSTER_MIN:
		return Vector2.ZERO
	var centroid = Vector2.ZERO
	for e in threats:
		centroid += Vector2(e.get("x", 0.0), e.get("y", 0.0))
	centroid /= float(threats.size())
	var inside = 0
	for e in threats:
		var ep = Vector2(e.get("x", 0.0), e.get("y", 0.0))
		if (ep - centroid).length() < BotConfig.BULL_CLUSTER_RADIUS:
			inside += 1
	if inside < BotConfig.BULL_CLUSTER_MIN:
		return Vector2.ZERO
	var w = arena.get("width", 2048.0)
	var h = arena.get("height", 1536.0)
	var m = BotConfig.REPULSION_WALL_MARGIN
	if (centroid.x < m or centroid.x > w - m or centroid.y < m or centroid.y > h - m):
		return Vector2.ZERO
	var to = centroid - pos
	if to.length() < 1.0:
		return Vector2.ZERO
	return to.normalized()


# ─────────────────────── pure repulsion (Bull/Wounded/Beast Master baseline) ──

func _pure_repulsion_flee(pos, enemies, bosses, projectiles, arena, prev_dir) -> Vector2:
	# Panic is handled in compute_movement before we get here.
	var flee = Vector2.ZERO

	# 1) Centroid flee.
	var nearby = []
	var reach = BotConfig.REPULSION_CENTROID_REACH
	for e in enemies:
		var ep = Vector2(e.get("x", 0.0), e.get("y", 0.0))
		if (ep - pos).length() < reach:
			nearby.append(ep)
	for b in bosses:
		var bp = Vector2(b.get("x", 0.0), b.get("y", 0.0))
		if (bp - pos).length() < reach:
			nearby.append(bp)
	if not nearby.empty():
		var centroid = Vector2.ZERO
		for n in nearby:
			centroid += n
		centroid /= float(nearby.size())
		var away = pos - centroid
		var ad = away.length()
		if ad > 1.0:
			flee += (away / ad) * BotConfig.REPULSION_CENTROID_K
	elif prev_dir.length() > 0.5:
		flee += prev_dir * BotConfig.REPULSION_CENTROID_K * 0.5

	# 2) Wall repulsion.
	var w = arena.get("width", 2048.0)
	var h = arena.get("height", 1536.0)
	var margin = BotConfig.REPULSION_WALL_MARGIN
	var wk = BotConfig.REPULSION_WALL_K
	if pos.x < margin:
		flee.x += wk * (margin - pos.x) / margin
	if pos.x > w - margin:
		flee.x -= wk * (pos.x - (w - margin)) / margin
	if pos.y < margin:
		flee.y += wk * (margin - pos.y) / margin
	if pos.y > h - margin:
		flee.y -= wk * (pos.y - (h - margin)) / margin

	# 3) Center pull (mild).
	var center = Vector2(w * 0.5, h * 0.5)
	var to_c = center - pos
	var cd = to_c.length()
	if cd > BotConfig.REPULSION_CENTER_INNER:
		var pull = min(1.0, (cd - BotConfig.REPULSION_CENTER_INNER) / BotConfig.REPULSION_CENTER_SPAN)
		flee += (to_c / cd) * BotConfig.REPULSION_CENTER_K * pull

	# 4) Projectile dodge — perpendicular sidestep.
	for p in projectiles:
		var pp = Vector2(p.get("x", 0.0), p.get("y", 0.0))
		var diff = pp - pos
		var d = diff.length()
		if d > BotConfig.REPULSION_BULLET_REACH or d < 1.0:
			continue
		var pv = Vector2(p.get("vx", 0.0), p.get("vy", 0.0))
		var pv_mag = pv.length()
		if pv_mag > 1.0:
			var perp = Vector2(-pv.y, pv.x) / pv_mag
			var sign_v = 1.0 if (pos - pp).dot(perp) > 0 else -1.0
			flee += perp * sign_v * BotConfig.REPULSION_BULLET_K * (BotConfig.REPULSION_BULLET_REACH - d) / BotConfig.REPULSION_BULLET_REACH
		else:
			flee += (-diff / d) * BotConfig.REPULSION_BULLET_K * (BotConfig.REPULSION_BULLET_REACH - d) / BotConfig.REPULSION_BULLET_REACH

	# Detect cancellation (mirror-bullet trap): when summed forces are tiny
	# despite obvious threats nearby, pick a perpendicular escape direction
	# instead of returning prev_dir (which often points STRAIGHT INTO a
	# bullet on its path). This is the trembling Pacifist/Wounded user saw.
	var mag = flee.length()
	if mag < BotConfig.PANIC_MIN_MAGNITUDE:
		var threat_axis = _threat_principal_axis(pos, enemies, bosses, projectiles,
			BotConfig.REPULSION_CENTROID_REACH, BotConfig.REPULSION_BULLET_REACH)
		if threat_axis.length() > 0.01:
			return _perpendicular_escape(threat_axis, pos, arena)
	if mag > 0:
		return flee / mag
	if prev_dir.length() > 0.5:
		return prev_dir.normalized()
	return Vector2(1.0, 0.0)


# ─────────────────────── orbital flee (Beast Master) ──────────────────────────

func _orbital_flee(pos, enemies, bosses, projectiles, arena, prev_dir, player_speed) -> Vector2:
	var w = arena.get("width", 2048.0)
	var h = arena.get("height", 1536.0)
	var center = Vector2(w * 0.5, h * 0.5)
	var radial = pos - center
	var rad_dist = radial.length()
	var target_radius = min(w, h) * BotConfig.ORBIT_RADIUS_FRACTION
	if rad_dist < 1.0:
		if prev_dir.length() > 0.5:
			return prev_dir.normalized()
		return Vector2(1.0, 0.0)
	var radial_unit = radial / rad_dist
	# Screen-clockwise tangent (Y-down): (-y, x)
	var tangent = Vector2(-radial_unit.y, radial_unit.x)
	var drift = abs(rad_dist - target_radius) / target_radius
	var radial_sign: float
	if rad_dist > target_radius:
		radial_sign = -1.0
	elif rad_dist < target_radius * BotConfig.ORBIT_INNER_FRACTION:
		radial_sign = 1.0
		drift = (target_radius * BotConfig.ORBIT_INNER_FRACTION - rad_dist) / (target_radius * BotConfig.ORBIT_INNER_FRACTION)
	else:
		radial_sign = 0.0
		drift = 0.0
	var radial_weight = min(BotConfig.ORBIT_RADIAL_MIX_MAX,
		BotConfig.ORBIT_RADIAL_MIX_BASE + drift * BotConfig.ORBIT_RADIAL_MIX_GAIN)
	var direction = tangent * (1.0 - radial_weight) + radial_unit * radial_sign * radial_weight
	var nrm = direction.length()
	if nrm > 0:
		direction /= nrm

	# Threat veer.
	var threats_pos = []
	var threats_vel = []
	var safety = BotConfig.FLEE_ENEMY_SPEED_SAFETY
	for e in enemies:
		var ep = Vector2(e.get("x", 0.0), e.get("y", 0.0))
		threats_pos.append(ep)
		threats_vel.append(_enemy_velocity(pos, ep, float(e.get("speed", 0.0)) * safety))
	for b in bosses:
		var bp = Vector2(b.get("x", 0.0), b.get("y", 0.0))
		threats_pos.append(bp)
		threats_vel.append(_enemy_velocity(pos, bp, float(b.get("speed", 0.0)) * safety))
	for p in projectiles:
		threats_pos.append(Vector2(p.get("x", 0.0), p.get("y", 0.0)))
		threats_vel.append(Vector2(p.get("vx", 0.0), p.get("vy", 0.0)))

	if not threats_pos.empty():
		var veer = Vector2.ZERO
		var min_d_overall = INF
		var horizon = BotConfig.ORBIT_VEER_HORIZON
		var n_steps = BotConfig.ORBIT_VEER_STEPS
		var dt = horizon / float(n_steps)
		var bot_pred = pos
		var threats_pred = []
		for tp in threats_pos:
			threats_pred.append(tp)
		for step in range(n_steps):
			bot_pred += direction * player_speed * dt
			for i in range(threats_vel.size()):
				threats_pred[i] += threats_vel[i] * dt
				var diff = bot_pred - threats_pred[i]
				var d = diff.length()
				if d < min_d_overall:
					min_d_overall = d
				if d < BotConfig.ORBIT_VEER_DIST:
					var away = diff / max(d, 1.0)
					var weight = (BotConfig.ORBIT_VEER_DIST - d) / BotConfig.ORBIT_VEER_DIST
					veer += away * weight
		if min_d_overall < BotConfig.ORBIT_CRITICAL_DIST and veer.length() < 0.5:
			veer = radial_unit * BotConfig.ORBIT_CRITICAL_RADIAL
		if veer.length() > 0:
			veer = veer.normalized()
			direction = direction * (1.0 - BotConfig.ORBIT_VEER_STRENGTH) + veer * BotConfig.ORBIT_VEER_STRENGTH
			var n2 = direction.length()
			if n2 > 0:
				direction /= n2

	# Enforce strict CW: at least ORBIT_MIN_TANGENT in the CW direction.
	var cw_component = direction.dot(tangent)
	if cw_component < BotConfig.ORBIT_MIN_TANGENT:
		var radial_component = direction.dot(radial_unit)
		if abs(radial_component) < 0.05:
			radial_component = BotConfig.ORBIT_TANGENT_BLOCK_RADIAL_NUDGE
		direction = tangent * BotConfig.ORBIT_MIN_TANGENT + radial_unit * radial_component
		var n3 = direction.length()
		if n3 > 0:
			direction /= n3
		else:
			direction = tangent
	return direction


# ─────────────────────── Pacifist sampling flee ──────────────────────────────

func _flee_direction(pos, enemies, bosses, arena, player_speed, projectiles, prev_dir, profile) -> Vector2:
	var threats = []
	for e in enemies:
		threats.append(e)
	for b in bosses:
		threats.append(b)
	var T = BotConfig.FLEE_TIME_SAMPLES
	var horizon = BotConfig.FLEE_HORIZON
	var times = []
	for i in range(T):
		times.append((float(i) / max(T - 1, 1)) * horizon)

	# Enemy trajectories.
	var enemies_t = []  # T entries, each an Array of Vector2 (one per enemy)
	if not threats.empty():
		var e_pos = []
		var e_vel = []
		var safety = BotConfig.FLEE_ENEMY_SPEED_SAFETY
		for e in threats:
			var ep = Vector2(e.get("x", 0.0), e.get("y", 0.0))
			e_pos.append(ep)
			e_vel.append(_enemy_velocity(pos, ep, float(e.get("speed", 0.0)) * safety))
		for ti in range(T):
			var row = []
			for i in range(e_pos.size()):
				row.append(e_pos[i] + e_vel[i] * times[ti])
			enemies_t.append(row)
	# Projectile trajectories.
	var proj_t = []
	if not projectiles.empty():
		var p_pos = []
		var p_vel = []
		for p in projectiles:
			p_pos.append(Vector2(p.get("x", 0.0), p.get("y", 0.0)))
			p_vel.append(Vector2(p.get("vx", 0.0), p.get("vy", 0.0)))
		for ti in range(T):
			var row = []
			for i in range(p_pos.size()):
				row.append(p_pos[i] + p_vel[i] * times[ti])
			proj_t.append(row)
	if enemies_t.empty() and proj_t.empty():
		return Vector2.ZERO

	var w = arena.get("width", 2048.0)
	var h = arena.get("height", 1536.0)
	var margin = BotConfig.FLEE_WALL_MARGIN
	var center = Vector2(w * 0.5, h * 0.5)
	var to_center = center - pos
	var to_center_norm = to_center.length()
	var center_dir = to_center / to_center_norm if to_center_norm > 1.0 else Vector2.ZERO
	var wall_proximity = min(min(pos.x, w - pos.x), min(pos.y, h - pos.y))
	var stuck_mult = BotConfig.FLEE_STUCK_CENTER_MULT if wall_proximity < BotConfig.FLEE_STUCK_DIST else 1.0
	var body_pen_mult: float = profile.body_pen_multiplier

	var best_dir = Vector2.ZERO
	var best_score = -1.0e18
	var n_dirs = BotConfig.FLEE_DIRECTIONS
	for k in range(n_dirs):
		var ang = (TAU * k) / float(n_dirs)
		var d = Vector2(cos(ang), sin(ang))
		var player_t = []
		for ti in range(T):
			player_t.append(pos + d * (player_speed * times[ti]))

		# Enemy clearance + crowd penalty.
		var min_e = INF
		var crowd_pen = 0.0
		if not enemies_t.empty():
			for ti in range(T):
				for ep in enemies_t[ti]:
					var dist = (player_t[ti] - ep).length()
					if dist < min_e:
						min_e = dist
					if dist < BotConfig.FLEE_CROWD_RADIUS:
						crowd_pen += (BotConfig.FLEE_CROWD_RADIUS - dist) * BotConfig.FLEE_CROWD_K

		# Projectile clearance.
		var min_p = INF
		if not proj_t.empty():
			for ti in range(T):
				for pp in proj_t[ti]:
					var dist = (player_t[ti] - pp).length()
					if dist < min_p:
						min_p = dist

		var min_d = min(min_e, min_p)
		var bullet_pen = 0.0
		if min_p < BotConfig.FLEE_BULLET_DANGER:
			bullet_pen = (BotConfig.FLEE_BULLET_DANGER - min_p) * BotConfig.FLEE_BULLET_K
		var body_pen = 0.0
		if body_pen_mult > 0 and min_e < BotConfig.FLEE_BODY_DANGER:
			var gap = BotConfig.FLEE_BODY_DANGER - min_e
			body_pen = gap * gap * BotConfig.FLEE_BODY_K * body_pen_mult

		# Wall penalty (averaged across path).
		var wall_pen = 0.0
		for pt in player_t:
			if pt.x < margin:
				wall_pen += BotConfig.FLEE_WALL_PENALTY * (margin - pt.x) / margin
			if pt.x > w - margin:
				wall_pen += BotConfig.FLEE_WALL_PENALTY * (pt.x - (w - margin)) / margin
			if pt.y < margin:
				wall_pen += BotConfig.FLEE_WALL_PENALTY * (margin - pt.y) / margin
			if pt.y > h - margin:
				wall_pen += BotConfig.FLEE_WALL_PENALTY * (pt.y - (h - margin)) / margin
		wall_pen /= float(player_t.size())

		var center_align = d.dot(center_dir) if to_center_norm > 1.0 else 0.0
		var center_factor = min(1.0, to_center_norm / max(w, h) * 2.0)
		var center_bonus = BotConfig.FLEE_CENTER_BIAS * center_align * center_factor * stuck_mult
		if center_align < 0:
			center_bonus -= BotConfig.FLEE_AWAY_PENALTY * (-center_align) * center_factor * center_factor

		# Hysteresis.
		var hyst = 0.0
		if prev_dir.length() > 0.5:
			var dot_v = d.dot(prev_dir)
			hyst = BotConfig.FLEE_HYSTERESIS_BONUS * dot_v
			if dot_v < 0:
				hyst -= BotConfig.FLEE_REVERSE_PENALTY * (-dot_v)

		var score = min_d - crowd_pen - wall_pen - bullet_pen - body_pen + center_bonus + hyst
		if score > best_score:
			best_score = score
			best_dir = d
	# Tie-breaker: when every direction scored very badly (all paths walk into
	# a bullet or body), the sampler returns the "least bad" one — often
	# diagonally INTO a hazard. If best score is below a panic threshold,
	# slip perpendicular to the dominant threat axis instead.
	if best_score < -BotConfig.FLEE_BULLET_K * BotConfig.FLEE_BULLET_DANGER * 0.5:
		var axis = _threat_principal_axis(pos, enemies, bosses, projectiles,
			BotConfig.FLEE_BODY_DANGER * 2.0, BotConfig.FLEE_BULLET_DANGER * 2.0)
		if axis.length() > 0.01:
			return _perpendicular_escape(axis, pos, arena)
	return best_dir


# ─────────────────────── Soldier stop-and-shoot ───────────────────────────────

func _should_stand(state, pos, enemies, bosses, weapons) -> bool:
	# Stand still to fire only when safe AND an enemy is in firing range.
	for p in state.get("projectiles", []):
		if _bullet_threatens_point(pos, p, BotConfig.PROJ_MAX_HORIZON, BotConfig.STAND_BULLET_CLEAR):
			return false
	var nearest = _nearest_threat_dist(pos, enemies, bosses)
	if nearest < BotConfig.STAND_DANGER_DIST:
		return false
	var max_range = BotConfig.DEFAULT_ENGAGE_DISTANCE
	for w in weapons:
		var r = w.get("max_range", 0)
		if r != null and r > max_range:
			max_range = float(r)
	if nearest > max_range:
		return false
	return true


func _bullet_threatens_point(pos, p, horizon, radius) -> bool:
	# Would this bullet pass within `radius` of a stationary player within `horizon`?
	var p_pos = Vector2(p.get("x", 0.0), p.get("y", 0.0))
	var p_vel = Vector2(p.get("vx", 0.0), p.get("vy", 0.0))
	var speed_sq = p_vel.x * p_vel.x + p_vel.y * p_vel.y
	var rel = pos - p_pos
	if speed_sq < 1.0:
		return rel.length() < radius
	var t = rel.dot(p_vel) / speed_sq
	t = clamp(t, 0.0, horizon)
	var closest = p_pos + p_vel * t
	return (pos - closest).length() < radius


# ─────────────────────── helpers ──────────────────────────────────────────────

func _normalize(v) -> Vector2:
	var m = v.length()
	if m < 0.001:
		return Vector2.ZERO
	return v / m


func _enemy_velocity(pos, e_pos, speed) -> Vector2:
	if speed <= 0.0:
		return Vector2.ZERO
	var toward = pos - e_pos
	var d = toward.length()
	if d < 1.0:
		return Vector2.ZERO
	return (toward / d) * speed


func _wall_repulsion(pos, arena) -> Vector2:
	var w = arena.get("width", 2048.0)
	var h = arena.get("height", 1536.0)
	var f = Vector2.ZERO
	var margin = BotConfig.WALL_MARGIN
	var k = BotConfig.WALL_REPULSION
	if pos.x < margin:
		f.x += k / sqrt(max(pos.x, 1.0))
	if pos.x > w - margin:
		f.x -= k / sqrt(max(w - pos.x, 1.0))
	if pos.y < margin:
		f.y += k / sqrt(max(pos.y, 1.0))
	if pos.y > h - margin:
		f.y -= k / sqrt(max(h - pos.y, 1.0))
	return f


func _center_pull(pos, arena, enemies, bosses) -> Vector2:
	var w = arena.get("width", 2048.0)
	var h = arena.get("height", 1536.0)
	var center = Vector2(w * 0.5, h * 0.5)
	var margin = BotConfig.WALL_MARGIN * 2.0
	var near_wall = (pos.x < margin or pos.x > w - margin
		or pos.y < margin or pos.y > h - margin)
	if not near_wall:
		return Vector2.ZERO
	var threat_dist = _nearest_threat_dist(pos, enemies, bosses)
	if threat_dist > BotConfig.SAFETY_DISTANCE * 2.0:
		return Vector2.ZERO
	var diff = center - pos
	var dist = max(diff.length(), 1.0)
	return (diff / dist) * 200.0


func _nearest_threat_dist(pos, enemies, bosses) -> float:
	var min_d = INF
	for e in enemies:
		var ep = Vector2(e.get("x", 0.0), e.get("y", 0.0))
		var d = (ep - pos).length()
		if d < min_d:
			min_d = d
	for b in bosses:
		var bp = Vector2(b.get("x", 0.0), b.get("y", 0.0))
		var d = (bp - pos).length()
		if d < min_d:
			min_d = d
	return min_d


func _loot_greed_mult(wave: int, nearby: int) -> float:
	var mult := 1.0
	if wave <= BotConfig.EARLY_LOOT_WAVE:
		# Full greed through plateau wave, then soft taper — never below floor.
		if wave <= BotConfig.EARLY_LOOT_PLATEAU_WAVE:
			mult = BotConfig.EARLY_LOOT_MULT
		else:
			var span = max(BotConfig.EARLY_LOOT_WAVE - BotConfig.EARLY_LOOT_PLATEAU_WAVE, 1)
			var t = 1.0 - float(wave - BotConfig.EARLY_LOOT_PLATEAU_WAVE) / float(span)
			t = clamp(t, 0.0, 1.0)
			mult = BotConfig.EARLY_LOOT_FLOOR + (BotConfig.EARLY_LOOT_MULT - BotConfig.EARLY_LOOT_FLOOR) * t
		mult = max(mult, BotConfig.EARLY_LOOT_FLOOR)
	if nearby <= BotConfig.SPARSE_LOOT_ENEMIES:
		mult *= BotConfig.SPARSE_LOOT_MULT
	return mult


func _count_nearby_enemies(pos, enemies, bosses) -> int:
	var nearby := 0
	var radius = BotConfig.PACK_DENSITY_RADIUS
	for e in enemies:
		var ep = Vector2(e.get("x", 0.0), e.get("y", 0.0))
		if (ep - pos).length() <= radius:
			nearby += 1
	for b in bosses:
		var bp = Vector2(b.get("x", 0.0), b.get("y", 0.0))
		if (bp - pos).length() <= radius:
			nearby += 2
	return nearby


func _enemies_blocking_loot(pos, loot_pos, enemies, bosses) -> int:
	# Count living threats on the corridor to the pile + clustered on the pile.
	var path = loot_pos - pos
	var plen = max(path.length(), 1.0)
	var dir = path / plen
	var width = BotConfig.LOOT_PATH_WIDTH
	var pile_r = BotConfig.LOOT_PILE_CLEAR_RADIUS
	var n := 0
	for e in enemies:
		var ep = Vector2(e.get("x", 0.0), e.get("y", 0.0))
		if (ep - loot_pos).length() <= pile_r:
			n += 1
			continue
		var rel = ep - pos
		var along = rel.dot(dir)
		if along < 0.0 or along > plen:
			continue
		var lateral = (rel - dir * along).length()
		if lateral <= width:
			n += 1
	for b in bosses:
		var bp = Vector2(b.get("x", 0.0), b.get("y", 0.0))
		if (bp - loot_pos).length() <= pile_r * 1.25:
			n += 2
			continue
		var rel = bp - pos
		var along = rel.dot(dir)
		if along < 0.0 or along > plen:
			continue
		var lateral = (rel - dir * along).length()
		if lateral <= width * 1.15:
			n += 2
	return n


func _has_clear_loot_target(pos, enemies, bosses, loot) -> bool:
	for item in loot:
		var ip = Vector2(item.get("x", 0.0), item.get("y", 0.0))
		if _enemies_blocking_loot(pos, ip, enemies, bosses) <= BotConfig.LOOT_PACK_ALLOW:
			return true
	return false


func _loot_attraction(pos, enemies, bosses, loot, wave = 1) -> Vector2:
	if loot.empty():
		return Vector2.ZERO
	var threat_dist = _nearest_threat_dist(pos, enemies, bosses)
	var nearby = _count_nearby_enemies(pos, enemies, bosses)
	var early = wave <= BotConfig.EARLY_LOOT_WAVE
	var sparse = nearby <= BotConfig.SPARSE_LOOT_ENEMIES
	# Never gold-dive a dense local pack — clear it first.
	if nearby >= BotConfig.PACK_DENSITY_SOFT:
		return Vector2.ZERO
	var safety = min(1.0, threat_dist / BotConfig.SAFETY_DISTANCE)
	if early and sparse:
		if threat_dist < BotConfig.CONTACT_DANGER * BotConfig.EARLY_LOOT_CONTACT_ABORT:
			return Vector2.ZERO
		safety = max(BotConfig.EARLY_LOOT_SAFETY_FLOOR, safety)
	else:
		safety = max(0.20, safety)
	var greed = _loot_greed_mult(wave, nearby)
	var force = Vector2.ZERO
	for item in loot:
		var ip = Vector2(item.get("x", 0.0), item.get("y", 0.0))
		var blockers = _enemies_blocking_loot(pos, ip, enemies, bosses)
		# Skip piles still sitting inside / behind a living group.
		if blockers > BotConfig.LOOT_PACK_ALLOW:
			continue
		var diff = ip - pos
		var dist = max(diff.length(), 1.0)
		var falloff = dist
		if early:
			falloff = pow(dist, 0.65)
		var clear_mult = 1.0
		if blockers > 0:
			clear_mult = 1.0 / float(1 + blockers)
		force += (diff / dist) * BotConfig.LOOT_ATTRACTION * greed * safety * clear_mult / falloff
	return force


func _is_valuable_pickup(cid: String) -> bool:
	if cid.empty():
		return false
	var id = cid.to_lower()
	if id.find("item_box") >= 0:
		return true
	if id.find("legendary") >= 0:
		return true
	if id.find("loot_crate") >= 0 or id.find("lootcrate") >= 0:
		return true
	if id.find("crate") >= 0 and id.find("explosive") < 0:
		return true
	return false


func _finale_ring_radius(pos, bosses, projectiles) -> Vector2:
	# Unit direction toward or away from the boss to hold the band where the agent
	# can OUT-ROTATE the projectile ring. Zero inside the deadband, and zero when
	# there is no ring in the state (this only makes sense against the ring).
	#
	# Requires finale_pivot_projectiles, same as co-rotation: without the ring in
	# the state there is nothing to outrun and the term is inert.
	if bosses.empty():
		return Vector2.ZERO
	var has_ring = false
	for p in projectiles:
		if str(p.get("type_id", "")).find("rotating") >= 0:
			has_ring = true
			break
	if not has_ring:
		return Vector2.ZERO
	var boss = bosses[0]
	var bpos = Vector2(float(boss.get("x", 0.0)), float(boss.get("y", 0.0)))
	var radial = pos - bpos
	var dist = radial.length()
	if dist < 1.0:
		return Vector2.ZERO
	var target = BotConfig.BOSS_FINALE_RING_RADIUS_TARGET
	var band = BotConfig.BOSS_FINALE_RING_RADIUS_BAND
	if dist > target + band:
		return _normalize(bpos - pos)
	if dist < target - band:
		return _normalize(radial)
	return Vector2.ZERO


func _finale_co_rotate(pos, bosses, projectiles) -> Vector2:
	# Unit tangent around the nearest boss, pointing the SAME way its orbiting
	# projectile ring is turning. Zero when there is no boss, no ring in the
	# state, or the ring is between reversals.
	#
	# Measured 2026-07-27 over 10,287 orbiter samples: the ring is coherent (all
	# nine share a rotation sign in 97.1% of captures) and holds a direction for
	# a median 3.2-9.7 s, but it REVERSES -- 51.9% clockwise / 48.1% counter
	# overall. So the direction is read from the state every decision and never
	# hard-coded.
	if bosses.empty():
		return Vector2.ZERO
	var boss = bosses[0]
	var bpos = Vector2(float(boss.get("x", 0.0)), float(boss.get("y", 0.0)))
	# Mean angular velocity of the ring about the boss. Averaged rather than
	# taken from one projectile so a single mis-sampled orbiter cannot flip it.
	var spin = 0.0
	var n = 0
	for p in projectiles:
		if str(p.get("type_id", "")).find("rotating") < 0:
			continue
		var r = Vector2(float(p.get("x", 0.0)), float(p.get("y", 0.0))) - bpos
		var rl = r.length()
		if rl < 1.0:
			continue
		var v = Vector2(float(p.get("vx", 0.0)), float(p.get("vy", 0.0)))
		spin += (r.x * v.y - r.y * v.x) / (rl * rl)
		n += 1
	if n == 0:
		return Vector2.ZERO
	var omega = spin / float(n)
	if abs(omega) < BotConfig.BOSS_FINALE_CO_ROTATE_MIN_OMEGA:
		return Vector2.ZERO
	var radial = pos - bpos
	if radial.length() < 1.0:
		return Vector2.ZERO
	# cross(radial, tangent) is positive for this tangent, so flip it when the
	# ring turns the other way.
	var tangent = _normalize(Vector2(-radial.y, radial.x))
	if omega < 0.0:
		tangent = -tangent
	return tangent


func _finale_range_keep(pos, bosses, weapons) -> Vector2:
	# Wave-20 range keeping: unit direction toward the nearest boss when it has
	# drifted outside shortest_range * BOSS_FINALE_RANGE_KEEP_FRACTION, else zero.
	# Never pushes AWAY, and never pulls while already inside the band.
	if bosses.empty():
		return Vector2.ZERO
	var shortest = _shortest_weapon_range(weapons)
	if shortest <= 0.0:
		return Vector2.ZERO
	var best_dist = -1.0
	var best_diff = Vector2.ZERO
	for b in bosses:
		var bp = Vector2(b.get("x", 0.0), b.get("y", 0.0))
		var diff = bp - pos
		var dist = diff.length()
		if best_dist < 0.0 or dist < best_dist:
			best_dist = dist
			best_diff = diff
	if best_dist < 0.0:
		return Vector2.ZERO
	if best_dist <= shortest * BotConfig.BOSS_FINALE_RANGE_KEEP_FRACTION:
		return Vector2.ZERO
	return _normalize(best_diff)


func _finale_heal_seek(pos, consumables, player) -> Vector2:
	# Wave-20 heal seeking: unit direction to the nearest ordinary heal, else zero.
	# Deliberately NOT _consumable_attraction: that function is gated by farming
	# heuristics (EARLY_LOOT_WAVE, greed multipliers, pack-density gates, a safety
	# term that shrinks the force as threats close in), so its behaviour depends on
	# constants unrelated to this experiment. This is a single directly tunable knob.
	if consumables.empty():
		return Vector2.ZERO
	var hp = float(player.get("hp", 1))
	var max_hp = max(float(player.get("max_hp", 1)), 1.0)
	if hp / max_hp >= BotConfig.BOSS_FINALE_HEAL_SEEK_HP_RATIO:
		return Vector2.ZERO
	var best_dist = -1.0
	var best_diff = Vector2.ZERO
	for c in consumables:
		var cid = str(c.get("id", ""))
		if _is_valuable_pickup(cid):
			continue
		if cid.to_lower().find("item_box") >= 0:
			continue
		var cp = Vector2(c.get("x", 0.0), c.get("y", 0.0))
		var diff = cp - pos
		var dist = diff.length()
		if best_dist < 0.0 or dist < best_dist:
			best_dist = dist
			best_diff = diff
	if best_dist < 0.0:
		return Vector2.ZERO
	if best_dist > BotConfig.BOSS_FINALE_HEAL_SEEK_MAX_DIST:
		return Vector2.ZERO
	return _normalize(best_diff)


func _consumable_attraction(pos, consumables, player, enemies, bosses, wave = 1) -> Vector2:
	if consumables.empty():
		return Vector2.ZERO
	var hp = float(player.get("hp", 1))
	var max_hp = max(float(player.get("max_hp", 1)), 1.0)
	var hp_ratio = hp / max_hp
	# Guide: don't waste heals at full HP (end-of-wave pickup still happens).
	var urgency = max(0.15, 1.0 - hp_ratio)
	if hp_ratio >= 0.92:
		urgency = 0.05
	var threat_dist = _nearest_threat_dist(pos, enemies, bosses)
	var safety = min(1.0, threat_dist / BotConfig.SAFETY_DISTANCE)
	var nearby = _count_nearby_enemies(pos, enemies, bosses)
	var early = wave <= BotConfig.EARLY_LOOT_WAVE
	var sparse = nearby <= BotConfig.SPARSE_LOOT_ENEMIES
	var greed = _loot_greed_mult(wave, nearby)
	var force = Vector2.ZERO
	for c in consumables:
		var cp = Vector2(c.get("x", 0.0), c.get("y", 0.0))
		var diff = cp - pos
		var dist = max(diff.length(), 1.0)
		var cid = str(c.get("id", ""))
		var valuable = _is_valuable_pickup(cid)
		var is_box = valuable or cid.find("item_box") >= 0
		var weight: float
		var local_urgency: float
		var local_safety: float
		if valuable:
			# Upgrade boxes / crates: greed across the whole run unless almost dead-contact.
			if threat_dist < BotConfig.CONTACT_DANGER * BotConfig.VALUABLE_CONTACT_ABORT:
				continue
			weight = BotConfig.ITEM_BOX_ATTRACTION * BotConfig.VALUABLE_LOOT_MULT
			local_urgency = 1.35
			local_safety = max(0.85, safety)
			if early or sparse:
				weight *= max(greed, 1.5)
		else:
			weight = BotConfig.CONSUMABLE_ATTRACTION
			local_urgency = urgency
			local_safety = safety
			if early and sparse and hp_ratio < 0.92:
				local_safety = max(BotConfig.EARLY_LOOT_SAFETY_FLOOR, local_safety)
				weight *= min(greed, 1.8)
			if nearby >= BotConfig.PACK_DENSITY_HARD and not (early and sparse):
				continue
			if nearby >= BotConfig.PACK_DENSITY_SOFT and hp_ratio > 0.45 and not early:
				local_safety *= 0.35
			if hp_ratio >= 0.92 and not early:
				continue
		force += (diff / dist) * weight * local_urgency * local_safety / dist
	return force


# Finale controller v2 (default OFF). Evaluate K candidate headings and pick the
# one that survives longest, saturating at FINALE_V2_HORIZON. Time to collision
# is CLOSED FORM, never sampled: v116 established discrete time sampling as the
# systemic root cause of the v84-103 collapse.
func _finale_v2_heading(pos: Vector2, enemies, bosses, projectiles, arena,
		player_speed: float, prev_dir: Vector2) -> Vector2:
	var headings := int(BotConfig.FINALE_V2_HEADINGS)
	if headings <= 0:
		return Vector2.ZERO
	var threat_list: Array = []
	for projectile in projectiles:
		threat_list.append(projectile)
	for boss in bosses:
		threat_list.append(boss)
	for enemy in enemies:
		threat_list.append(enemy)
	var w := float(arena.get("width", 2048.0))
	var h := float(arena.get("height", 1536.0))
	var horizon := float(BotConfig.FINALE_V2_HORIZON)
	var safe_speed := max(player_speed, 1.0)
	var best_score := -INF
	var best_dir := Vector2.ZERO
	for k in range(headings):
		var angle := (TAU * k) / float(headings)
		var candidate := Vector2(cos(angle), sin(angle))
		var player_vel := candidate * safe_speed
		var t_hit := INF
		for threat in threat_list:
			var threat_pos := Vector2(
				float(threat.get("x", 0.0)), float(threat.get("y", 0.0)))
			var threat_vel := Vector2(
				float(threat.get("vx", 0.0)), float(threat.get("vy", 0.0)))
			var threat_radius := max(float(threat.get("radius", 12.0)), 0.0)
			var rel_pos := pos - threat_pos
			var rel_vel := player_vel - threat_vel
			var c := rel_pos.length_squared() - threat_radius * threat_radius
			if c <= 0.0:
				# Already overlapping this threat. A heading that INCREASES
				# separation is not a future collision, so it must not be
				# scored as one: rel_pos points from threat to player, so
				# rel_pos.dot(rel_vel) > 0 means the gap is opening. Without
				# this branch every heading scores 0 whenever the player is in
				# contact with any enemy -- which in a finale swarm is most of
				# the time -- and heading selection stops discriminating at
				# exactly the moment it matters most.
				if rel_pos.dot(rel_vel) > 0.0:
					continue
				t_hit = 0.0
				continue
			var a := rel_vel.length_squared()
			if a <= 1.0e-9:
				continue
			var b := 2.0 * rel_pos.dot(rel_vel)
			var disc := b * b - 4.0 * a * c
			if disc < 0.0:
				continue
			var root := sqrt(disc)
			var t_first := (-b - root) / (2.0 * a)
			if t_first < 0.0:
				t_first = (-b + root) / (2.0 * a)
			if t_first < 0.0:
				continue
			if t_first < t_hit:
				t_hit = t_first
		var score := min(t_hit, horizon)
		var end_pos := pos + candidate * (safe_speed * horizon)
		var end_margin := min(
			min(end_pos.x, w - end_pos.x), min(end_pos.y, h - end_pos.y))
		if end_margin < BotConfig.BOSS_FINALE_WALL_HARD_MARGIN:
			score -= BotConfig.FINALE_V2_WALL_PENALTY
		if prev_dir != Vector2.ZERO:
			var align := candidate.dot(prev_dir)
			if align > 0.0:
				score += BotConfig.FINALE_V2_HYSTERESIS * align * 0.001
		# Strictly greater: ties resolve to the lowest k, for determinism.
		if score > best_score:
			best_score = score
			best_dir = candidate
	return best_dir
