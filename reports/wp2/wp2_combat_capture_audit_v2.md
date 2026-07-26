# WP2 combat-capture audit

- Runs with captures: 1 (1 terminal)
- Captures: 1581
- Valid transition estimate: 1581
- Gap to 200,000: 198419
- Schema mismatches: 0
- Invalid captures/actions: 0 / 0
- Near-duplicate fraction: 0.0051

## Entity count percentiles

| Group | p50 | p90 | p95 | p99 | max |
|---|---:|---:|---:|---:|---:|
| enemies | 7.0 | 15.0 | 17.0 | 21.0 | 23 |
| bosses | 1.0 | 1.0 | 1.0 | 1.0 | 1 |
| projectiles | 11.0 | 21.0 | 23.0 | 26.0 | 28 |
| materials | 23.0 | 37.0 | 39.0 | 45.0 | 47 |
| consumables | 2.0 | 4.0 | 5.0 | 5.0 | 5 |
| crates | 0.0 | 0.0 | 0.0 | 0.0 | 1 |
| obstacles | 0.0 | 0.0 | 0.0 | 1.0 | 1 |

## Severe-state capture counts

- boss: 1558
- charger: 1104
- dense_projectiles: 848

Capacities remain provisional until complete runs cover every wave band,
including representative late-projectile and wave-20 boss states.
