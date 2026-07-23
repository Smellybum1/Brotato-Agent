# WP2 combat-capture audit

- Runs with captures: 1 (1 terminal)
- Captures: 20683
- Valid transition estimate: 20683
- Gap to 200,000: 179317
- Schema mismatches: 0
- Invalid captures/actions: 0 / 0
- Near-duplicate fraction: 0.0193

## Entity count percentiles

| Group | p50 | p90 | p95 | p99 | max |
|---|---:|---:|---:|---:|---:|
| enemies | 7.0 | 16.0 | 19.0 | 26.0 | 35 |
| bosses | 0.0 | 0.0 | 0.0 | 1.0 | 1 |
| projectiles | 0.0 | 1.0 | 2.0 | 13.0 | 24 |
| materials | 13.0 | 44.0 | 50.0 | 50.0 | 50 |
| consumables | 1.0 | 4.0 | 5.0 | 7.0 | 9 |
| crates | 0.0 | 1.0 | 1.0 | 1.0 | 2 |
| obstacles | 0.0 | 1.0 | 1.0 | 2.0 | 3 |

## Severe-state capture counts

- boss: 620
- charger: 7845
- corner: 10
- dense_projectiles: 248
- low_health: 73
- near_wall: 25

Capacities remain provisional until complete runs cover every wave band,
including representative late-projectile and wave-20 boss states.
