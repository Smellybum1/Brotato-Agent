# v102 late-wave wall-recovery hysteresis repair

## Trigger

Fresh v101 run `run_1784721856_16015` ended in a wave-19 contact defeat that
looked stationary to the user. Telemetry confirmed severe command thrashing near
the top-wall soft recovery threshold:

- 68 major fresh-command reversals in the final 15 seconds;
- 28 reversals and only 66.8 units of net displacement in the final 5 seconds;
- 17 reversals and only 76.9 units of net displacement in the final 2 seconds;
- wall distance stayed between 272.7 and 377.2 units in the final 5 seconds;
- no projectiles were present, while the closing pack grew to 44-55 enemies.

The run and partial successor `run_1784722952_84552` are excluded from training.

## Root cause

The v98/v99 final safety tail intentionally applies `_finale_wall_safety` to all
waves 17-20. However, `compute_movement` still cleared
`_finale_wall_recovery_active` on every decision below wave 20. That defeated the
existing 280-unit enter / 420-unit release hysteresis on waves 17-19: commands
just inside 280 selected an interior lane, while commands just outside 280
returned immediately to the dense-pack survival objective.

The 96-unit predictive hard-wall clamp and v101 projectile-blend repair both
passed their capture-level audits; they are not changed here.

## Repair

- Preserve `_finale_wall_recovery_active` on waves 17-19.
- Clear the latch only before `LATE_SURVIVAL_WAVE`, where the late safety tail is
  not active.
- Retain the existing release rule: a latched recovery clears only after wall
  distance reaches 420 units.
- Add a source and deterministic boundary-trace regression test reproducing the
  279/284/298/277/350/419/421-unit sequence.
- Advance policy identity to `teacher_v1-0.1.102-gun-wp1` and mod identity to
  `0.2.10-wp2-capture`. The combat-capture schema is unchanged.

## Verification

- Focused source/collector gate: **52 passed**.
- Full suite: **98 passed**.
- Expected capture schema hash:
  `95B6444796A21FD44E94113B75BA2097BC381D5F72ED784F9B9A4A99DD46D951`.

## Deployment verification

- Packaged and deployed `Tom-BrotatoAgent.zip` with 18 entries, 325,225 bytes,
  SHA-256
  `CD156A5C535A6175A28297B1BC43678F9689A8C150214F29F55BAB937E440D3E`.
- The stopped load smoke reached `AgentController ready` at 22:34:17 with zero
  matching script, parse, load, or exception faults in the ModLoader tail.
- The positively identified smoke Brotato process was stopped; no Brotato or
  teacher-collector process remains, auto-start is false, and no post-smoke
  Brotato APPCRASH event was found.

Fresh v102-only runtime collection evidence is recorded separately.
