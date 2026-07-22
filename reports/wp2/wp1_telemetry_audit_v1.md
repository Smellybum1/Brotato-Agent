# WP2 Stage-A WP1 telemetry audit

Result: **PASS FOR INTERFACE REPAIR**

- Runs: 20 (20 terminal)
- Combat ticks: 40491
- Valid transition estimate: 40491
- Gap to 200,000-transition minimum: 159509
- Tick gap p50/p99/max: 500.0 / 518.0 / 12424.0 ms
- Action magnitude p50/p99/max: 1.000000001077 / 1.0000005721026863 / 1.0000007241447377
- Exact reduced-signature duplicate fraction: 0.0355
- Invalid/non-finite actions: 0

## Count percentiles

These are aggregate counts only and are insufficient to select entity-array capacities.

| Group | p50 | p90 | p95 | p99 | max |
|---|---:|---:|---:|---:|---:|
| consumables | 1.0 | 5.0 | 7.0 | 10.0 | 17.0 |
| enemies | 8.0 | 19.0 | 24.0 | 39.0 | 109.0 |
| materials | 7.0 | 29.0 | 39.5 | 50.0 | 50.0 |
| projectiles | 0.0 | 2.0 | 5.0 | 24.0 | 32.0 |

## Required field availability

| Field | Ticks | Fraction |
|---|---:|---:|
| player_position | 0 | 0.0000 |
| player_velocity | 0 | 0.0000 |
| wave_timer | 0 | 0.0000 |
| enemy_entities | 0 | 0.0000 |
| projectile_entities | 0 | 0.0000 |
| material_entities | 0 | 0.0000 |
| consumable_entities | 0 | 0.0000 |
| crate_entities | 0 | 0.0000 |
| obstacle_entities | 0 | 0.0000 |
| teacher_action | 40491 | 1.0000 |
| previous_action | 0 | 0.0000 |
| teacher_contributions | 0 | 0.0000 |
| observation_age | 0 | 0.0000 |

## Blocking telemetry repairs

- Player position/velocity and wave timer are absent from the certified v72 corpus.
- Observation-to-action delay and observation age are not recorded.
- Previous action and teacher field contributions are absent.
- Enemy/projectile identity, position, velocity, radius, health, and threat features are absent.
- Charger/elite/boss categories cannot be derived reliably from v72 ticks.
- Invalid/freed-object incidence is not explicitly observable in v72 telemetry.
- Per-entity enemy arrays are absent; count percentiles cannot define a threat-aware capacity.
- Per-entity hostile projectile arrays are absent.
- Materials and consumables are counts only; positions and velocities are absent.
- Crate and obstacle counts/entities are absent.

The certified v72 corpus remains valid WP1 evidence, but it cannot directly produce
`combat_obs_v1` or the mandatory 200k transition dataset. Add a compatible new
combat-telemetry schema, validate it in focused live teacher runs, and compute
capacities from those per-entity distributions before dataset harvesting.
