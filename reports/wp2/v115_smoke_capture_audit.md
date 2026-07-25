# WP2 combat-capture audit

- Runs with captures: 1 (1 terminal)
- Captures: 21835
- Valid transition estimate: 21835
- Gap to 200,000: 178165
- Schema mismatches: 0
- Invalid captures/actions: 0 / 0
- Near-duplicate fraction: 0.0286

## Entity count percentiles

| Group | p50 | p90 | p95 | p99 | max |
|---|---:|---:|---:|---:|---:|
| enemies | 10.0 | 25.0 | 31.0 | 42.0 | 53 |
| bosses | 0.0 | 0.0 | 1.0 | 1.0 | 1 |
| projectiles | 0.0 | 5.0 | 13.0 | 28.0 | 30 |
| materials | 17.0 | 50.0 | 50.0 | 50.0 | 50 |
| consumables | 1.0 | 5.0 | 6.0 | 8.0 | 13 |
| crates | 0.0 | 1.0 | 1.0 | 2.0 | 2 |
| obstacles | 0.0 | 1.0 | 1.0 | 2.0 | 3 |

## Severe-state capture counts

- boss: 1779
- charger: 9678
- dense_projectiles: 1564
- low_health: 463

Capacities remain provisional until complete runs cover every wave band,
including representative late-projectile and wave-20 boss states.
