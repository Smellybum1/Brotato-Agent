# WP2 Stage F Phase 1 -- residual-probe pilot analysis

- theta_max: 5.0 deg | probe seed run_name: `residual_probe_theta5_seed20260725`
- **Verdict: DEFERRED_TO_PRIMARY (no verdict issued by this analysis)**

## Sign convention (verified from ResidualProbeService)

perp_hat(u)=(-uy,ux)/|u|, the +90deg rotation in the raw action-vector algebra the probe rotates in (R=[[cos,-sin],[sin,cos]], dR/dd@0 maps u->(-uy,ux)); positive delta => positive expected L => sign-consistent effect is a POSITIVE slope. Godot screen y is down so this is visually clockwise; only internal consistency matters.

## 1. Per-run infra audit

| run | conn | smoke | result | last_wave | ctrl_frac | join_cov | probed | eff_samples | errors | hangs | illegal | integrity |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| run_1784890075_95641 | 0 | True | defeat | 15 | 0.9991 | 1.0000 | 14651 | 43140 | 0 | 0 | 0 | True |
| run_1784891038_60320 | 1 | False | victory | 20 | 0.9990 | 1.0000 | 20791 | 61385 | 0 | 0 | 0 | True |
| run_1784892185_3194 | 1 | False | defeat | 19 | 0.9993 | 1.0000 | 19737 | 58322 | 0 | 0 | 0 | True |
| run_1784893276_88958 | 1 | False | defeat | 15 | 0.9987 | 1.0000 | 14784 | 43507 | 0 | 0 | 0 | True |
| run_1784894100_69759 | 1 | False | defeat | 20 | 0.9993 | 1.0000 | 20619 | 60933 | 0 | 0 | 0 | True |
| run_1784895219_19972 | 1 | False | victory | 20 | 0.9992 | 1.0000 | 20562 | 60698 | 0 | 0 | 0 | True |

## 2. Effect estimability

Total effect samples: 327985

### SNR table (through-origin): slope [px/deg] / SNR / n

| k | overall | w1-5 | w6-10 | w11-15 | w16-19 | w20 |
| --- | --- | --- | --- | --- | --- | --- |
| 5 | 0.314/9.60/110395 | 0.333/4.43/18971 | 0.285/4.85/33571 | 0.330/5.62/36459 | 0.274/3.49/19525 | 0.725/3.24/1869 |
| 10 | 0.303/3.39/109595 | 0.425/1.93/18746 | 0.029/0.17/33366 | 0.378/2.36/36209 | 0.435/2.33/19420 | 1.132/1.94/1854 |
| 20 | 0.150/0.74/107995 | 0.778/1.47/18296 | -0.798/-2.10/32956 | 0.395/1.11/35709 | 0.478/1.24/19210 | 2.696/2.02/1824 |

### SNR table (with-intercept): slope [px/deg] / SNR / n

| k | overall | w1-5 | w6-10 | w11-15 | w16-19 | w20 |
| --- | --- | --- | --- | --- | --- | --- |
| 5 | 0.314/9.59/110395 | 0.333/4.43/18971 | 0.285/4.85/33571 | 0.330/5.62/36459 | 0.275/3.49/19525 | 0.710/3.19/1869 |
| 10 | 0.303/3.39/109595 | 0.426/1.93/18746 | 0.028/0.17/33366 | 0.379/2.36/36209 | 0.436/2.34/19420 | 1.065/1.85/1854 |
| 20 | 0.150/0.74/107995 | 0.774/1.46/18296 | -0.799/-2.10/32956 | 0.395/1.11/35709 | 0.481/1.25/19210 | 2.503/1.90/1824 |

Sign-consistent (positive slope) at k<=10 in early+mid bands: through-origin=**True**, with-intercept=**True**

### Naive binned means of L_10 (px) by delta bin (overall)

| delta bin | n | mean L_10 | 95% CI |
| --- | --- | --- | --- |
| [-5,-3) | 21953 | -1.119 | [-2.252, 0.013] |
| [-3,-1) | 21840 | 0.304 | [-0.818, 1.427] |
| [-1,1) | 21873 | 0.606 | [-0.541, 1.753] |
| [1,3) | 21939 | 1.122 | [-0.000, 2.244] |
| [3,5) | 21990 | 1.672 | [0.544, 2.800] |

## 3. Outcome sensitivity vs v122 baseline (NO causal claims)

- victories: probe **2/6** (rate 0.333, Wilson CI [0.097, 0.700]) vs baseline **11/20** (rate 0.550, CI [0.342, 0.742])
- Fisher exact two-sided p = **0.6447**; victory-rate diff -0.217
- last_wave: probe median 19.5 (mean 18.17) vs baseline median 20.0 (mean 18.55); Mann-Whitney U=46.5 p=0.3326; diff -0.38 CI95 [-2.80, 2.03]
- damage (CAVEATED, semantics differ): probe median 66.0 vs baseline median 100.0; MW U=39.0 p=0.2122
  - v122 damage = sum of the safety audit's tracked damage_events amounts; probe damage = sum of raw player_damage.amount. Inclusion semantics differ -- treat damage comparison as caveated/descriptive.
- probe last_waves: [15.0, 20.0, 19.0, 15.0, 20.0, 20.0]

## 4. Support coverage

- probed fraction 0.9993; zero-vector fraction 0.0007 (acts total 111319)

| wave band | probed ticks | mean\|delta\| | min delta | max delta |
| --- | --- | --- | --- | --- |
| w1-5 | 19181 | 2.508 | -5.000 | 4.999 |
| w6-10 | 33765 | 2.504 | -5.000 | 5.000 |
| w11-15 | 36689 | 2.504 | -5.000 | 5.000 |
| w16-19 | 19625 | 2.486 | -5.000 | 5.000 |
| w20 | 1884 | 2.533 | -4.989 | 4.992 |

Risk stratum (nearest-threat distance (px) from enemy/boss/projectile nx,ny: near<=200, mid 200-500, far>500 or no threat.):

| risk stratum | probed ticks | mean\|delta\| |
| --- | --- | --- |
| near(<=200) | 5341 | 2.507 |
| mid(200-500) | 59257 | 2.498 |
| far(>500/none) | 46546 | 2.506 |

## GO criteria (verbatim; verdict deferred to primary)

> GO to Phase 2 requires: sign-consistent displacement effect detectable at k<=10 ticks with |effect| SNR >= 3 in at least the early+mid bands, and no behavioral degradation vs the teacher baseline beyond noise. (design section 3; verdict DELEGATED to primary.)
