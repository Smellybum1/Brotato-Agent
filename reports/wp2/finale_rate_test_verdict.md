# Wave-20 control-rate test — VERDICT: NOT SHOWN

Date: 2026-07-27. Binding protocol: `reports/wp2/finale_rate_test_protocol.md` (predeclared
before trial 1). Build: policy `0.1.128` / mod `0.2.40`, commit `76d32dd` — the same build
in both arms, arm selected only by the `finale_rate_full` flag. Raw data
`.tmp/finale_rate_test/predator.jsonl`.

128/128 trials, 0 failed passes, **127/128 valid**. The single invalid trial was in the
**v1** arm, reason `game_exited_before_summary`.

## THE VALIDITY GATE PASSED

Reported first, because the protocol made it a gate: if the recompute ratios did not
separate, the campaign was VOID and no outcome number from it could be reported.

Measured `finale_recompute_ticks / finale_combat_ticks` per trial:

| arm | n | min | median | max |
|---|---|---|---|---|
| rate | 64 | 1.0000 | 1.0000 | 1.0000 |
| v1 | 63 | 0.3333 | 0.3335 | 0.3340 |

**Perfect separation, no overlap, on every single trial.** The rate change demonstrably
took effect.

This is the instrument finale v2 lacked. v2 could only be confirmed to have run via an
indirect behavioural signature that had to be reverse-engineered, and the first attempt at
that measurement was wrong. Here the claim is not "the flag was set" but **"the rate
actually tripled, on all 127 trials"**.

## VERDICT: NOT SHOWN. `finale_rate_full` stays default-OFF.

The predeclared rule required **both** pooled Fisher exact p<0.05 **and** a positive mean
paired delta. **Neither holds**, and the point estimate is slightly negative.

| view | rate | v1 | delta |
|---|---|---|---|
| pooled, 8 iteration builds | 39/64 = 0.6094 | 41/63 = 0.6508 | **-0.0414**, Fisher two-sided **p = 0.7140** |
| mean paired delta over 8 builds | | | **-0.0446**, bootstrap CI **[-0.1250, +0.0312]** |
| sign test | | | **2 of 5** non-tied builds favour the rate arm |
| worst case (invalid v1 trial charged as a WIN for v1) | | | mean paired delta **-0.0312** |

## Per-build raw series

| digest | rate | v1 | delta |
|---|---|---|---|
| `4ab34bff` | 7/8 = 0.875 | 6/8 = 0.750 | +0.1250 |
| `fc24b6eb` | 6/8 = 0.750 | 7/8 = 0.875 | -0.1250 |
| `7149d1b7` | 3/8 = 0.375 | 5/8 = 0.625 | -0.2500 |
| `6c32fe3d` | 1/8 = 0.125 | 2/8 = 0.250 | -0.1250 |
| `cab349ba` | 5/8 = 0.625 | 5/8 = 0.625 | 0.0000 |
| `a00d393a` | 2/8 = 0.250 | 2/8 = 0.250 | 0.0000 |
| `b02ffbef` | 8/8 = 1.000 | 8/8 = 1.000 | 0.0000 |
| `56e65a95` | 7/8 = 0.875 | 6/7 = 0.857 | +0.0179 |

## This null is different from the v2 null: the CI is TIGHT

The v2 campaign-1 CI was **[0.0375, 0.35]** — wide enough to be consistent with almost
anything, which is why a fresh sample could reverse it. This one is **[-0.1250, +0.0312]**.
It **excludes anything resembling the ~19 pp effect the campaign was powered for**, and
puts the upper bound near **+3 pp**.

That makes this an **informative null**: evidence of absence of a large effect, not merely
absence of evidence.

## What this closes

1. **The control-rate hypothesis is substantially refuted for effects of the size that
   would matter.** Running wave 20 at 60 Hz instead of 20 Hz does not measurably improve
   predator survival. That hypothesis was previously recorded as possibly the most
   consequential open lead on the project.

2. **The v2 confound is now RESOLVED.** finale v2 changed rate AND policy together and came
   back null; the worry named in its verdict was that this hid "rate helps, policy hurts by
   a similar amount". Rate alone is now null with a tight CI, so that explanation is dead —
   the policy component of v2 is also null-to-negative. Both components are individually
   accounted for.

3. **A planned expensive follow-up is now UNJUSTIFIED and should not be built.** The
   recorded test order was: (1) `BOSS_FINALE_RECOMPUTE_DIVISOR` 3 -> 1, and (2) ONLY THEN
   move the student path to 60 Hz — a real architecture change, since the dataset is 20 Hz
   and `control_dt` and prev-action are model inputs. Step 1 has returned a tight null, so
   the rationale for step 2 is gone.

   The honest limit: this tested the rate on wave 20 with the **teacher** policy, and does
   not directly measure the student's all-waves 20 Hz handicap. But the specific premise
   that motivated the sequencing — that the wave-20 throttle explains the finale hazard —
   is refuted.

## What remains open

The wave-20 finale hazard is **real and unexplained**: ~25% of runs that reach wave 20 die
there, replicated on a fresh sample (pooled 8/30 = 26.7%).

Two candidate mechanisms have now been tested cleanly and **both are null** — the control
rate, and the heading-selection movement policy. Neither explains the hazard. Any future
finale work needs a **new mechanism hypothesis**, not another variation on these two. Do
not re-run either without new evidence.

## Process note

Three campaigns ran in one night — **146 + 128 + 128 = 402 trials, 0 failed passes** — on
the wave-20 fixture harness, which turned a ~42 min Predator observation into ~45-75 s.
Every campaign had its protocol and decision rule committed before its first trial.

The net result is **two mechanisms closed and one false positive caught** — none of which
the previous one-smoke qualification standard could have produced.
