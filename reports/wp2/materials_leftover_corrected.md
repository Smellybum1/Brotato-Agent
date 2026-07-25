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
