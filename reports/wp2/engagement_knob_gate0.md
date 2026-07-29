# The engagement knob: named, scalar, dose-able — and it clears Gate 0 offline

**Date:** 2026-07-29. Closes the loop opened by `engagement_distance_lead.md` and
`in_range_fraction_mediator.md`. No new machine time.

## The design decision the data indicts

`potential_field.gd:1516-1521`, with the comment stating the intent outright:

```gdscript
var engage = _engage_distance(profile, player, weapons)
engage *= BotConfig.DPS_ENGAGE_SCALE          # 0.78 — "sit inside shortest weapon range"
if edge_kite:
    engage *= BotConfig.EDGE_ENGAGE_SCALE     # 1.18
```

and inside `_engage_distance` (`:1881`):

```gdscript
# Optimal DPS band = shortest weapon range (all weapons can hit).
var optimal: float = max(min_r * BotConfig.OPTIMAL_RANGE_FRAC, BotConfig.MIN_ENGAGE_DISTANCE)
```

**The standoff is derived from the SHORTEST weapon's range**, so the agent positions where *all six
weapons can hit the nearest target*. That optimises **weapons-per-target**. The measurement says the
thing that actually matters on a crowded wave is **targets-per-weapon** — and those trade against
each other, because standing off to keep the shortest weapon in play pushes the rest of the pack
outside even the longest.

`OPTIMAL_RANGE_FRAC` 0.90 · `DPS_ENGAGE_SCALE` 0.78 · `MIN_ENGAGE_DISTANCE` 120 ·
`ENGAGE_SPRING_K` 0.030 · profile `engage_scale`.

## Gate 0 evidence: the knob controls the observed behaviour

Across **272 agent wave-17 trials**, per-trial medians:

| shortest weapon range | n trials | median nearest-threat distance |
|---|---|---|
| 360-419 | 30 | 459 |
| 420-479 | 150 | 472 |
| 480-539 | 90 | 519 |

Monotone, Pearson **r = 0.377**. The standoff tracks the shortest weapon range across builds, which
is what the code says it should do. (r is well short of 1 because other repulsion terms also
contribute — the knob is a real lever, not the sole determinant.)

**The single cleanest statement of the whole diagnosis:**

| | nearest-threat ÷ shortest-weapon-range |
|---|---|
| **agent** (272 trials) | **1.062** |
| **human** (9 trials) | **0.631** |

The agent sits *at* the edge of its shortest weapon's reach. The human stands at roughly **two-thirds**
of it, inside, where more of the pack falls within the longer weapons.

## Why the neighbouring knobs are NOT the answer

`EDGE_ENGAGE_SCALE` (1.18) is gated on `edge_kite`, which requires `nearby >= 10` where `nearby`
counts enemies within 280 u. That variable is **0 on 90.5% of wave-17-19 ticks**, so edge-kiting
almost never activates. **This is the fourth threshold found sitting outside the support of its own
variable** — after the density veto (8), the `safety` throttle (280), and the projectile-proximity
threshold (70). Treat that as a standing code smell in this controller, not a coincidence.

So the lever is the engage distance itself, not the edge-kite scale.

## The proposed Gate 0 experiment (not yet run)

A **single scalar dose** on the engage distance, targeting the realised ratio:

| arm | multiplier | predicted realised ratio |
|---|---|---|
| C | 1.00 | ~1.06 (baseline) |
| D85 | 0.85 | ~0.90 |
| D75 | 0.75 | ~0.80 |
| D65 | 0.65 | ~0.69 (≈ human's 0.63) |

**Screen on the mediator, not the outcome.** Per-trial in-range fraction is perfectly separated
between human and agent (0.4417 ± 0.0187 vs 0.2801 ± 0.0535, d = 4.03), dense and non-zero-inflated,
so a handful of trials per arm shows whether the dose moves geometry at all. Reject any dose that
raises in-range fraction while also raising low-HP exposure or HP-deficit AUC — buying targets with
safety is the failure mode this whole line is trying to avoid.

**Expect gross damage taken to INCREASE, and do not treat that as a regression.** Closing distance
costs damage; the human took 1.95x more and won. A gross-damage endpoint would score this backwards,
which is exactly why it was retired.

Only a dose that clears the mediator screen earns a preregistered survival campaign, run on titrated
fixtures for the screen (`overdose_instrument_check.md` — `enemy_scaling.health` works above 1.0) and
at **baseline** dose for confirmation.

## Standing cautions

- **This is one constant, not a whole-field rebalance** — which corrects my earlier over-caution.
  It is still a change to the core movement field and still gets a campaign, not a ship.
- **The mediator is not the outcome.** A screen licenses a campaign; it never substitutes for one.
- The human comparison is **n = 9 trials, 8-way input, one fixture family**, and the direction of
  causation is not established: the human may fight close because a keyboard cannot kite precisely.
- `MIN_ENGAGE_DISTANCE` (120) will start to bind at the aggressive end of the ladder on
  short-weapon builds; check whether it clips before attributing a dose plateau to behaviour.
