# WP2 combat-capture audit

- Runs with captures: 1 (1 terminal)
- Captures: 21128
- Valid transition estimate: 21128
- Gap to 200,000: 178872
- Schema mismatches: 0
- Invalid captures/actions: 0 / 0
- Near-duplicate fraction: 0.0267

## Entity count percentiles

| Group | p50 | p90 | p95 | p99 | max |
|---|---:|---:|---:|---:|---:|
| enemies | 8.0 | 22.0 | 29.0 | 38.0 | 49 |
| bosses | 0.0 | 0.0 | 0.0 | 1.0 | 1 |
| projectiles | 0.0 | 2.0 | 7.0 | 24.0 | 30 |
| materials | 8.0 | 25.0 | 31.0 | 41.0 | 50 |
| consumables | 1.0 | 6.0 | 7.0 | 9.0 | 11 |
| crates | 0.0 | 1.0 | 1.0 | 1.0 | 2 |
| obstacles | 0.0 | 1.0 | 1.0 | 1.0 | 1 |

## Severe-state capture counts

- boss: 1033
- charger: 7743
- dense_projectiles: 803
- low_health: 5

Capacities remain provisional until complete runs cover every wave band,
including representative late-projectile and wave-20 boss states.
