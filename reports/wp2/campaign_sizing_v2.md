# Campaign sizing, rebuilt on the post-`damage_taken` endpoints

**Date:** 2026-07-29. **Item 3 of `NEXT_SESSION_PLAN.md`.** Supersedes the sizing table in
`campaign_sizing.md`, which was built on gross damage taken and does not transfer.

**Retired:** *32 trials detects 19 damage / 64 detects 13 / 128 detects 9, control mean ~20.7.*
Every number there is denominated in a gross counter that never subtracts healing.

---

## Endpoint 1 — terminal win from the wave-16 landmark (confirmatory primary)

Unchanged; the variance components were already measured in `landmark_continuation_pilot.md` and
are unaffected by the gross-damage retirement because the outcome is terminal.

`sigma2_between` **0.0418**, `sigma2_within` **0.1437**, **ICC 0.225** (within-dominated, which is
what makes the continuation estimator work). Continuation cost **3.76 min** mean.

| states `I` | reps `K` | trials | hours | min. detectable effect on P(win \| landmark) |
|---|---|---|---|---|
| 16 (have) | 4 | 128 | 8.0 | 18.8 pp |
| 16 (have) | 8 | 256 | 16.0 | 13.3 pp |
| 45 | 5 | 450 | 28.2 | 10.0 pp |

Variance × cost is flat in `K`, so precision depends on `K × I` and **state count is the binding
constraint** — spend budget on more states.

---

## Endpoint 2 — death-adjusted HP-deficit AUC at wave 17 (fixed-wave mechanism screen)

Measured today over **234 agent wave-17-entry fixture trials** in the `0.2.49`/`0.2.50` era at
`time_scale` 1.0. Horizon `T = 60 s` on every trial; no `elapsed_sec` resets occur in this stratum.

### The grouping key must include the dose

| grouping key | within-state SD | df |
|---|---|---|
| **(entry fingerprint, enemy dose)** — correct | **0.0630** | 162 |
| entry fingerprint only — dose-blind | 0.0846 | 195 |

`enemy_scaling` changes enemy health without touching any player stat, so a dose-blind key silently
pools treatment arms and **inflates within-state SD by 34%**, making the whole table ~34% too
pessimistic. Between-state SD **0.0328**, **ICC 0.213**; naive trial-level SD ignoring structure is
0.0976.

### Normal-theory sizing is INVALID on this endpoint

**59.8% of trials score exactly 0.0000.** The endpoint is a spike-at-zero mixture, and a
normal-approximation power calculation on it produced a table claiming 16 trials could detect
0.0624 AUC — larger than the entire mean of 0.0497. Discarded.

It is nonetheless a **graded** measure, not a death proxy: 61 of 201 survivors score nonzero
(0.0010–0.2794), and the death minimum (0.0472) overlaps the survivor maximum (0.2794).

### Simulation-based sizing

Paired within (fixture, dose), Wilcoxon signed-rank, two-sided α = 0.05, 2000 simulations, treatment
modelled as a **proportional** reduction (zeros stay zero — a helping treatment converts nonzero AUC
toward zero, it does not translate the distribution).

| F × k | trials | r=25% | r=50% | r=75% | r=100% |
|---|---|---|---|---|---|
| 8 × 2 | 16 | 0.10 | 0.21 | 0.40 | 0.51 |
| 8 × 4 | 32 | 0.20 | 0.50 | 0.75 | 0.89 |
| 16 × 2 | 32 | 0.20 | 0.48 | 0.80 | 0.96 |
| 16 × 4 | 64 | 0.34 | 0.79 | 0.96 | 1.00 |
| 24 × 2 | 48 | 0.27 | 0.68 | 0.94 | 1.00 |
| 32 × 2 | 64 | 0.31 | 0.80 | 0.99 | 1.00 |
| 32 × 4 | 128 | 0.55 | 0.96 | 1.00 | 1.00 |

**Standing practice, restated for this endpoint:**
- **SCREEN at 32 trials** — powered (~0.80) only for a **75% or larger** reduction. Read the effect
  size, never a p-value.
- **CONFIRM at 64 trials on a fresh sample** — powered (~0.80) for a **50%** reduction.
- **A 25% effect is out of reach.** 128 trials reaches only 0.55. Do not commission a campaign
  aimed at a quarter-sized effect on this endpoint; find a more sensitive one or a bigger lever.

Note that 16×4 and 32×2 both land at ~0.80 for r=50%. Because pairing already cancels the
between-state term and ICC is low (0.213), **more fixtures does not beat more repeats on this
endpoint** — unlike the old damage table and unlike the landmark endpoint. Choose F for
generalisation, not for precision.

### The cost of zero-inflation

Zero fraction 0.551 in the paired pool → **~30% of pairs are zero–zero ties** and contribute nothing
to a signed-rank test. **Roughly 70% of the trials you pay for are informative.** Budget for that.

---

## The binding constraint nobody had costed: discriminating fixtures

Of **72** distinct (fixture, dose) states in the wave-17 library, only **7** are discriminating on
terminal survival — the rest sit at 0% or 100% and cannot move the endpoint at any `n`:

| state | survival |
|---|---|
| max_hp 53, dose 68 | 4/21 |
| max_hp 53, dose 65 | 5/8 |
| max_hp 53, dose 61 | 3/8 |
| max_hp 53, dose 58 | 4/8 |
| max_hp 42, dose 68 | 4/5 |
| max_hp 36, dose 68 | 4/5 |

**A wave-17 campaign using terminal survival cannot exceed F = 7 with the current library.** Any
design calling for F = 16 or 32 on that endpoint requires building new fixtures first. This is a
supply problem, and it is now the thing to fix before the next wave-17 campaign is commissioned —
the same lesson as "state count is the binding constraint" on the landmark endpoint, arrived at
from the opposite direction.

AUC relaxes this somewhat (it is graded, so near-saturated states still carry a little information),
but states whose trials are all exactly 0 contribute nothing to it either.

---

## Method notes

- Era-matched: mod `0.2.49`/`0.2.50`, `time_scale` 1.0. Trials with ≤50 captures excluded as
  aborted launches.
- Death adjustment on the 33 agent trials that died in wave 17 moves mean AUC from **0.0933
  truncated to 0.2379 death-adjusted, a shift of +0.1447**. Truncating rewards dying early; the
  size of that bias is why the adjustment is not optional.
- The simulation resamples the observed within-state pools with replacement, so it inherits their
  finite-sample noise. It is a design tool, not an inference.
