# WP2 Stage F Phase 2 -- residual checkpoint comparison

- Learned arm: **residual-teacher-base control (14.3)** (7 runs)
- Control arm: **Phase-1 uniform random probe (matched theta bound)** (6 runs)
- Sign convention: learned - control; damage rates negative => learned better; final_wave/victory positive => learned better
- Bootstrap: 10000 resamples, seed 0, 2.5/97.5 percentile CIs. No significance tests.

- Damage accounting: PRIMARY = full combat_capture stream, unfiltered (every hp drop between consecutive captures, heal-clamped, normalized by pre-drop max_hp, attributed to the pre-drop capture's wave band / risk stratum; tick denominator = all captures). SECONDARY 'rl_usable_view' = the replay-usability-filtered RL-training view (valid student tick, 2s recovery exclusion, contiguous seq); it undercounts damage in recovery-heavy runs and is a diagnostic only.

## Per-run table (PRIMARY = full capture stream)

### Learned

| run | final_wave | victory | captures | full_dmg_rate | w20_rate | risk>=0.5_rate | capture_drop | player_damage | mismatch | rl_usable_rate |
|---|---|---|---|---|---|---|---|---|---|---|
| run_1784910686_39423 | 17 | 0 | 17077 | 0.00021 | n/a | 0.00476 | 156 | 157 (11) | no | 0.00020 |
| run_1784911798_60074 | 19 | 0 | 19937 | 0.00013 | n/a | 0.00349 | 135 | 136 (9) | no | 0.00011 |
| run_1784912900_14544 | 13 | 0 | 12519 | 0.00020 | n/a | 0.00382 | 114 | 116 (15) | no | 0.00019 |
| run_1784913937_22390 | 20 | 1 | 20825 | 0.00006 | 0.00161 | 0.00000 | 75 | 76 (4) | no | 0.00006 |
| run_1784915512_76287 | 20 | 1 | 21855 | 0.00009 | 0.00049 | 0.00129 | 107 | 107 (7) | no | 0.00009 |
| run_1784916694_13543 | 20 | 1 | 21417 | 0.00012 | 0.00045 | 0.00111 | 135 | 135 (17) | no | 0.00007 |
| run_1784917880_11008 | 20 | 1 | 21052 | 0.00002 | 0.00026 | 0.00046 | 22 | 22 (2) | no | 0.00002 |

### Control

| run | final_wave | victory | captures | full_dmg_rate | w20_rate | risk>=0.5_rate | capture_drop | player_damage | mismatch | rl_usable_rate |
|---|---|---|---|---|---|---|---|---|---|---|
| run_1784890075_95641 | 15 | 0 | 14704 | 0.00015 | n/a | 0.00345 | 109 | 109 (11) | no | 0.00015 |
| run_1784891038_60320 | 20 | 1 | 20851 | 0.00002 | 0.00000 | 0.00000 | 18 | 18 (5) | no | 0.00000 |
| run_1784892185_3194 | 19 | 0 | 19751 | 0.00011 | n/a | 0.00290 | 131 | 132 (11) | no | 0.00008 |
| run_1784893276_88958 | 15 | 0 | 14803 | 0.00006 | n/a | 0.00209 | 45 | 45 (5) | no | 0.00006 |
| run_1784894100_69759 | 20 | 0 | 20633 | 0.00009 | 0.00246 | 0.00216 | 87 | 87 (8) | no | 0.00009 |
| run_1784895219_19972 | 20 | 1 | 20579 | 0.00005 | 0.00084 | 0.00075 | 37 | 37 (5) | no | 0.00004 |

### Damage source cross-check

Per-run capture hp-drop sum vs the mod's player_damage event sum; mismatch flagged if |delta| > 5 hp.

All runs agree within 5 hp between the capture hp-drop sum and the mod's player_damage events.

## Arm summaries (point [CI])

| metric | learned | control |
|---|---|---|
| final_wave (mean) | 18.429 [16.429, 19.857] | 18.167 [16.500, 19.833] |
| final_wave (median) | 20.000 [17.000, 20.000] | 19.500 [15.000, 20.000] |
| victory_rate | 0.571 [0.143, 0.857] | 0.333 [0.000, 0.667] |
| dmg_rate overall (mean) | 0.00012 [0.00007, 0.00016] | 0.00008 [0.00005, 0.00011] |
| dmg_rate wave20 (mean) | 0.00070 [0.00032, 0.00132] | 0.00110 [0.00000, 0.00246] |
| dmg_rate risk>=0.5 (mean) | 0.00213 [0.00088, 0.00343] | 0.00189 [0.00095, 0.00281] |
| _rl_usable dmg_rate (mean, diagnostic)_ | 0.00011 [0.00006, 0.00015] | 0.00007 [0.00004, 0.00011] |

### Damage rate by wave band (mean [CI])

| band | learned | control |
|---|---|---|
| 1-5 | 0.00000 [0.00000, 0.00001] | 0.00000 [0.00000, 0.00001] |
| 6-10 | 0.00002 [0.00000, 0.00005] | 0.00003 [0.00001, 0.00005] |
| 11-15 | 0.00015 [0.00004, 0.00029] | 0.00008 [0.00001, 0.00017] |
| 16-19 | 0.00028 [0.00004, 0.00057] | 0.00015 [0.00003, 0.00036] |
| 20 | 0.00070 [0.00032, 0.00132] | 0.00110 [0.00000, 0.00246] |

### Damage rate by risk stratum (mean [CI])

| stratum | learned | control |
|---|---|---|
| 0.00-0.25 | 0.00002 [0.00000, 0.00004] | 0.00001 [0.00000, 0.00002] |
| 0.25-0.50 | 0.00000 [0.00000, 0.00000] | 0.00000 [0.00000, 0.00000] |
| 0.50-0.75 | 0.00091 [0.00028, 0.00164] | 0.00057 [0.00024, 0.00089] |
| 0.75-inf | 0.01020 [0.00481, 0.01696] | 0.01352 [0.00708, 0.01930] |

## Differences (learned - control, mean [CI])

| metric | diff [CI] |
|---|---|
| final_wave | 0.262 [-2.405, 2.762] [straddles 0] |
| victory_rate | 0.238 [-0.262, 0.714] [straddles 0] |
| dmg_rate overall | 0.00004 [-0.00002, 0.00010] [straddles 0] |
| dmg_rate wave20 | -0.00039 [-0.00171, 0.00076] [straddles 0] |
| dmg_rate risk>=0.5 | 0.00024 [-0.00135, 0.00187] [straddles 0] |
| dmg_rate band 1-5 | 0.00000 [-0.00000, 0.00001] [straddles 0] |
| dmg_rate band 6-10 | -0.00001 [-0.00004, 0.00003] [straddles 0] |
| dmg_rate band 11-15 | 0.00006 [-0.00008, 0.00022] [straddles 0] |
| dmg_rate band 16-19 | 0.00013 [-0.00018, 0.00047] [straddles 0] |
| dmg_rate band 20 | -0.00039 [-0.00170, 0.00076] [straddles 0] |
| dmg_rate risk 0.00-0.25 | 0.00001 [-0.00001, 0.00003] [straddles 0] |
| dmg_rate risk 0.25-0.50 | 0.00000 [0.00000, 0.00000] [straddles 0] |
| dmg_rate risk 0.50-0.75 | 0.00035 [-0.00035, 0.00117] [straddles 0] |
| dmg_rate risk 0.75-inf | -0.00332 [-0.01151, 0.00587] [straddles 0] |

## Checkpoint summary (predeclared decision surface)

Predeclared surface (FULL capture-stream damage): overall + wave-20 + risk>=0.5 learned-minus-control differences (normalized damage rate). NEGATIVE damage diff => learned takes less damage. Emitted, not adjudicated.

| highlighted diff | value [CI] |
|---|---|
| overall dmg_rate | 0.00004 [-0.00002, 0.00010] [straddles 0] |
| wave-20 dmg_rate | -0.00039 [-0.00171, 0.00076] [straddles 0] |
| risk>=0.5 dmg_rate | 0.00024 [-0.00135, 0.00187] [straddles 0] |
| final_wave | 0.262 [-2.405, 2.762] [straddles 0] |
| victory_rate | 0.238 [-0.262, 0.714] [straddles 0] |
