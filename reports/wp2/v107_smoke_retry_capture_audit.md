# WP2 combat-capture audit

- Runs with captures: 1 (1 terminal)
- Captures: 21242
- Valid transition estimate: 21242
- Gap to 200,000: 178758
- Schema mismatches: 0
- Invalid captures/actions: 0 / 0
- Near-duplicate fraction: 0.0231

## Entity count percentiles

| Group | p50 | p90 | p95 | p99 | max |
|---|---:|---:|---:|---:|---:|
| enemies | 8.0 | 19.0 | 23.0 | 32.0 | 42 |
| bosses | 0.0 | 0.0 | 1.0 | 1.0 | 1 |
| projectiles | 0.0 | 2.0 | 5.0 | 25.0 | 30 |
| materials | 7.0 | 20.0 | 23.0 | 34.0 | 43 |
| consumables | 1.0 | 4.0 | 5.0 | 7.0 | 8 |
| crates | 0.0 | 0.0 | 0.0 | 2.0 | 2 |
| obstacles | 0.0 | 1.0 | 1.0 | 2.0 | 3 |

## Severe-state capture counts

- boss: 1169
- charger: 8878
- corner: 17
- dense_projectiles: 803
- near_wall: 26

Capacities remain provisional until complete runs cover every wave band,
including representative late-projectile and wave-20 boss states.
