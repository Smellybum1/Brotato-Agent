# Consultation brief: getting a game-playing agent from Danger 0 to Danger 5

**You have no prior context on this project. Everything you need is in this document. There are no
file references you are expected to resolve — where I name a file it is only so my collaborator can
find it, and you should treat the numbers quoted here as the whole evidence base.**

## How I would like the answer

**Please write your answer as a single self-contained markdown file** (fenced or as a downloadable
artifact — whatever your interface supports), structured with headings, so it can be committed
straight into the project's `reports/` directory. Please include:

- an **executive verdict** near the top,
- an explicit separation of *what my evidence establishes* vs *what it merely suggests* vs *what it
  does not support at all* — I have a documented history of over-reading my own data and I would
  rather you were blunt,
- concrete, ordered, costed next steps,
- and where you disagree with my reasoning, say so directly rather than hedging.

---

# 1. The north star, stated plainly

**The goal is an agent that can complete a Danger 5 run.**

The single most important fact in this brief: **every one of the 1,873 runs ever recorded by this
project was at Danger 0.** I checked all 1,873 run summaries; the `danger` field is `0` in every
one. Danger 5 has never been attempted, not once. Every performance number below is from the
easiest difficulty tier in the game.

So this is not "improve a metric by 15%". It is "the agent has never played the target game".

# 2. The game

**Brotato** — a top-down arena survival roguelite (Godot 3 engine, single player, mouse+keyboard).
Structure of one run:

- **20 waves**, each a timed survival phase in a bounded arena (roughly 2048 x 1536 game units,
  which the project bins into 192 cells of 128 units for spatial analysis).
- Between waves there is a **shop** phase: spend materials collected during the wave on weapons,
  items and stat upgrades. Also periodic **level-up** choices offering stat boosts.
- The player character auto-attacks with up to 6 equipped weapons; **the only direct control input
  is a 2D movement vector.** Aiming and firing are automatic. This matters enormously: the entire
  learnable control problem is *where to stand and move*.
- Enemies spawn continuously, in waves of increasing size and difficulty. Wave 20 ends when a
  **boss** dies. Wave 17 is a **60-second timed** wave with heavy melee crowding.
- Dying at any wave ends the run. Completing wave 20 is a **win**.
- The project always uses the same character (`character_well_rounded`) and seeds the build with
  the same two starting weapon families (an SMG and a melee stick), to keep runs comparable.

## What "Danger" is, mechanically

Danger is Brotato's difficulty tier, 0 to 5. From the game's own save file, the tier is expressed as
a set of multipliers. The save records, per character, the hardest tier beaten with its multiplier
block. For our character it reads:

```json
{"difficulty_value": 0, "enemy_damage": 1, "enemy_health": 1,
 "enemy_speed": 1, "nightmare_proj": 1, "wave_number": 20}
```

So Danger scales at least four things: **enemy damage, enemy health, enemy speed, and
"nightmare projectiles"** (a projectile-density/behaviour modifier). At Danger 0 all four are 1.

**I do not know the exact Danger 5 multiplier values and I am not going to guess them.** They are
readable off the game at D5 and that is a cheap first task. What I can tell you is the *shape*: it
is a simultaneous increase in enemy durability, incoming damage, enemy movement speed, and
projectile pressure.

Two important facts I verified today:

1. **Danger 5 is already selectable.** The save's `max_selectable_difficulty` is **5** for our
   character (and for characters that have never won anything), while `max_difficulty_beaten` is
   `0`. So there is **no unlock grind** blocking us.
2. **The agent mod currently hardcodes Danger 0.** The mod's difficulty-selection hook calls
   `_activate_and_select_danger(0)` with a literal `0` on the auto-start path, ignoring the
   configured danger value. The config key exists and reaches an orchestrator field, but the
   selection path discards it. So "run at Danger 5" is currently a small code change that has never
   been made. (A resume-from-save path *does* honour the configured value, which is why the field
   exists at all.)

# 3. Where performance actually is — all at Danger 0

- **Full-run win rate, Danger 0: 0.395 measured** — 77 of 195 full runs on the current build era.
  That decomposes as P(reach the final wave) = 0.713 x P(survive it) = 0.554.
- The shipped wave-20 fix is **predicted** to raise that to **0.574**, but **that prediction has
  never been confirmed by a full-run campaign** — it is derived from fixture trials. Treat 0.395 as
  the only measured full-run figure. (An earlier prediction of "63% → 79%" was built on a
  contaminated baseline: the archive's win flag was true for two different populations, full runs and
  wave-20 fixture trials, and 933 of 1,411 archived runs were the latter.)
- On curated **fixture trials** (save-states resumed at a specific wave, used as a fast instrument),
  win rate on the shipped build is **pinned at 1.000** on the easy fixtures and cannot discriminate
  anything — a ceiling problem I will come back to.
- **A shipped, real win:** a perception defect where the agent was blind to a specific wave-20 boss
  projectile pattern. Fixing it moved paired fixture trials from **0.688 to 1.000**, n=64,
  p=0.000426. This is the *only* intervention in the project's history that produced a large, clean,
  replicated improvement.
- **A cautionary historical fact:** a **47-percentage-point win-rate collapse ran for roughly 20
  versions without being noticed.** Any comparison across versions in this project must be
  era-matched or it is meaningless.

**So: roughly a coin flip at the easiest difficulty, and the target is the hardest.**

# 4. Architecture, so you know what is modifiable

Two halves:

**(a) The in-game agent — GDScript, inside a Brotato mod.** This is the shipped policy. It is a
hand-written **potential-field controller**:

- A `_build_desire` stage sums ~12 weighted terms (enemy engagement, loot attraction, consumable
  attraction, a centre-pull, pack-density repulsion, edge-kiting, etc.) into a desired movement
  vector.
- That desire then passes through an ordered **"safety tail"**: a body-clearance arbiter, a
  projectile-avoidance blend, a corner guard, a wall-recovery latch with hysteresis, and smoothing.
- It also contains the shop policy and level-up policy (item valuation, weapon scoring).

**(b) A Python side — training, analysis, and a live inference bridge.**

- Rich telemetry: every ~50 ms the mod emits a `combat_capture` event with full arena state (player
  stats and position, every enemy/boss/projectile/material/crate/obstacle with position, velocity,
  health, radius), plus the teacher's chosen action and per-term diagnostics. Runs produce
  `events.jsonl` files reaching **hundreds of megabytes**.
- A **sidecar**: a loopback TCP server that loads a trained neural policy, receives the raw capture
  each tick, encodes it, and returns a movement vector. **When the sidecar replies within a 40 ms
  deadline, the mod replaces the controller's movement vector with the network's — bypassing the
  entire safety tail.** Control runs at 20 Hz.
- ~853 unit tests. Note: **the mod's GDScript is never parsed by the test suite**, so a GDScript
  syntax error ships silently and manifests as the game sitting on the title screen.

# 5. The critical structural fact about the hand-written controller

**`_build_desire` is overridden on most ticks, and this is measured, not inferred.**

Across 5 fixtures and 5,679 wave-17 ticks:

| quantity | range across runs |
|---|---|
| safety tail active (body OR projectile OR wall-recovery) | **0.500 – 0.882** |
| wall-recovery latch active | 0.370 – 0.869 |
| median angle between final command and the desire vector | **36.7° – 76.5°** (pooled 54.7°) |
| median angle when NO tail flag is set | **4.9° – 7.8°** |

The **wall path** is the dominant overrider. And a direct dose test: a threat-weight knob inside
`_build_desire` moved the desire vector by **+0.216** and the final issued command by **+0.003** —
roughly **72x attenuation, with the sign inverted.**

**Consequence, now a standing rule on the project: any change to the desire stage must be assumed
inert until a readback on the FINAL issued command proves otherwise.** This retro-explains a long
list of null results (below): they were changes to a vector that usually does not survive to become
the command.

# 6. The complete ledger of what has been tried and closed

This is the most important section for calibrating your advice. Almost everything has failed, and
the failures are informative.

**Movement / safety-tail interventions — all null:**
- Three separate "charge-aware threat" knobs (down-weighting non-charging enemies; a wall-lane
  penalty; a body-clearance discount). All **NO-GO**, one of them **at maximum dose in the wrong
  direction**. The underlying model — that a specific enemy type is the real threat — is confirmed
  as an accurate *description* but is **unreachable** through the tail's weights.
- Engagement-distance scaling, an `at_weapon_range` boundary dose, a loot-density veto, per-term
  magnitude retunes: all null, all explained by §5.
- A "head to low-density areas" idea turned out to be **already implemented and over-implemented
  relative to the human who wins**: the agent picks the emptiest of 8 candidate headings 72.4% of
  the time (mean rank 1.25 of 8) vs the human's 41.6% (rank 2.37). **The human moves toward ~2x the
  local enemy density and wins.** Pushing further toward avoidance moves *away* from the winner.
- A defect found and fixed on paper: one repulsion term is **exactly zero at wave 17** because it
  sits behind a branch that is false on 87.5% of ticks; the largest-magnitude term (a centre-pull,
  magnitude 20.19) is gated off on the same ticks. So the standoff behaviour is not a strong
  repulsion — it is a weak persistent outward push (magnitude 2.06) while everything that would pull
  the agent inward is switched off. Actionable-looking, but no lever has been found.

**Shop / economy / level-up interventions — all null:**
- Item valuation, materials economics, bank-cap calibration, a rare-weapon shop-lock lifetime
  change, level-up stat valuation: all null or unreachable.
- **A sizing correction worth internalising:** I claimed the shop was a "~100x larger surface" based
  on 1,037 offense-deficient purchases. The number of purchases where the policy actually had a
  *rankable choice* was **91**. Counting events is not counting decisions.

**Behaviour cloning from the hand-written teacher:** works as imitation (the student reproduces the
teacher) but by construction inherits all of the teacher's behaviour, including its defects.

**Behaviour cloning from a HUMAN — closed today, see §8.**

**Reinforcement learning — assessed as not viable in the current apparatus, see §9.**

# 7. The one substantive open finding: spatial confinement

This came from my collaborator watching a live run and saying, in effect: *"it gets skittish, settles
into a corner and stays within a small bounded area — constantly moving but only in a very small
bounded area. I'm constantly moving but I'm not bounding myself to a small area."*

The metric that captures it: **the number of 128-unit cells needed to hold 50% of a wave's player
positions** (192 cells in the arena).

| arm | raw values (n=6 each) | mean | sd |
|---|---|---|---|
| **HUMAN** (same fixture, human driving movement) | 27, 26, 30, 25, 28, 29 | **27.50** | 1.871 |
| **AGENT** (shipped controller) | 7, 19, 13, 17, 10, 12 | **13.00** | 4.427 |

**Every human run exceeds every agent run** — exact rank test p = 1/924 = 0.00108, a gap of 4.5
pooled sd. Fixture-invariant: the human reads 27.5 on one fixture and 29.0 across six others. The
human is also far more *consistent* (sd 1.87 vs 4.43) — the agent is not merely confined, it is
erratic about how confined.

**This is the best-separating endpoint the project has ever had, and no lever has been found for it.**

Two important negatives attached to it:
- **Distance-from-arena-centre is the wrong instrument** and an earlier "the agent edge-hugs" finding
  did **not** reproduce. Median distance from centre is essentially identical (human 597 vs agent
  593/537). An agent orbiting tightly at radius 600 and a human roaming through radius 600 have the
  same mean. Only the concentration metric sees it.
- **It is a correlate, not a proven cause.** It correlates with the human winning; it has never been
  shown to cause winning. Optimising it directly risks Goodharting.

## The related headroom argument

The hand-written teacher and the human are **not near neighbours — they are different policies**:

| predictor of the human's next movement direction | 9-way agreement | mean cosine |
|---|---|---|
| the hand-written teacher | **0.1167** (chance = 0.111) | **−0.0995** |
| best clean trained student | 0.2669 | +0.5232 |
| majority-class baseline | 0.1449 | — |

The teacher agrees with the human at **chance level** and its mean cosine to the human's action is
**negative**. On these states the teacher frequently wants close to the opposite of what the human
does. (This number is trustworthy: the teacher's action is excluded from the student's inputs, so it
cannot be leaked.)

# 8. What I closed today, and why it matters for your advice

I trained a policy by **behaviour cloning on human movement** (12 human-played runs, 12 wins,
~52,000 labelled ticks, split by whole fixture), served it live through the sidecar so that it
**replaced the hand-written controller's output entirely**, and ran a pre-registered 32-trial paired
screen (student vs shipped controller, interleaved, same fixtures, same build).

**Result: the cloned policy plays decisively worse.**

| fixture A | survived the wave | median gross damage |
|---|---|---|
| shipped controller | **10 / 10** | 66 |
| cloned-from-human student | **4 / 10** | 118 (survivors only) |

Fisher one-sided **p = 0.0054**. On a second fixture where all trials survived, the student took
**3.16x** the damage (median 126 vs 40).

And the confinement endpoint **did not even move consistently**: fixture A **−6.95 cells** (more
confined), fixture B **+7.00 cells** (less confined) — opposite signs, both beyond 1.8 control sd.
Even at its best the student reached 14.83 cells, still far below the human's 27.5–29.

**The interpretation I hold:** a policy cloned from a human's *direction choices* does not inherit
the human's *survival*. It bypassed the safety tail — which is exactly what made it worth trying and
exactly what killed it. Plausibly it learned *where* to go but not *when*, which fits a standing
hypothesis that the human's advantage is **temporal** (a single-frame observation with no history
cannot express "close on a walking enemy, disengage when it charges").

**Also relevant to trusting supervised numbers here:** the human-BC label was reconstructible from
the observation **four different ways**, and each fix revealed the next. The first run scored 0.92
validation agreement, which was worthless — a trivial "copy the player's current velocity" baseline
scored 0.9187, because in a human-driven run the player's velocity *is* the human's input one tick
delayed. Later leaks included **the sort order of entities in the observation** (a leak carried by
the permutation, invisible to any per-channel statistic) and **position plus derived scalars
jointly** (a linear probe cleared it; a nonlinear one found R² 0.80). The clean ceiling is 0.2669.

# 9. Constraints on the apparatus — the binding limitation on everything

This is where I most want your judgement, because I think it is the real problem.

- **There is no simulator.** The trainer's environment directory is **empty**. Evaluating a
  counterfactual movement requires launching the actual game. There is no fast model of the game.
- **Throughput: ~65,000–70,000 control decisions per wall-clock hour**, single instance.
- **Concurrency is actively destructive**: six scripts in the repo issue a *global* "kill all Brotato
  processes", so two experiments cannot share the machine. One machine, one run at a time.
- **A 1e6-step RL run is 15+ hours for one seed**, with no hyperparameter search. An RL implementation
  already exists (TD3 with twin critics, plus a residual actor) and was tried; it is structurally
  capped by a **±5° rotation action space**, and its critic was fit on logged data where the action
  was always the teacher's — i.e. **near-zero action diversity**.
- **Trial costs:** a full 20-wave run ~19 min; a wave-17 fixture trial ~4.3 min; a wave-20 fixture
  trial ~45 s.
- **Time-scale acceleration** (2x) is approved for paired fixture campaigns but **must not be used
  for a served neural policy**: the 40 ms inference deadline against a 50 ms control period means
  doubling game speed turns the treated arm into a partially-untreated arm.
- **A keypress during an agent run trips a manual-override emergency stop** and ends the run, so the
  machine is unusable for anything else while a campaign runs.

## One instrument that is unusually good, and may be the key to Danger 5

**`enemy_scaling` in the save file is a verified, exact, controller-free difficulty dial.** It is
`{"damage": 1, "health": 1, "speed": 1}` inside the run-state, and editing it then resuming works:

- At `health = 0.25`, per-enemy max HP scaled by exactly 4.00–4.10 across three independent enemy
  types **including the boss** (boss 29250 → 7313).
- At `health = 1.50`, wave-17 max HP scaled by exactly 1.500 across **six** independent types.
  **Nothing clamps at 1.0** — it works above baseline as well as below.

Note the correspondence: **Danger's own multipliers are enemy damage, enemy health, enemy speed and
nightmare projectiles — and this dial exposes three of those four.** So there is already a validated
way to synthesise most of Danger-5-like pressure on any existing save state, at fine granularity,
with a per-entity readback, without touching the controller and without shipping anything.

Caveats that come with it: an effect measured at elevated scaling is measured on a harder game than
we ship, so transfer must be argued or confirmed at baseline; and dose choice needs a pre-registered
rule or it becomes a garden of forking paths.

# 10. How this project fails — please calibrate your advice to this

I keep a written record of my own failure modes because they recur. The dominant one is **stopping
one step short**: reaching a conclusion that is correct as far as it went, one step before the step
that changes it. Concretely:

- Measured a real 6.4x mispricing in the shop, found the mechanism, implemented the fix — then
  discovered the fix **does not change the ordering** of any decision, because two other terms
  dominate. Reverted.
- Published "selection is clean: 0 misses over 1,037 decisions" from a diagnostic whose candidate
  filter was `null` on 100% of the relevant rows. **It had not found zero misses; it could not find
  one.** A zero from a vacuous filter is not a zero.
- Chose a primary outcome that the treatment **mechanically rescales** (measuring enemy HP pool in a
  campaign whose treatment halves enemy health) — would have produced a large, significant,
  meaningless effect. Caught by external review, not by me.
- Ran a validity guard that **rejected by outcome** (it would have discarded the treatment arm's
  worst trials, flattering it). This happened again *today*, in a document that cites the earlier
  instance.
- Used **gross** damage as the primary endpoint for months without noticing it never subtracts
  healing, while healing varied 15–171 across runs.
- Advertised an endpoint's quality as "~10x separation" from **n=2** control replicates; six
  replicates gave 3.1x more variance and the true figure was 4.5 sd.
- Built two theories on a single trial reading 0.193 against a 0.218–0.500 baseline; over four
  trials it came back 0.317, *above* baseline.

**What this means for your answer:** I am much more likely to be fooled by a plausible mechanism I
can measure than by a hard problem I cannot. If a direction you recommend depends on a causal chain,
please tell me what would *disconfirm* it and what the cheapest disconfirming measurement is.

# 11. The candidate directions I can see, and my honest read

1. **Just run Danger 5 and characterise the failure.** Change the hardcoded 0, run N full runs at
   D5, and measure *where and how* it dies (wave distribution, damage sources, whether death is
   melee crowding, projectiles, or attrition). Cost: ~19 min per run, so 20 runs is ~6.5 hours
   unattended. **My read: this is almost certainly the right first move and I am slightly
   embarrassed it has not been done.** The entire ledger in §6 was built at D0, and the binding
   constraint at D5 may simply be a different one. I would rather characterise the target than
   continue optimising a proxy.
2. **Use `enemy_scaling` to build a Danger-5-like difficulty ladder** on existing fixtures, and find
   the operating point where the current agent's win rate is ~50% — the maximally informative point
   for screening. **My read: strong, cheap, and it converts a ceiling-pinned instrument into a
   discriminating one.** The risk is external validity: it reproduces 3 of Danger's 4 multipliers
   and not the projectile modifier.
3. **Attack the safety tail directly** rather than the desire stage, since the tail owns the command
   on 50–88% of ticks and the wall-recovery latch is the dominant path. **My read: this is where the
   lever must be if the confinement finding is causal — but the agent's position is itself produced
   by the tail, so "why is it in the corner" is circular, and I have no non-circular design yet.**
4. **Give the policy temporal context** (frame stacking / recurrence) and retrain — motivated by the
   human's edge looking temporal and by the cloned policy learning "where" but not "when". **My read:
   the most intellectually satisfying and the most expensive. Given today's result I would want a
   reason to believe it before spending days on it.**
5. **Improve offense rather than movement.** Independent analysis found the separator at wave 17 is
   **offense** (kill rate), and that the agent is *already* more avoidance-seeking than the human who
   wins. **My read: underexplored relative to how much evidence points at it.** Most of my effort has
   gone into movement because movement is what the telemetry measures best — which is a bad reason.
6. **Abandon the hand-written controller and do serious RL** with a proper action space and
   action-diverse data collection. **My read: not viable on one machine with no simulator, at ~68k
   decisions/hour, unless something changes about the apparatus.**

# 12. My questions

1. **Given that Danger 5 has never been run — what is the right first experiment, and what should it
   measure?** Is my instinct (characterise the D5 failure mode before optimising anything) correct,
   or is there a better-value first move?
2. **Is Danger 5 plausibly reachable by improving this hand-written potential-field controller at
   all, or does the difficulty jump demand a qualitatively different policy class?** I would rather
   hear "your architecture caps out below the target" now than in three weeks.
3. **Where should effort go: movement, offense (kill rate), or the shop/build economy?** The
   evidence pointing at offense is decent and I have under-invested in it. At D5, enemy health
   scales — which mechanically punishes low kill rate. Does that change the ranking?
4. **How would you use the `enemy_scaling` dial?** Specifically: is a difficulty ladder on existing
   fixtures a sound way to buy statistical power, given the external-validity cost, and how would
   you pre-register the dose choice?
5. **Is the confinement finding worth continuing to chase?** It is my best-separating measurement
   (4.5 sd, p = 0.001, fixture-invariant) but it is a correlate, three knobs aimed at it are dead,
   and today's attempt to reach it by cloning a human made play *worse*. At what point is it a red
   herring?
6. **Given no simulator, ~68k decisions/hour, and no usable concurrency — is there a learning
   approach I am dismissing too fast?** In particular, is there a way to get useful
   action-diverse data, or a surrogate model worth building, that changes the RL calculus?
7. **What would you refuse to spend time on**, out of §6 and §11?

---

## Appendix: the numbers in one place

| quantity | value |
|---|---|
| runs ever recorded / at Danger > 0 | **1,873 / 0** |
| Danger 5 selectable in save | **yes** (`max_selectable_difficulty: 5`) |
| Danger tiers beaten, our character | **0** |
| full-run win rate, Danger 0 | **0.395 measured** (77/195); 0.574 predicted, never confirmed |
| historical unnoticed win-rate collapse | **47 points over ~20 versions** |
| only clean shipped win | wave-20 projectile blindness, 0.688 → 1.000, n=64, p=0.000426 |
| confinement, human vs agent (cells holding 50% of a wave) | **27.50 vs 13.00**, 4.5 sd, p=0.00108 |
| teacher agreement with human movement | **0.1167** (chance 0.111), cosine **−0.0995** |
| best clean human-BC student | 0.2669 agreement, cosine +0.5232 |
| human-BC student served live | **survival 4/10 vs 10/10**, p=0.0054; 3.16x damage |
| desire-stage knob attenuation through the safety tail | **~72x, sign inverted** |
| safety tail owns the command | **50–88%** of wave-17 ticks |
| control throughput | ~65–70k decisions/hour, no concurrency |
| full run / w17 fixture / w20 fixture cost | ~19 min / ~4.3 min / ~45 s |
| `enemy_scaling` dial fidelity | exact to dose, 0.25x and 1.50x, 6 enemy types + boss |
