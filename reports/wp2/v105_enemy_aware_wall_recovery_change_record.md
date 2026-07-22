# WP2 v105 enemy-aware wall-recovery change record

## Trigger

The v104 retry campaign was stopped after five complete runs when the operator
visually identified the agent entering a pack during the fifth run's wave-17
death. Closed telemetry confirmed a label-safety regression in
`run_1784735721_60788`:

- capture 17319 selected `(0.707, 0.707)` under non-projectile wall recovery
  and immediately lost 14 HP. A wall-compatible sampled lane increased the
  predicted minimum enemy clearance from 37.9 to 61.3 units and reduced the
  0.6-second crowd-path penalty from 260.8 to 85.9;
- capture 17413 retained `(0.866, -0.5)` and lost another 14 HP. A neighboring
  wall-compatible lane improved predicted minimum clearance from -5.0 to 26.8
  units and roughly halved crowd-path penalty from 1027.1 to 549.1.
- capture 17422 then lost 14 HP under an active projectile blend. Its projectile
  clearance was ample (688.4), but the static, radius-free enemy term did not
  recognize that moving enemies made the blended path materially denser.

The selector satisfied v104's limiting-wall improvement invariant, but
`_best_finale_interior_lane` ranked bosses, projectiles, wall clearance, center,
desired direction, and continuity without any ordinary-enemy path term. Soft
wall recovery could therefore replace a valid late-survival crowd dodge with a
direction through a pack. The automatically active successor
`run_1784736672_95948` was interrupted and excluded. All v104 raw telemetry is
preserved as diagnostic evidence and is not eligible for the primary dataset.

## Narrow repair

v105 keeps the existing 280/520 recovery hysteresis, mandatory 260-unit
limiting-wall improvement, projectile priority, and 96-unit hard projection.
Only recovery-lane ranking changes:

1. Each wall-improving sampled lane receives a four-point, velocity-aware enemy
   path penalty using enemy radius and predicted position.
2. A two-pass filter first finds the least-crowded eligible lane and rejects
   candidates more than 20 penalty units worse.
3. Existing wall, boss, projectile, center, desired-direction, and continuity
   terms rank only the remaining crowd-safe lanes.
4. Projectile lane selection uses the same velocity/radius-aware crowd model,
   preserves the current projectile-clearance safety tier, and repairs a
   weighted blend that rotates back into a materially denser enemy path.
5. Capture diagnostics expose recovery and projectile input, escape, blend,
   selected, and final enemy penalties so audits can verify every translation.

Policy identity advances to `teacher_v1-0.1.105-gun-wp1` and mod identity to
`0.2.13-wp2-capture`. The compatible `combat_capture_v2` schema hash remains
`95B6444796A21FD44E94113B75BA2097BC381D5F72ED784F9B9A4A99DD46D951`.

## Reversibility

The behavioral diff is confined to recovery candidate evaluation in
`teacher/potential_field.gd` and five constants in `teacher/config.gd`, plus
diagnostics, version declarations, tests, and records. Reverting the v105 repair
commit restores exact v104 behavior. Raw telemetry is never rewritten.

## Verification required

- Focused source tests must reproduce the v104 counterexample and prove the
  crowd-safety gate precedes final score selection.
- The full suite and deployment identity checks must pass.
- An isolated v105 smoke must reach the late-wave recovery path and show every
  non-projectile recovery choice within the configured penalty slack while
  retaining all wall/projectile/hard-margin invariants.
- Only after smoke acceptance may a fresh, exactly 20-run v105 collection begin.

## Verification results

- Focused source/collector tests: **54 passed**.
- A frozen pre-deployment replay of capture 17422 selects a different sampled
  lane, raises projectile clearance from the emitted v104 value of 688.4 to
  769.5, and reduces the predictive enemy penalty from 71,602.5 to 55,859.2.
  The runtime smoke remains the authoritative behavioral gate.
- Full suite: **100 passed**.
- Deployment and smoke: pending.
