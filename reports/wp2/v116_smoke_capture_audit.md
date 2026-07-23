# WP2 combat-capture audit

- Runs with captures: 1 (1 terminal)
- Captures: 20565
- Valid transition estimate: 20565
- Gap to 200,000: 179435
- Schema mismatches: 0
- Invalid captures/actions: 0 / 0
- Near-duplicate fraction: 0.0304

## Entity count percentiles

| Group | p50 | p90 | p95 | p99 | max |
|---|---:|---:|---:|---:|---:|
| enemies | 9.0 | 28.0 | 34.0 | 44.0 | 50 |
| bosses | 0.0 | 0.0 | 0.0 | 1.0 | 1 |
| projectiles | 0.0 | 2.0 | 6.0 | 9.0 | 14 |
| materials | 16.0 | 50.0 | 50.0 | 50.0 | 50 |
| consumables | 1.0 | 6.0 | 7.0 | 10.0 | 13 |
| crates | 0.0 | 1.0 | 1.0 | 2.0 | 2 |
| obstacles | 0.0 | 2.0 | 2.0 | 3.0 | 4 |

## Severe-state capture counts

- boss: 475
- charger: 8942
- dense_projectiles: 152
- low_health: 9

Capacities remain provisional until complete runs cover every wave band,
including representative late-projectile and wave-20 boss states.
