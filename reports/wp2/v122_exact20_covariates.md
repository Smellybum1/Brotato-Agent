# WP2 v122 exact-20 covariates

- Corner threshold: 280.0 units (two adjacent walls).
- Collection items classified data-driven from offer effects/tags (`pickup` tag / `pickup_range` effect / `instant_gold_attracting`).

## Collection-assist items observed in offers

| item_id | reasons |
|---|---|
| item_alien_tongue | effect:pickup_range, tag:pickup |
| item_baby_elephant | tag:pickup |
| item_baby_gecko | effect:instant_gold_attracting, tag:pickup |
| item_cute_monkey | tag:pickup |
| item_evil_hat | tag:pickup |
| item_little_frog | effect:pickup_range, tag:pickup |
| item_lootworm | tag:pickup |
| item_metal_detector | tag:pickup |

## Per-run totals and occupancy

| # | run_id | result | wv | captures | dmg_evt | dmg_amt | corner% | wall% | coll_buys |
|--:|---|---|--:|--:|--:|--:|--:|--:|--:|
| 1 | run_1784785556_51395 | victory | 20 | 21061 | 13 | 105 | 1.0 | 28.2 | 1 |
| 2 | run_1784786723_17546 | defeat | 17 | 17341 | 19 | 222 | 3.7 | 26.7 | 2 |
| 3 | run_1784787688_32406 | victory | 20 | 21795 | 15 | 166 | 1.2 | 24.2 | 6 |
| 4 | run_1784788917_7315 | defeat | 20 | 21013 | 22 | 237 | 2.9 | 33.5 | 3 |
| 5 | run_1784790063_90333 | defeat | 20 | 20835 | 4 | 55 | 1.0 | 21.8 | 3 |
| 6 | run_1784791214_74323 | defeat | 17 | 17478 | 3 | 62 | 0.7 | 20.3 | 2 |
| 7 | run_1784792179_82981 | defeat | 10 | 8638 | 9 | 50 | 4.2 | 19.7 | 1 |
| 8 | run_1784792652_7723 | victory | 20 | 21852 | 5 | 112 | 1.0 | 26.1 | 2 |
| 9 | run_1784793833_32034 | defeat | 17 | 17416 | 15 | 116 | 3.9 | 28.7 | 2 |
| 10 | run_1784794784_69267 | victory | 20 | 20860 | 2 | 22 | 0.9 | 17.7 | 3 |
| 11 | run_1784795927_93597 | victory | 20 | 21059 | 15 | 191 | 3.2 | 35.7 | 4 |
| 12 | run_1784797082_83949 | victory | 20 | 21616 | 11 | 75 | 0.7 | 22.2 | 2 |
| 13 | run_1784798249_41022 | victory | 20 | 21111 | 6 | 56 | 0.7 | 21.6 | 3 |
| 14 | run_1784799404_80018 | defeat | 20 | 20926 | 7 | 135 | 0.9 | 26.6 | 5 |
| 15 | run_1784800561_47448 | victory | 20 | 21313 | 2 | 27 | 1.5 | 28.2 | 1 |
| 16 | run_1784801716_88465 | defeat | 10 | 8550 | 8 | 52 | 4.0 | 24.4 | 0 |
| 17 | run_1784802191_76892 | defeat | 20 | 20568 | 12 | 183 | 2.9 | 30.5 | 2 |
| 18 | run_1784803299_7195 | victory | 20 | 21060 | 4 | 40 | 1.0 | 24.5 | 3 |
| 19 | run_1784804435_39794 | victory | 20 | 21730 | 8 | 95 | 1.0 | 23.9 | 6 |
| 20 | run_1784805636_10804 | victory | 20 | 21845 | 7 | 113 | 3.2 | 30.9 | 0 |

## Collection-assist purchases (item @ wave) per run

- run_1784785556_51395: item_lootworm@w10
- run_1784786723_17546: item_baby_gecko@w5, item_metal_detector@w8
- run_1784787688_32406: item_lootworm@w7, item_metal_detector@w8, item_baby_gecko@w10, item_metal_detector@w11, item_baby_gecko@w12, item_baby_gecko@w18
- run_1784788917_7315: item_lootworm@w11, item_baby_gecko@w11, item_alien_tongue@w11
- run_1784790063_90333: item_metal_detector@w11, item_baby_gecko@w16, item_lootworm@w18
- run_1784791214_74323: item_baby_gecko@w8, item_baby_gecko@w14
- run_1784792179_82981: item_alien_tongue@w9
- run_1784792652_7723: item_alien_tongue@w7, item_alien_tongue@w18
- run_1784793833_32034: item_baby_gecko@w5, item_lootworm@w16
- run_1784794784_69267: item_alien_tongue@w5, item_baby_elephant@w11, item_baby_gecko@w12
- run_1784795927_93597: item_baby_gecko@w1, item_baby_elephant@w8, item_baby_gecko@w9, item_lootworm@w14
- run_1784797082_83949: item_lootworm@w6, item_alien_tongue@w13
- run_1784798249_41022: item_metal_detector@w4, item_alien_tongue@w6, item_alien_tongue@w19
- run_1784799404_80018: item_baby_gecko@w4, item_baby_gecko@w5, item_baby_gecko@w10, item_alien_tongue@w10, item_lootworm@w14
- run_1784800561_47448: item_alien_tongue@w13
- run_1784801716_88465: (none)
- run_1784802191_76892: item_baby_elephant@w11, item_alien_tongue@w14
- run_1784803299_7195: item_metal_detector@w9, item_baby_gecko@w17, item_baby_gecko@w18
- run_1784804435_39794: item_alien_tongue@w1, item_baby_gecko@w6, item_lootworm@w7, item_baby_gecko@w11, item_baby_gecko@w17, item_baby_gecko@w17
- run_1784805636_10804: (none)

## Per-wave occupancy (corner% / single-wall%) per run

- run_1784785556_51395: w1:0/4 w2:0/9 w3:0/17 w4:0/10 w5:0/9 w6:0/10 w7:0/14 w8:0/23 w9:0/4 w10:2/37 w11:0/10 w12:0/11 w13:1/28 w14:0/29 w15:2/45 w16:1/20 w17:2/59 w18:4/61 w19:4/73 w20:1/42
- run_1784786723_17546: w1:2/15 w2:0/4 w3:0/11 w4:2/26 w5:1/11 w6:0/6 w7:0/12 w8:0/12 w9:0/15 w10:22/69 w11:6/41 w12:2/22 w13:3/34 w14:0/29 w15:1/36 w16:12/34 w17:3/35
- run_1784787688_32406: w1:0/12 w2:0/8 w3:1/8 w4:0/12 w5:1/7 w6:1/12 w7:0/8 w8:0/19 w9:0/7 w10:12/43 w11:0/31 w12:0/14 w13:0/23 w14:0/25 w15:1/29 w16:1/9 w17:1/44 w18:1/38 w19:2/55 w20:0/34
- run_1784788917_7315: w1:0/8 w2:0/19 w3:0/9 w4:0/16 w5:1/21 w6:0/9 w7:0/18 w8:0/27 w9:0/11 w10:27/76 w11:2/42 w12:5/31 w13:4/50 w14:0/33 w15:0/33 w16:3/30 w17:2/47 w18:2/61 w19:2/47 w20:0/25
- run_1784790063_90333: w1:0/8 w2:0/7 w3:0/13 w4:0/25 w5:0/13 w6:1/12 w7:1/11 w8:0/16 w9:0/2 w10:3/26 w11:0/13 w12:0/16 w13:0/16 w14:0/21 w15:0/37 w16:1/12 w17:4/29 w18:4/55 w19:3/47 w20:0/30
- run_1784791214_74323: w1:0/3 w2:0/12 w3:0/8 w4:2/25 w5:2/13 w6:1/13 w7:0/18 w8:0/10 w9:0/4 w10:0/9 w11:0/12 w12:1/18 w13:0/30 w14:3/36 w15:0/43 w16:0/22 w17:2/45
- run_1784792179_82981: w1:0/10 w2:0/10 w3:0/22 w4:1/9 w5:3/24 w6:0/14 w7:0/16 w8:0/6 w9:0/12 w10:31/64
- run_1784792652_7723: w1:0/5 w2:1/6 w3:0/16 w4:0/6 w5:0/11 w6:0/8 w7:2/25 w8:0/12 w9:0/7 w10:0/22 w11:0/8 w12:0/15 w13:4/17 w14:1/28 w15:0/18 w16:1/32 w17:2/46 w18:3/66 w19:3/77 w20:0/42
- run_1784793833_32034: w1:1/6 w2:0/6 w3:0/10 w4:2/28 w5:2/9 w6:2/15 w7:0/18 w8:0/23 w9:0/15 w10:21/58 w11:0/41 w12:10/46 w13:3/31 w14:3/30 w15:2/37 w16:7/28 w17:4/40
- run_1784794784_69267: w1:0/5 w2:1/12 w3:0/5 w4:0/23 w5:0/17 w6:1/7 w7:1/27 w8:0/19 w9:0/14 w10:6/32 w11:0/9 w12:0/14 w13:0/15 w14:1/23 w15:3/37 w16:0/21 w17:3/8 w18:0/19 w19:0/18 w20:0/7
- run_1784795927_93597: w1:0/13 w2:0/10 w3:0/28 w4:0/13 w5:1/24 w6:1/15 w7:0/16 w8:0/17 w9:0/11 w10:17/55 w11:4/40 w12:17/50 w13:3/47 w14:3/57 w15:1/54 w16:0/15 w17:2/37 w18:3/68 w19:3/51 w20:1/40
- run_1784797082_83949: w1:0/13 w2:0/8 w3:0/11 w4:0/13 w5:1/15 w6:1/10 w7:1/9 w8:0/12 w9:0/4 w10:1/21 w11:0/8 w12:0/19 w13:0/13 w14:1/33 w15:0/21 w16:0/9 w17:1/49 w18:2/52 w19:4/68 w20:1/25
- run_1784798249_41022: w1:0/2 w2:0/12 w3:0/20 w4:0/6 w5:0/9 w6:0/6 w7:0/17 w8:0/20 w9:1/14 w10:3/40 w11:1/32 w12:1/16 w13:0/15 w14:1/22 w15:1/21 w16:0/8 w17:0/15 w18:2/54 w19:3/50 w20:0/21
- run_1784799404_80018: w1:0/4 w2:0/12 w3:0/9 w4:0/13 w5:0/6 w6:0/14 w7:1/14 w8:1/18 w9:0/10 w10:3/38 w11:2/25 w12:0/21 w13:0/26 w14:0/30 w15:0/35 w16:0/8 w17:2/32 w18:2/66 w19:3/63 w20:0/43
- run_1784800561_47448: w1:0/11 w2:0/12 w3:0/22 w4:1/14 w5:1/14 w6:1/19 w7:1/18 w8:0/9 w9:1/22 w10:1/20 w11:0/13 w12:0/17 w13:0/21 w14:1/29 w15:2/54 w16:0/5 w17:5/65 w18:8/67 w19:4/72 w20:0/25
- run_1784801716_88465: w1:0/1 w2:0/9 w3:1/14 w4:0/6 w5:0/9 w6:0/11 w7:1/32 w8:5/32 w9:5/27 w10:22/72
- run_1784802191_76892: w1:1/22 w2:0/5 w3:0/15 w4:0/7 w5:0/11 w6:0/12 w7:1/23 w8:0/18 w9:0/1 w10:29/58 w11:0/17 w12:1/18 w13:3/34 w14:2/30 w15:2/47 w16:1/20 w17:5/78 w18:2/61 w19:1/46 w20:1/48
- run_1784803299_7195: w1:1/6 w2:0/12 w3:0/7 w4:0/10 w5:0/11 w6:4/14 w7:0/9 w8:0/5 w9:0/3 w10:2/35 w11:0/13 w12:0/10 w13:0/7 w14:1/43 w15:0/31 w16:0/12 w17:2/49 w18:4/66 w19:3/75 w20:0/28
- run_1784804435_39794: w1:0/9 w2:0/10 w3:2/33 w4:2/15 w5:1/11 w6:0/6 w7:1/23 w8:0/14 w9:2/16 w10:5/37 w11:0/15 w12:1/20 w13:0/26 w14:0/17 w15:1/44 w16:0/14 w17:1/35 w18:1/45 w19:2/46 w20:0/19
- run_1784805636_10804: w1:0/12 w2:0/3 w3:0/9 w4:1/12 w5:0/8 w6:0/11 w7:0/19 w8:0/10 w9:0/16 w10:36/67 w11:4/44 w12:0/22 w13:1/34 w14:0/33 w15:1/32 w16:0/16 w17:6/59 w18:4/54 w19:3/66 w20:0/29
