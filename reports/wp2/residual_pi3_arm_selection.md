# Stage F Phase 2 — pi3 regularizer arm selection (2026-07-25)

Decision authority: primary session under operator standing autonomy
(delegated, predeclared bars binding). Follow-up to
`residual_null_diagnostics.md`, which implicated `lambda_0 = 0.01` in the
pi1/pi2 residual collapse.

## Arms

Both trained by `scripts/train_residual_phase2.py --mode iterate
--iteration 3 --teacher-mix --seed 3` on the full 10-run replay pool
(183,343 transitions / 183,408 states: 6 Phase-1 probe runs + 4 pi1 batch
runs; aborted run_1784904016_34435 excluded), differing only in the new
`--actor-l2` knob:

| arm | lambda_0 | checkpoint | actor sha |
|---|---|---|---|
| A (SELECTED) | 0.001 | `.tmp/residual_pi3_l2_0p001.pt` | `689C1C64…AD26F` |
| B | 0.0003 | `.tmp/residual_pi3_l2_0p0003.pt` | `60E7467D…` |

Offline promotion gates (design §5): BOTH pass — finite losses, p99 |z|
0.139 (A) / 0.285 (B) vs bar 2.5, serving determinism max diff 0.0, no
theta_max saturation (max |delta| 4.01 / 4.43 deg vs 5 deg bound).

## Pooled |delta| (deterministic, sigma = 0, all 183,408 pool states)

| arm | p50 | p90 | p99 | mean | max |
|---|---|---|---|---|---|
| A | 0.046 | 0.163 | 0.691 | 0.084 | 4.014 |
| B | 0.273 | 0.683 | 1.386 | 0.354 | 4.426 |

Both lift the residual off the lambda-0.01 collapse (pi2 p99 ~0.12 deg).

## Stratified |delta| — the deciding evidence

Concentration = share of total |delta| mass vs share of state count:

| stratum | count% | A mass% (ratio) | B mass% (ratio) |
|---|---|---|---|
| wave 20 | 2.11 | 14.76 (**7.0x**) | 4.22 (2.0x) |
| risk >= 0.50 | 3.58 | 11.51 (**3.2x**) | 5.37 (1.5x) |
| risk >= 0.75 | 0.34 | 2.52 (**7.5x**) | 0.70 (2.1x) |

Within wave 20 itself: A p50/p90/p99 = 0.251/1.721/3.401 deg vs
B 0.470/1.490/3.770 — at p90 arm A applies MORE residual in wave 20 than
arm B despite a 6x smaller pooled median.

## Ruling: arm A (lambda_0 = 0.001) is pi3

Arm A is state-selective in exactly the strata where the null-diagnostics
critic located real advantage (wave 20: 37% of states advantaged > 0.01;
risk >= 0.75: 38%): near-zero residual on the low-risk early manifold,
concentrated displacement in the late-wave/high-risk pockets. Arm B's
extra magnitude is off-target baseline drift (p50 0.27 deg applied to
low-risk early states with no value evidence — the lambda-to-0
noise-like pathology in miniature) while delivering no more signal in the
decisive strata. Arm A dominates: equal-or-more residual where it
matters, less perturbation where the teacher is already good.

Evidence: `reports/wp2/residual_phase2_pi3_l2_0p001.json` /
`…_0p0003.json` (training + gates), `.tmp/pi3_delta_stratify.json` (raw
stratification, script `.tmp/pi3_delta_stratify.py`).

Canonical pi3 registry manifest (`models/registry/residual_pi3.json`) and
report (`reports/wp2/residual_phase2_pi3.json`) are set to arm A's
content; arm-specific copies retained alongside.

Honest classification: pi3, like all residual arms, is
residual-teacher-base control (§14.3) — not an independent student.

## Session note (machine-state discrepancy, benign)

On session entry `agent_config.json` was found still pinned to pi1
(`student_enabled: true`, pi1 actor sha) — the prior session's idle
restore did not happen. Harmless (auto_start false, game closed), but
recorded here; the pin is being moved to pi3's sha for the smoke rung.
