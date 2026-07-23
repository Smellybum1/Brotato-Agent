# WP2 v112 Smoke Stop/Repair Report

- Run: `run_1784763667_57757`
- Result: defeat on wave 20
- Capture structure: accepted (20,683 captures, all waves, terminal summary, zero telemetry errors)
- Teacher safety: rejected
- Dataset eligible: no

## Failure

The user-observed route through a pack is present in telemetry. At captures
20175 and 20176 the emitted route had predicted body clearances of 113.4 and
97.3, while sampled hard-wall-safe routes offered 206.0 and 201.9. The bounded
wall-body relief rule activated too late. A later active-relief decision also
used 292.4 clearance when 317.0 was available, narrowly missing the audit's
near-best tier after one frame of geometry change.

The original audit reported 26 faults. Twenty-three were a false overlap
between the strict inward-progress rule and the explicitly permitted bounded
body-relief exception. The corrected v113 re-audit reports the nine genuine
route-selection faults: eight missed early relief opportunities and one active
relief route outside the near-best tier.

## Repair

- Start wall-body relief at 140 clearance instead of 120, before the route is
  already deep in pack danger.
- Require an active relief command to remain within 10 clearance units of the
  best compatible hard-wall-safe lane, leaving a buffer inside the 20-unit
  audit limit.
- Exempt active bounded relief from the mutually exclusive strict inward-wall
  progress check while retaining hard-wall, projectile-tier, and near-best
  route checks.
- Version the repaired build as policy `teacher_v1-0.1.113-gun-wp1` and mod
  `0.2.21-wp2-capture`.

The v112 run remains preserved as rejected smoke evidence and is excluded from
the WP2 dataset.
