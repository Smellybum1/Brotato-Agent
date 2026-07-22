# WP2 v104 strict final-safety change record

## Trigger

The v103 campaign was stopped after two accepted completions when the closed
audit of defeat `run_1784728121_61357` found two label-safety violations:

- captures 22690-22691 had wall recovery active, projectile safety inactive,
  and 508.549 minimum wall clearance, but emitted `(1, 0)`. The command moved
  toward center on x while leaving the limiting lower-wall clearance unchanged;
- capture 20841 had active projectile safety and a 233.690 sampled escape lane,
  but hard-wall translation preserved a 178.654-clearance final command below
  the 204.6 panic threshold without activating a wall-safe replan.

The run was otherwise structurally valid: 20,702 valid combat captures, all 20
waves, complete terminal telemetry, and zero schema, sequence, invalid-entity,
drop/capacity, illegal-action, error, hard-margin, latch-release, activation,
blend-repair, or chatter faults. Its four wave-20 damage events did not expose
a materially safer ignored final lane at the sampled hit times. The two defects
above are still unacceptable teacher labels and therefore stop the campaign.

The automatically started successor `run_1784729245_14355` was interrupted by
the stop. All v103 runs are immutable diagnostic evidence and excluded from the
primary WP2 dataset.

## Narrow repair

v104 makes two ordered safety constraints stricter without changing the capture
schema, boss-range policy, shop policy, or collection protocol:

1. While wall recovery is latched below the 520-unit release boundary,
   `_finale_lane_score` rejects every candidate whose 260-unit lookahead does
   not increase the current minimum wall clearance. Boss, projectile, desired,
   and continuity terms then rank only candidates that actually open space.
2. The wall-safe projectile selector first filters for candidates with at least
   the existing 20-unit clearance gain over the dangerous clamped baseline.
   Enemy, alignment, and continuity terms choose among those materially clearer
   lanes; they can no longer prevent every qualifying safety improvement from
   being considered.

Policy identity advances to `teacher_v1-0.1.104-gun-wp1` and mod identity to
`0.2.12-wp2-capture`. The `combat_capture_v2` schema hash remains
`95B6444796A21FD44E94113B75BA2097BC381D5F72ED784F9B9A4A99DD46D951`.

## Reversibility

The behavioral diff is confined to two candidate gates in
`teacher/potential_field.gd`, plus version declarations, tests, and this record.
Reverting the v104 commit restores the exact v103 selector behavior. Raw v103
telemetry is not modified or reused as v104 training data.

## Verification required

- Source regression tests reproduce both v103 counterexamples and assert the
  new ordering of clearance gates before scoring.
- Focused tests must pass before the full suite.
- Deployment must preserve the unchanged capture schema and prove exact ZIP,
  policy, and mod identities in a one-run smoke check.
- A fresh v104-only 20-run campaign must show zero recovery commands that fail
  to improve minimum wall clearance, zero panic-level materially safer ignored
  wall-safe lanes, and all prior projectile, hard-wall, latch, chatter, stall,
  telemetry-integrity, and dataset-capacity gates.

## Deployment and smoke verification

- Focused source/collector tests: **53 passed**.
- Full suite: **99 passed**.
- Deployed ZIP SHA-256:
  `96E1ADA6BB2A71C76C6D7B847C86D685A0BD6F2AB44193FC6A430805C59B182A`.
- Packaged identities were read back from the ZIP as policy
  `teacher_v1-0.1.104-gun-wp1`, mod `0.2.12-wp2-capture`, and the unchanged
  capture schema hash.
- One-run smoke `run_1784730074_96068` completed as a valid wave-20 defeat with
  20,624 valid captures spanning every wave, complete terminal telemetry, and
  zero sequence, schema, invalid-entity, dropped/capacity, error, hang, or
  illegal-action faults.
- The closed safety audit found zero wall-recovery commands that failed to
  increase the limiting wall, zero hard-margin outward commands, zero
  blend-repair misses, zero panic-level materially safer ignored final paths,
  and zero wall-replan regressions. Low-net-displacement windows were wide
  loops (417-581 units travelled), not stalls.
- Two non-decision capture snapshots projected a held command marginally past
  the 96-unit margin. Wave-20 capture and decision cadences are phase-aliased,
  so all such snapshots correctly reported `action_fresh=false`; actual wall
  clearance never fell below 177.383 units and no command pointed outward from
  inside the hard margin. This is telemetry sampling alias rather than a failed
  v104 decision gate.
- Raw smoke checksums: events
  `3C42945A48ED56211AB0EF10EE0B5A6D59A16A39E1E850339DA8B9F85F4188BE`,
  summary
  `FEE33118CB1C4699FC30DE5779B0A91BEA3F1EAEE9FFA129786ED31233942326`.

The isolated smoke gate is accepted. The smoke run remains diagnostic evidence
and is excluded from the fresh 20-run v104 dataset campaign.
