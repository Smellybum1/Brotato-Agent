# Pre-registration — first Danger 5 characterisation campaign

**Written 2026-07-30, before any Danger 5 terminal outcome was known.**

**Disclosure:** one Danger 5 run (`run_1785372250_76725`, mod `0.2.58`) was in flight while this was
written, and I had observed it alive at wave 8. I had NOT seen its terminal wave, its result, or any
outcome statistic. **That run is EXCLUDED from this campaign** — it ran before the difficulty-readback
latch fix was deployed, so its summary cannot self-certify its difficulty. It is a technical
observation, not attempt #1.

Adopted from the external consultation (`pro_answer_20260730_danger5.md`, adoption record
`pro_review_adoption_20260730.md`).

---

## 1. Objective

**Characterise the shipped policy's actual Danger 5 failure distribution, and build a library of
independent Danger 5 saved states.**

This is **not** a test of a treatment. No mechanism is declared causal from this campaign. Its output
is a failure phenotype distribution and a set of fixtures for cheap follow-up experiments.

**A campaign with zero victories is not a failed campaign.** The terminal-wave distribution and the
failure-channel breakdown are the deliverables.

## 2. Why this runs before any further optimisation

Every prior result on this project was measured at **Danger 0**, and Danger 5 raises enemy damage,
health, speed and projectile pressure simultaneously. A clean Danger 0 null does not transfer, and a
plausible Danger 0 mechanism does not automatically become the Danger 5 mechanism. Continuing to tune
against Danger 0 risks another precise answer to the wrong question.

## 2b. AMENDMENT 2026-07-30 — version pin moved to 0.2.61, sample restarted at n=0

**Recorded BEFORE any 0.2.61 attempt was collected.** Amending a pre-registration after seeing data
is optional stopping; this amendment is dated ahead of collection deliberately, and the decision rule
in §5 is untouched.

What happened: the first 12-attempt campaign reached **9 valid attempts** and then halted twice on
`error {'kind': 'manual_override'}` — a movement keystroke, because the operator was using the
machine and Steam's launch had given Brotato focus. The movement E-stop
(`player_movement_behavior.gd`) fires on ANY input > 0.05 and movement binds Q/A/W/Z/S/D plus the
arrows, so ordinary typing ends a run. Two attempts were destroyed that way.

The fix — a `movement_estop_enabled` gate, default TRUE so nothing existing changes — required a
deploy, which moved the installed build to **0.2.61-wp2-capture**. That makes the remaining 3
attempts a different build from the first 9.

**Decision: do NOT top up. Collect a fresh 12 on 0.2.61.** Topping up across two build strings is
exactly what §4's `mod_version` criterion exists to prevent, and the campaign that lost 87% of its
trials to a mid-campaign version bump is the precedent. Cost of restarting is ~2 h of machine time,
which is cheap against a build-mixed baseline.

**The 9 attempts on 0.2.60 are RETAINED and reported as a separate era-matched sample**, not
discarded and not pooled. Their terminal waves were `[7,9,10,10,11,12,14,14,15]` (median 11,
mean 11.33, sd 2.65). They additionally serve as a free cross-build consistency check on 0.2.61.

Note on inertness: with `movement_estop_enabled` true the code path is byte-identical to 0.2.60, so
0.2.61 is expected to be behaviourally identical for movement. **That expectation is NOT a licence to
pool** — the whole point of a version pin is that it does not depend on my judgement of which changes
were harmless.

## 3. Frozen for the campaign's duration

```
mod version            0.2.61-wp2-capture (installed == repo; NO deploy mid-campaign)
movement_estop_enabled false   (unattended campaign; Ctrl+Shift+Q still stops the agent)
policy version         teacher_v1-0.1.129-gun-wp1
character              character_well_rounded
starting weapons       weapon_smg, weapon_stick
danger                 5
time_scale             1.0
student_enabled        false   (shipped hand-written controller only)
finale_pivot_projectiles  true (the shipped default)
all dev knobs          inert defaults
telemetry schema       unchanged
```

**No identity-constant edits and no deploys while this campaign runs** — the installed build and the
repo's identity constants must agree for the whole campaign, and a repo-only edit to `MOD_VERSION`
breaks the harness's identity gate just as effectively as a deploy.

## 4. Technical validity — evaluated before any outcome

A run counts as a valid **gameplay attempt** only if all of these hold:

```
requested_danger == 5
observed_danger  == 5      (latched from RunData on the FIRST COMBAT TICK)
danger_ok        == true
mod_version      == 0.2.61-wp2-capture   (amended 2026-07-30, see §2b)
policy_version   == teacher_v1-0.1.129-gun-wp1
mod_ready sentinel observed for this build
capture stream structurally complete (parses to EOF)
```

**`observed_danger` of −1 means "never read" and is a technical failure, NOT Danger 0.**

**A technical failure stays in the append-only attempt ledger and is reported separately. It is never
excluded on the basis of its gameplay outcome, and never silently retried.** Every guard above is
computed from arming/identity data, not from how the run turned out, so none of them can select on
the outcome.

Cross-check available and to be reported: `run_v3_0.json → current_run_state.current_difficulty` is
an independent source for the difficulty and disagreements with the mod's own readback must be
reported, not reconciled silently. (An earlier readback taken at run-start produced a **false**
mismatch; that is why the latch moved to the first combat tick.)

## 5. Sample rule — fixed now

```
minimum: 12 valid gameplay attempts
maximum: 20
```

**Continue past 12 only if, after 12 valid attempts, ANY of:**
- no two adjacent waves contain ≥75% of the losses;
- no single failure phenotype accounts for ≥2/3 of losses;
- fewer than 4 independent usable saves exist in the dominant failure band;
- the result is too diffuse to select the next diagnostic.

Otherwise **stop at 12.** The rule exists so I cannot stop merely because the first 12 tell an
attractive story, nor keep going until they do.

Cost: ~19 min per full run at 1.0x, so 12 attempts ≈ 3.8 h and 20 ≈ 6.3 h **upper bound**. If Danger 5
kills the agent early, attempts are cheaper and the real cost is lower.

**Archive a complete save at the entry to every reached wave** — this is the main durable asset of the
campaign and costs nothing extra.

## 6. Primary report

```
victories / valid attempts
terminal-wave distribution
time-within-terminal-wave distribution
```

## 7. Mechanistic report, per loss

**Failure channel — MULTI-LABEL.** Do not force one mutually exclusive story when several channels
contribute.

```
melee body | moving projectile | stationary projectile | other visible hazard
| unexplained / absent from the observation
```

Attribution uses the **HP-drop diff**, not `player_damage` events (those lag the true damage tick by
one capture interval and have manufactured a false residual before). **The causal lag must be
re-derived per context and never inherited** — measured previously as lag −1 for wave-20 projectiles
(18.7 u) but lag 0 for wave-17 melee bodies (0.9 u), because projectiles despawn on impact while a
melee body is still touching.

**Pressure and clearance**, per wave and over the 10 s before death:

```
enemies alive | total enemy HP alive | spawn rate | kill rate
effective damage output | fraction of ticks with a valid target
player HP trajectory | damaging-contact count
```

The distinction to resolve:
- **clearance failure** — backlog grows because the build cannot service the spawn stream;
- **survival failure** — backlog is manageable but avoidable hits are taken;
- **no-local-solution failure** — death in a state with no feasible short-horizon heading.

**Controller state:**

```
safety-tail activation | wall-recovery activation
angle(desire, final command) | which layer owned the command
cells holding 50% of the wave | distance to walls | heading reversals
```

### 7b. COLLECTION / ECONOMY — a named phenotype, on operator domain knowledge

**Operator, 2026-07-30:** *"one thing to note about danger 5 from what I remember from a long time ago
when I played it, you have to pick up as much currency as possible to be successful in the later
waves."*

This is recorded as a **first-class phenotype to measure, not an assumption to act on**. The last time
the operator described something they had seen directly (the agent bounding itself into a corner), the
metric built to show it out-performed every statistic already on hand.

**Why it is credible here and why the existing closure does not cover it.** The whole
collection/economy line was closed as null — but **entirely at Danger 0**. Danger 5 scales enemy
health, so clearance requires more damage, which requires more materials. A collection deficit that is
harmless when enemies die easily can be binding when they do not. "Danger 0 shop and economy
interventions were null" does **not** license "economy is irrelevant at Danger 5."

**And a known, measured deficit already exists:** the agent leaves a **median 28 currency units on the
ground at wave end**. That figure was delegated twice and came back as 1 both times.

Per wave, record:

```
materials spawned | materials collected | materials LEFT ON THE GROUND at wave end
cumulative materials | shop spend | end-of-wave bank
build strength trajectory (damage output, dps proxy) vs wave number
```

⚠️ **THE MEASUREMENT INSTANT IS THE WHOLE MEASUREMENT.** `combat_capture` events continue for ~40-55
ticks **after** the wave timer expires, and the game's end-of-wave sweep happens inside that window.
"The last capture before the drain" therefore lands **after** the sweep and reads ~0 left behind.
**The correct instant is the last capture with `remaining_sec > 0`.** Getting this wrong is what
produced the 1-versus-28 error, twice.

Also: `MAX_GOLDS = 50` is the **game's** cap on simultaneous ground currency, not our truncation — a
hard pile at exactly 50 is the game, not a censored instrument.

**Interpretation, pre-declared:** a collection deficit that correlates with early terminal waves is a
phenotype, **not** a proven cause — the agent's collection is itself produced by its movement policy,
so "it died because it collected less" and "it collected less because it was losing" are not
separable by this campaign. If collection emerges as the dominant phenotype, the matched follow-up is
a dosed test (e.g. granting materials directly via a save edit and asking whether the same states are
rescued), which gets its own pre-registration. The **causal-vs-actionable** check in §9 applies with
full force: if a rescue needs materials the policy could never realistically collect, the mechanism is
causal and not actionable.

**Reported as components, carrying no verdict:** gross `damage_taken` (a GROSS counter that never
subtracts healing — healing varied 15-171 across six runs), and the confinement metric, which is a
**phenotype here, not an endpoint to optimise.**

## 8. Failure-classification tree, pre-declared

Applied in order to each terminal event:

1. **Was the causal hazard represented in the observation?** No → perception defect.
2. **Was any locally feasible heading available?** No → upstream positioning / build / earlier
   trajectory.
3. **Did the issued command choose a feasible heading?** No → movement arbitration or temporal policy.
4. **Was the arena already saturated?** Yes → clearance / build / tempo.
5. **Did the tail materially replace the desire vector before the failure?** Yes → tail mechanism
   becomes testable. **No → do not blame the tail merely because it is often active elsewhere.**

This does not establish causality. It exists to stop me selecting a favourite mechanism immediately.

## 9. Interpretation rule

**No mechanism is declared causal from this campaign.** A dominant phenotype selects the next matched
intervention, which gets its own pre-registration. In particular:

- **A rescue-by-dose result proves a mechanism is CAUSAL, not that it is ACTIONABLE.** For any such
  result, immediately compute the required improvement against the maximum plausible gain from real
  shop/level/collection decisions. If a build needs +30% clearance and every realistic policy change
  yields 3-5%, that **closes** the path rather than justifying another scoring layer.
- **Fixture-clustered inference.** Fresh-RNG continuations from one saved build are repeated measures
  of that build, not independent builds. Report source count, repeats per source, and per-source
  rates; never let N continuations from one source pose as N independent builds.

## 10. Pre-declared threats

- **The dominant failure wave is unknown**, so trial cost and the useful fixture wave are both
  unknown until the campaign runs. Nothing downstream may assume a wave-17-like cost.
- **12 attempts is a characterisation sample, not a win-rate estimate.** A 0/12 and a 2/12 are not
  meaningfully distinguishable and neither will be quoted as a rate.
- **The `enemy_scaling` dial reproduces only 3 of Danger's 4 channels** (`nightmare_proj` is not
  exposed), so it is a three-channel pressure ladder and never a Danger 5 substitute. No synthetic
  result ships without confirmation on actual Danger 5.
- **Era-matching:** a 47-point win-rate collapse once ran ~20 versions unnoticed. Nothing from this
  campaign pools with any pre-`0.2.58` number.
