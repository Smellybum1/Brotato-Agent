# Consultation brief: a game-playing agent whose remaining loss has gone diffuse, and whose measuring instrument can no longer see it

You are being asked for **strategic and methodological advice**. Everything you need is in
this document; there are no external references, and no file paths you are expected to
open. Please **write your answer as a single self-contained markdown (`.md`) file** so it
can be committed alongside the project's records.

Be blunt. This project has a documented history of reaching conclusions that were correct
as far as they went and wrong one step later, and external review has caught several of
them — including two that would have manufactured false positives. That track record is
why you are being asked.

---

## 1. What the project is

A deterministic bot that plays **Brotato**, a top-down arena survival game.

**The game.** A run is 20 waves. Each wave drops the player into an arena where enemies
spawn continuously for a fixed duration (20-90 s; wave 17 is 60 s). Weapons fire
**automatically** at nearby enemies. **The only thing the player controls during combat is
movement** — a 2D direction vector. Between waves there is a shop where materials are spent
on items and weapons, plus level-ups where stat upgrades are picked. Wave 20 ends with a
**boss**, drawn from two possibilities. Dying at any point ends the run; surviving wave 20
is a victory.

Configuration is fixed across every experiment ever run: character **"Well Rounded"**,
**Danger level 0** (the easiest of five difficulty tiers), ranged/gun build.

**Structural consequences worth holding onto:**
- Combat skill == movement policy. Nothing else is controllable during a wave.
- Aiming, target selection and DPS are not agent decisions; they follow from the build.
- The build (shop + level-ups) sets how fast you kill and how much you can absorb.
- So a run can fail two ways: a **movement failure** (hit too often) or a **build failure**
  (cannot kill fast enough, so you are exposed longer and the arena saturates).

**The agent.** A hand-written deterministic "teacher": a potential-field movement
controller (attraction to loot and open space; repulsion from enemies, projectiles and
walls; plus a large accumulated safety layer — density veto, relief fallback, corner guard,
edge-kite rail, pack repulsion, loot dash, build-strength tiers, a wave-20 finale override,
greed budgets) and a scoring-based shop / level-up policy. Roughly 22 tuned constants
govern the wave-20 finale alone.

A learned **student** (behaviour cloning on teacher demonstrations) exists and has been
qualified end-to-end, but it is **not enabled** — every number in this document comes from
the deterministic teacher. The student appears once, in §5, because one of its results is
informative.

---

## 2. Where performance actually is, measured on the shipped build

The shipped build is policy `0.1.129` / mod `0.2.49`. Two independent 18-run batches of
**complete full runs at 1.0x game speed**, same build, run 2026-07-27 and 2026-07-28:

| outcome | runs | share |
|---|---|---|
| **win** (survive wave 20) | 26/36 | **0.722** |
| die **before** wave 20 | 8/36 | 0.222 |
| die **at** wave 20 | 2/36 | 0.056 |

Waves at which the 10 losses fell: **12, 15, 16, 17, 17, 17, 19, 19, 20, 20**.

This was run as a **consistency check against a prediction**, not as a fishing expedition.
The prediction (0.574) came from a term-by-term derivation built on 195 archived runs; the
observed 0.722 sits about 1.8 SD above it. That is suggestive but **not** grounds to revise
the model, and it has not been revised. A 26/36 rate carries roughly a [0.55, 0.85]
interval.

**One term in that derivation is the reason performance moved at all**, and it is described
in §6.

### The historical context you should have

This project once suffered a **47-percentage-point win-rate collapse that ran for ~20
versions completely invisibly**, because the qualification standard at the time was one
smoke run plus internal rule-compliance audits. Those audits check whether the agent
obeyed its own movement rules — a run that dies at wave 3 with zero rule violations
returns "accepted". There was no statistical power against an outcome change at all.
The peak version is permanently unrecoverable (the repo had zero commits when it was
certified). "Go back to what worked" is not available.

The process was fixed: a three-gate model (executability/determinism → mechanistic →
**outcome**), with the standing rule that gate 2 can never again substitute for gate 3.
That fix is the direct cause of the measurement-cost problem in §7 — outcome gates are
expensive, and now everything must pass one.

---

## 3. The loss budget is now diffuse, and that is the strategic problem

Ranking the 10 losses by wave:

| wave | deaths (of 36 runs) | share of all runs |
|---|---|---|
| 17 | 3 | 0.083 |
| 19 | 2 | 0.056 |
| 20 | 2 | 0.056 |
| 12 | 1 | 0.028 |
| 15 | 1 | 0.028 |
| 16 | 1 | 0.028 |

**No single wave accounts for more than 8.3% of runs.** Historically this was not true —
an earlier archive analysis (197 runs, older builds, before the wave-20 fix in §6) had
wave 20 at 0.320 of runs and wave 17 at 39% of all pre-20 deaths. Closing the wave-20
hazard removed the one big block, and what remains is spread thin.

**Two headroom calculations, recomputed for this brief rather than quoted:**

- *If pre-wave-20 deaths were eliminated entirely* and wave-20 survival stayed as measured
  (predator boss 1.000 post-fix, invoker boss 0.597 from a 67-run archive, boss draw split
  0.518/0.482), the ceiling is **0.518 + 0.482 x 0.597 = 0.806**. The residual 0.194 is
  **entirely the invoker boss**, which the wave-20 fix cannot reach.
- *If wave 17 alone were eliminated*, the 3 rescued runs would still face waves 18-20, and
  P(win | reached wave 18) in this sample is 26/30 = 0.867. So the honest figure is
  **0.722 → ~0.79**, not the ~0.80 obtained by naively converting all three deaths into
  wins.

So the two structural ceilings are ~0.79 (fix wave 17 only) and ~0.81 (fix *everything*
before wave 20). Neither is reachable by any lever currently in hand — see §5.

*(A previously recorded figure put the invoker's cap at "~0.71". Recomputing it here gives
0.806; the 0.71 does not reproduce from any combination of the measured terms and appears
to be a transcription of P(reach wave 20) = 0.713. Treat 0.806 as the number.)*

---

## 4. A scope constraint you need to know about, and may want to attack

There is a standing directive that **controller changes are confined to wave 20**, with
**waves 1-19 held frozen as an internal control**. This was correct when wave 20 was the
dominant loss: it meant any behavioural change had a built-in null region, and several
findings were interpretable only because of it. For example, the wave-20 fix in §6 was
proved **provably inert before wave 20** (0 relevant observations in 60,132 pre-wave-20
captures, versus 443-1,581 at wave 20 in the same streams).

**But 8 of the 10 remaining losses are now in the frozen region.**

The internal control is a real asset, not a bureaucratic obstacle, and spending it is
explicitly the human operator's call rather than the agent's. But the situation has
inverted since the directive was written. Whether to spend it is one of the questions in
§10.

Note the constraint is on the **controller**. Two things are *not* frozen: the **shop /
level-up scoring policy**, and **save-file manipulation** used purely as an experimental
instrument (see §7).

---

## 5. The complete ledger of what has been tested and closed

Each of these is a pre-registered or properly powered result, not an impression. This is
the full list, including the ones that make the project look bad.

**(a) Wave 17 — understood, and NOT actionable.** *(Four pre-registered experiments,
232 trials, 2026-07-28/29. Every decision rule was frozen before its data existed and none
was relaxed afterwards.)*

- **Observational stage (25 died vs 25 survived).** Wave 17 is **build-limited**. Deaths
  are caused by ordinary **melee crowding**: 92.9% of damage events are melee bodies at a
  median surface distance of −1.0 u; enemy projectiles are 1-4 of 84 events. Enemy
  composition at damage ticks is enriched ~2-3x across *every* enemy type — it is crowding,
  not a specific dangerous enemy. The unexplained residual is 0/115: no perception gap.
- **The only *controllable* hypothesis — movement — is refuted on its own sign.** The agent
  steers while weapons auto-fire, so a movement failure would show as enemies kept out of
  weapon range, throttling clear rate. Crowd-matched (binning by enemies alive), weapon
  coverage is null in every evaluable bin and target uptime is **null-or-higher** in dying
  runs. The naive uptime metric runs backwards from the hypothesis for a mechanical reason:
  more enemies nearby ⇒ something is in range ⇒ uptime rises. **Uptime is partly the
  outcome (crowding), not a measure of movement quality.** Dying runs sit at 0.88-1.00
  uptime from 20 s onward — they are not failing to shoot, they are shooting almost
  constantly and still not clearing.
- **Only two entry statistics separate died from survived**, and they tell one story:
  nominal DPS **28.26 vs 35.25** and movement-speed stat **531 vs 499**. Every defensive
  stat (armour, dodge, HP, max HP, regen, lifesteal) is null. **Dying builds bought speed
  instead of damage.** An independent instrument (shop-exit weapon damage) agrees: doomed
  runs enter wave 17 with **half** the summed weapon damage (162.5 vs 335).
- **Causal dose-response, using an enemy-health dial in the save file.** Restoring a saved
  build and replaying wave 17 costs ~4.3 min. Inside a build that reliably dies:

  | enemy health | failures | |
  |---|---|---|
  | 1.00 | 6/8 | control |
  | 0.95 | 3/8 | not rescued |
  | 0.90 | 5/8 | not rescued |
  | 0.85 | 4/8 | not rescued |
  | **0.75** | **0/8** | rescued, p=0.0035 |
  | **0.50** | **0/8** | rescued, p=0.0035 |

  The three intermediate arms carry **no ordering information** — their Wilson intervals
  overlap each other and the control, so 3 < 4 < 5 is noise. Pooled they give 12/24 = 0.50
  vs 0.75, p=0.207.
- **The number that closes it: rescuing a doomed wave-17 build needs roughly a 25%
  enemy-health reduction — about a 33% clearance-rate improvement. Below that, nothing
  works.** No known lever produces a 25-33% offense gain on a doomed build.
- **Caveat that limits the claim:** every dose result rests on **one** build. Reliably-
  failing fixtures are the scarce resource — yield is 1-in-16 from arbitrary runs but
  1-in-1 from runs that died at wave 17, and archived runs cannot be converted (the save
  must be snapshotted live). About 10 such fixtures would cost ~90-110 full runs = 30-36 h.

**(b) The shop / build-scoring layer — CLOSED, NULL.** Tested twice, including
specifically against wave-17 deaths. 22 died vs 150 survivors, 63,711 offered-item
observations, with the null band calibrated *first* (rank-biserial P in [0.370, 0.630] is
indistinguishable from no separation). Gold earned and spent, weapons bought, rerolls,
leftovers, tiers, prices, weapon share, combines, sells, and offense-deficient shop exits
(28.1% vs 26.9%) are **all** inside the band. There is **no resource gap of any kind
through wave 12** — per-wave gold earned first leaves the band at wave 13. **Doomed runs'
boards were marginally *better*, so offer luck is ruled out.** A genuine mispricing was
found in the scorer, implemented as a fix, and then **withdrawn before shipping** because
computing the decisions it would change showed it did not change the *ordering* of any
actual choice. Also measured: the **rankable** decision surface is only ~91 decisions in
total (~4.6 per run) — this layer is much smaller than it looks.

**(c) A learned RL residual on the teacher's movement — NULL, twice.** Trained against a
matched random-perturbation control; every confidence interval straddles zero.

**(d) Wave-20 movement policy replacement — NULL.** An exploratory campaign gave +18.75 pp
with a bootstrap CI excluding zero; the pre-registered fresh-sample confirmation (128
trials) gave **−7.8 pp, p = 0.454**, with per-build effects flipping sign rather than
shrinking. The first campaign was noise. A control-arm check confirmed nothing had drifted
between campaigns.

**(e) Wave-20 control-rate change — NULL with a tight interval.** −4.1 pp, p = 0.714, CI
[−0.125, +0.031], with a validity instrument proving the rate genuinely changed (recompute
ratio 1.0000 on all treatment trials vs 0.3333-0.3340 on all controls, zero overlap). This
is evidence of *absence* of a large effect.

**(f) Invoker boss (the wave-20 boss the fix cannot reach) — GATE NO-GO.** Measured over
180 damage events in 66 fights: the invoker kills by **stationary projectile fields** —
**78 of 78** projectile hits in defeats were exactly motionless, median surface distance
3-13 u. The agent walks into fully visible hazards. This looked like the ideal target for
local avoidance. It was gated before implementing, per a standing "show the decision flips
first" rule, and **it does not flip**: the avoidance term **already exists**, it is
**saturated** (urgency at 1.0 across p10/median/p90, at which point the blend returns the
escape direction outright), it is active on **121/121** causal ticks with zero downstream
overrides, and the agent is **enclosed** — 82.2% of hits had *no* heading among 24 sampled
that would buy even one capture-interval of clearance, and in 62% it was already commanding
the single best available heading. **Addressable ceiling: 11.9% of hits, assuming a perfect
selector.** The only remaining lever is **upstream positioning** — not being there 0.6 s
earlier — which is a much larger intervention that nothing yet justifies.

**(g) A learned student that agreed with the teacher MORE and played WORSE.** A newer
behaviour-cloning student cut held-out imitation error from 55.7° to 37.9° and yet died
earlier and more often in live play. Mechanistically it was a smoother, less evasive mover
with ~45x more low-HP exposure in mid-game waves. The reading was: **teacher-imitation
error is not the live objective, and evasiveness or dither may itself be protective.**

**(h) A refuted unification hypothesis, worth its own line.** Having found that wave 17
separates on offense, I proposed that the whole late game might be one offense story —
which would have explained every nulled movement intervention at once. **It does not
hold.** Same covariates, wave-20 outcomes, same null band:

| | weapon damage | max HP | armour |
|---|---|---|---|
| **wave 17** | **0.188** | 0.479 | 0.426 |
| wave 20, invoker (42W/29L) | 0.553 | 0.320 | 0.620 |
| wave 20, predator (38W/35L) | 0.464 | 0.370 | 0.350 |

**Offense does not separate wave-20 outcomes for either boss.** That is mechanistically
coherent — wave 17 is a **60 s timed wave** (clear fast enough or the arena saturates =
offense), wave 20 is a **boss fight** (survive incoming damage = defense/dodging). They are
different problems on different covariates.

---

## 6. The one thing that ever worked, and what class of defect it was

Exactly one intervention in this project's history produced a large, replicated,
shipped improvement. It is worth studying as a *class*.

The harder wave-20 boss carries nine rotating projectile nodes mounted on a pivot child
node. The telemetry collector enumerated one node's **direct children**, so those nine were
**invisible to the agent's state vector** — while carrying **84-91% of all wave-20 damage**.
The agent was being killed by hazards it could not see.

Fixing the collector (not the movement policy — the *perception*) took paired wave-20
survival from **0.688 to 1.000** over 64 trials, p = 0.000426, and it held on natural
arrivals afterwards (7/7, with the structural signature present in every one: 9,477-16,011
rotating-projectile observations per run, against **0 in 245,057** control observations).

**The pattern across the whole ledger:**

| class of defect | interventions | result |
|---|---|---|
| **perception / state-vector blind spot** | 1 | **large, replicated, shipped** |
| movement policy & control rate | 3 | null |
| learned policy (RL residual, BC student) | 3 | null-to-negative |
| shop / build scoring | 2 | null |

One data point on the winning side is one data point. But the contrast is stark enough
that "what else is the agent structurally unable to see?" may be a better prior than
"what should the agent do differently?"

Against that: the wave-17 analysis explicitly looked for a perception gap and found
**none** (0/115 unexplained damage events), and the invoker analysis found the damage
**fully visible** (0/180 unexplained). So the two remaining loss centres have both been
checked for this specific defect class and both came back clean.

---

## 7. The measurement economics — the binding constraint on everything

This is the section I most want you to engage with, because it is what makes the strategic
question hard rather than merely open.

### Full runs

A complete run costs **~19 minutes** of machine time. The outcome is **binary**
(win/loss). To detect an improvement from the measured 0.722, two-arm, 80% power,
α = 0.05 two-sided:

| target win rate | improvement | runs per arm | total runs | machine time |
|---|---|---|---|---|
| 0.80 | +7.8 pp | 465 | 930 | **~294 h (12 days)** |
| 0.85 | +12.8 pp | 157 | 314 | ~99 h (4 days) |
| 0.90 | +17.8 pp | 72 | 144 | ~46 h |
| 0.95 | +22.8 pp | 38 | 75 | ~24 h |

Testing single-arm against a fixed historical baseline of 0.722 roughly halves this
(~243 runs, ~77 h, for the 0.80 target) — but historical baselines are exactly what
produced the invisible 47-point collapse and a separate contaminated-population error, so
this project distrusts them structurally.

**Recall from §3 that the entire structural ceiling is ~0.81.** So *every* achievable
improvement sits in the top row of that table, at 12 days of continuous machine time per
experiment. **The full-run instrument can no longer resolve any effect this project could
actually produce.**

### The fast instrument, and why it does not rescue this

The game continuously writes a complete mid-run save. Snapshots are archived and a trial
restores one, resumes, and plays a single wave. **A wave-20 trial costs ~45 s; a wave-17
trial ~4.3 min.** Last week this ran 402 pre-registered trials overnight with zero failed
passes. Paired campaign sizing is calibrated: with damage-taken as a continuous outcome,
32 trials detects a 19-damage effect, 64 detects 13, 128 detects 9, against a control mean
of ~20.7.

Three limits:

1. **It is per-wave, not per-run.** It cannot see anything that accumulates across waves —
   and the leading remaining hypothesis (build allocation, §9) is exactly that.
2. **Its binary outcome is saturated.** On the shipped build, wave-20 fixture win rate is
   pinned at **1.000** and cannot discriminate at *any* n. Only the continuous
   damage-taken outcome retains power.
3. **It needs a failing population to study.** For wave 17 the yield of reliably-failing
   fixtures is 1-in-16 from arbitrary runs, and every causal result so far rests on a
   single build.

### Two hard-won constraints on the apparatus

- **Time acceleration is limited to 2.0x, and only for paired fixture campaigns.** 4x and
  8x fail — 8x roughly doubles damage taken. The degradation tracks physics **saturation**,
  not speed, so an achieved/nominal ratio is verified on every run.
- **Running the game headless gives no speedup at all** — measured, closed.

---

## 8. How this project fails, so you can calibrate your advice

The dominant failure mode, hit repeatedly, is **stopping one step short**: a conclusion
that is correct as far as it goes, reached one step before the step that reverses it.
Instances include reading a resource as destroyed when it was deferred one function
forward; declaring a layer exhausted after testing the component that is almost never the
deciding term in a `max()`; and implementing a real, correctly-measured mispricing without
first checking whether it changes any actual ordering (it did not).

Adjacent recurring traps, all real:

- **Zeros from vacuous filters.** A diagnostic reported "0 misses over 1,037 decisions" and
  was believed for a day. Its filter required a field that is `null` on 100% of the relevant
  rows, so the comparison set was empty. It did not find zero; **it could not find one.**
  At least seven telemetry fields have turned out structurally uninformative — the working
  assumption is now "uninformative until shown otherwise".
- **Three ways an experiment can lie before it runs**, all caught in the last two days,
  two of them only because someone else looked:
  1. An **outcome the treatment mechanically rescales** — planning "enemy HP pool remaining"
     as the primary outcome of a campaign whose treatment *halves enemy health*. It would
     have produced a large, significant, meaningless effect. Caught by external review.
  2. A **validity guard that rejects by outcome** — a boss-identity check that would have
     invalidated exactly the trials that *survived* wave 17.
  3. A **test statistic that cannot return the positive** — a hand-rolled Fisher exact test
     summing the wrong tail, returning 0.9986 where the answer is 0.016, making the
     positive branch unreachable regardless of the data.
- **Same-named fields from different sources, 3.40x apart.** Ranking builds by
  `damage/cooldown` from the save file gave a uniformly weak library, contradicting the
  running trials. The save holds the weapon's **base template**; the live capture holds the
  **effective in-run value** after bonuses. Identical field names, identical formula.
- **Null bands do not travel.** A band calibrated for one comparison's denominator was
  carried to a table with a different one, which changed which covariates counted as
  separating. Caught externally.

The counter-question that goes with all of this, and which I would like challenged: this
process is now heavy — pre-registration, frozen decision rules, gates, readback
verification of anything that arms an experiment. **It has caught real errors. It has also
produced a ledger that is almost entirely nulls.** Whether that ratio reflects good
discipline finding nothing, or discipline so expensive that only small safe things get
tested, is not something I can assess from inside.

---

## 9. The candidate directions I can see, and my honest read of each

**(i) Spend the internal control and work on waves 1-19.** 80% of remaining losses are
there. Cost: the frozen region that made several past findings interpretable. Also, the
one wave in that region that *has* been characterised (17) turned out build-limited, not
movement-limited — so "work on pre-20 movement" may be aiming at the wrong modality
throughout.

**(ii) Attack build allocation.** The single most robust unexplained signal in the whole
project: **dying builds bought speed instead of damage** (nominal DPS 28.26 vs 35.25, speed
stat 531 vs 499), corroborated from two independent instruments (entry state and shop-exit
weapon damage). But the shop layer tested null on every proxy, and the rankable surface is
only ~91 decisions per run-population. The gap: the shop analysis asked *"did the policy
miss an affordable offense item?"* (no) — it did **not** test the **valuation weights**
themselves, i.e. whether the scoring function systematically overvalues movement speed
relative to damage. That distinction may or may not be real; I cannot tell whether it is a
genuine untested angle or me refusing to accept a null.

**(iii) Systematic perception audit.** On the prior in §6, enumerate everything in the game
that can damage the player and verify each is represented in the state vector. Cheap,
bounded, and the one class of defect that ever paid. Against it: the two remaining loss
centres have already been checked for this and came back clean (0/115 and 0/180
unexplained).

**(iv) Upstream positioning for the invoker boss.** Named by its own gate analysis as the
only remaining lever, and it is worth 0.194 of the ceiling. Large, and currently
unjustified by any mechanism.

**(v) Stop.** If 0.722 is near the practical ceiling for this character at this difficulty,
the correct move is to declare the project finished. **I do not know how to establish
that.** A specific sub-question: what *does* a competent human player win at, on Well
Rounded at Danger 0? If it is ~95%+, then ~25 points of real headroom exist and
"irreducible variance" is not an acceptable answer. If it is ~75%, we are done.

---

## 10. Questions

1. **Where should effort go?** Given a loss budget where no single wave exceeds 8.3% of
   runs, a structural ceiling of ~0.81, and the option list in §9 — what would you do, and
   what would you explicitly decline to do?

2. **Is "which wave did it die on" the wrong decomposition?** It is the natural unit and
   it has now gone flat. What is a better one — hazard conditional on build state? A
   per-run tempo or economy trajectory? Something that treats a run as a single trajectory
   with an accumulating deficit rather than 20 independent hurdles? This matters because
   if the loss is one upstream cause expressing itself at whatever wave happens to be
   hardest, then per-wave targeting is structurally guaranteed to keep finding diffuse
   nulls.

3. **The measurement crisis (§7) — what design gets us out?** Full runs cannot resolve
   anything below +13 pp at a tolerable cost, and the whole remaining headroom is +8 pp.
   Options I can see: a validated **continuous surrogate outcome** for full runs (what
   would you use, and how would you validate that it predicts win rate?); sequential /
   group-sequential designs; variance reduction by pairing full runs on a seeded start or
   on covariates; accepting single-arm tests against a fixed baseline. **What would you
   actually recommend?** I regard this as the highest-value question in the document —
   without an answer, no strategic choice in Q1 can be evaluated afterwards.

4. **The build-allocation lever (§9 ii).** Is "the shop scoring function overvalues speed
   relative to damage" a genuinely untested hypothesis distinct from the closed shop-layer
   null, or am I refusing to accept a null? If it is genuine, what is the cheapest decisive
   test — bearing in mind that the intervention is on a *deterministic scoring policy we
   fully control*, so the counterfactual decisions can be computed offline without playing
   anything.

5. **What should I infer from the pattern in §6?** One perception fix worked; three
   movement/control interventions, three learned-policy attempts and two shop interventions
   all nulled. Is that a real prior about where defects live in this kind of system, or is
   it survivorship reasoning over a small sample?

6. **How would you establish the ceiling (§9 v)?** What is a defensible way to estimate the
   maximum achievable win rate for a fixed character/difficulty in a game with this much
   run-to-run RNG — and do you have a view on what a strong human actually achieves on
   Well Rounded at Danger 0?

7. **Is the scope directive in §4 now costing more than it buys?** The internal control is
   genuinely valuable and has made past results interpretable. It also fences off 80% of the
   remaining loss. How would you make that trade, and is there a design that keeps a usable
   control while unfreezing waves 1-19?

8. **Anything in §§2-8 that you think is mis-analysed or over-claimed.** In particular:
   the wave-17 closure argument in §5(a) — is "the required intervention is 25-33% and we
   have no lever that size" a sound reason to stop, or is it an argument that we have not
   looked hard enough for a lever?

Please deliver your answer as a **markdown file**.
