extends "res://ui/menus/run/difficulty_selection/difficulty_selection.gd"

# Benchmark activation: robot button starts D0 (not upstream D6).
# Auto-start mode selects D0 without requiring a click when agent requests it.

const _ICON_PATH := "res://mods-unpacked/Tom-BrotatoAgent/assets/bot_button.png"
const LOG_NAME := "Tom:BrotatoAgent:Difficulty"

var _auto_attempted: bool = false

func _ready() -> void:
	._ready()
	_install_bot_button()
	# Defer auto-start so inventory elements exist.
	call_deferred("_maybe_auto_start")

func _install_bot_button() -> void:
	if _inventory1 == null:
		return
	if _inventory1.has_node("BotAutoplayButton"):
		return
	var btn := Button.new()
	btn.name = "BotAutoplayButton"
	btn.rect_min_size = Vector2(96, 96)
	btn.icon_align = Button.ALIGN_CENTER
	btn.expand_icon = true
	var tex := _load_icon()
	if tex != null:
		btn.icon = tex
	btn.mouse_filter = Control.MOUSE_FILTER_STOP
	btn.focus_mode = Control.FOCUS_ALL
	btn.connect("pressed", self, "_on_bot_button_pressed")
	_inventory1.add_child(btn)

func _load_icon() -> Texture:
	var tex: Texture = load(_ICON_PATH) as Texture
	if tex != null:
		return tex
	var f := File.new()
	if f.open(_ICON_PATH, File.READ) == OK:
		var buf := f.get_buffer(f.get_len())
		f.close()
		var img := Image.new()
		if img.load_png_from_buffer(buf) == OK:
			var itex := ImageTexture.new()
			itex.create_from_image(img, 0)
			return itex
	return null

func _on_bot_button_pressed() -> void:
	_activate_and_select_danger(0)

func _maybe_auto_start() -> void:
	if _auto_attempted or difficulty_selected:
		return
	var runner = _find_bot_runner()
	if runner == null:
		return
	# Auto when agent flag set (batch / config).
	if runner.get("auto_start_benchmark") == true and runner.get("active") != true:
		_auto_attempted = true
		_activate_and_select_danger(0)

func _activate_and_select_danger(danger_value: int) -> void:
	if difficulty_selected:
		return
	var runner = _find_bot_runner()
	if runner != null:
		runner.set("active", true)
		if runner.has_method("on_benchmark_activated"):
			runner.on_benchmark_activated(danger_value)
	else:
		printerr("[%s] BotRunner not found" % LOG_NAME)
	var el = _find_difficulty_element(danger_value)
	if el != null:
		_on_element_pressed(el, 0)

func _find_bot_runner() -> Node:
	var root := get_tree().get_root()
	var r = root.get_node_or_null("ModLoader/Tom-BrotatoAgent/BotRunner")
	if r != null:
		return r
	return _find_node_by_name(root, "BotRunner", 4)

func _find_node_by_name(node: Node, target: String, depth: int) -> Node:
	if node == null or depth < 0:
		return null
	if node.name == target:
		return node
	for c in node.get_children():
		var r = _find_node_by_name(c, target, depth - 1)
		if r != null:
			return r
	return null

func _find_difficulty_element(value: int):
	if _inventory1 == null:
		return null
	for el in _inventory1.get_children():
		if el != null and "item" in el and el.item != null and el.item.value == value:
			return el
	return null
