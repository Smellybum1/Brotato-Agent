# Is the scorer's item allowlist miscalibrated?

**Answered 2026-08-02 from existing data — 0 new runs.** Motivated by the fairy divergence: an
external D5 guide ranks `item_fairy` its first S-tier universal item, while our scorer's allowlist
omits it entirely. The direct test (offer→buy on fairy) is underpowered by ~33 h of runs
(`acquisition_block1_result.md`). This is the cheap design that replaces it.

## The design, and why it isolates the allowlist

`rogueranker_item_allowed()` permits `ROGUERANKER_ITEM_TIERS` ∪ `WIKI_USEFUL_ITEM_TIERS`; anything
else scores **-1e9 from `ROGUERANKER_ITEMS_ONLY_FROM_WAVE` = 11**. The **bonus**
(S +28 / A +18 / B +10 / C +3 / **D −12**) comes only from the rogueranker list. Measured against the
installed zip: **RR 68, WIKI 98, overlap 0, union 166.** So three disjoint classes:

| class | allowed from w11 | rogueranker bonus |
|---|---|---|
| 1 — on rogueranker | ✅ | ✅ |
| 2 — wiki only | ✅ | ❌ |
| 3 — off both | ❌ **vetoed** | ❌ |

**Classes 2 and 3 differ only by the wave-11 veto.** In **waves 1–10** the scorer treats them
identically — no veto, no bonus for either — so their buy rates there are the scorer's *own*
valuation, uncontaminated by the allowlist mechanism being tested. That is the comparison.

## Result — the allowlist is CONFIRMATORY, not contradictory

24 full runs (the post-fairy §27 cells), waves 1–10, conditioned on **affordable** (`gold >= price`):

| class | affordable offers | bought | buy rate |
|---|---:|---:|---:|
| 2 — wiki only | 978 | 521 | **0.533** |
| 3 — off both (vetoed from w11) | 431 | 71 | **0.165** |

**Ratio 3.23x. Risk difference 0.368, 95% CI [0.321, 0.415]. χ² (Yates) = 164.8, p ≈ 1.0e-37.**

⇒ In the window where the allowlist does nothing, **the scorer independently buys allowlisted items
~3x more often than off-list ones.** The wave-11 veto largely ratifies a preference the scorer already
holds; it is not an external judgment overriding it.

### Composition confound ruled out
The two classes are near-identical in the things that could drive a buy-rate gap:

| class | median price | tier mix (t0/t1/t2) |
|---|---:|---|
| 2 | 44 | 0.754 / 0.218 / 0.029 |
| 3 | 43 | 0.724 / 0.225 / 0.051 |

And the gap holds **at every tier**, so it is not a composition artifact:

| tier | class 2 | class 3 |
|---|---|---|
| 0 | 393/737 = 0.533 | 49/312 = 0.157 |
| 1 | 117/213 = 0.549 | 18/97 = 0.186 |
| 2 | 11/28 = 0.393 | 4/22 = 0.182 |

### Class 1's low rate is composition, not a puzzle
Class 1 buys at only 29/152 = 0.191 despite carrying the bonus. Explained, not anomalous: its median
price is **89** (2x the others), its tier mix skews high (0.191/0.559/0.250), and the rogueranker list
contains **11 D-tier entries carrying a −12 penalty** (S 7 / A 17 / B 15 / C 18 / D 11). Class 1 holds
both the best- and worst-ranked items. It plays no part in the class-2-vs-3 comparison.

## ⛔ What this does NOT establish

- **It does not show the allowlist is RIGHT about the game.** It shows the allowlist and the scorer
  *agree*. They may share a common source of error — the scorer's tuning and the community rankings
  are not independent. The D5 guide's claim about Fairy is about real game value, which a
  revealed-preference test cannot reach. **Answering that needs an OUTCOME-based design.**
- **Aggregate agreement does not exonerate individual entries.** `item_fairy` may still be a specific
  gap, exactly as previously recorded; this result only removes the *systemic* reading.
- Single era (178-179), one campaign, 24 runs, all full runs. Fixture contamination is not a risk here
  (every run starts at wave 1), but the item pool is one era's.

## Bearing on the fairy question

The hypothesis *"the allowlist is a blind spot that overrides the scorer's own judgment"* is **dead**.
What survives is the narrower and harder question — whether the scorer *and* the allowlist are
jointly wrong about a handful of items. Fairy is the only such item with an external case, and pricing
it costs ~33 h of runs for ~10 buying opportunities. **Recommend not paying that** on current evidence:
the systemic worry that motivated it has been answered negatively for the cost of one analysis.
