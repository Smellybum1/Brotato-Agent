# Finale v2 — CONFIRMATION campaign protocol (PREDECLARED, binding)

Written 2026-07-27, **after** the first evaluation completed and **before** any
confirmation trial was run. First campaign: `reports/wp2/finale_v2_eval_verdict.md`
(protocol `reports/wp2/finale_v2_eval_protocol.md`). Build unchanged: policy `0.1.128`
/ mod `0.2.39`, commit `4930e44`.

## Why a fresh sample rather than extending the first one

The first campaign returned a mean paired delta of **+0.1875 [0.0375, 0.35]** on the 8
iteration predator builds, but **no test cleared p<0.05**: exact Wilcoxon p=0.125, sign
test p=0.375, pooled Fisher p=0.102, and the bootstrap CI includes zero once the two
invalid v2 trials are charged as losses (+0.15 [-0.05, 0.35]).

Adding trials to that sample and re-testing would be **optional stopping**: the decision
to collect more was made *after* seeing a favourable result, which inflates the type-I
error of any test run on the combined data. This project has already learned the
alternative and it worked — the wave-20 finale hazard became a finding precisely because
it was tested on a **fresh, pre-registered sample rather than re-analysed**.

So this is an **independent confirmation sample, analysed standalone**. The first
campaign's numbers are the hypothesis; they are not pooled into the primary test.

## Design

- **Arms:** identical to the first campaign — v2 (`finale_v2=true`) vs v1 (false).
- **Fixtures:** the **8 iteration predator builds only**, same frozen list and order.
  The 3 holdout builds are NOT run: they are reserved for a final check if and only if
  v2 is confirmed. Re-running them now would spend the holdout on a question it was not
  reserved for.
- **Invoker is NOT re-run.** The internal control was pre-registered and it passed
  (delta -0.167, `control_ratio` -0.89): v2 did not improve the boss whose projectiles
  are 96.3% stationary. The open question is the predator magnitude alone. Re-running
  the control would cost 36 trials and answer nothing new.
- **8 trials per build per arm = 64 trials/arm, 128 total**, ~45-75 s each, so roughly
  2-2.5 h.
- **Arms alternate pass by pass**, as before, so time drift is balanced across arms.

## Primary endpoint and decision rule — fixed now

Victory rate on the 8 iteration predator builds, v2 vs v1, on **this sample only**.

**v2 is CONFIRMED** if and only if BOTH hold on the confirmation sample alone:
1. pooled Fisher exact two-sided **p < 0.05**, and
2. mean paired delta over the 8 builds **> 0**.

Anything else is **NOT CONFIRMED**, and the flag stays default-OFF. Per
`docs/RELEASE_GATE.md`, **inconclusive means DO NOT SHIP** — that is what makes a
low-powered gate safe rather than risky, and the cost is shipping velocity, not risk.

Reported alongside, none of them able to overturn the rule above: per-build raw series,
exact Wilcoxon and sign test on the 8 build-pairs, the paired bootstrap CI, and the
worst-case sensitivity in which every invalid v2 trial is charged as a loss.

## Power

At 64/arm, against the first campaign's observed rates (0.55 v1, 0.74 v2), Fisher exact
has roughly **80%** power. A true effect near +19 pp should therefore be detected; a
+5 pp effect still will not be, and none will be claimed.

## Validity, stopping, and the invalid-trial asymmetry

- Trial validity as before: wave set exactly `[20]`, single boss path, boss entity
  predator, policy/mod match, **arm match**.
- The first campaign had **2 invalid trials, both in the v2 arm** (2/55 vs 0/55, Fisher
  p~0.50 — not significant, but the asymmetry is recorded). **This campaign reports the
  same worst-case sensitivity**, charging every invalid v2 trial as a loss. If the
  headline conclusion depends on how invalid trials are handled, the conclusion is
  reported as depending on it.
- **Run to completion; no interim look drives any decision.**
- A failed pass does not end the campaign; the next pass relaunches the game fresh.
