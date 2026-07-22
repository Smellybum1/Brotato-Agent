# Combat observation v1 — Stage A design record

Status: **provisional capacities selected; multi-run tail validation pending**

The certified WP1 corpus contains aggregate counts but not entity arrays. WP2
therefore introduces the compatible `combat_capture` v2 event before freezing
the model input. This avoids guessing capacities or silently discarding the
most dangerous late-wave entities.

## Invariants

- Current state only; no future game state or reward leakage.
- The deterministic teacher remains the sole controller during capture. New
  collection uses v97; completed v92-v96 captures remain immutable historical data.
- Existing v1 telemetry remains unchanged; policy changes are independently
  versioned and never inferred from the capture schema version.
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

## First complete-run evidence

Run `run_1784679399_37598` reached wave 20 and yielded 20,830 valid captures
under schema hash
`95B6444796A21FD44E94113B75BA2097BC381D5F72ED784F9B9A4A99DD46D951`.
It had no malformed records, invalid actions, invalid entities, dropped
entities, telemetry errors, hangs, or illegal actions. Median/p99 within-stream
capture intervals were 51/54 ms and observation age was 0/1 ms. The 11.3-second
maximum control interval is the expected shop-to-next-wave discontinuity and
must be masked when transitions are built.

Measured whole-run p99/max counts were:

| Group | p99 | max | provisional capacity |
|---|---:|---:|---:|
| enemies | 44 | 53 | 64 |
| bosses | 1 | 1 | 2 |
| hostile-projectile candidates | 8 | 16 | 32 |
| materials | 38 | 49 | 64 |
| consumables | 5 | 9 | 24 |
| crates | 0 | 1 | 2 |
| obstacles | 2 | 3 | 8 |

The projectile and consumable capacities also respect the certified WP1
aggregate maxima (32 and 17). These capacities are provisional until multiple
complete v2 runs confirm the tails; all overflow remains deterministically
threat-sorted and explicitly counted.

## Frozen encoder contract

`configs/wp2/observation_v1.yaml` defines the current encoder contract with
schema hash
`C653D836F3EBC821A51AFC70482D3772FC7B7B927D393A6B9BBADC2718BB9B2A`.
It emits 48 ordered global features plus seven fixed-capacity entity tensors,
each with 15 features and an explicit mask. Entity rows are player-relative and
ranked by predicted contact risk, time/closest approach, distance, and stable
identity. Zero padding is inert; overflow counts remain visible.

The golden fixture digest is
`D62D26F3FCAE019A9A6E02A8C617B2C95DA8911983F3342402B645EC47E84F25`.
Inputs with NaN/Inf, a source-schema mismatch, or malformed groups are rejected.
Shop/wave gaps above 250 ms remain valid snapshots but set `temporal_valid` to
false so they cannot become ordinary one-step transitions.
