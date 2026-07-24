# WP2 M4 paired evaluation: bc_v2_f vs bc_v3_a

Arms are 6v6, collected under identical conditions (same build, danger 0, rails, collector; Brotato RNG is not seed-controllable).

## Task 1 - Verdict

- bc_v2_f last_wave (victory=21): [16, 17, 20, 20, 20, 21] -> median **20.0**, victories **1**
- bc_v3_a last_wave (victory=21): [10, 11, 13, 20, 20, 20] -> median **16.5**, victories **0**

Predeclared rule (verbatim): _Promote bc_v3_a iff median(last_wave) strictly exceeds bc_v2_f's, OR equals it with at least as many victories. Otherwise retain bc_v2_f as the validated live policy; bc_v3_a's runs still enter the round-3 corrective pool. No re-rolls, no post-hoc metric substitution. n=6 is small; the rule is deliberately simple ordering, not significance claims. Primary metric: median last_wave (victory ordered as 21). Secondary: victory count._

**VERDICT: RETAIN bc_v2_f** - v3a median 16.5 vs v2f median 20.0; v3a victories 0 vs v2f 1. v3a neither exceeds nor ties-with-at-least-as-many-victories -> rule retains bc_v2_f.

### 6v6 last_wave table

| # | bc_v2_f run | wave | result | bc_v3_a run | wave | result |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | run_1784872256_15901 | 20 | defeat | run_1784880640_76087 | 13 | defeat |
| 2 | run_1784873462_1600 | 16 | defeat | run_1784882794_20877 | 20 | defeat |
| 3 | run_1784874327_52508 | 20 | defeat | run_1784883926_57395 | 10 | defeat |
| 4 | run_1784875463_98163 | 20 | victory | run_1784884408_98596 | 11 | defeat |
| 5 | run_1784876633_43940 | 17 | defeat | run_1784884958_1046 | 20 | defeat |
| 6 | run_1784877573_54783 | 20 | defeat | run_1784886119_60496 | 20 | defeat |

## Task 1 - Per-run infra audit (all 12)

| arm | run_id | smoke | ctrl_frac | gate>=.95 | lat p50/p99/max | err | hang | illegal | join_cov | recon_ok | infra_pass |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| v2f | run_1784872256_15901 | True | 0.9981 | True | 14.0/20.0/280.0 | 0 | 0 | 0 | 1.0000 | True | True |
| v2f | run_1784873462_1600 | False | 0.9982 | True | 15.0/19.0/239.0 | 0 | 0 | 0 | 1.0000 | True | True |
| v2f | run_1784874327_52508 | False | 0.9980 | True | 15.0/17.0/179.0 | 0 | 0 | 0 | 1.0000 | True | True |
| v2f | run_1784875463_98163 | False | 0.9986 | True | 15.0/18.0/211.0 | 0 | 0 | 0 | 1.0000 | True | True |
| v2f | run_1784876633_43940 | False | 0.9984 | True | 15.0/18.0/197.0 | 0 | 0 | 0 | 1.0000 | True | True |
| v2f | run_1784877573_54783 | False | 0.9981 | True | 15.0/19.0/163.0 | 0 | 0 | 0 | 1.0000 | True | True |
| v3a | run_1784880640_76087 | True | 0.9981 | True | 15.0/17.0/155.0 | 0 | 0 | 0 | 1.0000 | True | True |
| v3a | run_1784882794_20877 | False | 0.9979 | True | 15.0/19.0/204.0 | 0 | 0 | 0 | 1.0000 | True | True |
| v3a | run_1784883926_57395 | False | 0.9981 | True | 15.0/20.0/213.0 | 0 | 0 | 0 | 1.0000 | True | True |
| v3a | run_1784884408_98596 | False | 0.9979 | True | 14.0/19.0/284.0 | 0 | 0 | 0 | 1.0000 | True | True |
| v3a | run_1784884958_1046 | False | 0.9982 | True | 14.0/20.0/294.0 | 0 | 0 | 0 | 1.0000 | True | True |
| v3a | run_1784886119_60496 | False | 0.9983 | True | 15.0/19.0/218.0 | 0 | 0 | 0 | 1.0000 | True | True |

Infra summary: all 12 runs infra_pass = True (control gate, zero faults, reconciliation).

## Task 1 - Caveats

- v2f arm runs are REUSED from the round-2 collection campaign (5 runs + 1 smoke); design sect. 9 records this openly - collection and eval runs are procedurally identical (no interventions, same config).
- n=6 per arm. The verdict rule is a deliberately simple ordering, NOT a significance claim; one bad seed is within campaign variance (bc_v1's own campaign contained a w10).
- Brotato RNG is not seed-controllable, so 'matched' means identical conditions, not identical scenarios - shop/enemy draws differ per run.
- contact_risk is an encoder-derived feature; risk exposure is read from the frozen shards (combat_dagger_r2 for v2f, combat_dagger_r3 for v3a), which encode exactly what the policy saw.
- cos(student,teacher) uses the RAW pre-clamp proposal vs teacher.action; on clamped ticks (~35-40%) renormalization preserves proposal direction, so the cosine is unaffected by clamping.
- Data-integrity cross-check: teacher action mismatches between the capture and student_tick streams across all 12 runs = 0 (expected 0).

## Task 2 - Mechanism analysis

Subgroups: **v2f** (all 6) | **v3a_all** (all 6) | **v3a_good** (w20: 20877/1046/60496) | **v3a_bad** (w13/10/11: 76087/57395/98596).

### Wave band 1-5

| metric | v2f | v3a_all | v3a_good | v3a_bad |
| --- | --- | --- | --- | --- |
| (a) hp_mean | 0.9994 | 0.9992 | 0.9988 | 0.9996 |
| (a) hp frac <0.5 | 0.0 | 0.0 | 0.0 | 0.0 |
| (a) hp frac <0.25 | 0.0 | 0.0 | 0.0 | 0.0 |
| (b) raw |proposal| mean | 0.9998 | 0.981 | 0.981 | 0.981 |
| (b) clamp fraction | 0.4693 | 0.3562 | 0.3431 | 0.3693 |
| (b) student dither deg | 6.806 | 6.514 | 6.466 | 6.562 |
| (b) teacher dither deg | 8.687 | 9.286 | 9.268 | 9.304 |
| (c) risk mean | 0.0621 | 0.0732 | 0.0733 | 0.0731 |
| (c) risk p90 | 0.2783 | 0.3343 | 0.3321 | 0.3367 |
| (c) risk frac >=0.5 | 0.0318 | 0.0468 | 0.0445 | 0.049 |
| (d) cos(student,teacher) | 0.5247 | 0.5526 | 0.5428 | 0.5624 |
| (d) disagree angle med deg | 27.201 | 28.457 | 28.685 | 28.157 |
| ticks (n) | 19313 | 19293 | 9631 | 9662 |

### Wave band 6-10

| metric | v2f | v3a_all | v3a_good | v3a_bad |
| --- | --- | --- | --- | --- |
| (a) hp_mean | 0.9888 | 0.9627 | 0.9821 | 0.9432 |
| (a) hp frac <0.5 | 0.001 | 0.0231 | 0.0005 | 0.0459 |
| (a) hp frac <0.25 | 0.0 | 0.0044 | 0.0 | 0.0088 |
| (b) raw |proposal| mean | 0.9918 | 0.9698 | 0.9744 | 0.9651 |
| (b) clamp fraction | 0.4366 | 0.2953 | 0.3019 | 0.2887 |
| (b) student dither deg | 8.831 | 6.933 | 6.557 | 7.312 |
| (b) teacher dither deg | 10.153 | 11.473 | 11.026 | 11.923 |
| (c) risk mean | 0.1158 | 0.1342 | 0.1229 | 0.1455 |
| (c) risk p90 | 0.4646 | 0.5189 | 0.4925 | 0.5417 |
| (c) risk frac >=0.5 | 0.0844 | 0.1098 | 0.0972 | 0.1225 |
| (d) cos(student,teacher) | 0.3202 | 0.3698 | 0.3829 | 0.3566 |
| (d) disagree angle med deg | 51.964 | 44.807 | 44.411 | 45.189 |
| ticks (n) | 33761 | 33681 | 16901 | 16780 |

### Wave band 11-15

| metric | v2f | v3a_all | v3a_good | v3a_bad |
| --- | --- | --- | --- | --- |
| (a) hp_mean | 0.9497 | 0.9417 | 0.9482 | 0.9155 |
| (a) hp frac <0.5 | 0.0246 | 0.0393 | 0.0296 | 0.0787 |
| (a) hp frac <0.25 | 0.0097 | 0.0067 | 0.0 | 0.034 |
| (b) raw |proposal| mean | 0.9783 | 0.9662 | 0.966 | 0.9672 |
| (b) clamp fraction | 0.4045 | 0.3276 | 0.328 | 0.3261 |
| (b) student dither deg | 17.565 | 12.396 | 13.566 | 7.663 |
| (b) teacher dither deg | 11.323 | 11.482 | 11.518 | 11.334 |
| (c) risk mean | 0.1476 | 0.1348 | 0.1316 | 0.1477 |
| (c) risk p90 | 0.5218 | 0.5082 | 0.4886 | 0.5675 |
| (c) risk frac >=0.5 | 0.1123 | 0.1032 | 0.0947 | 0.1374 |
| (d) cos(student,teacher) | 0.1871 | 0.3166 | 0.3048 | 0.3642 |
| (d) disagree angle med deg | 65.924 | 52.296 | 53.685 | 48.084 |
| ticks (n) | 37331 | 23289 | 18675 | 4614 |

### Wave band 16-20

| metric | v2f | v3a_all | v3a_good | v3a_bad |
| --- | --- | --- | --- | --- |
| (a) hp_mean | 0.9345 | 0.9264 | 0.9264 | - |
| (a) hp frac <0.5 | 0.0354 | 0.0629 | 0.0629 | - |
| (a) hp frac <0.25 | 0.0149 | 0.016 | 0.016 | - |
| (b) raw |proposal| mean | 0.9486 | 0.9748 | 0.9748 | - |
| (b) clamp fraction | 0.3615 | 0.3941 | 0.3941 | - |
| (b) student dither deg | 29.758 | 25.74 | 25.74 | - |
| (b) teacher dither deg | 13.637 | 14.513 | 14.513 | - |
| (c) risk mean | 0.1439 | 0.1389 | 0.1389 | - |
| (c) risk p90 | 0.503 | 0.5129 | 0.5129 | - |
| (c) risk frac >=0.5 | 0.1013 | 0.1074 | 0.1074 | - |
| (d) cos(student,teacher) | 0.1353 | 0.161 | 0.161 | - |
| (d) disagree angle med deg | 73.275 | 70.551 | 70.551 | - |
| ticks (n) | 25981 | 17036 | 17036 | 0 |

## Task 2 - Per-wave hp (damage timing), v3a subgroups

| wave | v2f mean_hp | v2f run_min | v3a_good mean_hp | v3a_good run_min | v3a_bad mean_hp | v3a_bad run_min |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |
| 2 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |
| 3 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |
| 4 | 0.9974 | 0.975 | 0.9957 | 0.9545 | 0.9982 | 0.9545 |
| 5 | 1.0 | 1.0 | 0.9991 | 0.96 | 1.0 | 1.0 |
| 6 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |
| 7 | 0.995 | 0.9792 | 0.9851 | 0.8827 | 0.9903 | 0.8516 |
| 8 | 0.9871 | 0.8984 | 0.9936 | 0.8667 | 0.9635 | 0.7344 |
| 9 | 0.9888 | 0.8493 | 0.9846 | 0.8195 | 0.9348 | 0.7049 |
| 10 | 0.9764 | 0.8065 | 0.9527 | 0.6065 | 0.8476 | 0.2251 |
| 11 | 0.984 | 0.7993 | 0.9373 | 0.6837 | 0.9196 | 0.4056 |
| 12 | 0.9975 | 0.9322 | 1.0 | 1.0 | 0.9726 | 0.6667 |
| 13 | 0.9732 | 0.7143 | 0.9319 | 0.7917 | 0.8416 | 0.0833 |
| 14 | 0.9198 | 0.6028 | 0.9489 | 0.6296 | - | - |
| 15 | 0.8738 | 0.4192 | 0.9232 | 0.5923 | - | - |
| 16 | 0.9548 | 0.6668 | 0.9815 | 0.8667 | - | - |
| 17 | 0.9529 | 0.6411 | 0.9577 | 0.726 | - | - |
| 18 | 0.9718 | 0.7241 | 0.9524 | 0.7368 | - | - |
| 19 | 0.9933 | 0.9273 | 0.9705 | 0.5703 | - | - |
| 20 | 0.6928 | 0.1303 | 0.6479 | 0.1321 | - | - |

## Task 2 - (e) Early-build / RNG confound check

| run_id | arm | subgroup | wave | first purchases (item_id) |
| --- | --- | --- | --- | --- |
| run_1784872256_15901 | v2f | v2f | 1 wpn | w1:shop_reroll; w1:weapon_revolver_1; w1:shop_go; w2:weapon_smg_1; w2:shop_reroll; w2:weapon_revolver_1 |
| run_1784873462_1600 | v2f | v2f | 1 wpn | w1:shop_reroll; w1:weapon_pistol_1; w1:weapon_shredder_1; w1:item_propeller_hat; w1:shop_go; w2:weapon_pistol_1 |
| run_1784874327_52508 | v2f | v2f | 1 wpn | w1:shop_reroll; w1:weapon_smg_1; w1:weapon_pistol_1; w1:item_insanity; w1:item_hedgehog; w1:shop_go |
| run_1784875463_98163 | v2f | v2f | 1 wpn | w1:weapon_revolver_1; w1:item_helmet; w1:shop_go; w2:weapon_laser_gun_1; w2:weapon_shredder_1; w2:shop_go |
| run_1784876633_43940 | v2f | v2f | 1 wpn | w1:weapon_smg_1; w1:item_coffee; w1:shop_go; w2:weapon_smg_1; w2:weapon_revolver_1; w2:item_lootworm |
| run_1784877573_54783 | v2f | v2f | 1 wpn | w1:shop_reroll; w1:weapon_smg_1; w1:item_mushroom; w1:shop_go; w2:weapon_smg_1; w2:weapon_laser_gun_1 |
| run_1784880640_76087 | v3a | bad | 1 wpn | w1:weapon_smg_1; w1:item_mutation; w1:shop_go; w2:weapon_smg_1; w2:item_glasses; w2:item_lootworm |
| run_1784882794_20877 | v3a | good | 1 wpn | w1:weapon_smg_1; w1:shop_go; w2:shop_reroll; w2:weapon_smg_1; w2:shop_reroll; w2:item_coupon |
| run_1784883926_57395 | v3a | bad | 1 wpn | w1:weapon_shredder_1; w1:shop_reroll; w1:weapon_pistol_1; w1:item_gentle_alien; w1:shop_go; w2:weapon_revolver_1 |
| run_1784884408_98596 | v3a | bad | 1 wpn | w1:shop_reroll; w1:weapon_smg_1; w1:shop_go; w2:weapon_smg_1; w2:shop_reroll; w2:shop_reroll |
| run_1784884958_1046 | v3a | good | 1 wpn | w1:weapon_smg_1; w1:weapon_revolver_1; w1:item_lens; w1:item_alien_worm; w1:shop_go; w2:weapon_shredder_1 |
| run_1784886119_60496 | v3a | good | 1 wpn | w1:weapon_double_barrel_shotgun_1; w1:item_mutation; w1:shop_go; w2:shop_reroll; w2:shop_reroll; w2:weapon_pistol_1 |

## Task 2 - Synthesis

- (d) Early-game teacher disagreement: v3a_all cos(student,teacher) 0.5526/0.3698 (bands 1-5/6-10) vs v2f 0.5247/0.3202; disagreement angle median v3a_all 28.457/44.807 deg vs v2f 27.201/51.964 deg.
- (d) Within v3a, bad vs good early cos: bad 0.5624/0.3566 vs good 0.5428/0.3829 (bands 1-5/6-10).
- (c) Risk exposure early (frac ticks contact_risk>=0.5): v3a_bad 0.049/0.1225 vs v3a_good 0.0445/0.0972 vs v2f 0.0318/0.0844 (bands 1-5/6-10).
- (a) Early hp (frac ticks hp<0.5): v3a_bad 0.0/0.0459 vs v3a_good 0.0/0.0005 vs v2f 0.0/0.001.
- (b) Dither (applied-direction change deg, band 6-10): v3a_bad 7.312 vs v3a_good 6.557 vs v2f 8.831; teacher baseline 11.473. Clamp fraction band 6-10: v3a_bad 0.2887 vs v3a_good 0.3019 vs v2f 0.4366.
- 
- CONCLUSION - which hypotheses the data supports:
- SUPPORTED (risk-exposure -> early HP attrition): the fragility signal is spatial. In band 6-10 v3a_bad sits at contact_risk>=0.5 for 0.1225 of ticks (p90 risk 0.5417) vs v3a_good 0.0972 and v2f 0.0844, and this converts to damage: v3a_bad spends 0.0459 of band-6-10 ticks below half hp (0.0088 below quarter) vs v3a_good 0.0005 and v2f 0.001 - a ~45x higher low-hp rate in the SAME band, well before the w10-13 deaths (per-wave hp shows the divergence opening at wave ~8, a compounding attrition spiral, not one catastrophic tick).
- CONTRADICTED (teacher-disagreement): v3a does NOT disagree more with the teacher early - v3a_all cos 0.3698 vs v2f 0.3202 in band 6-10, and v3a AGREES more than v2f in bands 11-15 (0.3166 vs 0.1871) and 16-20. The WINNING arm (v2f) has larger teacher-imitation error - consistent with the design's negative result that offline teacher-error does not predict live outcome.
- CONTRADICTED (hesitation/dither): v3a is SMOOTHER, not more hesitant - lower applied-direction change than v2f in every band (e.g. band 11-15 12.396 vs 17.565 deg) and v3a_bad dithers the LEAST (7.663 deg). Combined with lower raw |proposal| magnitude and lower clamp fraction, v3a moves more sluggishly/committally and less evasively - the plausible driver of the sustained contact-risk exposure above.
- WEAK/INCONCLUSIVE (RNG build confound): early weapon+item draws overlap between v3a good and bad runs (both get standard smg/revolver/pistol/shredder starts and rerolls); the data does not volunteer a build-quality split that would explain the bimodality. At n=3/3 a shop-RNG contribution cannot be fully excluded, but the movement/risk-exposure axis is the consistent signal.
