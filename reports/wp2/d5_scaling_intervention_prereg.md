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

**Fixtures: 8 distinct wave-1 D5 mutant snapshots.** Harvesting is cheap (~1 min each; the gate's
snapshot was captured 20 s after launch). Distinct snapshots carry distinct predetermined
`bosses_spawn` and RNG streams, which is the generalisation unit — memory's standing rule is to spend
budget on **more fixtures, not more repeats**.
⚠️ Wave-1 builds are far more homogeneous than the w17 fixture library, so between-fixture variance
will be smaller here and pairing buys less than it does at wave 17. Pairing is still used; it cannot hurt.

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

**Per-trial dose readback — the manipulation check.** Every trial's per-entity `max_hp` is compared to
the arm's expected ratio. A trial whose readback does not match its assigned dose is **excluded and
reported**, not silently kept. *A self-report proves delivery, never correctness.*
⚠️ Read the **LARGE-HP** types (bruiser, horned_bruiser, healer); small-HP types deviate by integer
rounding alone.

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

## §28h Cost

Control runs ~5-8 min (the gate's died at wave 8 in 320 s). Rescued arms run much longer — the gate's
`health 0.25` run exceeded 900 s without finishing. Estimated **~10-11 h** for 40 runs at a 2400 s cap.
A 3-arm screen (control, H50, D50; 24 runs, ~6 h) answers the qualitative dissociation at one dose per
dial but forfeits the slope comparison that makes the dials comparable.
