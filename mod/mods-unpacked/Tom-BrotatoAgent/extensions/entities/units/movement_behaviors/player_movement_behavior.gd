extends "res://entities/units/movement_behaviors/player_movement_behavior.gd"

# Movement handoff to BotRunner. Manual input disables agent for the run.
# Emergency stop: hold Ctrl+Shift+Q also disables.

var _bot_runner_cache: Node = null

func get_movement() -> Vector2:
	var human: Vector2 = .get_movement()
	var runner := _get_bot_runner()
	if runner == null or not runner.get("active"):
		return human
	# Movement-only handover (dev instrument). The agent stays ACTIVE -- it keeps
	# shop, level-up, capture and telemetry control -- and only the movement
	# vector comes from the keyboard. Without this branch the E-stop below fires
	# on the first keypress and disables the agent for the whole run, handing
	# over shopping too and confounding a movement comparison with a build one.
	#
	# `get()` on an absent property returns null in Godot 3, so an older runner
	# without this flag falls through to the unchanged path rather than erroring.
	if runner.get("human_movement"):
		# `human` IS the keyboard vector. Log it as the real behaviour-cloning
		# label -- teacher.action is the AGENT's intended vector on this arm.
		# Guarded exactly like on_manual_override below so an older runner
		# without the method falls through instead of erroring.
		if runner.has_method("note_human_movement"):
			runner.note_human_movement(human)
		return human
	# CAMPAIGN MODE. The E-stop below is a hair trigger: the movement actions bind
	# Q/A/W/Z/S/D and the arrows (project.godot move_*_keyboard_only), so whenever
	# the game window holds focus, ordinary typing reads as movement and ends the
	# run. That destroyed 2 of 12 attempts of the D5 baseline on 2026-07-30.
	# With movement_estop_enabled false, movement input is ignored here and only
	# the explicit Ctrl+Shift+Q stop (agent_controller._check_emergency_stop) ends
	# the run.
	#
	# FAIL SAFE: `get()` on an absent property returns null in Godot 3 and
	# `null == false` is false, so an older runner -- or any failure to plumb the
	# flag through -- falls through to the unchanged E-stop path. A missing config
	# must never silently disable a safety mechanism.
	var estop_off: bool = runner.get("movement_estop_enabled") == false
	if estop_off and runner.has_method("note_movement_estop"):
		runner.note_movement_estop(human.length() > 0.05)
	if human.length() > 0.05:
		if estop_off:
			return runner.current_move_vector
		runner.set("active", false)
		if runner.has_method("on_manual_override"):
			runner.on_manual_override()
		return human
	return runner.current_move_vector

func _get_bot_runner() -> Node:
	if _bot_runner_cache != null and is_instance_valid(_bot_runner_cache):
		return _bot_runner_cache
	var root := get_tree().get_root()
	var r = root.get_node_or_null("ModLoader/Tom-BrotatoAgent/BotRunner")
	if r != null:
		_bot_runner_cache = r
		return r
	return _find_runner_recursive(root, 4)

func _find_runner_recursive(node: Node, depth: int) -> Node:
	if node == null or depth < 0:
		return null
	if node.name == "BotRunner":
		_bot_runner_cache = node
		return node
	for c in node.get_children():
		var r = _find_runner_recursive(c, depth - 1)
		if r != null:
			return r
	return null
