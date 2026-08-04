# §46 — Route-cohort commitment offline Gate 0 verdict

**Verdict: `FAIL`.** The mechanism reliably persists an original threat objective for 0.60 seconds
under current-tick safety revalidation, but it does not reliably turn its overrides into better
projected engagement of that cohort. No implementation, live mediator screen, or campaign is
licensed.

Pre-registration: `route_cohort_commitment_gate0_prereg.md`, commit `32efd33`, before any cohort
calculation. Frozen analyzer and synthetic tests: commit `16c01fc`, before opening the fixed archive
with that analyzer. Full result: `route_cohort_commitment_gate0_result.json`. The analysis uses only
the four manifest-owned §45 runs; no run was launched or added.

## Controls first — all pass

The §45 archive and instrument controls reproduced exactly:

| control | result |
|---|---:|
| frozen unique summaries | **4/4** |
| raw / fresh / instrument-enabled captures | **28,173 / 28,173 / 28,173** |
| stale / non-increasing / parse failures | **0 / 0 / 0** |
| ranked row parity | **215,901/215,901** |
| exact parity captures | **9,079/9,079** |
| living `baseline_kept` ready | **15,457/15,457** |
| emitted/selected delivery | **9,079/9,079** |
| conversion gain/body/subcritical guards | **1,824/1,824 each** |
| complete and unique living threat identity | **24,536/24,536** |

Identity also passed 100% in every run: 8,887/8,887, 8,253/8,253, 3,174/3,174,
and 4,222/4,222. The state machine found 710 otherwise valid conversion triggers; 708/710 had the
required same-wave 600 ± 75 ms future window, while 2/710 were explicitly excluded. Every run had
both override and no-override branches. Synthetic tests covered trigger, suppression, current-tick
revalidation, deterministic ties, resolved cohorts, horizon, wave-change, missing-input, and
no-safe-candidate paths.

## Frozen bars

| bar | result | verdict |
|---|---:|---:|
| median duration ≥0.30 s | **0.600 s** | PASS |
| horizon rate ≥25% | **690/708 = 97.46%** | PASS |
| every run contributes a horizon | **4/4** | PASS |
| leave-one-run-out horizon ≥20%; median ≥25% | **97.34–97.59%; median 97.45%** | PASS |
| largest eligible-run share ≤35% | **275/708 = 38.84%** | **FAIL** |
| projectile/body/subcritical/enemy invariants | **8,514/8,514 each** | PASS |
| override rate ≥20% | **6,351/8,529 = 74.46%** | PASS |
| median override advantage ≥0.05 | **0.000** | **FAIL** |
| mean all-step advantage ≥0.02 | **0.05769** | PASS |

The 18 non-horizon episodes have honest release denominators: 9/708 released on a not-ready
revalidation capture and 9/708 on no current safe candidate. Fifteen of 8,529 retained steps had
an already-resolved original cohort and correctly retained the recorded command.

The result is deterministic: an immediate second execution wrote a byte-identical JSON result
(SHA-256 `6479D463DA895F9BA6B1F0348B60D8D5054321BC4F85B605CB0C88BD306104B1`).

## Post-result diagnostic — descriptive, not a new bar

Because the preregistered median was exactly zero, the distribution was printed rather than treating
the zero as self-explanatory. Of 6,351 override steps:

- **2,420/6,351 = 38.10%** had positive cohort advantage;
- **3,805/6,351 = 59.91%** had exactly zero advantage;
- **126/6,351 = 1.98%** had negative advantage.

The zero mass is structural: cohort value is a coarse resolved-or-projected-in-range fraction, and
the frozen tie rule selects the safer revalidation-grid direction even when several directions have
the same cohort value. Negative values are possible because the recorded arbitrary-angle command
is the comparison but is not itself necessarily one of the 24 revalidation-grid candidates.

This diagnostic does not rescue the gate. It identifies the defect in the exact mechanism: it
manufactures many direction changes without an engagement improvement. A strict-improvement
deadband would be a different mechanism and cannot be retrofitted to §46's result.

As a discovery-only screen for that possible next mechanism, retaining only strictly positive
overrides leaves **2,420/8,529 = 28.37%** of all retained steps. The surface is present in every run:

| run | positive / retained | rate | median positive advantage |
|---|---:|---:|---:|
| `run_1785826116_89378` | 905/3,318 | 27.28% | 0.1667 |
| `run_1785826737_53506` | 806/2,905 | 27.75% | 0.1623 |
| `run_1785827267_71832` | 297/1,013 | 29.32% | 0.2000 |
| `run_1785827488_46830` | 412/1,293 | 31.86% | 0.2000 |

These numbers are hypothesis-generating only. They were computed after the §46 verdict and therefore
must not be treated as a passed gate or reused as confirmatory evidence.

## Interpretation

The prediction was **PASS** and was wrong. Objective identity does repair the temporal failure of
the fixed heading—97.46% reach the horizon instead of the §43 one-tick reversal—but persistence
alone is not enough. The exact selector fails both a robustness/concentration bar and its primary
conditional-benefit bar.

Therefore:

- the exact 0.60-second cohort-objective selector is closed;
- the §45 fixed archive must not be re-read under relaxed §46 bars;
- no live treatment or survival campaign is licensed;
- a strict-positive-advantage version remains only a discovery lead. Because it was suggested by
  this result, it requires a new preregistration and sealed evidence rather than post-hoc
  adjudication on these four runs.
