# BC offline evaluation — `bc_v2`

Generated 2026-07-24 15:14:09 · checkpoint `best` · 2 run(s). Metrics recomputed independently from the frozen dataset + saved checkpoints (metrics.jsonl not trusted). Findings only.

## Sanity gates

Operationalization per architecture note §7 (fixed 2026-07-24): (a) beat mean-direction on overall median AND mean angular error; (b) beat copy-previous on overall MEAN angular error AND on median AND mean restricted to direction-change frames (teacher Δangle ≥ 1° vs previous tick). Overall-median vs copy-previous is deliberately NOT a gate (persistence artifact — 30.6% of labels repeat exactly).

| run | (a) mean-dir gate | (b) copy-prev gate | overall | model med° | model mean° | mean-dir med° | mean-dir mean° | copy mean° (overall) | model chg med° | model chg mean° | copy chg med° | copy chg mean° |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| bc_v2_a_s1 | PASS | PASS | PASS | 10.15 | 20.53 | 86.93 | 87.99 | 21.20 | 11.52 | 23.26 | 15.00 | 34.61 |
| bc_v2_b_s1 | PASS | PASS | PASS | 9.25 | 19.71 | 86.93 | 87.99 | 21.20 | 10.93 | 22.59 | 15.00 | 34.61 |

Informational — not a gate (persistence artifact — see architecture note §7):

| run | model overall median° | copy-previous overall median° |
|---|---|---|
| bc_v2_a_s1 | 10.15 | 4.32 |
| bc_v2_b_s1 | 9.25 | 4.32 |

## Direction-change frames (§7 gate stratum + ≥15° diagnostic)

Frames where both the teacher label and the unnormalized previous_action are moving (|a| > mag_eps) and the teacher Δangle ≥ threshold. The ≥1° row is the gating stratum; ≥15° is diagnostic only.

| run | threshold | n | model median° | model mean° | copy-prev median° | copy-prev mean° |
|---|---|---|---|---|---|---|
| bc_v2_a_s1 | ≥1° (gate) | 50036 | 11.52 | 23.26 | 15.00 | 34.61 |
| bc_v2_a_s1 | ≥15° (diag) | 24120 | 18.75 | 34.46 | 41.68 | 63.94 |
| bc_v2_b_s1 | ≥1° (gate) | 50036 | 10.93 | 22.59 | 15.00 | 34.61 |
| bc_v2_b_s1 | ≥15° (diag) | 24120 | 18.53 | 33.95 | 41.68 | 63.94 |

## Overall validation metrics

| run | seed | n | val_loss | median ang° | mean ang° | cosine | |mag err| | sat frac |
|---|---|---|---|---|---|---|---|---|
| bc_v2_a_s1 | 1 | 81790 | 0.1502 | 10.15 | 20.53 | 0.857 | 0.113 | 0.0000 |
| bc_v2_b_s1 | 1 | 81790 | 0.1449 | 9.25 | 19.71 | 0.862 | 0.112 | 0.0004 |

## Baselines (per run)

### bc_v2_a_s1

| stratum | n | median ang° | mean ang° | cosine | |mag err| | sat frac |
|---|---|---|---|---|---|---|
| mean-direction | 81790 | 86.93 | 87.99 | 0.023 | 0.000 | 0.0000 |
| copy-previous | 81790 | 4.32 | 21.20 | 0.814 | 0.000 | 0.0784 |

### bc_v2_b_s1

| stratum | n | median ang° | mean ang° | cosine | |mag err| | sat frac |
|---|---|---|---|---|---|---|
| mean-direction | 81790 | 86.93 | 87.99 | 0.023 | 0.000 | 0.0000 |
| copy-previous | 81790 | 4.32 | 21.20 | 0.814 | 0.000 | 0.0784 |

## Strata — bc_v2_a_s1

### By wave band

| stratum | n | median ang° | mean ang° | cosine | |mag err| | sat frac |
|---|---|---|---|---|---|---|
| 1-5 | 12828 | 7.49 | 11.19 | 0.958 | 0.082 | 0.0000 |
| 6-10 | 22470 | 9.03 | 15.17 | 0.920 | 0.099 | 0.0000 |
| 11-15 | 24925 | 10.15 | 19.33 | 0.874 | 0.116 | 0.0000 |
| 16-19 | 17324 | 13.74 | 30.55 | 0.743 | 0.144 | 0.0000 |
| 20 | 4243 | 19.11 | 43.24 | 0.587 | 0.134 | 0.0000 |

### By risk stratum

| stratum | n | median ang° | mean ang° | cosine | |mag err| | sat frac |
|---|---|---|---|---|---|---|
| 0.00-0.25 | 71206 | 9.68 | 18.80 | 0.877 | 0.110 | 0.0000 |
| 0.25-0.50 | 8004 | 12.37 | 26.07 | 0.796 | 0.122 | 0.0000 |
| 0.50-0.75 | 2384 | 27.13 | 49.92 | 0.515 | 0.169 | 0.0000 |
| 0.75-inf | 196 | 45.53 | 63.79 | 0.334 | 0.185 | 0.0000 |

### By validation run

| run_id | outcome | last_wave | n | median ang° | mean ang° | cosine | |mag err| | sat frac |
|---|---|---|---|---|---|---|---|---|
| run_1784787688_32406 | victory | 20 | 21775 | 13.62 | 26.24 | 0.801 | 0.150 | 0.0000 |
| run_1784793833_32034 | defeat | 17 | 17399 | 8.74 | 16.24 | 0.902 | 0.088 | 0.0000 |
| run_1784799404_80018 | defeat | 20 | 20906 | 8.65 | 17.70 | 0.883 | 0.089 | 0.0000 |
| run_1784804435_39794 | victory | 20 | 21710 | 10.29 | 20.95 | 0.852 | 0.118 | 0.0000 |

## Strata — bc_v2_b_s1

### By wave band

| stratum | n | median ang° | mean ang° | cosine | |mag err| | sat frac |
|---|---|---|---|---|---|---|
| 1-5 | 12828 | 7.00 | 10.78 | 0.960 | 0.080 | 0.0021 |
| 6-10 | 22470 | 8.14 | 14.64 | 0.921 | 0.095 | 0.0001 |
| 11-15 | 24925 | 9.27 | 18.25 | 0.882 | 0.118 | 0.0000 |
| 16-19 | 17324 | 12.37 | 29.32 | 0.753 | 0.142 | 0.0000 |
| 20 | 4243 | 18.93 | 42.94 | 0.589 | 0.133 | 0.0000 |

### By risk stratum

| stratum | n | median ang° | mean ang° | cosine | |mag err| | sat frac |
|---|---|---|---|---|---|---|
| 0.00-0.25 | 71206 | 8.79 | 17.94 | 0.882 | 0.109 | 0.0004 |
| 0.25-0.50 | 8004 | 11.72 | 25.70 | 0.798 | 0.121 | 0.0002 |
| 0.50-0.75 | 2384 | 27.45 | 49.04 | 0.524 | 0.165 | 0.0000 |
| 0.75-inf | 196 | 44.00 | 62.87 | 0.352 | 0.229 | 0.0026 |

### By validation run

| run_id | outcome | last_wave | n | median ang° | mean ang° | cosine | |mag err| | sat frac |
|---|---|---|---|---|---|---|---|---|
| run_1784787688_32406 | victory | 20 | 21775 | 12.76 | 25.18 | 0.811 | 0.150 | 0.0008 |
| run_1784793833_32034 | defeat | 17 | 17399 | 7.30 | 15.21 | 0.905 | 0.089 | 0.0000 |
| run_1784799404_80018 | defeat | 20 | 20906 | 8.22 | 17.12 | 0.887 | 0.089 | 0.0001 |
| run_1784804435_39794 | victory | 20 | 21710 | 9.61 | 20.34 | 0.855 | 0.115 | 0.0005 |

## Seed variance (across runs)

| metric | mean | std | min | max | n |
|---|---|---|---|---|---|
| val_loss | 0.1476 | 0.0026 | 0.1449 | 0.1502 | 2 |
| median_angular_error_deg | 9.6974 | 0.4495 | 9.2479 | 10.1469 | 2 |
| mean_angular_error_deg | 20.1194 | 0.4061 | 19.7134 | 20.5255 | 2 |
| mean_cosine | 0.8597 | 0.0027 | 0.8571 | 0.8624 | 2 |
| mean_abs_magnitude_error | 0.1124 | 0.0005 | 0.1119 | 0.1129 | 2 |
| saturation_fraction | 0.0002 | 0.0002 | 0.0000 | 0.0004 | 2 |

## Inter-seed agreement (val predictions, moving samples)

| run A | run B | n | median diff° | mean diff° |
|---|---|---|---|---|
| bc_v2_a_s1 | bc_v2_b_s1 | 81790 | 7.33 | 11.59 |

