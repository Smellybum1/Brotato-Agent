# Ring-radius ("outrun the ring") eval protocol — PRE-REGISTERED

**Written before trial 1, and deliberately written BEFORE the co-rotation campaign
reports**, so its design cannot be shaped by that outcome.

## The hypothesis (operator, 2026-07-27)

The ring rotates slowly enough that at a close enough radius the agent out-rotates it
and the projectiles never catch up.

**Measured and confirmed available.** The agent out-rotates the ring when
`v_player / r > omega`. Player speed p50 558 u/s, ring |omega| p50 1.45 rad/s =>
nominal crossover 386 u, ~300 u in practice. Observed out-rotating fraction by band:

| radius | 0-150 | 150-300 | 300-450 | 450-600 | 600-900 | 900+ |
|---|---|---|---|---|---|---|
| out-rotating | 84.7% | 51.9% | 18.7% | 7.1% | 3.9% | 0.6% |

**The agent sits at p50 566 u and is inside the crossover only 17.5% of ticks**, so it
loses this race ~82% of the time. The option is real and currently unexploited.

Target 300 u, not closer, because the two threat classes want OPPOSITE radii: the
radiating burst's inter-projectile gap is 9 u at 0-150 and a ~12 u player cannot thread
it, versus ~61 u at 300-450. 300 u also sits inside the shortest weapon range (458 u),
so it does not trade against damage output.

## Arms

| arm | flags |
|---|---|
| control | `--finale-pivot-projectiles` |
| treatment | `--finale-pivot-projectiles --finale-co-rotate --finale-ring-radius` |

**Treatment carries co-rotation as well, on purpose.** Outrunning REQUIRES rotating with
the ring — radius without direction is not the mechanism. The co-rotation campaign
supplies the direction-only decomposition, so between the two campaigns the contribution
of radius can be read off. Both arms re-run on the SAME build (0.2.47); the co-rotation
campaign's control ran on 0.2.46 and is NOT reused.

## Primary metric and decision rule — FIXED NOW

Identical to the co-rotation protocol, so the two campaigns are directly comparable:

- Primary metric **damage taken**; win rate SECONDARY and not the decision variable.
- Unit of analysis is the **FIXTURE** (n=8), not the trial.
- d_f = mean(damage | treatment, f) − mean(damage | control, f); negative = helped.
- **PASS requires BOTH** exact Wilcoxon signed-rank **p < 0.05** AND mean d_f **< 0**.
- Anything else is NOT CONFIRMED, flag stays default-OFF. No metric switching, no
  adding trials and re-testing.
- A PASS promotes to candidate only and needs a fresh-sample confirmation.

8 fixtures x 8 trials x 2 arms = 128 trials, arms alternating in rounds of 8.

## Validity gate — checked first, can VOID the campaign

- 0 invalid trials; every trial's recorded arm matches the requested arm.
- **Radius signature:** the treatment arm's median player-boss distance must move
  toward 300 u versus the control's ~566 u. If the distance does not move, the term did
  not take effect and the campaign is VOID.
- **Out-rotating signature:** treatment's out-rotating fraction must exceed control's.

## Stated in advance: how this could fail, and what would still be learned

1. **The burst may punish the closer band harder than the ring rewards it.** Gaps of
   ~61 u at 300-450 are threadable but tighter than the ~87 u the agent currently
   enjoys. A damage INCREASE would be evidence the burst dominates, which is itself
   worth knowing and would close the "get closer" line.
2. **The safety tail may refuse to hold the band.** Body safety and the corner guard
   both push away from the boss. If the radius signature does not move, that is the
   explanation, and the fix would be term ordering rather than a bigger weight —
   co-rotation already showed that raising weight to 1.00 made things WORSE (65.2%
   co-rotating, below control) because the tail fights a dominating term.
3. **Both may be null**, leaving the pivot fix as the whole story. That is an
   acceptable outcome and would close the wave-20 line for now.

## AMENDMENT, made BEFORE trial 1 and on the SIGNATURE only

Pre-campaign smoke measured the radius signature and it moved far less than intended.
Recorded here in full, before any outcome data exists, because it changes what this
campaign can and cannot conclude.

| arm | dist p25 | p50 | p75 | in-band 240-360 | out-rotating |
|---|---|---|---|---|---|
| control (pivot only) | 467 | **565** | 717 | 8.4% | **7.2%** |
| + radius, weight 0.50 | 382 | **503** | 632 | 10.8% | 8.0% |
| + radius, weight 0.85 | 404 | **485** | 587 | 12.2% | **8.6%** |

**Weight is not the lever.** A 70% weight increase (0.50 -> 0.85) moved the median only
18 u. Weight raised to 0.85 for the campaign, but the target band is NOT being held.

**Why: the inward command does not survive the pipeline.** On ticks beyond 360 u, where
the term should command inward, the FINAL action points **outward 73.5%** of the time
(1079/1468). On 91.4% of those the PREVIOUS command was also outward, and the agent was
neither cornered (nearest wall p50 411 u) nor dodging (projectile gap p50 386 u). An
outward heading, once established, persists.

**Honest limit on that diagnosis:** heading persistence is consistent with the
anti-reversal guard (`_finale_turn_without_reversal`) AND with plain `MOVE_SMOOTHING`
against `prev_move`. This measurement cannot separate them. Not asserting which.

**Consequence for interpretation — stated now, not afterwards.** The treatment does NOT
deliver the outrun mechanism: out-rotating goes 7.2% -> 8.6%, which is nearly nothing.
**This campaign therefore tests "a moderately closer standoff (565 -> 485 u)", NOT
"outrunning the ring".** A null here is NOT evidence against the operator's outrun
hypothesis; it is evidence about a partial intervention. The mechanism itself remains
untested and would need the heading-persistence problem solved first — which means
touching safety machinery, and the one previous attempt at that
(`finale_projectile_priority`) looked harmful in supervised trials.

The campaign is still worth running: per failure mode 1 below, a damage INCREASE would
be evidence the burst dominates at closer range and would close the "get closer" line
regardless of whether the full mechanism is ever delivered.

## Dials

`BOSS_FINALE_RING_RADIUS_TARGET` 300.0, `..._BAND` 60.0 (tight, because range-keep
overshot with a deeper deadband), `..._WEIGHT` 0.50 (matching co-rotation, where 1.00
was measured to be worse).
