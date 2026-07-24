# WP2 M4 change record — DAgger corrective iteration (bc_v2 / bc_v3)

Milestone **M4 (DAgger)** of the WP2 learned-combat track. Status: **CLOSED
2026-07-24** — production student **`bc_v2_f_s1`** (behaviorally validated: 6
runs, waves 16–20, one victory). Commits `5682ba3` (r1 + gate revision),
`3eab510` (r2 + first victory + relative gates), `8ef4d90` (paired eval +
mechanism finding). Branch `wp2-combat-learning`. Design of record:
`.tmp/wp2_m4_dagger_design.md` (incl. §8 gate-revision log, §9 paired-eval
protocol).

DAgger with **zero mod changes**: during student control the M3 capture stream
already records, per 20 Hz tick, the student-visited state (prev-action = the
student's applied action) and `teacher.action` = the teacher's fresh
counterfactual for that state — exactly the DAgger corrective pair. Every
campaign ran on the qualified M3 torch sidecar (§ `reports/wp2/m3_change_record.md`).

## Round 1 — measure live distribution shift, revise gates, select bc_v2_f (`5682ba3`)

**Campaign.** 5 student-controlled runs under `bc_v1_s1_full` (operator-approved:
"lets go with your recommendation"), all ~99.8 % control, zero telemetry faults
→ **`datasets/combat_dagger_r1`**: 78,874 training-eligible rows (78,955 total, 5
shards; manifest sha256 `7AF8403F…D35EE84`). Label = `teacher.action`
(counterfactual); prev-action = student's applied action; event-balanced sample
weights (45/30/15/10 mass over background/precursor/onset/recovery).

**KEY FINDING — copy-through inflation.** On its own visited states (the 7,887-
row r1 holdout), `bc_v1` measures **median angular error 71.5°** / mean cosine
0.161 (median cosine 0.294 per commit), with **negative cosine in the high-risk
strata** (0.50–0.75 = −0.047; 0.75+ = −0.198) — statistically indistinguishable
from the `copy_previous` baseline (74.6°). The offline **4.80°** teacher-val
figure was substantially measuring the prev-action copy-through channel, not
policy quality on the *deployment* distribution. This is the central M4 result:
teacher-val error alone is not a deployment-quality signal.

**Gate evolution (operator-delegated: "I give you authority to make the
decisions on 1 and 2"; standing autonomy confirmed).**

- *Original* (design §5): risk≥0.5 median improve ≥15 %, wave-20 median <17°,
  overall no regress >0.2° — all on teacher-val only.
- *Decision 1 — dual-distribution:* add a deployment-distribution clause
  (r1 holdout: median ≤30°, mean cosine >0 in every risk stratum, risk≥0.5
  medians ≤35°); keep a teacher-val bound. Evidence: the copy-through finding
  above.
- *Decision 1a — frontier-adjusted (the applied gates):* an 8-point training
  frontier (mass 0.05/0.10/0.15/0.25 × dropout 0.1/0.4 × λmag 0.5/1.0; sweep +
  sweep2) proved tv median is monotone in corrective exposure and ≥7.37° even at
  5 % mass — the tight tv ≤6.5° clause was reachable only by re-exploiting the
  copy-through channel proven to collapse live. Final gates: **teacher-val
  median ≤9.0° / |mag err| ≤0.09 / no saturation regression**; **anti-copy-
  through** (holdout median ≤37.3° = ≥2× better than copy_previous 74.6°, cosine
  >0 every stratum); **deployment holdout** median ≤30°, risk 0.50–0.75 ≤35°,
  risk 0.75+ ≤45°.

**Selection** (`reports/wp2/bc_v2_sweep_report.md`). Sole qualifier
**`bc_v2_f_s1`** (mass 0.15, dropout 0.4, λmag 1.0; best.pt sha256
`1AD517B0…F29F331`): teacher-val 8.73° / 0.083; holdout 25.5°, cosine
+0.69/+0.65/+0.64/+0.57, risk medians 29.6 / 38.9. Variants a/b/c/d/e/g/h each
fail ≥1 clause. Round-2 precondition satisfied: sidecar now logs the raw
pre-clamp proposal per act (`sidecar.py`, default on), completing the
(proposal, teacher, executed) logging triple from r2 onward. Collector
`set_auto_start` made merge-preserving (no longer drops student config keys).
373 tests green.

## Round 2 — first student victory, relative gates, select bc_v3_a (`3eab510`)

**Campaign.** 5 runs under `bc_v2_f` (waves 16–20 incl. the **first student
victory**, w20) + 1 smoke = 6 included, all ~99.8 % control; complete (proposal,
teacher, executed) triples reconciled exact (join coverage 1.0) →
**`datasets/combat_dagger_r2`**: 116,269 rows (manifest sha256
`9B2C1E91…65332A0B`). **bc_v3** trained on base + r1 + r2.

**Decision 1b — deployment gates made RELATIVE.** The r2 holdout is measurably
harder than r1's (copy_previous 59.8° vs 74.6°; every model's risk-strata
medians shift ~2×) because `bc_v2_f` survives longer and visits later, denser
states — absolute deployment thresholds are incoherent across rounds. Revised
deployment clauses (evaluated on the fresh predecessor-collected holdout;
teacher-val clauses unchanged/absolute): **beat the predecessor's median by
≥25 %; beat copy_previous's median by ≥1.5×; mean cosine >0 in every risk
stratum**.

**bc_v3 aggregate eval** (`reports/wp2/bc_v3_eval.md`; the r2 holdout, n=11,627,
is unbiased for all four models):

| model | r2 median | r2 cosine |
|---|---|---|
| bc_v3_a_s1 | 37.85° | 0.480 |
| bc_v3_b_s1 | 36.84° | 0.507 |
| bc_v2_f_s1 | 55.75° | 0.271 |
| bc_v1_s1_full | 56.68° | 0.265 |
| copy_previous | 59.85° | 0.234 |

**Selected `bc_v3_a_s1`**: 32 % better than predecessor `bc_v2_f` (37.85 vs
55.75), 1.58× over copy_previous, cosine >0 in every stratum (incl. risk 0.75+
at +0.063), teacher-val 8.70° / 0.076. `bc_v3_b` fails the tv-median clause
(9.25°). Recorded convergence: each generation's self-distribution error
improves (bc_v1 on r1: 71.5° → bc_v2_f on r2: 55.7°) alongside live outcomes.
377 tests green.

## bc_v3_a smoke + paired evaluation — retain bc_v2_f (`8ef4d90`)

**Smoke.** `bc_v3_a` smoke `run_1784880640_76087` **missed the predeclared
behavioral bar** (defeat wave 13; bar was ≥16 or victory) despite clean infra
(99.8 % control). Per the predeclared rule the autonomous iteration loop
**stopped**. Operator chose option (a): a paired live evaluation to settle
promotion.

**Paired eval** (`reports/wp2/paired_eval_v2f_v3a.md`; 6v6, predeclared rule,
no re-rolls). All 12 runs infra-pass (≥99.79 % control, zero faults, exact
reconciliation).

- `bc_v2_f`: last-wave [16, 17, 20, 20, 20, 21] → **median 20.0, 1 victory**
- `bc_v3_a`: last-wave [10, 11, 13, 20, 20, 20] → **median 16.5, 0 victories**

**VERDICT: RETAIN `bc_v2_f_s1`** as the production student. Config pin restored
to it.

**Mechanism finding (telemetry-only; the key negative result).** `bc_v3_a`'s
offline dominance on the unbiased r2 holdout (37.9° vs 55.7°) did **not**
translate to live behavior. The failure axis is **risk-exposure attrition, not
imitation error**: `bc_v3_a` is a *smoother, less evasive* mover (lower applied-
direction change than v2f in every wave band; lower raw proposal magnitude and
clamp fraction), so it sits in contact-risk ≥0.5 longer. In band 6–10 the doomed
`v3a_bad` runs spend 0.0459 of ticks below half-HP vs 0.001 for v2f — a **~45×
higher low-HP rate in the same band**, well before the w10–13 deaths (a
compounding attrition spiral, divergence opening ~wave 8). Critically, `bc_v3_a`
**agrees with the teacher MORE** than `bc_v2_f` in the mid/late bands while
losing — confirming that offline teacher-imitation error on the predecessor's
distribution does not predict live outcome. **Consequence for future rounds:
live behavioral evidence must enter selection earlier** (e.g. 2-run behavioral
screens per short-listed candidate before full eval).

`bc_v3_a`'s 6 runs are valid DAgger data under v3a → **`datasets/combat_dagger_r3`**:
93,203 rows (manifest sha256 `F8DC2ED0…B4CD9B2A`, triples exact), available for
the next round's aggregate.

## Datasets & artifacts

| dataset | student policy | rows (train-eligible) | manifest sha256 |
|---|---|---|---|
| `combat_dagger_r1` | bc_v1_s1_full | 78,874 | `7AF8403F…D35EE84` |
| `combat_dagger_r2` | bc_v2_f_s1 | 116,269 | `9B2C1E91…65332A0B` |
| `combat_dagger_r3` | bc_v3_a_s1 | 93,203 | `F8DC2ED0…B4CD9B2A` |

Production student: **`bc_v2_f_s1`** (`models/registry/bc_v2_f_s1.json`, best.pt
sha256 `1AD517B0…F29F331`). `bc_v3_a_s1` is offline-selected/dominant but
behaviorally unconfirmed — archived candidate, folded into the next aggregate.
See `docs/MODEL_REGISTRY.md`.
