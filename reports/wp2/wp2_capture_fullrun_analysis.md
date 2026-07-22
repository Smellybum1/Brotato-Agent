# WP2 first complete combat-capture run

Run: `run_1784679399_37598`

Result: **capture validation PASS; teacher episode DEFEAT at wave 20**

- Policy stayed `teacher_v1-0.1.92-gun-wp1`; build was
  `0.2.0-wp2-capture`.
- 20,830/20,830 captures were valid under the frozen v2 capture hash.
- Zero malformed lines, schema mismatches, invalid actions, invalid/freed
  objects, dropped entities, telemetry errors, hangs, or illegal actions.
- All wave bands and wave 20 were represented; wave 20 contributed 795 boss
  captures.
- Median/p99 capture interval: 51/54 ms. Median/p99 observation age: 0/1 ms.
- The 11,304 ms maximum interval crosses a shop/wave boundary and is excluded
  from transition training rather than treated as a control stall.
- Raw size: 178,425,034 bytes. Near-duplicate fraction under the audit's
  reduced signature: 2.14%.
- Severe-state coverage: 157 low-health, 119 dense-projectile, 69 near-wall,
  and 774 boss captures. Charger classification is diagnostic and intentionally
  broad until runtime type identifiers are mapped.

The defeat is ordinary teacher outcome evidence, not an instrumentation
failure. It is retained for rare wave-20 failure-state training and excluded
from any claim that the capture build improved gameplay.

## Observation encoder validation

The frozen `combat_obs_v1` encoder processed all 20,830 captures without an
error at 3,800.8 rows/second on this machine. All snapshots were valid, 20
shop-to-wave discontinuities were correctly marked `temporal_valid: false`, and
no group overflowed its provisional capacity. This is an encoder smoke and
capacity sanity check, not the later 10,000-fixture Godot/Python parity gate.
