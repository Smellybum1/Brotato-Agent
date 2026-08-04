# §38 positive-score lexicographic DPS Gate 0 verdict

**Date:** 2026-08-04  
**Verdict:** **FAIL — constrained exposure narrowly below bar**  
**Campaign:** not licensed; none run

## Fixed rule

On an already-authorized nominal-D5 waves 1–11 buy, retain only candidates with incumbent
`board_scores.score > 0`, then select maximum immediate effective weapon-DPS gain. Zero/negative,
skipped, untrusted, full-slot, and non-buy surfaces remain unchanged. The preregistration fixed one
rule with no coefficient or threshold ladder.

## Controls and denominator

The full policy denominator is **409** buys across the same 16 terminal, era-matched D5 Ranger runs.
All inherited §37 controls passed before §38 was computed:

| control | result | bar |
|---|---:|---:|
| offer/row join | **736/736 = 100.00%** | ≥99% |
| loadout trust | **224/232 = 96.55%** | ≥95% |
| ordinary-weapon gain parity | **253/253 = 100.00%** | ≥99% |
| baseline reproduction | **222/223 = 99.55%** | ≥99% |
| disabled/null flips | **0/409** | exactly 0 |

The safeguard vetoed **142/705** modeled candidate rows; **48** vetoed rows had higher marginal DPS
than their decision's incumbent. No incumbent had a nonpositive score.

## Preregistered result

The rule flips **78/409 = 19.07%**, four decisions short of the fixed **20% (82/409)** bar.

| bar | result | verdict |
|---|---:|---:|
| policy flip surface | **19.07%** vs ≥20% | **FAIL** |
| median marginal-DPS improvement | **7.50 points** vs ≥5 | PASS |
| positive flips | **78/78 = 100%** vs ≥90% | PASS |
| median per-run optimistic upper | **0.428** vs ≥0.33 | PASS |
| minimum leave-one-run-out flip rate | **18.13%** vs ≥18% | PASS |
| median leave-one-run-out flip rate | **19.04%** vs ≥20% | **FAIL** |
| runs containing flips | **16/16** vs ≥12 | PASS |
| largest run contribution | **10.26%** vs ≤20% | PASS |

The prediction was **PASS, narrowly on exposure**. It was falsified. The null is not caused by one
run, negative DPS changes, weak median magnitude, or an optimistic planning ceiling; the positive
acceptability constraint itself leaves the mechanism just below the predeclared intervention size.

The 78 flips are distributed across waves 1–8 and all runs. Transitions are 39 item→weapon,
27 weapon→weapon, 6 item→item, and 6 weapon→item. The selected candidate retains a median **47.5%**
of incumbent score, but the minimum is only **1.28%** despite remaining positive. That large existing
value sacrifice makes relaxing the safeguard especially difficult to justify.

## Interpretation and next fork

§37 showed enough unconstrained higher-DPS surface but weak additive doses failed. §38 made DPS
lexicographically decisive behind the incumbent scorer's natural positive boundary and still missed
the exposure bar. Lowering that boundary, adding a small tolerance, or selecting four convenient
vetoed decisions after seeing this result would be post-hoc threshold fishing.

Accordingly, the danger-aware immediate-DPS ordering direction is **closed for campaign purposes**
on the present evidence. This does not prove that no shop planner can help; it says the two
predeclared target-free mechanisms are not licensed to consume live trials. The recommended next
fork is to return to the **bootstrap**: derive a D5 clearance requirement from the measured enemy
health intervention and wave demand, with the modelling assumptions and falsifiers explicit, then
price that planner offline before implementation.

## Artifacts

- preregistration: `danger_aware_dps_lexicographic_prereg.md`
- analyzer: `scripts/wp2_danger_aware_dps_lexicographic_gate0.py`
- full result: `danger_aware_dps_lexicographic_result.json`
