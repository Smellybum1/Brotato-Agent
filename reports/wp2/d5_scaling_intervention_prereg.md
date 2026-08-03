# §28 Pre-registration — Is D5 failure SURVIVAL-limited or CLEARANCE-limited?

**Written 2026-08-02, before any confirmatory data.** Supersedes nothing; §26 produced the first valid
D0/D5 pair and explicitly deferred this question: *"a §26d null does NOT show D5 failure is
survival-limited — that needs an INTERVENTION."* This is that intervention.

## §28a The question

At Danger 5 the agent dies at median wave 11 (§26, n=16, mean 10.562, sd 1.590, 0/16 victories).
Two incompatible explanations have stood unresolved:

- **SURVIVAL-limited** — it takes damage faster than it can absorb (§7's reading: contacts 13.2x a
  matched control, 0.90 of max_hp lost in the final 10 s).
- **CLEARANCE-limited** — it kills too slowly, so the arena saturates and damage follows
  ([[brotato-arena-population]]: D5 clearance is uniformly deficient, enemy lifetime flat 1.6-3.3 s).

Observation cannot separate these because they are mutually reinforcing. An intervention can.

## §28b The lever, and why it is valid here

`current_run_state.enemy_scaling` in the save: `{damage, health, speed}`.
**Feasibility gate PASSED 2026-08-02** (`brotato-enemy-scaling-lever`, 2 trials):

- A **wave-1 D5 snapshot resumes preserving danger 5** — `observed_danger == 5` in the capture stream
  of both arms, control `character_ok` + `danger_ok`, waves contiguous `[2..8]`.
- **The dial applies at wave-1 depth**: at `health = 0.25`, per-entity `max_hp` scaled **exactly
  4.00x** on clean-valued types (bruiser 136→34, fly 32→8, helmet_alien 28→7, slasher_egg 32→8).
- No deploy, no version bump, no code change: the dial is a save edit.

## ⭐ §28c THE ASYMMETRY THAT DRIVES INTERPRETATION — declared in advance

**The two dials are NOT symmetric, and this is the single most important thing in this document.**

- **`damage` is a CLEAN defensive lever.** It changes incoming damage per hit and does not change how
  fast enemies die.
- **`health` is NOT a clean offensive lever.** Killing enemies faster *also* reduces incoming damage,
  because dead enemies stop hitting you. It carries an indirect defensive effect.

Therefore the inference table is asymmetric, and the *informative* cell is not the obvious one:

| result | inference |
|---|---|
| **`health` moves the endpoint, `damage` does not** | **CLEARANCE-limited — and this is CLEAN.** If health's benefit ran through its defensive side-effect, then reducing damage directly would also have worked. It did not, so the benefit must be the clearance channel. |
| **`damage` moves it, `health` does not** | **SURVIVAL-limited**, with a caveat: health's defensive side-effect should have produced *some* movement, so a hard zero on health needs explaining. |
| **both move it** | **NO DISSOCIATION.** Report as such. Do not rank the dials — see §28g. |
| **neither moves it** | Dose too weak, or the endpoint is insensitive. **Not** evidence of "neither channel matters." |

⛔ **This table is fixed now.** It is not to be reinterpreted after seeing the data.

## §28d Design

**Character `mutant`, Danger 5, build `0.2.73-wp2-capture`, port INERT** — matching §26's arm so the
control is comparable in construction (though NOT poolable: different era, and fixture-resume rather
than a wave-1 start).

**Fixtures: 8 distinct wave-1 D5 mutant snapshots**, harvested cheaply (~1 min each).

⛔⛔ **CORRECTED 2026-08-02 BEFORE COLLECTION — the first draft justified this wrongly.** It claimed
distinct snapshots carry "distinct predetermined `bosses_spawn` and RNG streams." Measured across 8
harvested files:

- **`bosses_spawn` takes only TWO values**, and they are the same pair in either order —
  `["boss_wizard","boss_crab"]` / `["boss_crab","boss_wizard"]`. Boss identity is effectively fixed;
  only which one arrives first varies. **Much narrower than the draft claimed.**
- **`elites_spawn` DOES carry per-wave RNG seeds** (`[[12, 0, 2907336940], ...]` vs
  `[[12, 0, 1458511319], ...]`) and is the real run identity.
- Entry state genuinely varies: **`current_level` 2-3, gold, `current_health` 12-13, `shop_items`.**

⛔⛔ **AND THE DEDUP KEY MATTERS: 8 snapshot FILES were only 5 distinct RUNS.** The collector writes a
snapshot per save-write, so one run yields several wave-1 states (before/after the wave-1 shop) that
differ in gold but share a run. **Selecting fixtures by file would be silent pseudo-replication** —
near-identical entry states counted as independent draws, which would understate variance and inflate
any effect. **Fixtures are therefore selected ONE PER DISTINCT `elites_spawn`**, and the harvest counts
distinct runs, not files.

⚠️ Consequence for the design: wave-1 states are far more homogeneous than the w17 fixture library, so
**between-fixture variance is small and pairing buys much less here than at wave 17.** The primary
analysis is therefore reported **unpaired**, with the paired form as a sensitivity. The generalisation
claim narrows accordingly: this is one wave-1 D5 mutant entry distribution, not a build library.
⚠️ **No RNG seed for in-run combat is stored**, so replays of the same fixture are NOT deterministic —
the control arm's own spread across 8 fixtures is the check on that, and is reported first.

**5 arms, each fixture played under all 5 (paired):**

| arm | `enemy_scaling` | role |
|---|---|---|
| control | health 1.0, damage 1.0 | baseline |
| H75 | **health 0.75** | clearance ladder, low |
| H50 | **health 0.50** | clearance ladder, high |
| D75 | **damage 0.75** | survival ladder, low |
| D50 | **damage 0.50** | survival ladder, high |

**8 fixtures x 5 arms = 40 runs.** A two-point ladder per dial is what makes the dials comparable at
all: a single dose per dial cannot distinguish "this dial matters more" from "this dose was larger."
**Compare SLOPES, not single points.**

`speed` is held at 1.0 in every arm and is not investigated.

## §28e Endpoint and analysis, fixed in advance

**PRIMARY: terminal wave.** Same endpoint as §26, chosen before collection here.
**Analysis: exact permutation on fixture-level paired differences**, arm vs control, one test per arm.
Two-sided, α = 0.05. Reported per arm with the raw per-fixture series printed.

**Power:** using §26's D5 sd of 1.590 and 8 pairs, ~80% power for Δ ≈ 2.2 waves. The gate's `health
0.25` run reached wave 17+ against a control dying at 8, so doses of 0.5 are expected to clear this
comfortably; 0.75 may not, which is the point of a ladder.

**SECONDARY, descriptive only:** victories at wave 20; HP-deficit AUC. Not decision-bearing.

## §28f Validity — the three design-time lies, each addressed

**(a) Does the treatment mechanically rescale the outcome?** No. Terminal wave is a count of waves
survived; `enemy_scaling` does not change its units. *(Contrast: `enemy_hp_pool` at fixed time WOULD be
disqualified — that was caught by external review once already.)*

**(b) Does any guard reject by outcome?** ⛔ **One did, and it is fixed.** The gate's treatment run
reached wave 17, was still alive at `--timeout-sec 900`, and was recorded
`valid=False, reason='timeout_900s', captures=0` — *the arm working as intended scored as a technical
failure.* In a campaign at 900 s **every successful rescue would be discarded and the effective arm
would report a null.**
⇒ **`--timeout-sec 2400`, and a timeout is a CENSORED OBSERVATION**: record the highest wave reached
from the capture stream and mark it censored. **A timeout is never an invalid trial.** Censored counts
are reported per arm BEFORE any outcome statistic.
No other guard is evaluated on data produced after the measured event.

**(c) Can the statistic return the positive?** The permutation implementation is verified against a
known closed form before it decides anything, and checked in BOTH directions (a p-value that is small
when it should be large is as broken as the reverse).

**⛔⛔ A SECOND REJECT-BY-OUTCOME GUARD WAS FOUND IN THE PILOT AND FIXED (2026-08-02).** §28f originally
claimed class (b) was handled because the timeout was fixed. It was not. `wp2_finale_loop.py` carried
`elif boss_paths: return "unexpected_boss"` under the comment *"Bosses only exist at wave 20."*
**That premise is false: ELITES are classified into `boss_paths` and spawn from wave 11** — the save's
own `elites_spawn` lists their waves (`[[11,1,...],[14,0,...]]`).

Measured on the first 10 pilot trials: **every trial reaching wave >= 12 was rejected
`unexpected_boss`** (monk, rhino, gargoyle, mantis) **while every trial ending <= 11 passed.** It
discards the high tail of every arm and discards MOST from the arms that work best (H50: 2/2 rejected).
*The adjacent branch in the same function already carried the correct reasoning — "enforcing boss
identity here would reject exactly the trials that SURVIVED" — fixed for the wave-20 case and left
unfixed here.*
**Fixed:** no boss/elite check at all when `target_wave < 20` (a long run legitimately accumulates
several distinct elite paths — one pilot trial had three at wave 18). Verified: all 6 wrongly-rejected
trials now pass, and the guard still rejects real faults (`resume_failed_fresh_run`, `wave_gap`) — the
fix is not vacuous.

**Dose readback — the manipulation check, and it differs per dial.**

- **HEALTH arms — per-trial, deterministic.** Per-entity `max_hp` vs the arm's expected ratio; a trial
  that does not match is **excluded and reported**. Read the **LARGE-HP** types (bruiser,
  horned_bruiser, healer); small-HP types deviate by integer rounding alone.
- **⛔ DAMAGE arms — `max_hp` IS VACUOUS FOR THEM.** Damage scaling does not change `max_hp`, and
  **the capture carries no enemy damage field** (verified: enemy keys are `armor, health_ratio, hp,
  max_hp, speed, ...`). Applying the health readback to the D arms would be a check that cannot
  return the positive — the artificer-melee trap.
  **Replacement: median player HP-DROP SIZE at MATCHED WAVES, aggregated PER ARM.** Per-trial is
  impossible — a control run yields only ~5 drop events in ~11,700 captures.
  ⛔ **Gross `damage_taken` is NOT a valid check here.** Pilot: D50 took *more* gross damage per wave
  than control (11.8 vs 4.7) because the dial changes behaviour — more hits, each smaller. Drop SIZE
  is confound-resistant; drop COUNT and gross total are not.
  ✅ **Pilot evidence the dial engages** (n=1/cell, indicative only): damage-1.0 arms show drops of
  9-33, damage-reduced arms 3-8.
  ⚠️ **The damage dial had never actually been verified** — the 2026-07-28 lever check tested `health`
  only, and "damage perturbs incoming damage" was a design statement carried as if measured.

**Arm certification.** `character_ok` and `observed_danger` are taken from the **capture stream**, not
the summary — the gate found `summary.observed_danger` reading `None` while `danger_ok` read `True`,
which cannot both be right. Opener must be `weapon_smg_1` on every trial.

**Era stability — DERIVED FOR THIS POPULATION, not inherited.** Era is **179/48/59** and
**cannot drift**: `chal_mutant` is already completed (verified by djb2 with passing controls), so a
mutant victory grants nothing. *This is exactly the property §24 assumed for Jack and §25 wrongly
inherited for four other characters; it is re-derived here rather than carried over.*

**Launch hygiene.** After any force-kill, `deploy_mod.py --repair-launch` runs before the next launch,
unconditionally — the latch is applied at the NEXT launch, so a pre-launch log check cannot detect it.
A fresh `mod_ready.json` mtime is the only proof the mod loaded.

## §28g Stopping rule and pre-declared limits

- **Fixed n. All 40 runs are collected regardless of interim results.** No `--stop-on-win` (it censors
  on the largest possible terminal wave and biased a headline result once already). No extension of a
  disappointing arm; no top-up-and-retest.
- ⛔ **The dials are NOT unit-commensurable.** "health 0.5" and "damage 0.5" are not equal-strength
  interventions. Only **qualitative** comparisons are licensed — flat vs steep. **No claim of the form
  "clearance matters 2.3x more than survival" may be made from this design.**
- ⛔ **Ceiling risk is real.** If an arm pins at wave 20, terminal wave becomes a FLOOR for that arm and
  loses discriminating power. Censored/victory counts are reported per arm first; if an arm is ≥50% at
  wave 20, its effect size is reported as a bound, not a point estimate.
- ⛔ **One character, one danger tier, one build, wave-1 entry.** Nothing here generalises to other
  characters, and this control is **not poolable with §26's** (different era, different entry).
- ⛔ **This measures where the BINDING CONSTRAINT is, not what to build.** A dissociation identifies a
  channel; it does not identify a reachable lever. Gate 0 still applies to anything proposed afterward.

## §28i Corrections recorded 2026-08-03 02:5x, at 22/40, BEFORE any outcome statistic

Both were found while adopting the running campaign. **No outcome statistic has been computed**, and
neither correction is resolvable by a choice I could tune to a result — see the disclosure at the end.

### (i) §28d and §28e CONTRADICT EACH OTHER on the primary test

- **§28d** (the dated pre-collection correction): *"between-fixture variance is small and pairing buys
  much less here than at wave 17. The primary analysis is therefore reported **unpaired**, with the
  paired form as a sensitivity."*
- **§28e** (the section titled *Endpoint and analysis, fixed in advance*): *"Analysis: exact
  permutation on fixture-level **paired** differences"* — and its power calculation is framed on
  *"8 pairs."*

Both are pre-registered. Picking one now, after I have been exposed to partial outcome data (below),
would be a garden-of-forking-paths choice however honestly made.

⇒ **RESOLUTION: BOTH ARE REPORTED, WITH EQUAL STANDING, AND NEITHER IS PRIVILEGED AS "THE" PRIMARY.**
The paired permutation on fixture-level differences and the unpaired permutation on arm-vs-control are
each computed for every arm and printed side by side. **Their agreement or disagreement is itself a
reported result**: if the two forms disagree on any arm at α = 0.05, that arm's effect is declared
**FRAGILE TO THE PAIRING CHOICE** and reported as such rather than as a significant finding. This is
choice-free and therefore immune to my partial exposure. It costs nothing — both tests run on the same
40 rows.

### (ii) §28f's CENSORING PROMISE WAS NEVER IMPLEMENTED IN THE DRIVER

§28f states: *"a timeout is a CENSORED OBSERVATION: record the highest wave reached from the capture
stream and mark it censored. **A timeout is never an invalid trial.**"* **Only the first half of that
fix landed** (`--timeout-sec 2400`). Read from source at `scripts/wp2_finale_loop.py:551-555`: on
timeout the loop sets `invalid_reason` and `break`s with `run_dir` still `None`, so the enrichment
block at `:571` — which is what populates `waves`, `last_wave`, `n_captures` and evaluates
`validate_trial` — **is skipped entirely.** The row keeps its initialized `valid=False,
last_wave=None, waves=[], n_captures=0`: precisely the pilot pathology §28f(b) was written to kill,
still live, in the arms most likely to trigger it.

**This is the reject-by-outcome class for the FOURTH time on this project** (11(b), 17th instance,
25th instance, now this). The 25th instance's lesson — *fixing one instance does not close the class* —
applies to itself: §28f fixed the guard and left the recording path unfixed.

**Exposure, measured at 22/40: ZERO.** Max `trial_wall_sec` **1181 s = 49.2% of the 2400 s cap**;
0 rows at the cap; 0 blank `run_id`. Reaching wave 20 ends a run in victory, so trial length has a
natural ceiling near ~1200 s and the cap is unlikely to bind.

⛔ **NOT FIXED IN CODE, DELIBERATELY.** The apparatus must not change mid-campaign — that discarded 10
pilot trials once already. It is also moot: the driver imported the module at launch, so a file edit
cannot reach the running process.

⇒ **RESOLUTION — recover censoring at ANALYSIS time, which is fully possible because `run_id` is
recorded on the timeout path (`:553-554`):**
1. A row with `invalid_reason` matching `^timeout_` is a **CENSORED OBSERVATION, NOT an invalid
   trial.** Re-open that `run_id`'s `events.jsonl` and recompute the wave series with the driver's own
   `analyse_events`; the censored terminal wave is `max(waves)`.
2. `telemetry_stale_*` and `game_exited_before_summary` **remain genuinely invalid** — the game stopped
   writing or died, which is a technical failure, not an outcome. A timeout means the run was *still
   going*, which is the opposite.
3. A timeout row with a blank `run_id` (game never started) is invalid and unrecoverable — reported
   separately.
4. **Censored counts are reported PER ARM before any outcome statistic**, per §28f(b) and §28g, and a
   censored observation is a **FLOOR** on terminal wave — combined with §28g's wave-20 ceiling rule.

### (iii) §28f's ARM-CERTIFICATION INSTRUCTION IS UNEXECUTABLE, AND ITS JUSTIFICATION WAS A BAD LOOKUP

§28f says: *"`character_ok` and `observed_danger` are taken from the **capture stream**, not the
summary — the gate found `summary.observed_danger` reading `None` while `danger_ok` read `True`, which
cannot both be right."*

Neither field is in `combat_capture` or `combat_tick`. Measured on a full 142 MB run:
`combat_capture`'s payload keys are `arena, capture_schema_hash, capture_schema_id, capture_seq,
control_dt_ms, dropped_counts, entities, invalid_counts, observation_age_ms, observation_ts_ms,
player, teacher, valid, wave, wave_time, weapons`; `combat_tick`'s are `bosses, build_metrics,
consumables, debug, hp, loot, move, player, wave`. A recursive hunt for `danger|character|_ok|observed`
over both returns **zero hits**.

⛔ **AND MY FIRST CONCLUSION FROM THAT WAS WRONG — CORRECTED BELOW, SAME DAY.** I wrote that the
instruction was *unexecutable* and that certification must come from `summary.json`. **It is
executable.** My event-type enumeration printed `.most_common(12)` of **16** types; the counts summed
to 11,325 of 11,329 lines and **I did not notice the 4 missing events.** One of them is a dedicated
**`difficulty_readback`** event — which is exactly the stream-derived source §28f asked for:

```
difficulty_readback.payload = {
  requested_danger: 5, observed_danger: 5, danger_ok: true, rundata_current_difficulty: 5,
  rundata_current_run_accessibility_settings: {damage: 1, health: 1, speed: 1}
}
```

*Stopping one step short, on my own alarm, via a truncated print. A `most_common(N)` is a **filter**,
and this project's standing rule is that a filter needs its candidate-set size checked — I checked the
denominator for the analysis and not for my own diagnostic.*

⇒ **CORRECTED SOURCE OF TRUTH — `difficulty_readback` (stream-derived, per §28f as written):**
`observed_danger`, `danger_ok`, `requested_danger`, plus the **live dial**. Opener is
`run_start.payload.weapon`. `summary.json` remains a valid cross-check (`character_observed`,
`character_ok`, `danger`, `unlock_pool`) but is **not** the primary — §28f's preference for the stream
was right.

*The `observed_danger`-reads-`None` complaint was about the SUMMARY, where the field genuinely does not
exist (the summary's key is `danger`). So it was a wrong-key lookup — 21st-instance shaped — but the
remedy is the `difficulty_readback` event, not the summary.*

### ⭐⭐ THE DAMAGE ARMS DO HAVE A PER-TRIAL READBACK AFTER ALL — but it is DELIVERY, not EFFECT

§28f states the damage dial has no per-trial readback (`max_hp` vacuous, no enemy damage field) and
falls back to an aggregate. **`rundata_current_run_accessibility_settings` carries the live
`{damage, health, speed}` directly**, giving a deterministic per-trial check for BOTH dials.

**✅ Verified in the primary session, 23/23 trials, 0 missing readbacks, every arm exact:**

| arm | dial readback | `observed_danger` | n |
|---|---|---|---|
| control | `damage=1, health=1` | 5 | 5 |
| H75 | `damage=1, health=0.75` | 5 | 5 |
| H50 | `damage=1, health=0.5` | 5 | 5 |
| D75 | `damage=0.75, health=1` | 5 | 4 |
| D50 | `damage=0.5, health=1` | 5 | 4 |

**Five distinct values ⇒ the field varies and the check is not vacuous.**

⛔ **THIS DOES NOT RETIRE THE HP-DROP-SIZE CHECK.** The readback proves the value **reached the run's
state** — that is DELIVERY. This project's standing lesson is that a self-report proves delivery and
never correctness (the sidecar shipped the wrong encoder with every health indicator green). Whether
scaled damage actually produces smaller hits is an EFFECT question, and **median player HP-drop size at
matched waves, aggregated per arm, remains the required effect check.** The two are complementary: a
readback that matches with drop sizes unchanged would mean the dial is inert, which is precisely the
failure the aggregate exists to catch.

**✅ CERTIFIED, all 22 completed trials, 0 missing:** `character` / `character_observed` /
`requested_character` all `character_mutant`; `character_ok` true; `danger` / `requested_danger` **5**;
`danger_ok` true; `mod_version` **0.2.73-wp2-capture**; `policy_version` constant; **era
`179/48/2018397571` on every trial — no drift**, confirming the `chal_mutant` argument empirically
rather than by inheritance. `movement_estop_enabled` **false** (correct for unattended) with
`movement_estop_suppressed` **0** (gate live, never needed to suppress).

**⚠️ AND THE CONTROL THAT MAKES THOSE COUNTS MEAN SOMETHING — it only half passes.** Every field above
reads a CONSTANT, which is the exact shape of the hardcoded-literal trap (`danger` was a hardcoded `0`
across 1,873 runs once). Positive control over **441 recent archived summaries**:

| field | distinct values | verdict |
|---|---|---|
| `danger` | **2** — `0` (356) / `5` (85) | ✅ varies; the old hardcode is genuinely fixed |
| `character_observed` | **12** distinct characters | ✅ varies |
| `result` | victory 117 / defeat 324 | ✅ varies |
| `danger_ok` | `true` / `<ABSENT>` — **never FALSE** | ⚠️ cannot be shown to return the negative |
| `character_ok` | `true` / `<ABSENT>` — **never FALSE** | ⚠️ same |

⇒ **Certify off the PRIMITIVES, not the booleans.** `danger == 5` and `character_observed ==
"character_mutant"` are proven-varying and therefore informative; `danger_ok` / `character_ok` are
derived comparisons never observed false anywhere in the archive, so a `true` from them carries no
independent evidence. (`<ABSENT>` is simply older builds predating the fields.)

### (iv) THE DROP-SIZE CHANNEL — `player_damage` for MAGNITUDE, HP-diff for ATTRIBUTION

§28f prescribes drop size by differencing player `hp` between consecutive captures. **Within a wave,
that channel is lossy and the loss is not random.** Measured on one H50 trial: 4 real damage events
were missed because they straddle **wave boundaries** (15→16, 17→18, 18→19, 19→20), which a within-wave
rule excludes by construction; cross-wave differencing cannot fix it because `hp` and `max_hp` both
change in the shop. **3 of the 4 missed were small (3, 5, 6), so the channel inflates median drop size
— biased TOWARD the hypothesis.**

⛔ **And the bias is ARM-DEPENDENT, which is what makes it disqualifying rather than merely noisy:**
longer-surviving trials cross more wave boundaries, so the arms the intervention rescues lose more
small drops than the control does. That is a confound between the dial and the very statistic meant to
verify it.

⇒ **`player_damage.amount` is the PRIMARY magnitude channel; the HP-diff is corroboration.** They agree
exactly where no boundary is crossed (10 vs 10, 28 vs 28 on two runs).

⚠️ **Scoping note, because memory says the opposite in a different context.** The standing rule *"use
the HP-drop diff for attribution, not `player_damage`"* was established because `player_damage` **lags
the true damage tick by ~one capture interval**, which corrupts *which enemy* gets blamed. That is an
**ATTRIBUTION** defect and it does not touch **MAGNITUDE** — the amount is correct whichever tick
carries it. Both rules stand, in their own scopes: **magnitude ← `player_damage.amount`;
attribution ← HP-drop diff.** Neither supersedes the other.

### (v) ONE TRIAL'S EFFECTIVE DOSE DRIFTED MID-RUN — and §28f's exclusion rule would reject it BY OUTCOME

**Measured across all 14 health-arm trials, effective multiplier (trial `max_hp` / control `max_hp`) by
wave, large-HP cells only.** 13 of 14 are flat at nominal for every wave: H75 spans **0.745-0.756**,
H50 spans **0.489-0.505**.

**`f06_H75` is the sole exception.** It reads a correct **0.756 at w5**, then steps to
**0.823 / 0.826 / 0.825 / 0.828 at w6-w9** and holds — a clean **x1.10** step, mid-run, stable after.

What it is NOT, each checked:
- **Not the dial.** `difficulty_readback` for this trial reads `health: 0.75` — and all **35** trials'
  readbacks are exact. *Delivery was correct; the effect diverged. Delivery is not correctness.*
- **Not the fixture.** The same fixture's `f06_H50` is perfect (0.489-0.505 at every wave).
- **Not a purchased item.** I hypothesised `item_lost_duck` (bought at w5, and the w5 shop takes effect
  in w6 — the fit was **exact on 5 cells**). **REFUTED from the game's own data:** its effects are
  `stat_luck +10` and `stat_elemental_damage -1`. The literal `value = 10` is what made "+10%" feel
  right. ⇒ 23rd instance: *a correct measurement filed under the wrong mechanism.* Broader check: the
  `enemy_health` effect key exists on **difficulty tiers 3/4/5 and the Jack character only** — **no
  shop item can modify enemy health**, so no purchase explains this.

⛔ **MECHANISM UNRESOLVED.** It is characterised, not explained, and it is recorded that way.

⛔⛔ **THE ANALYSIS TRAP — §28f says "a trial that does not match its expected ratio is EXCLUDED and
reported." Applied literally here, that is a REJECT-BY-OUTCOME exclusion.** `f06_H75` received a
**WEAKER** effective dose (0.825 vs 0.75 — less help) and is the **shortest-surviving H75 trial**.
Dropping it removes that arm's worst run and **inflates H75's apparent effect** — the direction that
flatters the hypothesis. Sixth appearance of this class on this project.

⇒ **RESOLUTION — INTENTION-TO-TREAT IS PRIMARY** (17th instance's standing rule): the arm is assigned
from what was **configured and verified by dial readback**, never from how well the trial complied.
`f06_H75` **stays in the primary analysis.** A **per-protocol sensitivity** excluding it is reported
alongside, and if the two disagree that is reported as a finding rather than resolved in either
direction. Both n's are printed.

⚠️ Do not read the "weaker dose → worse outcome" coincidence as dose-response evidence. **n=1**, against
a within-arm sd of 1.590. It is an anomaly to disclose, not a result.

### ⚠️ DISCLOSURE — partial outcome exposure, and why it does not license a choice

While establishing trial cadence and validity on adoption I printed the raw per-trial series including
the `last_wave` column, so **I have seen terminal waves for the first 22 trials.** It changes no design
parameter — n is fixed at 8/arm, the stopping rule is not mine to influence, §28c/§28e predate all
data — but it does mean any *discretionary* analysis choice made from here is not blind. **That is
exactly why (i) resolves to "report both" rather than to a pick, and (ii) resolves to a rule fixed by
§28f's own prior text rather than to my judgement.** The watcher's progress line, which was printing
per-arm terminal-wave lists every 5 trials, has been changed to counts only so the channel is closed
going forward.

## §28h Cost

Control runs ~5-8 min (the gate's died at wave 8 in 320 s). Rescued arms run much longer — the gate's
`health 0.25` run exceeded 900 s without finishing. Estimated **~10-11 h** for 40 runs at a 2400 s cap.
A 3-arm screen (control, H50, D50; 24 runs, ~6 h) answers the qualitative dissociation at one dose per
dial but forfeits the slope comparison that makes the dials comparable.
