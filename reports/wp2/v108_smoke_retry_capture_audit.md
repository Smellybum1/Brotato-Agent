# WP2 combat-capture audit

- Runs with captures: 1 (1 terminal)
- Captures: 20892
- Valid transition estimate: 20892
- Gap to 200,000: 179108
- Schema mismatches: 0
- Invalid captures/actions: 0 / 0
- Near-duplicate fraction: 0.0193

## Entity count percentiles

| Group | p50 | p90 | p95 | p99 | max |
|---|---:|---:|---:|---:|---:|
| enemies | 8.0 | 19.0 | 23.0 | 29.0 | 37 |
| bosses | 0.0 | 0.0 | 0.0 | 1.0 | 1 |
| projectiles | 0.0 | 2.0 | 3.0 | 30.0 | 30 |
| materials | 11.0 | 37.0 | 47.0 | 50.0 | 50 |
| consumables | 2.0 | 5.0 | 6.0 | 8.0 | 11 |
| crates | 0.0 | 0.0 | 0.0 | 0.0 | 1 |
| obstacles | 0.0 | 1.0 | 1.0 | 1.0 | 2 |

## Severe-state capture counts

- boss: 855
- charger: 8171
- dense_projectiles: 582
- near_wall: 8

Capacities remain provisional until complete runs cover every wave band,
including representative late-projectile and wave-20 boss states.
