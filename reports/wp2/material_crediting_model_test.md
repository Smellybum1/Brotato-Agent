# Material crediting model test — Model A (immediate credit) vs Model B (backlog pairing)

Date: 2026-07-25. Read-only telemetry analysis. 13 runs, policy `teacher_v1-0.1.125`.
Source: `%APPDATA%/Brotato/brotato_agent/runs/<run_id>/events.jsonl` (read only; no launches, deploys,
mod edits, or commits; live F2 campaign untouched).

> ## RETRACTION OF THE PREVIOUS VERSION
>
> The previous version of this report measured `left_on_ground(W)` at **the last capture before the
> drain to zero**. That capture lies *inside* a post-wave-timer window of ~40–57 capture ticks
> (~2 s at 20 Hz) during which the on-ground count drains smoothly to zero. The measurement therefore
> read the count *after* the end-of-wave collection had largely run, yielding a median leftover of 1.
> **The correct measure is the count at the last capture with `wave_time.remaining_sec > 0`,** which
> gives a median of 28. The previous "cannot discriminate" verdict rested entirely on that
> mismeasurement and is **RETRACTED**.
>
> Verified independently against the coordinator's figures before re-running: run_1784913937_22390
> median 26.0 / mean 25.6 / max 50, and run_1784911798_60074 median 26.0 / mean 30.4 / max 50 — both
> reproduce exactly.

## Verdict

**Model A is rejected. The data support a deferred-crediting mechanism of Model B's form.**

In the fixed-effects nesting test the coefficient on `backlog(W−1)` is **+2.70, 95% CI
[1.62, 3.79], t = 4.89**. Model A requires this to be **0**; zero is excluded in every specification
tested, including subsamples with no censoring at all. Leftover material at wave end demonstrably
carries forward into the *next* wave's income.

Model B is directionally correct and quantitatively consistent on the clean subsamples, but the
full-sample magnitude overshoots its prediction — discussed under "Where Model B does not quite fit".

## Corrected measurement

| | old (mismeasured) | corrected (timer-end) |
|---|---|---|
| definition | last non-zero capture | last capture with `remaining_sec > 0` |
| median | 1.0 | **28.0** |
| mean | 3.2 | **28.2** |
| max | 50 | 50 |
| n | 239 | 239 |

**Post-timer window behaviour** (directly relevant to interpretation, see caveat at the end): on every
non-terminal wave there are 40–57 further capture ticks with `remaining_sec == 0`, across which the
count drains **smoothly and monotonically** to zero — e.g. wave 19 of run_1784945653_24977:
`50, 50, 49, 49, 48, 46, 46, … 36, 31, 22, 12, 12, 10, 8, … 0`. It is a ramp, not an instantaneous
despawn. **Terminal waves have exactly 0 post-timer ticks in all 13 runs** (verified), so on terminal
waves the two measures coincide — a useful consistency check, and they do coincide exactly.

## 1. Distribution and censoring rate by wave band

The materials entity list is **capped at 50 per capture**. Leftover values of 50 are therefore
**censored lower bounds**, not measurements.

| wave band | n | median leftover | mean | **censoring rate** | leftover / drops |
|---|---|---|---|---|---|
| 1–4 | 52 | 4.0 | 5.0 | 0.0% | 0.096 |
| 5–8 | 52 | 22.0 | 23.2 | 0.0% | 0.146 |
| 9–12 | 52 | 40.5 | 39.1 | **23.1%** | 0.153 |
| 13–16 | 46 | 45.0 | 39.4 | **30.4%** | 0.184 |
| 17–20 | 37 | 49.0 | 38.9 | **43.2%** | 0.237 |
| **all** | 239 | 28.0 | 28.2 | 17.6% | — |

**Censoring makes Model B's predicted effect an underestimate.** True leftover in censored waves
exceeds 50, so the true backlog carried into W+1 is larger than measured, and the true share of each
wave's material left on the floor is higher than the table shows — most severely in waves 17–20,
where 43% of observations are at the ceiling.

## 5. Leftover as a fraction of that wave's drops

From the table above: **9.6% in waves 1–4 rising monotonically to 23.7% in waves 17–20** (and those
late-wave figures are downward-biased by censoring). Roughly **one sixth of all material dropped is
still on the floor when the wave timer expires**, rising to at least a quarter late.

## 2. Model fits

n = 213 wave rows. Income = `gold_at_entry(W) − gold_at_exit(W−1)`; `gold_at_entry` = `gold_before` of
the first `purchase_decision` of shop W; `gold_at_exit` = `gold_before` of the last decision minus its
cost. Income 43–835, mean 294, no negatives.

Simple OLS, `income ~ a·X + b`. The regressors now differ by a mean absolute **8.54 units** (4.4% of
scale) rather than 0.77:

| model | regressor | slope | MAE | R² | corr |
|---|---|---|---|---|---|
| A | `drops(W)` | 1.521 | 67.47 | 0.6877 | 0.8293 |
| **B** | `pickups(W) + min(pickups(W), backlog(W−1))` | 1.539 | **62.03** | **0.7239** | **0.8508** |

Model B now beats Model A outright — MAE 62.03 vs 67.47, R² 0.724 vs 0.688.

### Nesting test (run + wave fixed effects)

`income ~ drops(W) + backlog(W−1) + left(W) + wave FE + run FE`

| subsample | n | drops(W) | **backlog(W−1)** | left(W) | Model A pred. | Model B pred. |
|---|---|---|---|---|---|---|
| all | 213 | 1.182 | **+2.704 [1.619, 3.789]** | −1.083 [−2.069, −0.098] | 0 / 0 | +1.182 / −1.182 |
| uncensored only | 155 | 0.949 | **+1.470 [0.836, 2.105]** | −1.570 [−2.179, −0.961] | 0 / 0 | +0.949 / −0.949 |
| waves ≤ 8 (zero censoring) | 91 | 0.937 | **+1.250 [0.767, 1.733]** | −0.681 [−1.105, −0.256] | 0 / 0 | +0.937 / −0.937 |

- **Model A predicts both leftover coefficients are 0. Zero is excluded from the `backlog(W−1)` CI in
  all three specifications, including the wholly uncensored waves ≤ 8.** Model A is rejected, and not
  as an artefact of censoring.
- **Model B's predictions fall inside the CIs on both clean subsamples** (uncensored: predicts 0.949,
  CI [0.836, 2.105]; waves ≤ 8: predicts 0.937, CI [0.767, 1.733]). The `left(W)` coefficient is
  negative as Model B requires in all three.
- R² rises 0.688 → 0.908 and MAE falls to 34.82 with fixed effects.

### Where Model B does not quite fit

On the **full** sample the backlog coefficient is 2.70 against Model B's predicted 1.18 — a ratio of
**2.29**, with Model B's prediction *outside* the CI. Two readings, not separable here:

1. **Censoring bias.** Censored waves understate backlog; the regression compensates with a larger
   coefficient. This is supported by the gradient: the ratio falls from 2.29 (all) to 1.55
   (uncensored) to 1.33 (waves ≤ 8) as censoring is removed. This is the reading I favour.
2. **A super-conserving credit.** A ratio near 2 is what the *original* (later withdrawn) 2x-value
   formulation predicted. It cannot be dismissed from these data alone — but the censoring gradient
   is a sufficient explanation and does not require new mechanics.

## 3. Sharp spot checks — waves with leftover ≥ 40 followed by a survived wave

71 such cases exist. Raw comparison of `income(W+1)/drops(W+1)` against each run's median ratio:
**66 of 71 are elevated**, many by 30–100%+ (e.g. run_1784916694_13543 w14: +223%; w10: +112%;
run_1784917880_11008 w16: +153%).

**That raw comparison is confounded** — leftover ≥ 40 occurs mostly in late waves, and the
income-per-drop ratio rises with wave anyway (harvesting growth). Controlling for it by comparing each
observation to the **same-wave mean across runs**:

| group | n | mean residual income/drops |
|---|---|---|
| leftover(W−1) ≥ 40 | 68 | **+0.108** |
| leftover(W−1) < 20 | 78 | **−0.034** |
| **difference** | | **+0.142, 95% CI [+0.025, +0.258]** |

Model A predicts a difference of **0**; it is excluded. Waves following a large leftover earn
measurably more gold per unit dropped than waves following a small one, at the same wave index.

## 4. Terminal loss

All 13 terminal waves have **0 post-timer ticks** — confirmed, so terminal leftover is never subject
to the post-timer drain and is genuinely stranded. Gold conversion uses each run's own late-wave
income-per-drop ratio.

| run | result | last wave | leftover | est. gold | % of run total income |
|---|---|---|---|---|---|
| run_1784945653_24977 | defeat | 20 | 33 | 59 | 1.1% |
| run_1784946938_72738 | defeat | 20 | 47 | 90 | 1.8% |
| run_1784948107_34039 | victory | 20 | 40 | 83 | 1.2% |
| run_1784949300_58273 | defeat | 17 | 30 | 52 | 1.3% |
| run_1784950784_87944 | defeat | 20 | 14 | 27 | 0.5% |
| run_1784952010_30146 | defeat | 13 | 11 | 15 | 0.6% |
| run_1784952710_62975 | defeat | 17 | 18 | 26 | 0.7% |
| run_1784913937_22390 | victory | 20 | 25 | 44 | 0.9% |
| run_1784915512_76287 | victory | 20 | 50 | 104 | 1.9% |
| run_1784916694_13543 | victory | 20 | 13 | 31 | 0.4% |
| run_1784917880_11008 | victory | 20 | 50 | 119 | 2.4% |
| run_1784911798_60074 | defeat | 19 | 26 | 45 | 0.8% |
| run_1784912900_14544 | defeat | 13 | 47 | 69 | 3.0% |

| | n | mean leftover | mean gold | mean % of total run income |
|---|---|---|---|---|
| victories | 5 | 35.6 | 76 | **1.4%** |
| defeats | 8 | 28.2 | 48 | **1.2%** |

Victories strand more in absolute terms (they always end at wave 20 with full late-wave drop volume);
as a share of total income the two are close. **Terminal loss is real under Model B but small —
~1–3% of a run's income — and it is stranded at a point where no shop remains to spend it.**

## What this means for uncollected materials

- **Uncollected material is delayed income, not lost income, for the duration of the run.** The
  backlog coefficient is positive and significantly non-zero: material left at timer-end reappears in
  the next wave's income. Model A's "everything is banked immediately" is refuted.
- **The delay is economically real and not small in flow terms.** One sixth of each wave's material
  (rising to a quarter or more late, censoring-biased downward) is still on the floor at timer-end
  and arrives one wave later. In the early gold-binding phase this shifts purchasing power one shop
  later than a Model-A accounting would predict — which matters for shop-policy work, because it
  means early-wave income is systematically front-loaded in the model and back-loaded in reality.
- **Genuine loss is confined to the terminal wave** — 1.2–1.4% of total run income, unspendable
  anyway since the run is over. Not a target for optimisation.
- **The actionable target is timing, not recovery.** Faster in-wave collection does not create new
  currency under Model B; it moves currency one wave earlier. Whether that is worth engineering
  effort depends on how binding the early-wave shop budget is — the 9.6% leftover fraction in waves
  1–4 is the relevant number, and it is the smallest of the run.

### Caveat I am obliged to flag

The post-timer window drains **smoothly and monotonically** from the timer-end value to zero over
~2 s. That shape is what an end-of-wave vacuum/magnet animation looks like — material being collected,
not despawning. If those post-timer pickups are credited to wave W, then the economically effective
leftover is the *post-drain* value (≈1) rather than the timer-end value (≈28), and the flow
magnitudes above would shrink drastically. **What the income regression establishes is that leftover
at timer-end predicts next-wave income with a coefficient reliably above zero** — that finding is
robust and kills Model A regardless. The *magnitude* of the delayed flow depends on which side of the
post-timer window the credit lands, and telemetry cannot see the credit event itself. Resolving that
needs a per-capture player material/gold counter — with one, this question closes in a single run.

## Reproduction

Three full streaming passes over 13 × ~240 MB `events.jsonl` (the third re-measuring at
`remaining_sec > 0`). Note the drop proxy remains `drops_appear` = absent→present instance_id
transitions: `instance_id` is pooled/recycled (distinct-id count per wave exactly equals peak
simultaneous count in every wave of every run), so distinct-id counting is not a drop counter.
Material entities carry **no value field** and one `type_id` only
(`res://items/materials/gold.gd`); `summary.json` has `materials_spent = 0` and no material counter.
Counts are proxies for value throughout. All derived rows, per-run backlog trajectories, and the
three nesting specifications are in the companion JSON
(`reports/wp2/material_crediting_model_test.json`).
