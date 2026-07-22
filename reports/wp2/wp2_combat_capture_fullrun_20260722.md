# WP2 combat-capture audit

- Runs with captures: 1 (1 terminal)
- Captures: 20830
- Valid transition estimate: 20830
- Gap to 200,000: 179170
- Schema mismatches: 0
- Invalid captures/actions: 0 / 0
- Near-duplicate fraction: 0.0214

## Entity count percentiles

| Group | p50 | p90 | p95 | p99 | max |
|---|---:|---:|---:|---:|---:|
| enemies | 8.0 | 22.0 | 30.0 | 44.0 | 53 |
| bosses | 0.0 | 0.0 | 0.0 | 1.0 | 1 |
| projectiles | 0.0 | 2.0 | 3.0 | 8.0 | 16 |
| materials | 5.0 | 20.0 | 26.0 | 38.0 | 49 |
| consumables | 1.0 | 3.0 | 4.0 | 5.0 | 9 |
| crates | 0.0 | 0.0 | 0.0 | 0.0 | 1 |
| obstacles | 0.0 | 1.0 | 2.0 | 2.0 | 3 |

## Severe-state capture counts

- boss: 774
- charger: 8902
- dense_projectiles: 119
- low_health: 157
- near_wall: 69

Capacities remain provisional until complete runs cover every wave band,
including representative late-projectile and wave-20 boss states.
