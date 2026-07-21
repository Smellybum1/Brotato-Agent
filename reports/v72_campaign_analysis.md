# v72 WP1 campaign analysis

Date: 2026-07-21 Australia/Brisbane

## Certified result

- Version: `0.1.72-gun-wp1` / `teacher_v1-0.1.72-gun-wp1`.
- Completed runs: 20.
- Result: 18 victories, 2 defeats (90.0%); WP1 acceptance met exactly.
- Reliability: 0 telemetry errors, 0 hangs, 0 APPCRASH events, and 20 complete terminal summaries.
- Authoritative outputs: `reports/batch_overnight_20_v72.md`, `reports/batch_overnight_20_v72.csv`, and `reports/gate_state_v72.json`.
- An automatically started run 21 was outside the completed 20-run campaign and is excluded. The v72 tasks were disabled and stopped, and the scoped watchdog/Brotato process tree was closed.

## Density measurement

The primary strength metric is the mean of each wave's p90 observed enemy count. It reflects sustained pressure without letting one transient spawn dominate the whole run. The secondary metric is the mean per-wave maximum; absolute peaks and 30+ density waves remain diagnostic signals.

Across the 18 victories, the primary mean was 15.26. The five lowest-density victories averaged 12.5, versus 16.3 for the other 13 victories.

| Build signal | Lowest-density 5 wins | Other 13 wins | Difference |
|---|---:|---:|---:|
| Mean per-wave p90 density | 12.5 | 16.3 | -23% |
| Late-wave p90 density | 16.7 | 26.5 | -37% |
| Mean absolute peak | 31.8 | 59.7 | -47% |
| Telemetry-derived offense added | 185.0 | 110.4 | +68% |
| Max HP added | 29.4 | 46.5 | -37% |
| Sustain added | 35.0 | 37.2 | broadly equal |
| Minigun runs | 2/5 | 2/13 | more frequent |
| Shotgun purchases per run | 7.6 | 5.0 | more weapon laddering |
| Bandana purchases | 3/5 | 2/13 | more piercing |

`Offense added` is a decision-telemetry proxy: positive ranged damage, percent damage, and attack-speed contributions selected or purchased. It is not the exact live stat and excludes baseline/set adjustments.

## The two defeats

1. `run_1784573193_53233`, wave 9: an early, underbuilt collapse. The run had only about 39 offense added, 40 max HP, 2 armor, negative speed, no piercing/bounce, and a wave-9 enemy peak of 34. It died to a hit chain before the late defense-saturation policy could matter.
2. `run_1784593331_58683`, wave 16: a clear general-DPS failure. Density jumped to p90 39 / max 56, compared with the victorious wave-16 averages of p90 18.2 / max 25.2. The build held 79 HP until density exceeded 43, then took 16/20/18/20 damage in under two seconds. It had about 90 offense added against the 120 target, while buying +49 HP and substantial sustain. The wave-15 shop spent on Silver Bullet, Shmoop, Injection, and White Flag; only Injection improved general wave clear.

The user-observed diagnosis is supported: the second defeat had enough practical durability to tank for a long time, but not enough clearing power to prevent the arena from saturating.

## Rare weapons

- Minigun appeared in seven v72 runs. Four were purchased and all four runs won. Two offers were unaffordable; one offer was locked and bought in the next shop.
- Chain Gun did not appear in v72. Historical telemetry contains four offers, all unaffordable, and zero purchases. Its old generic premium-lock reach condition was too conservative for such a rare, expensive gun.

## v73 hypothesis

Preserve v72's defense thresholds and sustain behavior, but once a defensive layer is adequate and general offense remains below target:

- hard-reject defense-only investment in already adequate layers;
- value piercing, explosions, spread, and death-projectiles as crowd-clear DPS;
- defer boss-only Silver Bullet spending until the final shop;
- explicitly prioritize Minigun III+ and Chain Gun IV, locking once to save and replacing only a strictly lower-tier gun when necessary.

This is a post-pass improvement experiment, not a reopened WP1 repair. It will be compared over eight runs, requiring at least 7/8 wins, no infrastructure errors or early deaths, and a victory-density mean below the v72 baseline of 15.26.
