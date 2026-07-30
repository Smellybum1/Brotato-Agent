extends Reference
# Phase FSM + bounded recovery for unattended benchmark runs.

const PHASES = [
	"BOOT", "MAIN_MENU", "CHARACTER_SELECT", "STARTING_WEAPON_SELECT",
	"DANGER_SELECT", "RUN_LOADING", "COMBAT", "CRATE_RESOLUTION",
	"LEVEL_UP", "SHOP", "VICTORY", "DEFEAT", "RECOVERY", "TERMINAL_ERROR"
]

var phase: String = "BOOT"
var prev_phase: String = "BOOT"
var stale_ticks: int = 0
var recovery_attempts: int = 0
var max_recovery_attempts: int = 12
var last_action_ms: int = 0
var last_move_ms: int = 0
var menu_action_cooldown_ms: int = 400
var _last_menu_action_ms: int = 0
var _last_watchdog_ms: int = 0
var watchdog_cooldown_ms: int = 30000

# Benchmark targets
var target_character_id: String = "character_well_rounded"
var target_weapon_prefixes: Array = ["weapon_smg", "weapon_stick"]
var target_danger: int = 0
var auto_start: bool = true
var reject_endless: bool = true
var reject_wave_retry: bool = true

signal phase_changed(from_phase, to_phase)
signal recovery(reason)
signal terminal(reason)

func reset() -> void:
	phase = "BOOT"
	prev_phase = "BOOT"
	stale_ticks = 0
	recovery_attempts = 0
	last_action_ms = OS.get_ticks_msec()
	last_move_ms = OS.get_ticks_msec()

func note_action() -> void:
	last_action_ms = OS.get_ticks_msec()
	stale_ticks = 0

func note_move() -> void:
	last_move_ms = OS.get_ticks_msec()
	stale_ticks = 0

func update_phase(detected: String) -> void:
	if detected == phase:
		stale_ticks += 1
		return
	prev_phase = phase
	phase = detected
	stale_ticks = 0
	emit_signal("phase_changed", prev_phase, phase)

func check_watchdogs(agent_active: bool, in_combat: bool, had_move: bool) -> String:
	var now = OS.get_ticks_msec()
	if not agent_active:
		return ""
	# Cooldown so soft stalls do not spam recovery / exhaust the budget.
	if now - _last_watchdog_ms < watchdog_cooldown_ms:
		return ""
	# Only treat BOOT as "no valid phase" — RECOVERY is a transient local state.
	if phase == "BOOT" and now - last_action_ms > 45000:
		_last_watchdog_ms = now
		return "no_valid_phase"
	# Standing still briefly is normal (shop-bound kite / force cancel). Soft only.
	if in_combat and not had_move and now - last_move_ms > 45000:
		_last_watchdog_ms = now
		return "no_movement_in_combat"
	if (phase == "SHOP" or phase == "LEVEL_UP" or phase == "CRATE_RESOLUTION") and now - last_action_ms > 45000:
		_last_watchdog_ms = now
		return "meta_screen_stalled"
	if phase == "MAIN_MENU" and prev_phase in ["COMBAT", "SHOP", "LEVEL_UP"] and now - last_action_ms > 10000:
		_last_watchdog_ms = now
		return "unexpected_main_menu"
	return ""

func begin_recovery(reason: String) -> bool:
	# Soft stalls are logged by the controller but must not burn the hard budget
	# or flip the FSM into RECOVERY. Hard faults previously aborted mid-combat and
	# left the agent unable to click through EndRun — breaking batch re-arm.
	var hard = reason in ["recovery_exhausted"]
	emit_signal("recovery", reason)
	note_action()
	if not hard:
		return true
	recovery_attempts += 1
	if recovery_attempts > max_recovery_attempts:
		emit_signal("terminal", "recovery_exhausted:" + reason)
		phase = "TERMINAL_ERROR"
		return false
	phase = "RECOVERY"
	return true

func try_menu_advance(scene, adapter) -> Dictionary:
	# Returns {acted: bool, detail: Dictionary}
	var now = OS.get_ticks_msec()
	if now - _last_menu_action_ms < menu_action_cooldown_ms:
		return {"acted": false}
	if scene == null:
		return {"acted": false}
	if not auto_start:
		return {"acted": false}

	match phase:
		"VICTORY", "DEFEAT":
			# 1.1.x death screen: dismiss Killed-by panel via OkButton first.
			if scene.has_method("_on_CancelButton_pressed"):
				var ok = _find_by_name(scene, "OkButton", 10)
				if ok != null and ok is BaseButton and ok.visible and not ok.disabled:
					ok.emit_signal("pressed")
					_last_menu_action_ms = now
					note_action()
					return {"acted": true, "detail": {"action": "end_run_ok"}}
				# Ok may already be gone; Cancel handler still advances some layouts.
			var r_ok = _click_named_button(scene, ["OkButton", "ConfirmButton"])
			if not r_ok:
				r_ok = _click_button_by_text(scene, ["ok", "okay"])
			if r_ok:
				_last_menu_action_ms = now
				note_action()
				return {"acted": true, "detail": {"action": "end_run_ok"}}
			# Prefer New Run so batch chaining skips the title screen. Never Retry.
			if scene.has_method("_on_NewRunButton_pressed"):
				scene._on_NewRunButton_pressed()
				_last_menu_action_ms = now
				note_action()
				return {"acted": true, "detail": {"action": "end_run_new_run"}}
			var r_end = _click_named_button(scene, ["NewRunButton", "ExitButton"])
			if not r_end:
				r_end = _click_button_by_text(scene, ["new run", "exit"])
			if r_end:
				_last_menu_action_ms = now
				note_action()
				return {"acted": true, "detail": {"action": "end_run_continue"}}
		"MAIN_MENU", "BOOT", "RECOVERY":
			# Prefer Start over Continue so mid-run saves do not resume a broken wave.
			var r = _click_named_button(scene, ["StartButton", "SoloButton", "NewRunButton", "ButtonStart"])
			if not r:
				r = _click_button_by_text(scene, ["solo", "start", "new run", "play"])
			if r:
				_last_menu_action_ms = now
				note_action()
				return {"acted": true, "detail": {"action": "main_menu_start"}}
		"CHARACTER_SELECT":
			var r2 = _select_inventory_by_id(scene, target_character_id)
			if r2:
				_last_menu_action_ms = now
				note_action()
				return {"acted": true, "detail": {"action": "select_character", "id": target_character_id}}
		"STARTING_WEAPON_SELECT":
			for pref in target_weapon_prefixes:
				var r3 = _select_inventory_by_id_prefix(scene, pref)
				if r3:
					_last_menu_action_ms = now
					note_action()
					return {"acted": true, "detail": {"action": "select_weapon", "prefix": pref}}
			# LAST RESORT. A character whose starting_weapons contains none of the
			# configured prefixes stalls here forever, because falling through
			# returns {"acted": false} and nothing else advances this screen.
			# Measured in the game data: arms_dealer offers ONLY weapon_pistol and
			# artificer only plank/screwdriver/wrench/shredder, so the defaults
			# (smg, stick) match neither. well_rounded matches both, which is why
			# every campaign so far ran clean and this stayed invisible.
			# Picking any weapon turns a dead unattended campaign into a run whose
			# actual weapon is recorded in the summary. Reported under its own
			# action name so the fallback is never silent.
			var r_any = _select_inventory_by_id_prefix(scene, "weapon_")
			if r_any:
				_last_menu_action_ms = now
				note_action()
				return {"acted": true, "detail": {"action": "select_weapon_fallback", "prefix": "weapon_"}}
		"DANGER_SELECT":
			# Difficulty extension handles bot activation + D0 click when auto.
			pass
		"TERMINAL_ERROR":
			# Still try to leave end/title screens so a later relaunch is not required.
			if scene.has_method("_on_NewRunButton_pressed"):
				scene._on_NewRunButton_pressed()
				_last_menu_action_ms = now
				note_action()
				return {"acted": true, "detail": {"action": "terminal_new_run"}}
			var r_t = _click_named_button(scene, ["NewRunButton", "ExitButton", "StartButton"])
			if r_t:
				_last_menu_action_ms = now
				note_action()
				return {"acted": true, "detail": {"action": "terminal_menu"}}
	return {"acted": false}

func enforce_settings() -> Dictionary:
	var changes = {}
	if ProgressData == null:
		return changes
	var settings = ProgressData.get("settings")
	if typeof(settings) != TYPE_DICTIONARY:
		return changes
	if reject_endless and settings.get("endless_mode_toggled", false):
		settings["endless_mode_toggled"] = false
		changes["endless"] = false
	if reject_wave_retry and settings.get("retry_wave", false):
		settings["retry_wave"] = false
		changes["wave_retry"] = false
	# Allow alt-tab / background batch without opening the pause menu.
	# 1.1.x uses Options > Audio > "On lost focus" dropdown (0=Do nothing).
	if settings.get("pause_on_focus_lost", true):
		settings["pause_on_focus_lost"] = false
		changes["pause_on_focus_lost"] = false
	if int(settings.get("on_lost_focus", 0)) != 0:
		settings["on_lost_focus"] = 0
		changes["on_lost_focus"] = 0
	# Keep difficulty multipliers at 100%/default if present
	if settings.has("enemy_scaling"):
		var es = settings["enemy_scaling"]
		if typeof(es) == TYPE_DICTIONARY:
			es["damage"] = 1
			es["health"] = 1
			es["speed"] = 1
			changes["enemy_scaling"] = es
	return changes

func _click_named_button(root: Node, names: Array) -> bool:
	for name in names:
		var n = _find_by_name(root, name, 10)
		if n != null and n.has_method("emit_signal"):
			if n is BaseButton and not n.disabled and n.visible:
				n.emit_signal("pressed")
				return true
	return false

func _click_button_by_text(root: Node, texts: Array) -> bool:
	var buttons = []
	_collect_buttons(root, buttons, 10)
	for b in buttons:
		if b == null or not (b is BaseButton) or b.disabled:
			continue
		var t = str(b.text).to_lower()
		for needle in texts:
			if t.find(needle) >= 0:
				b.emit_signal("pressed")
				return true
	return false

func _select_inventory_by_id(root: Node, item_id: String) -> bool:
	var els = []
	_collect_inventory_elements(root, els, 10)
	for el in els:
		if el == null or not ("item" in el) or el.item == null:
			continue
		var id = ""
		if "my_id" in el.item:
			id = str(el.item.my_id)
		if id == item_id:
			return _press_inventory_element(root, el)
	return false

func _select_inventory_by_id_prefix(root: Node, prefix: String) -> bool:
	var els = []
	_collect_inventory_elements(root, els, 10)
	for el in els:
		if el == null or not ("item" in el) or el.item == null:
			continue
		var id = ""
		if "my_id" in el.item:
			id = str(el.item.my_id)
		elif "weapon_id" in el.item:
			id = str(el.item.weapon_id)
		if id.begins_with(prefix) or id.find(prefix) >= 0:
			return _press_inventory_element(root, el)
	return false

func _press_inventory_element(scene, el) -> bool:
	# Prefer the scene's normal selection handler when available.
	if scene.has_method("_on_element_pressed"):
		scene._on_element_pressed(el, 0)
		return true
	if el.has_method("select"):
		el.select()
		return true
	if el is BaseButton:
		el.emit_signal("pressed")
		return true
	return false

func _collect_inventory_elements(node: Node, out: Array, depth: int) -> void:
	if node == null or depth < 0:
		return
	if "item" in node and node.get("item") != null:
		out.append(node)
	for c in node.get_children():
		_collect_inventory_elements(c, out, depth - 1)

func _collect_buttons(node: Node, out: Array, depth: int) -> void:
	if node == null or depth < 0:
		return
	if node is BaseButton:
		out.append(node)
	for c in node.get_children():
		_collect_buttons(c, out, depth - 1)

func _find_by_name(node: Node, target: String, depth: int) -> Node:
	if node == null or depth < 0:
		return null
	if str(node.name) == target:
		return node
	for c in node.get_children():
		var r = _find_by_name(c, target, depth - 1)
		if r != null:
			return r
	return null
