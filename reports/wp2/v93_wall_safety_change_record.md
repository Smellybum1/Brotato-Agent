# v93 change record — boss-finale wall recovery

- **Date:** 2026-07-22
- **Policy:** `teacher_v1-0.1.93-gun-wp1`
- **Capture build:** `0.2.1-wp2-capture`
- **Scope:** keep the wave-20 controller from voluntarily driving into a wall
  or preserving an outward command after reaching a corner.

## Evidence

Two completed v92 teacher captures independently reproduced the same control
failure:

- `run_1784686095_77270` reached the bottom-left corner during a Predator
  charge. Its final desired vector continued into both walls while measured
  movement fell to zero, leaving the boss to body-block and kill it.
- `run_1784689971_83278` voluntarily entered the left rail and bottom-left
  corner against an Invoker while the boss was still hundreds of units away.
  It then held an outward vector for more than three seconds until the boss
  arrived and killed it.

This isolates a final-output ordering defect: earlier corner steering could be
overridden by close-boss escape and then reintroduced by movement smoothing.
The failures are not treated as random outcomes or as useful teacher labels.

The stopped v92 collection preserved eight completed runs. Interrupted run
`run_1784691092_61493` is excluded. The completed v92 captures remain immutable
diagnostic evidence and will not be silently mixed into the primary v93
training dataset.

## Repair

The boss finale now has a latched interior-recovery envelope:

- recovery enters within 280 units of any arena wall and remains active until
  the agent regains 420 units of clearance;
- candidate inward lanes are sampled against predicted boss and projectile
  paths, so the agent does not blindly choose the geometric centre through a
  charging boss or stationary Invoker hazard ring;
- a hard 96-unit boundary projection runs after all contact escape,
  commitment, reversal handling, corner logic, and movement smoothing. It
  removes any component that still points out through a nearby wall and falls
  back toward centre if both components collapse;
- `wall_recovery_active` is exposed in finale diagnostics for live proof.

No shopping, scoring, capture schema, pre-wave-20 movement, or WP2 observation
encoding behavior changes.

## Validation and deployment

- Focused source, collector, and live-monitor regression checks: **63 passed**.
- Full repository suite: **89 passed** using workspace-local pytest basetemp.
- ModLoader/GDScript load smoke: **1/1**, reaching `Init`, `Ready`, and
  `AgentController ready` without a script or parse error.
- Both installed archives contain 18 files, report manifest version `0.2.1`,
  contain the v93 policy/build identifiers, and are byte-identical at SHA-256
  `85E3CAAC154BB46B185F8DF1D16FD11C2CF25B44A2A6E3CEA3866AD9E916E9DE`.
- No post-deploy Brotato APPCRASH evidence was found. Auto-start was restored
  to false after smoke validation.

## Live acceptance

Resume a fresh v93-only teacher collection. At each wave 20, verify from combat
captures that recovery activates near the boundary, the final action does not
retain an outward component inside the hard margin, and the agent actually
leaves a corner unless all candidate lanes are physically unsafe. Any repeated
voluntary corner stall is a stop-and-repair condition.
