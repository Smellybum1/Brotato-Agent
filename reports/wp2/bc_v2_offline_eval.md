# bc_v2 offline evaluation - design section-5 selection gates

Metrics recomputed independently via the UNCHANGED `trainer/evaluation/bc_offline.py`
path (`reports/wp2/bc_offline_eval_bc_v2.json`) on the frozen `combat_obs_v1`
`dataset_split_v1` validation split (81,790 rows), directly comparable with
bc_v1. Candidate A = `BCPolicyV1` checkpoint (native). Candidate B = the exported
`BCPolicyV1`-compatible base state_dict registered in `bc_v2_b_s1.json` (aux heads
dropped at serving). Findings only.

## Verdict

**NEITHER candidate qualifies. Both FAIL all four design section-5 gates**, and
both regress on the very weak strata the corrective data was meant to improve.
Per design section 5, escalate to round 2 (more/targeted corrective runs) - do
NOT relax gates.

## Design section-5 gates (per candidate, PASS/FAIL)

| gate | bc_v1 | threshold | A value | A | B value | B |
|---|---|---|---|---|---|---|
| G1 risk 0.50-0.75 median | 18.21 | <= 15.5 | 27.13 | FAIL | 27.45 | FAIL |
| G2 risk 0.75+ median | 30.98 | <= 26.3 | 45.53 | FAIL | 44.00 | FAIL |
| G3 wave-20 median | 18.25 | < 17.0 | 19.11 | FAIL | 18.93 | FAIL |
| G4 overall median | 4.80 | <= 5.00 | 10.15 | FAIL | 9.25 | FAIL |
| G5 no sat / mag regression | sat 0.0, |mag err| 0.052 | no regress | sat 0.0, |mag err| 0.113 | FAIL (mag 2.2x) | sat 0.0004, |mag err| 0.112 | FAIL (mag 2.2x) |

Every gate regressed rather than improved. G5 fails on magnitude error (mean
abs magnitude error roughly doubled vs bc_v1); saturation is effectively zero
for both (no saturation regression).

## Overall validation (vs bc_v1)

| run | median deg | mean deg | val_loss | mean |mag err| | sat frac |
|---|---|---|---|---|---|
| bc_v1_s1_full | 4.80 | 13.73 | 0.0981 | 0.0517 | 0.0000 |
| bc_v2_a_s1 (A) | 10.15 | 20.53 | 0.1502 | 0.1129 | 0.0000 |
| bc_v2_b_s1 (B) | 9.25 | 19.71 | 0.1449 | 0.1119 | 0.0004 |

Note: both bc_v2 candidates are now WORSE than the copy-previous baseline on
overall median (copy-previous = 4.32 deg), the exact channel the corrective data
degraded (see root cause).

## By risk stratum (median deg | mean deg)

| stratum | n | bc_v1 med | A med | A mean | B med | B mean |
|---|---|---|---|---|---|---|
| 0.00-0.25 | 71206 | 4.55 | 9.68 | 18.80 | 8.80 | 17.94 |
| 0.25-0.50 | 8004 | 6.02 | 12.37 | 26.07 | 11.72 | 25.70 |
| 0.50-0.75 | 2384 | 18.21 | 27.13 | 49.92 | 27.45 | 49.04 |
| 0.75-inf | 196 | 30.98 | 45.53 | 63.79 | 44.00 | 62.87 |

## By wave band (median deg)

| band | n | bc_v1 | A | B |
|---|---|---|---|---|
| 1-5 | 12828 | 3.37 | 7.49 | 7.00 |
| 6-10 | 22470 | 3.92 | 9.03 | 8.14 |
| 11-15 | 24925 | 4.74 | 10.15 | 9.27 |
| 16-19 | 17324 | 7.12 | 13.75 | 12.37 |
| 20 | 4243 | 18.25 | 19.11 | 18.93 |

## Candidate preference (A vs B)

Design rule: B is preferred over A only if it beats A on the weak strata.

| weak metric | A | B | winner |
|---|---|---|---|
| risk 0.50-0.75 median | 27.13 | 27.45 | A (B worse) |
| risk 0.75+ median | 45.53 | 44.00 | B |
| wave-20 median | 19.11 | 18.93 | B |
| overall median | 10.15 | 9.25 | B |

B is marginally better overall and on 2 of 3 weak metrics but WORSE at risk
0.50-0.75; the differences are tiny and neither beats bc_v1. Preference is moot -
neither qualifies.

## Candidate B aux-head metrics (held-out dagger rows, best epoch)

The aux heads are scored on the deterministic 10% dagger holdout (7,887 rows;
7,810 horizon-valid), which is EXCLUDED from training for both candidates. The
frozen val split carries no aux labels, per design section 6.

| head | metric | value |
|---|---|---|
| aux_damage (P hp-loss within 10 ticks) | ROC-AUC | 0.964 |
| | BCE | 0.048 |
| | base rate | 0.0193 |
| | pred mean (pos / neg) | 0.335 / 0.017 |
| aux_margin (1 - max future contact_risk) | MAE | 0.172 |
| | RMSE | 0.217 |
| | Pearson r | 0.667 |
| | label mean / pred mean | 0.761 / 0.750 |

The shared representation predicts imminent damage very well (AUC 0.96) and
tracks the safety margin (r 0.67), so the aux signal is learnable - but it did
NOT rescue the main action-prediction task.

## Root cause (diagnostic, not a pipeline bug)

Both candidates regress on ALL strata, including the weak strata the corrective
data targeted. The cause is a near-inversion of the `previous_action` -> label
relationship between the two data sources:

| source | frac(cos(prev_action, label) > 0.999) | median cosine |
|---|---|---|
| combat_obs_v1 (teacher-generated) | 45.2% | 0.997 |
| combat_dagger_r1 (student-controlled) | 2.5% | 0.238 |

In teacher data, `previous_action` almost equals the current teacher action ~45%
of the time (the copy-through channel bc_v1 exploits for its 4.8 deg median). In
the corrective set, the executed (magnitude-clamped) STUDENT action enters as the
`previous_action` state (design section 7, ruling 3 - the logging-triple gap: the
raw pre-clamp student proposal is not persisted), and it is near-orthogonal to
the teacher counterfactual label. Training on 25% mass of "previous_action does
NOT predict the label" teaches the model to distrust `previous_action`, which is
catastrophic on the teacher-distribution frozen val where it usually does.

Controls confirming this is not a bug: normalization drift base vs composite is
negligible (< 5% on a handful of columns); dagger labels are sane unit vectors
(|a| ~ 1.0); the offline eval independently reproduced the training-time numbers.

## Recommendation

Round 2, per design section 5. The round-2 precondition already named in the
design (section 7, ruling 3) is directly implicated: complete the sidecar
per-request action logging so the raw pre-clamp student proposal (its true
direction) is captured, and reconsider whether `previous_action` in corrective
frames should carry the teacher's prior action rather than the clamped student
action. Do NOT relax gates.
