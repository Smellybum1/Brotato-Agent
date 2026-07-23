# WP2 v120 change record — calibrated collection thresholds

## Trigger evidence (v119 smoke, run_1784779931_16883)

Rejected by primary-agent judgment despite zero audit violations: defeat on
wave 10 (earliest death on record) and the dash never fired even though the
targeted starvation condition occurred (9.25% ground-cap saturation, waves
6-10).

Measured causes:
1. **Miscalibrated stall gate.** Materials within 420 units of the player:
   p50 4 / p90 11 / max 23 across 5,102 wave-6-10 captures — the >=30 stall
   threshold was calibrated against the global ground count, not the
   player's neighborhood, and could never fire. Best 130-unit cluster: p90
   7 / max 21, so the >=10 pile gate also almost never fired. HP floor was
   innocent (99% of captures above 0.5).
2. **Overweighted strafe bonus.** A close flank enemy contributes ~0.32
   pressure after weighting; the v119 loot bonus capped at 1.0 and the
   side-flip continuity band is 0.55, so the bonus could out-vote real
   enemy pressure and steer the orbit into material-rich (= enemy-rich)
   flanks. Implicated in the wave-10 death (40% charger presence, sustained
   chip damage, terminal cluster of five 8-damage hits).

## Changes (policy v120, mod 0.2.28)

- LOOT_DASH_STALL_COUNT 30 -> 12 (fires in the top ~10% of measured
  neighborhood accumulation).
- LOOT_DASH_MIN_PILE 10 -> 5 (real clusters are 5-9).
- ENGAGE_STRAFE_LOOT_WEIGHT 6.0 -> 4.0 and CAP 1.0 -> 0.35: strictly below
  one close flank enemy and the 0.55 continuity band — the bonus can only
  break genuine near-ties, restoring the "collect at equal safety" intent.

All dash safety bounds (HP floor, continuous-clearance window, time-box,
cooldown, audit gates) unchanged.

## Verification

Full suite: 134 passed. Requires a fresh one-run qualification smoke; the
exact-20 campaign starts only on a clean pass with the dash actually
exercised or demonstrably unnecessary (no accumulation).
