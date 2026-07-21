# v73 post-pass comparison analysis

Updated: 2026-07-21 12:15 Australia/Brisbane

## Outcome

The user-approved eight-run v73 comparison stopped after three completed runs at **1W/2L**. The second loss made the required **7W/8** result mathematically impossible, so the exact v73 watchdog tasks were disabled and stopped and the scoped v73 process tree was cleared. Brotato had already been stopped by the supervisor. No v74 campaign, WP2 work, or commit was started.

All three summaries are telemetry-complete. There were no telemetry errors, hangs, illegal actions, shop/combine/lock safety violations, or post-start Brotato APPCRASH events.

| Run | Result | Last wave | Mean per-wave p90 density | Late-wave p90 | Mean wave max | Peak | Offense added at wave 18 |
|---|---|---:|---:|---:|---:|---:|---:|
| `run_1784596517_3802` | Victory | 20 | 31.45 | 54.33 | 39.45 | 102 | 103 |
| `run_1784597678_2726` | Defeat | 17 | 20.71 | 42.67 | 26.18 | 74 | 65 at terminal build |
| `run_1784598630_61503` | Defeat | 19 | 19.37 | 35.20 | 24.53 | 74 | 67 |

The only v73 victory's primary density metric was **31.45**, far above the v72 victory baseline of **15.26**. With two losses already recorded, neither the win-rate requirement nor the density-improvement requirement could be recovered by the remaining five planned runs.

## Loss analysis

### Run 2: wave 17

- General offense added was only **65**, versus the late target of 120: ranged damage +9, percent damage +40, and attack speed +16.
- The build added +45 max HP, +16 regeneration, +3 lifesteal, and +4 armor, while speed ended at -5. This is the same defense-heavy/offense-light shape v73 was intended to avoid.
- Wave 17 reached p90 density 51 and a peak of 74. The terminal chain dealt **17, 13, and 16 damage in 0.87 seconds**, taking observed HP from 46 before the chain to 1.
- The Minigun III workflow behaved exactly as designed: it was offered unaffordable on wave 15, locked and banked, then the agent sold a strictly lower-tier Laser Gun II and bought the locked Minigun III on wave 16. That validated the lock/save/buy mechanism, but one shop before the terminal wave was too late to repair the broader offensive deficit.

### Run 3: wave 19

- This run was stable through wave 18, but general offense added was only **67**: ranged damage +18, percent damage +9, and attack speed +40. It had no telemetry-derived piercing, bounce, explosion, or burning-spread addition.
- It instead added +22 max HP, +22 regeneration, +8 lifesteal, +3 armor, and +18 speed. Defense and mobility prolonged the run but did not keep pace with the final density spike.
- Wave 19 jumped to p90 density 59 and a peak of 74, from wave-18 p90 25. The terminal chain dealt **20, 18, and 18 damage in 1.24 seconds**, leaving observed HP at 2 immediately before defeat.
- No Minigun or Chain Gun was offered in this run.

These two losses support the user's visual diagnosis: the immediate cause was a late crowd-density surge, while the build-level cause was insufficient general DPS rather than a lack of survivability.

## Victory and rare-gun findings

- The victory survived an extreme wave-16 peak of 102 and recovered from 7 HP. It was not a low-density win: ten waves had p90 density at or above 30.
- Its offense rose from 45 after wave 15 to 103 after wave 18, with +23 ranged damage, +34 percent damage, +52 attack speed, and +2 piercing by the terminal build. This was materially stronger than either loss but still below the nominal late target.
- Minigun III was offered affordable and bought in the final shop before wave 20. It therefore helped only the finale and cannot explain the earlier density profile.
- Across the three runs, Minigun appeared in two runs and was bought in both; Chain Gun was never offered. The explicit rare-gun workflow is operational, but the sample does not show that rare-gun pursuit improved ordinary-wave density or win rate.

## Decision

v73 should not replace certified v72 on this evidence. The defense-saturation veto and rare-gun mechanics worked safely, but they did not reliably lift general offense toward 120, and all three runs had substantially higher sustained density than the v72 victory baseline. Any v74 proposal should focus on earlier, broader offensive acquisition rather than relying on late rare weapons. It requires explicit user direction before implementation or another evaluation.
