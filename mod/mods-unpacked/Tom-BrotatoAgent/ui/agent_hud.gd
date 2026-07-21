extends CanvasLayer
# Diagnostic HUD. Toggle with F10. Does not capture mouse when hidden.

var visible_hud: bool = true
var _label: Label
var lines: Dictionary = {}

func _ready() -> void:
	layer = 100
	pause_mode = Node.PAUSE_MODE_PROCESS
	_label = Label.new()
	_label.name = "AgentHudLabel"
	_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	# Keep diagnostics in a bounded bottom-left viewport column. Autowrap
	# prevents long metric lines from expanding Label's content minimum past
	# the screen, while bottom alignment makes additional rows grow upward.
	_label.rect_min_size = Vector2(0, 340)
	_label.anchor_left = 0.0
	_label.anchor_right = 0.62
	_label.anchor_top = 0.0
	_label.anchor_bottom = 1.0
	_label.margin_left = 12
	_label.margin_right = -12
	_label.margin_top = 12
	_label.margin_bottom = -12
	_label.align = Label.ALIGN_LEFT
	_label.valign = Label.VALIGN_BOTTOM
	_label.autowrap = true
	_label.clip_text = true
	_label.add_color_override("font_color", Color(0.85, 1.0, 0.85, 0.95))
	add_child(_label)
	set_process_input(true)
	_refresh()

func _input(event) -> void:
	if event is InputEventKey and event.pressed and not event.echo:
		if event.scancode == KEY_F10:
			visible_hud = not visible_hud
			_label.visible = visible_hud

func set_status(key: String, value) -> void:
	lines[key] = value
	if visible_hud:
		_refresh()

func _refresh() -> void:
	if _label == null:
		return
	_label.visible = visible_hud
	if not visible_hud:
		return
	var order = [
		"enabled", "phase", "wave", "record", "mode", "hp", "enemies", "bosses",
		"loot", "consumables", "offense", "offense_values", "offense_weapons", "defense",
		"defense_values", "defense_sustain", "off_dps", "def_ehp", "rsi",
		"policy", "move", "build", "last_buy", "meta_action",
		"watchdog", "run_id", "recoveries"
	]
	var text = "BrotatoAgent HUD (F10 toggle)\n"
	for k in order:
		if lines.has(k):
			text += "%s: %s\n" % [k, str(lines[k])]
	_label.text = text
