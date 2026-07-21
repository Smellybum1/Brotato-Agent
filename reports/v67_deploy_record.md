# v67 deployment record

- **Date:** 2026-07-20 (Australia/Brisbane), packaged at approximately 17:51.
- **Version:** `0.1.67-gun-wp1` / policy `teacher_v1-0.1.67-gun-wp1`.
- **Superseded gate:** v66 stopped automatically at **8W/3L after 11 runs**. All three defeats occurred on wave 17 (`run_1784525978_54680`, `run_1784531567_60545`, and `run_1784532527_90900`) with complete telemetry and zero errors, hangs, illegal actions, or Brotato APPCRASH events.

## Single focused policy repair

`teacher/potential_field.gd` now applies a late low-health survival override:

- Activation: wave 17 or later, current HP at or below 85% of max HP, with a live enemy, boss, or projectile threat.
- Behavior: use the existing panic dodge when it fires; otherwise use the existing pure-repulsion flee direction. Blend at 0.70 and return before normal engagement, edge-kite, or boss-finale movement.
- Recovery: normal movement resumes automatically after HP rises above 85%.

Rationale: v66 fixed the early HP deficit, but each loss entered wave 17 with 67-76 HP and then died to a chained-hit sequence. Two losses saw tail enemy peaks of 50-51; the third peaked at only 28, so enemy count alone did not explain the failures. The common failure mode was continued engagement after the first meaningful hit. The override preserves full-health combat behavior and changes only injured late-wave movement.

## Explicitly unchanged

- v66 max-HP valuation, crate weapon identity, and combine-timeout barrier release.
- The wave-16+ corner guard and intentional any-gun pool.
- Blood Donation and Ball-and-Chain vetoes; Sharp Bullet remains allowed.
- Shop policy, item tiers, reroll caps, locks, and harvesting valuation.
- All combine invariants. One safeguarded wave-19 combine remains allowed and is not a final-shop violation.

## Tests and monitoring

- Added `test_v67_wave17_low_hp_survival_override_uses_repulsion_before_normal_kiting`.
- Bumped the policy/version consistency and live-monitor fail-open tests to v67.
- Added `0.1.67` to every applicable live-monitor safety tuple. The intentionally historical zero-combine tuple and the v55-v64 final-shop-combine prohibition remain the only exclusions.
- Focused source tests: **18 passed**.
- Full suite: **45 passed**.

## Deployment verification

- Workshop zip: `C:\Games\Steam\steamapps\workshop\content\1942280\3737864106\Tom-BrotatoAgent.zip`
- Size: 305655 bytes.
- SHA-256: `1D63E76BC601EFC39F22F40145DDDC0882D813BE4FC142B2F1360D199432C92A`.
- Zip inspection confirmed manifest `0.1.67`, v67 policy metadata, wave-17 threshold, 0.85 HP threshold, and the pure-repulsion override.

## Gate

- Fresh gate: 20 runs, at least 18 wins, at most two losses.
- Started: 2026-07-20 17:53 Australia/Brisbane; initial run `run_1784533992_75711` verified on `teacher_v1-0.1.67-gun-wp1` / `0.1.67-gun-wp1` with fresh telemetry.
- Watchdogs: `BrotatoAgent-LiveMonitor-v67` and `BrotatoAgent-Supervisor-v67`.
- Logs: `reports/live_monitor_v67.log` and `reports/overnight_supervisor_v67.log`.
- Startup audit: both exact scheduled tasks and their scoped process trees running, Brotato running, HUD freshly reset to 0/0, deployed zip hash unchanged after supervisor redeploy, and zero Brotato APPCRASH events after the v67 start.
