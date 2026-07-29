# Closing the collection-deficit line: items 4b and 6

**Date:** 2026-07-29. **NO-GO on both.** Decided under the standing delegated-decision authority.
No machine time was spent reaching this.

---

## The full dose chain, measured

The thesis was that the agent's late-game collection deficit is caused by a suppression mechanism
inside `_loot_attraction`, and that relieving it would rescue wave 17. Every link in that chain is
now measured, and **every suppressor is inert**:

| suppressor | dose at waves 17-19 | verdict |
|---|---|---|
| binary density veto (`nearby >= PACK_DENSITY_SOFT`) | fires on **0.03%** of ticks | inert |
| `safety = min(1, threat_dist/280)`, floor 0.20 | **median 1.000**, at-floor on **0.0%** | inert |
| `greed = _loot_greed_mult(wave, nearby)` | **constant 2.6** (the sparse multiplier always applies) | inert |
| per-pile corridor veto (`blockers > 2`) | zeroes ALL piles on **0.17%** of ticks | inert |
| late-survival HP branch (`hp_ratio <= 0.85`) | **1.48%** of ticks | too small to carry it |

And the loot force itself does not weaken under pressure — **it gets stronger**, because more
enemies means more material on the ground. Median `|loot force|` by total-enemy band:

| enemies | 0-9 | 10-19 | 20-29 | 30+ |
|---|---|---|---|---|
| median nearest threat (u) | 534 | 494 | 471 | 399 |
| `safety` | 1.000 | 1.000 | 1.000 | 1.000 |
| **median `\|loot force\|`** | **2.85** | **4.87** | **8.04** | **6.72** |

The nearest enemy sits 399-534 units away at the median — far outside `SAFETY_DISTANCE = 280` — so
the safety throttle never engages. This is the third threshold found sitting outside the support of
its own variable.

Meanwhile the behaviour it was supposed to explain is undiminished: on these same unvetoed,
unthrottled ticks the median heading-to-loot angle still degrades **47.6° → 78.2° → 84.8° → 89.1°**
across those bands.

**Conclusion: the loot term is not suppressed, throttled, or weakened. It is out-voted.** The cause
lies entirely in the competing terms of `_build_desire` (engagement, strafe, repulsion) growing
faster with enemy count than the loot term does, and/or in the downstream safety tail.

---

## Item 4b — NO-GO at Gate 0

The original ablation set (`NO_DENSITY_ZERO` / `NO_STALL_REQUIREMENT` / `NO_HP_SUPPRESSION` /
`NO_FINALE_SUPPRESSION`) has a combined ceiling of **1.68% of ticks** before any downstream
override — a test that could not return a positive regardless of the data.

The redirected version — "can the loot term's *weight* change the final command?" — also fails
Gate 0, for a different reason. Any weight large enough to win against terms that scale with enemy
count is not a targeted fix; it is a **rebalance of the whole desire field**. That class of change
is precisely what produced the 47-point win-rate collapse that ran ~20 versions invisibly. It
should not be attempted on the current evidence, and certainly not to chase an effect whose payoff
is now known to be small (below).

Building the offline `_build_desire` port to measure the force balance would cost real effort and,
at best, quantify a mechanism we have already decided not to act on. **Not built.**

## Item 6 (economic-rescue arm) — NO-GO

The arm was designed to answer "would a richer build have helped?" by crediting historically
stranded value into the wave-16 landmark save. Three independent measurements say the premise is
already answered, negatively:

1. **The human is not richer.** Over waves 1-19, human gross income **5380** vs agent median
   **5328** — ratio 1.010, with 16 of 31 agent runs below the human. The one trajectory that *did*
   rescue wave 17 accumulated no more currency than the agent does.
2. **Stranding costs timing, not totals.** The wave-end sweep credits ground material as bonus gold;
   ground value is fully credited in 76% of late-wave instances, and total income comes out equal
   despite the human's bag draining 20/20 against the agent's 76.7% on waves 17-20.
3. **Collection cannot explain wave-17 survival anyway** — materials collected during wave 17 are
   spent after it. This was always in the record; the new measurements remove the remaining
   indirect route (a richer *entering* build), because the incomes are equal.

Spending ~5-7 machine hours to bound a pathway that the natural experiment already found inert is
not a good trade.

**What would reopen it:** a demonstration that *timing* rather than *total* matters — i.e. that
material arriving before shop N rather than after it changes what gets bought. That is measurable
offline from the existing archive (compare `gold_before` at each shop against the counterfactual
where swept value arrived pre-shop) and costs nothing. It is the honest successor question, and it
is NOT what item 6 proposed.

---

## What survives, and where the line actually goes

**Survives, unchanged:** the human rescued wave 17 on the matched fixture at the undiluted dose,
4/21 vs 5/5, p = 0.00192 (re-verified today). Wave 17 remains movement-actionable.

**Now excluded:** collection/economy as the mechanism of that rescue. The suppressors are inert,
the loot force is strong and rising, and the incomes are equal.

**Therefore the movement advantage is combat positioning, not resource routing.** The corroborating
observation from today's kill analysis: on waves 1-19 the human cleared **94.96%** of spawns against
an agent median of **92.77%** (beaten by 1 of 31 runs), leaving far fewer enemies alive at the timer
in waves 15-19 (e.g. w18: 12 vs 23) — though build and movement are confounded there and it is n=1.

**The next question is the loot-independent one:** what does the human do differently in the combat
geometry of the failing stratum? That is a question about engagement distance, pack handling and
the safety tail — not about loot at all.
