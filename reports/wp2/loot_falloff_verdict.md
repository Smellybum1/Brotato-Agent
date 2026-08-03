# §35 — Gate 0 for the loot falloff exponent: RESULT

**VERDICT: GATE 0a PASSES, GATE 0b FAILS. DO NOT IMPLEMENT.**
And the failure is **ADVERSE, not null** — steepening the falloff makes in-range **worse** at every
dose. Pre-registration: `reports/wp2/loot_falloff_prereg.md`, commit `a4d8126`, written before the
counterfactual existed. Script: `scripts/wp2_loot_falloff_gate0.py` (`--self-test`, 16 checks).
**Zero new runs.**

## §35j — Denominators

8 D5 ranger runs at `0.2.76-wp2-capture`, full scan (stride 1). **Analysis set 32,994.**
Exclusions, all counted: `exit_not_baseline_or_no_threats` 25,788 · `wave_outside_1_11` 10,828 ·
`degenerate_desire_total` 4,619 · `no_materials_present` 2,261 · `stale_desire_seq` 53.
✅ The analysis set was **rebuilt independently in the primary session** and reproduces **32,994**.

## §35k — Controls

| control | result |
|---|---|
| **1. loot reproduction @ e=0.65 (make-or-break)** | **32,528/32,528 = 1.0000** |
| — recorded-loot-exactly-zero captures, reported separately | 466 recorded zero, 466 recomputed zero, **0 disagree** |
| 2. sum reproduction (`early_force_mult·enemy_engagement + Σ11 == total`) | **32,994/32,994 = 1.0000** |
| 3a. null-dose, recorded loot substituted (can the statistic return the negative?) | rotation ≠ 0 on **0/32,994** |
| 3b. recompute residual @ e=0.65 | median **1.479e-06°**, p99 1.86e-05°, **max 1.03e-02°**; ≥15° on **0** |

⭐ Control 1 passing at 1.0000 is what makes this counterfactual reportable at all: it validates the
reimplementation of `greed`, `safety`, `clear_mult`, the `nearby >= PACK_DENSITY_SOFT` return-ZERO veto
(`:3559-3560`) and the `blockers > LOOT_PACK_ALLOW` item skip (`:3574`).

## ⚠️ §35l — I MIS-SPECIFIED TWO BARS. Both disclosed; neither changes the verdict.

**(a) Control 3 was unattainable by construction.** The prereg demanded rotation be **exactly 0.0** at
the null dose. The telemetry stores desire vectors **rounded to 6 decimals**, so a full-precision
recomputation differenced against a rounded record **can never be bit-exact** — it read 24,654/32,994
nonzero. That is not a modelling error; **the bar could not be met by a correct implementation.**
Resolution: split into **3a** (the property the control actually exists to prove — feed the *recorded*
loot back in, rotation is exactly 0.0 on all 32,994) and **3b** (bound the recomputation noise: max
**0.0102°** against a 15° gate bar, three orders of magnitude clear). ⭐ This is the *"statistic that
cannot return the positive"* family, wearing the opposite sign: **a control bar that cannot pass is as
broken as a test that cannot fail**, and writing one costs a stop-and-adjudicate mid-analysis.

**(b) The Gate 0b bar sits below the statistic's resolution.** `inrange_after` divides by the living
threat count `k`. Measured on the analysis set: **k median 8** (p10 2, p25 4, p75 13, p90 19), so the
finest nonzero |gain| expressible at the median is **1/8 = 0.125**, and **27.9% of captures have k ≤ 4**
(resolution ≥ 0.25). A **0.05** median bar is therefore lumpy — attainable only via the high-`k` tail.
⇒ **It did not bind here** (see below: the median is pinned by the *sign* split, not by resolution),
but the bar should have been stated in units of `1/k` or as a mean.

## §35m — GATE 0a: PASS. The exponent genuinely rotates the desire.

| e | rotation ≥15° rate | median rotation | n rotated |
|---|---|---|---|
| 0.90 | 0.1693 | 3.489° | 5,585 |
| **1.20** | **0.4111** | 10.656° | 13,563 |
| **1.60** | **0.6882** | 31.753° | 22,707 |

Bar was ≥20%; e=1.2 and e=1.6 clear it comfortably. ⭐ **The prereg predicted 0a would pass and it
did** — the exponent reweights a ~10-item sum and the resultant moves substantially.

## §35n — GATE 0b: FAIL, AND THE SIGN IS INVERTED

Median gain is **0.0000 at every dose**, so the pre-registered bar (≥0.05) fails. But the median alone
would be a weak reading, so the **raw distribution** was computed in the primary session:

| e | n | **mean gain** | p10 | p25 | med | p75 | p90 | frac = 0 | frac > 0 | **frac < 0** |
|---|---|---|---|---|---|---|---|---|---|---|
| 0.90 | 5,406 | **−0.0424** | −0.2667 | −0.1111 | 0.0000 | 0.0000 | 0.1429 | 0.4517 | 0.1731 | **0.3751** |
| 1.20 | 13,092 | **−0.0415** | −0.3125 | −0.1429 | 0.0000 | 0.0000 | 0.1875 | 0.4092 | 0.2024 | **0.3884** |
| 1.60 | 21,958 | +0.0096 | −0.3333 | −0.1333 | 0.0000 | 0.1000 | 0.3333 | 0.3638 | 0.2907 | **0.3455** |

⛔ **The median is 0.0000 because 71-83% of rotated captures have gain ≤ 0** — `frac=0 + frac<0` is
0.8268 / 0.7976 / 0.7093. **That is a sign result, not a resolution artifact**, which is what §35l(b)
would otherwise have left ambiguous.
⛔ **Negatives outnumber positives at EVERY dose**, including e=1.6 where the mean is nominally
positive (+0.0096 with 0.3455 negative vs 0.2907 positive).
⛔ **Monotonicity is VACUOUS here** — "non-decreasing: True" over three identical zeros is not
dose-response evidence and must not be read as partial support.

⇒ ⭐⭐ **MY PRE-REGISTERED MECHANISM IS REFUTED, WITH THE SIGN INVERTED.** §35h bet that a steeper
falloff would keep the agent near recently-killed ground and raise in-range. The opposite holds:
**weakening the distant-loot pull moves the agent AWAY from in-range positions.** So the far-loot term
is, on net, pulling the agent **toward** the pack, not away from it — which inverts the intuition that
loot-chasing costs clearance. **Recording the prediction in advance is what makes this readable as a
refutation rather than as hindsight.**

## §35o — Reported, not barred

- `baseline_admitted` **29,570/32,994 = 0.8962**; `floor_admitted` identical; `body_floor` median
  **160.0** (the PACK constant, saturating — consistent with §33).
- Exits on the analysis set: `baseline_kept` 29,570 · `no_threats` 3,424.
- ⚠️ **`no_threats` is EXACTLY the 3,424 captures with no in-range inputs**, so every `no_threats`
  capture contributes to Gate 0a but **never** to Gate 0b. A structural asymmetry between the gates;
  it inflates 0a's denominator relative to 0b's by ~10%.
- ⚠️ **Mean in-range here (~0.46-0.51) is NOT comparable to the recorded agent figure 0.2801.**
  Different quantity: in-range 0.6 s ahead, conditioned on captures with living threats AND materials
  present. Same caveat §32 recorded for its 0.4774.
- One `_loot_attraction` non-reproduction was found during prototyping, at **wave 18** — outside the
  1..11 band and in the `falloff = dist` (non-early) branch, so it does not enter this analysis set.
  Flagged as the only known non-reproduction.
- `EARLY_LOOT_WAVE` (`config.gd:86`) and `EARLY_HUNT_WAVE` (`:100`) are **different constants that
  happen both to be 15** in this build. Asserted in the self-test so a future divergence breaks loudly.

## §35p — The §35f limitations still stand and were NOT resolved

`route.scores` is empty on `baseline_kept` (0/4,321) and `no_threats` (0/1,135), so **whether a rotated
baseline would still clear the body floor remains unmodellable** — a rotation may divert the tick to
`ranked`, where the command is orthogonal to the desire. That bias runs **toward a pass**, and the gate
failed anyway, so the verdict is **robust to it**: the unmodelled effect could only have made 0a's
reach smaller, and 0b failed on sign, not on reach.

Single-tick counterfactual on a stateful closed loop; this is **not** a survival claim.

## §35q — What this closes

**The desire layer at D5 is closed to the levers this controller exposes.** Combined with §31/§32/§33
(the route layer) and §34 (both `_build_desire` config knobs), the position is:

- The **route** layer: 4 levers priced, all dead.
- The **desire** layer: both config knobs structurally inert (§34), and the one term with real command
  authority — `loot` — priced here and **adverse** in the only direction its parameter can move it.

⇒ ⛔ **The D5 movement command is not reachable, in a beneficial direction, by any parameter currently
exposed.** [[brotato-in-range-headroom]]'s gap (human 0.4417 vs agent 0.2801, d=4.03) is **untouched
and still real** — five levers across two layers have now failed to convert it.
⭐ **A sixth lever on the same two layers is not indicated.** The next move should either change the
CONTROLLER STRUCTURE rather than a parameter, or leave movement entirely — §28's clearance result
(enemy-health doses move terminal wave, damage doses do not) remains the strongest live thread toward
North Star 1.
