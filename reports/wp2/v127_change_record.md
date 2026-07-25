# WP2 v127 change record (DRAFT) — material-crediting + loot-dash telemetry, derived dropped_counts

DRAFT — consolidated onto branch `claude/keen-wu-fa36b5`, **NOT deployed, NOT
smoked**. Brotato was running the Stage F2 campaign throughout this work
(`reports/wp2/f2/r01..r11` accumulating at the time of writing), so no ZIP
rebuild, no install, no launch. Deploy is operator-gated.

Policy `teacher_v1-0.1.126-gun-wp1` -> **`teacher_v1-0.1.127-gun-wp1`**; mod
`0.2.35-wp2-capture` -> **`0.2.36-wp2-capture`**. v126 (bounded surplus reroll) is
also still undeployed, so **a v127 deploy ships v126's shop behaviour too** — the
smoke must cover both, and v126's success metrics still apply.

**Three telemetry changes ship in this one bump, with one smoke**, as the
late-wave collection report asked:

1. material-crediting fields (`player.materials`, `player.bonus_materials`,
   `entities.materials[].value`) — settles Model A vs Model B;
2. derived `dropped_counts` — replaces a hardcoded zero block with a measurement;
3. the **loot-dash block** (`teacher.contributions.loot_dash`) — makes the v118
   dash's arm/abort behaviour observable.

All three were developed in separate sessions and are merged here; nothing is
applied twice. See "Coordination" below.

## Why

`reports/wp2/materials_leftover_corrected.md` left the crediting mechanic
unresolved: ~28-49 material entities are on the floor when each wave's timer
expires, and existing telemetry cannot distinguish "swept and credited at wave
end" (Model A) from "carried as a backlog that pairs with next wave's pickups"
(Model B). The two models predict near-identical income once the leftover is
stationary; the discriminating signal is a player-side counter, which the capture
did not have.

## What the game source says (read-only, `third_party/brotatoai`)

The mechanic is legible in the decompiled sources, and it is Model B:

- `main.gd:729-757` `clean_up_room()` — every gold still on the floor is sent to
  the gold bag, not the player (`_player.disable_gold_pickup()`); with
  `optimize_end_waves` it is summed straight into `RunData.add_bonus_gold(...)`,
  otherwise each gold is re-targeted at `_gold_bag` and lands in the same place via
  `on_gold_picked_up` (`add_gold` only when `attracted_by == _player`).
- `run_data.gd:268-278` — `bonus_gold` is a separate pool from spendable `gold`.
- `main.gd:607-613` `spawn_gold()` — while the pool is non-empty each new drop is
  boosted (`gold.value += min(gold.value, RunData.bonus_gold)`) and the pool is
  drained by the drop's original value. That is exactly the operator's pairing
  model, and it also means **materials are not unit-valued**.
- `main.gd:22,505-508` — `const MAX_GOLDS = 50`. Past 50 entities a new drop
  spawns nothing; a random existing gold absorbs its value
  (`gold_boosted.value += unit.stats.value`).

This is a source reading, not a measurement: it says what the shipped 1.1.15.x
build should do, from a decompile of a nearby version. The telemetry below is what
settles it empirically, and the two now agree in advance — worth stating, because a
disagreement at the smoke would mean the decompile is stale for this build.

## The 50-entity ceiling is the engine's, not the capture's

The report asked to lift or make explicit the 50-entity cap on the materials list.
There is **no capture-side cap to lift** — `_collect_loot` has always emitted every
visible gold, and after the `dropped_counts` fix below the capture proves it
(`dropped_counts.materials` is derived from the emitted array, so a zero there is
measured, not asserted). The 50 is `MAX_GOLDS` inside Brotato, and the mod must not
raise it: that would change game behaviour, not observation.

The censoring is real but it is a *count* censoring, and `value` removes it. A pile
pinned at 50 entities can be worth 50 or 500; summing `value` recovers the true
amount at any pile size. So the 18% of wave-observations at the ceiling stop being
lower bounds — with one carried caveat: **already-collected runs stay censored**,
because their captures have no `value` field. The corrected-leftover figures cannot
be retro-fixed; they need a v127 campaign.

## Payload changes (`runtime/agent_controller.gd`)

1. `player.materials` — `RunData.get_player_gold(0)`, the accessor the shop path
   already reads (`agent_controller.gd:1195`, `bot_runner.gd:219`,
   `game_adapter.gd:142`). `-1` if the accessor is absent, never `0`.
2. `player.bonus_materials` — the carry-over pool. Probes
   `get_player_bonus_gold(0)` then the `bonus_gold` property (the decompile is
   pre-coop single-player; the live build is coop-era, so the accessor shape is not
   assumed), `-1` if neither exists. **This is the decisive field**: at a wave
   boundary Model A moves `materials` and leaves `bonus_materials` at 0; Model B
   moves `bonus_materials` and leaves `materials` flat.
3. `entities.materials[].value` — live `Gold.value` via a new `_material_snapshot`
   used by both `_collect_loot` branches, defaulting to the class default `1` if
   the property is absent.
4. `dropped_counts` — the pending hardcoded-zero fix, ported verbatim from the
   concurrent task's working tree (a `_WP2_CAPTURE_LIMITS` table, all groups
   unlimited, and `_wp2_apply_capture_limit`, so drops are derived from
   `raw.size() - kept.size()`). See "Coordination" below.

Both counters are written onto the payload copy **after** `player.duplicate(true)`,
never into `state`, and `_material_snapshot` only adds a key. The teacher's decision
inputs are therefore identical to v126: any behaviour delta in the v127 smoke is a
real regression, not instrumentation. A source test pins this ordering.

## Loot-dash observability (`teacher/potential_field.gd`)

`reports/wp2/late_wave_collection_mechanism.md` called the v118 loot dash an
observability gap blocking the actionable tuning decision. Working on it produced a
**correction to that report first**: dash uptime was already observable.
`finale_translation` nests `loot_dash_active` and *is* emitted, at 20 Hz in
`teacher.contributions` and at 0.5 s in `combat_tick.debug`;
`scripts/wp2_telemetry_stats.py` already edge-detects episodes from it. Measured
over the 5 most recent completed pure-teacher runs (`0.1.125`), dash uptime is
3.3% / 16.2% / 9.3% / 12.2% / 0.0% across w1-5 / w6-10 / w11-15 / w16-19 / w20,
10.5% overall — so **the dash is not shut off in late waves**, and wave 20's exact
zero is the finale branch dropping it by design, not suppression.

What was genuinely missing is *why*. A dash that fires and fails to clear a pile
(capacity) and one the cooldown / HP floor / `LOOT_DASH_MAX_TICKS` bounds keep from
arming (tuning) imply opposite fixes, and uptime does not separate them. The new
block carries seven flat scalars — `active`, `state`, `seq`, `ticks`, `cooldown`,
`scan`, `pile` — documented in `docs/TELEMETRY_SCHEMA.md`. Design points:

- **Reasons are per-tick, transitions are a counter.** A dash that never arms has no
  transitions, so suppression is only measurable as a per-tick rate; `seq` advances
  only on a real arm/abort/drop edge, so episodes are recovered by differencing it
  rather than by parsing states.
- **`scan` and `pile` are `-1` when not computed.** The arming check computes them
  lazily and the cooldown/HP-floor exit precedes both, so a sentinel can never be
  mistaken for a measured zero.
- **`aborted_pile_gone` is split out of "arrived".** Ending because the pile is no
  longer there means the dash cleared it; ending inside the arrive radius with
  material still present means it did not. That split *is* the capacity-vs-tuning
  discriminator.
- **Two suppressing branches are instrumented** (`suppressed_survival`,
  `suppressed_finale`). Both return before `_apply_loot_dash` runs, so without this
  the block would keep reporting the last pre-suppression tick indefinitely.
- **Two exits the original brief did not list** are also coded, because they are
  real returns: `not_armed_no_stall` (neither the stall count nor `PACK_DENSITY_SOFT`
  met — in practice the common early-wave case) and `not_armed_degenerate`.
- **No in-mod yield counter.** `player.materials` is on every capture from change
  (1) above, so material gained across a dash is an exact difference between the
  captures bounding a `seq` interval — better than an in-mod count, at zero runtime
  cost.

Cost: the block is built once per movement decision alongside the existing 40-key
`finale_translation` dict, and every value is a preassigned scalar — the 60 Hz
decision path allocates nothing new beyond the 7-key dictionary itself.

Behaviour is unchanged: every added line assigns a new `_loot_dash_*` telemetry var
or calls a helper that only touches those, except `_suppress_loot_dash`, which
performs the same `_loot_dash_active = false` the two branches did before. A test
pins the exact set of writes to behavioural dash state.
`finale_translation.loot_dash_active` is retained so pre-v127 analysis keeps working.

## Schema + deploy surface

Capture schema hash
`95B6444796A21FD44E94113B75BA2097BC381D5F72ED784F9B9A4A99DD46D951`
-> **`2823CB7E7D6A6DDB7F805A76D0CD674BA7A2A908058771B66B4A8FEFF9BC1174`**.
`$defs/player` gains `materials` / `bonus_materials` (required, `integer >= -1`);
`entities.materials` moves to a new `material_array` whose items require
`value` (`integer >= 1`).

**The loot-dash block moves the hash no further.** `teacher.contributions` is typed
`{"type": "object"}` with no `additionalProperties` restriction — a deliberately
free-form teacher debug bag, which is how the existing 40-key `finale_translation`
already rides there. So the dash fields need no schema edit, and the single hash
move above is attributable entirely to the material fields. This is also the right
call going forward: pinning the debug bag would turn every future teacher-diagnostic
tweak into a schema-hash event, and the hash gates dataset identity. The dash fields
are pinned instead by GDScript source tests, by `docs/TELEMETRY_SCHEMA.md`, and by
Python tests over the consumer arithmetic.

Edited in-repo now, per the v125/v126 precedent:

- `runtime/agent_controller.gd`: `policy_version`, `mod_version` (0.2.36),
  `_WP2_CAPTURE_SCHEMA_HASH`, and the `loot_dash` entry in `choose_movement`'s
  debug bag.
- `teacher/potential_field.gd`: loot-dash state instrumentation + `loot_dash_debug()`.
- `telemetry/telemetry_writer.gd`: `POLICY_VERSION`, default `mod_version`.
- `manifest.json`: `version_number` 0.2.36, description "v127 deterministic teacher".
- `trainer/evaluation/live_monitor.py`: `"0.1.127"` appended to all 6 gated
  safety-check version tuples.
- `tests/unit/test_shop_policy_source.py`: deployed-identity block -> 0.1.127 /
  0.2.36, and the v118 dash safety pin re-expressed for `_suppress_loot_dash`
  (same guarantee — both branches still drop an active dash).

**Deliberately NOT edited** (v126 precedent — protects in-flight F2 collection):
`scripts/wp2_collect_teacher.py` stays at the live `0.1.125` / `0.2.34`. Bump it as
part of the deploy, not before.

## Line endings: a latent hazard that this change trips over

The capture hash is SHA-256 over the schema file's **raw bytes**, and
`core.autocrlf` is `true` in this repo. The main checkout holds these files with LF;
a fresh worktree checkout produced CRLF, which changed the hash of byte-identical
content and (pre-existing, unrelated to this change) broke
`test_observation_encoder_v1.py::test_golden_digest_is_stable`, whose digest depends
on `observation_v1.yaml`'s bytes.

Left alone, a re-checkout or a merge that rewrites `configs/wp2/*` would leave the
pinned `_WP2_CAPTURE_SCHEMA_HASH` not matching the file, and
`scripts/validate_telemetry.py` would then reject **every** capture. Added a
`.gitattributes` pinning `configs/**` and `datasets/**/manifest.json` to `eol=lf`,
and normalized the working copies. The full suite is green with it, including the
golden-digest test that was failing beforehand.

## Downstream impact — what this hash change invalidates

The new hash is a **hard** gate in two places:

- `trainer/observation/encoder_v1.py:245` — refuses a payload whose
  `capture_schema_hash` != the observation schema's `source_capture_schema_hash`.
- `trainer/bridge/sidecar.py:949` — refuses the student handshake on the same
  comparison, against the *model registry* identity.

**This change does not re-pin any of them.** `configs/wp2/observation_v1.yaml`,
`configs/wp2/reward_v1.yaml`, the four dataset manifests (`combat_obs_v1`,
`combat_dagger_r1/r2/r3`) and the six `models/registry/*.json` identities all still
carry the legacy hash, and they remain mutually consistent — a test pins that
agreement. Consequences, stated rather than papered over:

| surface | v127 status |
|---|---|
| Teacher collection (`wp2_collect_teacher.py`) | **works** — its identity gate is a separate constant, and the materials campaign is teacher-only |
| `validate_telemetry.py`, capture audit | **works** — they hash the schema file at runtime and follow it |
| Existing datasets / trained models | **unaffected** — nothing is re-encoded; their captures and pins are self-consistent |
| Encoding v127 captures into `combat_obs_v1` | **blocked** — hash mismatch |
| Student / residual sidecar runs under v127 | **blocked** — handshake mismatch. bc_v2_f cannot run on a v127 build |

Nothing regresses today (v127 is undeployed and F2 runs on v125), but the student
block must be cleared **before** anyone deploys v127 for a student campaign. Three
options, none started here because the choice is a real one and it touches the
production student path:

1. **Compatibility list** (cheapest, preferred): add
   `compatible_source_capture_schema_hashes: [legacy, v127]` to
   `observation_v1.yaml` and accept membership in the encoder and the sidecar
   handshake. Safe because the encoder reads none of the new fields — a v127
   capture encodes bit-identically to a v126 one — but it needs matching entries or
   a lookup in the six model-registry identities, plus tests.
2. **Re-pin and re-encode**: bump every pin and rebuild the datasets. Expensive and
   it invalidates the F2/Stage-F provenance chain for no gain.
3. **Split builds**: keep v126 for student campaigns, v127 for teacher collection.
   Zero code, but two live builds to track — acceptable only for one campaign.

Recommendation: option 1, as its own change with its own tests, after the materials
campaign has settled the mechanic.

## Coordination — how the three tasks were merged

All three landed on `claude/keen-wu-fa36b5`, once each:

- The **`dropped_counts`** fix originated in a concurrent session, was present then
  reverted in the main checkout, and was ported verbatim into the materials work
  (`_WP2_CAPTURE_LIMITS`, `_wp2_apply_capture_limit`, drops derived from
  `raw.size() - kept.size()`). Its own test file
  (`tests/unit/test_wp2_capture_dropped_counts.py`) was never recovered; the
  derivation is covered by `test_capture_side_imposes_no_limit_on_materials` and the
  updated `test_wp2_combat_capture_source.py`, so re-adding it is optional.
- The **materials** work was built in the `elastic-mcnulty-7aa022` worktree and left
  uncommitted there. It was applied here as a patch against this branch and verified
  green before any loot-dash edit — so the two are separable in review, and the
  sibling worktree's copy is now redundant and should not be landed again.
- The **loot-dash** work is new here and touches disjoint code
  (`potential_field.gd` plus one line of `choose_movement`), so it cannot conflict
  with the other two.

Checked before merging: the other two sibling branches (`elastic-mcnulty-7aa022`,
`silly-leavitt-ec7640`) are **ancestors** of this one, not divergent work, and the
main checkout holds no uncommitted `.gd` changes — its two "modified" teacher files
are CRLF artefacts with an empty diff.

## Tests

`tests/unit/test_wp2_capture_materials_telemetry.py` (new, 12 passed + 1 skipped):

- source pins for both counters, the shared material snapshot (both `_collect_loot`
  branches), the accessor probe order, and the sentinel;
- the no-mutation ordering pin (payload copy, after `duplicate(true)`);
- `_WP2_ENGINE_MAX_GOLDS` cross-checked against `const MAX_GOLDS = 50` and
  `var value: = 1` in the game source (skips when the `brotatoai` submodule is not
  checked out);
- schema shape + `_WP2_CAPTURE_SCHEMA_HASH` == SHA-256 of the schema file, and that
  it moved off the legacy hash;
- the encoder-pin/dataset-manifest agreement invariant described above;
- pure-Python consumer arithmetic: value-summing past the 50-entity ceiling,
  missing-value fallback, Model A vs Model B separation across a wave boundary,
  backlog drain via boosted drops, and the terminal-wave strand.

`tests/unit/test_wp2_loot_dash_telemetry.py` (new, 13 passed):

- the debug block exposes exactly the seven documented scalars, in order;
- the controller emits `loot_dash` into the same bag as `finale_translation`, so
  both the 20 Hz capture and the 0.5 s `combat_tick` carry it;
- **exit coverage** — every one of the 9 guarded returns in `_apply_loot_dash`
  records a state first. A silent exit would leave the block reporting the previous
  tick's reason, which reads as a real measurement; this test was mutation-checked
  (deleting one instrumentation line makes it fail);
- the declared code list and the codes actually emitted agree exactly, with `idle`
  confined to the initialiser;
- only real transitions advance `seq` (per-tick blocking reasons must not, or the
  edge count is meaningless);
- both suppressing branches go through `_suppress_loot_dash`, and nothing else in
  `compute_movement` clears the flag;
- `scan` / `pile` sentinel discipline at the short-circuiting exit;
- a pin on the exact set of writes to *behavioural* dash state, so this stays a
  pure telemetry change;
- consumer arithmetic: uptime, the blocked-reason histogram, episode segmentation
  by `seq` with per-episode yield from `player.materials`, and sentinel exclusion
  from pile statistics.

`test_wp2_combat_capture_source.py` updated for the derived `dropped_counts`.
Full suite: **514 passed, 1 skipped, 7 failed** — all 7 pre-existing on the branch
point and unrelated (missing `onnx` module: 5 in `test_student_sidecar.py`, 2 in
`test_onnx_export.py`; verified by running them against the unmodified main
checkout). GDScript is unexecuted — no headless Godot — so parse is verified at the
deploy smoke, per the v126 precedent. Note the suite needs an explicit
`--basetemp` under a sandboxed run; the default pytest tmp root is not writable.

## Deploy checklist (operator, NOT done here)

1. Confirm the F2 campaign is finished and the game is idle.
2. Reconcile the `dropped_counts` port with the concurrent session.
3. Bump `scripts/wp2_collect_teacher.py` to `0.1.127` / `0.2.36`, and the collector
   summary fixture in `test_wp2_teacher_collector.py`.
4. Rebuild the mod ZIP; install to both the workshop and game mod paths.
5. Isolated v127 smoke; zero-violation safety audit; capture audit clean against the
   **new** hash. Confirm `player.materials` tracks the HUD, `bonus_materials` is not
   stuck at `-1` (which would mean the accessor probe missed on this build), and
   material entities carry `value > 1` at least once late-wave.
   For the dash block, confirm `teacher.contributions.loot_dash` is present, that
   `state` takes at least the values `armed` and one `aborted_*` over the run, that
   `seq` is non-decreasing and advances only on those, and that dash uptime derived
   from the new `active` field matches the legacy
   `finale_translation.loot_dash_active` exactly — they are the same variable, so a
   disagreement means the block is wired wrong.
6. Because v126 rides along: re-check its metric — guard-applicable rerolls over
   gate-clearing boards = 0.
7. Write `reports/wp2/v127_deploy_record.md`.

## What the campaign then measures

At each wave boundary, compare the last capture with `remaining_sec > 0` against the
first capture of the next wave:

- `bonus_materials` jumps by ~the ground pile's summed `value` while `materials`
  stays flat -> **Model B**; the terminal strand is unrecoverable and the
  late-wave/terminal collection posture in the corrected-leftover report is
  justified.
- `materials` jumps instead -> **Model A**; collection tempo is economically
  irrelevant and the question is closed.

And, from the dash block, the question the uptime measurement could not settle:

- **Capacity** — dashes mostly end `aborted_ticks` with `pile` still large and a
  small `player.materials` yield: the dash reaches piles but cannot drain them, so
  `LOOT_DASH_MAX_TICKS` / arrive radius are the levers.
- **Tuning** — dashes mostly end `aborted_pile_gone` with good yield, while the
  non-armed ticks are dominated by `not_armed_cooldown` or `not_armed_hp_floor`:
  the dash works when it runs and the bounds are holding it off, so the cooldown /
  HP-floor tiers are the levers.
- **Neither** — non-armed ticks dominated by `not_armed_no_pile` while material is
  demonstrably on the ground would mean piles are not clustering within
  `LOOT_DASH_CLUSTER_RADIUS`, pointing at the clustering geometry rather than the
  dash bounds.

`scripts/wp2_telemetry_stats.py` is the natural home for this histogram; it already
edge-detects dash episodes from the legacy flag and would extend to the richer
fields. Deliberately not written yet — there is no v127 data to validate it against,
and writing an analyzer against a payload nothing has emitted invites pinning the
wrong thing.
