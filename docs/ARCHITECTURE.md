# Architecture

## Overview

```text
Brotato + ModLoader
        |
        v
+-------------------------+
| GameAdapter             |  exact state + legal actions
+------------+------------+
             |
             v
+-------------------------+
| RunOrchestrator         |  phase FSM + watchdog + menu advance
+-----+---------------+---+
      |               |
      v               v
+-----------+   +-------------------+
| Teacher   |   | Teacher meta      |
| movement  |   | shop/level/crate  |
+-----+-----+   +---------+---------+
      |                   |
      +---------+---------+
                v
       +------------------+
       | AgentController  |  action exec + HUD + emergency stop
       +--------+---------+
                v
       +------------------+
       | TelemetryWriter  |  JSONL + summary
       +------------------+
```

## Modules (`mod/mods-unpacked/Tom-BrotatoAgent`)

| Path | Role |
|------|------|
| `mod_main.gd` | ModLoader entry; installs extensions; spawns `BotRunner` |
| `runtime/agent_controller.gd` | Main loop; teacher APIs; lifecycle |
| `adapter/game_adapter.gd` | Phase detect + versioned snapshots |
| `orchestrator/run_orchestrator.gd` | FSM, watchdogs, menu heuristics |
| `teacher/*` | GPL-derived deterministic teacher (full-autobot port) |
| `telemetry/telemetry_writer.gd` | Append-only JSONL under `user://brotato_agent/` |
| `ui/agent_hud.gd` | F10 toggle diagnostics |
| `extensions/.../difficulty_selection.gd` | Robot button → Danger 0 + activate |
| `extensions/.../player_movement_behavior.gd` | Apply move vector; manual override |

## Phase state machine

`BOOT → MAIN_MENU → CHARACTER_SELECT → STARTING_WEAPON_SELECT → DANGER_SELECT → RUN_LOADING → COMBAT ⇄ (CRATE|LEVEL_UP) → SHOP → … → VICTORY|DEFEAT`

Recovery and `TERMINAL_ERROR` are bounded; never infinite loops.

## Teacher APIs

```text
choose_movement(combat_observation) -> {vector, reason, debug}
choose_meta_action(run_observation, legal_actions) -> {action, score, score_breakdown, reason}
```

## Safeguards

- No overwrite of original game files beyond reversible `mods-unpacked` + profile
- Endless / wave-retry rejected by orchestrator
- Emergency stop: Ctrl+Shift+Q
- Manual override: any movement key
