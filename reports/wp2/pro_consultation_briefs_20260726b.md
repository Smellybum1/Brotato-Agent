# Pro consultation briefs — 2026-07-26 (second set)

Two questions. Brief 1 could invalidate a finding I currently believe; Brief 2 is
the design problem it creates. Both self-contained — no repo access assumed.

---

# Brief 1: Is theoretical sustained DPS the right thing to optimise?

## Setup

I maintain a deterministic scripted agent that plays **Brotato** — a top-down
arena survival game. Fixed configuration: one character ("Well-Rounded"),
difficulty 0, a ranged/gun build, **20 waves**, objective is **win rate**. The
agent is hand-written policy code (no learned model). Each wave is a fixed-length
timed survival fight against swarms of melee enemies plus some ranged ones; a boss
appears at wave 20. Between waves there is a shop, and on level-up the agent picks
one of four random stat upgrades.

The agent scores candidate purchases and level-up options using its own model of
weapon DPS. That model, verbatim (it is an exact reimplementation of the game's
damage maths):

```
flat  = weapon.damage + Σ over weapon.scaling of (player_stat[key] * coefficient)
flat  = max(1, flat)
hit   = flat * (1 + percent_damage/100)
crit_chance = weapon.crit_chance + player.crit_chance/100          # capped at 1
hit  *= 1 + crit_chance * max(0, crit_damage - 1)
rate  = (1 + attack_speed/100) * 60 / max(1, weapon.cooldown)
dps   = hit * rate
```

and then a "crowd" adjustment for multi-hit weapons:

```
effective_dps = dps * nb_projectiles
              * (1 + piercing*keep*0.35 + bounce*keep*0.25)
              * 1.15 if explosive * 1.10 if burning
```

Total loadout DPS is the sum over up to six equipped weapons.

## The measurement

I reconstructed the equipped loadout at 244 validated shop visits across 20 runs
and priced **+1 point of each offense stat** as
`total_effective_dps(stats + 1 point) - total_effective_dps(stats)`:

| wave | +1 ranged_damage | +1 percent_damage | +1 attack_speed |
|---|---|---|---|
| 1 | **15.99%** | 1.00% | 1.00% |
| 9 | **6.48%** | 0.94% | 0.84% |
| 12 | **5.35%** | 0.84% | 0.76% |
| 19 | **4.35%** | 0.68% | 0.70% |

So on this model **+1 ranged_damage is worth ~6.4x +1 attack_speed** at waves
12-19, and ~16x in the early game.

The reason is structural. `ranged_damage` enters `flat` through *every* equipped
weapon's scaling coefficient and is then multiplied by the percent-damage term,
the crit term, projectile count and the crowd multiplier — so with six weapons it
compounds six times. `attack_speed` is a single rate multiplier with diminishing
returns in its own level: at attack_speed 88, +1 is worth 1/188 ≈ 0.53%.

The agent's scoring treats a raw point of each as roughly equal, so it
systematically prefers attack_speed, which arrives in bigger numeric chunks
(+15 attack_speed vs +2 ranged_damage on the same level-up board). Observed
outcome across 20 runs: losing runs end with ~37% more attack_speed and ~27% less
ranged_damage than winning runs, with identical weapon quality.

## Why I am not confident

The DPS figure above is **theoretical sustained damage against a single
infinitely-durable target**. Real conditions differ in ways that plausibly favour
attack_speed and disfavour flat damage:

1. **Overkill.** Most enemies are weak swarm units. If one shot already kills a
   trash enemy, extra flat damage per shot is wasted on it, whereas firing more
   often is not. Flat damage only pays off against the few high-HP units.
2. **Uptime and interruption.** The agent dodges constantly and weapons fire
   automatically at whatever is in range. Faster attacks mean more shots land
   during the brief windows when an enemy is in range; a slow high-damage weapon
   can waste its cooldown while nothing is targetable.
3. **Kill latency.** Killing an approaching enemy sooner prevents damage. Rate may
   matter more than per-shot size for survival specifically, which is what
   actually ends runs.
4. **Multi-projectile interaction.** `nb_projectiles` multiplies the whole DPS
   term in my model, but in the real game separate projectiles hit separate
   enemies — so the model may be over-crediting flat damage for shotgun-type
   weapons that already spread damage across targets.

Against that, the observed correlation (winners hold more ranged_damage) points
the same way as the DPS model, though it is correlational and I have not
established causality — winners might simply be offered different upgrades.

## Questions

1. **Is marginal theoretical sustained DPS the right objective for this decision**,
   or does it systematically overvalue flat damage relative to attack speed in a
   swarm game with heavy overkill? Is a 6.4x ratio plausible as a real decision
   weight, or is it an artefact of a single-target sustained model?
2. **How would you correct for overkill without simulating the game?** Is there a
   principled adjustment — e.g. weighting flat damage by the fraction of enemy HP
   pools above the per-shot damage threshold — that stays computable from data I
   already have (per-wave enemy counts and the agent's own per-shot damage)?
3. **Does the survival objective change the answer?** The run ends on death, not
   on low DPS. If attack_speed reduces time-to-kill on approaching threats more
   than flat damage does, it might be worth more than its DPS contribution
   suggests, even if its DPS contribution is genuinely 6x smaller.
4. If you think the DPS model is roughly right, **what would convince you?** I can
   measure almost anything from recorded telemetry (per-wave damage taken, enemy
   counts, weapon composition, stat trajectories), but I cannot easily run
   controlled experiments — a 20-run campaign takes about 7 hours of wall-clock.

---

# Brief 2: Correcting a scoring stack that has accreted three redundant layers

## The situation

The same agent scores each candidate stat option by summing several terms that
were added at different times, each for a specific observed failure, each with
evidence at the time. For a level-up option the total is:

```
score = combat_value(build, deltas, wave, profile)          # term A + term B
      + late_shop_pivot_bonus(effects, build, wave, profile) # term C
      [+ direct_offense_gain(effects) * 6.0]                 # term D, offense-deficient only
```

**Term A — principled.** Inside `combat_value`:
`1.0 * dps_gain_pct * 1.45`, where `dps_gain_pct = 100*(dps_new - dps_old)/dps_old`
computed on the real equipped loadout. This is the correct marginal-DPS term.

**Term B — raw points.** Also inside `combat_value`, added later:
`score += Σ (raw stat delta) * 0.55` over a list of damage stats. That list
includes ranged_damage and percent_damage but **excludes attack_speed**.

**Term C — raw points.** `late_shop_pivot_bonus`, a wave-tiered table:
mid-game (waves 9-14) multiplies the raw stat delta by
`ranged_damage 2.40`, `attack_speed 2.10`, `percent_damage 1.85` when the build is
below an offense floor, or `0.95 / 0.85 / 0.70` when above it.

**Term D — raw points.** In the level-up path only, when the build is below its
offense target, options are ranked by `score + raw_offense_points * 6.0`.

So the same three stats are priced **four times**: once correctly by marginal DPS,
and three times by raw stat points at weights that treat them as near-equal
(term C's ratio between ranged_damage and attack_speed is 2.40/2.10 ≈ 1.14x, where
the measured DPS ratio is 6.4x).

## What I tried, and why it failed

I identified term D as the culprit and removed it, keeping the raw-point sum only
as a *filter* (consider offense options only). I then checked the arithmetic on the
real recorded cases before shipping. Worked example, a genuine wave-12 decision
with a loadout doing 792 DPS, choosing between `+2 ranged_damage` and
`+15 attack_speed`:

| option | term A | term B | term C | total |
|---|---|---|---|---|
| +2 ranged_damage | 18.21% → 26.40 | 1.10 | 1.90 | **29.40** |
| +15 attack_speed | 13.04% → 18.91 | 0 | 12.75 | **31.66** |

Removing term D changes the margin but not the ordering — terms B and C still
carry enough raw-point weight to prefer the option with more raw points. **The
change was inert, and I reverted it.**

## The constraints that make this awkward

- Terms B, C and D were each introduced to fix a real observed failure and were
  validated at the time. I do not have the counterfactual showing any of them is
  now unnecessary — only that collectively they bury term A.
- Term C's coefficients are **pinned as exact source strings by six tests**, so
  changing them trips a wall of assertions that exist precisely to stop unplanned
  drift.
- There is **no behavioural test** on the level-up path at all — every test is a
  source-text assertion. So behaviour can change with a fully green suite.
- Deploying is expensive: each version needs a manual smoke run (~20 minutes of
  real gameplay) and a full audit, and a proper evaluation campaign is ~7 hours.
- The agent is deterministic and I want to keep it that way.

## Questions

1. **Is there a principled way to collapse redundant scoring layers** when each was
   added for a real reason and you cannot re-run the experiments that justified
   them? My instinct is to reconstruct what each term was compensating for and
   check whether the compensation is still needed, but that is slow and partly
   unfalsifiable.
2. **Or should I not collapse them at all** — instead leave the stack alone and add
   a single corrective term that restores the intended DPS ratio? That feels like
   adding a fifth layer to fix four, which is how the situation arose.
3. **How would you sequence this** given a ~20-minute smoke per version and no
   behavioural test coverage on the path being changed? Specifically: is it
   defensible to change several coefficients at once here, given that changing one
   at a time costs a deploy cycle each and the terms interact additively?
4. **What is the right test to build first?** I can execute the scoring logic in a
   reimplementation but not the real engine code. Is a reimplementation-based
   behavioural test worth building when it proves nothing about the shipped code,
   or is there a better structure — e.g. a data-driven scoring table shared by both
   implementations so the reimplementation and the real thing cannot diverge?
