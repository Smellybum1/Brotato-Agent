# Materials collection analysis — is the agent leaving currency on the ground?

Read-only analysis of 13 runs on teacher policy `teacher_v1-0.1.125-gun-wp1`
(7 F2-campaign runs + 6 Stage F batch runs), 248,113 `combat_capture` ticks.
No game launch, no deploy, no mod changes. Raw per-run/per-wave numbers in
`materials_collection_analysis.json`.

## Headline

**The agent leaves essentially nothing on the ground. There is no material
headroom here.** Across all 226 wave boundaries in these 13 runs, the number of
on-ground materials at the final capture of the wave is **0**, and **0** material
instance ids ever survive into the next wave. Brotato's end-of-wave auto-collect
vacuums the entire field, and the capture stream shows it happening: in
`run_1784913937_22390` wave 12, once `remaining_sec` hits 0 the count decays
`12 → 11 → 9 → 8 → 6 → 5 → 3 → 1 → 0` over ~9 captures (~0.45 s), then stays at 0
for the remaining 26 captures of the wave.

Every material that drops is banked. The "uncollected at wave end" proxy is
identically **zero for every run, victory and defeat alike**.

## 1. On-ground material counts and truncation

| Wave band | ticks | mean on-ground | peak | ticks with a material ≤150u | ignore rate | hp lost | hp / 1k ticks |
|---|---|---|---|---|---|---|---|
| w1–5   | 41,834 | 4.48 | 32 | 17.9% | 10.8% | 0 | 0.00 |
| w6–10  | 73,243 | 17.50 | 49 | 31.1% | 29.7% | 47 | 0.64 |
| w11–15 | 75,520 | 22.94 | 52 | 28.3% | 36.1% | 195 | 2.58 |
| w16–19 | 49,244 | 23.62 | 53 | 23.3% | 40.3% | 336 | 6.82 |
| w20    | 8,272 | 18.55 | 50 | 15.4% | 51.4% | 480 | 58.03 |

### Truncation: does not undermine the estimate, but the field is not a clean gauge

- `payload.dropped_counts.materials` is **0 on all 248,113 ticks**. This field is
  **hardcoded to `0`** in `runtime/agent_controller.gd` (the `dropped_counts`
  dict is a literal with every entry `0`) — it carries **no information** and must
  not be read as evidence of no truncation.
- The real check is the capture path: `_collect_loot()` in
  `runtime/agent_controller.gd` and `adapter/game_adapter.gd` iterates the full
  `main._golds` array with **no cap and no slice**. So there is genuinely **no
  capture-side truncation** — the emitted list is the complete live list.
- However, counts pin against a **game-side ceiling near 50** (global max 53;
  12.7% of ticks ≥45, 8.0% of ticks ≥50). Brotato's own `_golds` list is
  effectively capped/merged around that value. So *mean and peak on-ground counts
  are censored from above* and are a lower bound on materials dropped. This does
  **not** affect the headline, because the wave-end result (0 remaining, 0
  carry-over) is a floor observation, not a count.

## 2. "Uncollected at wave end" proxy

Counts persist through the wave — the last 1.5 s of a wave averages 13–24
on-ground materials — and then go to 0 within ~0.5 s of the timer expiring.
Materials are **auto-collected at wave end, not lost**. The data does not merely
fail to show loss; it positively shows the vacuum.

| | boundaries | mean count at wave's last capture | max count at last capture | max instances surviving into next wave |
|---|---|---|---|---|
| all 13 runs | 226 | 0.000 | 0 | 0 |

## 3. "Ignoring nearby loot" rate

Definition: a capture tick where the nearest material is within 150 units **and**
`dot(teacher.action, vector_to_nearest_material) < 0`.

- **Overall: 31.9%** of near-loot ticks have the commanded vector pointing away.
- By band: 10.8% (w1–5) → 29.7% (w6–10) → 36.1% (w11–15) → 40.3% (w16–19) →
  **51.4% (w20)**. The rate rises monotonically with wave difficulty.
- Mean distance to nearest material across all runs: 234–258 units per run.

**This rate is a kinematic descriptor, not a loss measure.** Given the wave-end
vacuum, a tick spent moving away from a material costs nothing — the material is
collected anyway, either later in the wave or by the end-of-wave sweep. A high
ignore rate is only actionable if it also implied lost currency, and it does not.

## 4. Correlation with outcome

| | n | ignore rate | mean on-ground | mean nearest dist | uncollected at wave end | hp / 1k ticks | mean final wave |
|---|---|---|---|---|---|---|---|
| victory | 5 | **31.86%** | 18.89 | 241.4 | **0** | 2.81 | 20.00 |
| defeat  | 8 | **31.98%** | 17.71 | 234.3 | **0** | 5.35 | 17.38 |

**No correlation.** The ignore rate is identical between victories and defeats
(0.12 pp apart). The uncollected proxy is zero in both arms, so it cannot
correlate with anything. Damage rate separates the arms cleanly (2.81 vs 5.35 hp
per 1k ticks); loot behaviour does not.

Note the confound in the per-wave band numbers: the ignore rate rises with wave
number, and defeats end earlier, so a naive per-run average is if anything
*biased against* victories — and the two are still equal.

## 5. Banked income (shop gold at entry), for scale

Gold at the first `purchase_offer` of each shop, pooled across the 13 runs:

| after wave | n | mean gold | min | max |
|---|---|---|---|---|
| 1 | 13 | 63.7 | 59 | 70 |
| 3 | 13 | 96.3 | 72 | 125 |
| 5 | 13 | 158.5 | 127 | 214 |
| 7 | 13 | 250.3 | 205 | 293 |
| 9 | 13 | 480.4 | 388 | 590 |
| 11 | 13 | 508.1 | 307 | 838 |
| 13 | 11 | 501.3 | 199 | 760 |
| 15 | 11 | 561.7 | 252 | 1562 |
| 17 | 9 | 511.4 | 316 | 702 |
| 19 | 8 | 670.0 | 436 | 971 |

Income is healthy and rising; the spread at w15–19 (252 → 1562) is dominated by
*spending* policy, not collection. Since ground loss is zero, **the entire lever
on material economy is the shop layer, not pickup behaviour** — consistent with
the existing v126 rich-exit evidence.

## 6. Threat-context split (operator follow-up)

Contexts assigned per capture tick, exclusive with priority
`d_boss > c_projectiles > b_enemies > a_clear`; "within 300 units" for enemies and
projectiles; `d_boss` = `entities.bosses` non-empty.

| context | % of ticks | mean on-ground | near-loot % | ignore rate | share of all ignore ticks | hp lost | share of total hp | hp / 1k ticks |
|---|---|---|---|---|---|---|---|---|
| a_clear (no enemy/proj ≤300) | 80.5% | — | 24.4% | 27.3% | **64.8%** | 0 | **0.0%** | 0.00 |
| b_enemies (enemies ≤300, no proj) | 14.2% | — | 36.8% | 45.4% | **28.7%** | 494 | 46.7% | 13.99 |
| c_projectiles (proj ≤300) | 2.0% | — | 26.3% | 51.0% | 3.3% | 84 | 7.9% | 16.57 |
| d_boss (boss present) | 3.3% | — | 15.8% | 51.4% | 3.2% | 480 | **45.4%** | **59.27** |

Non-exclusive overlays:

| overlay | ticks | % of all ticks | ignore rate | hp lost | share of total hp | hp / 1k ticks |
|---|---|---|---|---|---|---|
| any projectile ≤300 | 9,259 | 3.7% | 50.7% | 332 | **31.4%** | 35.86 |
| boss present | 8,098 | 3.3% | 51.4% | 480 | **45.4%** | 59.27 |
| all ticks | 248,113 | 100% | 31.9% | 1,058 | 100% | 4.26 |

**Plainly: the loot being ignored is overwhelmingly in SAFE contexts.**
93.5% of ignore ticks occur with no projectile within 300 units and no boss on
screen (64.8% in fully clear space, 28.7% with enemies but no projectiles). Only
6.5% of ignored-loot ticks are in the projectile/boss contexts. So the current
caution is *not* what explains the ignoring — the agent walks away from loot
mostly when nothing is threatening it.

That would be a headroom finding **if the ignored loot were ever lost. It is
not.** The agent is already collecting 100% of it. The correct reading is that
the potential field simply does not weight materials strongly in clear space
because it does not need to — the vacuum collects the remainder for free.

The damage picture confirms the operator's observation about threat type:
**45.4% of all damage across these runs is taken while a boss is present, in just
3.3% of ticks** (59.3 hp/1k ticks vs a 4.26 baseline, ~14×), and 31.4% while a
projectile is within 300 units (3.7% of ticks, ~8×). Enemy-only contexts carry
46.7% of damage but across 4.3× more ticks (14.0 hp/1k, ~3×). Clear-space ticks
(80.5% of the run) take **exactly zero** damage.

### Wave 20 (boss wave)

| run | result | mean proj ≤300 | p90 proj ≤300 | hp lost | hp / 1k ticks | boss-tick % | ignore rate |
|---|---|---|---|---|---|---|---|
| run_1784945653_24977 | defeat | 0.45 | 1 | 109 | 88.5 | 98% | 48.1% |
| run_1784946938_72738 | defeat | 0.46 | 1 | 128 | 141.6 | 98% | 51.6% |
| run_1784948107_34039 | victory | 7.18 | 12 | 17 | 23.1 | 97% | 56.6% |
| run_1784950784_87944 | defeat | 5.14 | 14 | 46 | 96.4 | 96% | 61.5% |
| run_1784913937_22390 | victory | 0.38 | 2 | 75 | 97.5 | 97% | 42.0% |
| run_1784915512_76287 | victory | 7.79 | 13 | 52 | 28.9 | 99% | 53.0% |
| run_1784916694_13543 | victory | 7.24 | 12 | 37 | 27.7 | 98% | 51.4% |
| run_1784917880_11008 | victory | 7.30 | 12 | 16 | 15.7 | 98% | 52.1% |

Wave 20 is 3.3% of all capture ticks but **45.4% of all damage taken**. Two
distinct boss profiles appear: a low-projectile variant (mean ≤0.5 proj within
300) and a dense-projectile variant (mean ~5.1–7.8, p90 12–14). Note the
counter-intuitive split — the five dense-projectile runs average **38.4 hp/1k**
while the three low-projectile runs average **109.2 hp/1k**. Under this small n (8 runs)
that inverts the "weak against boss projectiles" hypothesis at the *aggregate
damage* level: the runs that bleed are the low-projectile ones, where damage is
presumably contact/melee from the boss rather than projectiles. This is
suggestive only, not evidence — boss identity is not recorded in these fields and
the two groups may simply be different bosses with different difficulty.

## Estimator limitations

1. **`dropped_counts` is uninformative.** Hardcoded `0`. Absence of truncation is
   established from the mod source (uncapped `_golds` iteration), not from this field.
2. **Game-side ceiling ~50.** 8.0% of ticks sit at ≥50 materials. Mean/peak
   on-ground counts are censored from above and are lower bounds on drops. The
   wave-end zero result is unaffected.
3. **~20 Hz sampling.** A material could in principle appear and be collected
   between captures; this would cause under-counting of drops, not of leftovers.
4. **Auto-collect vs genuinely lost.** The data cannot distinguish "the agent
   walked over it" from "the end-of-wave sweep took it" for any individual
   material. It does not need to: both bank the currency. The economically
   relevant question — is any material forfeited — answers cleanly as no.
5. **Damage attribution** uses full-stream hp drops between consecutive captures
   within the same wave, per `wp2_residual_checkpoint_compare.py`'s primary view.
   `player_damage` events are far too sparse to use (4 events vs 76 hp taken in
   `run_1784913937_22390`). Reconstructed totals match `summary.damage_taken`
   within a few hp on 11/13 runs; two runs undercount
   (`run_1784945653_24977` 109 vs 168, `run_1784916694_13543` 77 vs 135), likely
   damage spanning wave boundaries or recovery gaps, which this method skips.
6. **n = 13 runs, 5 victories.** All outcome splits are underpowered. The
   ignore-rate null (31.86% vs 31.98%) is tight enough to be meaningful; the
   wave-20 projectile-profile inversion is not.
7. **The ignore metric ignores magnitude and persistence.** A single tick with a
   negative dot product is not "abandoning" loot; the agent may pick it up two
   seconds later. Treat 31.9% as an upper bound on genuine avoidance.

## Read

There is **no headroom in ground collection**. The agent banks 100% of dropped
material — the end-of-wave auto-collect guarantees it, and the capture stream
confirms it at all 226 wave boundaries in these runs. The 31.9% "ignoring nearby
loot" rate is real as a movement descriptor and is concentrated in safe contexts
(93.5% with no projectiles and no boss), but it has zero economic cost, and it
does not correlate with outcome (31.86% victory vs 31.98% defeat).

A "collect more aggressively" rule would buy nothing on income and would pull the
agent toward loot during the 3.3% of ticks that account for 45.4% of all damage.
Recommend **not** pursuing a collection-behaviour change. The material-economy
lever is the shop layer (spend efficiency), consistent with the existing v126
rich-exit evidence; the survival lever is the boss/projectile phase, which is
where the damage actually is.
