# WP2 bc_v3 aggregate offline evaluation (r1 + r2 corrective)

Generated 2026-07-24 18:06:04 - device `cuda` - mag_eps 0.01. Findings only, no promotion recommendation.

Three distributions: (i) teacher-val = frozen `combat_obs_v1` val split via the unchanged `bc_offline.evaluate_run` path (each model's own normalization manifest); (ii) r1 holdout = deterministic 10% `combat_dagger_r1` (n=7887); (iii) r2 holdout = deterministic 10% `combat_dagger_r2` (n=11627, seed 20260724). Label on both holdouts = teacher.action.

**The R2 holdout is the primary deployment-distribution comparison and is unbiased for ALL FOUR models**: bc_v1_s1_full and bc_v2_f_s1 never trained on any r2 row (r2 was collected under the bc_v2_f student), and both bc_v3 candidates exclude the r2 holdout from training.

## Summary: 4 models x 3 distributions (median / cosine / |mag err|)

| model | tv median | tv cos | tv |mag| | r1 median | r1 cos | r1 |mag| | r2 median | r2 cos | r2 |mag| |
|---|---|---|---|---|---|---|---|---|---|
| bc_v1_s1_full | 4.801 | 0.9037 | 0.0517 | 71.504 | 0.1610 | 0.0403 | 56.679 | 0.2649 | 0.0495 |
| bc_v2_f_s1 | 8.734 | 0.8704 | 0.0831 | 25.488 | 0.6801 | 0.1194 | 55.746 | 0.2706 | 0.0883 |
| bc_v3_a_s1 | 8.699 | 0.8705 | 0.0756 | 35.638 | 0.5091 | 0.1030 | 37.853 | 0.4802 | 0.0969 |
| bc_v3_b_s1 | 9.252 | 0.8601 | 0.0809 | 34.395 | 0.5314 | 0.1086 | 36.840 | 0.5071 | 0.0950 |
| copy_previous (baseline) | - | - | - | 74.565 | 0.1357 | 0.0248 | 59.845 | 0.2342 | 0.0552 |

## §8 REVISED gates (deployment clauses on R2 holdout) -- PASS/FAIL per clause

Clauses (ALL must pass): `tv_median` <= 9.0deg; `tv_magerr` <= 0.09; `tv_sat` no saturation regression (~0); `ho_median_r2` <= 30deg; `ho_cos_pos_r2` cosine > 0 in every risk stratum; `ho_risk_mid_r2` risk 0.50-0.75 median <= 35deg; `ho_risk_hi_r2` risk 0.75+ median <= 45deg; `anti_copy_r2` r2 median <= 37.3deg (>= 2x better than copy_previous 59.845deg).

| model | tv_median | tv_magerr | tv_sat | ho_median_r2 | ho_cos_pos_r2 | ho_risk_mid_r2 | ho_risk_hi_r2 | anti_copy_r2 | QUALIFIES |
|---|---|---|---|---|---|---|---|---|---|
| bc_v3_a_s1 | 8.699 [PASS] | 0.0756 [PASS] | 0.00017 [PASS] | 37.853 [FAIL] | 0.00-0.25=0.5156, 0.25-0.50=0.3999, 0.50-0.75=0.3094, 0.75-inf=0.0634 [PASS] | 57.803 [FAIL] | 78.824 [FAIL] | 37.853 [FAIL] | **FAIL** |
| bc_v3_b_s1 | 9.252 [FAIL] | 0.0809 [PASS] | 0.00010 [PASS] | 36.840 [FAIL] | 0.00-0.25=0.5417, 0.25-0.50=0.4239, 0.50-0.75=0.3437, 0.75-inf=0.1319 [PASS] | 55.797 [FAIL] | 78.037 [FAIL] | 36.840 [PASS] | **FAIL** |

## Teacher-val -- by risk stratum (median deg / cosine)

| model | 0.00-0.25 med | 0.25-0.50 med | 0.50-0.75 med | 0.75-inf med | 0.00-0.25 cos | 0.25-0.50 cos | 0.50-0.75 cos | 0.75-inf cos |
|---|---|---|---|---|---|---|---|---|
| bc_v1_s1_full | 4.551 | 6.024 | 18.213 | 30.984 | 0.9221 | 0.8490 | 0.5744 | 0.4276 |
| bc_v2_f_s1 | 8.250 | 11.618 | 24.658 | 42.528 | 0.8898 | 0.8099 | 0.5360 | 0.3578 |
| bc_v3_a_s1 | 8.313 | 10.687 | 21.890 | 35.177 | 0.8893 | 0.8174 | 0.5293 | 0.3801 |
| bc_v3_b_s1 | 8.788 | 11.630 | 24.194 | 37.198 | 0.8786 | 0.8094 | 0.5187 | 0.3687 |

## R1 holdout -- by risk stratum (median deg / cosine)

| model | 0.00-0.25 med | 0.25-0.50 med | 0.50-0.75 med | 0.75-inf med | 0.00-0.25 cos | 0.25-0.50 cos | 0.50-0.75 cos | 0.75-inf cos |
|---|---|---|---|---|---|---|---|---|
| bc_v1_s1_full | 69.144 | 68.117 | 94.171 | 112.041 | 0.1878 | 0.1864 | -0.0465 | -0.1975 |
| bc_v2_f_s1 | 23.873 | 29.846 | 29.608 | 38.851 | 0.6912 | 0.6507 | 0.6435 | 0.5661 |
| bc_v3_a_s1 | 32.187 | 42.674 | 59.761 | 82.512 | 0.5518 | 0.4506 | 0.2889 | 0.0560 |
| bc_v3_b_s1 | 31.177 | 41.998 | 54.417 | 79.398 | 0.5677 | 0.4783 | 0.3604 | 0.1168 |
| copy_previous | 72.307 | 69.648 | 95.124 | 111.696 | 0.1594 | 0.1722 | -0.0625 | -0.2013 |

## R2 holdout -- by risk stratum (median deg / cosine)

| model | 0.00-0.25 med | 0.25-0.50 med | 0.50-0.75 med | 0.75-inf med | 0.00-0.25 cos | 0.25-0.50 cos | 0.50-0.75 cos | 0.75-inf cos |
|---|---|---|---|---|---|---|---|---|
| bc_v1_s1_full | 51.307 | 67.572 | 76.969 | 109.279 | 0.3011 | 0.1972 | 0.0776 | -0.2384 |
| bc_v2_f_s1 | 49.623 | 68.965 | 78.124 | 107.482 | 0.3103 | 0.1855 | 0.0681 | -0.1835 |
| bc_v3_a_s1 | 33.718 | 48.947 | 57.803 | 78.824 | 0.5156 | 0.3999 | 0.3094 | 0.0634 |
| bc_v3_b_s1 | 32.765 | 46.582 | 55.797 | 78.037 | 0.5417 | 0.4239 | 0.3437 | 0.1319 |
| copy_previous | 54.289 | 70.758 | 82.367 | 116.318 | 0.2715 | 0.1756 | 0.0261 | -0.3097 |

## Teacher-val -- by wave band (median deg)

| model | 1-5 | 6-10 | 11-15 | 16-19 | 20 |
|---|---|---|---|---|---|
| bc_v1_s1_full | 3.368 | 3.920 | 4.735 | 7.118 | 18.251 |
| bc_v2_f_s1 | 6.023 | 7.550 | 9.053 | 12.607 | 19.018 |
| bc_v3_a_s1 | 6.045 | 7.726 | 8.506 | 12.871 | 17.714 |
| bc_v3_b_s1 | 6.123 | 7.968 | 9.197 | 14.456 | 19.463 |

## R1 holdout -- by wave band (median deg)

| model | 1-5 | 6-10 | 11-15 | 16-19 | 20 |
|---|---|---|---|---|---|
| bc_v1_s1_full | 59.014 | 69.121 | 77.763 | 91.353 | 51.713 |
| bc_v2_f_s1 | 23.463 | 24.120 | 26.122 | 28.953 | 24.513 |
| bc_v3_a_s1 | 33.391 | 33.693 | 36.829 | 42.729 | 35.730 |
| bc_v3_b_s1 | 32.087 | 32.843 | 35.222 | 39.920 | 33.733 |
| copy_previous | 62.887 | 71.499 | 80.307 | 93.266 | 54.756 |

## R2 holdout -- by wave band (median deg)

| model | 1-5 | 6-10 | 11-15 | 16-19 | 20 |
|---|---|---|---|---|---|
| bc_v1_s1_full | 30.747 | 56.194 | 62.678 | 73.034 | 79.791 |
| bc_v2_f_s1 | 27.852 | 53.375 | 62.839 | 74.253 | 81.439 |
| bc_v3_a_s1 | 24.112 | 37.514 | 37.839 | 50.056 | 45.364 |
| bc_v3_b_s1 | 24.420 | 36.173 | 36.554 | 46.440 | 40.880 |
| copy_previous | 31.877 | 57.516 | 67.303 | 79.086 | 83.366 |

## Holdout stratum counts

| stratum | r1 n | r2 n |
|---|---|---|
| overall | 7887 | 11627 |
| risk 0.00-0.25 | 6233 | 9136 |
| risk 0.25-0.50 | 880 | 1495 |
| risk 0.50-0.75 | 583 | 859 |
| risk 0.75-inf | 191 | 137 |

## Training wall times (from registries)

| model | epochs_run | best_epoch | wall_time_sec |
|---|---|---|---|
| bc_v1_s1_full | 28 | 22 | 67.0 |
| bc_v2_f_s1 | 19 | 13 | 44.0 |
| bc_v3_a_s1 | 13 | 7 | 40.4 |
| bc_v3_b_s1 | 11 | 5 | 35.6 |

No anomalies.

