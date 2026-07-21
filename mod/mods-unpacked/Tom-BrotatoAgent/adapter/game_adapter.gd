extends Reference
# Stable versioned game-state snapshot for Tom-BrotatoAgent (instrumented track).

const SCHEMA_VERSION := "1.0.0"

const _STAT_NAMES = [
	"max_hp", "armor", "dodge", "speed", "hp_regeneration", "lifesteal",
	"crit_chance", "crit_damage", "attack_speed", "percent_damage", "damage",
	"ranged_damage", "melee_damage", "elemental_damage", "range",
	"harvesting", "engineering", "luck",
]

func detect_phase(scene) -> String:
	if scene == null:
		return "BOOT"
	var n = str(scene.name).to_lower()
	var cn = scene.get_class().to_lower() if scene.has_method("get_class") else ""
	if scene is Main:
		# Death/victory banners stay on Main until EndWaveTimer flips to EndRun.
		if bool(scene.get("_is_run_lost")):
			return "DEFEAT"
		if bool(scene.get("_is_run_won")):
			return "VICTORY"
		var ui = _get_upgrades_ui(scene)
		if ui != null and ui.visible:
			var pc = ui._get_player_container(0) if ui.has_method("_get_player_container") else null
			if pc != null and pc.visible:
				if "_items_container" in pc and pc._items_container != null and pc._items_container.visible:
					return "CRATE_RESOLUTION"
				return "LEVEL_UP"
		return "COMBAT"
	if scene is BaseShop:
		return "SHOP"
	if n.find("character") >= 0 or cn.find("character") >= 0:
		return "CHARACTER_SELECT"
	if n.find("weapon") >= 0 or cn.find("weapon") >= 0:
		return "STARTING_WEAPON_SELECT"
	if n.find("difficulty") >= 0 or cn.find("difficulty") >= 0:
		return "DANGER_SELECT"
	# TitleScreen is the real boot scene; MainMenu is a child Control inside it.
	if (
		n.find("titlescreen") >= 0 or cn.find("titlescreen") >= 0
		or n.find("title_screen") >= 0
		or n.find("mainmenu") >= 0 or n.find("main_menu") >= 0 or cn.find("mainmenu") >= 0
	):
		return "MAIN_MENU"
	if n.find("endrun") >= 0 or cn.find("endrun") >= 0 or n.find("end_run") >= 0:
		return "VICTORY" if _looks_like_victory(scene) else "DEFEAT"
	if n.find("end") >= 0 or n.find("victory") >= 0 or n.find("defeat") >= 0 or n.find("game_over") >= 0:
		if n.find("victory") >= 0 or n.find("win") >= 0:
			return "VICTORY"
		if n.find("defeat") >= 0 or n.find("lose") >= 0 or n.find("death") >= 0:
			return "DEFEAT"
		return "VICTORY" if _looks_like_victory(scene) else "DEFEAT"
	return "RECOVERY"

func snapshot_combat(main) -> Dictionary:
	var state = {
		"schema_version": SCHEMA_VERSION,
		"phase": "COMBAT",
		"wave": RunData.current_wave,
		"character": _character_id(),
		"danger": _danger(),
		"endless": _endless_enabled(),
		"wave_retry": _wave_retry_enabled(),
	}
	var es = main.get_node_or_null("EntitySpawner")
	if es == null:
		return state
	var players = []
	for p in es._players:
		if not is_instance_valid(p) or p.dead:
			continue
		players.append({
			"x": p.global_position.x, "y": p.global_position.y,
			"hp": p.current_stats.health, "max_hp": p.max_stats.health,
			"speed": p.max_stats.speed,
		})
	state["players"] = players
	if not players.empty():
		state["player"] = players[0]
	var enemies = []
	for e in es.enemies:
		if not is_instance_valid(e) or e.dead:
			continue
		enemies.append({"x": e.global_position.x, "y": e.global_position.y,
			"hp": e.current_stats.health, "speed": e.current_stats.speed})
	state["enemies"] = enemies
	var bosses = []
	for b in es.bosses:
		if not is_instance_valid(b) or b.dead:
			continue
		bosses.append({"x": b.global_position.x, "y": b.global_position.y,
			"hp": b.current_stats.health, "max_hp": b.max_stats.health,
			"speed": b.current_stats.speed, "name": str(b.name)})
	state["bosses"] = bosses
	var projs = []
	var projs_node = main.get_node_or_null("Projectiles")
	if projs_node == null:
		projs_node = main.get_node_or_null("%EnemyProjectiles")
	if projs_node:
		for proj in projs_node.get_children():
			if not is_instance_valid(proj) or not proj.visible:
				continue
			if not ("global_position" in proj):
				continue
			var vel = Vector2.ZERO
			if "velocity" in proj:
				vel = proj.velocity
			projs.append({"x": proj.global_position.x, "y": proj.global_position.y, "vx": vel.x, "vy": vel.y})
	state["projectiles"] = projs
	var loot = _collect_loot(main)
	state["loot"] = loot
	state["materials"] = loot
	state["consumables"] = _collect_consumables(main)
	var weapons = []
	for w in RunData.get_player_weapons(0):
		if w == null or w.stats == null:
			continue
		weapons.append({
			"type": "ranged" if w.type == 1 else "melee",
			"max_range": w.stats.max_range,
			"damage": w.stats.damage,
			"cooldown": w.stats.cooldown,
			"id": w.my_id if "my_id" in w else "",
		})
	state["weapons"] = weapons
	state["can_attack_while_moving"] = RunData.get_player_effect(Keys.can_attack_while_moving_hash, 0) > 0
	var zone_data = _get_current_zone_data()
	if zone_data:
		state["arena"] = {"width": zone_data.width * 64, "height": zone_data.height * 64}
	else:
		state["arena"] = {"width": 2048, "height": 1536}
	# Normalize only after every entity list exists. The old call ran immediately
	# after the player snapshot, so enemies, bosses, and projectiles never gained
	# the documented player-relative nx/ny fields.
	_normalize_player_relative(state)
	state["legal_actions"] = ["move"]
	return state

func snapshot_shop(shop) -> Dictionary:
	var gold: int = RunData.get_player_gold(0)
	var state = {
		"schema_version": SCHEMA_VERSION,
		"phase": "SHOP",
		"wave": RunData.current_wave,
		"gold": gold,
		"character": _character_id(),
		"danger": _danger(),
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
			if node == null or not node.active or node.item_data == null:
				continue
			var data = node.item_data
			var entry = {
				"slot": i, "id": data.my_id, "price": node.value, "tier": data.tier,
				"category": "weapon" if data is WeaponData else "item",
				"affordable": gold >= node.value, "locked": node.locked,
				"effects": _effects_to_list(data.effects),
				"tags": data.tags if "tags" in data and data.tags != null else [],
			}
			if data is WeaponData:
				entry["weapon_type"] = "ranged" if data.type == 1 else "melee"
				entry["weapon_id"] = data.weapon_id
			items.append(entry)
	state["shop_items"] = items
	state["legal_actions"] = _shop_legal_actions(state)
	return state

func _shop_legal_actions(state: Dictionary) -> Array:
	var acts = ["shop_go", "shop_reroll"]
	for it in state.get("shop_items", []):
		acts.append({"type": "shop_buy", "slot": it.slot})
		acts.append({"type": "shop_lock" if not it.locked else "shop_unlock", "slot": it.slot})
	return acts

func _normalize_player_relative(state: Dictionary) -> void:
	var p = state.get("player", {})
	if p.empty():
		return
	var px = float(p.get("x", 0))
	var py = float(p.get("y", 0))
	for key in ["enemies", "bosses", "projectiles", "loot", "materials", "consumables"]:
		if not state.has(key):
			continue
		for e in state[key]:
			e["nx"] = float(e.get("x", 0)) - px
			e["ny"] = float(e.get("y", 0)) - py

func _character_id() -> String:
	var c = RunData.get_player_character(0)
	return c.my_id if c != null else ""

func _danger() -> int:
	# Avoid `"prop" in RunData` — Godot 3 rejects that for some autoload types.
	if RunData == null:
		return -1
	if RunData.get("current_difficulty") != null:
		return int(RunData.current_difficulty)
	if RunData.get("difficulty") != null:
		return int(RunData.difficulty)
	return -1

func _endless_enabled() -> bool:
	if ProgressData == null:
		return false
	var settings = ProgressData.get("settings")
	if typeof(settings) != TYPE_DICTIONARY:
		return false
	return bool(settings.get("endless_mode_toggled", false))

func _wave_retry_enabled() -> bool:
	if ProgressData == null:
		return false
	var settings = ProgressData.get("settings")
	if typeof(settings) != TYPE_DICTIONARY:
		return false
	return bool(settings.get("retry_wave", false))

func _get_current_zone_data():
	for zone in ZoneService.zones:
		if zone.my_id == RunData.current_zone:
			return zone
	if ZoneService.zones.size() > 0:
		return ZoneService.zones[0]
	return null

func _get_upgrades_ui(scene):
	if "_upgrades_ui" in scene:
		return scene._upgrades_ui
	if scene.has_method("get_node_or_null"):
		return scene.get_node_or_null("%UpgradesUI")
	return null

func _effects_to_list(effects) -> Array:
	var out = []
	if effects == null:
		return out
	for e in effects:
		if e == null:
			continue
		var entry = {"key": "", "value": 0, "sign": 3}
		if "key" in e:
			entry["key"] = e.key
		if "value" in e:
			entry["value"] = e.value
		if "effect_sign" in e:
			entry["sign"] = e.effect_sign
		out.append(entry)
	return out

func _looks_like_victory(scene) -> bool:
	if RunData != null:
		var won = RunData.get("run_won")
		if won != null:
			return bool(won)
	var wave = RunData.current_wave if RunData != null else 0
	return wave >= 20

func _collect_loot(main) -> Array:
	var loot = []
	var golds = main.get("_golds")
	if typeof(golds) == TYPE_ARRAY:
		for item in golds:
			if not is_instance_valid(item):
				continue
			if ("visible" in item) and not item.visible:
				continue
			loot.append({"x": item.global_position.x, "y": item.global_position.y})
		return loot
	var items = main.get_node_or_null("Items")
	if items == null:
		items = main.get_node_or_null("%Materials")
	if items:
		for item in items.get_children():
			if not is_instance_valid(item) or not item.visible:
				continue
			loot.append({"x": item.global_position.x, "y": item.global_position.y})
	return loot

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
			cons.append({"x": c.global_position.x, "y": c.global_position.y, "id": id})
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
			cons.append({"x": c.global_position.x, "y": c.global_position.y, "id": id2})
	return cons
