# v71 change and deployment record

- **Date:** 2026-07-21 (Australia/Brisbane), implemented after both v70 watchdog task roots vanished together during run 3.
- **Version:** `0.1.71-gun-wp1` / `teacher_v1-0.1.71-gun-wp1`.
- **Fresh gate start:** 2026-07-21 00:19 Australia/Brisbane.
- **First run:** `run_1784557174_49938`.

## Trigger and diagnosis

- v70 began 2W/0L, preserving the expected adequate-defense offense pivot. During run 3, both exact scheduled tasks transitioned together from Running to Ready while Brotato remained active.
- Both tasks reported last result `0xFFFFFFFF`. Their logs ended normally without a Python traceback, and no Brotato APPCRASH or relevant Task Scheduler/Application event explained the exit.
- v68's `RestartCount=999`, one-minute `RestartInterval`, and `StopOnIdleEnd=false` settings did not relaunch this termination class. Because the supervisor had no persistent gate checkpoint, the v70 evidence could not safely continue after a relaunch.

## The one repair: resumable triggered watchdogs

- Each exact scheduled task now has a real one-minute repeating trigger for two days. `MultipleInstances=IgnoreNew` prevents duplicates while healthy; a vanished task root is relaunched on the next trigger.
- The supervisor now checkpoints the baseline run IDs and every collected summary atomically in `reports/gate_state_v71.json`.
- A relaunched supervisor loads that checkpoint, verifies every referenced summary still exists, preserves the HUD/evidence set, and does not redeploy merely because `-Redeploy` was part of the original task action.
- A resumed already-impossible record remains impossible and cannot silently launch another run.
- Gate status now verifies trigger count, enabled state, `PT1M` interval, and `P2D` duration in addition to the v68 task settings and scoped process trees.
- The first live repeat fired at 00:20:14. Both tasks stayed Running with unchanged scoped PIDs; Task Scheduler returned the expected `0x800710E0` ignored-overlap result.

No gameplay scoring or movement changed. v71 carries v70's adequate-defense offense pivot unchanged.

## Verification and deployment

- Targeted policy/monitor tests: **42 passed**.
- Full suite with an isolated workspace temp root: **51 passed**.
- Workshop zip: `C:\Games\Steam\steamapps\workshop\content\1942280\3737864106\Tom-BrotatoAgent.zip`.
- Installed copy: `C:\Games\Steam\steamapps\common\Brotato\mods\Tom-BrotatoAgent.zip`.
- Both copies: 306539 bytes, SHA-256 `C2E6ABB37577A79FF200BBF1717F87B0B6238AE4D234573A68C92B5B66BB0C01`.
- Zip inspection confirmed manifest/controller/telemetry v71 identifiers and the unchanged v70 defense-saturation code.
- Live-monitor safety coverage was extended to v71 without changing historical zero-combine or final-shop gates.

## Acceptance

- Fresh 20-run gate requires at least 18 wins and at most two losses.
- Both exact tasks must remain Running while healthy. If either task root disappears, its one-minute trigger must restore it and the supervisor must log a resume from the same checkpoint without resetting the HUD.
- A task that remains absent past the next trigger, missing checkpoint evidence, a resume failure, or any ordinary gameplay/safety trigger is actionable.
