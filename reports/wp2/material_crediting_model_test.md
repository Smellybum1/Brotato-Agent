# Material crediting model test — Model A (immediate 1x) vs Model B (deferred 2x)

Date: 2026-07-25. Read-only telemetry analysis. 13 runs, policy `teacher_v1-0.1.125`.
Data source: `%APPDATA%/Brotato/brotato_agent/runs/<run_id>/events.jsonl` (read only; no launches, deploys, or mod edits).

## Verdict

**The data cannot discriminate between Model A and Model B.** Not because the models fit equally
badly, but because the quantity that separates them — materials left on the ground at wave end — is
**essentially always 1** during waves the agent survives. The two models therefore make predictions
about wave income that differ by **1.9 gold on average**, against a residual noise floor of
**37 gold** (best model) / **67 gold** (simple model). The separation is ~5% of the noise. No amount
of the available data settles the question.

The more consequential finding is that the question is close to moot for these runs: **the agent
does not leave meaningful material on the ground in any wave it survives.**

## Entity schema (as observed)

Material entities in `combat_capture.payload.entities.materials` carry:

`x, y, vx, vy, instance_id, id, category, type_id, radius, nx, ny`

- **There is no value/amount field.** Counts are the only available unit; per-unit value cannot be
  recovered from telemetry. Stated as a limitation, not worked around.
- Only one `type_id` was ever observed across 307,533 material observations in the sampled run:
  `res://items/materials/gold.gd`. No type-level value differentiation is visible.
- `id` is always empty.

Two capture artifacts materially affect drop counting:

1. **`instance_id` is pooled/recycled.** Per wave, the count of distinct instance_ids is *exactly*
   equal to the peak simultaneous on-ground count, in every wave of every run. That is the signature
   of an object pool handing back the same ids. The originally-specified `drops_seen` metric
   (distinct instance_ids) is therefore **not a drop counter** and was discarded.
2. **The materials list is capped at 50 entities per capture.** The cap saturates frequently in late
   waves (e.g. 837 saturated captures in wave 19 of run_1784946938_72738), so on-ground counts and
   any drop proxy are censored from above there.

Substitute drop proxy used: `drops_appear(W)` = number of absent→present instance_id transitions
within wave W. This is upward-biased (pool reuse, and entities re-entering the 50-item window) and
downward-biased when the cap saturates. It correlates well with income (r = 0.83 raw, R² = 0.90 with
run+wave fixed effects) but its absolute scale is not trustworthy.

## left_on_ground: the decisive observation

`left_on_ground(W)` = on-ground count at the last capture before the terminal run of zeros in wave W.

Across 239 wave-observations:

| statistic | value |
|---|---|
| median | **1** |
| mean | 3.15 |
| p90 | 4 |
| max | 50 |
| **max on any non-terminal wave** | **6** |

Every `left_on_ground >= 10` occurs on the **terminal wave of a run** (the wave in which the agent
died, or wave 20 of a victory) — where the pile is simply the material still on the field when the
run stopped, and no wave W+1 exists to inspect. Representative terminal values: 33, 47, 40, 30, 14,
11, 18, 25, 50, 13, 50, 26, 47.

The tail shape of a normal wave is a gradual decline, not a cliff, e.g.
`[11, 7, 4, 3, 2, 1, 0, 0, 0, …]` — consistent with the player picking material up through the wave
and one or two stragglers remaining at the end.

## The sharpest single check — unavailable

The requested spot check (find waves with LARGE `left_on_ground(W)`, look for excess income in W+1)
**cannot be run on this data**: there are no non-terminal waves with a large pile. The largest
non-terminal `left_on_ground` is 6, whose model-B excess (2×6 = 12 gold) is a third of the residual
noise. All 13 large piles are terminal.

## Fit statistics

n = 213 wave rows (waves with both a shop at W and a shop at W−1). Income is
`gold_at_entry(W) − gold_at_exit(W−1)`, with `gold_at_entry` = `gold_before` of the first
`purchase_decision` of shop W, and `gold_at_exit` = `gold_before` of the last decision minus its cost
(buy price from the paired `purchase_offer`, `reroll_price` for rerolls, 0 for `shop_go`).
Income range 43–835 gold, mean 294, median 300; **no negative incomes** (a sanity check that the
shop reconstruction is not badly broken).

Simple OLS, `income ~ a·X + b`:

| model | regressor X | slope a | MAE | R² | corr |
|---|---|---|---|---|---|
| A (immediate 1x) | `drops(W)` | 1.521 | **67.47** | 0.6877 | 0.8293 |
| B (deferred 2x) | `drops(W) − left(W) + 2·left(W−1)` | 1.521 | **67.09** | 0.6888 | 0.8299 |

The regressors differ by a mean absolute 1.80 units against a mean of 194 units. Model B's 0.4-gold
MAE advantage is noise, not evidence.

Unconstrained nesting test (run + wave fixed effects, R² = 0.896, MAE = 37.16):

| coefficient | estimate | 95% CI | Model A predicts | Model B predicts |
|---|---|---|---|---|
| `drops(W)` | 1.046 | ±0.226 | a | a |
| `left(W−1)` | −0.779 | ±9.094 | **0** | **+2.093** |
| `left(W)` | −2.807 | ±8.723 | **0** | **−1.046** |

Both models' predicted values sit comfortably inside both confidence intervals. The CIs are ~9 gold
wide because `left` has a standard deviation of only ~1.0 — there is no leverage. The point estimates
lean very slightly against Model B on `left(W−1)` (−0.78 vs the predicted +2.09) and slightly toward
a larger-than-either penalty on `left(W)`, but neither is separated from zero or from the alternative.

## Unexplained variance

Substantial, and it is what blocks discrimination:

- Simple model: R² ≈ 0.69, MAE ≈ 67 gold on mean income 294 (23%).
- With run and wave fixed effects: R² ≈ 0.896, MAE ≈ 37 gold (13%).
- Model-separating signal: **1.9 gold**.

Known unmodelled gold sources, none of which telemetry lets us net out: harvesting stat growth
(the income-per-drop-proxy ratio drifts from ~1.05 in wave 2 to ~2.2–2.5 by wave 18, which is
consistent with harvesting/level-up scaling rather than with either crediting model), item and
effect-based gold, consumables, crates, and per-unit material value differences that the schema does
not expose. Add the drop-proxy's own bias (pool reuse up, 50-cap censoring down) and the residual is
an order of magnitude larger than the effect under test.

## What this means for uncollected materials

For these 13 runs, the practical answer does not depend on which model is true:

- **Uncollected material is not a live loss channel during survived waves.** The typical wave ends
  with 1 unit on the ground (median 1, p90 4). Whether that unit is banked, deferred at 2x, or lost
  outright, it is worth on the order of 1–3 gold against a per-wave income of ~300 gold — under 1%.
- **The only large piles are terminal-wave piles**, where the run has already ended. Under any model
  those are irrelevant to the run's economy: there is no subsequent wave or shop to spend in.
- The prior conclusion in `reports/wp2/materials_collection_analysis.md` — "end-of-wave auto-collect
  banks everything" — remains **an unsupported inference**, exactly as the operator says. The drain
  to zero is equally consistent with despawn. This analysis does not rescue it; it also does not
  refute it, and it does not confirm the operator's deferred-2x model either. The income accounting
  is simply blind at this magnitude.
- If the deferred-2x mechanic needs to be settled, it will not be settled by these logs. It needs
  either a telemetry change (emit the player's material/gold counter per capture, and a per-entity
  value field) or a deliberate experiment that leaves a large pile on the ground in a survivable
  mid-run wave and reads income in W+1 — neither of which this policy's behaviour produces naturally.

## Reproduction

Two full streaming passes over 13 × ~240 MB `events.jsonl`. Extraction scripts in the session
scratchpad; all derived per-wave rows are in the companion JSON
(`reports/wp2/material_crediting_model_test.json`, key `per_wave_rows`).
