# v70 change and deployment record

- **Date:** 2026-07-20 (Australia/Brisbane), implemented after the v69 gate became impossible at 6W/3L.
- **Version:** `0.1.70-gun-wp1` / `teacher_v1-0.1.70-gun-wp1`.
- **Fresh gate start:** 2026-07-20 23:29 Australia/Brisbane.
- **First run:** `run_1784554154_72551`.

## Trigger and diagnosis

- v69's third loss was `run_1784552522_3141`, a telemetry-complete defeat on wave 19 with no safety, orchestration, combine, lock, or APPCRASH error.
- The run entered the late game with an offense proxy far below target. Reconstructed item/level-up effects after shop wave 18 were ranged damage `13`, percent damage `-11`, and attack speed `41`: offense proxy `43` versus the v69 target of `120`.
- Defense was already adequate: roughly `+30` max HP, `14` armor, `3` dodge, and `25` regeneration from acquired effects. The run started wave 19 at 65 HP, survived repeated hits and healing, but enemy density climbed to 111 and it died after taking 321 total damage.
- Late spending still favored pure defense/control: Jelly Shield, Wandering Bot, Mushroom, Blindfold, Helmet, and Glasses were bought across shops 17-18. The wave-18 level-up also chose regeneration over speed because no direct damage option was offered.
- This matches the operator's repeated visual observation: adequate defense was masking a kill-rate deficit. It does not satisfy v69's movement falsification clause because the losing run did not meet the offense floor.

## The one gameplay change: adequate-defense offense pivot

v70 keeps the v69 offense floor and adds one conditional defense-saturation mode shared by shop, level-up, and crate scoring:

- Defense is adequate when live max HP is at least `65`, armor at least `10`, and regeneration plus lifesteal at least `12`.
- The mode activates only on wave 15+ while offense remains below `120`.
- While active, pure additional max HP, armor, dodge, and regeneration receive strong negative marginal weights, as do Jelly Shield and Wandering Bot control fillers. This makes those offers fall below the buy threshold so the existing shop policy retains budget and rerolls for offense.
- Offensive and hybrid stats remain available: ranged damage, percent damage, attack speed, crit, piercing/bounce, and lifesteal keep their v69 valuation.
- The same pivot is now included in crate scoring, matching the intended shared reward-surface policy.

Everything else is unchanged: movement, the v67 survival override, v68 watchdog settings, combines, locks, item vetoes, weapon pool, telemetry, and gate criteria.

## Verification and deployment

- Targeted policy and monitor tests: **41 passed**.
- Full suite: **48 passed**.
- Deployed workshop zip: `C:\Games\Steam\steamapps\workshop\content\1942280\3737864106\Tom-BrotatoAgent.zip`.
- Installed game copy: `C:\Games\Steam\steamapps\common\Brotato\mods\Tom-BrotatoAgent.zip`.
- Both copies: 306539 bytes, SHA-256 `D9096B019B3B78F05FCE3EB34ADD539E5E746DA811DD49624C04951A30500B39`.
- Zip inspection confirmed manifest `0.1.70`, controller/telemetry policy `teacher_v1-0.1.70-gun-wp1`, all three defense-adequacy thresholds, and the defense-saturation scoring path.
- Live-monitor version coverage was extended to v70 without changing the historical zero-combine or final-shop-combine gates.

## Acceptance and falsification

- Fresh 20-run gate requires at least 18 wins and at most two losses.
- Most runs should reach offense proxy about 70 by wave 12 and 120 by wave 18; wave 17-19 enemy peaks should usually remain below about 50.
- When the defense-adequacy condition is met while offense is below target, pure defense/control purchases should stop and reroll activity should continue until offense or weapon upgrades appear.
- If losses still remain below the offense floor despite saturation, inspect reroll reach and effective-DPS valuation. If losses meet the floor yet die to late density, revisit the queued v67 movement/healing-consumable candidate.
