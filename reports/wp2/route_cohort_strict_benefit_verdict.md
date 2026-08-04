# §47 — Strict-benefit cohort commitment sealed Gate 0 verdict

**Verdict: `VOID`; result bars not computed.** All six sealed runs and every archive,
instrumentation, delivery, conversion-guard, and identity control passed. One valid wave-3 defeat
supplied only **31 eligible episodes** and **365 retained steps**, below the preregistered per-run
minima of 50 and 500. The protocol does not permit replacement, top-up, or dropping the run.

No §47 endpoint bar was adjudicated. The exact strict-benefit mechanism is neither passed nor failed,
and no implementation, live mediator screen, or survival campaign is licensed.

## Frozen lineage

- Preregistration and prediction: `route_cohort_strict_benefit_sealed_prereg.md`, commit `b36db97`,
  before driver/analyzer implementation or collection.
- Six-slot driver, analyzer, and tests: commit `5e052ae`, before slot 1.
- Manifest-owned run IDs: `route_cohort_strict_benefit_manifest.json`, commit `270db73`, before the
  analyzer opened the sealed runs.
- Control-order repair: commit `e42caa6`, after the initial `VOID`; described below.
- Corrected controls-only result: `route_cohort_strict_benefit_result.json`.

Build remained `0.2.81-wp2-capture`, policy
`teacher_v1-0.1.129-gun-wp1`, Ranger nominal/observed Danger 5, era
179/48/`2018397571`/`1530875081`. The §47 mechanism was shadow-only and did not affect live actions.

## Fixed acquisition

All six slots completed without retry, replacement, top-up, or optional stopping:

| slot | run | result | terminal wave |
|---:|---|---|---:|
| 1 | `run_1785841731_99333` | defeat | 14 |
| 2 | `run_1785842475_92913` | defeat | 3 |
| 3 | `run_1785842563_81367` | defeat | 7 |
| 4 | `run_1785842851_55907` | defeat | 10 |
| 5 | `run_1785843329_72938` | defeat | 12 |
| 6 | `run_1785843952_82128` | defeat | 10 |

The driver repaired the mods-disabled latch before every slot, armed the complete fixed dictionary
after repair, required a fresh exact `mod_ready.json`, certified each terminal summary before
advancing, and parked the machine after slot 6. No nominal D5 victory occurred.

## Archive controls — all pass

| control | result |
|---|---:|
| valid unique manifest summaries | **6/6** |
| raw / fresh / instrument-enabled captures | **43,690 / 43,690 / 43,690** |
| parse / stale / non-increasing faults | **0 / 0 / 0** |
| ready / honest not-ready revalidation | **38,273 / 5,417** |
| ranked row parity | **333,666/333,666** |
| living `baseline_kept` ready | **24,171/24,171** |
| emitted/selected delivery | **14,102/14,102** |
| delivered live conversions | **2,594**, nonzero in 6/6 runs |
| conversion gain/body/subcritical guards | **2,594/2,594 each** |
| complete and unique living threat identity | **38,273/38,273** |

## Binding branch-control failure

Counts were computed before any result endpoint:

| run | eligible episodes | retained steps | strict branch | deadband branch | resolved | correctness |
|---|---:|---:|---:|---:|---:|---:|
| `run_1785841731_99333` | 252 | 3,073 | 789 | 2,278 | 6 | 3,073/3,073 |
| `run_1785842475_92913` | **31** | **365** | 111 | 254 | 0 | 365/365 |
| `run_1785842563_81367` | 102 | 1,220 | 367 | 848 | 5 | 1,220/1,220 |
| `run_1785842851_55907` | 203 | 2,468 | 701 | 1,762 | 5 | 2,468/2,468 |
| `run_1785843329_72938` | 246 | 2,949 | 713 | 2,232 | 4 | 2,949/2,949 |
| `run_1785843952_82128` | 212 | 2,537 | 598 | 1,939 | 0 | 2,537/2,537 |
| pooled | **1,046** | **12,612** | **3,279** | **9,313** | **20** | **12,612/12,612** |

The positive and negative branches are observable in every run, including the short run. That does
not waive the fixed per-run evidence minima. Slot 2 fails both required controls:

- eligible episodes: **31/50 required**;
- retained steps: **365/500 required**.

Its wave-3 defeat is a valid trial, not an infrastructure fault. Excluding it, replacing it, pooling
away the per-run minimum, or adding a seventh run would be a post-result protocol change.

## Control-order incident and repair

The first analyzer execution correctly printed `VOID` after Step 2 and never printed or adjudicated
Step 3. During artifact audit, however, the initial JSON was found to contain per-run endpoint values.
The cause was code order: `run_result(...)` constructed endpoint dictionaries before the branch
control, even though the PASS/FAIL bars came later.

Those leaked endpoint values are not interpreted or reported here. Commit `e42caa6` moved endpoint
construction below the successful branch-control return and added a source-order regression test.
The repair changes no identity, threshold, state-machine, count, or verdict logic. Rerunning solely
to reproduce the controls yields the same two faults and a controls-only JSON. An immediate second
repaired run was byte-identical: SHA-256
`0ADB4C857A1D640605F9056E8E343682BE8620FCC4FF187F1F652330640429CA`.

## Interpretation

The prediction was **PASS**, but a `VOID` does not adjudicate it. The acquisition proves the
instrument and both strict/deadband branches are present; it does not qualify the run-equal endpoint
surface under the frozen evidence contract.

Therefore:

- §47 is closed as `VOID` and cannot be topped up;
- §46 remains `FAIL`; §47 does not rescue it;
- the strict-benefit cohort mechanism remains unresolved, not licensed;
- any new confirmation would require a genuinely new preregistration and new sealed evidence, with
  an explicit justification that does not silently relax §47's failed minima.
