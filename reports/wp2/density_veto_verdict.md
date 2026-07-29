# The density-veto diagnosis is refuted at observed doses

**Date:** 2026-07-29. **Item 4 of `NEXT_SESSION_PLAN.md`, part (a): the joint contingency.**
**Verdict: NO-GO on the density-veto causal story. The phenomenon it was invented to explain is
real; the proposed mechanism is not the cause.**

No machine time was spent. Everything here is computed from the existing capture archive.

---

## What was being tested

The standing diagnosis was that `_loot_attraction`'s hard density veto
(`potential_field.gd:2925`, `if nearby >= PACK_DENSITY_SOFT: return Vector2.ZERO`) zeroes ordinary
loot attraction under crowding, starving the late-game economy. The planned intervention was to
replace that binary veto with a safety-constrained resource tie-break.

The gate question from the plan was deliberately hostile to that story:

> Which single component changes the FINAL command, after every downstream override? If nothing
> changes the final command, the density-veto diagnosis is inert and everything downstream is
> wasted effort.

It does not survive an earlier question: **the veto almost never fires at all.**

---

## 1. The veto's trigger sits in the far tail of its own variable

`_count_nearby_enemies` counts enemies within `PACK_DENSITY_RADIUS = 280.0` (bosses count 2).
`PACK_DENSITY_SOFT = 8.0`. Measured over waves 17-19:

| `nearby` | share of ticks |
|---|---|
| 0 | **0.9054** |
| 1 | 0.0493 |
| 2 | 0.0169 |
| 3-7 | 0.0255 |
| **>= 8 (the veto)** | **0.0029** |

mean 0.219, median 0, p90 0, p99 5, max 11. (Independent recomputation in the primary session over
3 full runs, 11,212 captures; the delegated sweep over the full 366-run era pool returned the same
shape, T1 = 0.0058 there, the difference being that its pool includes 33 wave-17 fixture trials
which are selected for being crowded.)

**The 8-threshold is not calibrated against a mass of the distribution — it is a far-tail cut.**
This is the same trap logged before: a threshold set without checking it against the real
distribution of the quantity it gates.

## 2. The crowd variable that produced the original finding is a DIFFERENT variable

The loot-directedness gap was binned on **total enemies on the map**. That variable is large and
well-spread — median 16, p75 28, p90 35, max 55. The veto's variable is **local** enemies within
280 units, which is 0 on 90% of ticks.

They are nearly uncorrelated at the decision boundary: of the 41.4% of wave-17-19 ticks with
**20 or more total enemies on the map, only 0.71% have `nearby >= 8`.**

The evidence that motivated the density-veto diagnosis therefore never implicated the density veto.

## 3. Decomposing the actual cause of zero loot attraction

Classifying every wave-17-19 capture by the first branch that would zero ordinary loot attraction,
in the order `compute_movement` evaluates them (5 full runs, 18,686 captures):

| cause | captures | share |
|---|---|---|
| **loot attraction is LIVE (nothing vetoes it)** | 16,635 | **0.8902** |
| no materials on the ground | 1,737 | 0.0930 |
| late-survival HP branch (`hp_ratio <= 0.85`, w17-19) | 276 | 0.0148 |
| all piles corridor-blocked (`blockers > LOOT_PACK_ALLOW`) | 32 | 0.0017 |
| **density veto** | **6** | **0.0003** |

By total-enemy band, the density veto reaches 0.002 only in the 30+ band and is exactly zero in
every other band. The late-survival branch is the largest of the three suppressors and is still
only 0.074 at 30+ enemies.

## 4. The gap lives ENTIRELY inside the unvetoed regime

Restricting to ticks where loot attraction is fully live — not late-survival, materials present,
`nearby < 8`, at least one pile with an admissible corridor — the crowding effect is undiminished:

| total enemies | n | median angle to nearest admissible material | fraction heading AWAY (>90°) |
|---|---|---|---|
| 0-9 | 5,031 | 47.6° | 0.2838 |
| 10-19 | 5,223 | 78.2° | 0.4342 |
| 20-29 | 3,481 | 84.8° | 0.4694 |
| 30+ | 2,900 | 89.1° | 0.4914 |

Pooled n = 16,635, median 72.4°, fraction away 0.4061.

**The agent abandons loot under crowding on ticks where nothing has vetoed loot attraction.**
The monotone degradation from 47.6° to 89.1° is entirely a property of the unvetoed regime.

---

## What this changes

**Dead:** the density-veto causal story, and with it the planned intervention ("replace binary
`loot attraction = 0` with a safety-constrained resource tie-break"). That intervention targets a
branch that fires on 0.03% of ticks. Shipping it would have been v128 again — a real defect that is
not load-bearing — except this time we would have paid for a campaign to discover it.

**Alive and unchanged:** the phenomenon. The loot-directedness gap is real, it is intrinsic to the
agent (reproduced on its own runs), it grows monotonically with crowding, and it is now localised
to a regime where no veto is responsible.

**The remaining mechanism is force balance, not suppression.** `_loot_attraction` returns
`LOOT_ATTRACTION * greed * safety * clear_mult / dist` per pile, with `LOOT_ATTRACTION = 120` and,
above wave 15, `falloff = dist`. For a pile 400 units away that is ~0.3 × greed × safety, summed
against engagement, strafe and repulsion terms that scale with enemy count. The v118 comment in the
source says exactly this — "engagement and strafe forces out-vote the per-item loot pull" — and it
was written about the wave-10 case, not believed for the late game.

## The redirected gate

Item 4b's ablation set was `CURRENT / NO_DENSITY_ZERO / NO_STALL_REQUIREMENT / NO_HP_SUPPRESSION /
NO_FINALE_SUPPRESSION`. Three of those five now have no dose to ablate. Their combined ceiling on
waves 17-19 is 1.68% of ticks, before any downstream override, so the ablation as specified cannot
return a positive regardless of the data — the same design-time failure as a test statistic that
cannot return the positive.

The gate should instead ask whether the **loot term's weight** can change the final command in the
crowded stratum. That is a different experiment and it needs the offline `_build_desire` force
decomposition, which does not exist yet.

**Do not build the tie-break intervention.** Do not spend a campaign on the density veto.

## Method notes and limits

- Run selection is era-matched (mod `0.2.49`/`0.2.50`, policy `0.1.129`, `time_scale == 1.0`).
  Pooling across the 47-point win-rate collapse would have been meaningless.
- `payload.valid` is **true on 100%** of 1,844,865 captures in this era — that filter is vacuous
  here and should not be cited as a quality control.
- `summary.json`'s `materials_spent` field reads **0** while the true figure for the same run is
  5,378. Add it to the list of structurally uninformative telemetry fields.
- The angle metric is to the *nearest admissible* material and inherits the known weakness already
  on record: target identity can switch between ticks and manufacture apparent bimodality. It is
  used here only as a relative comparison across crowd bands within one arm, which that weakness
  does not threaten.
- This is a contingency and conditioning analysis. It does **not** prove that changing the loot
  weight would change the final command; it proves that the vetoes cannot, because they are not
  active.
