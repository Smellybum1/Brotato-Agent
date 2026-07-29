# Consultation brief: a human outplayed our agent on identical game states, and we logged both decisions on every tick

> ## ⛔ CORRECTION 2026-07-29 — two claims in this brief are retracted
>
> This is a dated record of what we asked, kept as sent. Two of its assertions are wrong:
>
> **1. §3.1: "the human collected 5x more while taking a quarter of the damage" — RETRACTED,
> and the error is mine.** The damage half was inferred from **minimum HP ratio** (0.61 vs
> 0.13), which is not a damage statistic. Measured on the same fixture: **agent median 80,
> human median 156 — the human took 1.95x MORE gross damage.** The defensible statement is
> that the human reached **more waves (2-4 vs 1)** and took **less damage per wave reached
> (53 vs 74)** with a far healthier HP floor. (External review flagged exactly this; see
> `pro_answer_20260729_human_vs_agent.md` §4.)
>
> **2. §4: "under crowding, the density veto zeroes the loot attraction term" — REFUTED at
> observed doses.** The veto (`nearby >= PACK_DENSITY_SOFT = 8`) fires on **0.03%** of
> wave-17-19 ticks; loot attraction is **LIVE on 89%** of them; and the loot-abandonment
> gap lives **entirely inside the unvetoed regime** (median angle 47.6° → 89.1° across
> crowd bands with nothing suppressed). The crowd variable that produced the finding is
> **total enemies on the map**, a different variable from the veto's local count.
> The phenomenon is real; this mechanism is not its cause. **Do not build the proposed
> safety-constrained tie-break intervention.** Full result:
> `reports/wp2/density_veto_verdict.md`.
>
> The `damage_taken` retirement raised in §3.2 of this brief was **accepted** and is now
> standing — see `reports/wp2/campaign_sizing.md`.

You are being asked for a **diagnostic and experimental-design opinion**. Everything you need is
in this document; there are no external references. Please **write your answer as a single
self-contained markdown (`.md`) file**.

Be blunt. This project has a documented history of conclusions that were correct as far as they
went and wrong one step later, and external review has already caught two design-time errors here
that would have manufactured false positives.

---

## 1. The system, in one page

A deterministic bot plays **Brotato**, a top-down arena survival game. A run is 20 waves. Enemies
spawn continuously; **weapons fire automatically**; the only thing the player controls during a
wave is **movement**, a 2D direction vector. Between waves there is a shop and level-up choices.
Wave 20 ends with a boss. Dying ends the run; surviving wave 20 is a victory. Fixed configuration
throughout: character "Well Rounded", Danger 0, ranged/gun build.

The agent is a hand-written potential-field movement controller (attraction to loot and open
space; repulsion from enemies, projectiles, walls) plus a scoring-based shop/level-up policy, with
a large accumulated safety layer: density veto, relief fallback, corner guard, edge-kite rail,
pack repulsion, loot dash, and a wave-20 finale override.

Current measured performance: **win rate 0.722** (26/36 full runs on the shipped build). Remaining
losses are diffuse — no single wave exceeds 8.3% of runs.

**Materials** are the currency. They drop during a wave and are picked up by walking over them.
Uncollected materials are swept at wave end into a **"Material Bag"** — deferred value that then
redeems *incrementally through pickups during the next wave*. So failing to collect is doubly
costly: the current wave's drops defer, and the previous wave's bag goes unredeemed. Anything
still in the bag when the run ends is lost.

---

## 2. The instrument — why this data is unusual

We built a **movement-only handover**: a human takes the movement vector while the agent retains
shop, level-up, capture and telemetry control. Crucially, **the agent keeps computing and logging
its own intended movement vector every tick — it is simply not applied.**

So on every tick we have a triple: **(game state, what the agent wanted to do, what the human
actually did)**. Same states, two decision-makers, ~20 Hz.

The handover was verified by effect rather than by its own self-report: with the flag on and no
keyboard input, 577/577 wave-17 captures show the player stationary (1.0000) against agent-steered
controls at 0.068 and 0.063. Agreement between realised velocity and the agent's commanded vector
is **0.7° median in agent trials** (the instrument's control) and **75° median in human trials**.

**Data collected:** 5 human trials on one saved wave-16 state, against 21 agent trials on that
identical state; plus **one complete human-played run, waves 1-20, ~18,000 ticks**. Plus an archive
of 36 agent full runs on the same build for baselines.

---

## 3. What the human did differently

### 3.1 On one identical saved state (human 5 trials vs agent 21)

This state is a build the agent reliably loses on — it died at wave 17 in **17 of 21** attempts.

| | agent | human |
|---|---|---|
| survived wave 17 | 4/21 | **5/5** (p = 0.0019) |
| won the run | 0/21 | 1/5 (p = 0.19) |
| materials gained during wave 17 (median) | 90 | **441** |
| Material Bag fully redeemed | **1/21** | **5/5** (p = 0.0001) |
| minimum HP ratio (median) | 0.13 | **0.61** |
| distance travelled (median) | 22,333 | 30,231 |

**Important discipline note:** the *predeclared* endpoint was terminal win, and it **FAILED**
(1/5 vs a bar of ≥2/5). Wave-17 survival was recorded but not predeclared as the decision rule, so
the 0.0019 is hypothesis-generating, not confirmatory. That was my design error — I bound the rule
to the endpoint that answers "what is the policy worth" rather than "is this wave movement-limited".

Note also the human collected **5x more while taking a quarter of the damage** — this is not a
risk-for-reward trade.

### 3.2 The Material Bag, across the archive — this corrected an over-generalisation

Pooled over **36 agent full runs, 709 wave-observations**, the agent drains the bag in **94.8%** of
waves. So the 1-of-21 collapse above is *not* the agent's normal behaviour. But by wave band:

```
w1-6    100.0%      w13-16   97.2%
w7-12    99.1%      w17-20   76.7%   <-- the deficit
```

The human's full run drained the bag in **20/20 waves, 0 stranded**.

### 3.3 Loot-directedness on identical ticks (the paired measurement)

Angle between movement direction and the direction to the nearest material; lower = more
loot-directed. Both columns come from the *same ticks* of the human run — the human's realised
velocity versus the agent's simultaneously-logged intent.

| | human | agent intent | gap |
|---|---|---|---|
| overall (n=17,828) | 43.8° | 58.3° | 14.6° |
| waves 1-6 | 30.4° | 38.5° | 8.1° |
| waves 7-12 | 39.7° | 54.9° | 15.2° |
| waves 13-16 | 50.7° | 58.8° | 8.0° |
| **waves 17-20** | **58.9°** | **85.2°** | **26.3°** |

At 85° the agent is essentially perpendicular to loot — ignoring it.

### 3.4 Crowd-matched control — the gap SURVIVES and grows

This project has been burned before by an endogenous metric: a "movement quality" proxy ran
backwards because more enemies nearby mechanically raises it. So the same control was applied here
— bin by number of enemies alive, compare within bins:

| enemies alive | n | human | agent | gap |
|---|---|---|---|---|
| 0-4 | 4,108 | 35.9° | 29.6° | **−6.3°** |
| 5-9 | 5,844 | 40.5° | 56.2° | +15.7° |
| 10-14 | 4,248 | 49.8° | 67.7° | +17.9° |
| 15-19 | 2,022 | 49.6° | 83.5° | +33.9° |
| 20-29 | 1,415 | 60.9° | 98.4° | +37.5° |

**At low crowding the agent is MORE loot-directed than the human.** The gap appears only as
crowding rises, and grows monotonically. This is not laziness; it is **disengagement under
pressure**.

### 3.5 Was the loot actually reachable? (i.e. is the deficit addressable at all)

On the 41.1% of ticks where the agent's intent is >75° off the nearest material:
- median distance to that material: **170 u**
- median distance to the nearest enemy: **402 u**
- the material was closer than the nearest enemy in **90%** of those cases
- on that reachable subset: human **48.6°** vs agent **121.5°** — the agent is actively heading away

So in the large majority of abandonment cases there was no enemy between the agent and the loot.

### 3.6 Consequence for the build

Summed weapon damage/cooldown at wave-17 entry: **human 58.78**. Reference from an earlier
observational study of 50 agent runs: runs that *died* at wave 17 median **28.26**, runs that
*survived* median **35.25**. The human's build was 1.67x the survivor median.

Human build trajectory: w1 = 1, w5 = 4, w9 = 12, w13 = 25, w15 = 31, w17 = 59, w20 = 75.

**And the human still lost at wave 20.** That is consistent with a previously measured result:
offense does **not** separate wave-20 outcomes (rank-biserial 0.553 and 0.464 for the two bosses,
against a null band of [0.370, 0.630]), while wave 17 separates strongly on offense (0.188). Wave
17 is a 60-second timed clear; wave 20 is a boss fight. A prediction that could have failed, and
did not.

### 3.7 An apparent counter-result that DISSOLVED on inspection — and took a standing metric with it

Over the **full 20-wave run** the human took **251 damage** against an agent archive median of
**83** (p10 18, p90 208; victories-only median 82) — ~3x the median and above the 90th percentile.
I initially recorded this as the main evidence against the "copy the human's aggression" thesis.

**It does not survive.** `damage_taken` is a **gross cumulative counter**: it sums damage events and
never subtracts healing. Measuring risk exposure directly instead:

| | human | agent median (n=6 full runs) |
|---|---|---|
| fraction of ticks below 70% HP | **0.022** | 0.033 |
| fraction of ticks below 50% HP | 0.013 | 0.004 |
| fraction of ticks below 30% HP | 0.003 | 0.000 |
| median HP ratio | 1.00 | 1.00 |
| minimum HP ratio | 0.19 | range 0.10-0.72 |
| **HP healed back over the run** | **120** | **38** |

The human took more gross damage **and healed 3.2x more of it back**, spending *less* time below
70% HP than the typical agent run and landing inside the agent's own range on the deeper bands.
The operator's account — "I traded health for collection because I knew consumables were there to
recover it" — is supported: it is a **deliberate policy of spending a recoverable resource**, not
recklessness. Net risk was comparable or better.

**The wider consequence, which matters more than this run.** `damage_taken` is this project's
**standing primary endpoint for paired campaigns** — the whole sizing table (32 trials detects 19
damage, 64 detects 13, 128 detects 9) rests on it. Healing varied **15 to 171** across the six
agent runs checked. So any intervention that shifts healing — more collection, more consumable
pickup, more lifesteal — moves the endpoint without moving actual risk, or masks a real change.
That is the same family as a treatment-rescaled outcome. **Question 8 below asks whether the
endpoint should be replaced.**

Honest note on how this was found: the operator supplied the explanation, and it prompted a
measurement I would not otherwise have run. The gross-vs-net distinction was invisible in the
summary statistic.

### 3.8 Control: is the agent's behaviour intrinsic, or an artifact of human-visited states?

§3.3-3.5 measure the agent's *intent* on states the **human** created. That is the right
counterfactual for "what would the agent do here", but it does not show the behaviour is intrinsic.
Re-measured on **5 agent runs the agent itself drove, 95,630 ticks**:

| | agent, own runs | agent, on human-visited states |
|---|---|---|
| waves 1-6 | 32.5° | 38.5° |
| waves 7-12 | 56.7° | 54.9° |
| waves 13-16 | 58.9° | 58.8° |
| waves 17-20 | **77.3°** | 85.2° |
| 0-4 enemies | 31.1° | 29.6° |
| 5-9 | 51.5° | 56.2° |
| 10-14 | 65.3° | 67.7° |
| 15-19 | 77.1° | 83.5° |
| 20-29 | **85.7°** | 98.4° |

**The control passes** — same pattern, similar magnitudes. The disengagement is intrinsic.

**And the distribution is bimodal, which the medians hide.** In the agent's own runs at waves
17-20: **p10 = 10.7°, median 77.3°, p90 = 158.6°**. The agent is either heading almost straight at
loot or almost straight away from it — not smoothly trading off. That is the signature a **binary
veto** would produce, and it corroborates the mechanism in §4. (This project has previously been
burned by a median taken over a mixture, so the percentiles are given throughout.)

---

## 4. The mechanism, located in the code

The controller has an explicit comment: *"when density suppression has zeroed ordinary loot
attraction"*. Under crowding, the **density veto zeroes the loot attraction term**, and the
compensating mechanism is a separate **"loot dash"** with its own arming conditions.

Per-tick instrumentation of why the dash fires or does not, waves 17-20:

| dash state | agent run | human run |
|---|---|---|
| `suppressed_finale` | 30.4% | 12.7% |
| `not_armed_no_stall` | 29.3% | 51.4% |
| `suppressed_survival` | 21.7% | 5.2% |
| `active` | 6.9% | 9.9% |

In the agent's run the dash is **suppressed on 52.1%** of late-wave ticks (finale + survival), and
where not suppressed it usually fails to arm because it requires a "stall" condition. So under
crowding at late waves the agent has **neither** ordinary loot attraction **nor** the dash.

`suppressed_survival` is HP-gated, and the agent's median minimum HP on the hard state was 0.13
against the human's 0.61 — which suggests a **feedback loop**: damage taken → low HP → loot
suppression → fewer materials → weaker build → more damage. An earlier study flagged exactly this
loop and concluded its data could not orient it.

### Relevant history — this has been attempted before and mostly failed

Roughly five versions were spent on this area previously:
- a bounded opportunistic loot dash was added — and in its qualification run **the dash never fired**;
- a stall trigger plus loot-biased strafe was **rejected** after causing a wave-10 death (the stall
  gate measured the wrong quantity; a strafe cap was out-voted by enemy pressure ~0.32);
- a recalibrated version produced the behaviourally best run ever recorded but was rejected on a
  missing diagnostic;
- subsequent versions tightened arbitration but did not revisit the density-veto/loot interaction.

So the machinery exists, has been tuned twice, and still reports `not_armed_no_stall` on half of
late-wave ticks.

---

## 5. Experimental apparatus and costs

- A full run costs **~19 minutes**; the outcome is binary.
- Detecting a win-rate improvement from 0.722 to 0.80 at 80% power needs ~930 runs ≈ **294 hours**.
  The full-run instrument cannot economically resolve anything smaller than ~+13 pp.
- A **saved-state harness** restores a mid-run save and replays one wave onward to run end at
  **~4.3 min/trial**. Paired on source state it is ~7x more efficient than paired full runs.
  Terminal win from a wave-16 landmark is validated as an endpoint: `P(win | landmark)` = 61/80 =
  0.7625 against natural full runs at 26/34 = 0.7647.
- Source state is the inferential unit; K continuations from one save are not K independent builds.
- Standing practice: screen at 32 paired trials on effect size, confirm at 64 on a **fresh** sample
  with a pre-registered rule.
- Human play cannot be automated (synthetic keyboard input does not reach the game), so human data
  costs operator hours: ~1,250 ticks per wave-17 trial, ~18,000 per full run.

Also relevant: previous learned-policy attempts all failed — two RL residuals nulled, and a
behaviour-cloning student that agreed with the teacher **more** (37.9° vs 55.7° held-out error)
yet died earlier and more often. The recorded lesson was "teacher-imitation error is not the live
objective". Note every one of those imitated the *teacher*, whose ceiling is the teacher.

---

## 6. Questions

1. **Is the diagnosis right?** Is "the density veto zeroes loot attraction under crowding, and the
   dash's arming conditions fail to compensate" adequately supported by §3.4, §3.5 and §4 — or is
   there a competing explanation I have not excluded?

2. **Can the feedback loop be oriented with the data I have?** Damage → low HP → loot suppression →
   weaker build → damage. The human broke the loop on an identical starting state, which feels like
   evidence about direction, but I am wary of over-reading one operator's play. What measurement
   would actually orient it?

3. **Is the causal chain to winning established, or am I chaining assumptions?** I have: agent
   under-collects under pressure (measured); human collects far more (measured); human's build at
   wave 17 was 1.67x the survivor median (n=1); stronger builds survive wave 17 (correlational, plus
   a causal enemy-health dose-response showing a ~25% HP reduction eliminates wave-17 deaths). But
   the human still lost at wave 20. What is actually established here?

4. **How should the fix be designed given the failure history in §4?** A previous loot-greed change
   caused a wave-10 death. My instinct is to make the trigger *economic* rather than a tuned
   constant, but my first such proposal was already refuted by data (I wanted to gate on "bag > 0",
   and it turns out the agent is *already more* loot-directed than the human when the bag is
   non-empty — gap −10.5°; the deficit is in ordinary materials when the bag is empty).

5. **What is the right experiment**, given a 4.3-min paired trial, a validated terminal-win
   endpoint, and roughly 23% of late waves as the addressable set?

6. **What is the best use of the paired (state, agent-intent, human-action) data?** Options I see:
   (a) mine disagreements to hand-author explicit rules — what produced everything above;
   (b) behaviour-cloning on human demonstrations, which would need ~60-80 trials (5-7 operator
   hours) to reach the scale of previous training rounds;
   (c) treat human takeover as DAgger-style correction on failure strata only.
   Given that every prior learned attempt imitated the *teacher* and this would be the first
   demonstrably-better demonstrator, does (b) deserve more credit than the null history suggests?

7. **What have I got wrong or over-claimed in §§3-4?** In particular: is the crowd-matched control
   in §3.4 sufficient to rule out endogeneity, or is "enemies alive" the wrong thing to match on?

8. **Should `damage_taken` be replaced as the primary paired-campaign endpoint (§3.7)?** It is a
   gross counter, healing varies 15-171 across runs, and the project's entire power/sizing table is
   built on it. Candidates: time-below-HP-threshold, an integral of HP deficit, net HP lost, or the
   already-validated terminal-win-from-landmark endpoint. What would you use, and does the existing
   sizing table need redoing? Note the same concern may apply to any past result that used damage
   taken as its outcome.

9. **The human's stated policy is "spend HP because consumables can recover it."** The agent has no
   such notion — it treats HP purely as a thing to conserve, and the loot-dash is suppressed when HP
   is low (`suppressed_survival`, 21.7% of late ticks). Is "treat HP as a spendable resource priced
   against available recovery" a sound policy principle to encode here, and if so how would you
   express it without producing the reckless behaviour that got a previous greed change rejected?

Please deliver your answer as a **markdown file**.

---

## Appendix A — raw per-wave tables

### A1. The human's full run, per wave (pre-sweep instant)

`gained` = materials collected during the wave; `bag in` = Material Bag carried in;
`stranded` = bag still unredeemed at wave end; `gnd` = material value left on the floor.

| wave | gained | bag in | stranded | gnd | | wave | gained | bag in | stranded | gnd |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 26 | 0 | 0 | 3 | | 11 | 302 | 39 | 0 | 13 |
| 2 | 42 | 3 | 0 | 2 | | 12 | 303 | 13 | 0 | 29 |
| 3 | 60 | 2 | 0 | 7 | | 13 | 270 | 29 | 0 | 25 |
| 4 | 93 | 7 | 0 | 4 | | 14 | 238 | 23 | 0 | 26 |
| 5 | 120 | 4 | 0 | 16 | | 15 | 355 | 27 | 0 | 38 |
| 6 | 158 | 16 | 0 | 11 | | 16 | 359 | 38 | 0 | 20 |
| 7 | 185 | 11 | 0 | 16 | | 17 | 316 | 20 | 0 | 23 |
| 8 | 193 | 16 | 0 | 20 | | 18 | 296 | 23 | 0 | 22 |
| 9 | 401 | 19 | 0 | 24 | | 19 | 481 | 22 | 0 | 30 |
| 10 | 337 | 24 | 0 | 39 | | 20 | 57 | 29 | 0 | 37 |

### A2. Agent baseline, 36 full runs, per wave

| wave | n | drained | gnd left (median) | | wave | n | drained | gnd left (median) |
|---|---|---|---|---|---|---|---|---|
| 1 | 36 | 1.000 | 2 | | 11 | 36 | 0.944 | 28 |
| 2 | 36 | 1.000 | 6 | | 12 | 36 | 1.000 | 34 |
| 3 | 36 | 1.000 | 8 | | 13 | 36 | 1.000 | 38 |
| 4 | 36 | 1.000 | 3 | | 14 | 36 | 1.000 | 56 |
| 5 | 36 | 1.000 | 14 | | 15 | 36 | 1.000 | **116** |
| 6 | 36 | 1.000 | 16 | | 16 | 36 | 0.889 | 38 |
| 7 | 36 | 1.000 | 28 | | 17 | 36 | 0.917 | 67 |
| 8 | 36 | 1.000 | 18 | | 18 | 33 | 0.879 | 65 |
| 9 | 36 | 1.000 | 28 | | 19 | 33 | **0.697** | **126** |
| 10 | 36 | 1.000 | 56 | | 20 | 31 | **0.548** | 34 |

The bag-redemption failure is monotone from wave 16 and worst at 19-20. Note the human's
corresponding `stranded` column is 0 at **every** wave, and its `gnd left` never exceeds 39.

### A3. Raw series behind the headline fixture comparison (one saved state)

Material Bag stranded per trial, bag carried in = 239 for all:
- **agent (n=21):** 0, 3, 5, 9, 22, 36, 46, 54, 65, 67, 69, 70, 73, 79, 79, 86, 86, 93, 95, 99, 173
- **human (n=5):** 0, 0, 0, 0, 0

Terminal wave per trial:
- **agent (n=21):** 17 x17, 19 x4
- **human (n=5):** 20, 20, 19, 19, 18

Materials gained during wave 17:
- **agent:** 32, 45, 59, 61, 61, 73, 77, 78, 78, 82, 90, 118, 129, 133, 152, 179, 185, 337, 339, 368, 496
- **human:** 328, 406, 441, 461, 468
