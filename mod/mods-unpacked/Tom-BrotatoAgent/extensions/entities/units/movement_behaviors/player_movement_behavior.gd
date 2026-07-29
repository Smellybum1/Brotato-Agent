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
	if human.length() > 0.05:
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
