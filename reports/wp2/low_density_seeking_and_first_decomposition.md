# Low-density seeking: already implemented, and over-implemented relative to the winner

**Date:** 2026-07-29. Operator proposal + the first read from the new desire decomposition.

## The proposal

> When there are a lot of enemies the agent's avoidance technique should be to identify areas of
> low enemy density and head towards them, constantly, while avoiding getting hit.

## Test: does the WINNING policy do this?

The decisive question is not whether the idea sounds right, it is whether the arm that actually
rescues wave 17 — the human — behaves that way. We have matched ticks for both.

At each tick, sample candidate headings, project the player forward by `speed * 0.5 s`, and count
enemies within 280 u of that projected point. Rank the **realised** heading among the candidates
(rank 0 = chose the emptiest direction).

**Sampled at 8 directions, matching the human's 8-way keyboard so both arms choose from the same
set** (chance rank = 3.5). Waves 17-20, matched fixture C, same enemy dose:

| | ticks | mean rank | median | picks the EMPTIEST of 8 | enemies near projected point |
|---|---|---|---|---|---|
| **AGENT** | 21,789 | **1.25** | **0.0** | **0.724** | **0.86** |
| **HUMAN** | 14,893 | 2.37 | 2.0 | 0.416 | 1.59 |

*(At 16 directions the gap is wider still — agent 2.51 vs human 4.90 against a chance of 7.5 — but
that comparison is unfair to the human, who cannot reach 8 of the 16 headings.)*

**The agent already does this, and does it nearly twice as often as the human who wins.** It picks
the emptiest of eight directions on **72.4%** of ticks. The human deliberately moves toward roughly
**twice** the local enemy density (1.59 vs 0.86 enemies near the projected point), and wins.

Mean rank by crowd band shows the agent is *more* low-density-seeking than the human at **every**
level of crowding (5-9: 0.43 vs 1.90; 10-19: 0.89 vs 2.41; 20-29: 1.65 vs 2.76; 30+: 1.98 vs 2.35).

**Verdict: the intuition is already in the policy, and pushing further in that direction moves away
from the behaviour that wins.** This is consistent with everything else measured today — the agent's
binding constraint is not avoidance, it is kill rate. It converts 1.7x less of the pack into targets
and spends one tick in seven with nothing in range.

## But the idea did surface a real defect

The first read from the new per-term desire decomposition (build `0.2.53`, run
`run_1785313331_32565`, **1159 wave-17 captures, 0 missing, 1159 distinct `seq` values** so every
tick is fresh) shows the dedicated density-avoidance force is **dead**:

| term | mean outward push | mean magnitude |
|---|---|---|
| `enemy_engagement` | **+1.678** | 2.062 |
| `inward_damp` | +0.012 | 0.012 |
| `engage_strafe` | 0.000 | 0.617 |
| **`pack_density`** | **0.000** | **0.000** |
| `edge_kite`, `early_hunt`, `tree`, `wall` | 0.000 | 0.000 |
| `circling` | −0.000 | 0.031 |
| `loot` | −6.844 | 10.336 |
| `consumable` | −7.634 | 11.162 |
| `center` | −10.607 | 20.190 |

(*outward = projected away from the nearest threat; positive pushes away.*)

**`_pack_density_repulsion` — the exact "shove off dense packs" force — contributes EXACTLY ZERO at
wave 17.** It sits behind `elif not out_of_range:`, and `out_of_range` is **true on 87.5% of ticks**.
On the remaining ticks the edge-kite branch owns it, and `edge_kite` never fires either (it needs
`nearby >= 10`, and `nearby` is 0 on 90% of ticks — the same dead threshold documented four times
over now).

So the agent achieves its low-density seeking **entirely through `enemy_engagement`**, which is the
only outward term at all — 99.3% of the total outward push — and is *small* in magnitude (2.06).
The largest-magnitude terms (`center` 20.19, `consumable` 11.16, `loot` 10.34) all pull **inward**,
and `center` is itself gated off on the 87.5% of ticks where `out_of_range` holds.

**The standoff is not produced by a strong repulsion. It is produced by a weak but persistent
outward term while everything that would pull the agent in is conditionally switched off.** That is
a different — and more actionable — picture than "some force pushes it away", and it is the first
thing the decomposition bought.

## Caveats

- The decomposition is **one run, 1159 ticks**. Directionally clear (several terms are exactly zero,
  which is structural rather than statistical) but the magnitudes should not be hardened until it is
  run across several fixtures.
- `out_of_range` at 87.5% is computed against `engage`, and dosing `engage` was already shown inert
  for the standoff — so this is a gating effect, not a contradiction of that result.
- The low-density comparison uses realised velocity, so the human's is 8-way quantised. The
  8-direction table controls for that; the 16-direction one does not and is reported only for
  completeness.
