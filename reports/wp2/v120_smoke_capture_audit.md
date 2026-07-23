# WP2 combat-capture audit

- Runs with captures: 1 (1 terminal)
- Captures: 21899
- Valid transition estimate: 21899
- Gap to 200,000: 178101
- Schema mismatches: 0
- Invalid captures/actions: 0 / 0
- Near-duplicate fraction: 0.0343

## Entity count percentiles

| Group | p50 | p90 | p95 | p99 | max |
|---|---:|---:|---:|---:|---:|
| enemies | 8.0 | 20.0 | 24.0 | 30.0 | 37 |
| bosses | 0.0 | 0.0 | 1.0 | 1.0 | 1 |
| projectiles | 0.0 | 3.0 | 8.0 | 24.0 | 35 |
| materials | 5.0 | 15.0 | 19.0 | 25.0 | 34 |
| consumables | 2.0 | 6.0 | 7.0 | 9.0 | 12 |
| crates | 0.0 | 1.0 | 2.0 | 2.0 | 3 |
| obstacles | 0.0 | 1.0 | 1.0 | 1.0 | 2 |

## Severe-state capture counts

- boss: 1779
- charger: 9627
- dense_projectiles: 928
- low_health: 57

Capacities remain provisional until complete runs cover every wave band,
including representative late-projectile and wave-20 boss states.
