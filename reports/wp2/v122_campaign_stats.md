# v122 exact-20 campaign — pooled telemetry statistics

Pooled tables over all **20** v122 exact-20 campaign runs, plus the **v123
smoke** run (`run_1784810419_25652`), computed by
`scripts/wp2_telemetry_stats.py` (one streaming pass/run). Full per-run + per-
wave detail is in `v122_campaign_stats.json`. Method consolidates
`v123_run5_calibration.md` / `v122_campaign_strength_drivers.md` /
`v122_exact20_covariates.md`.

- **S** = clamp(weapon_dps/dps_target, 0, 2) from combat_tick build_metrics.
- **edge** = capture <280 of any wall; **corner** = <280 of a vertical AND a
  horizontal wall (arena 2048x1536).
- **sat** = fraction of captures with ground `materials` >= **48** (near the
  50-cap; task-specified threshold, stricter than the precedents' 45).
- Tick-time tier fractions use the v123 hysteresis (strong enter 1.25/exit
  1.15, weak enter 0.75/exit 0.85).

## Pooled tier occupancy (mean of per-run tick-time fractions)

| strong >=1.25 | neutral | weak <=0.75 |
|---|---|---|
| 32.5% | 45.9% | 21.7% |

## Pooled per-wave (20 runs)

| wave | S med | edge% | corner% | loot sat% (>=48) | dmg sum |
|---|---|---|---|---|---|
| 1 | 1.01 | 9% | 0% | 0% | 0 |
| 2 | 0.86 | 9% | 0% | 0% | 0 |
| 3 | 0.95 | 14% | 0% | 0% | 0 |
| 4 | 0.98 | 15% | 1% | 0% | 2 |
| 5 | 0.93 | 13% | 1% | 0% | 0 |
| 6 | 0.87 | 11% | 1% | 0% | 0 |
| 7 | 0.89 | 17% | 1% | 1% | 3 |
| 8 | 0.83 | 16% | 0% | 1% | 11 |
| 9 | 0.88 | 11% | 1% | 5% | 23 |
| 10 | 1.01 | 43% | 12% | 20% | 141 |
| 11 | 1.06 | 23% | 1% | 5% | 109 |
| 12 | 0.98 | 21% | 2% | 4% | 24 |
| 13 | 1.17 | 26% | 1% | 6% | 127 |
| 14 | 1.26 | 30% | 1% | 13% | 39 |
| 15 | 1.23 | 36% | 1% | 26% | 45 |
| 16 | 1.25 | 17% | 2% | 3% | 83 |
| 17 | 1.18 | 43% | 3% | 12% | 357 |
| 18 | 1.29 | 55% | 3% | 24% | 123 |
| 19 | 1.31 | 57% | 3% | 42% | 80 |
| 20 | 1.34 | 30% | 0% | 12% | 947 |

## v123 smoke vs v122 pooled — late game (the rail-drift first showing)

v123 smoke = single **victory**, strong build (tick-time strong 47%, S peaks
at the 2.0 cap). n=1, directional only.

| wave | smoke edge% | v122 edge% | smoke sat% | v122 sat% | smoke S | v122 S |
|---|---|---|---|---|---|---|
| 16 | 12% | 17% | 0% | 3% | 1.68 | 1.25 |
| 17 | 43% | 43% | 8% | 12% | 2.00 | 1.18 |
| 18 | 62% | 55% | 0% | 24% | 1.96 | 1.29 |
| 19 | 73% | 57% | 27% | 42% | 2.00 | 1.31 |
| 20 | 52% | 30% | 0% | 12% | 2.00 | 1.34 |

**Wave 19 (operator-flagged):** the v123 smoke still wall-hugs (**73%** single-
wall edge, at the **top** of the v122 per-run range 18-77% / 47-73% among runs
reaching w19), so the EDGE_RAIL_DRIFT did **not** visibly cut edge dwell in its
first live showing. But wave-19 **loot saturation dropped to 27%** vs v122
pooled **42%** (per-run median 52%, up to 76%) — loot cleared better despite the
high edge dwell (confounded by the strong build clearing kills fast; n=1).
Final (wave-19) shop: smoke entering 674 / idle 20 / 5 rerolls (126g); v122 idle
gold median 27 (range 1-38) — economy comparable.
