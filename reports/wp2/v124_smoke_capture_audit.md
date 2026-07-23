# WP2 combat-capture audit

- Runs with captures: 1 (1 terminal)
- Captures: 17188
- Valid transition estimate: 17188
- Gap to 200,000: 182812
- Schema mismatches: 0
- Invalid captures/actions: 0 / 0
- Near-duplicate fraction: 0.0226

## Entity count percentiles

| Group | p50 | p90 | p95 | p99 | max |
|---|---:|---:|---:|---:|---:|
| enemies | 9.0 | 23.0 | 27.0 | 32.0 | 37 |
| bosses | 0.0 | 0.0 | 0.0 | 0.0 | 0 |
| projectiles | 0.0 | 2.0 | 7.0 | 11.0 | 15 |
| materials | 14.0 | 47.0 | 50.0 | 50.0 | 51 |
| consumables | 1.0 | 5.0 | 5.0 | 6.0 | 8 |
| crates | 0.0 | 0.0 | 1.0 | 1.0 | 2 |
| obstacles | 0.0 | 2.0 | 2.0 | 3.0 | 3 |

## Severe-state capture counts

- charger: 7232
- dense_projectiles: 329
- low_health: 10

Capacities remain provisional until complete runs cover every wave band,
including representative late-projectile and wave-20 boss states.
