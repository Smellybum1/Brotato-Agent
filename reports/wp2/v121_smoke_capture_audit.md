# WP2 combat-capture audit

- Runs with captures: 1 (1 terminal)
- Captures: 21517
- Valid transition estimate: 21517
- Gap to 200,000: 178483
- Schema mismatches: 0
- Invalid captures/actions: 0 / 0
- Near-duplicate fraction: 0.0276

## Entity count percentiles

| Group | p50 | p90 | p95 | p99 | max |
|---|---:|---:|---:|---:|---:|
| enemies | 9.0 | 26.0 | 30.0 | 38.0 | 50 |
| bosses | 0.0 | 0.0 | 1.0 | 1.0 | 1 |
| projectiles | 0.0 | 3.0 | 6.0 | 20.0 | 27 |
| materials | 12.0 | 44.0 | 49.0 | 50.0 | 50 |
| consumables | 1.0 | 4.0 | 6.0 | 8.0 | 9 |
| crates | 0.0 | 0.0 | 1.0 | 1.0 | 2 |
| obstacles | 0.0 | 1.0 | 1.0 | 2.0 | 3 |

## Severe-state capture counts

- boss: 1438
- charger: 9880
- dense_projectiles: 654
- low_health: 111

Capacities remain provisional until complete runs cover every wave band,
including representative late-projectile and wave-20 boss states.
