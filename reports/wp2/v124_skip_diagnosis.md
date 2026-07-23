# v124 skip diagnosis -- the real blocker of mid-game offense conversion

Follow-up to the marginal-DPS replay. The 6.0 `OFFENSE_IMPACT_MIN_ITEM_GAIN` gate was assumed to block mid-game offense buys, but 64% of skipped positive-gain offense offers in defeat runs already cleared it. This classifies the **actual** blocking condition from recorded decision evidence.

well_rounded `min_buy_score` = **5.0**, `gold_reserve` = 40.0. Set: **118** skipped positive-gain offense offers (defeat, w9-15); 158 in victory (control).

## Classification histogram

| bucket | defeat | victory (control) |
|---|---|---|
| outscored | 41 (35%) | 66 (42%) |
| loop_exit | 36 (30%) | 34 (22%) |
| gold_blocked | 24 (20%) | 32 (20%) |
| other | 17 (14%) | 26 (16%) |

### Root-cause breakdown (why the mandatory-offense path didn't fire)

| root cause | defeat | victory |
|---|---|---|
| deficient_but_outranked_this_board | 39 (33%) | 53 (34%) |
| deficient_but_rerolled_for_more_impact | 35 (30%) | 23 (15%) |
| unaffordable | 24 (20%) | 32 (20%) |
| deficient_but_board_did_shop_sell | 13 (11%) | 20 (13%) |
| deficient_but_board_did_shop_combine | 2 (2%) | 0 (0%) |
| deficient_but_board_did_shop_unlock | 2 (2%) | 0 (0%) |
| offense_adequate_no_mandatory_path | 2 (2%) | 25 (16%) |
| deficient_but_shop_exited | 1 (1%) | 2 (1%) |
| deficient_but_other | 0 (0%) | 3 (2%) |

- defeat: offense_deficient at skip = **112/118**; band_gate active = 16/118; clears 6.0 = 75/118.
- victory: offense_deficient = 128/158; band_gate active = 10/158.

## Dominant blocker

Raw plurality bucket: **outscored** -- 41/118 (35%).

**Interpretation.** The 6.0 gate is NOT the blocker: band_gate is active in only 16/118 skips (it is structurally off below wave 13, where most skips occur), and where active the item cleared it. 'outscored' is the raw plurality but largely reflects the offense-first single-best pick buying a higher-ranked offense item or a weapon on the same board (offense IS converted, just a different item): 15 lost to another offense item, 26 to a weapon/other item.

**Actionable blocker.** reroll-for-impact pressure -- of the items truly LEFT on the board, 35 were rerolled away and only 1 left by shop-exit. While offense-deficient the reroll worth is boosted by +8 (shop_strategy.gd:1514-1518), so the shop rerolls past affordable gate-clearing offense items instead of banking the buy. Second: gold_blocked (24, median 60 gold short).

Source: `shop_strategy.gd:1514-1518 (+8 offense-deficient reroll boost) and :1525-1527 (reroll when best_here < worth)`

Reference (distinct items): of 62 distinct positive-gain offense items skipped in defeat runs, **49 were never bought that shop** (true misses), 13 were bought on a later board of the same shop.

## 5 walked-through examples (defeat)

### `item_hedgehog` -- w9 run ...23_17546 [loop_exit]
- offense keys ['stat_ranged_damage'], direct_gain=1.0 (clears 6.0: False); price=62, gold_before=498 -> affordable=True
- offense_total=27.1 vs target=116.0 -> deficient=True; weapon_dps=406.7 vs dps_target=645 -> band_gate=False
- board action taken: **shop_reroll**; root cause: **deficient_but_rerolled_for_more_impact**
- shop decision sequence: shop_reroll g=498 | shop_buy(weapon_revolver_1@44) g=489 | shop_buy(item_recycling_machine@71) g=445 | shop_buy(item_padding@89) g=374 | shop_combine g=285 | shop_reroll g=285 | shop_reroll g=273 | shop_buy(weapon_smg_2@78) g=258 | shop_buy(item_piggy_bank@80) g=180 | shop_buy(item_terrified_onion@35) g=100 | shop_go g=65

### `item_ball_and_chain` -- w10 run ...23_17546 [other]
- offense keys ['stat_percent_damage'], direct_gain=15.0 (clears 6.0: True); price=152, gold_before=379 -> affordable=True
- offense_total=35.7 vs target=215.0 -> deficient=True; weapon_dps=534.9 vs dps_target=765 -> band_gate=False
- board action taken: **shop_sell**; root cause: **deficient_but_board_did_shop_sell**
- shop decision sequence: shop_sell g=379 | shop_buy(weapon_laser_gun_2@68) g=401 | shop_buy(item_poisonous_tonic@161) g=333 | shop_combine g=172 | shop_reroll g=172 | shop_buy(weapon_double_barrel_shotgun_1@47) g=161 | shop_buy(item_blindfold@95) g=114 | shop_go g=19

### `item_poisonous_tonic` -- w10 run ...23_17546 [outscored]
- offense keys ['stat_attack_speed', 'stat_crit_chance'], direct_gain=10.0 (clears 6.0: True); price=161, gold_before=401 -> affordable=True
- offense_total=32.5 vs target=215.0 -> deficient=True; weapon_dps=487.0 vs dps_target=765 -> band_gate=False
- board action taken: **shop_buy**; root cause: **deficient_but_outranked_this_board**
- shop decision sequence: shop_sell g=379 | shop_buy(weapon_laser_gun_2@68) g=401 | shop_buy(item_poisonous_tonic@161) g=333 | shop_combine g=172 | shop_reroll g=172 | shop_buy(weapon_double_barrel_shotgun_1@47) g=161 | shop_buy(item_blindfold@95) g=114 | shop_go g=19

### `item_glass_cannon` -- w12 run ...63_90333 [gold_blocked]
- offense keys ['stat_percent_damage'], direct_gain=25.0 (clears 6.0: True); price=177, gold_before=147 -> affordable=False
- offense_total=107.8 vs target=102.0 -> deficient=False; weapon_dps=1616.9 vs dps_target=1150 -> band_gate=False
- board action taken: **shop_reroll**; root cause: **unaffordable**
- shop decision sequence: shop_reroll g=520 | shop_reroll g=507 | shop_reroll g=490 | shop_buy(weapon_smg_1@56) g=469 | shop_buy(item_poisonous_tonic@188) g=413 | shop_buy(item_dangerous_bunny@78) g=225 | shop_reroll g=147 | shop_sell g=147 | shop_buy(weapon_smg_3@174) g=180 | shop_combine g=6 | shop_go g=6

### `item_retromations_hoodie` -- w9 run ...23_17546 [loop_exit]
- offense keys ['stat_attack_speed'], direct_gain=2.0 (clears 6.0: False); price=207, gold_before=498 -> affordable=True
- offense_total=27.1 vs target=116.0 -> deficient=True; weapon_dps=406.7 vs dps_target=645 -> band_gate=False
- board action taken: **shop_reroll**; root cause: **deficient_but_rerolled_for_more_impact**
- shop decision sequence: shop_reroll g=498 | shop_buy(weapon_revolver_1@44) g=489 | shop_buy(item_recycling_machine@71) g=445 | shop_buy(item_padding@89) g=374 | shop_combine g=285 | shop_reroll g=285 | shop_reroll g=273 | shop_buy(weapon_smg_2@78) g=258 | shop_buy(item_piggy_bank@80) g=180 | shop_buy(item_terrified_onion@35) g=100 | shop_go g=65
