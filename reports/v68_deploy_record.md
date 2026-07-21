# BrotatoAgent v68 deploy record

Date: 2026-07-20 19:24 Australia/Brisbane

## Trigger

The v67 gate was stopped at 2W/2L during run 5 after both exact watchdog scheduled tasks unexpectedly transitioned to `Ready` together while Brotato remained running. The last live-monitor entry was 19:18:52 with no Python exception, safety failure, APPCRASH, or intended supervisor shutdown. Telemetry then became stale. Task Scheduler history was unavailable; both registrations allowed idle-end termination and had no restart-on-failure policy.

The exact v67 tasks were stopped and Brotato PID 14736 was terminated. No unrelated console, Python, Slay the Spire 2, or Claude process was touched.

## Single focused v68 repair

The gate watchdog scheduled-task settings now use:

- `RestartCount=999`
- `RestartInterval=PT1M`
- `StopOnIdleEnd=false`

This is one orchestration-resilience change. The v67 gameplay policy, including the wave-17 injured survival override, is unchanged.

## Version and monitor coverage

- Mod: `0.1.68-gun-wp1`
- Policy: `teacher_v1-0.1.68-gun-wp1`
- v68 was added to every applicable live-monitor safety tuple. It remains excluded only from the intentionally historical zero-combine and final-shop-combine prohibition tuples.

## Verification

- Focused source tests: 19 passed.
- Full suite: 46 passed.
- Deployed zip: `C:\Games\Steam\steamapps\workshop\content\1942280\3737864106\Tom-BrotatoAgent.zip`
- Size: 305655 bytes.
- SHA-256: `2F58BA4A665A9591D8697D087134B43C24FE5AB78F757D8A35500C3377EE6292`
- Zip inspection confirmed manifest `0.1.68`, controller policy `teacher_v1-0.1.68-gun-wp1`, and matching telemetry policy.
- Both v68 tasks were verified `Running` with restart count 999, interval `PT1M`, and `StopOnIdleEnd=false`.
- Fresh run 1: `run_1784539456_49033`, with fresh v68 telemetry and no initial alerts.

## Gate

A fresh 20-run, 18-win gate started at 19:24 Australia/Brisbane via `scripts\start_gate_watchdogs.ps1 -Version v68 -Runs 20 -MinWins 18 -Redeploy`.
