# v122 campaign — what makes the strong runs strong?

Read-only analysis of all 13 completed v122 exact-20 campaign runs. Same
deterministic policy every run (teacher v1-0.1.122-gun-wp1 + WP1 shop strategy,
`character_well_rounded` / `weapon_smg_1` / danger 0), so every between-run
difference is RNG: which shop items, level-up options, and crates were **offered**,
and how those advantages compound. Source:
`C:/Users/moxhe/AppData/Roaming/Brotato/brotato_agent/runs/<run_id>/events.jsonl`
(streamed line-by-line) + `summary.json`.

**Strength** S = clamp(offense.weapon_dps / offense.dps_target, 0, 2), read from
`combat_tick.payload.build_metrics.offense` (0.5 s cadence). Per-wave value = median
of that wave's ticks. "Late S" = median S over waves 13–20 (or last band reached).

## What the telemetry records (offers vs buys)

Offers **are** fully recorded — this is not a buys-only dataset:
- `purchase_offer` — every shop refresh **and every reroll**, listing all 4 slots
  with `id / tier / price / category / weapon_id / damage / affordable` + shop `gold`.
- `level_up_offer` — the 4 stat options with `key / value / tier`.
- `crate_offer` / `crate_decision` — the item offered and take/discard.
- `purchase_decision` — the chosen action (`shop_buy`/`shop_reroll`/`shop_go`/
  `shop_lock`), `gold_before`, `reroll_price`, `legal_alternatives`, full `build_metrics`.
- `shop_combine_confirmed` — before/after weapon signatures (tier per weapon).

Because selection is a **fixed deterministic policy**, "selection quality" cannot vary
between runs except through what was offered. Selection is held constant by design;
**offer luck is the only free variable**, and the question is where that luck lands.

## 1. Strength ranking (late-game S) and outcome

| rank | run | id | result | last w | S 13+ | S 5–8 | S@8 | S@15 | dmg taken |
|---|---|---|---|---|---|---|---|---|---|
| 1 | r10 | run_1784794784_69267 | victory | 20 | **2.00** | 1.11 | 0.81 | 2.00 | **22** |
| 2 | r8  | run_1784792652_7723  | victory | 20 | **1.75** | 1.17 | 0.98 | 1.90 | 112 |
| 3 | r1  | run_1784785556_51395 | victory | 20 | **1.65** | 0.70 | 0.72 | 1.39 | 105 |
| 4 | r13 | run_1784798249_41022 | victory | 20 | 1.53 | 0.82 | 0.71 | 1.33 | 56 |
| 5 | r12 | run_1784797082_83949 | victory | 20 | 1.32 | 0.98 | 1.35 | 1.41 | 75 |
| 6 | r3  | run_1784787688_32406 | victory | 20 | 1.24 | 1.15 | 1.15 | 1.09 | 166 |
| 7 | r9  | run_1784793833_32034 | defeat  | 17 | 1.13 | 0.72 | 0.60 | 1.13 | 116 |
| 8 | r5  | run_1784790063_90333 | defeat  | 20 | 1.11 | 1.28 | 1.22 | 1.13 | 55 |
| 9 | r11 | run_1784795927_93597 | victory | 20 | 0.99 | 0.78 | 0.71 | 0.89 | 191 |
| 10 | r6 | run_1784791214_74323 | defeat  | 17 | 0.94 | 0.99 | 1.31 | 0.84 | 62 |
| 11 | r2 | run_1784786723_17546 | defeat  | 17 | 0.89 | 0.75 | 0.74 | 0.99 | 222 |
| 12 | r4 | run_1784788917_7315  | defeat  | 20 | 0.83 | 0.72 | 0.56 | 0.85 | 237 |
| — | r7 | run_1784792179_82981 | defeat  | 10 | — | 1.04 | 0.85 | — | 50 |

**Top-3 = r10 / r8 / r1; bottom-3 (reaching the late game) = r4 / r2 / r6.**
Victory mean late-S **1.50** vs defeat mean **0.98** — clean separation (only r5 def@1.11
and r11 vic@0.99 straddle the line). r7 is the lone early death (wave 10) and the only
death not attributable to weak offense.

## 2. The mechanism — S is *entirely* weapon_dps, and weapon_dps is *stat multipliers*

`dps_target` is a **fixed function of wave, identical in all 13 runs** (300 @ w5,
765 @ w10, 1620 @ w15, 2900 @ w20). So **100% of S variance is `weapon_dps`.**

Weapon *acquisition* is near-saturated and near-uniform across every run — all reach
**6 gun-set weapons by ~wave 6**, and end-game `weapon_tier_sum` clusters at 15–22 for
winners and losers alike. It is not the driver:

| wave-15 cross-section (n=12) | corr with weapon_dps |
|---|---|
| weapon_tier_sum | **−0.17** (weapon count/tier is *not* it) |
| ranged_damage stat | **+0.69** |
| attack_speed stat | +0.47 |
| percent_damage stat | +0.15 |
| pct+atkspd+2·crit (multiplier proxy) | +0.54 |
| gold entering shop @ w9 (early net worth) | **+0.05** |

`corr(weapon_tier_sum, multiplier proxy) = +0.01` — weapon tiers and damage-multiplier
stats accumulate independently. Every run fills the same 6-gun rack; the winners are
the runs whose **damage-multiplier stats (ranged_damage / attack_speed / % damage / crit)
spiked**. Those stats come from level-up picks and shop stat-items — i.e. **offer luck**,
since the policy always takes the best offered.

Each strong run rode a *different* offered engine (offense stat trajectory, median/wave):

| run | engine | signature climb | weapon_dps 10→15 |
|---|---|---|---|
| r10 | % damage + attack speed | pct 41→55, atkspd 0→38 by w12–13 | 978 → **3292** |
| r8  | attack speed | atkspd 10→60→**110** (w7→16) | 825 → **3085** |
| r1  | crit + attack speed | crit →25–35, atkspd 28→98 (w12–18) | 740 → 2253 |
| r4 (weak) | none | pct stuck ≤9, crit 0 until w15 | 421 → 1371 |
| r2 (weak) | lopsided | **ranged_damage stuck at 1 all game** | 517 → 1608 |
| r6 (weak) | none | every multiplier modest (crit 5, atkspd ~35) | 850 → 1356 |

Lopsided luck still fails: r9 and r11 both got % damage ~57 but almost no attack speed
(5 and 11) → weapon_dps only ~1.4–1.8 k; r9 died, r11 scraped a win taking the most
damage of any victor (191).

## 3. Compounding test — strength is built LATE, not snowballed early

Early advantage does **not** predict late strength:
- `corr(S@wave8, S@wave15) = +0.04`; `corr(median S 5–8, median S 13+) = +0.32` (weak).
- Runs are indistinguishable through ~wave 10 then **fan out**: the champion r10 was
  *below average early* (S@8 = 0.81) and only crossed into dominance when its
  multiplier engine came online at **wave 12–13** (weapon_dps tripled 978→2714). r1
  (S@8 = 0.72) and r13 (S@8 = 0.71) likewise start weak and finish top-4.
- Conversely, several of the *strongest-early* runs faded: r5 (S 5–8 = 1.28) and r6
  (S@8 = 1.31) both drifted down and **lost**.

The divergence is a mid/late-game event (a multiplier stat catching fire), not an
early lead that compounds.

## 4. Early accumulation / economy is NOT the driver

Gold entering the shop is tightly clustered — CV **12% @ w5, 15% @ w9, 11% @ w12** — no
run buys its way to a lead. And late gold is if anything *anti*-correlated with winning:

| wave-19 shop gold | run | result |
|---|---|---|
| 1022 | r5 | **defeat** |
| 947 | r3 | victory |
| 765 | r4 | **defeat** |
| 722 | r1 | victory |
| … | | |
| 649 | r10 | victory (champion) |
| 308 | r8 | victory (rank 2) |

The two richest late shops (r5, r4) both lost; the two strongest runs (r10, r8) had
among the **lowest** wave-19 gold — they had already *converted* materials into an
effective multiplier build, while the losers were sitting on unspent gold with nothing
worth buying offered. `corr(gold@9, weapon_dps@15) = +0.05`. Reroll volume doesn't
explain it either (r3 rerolled most at 54 → only a mid-strength win; r8 rerolled 29 →
rank 2), nor do crates (champion r10 **discarded 9 of 13** crates and took only 4;
crate-greedy r3 took 12 → modest win) or combine cadence (r10 = 8 combines, weak r4 = 6,
mid r3 = 11).

## 5. Damage taken tracks offense, not movement

`corr(median late-S, total damage taken) = −0.62`; `corr(early S, dmg) = −0.51`. The
offense-starved runs bleed out: r4 (weakest late-S 0.83) took 237, r2 (ranged_damage
pinned at 1) took 222 — the two highest — and both died. The champion r10 took **22**.
Deaths in this campaign are overwhelmingly **offense-starvation** (build can't clear the
wave fast enough), not a movement/positioning failure. Sole exception: r7 died at wave 10
with only 50 damage taken and average S — a genuine early-survival loss, the one run that
doesn't fit the offense-starvation pattern.

## Bottom line

Runs are strong because a **damage-multiplier stat got lucky offers and caught fire in
the mid-to-late game** (waves ~12–16), tripling weapon_dps against a fixed target curve.
It is **offer luck, not selection** (selection is deterministic) and **not early
accumulation** (economy is uniform; early strength doesn't predict late; the richest late
shops belong to losers). Different champions rode different offered engines
(r10 % damage, r8 attack speed, r1 crit), but all needed a multiplier to spike; the
losers are the runs the multiplier never showed up for.
