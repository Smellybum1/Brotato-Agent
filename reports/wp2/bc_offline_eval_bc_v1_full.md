# BC offline evaluation — `bc_v1_full`

Generated 2026-07-24 02:22:52 · checkpoint `best` · 4 run(s). Metrics recomputed independently from the frozen dataset + saved checkpoints (metrics.jsonl not trusted). Findings only.

## Sanity gates

Operationalization per architecture note §7 (fixed 2026-07-24): (a) beat mean-direction on overall median AND mean angular error; (b) beat copy-previous on overall MEAN angular error AND on median AND mean restricted to direction-change frames (teacher Δangle ≥ 1° vs previous tick). Overall-median vs copy-previous is deliberately NOT a gate (persistence artifact — 30.6% of labels repeat exactly).

| run | (a) mean-dir gate | (b) copy-prev gate | overall | model med° | model mean° | mean-dir med° | mean-dir mean° | copy mean° (overall) | model chg med° | model chg mean° | copy chg med° | copy chg mean° |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| bc_v1_s1_full | PASS | PASS | PASS | 4.80 | 13.73 | 86.93 | 87.99 | 21.20 | 6.67 | 16.93 | 15.00 | 34.61 |
| bc_v1_s2_full | PASS | PASS | PASS | 5.30 | 14.17 | 86.93 | 87.99 | 21.20 | 7.15 | 17.61 | 15.00 | 34.61 |
| bc_v1_s3_full | PASS | PASS | PASS | 4.91 | 13.80 | 86.93 | 87.99 | 21.20 | 6.74 | 17.03 | 15.00 | 34.61 |
| bc_v1_s1_p0_diag | PASS | PASS | PASS | 5.00 | 13.67 | 86.93 | 87.99 | 21.20 | 6.61 | 16.79 | 15.00 | 34.61 |

Informational — not a gate (persistence artifact — see architecture note §7):

| run | model overall median° | copy-previous overall median° |
|---|---|---|
| bc_v1_s1_full | 4.80 | 4.32 |
| bc_v1_s2_full | 5.30 | 4.32 |
| bc_v1_s3_full | 4.91 | 4.32 |
| bc_v1_s1_p0_diag | 5.00 | 4.32 |

## Direction-change frames (§7 gate stratum + ≥15° diagnostic)

Frames where both the teacher label and the unnormalized previous_action are moving (|a| > mag_eps) and the teacher Δangle ≥ threshold. The ≥1° row is the gating stratum; ≥15° is diagnostic only.

| run | threshold | n | model median° | model mean° | copy-prev median° | copy-prev mean° |
|---|---|---|---|---|---|---|
| bc_v1_s1_full | ≥1° (gate) | 50036 | 6.67 | 16.93 | 15.00 | 34.61 |
| bc_v1_s1_full | ≥15° (diag) | 24120 | 12.66 | 27.16 | 41.68 | 63.94 |
| bc_v1_s2_full | ≥1° (gate) | 50036 | 7.15 | 17.61 | 15.00 | 34.61 |
| bc_v1_s2_full | ≥15° (diag) | 24120 | 14.21 | 28.59 | 41.68 | 63.94 |
| bc_v1_s3_full | ≥1° (gate) | 50036 | 6.74 | 17.03 | 15.00 | 34.61 |
| bc_v1_s3_full | ≥15° (diag) | 24120 | 13.11 | 27.33 | 41.68 | 63.94 |
| bc_v1_s1_p0_diag | ≥1° (gate) | 50036 | 6.61 | 16.79 | 15.00 | 34.61 |
| bc_v1_s1_p0_diag | ≥15° (diag) | 24120 | 12.48 | 26.85 | 41.68 | 63.94 |

## Overall validation metrics

| run | seed | n | val_loss | median ang° | mean ang° | cosine | |mag err| | sat frac |
|---|---|---|---|---|---|---|---|---|
| bc_v1_s1_full | 1 | 81790 | 0.0981 | 4.80 | 13.73 | 0.904 | 0.052 | 0.0000 |
| bc_v1_s2_full | 2 | 81790 | 0.0999 | 5.30 | 14.17 | 0.902 | 0.052 | 0.0000 |
| bc_v1_s3_full | 3 | 81790 | 0.0984 | 4.91 | 13.80 | 0.903 | 0.051 | 0.0002 |
| bc_v1_s1_p0_diag | 1 | 81790 | 0.0968 | 5.00 | 13.67 | 0.905 | 0.055 | 0.0000 |

## Baselines (per run)

### bc_v1_s1_full

| stratum | n | median ang° | mean ang° | cosine | |mag err| | sat frac |
|---|---|---|---|---|---|---|
| mean-direction | 81790 | 86.93 | 87.99 | 0.023 | 0.000 | 0.0000 |
| copy-previous | 81790 | 4.32 | 21.20 | 0.814 | 0.000 | 0.0784 |

### bc_v1_s2_full

| stratum | n | median ang° | mean ang° | cosine | |mag err| | sat frac |
|---|---|---|---|---|---|---|
| mean-direction | 81790 | 86.93 | 87.99 | 0.023 | 0.000 | 0.0000 |
| copy-previous | 81790 | 4.32 | 21.20 | 0.814 | 0.000 | 0.0784 |

### bc_v1_s3_full

| stratum | n | median ang° | mean ang° | cosine | |mag err| | sat frac |
|---|---|---|---|---|---|---|
| mean-direction | 81790 | 86.93 | 87.99 | 0.023 | 0.000 | 0.0000 |
| copy-previous | 81790 | 4.32 | 21.20 | 0.814 | 0.000 | 0.0784 |

### bc_v1_s1_p0_diag

| stratum | n | median ang° | mean ang° | cosine | |mag err| | sat frac |
|---|---|---|---|---|---|---|
| mean-direction | 81790 | 86.93 | 87.99 | 0.023 | 0.000 | 0.0000 |
| copy-previous | 81790 | 4.32 | 21.20 | 0.814 | 0.000 | 0.0784 |

## Strata — bc_v1_s1_full

### By wave band

| stratum | n | median ang° | mean ang° | cosine | |mag err| | sat frac |
|---|---|---|---|---|---|---|
| 1-5 | 12828 | 3.37 | 5.58 | 0.986 | 0.041 | 0.0000 |
| 6-10 | 22470 | 3.92 | 8.25 | 0.963 | 0.039 | 0.0000 |
| 11-15 | 24925 | 4.74 | 11.30 | 0.933 | 0.045 | 0.0000 |
| 16-19 | 17324 | 7.12 | 23.40 | 0.797 | 0.070 | 0.0000 |
| 20 | 4243 | 18.25 | 42.06 | 0.600 | 0.110 | 0.0000 |

### By risk stratum

| stratum | n | median ang° | mean ang° | cosine | |mag err| | sat frac |
|---|---|---|---|---|---|---|
| 0.00-0.25 | 71206 | 4.55 | 12.02 | 0.922 | 0.049 | 0.0000 |
| 0.25-0.50 | 8004 | 6.02 | 18.99 | 0.849 | 0.054 | 0.0000 |
| 0.50-0.75 | 2384 | 18.21 | 43.52 | 0.574 | 0.112 | 0.0000 |
| 0.75-inf | 196 | 30.98 | 56.76 | 0.428 | 0.145 | 0.0000 |

### By validation run

| run_id | outcome | last_wave | n | median ang° | mean ang° | cosine | |mag err| | sat frac |
|---|---|---|---|---|---|---|---|---|
| run_1784787688_32406 | victory | 20 | 21775 | 4.87 | 13.51 | 0.906 | 0.049 | 0.0000 |
| run_1784793833_32034 | defeat | 17 | 17399 | 4.38 | 11.71 | 0.924 | 0.046 | 0.0000 |
| run_1784799404_80018 | defeat | 20 | 20906 | 4.62 | 13.49 | 0.905 | 0.050 | 0.0000 |
| run_1784804435_39794 | victory | 20 | 21710 | 5.38 | 15.78 | 0.883 | 0.061 | 0.0000 |

## Strata — bc_v1_s2_full

### By wave band

| stratum | n | median ang° | mean ang° | cosine | |mag err| | sat frac |
|---|---|---|---|---|---|---|
| 1-5 | 12828 | 4.03 | 6.19 | 0.985 | 0.045 | 0.0000 |
| 6-10 | 22470 | 4.54 | 8.80 | 0.962 | 0.042 | 0.0000 |
| 11-15 | 24925 | 5.34 | 11.89 | 0.931 | 0.048 | 0.0000 |
| 16-19 | 17324 | 7.08 | 23.65 | 0.796 | 0.074 | 0.0000 |
| 20 | 4243 | 14.86 | 41.51 | 0.595 | 0.066 | 0.0000 |

### By risk stratum

| stratum | n | median ang° | mean ang° | cosine | |mag err| | sat frac |
|---|---|---|---|---|---|---|
| 0.00-0.25 | 71206 | 5.08 | 12.43 | 0.921 | 0.051 | 0.0000 |
| 0.25-0.50 | 8004 | 6.23 | 19.52 | 0.845 | 0.056 | 0.0000 |
| 0.50-0.75 | 2384 | 18.30 | 44.90 | 0.556 | 0.078 | 0.0000 |
| 0.75-inf | 196 | 37.20 | 57.04 | 0.425 | 0.103 | 0.0000 |

### By validation run

| run_id | outcome | last_wave | n | median ang° | mean ang° | cosine | |mag err| | sat frac |
|---|---|---|---|---|---|---|---|---|
| run_1784787688_32406 | victory | 20 | 21775 | 5.22 | 13.84 | 0.905 | 0.049 | 0.0000 |
| run_1784793833_32034 | defeat | 17 | 17399 | 4.97 | 12.29 | 0.923 | 0.050 | 0.0000 |
| run_1784799404_80018 | defeat | 20 | 20906 | 5.21 | 13.91 | 0.904 | 0.052 | 0.0000 |
| run_1784804435_39794 | victory | 20 | 21710 | 5.80 | 16.28 | 0.880 | 0.057 | 0.0000 |

## Strata — bc_v1_s3_full

### By wave band

| stratum | n | median ang° | mean ang° | cosine | |mag err| | sat frac |
|---|---|---|---|---|---|---|
| 1-5 | 12828 | 3.44 | 5.66 | 0.986 | 0.039 | 0.0011 |
| 6-10 | 22470 | 4.09 | 8.26 | 0.964 | 0.039 | 0.0000 |
| 11-15 | 24925 | 4.89 | 11.45 | 0.933 | 0.046 | 0.0000 |
| 16-19 | 17324 | 7.16 | 23.55 | 0.797 | 0.068 | 0.0000 |
| 20 | 4243 | 16.91 | 41.72 | 0.598 | 0.120 | 0.0000 |

### By risk stratum

| stratum | n | median ang° | mean ang° | cosine | |mag err| | sat frac |
|---|---|---|---|---|---|---|
| 0.00-0.25 | 71206 | 4.66 | 12.09 | 0.922 | 0.049 | 0.0002 |
| 0.25-0.50 | 8004 | 6.00 | 19.28 | 0.846 | 0.055 | 0.0000 |
| 0.50-0.75 | 2384 | 17.55 | 43.05 | 0.578 | 0.113 | 0.0000 |
| 0.75-inf | 196 | 37.17 | 57.69 | 0.422 | 0.141 | 0.0000 |

### By validation run

| run_id | outcome | last_wave | n | median ang° | mean ang° | cosine | |mag err| | sat frac |
|---|---|---|---|---|---|---|---|---|
| run_1784787688_32406 | victory | 20 | 21775 | 5.03 | 13.68 | 0.905 | 0.051 | 0.0006 |
| run_1784793833_32034 | defeat | 17 | 17399 | 4.47 | 11.73 | 0.925 | 0.045 | 0.0000 |
| run_1784799404_80018 | defeat | 20 | 20906 | 4.62 | 13.44 | 0.906 | 0.048 | 0.0000 |
| run_1784804435_39794 | victory | 20 | 21710 | 5.50 | 15.93 | 0.882 | 0.060 | 0.0000 |

## Strata — bc_v1_s1_p0_diag

### By wave band

| stratum | n | median ang° | mean ang° | cosine | |mag err| | sat frac |
|---|---|---|---|---|---|---|
| 1-5 | 12828 | 3.94 | 5.89 | 0.987 | 0.044 | 0.0000 |
| 6-10 | 22470 | 4.02 | 8.19 | 0.964 | 0.044 | 0.0000 |
| 11-15 | 24925 | 4.87 | 11.32 | 0.934 | 0.051 | 0.0000 |
| 16-19 | 17324 | 7.06 | 22.95 | 0.802 | 0.075 | 0.0001 |
| 20 | 4243 | 16.19 | 42.07 | 0.594 | 0.095 | 0.0000 |

### By risk stratum

| stratum | n | median ang° | mean ang° | cosine | |mag err| | sat frac |
|---|---|---|---|---|---|---|
| 0.00-0.25 | 71206 | 4.75 | 11.92 | 0.924 | 0.053 | 0.0000 |
| 0.25-0.50 | 8004 | 6.32 | 19.21 | 0.847 | 0.059 | 0.0001 |
| 0.50-0.75 | 2384 | 16.78 | 43.90 | 0.565 | 0.094 | 0.0000 |
| 0.75-inf | 196 | 28.84 | 55.03 | 0.450 | 0.120 | 0.0000 |

### By validation run

| run_id | outcome | last_wave | n | median ang° | mean ang° | cosine | |mag err| | sat frac |
|---|---|---|---|---|---|---|---|---|
| run_1784787688_32406 | victory | 20 | 21775 | 5.17 | 13.57 | 0.907 | 0.054 | 0.0000 |
| run_1784793833_32034 | defeat | 17 | 17399 | 4.47 | 11.65 | 0.926 | 0.051 | 0.0000 |
| run_1784799404_80018 | defeat | 20 | 20906 | 4.89 | 13.32 | 0.908 | 0.052 | 0.0001 |
| run_1784804435_39794 | victory | 20 | 21710 | 5.40 | 15.72 | 0.884 | 0.063 | 0.0000 |

## Seed variance (across runs)

| metric | mean | std | min | max | n |
|---|---|---|---|---|---|
| val_loss | 0.0983 | 0.0011 | 0.0968 | 0.0999 | 4 |
| median_angular_error_deg | 5.0030 | 0.1868 | 4.8008 | 5.3023 | 4 |
| mean_angular_error_deg | 13.8418 | 0.1973 | 13.6666 | 14.1735 | 4 |
| mean_cosine | 0.9034 | 0.0011 | 0.9018 | 0.9049 | 4 |
| mean_abs_magnitude_error | 0.0526 | 0.0015 | 0.0514 | 0.0552 | 4 |
| saturation_fraction | 0.0001 | 0.0001 | 0.0000 | 0.0002 | 4 |

## Inter-seed agreement (val predictions, moving samples)

| run A | run B | n | median diff° | mean diff° |
|---|---|---|---|---|
| bc_v1_s1_full | bc_v1_s2_full | 81790 | 4.05 | 6.20 |
| bc_v1_s1_full | bc_v1_s3_full | 81790 | 3.37 | 5.54 |
| bc_v1_s1_full | bc_v1_s1_p0_diag | 81790 | 3.16 | 5.25 |
| bc_v1_s2_full | bc_v1_s3_full | 81790 | 4.20 | 6.46 |
| bc_v1_s2_full | bc_v1_s1_p0_diag | 81790 | 4.17 | 6.20 |
| bc_v1_s3_full | bc_v1_s1_p0_diag | 81790 | 3.89 | 6.19 |

