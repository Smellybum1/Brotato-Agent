# §45 — All-exit route-revalidation acquisition verdict

**Verdict: `INSUFFICIENT_INSTRUMENT`; latch result not computed.** The instrument itself passes every
validity, parity, delivery, and coverage control, but the fixed four-run acquisition produced
**885** stateful episodes against the preregistered **1,000** minimum. The protocol forbids a fifth
run or a post-result boundary change.

Pre-registration: `route_latch_revalidation_acquisition_prereg.md`, commit `7b511e3`, before
implementation or collection. Instrument, fixed driver, analyzer, and tests: commit `06b639f`, before
deployment. Build `0.2.81-wp2-capture`; policy unchanged at
`teacher_v1-0.1.129-gun-wp1`. Full result: `route_latch_revalidation_result.json`; fixed run ownership:
`route_latch_revalidation_manifest.json`.

## Fixed acquisition and machine state

Four fixed Ranger D5 instrument slots completed without retry, replacement, top-up, or optional
stopping:

| slot | run | result | terminal wave |
|---:|---|---|---:|
| 1 | `run_1785826116_89378` | defeat | 12 |
| 2 | `run_1785826737_53506` | defeat | 11 |
| 3 | `run_1785827267_71832` | defeat | 6 |
| 4 | `run_1785827488_46830` | defeat | 7 |

All four matched the exact 179/48 era and fixed arm. Between force-killed slots, the driver ran
`deploy_mod.py --repair-launch` before re-arming. After slot 4, Brotato was stopped and config was
read back with `auto_start=false`, conversion false, route scores false, and revalidation false.

## Controls first — all pass

| control | result |
|---|---:|
| valid manifest-owned summaries | **4/4** |
| fresh captures | **28,173/28,173** |
| stale / non-increasing / parse failures | **0/28,173 / 0/28,173 / 0/28,173** |
| instrument enabled | **28,173/28,173** |
| ready / honest no-threat negative | **24,536 / 3,637** |
| ranked row parity | **215,901/215,901 = 100%** |
| exact parity captures | **9,079/9,079 = 100%** |
| living `baseline_kept` ready | **15,457/15,457 = 100%** |
| emitted/selected heading | **9,079/9,079 = 100%** |
| conversions delivered in every run | **1,824 pooled; 729/618/236/241** |
| gain/body/subcritical guard checks | **1,824/1,824 each** |

The instrument repaired §44's specific defect. Pooled active-future observability rose from 75.63%
to **6,242/6,248 = 99.904%**; every run passed 99.876%, and active `baseline_kept` observability was
**3,125/3,125 = 100%**.

## Binding sufficiency failure

Only one preregistered sufficiency bar failed:

| bar | result | verdict |
|---|---:|---:|
| stateful episodes | **885** vs ≥1,000 | FAIL |
| pooled observability | **99.904%** vs ≥99% | PASS |
| per-run observability | **99.876–99.913%** vs ≥98% | PASS |
| active `baseline_kept` observability | **100%** vs ≥99% | PASS |
| future-eligible episodes per run | **347 / 310 / 99 / 128** vs ≥30 | PASS |

An independent raw-event state machine reproduced **1,824** applied conversions and exactly **885**
non-overlapping latch starts by run (**347/311/99/128**). The short wave-6 and wave-7 runs are valid
and remain in the denominator.

Per the committed analysis order, the analyzer stopped after sufficiency and did **not** print or
write duration, horizon rate, leave-one-run-out, concentration, or latch pass/fail bars. Computing
those now, adding a fifth run, or lowering 1,000 would violate the protocol.

## Interpretation

The all-exit instrument is qualified: it is default-inert, reproduces the established ranked rows
exactly, exposes every living `baseline_kept` candidate set, and leaves action delivery intact. The
four-run dataset is not qualified to adjudicate the bounded latch under §45.

Therefore:

- §44's `DATA_LIMITED` latch remains unresolved, not passed or failed;
- §45 does not license latch implementation, a mediator screen, or a survival campaign;
- the fixed §45 acquisition is closed and cannot be topped up post hoc;
- build 0.2.81 may be reused as an observational instrument only under a new, separately justified
  and preregistered question—not to continue §45 until its bar happens to pass.
