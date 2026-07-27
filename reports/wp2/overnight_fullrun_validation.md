# The corrected derivation VALIDATES, and predator survival holds on natural arrivals

18 full runs at **1.0x** on the shipped build (mod `0.2.49`, policy `0.1.129`),
18/18 completed, 0 restarts. Snapshot collector alongside.

## Result vs the prediction

| term | predicted | observed | |
|---|---|---|---|
| `P(reach w20)` | 0.713 | **13/18 = 0.722** | near-exact |
| `P(survive w20 \| predator)` | **1.000** *(fixture-measured)* | **7/7 = 1.000** | **holds** |
| `P(survive w20 \| invoker)` | 0.597 | 5/6 = 0.833 | runs hot, n=6 |
| **win rate** | **0.574** | **12/18 = 0.667** | within CI |

**The term the derivation was most sensitive to came in exactly.** Post-fix
predator survival was the largest source of error in
`fullrun_derivation_corrected.md` precisely because 1.000 had only ever been
measured on **restored fixtures** — and at 0.85 the whole prediction fell to
0.519. On **naturally-reached** wave 20s it is **7/7**. The fixture harness does
not flatter the fix.

**And the fix is confirmed firing in natural runs.** All seven predator arrivals
carry the structural signature: **9,477 to 16,011 rotating-projectile
observations each**, against **0 in 245,057 control observations** at
qualification. This is the first observation of the shipped fix operating at a
wave 20 the agent actually played its way to.

## The excess over prediction is entirely the invoker, and it is n=6

Observed win rate 0.667 sits above the predicted 0.574. Decomposing with the
observed terms: `0.722 x (0.538 x 1.000 + 0.462 x 0.833) = 0.667`. Substituting
the invoker's archive rate of 0.597 instead gives **0.588** — essentially the
original prediction. So the entire overshoot is the invoker going 5/6 against an
expected 0.597, on six trials. **No reason to revise the invoker term.**

A 12/18 win rate has a 95% interval of roughly [0.41, 0.87], which contains
0.574 comfortably. **This is a consistency check that passed, not a new estimate.**

## Where the losses fell — as the loss budget predicted

Pre-finale deaths at waves **16, 17, 17, 19, 19** — five of the six losses, with
only one at wave 20 (an invoker). That is the shape
`loss_budget_after_the_fix.md` describes: with the predator hazard closed,
**most remaining losses arrive before the finale.**

**Two fresh wave-17 deaths on the shipped build.** The wave-17 study rested on
n=22, all from older builds, and its binding constraint was sample size. One of
these was checked out-of-sample and fits the profile: weapon damage **135.0**
against a died-group median of 162.5 and a survivor median of 335, with
defensive stats on the died-group values. A prediction that could have failed and
did not — worth exactly what n=1 is worth.

## Fixture library

The collector took the library from 46 to **73 snapshots**, and the number that
matters — **distinct predator source runs — from 10 to 18**. That directly widens
the build diversity behind every future fixture campaign, which was the
representativeness concern that started this thread.

## Caveats

1. `P(survive w20 | predator) = 7/7` has a 95% lower bound near 0.59. It is
   consistent with 1.000 and rules out the low end, but it does not *prove* 1.000.
2. 18 runs is a consistency check. Every term here has a wide interval.
3. The 1.0x choice was deliberate: 2.0x is validated for **paired fixture**
   campaigns only, and this campaign has no control arm, so a saturation
   excursion would have been undetectable. See
   `timescale_doseresponse_verdict.md`.
