# Tail Gate 0: one knob dead, one live — and the READBACK ENDPOINT is unusable as defined

**Date:** 2026-07-29. Mod `0.2.55`. 2 agent control trials + 1 human-handover trial, all on the
**same** wave-17 fixture `w16_predator_..._7f124906e6bb49cb`. ~20 min machine time.

## 0. The human trial is verified human, behaviourally

`human_movement` was on. The config flag is the mod's *self-report*, so it is not evidence. The
discriminator is structural: human input is **8-way keyboard**, the agent's command is continuous.
Fraction of actual per-tick headings within 2° of a 45° axis:

| run | on 8-way grid |
|---|---|
| **human trial** | **0.8654** |
| agent control 1 | 0.2159 |
| agent control 2 | 0.2243 |

A signature the agent arm cannot produce. Result: **victory, 139 damage, waves 17-20.**

## 1. GATE 0 — `tail_calm_penalty_mult` is a NO-GO; `tail_calm_clearance_mult` is LIVE

1019 fresh wave-17 lane decisions (2302 captures, **1283 dropped as stale seq** — the interior lane
runs on ~44% of ticks, which is why the `seq` counter is mandatory).

**The enemy-penalty term cannot be the lever:**

| | value |
|---|---|
| `enemy_penalty_term` median / p75 | **0.000 / 0.000** |
| its share of mean \|total\| | **0.0027** — smallest of seven terms |
| ticks where \|penalty\| > winning margin | **35 / 794 = 0.0441** |

Scaling a term that is exactly zero on three-quarters of decisions cannot move an endpoint. Dead.

**The body-clearance floor is the live constraint:**

| | value |
|---|---|
| `body_floor` p25 / med / p75 | **45.0 / 45.0 / 45.0** |
| regime `critical` (hard 45 u floor) | **0.7684** of fresh ticks |
| pooled candidates clearing it | **6261 / 9452 = 0.6624** |

The 45-unit contact floor rejects a third of candidate lanes on most ticks, and it is exactly what
forbids closing on an approaching enemy. `tail_calm_clearance_mult` acts on it directly.

### ⚠️ Magnitude share is NOT decision influence

`boss` is **constant at 877.500, zero variance** (no boss at wave 17, so it is the 650.0 default) and
`projectile` is pinned at 560.0 through p75. Together **50% of the score magnitude contributes
nothing to which lane wins.** `wall` is the only genuinely high-variance term (384 → 2080). Ranking
terms by share of the total would have named `boss` the second most important term in the
controller. It is inert. **Rank candidate-selection terms by SPREAD ACROSS CANDIDATES, never by
magnitude.**

## 2. ⛔ THE HEADLINE: the differentiation endpoint has a within-arm spread that SWAMPS the effect

The readback the whole charge-aware line was predicated on — charging-vs-walking radial velocity
w.r.t. the nearest pursuer within 600 u — **does not reproduce**. Measured on actual displacement
(required: in a human trial `teacher.action` is the agent's *intent*, not what executed):

| run | charging | walking | **differentiation** |
|---|---|---|---|
| HUMAN (this trial) | −0.157 | −0.138 | **−0.018** |
| AGENT control 1 | +0.008 | +0.096 | **−0.087** |
| AGENT control 2 | +0.023 | +0.002 | **+0.021** |

**The two agent controls — same fixture, same build, same settings — differ by 0.108.** The archived
values (agent +0.061, human +0.219) are outside everything measured here. Three separate estimates of
the nominally identical control now read **+0.036, +0.012, −0.036**.

**A statistic whose control spread exceeds the effect it must detect cannot serve as a readback.**
The 0.2.54 conclusion survives — the desire-level +0.216 is far outside this band — but any *future*
dose measured on the differentiation would be unreadable.

## 3. ⭐ THE REPLACEMENT ENDPOINT — pooled approach velocity, cleanly separated

Drop the charging/walking split and take the pooled radial velocity (+1 = moving straight away):

| run | pooled radial | median | median distance to pursuer |
|---|---|---|---|
| **HUMAN** | **−0.147** | −0.220 | 410 |
| AGENT control 1 | **+0.050** | +0.066 | 436 |
| AGENT control 2 | **+0.014** | −0.008 | 476 |

**Gap ≈ 0.18 against a within-arm spread of 0.036 — roughly 5x.** The human moves *toward* the
nearest pursuer on average; the agent moves away or is neutral. Same underlying behaviour the
differentiation was trying to capture, without the variance of a difference-of-two-noisy-means.

This partly reframes the archived claim that "the edge is TEMPORAL, not spatial". The temporal
split is real in the archive's larger sample but is the **noisy** statistic; the plain question
*does the agent ever close on a pursuer* separates the arms far more cleanly at this n.

## 3b. ⭐⭐ OPERATOR OBSERVATION CONFIRMED — and it yields the best endpoint yet

Operator, watching the run: *"it gets skittish and settles into a corner and stays within a small
bounded area... constantly moving but only in a very small bounded area. I'm constantly moving but
I'm not bounding myself to a small area."*

**Occupancy concentration, 128 u cells, 192 cells in the arena, wave 17:**

| | cells visited | **cells holding 50% of time** | as fraction of arena |
|---|---|---|---|
| **HUMAN** | 106 / 192 | **33** | **0.172** |
| AGENT control 1 | 70 / 192 | **10** | 0.052 |
| AGENT control 2 | 72 / 192 | **12** | 0.062 |

**The agent spends half of wave 17 inside ~5-6% of the arena; the human spreads the same half over
17%. A 3.0x concentration difference, with the two agent runs 2 cells apart and the human 21 cells
away from both.** The agent also touches only ~71 of 192 cells against the human's 106.

**Corner occupancy, against the uniform-random baseline** (stated because a corner box is a large
share of the arena and a bare fraction would mislead):

| corner radius | HUMAN | AGENT 1 | AGENT 2 | uniform baseline |
|---|---|---|---|---|
| < 300 u | 0.0039 (**0.03x**) | 0.0825 (0.72x) | 0.0904 (0.79x) | 0.1144 |
| < 400 u | 0.0525 (**0.26x**) | 0.3585 (**1.76x**) | 0.3026 (**1.49x**) | 0.2035 |
| < 500 u | 0.1701 (0.53x) | 0.4193 (1.32x) | 0.3765 (1.18x) | 0.3179 |

The agent sits in the corner **region** at 400-500 u well above chance while the human is far below
it — but at 300 u the agent is *below* random too, so it is not jamming into the extreme corner. The
observation is right; the mechanism is a corner-region attractor, not a hard pin.

**Note what did NOT reproduce:** median distance from arena centre is essentially IDENTICAL
(human 597, agent 593 / 537), as is median distance to the nearest wall (339 vs 346 / 392). The
archived "agent edge-hugs, 810 vs the human's 535 from centre" does **not** hold on this fixture.
Distance-from-centre is the wrong instrument; **concentration is the right one**, and only the
concentration metric sees what the operator saw.

**Separation-to-noise, all of today's candidate endpoints:**

| endpoint | human vs agent gap | agent within-arm spread | ratio |
|---|---|---|---|
| charging−walking differentiation | 0.07 | **0.108** | **< 1 — unusable** |
| pooled approach velocity | 0.18 | 0.036 | ~5x |
| **cells holding 50% of time** | **21-23 cells** | **2 cells** | **~10x** |

## 4. What this licenses, and what it does not

- **Dose `tail_calm_clearance_mult`, read it on POOLED approach velocity.** The mechanism is
  identified (45 u floor, binding on 77% of ticks), the knob acts on it, and the endpoint separates.
- **Do NOT dose `tail_calm_penalty_mult`.** Predeclared bar failed at Gate 0.
- **Establish the control spread FIRST.** n=2 gives a range, not a variance. The next spend should be
  control replicates on this fixture before any treatment arm, or the dose is unreadable for the same
  reason the differentiation is.
- **n=1 human, n=2 agent, one fixture.** Nothing here is a campaign result. The 8-way verification
  and the Gate 0 term statistics are robust (they are per-tick structural facts over ~1000
  decisions); the endpoint comparisons are not.
