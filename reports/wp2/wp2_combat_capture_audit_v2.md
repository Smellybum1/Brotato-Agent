# WP2 combat-capture audit

- Runs with captures: 1 (1 terminal)
- Captures: 717
- Valid transition estimate: 717
- Gap to 200,000: 199283
- Schema mismatches: 0
- Invalid captures/actions: 0 / 0
- Near-duplicate fraction: 0.0335

## Entity count percentiles

| Group | p50 | p90 | p95 | p99 | max |
|---|---:|---:|---:|---:|---:|
| enemies | 10.0 | 23.0 | 26.0 | 29.840000000000032 | 31 |
| bosses | 1.0 | 1.0 | 1.0 | 1.0 | 1 |
| projectiles | 0.0 | 16.0 | 23.0 | 24.0 | 24 |
| materials | 9.0 | 28.0 | 31.0 | 35.0 | 36 |
| consumables | 0.0 | 1.0 | 2.0 | 3.0 | 3 |
| crates | 0.0 | 0.0 | 1.0 | 1.0 | 1 |
| obstacles | 0.0 | 0.39999999999997726 | 1.0 | 1.0 | 1 |

## Severe-state capture counts

- boss: 696
- charger: 672
- dense_projectiles: 149

Capacities remain provisional until complete runs cover every wave band,
including representative late-projectile and wave-20 boss states.
