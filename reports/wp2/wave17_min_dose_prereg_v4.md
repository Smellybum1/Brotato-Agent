# PREREGISTRATION v4 — minimum effective dose on the failing fixture

**Frozen 2026-07-29 ~07:25, BEFORE any v4 trial was run.**

## Why

v3 (`wave17_dose_ladder_prereg_v3.md`) returned `MODEST_DOSE_SUFFICIENT` on fixture
`run_1785214891_49265`: control **6/8**, H75 **0/8**, H50 **0/8**, both p=0.0035.
**H75 and H50 are identical, so the effect has SATURATED** — the minimum effective dose
is at or below a 25% health reduction and could be far smaller. The engineering target
differs enormously between "needs 25%" and "needs 5%".

## Design

Same single fixture `run_1785214891_49265`. Arms: `C` (1.00), `H95` (0.95), `H90` (0.90),
`H85` (0.85). **8 reps x 4 arms = 32 trials**, ~2.3 h. Arm order randomised, seed
recorded. Same verified save-file instrument; per-file readback; no deploy, no
identity-constant change, controller untouched.

**Scope, unchanged from v3: ONE build.** Every conclusion is a statement about that
build. Generality needs more reliably-failing fixtures, which cost ~30-36 h to collect.

## Outcome

Primary: wave-17 failure <=> observed wave set is exactly `[17]`.
Banned as before: `enemy_hp_pool` (dose rescales it), downstream win rate, damage taken.

## Decision rules — frozen

**`UNINFORMATIVE_FIXTURE`** — control fails **< 5 of 8**. The fixture drifted below its
v2 (4/4) and v3 (6/8) rates; everything below is void. **NOT a null.**

Otherwise define, per dose d, **RESCUED(d)** = fails **<= 1 of 8** AND Fisher one-sided
p < 0.05 vs control.

**`MIN_DOSE_<=5%`** — RESCUED(0.95). A ~5% clearance gain suffices on this build. This
is a SMALL, plausibly attainable target and would justify scoping an agent-side or
build-side lever.

**`MIN_DOSE_5_TO_15%`** — not RESCUED(0.95) but RESCUED(0.90).

**`MIN_DOSE_15_TO_25%`** — not RESCUED(0.90) but RESCUED(0.85).

**`MIN_DOSE_ABOVE_25%`** — none of 0.95/0.90/0.85 rescue. The v3 threshold sits between
0.85 and 0.75, i.e. a 15-25% gain is required.

**`NON_MONOTONE`** — a WEAKER dose rescues while a STRONGER one does not (e.g.
RESCUED(0.95) but not RESCUED(0.85)). Takes precedence over every reading above: report
it as a failure of the dose-response assumption and STOP. Do not pick whichever
neighbouring bracket is convenient.

## Analysis

Fisher one-sided per dose vs the shared control (verified implementation: Fisher's tea
table 17/70 and the closed-form hypergeometric). No pooling with v1/v2/v3 — different
rules, different samples. The shared control is used for all three contrasts and that
multiplicity is NOT corrected; with three tests at p<0.05 the family-wise error is ~14%,
so a single borderline dose is weak evidence and is to be reported as such.
