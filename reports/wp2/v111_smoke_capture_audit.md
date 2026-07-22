# WP2 combat-capture audit

- Runs with captures: 1 (1 terminal)
- Captures: 21779
- Valid transition estimate: 21779
- Gap to 200,000: 178221
- Schema mismatches: 0
- Invalid captures/actions: 0 / 0
- Near-duplicate fraction: 0.0224

## Entity count percentiles

| Group | p50 | p90 | p95 | p99 | max |
|---|---:|---:|---:|---:|---:|
| enemies | 8.0 | 17.0 | 20.0 | 27.0 | 34 |
| bosses | 0.0 | 0.0 | 1.0 | 1.0 | 1 |
| projectiles | 0.0 | 2.0 | 10.0 | 29.220000000001164 | 32 |
| materials | 11.0 | 40.0 | 46.0 | 50.0 | 50 |
| consumables | 1.0 | 4.0 | 5.0 | 8.0 | 9 |
| crates | 0.0 | 0.0 | 1.0 | 3.0 | 4 |
| obstacles | 0.0 | 1.0 | 1.0 | 1.0 | 2 |

## Severe-state capture counts

- boss: 1710
- charger: 9003
- corner: 4
- dense_projectiles: 1231
- near_wall: 4

Capacities remain provisional until complete runs cover every wave band,
including representative late-projectile and wave-20 boss states.
