# WP2 combat-capture audit

- Runs with captures: 1 (1 terminal)
- Captures: 21144
- Valid transition estimate: 21144
- Gap to 200,000: 178856
- Schema mismatches: 0
- Invalid captures/actions: 0 / 0
- Near-duplicate fraction: 0.0206

## Entity count percentiles

| Group | p50 | p90 | p95 | p99 | max |
|---|---:|---:|---:|---:|---:|
| enemies | 8.0 | 24.0 | 30.0 | 37.0 | 46 |
| bosses | 0.0 | 0.0 | 1.0 | 1.0 | 1 |
| projectiles | 0.0 | 4.0 | 7.0 | 18.0 | 25 |
| materials | 9.0 | 36.0 | 47.0 | 50.0 | 50 |
| consumables | 1.0 | 5.0 | 7.0 | 10.0 | 11 |
| crates | 0.0 | 1.0 | 1.0 | 3.0 | 3 |
| obstacles | 0.0 | 1.0 | 1.0 | 1.0 | 1 |

## Severe-state capture counts

- boss: 1066
- charger: 9193
- dense_projectiles: 618
- low_health: 244

Capacities remain provisional until complete runs cover every wave band,
including representative late-projectile and wave-20 boss states.
