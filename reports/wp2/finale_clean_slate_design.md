# Clean-slate finale controller — design note

**Status 2026-07-26: DESIGN, nothing implemented.** Operator direction: run the boss
wave at 60 Hz, strip the finale back to as few commands as possible, and iterate fast
against snapshot fixtures.

## Why a rewrite is the right shape here, not just a tuning pass

The finale currently carries **~22 `BOSS_FINALE_*` constants**: `RANGE_FRAC`,
`SPRING_K`, `STRAFE`, `ADD_REPEL`, `PROJ_CAUTION`, `PROJ_URGENCY_FLOOR`,
`PROJ_URGENCY_MULT`, four `RECOVERY_*`, two `CRITICAL_*`, `CONTACT_ESCAPE_DISTANCE`,
`RECOMPUTE_DIVISOR`, `ESCAPE_CONTINUITY`, `STRAFE_SWITCH_MARGIN`, `REVERSE_DOT`, and
three `COMMIT_*` — on top of the general movement layer beneath it. Each was added for
a real observed failure and validated by a single smoke plus internal audits. None was
ever validated against wave-20 survival, because nothing measured wave-20 survival.

**The architectural argument is stronger than the accretion argument.** The freezing
that `RECOMPUTE_DIVISOR` exists to suppress is *intrinsic to summing repulsion
vectors*: two symmetric projectiles produce opposing forces that cancel to zero, and
the agent sits still. Everything downstream — the rate throttle, the commitment
constants, the continuity and reverse-dot terms — is machinery to paper over that one
structural property.

A **heading-selection** controller has no such failure mode. Evaluate K candidate
directions and pick the best one; with two symmetric threats it *chooses one of the
two good escapes* instead of averaging them into a standstill. Remove the cancellation
and most of the machinery built to compensate for it becomes unnecessary — including,
plausibly, the rate throttle itself.

**That is what makes 60 Hz achievable rather than merely desirable.** The reason the
finale runs at 20 Hz is dead time bought to damp oscillation. If the oscillation is
gone by construction, the dead time is pure cost and can be deleted.

## The minimal controller

All the information needed is already in the capture stream, exactly:
- projectiles: `x, y, vx, vy, radius` — Predator projectiles travel a uniform 500 u/s
- boss: `x, y, vx, vy, radius, hp`
- player position; arena bounds; enemies with velocities

Because velocities are exact, **time to closest approach is closed-form** — the same
continuous-geometry primitive v116 introduced when discrete time-sampling was found to
be the systemic root cause of the v84-103 collapse. Do not reintroduce sampling.

Proposed core, three parameters instead of twenty-two:

```
for each of K candidate headings (K ~ 24-32):
    t_hit = min over threats of closed-form time-to-collision along that heading
    score = min(t_hit, HORIZON)                       # survival first
    tie-break by preferred boss range (keep weapons in range)
    + small bonus to the currently-held heading        # hysteresis, anti-chatter
pick argmax; run every 60 Hz tick
```

Parameters: `K`, `HORIZON`, `HYSTERESIS_BONUS`. Range preference reuses the existing
weapon-range value rather than adding a new constant.

Hysteresis replaces the five commitment/continuity constants with one term, and it is
the *right* place for anti-chatter: chatter in a selection method is a tie-breaking
problem, not a dead-time problem.

## Test protocol

**Fixtures.** `scripts/wp2_snapshot_collector.py` archives
`%APPDATA%/Brotato/<steamid>/run_v3_0.json` whenever a run reaches wave 19 or 20. That
file carries the full build and `bosses_spawn`, which **predetermines the wave-20
boss** — so each fixture has a known boss and a restartable build. Running now
alongside the champion bank; every bank run donates one.

**Overfitting is the main risk and it has a history on this project** — gates tuned to
a single observed death, and an audit threshold widened because "the v116 smoke died
with references at 140.7-151.1". Mitigations, all mandatory:
- evaluate on a **library** of fixtures spanning many builds, never one;
- **hold out** a fraction of fixtures never used during iteration;
- confirm any winner with **full runs** before shipping, since fixtures test wave 20
  only.

Note a property that makes this cleaner than it looks: the change is confined to
wave 20, so the distribution of builds *arriving* at wave 20 is unaffected by it.
Fixtures drawn from the current policy's trajectories remain representative.

**Internal control.** The Invoker's projectiles are 96.3% stationary; the Predator's
are 0% stationary at a uniform 500 u/s. A latency fix should therefore **improve
Predator outcomes and do little for Invoker**. If a variant improves both equally, the
mechanism story is wrong and the result should be distrusted.

**Per-trial metrics:** survived wave 20; hits taken; damage taken; time-to-kill boss;
and the freeze detectors — stationary fraction, direction-reversal rate, and net
displacement per unit path length. A controller that wins by standing still in a safe
pocket while failing to kill the boss must be visible as such.

## Sequence

1. Fixture library from the running bank (free).
2. Harness: restore a fixture, launch, run wave 20, record, repeat. Verify the game
   resumes from `run_v3_0.json` on launch, and that repeated restores draw fresh
   spawn RNG (varied draws on a fixed build is what we want).
3. Baseline the **current** finale stack on the library — required before any claim
   that a replacement is better.
4. Minimal controller behind a flag, at 60 Hz.
5. Add terms back only where they demonstrably earn their place on held-out fixtures.
6. Full-run confirmation through `docs/RELEASE_GATE.md` against the champion bank.

Step 3 is not optional. Without a fixture-measured baseline for the existing stack,
"the new one looks good" is the same evidence standard that produced the current mess.

---

# ADDENDUM 2026-07-26 — corrections from measurement and a code map

Everything above is the ORIGINAL design. Four of its premises are now known to be
wrong or incomplete. Read this before implementing any of it.

## 1. The freezing premise does not hold — the agent never stands still

The design's central argument is that the finale machinery exists to paper over
**vector-cancellation freezing** ("two symmetric projectiles ... cancel to zero, and
the agent sits still"), and that a heading-selection controller removes the failure
mode and with it the need for the rate throttle.

Measured over 40 fixture trials (`finale_baseline_0.1.128.md`): **`stationary_frac` =
0.000** and **`action_zero_frac` = 0.000**. The commanded vector is never zero and the
player is never stationary. The agent **oscillates** instead — reversal rate ~0.111
median at wave 20.

Further, oscillation is **not wave-20-specific**: per-wave reversal rate is ~0.00-0.01
through wave 9, then w17 0.269/0.102, w18 0.306/0.252, w19 0.380/0.258 against w20's
0.336/0.232 — and **waves 17-19 run at 60 Hz**. (Caveat: waves 1-19 recompute at 60 Hz
but capture at 20 Hz, so reversals there are subsampled and can alias.)

**Consequence:** the "remove the cancellation and most of the machinery becomes
unnecessary" argument cannot be leaned on. A heading-selection controller may still be
better, but it must be justified by measured survival on fixtures, not by removing a
failure mode that is not occurring.

## 2. "~22 BOSS_FINALE_* constants" is wrong — there are 39

Exact: `grep -c "^const BOSS_FINALE_" teacher/config.gd` = **39**, lines 116-204.

## 3. The `BOSS_FINALE_` PREFIX IS MISLEADING — most of it is NOT wave-20 code

Verified at `potential_field.gd:256-273`:

- `_finale_projectile_safety` and `_finale_wall_safety` run at **`wave >= LATE_SURVIVAL_WAVE` (17)**, not 20.
- `_finale_body_safety` runs on **EVERY COMBAT WAVE** (v114, after the v113 smoke
  exposed a wave-12 pack-route failure).

So only the wave gate/throttle, `PROJ_CAUTION`, `PROJ_URGENCY_*`,
`CONTACT_ESCAPE_DISTANCE`, `REVERSE_DOT` and the `COMMIT_*` family are genuinely
wave-20-exclusive. **"Strip the finale back" would change waves 1-19.**

## 4. THE SEAM, AND WHAT A REPLACEMENT SILENTLY LOSES

Narrowest seam leaving waves 1-19 byte-identical: **`agent_controller.gd:330-333`**,
inside the existing `if wave >= BOSS_FINALE_WAVE` region. It also owns the throttle
(`:325-327`), so 60 Hz is expressible there and NOT at a potential_field seam.

But `compute_movement` owns the whole safety tail, so a replacement at that seam
**bypasses all of it**. What is lost, in descending order of how quietly it fails:

1. **THE AUDIT SURFACE.** The three audits replay the emitted action against
   `teacher.contributions.finale_translation`, produced by `finale_translation_debug()`
   (`potential_field.gd:1299`). A replacement that does not populate that dict makes
   every finale audit **vacuous or failing** — and "0 violations" is how qualification
   is currently earned. This is the same shape as the `can_buy` defect: a check that
   silently stops checking. **Any replacement MUST emit an equivalent debug contract.**
2. **The 45-unit contact floor** (`BOSS_FINALE_BODY_CRITICAL_CLEARANCE`), explicitly
   never modulated, and currently applied on every wave — so wave 20 would lose a
   floor that wave 1 keeps.
3. **The unconditional hard wall projection** (`_clamp_finale_wall_components`,
   `:501-534`), applied twice around renormalization. Only guard against the corner
   traps that motivated v93/v96/v110.
4. **Latched wall recovery** (280 enter / 520 release hysteresis).
5. **`_prev_move` goes stale** if `compute_movement` is never called at wave 20, so any
   mid-wave fallback to the old controller resumes from a stale vector.

## 5. 60 Hz MUST NOT CHANGE THE CAPTURE RATE

`agent_controller.gd:344-345` sets `emit_capture = recompute_move` on finale waves.
If a 60 Hz controller recomputes every tick, **captures would also go to 60 Hz**,
tripling wave-20 capture volume and changing `control_dt_ms` from ~50 ms to ~16 ms.
The dataset and the student path are fixed at 20 Hz (`control_dt` and prev-action are
model inputs). **Decouple these: recompute at 60 Hz, keep emitting at 20 Hz.**
Note `tests/unit/test_wp2_teacher_safety_audit.py::test_v117_nonfresh_finale_captures_reject_the_run`
rejects runs whose wave-20 captures are not on recompute ticks — at 60 Hz "fresh"
changes meaning and that audit needs a deliberate decision, not an incidental one.

## 6. ~120 verbatim source-string pins will resist the edit

`tests/unit/test_shop_policy_source.py` (misleading name) carries the finale source
pins at lines 517-1510: exact constant declarations with values, substring COUNTS,
`.index()` orderings, and **negative pins** asserting `BOSS_FINALE_RANGE_FRAC`,
`BOSS_FINALE_SPRING_K`, `_boss_finale_desire` etc. are ABSENT. Per
`[[brotato-gdscript-parse-gap]]`, such pins assert presence, not validity, and have
previously pinned a fatal bug as a requirement. Expect to update them deliberately and
ask, for each, whether it pins a MECHANISM or an OUTCOME.

## 7. Flee-mode characters never reach the finale throttle

`agent_controller.gd:316-322` applies a 30 Hz flee throttle that early-returns before
the wave check. Irrelevant for `well_rounded`, but do not assume the finale path is
universal.
