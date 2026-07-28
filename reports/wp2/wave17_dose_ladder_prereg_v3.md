# PREREGISTRATION v3 — dose ladder INSIDE the one reliably-failing fixture

**Frozen 2026-07-29 ~05:35, BEFORE any v3 trial was run.**

## Why single-fixture, deliberately

v2 established `NEAR_TOTAL_RESCUE` but the evidence was carried by ONE fixture:
`run_1785214891_49265`, which failed **4/4 under control** and **0/4 under H50**
(p=0.0143 within-fixture). Twelve of sixteen fixtures never failed in either arm.

The unanswered question is **actionability**: does a MODEST clearance gain help, or does
only a 2x rescue work? Across a mixed library that costs ~48 h (340 trials/arm at a
0.125 base rate). **Inside a fixture whose control rate is ~1.0 it is affordable**, because
the contrast is 8/8 vs 0/8 rather than 8/64 vs 0/64.

**The cost is generality.** This is a single build. Whatever it returns is a statement
about THAT build, not about wave 17. It is stated that way in the writeup or not at all.

## Design

Fixture `run_1785214891_49265` (entry nominal_dps 22.10, below Stage A's died median
28.26; boss invoker). Arms `C` (health 1.00), `H75` (0.75), `H50` (0.50).
**8 reps x 3 arms = 24 trials**, ~1.7 h. Arm order randomised, seed recorded.
Same verified instrument; no deploy, no identity-constant change, controller untouched.

## Outcome

Primary: wave-17 failure <=> observed wave set is exactly `[17]`.
Still banned: `enemy_hp_pool` (dose rescales it), downstream win rate, damage taken.

## Decision rules — frozen

**`UNINFORMATIVE_FIXTURE`** — control fails **< 6 of 8**. The fixture is not reliably
failing after all and v2's 4/4 was partly luck. Everything below is void. **NOT a null**,
and it would also weaken v2's headline, which must then be restated.

Otherwise:

**`MODEST_DOSE_SUFFICIENT`** — `H75` fails **<= 1 of 8** AND Fisher one-sided p < 0.05 vs
control. Reading: a ~33% clearance gain rescues this build. An agent-side or build-side
lever of that magnitude becomes worth scoping.

**`MODEST_DOSE_INSUFFICIENT`** — `H75` fails **>= 4 of 8** AND `H50` fails **<= 1 of 8**.
Reading: only the ~2x rescue works on this build; modest improvements will not move it,
and wave 17 should be deprioritised relative to its 8.3%-of-runs share.

**`INTERMEDIATE`** — `H75` fails 2 or 3 of 8. Partial rescue. Report the numbers, make no
strong claim, do not reinterpret as either of the above.

**`H50_DID_NOT_REPLICATE`** — `H50` fails **>= 2 of 8**. This contradicts v2's 0/4 on this
same fixture and takes precedence over every reading above: report the inconsistency and
stop rather than explaining it away.

## Analysis

Fisher one-sided per contrast (verified implementation: matches Fisher's tea table 17/70
and the closed-form hypergeometric; an earlier version summed the wrong tail and would
have made a positive verdict unreachable). No pooling with v1 or v2 data — those were
collected under different rules.
