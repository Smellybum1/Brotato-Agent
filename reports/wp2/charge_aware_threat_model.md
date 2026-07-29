# The operator's threat model is correct, and the agent lacks it

**Date:** 2026-07-29. Testing the proposal: *treat normal enemies as near-harmless and be reckless
around them; track the large charging elites and be ready to dodge their charge.*
**Verdict: confirmed on all three mechanics, and it is visible in the human's play.** No machine
time — all from the archive.

## 1. Exactly one enemy type charges, and the data names it without guessing

A dashing enemy exceeds its own `speed` stat; a walker does not. Both `vx/vy` and `speed` are
captured per enemy per tick, so this needs no assumption about which type is "the elite":

| type | n ticks | median \|v\|/speed | p90 | p99 | max | frac > 1.5 |
|---|---|---|---|---|---|---|
| **pursuer** | 28,646 | **1.38** | **2.27** | **2.91** | **3.67** | **0.4948** |
| fin_alien | 18,042 | 1.00 | 1.00 | 1.00 | 1.00 | 0.0000 |
| junkie | 14,476 | 1.00 | 1.00 | 1.00 | 1.00 | 0.0000 |
| helmet_alien | 14,133 | 1.00 | 1.00 | 1.00 | 1.00 | 0.0000 |
| baby_alien | 8,363 | 1.00 | 1.00 | 1.00 | 1.00 | 0.0000 |
| spawner | 5,791 | 1.00 | 1.00 | 1.00 | 1.00 | 0.0000 |
| buffer | 2,841 | 1.00 | 1.00 | 1.00 | 1.00 | 0.0000 |
| looter | 674 | 1.00 | 1.00 | 1.00 | 1.00 | 0.0000 |

**`pursuer` is the only type that ever exceeds its stat speed, and it does so on 49.5% of ticks.**
Every other type sits at exactly 1.00 with zero variance. It is also the tankiest common type
(`max_hp` 335-837 vs 22-94 for most others).

## 2. The charger does most of the damage

Attribution by nearest-surface enemy at the HP-drop tick (the HP-drop diff method; `player_damage`
lags by one capture and has manufactured a false finding before). Wave 17 is melee-body damage where
the measured causal lag is 0.

| | agent | human |
|---|---|---|
| HP lost / drop events | 408 / 25 | 199 / 13 |
| **pursuer share** | **0.725** | **0.613** |
| fin_alien | 0.201 | 0.196 |
| helmet_alien | 0.074 | 0.080 |

`pursuer` is 30.8% of tick-presence but **61-73% of the damage.** Note *how*: HP-per-event is flat
across types (13-17), so pursuer does not hit harder — **it lands more hits.** That is exactly what
a charge buys: it closes distance you thought was safe.

## 3. The human's edge is TEMPORAL, not spatial — and the static test missed it

The obvious test — "does the human keep more distance from pursuers?" — **says no.** The human is
closer to *every* type, pursuer included:

| type | agent median dist | human median dist | gap |
|---|---|---|---|
| pursuer | 402 | 292 | −110 |
| fin_alien | 440 | 304 | −136 |
| helmet_alien | 520 | 413 | −106 |
| baby_alien | 544 | 407 | −138 |
| junkie | 676 | 582 | −93 |

Uniformly closer, with no selective respect for the charger. On a static reading the proposal looks
unsupported.

**Conditioning on whether the pursuer is actually charging reverses that.** Player radial velocity
w.r.t. the nearest pursuer within 600 u (+1 = moving straight away):

| | pursuer CHARGING | pursuer WALKING | **differentiation** |
|---|---|---|---|
| **AGENT** | +0.117 (n=3222) | **+0.056** (n=1522) | **+0.061** |
| **HUMAN** | +0.131 (n=3182) | **−0.087** (n=1704) | **+0.219** |

**The human's differentiation is 3.6x the agent's.** Under charge both back off about equally
(+0.131 vs +0.117). The difference is entirely in the *walking* state: **the human moves toward a
walking pursuer (−0.087) while the agent still backs away from it (+0.056).**

So the agent pays the positioning cost of respecting the pursuer **all the time**, and gets only a
third of the differentiation. That is precisely the operator's description — be reckless when it is
walking, disengage when it charges — and the agent does not do it.

## Why this is a strong candidate

- **No perception gap.** The charge signal is `|v| / speed`, and both fields are already captured
  per enemy per tick. The agent has everything it needs and does not look.
- **The agent currently has NO type differentiation at all.** In `_enemy_engagement_force`,
  every non-boss enemy is appended with weight **1.0** (`threats.append([e, 1.0])`); only bosses get
  `BOSS_WEIGHT`. Threat is treated as identical across a 3.67x charge-speed range and a 30x
  max-HP range.
- It explains the target-conversion deficit without contradicting it: the agent's uniform standoff
  is set by the most dangerous enemy present, applied to all of them.

## ⛔ The blocker this must respect

**This lands in `_enemy_engagement_force`, which is inside `_build_desire` — and `_build_desire` is
overridden on 50-88% of wave-17 ticks** (`desire_is_discarded.md`). The standing rule applies:
**assume it is inert until a behavioural readback on the FINAL command proves otherwise.**

A charge-aware threat weight therefore has two possible homes, and the choice is an empirical
question rather than a design preference:
1. In `_enemy_engagement_force` — natural, but likely mostly discarded.
2. In the **safety tail** (`_finale_body_safety` and the wall path), which actually owns the command.

**Do not implement before deciding that.** The readback is well-defined and cheap: the
charging-vs-walking differentiation above, measured on the final command, must move from +0.061
toward the human's +0.219.

## Caveats

- **Damage attribution rests on 25 agent and 13 human drop events.** The direction is strong and
  consistent across arms, but the shares are not precise. The charge-detection and
  differentiation numbers are on 3-28k ticks and are solid.
- The distance and differentiation comparisons are between two different policies, so state
  distributions differ; the charging/walking split is *within* each arm, which is what makes the
  differentiation number a fair comparison.
- One fixture family, 5 trials per arm, human input is 8-way.
