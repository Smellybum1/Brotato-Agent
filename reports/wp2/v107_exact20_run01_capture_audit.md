# WP2 combat-capture audit

- Runs with captures: 1 (1 terminal)
- Captures: 21836
- Valid transition estimate: 21836
- Gap to 200,000: 178164
- Schema mismatches: 0
- Invalid captures/actions: 0 / 0
- Near-duplicate fraction: 0.0204

## Entity count percentiles

| Group | p50 | p90 | p95 | p99 | max |
|---|---:|---:|---:|---:|---:|
| enemies | 9.0 | 22.0 | 26.0 | 34.0 | 49 |
| bosses | 0.0 | 0.0 | 1.0 | 1.0 | 1 |
| projectiles | 0.0 | 5.0 | 13.0 | 28.0 | 30 |
| materials | 10.0 | 46.0 | 50.0 | 50.0 | 50 |
| consumables | 1.0 | 3.0 | 4.0 | 6.0 | 8 |
| crates | 0.0 | 0.0 | 1.0 | 2.0 | 2 |
| obstacles | 0.0 | 1.0 | 2.0 | 2.0 | 3 |

## Severe-state capture counts

- boss: 1779
- charger: 9591
- corner: 56
- dense_projectiles: 1432
- low_health: 5
- near_wall: 56

Capacities remain provisional until complete runs cover every wave band,
including representative late-projectile and wave-20 boss states.
