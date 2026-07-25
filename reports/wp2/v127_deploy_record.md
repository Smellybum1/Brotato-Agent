# WP2 teacher v127 deploy record

Ships **two** undeployed changes in one bump with one smoke, as planned: v126
(bounded surplus reroll, shop behaviour) and v127 (materials + loot-dash +
derived `dropped_counts` telemetry). Change records: `v127_change_record.md`
and the v126 material in `brotato-v124-engine-focus` lineage.

## Build / deploy

- Deploy timestamp: **2026-07-26 02:07:12** local (second attempt — see below).
- Built mod ZIP SHA-256:
  **`24F1B8C149CABDB0C12533547E34B58BB7A5E69EA4F4BCBBC2D3F1C1E018FD3A`**.
  Installed identically to the Steam workshop path and `<install>/mods/`
  (both hashes verified equal).
- Deployed identity: policy `teacher_v1-0.1.127-gun-wp1`, mod
  `0.2.36-wp2-capture`, capture schema hash
  `2823CB7E7D6A6DDB7F805A76D0CD674BA7A2A908058771B66B4A8FEFF9BC1174`
  (moved off the legacy `95B6...D951`; the move is attributable entirely to the
  two new `player` material fields).
- Repo state at deploy: branch `wp2-combat-learning`, HEAD `0d24f22`.
- Collector PID 38088 (first attempt), 33072 (second). Full suite green at
  deploy: **526 passed, 0 failed**.

### Deploy-surface bumps made at deploy time

`scripts/wp2_collect_teacher.py` was deliberately left at the live `0.1.125` /
`0.2.34` during development to protect the in-flight F2 campaign, and was bumped
here. Note this file carries **three** constants, not the two the checklist
listed: `POLICY_VERSION`, `MOD_VERSION`, and `CAPTURE_SCHEMA_HASH`. The hash is
recorded into the collector's state and summary as campaign provenance, so
leaving it at the legacy value would have stamped every v127 campaign with a
false schema identity. All three bumped, plus the collector identity fixture in
`test_wp2_teacher_collector.py`.

`test_wp2_telemetry_stats_frozen.py` still pins `0.1.125` and was correctly left
alone — it is a frozen regression pin over a specific historical run, not a
statement about the live build.

## The first deploy attempt failed: v126 shipped a parse error

The first smoke never started a run. Brotato launched and sat on the **title
screen**; the collector waited for a run that would never begin. This was caught
by the operator noticing the title screen, not by any automated signal — the
collector's own view was indistinguishable from a slow start.

ModLoader's log carried the cause:

```
SCRIPT ERROR: Parse Error: Invalid operand types ("String" and "null") to operator "in".
   at: GDScript::reload (res://mods-unpacked/Tom-BrotatoAgent/runtime/agent_controller.gd:1643)
SCRIPT ERROR: Parse Error: Couldn't fully preload the script ... mod_main.gd:7
```

The offending line was **v126's**, not v127's:

```gdscript
elif "items" in RunData and RunData.items != null:
```

Godot 3 rejects `in` against an autoload at parse time, and a parse error is not
local — it takes the whole mod down, so the agent never installs.

Three things about this are worth recording, because none of them are obvious
from the code:

1. **The repo already knew.** `adapter/game_adapter.gd::_danger` carries the
   comment "Avoid `"prop" in RunData` — Godot 3 rejects that for some autoload
   types" and uses the `RunData.get("prop") != null` idiom. v127's own
   `_wp2_bonus_materials` follows it correctly. v126 did not, and nothing
   enforced it.
2. **A test was pinning the defect.** `test_v126_surplus_reroll.py` asserted the
   broken line was present in the source, verbatim, as a regression pin. The
   suite was therefore **green on a mod that could not load**. Source-text pins
   assert presence, not validity, and this one encoded a fatal bug as a
   requirement.
3. **GDScript is never parsed by the test suite** (no headless Godot here), so
   the deploy smoke is the first real parse. That is a known structural gap; it
   cost one build/deploy/launch cycle.

Fixed in `0d24f22`: the line now uses the established `get()` probe (behaviour
unchanged — it was unreachable before, since nothing loaded), the test pin was
re-pointed at the correct form, and a new
`tests/unit/test_mod_gdscript_parse_hazards.py` guards the whole mod tree
against `"literal" in <CapitalisedName>`, with a mutation check proving it
catches this exact regression. A static sweep of the entire v126+v127 GDScript
delta found this was the **only** instance.

## Smoke run

- Run id: **`run_1784995647_96514`**.
- Result: **VICTORY** at wave **20**; duration 1,183,330 ms (~19.7 min); damage
  taken **116**.
- Captures 21,128; other events 2,629.
- Clean shutdown confirmed: collector status `complete` (target 1 / completed 1,
  stop reason "target reached"), Brotato absent from the process list,
  `auto_start=false` in `agent_config.json`.

## Audits

- **Safety audit** (`v127_smoke_safety_audit.json/.md`): runs 1, accepted 1,
  **violation_count 0** across every category. Captures 21,128 (21,128 fresh
  decisions; 4,787 late). Activations: 7,358 body, 1,495 projectile, 3,555 wall,
  1,480 wall-body relief. Avoidable damage-path violations 0; hidden wall-relief
  body lanes 0. Events SHA-256 `E50A9C38...D5A2F`, summary SHA-256
  `19DF7849...DAFAD`.
- **Capture audit** (`v127_smoke_capture_audit.json/.md`): 21,128 captures,
  **schema mismatches 0** against the new hash, invalid captures 0, invalid
  actions 0, valid transition estimate 21,128, near-duplicate fraction 0.0267.
- **v126 shop audit** (`v127_smoke_v126_shop_audit.json`): **violation_count 0**,
  surplus rerolls 4, stale-board timeouts 0. The v126 rule is exercised and
  never violated.
- **v127 field check** (`v127_smoke_field_check.json`, produced by the new
  `scripts/wp2_v127_field_check.py`): **12/12 PASS**.

## v127 field verification (deploy checklist item 5)

| check | result |
|---|---|
| `player.materials` on every capture, never the `-1` sentinel | PASS — coverage 1.0, range [1, 797] |
| `player.bonus_materials` on every capture, not stuck at `-1` | PASS — coverage 1.0, range [0, 49], 49 distinct values |
| `entities.materials[].value > 1` observed | PASS — 8,894 entity-observations at value 2, present in every wave 2-20 |
| `teacher.contributions.loot_dash` present | PASS — coverage 1.0 |
| dash `state` takes `armed` and an `aborted_*` | PASS — `armed` 30; `aborted_ticks` 17, `aborted_arrived` 12, `aborted_pile_gone` 3 |
| dash `seq` non-decreasing | PASS — 0 regressions, 184 total edges |
| every emitted `state` is declared in the mod's `LOOT_DASH_STATES` | PASS — 0 undeclared |
| new `active` == legacy `finale_translation.loot_dash_active` | PASS — **0 disagreements over 21,128 captures** |
| `dropped_counts` derived and zero | PASS — all 7 groups, 0 captures with a nonzero drop |

The `bonus_materials` probe finding a live accessor is the load-bearing result
here: a run of uniform `-1` would have meant the probe missed on this build and
the crediting question was still open.

### One check was mine and was wrong

An initial pass flagged "seq advances only on edge states" as failing. It is not
a defect: dash state updates on the **60 Hz** movement decision while captures
sample at **20 Hz**, so a seq advance frequently lands on a capture whose `state`
has already been overwritten, and a one-tick `armed` can be aliased away
entirely (122 such aliased advances in this run). "seq advances only on edges" is
a property of the variable, pinned at source level by the mutation-checked
`test_wp2_loot_dash_telemetry.py`; it is **not** recoverable from subsampled
captures. The check was replaced with one that is: every emitted state must be
declared in the mod source. Recording this because the same trap will catch the
next person reading dash telemetry.

## What the run measured: crediting is Model B

At each wave boundary, comparing the last capture with `remaining_sec > 0`
against the first capture of the next wave (the correct instant — captures
continue past timer expiry and the sweep happens inside that window):

| wave | floor ents | floor value | Δmaterials | Δbonus | Δbonus == floor value |
|---:|---:|---:|---:|---:|:--|
| 1 | 2 | 2 | -49 | 2 | Y |
| 2 | 5 | 5 | -45 | 5 | Y |
| 3 | 7 | 7 | -68 | 7 | Y |
| 4 | 7 | 7 | -96 | 7 | Y |
| 5 | 8 | 8 | -110 | 8 | Y |
| 6 | 2 | 2 | -165 | 2 | Y |
| 7 | 16 | 16 | -197 | 15 | n |
| 8 | 16 | 16 | -211 | 16 | Y |
| 9 | 19 | 19 | -424 | 18 | n |
| 10 | 46 | 49 | -456 | 49 | Y |
| 11 | 23 | 23 | -126 | 23 | Y |
| 12 | 22 | 22 | -523 | 21 | n |
| 13 | 14 | 14 | -381 | 14 | Y |
| 14 | 20 | 20 | -223 | 20 | Y |
| 15 | 46 | 48 | -465 | 48 | Y |
| 16 | 18 | 18 | -462 | 18 | Y |
| 17 | 23 | 23 | -94 | 23 | Y |
| 18 | 20 | 20 | -655 | 20 | Y |
| 19 | 30 | 30 | -570 | 28 | n |

**15/19 boundaries match exactly; the other 4 are short by 1, 1, 1 and 2.** The
misses are all in the same direction (Δbonus < floor value), which is what a
sampling gap predicts: the sampled capture is 5-50 ms before expiry and the
player can still collect an entity or two in that window, so the true floor at
the instant of the sweep is slightly smaller. No miss is in the direction that
would challenge the model.

`Δmaterials` is **not** evidence either way — the shop sits between these two
captures, so spendable materials move for reasons unrelated to crediting. The
discriminator is whether the *bonus* pool absorbs the floor, and it does.

**This confirms Model B**, and it agrees with the game source read independently
beforehand — worth stating, because a disagreement would have meant the
decompile was stale for this build.

### A second result the table gives for free

`bonus_materials` is **0 at the end of every one of the 19 waves**. The pool
fully drains within each wave, every wave, all the way to 19. It never
accumulates, so on this run there is no saturation regime in which deferred
value is stranded. That has direct consequences for how much the collection
tempo is actually worth, which is being worked separately and is **not** settled
by this deploy.

### Loot dash: the capacity-vs-tuning discriminator now has data

State histogram over 21,128 captures: `not_armed_no_stall` 14,520 (68.7%),
`not_armed_cooldown` 3,358 (15.9%), `active` 1,801 (8.5%), `suppressed_finale`
1,055, `not_armed_no_pile` 265, `suppressed_survival` 35,
`not_armed_window_clearance` 31, `armed` 30, `aborted_ticks` 17,
`aborted_arrived` 12, `aborted_pile_gone` 3, `not_armed_projectile_context` 1.
Uptime from the new `active` field: **8.7%**.

Read against the discriminator the block was designed for: dashes end
`aborted_ticks` (17) and `aborted_arrived` (12) far more often than
`aborted_pile_gone` (3), i.e. the dash usually does **not** clear the pile it
went for — the capacity signature. But the dominant fact is upstream of that:
**68.7% of ticks never arm because neither the stall count nor the pack-density
condition is met at all**, with cooldown a distant second at 15.9%. Tuning the
dash bounds addresses at most the 15.9%; the arming condition governs the 68.7%.

One caveat: this is a single run, and a **victory**, so it is a favourable-path
sample. These proportions should not be treated as the run-population
distribution.

## Open observation, recorded rather than resolved

Capture-audit percentiles show the materials group reaching **50** entities, the
engine's `MAX_GOLDS` ceiling, at which point the game stops spawning new gold and
instead adds the drop's value to a random existing entity. That absorption path
should be able to produce entities of value 3 or more, yet the **maximum `value`
observed in the entire run is 2** — the same value the bonus-pool boost produces
(`gold.value += min(gold.value, bonus_gold)` on a base-1 gold). So the two
mechanisms are not separable from `value` alone in this run, and the absorption
path is not independently confirmed. This does not affect the deploy: `value` is
populated and pile worth is recoverable by summing it, which is what the field
was added for. Flagged so the materials campaign can check it deliberately.

## Summary

Teacher v127 (`teacher_v1-0.1.127-gun-wp1`, mod `0.2.36-wp2-capture`) is deployed
from a reproducible ZIP (SHA-256 `24F1...FD3A`), carrying v126's shop change with
it. The first deploy attempt failed on a v126 GDScript parse error that made the
mod unloadable and that the test suite was actively pinning; it is fixed and
guarded. The re-run smoke is a wave-20 **victory** (damage 116, ~19.7 min) with
**zero safety violations**, a fully clean capture audit against the new schema
hash, **zero v126 shop violations** over 4 surplus rerolls, and **12/12** on the
v127 field checklist. The crediting mechanic is confirmed **Model B** on 15/19
exact boundary matches with the four misses explained by sampling, and the bonus
pool is shown to fully drain within every wave.
