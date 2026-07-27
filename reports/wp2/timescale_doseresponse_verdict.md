# VERDICT — 2.0x is SAFE. The failure is a saturation CLIFF, not a slope.

Protocol `timescale_doseresponse_protocol.md`, committed before trial 1 (`9c42e07`).
Build mod `0.2.49-wp2-capture`, policy `teacher_v1-0.1.129-gun-wp1` on all 96
trials. 8 predator fixtures x 4 rounds x 3 arms, **96 trials, 96/96 valid, 32
pairs per comparison**, all three arms in every round so the control is never
stale.

## Result

| arm | achieved / nominal | mean paired diff | 95% CI | victories | verdict |
|---|---|---|---|---|---|
| **2.0x** | **0.985** | **−2.66** | **[−13.42, +8.10]** | **32/32** | **EQUIVALENT** |
| 4.0x | 0.870 | +7.56 | [−7.59, +22.72] | 28/32 | INCONCLUSIVE [A5] |
| 8.0x *(prior campaign)* | 0.78 | +23.16 | [+10.53, +35.78] | 26/32 | FAIL |

**2.0x is approved.** CI inside ±19 and containing zero, all structural gates
pass, zero losses in either arm so the loss clause never fires, sign test 13
worse / 10 better / 9 tied (p = 0.68) — no direction at all.

**4.0x is INCONCLUSIVE by the A5 loss clause** — 4 more losses than control,
which outranks its damage CI. Per the protocol, no escalation is pre-registered
in any branch, so the campaign ends there.

## THE MECHANISM: degradation tracks SATURATION, not speed

The pre-registered diagnostic was `achieved ÷ nominal`. Across three scales it
moves monotonically with the damage, and the two are locked together:

| achieved/nominal | outcome |
|---|---|
| 0.985 | clean — CI contains zero, 0 extra losses |
| 0.870 | 4 extra losses |
| 0.78 | 6 extra losses, damage doubled |

**The dose-response is in the saturation variable, not the scale variable.** The
2.0x arm ran with headroom and was indistinguishable from 1.0x; every arm that
degraded was one the machine could not deliver.

**What is and is not established.** The protocol's strong branch required BOTH
2x and 4x to achieve ≥0.95 and come back equivalent. 4x achieved 0.870, so it
falls into the second branch — *itself saturated*, meaning its result reads as
"this machine's ceiling sits below 4x", **not** "4x is unsafe as a scale". So
saturation is **implicated by one unsaturated clean arm, not confirmed by two.**

The branch that would have REFUTED saturation — an arm achieving ≥0.95 that still
degraded — did not occur. That is the honest limit: the hypothesis survived a
test that could have killed it, on a single supporting arm.

## Operating rule

**Paired fixture campaigns may run at 2.0x on this machine**, which is a measured
**1.70x wall-clock saving** per trial (median 69.0 s → 40.65 s; the residual is
process launch, which is not accelerated).

Three conditions, all load-bearing:

1. **Verify achieved ratio per run, do not assume it.** The saturation point is a
   property of the machine AT THAT MOMENT, not of the scale. This box runs
   several other projects' campaigns concurrently, and the 8x arm reached 6.20x
   absolute while the 4x arm reached only 3.48x — a fixed hardware ceiling would
   have capped both at the same absolute speed, so external load is moving it.
   **Anything below ~0.95 of nominal invalidates the run.**
2. **Paired designs with a contemporaneous control only.** Never unpaired
   collection, because a saturation excursion would be undetectable without one.
3. **Dataset collection still stays at 1.0x**, unchanged: `control_dt_ms` is real
   time and is a student model input.

**Not extended to full-run campaigns.** This tested wave 20 only. A full run
spends most of its time in waves 1-19, which no arm has tested, and a collection
campaign carries no control arm. The whole lesson of the 8x campaign is that
internal checks passed while outcomes doubled — that is not a risk worth taking
on an uncontrolled measurement.

## Method note

G1 was rewritten for this campaign to test its own stated purpose — a generous
lower bound and **no upper bound** — after the 8x protocol's `[6.5, 9.5]` band
conflated *acceleration took effect* with *acceleration hit its nominal figure*
and failed on 6.20 while the effect was proven decisively. Both arms here pass G1
comfortably; the achieved/nominal figure carries the throughput information as a
diagnostic that cannot touch the verdict.
