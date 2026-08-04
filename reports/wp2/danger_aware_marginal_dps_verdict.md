# §37 danger-aware marginal effective-DPS Gate 0 verdict

**Date:** 2026-08-04  
**Verdict:** **FAIL — score-margin / flip-limited**  
**Campaign:** not licensed; none run

## Question and fixed rule

On nominal-D5 Ranger shop buys in waves 1–11, would adding
`lambda * immediate_effective_weapon_DPS_gain_percent` to every recorded candidate score flip enough
existing buy decisions to justify a live campaign? The committed preregistration fixed doses
`lambda = {0, 0.5, 1, 2, 4}`, a 20% policy-denominator flip bar, and the controls and secondary bars
before the counterfactual was computed.

## Denominators and controls

The policy denominator is **409** shop-buy decisions across **16/16** era-matched, terminal,
nominal-D5 Ranger runs. Decisions outside the trusted free-slot scored surface remain in that
denominator and remain unchanged:

| unchanged reason | decisions |
|---|---:|
| slots full | 130 |
| no scored rows | 47 |
| loadout untrusted | 8 |
| gain uncomputable | 1 |
| baseline mismatch | 1 |

All preregistered controls passed after three control-only VOID repairs:

| control | result | bar |
|---|---:|---:|
| offer/row join | **736/736 = 100.00%** | ≥99% |
| loadout trust | **224/232 = 96.55%** | ≥95% |
| independent ordinary-weapon gain parity | **253/253 = 100.00%** | ≥99% |
| baseline decision reproduction | **222/223 = 99.55%** | ≥99% |
| null-dose flips | **0/409** | exactly 0 |

The three preserved VOID files are evidence-quality failures, not Gate 0 results. They caught, in
order, the two-copy Ranger start, missing permanent scaling-stat state, the live Gun-set range bonus,
and sell-order reconstruction. No dose, denominator, bar, prediction, or policy rule was changed by
those repairs.

## Preregistered result

The reachable higher-DPS surface is **100/409 = 24.45%**, passing the 20% surface bar and falsifying
the preregistered prediction that surface would probably bind.

| lambda | flips / 409 | policy rate | median delta m | positive flips | median per-run optimistic upper |
|---:|---:|---:|---:|---:|---:|
| 0.0 | 0 | 0.00% | — | — | 0.000 |
| 0.5 | 28 | 6.85% | 18.70 points | 100% | 0.258 |
| 1.0 | 38 | 9.29% | 15.45 points | 100% | 0.408 |
| 2.0 | 53 | 12.96% | 12.33 points | 100% | 0.484 |
| 4.0 | 63 | **15.40%** | 11.88 points | 100% | 0.573 |

The dose response is monotone. At `lambda >= 1`, the magnitude, positive-flip-share, and per-run
optimistic-planning bars pass. **No preregistered dose reaches the required 20% policy flip rate.**
The binding failure is therefore the incumbent score margin, not candidate availability, DPS
magnitude, sign, or the one-step optimistic total.

## Interpretation and scope

This closes the tested **weak additive override (`lambda <= 4`)**. It does not close danger-aware
immediate-DPS prioritization as a defect class: unlike §30 and §36, the structural surface itself
passes, and all 63 strongest-dose flips move immediate effective weapon DPS in the intended
direction.

Simply extending the lambda ladder until it crosses the bar would be post-hoc dose fishing. The next
licensed move, if this direction continues, is a mechanism-distinct preregistration—for example a
lexicographic/top-DPS constraint—with an explicit safeguard for sacrificed incumbent value and a
stability check. It must pass a fresh offline gate before any live campaign. The bootstrap remains
the alternative fork.

## Artifacts

- preregistration and measurement amendments: `danger_aware_marginal_dps_prereg.md`
- analyzer: `scripts/wp2_danger_aware_marginal_dps_gate0.py`
- adjudicated result: `danger_aware_marginal_dps_result.json`
- preserved control VOIDs: `danger_aware_marginal_dps_control_void1.json`,
  `danger_aware_marginal_dps_control_void2.json`, `danger_aware_marginal_dps_control_void3.json`
