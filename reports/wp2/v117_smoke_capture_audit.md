# WP2 combat-capture audit

- Runs with captures: 1 (1 terminal)
- Captures: 20455
- Valid transition estimate: 20455
- Gap to 200,000: 179545
- Schema mismatches: 0
- Invalid captures/actions: 0 / 0
- Near-duplicate fraction: 0.0257

## Entity count percentiles

| Group | p50 | p90 | p95 | p99 | max |
|---|---:|---:|---:|---:|---:|
| enemies | 9.0 | 25.0 | 31.0 | 42.0 | 51 |
| bosses | 0.0 | 0.0 | 0.0 | 1.0 | 1 |
| projectiles | 0.0 | 2.0 | 5.0 | 10.0 | 30 |
| materials | 11.0 | 41.0 | 48.0 | 50.0 | 50 |
| consumables | 2.0 | 8.0 | 9.0 | 16.0 | 18 |
| crates | 0.0 | 0.0 | 1.0 | 1.0 | 2 |
| obstacles | 0.0 | 1.0 | 1.0 | 2.0 | 3 |

## Severe-state capture counts

- boss: 377
- charger: 8160
- dense_projectiles: 263
- low_health: 218

Capacities remain provisional until complete runs cover every wave band,
including representative late-projectile and wave-20 boss states.
