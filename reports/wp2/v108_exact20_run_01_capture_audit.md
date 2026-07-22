# WP2 combat-capture audit

- Runs with captures: 1 (1 terminal)
- Captures: 20830
- Valid transition estimate: 20830
- Gap to 200,000: 179170
- Schema mismatches: 0
- Invalid captures/actions: 0 / 0
- Near-duplicate fraction: 0.0218

## Entity count percentiles

| Group | p50 | p90 | p95 | p99 | max |
|---|---:|---:|---:|---:|---:|
| enemies | 8.0 | 18.0 | 22.0 | 32.0 | 47 |
| bosses | 0.0 | 0.0 | 0.0 | 1.0 | 1 |
| projectiles | 0.0 | 1.0 | 3.0 | 13.0 | 26 |
| materials | 10.0 | 30.0 | 38.0 | 48.0 | 50 |
| consumables | 1.0 | 5.0 | 6.0 | 8.0 | 9 |
| crates | 0.0 | 1.0 | 1.0 | 1.0 | 3 |
| obstacles | 0.0 | 1.0 | 1.0 | 2.0 | 2 |

## Severe-state capture counts

- boss: 753
- charger: 8197
- corner: 36
- dense_projectiles: 250
- low_health: 124
- near_wall: 34

Capacities remain provisional until complete runs cover every wave band,
including representative late-projectile and wave-20 boss states.
