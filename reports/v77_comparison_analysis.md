# v77 shortened-comparison analysis

Updated: 2026-07-21 18:20 Australia/Brisbane

## Outcome and scoped stop

- The eight-run comparison stopped after seven completed runs at **5W/2L**.
  The second defeat made the required **7W/8** result impossible.
- The exact tasks `BrotatoAgent-LiveMonitor-v77` and
  `BrotatoAgent-Supervisor-v77` are disabled and stopped. Their positively
  identified workspace process trees are gone, and Brotato is stopped.
- All seven summaries are telemetry-complete. There were no telemetry errors,
  hangs, illegal actions, shop/combine/lock safety failures, watchdog failures,
  or post-start Brotato APPCRASH events.
- No v78 campaign, WP2 work, or commit was started.

## Gate and density result

| Run | Result | Last wave | Mean per-wave p90 density | Late-wave p90 | Mean wave max | Peak | Final offense | Estimated DPS | Tier sum | Final defense | Sustain |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `run_1784613701_78127` | Victory | 20 | 16.66 | 25.03 | 21.10 | 66 | 174.98 | 2,625 | 21 | 215.00 | 10 |
| `run_1784614873_80506` | Victory | 20 | 15.87 | 22.18 | 21.30 | 43 | 374.67 | 5,620 | 17 | 235.00 | 8 |
| `run_1784616012_1096` | Victory | 20 | 19.38 | 31.20 | 24.75 | 52 | 123.81 | 1,857 | 18 | 227.50 | 9 |
| `run_1784617211_51655` | Defeat | 19 | 23.72 | 42.62 | 29.74 | 66 | 133.03 | 1,995 | 18 | 404.17 | 27 |
| `run_1784618282_62472` | Victory | 20 | **14.36** | **19.22** | **19.45** | **32** | 367.25 | 5,509 | 21 | **166.67** | 8 |
| `run_1784619415_60958` | Victory | 20 | 18.91 | 30.80 | 24.30 | 57 | 173.73 | 2,606 | 18 | 336.67 | 18 |
| `run_1784620606_1677` | Defeat | 20 | 15.50 | 22.27 | 20.10 | 40 | 226.21 | 3,393 | 18 | 191.67 | 8 |

The five victories averaged **17.04 mean per-wave p90 density**, above the v72
victory baseline of **15.26**. Only `run_1784618282_62472` beat the baseline.
V77 therefore failed both its win-rate requirement and its density-improvement
requirement.

## Strongest-run finding

`run_1784618282_62472` is the clearest low-density build in the comparison. It
finished with 5,509 estimated DPS and 367 offense while defense was only 167
and sustain was 8. Waves 11-13 peaked at 16-18 enemies, and waves 14-19 caused
only 3-9 damage per wave. This directly supports the user's observation that a
high-offense build can perform better with defense well below the nominal 300
target.

The Minigun victory, `run_1784614873_80506`, was the next strongest density
result. It reached 5,620 estimated DPS and 375 offense with 235 defense. These
two runs support using offense margin and observed clear rate, rather than a
large fixed defense target, once a modest survival floor is present.

## Defeat analysis

### Run 4: wave-19 crowd overwhelm

- The build entered late waves with the comparison's most defensive shape:
  defense 404 and sustain 27, versus final offense 133 and 1,995 estimated DPS.
- Sustain was already 25 on wave 9 and 27 on wave 10. Wave 16 peaked at 66
  enemies; wave 19 reached p90 density 50 and a peak of 64 with no projectile
  pressure.
- The terminal chain dealt 22 and 22 damage in 0.80 seconds, taking observed HP
  from 23 to 6 immediately before defeat.
- This was the user's original failure mode: durability prolonged the run but
  could not compensate for inadequate crowd clearing.

### Run 7: wave-20 movement failure

- The build recovered late through Minigun III and finished with 3,393
  estimated DPS, 226 offense, defense 192, and sustain 8. Its mean per-wave p90
  density was 15.50, close to the v72 baseline.
- Wave 20 peaked at only 23 enemies but 25 projectiles. The terminal chain dealt
  20 and 20 damage in 0.44 seconds, taking observed HP from 32 to 12 before
  defeat.
- Commanded movement had only 4.18% net displacement relative to path length.
  Direct reversals fell to 5, but the extremely low net movement shows that the
  agent still looped or cancelled its escape instead of translating away.
- This loss was primarily a boss-wave movement failure, not a general DPS or
  sustain failure.

## Weapon-aware offense metric

The weapon-aware metric is materially better than v76's stat-only proxy. It
recognized tier upgrades, Laser Gun III/IV, Shredder III, and Minigun III, and
correctly distinguished the 5,509-DPS low-density victory from weak builds with
similar raw stats.

It is not yet a complete adequacy rule:

- Run 4 finished above the nominal 120 offense target but still reached 64
  enemies and died. The target/model can overrate a composition that lacks
  enough practical crowd clearing.
- Run 7 reached 226 offense and low ordinary-wave density but died because the
  metric cannot represent movement survival on the boss wave.
- The most useful strength signal is therefore weapon-aware offense together
  with observed per-wave density, hit rate, and movement margin—not one score
  alone.

## Sustain-cap behavior

The hard cap prevented new direct sustain additions after activation, but it
activates too late to prevent the failure mode:

- Run 4 had sustain 25 by wave 9 and 27 by wave 10.
- Run 5 bought Blood Leech in the wave-9 shop, moving from sustain 7 to 11
  before the cap applied.
- Run 6 had sustain 18 by wave 9 and kept it for the remainder of the run.
- Indirect sustain such as Garden remained eligible after the direct-stat cap.

The repair needs to begin before the shop that precedes wave 10, apply to mixed
items as well as pure lifesteal/regeneration, and classify indirect healing
sources such as Garden.

## Affordable-offense and utility behavior

Three concrete misses survived the v76/v77 rules:

- Run 3 was at 47.95/70 offense when affordable Sunglasses appeared. It bought
  Cyberball and Alien Tongue, then rerolled Sunglasses away.
- Run 6 was materially below target when affordable Sunglasses and Small
  Magazine appeared together on wave 7. It rerolled both after buying Bat; by
  wave 8 it had defense 303, sustain 14, and offense only 29/56.
- Run 7 was at 119.81/120 with 523 materials on wave 16. It rerolled affordable
  Defective Steroids, Cyclops Worm, Missile, Bandana, and Blindfold, then left
  with 415 materials. Wave 17 subsequently dropped to 29 HP.

Defensive and utility locks also remained common before a secure offense
margin: Butterfly, Helmet, Cake, Plant, Metal Plate, Doc Moth, Tardigrade,
Tractor, and economic/collection items all appeared in locked trajectories.
The follow-up should treat affordable net-positive ranged offense as mandatory
until a margin above target is reached, not merely until the score is equal to
the target within rounding tolerance.

## Rare-gun behavior

- Minigun III appeared in three runs. It was unaffordable in run 1's final shop,
  bought in run 2 on waves 8 and 11, and bought in run 7 on waves 17 and 18.
- The Minigun runs finished 1W/1L: it strongly helped run 2, but could not save
  run 7 from wave-20 movement failure.
- Chain Gun never appeared in the seven completed runs.
- Rare-gun buy/sell/replace behavior operated safely, but rare weapons are an
  accelerator rather than a substitute for ordinary offense acquisition or
  correct movement.

## Wave-20 movement evidence

| Run | Result | Samples | Direct reversals | Net/path movement | Min HP | Max enemies | Max projectiles |
|---|---|---:|---:|---:|---:|---:|---:|
| `run_1784613701_78127` | Victory | 130 | 30 | 6.13% | 34 | 20 | 30 |
| `run_1784614873_80506` | Victory | 83 | 22 | 8.73% | 14 | 16 | 25 |
| `run_1784616012_1096` | Victory | 180 | 38 | 3.72% | 19 | 21 | 29 |
| `run_1784618282_62472` | Victory | 58 | 13 | 10.02% | 28 | 22 | 30 |
| `run_1784619415_60958` | Victory | 167 | 49 | 3.22% | 37 | 21 | 33 |
| `run_1784620606_1677` | Defeat | 58 | 5 | 4.18% | 12 | 23 | 25 |

All six wave-20 runs had net movement at or below 10.02% of commanded path
length. The v77 anti-oscillation change did not repair the observed stuck-in-
place behavior. Direct reversals alone are insufficient as a diagnostic because
run 7 reduced direct reversals while still cancelling almost all translation.

## Decision

V77 should not replace certified v72 on this evidence. Its weapon-aware metric
is worth retaining, and the strongest run validates a lower-defense,
higher-offense strategy. A future user-authorized version should:

1. start the offense pivot and sustain veto before the shop preceding wave 10;
2. require affordable net-positive offense until a meaningful margin above the
   wave target exists, including mixed items and upgrades;
3. cap indirect sustain and utility locks while offense is deficient;
4. calibrate offense against observed density/clear rate as well as estimated
   DPS; and
5. replace the finale movement selector with an escape controller that measures
   actual translation and commits to a lane until displacement is achieved.

