# Corrected end-of-wave leftover measurement (2026-07-25)

Author: Claude Fable (primary, measured directly — two delegated attempts
mismeasured this; see "Measurement history" below). Read-only analysis of
13 runs, all `teacher_v1-0.1.125-gun-wp1`.

## The measurement bug

`combat_capture` events CONTINUE for ~40-55 ticks (2+ seconds at 20 Hz)
after a wave's timer expires — every such tick carries
`wave_time.remaining_sec == 0`. The end-of-wave material sweep happens
inside that post-timer window. Both prior analyses measured "materials
left at wave end" somewhere inside the post-timer window (i.e. AFTER the
sweep) and therefore reported ~1 unit.

CORRECT instant: the last capture with `wave_time.remaining_sec > 0`.

## Corrected result (n=239 wave-observations, 13 runs)

| wave band | median left | mean | at 50-cap |
|---|---|---|---|
| 1-5 | 5.0 | 7.4 | 0/65 |
| 6-10 | 31.0 | 31.4 | 6/65 |
| 11-15 | 44.0 | 40.2 | 18/59 |
| 16-19 | 49.0 | 39.4 | 16/37 |
| non-terminal overall (n=226) | 28 | 28.1 | — |
| TERMINAL wave (n=13) | 30 | 31.1 | — |

**18% (42/239) of wave-observations are pinned at the 50-entity capture
ceiling**, so mid/late-wave figures are CENSORED LOWER BOUNDS. The true
piles may be substantially larger.

The operator's live observation ("it's leaving a lot of currency on the
ground") is CORRECT. The earlier report's contrary claim is withdrawn.

## Economic consequence depends on the (still-unresolved) crediting mechanic

- **Model A** (leftovers collected by the end-of-wave sweep): no loss, no
  delay; collection tempo is irrelevant.
- **Model B** (operator's: leftovers persist as a backlog, drained by
  pairing with next-wave pickups; total conserved): each wave LOSES that
  wave's leftover but GAINS the previous wave's. Once the leftover
  stabilises (44 at w11-15, 49 at w16-19) these cancel and steady-state
  income per wave is UNCHANGED. The real costs are:
  1. a ONE-TIME level shift of ~30-50 units, established during the
     ramp in waves ~5-10, carried for the rest of the run; and
  2. the TERMINAL STRAND: median 30 units (mean 31.1) on the floor when
     the run ends. Terminal waves have ZERO post-timer ticks, so under
     Model B this is unrecoverable — pure lost currency, at the one
     moment no shop remains to spend it.

  NOT a recurring 10-17%/wave loss (an intermediate claim of mine, also
  withdrawn).

## Why existing telemetry cannot settle the mechanic

Under Model B, income(W) = k·[drops(W) − left(W) + left(W−1)]. With a
stationary leftover, `left(W−1) − left(W) ≈ 0`, so Models A and B predict
near-identical income. The discriminating signal exists only during the
ramp phase, where it is comparable to the residual noise floor (~37 gold,
13% of mean wave income; income-per-drop itself drifts 1.05 → 2.5 across
waves due to harvesting scaling). No further analysis of existing runs
will resolve this.

## Recommendation

1. **Add a player-side material counter to the capture payload** (and a
   per-entity material value field; lift or report the 50-entity cap).
   Small change; bundles with the pending `dropped_counts` hardcoded-zero
   fix — same file, same version bump, same smoke. One campaign then
   settles the mechanic definitively.
2. **No collection-behaviour change until then.** Worst case under the
   unresolved mechanic is a bounded one-time lag, and the v119 precedent
   (loot bias out-voting enemy pressure → wave-10 death) makes an
   unmotivated change actively risky.
3. **If Model B is confirmed**, the terminal strand alone justifies a
   late-wave/terminal collection posture: ~30 units of dead value sitting
   on the floor exactly when the run ends. That is a targeted, bounded
   change, unlike a global aggression increase.

## Measurement history (for the record)

1. `materials_collection_analysis.md` — reported leftover ~1; concluded
   "no headroom". Mismeasured (post-timer window). Two further claims in
   it were separately retracted (auto-collect inference; pooled
   `instance_id` comparison).
2. `material_crediting_model_test.md` — re-ran the A/B discrimination but
   did NOT apply the timer-end correction (its `left` column remains
   median 1 / max 6); its "cannot discriminate" verdict rests on the
   wrong input. The conclusion may still hold, but for the structural
   reason given above, not the one stated there.
3. This document — measured directly at `remaining_sec > 0`, verified per
   wave per run.

Lesson: for contested, load-bearing measurements, the primary agent
should compute and eyeball the raw series rather than delegate.

---

## CORRECTION 2 (2026-07-25) — the "50-entity capture cap" does not exist

A parallel session auditing `dropped_counts` established from the
collector source that there is **NO capture-side capacity limit
anywhere**: every collector iterates the full live entity list, and
untruncated raw capture is a deliberate certified invariant (so captures
can be re-encoded at any downstream capacity). All real caps live in
`configs/wp2/observation_v1.yaml` and apply at ENCODE time, not capture
time.

Consequence for this document: the repeated values of exactly 50 in the
leftover series are NOT telemetry censoring. They reflect the game's own
on-ground material ceiling (max observed across runs: 53). The leftover
measurements are therefore **real counts, not lower bounds** — this
strengthens rather than weakens them. References above to "censored
lower bounds" and to lifting a 50-entity capture cap are withdrawn.

Related fact worth not rediscovering: `source_dropped_count` is a LIVE
MODEL INPUT FEATURE. Changing any capture limit would alter what
bc_v2_f and the residual actors consume — an observation-schema
decision, not a mod tweak.

---

## RESOLUTION (2026-07-25) — Model B CONFIRMED from game source

A parallel session read the decompiled game source (record:
`reports/wp2/v127_change_record.md`, memory
`brotato-v127-materials-telemetry`). The mechanic is **Model B**, read
directly rather than inferred:

- `main.gd clean_up_room()` sends floor materials to the gold bag ->
  `RunData.add_bonus_gold`, a pool held SEPARATELY from spendable gold.
- `spawn_gold()` drains that pool by boosting the value of later drops.

So uncollected material is genuinely deferred income, credited through
subsequent drops — the operator's model, confirmed. The open question in
the sections above is CLOSED.

### Consequence that revises this document's numbers upward

`const MAX_GOLDS = 50`: once 50 material entities are on the floor, a new
drop spawns NOTHING and a random existing entity ABSORBS its value.
Therefore:

- The 50-ceiling is the ENGINE's, not telemetry's (consistent with
  Correction 2), and
- **materials are NOT unit-valued**. Entity count is a CENSORED PROXY
  for pile worth. Every leftover figure in this document (median 28
  non-terminal; 44-49 in waves 11-19; 30 on terminal waves) UNDERSTATES
  the value left on the floor whenever the count approached 50 — which
  is 18% of wave-observations outright and more once absorption begins.

The terminal-strand and delayed-income estimates derived from counts are
therefore LOWER BOUNDS on value. v127 adds `entities.materials[].value`
plus `player.materials` / `player.bonus_materials`, which will make the
true worth directly measurable on the next teacher campaign.

### Sequencing constraint discovered with it

Deploying v127 moves the capture schema hash; `encoder_v1.py` and the
sidecar handshake both gate on exact hash equality, so **bc_v2_f and the
residual actors cannot run on a v127 build** until a compatibility-list
change lands. Teacher collection is unaffected. Stage F2 must therefore
complete before v127 deploys, and any future student/residual campaign
needs the compatibility fix first.
