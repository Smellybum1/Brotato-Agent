# v79 pause and HUD layout fix

Updated: 2026-07-21 22:15 Australia/Brisbane

## Stopped comparison

- The user explicitly stopped the v79 comparison after four completed runs at
  **3W/1L**.
- Run 4 (`run_1784634616_90494`) was a wave-20 victory with complete telemetry
  and zero errors, hangs, or illegal actions.
- The automatically started fifth run (`run_1784635773_172`) was interrupted
  during wave 5 and is excluded from completed comparison results.
- `BrotatoAgent-LiveMonitor-v79` and `BrotatoAgent-Supervisor-v79` are disabled
  and stopped. Their verified process trees and Brotato are stopped.
- The three-minute Codex heartbeat automation was deleted.

## HUD correction

The diagnostic label could expand beyond the right edge because long metric
rows were not constrained to a viewport-width column. The HUD now:

- occupies a bounded bottom-left column (0% to 62% of viewport width);
- uses 12-pixel viewport margins;
- aligns text left and grows upward from the bottom;
- wraps long metric rows; and
- clips any residual overflow inside its viewport bounds.

The correction is installed in both the Workshop and local Brotato archives.
They are byte-identical at SHA-256
`457753F7A49F61F942082D921AABF20F10E7B2FDED192733ABBDC91994A2563F`,
and each packaged `agent_hud.gd` matches the workspace source exactly.

## Verification

- Focused HUD/source tests: **32 passed**.
- Full test suite with an isolated workspace temp root: **61 passed**.
- Package/source parity: passed for both installed archives.
- Stopped-state audit: both exact tasks disabled, no watchdog process tree, and
  no Brotato process.
- Live visual confirmation is intentionally deferred until the next
  user-authorized launch so this explicit stop is not undone.
