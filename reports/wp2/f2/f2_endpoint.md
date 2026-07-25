# WP2 Stage F2 -- primary endpoint (hierarchical run outcome)

- Arm T: **T (pure teacher)** (20 runs)
- Arm P: **P (deterministic pi4, residual-teacher-base control 14.3)** (20 runs)
- Endpoint: Hierarchical run outcome: victory > combat progress (completed waves + fraction of death wave) > alive-and-healthy AUC. Primary statistic = P(random P run outranks random T run), ties 0.5, with a 95% percentile CI from a run-level cluster bootstrap. Ticks are never units of analysis.
- Bootstrap: 10000 run-level resamples, seed 0, 2.5/97.5 percentile CI. No significance tests.

## Primary statistic

| statistic | value |
|---|---|
| P(P outranks T) | **0.4500** [0.2725, 0.6350] |
| CI vs 0.5 | straddles 0.5 |
| direction | T favored |
| pairs | 400 (20 P x 20 T) |

## Secondaries (non-gating)

| metric | T (pure teacher) | P (deterministic pi4) |
|---|---|---|
| n_runs | 20 | 20 |
| victory_rate | 0.5000 | 0.3500 |
| n_victories | 10 | 7 |
| final_wave (mean) | 18.700 | 18.950 |
| final_wave (median) | 20.000 | 20.000 |
| combat_progress (mean) | 19.0528 | 19.0622 |
| auc_norm (mean) | 0.9046 | 0.9121 |

## Per-run outcome tuples

| arm | run | result | final_wave | combat_progress | auc_norm | death_wave_ticks | expected_ticks | frac | combat_time_s | horizon_s |
|---|---|---|---|---|---|---|---|---|---|---|
| P | run_1784953695_36698 | victory | 20 | 21.0000 | 0.9916 | 1260 | n/a | n/a | 1064.9 | 1064.9 |
| P | run_1784956164_5478 | victory | 20 | 21.0000 | 0.9925 | 860 | n/a | n/a | 1042.6 | 1042.6 |
| P | run_1784957443_38720 | victory | 20 | 21.0000 | 0.9985 | 1800 | n/a | n/a | 1091.7 | 1091.7 |
| P | run_1784967186_41673 | victory | 20 | 21.0000 | 0.9923 | 986 | n/a | n/a | 1050.4 | 1050.4 |
| P | run_1784970850_46428 | victory | 20 | 21.0000 | 0.9909 | 1800 | n/a | n/a | 1090.4 | 1090.4 |
| P | run_1784973259_91857 | victory | 20 | 21.0000 | 0.9910 | 1572 | n/a | n/a | 1080.3 | 1080.3 |
| P | run_1784974498_75496 | victory | 20 | 21.0000 | 0.9865 | 1040 | n/a | n/a | 1052.6 | 1052.6 |
| P | run_1784961547_58546 | defeat | 20 | 20.0000 | 0.9864 | 1364 | 1273.0 | 1.0000 | 1068.9 | 1068.9 |
| P | run_1784946938_72738 | defeat | 20 | 19.7101 | 0.9625 | 904 | 1273.0 | 0.7101 | 1045.5 | 1064.9 |
| P | run_1784979286_89292 | defeat | 20 | 19.4682 | 0.9549 | 596 | 1273.0 | 0.4682 | 1029.6 | 1064.9 |
| P | run_1784978117_43366 | defeat | 20 | 19.4438 | 0.9507 | 565 | 1273.0 | 0.4438 | 1027.0 | 1064.9 |
| P | run_1784950784_87944 | defeat | 20 | 19.3747 | 0.9590 | 477 | 1273.0 | 0.3747 | 1025.2 | 1064.9 |
| P | run_1784965010_89007 | defeat | 20 | 19.3700 | 0.9467 | 471 | 1273.0 | 0.3700 | 1024.2 | 1064.9 |
| P | run_1784985808_57093 | defeat | 19 | 18.9525 | 0.9246 | 1182 | 1241.0 | 0.9525 | 996.8 | 1064.9 |
| P | run_1784982683_96483 | defeat | 19 | 18.8783 | 0.9230 | 1090 | 1241.0 | 0.8783 | 991.6 | 1064.9 |
| P | run_1784989339_73647 | defeat | 19 | 18.7510 | 0.9006 | 932 | 1241.0 | 0.7510 | 983.3 | 1064.9 |
| P | run_1784949300_58273 | defeat | 17 | 16.7916 | 0.8076 | 986 | 1245.5 | 0.7916 | 862.8 | 1064.9 |
| P | run_1784984822_87528 | defeat | 17 | 16.4994 | 0.7728 | 622 | 1245.5 | 0.4994 | 844.3 | 1064.9 |
| P | run_1784964012_68941 | defeat | 17 | 16.3348 | 0.7654 | 417 | 1245.5 | 0.3348 | 832.7 | 1064.9 |
| P | run_1784991168_34635 | defeat | 11 | 10.6685 | 0.4434 | 833 | 1246.0 | 0.6685 | 482.0 | 1064.9 |
| T | run_1784948107_34039 | victory | 20 | 21.0000 | 0.9995 | 735 | n/a | n/a | 1038.5 | 1038.5 |
| T | run_1784954925_96458 | victory | 20 | 21.0000 | 0.9942 | 1614 | n/a | n/a | 1082.1 | 1082.1 |
| T | run_1784962766_94914 | victory | 20 | 21.0000 | 0.9960 | 1800 | n/a | n/a | 1089.6 | 1089.6 |
| T | run_1784968385_22836 | victory | 20 | 21.0000 | 0.9792 | 1361 | n/a | n/a | 1066.8 | 1066.8 |
| T | run_1784969600_14272 | victory | 20 | 21.0000 | 0.9893 | 1273 | n/a | n/a | 1063.0 | 1063.0 |
| T | run_1784972087_51182 | victory | 20 | 21.0000 | 0.9967 | 328 | n/a | n/a | 1016.4 | 1016.4 |
| T | run_1784976889_60009 | victory | 20 | 21.0000 | 0.9708 | 1622 | n/a | n/a | 1082.7 | 1082.7 |
| T | run_1784980475_23728 | victory | 20 | 21.0000 | 0.9926 | 1474 | n/a | n/a | 1075.4 | 1075.4 |
| T | run_1784986939_57689 | victory | 20 | 21.0000 | 0.9827 | 684 | n/a | n/a | 1034.0 | 1034.0 |
| T | run_1784988115_41438 | victory | 20 | 21.0000 | 0.9903 | 1037 | n/a | n/a | 1053.2 | 1053.2 |
| T | run_1784945653_24977 | defeat | 20 | 19.9678 | 0.9756 | 1232 | 1273.0 | 0.9678 | 1063.2 | 1064.9 |
| T | run_1784960335_93344 | defeat | 20 | 19.4878 | 0.9643 | 621 | 1273.0 | 0.4878 | 1033.0 | 1064.9 |
| T | run_1784975722_8937 | defeat | 20 | 19.4375 | 0.9487 | 557 | 1273.0 | 0.4375 | 1027.0 | 1064.9 |
| T | run_1784959155_91786 | defeat | 20 | 19.4038 | 0.9612 | 514 | 1273.0 | 0.4038 | 1027.4 | 1064.9 |
| T | run_1784952710_62975 | defeat | 17 | 16.8832 | 0.8142 | 1100 | 1245.5 | 0.8832 | 869.4 | 1064.9 |
| T | run_1784983826_28269 | defeat | 17 | 16.8784 | 0.8041 | 1094 | 1245.5 | 0.8784 | 870.2 | 1064.9 |
| T | run_1784981684_28595 | defeat | 17 | 16.7411 | 0.8026 | 923 | 1245.5 | 0.7411 | 859.4 | 1064.9 |
| T | run_1784966179_70477 | defeat | 17 | 16.7025 | 0.7866 | 875 | 1245.5 | 0.7025 | 858.5 | 1064.9 |
| T | run_1784990448_88332 | defeat | 13 | 12.8234 | 0.5700 | 1026 | 1246.0 | 0.8234 | 616.7 | 1064.9 |
| T | run_1784952010_30146 | defeat | 13 | 12.7311 | 0.5727 | 911 | 1246.0 | 0.7311 | 611.2 | 1064.9 |

## Estimators (invocation-scoped, arm-blind)

Estimators are invocation-scoped and pooled over both arms (arm-blind). expected_ticks falls back to the max observed count for waves no run completed; reference_full_duration falls back to the longest observed combat time when no run is a victory.

- reference_full_duration = 1064.9 s (median_victory_duration, 17 victories)
- dt clamp = 1000 ms; horizon = 20 waves

| wave | expected_ticks | source | n_completers | n_observers |
|---|---|---|---|---|
| 1 | 440.0 | median_of_completers | 40 | 40 |
| 2 | 546.0 | median_of_completers | 40 | 40 |
| 3 | 640.0 | median_of_completers | 40 | 40 |
| 4 | 741.0 | median_of_completers | 40 | 40 |
| 5 | 846.0 | median_of_completers | 40 | 40 |
| 6 | 940.5 | median_of_completers | 40 | 40 |
| 7 | 1045.0 | median_of_completers | 40 | 40 |
| 8 | 1146.0 | median_of_completers | 40 | 40 |
| 9 | 1251.0 | median_of_completers | 40 | 40 |
| 10 | 1246.0 | median_of_completers | 40 | 40 |
| 11 | 1246.0 | median_of_completers | 39 | 40 |
| 12 | 1246.0 | median_of_completers | 39 | 39 |
| 13 | 1246.0 | median_of_completers | 37 | 39 |
| 14 | 1245.0 | median_of_completers | 37 | 37 |
| 15 | 1246.0 | median_of_completers | 37 | 37 |
| 16 | 1246.0 | median_of_completers | 37 | 37 |
| 17 | 1245.5 | median_of_completers | 30 | 37 |
| 18 | 1241.0 | median_of_completers | 30 | 30 |
| 19 | 1241.0 | median_of_completers | 27 | 30 |
| 20 | 1273.0 | median_of_completers | 17 | 27 |
