# Step 0: the landmark-continuation endpoint qualifies, and my rejection of it was wrong

Re-scoring of the 232 existing wave-17 dose trials on **terminal outcome** (eventual win)
rather than wave-17 survival. **Zero machine time** — these trials already resumed at the
wave-16 shop and played through to run end; only the endpoint we read off them changed.

Result: the estimator external review proposed is **better than I judged**, my rejection
rested on a variance regime measured at the wrong endpoint, and the endpoint passes a
validity check that was free.

## Extraction validity

232/232 trials valid, 0 invalid, arms recoverable from the fixture filename suffix
(`__C` / `__H50` / `__H75` / `__H85` / `__H90` / `__H95`). The re-scoring **reproduces the
published wave-17 numbers exactly** — v2 control survival 57/64 = 0.891, i.e. the reported
7/64 failures — which is what licenses trusting the new endpoint computed from the same rows.

Control arms only. Treatment arms are contaminated for this purpose because the
`enemy_scaling` save edit persists past wave 17 into 18-20.

## The variance split is endpoint-dependent, and it inverts

Pooled round1 + v2 controls: **16 distinct source states x 5 continuations = 80 trials.**

Raw per-state win series (chronological within state):

| source state | series | wins |
|---|---|---|
| `w16_invoker_...120747` | `11101` | 4/5 |
| `w16_invoker_...122720` | `11111` | 5/5 |
| `w16_invoker_...130625` | `01111` | 4/5 |
| `w16_invoker_...133857` | `11111` | 5/5 |
| `w16_invoker_...143758` | `01111` | 4/5 |
| `w16_invoker_...145730` | `00111` | 3/5 |
| **`w16_invoker_...69b670f4`** | **`00000`** | **0/5** |
| `w16_predator_...112824` | `11110` | 4/5 |
| `w16_predator_...114824` | `11111` | 5/5 |
| `w16_predator_...124642` | `00110` | 2/5 |
| `w16_predator_...135835` | `11111` | 5/5 |
| `w16_predator_...141824` | `11011` | 4/5 |
| `w16_predator_...153255` | `11100` | 3/5 |
| `w16_predator_...155216` | `11011` | 4/5 |
| `w16_predator_...162226` | `11111` | 5/5 |
| `w16_predator_...164236` | `11101` | 4/5 |

Decomposition (source state = cluster; within estimated unbiasedly as
`K/(K-1) x ybar(1-ybar)`):

| endpoint | `sigma2_between` | `sigma2_within` | **ICC** | dominant term |
|---|---|---|---|---|
| **terminal win** (K=5, I=16) | 0.0418 | 0.1437 | **0.225** | **within** |
| terminal win (K=4, v2 only) | 0.0401 | 0.1354 | 0.228 | within |
| **wave-17 survival** (K=4, v2 only) | 0.0547 | 0.0469 | **0.538** | **between** |

`b + w = 0.1855` against `p(1-p) = 0.1811` — the decomposition closes, so the estimator is
internally consistent. The K=4 and K=5 estimates agree to the third decimal, so the split is
stable rather than an artifact of one campaign.

**The two endpoints have opposite variance structure.** The wave-16 state strongly
determines whether wave 17 is survived — "a doomed build replays as doomed" is correct, for
*that* endpoint. It does **not** carry to eventual victory, because waves 18-20 inject fresh
RNG including the wave-20 boss draw, whose two bosses have survival rates 1.000 and 0.597.

**This is exactly the failure mode the project's own measurement discipline names: I read
which component dominates one aggregate and carried it to a different one.** I predicted
ICC high and the continuation estimator therefore worthless. Measured, it is 0.225 and the
estimator works.

Corroborating detail visible in the raw series: three states survived wave 17 on every
continuation yet still lost runs downstream (`...153255` is `1111` on wave-17 survival but
`11100` on terminal win, losing at waves 20 and 19). Wave-17 survival is not a sufficient
statistic for the run.

## Validity: the landmark endpoint does not flatter

| quantity | value |
|---|---|
| `P(win \| wave-16 landmark)`, continuations | **61/80 = 0.7625** |
| `P(win \| reached wave 16)`, natural full runs | **26/34 = 0.7647** |

Essentially identical. This matters because the archive's headline win rate was contaminated
for weeks by fixture trials winning far more often than full runs — that contamination came
from wave-19 fixtures, which skip most of the run. A wave-16 landmark does not show it.

**The endpoint is also not saturated**, which was the defect that forced the wave-20 fixture
harness onto damage-taken as a proxy: terminal win sits at 0.76 where wave-17 survival sits
at 0.89 and wave-20 fixture win is pinned at 1.000.

## What it costs, measured

Continuation wall-clock over 96 control trials: **mean 3.76 min**, median 4.46, min 0.58
(failures are short). In-game duration median 4.28 min, so an independent prefix to the
wave-16 landmark costs about `19.0 - 4.28 = 14.7` min.

**(A) Unpaired, estimating the overall win rate** — the prefix must be paid per source:

| K | variance | cost/source | variance x cost |
|---|---|---|---|
| 1 | 0.1755 | 18.5 min | 3.24 |
| 2 | 0.1078 | 22.2 min | 2.40 |
| **4** | **0.0739** | **29.8 min** | **2.20** |
| 6 | 0.0627 | 37.3 min | 2.34 |

Against a full run's `0.2007 x 19 = 3.81`, the best is **1.73x**. Real, but it turns the
294-hour full-run experiment into ~170 hours. **It does not rescue the win-rate instrument.**

**(B) Paired at the landmark, reusing the existing library** — prefix already sunk, and the
between-state term cancels:

| design | variance x cost |
|---|---|
| paired landmark continuations | **2.04-2.16** |
| paired full runs | 15.25 |

**~7x.** This is where the value is.

### Sizing against the library we actually have

Standard error of the mean paired contrast is `sqrt(2 x sigma2_within / (K x I))`:

| states `I` | reps `K` | trials | hours | min. detectable effect on `P(win\|landmark)` |
|---|---|---|---|---|
| 16 (have) | 4 | 128 | 8.0 | 18.8 pp |
| 16 (have) | 8 | 256 | 16.0 | 13.3 pp |
| 45 | 5 | 450 | 28.2 | 10.0 pp |

Variance x cost is **flat in K** for the paired design, so precision depends on `K x I` and
the choice is free — which reconfirms standing practice: **spend budget on more states, not
more repeats**, because states are the generalisation unit. State count is now the binding
constraint. States are **not** an extra cost: every full run yields one.

## Verdict

**GO on the endpoint.** Adopt terminal win, scored from a wave-16 landmark, source-state
clustered, as the outcome of the paired fixture harness. It is unsaturated, it is the actual
objective rather than a proxy, it agrees with natural full runs, and it is ~7x more
efficient than paired full runs.

**NO-GO on it as a replacement for full-run win-rate measurement.** 1.73x unpaired does not
change what is affordable there.

Standing caveats: `K` continuations from one save are not `K` independent builds — the
source state is the inferential unit in every analysis. And this estimates
`P(win | reached the landmark)`, so it is structurally blind to any effect on
`P(reach the landmark)`; an intervention acting before wave 16 must either be instantiated
by save-edit (a mechanism probe, not a deployable-policy counterfactual) or measured on full
runs.
