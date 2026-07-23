# WP2 combat-capture audit

- Runs with captures: 1 (1 terminal)
- Captures: 15943
- Valid transition estimate: 15943
- Gap to 200,000: 184057
- Schema mismatches: 0
- Invalid captures/actions: 0 / 0
- Near-duplicate fraction: 0.0226

## Entity count percentiles

| Group | p50 | p90 | p95 | p99 | max |
|---|---:|---:|---:|---:|---:|
| enemies | 10.0 | 32.0 | 37.0 | 44.0 | 54 |
| bosses | 0.0 | 0.0 | 0.0 | 0.0 | 0 |
| projectiles | 0.0 | 2.0 | 10.0 | 17.0 | 24 |
| materials | 5.0 | 19.0 | 23.0 | 27.0 | 33 |
| consumables | 1.0 | 2.0 | 3.0 | 6.0 | 6 |
| crates | 0.0 | 0.0 | 1.0 | 1.0 | 1 |
| obstacles | 0.0 | 2.0 | 2.0 | 5.0 | 5 |

## Severe-state capture counts

- charger: 6625
- dense_projectiles: 824
- low_health: 12

Capacities remain provisional until complete runs cover every wave band,
including representative late-projectile and wave-20 boss states.
