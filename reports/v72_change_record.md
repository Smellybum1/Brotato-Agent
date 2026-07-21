# v72 change and deployment record

- **Date:** 2026-07-21 (Australia/Brisbane), implemented after the v71 gate became impossible at 11W/3L.
- **Version:** `0.1.72-gun-wp1` / `teacher_v1-0.1.72-gun-wp1`.
- **Fresh gate start:** 2026-07-21 04:46 Australia/Brisbane.
- **First run:** `run_1784573193_53233`.

## Trigger and diagnosis

- v71 completed 14 runs at 11W/3L. The three telemetry-complete defeats were `run_1784557174_49938` (wave 16), `run_1784559240_48749` (wave 16), and `run_1784571810_55421` (wave 10). There was no APPCRASH, orchestration, combine, lock, timeout, hang, or illegal-action failure.
- The two repeated late defeats were offense-starved: reconstructed ranged damage + percent damage + attack speed after shop wave 15 was `58` and `-3`, versus the late target of `120`.
- v70/v71's defense-saturation rule required max HP 65+, armor 10+, and sustain 12+ simultaneously before suppressing any pure defense. It therefore never activated in either late loss. The first loss entered wave 16 with 72 HP and had bought +39 HP and 32 sustain, but its 5 armor kept further HP/regeneration attractive despite adequate practical durability.
- The second late loss had 30 sustain but only 46 observed max HP and 2 armor. A layer-local rule can stop further regeneration while preserving needed HP and armor offers.
- The third loss was a separate early high-density hit-chain outlier: offense proxy `77` after shop wave 9, 43 observed max HP, two Gentle Aliens, a wave-10 enemy peak of 50, and repeated 5-8 damage hits. Because the runbook permits exactly one repair, v72 does not also change movement or density-item policy.

## The one gameplay change: layer-local defense saturation

v72 retains the existing wave-15+, offense-below-120 activation, but replaces the all-three-layers conjunction with independent marginal caps:

- max HP offers are suppressed once max HP is at least 65;
- armor offers are suppressed once armor is at least 10;
- regeneration offers are suppressed once regeneration + lifesteal is at least 12;
- dodge, Jelly Shield, and Wandering Bot are suppressed only when any two defensive layers are adequate;
- lifesteal remains positively weighted because it is hybrid sustain for rapid-fire guns;
- a weak defensive layer retains its prior positive weight.

This is one scoring-dimension repair shared by shops, level-ups, and crates through `_late_shop_pivot_bonus`. Movement, weapons, combines, locks, item vetoes, orchestration, and gate criteria are unchanged.

## Verification and deployment

- Targeted policy and monitor tests: **42 passed**.
- Full suite with an isolated workspace temp root: **51 passed**.
- Workshop zip: `C:\Games\Steam\steamapps\workshop\content\1942280\3737864106\Tom-BrotatoAgent.zip`.
- Installed copy: `C:\Games\Steam\steamapps\common\Brotato\mods\Tom-BrotatoAgent.zip`.
- Both copies: 306672 bytes, SHA-256 `B4961DC6C68EE90DEEC7B6777EF7237B568DDFBC1BC2C6F47BF0964C18BEFBE8`.
- Zip inspection confirmed manifest `0.1.72`, controller/telemetry v72 identifiers, all three unchanged adequacy thresholds, and the layer-local scoring paths.
- Live-monitor safety coverage includes v72 in all six active version gates while leaving the historical zero-combine and final-shop-combine tuples unchanged.

## Acceptance and falsification

- Fresh 20-run gate requires at least 18 wins and at most two losses.
- Most runs should reach offense proxy about 70 by wave 12 and 120 by wave 18.
- Below the late offense floor, an individually adequate HP, armor, or sustain layer should stop receiving further pure investment while deficient layers remain buyable and rerolls continue toward DPS.
- If late losses remain below the offense floor despite layer-local activation, inspect reroll reach and effective-DPS valuation. If losses meet the floor yet die to density, the next candidate remains movement/healing-consumable behavior or density-risk policy, not another defense-weight change.
