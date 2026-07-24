# WP2 bc_v2 round-2 sweep -- offline evaluation (frontier)

Generated 2026-07-24 15:36:09 - device `cuda` - mag_eps 0.01. Findings only, no promotion recommendation.

Two distributions: (a) teacher-val = frozen `combat_obs_v1` val split (81790 rows) via the unchanged `bc_offline.evaluate_run` path (each model's own normalization manifest); (b) dagger-holdout = the deterministic 10% `combat_dagger_r1` holdout (n=7887, seed 20260724), excluded from all bc_v2 training, label = teacher.action.

Split reproduction: holdout aux_damage base rate 0.019334188 (registry 0.019334188), aux_margin mean 0.761300862 (registry 0.761300862) -> reproduces training split: True.

## Sweep configuration

| variant | corrective mass | prev-action dropout | lambda_mag | note |
|---|---|---|---|---|
| bc_v1_s1_full | - | 0.1 | 0.5 | no dagger data (teacher-only bc_v1) |
| bc_v2_a_s1 | 0.25 | 0.1 | 0.5 | round-1 candidate A |
| bc_v2_b_s1 | 0.25 | 0.1 | 0.5 | round-1 candidate B (aux heads, base export) |
| bc_v2_c_s1 | 0.10 | 0.1 | 0.5 | round-2 C |
| bc_v2_d_s1 | 0.25 | 0.4 | 0.5 | round-2 D |
| bc_v2_e_s1 | 0.10 | 0.4 | 0.5 | round-2 E |
| bc_v2_f_s1 | 0.15 | 0.4 | 1.0 | round-2 F (magnitude-repair probe) |

## Frontier table (requested)

| variant | tv median deg | tv \|mag err\| | tv risk 0.50-0.75 median | holdout median deg | holdout cosine | holdout \|mag err\| | holdout risk 0.50-0.75 median |
|---|---|---|---|---|---|---|---|
| bc_v1_s1_full | 4.801 | 0.0517 | 18.213 | 71.504 | 0.1610 | 0.0403 | 94.171 |
| bc_v2_a_s1 | 10.147 | 0.1129 | 27.131 | 19.196 | 0.7878 | 0.1482 | 23.041 |
| bc_v2_b_s1 | 9.248 | 0.1119 | 27.449 | 20.827 | 0.7525 | 0.1550 | 24.077 |
| bc_v2_c_s1 | 8.381 | 0.0941 | 21.849 | 36.524 | 0.5118 | 0.1546 | 59.896 |
| bc_v2_d_s1 | 9.687 | 0.1100 | 26.709 | 18.928 | 0.7798 | 0.1517 | 20.257 |
| bc_v2_e_s1 | 8.008 | 0.0863 | 23.590 | 30.477 | 0.5955 | 0.1499 | 43.015 |
| bc_v2_f_s1 | 8.734 | 0.0831 | 24.658 | 25.488 | 0.6801 | 0.1194 | 29.608 |

## Teacher-val overall (frozen combat_obs_v1 val split)

| variant | n | val_loss | median deg | mean deg | cosine | \|mag err\| | sat frac |
|---|---|---|---|---|---|---|---|
| bc_v1_s1_full | 81790 | 0.0981 | 4.801 | 13.726 | 0.9037 | 0.0517 | 0.0000 |
| bc_v2_a_s1 | 81790 | 0.1502 | 10.147 | 20.525 | 0.8571 | 0.1129 | 0.0000 |
| bc_v2_b_s1 | 81790 | 0.1449 | 9.248 | 19.713 | 0.8624 | 0.1119 | 0.0004 |
| bc_v2_c_s1 | 81790 | 0.1288 | 8.381 | 18.176 | 0.8763 | 0.0941 | 0.0000 |
| bc_v2_d_s1 | 81790 | 0.1538 | 9.687 | 20.663 | 0.8533 | 0.1100 | 0.0006 |
| bc_v2_e_s1 | 81790 | 0.1293 | 8.008 | 18.018 | 0.8754 | 0.0863 | 0.0001 |
| bc_v2_f_s1 | 81790 | 0.1382 | 8.734 | 18.778 | 0.8704 | 0.0831 | 0.0002 |

## Dagger-holdout overall (student-visited distribution)

| variant | n | median deg | mean deg | cosine | \|mag err\| |
|---|---|---|---|---|---|
| bc_v1_s1_full | 7887 | 71.504 | 77.774 | 0.1610 | 0.0403 |
| bc_v2_a_s1 | 7887 | 19.196 | 29.183 | 0.7878 | 0.1482 |
| bc_v2_b_s1 | 7887 | 20.827 | 32.160 | 0.7525 | 0.1550 |
| bc_v2_c_s1 | 7887 | 36.524 | 51.294 | 0.5118 | 0.1546 |
| bc_v2_d_s1 | 7887 | 18.928 | 29.712 | 0.7798 | 0.1517 |
| bc_v2_e_s1 | 7887 | 30.477 | 44.774 | 0.5955 | 0.1499 |
| bc_v2_f_s1 | 7887 | 25.488 | 38.106 | 0.6801 | 0.1194 |

## Teacher-val by risk stratum (median deg)

| variant | 0.00-0.25 | 0.25-0.50 | 0.50-0.75 | 0.75-inf |
|---|---|---|---|---|
| bc_v1_s1_full | 4.551 | 6.024 | 18.213 | 30.984 |
| bc_v2_a_s1 | 9.684 | 12.369 | 27.131 | 45.530 |
| bc_v2_b_s1 | 8.795 | 11.724 | 27.449 | 44.001 |
| bc_v2_c_s1 | 8.021 | 9.994 | 21.849 | 34.591 |
| bc_v2_d_s1 | 9.204 | 12.610 | 26.709 | 45.361 |
| bc_v2_e_s1 | 7.570 | 10.712 | 23.590 | 45.463 |
| bc_v2_f_s1 | 8.250 | 11.618 | 24.658 | 42.528 |

## Dagger-holdout by risk stratum (median deg)

| variant | 0.00-0.25 | 0.25-0.50 | 0.50-0.75 | 0.75-inf |
|---|---|---|---|---|
| bc_v1_s1_full | 69.144 | 68.117 | 94.171 | 112.041 |
| bc_v2_a_s1 | 18.082 | 22.034 | 23.041 | 29.954 |
| bc_v2_b_s1 | 19.676 | 25.019 | 24.077 | 33.395 |
| bc_v2_c_s1 | 32.396 | 43.798 | 59.896 | 86.500 |
| bc_v2_d_s1 | 18.164 | 20.747 | 20.257 | 29.843 |
| bc_v2_e_s1 | 28.742 | 33.370 | 43.015 | 49.287 |
| bc_v2_f_s1 | 23.873 | 29.846 | 29.608 | 38.851 |

## Teacher-val by wave band (median deg)

| variant | 1-5 | 6-10 | 11-15 | 16-19 | 20 |
|---|---|---|---|---|---|
| bc_v1_s1_full | 3.368 | 3.920 | 4.735 | 7.118 | 18.251 |
| bc_v2_a_s1 | 7.487 | 9.025 | 10.145 | 13.745 | 19.111 |
| bc_v2_b_s1 | 6.999 | 8.136 | 9.266 | 12.371 | 18.931 |
| bc_v2_c_s1 | 5.711 | 7.191 | 8.589 | 12.314 | 16.344 |
| bc_v2_d_s1 | 6.990 | 8.282 | 9.916 | 13.657 | 22.050 |
| bc_v2_e_s1 | 5.564 | 6.893 | 8.296 | 11.857 | 17.239 |
| bc_v2_f_s1 | 6.023 | 7.550 | 9.053 | 12.607 | 19.018 |

## Dagger-holdout by wave band (median deg)

| variant | 1-5 | 6-10 | 11-15 | 16-19 | 20 |
|---|---|---|---|---|---|
| bc_v1_s1_full | 59.014 | 69.121 | 77.763 | 91.353 | 51.713 |
| bc_v2_a_s1 | 17.557 | 18.234 | 19.376 | 22.896 | 25.301 |
| bc_v2_b_s1 | 18.440 | 20.507 | 21.033 | 25.212 | 21.070 |
| bc_v2_c_s1 | 34.008 | 34.478 | 36.769 | 43.786 | 41.223 |
| bc_v2_d_s1 | 16.712 | 18.260 | 18.719 | 24.871 | 24.735 |
| bc_v2_e_s1 | 31.395 | 29.969 | 29.760 | 31.574 | 30.530 |
| bc_v2_f_s1 | 23.463 | 24.120 | 26.122 | 28.953 | 24.513 |

## Training wall times (from registries)

| variant | epochs_run | best_epoch | wall_time_sec |
|---|---|---|---|
| bc_v1_s1_full | 28 | 22 | 67.0 |
| bc_v2_a_s1 | 23 | 17 | 56.7 |
| bc_v2_b_s1 | 16 | 10 | 55.1 |
| bc_v2_c_s1 | 12 | 6 | 32.9 |
| bc_v2_d_s1 | 24 | 18 | 55.9 |
| bc_v2_e_s1 | 19 | 13 | 46.6 |
| bc_v2_f_s1 | 19 | 13 | 44.0 |

No anomalies.

