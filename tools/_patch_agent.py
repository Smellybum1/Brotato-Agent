from pathlib import Path
path = Path(r"C:\Codex\Brotato Agent\mod\mods-unpacked\Tom-BrotatoAgent\runtime\agent_controller.gd")
text = path.read_text(encoding="utf-8")

# Update header comment and add module preloads / state after current_move_vector
old = '''# Set by difficulty_selection_ext when the user clicks the robot button.
var active: bool = false
# Movement direction applied by player_movement_behavior_ext via the
# bot.current_move_vector path.
var current_move_vector: Vector2 = Vector2.ZERO

# Decision sub-systems (instantiated once). Use preload paths instead of
# class_name references so the script parses cleanly even before ModLoader
# has registered the mod's class_name table.
const _PROFILES_SCRIPT = preload("res://mods-unpacked/Tom-BrotatoAgent/teacher/build_profiles.gd")
const _SHOP_SCRIPT = preload("res://mods-unpacked/Tom-BrotatoAgent/teacher/shop_strategy.gd")
const _FIELD_SCRIPT = preload("res://mods-unpacked/Tom-BrotatoAgent/teacher/potential_field.gd")
var _profiles
var _shop
var _field
'''

new = '''# Activated by difficulty robot button / auto-start benchmark.
var active: bool = false
var auto_start_benchmark: bool = true
var current_move_vector: Vector2 = Vector2.ZERO
var policy_version: String = "teacher_v1-0.1.0-wp1"
var last_move_debug: Dictionary = {}
var last_meta_debug: Dictionary = {}
var _manual_override: bool = false
var _run_started: bool = false
var _last_hp: float = -1.0
var _combat_tick_counter: int = 0

const _PROFILES_SCRIPT = preload("res://mods-unpacked/Tom-BrotatoAgent/teacher/build_profiles.gd")
const _SHOP_SCRIPT = preload("res://mods-unpacked/Tom-BrotatoAgent/teacher/shop_strategy.gd")
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
'''

if old not in text:
    raise SystemExit('anchor1 not found')
text = text.replace(old, new, 1)

old_ready = '''func _ready() -> void:
	_profiles = _PROFILES_SCRIPT.new()
	_shop = _SHOP_SCRIPT.new()
	_field = _FIELD_SCRIPT.new()
	ModLoaderLog.info("BotRunner ready", LOG_NAME)
'''

new_ready = '''func _ready() -> void:
	_profiles = _PROFILES_SCRIPT.new()
	_shop = _SHOP_SCRIPT.new()
	_field = _FIELD_SCRIPT.new()
	_adapter = _ADAPTER_SCRIPT.new()
	_orch = _ORCH_SCRIPT.new()
	_telem = _TELEM_SCRIPT.new()
	_hud = _HUD_SCRIPT.new()
	add_child(_hud)
	_load_auto_config()
	ModLoaderLog.info("AgentController ready", LOG_NAME)
'''

if old_ready not in text:
    raise SystemExit('anchor ready not found')
text = text.replace(old_ready, new_ready, 1)

old_phys = '''func _physics_process(_delta: float) -> void:
	# PlayerMovementBehavior extension reads `current_move_vector` directly
	# (bypasses Input.action_press, which only supports unit-strength axis
	# components — diagonal moves stuttered). Just keep the vector updated.
	if not active:
		current_move_vector = Vector2.ZERO
		return
	var scene = get_tree().current_scene
	if scene == null: return
	if scene is Main:
		_handle_combat(scene)
		return
	if scene is BaseShop:
		current_move_vector = Vector2.ZERO
		_handle_shop(scene)
		return
	current_move_vector = Vector2.ZERO
	_handle_overlay(scene)
'''

new_phys = '''func _physics_process(_delta: float) -> void:
	_check_emergency_stop()
	var scene = get_tree().current_scene
	var detected = _adapter.detect_phase(scene) if _adapter != null else "BOOT"
	if _orch != null:
		_orch.update_phase(detected)
		_orch.enforce_settings()
		_update_hud_phase(detected)
		if detected in ["VICTORY", "DEFEAT"] and _run_started:
			_finish_run(detected)
		if not active and auto_start_benchmark and not _manual_override:
			# Drive menus until difficulty activation sets active=true.
			if detected in ["MAIN_MENU", "CHARACTER_SELECT", "STARTING_WEAPON_SELECT", "DANGER_SELECT"]:
				var adv = _orch.try_menu_advance(scene, _adapter)
				if adv.get("acted", false) and _telem != null and _run_started:
					_telem.emit("phase_transition", adv.get("detail", {}))
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
'''

if old_phys not in text:
    raise SystemExit('anchor phys not found')
text = text.replace(old_phys, new_phys, 1)

# Patch combat movement to use choose_movement API
old_move = '''	current_move_vector = _field.compute_movement(state, profile)
	# Drive overlays that can fire mid-wave (level-up / crate).
	_handle_overlay(main)
'''
new_move = '''	var mv = choose_movement(state)
	current_move_vector = mv.get("vector", Vector2.ZERO)
	last_move_debug = mv
	if _orch != null and current_move_vector.length() > 0.01:
		_orch.note_move()
	_combat_tick_counter += 1
	if _telem != null and _combat_tick_counter % 30 == 0:
		_telem.emit("combat_tick", {
			"wave": state.get("wave", 0),
			"move": {"x": current_move_vector.x, "y": current_move_vector.y},
			"debug": last_move_debug.get("debug", {}),
			"hp": state.get("player", {}).get("hp", 0),
		})
	_track_damage(state)
	if _hud != null:
		_hud.set_status("move", "(%.2f, %.2f)" % [current_move_vector.x, current_move_vector.y])
		_hud.set_status("build", profile.name if profile != null else "")
	# Drive overlays that can fire mid-wave (level-up / crate).
	_handle_overlay(main)
'''
if old_move not in text:
    raise SystemExit('anchor move not found')
text = text.replace(old_move, new_move, 1)

# Patch shop decide
old_shop = '''	var action: Dictionary = _shop.decide_shop(state, profile)
	if action.empty() or action.get("type", "") == "shop_go":
		_shop_go(shop)
	else:
		_apply_shop_action(shop, action)
	_last_shop_action_at = now
'''
new_shop = '''	var decision = choose_meta_action(state, state.get("legal_actions", []))
	var action: Dictionary = decision.get("action", {})
	last_meta_debug = decision
	if _telem != null:
		_telem.emit("purchase_offer", {"items": state.get("shop_items", []), "gold": state.get("gold", 0), "reroll_price": state.get("reroll_price", 0)})
		_telem.emit("purchase_decision", {
			"action": action,
			"score_breakdown": decision.get("score_breakdown", {}),
			"legal_alternatives": decision.get("legal_alternatives", []),
			"reason": decision.get("reason", ""),
		})
	if _hud != null:
		_hud.set_status("meta_action", "%s score=%s" % [action.get("type", ""), String(decision.get("score", 0))])
	if action.empty() or action.get("type", "") == "shop_go":
		_shop_go(shop)
	else:
		_apply_shop_action(shop, action)
	if _orch != null:
		_orch.note_action()
	_last_shop_action_at = now
'''
if old_shop not in text:
    raise SystemExit('anchor shop not found')
text = text.replace(old_shop, new_shop, 1)

# Append new methods at end
extra = r'''

# ───────────────────────── teacher API + agent lifecycle ─────────────────────

func choose_movement(combat_observation: Dictionary) -> Dictionary:
	var profile = _profiles.get_profile(combat_observation.get("character", ""))
	var vec: Vector2 = _field.compute_movement(combat_observation, profile)
	return {
		"vector": vec,
		"reason": "potential_field",
		"debug": {
			"profile": profile.name if profile != null else "",
			"enemies": combat_observation.get("enemies", []).size(),
			"projectiles": combat_observation.get("projectiles", []).size(),
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
	if _orch != null:
		_orch.target_danger = danger_value
		_orch.note_action()
	if not _run_started:
		_start_run()
	if _hud != null:
		_hud.set_status("enabled", "true")
		_hud.set_status("policy", policy_version)

func on_manual_override() -> void:
	_manual_override = true
	active = false
	if _telem != null and _run_started:
		_telem.emit("error", {"kind": "manual_override"})
	if _hud != null:
		_hud.set_status("enabled", "false (manual override)")

func _start_run() -> void:
	_run_started = true
	_combat_tick_counter = 0
	_last_hp = -1.0
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
		"mod_version": "0.1.0-wp1",
		"config_id": "well_rounded_d0_smg",
		"policy_version": policy_version,
	}
	if _telem != null:
		_telem.begin_run(meta)
	if _hud != null:
		_hud.set_status("run_id", meta["run_id"])
		_hud.set_status("enabled", "true")
		_hud.set_status("policy", policy_version)

func _finish_run(result_phase: String) -> void:
	if not _run_started:
		return
	var result = "victory" if result_phase == "VICTORY" else "defeat"
	if _telem != null:
		_telem.end_run(result, {"last_wave": RunData.current_wave, "waves_completed": RunData.current_wave})
	_run_started = false
	active = false
	# Prepare for next batch run if auto_start remains enabled.
	if auto_start_benchmark and not _manual_override:
		# Soft re-arm after short delay via stale menu navigation.
		pass

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
		_orch.target_character_id = String(cfg["character"])
	if cfg.has("danger") and _orch != null:
		_orch.target_danger = int(cfg["danger"])

func _update_hud_phase(detected: String) -> void:
	if _hud == null:
		return
	_hud.set_status("phase", detected)
	_hud.set_status("wave", String(RunData.current_wave) if RunData != null else "?")
	_hud.set_status("enabled", String(active))
	if _telem != null:
		_hud.set_status("run_id", _telem.run_id)
	if _orch != null:
		_hud.set_status("recoveries", String(_orch.recovery_attempts))

func _track_damage(state: Dictionary) -> void:
	var hp = float(state.get("player", {}).get("hp", -1))
	if _last_hp >= 0 and hp >= 0 and hp < _last_hp and _telem != null:
		_telem.emit("player_damage", {"amount": _last_hp - hp, "hp": hp})
	_last_hp = hp

func _starting_weapon_id() -> String:
	var weapons = RunData.get_player_weapons(0)
	if weapons != null and weapons.size() > 0 and weapons[0] != null:
		return String(weapons[0].my_id)
	return ""
'''

# Also instrument level-up and crate decisions lightly
old_lu = '''	var action: Dictionary = _shop.decide_levelup(state, profile)
	match action.get("type", ""):
'''
new_lu = '''	var decision = choose_meta_action({"phase": "LEVEL_UP", "character": _character_id(), "options": options, "wave": RunData.current_wave, "gold": RunData.get_player_gold(0), "reroll_price": 0, "reroll_count": 0, "build": _build_dict()}, options)
	var action: Dictionary = decision.get("action", {})
	if _telem != null:
		_telem.emit("level_up_offer", {"options": options})
		_telem.emit("level_up_decision", {"action": action, "score_breakdown": decision.get("score_breakdown", {}), "legal_alternatives": options})
	if _orch != null:
		_orch.note_action()
	match action.get("type", ""):
'''
if old_lu not in text:
    raise SystemExit('anchor levelup not found')
text = text.replace(old_lu, new_lu, 1)

old_crate = '''	var action: Dictionary = _shop.decide_crate(state, profile)
	if action.get("type", "") == "crate_take" and pc.has_method("_on_TakeButton_pressed"):
'''
new_crate = '''	var decision = choose_meta_action({"phase": "CRATE_RESOLUTION", "character": _character_id(), "item": item, "wave": RunData.current_wave, "build": _build_dict()}, ["crate_take", "crate_discard"])
	var action: Dictionary = decision.get("action", {})
	if _telem != null:
		_telem.emit("crate_offer", {"item": item})
		_telem.emit("crate_decision", {"action": action, "score_breakdown": decision.get("score_breakdown", {}), "legal_alternatives": ["crate_take", "crate_discard"]})
	if _orch != null:
		_orch.note_action()
	if action.get("type", "") == "crate_take" and pc.has_method("_on_TakeButton_pressed"):
'''
if old_crate not in text:
    raise SystemExit('anchor crate not found')
text = text.replace(old_crate, new_crate, 1)

# Shop gather should include legal_actions via adapter-like fields
old_shop_ret = '''	state["shop_items"] = items
	state["build"] = _build_dict()
	return state
'''
new_shop_ret = '''	state["shop_items"] = items
	state["build"] = _build_dict()
	var legal = ["shop_go", "shop_reroll"]
	for it in items:
		legal.append({"type": "shop_buy", "slot": it.slot})
		legal.append({"type": "shop_lock" if not it.locked else "shop_unlock", "slot": it.slot})
	state["legal_actions"] = legal
	return state
'''
if old_shop_ret not in text:
    raise SystemExit('anchor shop_ret not found')
text = text.replace(old_shop_ret, new_shop_ret, 1)

path.write_text(text + extra, encoding="utf-8")
print("agent_controller patched, bytes", path.stat().st_size)
