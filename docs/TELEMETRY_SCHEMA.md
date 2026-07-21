# Telemetry Schema (v1.0.0)

Append-only JSONL, one sequence per run. Each line:

```json
{"schema_version":"1.0.0","run_id":"...","seq":1,"ts_ms":123,"event":"run_start","payload":{}}
```

## Required event classes

`run_start`, `phase_transition`, `combat_tick`, `player_damage`, `purchase_offer`, `purchase_decision`, `lock_decision`, `reroll_decision`, `weapon_combine_or_sale`, `level_up_offer`, `level_up_decision`, `crate_offer`, `crate_decision`, `recovery_attempt`, `error`, `run_end`

Decisions include legal alternatives and teacher score/reason breakdown when available.

## Summary (`summary.json`)

Includes run_id, timestamps, versions, character/weapon/danger/settings, result, last wave, duration, materials/rerolls/locks/purchases/upgrades/crates, damage taken, recoveries/errors/hangs, telemetry completeness.
