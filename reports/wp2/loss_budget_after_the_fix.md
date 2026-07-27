# After the pivot fix, 67% of remaining losses happen BEFORE the finale

Derived from the corrected full-run terms (`fullrun_derivation_corrected.md`)
over **197 WP2-era full runs** (`duration_ms >= 300000`, `mod_version` `0.2.*`).
No machine time.

## The loss budget

Observed, pre-fix:

| outcome | runs | share |
|---|---|---|
| die BEFORE wave 20 | 56 | 0.284 |
| die AT wave 20 | 63 | 0.320 |
| win | 78 | 0.396 |

Projected, with the shipped pivot fix taking predator wave-20 survival to 1.000
and leaving the invoker at 0.597 (the fix adds predator-mounted orbiters and
nothing else, so it cannot reach an invoker wave):

| outcome | share |
|---|---|
| die BEFORE wave 20 | **0.284** — *unchanged, the fix cannot touch it* |
| die AT wave 20 | 0.139 |
| win | 0.577 |

**Of the 0.423 remaining losses, dying before wave 20 is 0.284 = 67.2%.**

Every finale intervention on this project — v2 heading selection, the 60 Hz rate
change, co-rotation, the ring-radius arm, the pivot fix itself — addresses the
smaller third. That was correct while wave 20 was the dominant loss; it is no
longer.

## The pre-20 deaths are concentrated at wave 17

Deaths by `last_wave`, WP2-era full-run non-victories:

| wave | deaths |
|---|---|
| 20 | 63 |
| **17** | **22** |
| 10 | 9 |
| 19 | 9 |
| 15 | 5 |
| 13 | 5 |
| 16 | 3 |
| 11 | 3 |

**Wave 17 alone is 22 of 56 pre-20 deaths = 39%** — more than waves 10, 13, 15,
16 and 19 combined.

Wave 17 is also exactly where the late-game regime begins by an independent
measure: per-wave reversal rate runs ~0.00-0.01 through wave 9, then jumps to
0.269/0.102 at w17, 0.306/0.252 at w18, 0.380/0.258 at w19
(`brotato-wave20-fixture-harness`). Two unrelated signals — where the agent dies,
and where its movement changes character — both mark wave 17.

**That is a correlation, not a mechanism**, and it should not be read as one
until the wave-17 deaths are actually attributed. The oscillation measurement
also came with a live caveat: waves 1-19 recompute at 60 Hz but capture at 20 Hz,
so reversals can alias there in a way they cannot at wave 20.

## Scope note

The operator directive fixes CONTROLLER scope at wave 20 only, with waves <20 as
the internal control. **This report is analysis, not a scope change** — nothing
here proposes touching behaviour below wave 20, and doing so would cost the
internal control that made several earlier findings interpretable. If a wave-17
intervention is ever justified, that trade has to be made deliberately and by the
operator.

## The two failures are DIFFERENT problems — a unification hypothesis, refuted

Wave 17 separates on **offense** and not defense. I proposed that the whole late
game might therefore be an offense story, which would have explained why every
movement intervention nulled. **It does not hold.** Same covariates, wave-20
full-run outcomes, rank-biserial P(defeat > victory), null band [0.370, 0.630]:

| | weapon damage | max_hp | armor |
|---|---|---|---|
| **wave 17** | **0.188** | 0.479 | 0.426 |
| wave 20, invoker (42W/29L) | 0.553 | 0.320 | 0.620 |
| wave 20, predator (38W/35L) | 0.464 | 0.370 | 0.350 |

**Offense does not separate wave-20 outcomes for either boss.** If anything
defense weakly does, but at P = 0.32-0.37 those sit at the very edge of the null
band and are suggestive at most.

That is mechanistically coherent: **wave 17 is a 60 s timed wave** where the
arena saturates unless enemies are cleared fast enough (offense), while **wave 20
is a boss fight** decided by surviving incoming damage (defense and dodging). So
the finale movement work was aimed at the right modality for wave 20 — and wave
17 is not more of the same.

Caveat: weapon damage is read at the first wave-20 capture, and these are
marginal effects at n≈70 per boss.

## Caveats

- The projection inherits every caveat of the corrected derivation, chiefly that
  post-fix predator survival of 1.000 is FIXTURE-measured; at 0.85 the win rate
  falls to 0.519 and the pre-20 share of remaining losses rises further still.
- 197 runs pool ~20 builds across `0.2.0`-`0.2.49`, not the shipped build alone.
- Wave-17 deaths have NOT been attributed. Whether they share a mechanism with
  the wave-20 failures, or with each other, is unknown at the time of writing.
