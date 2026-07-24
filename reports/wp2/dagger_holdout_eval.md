# WP2 DAgger-holdout offline evaluation (Case A)

Generated 2026-07-24 15:25:14 - device `cuda` - mag_eps 0.01. Findings only.

Case A = student-visited deployment distribution: the deterministic 10% dagger holdout (seed 20260724, frac 0.1), excluded from training of both bc_v2 candidates. Label = teacher.action (dataset action label). Each model standardized with its own normalization manifest (bc_v1 -> own; bc_v2_a/bc_v2_b -> composite-train).

Holdout rows: n = 7887 (expected 7887, registry n_dagger_holdout 7887).

Split reproduction: holdout aux_damage base rate 0.019334188 (registry 0.019334188), aux_margin mean 0.761300862 (registry 0.761300862) -> reproduces training split: True.

## Overall (all holdout rows)

| entry | n | median ang deg | mean ang deg | mean cosine | mean |mag err| |
|---|---|---|---|---|---|
| bc_v1_s1_full | 7887 | 71.504 | 77.774 | 0.1610 | 0.0403 |
| bc_v2_a_s1 | 7887 | 19.196 | 29.183 | 0.7878 | 0.1482 |
| bc_v2_b_s1 | 7887 | 20.827 | 32.160 | 0.7525 | 0.1550 |
| copy_previous (baseline) | 7887 | 74.565 | 79.652 | 0.1357 | 0.0248 |
| mean_direction (baseline) | 7887 | 81.298 | 84.877 | 0.0680 | 0.0000 |

## By risk stratum

### risk 0.00-0.25 (n=6233)

| entry | n | median ang deg | mean ang deg | mean cosine | mean |mag err| |
|---|---|---|---|---|---|
| bc_v1_s1_full | 6233 | 69.144 | 75.547 | 0.1878 | 0.0406 |
| bc_v2_a_s1 | 6233 | 18.082 | 27.859 | 0.8012 | 0.1411 |
| bc_v2_b_s1 | 6233 | 19.676 | 30.792 | 0.7662 | 0.1469 |
| copy_previous (baseline) | 6233 | 72.307 | 77.661 | 0.1594 | 0.0252 |
| mean_direction (baseline) | 6233 | 79.508 | 84.041 | 0.0789 | 0.0000 |

### risk 0.25-0.50 (n=880)

| entry | n | median ang deg | mean ang deg | mean cosine | mean |mag err| |
|---|---|---|---|---|---|
| bc_v1_s1_full | 880 | 68.117 | 76.861 | 0.1864 | 0.0379 |
| bc_v2_a_s1 | 880 | 22.034 | 33.421 | 0.7461 | 0.1670 |
| bc_v2_b_s1 | 880 | 25.019 | 37.054 | 0.7050 | 0.1778 |
| copy_previous (baseline) | 880 | 69.648 | 77.921 | 0.1722 | 0.0242 |
| mean_direction (baseline) | 880 | 86.925 | 88.058 | 0.0266 | 0.0000 |

### risk 0.50-0.75 (n=583)

| entry | n | median ang deg | mean ang deg | mean cosine | mean |mag err| |
|---|---|---|---|---|---|
| bc_v1_s1_full | 583 | 94.171 | 94.109 | -0.0465 | 0.0406 |
| bc_v2_a_s1 | 583 | 23.041 | 32.967 | 0.7515 | 0.1803 |
| bc_v2_b_s1 | 583 | 24.077 | 35.698 | 0.7187 | 0.1880 |
| copy_previous (baseline) | 583 | 95.124 | 95.241 | -0.0625 | 0.0233 |
| mean_direction (baseline) | 583 | 86.925 | 87.315 | 0.0358 | 0.0000 |

### risk 0.75-inf (n=191)

| entry | n | median ang deg | mean ang deg | mean cosine | mean |mag err| |
|---|---|---|---|---|---|
| bc_v1_s1_full | 191 | 112.041 | 104.803 | -0.1975 | 0.0404 |
| bc_v2_a_s1 | 191 | 29.954 | 41.293 | 0.6532 | 0.1966 |
| bc_v2_b_s1 | 191 | 33.395 | 43.452 | 0.6252 | 0.2107 |
| copy_previous (baseline) | 191 | 111.696 | 105.040 | -0.2013 | 0.0182 |
| mean_direction (baseline) | 191 | 93.075 | 90.041 | 0.0011 | 0.0000 |

## By wave band

### wave 1-5 (n=1645)

| entry | n | median ang deg | mean ang deg | mean cosine | mean |mag err| |
|---|---|---|---|---|---|
| bc_v1_s1_full | 1645 | 59.014 | 70.063 | 0.2632 | 0.0376 |
| bc_v2_a_s1 | 1645 | 17.557 | 28.484 | 0.7890 | 0.1332 |
| bc_v2_b_s1 | 1645 | 18.440 | 31.029 | 0.7560 | 0.1272 |
| copy_previous (baseline) | 1645 | 62.887 | 72.329 | 0.2332 | 0.0268 |
| mean_direction (baseline) | 1645 | 72.060 | 78.799 | 0.1529 | 0.0000 |

### wave 6-10 (n=2833)

| entry | n | median ang deg | mean ang deg | mean cosine | mean |mag err| |
|---|---|---|---|---|---|
| bc_v1_s1_full | 2833 | 69.121 | 75.520 | 0.1931 | 0.0386 |
| bc_v2_a_s1 | 2833 | 18.234 | 28.581 | 0.7939 | 0.1430 |
| bc_v2_b_s1 | 2833 | 20.507 | 32.026 | 0.7528 | 0.1508 |
| copy_previous (baseline) | 2833 | 71.499 | 77.351 | 0.1686 | 0.0236 |
| mean_direction (baseline) | 2833 | 81.527 | 83.983 | 0.0783 | 0.0000 |

### wave 11-15 (n=2355)

| entry | n | median ang deg | mean ang deg | mean cosine | mean |mag err| |
|---|---|---|---|---|---|
| bc_v1_s1_full | 2355 | 77.763 | 80.489 | 0.1221 | 0.0404 |
| bc_v2_a_s1 | 2355 | 19.376 | 28.649 | 0.7975 | 0.1535 |
| bc_v2_b_s1 | 2355 | 21.033 | 31.496 | 0.7655 | 0.1628 |
| copy_previous (baseline) | 2355 | 80.307 | 82.619 | 0.0930 | 0.0242 |
| mean_direction (baseline) | 2355 | 79.900 | 84.351 | 0.0759 | 0.0000 |

### wave 16-19 (n=968)

| entry | n | median ang deg | mean ang deg | mean cosine | mean |mag err| |
|---|---|---|---|---|---|
| bc_v1_s1_full | 968 | 91.353 | 91.672 | -0.0233 | 0.0487 |
| bc_v2_a_s1 | 968 | 22.896 | 33.029 | 0.7487 | 0.1746 |
| bc_v2_b_s1 | 968 | 25.212 | 35.925 | 0.7163 | 0.1958 |
| copy_previous (baseline) | 968 | 93.266 | 92.608 | -0.0358 | 0.0254 |
| mean_direction (baseline) | 968 | 101.925 | 97.534 | -0.1045 | 0.0000 |

### wave 20 (n=86)

| entry | n | median ang deg | mean ang deg | mean cosine | mean |mag err| |
|---|---|---|---|---|---|
| bc_v1_s1_full | 86 | 51.713 | 68.742 | 0.2890 | 0.0501 |
| bc_v2_a_s1 | 86 | 25.301 | 33.710 | 0.7371 | 0.1639 |
| bc_v2_b_s1 | 86 | 21.070 | 34.031 | 0.7239 | 0.1493 |
| copy_previous (baseline) | 86 | 54.756 | 68.471 | 0.2877 | 0.0311 |
| mean_direction (baseline) | 86 | 108.075 | 102.506 | -0.1637 | 0.0000 |

## Checkpoint provenance (sha256 verified against registry)

| model | checkpoint | sha256 | normalization manifest hash |
|---|---|---|---|
| bc_v1_s1_full | `best.pt` | `BE7E82326EC8A424...` | `FD3C55F62F210A65...` |
| bc_v2_a_s1 | `best.pt` | `6D49095BD44CACE9...` | `3BEC515CE33D71CB...` |
| bc_v2_b_s1 | `best.pt` | `B261BF65CA8A75A5...` | `3BEC515CE33D71CB...` |

No anomalies.

