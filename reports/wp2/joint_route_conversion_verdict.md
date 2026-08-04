# §40 joint route-conversion verdict

**Date:** 2026-08-04
**Verdict:** **FAIL — conversion passes decisively; geometry safety vetoes the controller**
**Campaign:** not licensed; none run

## Mechanism tested

The controller combines the two route components that §§32–33 tested only in isolation:

1. lower the PACK admission ceiling from 160 to 80 while preserving the production projectile,
   enemy-penalty, loot-dash, critical-contact and emergency branches;
2. among admitted lanes, select the best projected in-range fraction at 0.60 s only when it improves
   on the recorded lane by more than 0.05, breaking ties with the reconstructed production score.

The primary population is the eight era-valid §32 Danger-5 Ranger runs, restricted to waves 1–11.

## Measurement correction

The first analyzer output incorrectly treated duplicate four-decimal direction keys as missing lane
geometry and excluded 4,231 valid captures. A denominator audit found **0/25,788** ranked captures
with a zero-length lane and **5,944/25,788** with a rounded-key collision. Equal headings have equal
projected positions, so collisions are not degenerate.

The initial output is preserved as `joint_route_conversion_result_initial_invalid.json`. The fix and
correction note were committed before rerunning the full replay; no policy, bar, run or wave changed.
The corrected result below is the §40 result.

## Controls and denominators

| quantity | result |
|---|---:|
| arm validity | **8/8**, zero errors |
| wave-1–11 route blocks | **65,662** |
| ranked route blocks | **25,788** |
| final analysis set | **23,501** |
| vector recovery within 0.01 | **23,509/23,722 = 99.10%** |
| floor model reproduction | **23,722/23,722 = 100%** |
| admission-at-160 reproduction | **23,502/23,509 = 99.97%** |
| selection-at-160 reproduction | **23,501/23,502 = 99.996%** |
| disabled-policy changes | **0/23,501** |
| PACK 80 adds / does not add lanes | **19,354 / 4,147** |
| rounded-key collisions retained | **4,231** |

All preregistered controls pass. Exclusions are explicit in the result JSON; the largest are
`baseline_kept` 31,781, `no_threats` 8,093 and fewer than two recorded admitted lanes 2,066.

## Preregistered primary result — PACK 80

The conversion side is not marginal:

| bar | result | verdict |
|---|---:|---:|
| flips | **15,274/23,501 = 64.99%** vs ≥20% | PASS |
| runs contributing flips | **8/8** vs ≥7 | PASS |
| leave-one-run-out min / median | **64.47% / 65.03%** vs 18% / 20% | PASS |
| largest run share | **17.12%** vs ≤25% | PASS |
| median conditional in-range gain | **0.2500** vs ≥0.10 | PASS |
| integrated gain / all route ticks | **0.0651** vs ≥0.02 | PASS |
| median body-clearance retention | **0.7264** vs ≥0.80 | **FAIL** |
| p10 body-clearance retention | **0.5155** vs ≥0.60 | **FAIL** |
| projectile floor preserved | **15,274/15,274** | PASS |
| subcritical non-worsening | **15,264/15,274** vs 100% | **FAIL** |

The prediction is resolved cleanly: exposure and conversion pass by wide margins, while the
predeclared geometry veto fails on all three body-safety checks. This controller would buy targets by
giving up too much contact clearance and therefore does not license implementation or a live screen.

## Sensitivities — descriptive only

PACK 45 saturates at the same **15,274** flips as PACK 80 and has the same safety failure. PACK 120
still flips **14,190/23,501 = 60.38%** with median gain **0.2308**. Its median/p10 body ratios improve
to **0.8158/0.6300**, but it still creates the same **10** newly worse subcritical choices. Per the
preregistration, a sensitivity cannot rescue the primary result.

## Interpretation and next mechanism

The in-range gap is no longer merely an upper-bound opportunity: within the exact production route
candidate set, a joint controller can change roughly two thirds of analysable decisions and buy a
large projected conversion gain. What fails is the **unguarded selection rule**, not conversion
authority.

The next defensible Gate 0 is a fixed per-decision clearance-retention guard, not another PACK or
weight sweep. The guard values already existed before this result: retain at least **80%** of the
recorded lane's body clearance and never worsen a subcritical lane. Then ask whether the remaining
safe flips still clear the unchanged exposure, stability and integrated-gain bars. Because those
constants come from §40's preregistration rather than this result, that test does not shave a failed
boundary post hoc. It remains offline and licenses no campaign unless it passes independently.

## Artifacts

- preregistration: `joint_route_conversion_prereg.md`
- measurement correction: `joint_route_conversion_measurement_correction.md`
- analyzer: `scripts/wp2_joint_route_conversion_gate0.py`
- corrected result: `joint_route_conversion_result.json`
- preserved invalid first output: `joint_route_conversion_result_initial_invalid.json`
