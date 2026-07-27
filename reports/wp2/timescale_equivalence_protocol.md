# Pre-registration — does `time_scale = 8.0` change OUTCOMES?

**Committed BEFORE trial 1.** Build: mod `0.2.49-wp2-capture`, policy `0.1.129`,
installed zip verified equal to the repo's identity constants at protocol time.

## The question

Acceleration's INTERNAL checks already pass at every scale: captures per
game-second 20.0 at 1x/4x/8x, orbiter velocity scale-invariant, burst speed
exactly 500. None of that shows the OUTCOME distribution is unchanged — game
logic may have timing paths on `_process` rather than `_physics_process`.

Until this is settled, acceleration is a dev convenience. If it passes, campaigns
run ~8x faster; if it fails, real campaigns run at 1.0x and nothing else changes.

## Design

- 8 fixtures (predator), 2 rounds, both arms per round: **32 trials = 16 pairs**.
- A **pair** is (fixture, round): one 1.0x trial and one 8.0x trial.
- Pairing is not optional — between-fixture SD (20.7) is larger than
  within-fixture SD (18.8); see `reports/wp2/campaign_sizing.md`.
- Driver `scripts/wp2_timescale_equivalence.sh`, out `.tmp/ts_equiv/`.
- The 16 partial trials in `.tmp/partial_ts_equiv/` are **QUARANTINED** — not
  analysed, not pooled, not used to calibrate anything in this protocol.

## Primary outcome

**`damage_taken`, paired difference (fast − slow).**

Win rate is NOT the primary and cannot be: the shipped pivot fix pins victory at
1.000 on these fixtures, so it cannot discriminate at any n.

**Equivalence margin Δ = 19 damage** — the smallest effect a 32-trial screening
campaign can resolve. The margin is set to the resolution of the campaigns
acceleration would be used for: if acceleration shifts damage by less than the
smallest effect those campaigns could detect, it cannot manufacture or mask one.
Attainability check (this is what makes the test non-vacuous): with within-fixture
SD 18.8 and 16 pairs, the expected 95% CI half-width is ~14 < 19, so a true zero
difference CAN land inside the margin.

## Decision rule (fixed now)

Let `CI` = 95% confidence interval on the mean paired difference (paired t,
n = 16), with a bootstrap percentile CI reported alongside as a robustness check.

| verdict | condition | consequence |
|---|---|---|
| **EQUIVALENT** | `CI ⊂ [−19, +19]` **and** `0 ∈ CI`, all structural gates pass | acceleration approved for campaigns |
| **SMALL SHIFT** | `CI ⊂ [−19, +19]` but `0 ∉ CI`, all gates pass | approved for **paired same-scale campaigns only**; never pooled with 1.0x data or compared against archived 1x baselines |
| **INCONCLUSIVE** | `0 ∈ CI` but CI extends beyond ±19 | one pre-registered escalation, below |
| **FAIL** | any structural gate fails, **or** CI lies wholly outside [−19, +19] | acceleration stays a dev convenience; real campaigns run at 1.0x |

**Pre-registered escalation (declared now, so it is not optional stopping):**
in the INCONCLUSIVE branch only, exactly ONE extension to 32 pairs (64 trials)
is permitted, appending 2 further rounds. The rule at 64 is the same table with
the same Δ = 19. No second extension, in any branch.

## Structural gates — any failure is a FAIL regardless of the damage CI

**G1 — acceleration actually took effect.** A config field's self-report is not
evidence. `duration_ms` comes from `OS.get_ticks_msec()`, which is REAL time and
is not scaled, so the same game content must complete in ~1/8 the real time:
median `n_captures / duration_ms` for the fast arm ÷ the slow arm must fall in
**[6.5, 9.5]**. This is a signature the slow arm structurally cannot produce.

**G2 — trial validity.** ≥ 14/16 valid in EACH arm; every valid trial has wave
set exactly `[20]` and one boss path, boss `predator`.

**G3 — build identity.** Every trial: `finale_pivot_projectiles == true`,
`mod_version == 0.2.49-wp2-capture`, `policy_version == 0.1.129`.
[**Corrected post-hoc, factual not substantive:** the field carries the full
string `teacher_v1-0.1.129-gun-wp1`. The expected VALUE was written wrong here;
the gate's intent — the deployed policy must be 0.1.129 — is unchanged, and the
observed value satisfies it on all 32 trials.] The repo is
FROZEN for the run — no edits to `MOD_VERSION`, `manifest.json`, or
`wp2_collect_teacher.MOD_VERSION`, and no deploy.

**G4 — no dead rounds.** Both arms produce ≥ 1 valid trial in every round; the
driver aborts on an empty round rather than logging and continuing.

## Reported but NOT decisive

Victory rate (pinned at the ceiling, underpowered), boss TTK, capture counts,
wall-clock per trial. **One exception with teeth:** if the fast arm records
**≥ 3 more losses** than the slow arm, escalation to 64 is MANDATORY regardless
of the damage CI — win rate can only move downward from 1.000, so that is the
one direction in which a ceiling-pinned metric carries information.

## AMENDMENT — ambiguities closed BEFORE any outcome data was read

Writing the evaluator against this protocol exposed six places where the rule
above did not determine an answer. All six are closed here **while the campaign
is still running and before a single result has been looked at**, so this is
specification, not tuning. The original text above is left unedited.

**A1 — the decision table was not exhaustive.** A CI like `[+10, +25]` is neither
wholly inside nor wholly outside `[−19, +19]` and matched no row. The table is
replaced by these five mutually exclusive, exhaustive rules, evaluated in order:

1. any structural gate fails → **FAIL**
2. CI lies wholly outside `[−19, +19]` → **FAIL**
3. `CI ⊂ [−19, +19]` and `0 ∈ CI` → **EQUIVALENT**
4. `CI ⊂ [−19, +19]` and `0 ∉ CI` → **SMALL SHIFT**
5. otherwise (the CI straddles a margin boundary) → **INCONCLUSIVE**

**A2 — pairs, not per-arm counts, set the precision.** G2 is per-arm, so both arms
could pass at 14/16 while only 12 pairs survive; the Δ = 19 attainability
calculation assumed 16 pairs. New gate **G5: at least 14 pairs must form.** Fewer
than 14 → **INCONCLUSIVE** (not FAIL — it is a precision shortfall, not a
validity break), eligible for the single pre-registered escalation.

**A3 — G2's boss check.** Read as: every valid trial has `len(boss_paths) == 1`
**and** `boss_entity == "predator"`.

**A4 — boss TTK is struck from the report.** The trial row carries no boss-death
timestamp; `duration_ms` is whole-trial real time. It was listed in error. Do not
substitute a proxy — it is non-decisive either way.

**A5 — the loss clause outranks the damage CI.** If the fast arm records ≥ 3 more
losses than the slow arm, the verdict is **INCONCLUSIVE with mandatory
escalation**, overriding EQUIVALENT or SMALL SHIFT. "Regardless of the damage CI"
means what it says: a ceiling-pinned metric moving downward is the one signal
that does not need the CI's permission.

**A6 — arm identity is cross-checked, not assumed.** The evaluator takes the arm
from the file argument; it must additionally assert that every row in the slow
file has a `label` beginning `ts_slow` and every row in the fast file `ts_fast`,
and abort loudly on any mismatch. A file passed to the wrong flag would otherwise
invert the sign of the entire result silently.

## Reporting

The verdict report prints the **raw 16-pair table** (fixture, round, slow damage,
fast damage, difference), not only the summary statistics. Per
`brotato-measurement-discipline`, a load-bearing number gets its raw series shown.
