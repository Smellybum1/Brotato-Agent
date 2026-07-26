# Pro consultation brief — 2026-07-26 (third set)

One question: I have just found what I think is the dominant defect in a project I
have been working on for weeks, and it implies that most of that work was misdirected.
I want an outside check on the finding, on my proposed response, and on whether there
is a better response. Self-contained — no repo access assumed.

---

## The project

A deterministic, hand-written policy that plays **Brotato**, a top-down arena
survival game. Fixed configuration throughout: one character ("Well-Rounded"),
difficulty 0, a ranged/gun weapon pool, **20 waves**, objective is **win rate**
(surviving all 20 waves). Between waves there is a shop; on level-up the agent picks
one of four random stat upgrades.

The work has two parts:
- **WP1**: get the scripted policy good. Ended with a version certified at 18 wins
  in a fresh 20-run gate.
- **WP2**: use that policy as a *teacher* to train a learned neural policy —
  behaviour cloning from ~390k recorded decisions, then residual reinforcement
  learning on top. This required heavy instrumentation of the policy (telemetry
  capture at 20 Hz, schema-hashed observation vectors, audits).

Across both phases the policy went through ~128 numbered versions.

## How versions have been qualified since WP1 ended

This is the part that matters.

During WP1, each candidate version faced a **fresh 20-run gate** and had to hit
≥18 wins. That is a win-rate test.

From roughly version 84 onward, the qualification procedure became:
- **one** "smoke" run (~20 minutes of real gameplay), plus
- a set of **automated audits** over that run's telemetry: safety-rule violations,
  telemetry schema conformance, shop-rule conformance, movement-safety invariants.

A version ships if the smoke completes and the audits report zero violations.

Roughly 45 versions shipped under that procedure. Each was motivated by a real
observed failure and validated by that failure not recurring in the smoke.

## What I found today

I reconstructed win rate from the run archive: **642 archived runs, 454 with a
readable summary**. I confirmed the comparison is clean before drawing any
conclusion:

- **character**: `character_well_rounded` for all 454 runs.
- **difficulty**: 0 for all 454.
- **configuration id**: the entire version-60-to-128 span is one identical config.
- **game version**: `1.1.15.4` for all 454 runs, in both the early and late eras.
  The game itself never updated under the project.

Win rate by version band (95% Wilson intervals):

| band | wins/runs | win rate | 95% CI |
|---|---|---|---|
| v60-72 (end of WP1) | 82/113 | **72.6%** | [63.7, 79.9] |
| v73-83 (experiments) | 10/19 | 52.6% | [31.7, 72.7] |
| v84-99 | 11/47 | **23.4%** | [13.6, 37.2] |
| v100-116 (a repair chain) | 13/29 | 44.8% | [28.4, 62.5] |
| v117-124 | 17/30 | 56.7% | [39.2, 72.6] |
| v125-128 (current) | 27/78 | **34.6%** | [25.0, 45.7] |

And the two cleanest samples — both exactly 20 runs, identical configuration:

- **v72**, the WP1 certified gate: **18/20 = 90%** (CI [70, 97])
- **v125**, the pure-teacher arm of a recent controlled experiment:
  **10/20 = 50%** (CI [30, 70])

Fisher exact on those two: **p = 0.0138**.

So the policy appears to have regressed from roughly 73-90% to roughly 35-50%,
and **nobody noticed for ~45 versions**, because the qualification procedure that
replaced the 20-run gate cannot detect a win-rate change at all — a single run has
no power against a 40-point effect.

## Why this reframes the rest of the project

Everything downstream was built on the degraded policy:

- The behaviour-cloning student was trained on demonstrations from a policy winning
  ~35-50%, not the certified ~73-90% one.
- A recorded key negative result — "the student imitates the teacher *more* closely
  yet survives *less*" — may partly be "the student successfully imitated a mediocre
  teacher."
- Two residual-RL programs returned null results (the learned residual was not shown
  to beat a matched random control, twice).
- I spent this week investigating the shop/level-up scoring layer and closed it
  today: the defects found were real but worth about **0.2-0.45 decisions per run**,
  far too small to matter.

I was optimising fractions of a decision per run while a ~40-point win-rate
regression sat unmeasured in the version history.

## My hypothesis about the cause

I have not localised it yet, but I have a structural hypothesis, and it is the same
pathology I closed earlier today in a different subsystem.

The scoring code I examined this week had accreted **four separate terms pricing the
same three quantities**, each added at a different time, each in response to a real
observed failure, each locally justified, and collectively incoherent — the
principled term was buried by three cruder ones. I tried removing one and the change
was provably **inert**, because the others took over.

The movement/safety layer has the same shape. Over versions 84-128 it accumulated:
a density veto, a relief-trigger fallback, a corner guard, an edge-kite rail, pack
repulsion, a loot-collection dash, hysteretic "build strength" tiers modulating four
other parameters, a finale override, and wave-indexed "greed" budgets. Each was added
for a specific observed failure and validated by a single smoke run plus audits.

**My hypothesis: the accumulated layer is net-negative on win rate, and each
individual addition looked fine because the only thing ever measured was "did the
specific failure recur in one run" and "do the audits pass."** The audits check
internal consistency, not outcomes. There is a recorded phrase from the project's own
notes for this era — the "passes gates / looks awful" paradox.

## My proposed path forward

**Stop all feature work. Make win rate the controlled quantity again.**

**Phase A — finish the archive reconstruction (offline, free, ~half a day).**
Recover the 188 runs that have an event stream but no summary; separate
teacher-driven from learned-policy-driven runs; compute per-version win rate with
proper change-point detection rather than my hand-drawn bands; cross-reference each
change point against the version's recorded change note. Output: a defensible
win-rate-versus-version curve and a shortlist of 2-4 suspect transitions.

**Phase B — localise (offline).** Diff the policy across each suspect transition.
One collapse (v84-99) already has a diagnosed root cause found at v116 — two movement
safety primitives sampled time discretely and could not see fast threats crossing the
commanded path between samples. But the repair only recovered to ~57%, not to ~73%,
and then it fell again. So there is at least one further un-diagnosed regression.

**Phase C — the decisive experiment.** A/B the current policy against a
deliberately *reduced* variant with the accumulated layer stripped back toward the
v72-era behaviour, on win rate, ~20 runs per arm. Each run is ~20 minutes of real
gameplay, so an arm is ~7 hours of wall-clock and the machine can only run one at a
time. If the stripped variant wins, the path forward is **deletion, not addition.**

**Phase D — process fix, ships regardless.** No behavioural version ships on one
smoke again. Replace it with a win-rate-sensitive sequential gate against the
incumbent, sized to be affordable (perhaps 8-12 runs with a Bayesian stopping rule)
rather than a fresh 20-run gate every time.

## My questions

1. **Is the finding sound?** I ruled out character, difficulty, configuration and
   game version. The residual worries I can see: (a) the v60-72 band is inflated by
   survivorship, because campaigns in that era were stopped after 3 losses, so
   *good* versions contributed more runs than bad ones; (b) v72's 90% is the winner
   of ~15 attempted versions and so is a multiple-comparisons maximum, likely
   optimistic; (c) 188 runs (29%) are unclassifiable and are probably crashes or
   aborts, which may not be distributed evenly across eras. How much do these
   actually threaten the conclusion, and is there an analysis that would settle
   them from the archive alone?

2. **Is "stop and bisect" the right response**, or is it the sunk-cost-flavoured
   move of relitigating history when I should instead take the current policy as the
   baseline and optimise forward from it? Concretely: does it matter *why* the
   policy is at 50% if what I want is a policy at 90%?

3. **Is my "accreted layers are net-negative" hypothesis worth privileging**, given
   I just confirmed exactly that pattern in an adjacent subsystem today? Or is that
   a bias — pattern-matching a fresh finding onto an unrelated system?

4. **How would you sequence Phase C given the cost?** One arm is ~7 hours and the
   arms cannot run in parallel. Full ablation of ~10 accumulated features is
   combinatorially impossible. Is there a principled way to choose *which* reduction
   to test first, or a cheaper design — e.g. staged ablation, or reconstructing
   counterfactual outcomes offline from the recorded telemetry rather than replaying?

5. **What is the right qualification gate** for a change to a stochastic policy
   whose outcome is binary per run, where each run costs 20 minutes, and where I
   ship a version perhaps twice a week? I want something with real power against a
   20-point regression without costing 20 runs every time.

6. **What am I not seeing?** In particular: is there a reading of this evidence in
   which the regression is *not* real, or in which it is real but not worth chasing?
