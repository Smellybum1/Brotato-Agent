# PREREGISTRATION — wave-17 clear-rate dose response

**Frozen 2026-07-28, BEFORE any trial in this experiment was run.** Written while the
fixture library existed but zero wave-17 trials had been executed. Nothing below may be
revised after looking at any treatment contrast. If a rule here turns out to be
inconvenient, the result is what it is.

Design follows external review (2026-07-28), which rejected the original
`control / health x0.5 / damage x0.5` arm structure as unidentified. Rationale kept in
[[brotato-wave17-offense]] and [[brotato-enemy-scaling-lever]].

## Objective

Does reducing wave-17 enemy-health demand causally reduce wave-17 failure, and is a
MODEST dose enough? The second half is the point: it converts a near-tautology ("easier
enemies help") into an actionability question.

## Instrument

`current_run_state.enemy_scaling.health` in the resumed save. Verified live: exact dose
applied to every enemy type and the boss (41->10, 84->21, 29250->7313 at 0.25). No mod
change, no deploy, no identity-constant bump. The controller is untouched, so this
experiment does NOT spend the waves-<20 internal control.

## Arms

| arm | enemy health | approx outgoing-damage equivalent |
|---|---:|---:|
| `C` | 1.00 | 1.00x |
| `H75` | 0.75 | ~1.33x |
| `H50` | 0.50 | ~2.00x |

`D50` (enemy damage x0.5) is NOT part of the efficacy comparison. If run at all it is a
small pathway check, and its survival effect **must not** be numerically compared with
`H50` to decide whether offense is causal — the doses are not on a common scale.

## Fixtures

16 distinct source runs, one fixture each (lowest-gold snapshot per run = post-shop, so
the trial does not re-run the shop). Fixture is the **generalisation unit**. Arm order
randomised within fixture.

**Restores draw FRESH spawn RNG, so arms are BLOCKED by fixture, not paired
counterfactuals.** 96 trials across 16 fixtures are not 96 independent samples. All
uncertainty comes from resampling FIXTURES, never ticks and never bare trials.

## Outcomes

**Primary:** wave-17 failure (died during wave 17 = 1, else 0). Estimand = the
equal-weight mean within-fixture difference in failure rate vs `C`. Each fixture gets
equal weight regardless of how many trials it contributes.

**Secondary:** restricted survival time `min(death_time, 60)` seconds.

**Mediators (pre-specified):** enemies-alive-seconds and close-melee-seconds integrated
over a fixed pre-terminal window; clearance fraction = enemy HP removed / enemy HP
spawned.

⛔ **`enemy_hp_pool` is BANNED as a primary or secondary outcome.** The treatment
mechanically rescales it — halving enemy health halves the pool regardless of behaviour.
It would manufacture a large, significant, meaningless effect. Only the normalised
clearance FRACTION and entity COUNTS are comparable across doses.

⛔ Also banned: downstream win rate (the dial persists into waves 18-20), damage taken
(zero-inflated; 23 of 40 survivors take zero), HP at wave end (undefined for deaths),
tick-level pseudoreplication.

## Validity

A trial is invalid ONLY for a pre-specified technical reason: wave set not starting at 17
/ resume-failure walk / fixture hash mismatch / missing treatment readback / wrong
multiplier on readback / missing terminal event / telemetry gap / crash. **Never** invalid
for an extreme, early, or unwelcome result. Invalid trials are reported by arm before
replacement.

**Treatment readback is mandatory per trial**: confirm observed enemy `max_hp` per
`type_id` matches the dose. A flag's self-report is not evidence it took effect.

## The feasibility gate (decided BEFORE any contrast is examined)

Our fixtures come from runs that mostly WON (14 of 18), so the library may be too strong
to fail at all. Round 1 = 16 fixtures x 1 trial x 3 arms.

**After round 1 I will look at the CONTROL arm's failure rate ONLY, and at no treatment
contrast.** This is a design-feasibility check, not an outcome peek.

- Control wave-17 failure rate **< 15%** -> `UNINFORMATIVE_CEILING`. **STOP.** This is
  NOT a null and must never be reported as one. The fixture set cannot show rescue.
- Otherwise -> proceed to round 2 and analyse only at the end.

## Decision rules

**`CLEAR_RATE_CAUSAL`** — all of:
1. `H50` cuts wave-17 failure by >= **50% relative** to `C`;
2. one-sided fixture-resampled interval excludes no benefit;
3. survives leave-one-fixture-out (not carried by one fixture);
4. `H50` moves a pre-specified crowd mediator before most deaths;
5. treatment fidelity passes on every counted trial.

**`CLEAR_RATE_ACTIONABLE`** — additionally: `H75` cuts failure by >= **25% relative**,
and the dose ordering is monotone (`H50` <= `H75` <= `C` in failure).

**`CAUSAL_BUT_HIGH_DOSE_ONLY`** — `H50` passes, `H75` does not. Clear-rate demand is
causal but the required rescue is ~2x. **Do not start movement-side development** unless
an uptime deficit of comparable magnitude is demonstrated independently.

**`NO_LARGE_CLEAR_RATE_EFFECT`** — fidelity passes and the upper bound excludes even a
25% relative reduction under `H50`. Rejects the large rescue; does NOT prove offense has
zero effect.

**`INCONCLUSIVE`** — anything else. **Do not** extend the sample, switch endpoint, pool
strata, or promote a secondary metric after seeing results. A new question needs a new
preregistration.

## Analysis

Per-fixture rates -> equal-weight fixture contrasts -> uncertainty by resampling
FIXTURES -> supplement with a blocked permutation test on the actual within-fixture arm
assignment. Test `H50` first; `H75` is confirmatory only if `H50` passes. Report every
stratum including inconvenient ones. Leave-one-fixture-out reported always.

## What this experiment cannot establish

It cannot prove the *player weapon-damage sum* is causal — it manipulates the demand
side. The honest claim is "reducing wave-17 HP demand by dose X changes failure risk",
never "the observed damage covariate is proved causal". A legal shop-producible weapon
upgrade would be the ecological follow-up, not this.
