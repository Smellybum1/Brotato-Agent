# WP2 combat-capture audit

- Runs with captures: 1 (1 terminal)
- Captures: 20560
- Valid transition estimate: 20560
- Gap to 200,000: 179440
- Schema mismatches: 0
- Invalid captures/actions: 0 / 0
- Near-duplicate fraction: 0.0208

## Entity count percentiles

| Group | p50 | p90 | p95 | p99 | max |
|---|---:|---:|---:|---:|---:|
| enemies | 8.0 | 19.0 | 23.0 | 31.0 | 38 |
| bosses | 0.0 | 0.0 | 0.0 | 1.0 | 1 |
| projectiles | 0.0 | 2.0 | 5.0 | 24.0 | 30 |
| materials | 8.0 | 31.0 | 45.0 | 50.0 | 50 |
| consumables | 1.0 | 3.0 | 5.0 | 6.0 | 7 |
| crates | 0.0 | 0.0 | 0.0 | 1.0 | 2 |
| obstacles | 0.0 | 1.0 | 2.0 | 3.0 | 4 |

## Severe-state capture counts

- boss: 499
- charger: 8001
- corner: 5
- dense_projectiles: 428
- low_health: 98
- near_wall: 25

Capacities remain provisional until complete runs cover every wave band,
including representative late-projectile and wave-20 boss states.
