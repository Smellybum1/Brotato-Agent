# §43 — Route-conversion persistence verdict

**Verdict: PASS / `TRANSIENT_REVERSAL`.** This is a valid mechanistic diagnosis, not a policy
qualification or a survival result. No Brotato process was launched and no machine time was spent.

Pre-registration: `route_conversion_persistence_prereg.md`, committed as `4aa3158` before any
episode-duration, future-displacement, or projection-calibration aggregate was computed. The frozen
analyzer and its tests were committed separately as `689220c` before execution. Result artifact:
`route_conversion_persistence_result.json`.

## Controls first

All four fixed §42 treatment summaries matched the exact build, policy, Ranger/D5/opener, era,
terminal-completeness, and enabled-treatment contract. The capture stream supplied both positive and
negative route controls in every run.

| control | result | bar |
|---|---:|---:|
| fresh captures | **26,346/26,346** | report denominator |
| stale captures | **0/26,346** | zero with denominator |
| non-increasing timestamps | **0/26,346** | zero with denominator |
| applied selected heading = emitted action | **1,715/1,715 = 100%** | ≥99.9% |
| identified living threats | **229,688/229,688 = 100%** | ≥99.9% |
| duplicate-ID captures | **0/26,346** | zero with denominator |
| eligible starts with +0.60 s future | **1,238/1,241 = 99.76%** | ≥90% |
| cohort bookkeeping failures | **0/1,238** | zero with denominator |
| control faults | **0** | none permitted |

Per-run episode/future denominators were 484/484, 135/136, 442/442, and 177/179. The three missing
futures were excluded, never assigned zero. Six analyzer tests covered the frozen contract and its
positive, negative, boundary, and zero-denominator branches.

## Deciding results

### A. Temporal persistence — fails

The 1,715 delivered conversions fragmented into 1,241 episodes; 1,238 had matched futures. Episode
duration was p10/median/p90 **0.051 / 0.051 / 0.102 seconds**. Only **11/1,238 = 0.89%** lasted
0.30 seconds and **1/1,238 = 0.081%** lasted the full 0.60-second projection horizon. Both frozen
transience boundaries fail by a wide margin: median is below 0.30 seconds and fewer than 25% persist
to 0.60 seconds.

This is not a small-gain subset. The 1,227 episodes below 0.30 seconds retain median initial
projected gain **0.1538**, the same headline gain observed in §42.

### B. Executed displacement — fails

At +0.60 seconds, normalized forward progress along the initial conversion heading was
p10/median/p90 **−0.316 / 0.377 / 0.896**, below the frozen median ≥0.50 bar in every run
(per-run medians 0.389, 0.445, 0.357, 0.381). **306/1,238 = 24.72%** of matched starts had negative
forward progress. The current emitted heading's median dot product with the initial conversion fell
from **0.707** at +0.20 seconds to **0.086** at +0.60 seconds.

### C. Projection calibration — passes

The failure is not explained by the frozen moving-threat projection test. Against the original
identified cohort at +0.60 seconds:

- median selected projection: **0.7368**;
- median realised resolved-or-in-range: **0.7205**;
- median absolute error: **0.0714**, passing ≤0.20;
- Spearman rank correlation: **0.6855**, passing ≥0.30.

Both calibration bars pass over **1,238** matched episodes. This does not prove a causal trajectory
counterfactual—the player mostly did not execute the path—but it falsifies the preregistered claim
that gross one-step projection miscalibration is the primary explanation.

## Independent reproduction

A separate streaming enumeration that did not import the analyzer reproduced all four fresh/applied
and episode/future counts, pooled **26,346 / 1,715 / 1,238**, duration median **0.051**, persistence
counts **11** and **1**, forward median **0.3769586982**, and median absolute calibration error
**0.0714428571** exactly.

## Interpretation and next licensed fork

The §42 treatment had authority for one decision and almost none across controller time. The local
in-range choice is replaced before its 0.60-second prediction can be executed. This closes another
PACK/retention/deadband dose and closes a repeat of the same one-step mediator screen.

The next viable combat mechanism is a **bounded temporal conversion latch with current-tick safety
revalidation**: when guarded conversion fires, retain its heading across decisions only while a
current candidate still satisfies the unchanged projectile floor, §41 body-retention/subcritical
guard, and enemy-slack admission. Release immediately on safety failure; cap commitment at the fixed
projection horizon. This is mechanism-distinct from increasing the old continuity score: it gives a
delivered conversion stateful authority rather than merely adding another preference to the same
ranking.

§43 licenses only a separately preregistered offline availability/safety gate for that mechanism.
It does **not** license implementation, a live mediator screen, or a survival campaign.
