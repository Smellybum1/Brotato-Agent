extends Node

# Main bot loop. Replaces the Python WebSocket client of the old prototype:
# everything runs in-process so the mod is self-contained (no external deps).
#
# Activated by the robot button on the difficulty screen — sets `active=true`,
# from then on _physics_process drives shop / level-up / crate / movement
# decisions until run end.

const LOG_NAME = "Tom:BrotatoAgent:Runner"

# Activated by difficulty robot button / auto-start benchmark.
var active: bool = false
var auto_start_benchmark: bool = true
# Fixture harness (wave-20 iteration): resume a restored mid-run save instead of
# starting a fresh run. Default false -- flag-off behaviour is byte-identical.
var resume_from_save: bool = false
# Finale controller v2 (wave 20 only). Default false -- flag-off behaviour is
# byte-identical. When true the finale recomputes at 60 Hz while captures stay
# on the ordinary 20 Hz schedule (see reports/wp2/finale_v2_design.md).
var finale_v2: bool = false
# Rate-only finale arm (wave 20 only). Default false -- flag-off behaviour is
# byte-identical. When true the v1 movement policy is untouched but it
# recomputes every physics tick (60 Hz) instead of 1 tick in 3, so the rate
# change is isolated from the policy change v2 bundled with it. Captures stay
# on the ordinary 20 Hz schedule.
var finale_rate_full: bool = false
# Wave-20 dev flag: skip the low-HP panic override inside the v1 finale branch,
# leaving the pure-repulsion desire in place. Default false -- byte-identical.
var finale_no_panic: bool = false
# Wave-20 dev flag: below BOSS_FINALE_HEAL_SEEK_HP_RATIO, steer at the nearest
# ordinary healing consumable. Default false -- byte-identical.
var finale_heal_seek: bool = false
# Wave-20 dev flag: keep the boss inside weapon range instead of drifting out.
# Default false -- byte-identical.
var finale_range_keep: bool = false
# Dev flag: boss-projectile dodging gets the FINAL word in the wave-20 safety
# tail (projectile safety deferred to after body safety).
var finale_projectile_priority: bool = false
# DIAGNOSTIC ONLY, default false. Walks the live scene tree on wave 20 and emits
# every damage-carrying node with its PARENT PATH and `visible` flag, alongside
# the instance ids the controller actually collected on the same tick. Read-only:
# it reads the tree and emits telemetry, it changes no decision and no state.
# Exists because 84-91% of wave-20 predator damage has no cause in the captured
# state (invoker control: 0%), and the two candidate mechanisms -- wrong parent
# node vs. the `if not proj.visible: continue` filter -- are indistinguishable
# from existing telemetry.
var finale_scene_dump: bool = false
var _scene_dump_tick: int = 0
var _scene_dump_visited: int = 0
# THE FIX the scene dump motivates. Collects boss-MOUNTED projectiles -- nine
# `enemy_projectile_rotating.gd` nodes parented under `Boss/Pivot`, which the
# `Projectiles`/`%EnemyProjectiles` lookup can never reach -- into the same
# projectile list, so the existing avoidance machinery can act on them.
# Default FALSE: this CHANGES BEHAVIOUR (it changes what the potential field
# sees), so flag-off must stay byte-identical for the baseline to hold.
# The emitted dicts carry EXACTLY the existing projectile key set, so the
# capture schema hash does not move and the collector gate still passes.
# DEFAULT-ON since the qualification campaign (0.2.49). Pre-registered protocol
# reports/wp2/pivot_fix_qualification_protocol.md, 64 paired trials on 8 fixtures:
# victory rate 22/32 = 0.688 without the fix vs 32/32 = 1.000 with it, one-sided
# Fisher p = 0.000426, damage median 64 -> 20. The control arm came in at 0.688,
# right on its historical 0.651/0.703, so the baseline was not confounded.
# Structural gate: 0 rotating projectiles in 245,057 control observations vs
# 326,151 in the treatment -- the arms could not have been confused.
var finale_pivot_projectiles: bool = true
# Wave-20 dev flag: strafe around the boss in the same direction its projectile
# ring is rotating. DEPENDS ON finale_pivot_projectiles -- without it the ring is
# not in the state and this term is inert (a no-op, not an error).
var finale_co_rotate: bool = false
# Wave-20 dev flag: hold the radius band where the agent can out-rotate the ring
# (~300 u). Also depends on finale_pivot_projectiles, and pairs with
# finale_co_rotate -- direction without radius cannot outrun anything.
var finale_ring_radius: bool = false
# Dev knob (float, not a bool): multiply the engagement standoff distance the
# field holds from enemies. Pure multiplier applied after the shipped DPS scale,
# so the default 1.0 is exactly inert.
var engage_distance_scale: float = 1.0
# Dev knob: threat weight applied to enemies that are NOT currently charging.
# 1.0 (default) is exactly inert.
var calm_threat_mult: float = 1.0
# Dev knob: scale the safety tail's avoid/critical clearance thresholds for
# enemies that are NOT currently charging. 1.0 (default) is exactly inert.
var tail_calm_penalty_mult: float = 1.0
# Dev knob: clearance credit for non-charging enemies inside the safety tail's
# predictive body-clearance test. 1.0 (default) makes the credit exactly 0.0.
var tail_calm_clearance_mult: float = 1.0
# SHOP dev flag (not a movement knob): replace the rare-gun lock's one-visit
# lifetime with a reachability test (shortfall inside a band, or a shortfall that
# strictly decreased since the previous visit), capped at
# BotConfig.RARE_GUN_LOCK_MAX_VISITS so a locked slot can never persist for a
# whole run. Default false -- byte-identical to the shipped lifetime.
var rare_gun_lock_persist: bool = false
# Dev instrument, NOT a policy flag: hand MOVEMENT ONLY to a human at the keyboard
# while the agent keeps shop, level-up and telemetry control. Measures movement
# headroom on a build the agent itself produced, which no uptime proxy can do --
# the wave-17 uptime analysis refuted only the "enemies kept out of weapon range"
# mechanism and never measured movement EXECUTION at all.
#
# Distinct from the pre-existing E-stop: any human input normally sets active=false
# and disables the agent for the whole run (player_movement_behavior.gd), which
# would hand over shopping too and confound the comparison. This flag suppresses
# that takeover so ONLY the movement vector changes hands.
#
# Inert when false: the seam returns runner.current_move_vector exactly as before.
var human_movement: bool = false
# ── movement E-stop gate (default ON = today's behaviour) ─────────────────────
# The E-stop in player_movement_behavior.gd fires on ANY movement input > 0.05.
# Movement binds Q/A/W/Z/S/D plus the arrows, so while the game window holds
# focus, ordinary typing ends the run -- it cost 2 of 12 attempts of the D5
# baseline on 2026-07-30. Set false for UNATTENDED campaigns so a stray keystroke
# cannot destroy hours of collection. Ctrl+Shift+Q still stops the agent and is
# deliberately NOT gated by this flag.
#
# Defaults TRUE so interactive use and every existing campaign are unchanged, and
# so a config that never arrives leaves the safety mechanism in place.
var movement_estop_enabled: bool = true
# -1 = the movement seam never evaluated the gate this run (a real defect -- the
# extension did not load, or combat never ran). 0 = evaluated, no input seen.
# >0 = input seen and SUPPRESSED while the run continued. Defaults to -1 so
# "never written" cannot masquerade as a measured zero.
var movement_estop_suppressed: int = -1
# ── human input label (only meaningful when human_movement is true) ───────────
# During a handover run `teacher.action` is the AGENT's intended vector, not what
# the human did, so a behaviour-cloning label had to be reconstructed from
# player.measured_vx/vy -- a displacement derivative that blows up at low dt and
# is 8-way quantized. These three fields carry the RAW keyboard vector instead,
# fed by player_movement_behavior.gd via note_human_movement().
#
# get_movement() runs at physics rate (~60 Hz) and captures are ~20 Hz, so a
# capture samples only the LATEST of ~3 inputs. `samples` and `all_identical`
# exist so a consumer can tell "the human held one direction" from "we aliased
# away two of three inputs" -- without them the label cannot be checked for
# aliasing and is not trustworthy. Reset once per CAPTURE (not per recompute:
# choose_movement runs every physics tick, which would pin samples at 1).
var _human_move_latest: Vector2 = Vector2.ZERO
var _human_move_samples: int = 0
var _human_move_all_identical: bool = true
# Previous-tick world positions, keyed by instance id, for finite-difference
# velocity. These nodes DO expose `velocity` and it reads 0 -- their motion
# comes from the parent Pivot's rotation, so reading the property would model
# them as parked. Rebuilt every tick, so it cannot grow without bound.
var _pivot_prev: Dictionary = {}
var _pivot_cur: Dictionary = {}
# 0.5 s at 60 Hz. The walk is O(tree); this keeps it off the per-tick path.
const SCENE_DUMP_EVERY := 30
# Raised from 400 when unit nodes became candidates: truncation silently caps
# counts, and a wave-20 swarm is the case where it would bite.
const SCENE_DUMP_MAX_NODES := 800
const SCENE_DUMP_MAX_DEPTH := 14
# Boss -> Pivot -> projectile is 2 levels; 3 leaves one level of headroom without
# turning this into a whole-subtree scan on every physics tick.
const PIVOT_SCAN_DEPTH := 3
# Wall-clock accelerator for EVALUATION campaigns. Godot scales physics ticks
# with Engine.time_scale, so the agent still receives its 60 ticks per GAME
# second and its behaviour is unchanged -- only real time shrinks, provided the
# machine can compute the extra ticks.
#
# DEFAULT 1.0, and it must stay 1.0 for DATASET COLLECTION: `control_dt_ms` is
# measured in REAL time (now_ms - last_capture_ts_ms) and is a student model
# input, so captures taken at 2.0 would carry ~25 ms where the 20 Hz dataset
# carries ~51 ms. The value is written into the run summary so any dataset
# collected at != 1.0 is identifiable after the fact rather than silently wrong.
var time_scale: float = 1.0
const TIME_SCALE_MAX := 16.0
# Skip rendering entirely while accelerating. This is as close to headless as a
# shipped Godot client gets without re-exporting from source, which is not
# available: the only decompile on hand is a DIFFERENT, older build. Only worth
# enabling if the machine turns out to be render-bound -- at 4.0x it was not.
var headless_render: bool = false
var _resume_done: bool = false
var _resume_ticks: int = 0
# ~10 s at 60 Hz. ProgressData populates current_run_state during startup, so the
# first MAIN_MENU tick can arrive before the save is loaded.
const RESUME_MAX_TICKS := 600
var current_move_vector: Vector2 = Vector2.ZERO
var policy_version: String = "teacher_v1-0.1.129-gun-wp1"
# Single source of truth for the deployed mod identity: stamped into every run's
# meta AND into the mod-ready sentinel, so the collector cannot accept a build
# whose identity disagrees with what it asked for.
const MOD_VERSION := "0.2.61-wp2-capture"
const _MOD_READY_PATH := "user://brotato_agent/mod_ready.json"
var last_move_debug: Dictionary = {}
var last_meta_debug: Dictionary = {}
var _manual_override: bool = false
var _run_started: bool = false
var _last_hp: float = -1.0
var _last_known_max_hp: float = -1.0
var _combat_tick_counter: int = 0
# v123: smoothed build strength S = EMA of clamp(weapon_dps / dps_target, 0, 2).
# Default 1.0 (neutral) until the first build-metrics update (wave 1 pre-shop).
var _build_strength: float = 1.0
var _wp2_capture_seq: int = 0
var _wp2_previous_action: Vector2 = Vector2.ZERO
var _wp2_last_capture_player_pos: Vector2 = Vector2.ZERO
var _wp2_last_capture_ts_ms: int = -1
var _density_wave: int = -1
var _density_enemy_samples := []
var _last_wave_p90_density := 0.0
var _last_wave_peak_density := 0.0
var _batch_wins: int = 0
var _batch_runs: int = 0
const _BATCH_STATS_PATH := "user://brotato_agent/batch_hud.json"
const _WP2_CAPTURE_SCHEMA_VERSION := "2.0.0"
const _WP2_CAPTURE_SCHEMA_ID := "combat_capture_v2"
const _WP2_CAPTURE_SCHEMA_HASH := "2823CB7E7D6A6DDB7F805A76D0CD674BA7A2A908058771B66B4A8FEFF9BC1174"
const _WP2_CAPTURE_DIVISOR := 3 # 60 Hz physics / 3 = 20 capture decisions per second.
# Capture-side capacity limits, per entity group. 0 means unlimited, which is the
# shipped setting for every group: the capture deliberately emits untruncated raw
# groups so the stream can be re-encoded at any downstream capacity later (the
# encoder owns the real caps — see configs/wp2/observation_v1.yaml). These exist so
# dropped_counts is *derived* from an actual limit rather than asserted: it reports
# a measured zero while the limits are unlimited, and real counts if one is ever set.
const _WP2_CAPTURE_LIMITS := {
	"enemies": 0, "bosses": 0, "projectiles": 0, "materials": 0,
	"consumables": 0, "crates": 0, "obstacles": 0,
}
# v127: the 50-material ceiling seen in capture analysis is the ENGINE's, not ours.
# Brotato's main.gd holds `const MAX_GOLDS = 50`; past that, a new drop does not
# spawn an entity — a random existing gold absorbs it (`gold_boosted.value +=
# unit.stats.value`). So the material entity COUNT saturates at 50 while the
# material VALUE keeps climbing, which is why every material entity now carries
# `value` (see _collect_loot). Sum `value` for the true pile; the count alone is a
# censored lower bound. Documented here because the mod cannot raise the engine cap
# without changing game behaviour, and must not.
const _WP2_ENGINE_MAX_GOLDS := 50

const _PROFILES_SCRIPT = preload("res://mods-unpacked/Tom-BrotatoAgent/teacher/build_profiles.gd")
const _SHOP_SCRIPT = preload("res://mods-unpacked/Tom-BrotatoAgent/teacher/shop_strategy.gd")
const _CONFIG_SCRIPT = preload("res://mods-unpacked/Tom-BrotatoAgent/teacher/config.gd")
const _COMBAT_MODEL_SCRIPT = preload("res://mods-unpacked/Tom-BrotatoAgent/teacher/combat_model.gd")
const _FIELD_SCRIPT = preload("res://mods-unpacked/Tom-BrotatoAgent/teacher/potential_field.gd")
const _ADAPTER_SCRIPT = preload("res://mods-unpacked/Tom-BrotatoAgent/adapter/game_adapter.gd")
const _ORCH_SCRIPT = preload("res://mods-unpacked/Tom-BrotatoAgent/orchestrator/run_orchestrator.gd")
const _TELEM_SCRIPT = preload("res://mods-unpacked/Tom-BrotatoAgent/telemetry/telemetry_writer.gd")
const _HUD_SCRIPT = preload("res://mods-unpacked/Tom-BrotatoAgent/ui/agent_hud.gd")
# WP2 M3 student-inference path (loaded always, instantiated only when enabled).
const _COMBAT_BRIDGE_SCRIPT = preload("res://mods-unpacked/Tom-BrotatoAgent/learned/combat_bridge.gd")
const _LEARNED_SCRIPT = preload("res://mods-unpacked/Tom-BrotatoAgent/learned/learned_combat_controller.gd")
var _profiles
var _shop
var _field
var _adapter
var _orch
var _telem
var _hud
# Student-inference nodes: null (and inert) unless student_enabled is set in
# agent_config.json. When null the combat path is byte-identical to teacher-only.
var _bridge = null
var _learned = null
var student_enabled: bool = false
var student_port: int = 51888
var student_model_sha256: String = ""

# Action throttle (the game UI doesn't react well to back-to-back inputs).
var _last_shop_action_at: float = 0.0
var _last_shop_action_type: String = ""
var _shop_transition_wave: int = -1
var _shop_transition_item_id: String = ""
var _shop_transition_count: int = 0
var _last_levelup_action_at: float = 0.0
var _last_crate_action_at: float = 0.0
const ACTION_INTERVAL = 0.25
# Shop needs more breathing room — rapid combine/sell chains native-crash Brotato.
const SHOP_ACTION_INTERVAL = 0.55
const SHOP_MUTATE_INTERVAL = 0.75
const SHOP_COMBINE_CONFIRM_INTERVAL = 1.0
const SHOP_COMBINE_CONFIRM_TIMEOUT = 5.0
var _pending_combine_signature: String = ""
var _pending_combine_wave: int = -1
var _pending_combine_at: float = 0.0
var _combine_restore_mouse_mode: int = -1
var _combine_timeout_reported: bool = false
# v126: bounded surplus reroll — one action per board signature. After a surplus
# reroll is dispatched, no further shop action is considered until the board
# signature actually changes (confirmed refresh) or the stale-board timeout
# fires. The ordinary v125 reroll path is untouched.
const SHOP_SURPLUS_CONFIRM_INTERVAL = 0.6
const SHOP_SURPLUS_CONFIRM_TIMEOUT = 4.0
var _pending_surplus_signature: String = ""
var _pending_surplus_wave: int = -1
var _pending_surplus_at: float = 0.0
var _surplus_timeout_reported: bool = false
var _end_run_force_at_ms: int = 0

# Stat names whose live values we need for combat valuation.
const _STAT_NAMES = [
	"max_hp", "armor", "dodge", "speed", "hp_regeneration", "lifesteal",
	"crit_chance", "crit_damage", "attack_speed", "percent_damage", "damage",
	"ranged_damage", "melee_damage", "elemental_damage", "range",
	"harvesting", "engineering", "luck",
]


func _ready() -> void:
	_profiles = _PROFILES_SCRIPT.new()
	_shop = _SHOP_SCRIPT.new()
	_field = _FIELD_SCRIPT.new()
	_adapter = _ADAPTER_SCRIPT.new()
	_orch = _ORCH_SCRIPT.new()
	_telem = _TELEM_SCRIPT.new()
	_hud = _HUD_SCRIPT.new()
	add_child(_hud)
	_load_auto_config()
	# Applied AFTER _load_auto_config so agent_config.json can set it. Clamped:
	# a typo of 40 instead of 4 would outrun the machine, and once the engine
	# cannot keep up the tick budget is missed and behaviour DOES change.
	time_scale = clamp(time_scale, 1.0, TIME_SCALE_MAX)
	Engine.time_scale = time_scale
	# iterations_per_second MUST scale with time_scale, and this was MEASURED,
	# not reasoned. time_scale alone multiplies the delta per tick while ticks
	# keep firing at 60/REAL second, so the agent gets 60/time_scale decisions
	# per GAME second -- at 2.0 the capture rate fell 20 Hz -> 10 Hz and a trial
	# that won at 1.0 lost. Raising ips in proportion restores 60 ticks per game
	# second, so the agent decides exactly as often as before and only wall time
	# shrinks. Validity check for any accelerated run: captures per game-second
	# must still read 20.0.
	Engine.iterations_per_second = int(round(60.0 * time_scale))
	if time_scale > 1.0:
		# Without this, time_scale buys nothing: vsync caps the frame loop at the
		# monitor's refresh, so the engine cannot run the extra physics ticks that
		# time_scale asks for, falls behind, and the tick budget is missed --
		# which DOES change behaviour. Only touched when accelerating, so normal
		# 1.0 runs are unaffected.
		OS.vsync_enabled = false
		Engine.target_fps = 0
	if headless_render:
		# Stop the root viewport drawing at all. The game logic, physics and our
		# controller are untouched; only the render pass is skipped.
		var vp = get_tree().get_root()
		if vp != null:
			vp.render_target_update_mode = Viewport.UPDATE_DISABLED
	if _field != null:
		_field.finale_v2_enabled = finale_v2
		_field.finale_no_panic_enabled = finale_no_panic
		_field.finale_heal_seek_enabled = finale_heal_seek
		_field.finale_range_keep_enabled = finale_range_keep
		_field.finale_projectile_priority_enabled = finale_projectile_priority
		_field.finale_co_rotate_enabled = finale_co_rotate
		_field.finale_ring_radius_enabled = finale_ring_radius
		_field.engage_distance_scale = engage_distance_scale
		_field.calm_threat_mult = calm_threat_mult
		_field.tail_calm_penalty_mult = tail_calm_penalty_mult
		_field.tail_calm_clearance_mult = tail_calm_clearance_mult
	if _shop != null:
		_shop.rare_gun_lock_persist_enabled = rare_gun_lock_persist
	if student_enabled:
		_bridge = _COMBAT_BRIDGE_SCRIPT.new()
		_bridge.name = "CombatBridge"
		add_child(_bridge)
		_learned = _LEARNED_SCRIPT.new()
		_learned.name = "LearnedCombat"
		add_child(_learned)
		_learned.setup(_bridge, _telem, {
			"port": student_port,
			"capture_schema_id": _WP2_CAPTURE_SCHEMA_ID,
			"capture_schema_hash": _WP2_CAPTURE_SCHEMA_HASH,
			"control_hz": 20,
			"expected_model_sha256": student_model_sha256,
		})
		ModLoaderLog.info("Student-inference path enabled (port %d)" % student_port, LOG_NAME)
	_load_batch_stats()
	_refresh_batch_hud()
	_write_mod_ready()
	ModLoaderLog.info("AgentController ready", LOG_NAME)


func _write_mod_ready() -> void:
	# Positive install signal. A GDScript parse error anywhere in the mod stops
	# ModLoader from installing ANY of it, and the game then sits on the title
	# screen — which, from outside, is indistinguishable from a slow start. The
	# v127 deploy lost a build/launch cycle to exactly that, diagnosed only
	# because a human noticed the title screen.
	#
	# The collector deletes this file before launching and requires it to appear,
	# so absence is proof of non-installation and no timestamp trust is needed.
	# Identity is included so a stale or wrong build fails loudly rather than
	# silently collecting under the wrong version.
	var d = Directory.new()
	d.make_dir_recursive("user://brotato_agent")
	var f = File.new()
	if f.open(_MOD_READY_PATH, File.WRITE) != OK:
		ModLoaderLog.info("Could not write mod-ready sentinel", LOG_NAME)
		return
	f.store_string(JSON.print({
		"ready": true,
		"policy_version": policy_version,
		"mod_version": MOD_VERSION,
		"capture_schema_hash": _WP2_CAPTURE_SCHEMA_HASH,
		# Lets a caller assert the finale arm BEFORE spending a trial, rather
		# than discovering from the summary afterwards that the flag was lost.
		"finale_v2": finale_v2,
		"finale_rate_full": finale_rate_full,
		"finale_no_panic": finale_no_panic,
		"finale_heal_seek": finale_heal_seek,
		"finale_range_keep": finale_range_keep,
		"finale_projectile_priority": finale_projectile_priority,
		"finale_scene_dump": finale_scene_dump,
		"finale_pivot_projectiles": finale_pivot_projectiles,
		"finale_co_rotate": finale_co_rotate,
		"finale_ring_radius": finale_ring_radius,
		"engage_distance_scale": engage_distance_scale,
		"calm_threat_mult": calm_threat_mult,
		"tail_calm_penalty_mult": tail_calm_penalty_mult,
		"tail_calm_clearance_mult": tail_calm_clearance_mult,
		"rare_gun_lock_persist": rare_gun_lock_persist,
		"human_movement": human_movement,
		# Gate state only -- DELIVERY, not correctness. Proof that suppression
		# actually happened is the movement_estop_suppressed event/counter.
		"movement_estop_enabled": movement_estop_enabled,
		"time_scale": time_scale,
	}))
	f.close()


func _try_resume_saved_run() -> bool:
	# Wave-20 fixture harness. Restoring a snapshot of run_v3_0.json and launching
	# would otherwise start a NEW run and overwrite the very save being restored.
	#
	# Clicks the game's own ContinueButton rather than calling
	# RunData.resume_from_state directly. Reading ProgressData.get("current_run_state")
	# was tried first and always returned TYPE_NIL, and going through the real button
	# is more robust anyway: main_menu.gd only shows/focuses ContinueButton when
	# has_run_state is true, so the button's VISIBILITY is the run-state check, and
	# its handler does the resume with whatever internal bookkeeping the live build
	# expects. Resume lands in the SHOP of the saved wave, so a wave-19 fixture shops
	# and then plays wave 20.
	if not resume_from_save:
		return false
	if _orch == null:
		return false
	var scene = get_tree().current_scene
	if scene == null:
		return false
	if not _orch._click_named_button(scene, ["ContinueButton"]):
		if _resume_ticks % 120 == 1:
			ModLoaderLog.info("resume_from_save: ContinueButton not clickable yet", LOG_NAME)
		return false
	# Resuming bypasses the normal danger-select path, so the agent never gets
	# switched on and would sit idle in the restored shop (observed: save parked at
	# wave 19 for 114 s with no telemetry). Activate explicitly; on_benchmark_activated
	# calls _start_run(), so the resumed session gets its own telemetry run covering
	# the wave-19 shop and wave 20.
	var danger = 0
	if _orch != null:
		danger = int(_orch.target_danger)
	on_benchmark_activated(danger)
	ModLoaderLog.info("resume_from_save: clicked ContinueButton and activated agent", LOG_NAME)
	return true


func _student_active() -> bool:
	# Student mode engages only with the flag on, the agent active, and the
	# learned controller instantiated. Never engages while active is false.
	return student_enabled and active and _learned != null


func _physics_process(_delta: float) -> void:
	_check_emergency_stop()
	if _learned != null:
		_learned.poll()
	var scene = get_tree().current_scene
	var detected = _adapter.detect_phase(scene) if _adapter != null else "BOOT"
	if _orch != null:
		_orch.update_phase(detected)
		_orch.enforce_settings()
		_update_hud_phase(detected)
		if detected in ["VICTORY", "DEFEAT"] and _run_started:
			_finish_run(detected)
		# Always drive menus while auto-start is on — including after automation_fault
		# (active=false) so EndRun / title screens still chain the next benchmark.
		if auto_start_benchmark and not _manual_override and not active:
			# Resume BLOCKS menu advance until it succeeds or gives up. Without this the
			# menu driver races ahead, starts a fresh run, and overwrites the very save
			# we are trying to restore (observed 2026-07-26: fixture clobbered to wave 2).
			if resume_from_save and not _resume_done and detected in ["MAIN_MENU", "BOOT"]:
				_resume_ticks += 1
				if _try_resume_saved_run():
					_resume_done = true
					return
				if _resume_ticks < RESUME_MAX_TICKS:
					return
				_resume_done = true
				ModLoaderLog.info("resume_from_save: gave up after %d ticks; starting fresh" % _resume_ticks, LOG_NAME)
			if detected in ["MAIN_MENU", "CHARACTER_SELECT", "STARTING_WEAPON_SELECT", "DANGER_SELECT", "BOOT", "RECOVERY", "VICTORY", "DEFEAT", "TERMINAL_ERROR"]:
				var adv = _orch.try_menu_advance(scene, _adapter)
				if adv.get("acted", false) and _telem != null and _run_started:
					_telem.emit("phase_transition", adv.get("detail", {}))
		# Death banner / killed-by OK panel can stay on Main before EndRun.
		if auto_start_benchmark and not _manual_override and scene is Main:
			if bool(scene.get("_is_run_lost")) or _player_all_dead(scene) or _hp_is_zero(scene):
				if _run_started:
					_finish_run("DEFEAT")
				active = false
				if _dismiss_killed_by_ok(scene):
					pass
				else:
					_force_end_run_screen(scene)
		var wd = _orch.check_watchdogs(active, detected == "COMBAT", current_move_vector.length() > 0.01)
		if wd != "":
			_on_watchdog(wd)
	if not active:
		current_move_vector = Vector2.ZERO
		return
	if scene == null:
		return
	if scene is Main:
		_handle_combat(scene)
		return
	if scene is BaseShop:
		current_move_vector = Vector2.ZERO
		_handle_shop(scene)
		return
	current_move_vector = Vector2.ZERO
	_handle_overlay(scene)


# ───────────────────────────── combat ─────────────────────────────────────────

var _flee_tick := 0
var _finale_move_tick := 0
# Direct verification instrument for the finale rate arms. The ratio
# finale_recompute_ticks / finale_combat_ticks is 1.0 when the finale recomputes
# every tick and ~0.333 on the v1 1-in-3 schedule, so the arm that actually ran
# is proved from the run summary rather than inferred from behaviour.
var finale_combat_ticks: int = 0
var finale_recompute_ticks: int = 0
# Range-keeping instrument. "boss in range 90% of the time" must be read off a
# run, not inferred. Counted on wave-20 combat ticks with a boss present; both
# the shortest and the longest weapon range are reported because with five
# weapons spanning ~458-559 units "in range" is otherwise ambiguous.
# Computed UNCONDITIONALLY at wave 20 (not gated on the flag): they are pure
# observation and affect no decision, so flag-off behaviour stays identical.
var finale_boss_ticks: int = 0
var finale_boss_in_short_range_ticks: int = 0
var finale_boss_in_long_range_ticks: int = 0
func _handle_combat(main) -> void:
	var state = _gather_combat_state(main)
	if state.empty():
		current_move_vector = Vector2.ZERO
		return
	var profile = _profiles.get_profile(state.get("character", ""))
	# Throttle flee strategies (Pacifist sampling / Beast Master orbital /
	# Bull / Wounded pure-repulsion) to 30Hz — matches the inertia the
	# Python prototype had at 20Hz. Without this, two symmetric projectiles
	# whose forces cancel keep the bot frozen on every 60Hz tick. At half
	# rate the prev_move momentum carries the bot through the cancellation.
	if profile.flee_mode:
		_flee_tick += 1
		if _flee_tick % 2 == 0:
			# Skip recompute — leave current_move_vector as-is so PlayerMovement
			# extension keeps applying the last decision.
			_handle_overlay(main)
			return
	var wave := int(state.get("wave", 0))
	var recompute_move := true
	if wave >= _CONFIG_SCRIPT.BOSS_FINALE_WAVE:
		_finale_move_tick += 1
		if finale_v2:
			# v2 recomputes every physics tick (60 Hz); captures stay at 20 Hz.
			recompute_move = true
		elif finale_rate_full:
			# Rate-only arm: same v1 policy, recomputed every physics tick.
			# BOSS_FINALE_RECOMPUTE_DIVISOR is left at 3 and simply bypassed.
			recompute_move = true
		else:
			recompute_move = (_finale_move_tick % _CONFIG_SCRIPT.BOSS_FINALE_RECOMPUTE_DIVISOR) == 1
		finale_combat_ticks += 1
		if recompute_move:
			finale_recompute_ticks += 1
		_record_finale_range_sample(state)
		if finale_scene_dump and _telem != null:
			_scene_dump_tick += 1
			if _scene_dump_tick % SCENE_DUMP_EVERY == 1:
				_emit_scene_dump(main, state, wave)
	else:
		_finale_move_tick = 0
	if recompute_move:
		var mv = choose_movement(state)
		current_move_vector = mv.get("vector", Vector2.ZERO)
		last_move_debug = mv
	if _orch != null and current_move_vector.length() > 0.01:
		_orch.note_move()
	_combat_tick_counter += 1
	# v117: on finale waves, decisions recompute on _finale_move_tick's phase
	# while captures used _combat_tick_counter's. Whether wave-20 captures
	# landed on recompute ticks depended on the counter phase at wave entry:
	# the v115 smoke drew the aligned phase (all fresh), the v116 smoke drew
	# an offset (0/496 fresh) and every fresh-gated audit silently skipped
	# the death sequence. Emit finale captures on the recompute tick itself.
	var emit_capture := _combat_tick_counter % _WP2_CAPTURE_DIVISOR == 0
	# The v1 alignment override must NOT apply on the v2 path: v2 recomputes on
	# every tick, so this would move captures to 60 Hz and change control_dt_ms
	# from ~50 ms to ~16 ms under a dataset and student path fixed at 20 Hz.
	# The same applies to the rate-only arm, which also recomputes every tick;
	# and the alignment the override buys is automatic when every tick is a
	# recompute tick, so excluding both arms loses nothing.
	if wave >= _CONFIG_SCRIPT.BOSS_FINALE_WAVE and not finale_v2 and not finale_rate_full:
		emit_capture = recompute_move
	if _student_active():
		# Prev-action is the resolved applied vector of the finished period
		# (note §2.4); set it before emit so the payload picks it up. Then send
		# the fresh teacher vector + payload to the learned controller and apply
		# its override (held → student → teacher) to current_move_vector.
		if emit_capture:
			_wp2_previous_action = _learned.get_resolved_applied_vector()
			var _student_payload = _emit_wp2_combat_capture(main, state, recompute_move)
			if _student_payload != null:
				_learned.on_capture(_student_payload, current_move_vector, wave)
		if _learned.has_override():
			current_move_vector = _learned.get_override_vector()
	elif emit_capture:
		_emit_wp2_combat_capture(main, state, recompute_move)
	if _combat_tick_counter % 30 == 0:
		_record_density_sample(int(state.get("wave", 0)), state.get("enemies", []).size())
		var live_max_hp := float(state.get("player", {}).get("max_hp", -1))
		if live_max_hp > 0.0:
			_last_known_max_hp = live_max_hp
		var current_build := _build_dict()
		var build_metrics := _build_metrics(
			current_build.get("stats", {}), current_build.get("weapons", []),
			int(state.get("wave", 0)), _last_known_max_hp)
		# v123: update the smoothed build-strength signal from this build's
		# weapon DPS vs the winner-median target BEFORE the HUD/telemetry consume
		# build_metrics. tau ~1.7-2.0 s at the 0.5 s (30-tick) cadence.
		var strength_offense: Dictionary = build_metrics.get("offense", {})
		var strength_raw := clamp(
			float(strength_offense.get("weapon_dps", 0.0))
				/ max(float(strength_offense.get("dps_target", 1.0)), 1.0),
			0.0, 2.0)
		_build_strength = _build_strength * 0.75 + strength_raw * 0.25
		_update_build_metrics_hud(build_metrics)
		# AUTHORITATIVE difficulty readback, latched on the first combat tick.
		# It cannot be taken at _start_run(): on_benchmark_activated() starts the
		# run BEFORE difficulty_selection presses the difficulty element, so an
		# early read returns the pre-selection value and reports a false mismatch.
		# Observed once in the first Danger 5 smoke: the event said
		# observed_danger 0 while the save already said current_difficulty 5.
		if not _danger_latched and _telem != null:
			_danger_latched = true
			_danger_observed_latched = observed_danger()
			_telem.emit("difficulty_readback", difficulty_readback())
		if _telem != null:
			_telem.emit("combat_tick", {
				"wave": state.get("wave", 0),
				"move": {"x": current_move_vector.x, "y": current_move_vector.y},
				"debug": last_move_debug.get("debug", {}),
				"hp": state.get("player", {}).get("hp", 0),
				"player": state.get("player", {}),
				"bosses": state.get("bosses", []),
				"loot": state.get("loot", []).size(),
				"consumables": state.get("consumables", []).size(),
				"build_metrics": build_metrics,
			})
	_track_damage(state)
	if _hud != null:
		_hud.set_status("move", "(%.2f, %.2f)" % [current_move_vector.x, current_move_vector.y])
		_hud.set_status("build", profile.name if profile != null else "")
		_hud.set_status("hp", str(int(state.get("player", {}).get("hp", 0))) + "/" + str(int(state.get("player", {}).get("max_hp", 0))))
		_hud.set_status("enemies", str(state.get("enemies", []).size()))
		_hud.set_status("bosses", str(state.get("bosses", []).size()))
		_hud.set_status("loot", str(state.get("loot", []).size()))
		_hud.set_status("consumables", str(state.get("consumables", []).size()))
		if int(state.get("wave", 0)) >= 20:
			_hud.set_status("mode", "BOSS FINALE")
		else:
			_hud.set_status("mode", "normal")
		_refresh_batch_hud()
	# Drive overlays that can fire mid-wave (level-up / crate).
	_handle_overlay(main)


func _gather_combat_state(main) -> Dictionary:
	var state = {
		"phase": "combat",
		"wave": RunData.current_wave,
		"character": _character_id(),
		"observation_ts_ms": OS.get_ticks_msec(),
		"invalid_entities": {
			"players": 0, "enemies": 0, "bosses": 0, "projectiles": 0,
			"materials": 0, "consumables": 0, "obstacles": 0,
		},
	}
	var es = main.get_node_or_null("EntitySpawner")
	if es == null: return state

	# Player
	var players = []
	for p in es._players:
		if not is_instance_valid(p):
			state["invalid_entities"]["players"] += 1
			continue
		if p.dead: continue
		var player_velocity := Vector2.ZERO
		if p.has_method("get_next_velocity"):
			player_velocity = p.get_next_velocity()
		players.append({
			"x": p.global_position.x,
			"y": p.global_position.y,
			"vx": player_velocity.x,
			"vy": player_velocity.y,
			"hp": p.current_stats.health,
			"max_hp": p.max_stats.health,
			"hp_ratio": float(p.current_stats.health) / max(float(p.max_stats.health), 1.0),
			"speed": p.max_stats.speed,
			"armor": p.current_stats.armor,
			"dodge": p.current_stats.dodge,
			"hp_regeneration": float(Utils.get_stat(Keys.generate_hash("stat_hp_regeneration"), 0)),
			"lifesteal": float(Utils.get_stat(Keys.generate_hash("stat_lifesteal"), 0)),
		})
	state["players"] = players
	if not players.empty(): state["player"] = players[0]

	# Enemies / bosses
	var enemies = []
	for e in es.enemies:
		if not is_instance_valid(e):
			state["invalid_entities"]["enemies"] += 1
			continue
		if e.dead: continue
		enemies.append(_combat_unit_snapshot(e, "enemy"))
	state["enemies"] = enemies

	var bosses = []
	for b in es.bosses:
		if not is_instance_valid(b):
			state["invalid_entities"]["bosses"] += 1
			continue
		if b.dead: continue
		bosses.append(_combat_unit_snapshot(b, "boss"))
	state["bosses"] = bosses

	# Projectiles (vanilla Main uses $Projectiles; older bots looked for %EnemyProjectiles)
	var projs = []
	var projs_node = main.get_node_or_null("Projectiles")
	if projs_node == null:
		projs_node = main.get_node_or_null("%EnemyProjectiles")
	if projs_node:
		for proj in projs_node.get_children():
			if not is_instance_valid(proj):
				state["invalid_entities"]["projectiles"] += 1
				continue
			if not proj.visible: continue
			if not ("global_position" in proj): continue
			var vel = Vector2.ZERO
			if "velocity" in proj:
				vel = proj.velocity
			projs.append({"x": proj.global_position.x, "y": proj.global_position.y,
				"vx": vel.x, "vy": vel.y,
				"instance_id": proj.get_instance_id(),
				"type_id": _node_script_path(proj),
				"radius": _collision_radius(proj, 8.0),
				"damage": proj.get_damage() if proj.has_method("get_damage") else 0})
	# Boss-mounted projectiles. Flag-gated: with the flag off nothing is appended
	# and `projs` is byte-identical to before.
	if finale_pivot_projectiles:
		_pivot_cur = {}
		for b in es.bosses:
			if not is_instance_valid(b):
				continue
			if b.dead:
				continue
			_collect_mounted_projectiles(b, PIVOT_SCAN_DEPTH, projs)
		_pivot_prev = _pivot_cur
	state["projectiles"] = projs

	# Materials / gold — Main keeps the live list in `_golds` under `$Items`
	state["loot"] = _collect_loot(main)

	# Consumables: fruits + item boxes (upgrades on the ground)
	state["consumables"] = _collect_consumables(main)

	# Neutrals (trees) — chase early for crates/materials.
	state["trees"] = _collect_trees(es)

	# Weapons — prefer live current_stats (includes stat_range from items).
	state["weapons"] = _collect_live_weapons(es)

	# Stand-still check input for Soldier
	state["can_attack_while_moving"] = RunData.get_player_effect(Keys.can_attack_while_moving_hash, 0) > 0

	# v123: strength-conditioned aggression. Consume the PREVIOUS 0.5 s smoothed
	# value (the %30 block updates _build_strength after choose_movement); the
	# one-update staleness is intentional and simpler.
	state["build_strength"] = _build_strength

	# Arena
	var zone_data = _get_current_zone_data()
	if zone_data:
		state["arena"] = {"width": zone_data.width * 64, "height": zone_data.height * 64}
	else:
		state["arena"] = {"width": 2048, "height": 1536}
	_normalize_combat_relative(state)
	return state


func _combat_unit_snapshot(unit, category: String) -> Dictionary:
	var velocity := Vector2.ZERO
	if unit.has_method("get_next_velocity"):
		velocity = unit.get_next_velocity()
	var hp := float(unit.current_stats.health)
	var max_hp := max(float(unit.max_stats.health), 1.0)
	var stats_path := ""
	if unit.stats != null and "resource_path" in unit.stats:
		stats_path = str(unit.stats.resource_path)
	var attack_path := ""
	if "_current_attack_behavior" in unit and unit._current_attack_behavior != null:
		attack_path = _node_script_path(unit._current_attack_behavior)
	return {
		"x": unit.global_position.x, "y": unit.global_position.y,
		"vx": velocity.x, "vy": velocity.y,
		"hp": hp, "max_hp": max_hp, "health_ratio": hp / max_hp,
		"speed": unit.current_stats.speed,
		"armor": unit.current_stats.armor,
		"instance_id": unit.get_instance_id(),
		"name": str(unit.name),
		"category": category,
		"type_id": stats_path,
		"script_path": _node_script_path(unit),
		"attack_path": attack_path,
		"radius": _collision_radius(unit, 24.0),
		"is_boosted": bool(unit.is_boosted) if "is_boosted" in unit else false,
	}


func _node_script_path(node) -> String:
	if node == null:
		return ""
	var script = node.get_script()
	if script != null and "resource_path" in script:
		return str(script.resource_path)
	return ""


# Walks a boss subtree for projectile-scripted nodes. Bounded depth, and it does
# NOT descend into a projectile's own children (its hitbox is not a projectile).
# Deliberately matches on the SCRIPT rather than a node named "Pivot": the name
# is a property of one boss scene, the script is what makes it a projectile.
func _collect_mounted_projectiles(node: Node, depth: int, out: Array) -> void:
	if node == null or depth < 0:
		return
	for c in node.get_children():
		if not is_instance_valid(c):
			continue
		if _node_script_path(c).to_lower().find("projectile") >= 0:
			# Same filters the ordinary projectile path applies, so the two
			# sources cannot disagree about what counts as collectable.
			if not c.visible:
				continue
			if not ("global_position" in c):
				continue
			out.append(_mounted_projectile_snapshot(c))
			continue
		_collect_mounted_projectiles(c, depth - 1, out)


# Key set is EXACTLY the ordinary projectile dict's. Any extra key here would
# move the capture schema hash and fail the collector's identity gate.
func _mounted_projectile_snapshot(proj) -> Dictionary:
	var iid = proj.get_instance_id()
	var pos = proj.global_position
	# GAME-time delta, not real time. This is called exactly once per physics
	# tick, so the elapsed GAME time between calls is always
	# time_scale / iterations_per_second -- 1/60 s, whatever the acceleration.
	#
	# It previously used OS.get_ticks_msec() and that was WRONG under time_scale:
	# real time between ticks shrinks while positions advance by the game delta,
	# so derived speeds inflated with the acceleration (measured: median 864 u/s
	# at 1.0x, 1730 at 2.0x, 6000 at 4.0x, while the engine-authored burst
	# projectiles held exactly 500 at every scale). Real time also quantises
	# badly -- at 4.0x a tick is ~4.17 ms against a 1 ms clock.
	var game_dt := 1.0 / 60.0
	if Engine.iterations_per_second > 0:
		game_dt = Engine.time_scale / float(Engine.iterations_per_second)
	var vel := Vector2.ZERO
	if _pivot_prev.has(iid) and game_dt > 0.0:
		var prev = _pivot_prev[iid]
		vel = Vector2((pos.x - prev[0]) / game_dt, (pos.y - prev[1]) / game_dt)
	_pivot_cur[iid] = [pos.x, pos.y]
	return {"x": pos.x, "y": pos.y,
		"vx": vel.x, "vy": vel.y,
		"instance_id": iid,
		"type_id": _node_script_path(proj),
		"radius": _collision_radius(proj, 8.0),
		"damage": proj.get_damage() if proj.has_method("get_damage") else 0}


# DIAGNOSTIC ONLY. Recursive, depth- and count-bounded, mirrors the shape of
# _collect_buttons. Builds the parent path on the way DOWN rather than calling
# get_parent(), which has no precedent in this mod.
func _scene_dump_walk(node: Node, path: String, depth: int, out: Array) -> void:
	if node == null or depth < 0:
		return
	if out.size() >= SCENE_DUMP_MAX_NODES:
		return
	_scene_dump_visited += 1
	var script_path := _node_script_path(node)
	var lname := str(node.name).to_lower()
	# Broad on purpose: the source is unidentified, so match anything that can
	# deal damage or is named/scripted like a projectile or a hitbox.
	# has_method() is a pure query and calls nothing. Whether get_damage() is
	# actually INVOKED is decided separately below.
	var is_candidate := node.has_method("get_damage")
	var lscript := script_path.to_lower()
	var is_projectile_like := lscript.find("projectile") >= 0
	# Unit nodes are candidates in their OWN right, so an enemy's instance id can
	# be compared against the collected enemy list directly. Reading it off a
	# hitbox CHILD would compare the hitbox's id, which is never in any state.
	var is_unit_like := lscript.find("entities/units/") >= 0
	if is_projectile_like or is_unit_like:
		is_candidate = true
	if lname.find("projectile") >= 0 or lname.find("hitbox") >= 0:
		is_candidate = true
	if is_candidate:
		# Only CALL get_damage() on projectile-scripted nodes -- exactly the class
		# of object the existing collection path already calls it on. A weapon's
		# get_damage() may roll crit RNG, and calling it would perturb the RNG
		# stream: that would make this diagnostic change behaviour. -1 means
		# "has the method, deliberately not queried".
		# Untyped on purpose: get_damage() may return a float and `:= -1` would
		# infer int, making the assignment a type error at runtime.
		var dmg = -1
		if is_projectile_like and node.has_method("get_damage"):
			dmg = node.get_damage()
		var rec := {
			"path": path,
			"name": str(node.name),
			"script": script_path,
			"iid": node.get_instance_id(),
			"visible": bool(node.visible) if "visible" in node else true,
			"has_gp": ("global_position" in node),
			"has_get_damage": node.has_method("get_damage"),
			"damage": dmg,
			# Collection skips `if e.dead: continue`, so a dead-but-still-in-tree
			# enemy is CORRECTLY absent from the state. Without this field an
			# uncollected enemy row cannot be told apart from a real blind spot.
			"dead": bool(node.dead) if "dead" in node else false,
			"has_dead": ("dead" in node),
		}
		if "global_position" in node:
			rec["x"] = node.global_position.x
			rec["y"] = node.global_position.y
		if "velocity" in node:
			rec["vx"] = node.velocity.x
			rec["vy"] = node.velocity.y
		out.append(rec)
	for c in node.get_children():
		_scene_dump_walk(c, path + "/" + str(c.name), depth - 1, out)


# DIAGNOSTIC ONLY. Emits the live tree's damage-carrying nodes next to the
# instance ids the controller collected on the SAME tick, so "present in the
# scene but absent from the state" is a direct comparison rather than an
# inference. Changes no decision.
func _emit_scene_dump(main, state, wave: int) -> void:
	var found := []
	_scene_dump_visited = 0
	_scene_dump_walk(main, str(main.name), SCENE_DUMP_MAX_DEPTH, found)
	var collected := []
	for pr in state.get("projectiles", []):
		collected.append(pr.get("instance_id", 0))
	# Enemy/boss ids are emitted SEPARATELY. Comparing every candidate against the
	# projectile ids alone made enemy nodes read "not in state" by construction --
	# a vacuous denominator that inflated the first dump's headline.
	var collected_units := []
	for u in state.get("enemies", []):
		collected_units.append(u.get("instance_id", 0))
	for u in state.get("bosses", []):
		collected_units.append(u.get("instance_id", 0))
	var main_children := []
	for c in main.get_children():
		main_children.append(str(c.name))
	_telem.emit("scene_dump", {
		"wave": wave,
		"finale_tick": _finale_move_tick,
		"nodes_visited": _scene_dump_visited,
		"truncated": found.size() >= SCENE_DUMP_MAX_NODES,
		"collected_count": collected.size(),
		"collected_iids": collected,
		"collected_unit_count": collected_units.size(),
		"collected_unit_iids": collected_units,
		"candidates": found,
		"main_children": main_children,
	})


func _collision_radius(node, fallback: float) -> float:
	if node == null:
		return fallback
	var collision = node.get_node_or_null("Collision")
	if collision == null:
		collision = node.get_node_or_null("Hitbox/Collision")
	if collision == null or not ("shape" in collision) or collision.shape == null:
		return fallback
	var radius = collision.shape.get("radius")
	if radius != null:
		return max(float(radius), 0.0)
	var extents = collision.shape.get("extents")
	if typeof(extents) == TYPE_VECTOR2:
		return max(float(extents.x), float(extents.y))
	return fallback


func _emit_wp2_combat_capture(main, state: Dictionary, teacher_action_fresh: bool):
	# Returns the emitted capture payload dict (or null on early-out) so the
	# student path can forward it over the wire without rebuilding it.
	if _telem == null or not _telem.has_method("emit_versioned"):
		return null
	var player: Dictionary = state.get("player", {})
	if player.empty():
		return null
	var now_ms := OS.get_ticks_msec()
	var player_pos := Vector2(float(player.get("x", 0.0)), float(player.get("y", 0.0)))
	var measured_velocity := Vector2(float(player.get("vx", 0.0)), float(player.get("vy", 0.0)))
	var control_dt_ms := 0
	if _wp2_last_capture_ts_ms >= 0:
		control_dt_ms = max(now_ms - _wp2_last_capture_ts_ms, 0)
		if control_dt_ms > 0:
			measured_velocity = (player_pos - _wp2_last_capture_player_pos) * (1000.0 / float(control_dt_ms))
	var timer = _wave_timer_snapshot(main)
	var consumables := []
	var crates := []
	for item in state.get("consumables", []):
		if _is_crate_id(str(item.get("id", ""))):
			crates.append(item)
		else:
			consumables.append(item)
	_wp2_capture_seq += 1
	var raw_groups := {
		"enemies": state.get("enemies", []),
		"bosses": state.get("bosses", []),
		"projectiles": state.get("projectiles", []),
		"materials": state.get("loot", []),
		"consumables": consumables,
		"crates": crates,
		"obstacles": state.get("trees", []),
	}
	var entities := {}
	var dropped_counts := {}
	for group in raw_groups:
		entities[group] = _wp2_apply_capture_limit(raw_groups[group], group)
		dropped_counts[group] = raw_groups[group].size() - entities[group].size()
	var payload = {
		"capture_schema_id": _WP2_CAPTURE_SCHEMA_ID,
		"capture_schema_hash": _WP2_CAPTURE_SCHEMA_HASH,
		"capture_seq": _wp2_capture_seq,
		"observation_ts_ms": int(state.get("observation_ts_ms", now_ms)),
		"observation_age_ms": max(now_ms - int(state.get("observation_ts_ms", now_ms)), 0),
		"control_dt_ms": control_dt_ms,
		"valid": true,
		"wave": int(state.get("wave", 0)),
		"wave_time": timer,
		"player": player.duplicate(true),
		"teacher": {
			"action": {"x": current_move_vector.x, "y": current_move_vector.y},
			"previous_action": {"x": _wp2_previous_action.x, "y": _wp2_previous_action.y},
			"action_fresh": teacher_action_fresh,
			"reason": str(last_move_debug.get("reason", "potential_field")),
			"contributions": last_move_debug.get("debug", {}).duplicate(true),
		},
		"entities": entities,
		"weapons": state.get("weapons", []),
		"arena": state.get("arena", {}),
		"invalid_counts": state.get("invalid_entities", {}),
		"dropped_counts": dropped_counts,
	}
	payload["player"]["measured_vx"] = measured_velocity.x
	payload["player"]["measured_vy"] = measured_velocity.y
	# v127 material-crediting instrumentation. Written onto the payload copy, never
	# into `state`, so the teacher's decision inputs are byte-identical to v126.
	payload["player"]["materials"] = _wp2_player_materials()
	payload["player"]["bonus_materials"] = _wp2_bonus_materials()
	_telem.emit_versioned("combat_capture", payload, _WP2_CAPTURE_SCHEMA_VERSION)
	# Flag-off path unchanged: prev-action tracks current_move_vector. In student
	# mode the learned controller owns prev-action (resolved applied vector), so
	# skip this overwrite (it is set from get_resolved_applied_vector() at emit).
	if not _student_active():
		_wp2_previous_action = current_move_vector
	_wp2_last_capture_player_pos = player_pos
	_wp2_last_capture_ts_ms = now_ms
	# Human-label counters are per CAPTURE INTERVAL, so they reset HERE and not in
	# choose_movement (which runs ~3x per capture and would pin samples at 1). The
	# block was built by choose_movement earlier on THIS tick, so what the capture
	# carries is the interval that just closed.
	_human_move_samples = 0
	_human_move_all_identical = true
	return payload


func _wp2_apply_capture_limit(raw: Array, group: String) -> Array:
	# Returns the entities of `group` that survive its capture-side capacity limit.
	# A limit of 0 — the shipped setting for every group — means unlimited, so the
	# raw array is returned untouched and the capture stays untruncated. The caller
	# derives dropped_counts from raw.size() - kept.size(), so the reported drops can
	# never drift from what was actually emitted.
	var limit := int(_WP2_CAPTURE_LIMITS.get(group, 0))
	if limit <= 0 or raw.size() <= limit:
		return raw
	var kept := []
	for i in range(limit):
		kept.append(raw[i])
	return kept


func _wp2_player_materials() -> int:
	# Spendable material counter — the same RunData accessor the shop path reads for
	# `gold` (see _handle_shop / _build_dict). -1 means "unavailable", never 0, so a
	# missing accessor cannot be misread as a genuinely empty purse.
	if RunData == null or not RunData.has_method("get_player_gold"):
		return -1
	return int(RunData.get_player_gold(0))


func _wp2_bonus_materials() -> int:
	# The end-of-wave carry-over pool. Brotato's clean_up_room() sends every material
	# still on the floor to the gold bag, and those credit `bonus_gold` rather than
	# spendable gold; spawn_gold() then drains it by boosting subsequent drops. It is
	# therefore the direct observable for the deferred-crediting question in
	# reports/wp2/materials_leftover_corrected.md — a jump here at wave end (with no
	# matching jump in `materials`) is the backlog model; no jump is immediate credit.
	# Accessor shape differs across builds, so probe method then property; -1 =
	# unavailable.
	if RunData == null:
		return -1
	if RunData.has_method("get_player_bonus_gold"):
		return int(RunData.get_player_bonus_gold(0))
	var value = RunData.get("bonus_gold")
	if value == null:
		return -1
	return int(value)


func _wave_timer_snapshot(main) -> Dictionary:
	var timer = main.get("_wave_timer")
	if timer == null:
		return {"elapsed_sec": 0.0, "remaining_sec": 0.0, "duration_sec": 0.0, "valid": false}
	var duration := float(timer.wait_time)
	var remaining := float(timer.time_left)
	return {
		"elapsed_sec": max(duration - remaining, 0.0),
		"remaining_sec": max(remaining, 0.0),
		"duration_sec": max(duration, 0.0),
		"valid": true,
	}


func _is_crate_id(item_id: String) -> bool:
	var lowered := item_id.to_lower()
	return lowered.find("item_box") >= 0 or lowered.find("crate") >= 0


func _normalize_combat_relative(state: Dictionary) -> void:
	# This controller-owned snapshot is the active runtime path. Carry the same
	# player-relative coordinates as GameAdapter so finale telemetry and future
	# learned-combat transitions can measure actual engagement distance.
	var player = state.get("player", {})
	if player.empty():
		return
	var px = float(player.get("x", 0))
	var py = float(player.get("y", 0))
	for key in ["enemies", "bosses", "projectiles", "loot", "consumables"]:
		if not state.has(key):
			continue
		for entity in state[key]:
			entity["nx"] = float(entity.get("x", 0)) - px
			entity["ny"] = float(entity.get("y", 0)) - py


func _collect_live_weapons(es) -> Array:
	# Use equipped weapon nodes' current_stats so range items/stats apply.
	var weapons = []
	if es != null and "_players" in es:
		for p in es._players:
			if not is_instance_valid(p) or p.dead:
				continue
			if not ("current_weapons" in p):
				continue
			for w in p.current_weapons:
				if not is_instance_valid(w):
					continue
				var cs = w.current_stats if ("current_stats" in w) else null
				if cs == null:
					continue
				var wtype = "ranged"
				if ("stats" in w) and w.stats != null and not ("projectile_scene" in w.stats):
					wtype = "melee"
				weapons.append({
					"type": wtype,
					"max_range": float(cs.max_range),
					"damage": cs.damage,
					"cooldown": cs.cooldown,
				})
			if not weapons.empty():
				return weapons
	# Fallback: inventory base stats + live range stat (WeaponService formula).
	var range_stat := 0.0
	if typeof(Utils) != TYPE_NIL:
		range_stat = float(Utils.get_stat(Keys.generate_hash("stat_range"), 0))
	for w in RunData.get_player_weapons(0):
		if w == null or w.stats == null:
			continue
		var is_ranged = int(w.type) == 1
		var base_r = float(w.stats.max_range)
		var live_r: float
		if is_ranged:
			live_r = max(25.0, base_r + range_stat)
		else:
			live_r = max(25.0, base_r + range_stat / 2.0)
		weapons.append({
			"type": "ranged" if is_ranged else "melee",
			"max_range": live_r,
			"damage": w.stats.damage,
			"cooldown": w.stats.cooldown,
		})
	return weapons


func _collect_loot(main) -> Array:
	var loot = []
	var golds = main.get("_golds")
	if typeof(golds) == TYPE_ARRAY:
		for item in golds:
			if not is_instance_valid(item):
				continue
			if ("visible" in item) and not item.visible:
				continue
			loot.append(_material_snapshot(item))
		return loot
	var items = main.get_node_or_null("Items")
	if items == null:
		items = main.get_node_or_null("%Materials")
	if items:
		for item in items.get_children():
			if not is_instance_valid(item) or not item.visible:
				continue
			loot.append(_material_snapshot(item))
	return loot


func _material_snapshot(item) -> Dictionary:
	# v127: materials are NOT unit-valued. A Gold node ships with `value = 1`, but it
	# grows in two engine paths: bonus_gold boosting at spawn, and MAX_GOLDS
	# absorption once _WP2_ENGINE_MAX_GOLDS entities are already on the floor. Emit
	# the live value so the pile can be measured past the entity ceiling; fall back to
	# 1 (the class default) only if the property is absent on this build.
	var snap := _pickup_snapshot(item, "material", "")
	snap["value"] = int(item.value) if ("value" in item) else 1
	return snap


func _collect_trees(es) -> Array:
	var trees = []
	if es == null:
		return trees
	var neutrals = []
	if "neutrals" in es:
		neutrals = es.neutrals
	if typeof(neutrals) != TYPE_ARRAY:
		return trees
	for n in neutrals:
		if not is_instance_valid(n):
			continue
		if ("dead" in n) and n.dead:
			continue
		trees.append(_pickup_snapshot(n, "obstacle", "tree"))
	return trees


func _collect_consumables(main) -> Array:
	var cons = []
	var list = main.get("_consumables")
	if typeof(list) == TYPE_ARRAY:
		for c in list:
			if not is_instance_valid(c):
				continue
			if ("visible" in c) and not c.visible:
				continue
			var id = ""
			var data = c.get("consumable_data")
			if data != null and ("my_id" in data):
				id = str(data.my_id)
			cons.append(_pickup_snapshot(c, "consumable", id))
		return cons
	var cons_node = main.get_node_or_null("Consumables")
	if cons_node == null:
		cons_node = main.get_node_or_null("%Consumables")
	if cons_node:
		for c in cons_node.get_children():
			if not is_instance_valid(c) or not c.visible:
				continue
			var id2 = ""
			var data2 = c.get("consumable_data")
			if data2 != null and ("my_id" in data2):
				id2 = str(data2.my_id)
			cons.append(_pickup_snapshot(c, "consumable", id2))
	return cons


func _pickup_snapshot(node, category: String, item_id: String) -> Dictionary:
	var velocity := Vector2.ZERO
	if "velocity" in node:
		velocity = node.velocity
	elif node.has_method("get_next_velocity"):
		velocity = node.get_next_velocity()
	return {
		"x": node.global_position.x,
		"y": node.global_position.y,
		"vx": velocity.x,
		"vy": velocity.y,
		"instance_id": node.get_instance_id(),
		"id": item_id,
		"category": category,
		"type_id": _node_script_path(node),
		"radius": _collision_radius(node, 12.0),
	}


# ───────────────────────────── shop ───────────────────────────────────────────

func _handle_shop(shop) -> void:
	current_move_vector = Vector2.ZERO
	var now = OS.get_ticks_msec() / 1000.0
	var need: float = SHOP_ACTION_INTERVAL
	if (_last_shop_action_type == "shop_combine"
			or _last_shop_action_type == "shop_sell"
			or _last_shop_action_type == "shop_buy"):
		need = SHOP_MUTATE_INTERVAL
	if now - _last_shop_action_at < need:
		return
	var state = _gather_shop_state(shop)
	if state.empty(): return
	if _pending_combine_wave >= 0:
		# A combine is the only shop mutation allowed to cross this barrier.
		# Wait long enough for Brotato's UI/model to settle, then require a
		# freshly gathered weapon inventory that differs from the pre-combine
		# inventory before any later shop action can be considered.
		var observed_signature := _shop_weapon_signature(state)
		var combine_wait: float = now - _pending_combine_at
		if combine_wait < SHOP_COMBINE_CONFIRM_INTERVAL:
			return
		if observed_signature == _pending_combine_signature:
			if combine_wait >= SHOP_COMBINE_CONFIRM_TIMEOUT and not _combine_timeout_reported:
				_combine_timeout_reported = true
				var timeout_previous_mouse_mode := _combine_restore_mouse_mode
				_restore_pre_combine_mouse_mode()
				if _telem != null:
					_telem.emit("shop_combine_confirmation_timeout", {
						"wave": _pending_combine_wave,
						"wait_ms": int(combine_wait * 1000.0),
						"executor": "deferred_core_combine",
						"mouse_mode_restored": timeout_previous_mouse_mode >= 0,
						"signature": observed_signature,
					})
				# v66: clear the barrier after the timeout is reported so the shop can
				# resume (previously the run soft-locked here forever). The visit's
				# combine budget was already spent at dispatch, so no second combine
				# can be proposed this visit; all other combine invariants unchanged.
				_pending_combine_signature = ""
				_pending_combine_wave = -1
				_pending_combine_at = 0.0
				_combine_timeout_reported = false
				_last_shop_action_at = now
			return
		var restored_mouse_mode := _combine_restore_mouse_mode
		_restore_pre_combine_mouse_mode()
		if _telem != null:
			_telem.emit("shop_combine_confirmed", {
				"wave": _pending_combine_wave,
				"wait_ms": int(combine_wait * 1000.0),
				"state_changed": true,
				"executor": "deferred_core_combine",
				"mouse_mode_restored": restored_mouse_mode >= 0,
				"before_signature": _pending_combine_signature,
				"after_signature": observed_signature,
			})
		_pending_combine_signature = ""
		_pending_combine_wave = -1
		_pending_combine_at = 0.0
		_combine_timeout_reported = false
		_last_shop_action_at = now
		return
	if _pending_surplus_wave >= 0:
		# v126 board-refresh barrier. A surplus reroll was dispatched; act only
		# on a CONFIRMED new board (changed signature), never on a stale one, and
		# at most once per board signature.
		var surplus_signature := _shop_board_signature(state)
		var surplus_wait: float = now - _pending_surplus_at
		if surplus_wait < SHOP_SURPLUS_CONFIRM_INTERVAL:
			return
		if surplus_signature == _pending_surplus_signature:
			if surplus_wait >= SHOP_SURPLUS_CONFIRM_TIMEOUT and not _surplus_timeout_reported:
				_surplus_timeout_reported = true
				if _telem != null:
					_telem.emit("shop_surplus_stale_timeout", {
						"wave": _pending_surplus_wave,
						"wait_ms": int(surplus_wait * 1000.0),
						"signature": surplus_signature,
						"exit_reason": _CONFIG_SCRIPT.SHOP_EXIT_BOARD_STALE_TIMEOUT,
					})
				# Clear the barrier so the shop can resume; the surplus reroll
				# budget for this visit was already spent at dispatch.
				_pending_surplus_signature = ""
				_pending_surplus_wave = -1
				_pending_surplus_at = 0.0
				_surplus_timeout_reported = false
				_last_shop_action_at = now
			return
		if _telem != null:
			_telem.emit("shop_surplus_reroll_confirmed", {
				"wave": _pending_surplus_wave,
				"wait_ms": int(surplus_wait * 1000.0),
				"before_signature": _pending_surplus_signature,
				"after_signature": surplus_signature,
			})
		_pending_surplus_signature = ""
		_pending_surplus_wave = -1
		_pending_surplus_at = 0.0
		_surplus_timeout_reported = false
	var profile = _profiles.get_profile(state.get("character", ""))
	var decision = choose_meta_action(state, state.get("legal_actions", []))
	var action: Dictionary = decision.get("action", {})
	action = _apply_shop_cycle_guard(action, state)
	_track_shop_conversion(state, action)
	last_meta_debug = decision
	if _telem != null:
		var build_metrics := _build_metrics(
			state.get("build", {}).get("stats", {}),
			state.get("build", {}).get("weapons", []), int(state.get("wave", 0)),
			_last_known_max_hp)
		_telem.emit("purchase_offer", {"items": state.get("shop_items", []), "gold": state.get("gold", 0), "reroll_price": state.get("reroll_price", 0)})
		_telem.emit("purchase_decision", {
			"action": action,
			"wave": state.get("wave", 0),
			"gold_before": state.get("gold", 0),
			"reroll_price": state.get("reroll_price", 0),
			"score_breakdown": decision.get("score_breakdown", {}),
			"legal_alternatives": decision.get("legal_alternatives", []),
			"reason": decision.get("reason", ""),
			"build_metrics": build_metrics,
			# v126: shop-exit reason code + the surplus arithmetic it was derived
			# from, so the audit can recompute both from telemetry alone.
			"exit_reason": action.get("exit_reason", ""),
			"surplus": action.get("surplus", {}),
		})
	_update_shop_hud(action, state, decision)
	if action.empty() or action.get("type", "") == "shop_go":
		_shop_go(shop)
		_last_shop_action_type = "shop_go"
	else:
		if action.get("type", "") == "shop_combine":
			if _dispatch_safe_combine(shop, action, state):
				_pending_combine_signature = _shop_weapon_signature(state)
				_pending_combine_wave = int(state.get("wave", -1))
				_pending_combine_at = now
				_combine_timeout_reported = false
				_last_shop_action_type = "shop_combine"
			else:
				_last_shop_action_type = "shop_combine_rejected"
		else:
			_apply_shop_action(shop, action)
			_last_shop_action_type = str(action.get("type", ""))
			if action.get("surplus_reroll", false):
				# Arm the v126 board-refresh barrier against the PRE-reroll board.
				_pending_surplus_signature = _shop_board_signature(state)
				_pending_surplus_wave = int(state.get("wave", -1))
				_pending_surplus_at = now
				_surplus_timeout_reported = false
	if _orch != null:
		_orch.note_action()
	_last_shop_action_at = now


func _apply_shop_cycle_guard(action: Dictionary, state: Dictionary) -> Dictionary:
	var action_type := str(action.get("type", ""))
	if action_type != "shop_lock" and action_type != "shop_unlock":
		return action
	var wave := int(state.get("wave", -1))
	var item_id := str(action.get("item_id", ""))
	if item_id == "":
		var slot := int(action.get("slot", -1))
		for item in state.get("shop_items", []):
			if int(item.get("slot", -2)) == slot:
				item_id = str(item.get("id", ""))
				break
	if wave != _shop_transition_wave or item_id != _shop_transition_item_id:
		_shop_transition_wave = wave
		_shop_transition_item_id = item_id
		_shop_transition_count = 1
	else:
		_shop_transition_count += 1
	if _shop_transition_count <= _CONFIG_SCRIPT.SHOP_MAX_LOCK_TRANSITIONS_PER_ITEM:
		return action
	return {
		"type": "shop_go",
		"score": float(action.get("score", 0.0)),
		"shop_cycle_guard": true,
		"blocked_item_id": item_id,
		"blocked_transition": action_type,
		"transition_count": _shop_transition_count,
	}


func _shop_board_signature(state: Dictionary) -> String:
	# v126: identity of the offered board. A reroll must change this before any
	# further shop action is considered (stale-board protection + idempotency).
	var parts := []
	for item in state.get("shop_items", []):
		parts.append("%d:%s:%d:%d:%s" % [
			int(item.get("slot", -1)), str(item.get("id", "")),
			int(item.get("tier", -1)), int(item.get("price", 0)),
			"1" if item.get("locked", false) else "0"])
	parts.sort()
	return JSON.print(parts)


func _shop_weapon_signature(state: Dictionary) -> String:
	var parts := []
	for weapon in state.get("build", {}).get("weapons", []):
		parts.append("%s:%d" % [str(weapon.get("id", "")), int(weapon.get("tier", -1))])
	parts.sort()
	return JSON.print(parts)


func _update_shop_hud(action: Dictionary, state: Dictionary, decision: Dictionary) -> void:
	if _hud == null:
		return
	var atype: String = str(action.get("type", "?"))
	var score = action.get("score", decision.get("score", 0))
	var label: String = atype
	if atype == "shop_buy":
		var iid: String = str(action.get("item_id", ""))
		if iid.empty():
			var slot: int = int(action.get("slot", -1))
			for it in state.get("shop_items", []):
				if int(it.get("slot", -2)) == slot:
					iid = str(it.get("id", ""))
					if score == null or float(score) == 0.0:
						var profile = _profiles.get_profile(state.get("character", ""))
						score = _shop.item_score(it, state.get("build", {}), profile, int(state.get("wave", 1)))
					break
		label = "BUY %s  score=%.1f" % [iid, float(score)]
	elif atype == "shop_reroll":
		label = "REROLL  best=%.1f" % float(score)
	elif atype == "shop_combine":
		label = "COMBINE idx=%s" % str(action.get("index", "?"))
	elif atype == "shop_lock":
		label = "LOCK %s  score=%.1f" % [str(action.get("item_id", action.get("slot", "?"))), float(score)]
	elif atype == "shop_go":
		label = "GO"
	elif atype == "shop_sell":
		label = "SELL idx=%s" % str(action.get("index", "?"))
	_hud.set_status("last_buy", label)
	_hud.set_status("meta_action", "%s score=%s" % [atype, str(score)])
	_update_build_metrics_hud(_build_metrics(
		state.get("build", {}).get("stats", {}),
		state.get("build", {}).get("weapons", []), int(state.get("wave", 0)),
		_last_known_max_hp))


# v81 RSI: last-shop conversion factor and per-visit entry gold.
var _last_shop_conversion: float = 1.0
var _shop_conversion_wave: int = -1
var _shop_entry_gold: int = -1


func _track_shop_conversion(state: Dictionary, action: Dictionary) -> void:
	# v81 RSI conversion component: below the winner-DPS band, gold left
	# unspent at shop_go is a strength leak (the v79 loss banked 400+ while
	# weak). At or above the band, banking is legitimate and scores 1.0.
	var wave := int(state.get("wave", 0))
	if _shop_conversion_wave != wave:
		_shop_conversion_wave = wave
		_shop_entry_gold = int(state.get("gold", 0))
	if str(action.get("type", "")) != "shop_go":
		return
	if wave < _CONFIG_SCRIPT.OFFENSE_BAND_FROM_WAVE:
		_last_shop_conversion = 1.0
		return
	var rating: Dictionary = _COMBAT_MODEL_SCRIPT.offense_rating({
		"stats": state.get("build", {}).get("stats", {}),
		"weapons": state.get("build", {}).get("weapons", []),
	})
	if float(rating.get("weapon_dps", 0.0)) >= float(_CONFIG_SCRIPT.offense_dps_target(wave)):
		_last_shop_conversion = 1.0
		return
	var entry := float(max(_shop_entry_gold, 1))
	var leftover := max(0.0, float(state.get("gold", 0)) - float(_CONFIG_SCRIPT.SHOP_MED_GOLD_RESERVE))
	_last_shop_conversion = clamp(1.0 - leftover / entry, 0.0, 1.0)


func _metric_targets(wave: int, observed_p90_density: float = 0.0,
	observed_peak_density: float = 0.0) -> Dictionary:
	var offense_target := 0.0
	var hp_target := 0.0
	var armor_target := 0.0
	var sustain_target := 0.0
	if wave >= _CONFIG_SCRIPT.LATE_SHOP_WAVE:
		offense_target = _CONFIG_SCRIPT.OFFENSE_FLOOR_LATE
		hp_target = _CONFIG_SCRIPT.DEFENSE_ADEQUATE_MAX_HP
		armor_target = _CONFIG_SCRIPT.DEFENSE_ADEQUATE_ARMOR
		sustain_target = _CONFIG_SCRIPT.DEFENSE_ADEQUATE_SUSTAIN
	elif wave >= _CONFIG_SCRIPT.MID_SHOP_PIVOT_WAVE:
		offense_target = _CONFIG_SCRIPT.OFFENSE_FLOOR_MID
		hp_target = _CONFIG_SCRIPT.DEFENSE_ADEQUATE_MID_MAX_HP
		armor_target = _CONFIG_SCRIPT.DEFENSE_ADEQUATE_MID_ARMOR
		sustain_target = _CONFIG_SCRIPT.DEFENSE_ADEQUATE_MID_SUSTAIN
	else:
		# Display-only early ramp that meets the real policy targets at wave 10.
		var progress := clamp(float(max(wave, 1)) /
			float(_CONFIG_SCRIPT.MID_SHOP_PIVOT_WAVE), 0.1, 1.0)
		offense_target = _CONFIG_SCRIPT.OFFENSE_FLOOR_MID * progress
		hp_target = 15.0 + (_CONFIG_SCRIPT.DEFENSE_ADEQUATE_MID_MAX_HP - 15.0) * progress
		armor_target = max(1.0, _CONFIG_SCRIPT.DEFENSE_ADEQUATE_MID_ARMOR * progress)
		sustain_target = max(1.0, _CONFIG_SCRIPT.DEFENSE_ADEQUATE_MID_SUSTAIN * progress)
	if wave >= _CONFIG_SCRIPT.MID_SHOP_PIVOT_WAVE:
		offense_target += _CONFIG_SCRIPT.OFFENSE_TARGET_MARGIN
		offense_target += clamp(
			(observed_p90_density - _CONFIG_SCRIPT.OFFENSE_DENSITY_P90_GOAL)
				* _CONFIG_SCRIPT.OFFENSE_DENSITY_POINTS_PER_ENEMY,
			0.0, _CONFIG_SCRIPT.OFFENSE_DENSITY_MAX_BONUS)
		offense_target += clamp(
			(observed_peak_density - _CONFIG_SCRIPT.OFFENSE_DENSITY_PEAK_GOAL)
				* _CONFIG_SCRIPT.OFFENSE_DENSITY_POINTS_PER_PEAK_ENEMY,
			0.0, _CONFIG_SCRIPT.OFFENSE_DENSITY_MAX_PEAK_BONUS)
	return {
		"offense": offense_target,
		"hp": hp_target,
		"armor": armor_target,
		"sustain": sustain_target,
	}


func _build_metrics(stats: Dictionary, weapons: Array, wave: int,
	live_max_hp: float = -1.0) -> Dictionary:
	var targets := _metric_targets(wave, _last_wave_p90_density,
		_last_wave_peak_density)
	var ranged := _metric_stat(stats, "stat_ranged_damage")
	var damage := _metric_stat(stats, "stat_percent_damage")
	var attack_speed := _metric_stat(stats, "stat_attack_speed")
	var crit := _metric_stat(stats, "stat_crit_chance")
	var hp_policy_stat := _metric_stat(stats, "stat_max_hp")
	var hp := live_max_hp if live_max_hp > 0.0 else hp_policy_stat
	var armor := _metric_stat(stats, "stat_armor")
	var dodge := _metric_stat(stats, "stat_dodge")
	var regeneration := _metric_stat(stats, "stat_hp_regeneration")
	var lifesteal := _metric_stat(stats, "stat_lifesteal")
	var sustain := regeneration + lifesteal
	var offense_rating := _COMBAT_MODEL_SCRIPT.offense_rating({
		"stats": stats,
		"weapons": weapons,
	})
	var offense_total := float(offense_rating.get("total", 0.0))
	# Each policy defense layer is worth 100 points at adequacy. The total is
	# intentionally uncapped so values above the 300 target expose over-defense.
	var defense_total := (100.0 * max(0.0, hp) / float(targets["hp"])
		+ 100.0 * max(0.0, armor) / float(targets["armor"])
		+ 100.0 * max(0.0, sustain) / float(targets["sustain"]))
	# v80: winner-trajectory indices — estimated weapon DPS vs the winning runs'
	# median curve, and a wave-scaled effective-HP index vs the winners' floor.
	var dps_target := float(_CONFIG_SCRIPT.offense_dps_target(wave))
	var ehp_target := float(_CONFIG_SCRIPT.defense_ehp_target(wave))
	var ehp_stats := stats.duplicate()
	ehp_stats["stat_max_hp"] = hp
	var ehp := float(_COMBAT_MODEL_SCRIPT.defense_ehp_index(ehp_stats, wave))
	# v81 Run Strength Index (100 = tracking the median winning run).
	var live_p90 := _last_wave_p90_density
	if not _density_enemy_samples.empty():
		live_p90 = _sample_percentile(_density_enemy_samples, 0.90)
	var rsi: Dictionary = _COMBAT_MODEL_SCRIPT.run_strength_index(
		float(offense_rating.get("weapon_dps", 0.0)), dps_target, ehp, ehp_target,
		float(live_p90), _last_shop_conversion)
	return {
		"wave": wave,
		"rsi": rsi,
		"offense": {
			"ranged_damage": ranged,
			"percent_damage": damage,
			"attack_speed": attack_speed,
			"crit_chance": crit,
			"stat_score": float(offense_rating.get("stat_score", 0.0)),
			"weapon_dps": float(offense_rating.get("weapon_dps", 0.0)),
			"weapon_score": float(offense_rating.get("weapon_score", 0.0)),
			"weapon_tier_sum": int(offense_rating.get("weapon_tier_sum", 0)),
			"weapon_count": int(offense_rating.get("weapon_count", 0)),
			"previous_wave_p90_density": _last_wave_p90_density,
			"previous_wave_peak_density": _last_wave_peak_density,
			"total": offense_total,
			"target": float(targets["offense"]),
			"dps_target": dps_target,
		},
		"defense": {
			"max_hp": hp,
			"max_hp_policy_stat": hp_policy_stat,
			"armor": armor,
			"dodge": dodge,
			"hp_regeneration": regeneration,
			"lifesteal": lifesteal,
			"sustain": sustain,
			"hp_target": float(targets["hp"]),
			"armor_target": float(targets["armor"]),
			"sustain_target": float(targets["sustain"]),
			"total": defense_total,
			"target": 300.0,
			"ehp": ehp,
			"ehp_target": ehp_target,
		},
	}


func _metric_stat(stats: Dictionary, key: String) -> float:
	var value = stats.get(key, 0)
	return 0.0 if value == null else float(value)


func _record_density_sample(wave: int, enemies: int) -> void:
	if _density_wave != wave:
		if not _density_enemy_samples.empty():
			_last_wave_p90_density = _sample_percentile(_density_enemy_samples, 0.90)
			_last_wave_peak_density = _sample_peak(_density_enemy_samples)
		_density_wave = wave
		_density_enemy_samples = []
	_density_enemy_samples.append(float(enemies))


func _finalize_density_for_shop() -> void:
	if not _density_enemy_samples.empty():
		_last_wave_p90_density = _sample_percentile(_density_enemy_samples, 0.90)
		_last_wave_peak_density = _sample_peak(_density_enemy_samples)


func _sample_peak(values: Array) -> float:
	var peak := 0.0
	for value in values:
		peak = max(peak, float(value))
	return peak


func _sample_percentile(values: Array, quantile: float) -> float:
	if values.empty():
		return 0.0
	var ordered := values.duplicate()
	ordered.sort()
	var idx := int(ceil(clamp(quantile, 0.0, 1.0) * ordered.size())) - 1
	idx = int(clamp(idx, 0, ordered.size() - 1))
	return float(ordered[idx])


func _update_build_metrics_hud(metrics: Dictionary) -> void:
	if _hud == null or metrics.empty():
		return
	var offense: Dictionary = metrics.get("offense", {})
	var defense: Dictionary = metrics.get("defense", {})
	var offense_target := max(1.0, float(offense.get("target", 0)))
	var defense_target := max(1.0, float(defense.get("target", 300)))
	_hud.set_status("offense", "%.1f / %.1f target (%d%%)" % [
		float(offense.get("total", 0)), float(offense.get("target", 0)),
		int(round(100.0 * float(offense.get("total", 0)) / offense_target))])
	_hud.set_status("offense_values", "ranged=%.1f  damage%%=%.1f  AS=%.1f  crit=%.1f" % [
		float(offense.get("ranged_damage", 0)), float(offense.get("percent_damage", 0)),
		float(offense.get("attack_speed", 0)), float(offense.get("crit_chance", 0))])
	_hud.set_status("offense_weapons", "weapon DPS=%.0f  score=%.1f  tiers=%d/%d guns  prev p90/peak=%.1f/%.1f" % [
		float(offense.get("weapon_dps", 0)), float(offense.get("weapon_score", 0)),
		int(offense.get("weapon_tier_sum", 0)), int(offense.get("weapon_count", 0)),
		float(offense.get("previous_wave_p90_density", 0)),
		float(offense.get("previous_wave_peak_density", 0))])
	_hud.set_status("defense", "%.0f / %.0f target (%d%%)" % [
		float(defense.get("total", 0)), float(defense.get("target", 300)),
		int(round(100.0 * float(defense.get("total", 0)) / defense_target))])
	_hud.set_status("defense_values", "HP=%.0f/%.0f  armor=%.1f/%.1f  sustain=%.1f/%.1f  dodge=%.1f" % [
		float(defense.get("max_hp", 0)), float(defense.get("hp_target", 0)),
		float(defense.get("armor", 0)), float(defense.get("armor_target", 0)),
		float(defense.get("sustain", 0)), float(defense.get("sustain_target", 0)),
		float(defense.get("dodge", 0))])
	_hud.set_status("defense_sustain", "regen=%.1f  lifesteal=%.1f" % [
		float(defense.get("hp_regeneration", 0)), float(defense.get("lifesteal", 0))])
	# v80: winner-trajectory indices (current / winners' wave-median).
	var wave_no := int(metrics.get("wave", 0))
	var dps_target := max(1.0, float(offense.get("dps_target", 0)))
	var ehp_target := max(1.0, float(defense.get("ehp_target", 0)))
	_hud.set_status("off_dps", "%.0f / %.0f win-median DPS w%d (%d%%)" % [
		float(offense.get("weapon_dps", 0)), dps_target, wave_no,
		int(round(100.0 * float(offense.get("weapon_dps", 0)) / dps_target))])
	_hud.set_status("def_ehp", "%.0f / %.0f win-median EHP w%d (%d%%)" % [
		float(defense.get("ehp", 0)), ehp_target, wave_no,
		int(round(100.0 * float(defense.get("ehp", 0)) / ehp_target))])
	# v81 Run Strength Index (100 = tracking the median winning run).
	var rsi: Dictionary = metrics.get("rsi", {})
	_hud.set_status("rsi", "%.0f (P%.0f C%.0f D%.0f E%.0f) w%d" % [
		float(rsi.get("total", 0)), 100.0 * float(rsi.get("power", 0)),
		100.0 * float(rsi.get("control", 0)), 100.0 * float(rsi.get("durability", 0)),
		100.0 * float(rsi.get("conversion", 0)), wave_no])


func _gather_shop_state(shop) -> Dictionary:
	_finalize_density_for_shop()
	var gold: int = RunData.get_player_gold(0)
	var state = {
		"phase": "shop",
		"wave": RunData.current_wave,
		"gold": gold,
		"character": _character_id(),
		"is_endless": RunData.is_endless_run,
	}
	var reroll_price: int = 0
	if "_reroll_price" in shop and shop._reroll_price.size() > 0:
		reroll_price = shop._reroll_price[0]
	state["reroll_price"] = reroll_price

	var items = []
	var container = shop._get_shop_items_container(0)
	if container != null:
		for i in container._shop_items.size():
			var node = container._shop_items[i]
			if node == null or not node.active or node.item_data == null: continue
			var data = node.item_data
			var entry = {
				"slot": i,
				"id": data.my_id,
				"price": node.value,
				"tier": data.tier,
				"category": _item_category(data),
				"affordable": gold >= node.value,
				"locked": node.locked,
				"effects": _effects_to_list(data.effects),
				"tags": _item_tags(data),
				"locks_weapons": _item_locks_weapons(data),
				"blocks_healing": _item_blocks_healing(data),
			}
			if data is WeaponData:
				entry["weapon_type"] = "ranged" if data.type == 1 else "melee"
				entry["weapon_id"] = data.weapon_id
				entry["sets"] = _weapon_sets(data)
				entry["upgrades"] = data.upgrades_into != null and data.tier + 1 <= RunData.get_player_effect(Keys.max_weapon_tier_hash, 0)
				entry["can_buy"] = container._can_weapon_be_bought(node)
				entry["usable"] = _weapon_usable(data)
				if data.stats != null:
					entry["damage"] = data.stats.damage
					entry["cooldown"] = data.stats.cooldown
					entry["scaling"] = _weapon_scaling(data.stats)
					entry["crit_chance"] = data.stats.crit_chance
					entry["crit_damage"] = data.stats.crit_damage
					entry["nb_projectiles"] = data.stats.nb_projectiles if "nb_projectiles" in data.stats else 1
					entry["piercing"] = data.stats.piercing if "piercing" in data.stats else 0
					entry["piercing_dmg_reduction"] = data.stats.piercing_dmg_reduction if "piercing_dmg_reduction" in data.stats else 0.5
					entry["bounce"] = data.stats.bounce if "bounce" in data.stats else 0
					entry["bounce_dmg_reduction"] = data.stats.bounce_dmg_reduction if "bounce_dmg_reduction" in data.stats else 0.5
					entry["is_healing"] = data.stats.is_healing
			items.append(entry)
	state["shop_items"] = items
	var build := _build_dict()
	build["previous_wave_p90_density"] = _last_wave_p90_density
	build["previous_wave_peak_density"] = _last_wave_peak_density
	state["build"] = build
	var legal = ["shop_go", "shop_reroll"]
	for it in items:
		legal.append({"type": "shop_buy", "slot": it.slot})
		legal.append({"type": "shop_lock" if not it.locked else "shop_unlock", "slot": it.slot})
	state["legal_actions"] = legal
	return state


func _dispatch_safe_combine(shop, action: Dictionary, state: Dictionary) -> bool:
	var idx: int = int(action.get("index", -1))
	var weapons = RunData.get_player_weapons(0)
	var rejection := ""
	var weapon = null
	if shop == null or not is_instance_valid(shop) or not shop.has_method("_combine_weapon"):
		rejection = "core_combine_unavailable"
	elif RunData.get_player_effect_bool(Keys.lock_current_weapons_hash, 0):
		rejection = "weapons_locked"
	elif idx < 0 or idx >= weapons.size():
		rejection = "invalid_weapon_index"
	else:
		weapon = weapons[idx]
		if weapon == null or not is_instance_valid(weapon) or weapon.upgrades_into == null:
			rejection = "weapon_not_upgradeable"
		else:
			var matching_weapons := 0
			for owned_weapon in weapons:
				if owned_weapon != null and is_instance_valid(owned_weapon) and owned_weapon.my_id == weapon.my_id:
					matching_weapons += 1
			if matching_weapons < 2:
				rejection = "matching_weapon_missing"
	if rejection != "":
		if _telem != null:
			_telem.emit("shop_combine_dispatch_rejected", {
				"wave": int(state.get("wave", -1)),
				"index": idx,
				"reason": rejection,
			})
		return false

	_combine_restore_mouse_mode = Input.get_mouse_mode()
	Input.set_mouse_mode(Input.MOUSE_MODE_VISIBLE)
	# Brotato's button callback resets popup focus and its synchronous core path
	# may focus a newly-created control while it is outside the scene tree. Run
	# the core transaction on the next idle frame with visible-mouse semantics so
	# neither unsafe focus path executes.
	shop.call_deferred("_combine_weapon", weapon, 0, false)
	if _telem != null:
		_telem.emit("shop_combine_dispatched", {
			"wave": int(state.get("wave", -1)),
			"index": idx,
			"weapon_id": str(weapon.my_id),
			"executor": "deferred_core_combine",
			"mouse_mode": "visible",
			"previous_mouse_mode": _combine_restore_mouse_mode,
		})
	return true


func _restore_pre_combine_mouse_mode() -> void:
	if _combine_restore_mouse_mode < 0:
		return
	Input.set_mouse_mode(_combine_restore_mouse_mode)
	_combine_restore_mouse_mode = -1


func _apply_shop_action(shop, action: Dictionary) -> void:
	match action.get("type", ""):
		"shop_buy":
			var slot: int = int(action.get("slot", -1))
			var container = shop._get_shop_items_container(0)
			if container != null and slot >= 0 and slot < container._shop_items.size():
				var node = container._shop_items[slot]
				if node != null and node.active:
					container.on_shop_item_buy_button_pressed(node)
		"shop_lock", "shop_unlock":
			var slot: int = int(action.get("slot", -1))
			var container = shop._get_shop_items_container(0)
			if container != null and slot >= 0 and slot < container._shop_items.size():
				var node = container._shop_items[slot]
				if node != null and node.active:
					node.change_lock_status(action["type"] == "shop_lock")
		"shop_reroll":
			shop._on_RerollButton_pressed(0)
		"shop_sell":
			var idx: int = int(action.get("index", -1))
			var weapons = RunData.get_player_weapons(0)
			if idx >= 0 and idx < weapons.size():
				shop._on_item_discard_button_pressed(weapons[idx], 0)


func _shop_go(shop) -> void:
	# Brotato names the "next wave" button GoButton. Method takes a player index.
	if shop.has_method("_on_GoButton_pressed"):
		shop._on_GoButton_pressed(0)
	elif shop.has_method("_on_ContinueButton_pressed"):
		shop._on_ContinueButton_pressed()


# ───────────────────────── level-up / crate overlay ───────────────────────────

func _handle_overlay(scene) -> void:
	var ui = _get_upgrades_ui(scene)
	if ui == null or not ui.visible:
		return
	var pc = ui._get_player_container(0) if ui.has_method("_get_player_container") else null
	if pc == null or not pc.visible:
		return

	var now = OS.get_ticks_msec() / 1000.0

	# Crate (item box from a chest): pc._items_container visible + _item_data set.
	if "_items_container" in pc and pc._items_container != null and pc._items_container.visible:
		if now - _last_crate_action_at < ACTION_INTERVAL:
			return
		_handle_crate_overlay(pc)
		_last_crate_action_at = now
		return

	# Level-up
	if now - _last_levelup_action_at < ACTION_INTERVAL:
		return

	var uis: Array = []
	if pc.has_method("_get_upgrade_uis"):
		uis = pc._get_upgrade_uis()
	var options: Array = []
	for i in range(uis.size()):
		var u = uis[i]
		if u == null or not u.visible: continue
		var data = u.get("upgrade_data") if "upgrade_data" in u else null
		if data == null: continue
		options.append({
			"index": i,
			"effects": _effects_to_list(data.effects),
			"tier": data.tier if "tier" in data else 0,
		})
	if options.empty():
		return

	var profile = _profiles.get_profile(_character_id())
	var state = {
		"phase": "LEVEL_UP",
		"character": _character_id(),
		"options": options,
		"wave": RunData.current_wave,
		"gold": RunData.get_player_gold(0),
		"reroll_price": 0,
		"reroll_count": 0,
		"build": _build_dict(),
	}
	var decision = choose_meta_action(state, options)
	var action: Dictionary = decision.get("action", {})
	var build_metrics := _build_metrics(
		state.get("build", {}).get("stats", {}),
		state.get("build", {}).get("weapons", []), int(state.get("wave", 0)),
		_last_known_max_hp)
	if _telem != null:
		_telem.emit("level_up_offer", {"options": options})
		_telem.emit("level_up_decision", {
			"action": action,
			"score_breakdown": decision.get("score_breakdown", {}),
			"legal_alternatives": options,
			"build_metrics": build_metrics,
		})
	if _hud != null:
		_update_build_metrics_hud(build_metrics)
		var atype: String = str(action.get("type", "?"))
		if atype == "levelup_choose":
			_hud.set_status("last_buy", "LVL idx=%s  score=%s" % [str(action.get("index", "?")), str(decision.get("score", 0))])
		elif atype == "levelup_reroll":
			_hud.set_status("last_buy", "LVL REROLL")
		else:
			_hud.set_status("last_buy", "LVL %s" % atype)
		_hud.set_status("meta_action", atype)
	if _orch != null:
		_orch.note_action()
	match action.get("type", ""):
		"levelup_choose":
			var idx: int = int(action.get("index", -1))
			if idx >= 0 and idx < uis.size():
				var data = uis[idx].get("upgrade_data") if "upgrade_data" in uis[idx] else null
				if data != null:
					pc._on_choose_button_pressed(data)
		"levelup_reroll":
			if pc.has_method("_on_RerollButton_pressed"):
				pc._on_RerollButton_pressed()
	_last_levelup_action_at = now


func _handle_crate_overlay(pc) -> void:
	# pc._item_data carries the offered item (weapon or item).
	var item_data = pc.get("_item_data") if "_item_data" in pc else null
	if item_data == null:
		# Consumables show up here too — let the game auto-take.
		if pc.has_method("_on_TakeButton_pressed"):
			pc._on_TakeButton_pressed()
		return
	var item := {
		"id": item_data.my_id if "my_id" in item_data else "",
		"tier": item_data.tier if "tier" in item_data else 0,
		"effects": _effects_to_list(item_data.effects) if "effects" in item_data else [],
		"tags": item_data.tags if "tags" in item_data and item_data.tags != null else [],
	}
	# Mark weapons separately so shop_strategy can apply allow_melee/allow_ranged.
	if item_data is WeaponData:
		item["category"] = "weapon"
		item["weapon_type"] = "ranged" if item_data.type == 1 else "melee"
		# v66: mirror the shop entry's identity keys — without sets/weapon_id the
		# allowlist check in decide_crate rejected every crate weapon (set_gun never
		# matched an empty sets array), discarding free guns all run.
		item["weapon_id"] = item_data.weapon_id
		item["sets"] = _weapon_sets(item_data)
		if item_data.stats != null:
			item["is_healing"] = item_data.stats.is_healing
	else:
		item["category"] = "item"
	var profile = _profiles.get_profile(_character_id())
	var state = {
		"item": item,
		"wave": RunData.current_wave,
		"build": _build_dict(),
	}
	var decision = choose_meta_action({"phase": "CRATE_RESOLUTION", "character": _character_id(), "item": item, "wave": RunData.current_wave, "build": _build_dict()}, ["crate_take", "crate_discard"])
	var action: Dictionary = decision.get("action", {})
	if _telem != null:
		_telem.emit("crate_offer", {"item": item})
		_telem.emit("crate_decision", {"action": action, "score_breakdown": decision.get("score_breakdown", {}), "legal_alternatives": ["crate_take", "crate_discard"]})
	if _orch != null:
		_orch.note_action()
	if action.get("type", "") == "crate_take" and pc.has_method("_on_TakeButton_pressed"):
		pc._on_TakeButton_pressed()
	elif pc.has_method("_on_DiscardButton_pressed"):
		pc._on_DiscardButton_pressed()


# ─────────────────────── shared helpers (ported from old mod) ─────────────────

func _get_active_player_container():
	var scene = get_tree().current_scene
	if scene == null: return null
	if scene.get("_entity_spawner") == null: return null
	var ui = _get_upgrades_ui(scene)
	if ui == null: return null
	if ui.has_method("_get_player_container"):
		return ui._get_player_container(0)
	return null


func _get_upgrades_ui(scene):
	if "_upgrades_ui" in scene: return scene._upgrades_ui
	if scene.has_method("get_node_or_null"):
		return scene.get_node_or_null("%UpgradesUI")
	return null


func _character_id() -> String:
	var c = RunData.get_player_character(0)
	return c.my_id if c != null else ""


func _get_current_zone_data():
	for zone in ZoneService.zones:
		if zone.my_id == RunData.current_zone:
			return zone
	if ZoneService.zones.size() > 0:
		return ZoneService.zones[0]
	return null


func _build_dict() -> Dictionary:
	var weapons = []
	for w in RunData.get_player_weapons(0):
		if w == null: continue
		var entry = {
			"id": w.my_id,
			"tier": w.tier,
			"type": "ranged" if w.type == 1 else "melee",
			"sets": _weapon_sets(w),
			"upgrades": w.upgrades_into != null and w.tier + 1 <= RunData.get_player_effect(Keys.max_weapon_tier_hash, 0),
			"index": RunData.get_player_weapons(0).find(w),
			"weapon_id": w.weapon_id,
		}
		if w.stats != null:
			entry["damage"] = w.stats.damage
			entry["cooldown"] = w.stats.cooldown
			entry["scaling"] = _weapon_scaling(w.stats)
			entry["crit_chance"] = w.stats.crit_chance
			entry["crit_damage"] = w.stats.crit_damage
			entry["nb_projectiles"] = w.stats.nb_projectiles if "nb_projectiles" in w.stats else 1
			entry["piercing"] = w.stats.piercing if "piercing" in w.stats else 0
			entry["piercing_dmg_reduction"] = w.stats.piercing_dmg_reduction if "piercing_dmg_reduction" in w.stats else 0.5
			entry["bounce"] = w.stats.bounce if "bounce" in w.stats else 0
			entry["bounce_dmg_reduction"] = w.stats.bounce_dmg_reduction if "bounce_dmg_reduction" in w.stats else 0.5
			entry["is_healing"] = w.stats.is_healing
			var burning_data = w.stats.burning_data if "burning_data" in w.stats else null
			entry["burning"] = (burning_data != null
				and (float(burning_data.chance) > 0.0
					or int(burning_data.damage) > 0
					or int(burning_data.duration) > 0))
			entry["sell_value"] = ItemService.get_recycling_value(RunData.current_wave, w.value, 0, true)
		weapons.append(entry)
	# v126: owned item ids feed material_value_reserve (piggy-bank class items
	# whose effect operates on the held material stock). Additive; no existing
	# consumer reads "items".
	# Both the 1.1.x per-player accessor and the older flat array are handled;
	# an unavailable API degrades to an empty list (reserve 0), never an error.
	var owned_items := []
	var owned_source := []
	if RunData.has_method("get_player_items"):
		owned_source = RunData.get_player_items(0)
	elif RunData.get("items") != null:
		# Avoid `"prop" in RunData` — Godot 3 rejects that for some autoload types
		# (see adapter/game_adapter.gd::_danger). Probe with get(), read the property.
		owned_source = RunData.items
	for owned in owned_source:
		if owned == null or not ("my_id" in owned):
			continue
		owned_items.append({"id": str(owned.my_id)})
	return {
		"weapons": weapons,
		"items": owned_items,
		"stats": _current_stats(),
		"previous_wave_p90_density": _last_wave_p90_density,
		"previous_wave_peak_density": _last_wave_peak_density,
		"gain_mods": _stat_gain_mods(),
		"caps": _stat_caps(),
		"weapon_slots": RunData.get_player_effect(Keys.weapon_slot_hash, 0),
		"can_sell": not RunData.get_player_effect_bool(Keys.lock_current_weapons_hash, 0),
	}


func _weapon_sets(w) -> Array:
	var out = []
	if "sets" in w and w.sets != null:
		for s in w.sets:
			if s != null and "my_id" in s: out.append(s.my_id)
	return out


func _item_tags(data) -> Array:
	if "tags" in data and data.tags != null: return data.tags
	return []


func _item_locks_weapons(data) -> bool:
	if not ("effects" in data) or data.effects == null: return false
	for e in data.effects:
		if e == null: continue
		if "key" in e and e.key == "lock_current_weapons": return true
	return false


func _item_blocks_healing(data) -> bool:
	if not ("effects" in data) or data.effects == null: return false
	for e in data.effects:
		if e == null: continue
		if "key" in e and (e.key == "no_heal" or e.key == "dmg_when_heal"): return true
	return false


func _item_category(data) -> String:
	if data is WeaponData: return "weapon"
	return "item"


func _effects_to_list(effects) -> Array:
	var out = []
	if effects == null: return out
	for e in effects:
		if e == null: continue
		var entry = {"key": "", "value": 0, "sign": 3}
		if "key" in e: entry["key"] = e.key
		if "value" in e: entry["value"] = e.value
		if "effect_sign" in e: entry["sign"] = e.effect_sign
		out.append(entry)
	return out


func _current_stats() -> Dictionary:
	var out = {}
	for n in _STAT_NAMES:
		out["stat_" + n] = Utils.get_stat(Keys.generate_hash("stat_" + n), 0)
	return out


func _stat_caps() -> Dictionary:
	return {
		"stat_dodge": RunData.get_player_effect(Keys.generate_hash("dodge_cap"), 0),
		"stat_crit_chance": RunData.get_player_effect(Keys.generate_hash("crit_chance_cap"), 0),
		"stat_speed": RunData.get_player_effect(Keys.generate_hash("speed_cap"), 0),
	}


func _stat_gain_mods() -> Dictionary:
	var out = {}
	var c = RunData.get_player_character(0)
	if c == null: return out
	for eff in c.effects:
		if eff != null and "stats_modified" in eff and eff.stats_modified != null:
			for st in eff.stats_modified:
				out[st] = out.get(st, 0) + eff.value
	return out


func _weapon_scaling(stats) -> Array:
	var out = []
	if "scaling_stats" in stats and stats.scaling_stats != null:
		for s in stats.scaling_stats:
			if s.size() >= 2:
				var key = s[0]
				if typeof(key) == TYPE_INT:
					key = Keys.hash_to_string[key] if Keys.hash_to_string.has(key) else ""
				if key != "":
					out.append([key, s[1]])
	return out


func _weapon_usable(data) -> bool:
	var max_t = RunData.get_player_effect(Keys.max_weapon_tier_hash, 0)
	var min_t = RunData.get_player_effect(Keys.min_weapon_tier_hash, 0)
	if data.tier > max_t or data.tier < min_t: return false
	if RunData.get_player_effect_bool(Keys.no_melee_weapons_hash, 0) and data.type == 0: return false
	if RunData.get_player_effect_bool(Keys.no_ranged_weapons_hash, 0) and data.type == 1: return false
	return true


# ───────────────────────── teacher API + agent lifecycle ─────────────────────

func choose_movement(combat_observation: Dictionary) -> Dictionary:
	var profile = _profiles.get_profile(combat_observation.get("character", ""))
	var vec: Vector2 = _field.compute_movement(combat_observation, profile)
	var translation_debug: Dictionary = {}
	if _field.has_method("finale_translation_debug"):
		translation_debug = _field.finale_translation_debug()
	# v127: the loot-dash state machine gets its own compact block. It rides the
	# existing debug bag, so it reaches BOTH consumers with no new plumbing — the
	# 20 Hz capture (teacher.contributions) and the 0.5 s combat_tick. Kept out of
	# finale_translation because it is not a finale signal; `loot_dash_active`
	# stays duplicated there so analysis written against pre-v127 runs still works.
	var loot_dash_debug: Dictionary = {}
	if _field.has_method("loot_dash_debug"):
		loot_dash_debug = _field.loot_dash_debug()
	# Per-term decomposition of the desire vector. Rides the same free-form debug
	# bag as loot_dash, so it costs no capture-schema/hash change. `seq` advances
	# once per _build_desire call — the finale and late-survival paths never call
	# it, so a repeated seq means the block is stale, not that nothing moved.
	var desire_debug: Dictionary = {}
	if _field.has_method("desire_debug"):
		desire_debug = _field.desire_debug()
	# Per-term decomposition of the safety tail's lane score plus the
	# candidate-pool statistics. Same free-form debug bag, so no capture-schema
	# or hash change. `seq` advances once per _best_finale_interior_lane call --
	# that function does NOT run every tick, so a repeated seq means the block is
	# stale, exactly as with desire above.
	var tail_debug: Dictionary = {}
	if _field.has_method("tail_debug"):
		tail_debug = _field.tail_debug()
	return {
		"vector": vec,
		"reason": "potential_field",
		"debug": {
			"profile": profile.name if profile != null else "",
			"enemies": combat_observation.get("enemies", []).size(),
			"projectiles": combat_observation.get("projectiles", []).size(),
			"finale_translation": translation_debug,
			"loot_dash": loot_dash_debug,
			"desire": desire_debug,
			"tail": tail_debug,
			# Raw human keyboard vector for the handover arm. Same free-form debug
			# bag as desire/tail, so no capture-schema or hash change; capture path
			# is teacher.contributions.human. Empty dict when human_movement is off.
			"human": human_debug(),
		},
	}

func choose_meta_action(run_observation: Dictionary, legal_actions) -> Dictionary:
	var profile = _profiles.get_profile(run_observation.get("character", ""))
	var phase = run_observation.get("phase", "")
	var action := {}
	var reason := ""
	if phase == "shop" or phase == "SHOP":
		action = _shop.decide_shop(run_observation, profile)
		reason = "shop_strategy"
	elif phase == "level_up" or phase == "LEVEL_UP":
		action = _shop.decide_levelup(run_observation, profile)
		reason = "levelup_strategy"
	elif phase == "crate" or phase == "CRATE_RESOLUTION":
		action = _shop.decide_crate(run_observation, profile)
		reason = "crate_strategy"
	else:
		action = _shop.decide_shop(run_observation, profile)
		reason = "shop_strategy_default"
	return {
		"action": action,
		"reason": reason,
		"score": action.get("score", 0),
		"score_breakdown": action.get("breakdown", action.duplicate()),
		"legal_alternatives": legal_actions,
		"profile": profile.name if profile != null else "",
	}

var _danger_latched: bool = false
var _danger_observed_latched: int = -1


func get_requested_danger() -> int:
	# The danger the OPERATOR asked for, from agent_config.json via the
	# orchestrator. difficulty_selection.gd needs this: it used to pass a
	# hardcoded 0, which silently discarded the configured value.
	if _orch == null:
		return 0
	return int(_orch.target_danger)


func observed_danger() -> int:
	# The danger the GAME reports, read live. Never the requested value.
	# Returns -1 when it cannot be read, which must be treated as a failure and
	# never coerced to 0 -- a 0 that means "unknown" is indistinguishable from a
	# genuine Danger 0 run, and that is exactly how the record came to contain
	# 1,873 runs whose `danger` field was a hardcoded literal.
	if RunData == null:
		return -1
	if RunData.get("current_difficulty") != null:
		return int(RunData.current_difficulty)
	if RunData.get("difficulty") != null:
		return int(RunData.difficulty)
	return -1


func difficulty_readback() -> Dictionary:
	# Everything needed to prove which difficulty actually ran. Emitted as its
	# own telemetry event AND folded into the run summary, because a campaign
	# that cannot prove its own arm measures nothing.
	var requested = get_requested_danger()
	var observed = observed_danger()
	var out = {
		"requested_danger": requested,
		"observed_danger": observed,
		"danger_ok": observed == requested,
	}
	# The scaling dial is a separate mechanism from danger and is probed
	# defensively -- absent properties record as null rather than as 1.0, so a
	# missing readback cannot masquerade as an inert dial.
	if RunData != null:
		var scaling = RunData.get("enemy_scaling")
		if scaling != null:
			out["enemy_scaling"] = scaling
		for prop in ["current_difficulty", "difficulty", "current_run_accessibility_settings"]:
			var v = RunData.get(prop)
			if v != null:
				out["rundata_" + prop] = v
	return out


func on_benchmark_activated(danger_value: int) -> void:
	active = true
	_manual_override = false
	movement_estop_suppressed = -1
	_end_run_force_at_ms = 0
	_restore_pre_combine_mouse_mode()
	_pending_combine_signature = ""
	_pending_combine_wave = -1
	_pending_combine_at = 0.0
	_combine_timeout_reported = false
	if _orch != null:
		_orch.target_danger = danger_value
		_orch.note_action()
	if not _run_started:
		_start_run()
	if _hud != null:
		_hud.set_status("enabled", "true")
		_hud.set_status("policy", policy_version)

func note_human_movement(v: Vector2) -> void:
	# Called from player_movement_behavior.gd at PHYSICS rate on the handover
	# branch, with the keyboard vector it is about to return. Exact inequality is
	# the right test: repeated identical input produces a bit-identical vector,
	# so any difference here is a real input change, not float noise.
	if _human_move_samples > 0 and v != _human_move_latest:
		_human_move_all_identical = false
	_human_move_latest = v
	_human_move_samples += 1

func note_movement_estop(had_input: bool) -> void:
	# Called at PHYSICS rate from player_movement_behavior.gd, but ONLY while the
	# gate is off. Arms the counter on first evaluation so -1 keeps meaning "the
	# seam never ran" rather than "no input seen".
	if movement_estop_suppressed < 0:
		movement_estop_suppressed = 0
	if not had_input:
		return
	movement_estop_suppressed += 1
	# One-shot. A flag echoing its own value proves DELIVERY only; this proves
	# CORRECTNESS -- real movement input arrived and the run did NOT end. Emitted
	# once per run rather than at 60 Hz.
	if movement_estop_suppressed == 1 and _telem != null and _run_started:
		_telem.emit("movement_estop_suppressed", {"wave": RunData.current_wave})

func human_debug() -> Dictionary:
	# EMPTY unless the handover is armed. An agent vector must never be
	# mistakable for a human label, so there is no zero-filled off-state.
	if not human_movement:
		return {}
	return {
		"x": _human_move_latest.x,
		"y": _human_move_latest.y,
		"samples": _human_move_samples,
		"all_identical": _human_move_all_identical,
	}

func on_manual_override() -> void:
	_restore_pre_combine_mouse_mode()
	_manual_override = true
	active = false
	if _learned != null:
		_learned.shutdown()
	if _telem != null and _run_started:
		_telem.emit("error", {"kind": "manual_override"})
	if _hud != null:
		_hud.set_status("enabled", "false (manual override)")

func _start_run() -> void:
	_run_started = true
	_combat_tick_counter = 0
	finale_combat_ticks = 0
	finale_recompute_ticks = 0
	finale_boss_ticks = 0
	finale_boss_in_short_range_ticks = 0
	finale_boss_in_long_range_ticks = 0
	_wp2_capture_seq = 0
	_wp2_previous_action = Vector2.ZERO
	_wp2_last_capture_player_pos = Vector2.ZERO
	_wp2_last_capture_ts_ms = -1
	_density_wave = -1
	_density_enemy_samples = []
	_last_wave_p90_density = 0.0
	_last_wave_peak_density = 0.0
	_shop_transition_wave = -1
	_shop_transition_item_id = ""
	_danger_latched = false
	_danger_observed_latched = -1
	_shop_transition_count = 0
	_last_shop_conversion = 1.0
	_shop_conversion_wave = -1
	_shop_entry_gold = -1
	_last_hp = -1.0
	_last_known_max_hp = -1.0
	_end_run_force_at_ms = 0
	if _orch != null:
		_orch.reset()
	var meta = {
		"run_id": "run_%d_%d" % [OS.get_unix_time(), randi() % 100000],
		"character": _character_id(),
		"weapon": _starting_weapon_id(),
		# `danger` is DELIBERATELY not read here. At _start_run the difficulty
		# element has not been pressed yet, so any read is pre-selection. The
		# authoritative value is latched on the first combat tick and written into
		# the summary by _finish_run via end_run's extras.
		"requested_danger": get_requested_danger(),
		"endless": false,
		"wave_retry": false,
		"game_version": "1.1.15.4",
		"mod_version": MOD_VERSION,
		"config_id": "well_rounded_d0_anyranged",
		"policy_version": policy_version,
		"finale_v2": finale_v2,
		"finale_rate_full": finale_rate_full,
		"finale_no_panic": finale_no_panic,
		"finale_heal_seek": finale_heal_seek,
		"finale_range_keep": finale_range_keep,
		"finale_projectile_priority": finale_projectile_priority,
		"finale_pivot_projectiles": finale_pivot_projectiles,
		"finale_co_rotate": finale_co_rotate,
		"finale_ring_radius": finale_ring_radius,
		"engage_distance_scale": engage_distance_scale,
		"calm_threat_mult": calm_threat_mult,
		"tail_calm_penalty_mult": tail_calm_penalty_mult,
		"tail_calm_clearance_mult": tail_calm_clearance_mult,
		"rare_gun_lock_persist": rare_gun_lock_persist,
		"human_movement": human_movement,
		# Gate state only -- DELIVERY, not correctness. Proof that suppression
		# actually happened is the movement_estop_suppressed event/counter.
		"movement_estop_enabled": movement_estop_enabled,
		"time_scale": time_scale,
	}
	if _telem != null:
		_telem.begin_run(meta)
	if _hud != null:
		_hud.set_status("run_id", meta["run_id"])
		_hud.set_status("enabled", "true")
		_hud.set_status("policy", policy_version)
		_refresh_batch_hud()

func _finish_run(result_phase: String) -> void:
	if not _run_started:
		return
	var result = "victory" if result_phase == "VICTORY" else "defeat"
	if _telem != null:
		# end_run copies every extra key into the summary verbatim (begin_run's
		# dict is an allowlist and would drop these), so the recompute ratio is
		# recorded directly.
		_telem.end_run(result, {
			# The authoritative difficulty, latched on the first combat tick.
			# -1 means no combat tick ever ran, which is a technical failure and
			# must NOT be read as Danger 0.
			"danger": _danger_observed_latched,
			"danger_ok": _danger_observed_latched == get_requested_danger(),
			"last_wave": RunData.current_wave,
			"waves_completed": RunData.current_wave,
			"finale_combat_ticks": finale_combat_ticks,
			"finale_recompute_ticks": finale_recompute_ticks,
			"finale_boss_ticks": finale_boss_ticks,
			"finale_boss_in_short_range_ticks": finale_boss_in_short_range_ticks,
			"finale_boss_in_long_range_ticks": finale_boss_in_long_range_ticks,
			# CORRECTNESS readback for the E-stop gate. -1 = the movement seam never
			# evaluated it (defect); 0 = evaluated, no input; >0 = input arrived and
			# was suppressed while the run continued. Only >0 proves the gate works;
			# movement_estop_enabled alone proves delivery.
			"movement_estop_suppressed": movement_estop_suppressed,
		})
	_restore_pre_combine_mouse_mode()
	_record_batch_result(result == "victory")
	_run_started = false
	active = false
	# Prepare for next batch run if auto_start remains enabled.
	if auto_start_benchmark and not _manual_override:
		# Soft re-arm after short delay via stale menu navigation.
		pass


func _load_batch_stats() -> void:
	_batch_wins = 0
	_batch_runs = 0
	var f = File.new()
	if not f.file_exists(_BATCH_STATS_PATH):
		return
	if f.open(_BATCH_STATS_PATH, File.READ) != OK:
		return
	var raw = f.get_as_text()
	f.close()
	var parsed = JSON.parse(raw)
	if parsed.error != OK or typeof(parsed.result) != TYPE_DICTIONARY:
		return
	var data: Dictionary = parsed.result
	if str(data.get("policy_version", "")) != policy_version:
		# New policy deploy → fresh counter for this overnight.
		_save_batch_stats()
		return
	_batch_wins = int(data.get("wins", 0))
	_batch_runs = int(data.get("runs", 0))


func _save_batch_stats() -> void:
	var d = Directory.new()
	d.make_dir_recursive("user://brotato_agent")
	var f = File.new()
	if f.open(_BATCH_STATS_PATH, File.WRITE) != OK:
		return
	f.store_string(JSON.print({
		"policy_version": policy_version,
		"wins": _batch_wins,
		"runs": _batch_runs,
	}))
	f.close()


func _record_batch_result(won: bool) -> void:
	_batch_runs += 1
	if won:
		_batch_wins += 1
	_save_batch_stats()
	_refresh_batch_hud()


func _refresh_batch_hud() -> void:
	if _hud == null:
		return
	_hud.set_status("record", "%dW / %d runs" % [_batch_wins, _batch_runs])

func _on_watchdog(reason: String) -> void:
	if _telem != null:
		_telem.emit("recovery_attempt", {"reason": reason})
	if _hud != null:
		_hud.set_status("watchdog", reason)
	if _orch != null and not _orch.begin_recovery(reason):
		if _telem != null:
			_telem.emit("error", {"kind": "terminal", "reason": reason})
			_telem.end_run("automation_fault", {
				"failure_category": reason,
				"last_wave": RunData.current_wave,
				"finale_combat_ticks": finale_combat_ticks,
				"finale_recompute_ticks": finale_recompute_ticks,
				"finale_boss_ticks": finale_boss_ticks,
				"finale_boss_in_short_range_ticks": finale_boss_in_short_range_ticks,
				"finale_boss_in_long_range_ticks": finale_boss_in_long_range_ticks,
			})
		_run_started = false
		active = false
		# Keep auto_start_benchmark so menu driving can still chain the next run.


func _player_all_dead(main) -> bool:
	var es = main.get_node_or_null("EntitySpawner")
	if es == null:
		return false
	var players = es.get("_players")
	if typeof(players) != TYPE_ARRAY or players.empty():
		# After death the player list can be empty — treat as dead if run-lost flagged
		# or last known HP was already tracked as zero.
		return bool(main.get("_is_run_lost")) or _last_hp == 0.0
	var any_alive = false
	for p in players:
		if is_instance_valid(p) and not p.dead:
			any_alive = true
			break
	return not any_alive


func _hp_is_zero(main) -> bool:
	var es = main.get_node_or_null("EntitySpawner")
	if es == null:
		return _last_hp == 0.0
	var players = es.get("_players")
	if typeof(players) != TYPE_ARRAY or players.empty():
		return _last_hp == 0.0
	var saw_player = false
	for p in players:
		if not is_instance_valid(p):
			continue
		saw_player = true
		if p.dead:
			continue
		if float(p.current_stats.health) > 0.0:
			return false
	return saw_player


func _force_end_run_screen(main) -> void:
	# Wait briefly for the vanilla EndWaveTimer path, then force EndRun.
	var now = OS.get_ticks_msec()
	if _dismiss_killed_by_ok(main):
		_end_run_force_at_ms = now + 2000
		return
	if _end_run_force_at_ms == 0:
		_end_run_force_at_ms = now + 3500
		var t = main.get("_end_wave_timer")
		if t != null and t.has_method("start") and t.is_stopped():
			t.wait_time = 1.0
			t.start()
		return
	if now < _end_run_force_at_ms:
		return
	_end_run_force_at_ms = now + 5000
	if main.has_method("_on_EndWaveTimer_timeout"):
		main._on_EndWaveTimer_timeout()
		return
	var err = get_tree().change_scene("res://ui/menus/run/end_run.tscn")
	if err != OK:
		ModLoaderLog.warning("Failed to force EndRun scene: %s" % str(err), LOG_NAME)


func _dismiss_killed_by_ok(root: Node) -> bool:
	# 1.1.x shows RUN LOST + Killed-by panel with OkButton before EndRun continues.
	if root == null:
		return false
	var ok = _find_named_button(root, "OkButton", 12)
	if ok != null:
		ok.emit_signal("pressed")
		return true
	# Some layouts route Ok -> Cancel handler.
	if root.has_method("_on_CancelButton_pressed"):
		var maybe = _find_named_button(root, "OkButton", 12)
		if maybe != null or _find_named_button(root, "CancelButton", 12) != null:
			root._on_CancelButton_pressed()
			return true
	# Text fallback ("ok")
	var buttons = []
	_collect_buttons(root, buttons, 12)
	for b in buttons:
		if b == null or not (b is BaseButton) or b.disabled or not b.visible:
			continue
		var t = str(b.text).to_lower()
		if t == "ok" or t.find("ok") == 0 or t.find("okay") >= 0:
			b.emit_signal("pressed")
			return true
	return false


func _find_named_button(node: Node, target: String, depth: int):
	if node == null or depth < 0:
		return null
	if node.name == target and node is BaseButton and node.visible and not node.disabled:
		return node
	for c in node.get_children():
		var r = _find_named_button(c, target, depth - 1)
		if r != null:
			return r
	return null


func _collect_buttons(node: Node, out: Array, depth: int) -> void:
	if node == null or depth < 0:
		return
	if node is BaseButton:
		out.append(node)
	for c in node.get_children():
		_collect_buttons(c, out, depth - 1)


func _check_emergency_stop() -> void:
	# Ctrl+Shift+Q emergency stop
	if Input.is_key_pressed(KEY_Q) and Input.is_key_pressed(KEY_CONTROL) and Input.is_key_pressed(KEY_SHIFT):
		if active or auto_start_benchmark:
			active = false
			auto_start_benchmark = false
			_manual_override = true
			if _telem != null and _run_started:
				_telem.emit("error", {"kind": "emergency_stop"})
			if _learned != null:
				_learned.shutdown()
			if _hud != null:
				_hud.set_status("enabled", "EMERGENCY STOP")
			ModLoaderLog.info("Emergency stop engaged", LOG_NAME)

func _load_auto_config() -> void:
	# Optional user:// override for batch runner.
	var f = File.new()
	var p = "user://brotato_agent/agent_config.json"
	if f.open(p, File.READ) != OK:
		return
	var raw = f.get_as_text()
	f.close()
	var parsed = JSON.parse(raw)
	if parsed.error != OK or typeof(parsed.result) != TYPE_DICTIONARY:
		return
	var cfg = parsed.result
	if cfg.has("auto_start"):
		auto_start_benchmark = bool(cfg["auto_start"])
	if cfg.has("character") and _orch != null:
		_orch.target_character_id = str(cfg["character"])
	if cfg.has("danger") and _orch != null:
		_orch.target_danger = int(cfg["danger"])
	if cfg.has("student_enabled"):
		student_enabled = bool(cfg["student_enabled"])
	if cfg.has("student_port"):
		student_port = int(cfg["student_port"])
	if cfg.has("student_model_sha256"):
		student_model_sha256 = str(cfg["student_model_sha256"])
	if cfg.has("resume_from_save"):
		resume_from_save = bool(cfg["resume_from_save"])
	if cfg.has("finale_v2"):
		finale_v2 = bool(cfg["finale_v2"])
	if cfg.has("finale_rate_full"):
		finale_rate_full = bool(cfg["finale_rate_full"])
	if cfg.has("finale_no_panic"):
		finale_no_panic = bool(cfg["finale_no_panic"])
	if cfg.has("finale_heal_seek"):
		finale_heal_seek = bool(cfg["finale_heal_seek"])
	if cfg.has("finale_range_keep"):
		finale_range_keep = bool(cfg["finale_range_keep"])
	if cfg.has("finale_projectile_priority"):
		finale_projectile_priority = bool(cfg["finale_projectile_priority"])
	if cfg.has("time_scale"):
		time_scale = float(cfg["time_scale"])
	if cfg.has("headless_render"):
		headless_render = bool(cfg["headless_render"])
	if cfg.has("finale_scene_dump"):
		finale_scene_dump = bool(cfg["finale_scene_dump"])
	if cfg.has("finale_pivot_projectiles"):
		finale_pivot_projectiles = bool(cfg["finale_pivot_projectiles"])
	if cfg.has("finale_co_rotate"):
		finale_co_rotate = bool(cfg["finale_co_rotate"])
	if cfg.has("finale_ring_radius"):
		finale_ring_radius = bool(cfg["finale_ring_radius"])
	if cfg.has("engage_distance_scale"):
		engage_distance_scale = float(cfg["engage_distance_scale"])
	if cfg.has("calm_threat_mult"):
		calm_threat_mult = float(cfg["calm_threat_mult"])
	if cfg.has("tail_calm_penalty_mult"):
		tail_calm_penalty_mult = float(cfg["tail_calm_penalty_mult"])
	if cfg.has("tail_calm_clearance_mult"):
		tail_calm_clearance_mult = float(cfg["tail_calm_clearance_mult"])
	if cfg.has("rare_gun_lock_persist"):
		rare_gun_lock_persist = bool(cfg["rare_gun_lock_persist"])
	if cfg.has("human_movement"):
		human_movement = bool(cfg["human_movement"])
	if cfg.has("movement_estop_enabled"):
		movement_estop_enabled = bool(cfg["movement_estop_enabled"])

func _record_finale_range_sample(state) -> void:
	# Same state the controller already passed to the field: one source of truth
	# for the boss distance. No-op unless a boss is present on this tick.
	var bosses = state.get("bosses", [])
	if bosses.empty():
		return
	var player = state.get("player", {})
	if player.empty():
		return
	var pos = Vector2(player.get("x", 0.0), player.get("y", 0.0))
	var nearest = -1.0
	for b in bosses:
		var d = (Vector2(b.get("x", 0.0), b.get("y", 0.0)) - pos).length()
		if nearest < 0.0 or d < nearest:
			nearest = d
	if nearest < 0.0:
		return
	finale_boss_ticks += 1
	var shortest = -1.0
	var longest = -1.0
	for w in state.get("weapons", []):
		var r = float(w.get("max_range", 0))
		if r <= 0.0:
			continue
		if shortest < 0.0 or r < shortest:
			shortest = r
		if r > longest:
			longest = r
	if shortest > 0.0 and nearest <= shortest:
		finale_boss_in_short_range_ticks += 1
	if longest > 0.0 and nearest <= longest:
		finale_boss_in_long_range_ticks += 1


func _update_hud_phase(detected: String) -> void:
	if _hud == null:
		return
	_hud.set_status("phase", detected)
	_hud.set_status("wave", str(RunData.current_wave) if RunData != null else "?")
	_hud.set_status("enabled", str(active))
	if _telem != null:
		_hud.set_status("run_id", _telem.run_id)
	if _orch != null:
		_hud.set_status("recoveries", str(_orch.recovery_attempts))

func _track_damage(state: Dictionary) -> void:
	var hp = float(state.get("player", {}).get("hp", -1))
	if _last_hp >= 0 and hp >= 0 and hp < _last_hp and _telem != null:
		_telem.emit("player_damage", {"amount": _last_hp - hp, "hp": hp})
	_last_hp = hp

func _starting_weapon_id() -> String:
	var weapons = RunData.get_player_weapons(0)
	if weapons != null and weapons.size() > 0 and weapons[0] != null:
		return str(weapons[0].my_id)
	return ""
