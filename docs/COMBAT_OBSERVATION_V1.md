# Combat observation v1 — Stage A design record

Status: **capacity selection blocked on focused v2 capture evidence**

The certified WP1 corpus contains aggregate counts but not entity arrays. WP2
therefore introduces the compatible `combat_capture` v2 event before freezing
the model input. This avoids guessing capacities or silently discarding the
most dangerous late-wave entities.

## Invariants

- Current state only; no future game state or reward leakage.
- The deterministic v92 teacher remains the sole controller during capture.
- Existing v1 telemetry and policy semantics remain unchanged.
- Raw capture arrays are not padded or truncated.
- Invalid objects are skipped and counted; every encoded group later receives
  an explicit mask and deterministic threat-aware ordering.
- Current and previous teacher actions provide the initial one-step temporal
  context. A longer stack requires measured delay evidence.

## Freeze sequence

1. Validate the v2 event and measure 15/20/30 Hz overhead in focused runs.
2. Measure count percentiles by wave and severe-state category.
3. Choose capacities and deterministic overflow rules from those results.
4. Define normalized global/player, weapon, and masked entity tensors in
   `configs/wp2/observation_v1.yaml`.
5. Compute the canonical schema hash and lock golden fixtures.

Teacher contribution fields in the raw capture initially carry the controller's
existing diagnostic breakdown. Major risk and attraction components must be
made explicit before residual-policy training begins.
