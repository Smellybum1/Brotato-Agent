# External consultation — human versus agent movement, late-wave loot disengagement, and the next experiment

## Executive verdict

This is the strongest actionable movement finding the project has produced, but the current causal story is still one step too long.

The evidence strongly supports a **mechanism of late-wave under-collection**:

> under crowding, the density veto removes ordinary loot attraction; the separate loot-dash mechanism is usually suppressed or fails to arm; the resulting policy often commands movement away from nearby resources.

It does **not yet establish a mechanism of terminal wins**. In particular, the saved-state result contains a crucial temporal correction:

> The human's extra materials collected during wave 17 cannot have made the human's wave-17 build stronger, because shop and level-up decisions happen after the wave. The human survived wave 17 with the same entry build by moving differently.

That means the prior closure of wave 17 as “build-limited and not movement-actionable” is no longer defensible. A better description is:

> **Weak builds create high-pressure states, and the present movement policy appears to fail specifically in those states. Build strength and movement are interacting causes, not competing explanations.**

The human may have benefited from safer routing, maintaining circulation, following cleared-space “breadcrumbs,” collecting healing consumables, or some combination. Materials collected in the same wave are evidence that the route differed, but cannot be the immediate cause of that wave's survival.

My recommendations are:

1. **Reopen wave-17 movement.** Treat the human handover as strong, one-fixture, hypothesis-generating evidence that movement can rescue a build the agent usually loses.
2. **Do not tune the old dash again and do not add a blanket greed coefficient.** Replace the binary `loot attraction = 0` architecture with a constrained safe-resource selector: survival defines an admissible set; useful collection breaks ties inside that set.
3. **Make the first challenger risk-noninferior.** The hard fixture shows a possible free lunch—more collection and a much healthier HP trajectory. Do not encode deliberate HP spending in the first fix.
4. **Separate the fast and slow feedback loops experimentally.** Test direct same-wave movement effects separately from inter-wave economic effects.
5. **Replace `damage_taken` as the standing primary endpoint.** Keep it as gross-hit telemetry. Use terminal win for confirmatory run-to-terminal campaigns and a death-adjusted HP-deficit integral for fixed-wave mechanism screens. Rebuild the power table from scratch.
6. **Use the human data first for targeted disagreement analysis and DAgger-style corrections, not full-policy behaviour cloning.** A narrow learned override may become justified, but one human run and one source fixture are not yet enough support for an end-to-end student.

## What is established, what is strongly suggested, and what is not established

| Claim | Status | Reason |
|---|---|---|
| The handover genuinely gives movement control to the human | **Established** | Effect-based stationary and command/velocity controls pass |
| The agent and human choose very different actions on the same late/high-crowd states | **Established descriptively** | The two action vectors are logged on identical ticks |
| The agent's late-wave loot disengagement is intrinsic rather than unique to human-created states | **Established descriptively** | The same crowd-dependent pattern appears in five agent-driven runs |
| Density suppression can zero ordinary loot attraction | **Established in code** | It is an explicit controller operation |
| The current compensating dash is often inactive late | **Established marginally** | Dash-state telemetry shows low activation and frequent suppression/non-arming |
| The veto and dash jointly leave valuable, safely reachable loot unserved on the same ticks | **Strongly suggested, but one joint table is still missing** | The current evidence is largely marginal rather than a full joint contingency |
| Human movement can rescue the supplied hard wave-17 build | **Strong, exploratory, one-fixture evidence** | 5/5 human wave-17 survival versus 4/21 agent, with movement as the only controlled surface; endpoint was not predeclared |
| More same-wave material collection caused that wave-17 rescue | **Refuted by timing** | Materials cannot alter the build until after wave 17 |
| Collection contributed to a stronger build in the full human run | **Plausible, not established** | One run, no matched full-run counterfactual, and shop/offer RNG still operates |
| Fixing late collection will raise terminal win rate | **Not established** | The predeclared terminal endpoint failed, and the human still lost wave 20 |
| The human demonstrates a generally superior full movement policy | **Not established** | One operator, one full run, five continuations from one source state |

---

## 1. Is the diagnosis right?

### The narrow diagnosis is probably right

The following pieces line up unusually well:

- The controller explicitly zeroes ordinary loot attraction under density suppression.
- The replacement mechanism is not a continuous residual; it is a separately armed dash.
- Late-wave dash activation is rare, while `suppressed_survival`, `suppressed_finale`, and `not_armed_no_stall` occupy much of the state space.
- The agent's resource-directedness degrades monotonically with crowd count, both on human-created states and on states it creates itself.
- The late-wave angle distribution is strongly two-sided: near the resource or nearly opposite it. That is compatible with a binary arbitration rule rather than a smooth trade-off.

So I would accept this wording:

> **The current controller has a binary resource-attraction hole under pressure.**

I would not yet accept this stronger wording:

> **That hole is the principal cause of the remaining deaths, and making the dash fire more will fix them.**

### The missing joint contingency

The brief gives:

- crowd-conditioned action gaps;
- a reachable-looking subset;
- marginal dash-state frequencies;
- code showing ordinary attraction can be zeroed.

What it does not yet show in one table is the exact conjunction:

```text
density_veto_zeroed_loot = true
AND useful_resource_route_exists = true
AND dash_active = false
AND final_heading_moves_away = true
```

Produce that cross-tab separately for waves 15–19 and wave 20. For every tick in the conjunction, record:

```text
ordinary loot vector before suppression
density-veto result
dash state and dash vector
final controlling layer
final heading
resource value and type
short-horizon path-risk estimate
```

Then replay the same state through deterministic shadow variants:

```text
CURRENT
NO_DENSITY_ZERO
NO_STALL_REQUIREMENT
NO_HP_SUPPRESSION
NO_FINALE_SUPPRESSION
```

The useful question is not merely whether a line of code exists. It is:

> Which single component changes the **final** command on the target ticks, after every downstream override?

This is an offline, zero-gameplay identifiability test and should precede another implementation.

### Competing explanations not excluded

#### 1. Loot may be a safe-space marker rather than the objective

Materials appear where enemies died. A resource cluster may therefore be a breadcrumb trail through recently cleared space. The human may be following a stable circulation route that happens to collect materials, rather than accepting risk for economic reward.

This explanation fits the apparently paradoxical hard-state result:

- much more collection;
- much greater distance travelled;
- much higher minimum HP;
- same entry build.

It also explains why an economic trigger could be the wrong abstraction. The missing controller feature may be **route topology**—maintaining circulation through cleared space—not greed.

#### 2. Consumables may be the immediate mediator

Same-wave materials cannot improve offense, but healing consumables can improve survival immediately. The full-run healing result makes this a first-class candidate. Material-directedness may be correlated with travelling through mixed resource clusters that also contain consumables.

Add, by source and time:

```text
consumables visible
consumables picked
healing amount by source
route angle to nearest healing consumable
material-only pickups versus healing pickups
```

Do not combine materials and healing objects under one “loot” label in the next analysis.

#### 3. “Closer than the nearest enemy” is not a reachability proof

A material 170 units away and a nearest enemy 402 units away does not establish a safe route. It omits:

- other enemies intersecting the swept path;
- enemy relative velocities and time-to-contact;
- projectiles;
- walls, corners, and escape width;
- where the route leaves the player after pickup;
- whether the nearest material target changes before arrival.

Use a short-horizon swept-corridor test over the complete threat set. The relevant predicate is:

> A heading toward a resource cluster remains inside the near-best safety set over the next horizon.

#### 4. Nearest-material angle is an incomplete collection metric

The human may be targeting a cluster, a healing consumable, or a route through several pickups rather than the nearest entity. A nearest-target identity can also switch rapidly, manufacturing a two-mode angle distribution.

Add:

- signed radial velocity toward the selected resource cluster;
- predicted pickup value along the next 0.5–1.0 seconds of motion;
- target-identity persistence;
- value-weighted rather than entity-count-weighted routes.

### Verdict on Question 1

**Yes, the mechanism of under-collection is adequately supported to justify a narrowly targeted experiment. No, the mechanism of survival or winning is not yet identified.** Before coding, produce the joint contingency and final-command shadow ablation. Do not infer that the dash merely needs looser arming conditions.

---

## 2. Can the feedback loop be oriented?

The proposed loop actually contains two loops on different timescales.

### Fast loop: seconds

```text
crowding / bad position
→ damage
→ low HP
→ HP-gated suppression
→ no resource/recovery route or worse circulation
→ more damage
```

The human fixture supports this loop more strongly than the economic loop because the human's movement changed the HP trajectory **before any new build decision could occur**.

### Slow loop: waves

```text
under-collection
→ less useful value before a later shop
→ weaker future build
→ slower clearance
→ more crowding and damage
→ stronger suppression
→ further under-collection
```

The full human trajectory and late bag-redemption deficit are compatible with this loop, but do not orient it causally.

### What the existing data can orient

The code itself establishes one arrow:

```text
low HP → suppressed_survival
```

The same-state handover strongly suggests another on this fixture:

```text
movement policy → HP trajectory
```

It does **not** identify:

```text
material collection → same-wave HP
```

because that route is temporally impossible except through correlated healing pickups or spatial routing.

An observational event study can still be useful. Align each agent trial on:

1. first density-veto activation;
2. first `suppressed_survival` activation;
3. first sustained heading-away episode;
4. first bag-redemption stall;
5. first major HP drop.

Plot pre/post changes in collection, consumable pickup, local crowd geometry, and HP deficit. This reveals sequence, but it will not settle causality because the trigger states are endogenous.

### The causal intervention that orients the fast loop

Randomize the **controller's HP input for the suppression decision only**, while leaving physical HP unchanged.

At predeclared eligible blocks:

- **Control:** the loot arbitration sees actual HP.
- **Treatment:** only the `suppressed_survival` gate sees a shadow HP just above its threshold; all other controller and game logic sees actual HP.

Run the treatment for a short fixed block, followed by a washout. This isolates:

```text
HP gate → movement → short-horizon pickup / healing / HP trajectory
```

Recommended proximal outcomes over a fixed horizon:

- useful material value picked;
- healing consumable value picked;
- survival-adjusted HP-deficit area;
- actual damage events;
- minimum swept-path clearance;
- whether the action leaves an escape route.

Randomize at block level and analyse with the run/source state as a cluster. Do not treat 20 Hz ticks as independent.

### The causal intervention that orients the slow loop

Use a diagnostic **economic-rescue arm** with incumbent movement:

> At wave end, before the shop, credit the material value that remained stranded or missed, without changing movement during the wave.

This is not a shippable policy. It is an upper-bound instrument. It asks:

> If the agent had received the economic value without taking any collection route, would later build strength and terminal continuation improve?

If economic rescue is null, the slow-loop story has little actionable headroom and the human advantage is more likely direct movement/recovery. If it improves later outcomes, the economic pathway is real even if the first movement implementation fails.

### Verdict on Question 2

The current evidence orients **movement upstream of HP on the hard fixture** and confirms **HP upstream of suppression in code**. It does not orient collection as the mediator. Use a shadow-HP gate randomization for the fast loop and a movement-free economic rescue for the slow loop.

---

## 3. Is the causal chain to winning established?

No. Several links are measured, but they belong to different runs and different timescales.

### What is established or strongly supported

1. **The agent under-directs movement toward resources under pressure.** This is descriptive but well replicated across human-created and agent-created states.
2. **The agent has a late-wave bag-redemption problem.** This is real among runs reaching those waves.
3. **Human movement can rescue the supplied wave-17 source state.** It is a direct movement-only intervention on one build, although the endpoint was exploratory and the source-state population size is one.
4. **A large clearance improvement can rescue one doomed wave-17 build.** The enemy-health dose experiment establishes this for that fixture.
5. **The human's full-run build was unusually strong by wave 17.** This is descriptive evidence from one trajectory.

### What is not established

1. **The human survived the hard wave because of materials collected during that wave.** This is temporally impossible.
2. **The human's stronger full-run build was caused primarily by better collection.** Plausible, but there is only one full run and no matched full-run counterfactual.
3. **The current density-veto defect causes a meaningful fraction of the 27.8% full-run loss rate.** Prevalence of the behaviour is measured; its outcome effect is not.
4. **A collection fix will improve wave 20.** The human lost wave 20, and offense has not separated wave-20 outcomes.
5. **The 1.67× offense ratio is a threshold or causal dose.** It is one observation relative to medians from another population.

### The earlier wave-17 closure must be revised

The enemy-health result and the human result are not contradictory.

- The enemy-health intervention shows that a sufficiently stronger effective build can rescue the fixture.
- The human intervention shows that a different movement policy can also rescue the fixture without changing the entry build.

The correct model is an interaction:

```text
weak build
→ higher crowd pressure
→ enters the controller's failure stratum
→ movement/arbitration defect becomes consequential
```

A build can be weak enough to expose a movement defect without making movement irrelevant.

### What the human's wave-20 loss means

It does not refute the wave-17 finding. It sets a boundary:

- wave-17 movement/economy may be valuable;
- wave-20 remains a different boss-survival problem;
- terminal-win improvement must be measured rather than inferred from a stronger mid-game build.

### Verdict on Question 3

The causal chain currently reaches:

> **current movement can be beaten on one hard wave-17 state, and the defeated policy also under-collects in the relevant pressure stratum.**

It does not yet reach:

> **the density-veto collection defect is a demonstrated terminal-win lever.**

---

## 4. How should the fix be designed?

### Do not add another dash trigger

The existing architecture is the problem shape:

```text
ordinary attraction
→ binary zero under density
→ separate compensator
→ separate stall condition
→ separate HP suppression
→ separate finale suppression
```

Another threshold inside that stack is likely to create another locally sensible rule whose final effect is either inert or discontinuous.

### Do not start with an economic gate

The same-wave human rescue occurred before economic value could improve the build. That makes a purely economic trigger an unsafe abstraction. The route may be valuable because it:

- maintains circulation;
- enters recently cleared space;
- reaches healing consumables;
- avoids a trap;
- collects materials as a by-product.

Economic value should be a tie-breaker inside a safe movement set, not the sole arming condition.

### Recommended architecture: constrained safe-resource selection

Keep the incumbent command as a candidate, then evaluate a small candidate set:

```text
incumbent final heading
headings toward the best material clusters
headings toward visible healing consumables
one or more open-space / escape headings
```

For each candidate, estimate over a short horizon:

```text
minimum enemy time-to-contact
projectile swept-path clearance
predicted contact count
wall/corner trap risk
escape width after the route
resource value collected along the path
immediate healing available along the path
```

Then use a lexicographic rule:

1. Reject any candidate that violates a hard safety constraint.
2. Form a near-best safety set—candidates no worse than the incumbent by more than a frozen tolerance.
3. Within that set, select the route with the greatest useful resource/recovery value.
4. Commit briefly with hysteresis; abort immediately if the safety constraint changes.

The first version should use a tolerance of effectively zero: **only take collection routes predicted to be no less safe than the incumbent**. This targets the free-lunch cases implied by the hard fixture.

### Replace binary zeroing with a continuous or set-based decision

The important change is not “increase loot weight.” It is:

> Density may narrow the admissible resource routes, but it must not erase the resource objective when a safe route remains.

This can be implemented either as candidate selection or as a continuous clamp that preserves a minimum resource component. Candidate selection is easier to audit because every decision has an explicit reason:

```text
CURRENT_HEADING_SAFEST
RESOURCE_ROUTE_DOMINATES
HEAL_ROUTE_DOMINATES
NO_SAFE_RESOURCE_ROUTE
WAVE20_MATERIAL_VALUE_ZERO
```

### Scope the first challenger narrowly

The intervention should initially be inert outside the discovered failure stratum:

- waves 15–19;
- density suppression active;
- a resource route passes the safety test;
- no change in the 0–4-enemy stratum where the current agent is already more resource-directed than the human;
- no material-seeking on wave 20.

Wave 20 requires a split:

- ordinary materials have no useful post-wave economic value;
- healing consumables can still have immediate survival value.

Do not treat `suppressed_finale` as evidence of a material-collection defect without separating wave 20 from waves 15–19.

### Use useful-deadline value, not `bag > 0`

A better economic quantity is:

```text
useful_value_before_next_shop =
    ordinary ground value likely collectible now
  + bag value likely redeemable before the next useful shop
  + immediate healing value
```

The urgency should rise as the last useful shop approaches. Value collected or redeemed during wave 20 is mechanically real but economically too late for another shop.

### Required implementation proof before gameplay

Before launching a candidate, replay archived states and require:

- final commands actually change in the target stratum;
- no later layer cancels the change;
- action leakage outside the target stratum is near zero;
- signed progress toward useful resource routes increases;
- the frozen risk model does not worsen;
- low-crowd and wave-20-material fixtures remain unchanged.

### Verdict on Question 4

**Replace the veto-plus-dash patchwork with a safety-constrained resource tie-break. Do not loosen the old stall gate and do not use `bag > 0` as the trigger.** The first version should seek safe collection, not deliberate risk-for-reward.

---

## 5. What is the right experiment?

Do not jump directly to a 64-trial terminal campaign. First establish which pathway is real. The best design is staged.

### Stage 0 — offline final-command identifiability

No gameplay.

Run the shadow ablations described in Question 1 across all human and agent captures. Freeze:

- target-state definition;
- candidate implementation;
- activation and leakage measures;
- safety-model outputs.

Do not proceed if the challenger is inert or if its changes are mostly outside the stated target.

### Stage 1 — short-horizon randomized mechanism screen

At eligible late-wave blocks, randomize for a short fixed interval between:

- incumbent command;
- constrained safe-resource command.

Use washout intervals and prohibit overlapping treatment blocks.

Predeclare two questions:

1. **Efficacy:** does the challenger increase useful pickup/recovery along the next short horizon?
2. **Safety:** is survival-adjusted HP-deficit burden non-inferior, with no increase in imminent collisions or deaths?

Analyse blocks with cluster-aware randomization or bootstrap; the inferential units remain runs/source states, not ticks.

This stage exploits the 23% addressable set rather than diluting it across entire continuations. It cannot establish terminal value and must not be used to ship.

### Stage 2 — three-arm diagnostic landmark screen

Use as many **independent wave-16 source states** as possible. Prefer more distinct states over many repetitions of one state. If the library is limited, use two continuations per arm and still weight source states equally.

Recommended arms:

| Arm | Intervention | What it identifies |
|---|---|---|
| `C` | Current policy | Baseline |
| `M` | Constrained safe-resource movement | Deployable combined movement + natural collection effect |
| `E` | Current movement plus end-of-wave economic rescue | Upper bound on the slow economic pathway without changing movement |

The `E` arm should credit only well-defined stranded/missed value before the next shop. It is diagnostic, not shippable.

A practical screen would use 24–32 unique source states:

- 72–96 total continuations across three arms;
- approximately 5.2–6.9 machine hours at 4.3 minutes each.

Predeclared contrasts:

#### `M` versus `C`, wave-17 survival and fixed-wave healthy-HP burden

Any difference occurs before newly collected materials can change the build. This tests the direct movement/recovery pathway.

#### `E` versus `C`, later build trajectory and terminal win

This tests whether missed economics have enough headroom to matter even with unchanged movement.

#### `M` versus `C`, terminal win from the landmark

This is the deployable total effect, but the diagnostic screen is not the final promotion gate.

Interpretation matrix:

| Result | Interpretation |
|---|---|
| `M` improves wave-17 survival, `E` is null | Primarily a route/dodging/recovery defect, not an economic-build defect |
| `E` improves terminal continuation, `M` does not | Economic headroom exists; the proposed movement implementation fails to capture it |
| Both improve | Fast and slow loops both matter |
| `M` collects more but neither outcome improves | Under-collection is real but not a product lever at this scale |
| Neither changes mechanism or outcome | Stop this line |

### Stage 3 — fresh two-arm confirmation

Only if Stage 2 gives a predeclared go result, compare `M` versus `C` on a **fresh source-state sample**.

Primary endpoint:

> terminal win from the validated wave-16 landmark.

Key secondary:

> a hierarchical run outcome: win first; among losses, later terminal progress; then healthier fixed-horizon HP burden.

Analysis:

- source-state-stratified paired estimate;
- equal weight per source state;
- cluster bootstrap or a pre-specified paired binary analysis;
- intention-to-treat by assigned policy;
- no conditioning the primary result on whether the intervention happened to activate after randomization.

### The standing 32/64 rule cannot be carried over automatically

That practice was calibrated around `damage_taken`. Once that endpoint is retired, its sizing table is retired too.

A binary landmark effect near 8–10 percentage points is not reliably resolved by 32 or 64 unpaired observations. Pairing may help substantially, but the gain depends on source-state correlation and the number of discordant pairs. Use Stage 2 to estimate:

```text
between-source variance
within-source continuation variance
paired outcome correlation
discordant-pair rate
```

Then simulate the exact proposed confirmation design. If 64 fresh source-state pairs cannot meet the frozen operating characteristics, do not call 64 “confirmation” merely because it is customary.

### Suggested decision rule structure

Freeze a minimum worthwhile landmark effect before Stage 2—for example, the effect that would plausibly move the product from roughly 0.72 toward 0.80 after accounting for prevalence. Then define:

- **GO to confirmation:** screen estimate exceeds the minimum worthwhile effect, mechanism gates pass, and the HP-burden safety endpoint is non-inferior.
- **STOP:** terminal estimate is non-positive, the safety endpoint worsens materially, or the policy is mostly inert.
- **INCONCLUSIVE:** mechanism improves but terminal estimate is too imprecise. Do not relabel this as success.
- **ADOPT:** fresh confirmation supports a positive terminal effect of practical size and no hard safety regression.

### Verdict on Question 5

Use a staged mechanism → pathway → terminal design. The most informative use of roughly eight machine hours is not a single two-arm campaign; it is a three-arm landmark diagnostic that separates direct movement from economic rescue, followed only then by a powered fresh confirmation.

---

## 6. Best use of the paired human/action data

### The null history does not disqualify human imitation

Every prior learned policy imitated the teacher. The new demonstrator is the first actor with direct evidence of outperforming the teacher on an identical source state. That materially changes the prior.

However, it does not make ordinary full-policy behaviour cloning the best next step. The prior student result still teaches two important lessons:

1. lower mean angular imitation error is not the live objective;
2. a smoother policy can remove protective evasiveness and perform worse.

### Recommended sequence: `(a) + targeted (c)`, with narrow `(b)` later

#### First: disagreement mining

Use the current paired data to learn the **support of the defect**:

- density veto state;
- local threat geometry;
- HP and recovery availability;
- material and consumable cluster geometry;
- wall/edge position;
- recent movement history;
- human versus agent candidate-heading rank.

Fit interpretable diagnostics first—a small tree, monotonic model, or rule-list—not to ship automatically, but to discover whether the human override is explained by a compact state interaction.

Split and weight by source state or contiguous decision segment. A random tick split would leak almost identical adjacent states into train and test.

#### Second: DAgger-style targeted correction

Let the agent drive normally. In predeclared failure strata—high crowd, density veto active, valuable safe resource route, or high model uncertainty—the human takes over for a short segment. This gives labels on the states the evolving policy actually visits.

Prioritize **source-state diversity**, not raw tick count. Twenty independent late-wave states are more valuable than tens of thousands of adjacent ticks from one full run.

#### Third: learn a narrow residual or candidate-ranking policy

Do not initially clone the entire 2D movement surface. Learn one of:

- whether the human would override the incumbent;
- which candidate heading the human prefers within the safe set;
- a bounded residual used only in the target stratum.

Outside demonstrated support, fall back to the deterministic incumbent.

A preference/ranking target is preferable to raw angle MSE because multiple headings can be equally safe and useful. The objective should not punish the model for choosing a different but equivalent evasive route.

### Before learning, audit state sufficiency

The human may be using information absent from the learned observation:

- resource-cluster value;
- healing-consumable locations;
- relative enemy velocities;
- projected corridor safety;
- intended loop direction or recent history.

If those cues are missing, collecting more labels will not fix the model. The demonstrator's advantage may require a richer or recurrent state.

### Does full human BC deserve more credit?

**More credit, yes; priority, no.** It becomes reasonable after:

- human advantage replicates across multiple independent source states;
- the state representation can express the relevant cues;
- the target is a narrow correction or candidate ranking;
- evaluation is based on landmark outcome rather than imitation error.

Five to seven operator hours would be defensible for a diverse targeted correction set. It would be poorly spent producing 60–80 repetitions concentrated on one fixture or training another end-to-end angular imitator.

### Verdict on Question 6

Use the paired data to identify and learn a **failure-stratum override**, preferably through DAgger-style targeted collection. Do not make full-policy human BC the immediate next experiment.

---

## 7. What is over-claimed or mis-analysed?

### 1. The crowd-matched control does not rule out endogeneity

It rules out one coarse explanation: the gap is not merely an artefact of comparing low-enemy human ticks with high-enemy agent ticks.

`enemies_alive` is still too coarse. Match or model at least:

- local enemy density at several radii;
- nearest-threat distance and relative velocity;
- time-to-contact distribution;
- projectile risk;
- wall/corner geometry;
- time within wave;
- HP and recent damage;
- resource cluster distance/value;
- visible healing;
- route escape width.

The same-tick human-versus-agent action comparison itself is state-paired and therefore strong descriptively. What remains endogenous is the interpretation of why the action is better and the outcome it would have produced under the unapplied agent command.

### 2. The effective sample sizes are runs and source states, not ticks

The 17,828 and 95,630 tick counts demonstrate measurement precision within trajectories. They do not provide thousands of independent policy comparisons.

- human full-run generalisation: effectively one trajectory;
- agent-own-state replication: five runs;
- hard fixture generalisation: one source state with multiple fresh-RNG continuations.

Any interval or hypothesis test must cluster accordingly.

### 3. “No enemy between the agent and the loot” is not supported by the stated distances

The data support:

> the selected material was usually closer than the closest enemy.

They do not support a collision-free corridor. Replace the wording until a swept-path check exists.

### 4. “Collected five times more while taking a quarter of the damage” is not supported by the table shown

The table reports minimum HP ratio, not cumulative damage. A much higher minimum HP is strong evidence of a healthier trajectory, but it is not the same statistic as one-quarter of the damage. Keep the stronger claim only if separate damage-event totals for those trials exist and are reported.

### 5. The bimodality corroborates but does not prove the binary veto mechanism

Nearest-target switching, wave mixtures, and different route phases can also create two modes. Condition the distribution on:

```text
density veto active/inactive
dash active/inactive
same resource target identity
```

and show the shadow ablation changes the final command.

### 6. Wave-20 bag drainage should not be interpreted as economic success

A bag redeemed during wave 20 is too late for another shop. Separate:

- mechanical redemption;
- redemption before a useful shop;
- immediate healing/consumable value.

Likewise, `suppressed_finale` may be correct for ordinary material collection even if it is wrong for recovery consumables.

### 7. The human build comparison is one trajectory, not a causal mediator analysis

`58.78` versus historical medians is useful for generating an economic hypothesis. It does not prove that collection caused the build, that the metric is the relevant dose, or that the same result would recur.

### 8. The human's gross-damage counter-result is neutralized, not replaced by proof of superiority

The new HP and healing table shows that gross damage was a poor argument against the policy. With one human run and six agent runs, it does not establish that human net risk is generally lower. “Comparable on this trajectory and reference sample” is the defensible wording.

### 9. Human trial order and learning should be recorded

Five trials by one operator may include practice or adaptation. That does not make the achieved policy irrelevant—the project wants a strong demonstrator—but it affects claims about an average human effect and the exact p-value interpretation.

### Verdict on Question 7

The core finding survives. The strongest over-claims are the reachability proof, the quarter-damage wording, treating ticks as independent evidence, and chaining same-wave collection into same-wave build strength.

---

## 8. Should `damage_taken` be replaced?

**Yes, as the standing primary endpoint.** It should remain in telemetry as a mechanistic measure of gross hit exposure.

`damage_taken` answers:

> How much incoming damage landed before healing?

It does not answer:

> How much survival risk did the policy experience after accounting for recovery?

A policy that deliberately accepts recoverable damage can be better while scoring worse on gross damage. Conversely, two policies with equal gross damage can have very different low-HP exposure if one heals promptly and the other does not.

### Confirmatory primary for run-to-terminal campaigns

Use:

> **terminal win from the validated landmark.**

It is the actual product objective and is not mechanically altered by healing accounting.

### Continuous mechanism endpoint for a fixed wave

Use a survival-adjusted HP-deficit integral over a fixed horizon:

```text
h(t) = HP(t) / max_HP(t), while alive
h(t) = 0 after death for the rest of the fixed horizon

HP_deficit_AUC = (1 / T) * integral[0..T] (1 - h(t)) dt
```

Lower is better. Assigning zero HP after death prevents an early death from looking artificially good because recording stopped.

For a completed fixed-duration wave, this captures:

- depth of HP loss;
- duration of exposure;
- healing and recovery;
- death.

Use it primarily where build/max-HP is fixed during the interval. Across multiple shops, max-HP changes can complicate interpretation, so terminal win remains primary for the full landmark continuation.

### Hierarchical secondary for run-to-terminal campaigns

Use a hierarchy rather than forcing every run into one arbitrary scalar:

1. win beats loss;
2. among losses, later terminal wave/fraction of wave beats earlier death;
3. if progress ties, lower fixed-horizon HP-deficit burden wins.

This extracts information from losses while preserving the product ordering.

### Why the other candidates are weaker as sole primaries

#### Time below an HP threshold

Useful diagnostically, but threshold-dependent and coarse. Report several bands, and assign death as below threshold for the remaining horizon.

#### Net HP lost

Poor. End HP can be full after a dangerous trajectory, and early death creates censoring. It ignores duration and recovery timing.

#### Minimum HP

Useful tail-risk telemetry, but unstable and dominated by a single tick.

### Report the components, not only the composite

Every campaign affecting movement or collection should report:

```text
gross damage taken
healing by source
HP-deficit AUC
time below 70/50/30%
minimum HP
terminal progress
terminal win
materials useful before each shop
consumables picked
```

### The power/sizing table must be rebuilt

The existing statements—32 detects 19 damage, 64 detects 13, 128 detects 9—apply only to the old endpoint and its old variance structure. They do not transfer to HP-deficit AUC or terminal win.

Recompute the new endpoints on all archived paired campaigns, then use source-state-clustered resampling to estimate:

- paired variance;
- source-state heterogeneity;
- discordant win rate;
- power at each proposed number of source states and continuations.

### What happens to past conclusions?

- Results based on terminal survival/win remain valid on that endpoint.
- The perception fix remains compelling because it changed survival and had a structural readback.
- Any conclusion resting mainly on `damage_taken` should be reanalysed if the treatment could alter healing, consumable pickup, lifesteal, or willingness to spend HP.
- A damage null may still be informative for a pure avoidance change if healing was demonstrably balanced, but this must be shown rather than assumed.
- Do not automatically reopen every historical null. Triage by whether the decision depended on gross damage and whether treatment shifted recovery.

### Verdict on Question 8

Make terminal win the confirmatory primary, use death-adjusted HP-deficit AUC for fixed-wave mechanism screens, retain gross damage as a component, and rebuild all sizing from source-state-clustered data.

---

## 9. Is HP a spendable resource?

### The principle is sound

In a game with visible healing consumables, regeneration, and lifesteal, current HP is not the same as terminal survival margin. A competent policy can rationally exchange some temporary HP for:

- immediate healing access;
- a safer route after the pickup;
- useful materials before a deadline;
- a stronger future build.

The full human run is consistent with this idea. It is not yet enough evidence to make deliberate HP spending the first intervention.

### First exhaust risk-free or risk-noninferior collection

The hard fixture did not show a necessary risk-for-reward trade. The human collected far more and maintained a much healthier minimum-HP trajectory. Therefore the first challenger should ask:

> Can the agent take resource routes that are at least as safe as its incumbent route?

Only after that works should the project pay for an explicit HP-spending experiment.

### A conservative recovery-backed budget

For a candidate action over horizon `H`, estimate:

```text
upper-bound damage risk D(a, H)
lower-bound recoverable HP R(a, H)
hard survival reserve S(state)
recent unrepaid HP debt B(state)
```

Permit intentional risk only when:

```text
current_HP - D(a, H) + R(a, H) - B(state) >= S(state)
```

Use conservative bounds:

- `D` should be an upper quantile or worst credible short-horizon damage, not a mean;
- `R` should include visible, reachable healing and deterministic recovery only;
- do not credit hypothetical future random consumable drops;
- avoid double-counting the same healing source;
- reserve enough HP for a plausible large hit plus model error.

### Separate three categories

#### Hard reserve

Not spendable. It protects against an imminent hit, prediction error, and route failure.

#### Recovery-backed credit

Potentially spendable. It is backed by a visible consumable, deterministic regen, or sufficiently reliable lifesteal within the route horizon.

#### HP debt

Once HP has been spent, block further risk-taking until the predicted recovery is realised or the debt decays under a strict rule. This prevents a series of individually small “safe” gambles from accumulating into the old reckless behaviour.

### Low HP should not mean “ignore recovery”

The current binary `suppressed_survival` conflates two very different targets:

- ordinary materials with delayed economic value;
- healing resources with immediate survival value.

At low HP:

- material-seeking should become more conservative;
- reachable healing should become more attractive;
- no route may breach the hard reserve;
- if no credible recovery is visible, the incumbent survival policy remains authoritative.

### Wave-dependent value

- Waves 15–19: material value rises as the final useful shop approaches.
- Wave 20: ordinary material value is zero for the run objective; healing value remains positive.

### How to qualify an HP-spending policy

Before live outcome testing, calibrate predicted versus realised:

```text
damage over the horizon
healing over the horizon
minimum clearance
HP debt repayment
route completion
```

Then run a micro-randomized eligible-block experiment with a strict safety non-inferiority rule. A terminal campaign is justified only after the local risk model is calibrated.

### Verdict on Question 9

Treating HP as a recoverable budget is a sound later policy principle. It should be encoded as **recovery-backed, debt-limited risk**, not as a lower HP threshold or a blanket greed override. The first collection fix should remain risk-noninferior.

---

## Recommended execution order

### 1. Correct the project record now

Record these revisions before implementation:

- wave 17 is no longer closed as non-movement-actionable;
- the human hard-state rescue is movement evidence, not same-wave economic evidence;
- the density-veto diagnosis concerns under-collection, not yet terminal value;
- `damage_taken` is no longer a valid general primary risk endpoint.

### 2. Recompute endpoints from existing data

Without new gameplay:

- HP-deficit AUC;
- threshold exposures with absorbing death;
- healing by source;
- consumable pickups;
- useful-before-shop material value;
- joint veto/dash/reachability contingency.

Reanalyse any live decision that depended materially on gross damage.

### 3. Build the shadow ablation and safe-resource candidate

Do not deploy until final-command changes, target-stratum activation, and outside-stratum inertia are demonstrated offline.

### 4. Run the short-horizon mechanism screen

Establish that the candidate actually collects more and reaches more recovery without worsening immediate survival burden.

### 5. Run the three-arm landmark diagnostic

`C` current, `M` movement challenger, `E` economic rescue. This is the cleanest way to orient direct movement versus slow economics with the available apparatus.

### 6. Re-size and run a fresh two-arm terminal confirmation

Use the diagnostic campaign's source-state variance and discordance. Do not inherit the old 32/64 damage table.

### 7. Collect targeted human corrections only after the mechanism screen

Prioritize independent source states and high-disagreement failure strata. Train a narrow override or candidate ranker, not another full angular imitator.

### 8. Test explicit HP spending only after risk-noninferior collection is exhausted

The current evidence does not require the first fix to accept more risk.

---

## What I would explicitly decline to do

- I would not globally increase loot attraction.
- I would not loosen `not_armed_no_stall` and call that the fix.
- I would not disable `suppressed_survival` everywhere.
- I would not use `bag > 0` as an activation rule.
- I would not seek ordinary materials on wave 20.
- I would not train a full human behaviour-cloning policy from one full run and one fixture.
- I would not use tick count as the inferential sample size.
- I would not reuse the existing `damage_taken` power table.
- I would not claim the human result establishes a terminal-win improvement.

## Final decision

Proceed, but with a narrower claim and a different experiment.

The project has found a real controller pathology: **under pressure, resource attraction disappears discontinuously, and the compensator often does not replace it.** The human handover also shows that at least one supposedly build-doomed wave-17 state is movement-rescuable.

The next step is not “copy the human's aggression” and not “make the loot dash fire more.” It is:

> **replace binary disengagement with safety-constrained resource routing; prove the direct movement effect and the economic effect separately; then confirm terminal value on fresh source states.**

That path directly addresses the new evidence while protecting the project from making the next one-step-too-far conclusion.
