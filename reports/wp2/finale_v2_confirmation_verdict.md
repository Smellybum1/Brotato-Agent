# Finale v2 — CONFIRMATION VERDICT: NOT CONFIRMED

Date: 2026-07-27. Binding protocol: `reports/wp2/finale_v2_confirmation_protocol.md`
(predeclared before trial 1, commit `1132e31`). Campaign 1 verdict:
`reports/wp2/finale_v2_eval_verdict.md`. Build: policy `0.1.128` / mod `0.2.39`, commit
`4930e44` — the same build in both arms, arm selected only by the `finale_v2` flag.
Raw data `.tmp/finale_v2_confirm/predator.jsonl`.

## VERDICT: NOT CONFIRMED. `finale_v2` stays default-OFF.

128/128 trials, 0 failed passes, **128/128 valid** — zero invalid trials in either arm,
so no sensitivity analysis is needed this time.

The predeclared rule required **both** pooled Fisher exact p<0.05 **and** a positive mean
paired delta, on this sample alone. **Neither holds.** The effect did not merely fail to
reach significance — it **reversed sign**.

| view | v2 | v1 | delta |
|---|---|---|---|
| pooled, 8 iteration builds | 40/64 = 0.6250 | 45/64 = 0.7031 | **-0.0781**, Fisher two-sided **p = 0.4543** |
| mean paired delta over 8 builds | | | **-0.0781**, bootstrap CI [-0.2344, 0.0938] |
| sign test | | | **2 of 6** non-tied builds favour v2 |

## Per-build raw series

| digest | v2 | v1 | delta | campaign-1 delta |
|---|---|---|---|---|
| `4ab34bffc43f89c3` | 7/8 = 0.875 | 4/8 = 0.500 | +0.375 | 0 |
| `fc24b6eb79072a4d` | 7/8 = 0.875 | 6/8 = 0.750 | +0.125 | +0.6 |
| `7149d1b7ab27f0a8` | 4/8 = 0.500 | 7/8 = 0.875 | -0.375 | +0.4 |
| `6c32fe3d950f8d6e` | 3/8 = 0.375 | 6/8 = 0.750 | -0.375 | +0.2 |
| `cab349ba80106a37` | 4/8 = 0.500 | 4/8 = 0.500 | 0 | -0.1 |
| `a00d393ad114f2cf` | 1/8 = 0.125 | 2/8 = 0.250 | -0.125 | +0.4 |
| `b02ffbeff221983d` | 8/8 = 1.000 | 8/8 = 1.000 | 0 | 0 |
| `56e65a951b357b1c` | 6/8 = 0.750 | 8/8 = 1.000 | -0.250 | 0 |

**The per-build deltas do not merely shrink, they flip.** The two builds that carried
campaign 1 (`fc24b6eb` +0.6, `7149d1b7` +0.4) come back at +0.125 and **-0.375**. This is
the signature of a noise effect, not of a real effect measured imprecisely.

## The alternative explanation was checked and rejected

Before concluding "campaign 1 was noise", the competing account — that something drifted
between the two campaigns — was tested on the **control arm**, which should be unaffected
by anything about v2:

- v1 iteration rate: campaign 1 **22/40 = 0.550** vs confirmation **45/64 = 0.7031**,
  Fisher **p = 0.1417**
- v2 iteration rate: campaign 1 **28/38 = 0.7368** vs confirmation **40/64 = 0.6250**,
  Fisher **p = 0.2831**

Neither shift is significant. There is no evidence the machine, the build or the fixtures
changed between campaigns; the swing is per-build binomial variance at n=5-8 per cell.
That is the honest reading and it removes the escape hatch.

Descriptively, pooling both campaigns (**not** the decision, and not a legitimate test
after the fact) gives v2 ~68/102 = 0.667 vs v1 ~67/104 = 0.644 — a ~2 pp difference, i.e.
nothing.

## What this means

**The finale v2 controller, as implemented, does not improve wave-20 predator survival.**
Heading selection over 32 candidates with closed-form time-to-collision at 60 Hz is not
better than the existing vector-summation stack at 20 Hz.

This is consistent with the premise refutation already on record: the design was built to
eliminate vector-cancellation **freezing**, and the agent never freezes
(`stationary_frac` 0.000 across every trial ever measured). The design fixed a problem
that was not there.

**A confound worth naming, because it leaves one clean test open.** v2 changed **two**
things at once: the control rate (20 Hz -> 60 Hz on wave 20) and the movement policy
(summation -> heading selection). A null for the pair does not prove each is null — it is
consistent with the rate helping and the policy hurting by a similar amount. So the
**single-constant** test remains worth doing and is now the more attractive experiment:
`BOSS_FINALE_RECOMPUTE_DIVISOR` 3 -> 1 with the **v1 policy unchanged**. One constant,
one wave, waves <20 as the internal control, and no policy change to confound it. That
test was already sequenced ahead of the student-path work for exactly this reason.

## The meta-result

Campaign 1 produced **+0.1875 [0.0375, 0.35]** with a CI excluding zero. Under the
qualification standard this project used from ~v84 — one smoke run plus internal audits —
that would have shipped. A 47-point win-rate collapse once ran ~20 versions invisibly
under precisely that standard.

Here it did not ship, because three things were fixed in advance and each did work:

1. **Both arms ran on the same library**, so build variation could not masquerade as an
   arm effect.
2. **The decision rule was written down before the data existed**, so a p=0.102 could not
   be renarrated as a success.
3. **The follow-up was a fresh pre-registered sample rather than a top-up**, so optional
   stopping could not manufacture significance.

The cost of the correct answer was about five hours of unattended machine time. The cost
of the wrong one was previously measured in ~20 versions.

## Defect found and fixed during this analysis

`scripts/wp2_finale_v2_eval.py` assigned build roles by **positional slicing** (first 8
iteration, last 3 holdout), which is valid only for the 11-build list of the original
protocol. Run against the 8-build confirmation list — all of whose builds are iteration
builds — it silently split 5/3 and printed a PRIMARY computed over only 5 builds.

It was caught by the `candidate set size: N (protocol expects M)` line, which was
specified precisely because **a zero, or a wrong denominator, is the most believable
output a diagnostic can produce**. The headline numbers in this verdict were recomputed
independently in the primary session from the raw JSONL, not taken from the script.
The role assignment is now explicit rather than positional, with a regression test.
