# v86 change record - low-health finale balance and applied-DPS telemetry

- **Date:** 2026-07-22
- **Version:** `0.1.86-gun-wp1`
- **Scope:** one focused wave-20 movement balance plus non-behavioral boss
  telemetry required to verify whether estimated DPS reaches the boss.

## Evidence

v85 stopped at **0W/2L**. Its two runs used `_boss_finale_desire` for every
sampled wave-20 tick, so the earlier preemption bug was fixed, but they died in
29.5 and 22.5 seconds with 4490 and 5020 estimated DPS. v84's generic survival
path had produced two wave-20 victories but also one disengaged timeout. The
evidence brackets the desired behavior between pure survival and pure finale
engagement.

## Focused movement repair

- Above 85% HP, wave 20 is unchanged from v85: use the dedicated boss-range
  controller and its projectile/corner avoidance.
- At or below 85% HP, retain **55%** of the boss-range desire and blend **45%**
  of the existing panic-dodge/pure-repulsion direction.
- The result still passes through projectile urgency, reversal prevention,
  corner escape, and displacement commitment.

This preserves the operator-requested boss pressure while restoring enough of
the historically successful survival lane to avoid v85's all-or-nothing
over-correction.

## Applied-DPS telemetry

- Combat ticks now carry the player snapshot and live boss snapshots with
  absolute position, player-relative `nx`/`ny`, current HP, max HP, speed, and
  node name.
- Player-relative normalization now runs after all entity lists are populated;
  previously it ran before enemies, bosses, and projectiles existed, so the
  documented relative coordinates were never added.

This is compatible observability only; it does not alter scoring or control.
It supplies the first blocking telemetry slice from ROADMAP Step 3 and lets the
v86 finale report actual boss-HP change alongside estimated DPS.

## Evidence boundary and next gate

- v85 completed evidence: `run_1784649695_76233` and
  `run_1784650837_80690`.
- Excluded v85 partial: `run_1784651960_18420` (wave 1, no terminal summary).
- v86 uses a four-run gate with `-Runs 4 -MinWins 3` and stops on its second
  loss or any safety trigger.

## Validation and deployment

- Focused source/policy suite: **38 passed**.
- Full repository suite: **67 passed**.
- Both installed archives contain the exact 18 source files with no missing,
  mismatched, or extra entries; both have SHA256
  `81AC5D400B7767E0EE84D7D8AE77D8DAF6FE645D02EE74ADAFB3FCF459507613`.
- ModLoader smoke reached `Init`, `Ready`, and `AgentController ready`, with no
  post-start APPCRASH evidence.
- Fresh v86 runtime evidence began with `run_1784652432_11752` on policy
  `teacher_v1-0.1.86-gun-wp1`; telemetry was fresh and healthy, and raw combat
  ticks contained both the player snapshot and the boss array.
- The focused gate is active under exact tasks `BrotatoAgent-LiveMonitor-v86`
  and `BrotatoAgent-Supervisor-v86`.

## Focused gate outcome

v86 stopped at its second-loss threshold with **0 wins / 2 losses**:

- `run_1784652432_11752`: wave-20 defeat after about 22 sampled finale
  seconds. Boss HP fell from 29,250 to 17,252 (11,998 applied damage);
  median boss distance was 494 units and 91% of samples were within 700, but
  player HP fell to 8.
- `run_1784653555_21284`: wave-20 defeat after about 48 sampled finale
  seconds. Boss HP fell from 29,250 to 11,582 (17,668 applied damage);
  median boss distance was 502 units and 88% of samples were within 700, but
  player HP fell to 5.
- Excluded partial: `run_1784654708_29918` (wave 1, no terminal summary).

Terminal acceptance metrics:

- wins: **0/2 — fail**;
- median estimated DPS at wave 15: **1,846.658 — pass** (target 1,620);
- median estimated DPS at wave 18: **2,413.520 — pass** (target 2,400);
- wave-13–16 below-band shop exits with >400 unspent: **0 — pass**;
- errors / hangs / illegal actions / cycle-guard events: **0 / 0 / 0 / 0**;
- combine dispatches / confirmations: **16 / 16 — invariant preserved**;
- no Statue, Snowball, or Ice Cube purchases; Honey and Pumpkin were bought
  without a corresponding safety failure;
- isolated telemetry validation: **2/2 passed**; RSI remained diagnostic only
  (run RSI 109.2 and 97.1).

The result falsifies v86's 55% low-HP engagement balance: both agents applied
real boss damage and stayed in range, but neither created enough separation to
recover. v86 is superseded by the health-banded v87 repair.
