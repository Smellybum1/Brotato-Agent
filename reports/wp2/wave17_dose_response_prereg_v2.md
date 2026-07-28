# PREREGISTRATION v2 — wave-17 near-total rescue test

**Frozen 2026-07-28 ~20:45, BEFORE any v2 trial was run.** Supersedes the v1 arm
structure. v1's gate FAILED (`UNINFORMATIVE_CEILING`, control failure 2/16 = 0.125 < 0.15
bar) and its efficacy contrast was **never computed and must never be computed** — the
v1 data is a pilot, not evidence.

## Why v1 could not work, measured rather than assumed

Wave-17 failure is intrinsically rare per attempt. At the observed control rate 0.125,
detecting the v1 bar (50% relative reduction) needs **340 trials/arm = 680 trials =
48.8 h**. That is the real reason v1 failed, and it is NOT fixable by picking weaker
fixtures:

- The library spans nominal_dps **17.29-66.88** (median 33.48) against Stage A's died
  median 28.26 / survived median 35.25 — 5/16 below the died median, 6/16 above the
  survivor median. It covers the range; it is not a set of easy builds.
- **Entry capacity did not rank the failures.** The two fixtures that died read 22.10 and
  **49.31** (2nd highest in the library), while the WEAKEST fixture (17.29) survived.
  n=2, so this is a design signal only — but selecting low-capacity fixtures would not
  reliably manufacture failures.

## The v2 question

Only a near-total rescue is detectable within a sane budget, so that is what is tested:

> Does halving wave-17 enemy health essentially ELIMINATE wave-17 failure?

Two arms only. H75 is dropped — three arms cannot be afforded, and H75 answers an
actionability question that only matters if the causal one is answered first.

| arm | enemy health |
|---|---|
| `C` | 1.00 |
| `H50` | 0.50 |

## Design

16 fixtures x **4 reps x 2 arms = 128 trials** (64/arm, ~9.2 h at 4.3 min/trial).
FRESH sample: v1 trials are NOT pooled in. Arm order randomised within fixture, seed
recorded. Fixture is the generalisation unit; uncertainty resamples FIXTURES.

Same instrument as v1: `enemy_scaling.health` in the save, per-file readback, dose
confirmed at wave 17 across 7 enemy types (ratios 1.944-2.000). No deploy, no
identity-constant change, controller untouched.

## Outcome

**Primary:** wave-17 failure — the observed wave set is exactly `[17]`.
Estimand: pooled failure rate per arm, with fixture-clustered uncertainty.

⛔ Still BANNED as outcomes: `enemy_hp_pool` (the dose mechanically rescales it),
downstream win rate (the dial persists into 18-20), damage taken (zero-inflated),
tick-level pseudoreplication.

## Decision rules — frozen

Expected control failures at 0.125 over 64 trials: ~8.

**`NEAR_TOTAL_RESCUE`** — H50 failure rate <= **0.02** (<=1 failure in 64) AND Fisher
exact vs control one-sided p < 0.05 AND control failures >= 4 (else the control arm
itself was uninformative). Reading: clear-rate demand is causal at wave 17 and the
required dose is large.

**`NO_NEAR_TOTAL_RESCUE`** — control failures >= 4 and H50 failure rate > 0.02.
Reading: halving demand does NOT eliminate wave-17 death. This **bounds** the effect
from above; it does **not** prove clear rate is irrelevant, because a 50% relative
reduction was never detectable at this n. Say exactly that and no more.

**`UNINFORMATIVE_CONTROL`** — control failures < 4. The rate came in below expectation;
n was too small. **NOT a null.** Do not extend the sample under this preregistration.

**`INCONCLUSIVE`** — anything else. Do not extend, do not switch endpoint, do not
promote a mediator after the fact. A new question needs a new preregistration.

## What v2 cannot establish

It cannot show that a MODEST clearance improvement helps — that was v1's `H75` question
and it is now known to cost ~48 h. So a `NEAR_TOTAL_RESCUE` result does NOT license
movement-side or build-side development on its own; it only establishes the channel is
real. Nor can it prove the player weapon-damage sum is causal: this manipulates the
DEMAND side.

**Note on a mediator-only design, considered and rejected:** testing that the dose
reduces crowd accumulation would be cheap (16 pairs suffice) but near-tautological —
halving enemy HP reduces the standing crowd almost by construction. It would not answer
whether that reduction prevents deaths.
