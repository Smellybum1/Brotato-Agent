# WP2 combat-capture audit

- Runs with captures: 1 (1 terminal)
- Captures: 20481
- Valid transition estimate: 20481
- Gap to 200,000: 179519
- Schema mismatches: 0
- Invalid captures/actions: 0 / 0
- Near-duplicate fraction: 0.0212

## Entity count percentiles

| Group | p50 | p90 | p95 | p99 | max |
|---|---:|---:|---:|---:|---:|
| enemies | 7.0 | 19.0 | 24.0 | 38.0 | 48 |
| bosses | 0.0 | 0.0 | 0.0 | 1.0 | 1 |
| projectiles | 0.0 | 1.0 | 3.0 | 10.0 | 30 |
| materials | 11.0 | 34.0 | 44.0 | 50.0 | 50 |
| consumables | 1.0 | 4.0 | 5.0 | 6.0 | 7 |
| crates | 0.0 | 0.0 | 0.0 | 1.0 | 2 |
| obstacles | 0.0 | 1.0 | 1.0 | 1.0 | 2 |

## Severe-state capture counts

- boss: 403
- charger: 8125
- corner: 11
- dense_projectiles: 260
- low_health: 30
- near_wall: 21

Capacities remain provisional until complete runs cover every wave band,
including representative late-projectile and wave-20 boss states.
