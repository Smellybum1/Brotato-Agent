# WP2 combat-capture audit

- Runs with captures: 1 (1 terminal)
- Captures: 8313
- Valid transition estimate: 8313
- Gap to 200,000: 191687
- Schema mismatches: 0
- Invalid captures/actions: 0 / 0
- Near-duplicate fraction: 0.0255

## Entity count percentiles

| Group | p50 | p90 | p95 | p99 | max |
|---|---:|---:|---:|---:|---:|
| enemies | 6.0 | 19.0 | 24.0 | 30.0 | 41 |
| bosses | 0.0 | 0.0 | 0.0 | 0.0 | 0 |
| projectiles | 0.0 | 0.0 | 1.0 | 2.0 | 3 |
| materials | 8.0 | 35.0 | 50.0 | 50.0 | 50 |
| consumables | 0.0 | 2.0 | 4.0 | 6.0 | 8 |
| crates | 0.0 | 0.0 | 0.0 | 1.0 | 1 |
| obstacles | 0.0 | 1.0 | 2.0 | 2.0 | 3 |

## Severe-state capture counts

- charger: 3289
- low_health: 24

Capacities remain provisional until complete runs cover every wave band,
including representative late-projectile and wave-20 boss states.
