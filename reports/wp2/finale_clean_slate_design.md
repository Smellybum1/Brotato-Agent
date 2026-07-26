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
