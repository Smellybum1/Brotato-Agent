# `_build_desire` is overridden on most wave-17 ticks — which is why every knob was inert

> ## ⚠️ REPLICATED, AND THE HEADLINE NUMBER CORRECTED — 5 fixtures, 5679 ticks
>
> The single-run figures below (88.3% tail-active, median 76.5°) were **the most extreme of five**.
> Replicated across five fixtures:
>
> | run | n | tail active | wall_recovery | median angle(final, desire) | **no-tail angle** |
> |---|---|---|---|---|---|
> | run_1785313331_32565 | 1159 | 0.882 | 0.869 | 76.5° | 6.2° |
> | run_1785315541_71733 | 1105 | 0.755 | 0.730 | 58.3° | 4.9° |
> | run_1785315779_89860 | 1151 | 0.500 | 0.370 | 36.7° | 7.8° |
> | run_1785316082_53811 | 1110 | 0.575 | 0.480 | 38.1° | 7.4° |
> | run_1785316379_69287 | 1154 | 0.622 | 0.570 | 54.1° | 6.0° |
>
> **Corrected headline: the tail is active on 50-88% of wave-17 ticks (pooled median angle 54.7°),
> not 88%.** The rate is strongly fixture-dependent and tracks `wall_recovery` (0.370-0.869).
>
> **What replicates almost exactly is the part that carries the argument:** when no tail flag is
> set, the desire passes through at **4.9°-7.8°** in every single run. The pipeline reading is
> solid; only the duty cycle was overstated.
>
> Read every "88%" below as "50-88%, fixture-dependent".

**Date:** 2026-07-29. First substantive result from the desire-decomposition instrument (mod
`0.2.53`). **This supersedes the framing of every movement investigation in this project.**

## The finding

The new instrument records `_build_desire`'s pre-normalise output (`total_x`, `total_y`) alongside
the final `teacher.action`. Everything between them — the projectile-escape blend, the corner guard,
smoothing, and the ordered safety tail (`_finale_projectile_safety` → `_finale_wall_safety` →
`_finale_body_safety`) — is what separates the two.

Measured on 1158 wave-17 ticks (run `run_1785313331_32565`):

| angle between the final command and `_build_desire`'s output | |
|---|---|
| median | **76.5°** |
| p25 / p75 / p90 | 39.1° / 135.4° / 163.9° |
| fraction > 30° | 0.784 |
| fraction > 90° | **0.431** |
| fraction > 150° | 0.180 |

**On 43% of ticks the final command points into a different half-plane from the desire. On 18% it is
nearly reversed.**

## It is the safety tail, not smoothing

`MOVE_SMOOTHING = 0.30`, i.e. the command is 70% previous / 30% new, so smoothing lag is a serious
alternative explanation — and the final command does sit only 15.0° from the previous action.

The discriminator is `angle(previous, DESIRE)`. If smoothing lag were the cause, the desire would be
equally far from the previous command whether or not the tail is active. It is not:

| stratum | n | angle(final, DESIRE) | angle(final, prev) | **angle(prev, DESIRE)** |
|---|---|---|---|---|
| **tail active** (88.3%) | 1022 | **85.4°** | 15.0° | **86.5°** |
| no tail flag (11.7%) | 136 | **6.2°** | 7.0° | **14.8°** |

**5.8x further when the tail is active.** When no tail flag is set, desire, previous and final all
agree within ~15° — the desire passes through essentially untouched. When the tail is active, the
command trajectory has been persistently diverted and the desire keeps pointing somewhere the agent
is not going.

By flag, median angle to the desire: `wall_recovery_active` ON **84.5°** (n=1007) vs OFF **7.1°**
(n=152); `projectile_safety_active` 82.5 vs 68.6; `body_safety_active` 75.4 vs 76.7 (no separation).

**`wall_recovery_active` is the dominant one, and it is true on 86.9% of ticks in this run** (75.7%
pooled across five agent trials, against **40.7%** for the human on the same fixture).

## What this explains

Every movement knob tested in this project has come back inert, and this is why — **the thing they
modify is thrown away 88% of the time.**

- `engage_distance_scale` on the engage spring: 6.7x dose range, 2.2% effect. Inert.
- The same knob on the `at_weapon_range` boundary: predicted ratio 0.41, observed 0.902/1.045. Inert.
- The loot density veto: fires on 0.03% of ticks, and even when it fires it modifies a desire that is
  usually discarded.
- The per-term magnitudes (`center` 20.19, `consumable` 11.16, `loot` 10.34 vs `enemy_engagement`
  2.06) describe the composition of a vector that mostly does not survive to become the command.

It also explains why the agent's *realised* behaviour (edge-hugging at 810 u from centre, standing
at 1.06x shortest weapon range, converting 1.7x less of the pack into targets) could not be traced
to any preference constant: **those behaviours are produced downstream of preferences.**

## Standing rule this establishes

**Assume any change to `_build_desire` is inert until a behavioural readback proves otherwise.**
Roughly one tick in eight is a decision `_build_desire` actually makes. A treatment applied there
has, at best, a 12% duty cycle before any effect-size consideration — which is why an offline
"does this change the argmax of the desire?" check is *not* Gate 0 for this controller. Gate 0 must
be measured on the final command.

This is the same lesson as the v128 revert ("compute the decision the fix is meant to change and
show it actually flips") applied one level further out: it is not enough for a fix to change the
desire; the desire must survive to be the command.

## Where the investigation goes

The lever, if there is one, is in the **safety tail** — specifically `_finale_wall_safety` and the
wall-recovery latch (`280`/`520` hysteresis), which owns the command on ~76-87% of wave-17 ticks.
Two questions, in order:

1. **Why is the agent at the wall at all?** Wall recovery is a *response* to edge proximity. The
   human is in it 40.7% of the time against the agent's 75.7% because the human does not go there.
   If the position is upstream, the latch is a symptom.
2. **What does wall safety do to the command when it owns it?** The `wall_*` clearance fields are
   already captured and were not analysed here.

Note that (1) is circular with the desire being discarded — the agent's position is itself produced
by the tail — so this needs care rather than another plausible chain.

## Caveats

- **One run, 1158 ticks**, for the angle analysis. The effect is enormous (85.4° vs 6.2°) so noise
  is not a plausible explanation, but replication across fixtures is running and the numbers should
  not be hardened until it lands.
- The `no tail flag` stratum is only 136 ticks and is not a random sample of game states — it is the
  quiet ticks. The claim it supports is narrow: *when the tail is inactive the desire passes
  through*, which is a statement about the pipeline, not about typical play.
- `body_safety_active` shows no separation (75.4 vs 76.7), so the body arbiter is **not** the
  overriding term despite being active on 38% of ticks. The wall path is.
