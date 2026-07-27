# The full-run prediction was built on a contaminated baseline. Corrected.

The plan of record predicted the pivot fix would move full-run win rate
**~63% -> 79%**. That baseline is wrong. **The corrected prediction is
0.395 -> 0.574.** The improvement was roughly right (+17.9 pp vs +16 pp); the
LEVEL was ~24 points too high.

No new machine time was spent on this — it is all from the existing archive.

## What went wrong: `last_wave == 20` is true for two different populations

The archive holds 1,411 runs. **933 of them are wave-20-only FIXTURE TRIALS**
from the finale campaigns, not full runs. They carry `last_wave == 20` exactly
like a full run that reached the finale, and they win far more often because
they start at wave 19 with a build that already got there.

| population | n | win rate | reached w20 |
|---|---|---|---|
| pooled (the naive count) | 1411 | **0.650** | 0.867 |
| full runs (>= 5 min) | 478 | **0.418** | 0.621 |
| fixture trials (< 5 min) | 933 | 0.768 | 0.992 |

The remembered "63.4% over 1,307 archived runs" is the pooled number. Every
prediction derived from it inherits the contamination.

**The tell was an arithmetic impossibility.** A 63.4% overall win rate cannot sit
above a ~55% wave-20 survival rate when surviving wave 20 is required to win.
That was not a paradox; it was two numbers from two different populations.

## Second contamination: the archive spans two eras that differ enormously

Full runs only, split by build era:

| era | n | P(reach w20) | P(survive w20) | win rate |
|---|---|---|---|---|
| WP1 (`0.1.x`) | 283 | 0.558 | **0.778** | 0.435 |
| WP2 (`0.2.x`) | 195 | 0.713 | **0.554** | 0.395 |

This is the known ~47-point collapse showing up in an independent sample. It also
means the pooled 0.418 is itself an era mixture and is not a baseline for
anything. **The shipped build's baseline is the WP2 row.**

## Wave-20 survival by boss — and the invoker is NOT free

| boss | full-run wave-20 survival |
|---|---|
| predator | 37/72 = **0.514** |
| invoker | 40/67 = **0.597** |

The record said **"invoker 5W/5 (100%); predator 7W/11 (63.6%)"**. Both were
tiny samples. The invoker having ~0.60 survival matters directly, because the
pivot fix **cannot touch an invoker wave** — it adds predator-mounted orbiters
and nothing else. So roughly half of all wave-20 arrivals get no benefit at all,
which the old derivation implicitly assumed away by taking the fixture-measured
1.000 as if it applied to every wave 20.

Boss identity is only recoverable for the WP2 era: WP1 runs predate the
combat-capture schema, so all 158 unidentified runs are `0.1.x`. That is a
structural gap, not a random one — the per-boss rates describe the WP2 era only,
which is the era we want.

## The corrected derivation

```
P(win) = P(reach w20) x [ share_pred x P(survive|pred) + share_inv x P(survive|inv) ]

P(reach w20)      = 139/195 = 0.713      (WP2 full runs)
share_pred        = 72/139  = 0.518
P(survive|pred)   = 0.514  pre-fix  ->  1.000  post-fix (fixture-measured 32/32)
P(survive|inv)    = 0.597            ->  0.597 (unchanged; the fix cannot reach it)

PRE  = 0.713 x (0.518x0.514 + 0.482x0.597) = 0.395
POST = 0.713 x (0.518x1.000 + 0.482x0.597) = 0.574
```

**The PRE arm reproduces the observed WP2-era full-run win rate exactly: 0.395
against 77/195 = 0.395.** That is a genuine calibration check — the terms were
measured independently of the total and were not fitted to it.

## Caveats, in the order that would change the number most

1. **`P(survive|pred) = 1.000` is FIXTURE-measured, not natural.** 32/32 on a
   library of 8 saved wave-19 states. A naturally-reached wave 20 may arrive with
   a weaker build. At 0.85 instead of 1.000 the prediction falls to **0.519**.
   This is the single largest source of error and the only one worth machine time.
2. **The WP2 era pools ~20 builds** (`0.2.0`-`0.2.49`), not just the shipped one.
3. Per-boss rates rest on 139 runs; the boss share (0.518) on the same sample.
4. Today's full runs on the shipped build: 2 complete, both **invoker**, one
   defeat and one victory at 105 damage — consistent with ~0.597, and n=2.

## Consequence

The cheap-derivation shortcut does NOT remove the need for full runs; it just
tells us what to expect from them (~0.57, not ~0.79) and which term to spend on.
The only measurement that would materially sharpen this is **post-fix predator
survival on naturally-reached wave 20s**, not more fixture trials.
