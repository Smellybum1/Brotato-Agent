# WP2 combat-capture audit

- Runs with captures: 1 (1 terminal)
- Captures: 20675
- Valid transition estimate: 20675
- Gap to 200,000: 179325
- Schema mismatches: 0
- Invalid captures/actions: 0 / 0
- Near-duplicate fraction: 0.0235

## Entity count percentiles

| Group | p50 | p90 | p95 | p99 | max |
|---|---:|---:|---:|---:|---:|
| enemies | 9.0 | 24.0 | 28.0 | 35.0 | 42 |
| bosses | 0.0 | 0.0 | 0.0 | 1.0 | 1 |
| projectiles | 0.0 | 3.0 | 6.0 | 24.0 | 30 |
| materials | 13.0 | 40.0 | 48.0 | 50.0 | 51 |
| consumables | 1.0 | 4.0 | 6.0 | 13.0 | 16 |
| crates | 0.0 | 0.0 | 0.0 | 1.0 | 2 |
| obstacles | 0.0 | 1.0 | 1.0 | 1.0 | 1 |

## Severe-state capture counts

- boss: 634
- charger: 8745
- dense_projectiles: 539

Capacities remain provisional until complete runs cover every wave band,
including representative late-projectile and wave-20 boss states.
