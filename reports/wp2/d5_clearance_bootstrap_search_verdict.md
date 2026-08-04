# §39 D5 clearance bootstrap and target-backed search verdict

**Date:** 2026-08-04
**Verdict:** **FAIL — liquidity-, exposure-, yield-, and cost-limited**
**Campaign:** not licensed; none run

## Derived requirement

With zero nominal-D5 victories, the target remains a model rather than a winner measurement:

`T_w = 1.75 × D0 winner-median target_w`

The scale is fixed from the already-measured D5 trajectory and §28's low health dose:
`round(1.314 × 1/0.75, 2) = 1.75`. The resulting primary targets through the wave-10 shop are:

| shop wave | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| target DPS | 78.75 | 192.50 | 306.25 | 402.50 | 525.00 | 665.00 | 787.50 | 945.00 | 1128.75 | 1338.75 |

The H50-derived `2.63×` curve was descriptive only. It produced the same actionable count as the
primary curve, confirming that target scale did not bind this Gate 0.

## Controls and denominator

The population is the same 16 terminal, era-matched `0.2.79-wp2-capture` nominal-D5 Ranger runs.
The denominator is every recorded `shop_go` at shop waves 1–10: **133 exits**.

| control | result | bar |
|---|---:|---:|
| target fields complete | **133/133 = 100%** | ≥99% |
| budget fields complete | **132/133 = 99.25%** | ≥99% |
| legal-reroll positive branch | **133/133** | nonzero |
| unaffordable-after-lock negative branch | **110/133** | nonzero |
| disabled/null changes | **0/133** | exactly zero |

All controls passed. Actual target-deficient rerolls joined to their next board **139/139 = 100%**.

## Preregistered result

Only **22/133 = 16.54%** of exits are target-deficient and can afford one more reroll after preserving
locked commitments. The unchanged reasons are 98 unaffordable-after-lock, 12 without clearance debt,
and one missing budget record.

| bar | result | verdict |
|---|---:|---:|
| actionable exit rate | **16.54%** vs ≥20% | **FAIL** |
| runs with actionable exits | **11/16** vs ≥12 | **FAIL** |
| minimum leave-one-run-out rate | **13.82%** vs ≥18% | **FAIL** |
| median leave-one-run-out rate | **16.47%** vs ≥20% | **FAIL** |
| largest run contribution | **22.73%** vs ≤20% | **FAIL** |
| observed search-yield denominator | **139** vs ≥30 | PASS |
| next-board join | **100%** vs ≥99% | PASS |
| useful next-board yield | **26/139 = 18.71%** vs ≥30% | **FAIL** |
| median reroll cost / gold | **39.23%** vs ≤10% | **FAIL** |
| p90 reroll cost / gold | **98.0%** vs ≤25% | **FAIL** |
| locked commitments preserved | **22/22 = 100%** | PASS |

Search yield is weakest where it matters most: wave 9 produced **1/16** useful next boards and wave
10 produced **0/13**. Across all target-deficient actual rerolls, only 38 positive affordable scored
weapon rows appeared; 33 cleared the 5%-impact floor, distributed across 26 boards.

The prediction that exposure would pass was falsified. The prediction that yield was the main risk
was directionally correct, but the result is broader: exposure, stability, yield, and both cost bars
fail together.

## Interpretation

This is not a weak target dose. Raising the target from `1.75×` to the H50 sensitivity `2.63×`
changes **zero** actionable exits because post-shop liquidity, not target classification, is binding.
The agent has already spent or committed nearly all available gold by `shop_go`; adding search at the
exit is too late. When actual search occurs, qualifying weapon boards arrive only 18.7% of the time,
and the extra reroll would consume a median 39% of remaining gold.

Therefore the explicit bootstrap is retained as a documented planning assumption, but the
**one-extra-reroll exit planner is closed**. It does not license a live screen. A future clearance
planner would have to allocate for offense earlier in the shop sequence or improve combat conversion
without depending on scarce exit liquidity. Existing evidence also closes ordinary buy re-ranking
(§§37–38), the DPS-band candidate filter (§36), and the prior level-up valuation surface; those nulls
must not be rerun under the new target without a genuinely different action mechanism.

## Artifacts

- preregistration: `d5_clearance_bootstrap_search_prereg.md`
- analyzer: `scripts/wp2_d5_clearance_bootstrap_search_gate0.py`
- full result: `d5_clearance_bootstrap_search_result.json`
