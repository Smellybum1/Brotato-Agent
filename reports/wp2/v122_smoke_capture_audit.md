# WP2 combat-capture audit

- Runs with captures: 1 (1 terminal)
- Captures: 20942
- Valid transition estimate: 20942
- Gap to 200,000: 179058
- Schema mismatches: 0
- Invalid captures/actions: 0 / 0
- Near-duplicate fraction: 0.0271

## Entity count percentiles

| Group | p50 | p90 | p95 | p99 | max |
|---|---:|---:|---:|---:|---:|
| enemies | 7.0 | 18.0 | 24.0 | 35.0 | 45 |
| bosses | 0.0 | 0.0 | 0.0 | 1.0 | 1 |
| projectiles | 0.0 | 1.0 | 3.0 | 24.0 | 30 |
| materials | 17.0 | 50.0 | 50.0 | 50.0 | 50 |
| consumables | 1.0 | 5.0 | 5.0 | 7.0 | 8 |
| crates | 0.0 | 0.0 | 1.0 | 1.0 | 1 |
| obstacles | 0.0 | 1.0 | 1.0 | 2.0 | 2 |

## Severe-state capture counts

- boss: 898
- charger: 7741
- dense_projectiles: 666

Capacities remain provisional until complete runs cover every wave band,
including representative late-projectile and wave-20 boss states.
