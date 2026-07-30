# Brotato Agent: Strategy for Moving from Danger 0 to Danger 5

**Consultation date:** 2026-07-30  
**Scope:** Strategic diagnosis, experimental design, and next-step sequencing for the first Danger 5 campaign

---

## Executive verdict

The project should **stop ordinary Danger 0 feature iteration and run the target difficulty now**.

The correct first move is not “try another movement knob,” “train a larger policy,” or “improve the current Danger 0 win rate.” It is:

1. remove the hardcoded Danger 0 selection;
2. add authoritative, fail-closed difficulty readbacks;
3. run a frozen-policy Danger 5 characterisation campaign;
4. preserve a save at every reached wave;
5. use those actual Danger 5 states to determine whether the binding failure is clearance, incoming damage, enemy speed, projectile pressure, local movement, upstream positioning, or build trajectory.

I agree with the instinct in the brief that it is embarrassing Danger 5 has never been run. More importantly, every additional Danger 0 intervention performed before this step risks being another well-measured answer to the wrong question.

I would **not** begin with an undifferentiated 20-run campaign. I would pre-register a minimum of 12 independent Danger 5 attempts and a maximum of 20. Continue from 12 to 20 only if the failure modes remain diffuse or the first 12 do not provide enough independent saved states for the next diagnostic. At full run length, that costs approximately 3.8 to 6.3 machine-hours; early Danger 5 deaths will make the actual cost lower.

My architectural verdict is conditional:

> **A deterministic hand-written controller may still be capable of winning at Danger 5, but the present “sum a desire vector, then let an accumulated safety tail overwrite it” architecture should not receive more blind constant tuning.**

The existing controller has not been shown incapable of Danger 5. It has also not earned a presumption that another potential-field coefficient will get there. If Danger 5 exposes a movement-limited failure, the next credible policy class is a **hierarchical temporal controller**—a persistent waypoint or maneuver selector plus a small verified collision shield—not full model-free reinforcement learning and not another one-frame behavior-cloning replacement.

The `enemy_scaling` dial is extremely valuable, but it should be used as:

- a **channel-attribution tool** on genuine Danger 5 saves;
- a **calibrated pressure ladder** for cheap candidate screening;
- never as a substitute for final Danger 5 qualification.

The spatial-confinement result should remain a diagnostic. It should **not** be directly optimized. It deserves one last command-effective causal gate; if that gate moves confinement materially without improving survival, close it.

The tentative effort priority after the first Danger 5 baseline is:

1. **target characterisation and channel attribution;**
2. **offense/tempo**, if Danger 5 deaths show arena saturation or inadequate clearance;
3. **final-command arbitration and temporal positioning**, if human movement or safe-heading analysis rescues the same builds;
4. **shop/build scoring only when exact offline counterfactuals show actual decision flips large enough to matter;**
5. **no full online RL under the current apparatus.**

---

# 1. What the evidence establishes, suggests, and does not support

## 1.1 Established by the supplied evidence

The following claims are supported directly:

- All **1,873 recorded runs were Danger 0**. The target difficulty has never been evaluated.
- Danger 5 is already selectable; no unlock campaign is required.
- The automatic-start path currently discards the configured danger and explicitly selects `0`.
- The only measured full-run rate on the current Danger 0 era is **77/195 = 0.395**. The proposed `0.574` is a projection, not a measured full-run result.
- A perception repair produced the only large, clean, replicated improvement in the project: paired fixture survival moved from `0.688` to `1.000`.
- The hand-written controller's safety tail is active on **50% to 88.2%** of measured wave-17 ticks.
- The wall-recovery path is the dominant overrider.
- A desire-stage threat-weight change was attenuated by approximately **72×** before becoming the issued command, with the sign inverted.
- Therefore, a desire-stage change cannot be assumed to alter live behavior without final-command readback.
- A human and the controller occupy measurably different spatial regimes on the tested states: the human required approximately `27.5` cells for 50% positional mass, versus `13.0` for the agent.
- The human-trained one-frame policy did not reproduce the human's live survival and performed decisively worse than the shipped controller.
- The current apparatus has no simulator, no useful concurrency, and approximately `65,000–70,000` control decisions per wall-clock hour.
- The existing logged data have near-zero action diversity because the action was almost always the teacher's action.
- The existing RL residual is structurally narrow: a maximum `±5°` rotation that the teacher tends to cancel within roughly 10–20 ticks.
- `enemy_scaling.health`, `.damage`, and `.speed` are real, controller-independent intervention channels, and the health dial has been verified both below and above `1.0`.

## 1.2 Suggested, but not established

The evidence makes these hypotheses worth testing:

- Danger 5 may be substantially **clearance-limited**, because enemy health increases and Danger 0 wave 17 already shows an offense/kill-rate separator.
- The current safety-tail architecture may contribute to corner residence, spatial confinement, or failure to execute persistent maneuvers.
- The human's advantage may depend on temporal context—when to approach, when to disengage, and when to continue a maneuver—rather than only on the instantaneous desired direction.
- A short-horizon model or temporal high-level policy may be more useful than a full end-to-end movement network.
- Perception audits have a favorable prior because the only major shipped gain was a state-vector blind spot.

These are priors, not conclusions.

## 1.3 Not supported at all by the current evidence

The supplied evidence does **not** support any of the following:

- that Danger 5 is unreachable by a hand-written policy;
- that Danger 5 is reachable by the current controller with parameter tuning;
- that offense will be the dominant Danger 5 bottleneck;
- that shop scoring is irrelevant at Danger 5 merely because Danger 0 shop interventions were null;
- that spatial confinement causes deaths;
- that increasing arena coverage will improve survival;
- that the human advantage is definitely temporal;
- that the failed one-frame human clone proves human demonstration learning is unviable;
- that the three exposed `enemy_scaling` channels reproduce Danger 5;
- that a policy which succeeds on the synthetic scaling ladder will succeed on actual Danger 5;
- that ordinary model-free RL is impossible in principle.

The current data justify refusing to fund several of those directions under the present setup. They do not justify universal claims about what could never work.

---

# 2. Question 1 — The right first Danger 5 experiment

## 2.1 Yes: characterise the target before optimizing anything else

The instinct in the brief is correct.

The project is currently optimizing an agent that has never played the target game. Danger 5 changes several channels simultaneously, and the binding failure can therefore differ qualitatively from Danger 0:

- greater enemy health can create clear-rate saturation;
- greater damage can turn recoverable contact into terminal contact;
- greater speed can invalidate distance margins and wall-recovery timing;
- the nightmare-projectile channel can create a hazard class absent from the synthetic three-channel dial.

A clean Danger 0 null does not automatically transfer to Danger 5. Equally, a plausible Danger 0 mechanism does not automatically become the Danger 5 mechanism.

## 2.2 Do not start the campaign until selection is fail-closed

The hardcoded `0` should be replaced with the configured danger, but that code edit alone is not adequate qualification.

Every attempted run should record all of the following before combat begins:

```text
requested_danger
selected_ui_danger
save_difficulty_value
runtime multiplier block:
    enemy_health
    enemy_damage
    enemy_speed
    nightmare_projectiles
policy_version
mod_version
configuration_hash
```

Where feasible, add a live entity-level readback that confirms the expected health, damage, or speed effect rather than trusting only the menu or save field.

A run is technically valid only when the requested and observed difficulty values agree. A mismatch is a technical failure, not a gameplay loss and not a run to be silently retried.

The automatic-start fix should also have a positive runtime signal proving that the mod loaded and the Danger 5 branch executed. Source-text tests do not prove that the GDScript parsed or that the branch ran.

## 2.3 Recommended campaign: 12 attempts minimum, 20 maximum

Run one frozen policy, one fixed build configuration, at 1.0× game speed.

### Minimum campaign

- **12 independent full attempts**
- approximate upper-bound machine cost: `12 × 19 min = 3.8 h`
- archive a complete save at the entry to every reached wave
- retain every attempt in an append-only ledger

### Pre-registered extension to 20

Continue to 20 attempts if, after 12:

- terminal waves are spread across more than two adjacent wave bands;
- no primary failure phenotype accounts for at least two-thirds of losses;
- too few independent saves exist in the dominant failure band;
- or the campaign produces enough wins that a somewhat better baseline estimate is valuable.

The extension rule must be written before the first Danger 5 run. The purpose is to avoid stopping only when the first 12 happen to tell an attractive story.

Twenty full-length attempts cost approximately 6.3 hours. If Danger 5 kills the agent early, the actual cost will be lower.

## 2.4 This is a characterisation campaign, not a confirmatory treatment test

The north-star outcome remains:

```text
Danger 5 full-run victory
```

But a first campaign may produce no victories. That does not make it uninformative.

The baseline report should include four levels of outcome.

### A. Run outcome

```text
win
terminal wave
time within terminal wave
```

### B. Failure channel

Each damaging or terminal event should be classified from telemetry as far as the state supports:

```text
melee body
moving projectile
stationary projectile
other visible hazard
unexplained / absent from observation
```

Do not force each run into exactly one mutually exclusive story when several channels contribute. A multi-label phenotype is preferable to a falsely crisp label.

### C. Pressure and clearance trajectory

At each wave and especially in the 10 seconds preceding death:

```text
enemy count alive
total enemy HP alive
spawn rate
kill rate
effective damage output
fraction of time with a valid target
player HP trajectory
damaging-contact count
```

The key distinction is:

- **clearance failure:** enemy count or HP backlog grows because the build cannot service the spawn stream;
- **survival failure:** the backlog is manageable, but the agent takes avoidable hits;
- **no-local-solution failure:** the agent dies in a state where no feasible short-horizon heading exists.

### D. Controller-state trajectory

```text
safety-tail activation
wall-recovery activation
angle: desire vector → final command
final controlling layer
cell-concentration metric
distance to walls
heading reversals
loot attraction and collected value
```

The confinement metric should be reported here as a phenotype, not optimized as an endpoint.

## 2.5 A useful predeclared failure-classification tree

For each terminal event, ask in this order:

1. **Was the causal hazard represented in the observation?**
   - No: perception/state-vector defect.
   - Yes: continue.

2. **Was at least one locally feasible heading available?**
   - No: upstream positioning, build, or earlier trajectory failure.
   - Yes: continue.

3. **Did the issued command choose a feasible heading?**
   - No: movement arbitration or temporal policy failure.
   - Yes: continue.

4. **Was the arena already saturated?**
   - Yes: clearance/build/tempo failure, possibly with movement as a contributor.
   - No: local risk estimation or execution failure.

5. **Did the wall or safety tail materially replace the desire vector before the failure?**
   - Yes: tail-level mechanism becomes testable.
   - No: do not blame the tail merely because it is often active elsewhere.

This classification will not prove causality by itself, but it will prevent the project from immediately selecting a favorite mechanism.

## 2.6 The first high-value follow-up: human handover on actual D5 failure states

After the first Danger 5 campaign identifies a repeatable failure wave, use the archived save-state harness to let the human control movement while the agent retains the exact same build, shop policy, level-up policy, and state.

This is the cheapest strong discriminator between movement and build:

- **Human repeatedly rescues the same D5 build:** substantial movement-policy headroom exists.
- **Human also fails at approximately the same point:** build/clearance or intrinsic state difficulty becomes the stronger explanation.
- **Human survives the wave but later dies:** the immediate wave is movement-actionable, but the complete run may still be build-limited.

A useful first screen is three independent D5 source states with three human continuations each. At a wave-17-like cost, that is approximately 39 minutes of operator play. It is not a final performance estimate; it is a modality discriminator.

---

# 3. Question 2 — Can the hand-written controller plausibly reach Danger 5?

## 3.1 The evidence does not justify abandoning deterministic control

Brotato's combat action space is unusually narrow: the policy chooses a two-dimensional movement vector while weapons fire automatically. The state is richly observable. That is favorable to deterministic, engineered control.

A potential-field component can remain useful for:

- immediate repulsion;
- attraction to resources or open regions;
- smooth local motion;
- candidate-direction generation.

Nothing in the brief proves that a neural policy is required.

## 3.2 The present arbitration architecture is the concern

The problematic architecture is not “hand-written” versus “learned.” It is:

```text
sum approximately 12 motives into a desire vector
        ↓
pass through a long ordered safety tail
        ↓
allow wall recovery and other late rules to replace the command
```

Measured consequences include:

- the tail owns the command on most hard-wave ticks;
- desire-stage interventions can be attenuated by two orders of magnitude;
- the wall path is the dominant overrider;
- single-frame learned replacement loses the tactical protection of the tail.

That creates two bad choices:

1. tune a desire vector that often never reaches the game; or
2. bypass the tail and lose the mechanisms that keep the character alive.

More tuning inside the first box is not a credible route to Danger 5.

## 3.3 The next policy class, if movement is confirmed as binding

A qualitatively better deterministic architecture would be hierarchical:

### High-level temporal maneuver selector

Runs at perhaps 2–5 Hz or when a material state change occurs. It selects:

```text
waypoint
circulation direction
escape corridor
engage / disengage mode
resource-route objective
```

It has short memory or explicit state, so it can express:

- continue this orbit;
- finish crossing the arena;
- approach while an enemy is walking;
- disengage when a charge begins;
- avoid returning immediately to the same corner.

### Low-level verified safety shield

Runs at the normal control rate. It may modify the proposal only when a predicted collision or wall trap violates a hard safety condition.

The shield should report:

```text
proposal
executed command
reason for modification
minimum required correction
```

This differs materially from the current tail. The objective is not to let many heuristics repeatedly outvote one another. It is to preserve a persistent maneuver and apply the smallest necessary safety correction.

The high-level selector can initially be hand-written. It can later be learned from human handovers or action-probe data without replacing the low-level safety layer.

## 3.4 A bounded feasibility decision before a large rewrite

Do not spend three weeks deciding whether the old architecture can reach Danger 5. Use two gates.

### Gate A: same-build human rescue

Across several independent Danger 5 failure states, can human movement substantially improve wave survival or progression?

- If no, a movement-policy rewrite is not the first priority.
- If yes, movement headroom is real.

### Gate B: command-effective deterministic challenger

Can one intervention at the final-command or maneuver level:

- materially change the intended controller property;
- improve a hard scaled fixture or actual D5 fixture;
- and avoid a clear baseline regression?

If yes, retain the deterministic path.

If the human repeatedly rescues the states but no stateless command-level intervention can reproduce the behavior—and the disagreement depends on recent trajectory or enemy phase—then the current architecture has reached a meaningful limit. That is the point to adopt temporal hierarchy, not the point to launch generic TD3.

## 3.5 My direct answer

> **Danger 5 is plausibly reachable by a hand-written or hybrid deterministic controller. It is not plausibly reachable by continuing the current pattern of desire-stage knob tuning without changing arbitration.**

That distinction matters. The policy class is not yet disproved; the iteration method largely is.

---

# 4. Question 3 — Movement, offense, or shop/build economy?

## 4.1 Do not decide this from Danger 0 alone

The brief's offense evidence is real enough to create a prior:

- wave 17 showed a kill-rate separator;
- the agent is already more avoidance-seeking than the successful human;
- Danger 5 increases enemy health.

But Danger 5 also increases damage, speed, and projectile pressure. It is entirely possible for a health-driven clearance deficit to dominate one wave and a projectile or positioning deficit to dominate another.

The correct ranking is conditional on the first Danger 5 failure map.

## 4.2 A decision table

| Danger 5 observation | Strongest next area | Cheapest disconfirming test |
|---|---|---|
| Enemy count/HP backlog rises; target availability is near-continuous; human cannot rescue same build | Offense/build tempo | Reduce enemy health or increase player weapon output on the exact save; check whether the wave is rescued |
| Human rescues same build; feasible safe headings exist; agent chooses another heading | Movement arbitration | Final-command challenger on paired D5 fixtures |
| Human rescues only by persistent circulation or anticipatory moves | Temporal high-level policy | Frame-stack/recurrent human model or explicit maneuver state on the same fixtures |
| Deaths occur with no locally safe heading | Upstream positioning or clearance | Branch earlier landmark; test whether changed positioning 0.5–2 s earlier creates feasible headings |
| Damage source is absent from observation | Perception | State-vector coverage repair and entity-level readback |
| Build is weak because actual rankable shop decisions prefer speed/defense over offense | Shop scoring | Offline replay of every actual board under alternative weights; count real decision flips before coding |
| Build is weak but shop boards contain no actionable alternative | Economy/collection or RNG | Save-edit offense dose and collection trajectory; do not tune scoring |

## 4.3 My tentative priority after baseline

Absent the Danger 5 data, I would allocate effort in this order:

1. **Offense/tempo diagnostics**
2. **Final-command movement and temporal positioning**
3. **Shop scoring only after offline decision-flip proof**

Why offense first? Not because it has been established as the D5 cause, but because the target mechanically increases enemy durability and the current project has under-invested in clearance measurement relative to movement measurement.

Why not shop first? Because prior shop investigations found a small rankable surface and multiple nulls. Danger 5 can reopen the question, but only if actual D5 boards reveal a different decision boundary.

## 4.4 Distinguish “offense is causal” from “offense is actionable”

An enemy-health intervention can prove that more clearance would rescue a state. It does not prove the policy can acquire that clearance.

For every offense rescue, immediately calculate:

```text
required clearance improvement
maximum plausible gain from actual shop decision changes
maximum plausible gain from collection or levels
```

If a failing D5 build requires a 30% clearance increase and all realistic policy changes can produce 3–5%, the mechanism is causal but not currently actionable.

That should close the intervention path rather than justify more scoring layers.

## 4.5 Exact offline shop replay is the gate

Because the shop policy is deterministic, any proposed reweighting should first be run on the exact archived candidate boards.

The minimum gate is:

```text
How many choices actually flip?
At which waves?
What effective build delta do those flips create?
Would that delta approach the save-edit rescue dose?
```

If the answer is “almost no decisions flip,” do not deploy.

This is the same protection the project needed when a mathematically correct scoring repair was found to be behaviorally inert.

---

# 5. Question 4 — How to use `enemy_scaling`

## 5.1 Use it in two distinct roles

### Role A: channel attribution on genuine Danger 5 states

This is the highest-value use.

Collect actual Danger 5 saves from the dominant failure wave. On the same source states, compare:

```text
D5 control: all real D5 channels unchanged
H-off: health multiplier reset toward 1.0
D-off: damage multiplier reset toward 1.0
S-off: speed multiplier reset toward 1.0
HDS-off: all three exposed multipliers reset toward 1.0
```

The nightmare-projectile channel remains at the real Danger 5 setting in all arms.

This design is stronger than adding three channels to a Danger 0 save because it preserves the actual Danger 5 context and asks:

> Which exposed Danger 5 channel is necessary for this failure, and how much difficulty remains when all three are removed?

Interpretation:

- `H-off` rescues: enemy durability is a major contributor.
- `D-off` rescues: the number or timing of contacts may be similar, but their severity is terminal.
- `S-off` rescues: timing, spacing, or wall recovery is not robust to faster enemies.
- no single arm rescues, but `HDS-off` does: interactions matter.
- `HDS-off` remains difficult: nightmare projectiles or another Danger-linked mechanism is important.

Do not claim that the largest arm effect identifies the universally “most important” multiplier. The interventions are not commensurate and interactions can be substantial.

### Role B: a calibrated three-channel pressure ladder

This converts ceiling-pinned fixtures into a discriminating test bench.

Call it a **three-channel pressure ladder**, not a Danger 5 simulator. It omits at least the nightmare-projectile channel.

## 5.2 Prefer real danger-tier values; interpolate only when needed

First read the actual multiplier blocks for Danger levels 0 through 5.

If those tiers provide enough resolution, use their real health/damage/speed vectors.

If finer steps are required, interpolate each multiplier in log space:

\[
m_j(\lambda)=\exp\left(\lambda\log m_{j,D5}\right),
\quad j\in\{health,damage,speed\},
\quad \lambda\in[0,1].
\]

This guarantees:

```text
lambda = 0 → multiplier 1.0
lambda = 1 → exact D5 multiplier for that channel
```

A fixed grid such as:

```text
0.00, 0.25, 0.50, 0.75, 1.00
```

is sufficient initially.

## 5.3 Pre-register the operating-point selection

Do not inspect a broad dose grid and then choose the dose at which the preferred candidate looks strongest.

Use separate calibration data.

### Recommended calibration algorithm

1. Freeze a set of independent source fixtures.
2. Evaluate the incumbent only.
3. Start at the middle ladder dose.
4. Move one grid step harder or easier according to a prewritten staircase.
5. Select the first dose whose aggregate wave-survival estimate lies in `[0.35, 0.65]`.
6. If no dose enters the interval, choose the dose with survival closest to `0.50`; ties choose the lower dose.
7. Freeze that dose before running any challenger.
8. Evaluate the challenger on fresh source fixtures.

A practical calibration is:

```text
6 independent source states
× 2 fresh-RNG continuations per tested dose
```

At a wave-17-like duration and approved 2.0× acceleration, each 12-trial dose costs approximately 26 minutes. Two or three staircase doses cost roughly 50–80 minutes.

## 5.4 Use two nearby pressure levels for robustness

A candidate that helps only at one exactly tuned dose may be exploiting the instrument.

For a serious screen, test:

```text
selected operating dose
one adjacent easier or harder dose
```

The candidate need not improve equally at both, but the direction should be coherent and it should not catastrophically regress at baseline.

## 5.5 Endpoints for the ladder

Use a hierarchy:

1. wave completion;
2. time survived within the wave;
3. death-adjusted healthy-time or HP trajectory;
4. mechanism-specific measurements such as enemy backlog, damaging-contact count, feasible-heading rate, and final-command behavior.

Do not use an endpoint that the dial mechanically rescales as though it were an independent success measure. For example, total enemy maximum HP is not a valid primary comparison when enemy health itself is the treatment.

## 5.6 Inference must remain fixture-clustered

Fresh-RNG continuations from one saved build are repeated measurements of that build, not independent build samples.

Report:

- source-state count;
- repeats per source;
- per-source arm rates;
- fixture-clustered intervals or resampling.

Do not let 40 continuations from one source masquerade as 40 independent builds.

## 5.7 Final external-validity rule

No synthetic-ladder result ships on its own.

The ladder is for:

- selecting mechanisms;
- rejecting dead ideas cheaply;
- screening candidate policies;
- measuring dose response.

A candidate is only a Danger 5 improvement after it is evaluated on actual Danger 5 runs or actual Danger 5 saved states.

---

# 6. Question 5 — Is confinement worth continuing to chase?

## 6.1 Keep it as a biomarker, not an objective

The separation is unusually strong:

- every human run exceeded every agent run;
- the magnitude was large;
- it reproduced across fixtures;
- the mean-radius measure correctly failed to see it.

That makes confinement a valuable phenotype.

It does not make it a target.

The negative human-clone result is especially important. The learned policy:

- did not move the confinement endpoint consistently;
- performed much worse;
- bypassed the safety tail.

That does not refute the human policy, but it demonstrates that “make the action look more human” and “increase occupied cells” are insufficient objectives.

## 6.2 The cheapest remaining analysis: temporal ordering

Before another intervention, calculate rolling measures such as:

```text
cell concentration over the preceding 3–10 seconds
wall-recovery occupancy
distance to wall
enemy count and HP backlog
HP trajectory
damage in the following 1–3 seconds
```

Ask whether confinement:

- precedes the rise in risk;
- follows the rise in risk;
- or merely co-occurs with wall pressure.

This remains observational, but it can disconfirm a simplistic causal story.

If low coverage appears only after enemy pressure or HP collapse, it is more likely a symptom. If it consistently precedes the collapse across independent runs, it earns a causal intervention.

## 6.3 One final command-effective causal gate

If Danger 5 shows the same pattern, run one bounded deconfinement intervention that acts at the final-command or maneuver level.

A defensible design would:

- detect persistent residence in a small cell set;
- select a safe waypoint outside that set;
- hold the waypoint long enough to create a real maneuver;
- retain an immediate collision veto;
- log every proposed and executed command;
- prove that the occupied-cell endpoint moves before evaluating outcome.

The gate has two parts:

### Manipulation check

The challenger must materially increase spatial coverage on the targeted fixtures. If it does not, the experiment is invalid as a test of confinement.

### Outcome check

Primary: wave completion or terminal progression.  
Secondary: healthy-time, damaging contacts, and wall-trap recurrence.

## 6.4 Closure rule

Close confinement as an intervention target if:

- a final-command-effective challenger changes coverage by a large, predeclared amount;
- yet provides no coherent survival or progression benefit on paired hard fixtures;
- or increases coverage only by increasing unsafe exposure.

Continue logging it afterward because it may remain a useful state descriptor.

My blunt recommendation is:

> **Do not spend more time tuning ordinary attraction or repulsion coefficients to chase the cell metric. One final causal gate is justified; a fourth indirect knob is not.**

---

# 7. Question 6 — Is there a viable learning approach without a simulator?

## 7.1 Standard online model-free RL is still the wrong bet

The current setup combines several unfavorable properties:

- long, stochastic episodes;
- one serial game instance;
- no fast simulator;
- no parallel environments;
- a narrow residual action;
- teacher-only logged actions;
- expensive hyperparameter iteration;
- sparse terminal success.

One million decisions in approximately 15 hours is not itself impossible. The problem is that one million low-diversity decisions from one environment is not enough to make ordinary actor-critic training reliable, and there is no budget for repeated seeds and architecture search.

I would continue to refuse full TD3-style training under this apparatus.

## 7.2 The failed human clone does not close demonstration learning

The failed policy tested a particular design:

- one-frame input;
- direction imitation;
- full replacement of the shipped command;
- bypass of the safety tail;
- approximately 12 human runs.

It establishes that this design is inadequate.

It does not establish that the following are inadequate:

- temporal inputs;
- high-level maneuver imitation;
- intervention only on failure strata;
- a learned proposal passed through a safety shield;
- DAgger-style correction of states actually visited by the improved policy.

The negative result should prevent a larger repeat of the same design, not prevent a different formulation.

## 7.3 Best learning candidate: temporal high-level imitation

Use the existing human data first. Do not collect another 60–80 trials until an offline feasibility gate passes.

### Input

A short history, for example the preceding 0.5–1.5 seconds, including:

```text
player trajectory
enemy and projectile trajectories
wall-recovery state
current and recent final commands
recent hazard / HP change
local material field
```

### Output

Do not predict every 20-Hz movement vector. Predict a slower macro decision:

```text
target waypoint
circulation direction
engage / disengage
continue / switch maneuver
resource-route objective
```

### Execution

A deterministic low-level tracker follows the macro decision. A small safety shield makes only the minimum change required to avoid an imminent collision.

This preserves tactical protection while giving the learned component the temporal job the current controller may lack.

## 7.4 Targeted DAgger is more attractive than broad behavior cloning

The paired data are most valuable where:

- human and agent strongly disagree;
- crowding is high;
- wall recovery is active;
- Danger 5 failures concentrate;
- the human demonstrably rescues the same build.

Collect human corrections only in those strata. This avoids spending operator time labeling thousands of easy states where the incumbent is already adequate.

The objective is not “match the human everywhere.” It is:

> choose a better maneuver in states where the incumbent's maneuver is demonstrably associated with failure.

## 7.5 How to create action-diverse data safely

The project can create useful local action support without full random exploration.

On saved hard fixtures:

1. generate a small set of headings or macro-waypoints that pass a conservative collision screen;
2. randomize among those safe candidates;
3. hold the selected macro action for a meaningful duration, such as several control ticks, rather than one cancellable tick;
4. return to the incumbent afterward;
5. record proximal outcomes over the following 0.5–2 seconds.

Possible labels include:

```text
damaging contact
minimum clearance
change in enemy backlog
wall-trap entry
material pickup
future feasible-heading count
```

This is a micro-randomized action-probe instrument. It is not yet RL.

It provides the action diversity required to train either:

- a short-horizon action-value ranker;
- a risk model;
- or a candidate-heading selector.

The candidate set should be generated from safe actions rather than unrestricted random directions. The purpose is data support, not sacrificing full runs.

## 7.6 A useful surrogate is short-horizon, not a full game simulator

Building a complete learned Brotato simulator would be a major research project and would inherit compounding-error problems.

A tractable surrogate predicts only the next short window:

```text
P(damage within 1 s | state, macro action)
expected minimum clearance
expected enemy-pressure change
expected material collection
probability of entering a wall trap
```

The rich telemetry and known action make this much more plausible than predicting an entire 20-wave run.

Use the model to rank candidate maneuvers online or to identify states where the incumbent is clearly dominated. Final decisions must still be qualified in the real game.

## 7.7 A staged learning gate

Before serving any new learned component:

1. **Leak-free offline test**
   - split by complete source run or fixture;
   - beat trivial velocity-copy and majority baselines on the targeted disagreement stratum;
   - verify that temporal history adds value over a single frame.

2. **Shadow test**
   - compute proposals without applying them;
   - inspect when they disagree and whether the proposed macro action is feasible.

3. **Manipulation test**
   - apply on saved fixtures;
   - prove the intended maneuver or controller metric changes.

4. **Outcome screen**
   - paired hard-fixture survival/progression.

5. **Actual Danger 5 confirmation**
   - only after the prior gates pass.

Failure at any stage should stop the branch before a large human-data campaign.

---

# 8. Question 7 — What I would refuse to spend time on

## 8.1 More Danger 0 desire-stage coefficient tuning

Refuse unless a final-command readback first proves the proposed change survives the tail on the target states.

The measured 72× attenuation makes otherwise plausible coefficient work presumptively inert.

## 8.2 Direct optimization of the confinement metric

Refuse after one command-effective causal gate. A strong correlate is not a reward function.

## 8.3 Another one-frame, full-replacement human behavior clone

The existing experiment already rejected that design. More data do not repair the missing temporal state or the loss of tactical safety.

## 8.4 Full online actor-critic RL in the current environment

Refuse until at least one of these changes:

- a fast simulator exists;
- multiple independent environments can run;
- safe action-diverse data exist;
- or the learning problem is reduced to a low-frequency high-level action.

## 8.5 A full learned world model

Refuse as a near-term milestone. A short-horizon risk/action model is a bounded alternative.

## 8.6 Generic shop-policy retuning

Refuse until exact replay on actual Danger 5 boards proves the proposed weights alter enough decisions and approach the causal rescue dose.

## 8.7 Re-running the closed Danger 0 interventions merely because the difficulty changed

A Danger 5 mechanism can reopen an intervention class, but only with a specific prediction.

For example:

- if speed-channel ablation rescues and wall-latch timing fails, wall recovery is legitimately reopened;
- if health-channel ablation rescues, a prior projectile-avoidance knob remains irrelevant.

“Danger 5 is different” is not by itself a license to repeat the entire null ledger.

## 8.8 Large full-run campaigns before a candidate has passed fixture screening

Use full Danger 5 runs to establish the target baseline and to confirm a qualified candidate. Do not use them as the first test of every idea.

---

# 9. A concrete, ordered, costed next-phase plan

Times below separate approximate machine time from engineering or operator effort. Fixture costs assume a wave-17-like `4.3 min` trial and approved `2.0×` acceleration; the actual dominant wave may change the totals.

| Step | Work | Approximate cost | Decision produced |
|---|---|---:|---|
| **0** | Replace hardcoded Danger 0; add requested/selected/live multiplier readbacks and fail-closed validation | Small code change; roughly 1–3 engineering hours; 2 launch smokes, up to ~40 min machine | Proves the project can genuinely run D5 |
| **1** | Frozen-policy D5 baseline, 12 attempts minimum | Up to **3.8 h machine** | Initial terminal-wave and failure-phenotype distribution |
| **1b** | Extend baseline to 20 only under predeclared rule | Additional up to **2.5 h machine** | Better coverage if failures are diffuse |
| **2** | Archive saves at every reached wave; construct D5 failure-state library | Included in Step 1 plus ~1–2 h analysis | Supplies independent fixtures for cheap experiments |
| **3** | Human movement handover on 3 independent dominant-wave D5 fixtures, 3 repeats each | About **39 min operator/game time** at 1.0× for wave-17-like trials | Movement-versus-build discriminator |
| **4** | D5 channel-removal experiment: control, H-off, D-off, S-off, HDS-off; 4 fixtures × 2 repeats | 40 trials; about **86 min machine** at 2.0× for wave-17-like trials | Identifies exposed difficulty channels and interactions |
| **5** | Calibrate three-channel pressure ladder on separate fixtures | 24–36 trials; about **50–80 min machine** | Frozen discriminating dose for candidate screens |
| **6** | Select one mechanism-specific intervention; prove it changes the final command or build | Mostly offline plus 8–16 fixture trials | Manipulation check; rejects inert changes |
| **7** | Paired screen at calibrated pressure | 32 trials; about **69 min machine** | Effect-size screen |
| **8** | Fresh-fixture confirmation if screen passes | 64 trials; about **2.3 h machine** | Replication before actual D5 |
| **9** | Actual D5 full-run challenger versus frozen incumbent | Start with 12 per arm, approximately **7.6 h maximum machine time** | Target-level evidence |

This sequence spends approximately one working night of machine time to learn what Danger 5 actually is before committing to a policy rewrite.

---

# 10. Pre-registration template for the first D5 campaign

## 10.1 Objective

Characterise the shipped policy's actual Danger 5 failure distribution and create an independent saved-state library. This is not a test of a treatment.

## 10.2 Frozen elements

```text
policy version
shop policy
level-up policy
character
starting weapon families
game speed
telemetry schema
machine-use conditions
```

## 10.3 Technical validity

A run is valid only if:

```text
requested danger = 5
selected danger = 5
runtime/save danger readback = 5
multiplier block is present and recorded
mod-ready signal is observed
capture stream is structurally complete
```

A technical failure remains in the attempt ledger and is reported separately. It is never excluded because of its gameplay outcome.

## 10.4 Sample rule

```text
minimum: 12 valid gameplay attempts
maximum: 20
```

Continue from 12 to 20 if:

- no two-wave band contains at least 75% of losses;
- no failure phenotype contains at least two-thirds of losses;
- fewer than four independent usable saves exist in the dominant failure band;
- or the observed result is too diffuse to choose the next diagnostic.

## 10.5 Primary report

```text
wins / attempts
terminal-wave distribution
time-to-death distribution
```

## 10.6 Mechanistic report

For every loss:

```text
hazard class
visibility / perception coverage
feasible-heading count
issued-heading rank
enemy-count and HP-backlog trajectory
kill rate and target availability
tail/wall activation
desire-to-command angle
cell concentration
build and economy state
```

## 10.7 Interpretation rule

No mechanism is declared causal from this campaign alone. A dominant phenotype selects the next matched intervention.

---

# 11. Mechanism-specific disconfirmation rules

The project explicitly wants the cheapest measurement that can kill a plausible story. These are the ones I would precommit.

## Offense / clearance story

**Prediction:** reducing enemy health or increasing player weapon output on the identical D5 state materially improves wave completion and prevents backlog growth.

**Disconfirmation:** substantial dose changes fail to move survival, time-to-death, or enemy backlog.

## Incoming-damage story

**Prediction:** reducing the D5 damage channel rescues the state without materially changing kill rate or enemy count.

**Disconfirmation:** damage-channel removal does not improve progression, or deaths remain dominated by enclosure/no-safe-heading states.

## Enemy-speed / movement-timing story

**Prediction:** resetting speed toward 1.0 increases feasible-heading availability, reduces wall-latch activation, or rescues the same build.

**Disconfirmation:** speed removal changes measured enemy velocity but not the failure trajectory.

## Confinement story

**Prediction:** a final-command-effective deconfinement intervention increases coverage and improves survival or progression.

**Disconfirmation:** coverage moves substantially while outcome does not, or the intervention merely increases exposure.

## Temporal-human-policy story

**Prediction:** recent history materially improves leak-free prediction of human macro actions in the relevant high-crowd disagreement states, and a temporally persistent proposal improves live fixtures.

**Disconfirmation:** temporal context adds no held-out value, or improved imitation still does not improve the real outcome.

## Shop-scoring story

**Prediction:** alternative weights flip real Danger 5 decisions often enough to create a build change near the save-edit rescue dose.

**Disconfirmation:** few decisions flip, or the cumulative build effect is far below the required dose.

## Perception story

**Prediction:** a material fraction of causal hazards is absent or incorrectly represented.

**Disconfirmation:** all causal hazards are represented with correct position, velocity, radius, and identity on independent D5 losses.

---

# 12. Final answers to the seven questions

## 1. What is the right first experiment?

Fix and verify Danger 5 selection, then run a frozen-policy 12-attempt target-characterisation campaign, extending to 20 only under a predeclared rule. Measure terminal progression, hazard class, clearance/backlog, build trajectory, local escape feasibility, and final-command arbitration. Save every reached wave. This is higher value than any further Danger 0 optimization.

## 2. Is Danger 5 reachable by the current broad policy class?

Possibly. The evidence does not prove a neural policy is required. It does show that continued desire-stage knob tuning is a poor bet. If movement is binding, preserve deterministic control but move toward a temporal hierarchical maneuver selector plus a minimal safety shield.

## 3. Where should effort go?

Do not choose in advance. Use Danger 5 data and same-state human handovers. The tentative prior is offense/tempo first, because enemy health scales and clearance is already a known hard-wave issue. Movement becomes first when a human rescues the exact D5 build or a safe heading exists and the agent fails to choose it. Shop scoring is gated by exact offline decision flips.

## 4. How should `enemy_scaling` be used?

First, on actual D5 saves as a channel-removal instrument. Second, as a separately calibrated three-channel pressure ladder for cheap screens. Select the dose using an incumbent-only calibration set and a fixed algorithm; evaluate candidates on fresh source fixtures. Never call the ladder a complete Danger 5 reproduction and never ship from it alone.

## 5. Is confinement worth chasing?

As a diagnostic, yes. As a direct objective, no. Run temporal-order analysis and one final command-effective deconfinement intervention. If it changes coverage without improving survival, close it as an intervention target.

## 6. Is there a learning approach worth retaining?

Yes: targeted temporal high-level imitation or a short-horizon action ranker trained from human corrections and safe macro-action probes. Keep a low-level safety shield. Do not repeat one-frame full-command cloning and do not run full model-free RL under the present serial, simulator-free apparatus.

## 7. What should be refused?

Refuse more Danger 0 desire-weight tuning without final-command proof; direct confinement optimization; another one-frame human clone; generic shop retuning without decision flips; a full world model; and ordinary online actor-critic RL under the current setup. Reopen a closed intervention class only when an actual Danger 5 mechanism makes a specific prediction.

---

# 13. Final strategic judgment

The project does not yet have a Danger 5 agent problem. It has a **target-identification problem**.

The fastest route forward is not more sophistication. It is to expose the shipped policy to the target, record where the target breaks it, and use the unusually strong save-edit and human-handover instruments to identify the modality before changing the policy.

The current apparatus is weak for long-horizon reinforcement learning but strong for something more disciplined:

- exact target readback;
- rich state capture;
- matched saved-state interventions;
- human-versus-agent same-state comparison;
- controller-independent difficulty channels;
- final-command instrumentation.

That is enough to answer the most important immediate question:

> **On actual Danger 5 states, is the agent losing because it cannot kill, cannot survive contact, cannot keep spacing against faster enemies, cannot handle the projectile channel, or chooses the wrong trajectory despite having a viable one?**

Until that question is answered, every new controller feature is another candidate for a precise null on the wrong game.
