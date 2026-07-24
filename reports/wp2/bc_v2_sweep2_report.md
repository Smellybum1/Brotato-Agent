# WP2 bc_v2 round-2b -- curriculum vs joint-low-mass (dual-distribution + §8 gates)

Generated 2026-07-24 15:47:04 - device `cuda` - mag_eps 0.01. Findings only, no promotion recommendation.

Two distributions: (a) teacher-val = frozen `combat_obs_v1` val split (81790 rows) via the unchanged `bc_offline.evaluate_run` path (each model's own normalization manifest); (b) dagger-holdout = the deterministic 10% `combat_dagger_r1` holdout (n=7887, seed 20260724), excluded from all bc_v2 training, label = teacher.action.

Split reproduction: holdout aux_damage base rate 0.019334188 (registry 0.019334188), aux_margin mean 0.761300862 (registry 0.761300862) -> reproduces training split: True.

## Sweep configuration

| variant | corrective mass | prev-action dropout | lambda_mag | note |
|---|---|---|---|---|
| bc_v1_s1_full | - | 0.1 | 0.5 | no dagger data (teacher-only bc_v1) |
| bc_v2_f_s1 | 0.15 | 0.4 | 1.0 | round-2 F (magnitude-repair probe) |
| bc_v2_g_s1 | 0.15 | 0.4 | 1.0 | round-2b G (curriculum fine-tune from bc_v1, LR 3e-5, patience 3) |
| bc_v2_h_s1 | 0.05 | 0.4 | 1.0 | round-2b H (fresh joint, low mass 0.05) |

## Frontier table (requested)

| variant | tv median deg | tv \|mag err\| | tv risk 0.50-0.75 median | holdout median deg | holdout cosine | holdout \|mag err\| | holdout risk 0.50-0.75 median |
|---|---|---|---|---|---|---|---|
| bc_v1_s1_full | 4.801 | 0.0517 | 18.213 | 71.504 | 0.1610 | 0.0403 | 94.171 |
| bc_v2_f_s1 | 8.734 | 0.0831 | 24.658 | 25.488 | 0.6801 | 0.1194 | 29.608 |
| bc_v2_g_s1 | 7.970 | 0.0654 | 19.663 | 57.836 | 0.2915 | 0.0653 | 85.453 |
| bc_v2_h_s1 | 7.366 | 0.0597 | 21.610 | 48.743 | 0.3697 | 0.0776 | 77.717 |

## §8 dual-distribution gates (PASS/FAIL per clause)

Clauses (ALL must pass): `tv_median` teacher-val median <= 6.5deg; `tv_magerr` teacher-val mean |mag err| <= 0.06; `tv_sat` no saturation regression (~0); `ho_median` holdout median <= 30deg; `ho_cos_pos` holdout cosine > 0 in every risk stratum; `ho_risk_hi` holdout risk>=0.5 medians <= 35deg.

| variant | tv_median | tv_magerr | tv_sat | ho_median | ho_cos_pos | ho_risk_hi | QUALIFIES |
|---|---|---|---|---|---|---|---|
| bc_v1_s1_full | 4.801 [PASS] | 0.0517 [PASS] | 0.0000 [PASS] | 71.504 [FAIL] | 0.00-0.25=0.1878, 0.25-0.50=0.1864, 0.50-0.75=-0.0465, 0.75-inf=-0.1975 [FAIL] | 0.50-0.75=94.171, 0.75-inf=112.041 [FAIL] | **FAIL** |
| bc_v2_f_s1 | 8.734 [FAIL] | 0.0831 [FAIL] | 0.0002 [PASS] | 25.488 [PASS] | 0.00-0.25=0.6912, 0.25-0.50=0.6507, 0.50-0.75=0.6435, 0.75-inf=0.5661 [PASS] | 0.50-0.75=29.608, 0.75-inf=38.851 [FAIL] | **FAIL** |
| bc_v2_g_s1 | 7.970 [FAIL] | 0.0654 [FAIL] | 0.0000 [PASS] | 57.836 [FAIL] | 0.00-0.25=0.3309, 0.25-0.50=0.2708, 0.50-0.75=0.0434, 0.75-inf=-0.1429 [FAIL] | 0.50-0.75=85.453, 0.75-inf=109.141 [FAIL] | **FAIL** |
| bc_v2_h_s1 | 7.366 [FAIL] | 0.0597 [PASS] | 0.0001 [PASS] | 48.743 [FAIL] | 0.00-0.25=0.4164, 0.25-0.50=0.3133, 0.50-0.75=0.1059, 0.75-inf=-0.0903 [FAIL] | 0.50-0.75=77.717, 0.75-inf=103.167 [FAIL] | **FAIL** |

## Teacher-val overall (frozen combat_obs_v1 val split)

| variant | n | val_loss | median deg | mean deg | cosine | \|mag err\| | sat frac |
|---|---|---|---|---|---|---|---|
| bc_v1_s1_full | 81790 | 0.0981 | 4.801 | 13.726 | 0.9037 | 0.0517 | 0.0000 |
| bc_v2_f_s1 | 81790 | 0.1382 | 8.734 | 18.778 | 0.8704 | 0.0831 | 0.0002 |
| bc_v2_g_s1 | 81790 | 0.1138 | 7.970 | 16.567 | 0.8916 | 0.0654 | 0.0000 |
| bc_v2_h_s1 | 81790 | 0.1201 | 7.366 | 16.930 | 0.8845 | 0.0597 | 0.0001 |

## Dagger-holdout overall (student-visited distribution)

| variant | n | median deg | mean deg | cosine | \|mag err\| |
|---|---|---|---|---|---|
| bc_v1_s1_full | 7887 | 71.504 | 77.774 | 0.1610 | 0.0403 |
| bc_v2_f_s1 | 7887 | 25.488 | 38.106 | 0.6801 | 0.1194 |
| bc_v2_g_s1 | 7887 | 57.836 | 67.917 | 0.2915 | 0.0653 |
| bc_v2_h_s1 | 7887 | 48.743 | 62.085 | 0.3697 | 0.0776 |

## Teacher-val by risk stratum (median deg)

| variant | 0.00-0.25 | 0.25-0.50 | 0.50-0.75 | 0.75-inf |
|---|---|---|---|---|
| bc_v1_s1_full | 4.551 | 6.024 | 18.213 | 30.984 |
| bc_v2_f_s1 | 8.250 | 11.618 | 24.658 | 42.528 |
| bc_v2_g_s1 | 7.784 | 8.215 | 19.663 | 34.062 |
| bc_v2_h_s1 | 7.056 | 8.809 | 21.610 | 35.393 |

## Dagger-holdout by risk stratum (median deg)

| variant | 0.00-0.25 | 0.25-0.50 | 0.50-0.75 | 0.75-inf |
|---|---|---|---|---|
| bc_v1_s1_full | 69.144 | 68.117 | 94.171 | 112.041 |
| bc_v2_f_s1 | 23.873 | 29.846 | 29.608 | 38.851 |
| bc_v2_g_s1 | 53.809 | 59.671 | 85.453 | 109.141 |
| bc_v2_h_s1 | 43.791 | 56.595 | 77.717 | 103.167 |

## Teacher-val by wave band (median deg)

| variant | 1-5 | 6-10 | 11-15 | 16-19 | 20 |
|---|---|---|---|---|---|
| bc_v1_s1_full | 3.368 | 3.920 | 4.735 | 7.118 | 18.251 |
| bc_v2_f_s1 | 6.023 | 7.550 | 9.053 | 12.607 | 19.018 |
| bc_v2_g_s1 | 5.355 | 7.085 | 7.989 | 11.002 | 21.248 |
| bc_v2_h_s1 | 5.293 | 6.210 | 7.505 | 11.046 | 14.800 |

## Dagger-holdout by wave band (median deg)

| variant | 1-5 | 6-10 | 11-15 | 16-19 | 20 |
|---|---|---|---|---|---|
| bc_v1_s1_full | 59.014 | 69.121 | 77.763 | 91.353 | 51.713 |
| bc_v2_f_s1 | 23.463 | 24.120 | 26.122 | 28.953 | 24.513 |
| bc_v2_g_s1 | 48.879 | 55.125 | 63.592 | 75.710 | 44.301 |
| bc_v2_h_s1 | 44.598 | 47.608 | 50.854 | 60.093 | 45.589 |

## Training wall times (from registries)

| variant | epochs_run | best_epoch | wall_time_sec |
|---|---|---|---|
| bc_v1_s1_full | 28 | 22 | 67.0 |
| bc_v2_f_s1 | 19 | 13 | 44.0 |
| bc_v2_g_s1 | 4 | 0 | 19.4 |
| bc_v2_h_s1 | 14 | 8 | 38.6 |

No anomalies.

