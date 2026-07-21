# v75 short-comparison analysis

Date: 2026-07-21 Australia/Brisbane

## Disposition

- The comparison was stopped on its first run after a hard shop-policy guarantee failed.
- The sole v75 run completed as a wave-19 defeat: 0W/1L. Its terminal summary reports 19 waves completed, 13 recoveries, and zero errors, hangs, or illegal actions.
- v72 remains the certified WP1 result at 18W/2L. WP2 did not start.

## What worked

- The deployed v75 identifiers and telemetry were correct.
- The explicit offense-first path activated in live play. Confirmed item purchases were Small Magazine and Lens at wave 10, Reinforced Steel at wave 11, Medal at wave 13, and Vigilante Ring at wave 14.
- An offense-first level-up also selected attack speed at wave 15.
- No non-rare utility lock displaced an affordable direct-offense item. The only post-wave-10 lock was an SMG weapon lock at wave 12.
- No Minigun or Chain Gun offer appeared.

## Actionable failure

- The event-derived lower-bound offense proxy ended shops at 62 on wave 10, 76 on wave 11, 82 on wave 12, 85 on wave 13, 88 on wave 14, and 93 on wave 15—materially below the late target of 120.
- Despite already-heavy sustain and the below-target offense proxy, wave 15 bought Blood Leech, Butterfly, and Mushroom with normal positive scores. Wave 16 then bought Fresh Meat.
- Those choices contain only HP regeneration/lifesteal defense and should have received the v75 hard veto. The deployed helper was present, so this is a live integration/decision-context failure rather than a missing artifact.
- The exact reason requires a focused follow-up investigation of the live `build.stats`/profile values passed into item scoring; no v76 repair is authorized.

## Combat evidence

- Per-wave enemy-density p90 remained low through wave 15: 23 on wave 10, 12 on wave 11, 16 on wave 12, 17 on waves 13-14, and 24 on wave 15.
- It then rose sharply to 44 on wave 16, 31.4 on wave 17, 24.7 on wave 18, and 48 during the partial wave 19.
- Mean p90 across waves 1-18 was 16.16; the wave-10-to-18 mean was 23.23. Wave 19 reached p90 48 and maximum 62 before the defeat.
- Late damage included consecutive 20/20/20 hits on wave 16 and 24/24 then 22/19/27/24 chains later. There were 13 recovery attempts before shutdown.

## Shutdown and safety

- Disabled and stopped only `BrotatoAgent-LiveMonitor-v75` and `BrotatoAgent-Supervisor-v75`.
- Stopped only their positively identified `C:\Codex\Brotato Agent` process trees and the positively identified `C:\Games\Steam\steamapps\common\Brotato\Brotato.exe`.
- No unrelated, Slay the Spire 2, Claude, generic console, or unrecognized Python process was touched.
- The terminal summary was written during shutdown and confirms a wave-19 defeat rather than an aborted run.
- No restart, v76, WP2 work, or commit was performed.
