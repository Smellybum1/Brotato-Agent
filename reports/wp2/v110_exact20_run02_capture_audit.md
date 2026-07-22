# WP2 combat-capture audit

- Runs with captures: 1 (1 terminal)
- Captures: 21223
- Valid transition estimate: 21223
- Gap to 200,000: 178777
- Schema mismatches: 0
- Invalid captures/actions: 0 / 0
- Near-duplicate fraction: 0.0198

## Entity count percentiles

| Group | p50 | p90 | p95 | p99 | max |
|---|---:|---:|---:|---:|---:|
| enemies | 7.0 | 16.0 | 20.0 | 29.0 | 40 |
| bosses | 0.0 | 0.0 | 1.0 | 1.0 | 1 |
| projectiles | 0.0 | 1.0 | 3.0 | 18.0 | 26 |
| materials | 9.0 | 31.0 | 42.0 | 49.0 | 50 |
| consumables | 1.0 | 4.0 | 5.0 | 7.0 | 8 |
| crates | 0.0 | 0.0 | 1.0 | 1.0 | 1 |
| obstacles | 0.0 | 1.0 | 1.0 | 2.0 | 2 |

## Severe-state capture counts

- boss: 1140
- charger: 8517
- corner: 2
- dense_projectiles: 489
- low_health: 581
- near_wall: 23

Capacities remain provisional until complete runs cover every wave band,
including representative late-projectile and wave-20 boss states.
