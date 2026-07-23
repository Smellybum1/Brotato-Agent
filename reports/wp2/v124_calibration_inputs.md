# v124 calibration inputs — mid-game offense conversion

Computed by `scripts/wp2_telemetry_stats.py` from the finished 20-run
v122 exact-20 campaign (`reports/wp2/v122_campaign_stats.json`). Feeds the
v124 literals per `.tmp/wp2_v124_design_note.md` (Calibration inputs).
Window = shops after **waves 9-15** (the offense-conversion band). All
read-only; no re-derivation — this consolidates the streaming-agent method.

## Are offense marginal-DPS gains recorded? — **NO**

Offers **are** fully recorded (`purchase_offer` per refresh/reroll, all 4
slots with effect keys + flat stat values + weapon damage/scaling). But the
**combat_value()/marginal-DPS gain of each offer is NOT in the telemetry**
(verified: no marginal/dps_gain field in any offer or decision across all 20
runs). Design bullet 2 ("distribution of marginal-DPS gains of bought vs
skipped offense items") **cannot be satisfied from existing captures** — the
lowered `OFFENSE_IMPACT_MIN_ITEM_GAIN` (a DPS threshold, shop_strategy.gd:1030)
needs an offline `combat_value()` replay over the recorded offers, or a new
capture field, before it can be set numerically.

## 1. Idle (unspent, end-of-shop) gold at waves 9-15, by outcome

| outcome | shops | median | mean | p90 | max |
|---|---|---|---|---|---|
| victory | 77 | 65 | 73.1 | 126 | 318 |
| defeat | 51 | 63 | 74.5 | 158 | 210 |

Idle gold at mid shops is **only weakly outcome-separated** (defeat median 63
vs victory 65) — consistent with the campaign-driver finding that mid-game
economy is tightly clustered and outcome is set by offer luck, not banking.
The reroll-pressure "gold comfortably exceeds next-shop needs" guard should
therefore trigger only on genuine surplus: **p90 ~126-158 / cap near the
observed max ~210**, not on the ~63 median (spending to the median is normal).

Idle-gold median by wave (victory / defeat):

| wave | 9 | 10 | 11 | 12 | 13 | 14 | 15 |
|---|---|---|---|---|---|---|---|
| victory | 42 | 48 | 88 | 62 | 88 | 75 | 93 |
| defeat | 64 | 66 | 51 | 27 | 63 | 43 | 150 |

## 2. Offense-stat item conversion (marginal-DPS proxy)

Marginal DPS is unrecorded, so **offense-item buy rate** (offense-stat items
`ranged_damage/attack_speed/percent_damage/crit_chance` bought vs offered at
w9-15) is the available conversion signal:

| outcome | offered | bought | buy rate | bought/shop |
|---|---|---|---|---|
| victory | 234 | 98 | 42% | 1.27 |
| defeat | 190 | 58 | 30% | 1.14 |

Losing runs are **offered fewer** offense-stat items (190 vs 234) **and convert
a lower share to buys** (30% vs 42%). Part offer luck, part the banking
the v124 lowered-threshold is meant to correct: when an offense item is on the
board but below the current `OFFENSE_IMPACT_MIN_ITEM_GAIN`, buy it rather than
bank. This proxy — not a marginal-DPS distribution — is what calibrates the
direction; the exact lowered DPS literal awaits the offline replay (section 0).

## 3. Mid-shop reroll load (bounds added reroll pressure)

| outcome | rerolls/shop | reroll cost/shop |
|---|---|---|
| victory | 2.13 | 23.4 |
| defeat | 2.39 | 33.8 |

The policy already rerolls ~2/shop (~23.4-33.8 gold) at mid shops; added v124
offense-reroll pressure should stay within roughly this envelope so it does
not starve the build of buy gold.

## Headline v124 numbers

1. **Offense-item conversion gap:** defeat runs buy only **30%** of offered
   offense-stat items at w9-15 vs **42%** for victories — the indicted
   conversion failure the lowered threshold targets.
2. **Idle-gold surplus floor:** defeat idle gold at w9-15 is median **63**,
   p90 **158**, max **210** — arm reroll pressure only above ~p90, not the median.
3. **Reroll envelope:** ~**2.4** rerolls/shop @ ~**34** gold at mid shops —
   the ceiling the added offense-reroll pressure must stay within.

Marginal-DPS distribution (design bullet 2): **NOT RECORDED** — see section 0.
