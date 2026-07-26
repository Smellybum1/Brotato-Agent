# Wave-20 control-rate test — protocol (PREDECLARED, binding)

Written 2026-07-27, before any trial. Tests **one constant**:
`BOSS_FINALE_RECOMPUTE_DIVISOR` 3 -> 1, i.e. wave 20 recomputing movement every physics
tick (60 Hz) instead of 1 tick in 3 (20 Hz), **with the v1 movement policy unchanged**.

## Why this test exists

`reports/wp2/finale_v2_confirmation_verdict.md` returned NOT CONFIRMED for finale v2.
But v2 changed **two** things together — the control rate AND the movement policy
(summation -> heading selection). A null for the pair does not clear either individually:
it is equally consistent with the rate helping and the policy hurting by a similar amount.

This isolates the rate. It is the test the control-rate hypothesis always called for, and
it is attractive precisely because it is **one constant, on one wave**, with waves 1-19
(already at 60 Hz) as a standing internal control and no policy change to confound it.

## Arms

| arm | `finale_rate_full` | `finale_v2` | wave-20 recompute |
|---|---|---|---|
| rate | true | false | every physics tick (60 Hz) |
| v1 | false | false | 1 tick in 3 (20 Hz) |

Same ZIP, same policy version `0.1.128`, same movement policy, same safety tail. Only the
recompute gate differs.

## The verification instrument — declared as a validity gate, not a nicety

finale v2 could only be confirmed to have run via an indirect behavioural signature that
had to be reverse-engineered, and the first attempt at that measurement was wrong. This
arm ships a direct instrument: the mod counts, for wave >= 20 only,
`finale_recompute_ticks` and `finale_combat_ticks`, and emits both into the run summary.

**Expected ratio: ~1.0 in the rate arm, ~0.333 in the v1 arm.**

**This is a GATE, declared now.** If the observed ratios do not separate that way, the
campaign is **VOID** and no outcome number from it may be reported. A flag that did not
take effect must invalidate the experiment, not quietly produce a null.

Second gate, same standing: **`control_dt_ms` must stay ~51 ms in BOTH arms.** Captures
are fixed at 20 Hz by the dataset and student path; if the rate arm's captures slipped to
60 Hz, `control_dt_ms` would read ~16 ms and the arm would not be comparable to anything.

## Fixtures and allocation

The **8 iteration predator builds**, same frozen list as the confirmation campaign, with
an **explicit role map** in the fixtures JSON so role assignment uses the authoritative
path rather than positional inference.

**8 trials per build per arm = 64 trials/arm, 128 total**, ~45-75 s each, so ~2-2.5 h.
**Arms alternate pass by pass** so time drift is balanced across arms.

The 3 holdout builds are NOT run — still reserved. **Invoker is NOT run**: if the rate
helps, the mechanism predicts it helps the boss with MOVING projectiles (predator, 0%
stationary) far more than the one with stationary projectiles (invoker, 96.3%), and that
control is worth spending only on a live effect. It is reserved as part of the
confirmation step below.

## Primary endpoint and decision rule — fixed now

Victory rate on the 8 builds, rate arm vs v1, on this sample alone. Reported as per-build
raw series, never a pooled number alone.

**POSITIVE** requires BOTH: pooled Fisher exact two-sided **p < 0.05** AND mean paired
delta over the 8 builds **> 0**.

**A POSITIVE RESULT DOES NOT SHIP.** This is the standard the v2 episode bought: campaign
1 produced +0.1875 with a bootstrap CI excluding zero, and a fresh pre-registered sample
reversed it to -0.078. So a positive here promotes the change only to *candidate*, and it
must then survive a **fresh-sample confirmation plus the invoker control**, both
predeclared before that data is collected. Anything short of that leaves
`finale_rate_full` default-OFF.

Reported alongside, none able to overturn the rule: exact Wilcoxon and sign test on the 8
build-pairs, the paired bootstrap CI, and a worst-case sensitivity charging every invalid
rate-arm trial as a loss.

## Power

64/arm gives roughly 80% power against a ~19 pp effect by Fisher exact. A 5 pp effect will
not be detected and none will be claimed. **A null here means "a 60 Hz wave-20 recompute
was not shown to be worth ~19 pp", not "the control rate does not matter."**

## Validity and stopping

- Trial validity as before: wave set exactly `[20]`, single boss path, boss predator,
  policy/mod match, **and both arm flags matching what was requested** — a trial whose
  recorded `finale_rate_full` disagrees is invalidated (`finale_rate_arm_mismatch`), not
  relabelled.
- Invalid trials are reported with reason codes and never silently replaced.
- **Run to completion; no interim look drives any decision.**
- A failed pass does not end the campaign; the next pass relaunches the game fresh.
