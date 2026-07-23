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
var current_move_vector: Vector2 = Vector2.ZERO
var policy_version: String = "teacher_v1-0.1.122-gun-wp1"
var last_move_debug: Dictionary = {}
var last_meta_debug: Dictionary = {}
var _manual_override: bool = false
var _run_started: bool = false
var _last_hp: float = -1.0
var _last_known_max_hp: float = -1.0
var _combat_tick_counter: int = 0
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
const _WP2_CAPTURE_SCHEMA_HASH := "95B6444796A21FD44E94113B75BA2097BC381D5F72ED784F9B9A4A99DD46D951"
const _WP2_CAPTURE_DIVISOR := 3 # 60 Hz physics / 3 = 20 capture decisions per second.

const _PROFILES_SCRIPT = preload("res://mods-unpacked/Tom-BrotatoAgent/teacher/build_profiles.gd")
const _SHOP_SCRIPT = preload("res://mods-unpacked/Tom-BrotatoAgent/teacher/shop_strategy.gd")
const _CONFIG_SCRIPT = preload("res://mods-unpacked/Tom-BrotatoAgent/teacher/config.gd")
const _COMBAT_MODEL_SCRIPT = preload("res://mods-unpacked/Tom-BrotatoAgent/teacher/combat_model.gd")
const _FIELD_SCRIPT = preload("res://mods-unpacked/Tom-BrotatoAgent/teacher/potential_field.gd")
const _ADAPTER_SCRIPT = preload("res://mods-unpacked/Tom-BrotatoAgent/adapter/game_adapter.gd")
const _ORCH_SCRIPT = preload("res://mods-unpacked/Tom-BrotatoAgent/orchestrator/run_orchestrator.gd")
const _TELEM_SCRIPT = preload("res://mods-unpacked/Tom-BrotatoAgent/telemetry/telemetry_writer.gd")
const _HUD_SCRIPT = preload("res://mods-unpacked/Tom-BrotatoAgent/ui/agent_hud.gd")
var _profiles
var _shop
var _field
var _adapter
var _orch
var _telem
var _hud

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
	_load_batch_stats()
	_refresh_batch_hud()
	ModLoaderLog.info("AgentController ready", LOG_NAME)


func _physics_process(_delta: float) -> void:
	_check_emergency_stop()
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
		recompute_move = (_finale_move_tick % _CONFIG_SCRIPT.BOSS_FINALE_RECOMPUTE_DIVISOR) == 1
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
	if wave >= _CONFIG_SCRIPT.BOSS_FINALE_WAVE:
		emit_capture = recompute_move
	if emit_capture:
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
		_update_build_metrics_hud(build_metrics)
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


func _emit_wp2_combat_capture(main, state: Dictionary, teacher_action_fresh: bool) -> void:
	if _telem == null or not _telem.has_method("emit_versioned"):
		return
	var player: Dictionary = state.get("player", {})
	if player.empty():
		return
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
		"entities": {
			"enemies": state.get("enemies", []),
			"bosses": state.get("bosses", []),
			"projectiles": state.get("projectiles", []),
			"materials": state.get("loot", []),
			"consumables": consumables,
			"crates": crates,
			"obstacles": state.get("trees", []),
		},
		"weapons": state.get("weapons", []),
		"arena": state.get("arena", {}),
		"invalid_counts": state.get("invalid_entities", {}),
		"dropped_counts": {
			"enemies": 0, "bosses": 0, "projectiles": 0, "materials": 0,
			"consumables": 0, "crates": 0, "obstacles": 0,
		},
	}
	payload["player"]["measured_vx"] = measured_velocity.x
	payload["player"]["measured_vy"] = measured_velocity.y
	_telem.emit_versioned("combat_capture", payload, _WP2_CAPTURE_SCHEMA_VERSION)
	_wp2_previous_action = current_move_vector
	_wp2_last_capture_player_pos = player_pos
	_wp2_last_capture_ts_ms = now_ms


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
			loot.append(_pickup_snapshot(item, "material", ""))
		return loot
	var items = main.get_node_or_null("Items")
	if items == null:
		items = main.get_node_or_null("%Materials")
	if items:
		for item in items.get_children():
			if not is_instance_valid(item) or not item.visible:
				continue
			loot.append(_pickup_snapshot(item, "material", ""))
	return loot


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
	return {
		"weapons": weapons,
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
	return {
		"vector": vec,
		"reason": "potential_field",
		"debug": {
			"profile": profile.name if profile != null else "",
			"enemies": combat_observation.get("enemies", []).size(),
			"projectiles": combat_observation.get("projectiles", []).size(),
			"finale_translation": translation_debug,
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

func on_benchmark_activated(danger_value: int) -> void:
	active = true
	_manual_override = false
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

func on_manual_override() -> void:
	_restore_pre_combine_mouse_mode()
	_manual_override = true
	active = false
	if _telem != null and _run_started:
		_telem.emit("error", {"kind": "manual_override"})
	if _hud != null:
		_hud.set_status("enabled", "false (manual override)")

func _start_run() -> void:
	_run_started = true
	_combat_tick_counter = 0
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
		"danger": 0,
		"endless": false,
		"wave_retry": false,
		"game_version": "1.1.15.4",
		"mod_version": "0.2.30-wp2-capture",
		"config_id": "well_rounded_d0_anyranged",
		"policy_version": policy_version,
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
		_telem.end_run(result, {"last_wave": RunData.current_wave, "waves_completed": RunData.current_wave})
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
			_telem.end_run("automation_fault", {"failure_category": reason, "last_wave": RunData.current_wave})
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
