# WP2 v119 change record — stall-triggered dash and loot-biased strafe

## Trigger evidence (live v118 smoke, run_1784778591_87017, wave 10)

Operator observed substantial uncollected currency. Replay of all 1,241
wave-10 captures: materials on ground p50 19 / p90 49-50 (cap), nearest
material typically 176 units, at least one fully unblocked pile in 95% of
captures — yet local density never reached PACK_DENSITY_SOFT (8 within
280), so the v118 dash never armed (0 activations), and the ordinary desire
field kept orbiting away: engagement/strafe forces out-vote the per-item
loot pull. Neither the density hard-zero nor corridor blockers were the
active gate; collection simply never won the vote.

## Changes (policy v119, mod 0.2.27)

1. **Stall trigger:** >= LOOT_DASH_STALL_COUNT (30) materials within the
   420-unit scan radius arms the dash at any density — heavy accumulation
   is direct evidence that ordinary collection has stalled. All other dash
   bounds unchanged (HP floor, continuous-clearance window, time-box,
   cooldown, audit gates).
2. **Loot-biased strafe:** `_score_strafe_side` adds a bounded flank bonus
   (weight 6.0, cap 1.0) for materials on that side, so the weapon-range
   orbit sweeps over currency at equal safety. Enemy pressure (40/80) and
   wall openness keep their existing dominant weights.

## Verification

Full suite: 134 passed (new v119 source test with the frozen wave-10
evidence). Audit unchanged — dash gates from v118 cover the new trigger
path. Requires a fresh one-run qualification smoke; the exact-20 campaign
restarts under v119 only on a clean pass.
