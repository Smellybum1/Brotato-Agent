# v78 change and deployment record

Updated: 2026-07-21 19:14 Australia/Brisbane

## Evidence used

The v77 shortened comparison stopped at 5W/2L. Its strongest low-density
victory combined 5,509 estimated DPS and 367 offense with only 167 defense and
8 sustain. The Minigun victory similarly paired 5,620 DPS with 235 defense.
The two failures isolated different remaining problems:

- the wave-19 loss had 404 defense and 27 sustain but only 1,995 DPS, showing
  that excess durability could not compensate for weak clearing;
- the wave-20 loss had adequate ordinary-wave clearing, but only 4.18% net
  displacement relative to commanded path length, showing that reduced direct
  reversals had not stopped the agent cancelling its escape locally.

V77 also skipped affordable offense while below target, accumulated sustain
before the old cap activated, allowed indirect sustain and ordinary utility
locks, and used an offense target that did not react to observed crowd density.

## v78 policy changes

1. Move the mid-shop offense pivot to wave 9 and the sustain cap to wave 8.
2. Add a 15-point offense security margin and a bounded density-pressure bonus:
   each point of prior-wave p90 enemy density over 15 adds three target points,
   capped at 30.
3. Treat affordable net-positive direct ranged offense as mandatory while the
   build is deficient. Only hard safety/sustain vetoes may block it.
4. Clear and veto ordinary utility locks while offense is deficient, while
   preserving rare Minigun III+ and Chain Gun IV opportunities.
5. Apply the sustain veto to mixed items and indirect healing sources including
   Garden, Medical Turret, Doc Moth, Butterfly, and Plant.
6. Sample enemy count during combat and publish prior-wave p90 density through
   build payloads, HUD, and telemetry so the adaptive target is auditable.
7. Replace finale direction-only anti-oscillation with displacement commitment:
   hold an escape lane until 120 pixels of translation or 16 recomputation
   ticks, with corner override and only a small blend toward new desire.

The v77 weapon-aware offense model, Minigun/Chain Gun policy, hard safety
rules, combine behavior, lock lifetime, and the v76 offense/defense overlay are
retained.

## Verification and deployment

- Regression suite: 59/59 passed.
- Real Steam/Godot load check: mod `Init`, `Ready`, and
  `AgentController ready`; no remaining parse or script errors.
- Workshop and local archives are byte-identical at SHA-256
  `98ACB5305D99569AC6B1C313BF4A86A36EE63ABC4EC3083D1C25AF2D9C8EDDE8`.
- Policy: `teacher_v1-0.1.78-gun-wp1`; mod: `0.1.78-gun-wp1`.
- Comparison: 8 runs, minimum 7 wins, exact watchdogs
  `BrotatoAgent-LiveMonitor-v78` and `BrotatoAgent-Supervisor-v78`.
- Initial accepted run: `run_1784625123_14638`; telemetry was fresh and healthy
  with HUD/monitor policy agreement when the gate was activated.

During real-parser validation, two Godot 3 compatibility errors that Python
tests cannot detect were found and repaired before the gate was started: an
indentation error in `shop_strategy.gd` and inferred conditional-expression
typing in `agent_controller.gd`.
