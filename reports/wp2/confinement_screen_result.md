# Confinement screen: `tail_calm_clearance_mult` is a NO-GO — and my endpoint claim was 3.1x too optimistic

**Date:** 2026-07-29. Mod `0.2.55`. 4 control + 4 treatment trials, one wave-17 fixture
(`w16_predator_..._7f124906e6bb49cb`), plus 2 earlier controls on the same fixture. ~35 min.
Reports against `confinement_screen_prereg.md`, written before any treatment trial ran.

## Result — NO-GO on the predeclared rule

Primary endpoint: 128 u cells holding 50% of wave-17 captures. Higher = roams more. **Human = 33.**

| arm | raw values | mean |
|---|---|---|
| **control** (6 pooled) | **7, 19, 13, 17, 10, 12** | **13.00** |
| **treatment** (dose 0.0) | **12, 5, 18, 15** | **12.50** |

- `sd_ctrl` = **4.427**, so the predeclared bar `2 x sd_ctrl` = **8.85**
- observed difference = **−0.50 cells = −0.11 sd**, and in the **wrong direction**

**VERDICT: NO-GO.** Not marginal — the effect is a tenth of a standard deviation, negative, against
a bar of two. Both safety guards passed (survival 4/4 vs 4/4; treatment median damage 85.5 vs
control 67.0 = 1.28x, under the 1.5x threshold), so the NO-GO is on the primary alone.

The dose was the **maximum** (0.0 = a non-charging enemy fully discounted against the 45 u contact
floor, a 45 u credit). A knob that does nothing at max dose does not need titration.

## ⛔ THE MORE IMPORTANT RESULT: I overstated the endpoint's quality 3.1x, from n=2

`tail_gate0_and_endpoint_instability.md` §3b reported the confinement endpoint at
**"~10x separation-to-noise"**, from an agent within-arm spread of **2 cells** — the two control
runs then available happened to read 10 and 12.

With six controls the spread is **7 to 19, sd 4.427 — 3.13x larger.**

| | claimed (n=2) | measured (n=6) |
|---|---|---|
| control sd | 1.414 | **4.427** |
| human-vs-agent separation | "~10x" | **4.52 sd** |

**The endpoint survives — 4.5 sd is still the best separation on the project, and the human-agent
confinement difference (33 vs 13, 2.5x) is unaffected.** But the specific quality number was wrong,
and it was wrong for exactly the reason I had written into the prereg one screen earlier: *n=2 gives
a range, not a variance.* I applied that rule to the treatment arm and not to the endpoint I was
advertising.

**This is the "run the disconfirming check on your own claims" lesson recurring.** The correction
cost nothing because the prereg forced 6 controls before any comparison; had the screen been sized
off the n=2 spread (2 x 1.414 = 2.8 cells), a 3-cell noise excursion would have been read as a GO.

## Where this leaves the tail

**Both tail knobs are now dead**, on measurements rather than argument:

| knob | layer | verdict | evidence |
|---|---|---|---|
| `calm_threat_mult` | `_build_desire` | erased | desire +0.216, command +0.003 (72x) |
| `tail_calm_penalty_mult` | wall lane score | **NO-GO** | term is 0.000 at median AND p75; flips 4.4% |
| `tail_calm_clearance_mult` | body clearance | **NO-GO** | −0.11 sd at max dose |

The charge-aware threat model is **confirmed as a description** (`pursuer` is the only charging
type, 61-73% of wave-17 damage) and **unreachable through these three levers**. The tail's
type-blindness is real but is not what produces the behaviour.

## Non-decision-bearing observation, explicitly post-hoc

Pooled approach velocity moved toward the human under treatment (control **+0.103** → treatment
**+0.066**; human **−0.147**), and radius of gyration fell (513 → 467). So the knob is not inert —
it changes behaviour, just not confinement, and not enough. **This is post-hoc and on a secondary
endpoint; it is a hypothesis for a future prereg, not a result.** Note it also moved *damage* up
28%, which is the expected cost of relaxing a collision floor.

## What is NOT closed

The confinement **diagnosis** stands and is the strongest human-agent difference measured:
**agent 13 cells vs human 33, 4.5 sd.** No lever has been found for it. The three tested knobs all
targeted the tail's *enemy threat model*; confinement may instead be produced by the wall-recovery
latch geometry (280/520 hysteresis) or the corner guard — neither of which has a knob yet, and
neither of which should be assumed causal, since the agent's position is itself produced by the tail.
