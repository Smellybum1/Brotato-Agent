# WP2 v122 exact-20 combat-capture audit

- Runs with captures: 20 (20 terminal)
- Captures (all 20): 388067
- Valid transition estimate: 388067
- Gap to 200,000: 0
- Malformed lines: 0
- Schema mismatches: 0
- Invalid captures/actions: 0 / 0
- Near-duplicate fraction: 0.0315

All 20 runs terminate on `run_end` with zero error events and zero schema mismatches: no run carries a capture fault. Capture inclusion is therefore governed by the safety audit.

## Per-run captures

| # | run_id | captures | terminal | errors | schema_faults |
|--:|---|--:|:--|--:|--:|
| 1 | run_1784785556_51395 | 21061 | yes | 0 | 0 |
| 2 | run_1784786723_17546 | 17341 | yes | 0 | 0 |
| 3 | run_1784787688_32406 | 21795 | yes | 0 | 0 |
| 4 | run_1784788917_7315 | 21013 | yes | 0 | 0 |
| 5 | run_1784790063_90333 | 20835 | yes | 0 | 0 |
| 6 | run_1784791214_74323 | 17478 | yes | 0 | 0 |
| 7 | run_1784792179_82981 | 8638 | yes | 0 | 0 |
| 8 | run_1784792652_7723 | 21852 | yes | 0 | 0 |
| 9 | run_1784793833_32034 | 17416 | yes | 0 | 0 |
| 10 | run_1784794784_69267 | 20860 | yes | 0 | 0 |
| 11 | run_1784795927_93597 | 21059 | yes | 0 | 0 |
| 12 | run_1784797082_83949 | 21616 | yes | 0 | 0 |
| 13 | run_1784798249_41022 | 21111 | yes | 0 | 0 |
| 14 | run_1784799404_80018 | 20926 | yes | 0 | 0 |
| 15 | run_1784800561_47448 | 21313 | yes | 0 | 0 |
| 16 | run_1784801716_88465 | 8550 | yes | 0 | 0 |
| 17 | run_1784802191_76892 | 20568 | yes | 0 | 0 |
| 18 | run_1784803299_7195 | 21060 | yes | 0 | 0 |
| 19 | run_1784804435_39794 | 21730 | yes | 0 | 0 |
| 20 | run_1784805636_10804 | 21845 | yes | 0 | 0 |

## Per-wave capture coverage (all 20 runs)

| wave | captures |
|--:|--:|
| 1 | 8800 |
| 2 | 10909 |
| 3 | 12841 |
| 4 | 14849 |
| 5 | 16919 |
| 6 | 18869 |
| 7 | 20876 |
| 8 | 22912 |
| 9 | 25004 |
| 10 | 24379 |
| 11 | 22442 |
| 12 | 22422 |
| 13 | 22397 |
| 14 | 22399 |
| 15 | 22398 |
| 16 | 22428 |
| 17 | 21993 |
| 18 | 18642 |
| 19 | 18679 |
| 20 | 17909 |

All waves 1-20 are represented. Waves 1-20 remain represented in the 17-run inclusion set (the 3 excluded runs are all wave-20 victories).

## Entity count percentiles

| Group | p50 | p90 | p95 | p99 | max |
|---|---:|---:|---:|---:|---:|
| enemies | 9.0 | 24.0 | 30.0 | 40.0 | 61 |
| bosses | 0.0 | 0.0 | 0.0 | 1.0 | 1 |
| projectiles | 0.0 | 3.0 | 7.0 | 25.0 | 32 |
| materials | 11.0 | 47.0 | 50.0 | 50.0 | 54 |
| consumables | 1.0 | 5.0 | 6.0 | 10.0 | 18 |
| crates | 0.0 | 1.0 | 1.0 | 2.0 | 4 |
| obstacles | 0.0 | 1.0 | 1.0 | 2.0 | 5 |

## Severe-state capture counts

- boss: 17578
- charger: 164404
- dense_projectiles: 13857
- low_health: 894
