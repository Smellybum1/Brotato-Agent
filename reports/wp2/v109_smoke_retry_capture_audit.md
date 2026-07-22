# WP2 combat-capture audit

- Runs with captures: 1 (1 terminal)
- Captures: 21545
- Valid transition estimate: 21545
- Gap to 200,000: 178455
- Schema mismatches: 0
- Invalid captures/actions: 0 / 0
- Near-duplicate fraction: 0.0224

## Entity count percentiles

| Group | p50 | p90 | p95 | p99 | max |
|---|---:|---:|---:|---:|---:|
| enemies | 7.0 | 16.0 | 19.0 | 24.0 | 29 |
| bosses | 0.0 | 0.0 | 1.0 | 1.0 | 1 |
| projectiles | 0.0 | 1.0 | 4.0 | 26.0 | 30 |
| materials | 9.0 | 23.0 | 30.0 | 43.0 | 49 |
| consumables | 1.0 | 4.0 | 5.0 | 7.0 | 8 |
| crates | 0.0 | 0.0 | 1.0 | 2.0 | 3 |
| obstacles | 0.0 | 1.0 | 1.0 | 1.0 | 1 |

## Severe-state capture counts

- boss: 1435
- charger: 8215
- corner: 13
- dense_projectiles: 1035
- near_wall: 20

Capacities remain provisional until complete runs cover every wave band,
including representative late-projectile and wave-20 boss states.
