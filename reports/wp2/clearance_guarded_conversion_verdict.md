# §41 clearance-guarded conversion verdict

**Date:** 2026-08-04
**Verdict:** **PASS — implement exactly and preregister a mediator/safety screen**
**Campaign:** none run by Gate 0

## Fixed mechanism

§41 keeps §40's PACK 80, 0.60 s moving-threat projection, lexicographic in-range selection and strict
0.05 gain deadband. It adds one per-decision guard using constants declared before §40's result:

- when recorded body clearance is at least 45, require candidate clearance to be at least
  `max(45, 0.80 × recorded_clearance)`;
- when the recorded lane is already below 45, require the candidate not to worsen it.

There was no ladder and no post-result boundary choice.

## Controls and denominator

The analyzer re-ran §40's full validity and production-reconstruction chain on the same eight
era-valid D5 Ranger runs, waves 1–11. All controls passed before the guarded result was computed:

| control | result |
|---|---:|
| expected/valid runs | **8/8** |
| wave-1–11 route blocks | **65,662** |
| ranked route blocks | **25,788** |
| analysis set | **23,501** |
| floor reproduction | **23,722/23,722 = 100%** |
| admission-at-160 reproduction | **23,502/23,509 = 99.97%** |
| selection-at-160 reproduction | **23,501/23,502 = 99.996%** |
| disabled changes, base / guard | **0 / 0** |
| guard-veto / guard-no-op captures | **20,434 / 3,067** |
| candidates vetoed by guard | **67,087/331,440 = 20.24%** |

The guard is engaged and has a non-vacuous negative branch.

## Preregistered result

| bar | result | verdict |
|---|---:|---:|
| guarded flips | **11,457/23,501 = 48.75%** vs ≥20% | PASS |
| runs contributing | **8/8** vs ≥7 | PASS |
| leave-one-run-out min / median | **48.27% / 48.82%** vs 18% / 20% | PASS |
| largest run share | **17.28%** vs ≤25% | PASS |
| median conditional in-range gain | **0.2222** vs ≥0.10 | PASS |
| integrated gain / all route ticks | **0.0461** vs ≥0.02 | PASS |
| projectile-floor preservation | **11,457/11,457** | PASS |
| body-guard satisfaction | **11,457/11,457** | PASS |
| subcritical non-worsening | **11,457/11,457** | PASS |

The guard retains **11,457/15,274 = 75.01%** of §40's unguarded flips. Conditional body-clearance
retention is p10 **0.8287**, median **0.9847**, confirming the implementation of the fixed bound.

The effect is not confined to irrelevant early waves. Every wave 1–11 flips at least 36.0% of its
analysis set; wave 11 itself flips **540/1,387 = 38.93%** with projected gain sum 131.06.

## Interpretation

The prediction passes. §40's safety failure did not consume the conversion surface: discarding every
candidate that violates the already-declared clearance rules still leaves more than twice the
required flip exposure and more than twice the required integrated gain.

This is the first D5 combat-conversion mechanism in this line to clear Gate 0. It licenses:

1. implementing exactly the PACK-80, 0.80-retention, subcritical-non-worsening, 0.05-deadband policy;
2. source and offline parity tests proving the implementation matches this replay;
3. a separately preregistered live screen on the validated in-range mediator with the §31 low-HP
   exposure veto and final-command delivery readback.

It does **not** establish survival benefit and does not by itself license a D5 win claim. The live
screen must reject a controller that gains in-range by increasing low-HP exposure, regardless of this
offline pass.

## Artifacts

- preregistration: `clearance_guarded_conversion_prereg.md`
- analyzer: `scripts/wp2_clearance_guarded_conversion_gate0.py`
- full result: `clearance_guarded_conversion_result.json`
