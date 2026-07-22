# WP2 combat-capture audit

- Runs with captures: 1 (1 terminal)
- Captures: 21290
- Valid transition estimate: 21290
- Gap to 200,000: 178710
- Schema mismatches: 0
- Invalid captures/actions: 0 / 0
- Near-duplicate fraction: 0.0206

## Entity count percentiles

| Group | p50 | p90 | p95 | p99 | max |
|---|---:|---:|---:|---:|---:|
| enemies | 8.0 | 19.0 | 23.0 | 29.0 | 35 |
| bosses | 0.0 | 0.0 | 1.0 | 1.0 | 1 |
| projectiles | 0.0 | 3.0 | 6.0 | 19.0 | 29 |
| materials | 4.0 | 18.0 | 24.0 | 37.0 | 50 |
| consumables | 1.0 | 4.0 | 5.0 | 7.0 | 9 |
| crates | 0.0 | 0.0 | 0.0 | 1.0 | 1 |
| obstacles | 0.0 | 0.0 | 1.0 | 1.0 | 1 |

## Severe-state capture counts

- boss: 1212
- charger: 9199
- corner: 3
- dense_projectiles: 589
- low_health: 8
- near_wall: 20

Capacities remain provisional until complete runs cover every wave band,
including representative late-projectile and wave-20 boss states.
