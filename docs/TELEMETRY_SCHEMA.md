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

The current `0.2.18-wp2-capture` build preserves every existing v1 event and
summary field and executes policy `teacher_v1-0.1.110-gun-wp1`. Historical
`0.2.0` / v92 through `0.2.17` / v109 captures use the same extension. Instrumented runs
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
  projectile candidate tiers and bounded body-emergency activation;
- player position, live/measured velocity, combat stats, wave timer, weapons,
  and arena dimensions;
- raw enemies, bosses, hostile-projectile candidates, materials, consumables,
  crates, and obstacle arrays;
- invalid/freed-object and dropped-entity counts.

Since v127 (`0.2.36-wp2-capture`) the payload also carries the material-crediting
instrumentation:

- `player.materials` — the spendable material counter, read from the same
  `RunData.get_player_gold(0)` accessor the shop path uses;
- `player.bonus_materials` — the end-of-wave carry-over pool
  (`RunData.bonus_gold`), which Brotato's `clean_up_room()` credits with every
  material still on the floor and `spawn_gold()` later drains by boosting new
  drops. Both counters use `-1` for "accessor unavailable on this build", never
  `0`;
- `entities.materials[].value` — per-entity worth. Materials are **not**
  unit-valued: the engine boosts a drop's value from the carry-over pool at spawn,
  and once `MAX_GOLDS = 50` entities are on the floor a new drop spawns no entity
  at all — a random existing one absorbs its value. The material entity *count*
  therefore saturates at 50 while the pile keeps growing; sum `value` for the true
  amount. That ceiling is the engine's and cannot be raised from the mod;
  `dropped_counts.materials` is now derived from the emitted array and reports the
  capture's own truncation, which is zero.

v127 also adds the loot-dash block, `teacher.contributions.loot_dash`, mirrored in
`combat_tick.debug.loot_dash` at the 0.5 s cadence. Before it, the only dash signal
was `loot_dash_active` nested in `finale_translation` — enough to measure uptime,
but not to tell a dash that fires and fails to clear a pile (a capacity problem)
from one the cooldown / HP floor / `LOOT_DASH_MAX_TICKS` bounds keep from arming (a
tuning problem), which is the distinction the fix depends on. Seven flat scalars,
built once per movement decision:

- `active` — dash currently driving the desire vector;
- `state` — this tick's outcome code. Either a transition (`armed`,
  `aborted_ticks`, `aborted_pile_gone`, `aborted_arrived`, `aborted_hp`), the
  ongoing `active`, a branch that dropped the dash outright (`suppressed_survival`
  on the late-survival path, `suppressed_finale` on wave 20), or the reason arming
  was blocked this tick (`not_armed_cooldown`, `not_armed_hp_floor`,
  `not_armed_no_stall`, `not_armed_no_pile`, `not_armed_degenerate`,
  `not_armed_window_clearance`, `not_armed_projectile_context`). The blocked
  reasons are per-tick rather than transition-only on purpose: a dash that never
  arms has no transitions, so suppression is only measurable as a per-tick rate.
  Where several causes hold at once the code follows the source's own short-circuit
  order, and `pile` is emitted alongside so the attribution can be re-checked;
- `seq` — advances **only** on a transition, so dash episodes are recovered by
  differencing it rather than by parsing states;
- `ticks`, `cooldown` — remaining dash ticks (0 when inactive) and cooldown ticks;
- `scan`, `pile` — the material count inside `LOOT_DASH_SCAN_RADIUS` and the
  best-cluster size *that the arming check actually computed*. Both are `-1` when
  the check short-circuited before computing them (the cooldown/HP-floor exit
  precedes both), so a sentinel is never mistaken for a measured zero.

Dash **yield** is deliberately not emitted: `player.materials` is on every capture,
so material gained across a dash is an exact difference between the two captures
bounding a `seq` interval, at no runtime cost. `finale_translation.loot_dash_active`
is retained unchanged so analysis written against pre-v127 runs — including the
episode edge detection in `scripts/wp2_telemetry_stats.py` — keeps working.

The capture schema hash is the SHA-256 of the schema file bytes. Those bytes must
stay LF-terminated — see `.gitattributes`; a CRLF checkout changes the hash. Only
records that carry the current hash are accepted by `scripts/validate_telemetry.py`
and the capture audit. Historical v1 records remain valid and are never rewritten.
