# Materials economics — correction, and adoption record for the Pro review

Date: 2026-07-26. Supersedes the framing in the brief sent for external review
(`.tmp/pro_consultation_briefs_20260726.md`). Written after the v127 deploy
(`v127_deploy_record.md`) confirmed Model B empirically.

## The correction

I claimed: *material value recirculates through the `bonus_gold` pool, but XP is
destroyed, because the wave-end sweep calls `add_bonus_gold` and never `add_xp`.*

**That is wrong, and the error changes the recommendation.**

The sweep does call neither `add_gold` nor `add_xp` — that part was right. But I
stopped there instead of following the deferred unit forward to redemption. In
`main.gd::on_gold_picked_up`:

```gdscript
var value = gold.value       # CURRENT value, including any bonus boost
...
if gold.attracted_by == _player:
    RunData.add_gold(value)
    RunData.add_xp(value)
```

and at spawn, while the pool is non-empty, a base-1 entity is boosted to value 2
and the pool is drained by 1. So when the player collects that boosted entity
they receive **2 materials and 2 XP** — one of each for the current drop, one of
each for the previously deferred unit.

**Materials and XP defer together and redeem together.** Neither is destroyed by
being swept.

| fate of one generated unit | materials | XP |
|---|---|---|
| picked immediately | +1 now | +1 now |
| deferred, later redeemed | +1 later | +1 later |
| outstanding at death / run end | lost | lost |

### Why I got it wrong

I read the sweep code path in isolation and treated "no `add_xp` on this line" as
"XP destroyed at this moment". The conserved quantity only becomes visible when
you follow the pool through conversion to redemption — one function away. The
lesson generalises: *when a mechanic defers a resource, the loss must be measured
at the redemption boundary, not the deferral boundary.*

## What the cost actually is

Not an XP leak. Three real costs remain:

1. **Timing.** Value received several waves late is worth less: earlier stats
   apply to more remaining waves, and earlier materials can change the *next*
   shop rather than a later one.
2. **Useful-deadline loss.** Mechanically recovered is not strategically useful.
   Value deferred out of wave 19 into wave 20 arrives after the last shop and the
   last meaningful upgrade window.
3. **Terminal non-redemption.** Anything on the floor or in the pool at death or
   at the end of wave 20 is simply lost.

Against these sits **movement risk**, the direct cost of collecting.

## Adopted

- **The correction itself**, in full. It is verified against the game source, not
  taken on authority.
- **Reframe the objective** as deadline-adjusted realisation, not XP-capture rate.
- **The urgency curve**: opportunistic waves 1–17, rising at 18, **strongest at
  wave 19** (last wave whose gold can still reach the final shop and the wave-20
  build), targeted gold-seeking **off at wave 20**.
- **Cap-merge does not drain the pool.** Sharp mechanical point, verified: the
  `MAX_GOLDS` absorption path (`gold_boosted.value += unit.stats.value`) bypasses
  `spawn_gold` entirely, so it never calls `remove_bonus_gold`. Pool drain is
  driven by *entity-creation events*, not by nominal drop value — so the 50-entity
  ceiling throttles redemption capacity, not just observability.
- **Pool growth condition** `L_t > R_t` (newly abandoned value exceeds redeemed
  bonus value), rather than my cruder "pool didn't reach zero". A pool can stay
  positive while shrinking.
- **Bounded, risk-gated collection overlay** as the first intervention, scored on
  actual cluster *value* rather than entity count — not global gold chasing.
- **A/B qualification is still required** before deploying any movement change;
  counterfactual accounting cannot predict how altered movement perturbs enemy and
  projectile trajectories.

## Adopted with modification

**"Wave 20 collection has effectively zero value" — overstated.** Levelling
during wave 20 grants a stat upgrade immediately, mid-wave, which can help win the
boss fight; XP there is not strictly worthless. The conclusion still holds because
survival dominates on the boss wave and the effect is small, but the justification
is "dominated by survival", not "zero value".

Also worth recording: **the current policy already does this.** The v127 smoke
measured wave-20 loot-dash uptime at exactly 0.0% via the `suppressed_finale`
branch, which is the finale path dropping the dash by design. Wave 20 is already
gold-seeking-off; no change needed.

## Not needed — already shipped

The review recommended new telemetry for `bonus_pool_at_wave_start`,
`minimum_bonus_pool_during_wave`, `bonus_pool_immediately_before_timeout` and
`bonus_pool_after_floor_sweep`. **All four are already derivable**: v127 emits
`player.bonus_materials` on *every* capture at 20 Hz, so start / minimum /
pre-timeout / post-sweep are all just reductions over the existing stream. Only
the base-vs-bonus component split and a `cap_merge_events` counter would need new
instrumentation, and the component split can be inferred from an entity's current
value against its base.

One inference in the review does not survive the full run: it read
"floor value equals floor entity count" from the waves 1–5 table and concluded no
boosted component remained on the floor. Over the complete run that breaks —
wave 10 shows 46 entities worth 49, wave 15 shows 46 worth 48. Boosted entities
*are* being left behind in the mid game.

## Deferred

- Full oracle level-curve and shop-counterfactual reconstruction. High value, but
  it is the materials campaign's job and v127 has just shipped the stream it needs.
- Engine-executed GDScript policy fixture runner. Real, and larger than this line
  of work.

## Standing empirical facts from the v127 smoke

- Crediting is **Model B**: 15/19 wave boundaries match exactly, 4 short by 1–2 in
  the direction a 5–50 ms sampling gap predicts.
- The bonus pool is **0 at the end of every one of the 19 waves** — it fully
  converts within each wave. No saturation on this run. Note this is *conversion*,
  not proof of *redemption*: conversion attaches pool units to new entities, and
  those entities still have to be picked up.
