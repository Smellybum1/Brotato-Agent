# Why late-wave material collection degrades (2026-07-25)

Operator observation: "in the early rounds the agent does try to pick up
all the currency, it's from wave 10 onwards where it becomes skittish and
starts leaving currency on the ground." Confirmed by measurement
(`materials_leftover_corrected.md`): median leftover at wave-timer end
goes 5 (w1-5) -> 31 (w6-10) -> 44 (w11-15) -> 49 (w16-19), and the
leftover FRACTION of drops rises 9.6% -> 23.7%.

This document tests candidate mechanisms. Measured directly by the
primary agent on 2-3 full runs (all `teacher_v1-0.1.125-gun-wp1`).

## Candidates tested

| mechanism | code site | w1-5 | w11-15 | verdict |
|---|---|---|---|---|
| Density veto: `if nearby >= PACK_DENSITY_SOFT (8): return ZERO` (loot attraction hard-zeroed) | `potential_field.gd` `_loot_attraction` | 0.0% of loot-present ticks | 0.0% (2.7% at w16-19) | **REFUTED** — effectively never fires |
| Edge-kite suppression: loot attraction skipped entirely while edge-kiting | `_build_desire` (`if not edge_kite`) | n/a | n/a | **NOT the w10 transition** — requires `wave >= LATE_EDGE_KITE_WAVE (16)` AND `nearby >= ~10`; can only matter from w16 |
| Per-item corridor veto: `blockers > LOOT_PACK_ALLOW (2)` skips that pile | `_loot_attraction` | 2.1% of visible materials | 12.2% | contributes; too small alone |
| Distance growth (attraction falls as 1/dist) | `_loot_attraction` falloff | mean 535u | mean 684u (+28%) | contributes |
| Drop volume growth | game | low | high (list saturates at the 50 cap 23-43% of late waves) | contributes |
| Loot dash uptime (v118, the sanctioned pile-clearing mechanism) | `_apply_loot_dash` | UNMEASURABLE | UNMEASURABLE | **observability gap** |

## Conclusion

There is no single gate slamming shut at wave 10. The two hard
suppression mechanisms (density veto, edge-kite) do not fire in the
relevant range. The degradation is cumulative: late waves drop far more
material, spread ~28% farther from the player, while the attraction force
falls off as 1/distance and combat/strafe forces dominate the summed
vector — with ~12% of visible piles additionally vetoed by the corridor
rule. The agent is not refusing loot; it is out-ranged and out-voted.

## Observability gap (blocks the actionable next step)

`potential_field.gd` line ~1239 defines `"loot_dash_active":
_loot_dash_active` in a debug dict, but the emitted `combat_tick.debug`
payload contains only `{enemies, projectiles, profile,
finale_translation}`. Loot-dash uptime, arm/abort reasons, and clearance
yield are therefore unobservable in telemetry.

This matters because the loot dash is EXACTLY the sanctioned mechanism
for this situation (bounded, already safety-gated, arms on a pile of
>= LOOT_DASH_MIN_PILE (5) within LOOT_DASH_SCAN_RADIUS (420)). With 28-49
units on the ground it should be arming near-constantly. Either it fires
and fails to clear (capacity problem), or its cooldown / HP floor /
LOOT_DASH_MAX_TICKS bounds suppress it (tuning problem). These imply
opposite fixes and we cannot currently tell them apart.

## Recommendation

1. **Do NOT loosen collection aggression or the safety gates.** The
   v119 precedent (loot-biased strafe cap raised to 1.0 -> out-voted
   enemy pressure -> wave-10 death) is the failure mode, and the
   mechanism analysis shows the gates are not what is limiting
   collection anyway.
2. **Emit loot-dash telemetry** (active flag, arm/abort reason, target,
   ticks, cleared count) alongside the pending player-material-counter
   and `dropped_counts` fixes — one version bump, one smoke.
3. **Then measure dash uptime and clearance yield** on the next
   campaign, and tune the dash bounds (the bounded, safety-gated path)
   rather than the global attraction terms.
4. Economic size, for prioritisation: uncollected material is DELAYED
   income (Model A rejected — see `material_crediting_model_test.md`),
   with genuine loss confined to the terminal wave at ~1.2-1.4% of run
   income. This is a real but modest lever compared with the shop-side
   conversion evidence (v126).
