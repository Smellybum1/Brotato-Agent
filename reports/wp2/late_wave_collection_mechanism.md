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
| Loot dash uptime (v118, the sanctioned pile-clearing mechanism) | `_apply_loot_dash` | 3.3% of ticks | 9.3% | **REFUTED as a shutdown** — the dash runs *more* in late waves, not less (see correction below) |

## Conclusion

There is no single gate slamming shut at wave 10. The two hard
suppression mechanisms (density veto, edge-kite) do not fire in the
relevant range. The degradation is cumulative: late waves drop far more
material, spread ~28% farther from the player, while the attraction force
falls off as 1/distance and combat/strafe forces dominate the summed
vector — with ~12% of visible piles additionally vetoed by the corridor
rule. The agent is not refusing loot; it is out-ranged and out-voted.

## CORRECTION (2026-07-25): uptime was already observable, and was measured

The claim above that loot-dash uptime is unobservable was **wrong**, and the
correction changes the conclusion. `finale_translation` — which nests
`loot_dash_active` — *is* in the emitted payload, in two places: at 20 Hz in
`combat_capture.teacher.contributions.finale_translation`, and at 0.5 s in
`combat_tick.debug.finale_translation`. `scripts/wp2_telemetry_stats.py` already
edge-detects dash episodes from it. Only the *reasons* were missing.

Measured over the 5 most recent completed pure-teacher runs
(`teacher_v1-0.1.125-gun-wp1`; student-driven runs excluded, since under a student
override `loot_dash_active` is teacher intent rather than applied behaviour — the 9
student runs give a near-identical 10.7%):

| band | w1-5 | w6-10 | w11-15 | w16-19 | w20 |
|---|---|---|---|---|---|
| dash uptime | 3.3% | 16.2% | 9.3% | 12.2% | 0.0% |

Overall 10.5% of capture ticks. Two conclusions follow:

1. **The dash is not shut off in late waves.** It arms and runs throughout the
   range where collection degrades — more than in waves 1-5, not less. Any
   hypothesis that the wave-10 transition is the dash going quiet is refuted.
2. **Wave 20 is exactly 0.0% by design**, not by suppression: the boss-finale
   branch drops any dash and returns before `_apply_loot_dash` is ever reached.

## Remaining gap (still blocks the actionable next step)

What uptime alone cannot say is what the dash *achieved* in those ~10% of ticks,
or what blocked the other ~90%. The dash is EXACTLY the sanctioned mechanism for
this situation (bounded, already safety-gated, arms on a pile of
>= LOOT_DASH_MIN_PILE (5) within LOOT_DASH_SCAN_RADIUS (420)), so with 28-49 units
on the ground the live question is now sharper: of the dashes that do fire, how
many end with the pile actually gone (`aborted_pile_gone`) versus timing out with
material still there (`aborted_ticks`) — a capacity problem — and of the ticks that
do not arm, how many are held off by cooldown or the HP floor versus simply never
finding a qualifying pile (`not_armed_no_pile`) — a tuning problem. These imply
opposite fixes and uptime does not separate them.

v127 closes this: `teacher.contributions.loot_dash` carries the per-tick outcome
code, the arm/abort transition counter, the scan and best-cluster sizes the arming
check computed, and — via `player.materials`, added in the same version — an exact
per-dash material yield by differencing across a dash window. See
`docs/TELEMETRY_SCHEMA.md` and `reports/wp2/v127_change_record.md`. Not yet
deployed; no v127 data exists.

## Recommendation

1. **Do NOT loosen collection aggression or the safety gates.** The
   v119 precedent (loot-biased strafe cap raised to 1.0 -> out-voted
   enemy pressure -> wave-10 death) is the failure mode, and the
   mechanism analysis shows the gates are not what is limiting
   collection anyway.
2. **Emit loot-dash telemetry** (arm/abort reason, ticks, cooldown, scan
   and cluster sizes) alongside the pending player-material-counter and
   `dropped_counts` fixes — one version bump, one smoke. **DONE in v127**
   (implemented, not deployed); uptime turned out to be measurable
   already and is reported in the correction above.
3. **Then measure clearance yield and the blocked-reason mix** on the
   next campaign — uptime alone is now known not to settle it — and tune
   the dash bounds (the bounded, safety-gated path) rather than the
   global attraction terms.
4. Economic size, for prioritisation: uncollected material is DELAYED
   income (Model A rejected — see `material_crediting_model_test.md`),
   with genuine loss confined to the terminal wave at ~1.2-1.4% of run
   income. This is a real but modest lever compared with the shop-side
   conversion evidence (v126).
