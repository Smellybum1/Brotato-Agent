# Step 1: the level-up channel is a clean NO-GO, and the premise behind it is suspect

Offline audit of the speed-vs-damage valuation hypothesis — "the deterministic scorer
overvalues movement speed relative to damage, and that is why doomed builds enter wave 17
with half the weapon damage." **Zero machine time.** Current era only (`mod 0.2.49` /
`policy 0.1.129`).

Two results, in the order they were found. The second matters more than the first.

## 1. The scorer IS mis-dimensioned — confirmed from the code, not inferred

`combat_model.gd` `combat_value()` L211-219 sums terms in **incommensurable units**:

```
score = DPS_PRIORITY * dps_gain * dps_weight     # dps_gain is a PERCENTAGE
      + DEF_PRIORITY * ehp_gain  * ehp_w         # percentage
      + speed_gain   * speed_w                   # RAW POINTS, undiminished
```

- **Damage** enters as `dps_gain = 100*(dps1-dps0)/dps0` — self-normalising, so it
  **diminishes** as the build gets stronger. For `+1 stat_percent_damage` it is exactly
  `100/(100+p)`.
- **Movement speed** enters at L194 as `(new - old) * SPEED_VALUE`, with **no
  normalisation and no diminishing returns** — a flat `0.6 x 1.15 = 0.69` per raw point
  forever. It is also skipped by `_utility_score` (L79, `stat_speed` is in `_COMBAT_STATS`),
  so that single line is the *only* place speed is priced.

So the structural concern is real: as a build's DPS grows, the damage term shrinks toward
its `flat_damage_value` floor while speed stays flat. This is a **different** mispricing
from the one already recorded in `shop_scorer_migration_gate_verdict.md`, which compared
two *offense* stats (ranged damage vs attack speed, median 9.40x per point). Movement speed
vs damage had never been examined.

**Being real is not being load-bearing.** That is what the rest of this measures.

## 2. Parity gate — PASSED, exactly

`scripts/wp2_levelup_scorer_parity.py`. Ported the missing terms (`effective_hp`,
`combat_value`'s EHP/speed/flat-damage terms, the wave>=15 well_rounded overrides,
`_utility_score`, `_late_shop_pivot_bonus`, both `decide_levelup` paths), reusing the
already-verified numeric core from `wp2_offer_dps_replay.py`.

Current era, 377 scored decisions: **argmax parity 377/377 = 1.0000**, path agreement
377/377, and **score error against the engine's logged `action.score` is 0.0 at every
percentile including max.** Ablation confirms the match is not degenerate — removing any
single term breaks it (dps -> 0.814, ehp -> 0.833, utility -> 0.817, late_shop_pivot ->
0.767, flat_damage -> 0.971, speed -> 0.976).

Two same-named-field traps were hit and fixed during the port, both of which would have
produced a wrong answer: `build_metrics.offense.target` is **not** `_offense_target()` (it
comes from a different function and cost 64/377 argmax), and scoring a loadout-independent
option with an empty weapon list silently trips `combat_value`'s `dps0 == 0 -> dps_gain =
100.0` branch (cost 144/377).

**Known bias, stated before the result:** 799/1176 = **67.9%** of distinct current-era
decisions fail loadout reconstruction, and the failures are **not missing at random** —
they skew to 6-weapon builds (580) and to late waves (17/19/18 contribute 144/117/67). Any
conclusion drawn from the 377 scored decisions inherits that skew. **The result below does
not depend on the 377**; it is computed over all 1176 distinct decisions, which need no
reconstruction.

## 3. THE ACTIONABILITY BOUND — the level-up channel cannot carry the hypothesis

Over **241 current-era runs, 1176 distinct level-up decisions** (deduplicated on
`(wave, alternatives, picked)`; 567 exact duplicates = 32.5%, matching the known ~30% trap):

| | count | rate |
|---|---|---|
| boards **offering** `stat_speed` | 293/1176 | 0.249 |
| decisions **choosing** `stat_speed` | **31/1176** | **0.026** |
| **take rate when offered** | 31/293 | **0.106** |

What the policy actually picks:

| stat | picks | share |
|---|---|---|
| `stat_ranged_damage` | 218 | 0.185 |
| `stat_attack_speed` | 209 | 0.178 |
| `stat_percent_damage` | 200 | 0.170 |
| ... | | |
| **`stat_speed`** | **31** | **0.026** |

**Offense-family picks: 702/1176 = 59.7%. Damage-family: 436 = 37.1%.**

**The level-up policy is not choosing speed over damage. It declines speed ~89% of the
times it is offered, and spends three of its top three picks on offense.**

**Strict upper bound:** set the speed term to zero and flip *every* speed pick to the best
damage option on its board. That is **31 decisions across 241 runs = 0.13 per run**, worth
**225 `stat_speed` points total = 0.455 per run**. Against a target of a 25-33% clearance
improvement, this is not a candidate lever. **NO-GO, and it closes honestly rather than by
aggregate proxy.**

The shop/item channel is no better: across 495 runs, 4,416 buys, only **391 carry a
`stat_speed` effect at all, and they are bidirectional** — 193 buys carry *negative* speed
(109 at −3, 61 at −2, 23 at −1) against 195 positive. Net **+391 points over 495 runs =
+0.79 per run**. The agent is not accumulating speed through purchases either.

## 4. ⚠️ THE PREMISE IS PROBABLY A SAME-NAME CONFLATION — verify before spending anything else

Stage A's headline was `speed` **531 (died) vs 499 (survived)**, read as "dying builds
bought speed instead of damage". That field is
`payload.player.speed` — `scripts/wp2_stagea_metrics.py:179` — the player's **movement
speed in units/second**, a derived quantity. The invoker analysis used the same field as a
velocity (`median speed 499 x 0.051 s = 25.4 u` of clearance), which confirms the unit.

**It is not `stat_speed`, the stat the shop and level-up policy score.** They are related
by a percentage, not identity.

The arithmetic does not reconcile. Observed `player.speed` spans at least 445-531 (~19%).
If `+1 stat_speed` is `+1%` movement speed, that range needs ~19 `stat_speed` points, while
**total measured acquisition from every logged channel is ~1.25 points per run** (0.455
level-up + 0.79 items) — short by more than an order of magnitude. So **`player.speed` is
driven predominantly by something other than the stat the policy prices.**

This is the third instance on this project of two same-named quantities from different
sources being compared as if identical (after `damage`/`cooldown` base-template vs
effective, **3.40x apart**, and `build_metrics.offense.target` above).

**Consequence: "dying builds bought speed instead of damage" is not supported by the
purchasing record.** The speed half of the Stage A separator is an inference about a stat
the agent almost never buys. The *damage* half (nominal_dps 28.26 vs 35.25, summed weapon
damage 162.5 vs 335) is measured on a different instrument and is unaffected.

## Verdict and what follows

- **Level-up valuation: NO-GO, closed.** Measured actionability bound, not a null.
- **Shop item valuation: not closed, but the speed motivation for auditing it is gone.**
  Building the full shop frontier audit — a ~370-line policy port with vetoes — is no longer
  justified by this hypothesis. That is Gate 0 applied to my own next step.
- **Immediate cheap check first:** establish what actually drives `player.speed`. Until
  that is known, any further speed-related work risks optimising a quantity the policy
  cannot move. Correlating per-run `player.speed` at wave-17 entry against cumulative
  logged `stat_speed` acquisition is a single archive pass and answers it.
- The parity harness is built, exact, and reusable for any future level-up counterfactual.
