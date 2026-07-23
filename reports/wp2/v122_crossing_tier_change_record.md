# WP2 v122 change record — crossing-range projectile tier

## Trigger evidence (v121 smoke, run_1784782516_45468)

Victory through wave 20 with the v120 diagnostics defect fixed and the dash
heavily exercised (65 episodes, all within bounds), but rejected with 2
avoidable-damage violations. Adjudication:

1. Capture 14938 (wave 15, 12 damage) — GENUINE defect. Two sampled lanes
   with identical 145.8 body clearance; the selector took the 4.62
   projectile-clearance lane over 46.39 because the continuity term (+-85)
   swamps projectile differences whenever the floor is permissive
   (best-below-panic => floor = best - 60). A bullet crossing followed.
2. Capture 17514 (wave 17, 13 damage) — AUDIT GATE BUG. The concession
   rule compared a recorded escape clearance (685.35, from an inactive
   projectile pass) against the final pass's no-bullets-in-reach sentinel
   (-1) as if it were a real clearance. The continuous replay shows no
   concession (emitted 681.0 vs best 685.4).

## Changes (policy v122, mod 0.2.30)

- `_finale_body_safety`: when the best admissible lane's projectile
  clearance is below the safe tier (crossing range), candidates must stay
  within the bounded 20-unit gain of that best lane before soft terms
  (continuity/alignment/crowd) arbitrate. Body emergencies keep their
  deliberately broadened floor. The effective floor is recorded in the
  existing diagnostic, so audit parity is unchanged.
- Audit `_avoidable_damage_violations`: the >60-unit concession check now
  requires a real (>= 0) final clearance.

## Verification

- Full suite: 138 passed (frozen fixtures for both captures).
- Re-audit of the frozen v121 smoke under v122 gates: the sentinel
  violation disappears; exactly the genuine capture-14938 violation
  remains (1). The v121 run stays rejected; v122 requires its own smoke.
