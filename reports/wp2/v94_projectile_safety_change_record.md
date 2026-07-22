# v94 change record — final projectile safety

- **Date:** 2026-07-22
- **Policy:** `teacher_v1-0.1.94-gun-wp1`
- **Capture build:** `0.2.2-wp2-capture`
- **Scope:** prevent late finale transforms and movement smoothing from undoing
  a projectile escape that the existing evaluator had already identified.

## Evidence

The stopped v93-only collection completed three runs. The first two were
victories with clean wall-recovery audits. The third,
`run_1784694303_25583`, died to the Predator on wave 20 after repeated
18-damage projectile hits. The agent stayed away from the hard wall margin, so
this is distinct from the v92 corner-stall defect.

Replay of the combat captures immediately before four hits showed that the
final command retained only about 12.1, 7.6, 5.7, and 44.2 pixels of predicted
projectile clearance while sampled lanes offered about 140.2, 122.6, 182.5,
and 91.7 pixels respectively. Re-running the existing projectile evaluator
against those final commands selected materially safer directions. The defect
was ordering: low-health ring recovery, reversal handling, committed escape,
and smoothing all ran after the original projectile pass.

Interrupted v93 run `run_1784695478_70195` stopped at wave 8 and is excluded.
All v93 captures remain immutable diagnostic evidence and will not be mixed
into the primary v94 training dataset.

## Repair

- The existing `_projectile_escape` evaluator is rerun on wave 20 after all
  finale transforms and movement smoothing.
- Its urgency is applied to the actual final candidate rather than an earlier
  desire vector.
- The v93 wall-safety projection remains the last movement constraint.
- Finale diagnostics expose whether the final pass activated, its urgency,
  the input-command clearance, and the selected escape-lane clearance.

No shopping, scoring, capture schema, or pre-wave-20 movement behavior changes.

## Acceptance

Pre-campaign validation passed:

- focused source, collector, and live-monitor checks: **64 passed**;
- full repository suite: **90 passed**;
- ModLoader/GDScript load smoke: **1/1**, reaching `AgentController ready`
  without a script or parse error;
- both installed archives contain 18 files, report manifest `0.2.2`, contain
  the v94 policy/build identifiers exactly once, and are byte-identical at
  SHA-256
  `F2E2A386A028BE444C463AC9E81057F281F22886E5DEA199E8CD8456472E0950`;
- no post-deploy Brotato APPCRASH evidence was found, and auto-start was
  restored to false after smoke validation.

Start a fresh v94-only 20-run teacher collection. For every wave-20 run,
verify that dangerous final projectile clearance activates the final pass,
that the emitted command takes a materially safer available lane, and that
wall recovery still prevents outward commands or voluntary corner stalls.
