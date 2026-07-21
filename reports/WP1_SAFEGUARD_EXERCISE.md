# WP1 safeguard exercise

Exercise date: 2026-07-22 (Australia/Brisbane)  
Policy: v92 (`0.1.92-gun-wp1`, `teacher_v1-0.1.92-gun-wp1`)  
Excluded exercise run: `run_1784677381_46728`

## Result

Both required operator safeguards passed on a live, physically controlled
Brotato input surface.

- Manual override: during live wave 8, the operator briefly pressed a movement
  key. Physical movement immediately followed that direction, the agent stopped
  issuing movement, the HUD changed to `enabled: False`, and telemetry emitted
  `{"event":"error","payload":{"kind":"manual_override"}}` at sequence 728,
  timestamp 332724 ms.
- Emergency stop: with auto-start still armed after the manual override, the
  operator pressed Ctrl+Shift+Q. Telemetry emitted
  `{"event":"error","payload":{"kind":"emergency_stop"}}` at sequence 729,
  timestamp 407223 ms, and ModLoader logged `Emergency stop engaged` at
  09:49:42.
- Shutdown/recovery: Brotato was then closed through the scoped deployment
  helper, the same v92 archive was redeployed with auto-start disabled, and
  process/task checks found no Brotato process or v92/v920 command/Python tree.
  `agent_config.json` now records `"auto_start": false`.

## Evidence integrity and scope

The raw event file remains at
`%APPDATA%\Brotato\brotato_agent\runs\run_1784677381_46728\events.jsonl`.
At closeout it was 781,457 bytes with SHA-256
`851043F75F194ED504DC10DAE8E62EE6F74C3B4A2EF86632A6190C0A34A42B90`.
Its `run_start` records Well-Rounded, SMG, Danger 0, Endless false, retry false,
game 1.1.15.4, mod v92, and the v92 teacher policy.

This run is an intentional safeguard exercise, not evaluation evidence. It
must be excluded from win-rate, Step-1, WP2 teacher-quality, and telemetry
cleanliness claims because its two `error` events are expected test signals and
the run has no natural terminal result.
