# The level-up path prices offense stats by raw points, not by DPS

Date: 2026-07-26 (overnight, autonomous). Evidence: the 20 F2 pure-teacher runs
(10W/10L, policy `0.1.125`). Follows the shop verdict
(`shop_conversion_verdict.md`) and its correction.

## How this was reached

Four axes were tested and three came back null:

| axis | result |
|---|---|
| gold conversion (banked gold, rich exits, economy) | **null** — no discrimination; victories bank *more* |
| stat-item selection | **null** — 0 gate misses in 1,037 offense-deficient buys |
| weapon selection | **null** — 6.4% (defeat) vs 5.2% (victory) bought a lower-DPS affordable weapon |
| weapon acquisition (`weapon_tier_sum`) | **null** — identical at every wave (w19: 19.5 vs 19.0) |

So winners are not buying better weapons, not buying more weapons, not converting
gold better, and not selecting better items. Yet their loadout DPS is **1.27x**
higher by wave 19 (4,377 vs 3,433).

Decomposing `weapon_dps` — which is a function of weapons *and* the stats their
scaling terms consume — locates the whole difference in **stat composition**:

| wave | ranged_damage D/V | attack_speed D/V |
|---|---|---|
| 8 | 2.3 / **4.8** | **15.1** / 11.1 |
| 14 | 9.5 / 9.9 | 43.0 / 40.0 |
| 17 | 10.8 / **13.6** | **83.2** / 51.8 |
| 19 | 11.8 / **16.1** | **88.2** / 64.4 |

Losers end with ~37% more attack_speed and ~27% less ranged_damage. The split is
visible from wave 8, well before the DPS gap opens at wave 14.

## The defect

`shop_strategy.gd::_direct_offense_gain()` sums the three offense stats with
**equal weight, as raw stat points**:

```gdscript
if (key == "stat_ranged_damage" or key == "stat_percent_damage"
        or key == "stat_attack_speed"):
    gain += val
```

and `decide_levelup()`, whenever the build is offense-deficient, ranks options by

```gdscript
var rank0 := score0 + gain0 * 6.0
```

so that raw-point term, weighted 6x, dominates the selection.

**This is inconsistent with how the same file prices weapons.**
`_projected_weapon_dps_gain()` uses `BotCombatModel.effective_weapon_dps` — the
real marginal-DPS model. Weapons are priced by DPS; level-up stats are priced by
raw points.

Raw points are not DPS. From `combat_model.gd::weapon_dps`:

- `rate = (1 + attack_speed/100) * 60/cooldown` → +1 point is worth `1/(100+as)`
- `hit  = flat * (1 + percent_damage/100)` → +1 point is worth `1/(100+pd)`
- `flat = damage + Σ(stat * coef)` → ranged_damage enters **before** the percent,
  crit, projectile and crowd multipliers

Both multiplier stats therefore have **diminishing returns in their own level**,
and the scorer is blind to it.

## Quantified at the levels actually observed

Marginal %DPS of +1 stat point, computed exactly from the recorded stats at each
shop exit (no loadout reconstruction needed — these two terms are closed-form):

| wave | +1 attack_speed D/V | +1 percent_damage D/V | mispricing at defeat levels |
|---|---|---|---|
| 8 | 0.874% / 0.906% | 0.965% / 0.948% | 1.10x |
| 12 | 0.764% / 0.764% | 0.850% / 0.828% | 1.11x |
| 15 | 0.685% / 0.718% | 0.787% / 0.754% | 1.15x |
| 17 | 0.557% / 0.671% | 0.732% / 0.707% | **1.31x** |
| 19 | 0.542% / 0.627% | 0.698% / 0.705% | **1.29x** |

`_direct_offense_gain` scores these as **1.0 point each, identically**, at every
wave. The error grows monotonically with the stat level and is worst exactly where
the win/loss divergence appears — and worst in the losing runs, because they are
the ones stacked highest on the cheapest-to-mis-value stat.

This is self-reinforcing: taking attack_speed lowers the marginal value of the
next attack_speed point, but the scorer keeps valuing it at 1.0, so it keeps
taking it.

## What this does and does not establish

**Established:** the level-up scorer misprices offense stats against the project's
own DPS model, the error is systematic, it grows with stat level, and it reaches
~1.3x by wave 17. This is checkable against the DPS formula alone and does not
depend on any outcome data.

**Not established:** that this mispricing *causes* the losses. The correlation
between attack_speed stacking and defeat is consistent with the mechanism, but
reverse causality is live — runs that are behind get offered and take different
things, and winners kill faster for reasons this analysis does not isolate. The
measured mispricing (~1.3x on a subset of level-up choices) is also modest
relative to the 1.27x total DPS gap it is being asked to explain.

**Not measured:** the marginal DPS of `ranged_damage`, which needs the equipped
loadout (`flat` depends on each weapon's base damage and scaling coefficient).
The v124 replay has a validated `LoadoutReconstructor` that would close this, and
until it is run the ranged-vs-attack_speed comparison — the one the outcome data
actually points at — remains unquantified. Only the attack_speed-vs-percent_damage
pair above is exact.

## Proposed v128 (NOT implemented — deliberately)

Price level-up offense options by marginal DPS instead of raw stat points, reusing
`BotCombatModel` exactly as the weapon path already does, so one model arbitrates
both. This is a *consistency* fix and is justified by the mispricing alone,
independent of whether it moves win rate.

Held for review rather than implemented overnight, for three reasons:

1. The ranged_damage leg is unquantified (above), and that is the leg the outcome
   data points at. Shipping before measuring it would repeat the error this
   document's parent had to correct.
2. `decide_levelup` interacts with `_late_shop_pivot_bonus`, whose pinned
   coefficient strings are protected by frozen tests.
3. Deploying needs a version bump (which also carries the undeployed mod-ready
   sentinel) and a qualifying smoke; that should not land unattended.

**Next step, in order:** run the loadout reconstruction to quantify ranged_damage's
marginal DPS at waves 12-19, then decide v128 on the complete picture.
