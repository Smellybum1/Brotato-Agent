# v69 change and deployment record

- **Date:** 2026-07-20 (Australia/Brisbane), authored by Claude (Fable) at the operator's request following the FABLE_WP1_WIN_RATE_REVIEW_PROMPT analysis.
- **Status:** independently verified by Codex, deployed, and launched as a fresh gate at 2026-07-20 20:33 Australia/Brisbane.
- **Version:** `0.1.69-gun-wp1` / `teacher_v1-0.1.69-gun-wp1` (manifest.json, agent_controller.gd ×2, telemetry_writer.gd ×2).

## Diagnosis (from v66–v68 telemetry, 17 scored runs: 12W/5L)

- The dominant remaining failure is an **offense/kill-rate deficit**, not EHP: offense proxy (ranged+%dmg+AS) at wave 18 separates wins from losses at **d=+2.62** (wins ~137 vs losses ~75); at wave 15 d=+1.14. Weapon **tier-sums do not discriminate** — the deficit is offensive stat items/level-ups.
- The v66 HP floor worked and slightly over-corrected: losses now carry **more** bought HP (w12: 24.6 vs wins 16.6) and more crit (w9: 7.2 vs 0.6) than wins — budget mis-allocated away from damage.
- The v67 survival override correctly prevents wave-17 hit-chain deaths and does not harm healthy runs, but in DPS-starved runs it trades kills for safety and relocates death to wave 19 under runaway density (enemy peaks 91/109 vs win band 17–48; `run_1784533992_75711` took only 4 hits all wave yet drowned at 91 enemies).
- Piercing is the secondary discriminator (≥1 piercing by w18: 8/12 wins vs 1/5 losses, d=+1.22).
- Loss archetypes: runaway density from low DPS (`run_1784537410_90913` OFF=23 with tier-sum 18, `run_1784533992_75711`, `run_1784525978_54680`); density attrition (`run_1784531567_60545`); one low-density heavy-hit variance death (`run_1784532527_90900`).

## The one gameplay change: below-target offense floor

Mirror of the approved v66 HP-floor pattern, in `teacher/shop_strategy.gd` `_late_shop_pivot_bonus` (reaches shops, level-ups, and crates):

- New constants (`teacher/config.gd`): `OFFENSE_FLOOR_MID := 70.0`, `OFFENSE_FLOOR_LATE := 120.0`. Offense proxy = `stat_ranged_damage + stat_percent_damage + stat_attack_speed` from live build stats. Thresholds calibrated from telemetry (w12 win mean ~74; w15 win mean ~98, w18 win mean ~137).
- Late (wave 15+), when offense < 120: ranged 1.75→**2.30**, attack speed 1.50→**2.00**, %damage 1.30→**1.75**, piercing/bounce 2.40→**3.10**. At/above par: unchanged v65 weights.
- Mid (waves 12–14), when offense < 70: ranged 0.95→**1.45**, attack speed 0.85→**1.30**, %damage 0.70→**1.10**, piercing/bounce 1.40→**1.90**. At/above par: unchanged.
- Conditional-with-taper means healthy builds (all 12 wins would be over the late floor by ~w17) are minimally affected; offense-starved builds get offense outbidding the HP/crit/utility fillers that losses over-bought.

Everything else is untouched: v66 HP floor and crate fix, v67 survival override, v68 task settings, all combine/lock invariants, Blood Donation + Ball-and-Chain vetoes, Sharp Bullet allowed, any-gun pool.

## Supporting updates

- `trainer/evaluation/live_monitor.py`: `"0.1.69"` added to all six gated tuples; intentionally **not** added to the zero-combine (v48–58) or final-shop-combine (v55–64) tuples — the fail-open guard test enforces exactly this shape.
- `tests/unit/test_shop_policy_source.py`: `test_v68_policy_versions_are_consistent` → `test_v69_policy_versions_are_consistent`; new `test_v69_below_target_offense_floor_boosts_damage_stats_mid_and_late` asserting constants and all eight conditional coefficients.
- Full suite: **47 passed**.

## Acceptance metrics for the v69 gate

- Offense proxy ≥ ~70 by wave 12 and ≥ ~120 by wave 18 on most runs (v66–v68 losses: 14–88 at w12, 23–102 at w18).
- Losses' bought-HP/crit over-allocation shrinks (HP at w12 back toward ~16, crit at w9 < 5).
- Wave 17–19 enemy peaks stay in the win band (< ~50) — the direct symptom of the deficit.
- No degradation of HP floor outcomes (bought-HP at w9 stays ≥ ~10).

## Codex verification and deployment

- Independent full suite: **47 passed**.
- Deployed zip: `C:\Games\Steam\steamapps\workshop\content\1942280\3737864106\Tom-BrotatoAgent.zip`
- Size: 305982 bytes.
- SHA-256: `9F9B143287810CE2D11CD95C03C6422AE6AF3C7EE65B8CCB8656E2DC24045CF2`
- Zip inspection confirmed manifest `0.1.69`, controller and telemetry policy `teacher_v1-0.1.69-gun-wp1`, both offense-floor constants, and representative mid/late conditional boosts.
- Fresh gate: 20 runs, minimum 18 wins; run 1 `run_1784543594_42584` began with fresh, alert-free v69 telemetry.
- Exact tasks `BrotatoAgent-LiveMonitor-v69` and `BrotatoAgent-Supervisor-v69` were verified running with their expected scoped process trees and v68 resilience settings retained.

## Falsification / rollback signal

If v69 losses show offense at-or-above the floors yet still die to wave 17–19 density, the offense floor is not the binding constraint — revert attention to the survival override's DPS-uptime cost (below).

## Queued next repair (v70 candidate, NOT implemented)

The v67 survival override's early return skips `_build_desire` entirely, so a fleeing low-HP bot also stops seeking **healing consumables** — making the flee state self-sustaining (heal pickup is what would lift it back over the 85% threshold). It also has no hysteresis and overrides the wave-20 boss-finale engagement while HP ≤ 85%. Telemetry shows the override is not currently harming wins, so this was deliberately not bundled with v69; it is the natural next movement-dimension repair if wave-19/20 deaths persist. Separately, the v68 `RestartCount/RestartInterval/StopOnIdleEnd` task settings are likely a near no-op for the observed clean-exit failure mode (restart-on-failure does not catch exit-0 terminations and is unreliable for trigger-less on-demand tasks); a real trigger or a self-restarting wrapper would be the robust fix.
