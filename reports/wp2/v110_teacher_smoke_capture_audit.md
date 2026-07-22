# WP2 combat-capture audit

- Runs with captures: 1 (1 terminal)
- Captures: 21244
- Valid transition estimate: 21244
- Gap to 200,000: 178756
- Schema mismatches: 0
- Invalid captures/actions: 0 / 0
- Near-duplicate fraction: 0.0204

## Entity count percentiles

| Group | p50 | p90 | p95 | p99 | max |
|---|---:|---:|---:|---:|---:|
| enemies | 7.0 | 18.0 | 24.0 | 33.0 | 41 |
| bosses | 0.0 | 0.0 | 1.0 | 1.0 | 1 |
| projectiles | 0.0 | 2.0 | 7.0 | 29.0 | 30 |
| materials | 7.0 | 27.0 | 38.0 | 47.0 | 50 |
| consumables | 1.0 | 3.0 | 5.0 | 6.0 | 7 |
| crates | 0.0 | 0.0 | 1.0 | 2.0 | 2 |
| obstacles | 0.0 | 1.0 | 1.0 | 1.0 | 1 |

## Severe-state capture counts

- boss: 1179
- charger: 7982
- corner: 6
- dense_projectiles: 973
- near_wall: 20

Capacities remain provisional until complete runs cover every wave band,
including representative late-projectile and wave-20 boss states.
