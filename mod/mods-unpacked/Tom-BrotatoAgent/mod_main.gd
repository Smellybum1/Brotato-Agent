extends Node

# Tom-BrotatoAgent entry point. Derived from BlackTriangle Full Auto Bot (GPL-3.0).
# Spawns AgentController and installs script extensions.

const LOG_NAME := "Tom:BrotatoAgent"
const _AGENT_SCRIPT := preload("res://mods-unpacked/Tom-BrotatoAgent/runtime/agent_controller.gd")

func _init():
	ModLoaderLog.info("Init", LOG_NAME)
	ModLoaderMod.install_script_extension(
		"res://mods-unpacked/Tom-BrotatoAgent/extensions/ui/menus/run/difficulty_selection/difficulty_selection.gd"
	)
	ModLoaderMod.install_script_extension(
		"res://mods-unpacked/Tom-BrotatoAgent/extensions/entities/units/movement_behaviors/player_movement_behavior.gd"
	)

func _ready():
	ModLoaderLog.info("Ready", LOG_NAME)
	var agent = _AGENT_SCRIPT.new()
	agent.name = "BotRunner"
	add_child(agent)
