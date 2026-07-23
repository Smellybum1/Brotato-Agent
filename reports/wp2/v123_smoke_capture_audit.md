# WP2 combat-capture audit

- Runs with captures: 1 (1 terminal)
- Captures: 21268
- Valid transition estimate: 21268
- Gap to 200,000: 178732
- Schema mismatches: 0
- Invalid captures/actions: 0 / 0
- Near-duplicate fraction: 0.0273

## Entity count percentiles

| Group | p50 | p90 | p95 | p99 | max |
|---|---:|---:|---:|---:|---:|
| enemies | 8.0 | 22.0 | 26.0 | 34.0 | 42 |
| bosses | 0.0 | 0.0 | 1.0 | 1.0 | 1 |
| projectiles | 0.0 | 3.0 | 7.0 | 20.0 | 26 |
| materials | 7.0 | 22.0 | 31.0 | 50.0 | 50 |
| consumables | 1.0 | 6.0 | 8.0 | 9.0 | 10 |
| crates | 0.0 | 1.0 | 1.0 | 1.0 | 2 |
| obstacles | 0.0 | 1.0 | 1.0 | 2.0 | 2 |

## Severe-state capture counts

- boss: 1188
- charger: 8889
- dense_projectiles: 622
- low_health: 213

Capacities remain provisional until complete runs cover every wave band,
including representative late-projectile and wave-20 boss states.
