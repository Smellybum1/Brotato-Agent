# Wave 17: understood, and NOT currently actionable

Closing summary of the 2026-07-28/29 wave-17 investigation. Four preregistered
experiments, 232 trials, plus a 50-run observational sweep. Every rule was frozen before
its data existed and none was relaxed afterwards.

## The chain of results

**1. Stage A (observational, 25 died vs 25 survived).** Wave 17 is **BUILD-limited**. The
movement/uptime hypothesis — the only *controllable* story, since the agent steers while
weapons auto-fire — is **refuted on its own sign**: crowd-matched coverage is null in
every bin and uptime is HIGHER in dying runs. Only two entry stats separate: `nominal_dps`
28.26 vs 35.25 and `speed` 531 vs 499, with every defensive stat null. Dying builds bought
speed instead of damage.

**2. Round 1 (48 trials) — `UNINFORMATIVE_CEILING`.** Control failure 2/16 = 0.125 < the
0.15 bar. Efficacy contrast never computed. Not fixable by fixture selection: the library
spans the full Stage A capacity range, and entry capacity did not rank the replay
failures. The real obstacle is arithmetic — a 50% relative reduction at a 0.125 base rate
needs **680 trials / 48.8 h**.

**3. v2 (128 trials) — `NEAR_TOTAL_RESCUE`.** Control 7/64 = 0.109, H50 0/64, p=0.0066.
**But 4 of 7 control failures were ONE fixture**; drop it and the same rule returns
`UNINFORMATIVE_CONTROL`. The defensible claim was always the narrow one.

**4. v3 (24 trials) — `MODEST_DOSE_SUFFICIENT`.** Inside the reliably-failing fixture:
control 6/8, H75 **0/8**, H50 **0/8**, both p=0.0035. H50 replicated. The effect
SATURATED, so the minimum dose was unknown.

**5. v4 (32 trials) — `MIN_DOSE_ABOVE_25%`.** None of 0.95 / 0.90 / 0.85 rescue
(3/8, 5/8, 4/8 against control 6/8).

## The number that matters

**Rescuing a doomed wave-17 build requires roughly a 25% enemy-health reduction — about a
33% clearance-rate improvement. Below that, nothing works.**

| health | failure | note |
|---|---|---|
| 1.00 | 6/8 | control |
| 0.95 | 3/8 | not rescued |
| 0.90 | 5/8 | not rescued |
| 0.85 | 4/8 | not rescued |
| **0.75** | **0/8** | rescued, p=0.0035 |
| **0.50** | **0/8** | rescued, p=0.0035 |

The three intermediate arms carry **no ordering information** — their Wilson CIs overlap
each other and the control, so 3/8 < 4/8 < 5/8 is noise. Pooled they give 12/24 = 0.50 vs
0.75, p=0.207: a partial reduction that does not reach significance. The 0.85 -> 0.75
transition looks like a cliff (4/8 -> 0/8, p=0.0385) but that is CROSS-EXPERIMENT and not
a preregistered test.

## Why this closes wave 17 for now

The target is a **25-33% offense improvement on doomed builds**, and there is no known
lever to produce it:

- **Shop layer: CLOSED, null.** Every proxy inside the [0.370, 0.630] band; doomed runs'
  boards were marginally BETTER.
- **Movement: refuted** by Stage A, on the wrong sign, not merely unproven.
- **Build allocation** is the only remaining suspect (dying builds bought speed over
  damage) and no mechanism has been identified that would change it.

Wave 17 is **~8.3% of runs** (3/36 measured). Eliminating it entirely would move win rate
from 0.722 to roughly 0.80 — real, but it requires a lever we do not have.

**Recommendation: stop wave-17 work.** Not because it is unimportant or unexplained, but
because the required intervention size is now known and no available lever reaches it.
If a build-side lever ever appears, the harness is built and the experiment is cheap:
a reliably-failing fixture answers a dose question in ~1.7 h.

## What would change this

- **A reliably-failing fixture library.** Yield is 1-in-16 from arbitrary runs but
  **1-in-1 from runs that die at wave 17**; ~10 fixtures costs ~90-110 full runs
  (30-36 h). Only worth spending if a candidate lever exists to test.
- **Generality.** Every dose result rests on ONE build. The threshold could differ
  elsewhere.
- **A finer bracket** between 0.85 and 0.75 would need far more than 8 reps/arm — the CIs
  above show why.

## Method notes worth keeping

- `enemy_scaling` in the save is a **verified, controller-free intervention lever**: exact
  dose on every enemy and the boss, confirmed at wave 17 across 7 types. No deploy, no
  identity-constant change, and it does not spend the waves-<20 internal control.
- **A doomed build replays as doomed** — `run_1785214891_49265` failed 4/4, 6/8, 6/8 as
  control across three independent experiments.
- Two traps that would have produced confident nonsense: `enemy_hp_pool` as an outcome is
  **rescaled by the treatment itself**; and enforcing boss identity below wave 20 would
  have invalidated exactly the trials that SURVIVED.
