# Teacher action distribution (combat_obs_v1)

Read-only analysis over all 20 shards. Samples: 388067 total, 387695 valid AND temporal_valid (372 excluded).

## Magnitude

- exact zeros: 0.01% (40)
- near-zero (<0.01): 0.01% (40)
- within 1e-3 of 1.0 (unit): 99.99% (387655)
- min/mean/median/max: 0.000000 / 0.999897 / 1.000000 / 1.000001
- distinct rounded(6) magnitudes: 4

Histogram (|a|):

| lo | hi | count | frac |
| --- | --- | --- | --- |
| 0.000 | 0.010 | 40 | 0.01% |
| 0.010 | 0.100 | 0 | 0.00% |
| 0.100 | 0.200 | 0 | 0.00% |
| 0.200 | 0.300 | 0 | 0.00% |
| 0.300 | 0.400 | 0 | 0.00% |
| 0.400 | 0.500 | 0 | 0.00% |
| 0.500 | 0.600 | 0 | 0.00% |
| 0.600 | 0.700 | 0 | 0.00% |
| 0.700 | 0.800 | 0 | 0.00% |
| 0.800 | 0.900 | 0 | 0.00% |
| 0.900 | 0.990 | 0 | 0.00% |
| 0.990 | 0.999 | 0 | 0.00% |
| 0.999 | 1.001 | 387655 | 99.99% |
| 1.001 | 1.010 | 0 | 0.00% |
| 1.010 | 1.100 | 0 | 0.00% |
| 1.100 | 1.200 | 0 | 0.00% |
| 1.200 | inf | 0 | 0.00% |

## Direction (moving samples, |a| > 0.01)

- moving samples: 387655 (99.99% of all)
- within 0.5 deg of 15 deg grid: 53.28%
- within 2 deg of 15 deg grid: 63.04%
- within 0.5 deg of 45 deg grid: 17.92%
- within 0.5 deg of 90 deg grid: 7.73%

Top 10 of 360 one-degree angle bins:

| bin (deg) | count | frac |
| --- | --- | --- |
| [45, 46) | 10428 | 2.69% |
| [225, 226) | 10146 | 2.62% |
| [315, 316) | 9817 | 2.53% |
| [59, 60) | 9682 | 2.50% |
| [210, 211) | 9533 | 2.46% |
| [329, 330) | 9344 | 2.41% |
| [30, 31) | 9139 | 2.36% |
| [135, 136) | 9074 | 2.34% |
| [300, 301) | 8923 | 2.30% |
| [75, 76) | 8730 | 2.25% |

## Per-wave band

| band | n | zero | unit | grid15 (2deg, moving) | mean |a| |
| --- | --- | --- | --- | --- | --- |
| 1-5 | 64218 | 0.06% | 99.94% | 46.67% | 0.9994 |
| 6-10 | 111940 | 0.00% | 100.00% | 58.62% | 1.0000 |
| 11-15 | 111967 | 0.00% | 100.00% | 63.08% | 1.0000 |
| 16-19 | 81676 | 0.00% | 100.00% | 76.10% | 1.0000 |
| 20 | 17894 | 0.00% | 100.00% | 89.53% | 1.0000 |

## Persistence & label consistency

- seq-consecutive pairs: 387323
- identical action (exact float): 30.56%
- angle change < 1 deg (both moving, n=387283): 38.68%
- label check action(t) == previous_action(t+1) exact: 100.00%

## Component marginals

- x mean/std: -0.020621 / 0.719757
- y mean/std: -0.010913 / 0.693760
- |x| == 1.0 exactly: 3.52%
- |y| == 1.0 exactly: 3.71%

## Per-run summary

| run_id | n | zero | unit | grid15 |
| --- | --- | --- | --- | --- |
| run_1784785556_51395 | 21041 | 0.19% | 99.81% | 64.46% |
| run_1784786723_17546 | 17323 | 0.00% | 100.00% | 63.31% |
| run_1784787688_32406 | 21775 | 0.00% | 100.00% | 61.18% |
| run_1784788917_7315 | 20993 | 0.00% | 100.00% | 65.09% |
| run_1784790063_90333 | 20815 | 0.00% | 100.00% | 60.25% |
| run_1784791214_74323 | 17461 | 0.00% | 100.00% | 53.38% |
| run_1784792179_82981 | 8628 | 0.00% | 100.00% | 56.00% |
| run_1784792652_7723 | 21832 | 0.00% | 100.00% | 67.13% |
| run_1784793833_32034 | 17399 | 0.00% | 100.00% | 62.95% |
| run_1784794784_69267 | 20840 | 0.00% | 100.00% | 59.36% |
| run_1784795927_93597 | 21039 | 0.00% | 100.00% | 68.92% |
| run_1784797082_83949 | 21596 | 0.00% | 100.00% | 63.26% |
| run_1784798249_41022 | 21091 | 0.00% | 100.00% | 61.30% |
| run_1784799404_80018 | 20906 | 0.00% | 100.00% | 64.37% |
| run_1784800561_47448 | 21293 | 0.00% | 100.00% | 62.80% |
| run_1784801716_88465 | 8540 | 0.00% | 100.00% | 59.30% |
| run_1784802191_76892 | 20548 | 0.00% | 100.00% | 66.76% |
| run_1784803299_7195 | 21040 | 0.00% | 100.00% | 60.52% |
| run_1784804435_39794 | 21710 | 0.00% | 100.00% | 64.00% |
| run_1784805636_10804 | 21825 | 0.00% | 100.00% | 68.18% |

## Interpretation

Of the 387695 valid teacher actions, 0.01% are exact zeros (idle / no move) and 99.99% are within 1e-3 of unit magnitude, so magnitude is strongly bimodal at 0 and 1 (min 0.0000, max 1.0000, only 4 distinct rounded values).

Among the 99.99% of samples that are moving (|a| > 0.01), 63.04% fall within 2 deg of the 24-direction 15 deg lane grid and 53.28% within 0.5 deg, so the emitted directions are heavily quantized onto that grid.

Direction structure and unit-magnitude fraction shift across wave bands (see table); wave 20's finale controller is reported separately as its own band. Consecutive actions are highly persistent (30.56% identical exact-float, 38.68% with sub-1 deg angle change), and the label-pipeline check action(t)==previous_action(t+1) matches exactly 100.00% of the time.

