# WP2 combat-capture audit

- Runs with captures: 1 (1 terminal)
- Captures: 20474
- Valid transition estimate: 20474
- Gap to 200,000: 179526
- Schema mismatches: 0
- Invalid captures/actions: 0 / 0
- Near-duplicate fraction: 0.0266

## Entity count percentiles

| Group | p50 | p90 | p95 | p99 | max |
|---|---:|---:|---:|---:|---:|
| enemies | 8.0 | 25.0 | 30.0 | 35.0 | 43 |
| bosses | 0.0 | 0.0 | 0.0 | 1.0 | 1 |
| projectiles | 0.0 | 2.0 | 5.0 | 10.0 | 25 |
| materials | 5.0 | 19.0 | 26.0 | 46.0 | 50 |
| consumables | 1.0 | 4.0 | 6.0 | 9.0 | 10 |
| crates | 0.0 | 1.0 | 1.0 | 2.0 | 2 |
| obstacles | 0.0 | 1.0 | 1.0 | 3.0 | 3 |

## Severe-state capture counts

- boss: 390
- charger: 7971
- dense_projectiles: 260
- low_health: 29
- near_wall: 4

Capacities remain provisional until complete runs cover every wave band,
including representative late-projectile and wave-20 boss states.
