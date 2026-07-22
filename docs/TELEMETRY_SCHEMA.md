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

## Compatible combat capture extension (envelope v2.0.0)

The current `0.2.14-wp2-capture` build preserves every existing v1 event and
summary field and executes policy `teacher_v1-0.1.106-gun-wp1`. Historical
`0.2.0` / v92 through `0.2.13` / v105 captures use the same extension. Instrumented runs
may interleave a new `combat_capture` record whose envelope has
`schema_version: "2.0.0"`. Readers must dispatch by the schema version on each
record; a run is not required to use one envelope version exclusively.

The raw payload contract is tracked in
`configs/wp2/combat_capture_v2.schema.json`. It is deliberately unpadded and
untruncated so focused teacher runs can establish defensible entity capacities
before `combat_obs_v1` is frozen. The event records:

- a 20 Hz capture sequence, timing, validity, and observation age;
- current and previous deterministic-teacher movement actions;
- finale safety diagnostics, including pre-safety, sampled-escape, blended, and
  final emitted-command projectile clearance plus blend-repair and wall-safe
  replan activation, along with predicted body clearance for wall and
  projectile candidate tiers;
- player position, live/measured velocity, combat stats, wave timer, weapons,
  and arena dimensions;
- raw enemies, bosses, hostile-projectile candidates, materials, consumables,
  crates, and obstacle arrays;
- invalid/freed-object and dropped-entity counts.

The capture schema hash is the SHA-256 of the schema file bytes. Historical v1
records remain valid and are never rewritten.
