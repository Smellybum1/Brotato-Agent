# Material crediting model test — Model A (immediate credit) vs corrected Model B (backlog pairing)

Date: 2026-07-25. Read-only telemetry analysis. 13 runs, policy `teacher_v1-0.1.125`.
Source: `%APPDATA%/Brotato/brotato_agent/runs/<run_id>/events.jsonl` (read only; no launches, deploys,
mod edits, or commits).

Model B tested here is the **corrected** formulation (backlog pairing, total conserved), not the
earlier 2x-value formulation:

```
collected(W) = pickups(W) + min(pickups(W), backlog(W-1))
backlog(W)   = [drops(W) - pickups(W)] + [backlog(W-1) - min(pickups(W), backlog(W-1))]
```

## Verdict

**The income accounting cannot discriminate between Model A and corrected Model B.** The corrected
Model B is in fact *harder* to separate from Model A than the earlier 2x version was, because it
conserves total currency — it only shifts timing, and the timing shift here is one wave on a quantity
that is almost always 1 unit.

The two models' income regressors differ by a mean absolute **0.77 units ≈ 0.8 gold**, against a
residual noise floor of **37 gold**. That is 2% of the noise. The fits are numerically
indistinguishable and the nesting test's confidence intervals contain both models' predictions.

**But the backlog reconstruction itself answers the questions that matter**, and it does so without
needing to win the A-vs-B fit — because under Model B the backlog is directly observable as the
on-ground count at wave end. Two findings dominate:

1. **The backlog never accumulates during play.** It clears every single non-terminal wave, in all
   13 runs. Median 1 unit, max 6.
2. **All the loss is terminal.** Every run ends with 11–50 units stranded — and under Model B that
   is genuinely lost income, averaging **~76 gold for victories and ~48 gold for defeats**.

So: the mechanic question is unresolved, but the *economic* question it was asked in service of has a
clean answer. See "What this means" below.

## Entity schema (as observed)

Material entities in `combat_capture.payload.entities.materials` carry:
`x, y, vx, vy, instance_id, id, category, type_id, radius, nx, ny`

- **No value/amount field.** Counts are the only unit; per-unit value is not recoverable. Treated as
  a proxy throughout.
- One `type_id` only across 307,533 observations: `res://items/materials/gold.gd`. `id` always empty.
- `summary.json` has `materials_spent = 0` and no material counter — there is no ground-truth
  material channel anywhere in telemetry. Gold accounting is the only available route.

Two capture artifacts are load-bearing:

1. **`instance_id` is pooled/recycled.** Per wave, distinct-instance_id count is *exactly* equal to
   peak simultaneous on-ground count, in every wave of every run — the signature of an object pool
   reissuing ids. The specified `drops_seen` metric (distinct instance_ids) is **not a drop counter**
   and was discarded. Substitute: `drops_appear(W)` = absent→present transitions within wave W.
   Biased up by pool reuse and window re-entry, biased down by cap saturation.
2. **The materials list is capped at 50 entities per capture**, saturating heavily in late waves
   (e.g. 837 saturated captures in wave 19 of run_1784946938_72738).

`pickups(W)` is taken as `drops_appear(W) - left_on_ground(W)`. The requested
disappearance-near-player discrimination was not separately implemented, and is not needed for the
main results: material does not despawn mid-wave, so mid-wave disappearance is pickup by
construction. The residual bias is that in cap-saturated late waves an entity can leave the 50-item
window without being collected, which inflates `drops_appear` and hence `pickups` together.

## 1. Backlog trajectory — it clears every wave, it never accumulates

Backlog reconstructed per wave by the corrected recursion. Because `pickups(W)` runs ~190 units/wave
while `backlog(W-1)` is ~1, the `min(pickups, backlog)` term is *always* the full backlog: the
backlog drains to zero within the first handful of pickups of the next wave and
`backlog(W)` collapses to `left_on_ground(W)`.

| run | result | backlog per wave (units, waves 1–19) | terminal |
|---|---|---|---|
| run_1784945653_24977 | defeat | 1 1 1 1 1 1 1 1 3 1 1 1 2 1 3 3 1 1 1 | **33** |
| run_1784946938_72738 | defeat | 1 1 1 1 3 2 1 2 2 3 1 5 1 1 1 1 1 1 1 | **47** |
| run_1784948107_34039 | victory | 1 1 2 1 3 2 1 1 5 1 3 1 2 1 1 1 1 1 1 | **40** |
| run_1784949300_58273 | defeat | 1 1 1 1 5 1 1 1 4 1 2 2 2 1 1 4 30 | **30** |
| run_1784950784_87944 | defeat | 1 1 1 1 2 1 2 1 2 2 1 1 1 2 2 1 1 1 1 | **14** |
| run_1784952010_30146 | defeat | 1 1 1 1 1 2 1 1 1 1 2 6 11 | **11** |
| run_1784952710_62975 | defeat | 1 1 1 1 1 2 1 1 3 3 1 3 1 2 1 1 18 | **18** |
| run_1784913937_22390 | victory | 1 1 5 1 1 1 1 1 1 4 1 1 1 2 2 1 2 2 1 | **25** |
| run_1784915512_76287 | victory | 1 1 1 1 1 1 1 2 3 3 2 3 2 1 1 1 2 1 1 | **50** |
| run_1784916694_13543 | victory | 3 2 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 | **13** |
| run_1784917880_11008 | victory | 1 1 2 1 1 1 1 1 1 5 6 4 1 1 1 2 2 1 2 | **50** |
| run_1784911798_60074 | defeat | 1 1 1 1 3 1 1 1 1 2 1 4 1 2 4 3 1 1 26 | **26** |
| run_1784912900_14544 | defeat | 1 1 1 1 2 4 1 2 3 1 1 2 47 | **47** |

**Median non-terminal backlog is 1 unit; maximum is 6.** There is no run in which backlog persists
across multiple waves. The trajectory is flat noise around 1 for the whole run and then jumps once,
at the terminal wave, because the run stopped.

This also explains why the A-vs-B fit cannot separate: Model B's departure from Model A is
`backlog(W-1) - left(W)` ≈ `1 - 1` ≈ 0 in almost every wave.

## 2. Terminal loss — the real number

Under Model B the terminal backlog was never paired off and never spent: genuinely lost income.
Gold conversion uses each run's own late-wave income-per-drop ratio (mean 1.84, range 1.32–2.39).

| | n | mean terminal backlog (units) | mean est. lost gold |
|---|---|---|---|
| **victories** | 5 | **35.6** | **~76** |
| **defeats** | 8 | **28.2** | **~48** |

Per run: victories 40/25/50/13/50 units (83/44/104/31/119 gold); defeats 33/47/30/14/11/18/26/47
units (59/90/52/27/15/26/45/69 gold).

Victories strand *more* than defeats, which is the expected direction — a victory always terminates
at the end of wave 20 with a full late-wave drop volume on the field, whereas a defeat can occur in a
thin early wave. Note this is not a lost *opportunity* in the same sense for victories: wave 20 income
would only have been spendable in a shop that a completed run never visits. For defeats the stranded
material is likewise unspendable, since the run is over. **Under Model B this material is lost, but it
is lost at a moment when it could not have been converted into build strength anyway.**

## 3. Cumulative lag at wave 9

By the end of wave 9 — the gold-binding early phase — the backlog sitting unbanked is:

- mean **2.31 units** (range 1–5),
- **0.30% of cumulative wave-2..9 income** (per-run range 0.10%–0.72%; cumulative income w2–9 is
  ~1300–1570 gold per run).

Under Model B, essentially none of the early-phase income is trapped in backlog. The gold-binding of
the early game is not being caused by deferred crediting.

## Fit statistics

n = 213 wave rows (waves with a shop at both W and W−1). Income = `gold_at_entry(W) −
gold_at_exit(W−1)`; `gold_at_entry` = `gold_before` of the first `purchase_decision` of shop W;
`gold_at_exit` = `gold_before` of the last decision minus its cost (buy price from the paired
`purchase_offer`, `reroll_price` for rerolls, 0 for `shop_go`). Income 43–835, mean 294, median 300,
**no negative incomes**.

Simple OLS, `income ~ a·X + b`:

| model | regressor X | slope | MAE | R² | corr |
|---|---|---|---|---|---|
| A | `drops(W)` | 1.521 | **67.47** | 0.6877 | 0.8293 |
| B (corrected) | `pickups(W) + min(pickups(W), backlog(W−1))` | 1.523 | **67.20** | 0.6889 | 0.8300 |

Mean absolute regressor difference: **0.77 units** against a mean of 193.8. Model B's 0.27-gold MAE
advantage is noise.

Unconstrained nesting test with run + wave fixed effects (R² = 0.896, MAE = 37.16):

| coefficient | estimate | 95% CI | Model A predicts | Model B predicts |
|---|---|---|---|---|
| `drops(W)` | 1.046 | [0.820, 1.273] | a | a |
| `backlog(W−1)` | −0.779 | [−9.873, 8.314] | **0** | **+1.046** |
| `left(W)` | −2.807 | [−11.529, 5.916] | **0** | **−1.046** |

Both models' predictions lie inside both intervals. The intervals are ~9–17 gold wide because
`backlog` and `left` have standard deviations near 1.0 — there is no variance to regress against.

**The requested sharp check (large leftover in W → income excess in W+1) cannot be run**: the largest
non-terminal backlog anywhere in the dataset is 6 units, whose Model-B excess is ~6 gold, a sixth of
the residual noise. All 13 large backlogs are terminal-wave, with no wave W+1 in existence.

## Unexplained variance

- Simple model: R² ≈ 0.69, MAE ≈ 67 gold on mean income 294 (23%).
- Run+wave fixed effects: R² ≈ 0.896, MAE ≈ 37 gold (13%).
- Model-separating signal: **0.8 gold.**

Unmodelled and unrecoverable from telemetry: harvesting-stat growth (income per drop-proxy drifts
from ~1.05 in wave 2 to ~2.2–2.5 by wave 18, consistent with harvesting/level-up scaling and *not*
with either crediting model), item and effect gold, crates, consumables, and per-unit material value
variation the schema does not expose. Combined with the drop-proxy's own two-sided bias, the residual
is ~45x the effect under test. **This is the reason for non-discrimination, and it is not fixable by
more of the same data.**

## What this means for uncollected materials

- **The A-vs-B mechanic question is not settled by these logs, and cannot be.** The prior conclusion
  in `reports/wp2/materials_collection_analysis.md` — "end-of-wave auto-collect banks everything" —
  was and remains an unsupported inference; the drain to zero is equally consistent with a backlog
  handoff. This analysis does not rescue it, does not refute it, and does not confirm the operator's
  model either. It reports that gold accounting is blind at this magnitude.
- **Regardless of which model is true, in-run uncollected material is not a live loss channel.**
  Backlog clears every non-terminal wave in all 13 runs; median 1 unit; 0.30% of cumulative income at
  wave 9. The agent is already collecting essentially everything it drops while the wave is live.
  There is no recoverable income sitting on the floor mid-run.
- **The only material loss under Model B is terminal** (~76 gold victories, ~48 gold defeats), and it
  is stranded at a point where no shop remains to spend it. It does not represent a build-strength
  opportunity that better collection behaviour could capture.
- **Practical consequence: do not spend engineering effort on mid-wave collection behaviour on the
  strength of this hypothesis.** Neither model implies recoverable income. If the mechanic must be
  settled for other reasons, it needs a telemetry change (per-capture player material/gold counter,
  plus a per-entity value field, plus lifting or reporting the 50-entity cap) or a deliberate
  experiment that strands a large pile in a *survivable* mid-run wave — a state this policy never
  naturally produces.

## Reproduction

Two full streaming passes over 13 × ~240 MB `events.jsonl`; backlog recursion and fits computed from
the extracted per-wave table. All derived rows and per-run backlog trajectories are in the companion
JSON (`reports/wp2/material_crediting_model_test.json`, keys `per_wave_rows` and `per_run`).
