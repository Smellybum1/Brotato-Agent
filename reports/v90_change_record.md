# v90 change record - tight evasive boss ring and contact override

- **Date:** 2026-07-22
- **Version:** `0.1.90-gun-wp1`
- **Scope:** increase firing uptime and dodge authority while bypassing stale
  displacement commitment during a boss charge.

## Evidence

v89 stopped at **0W/2L**. Both runs passed offense/economy and held the boss
near gun range, proving the post-projectile ring projection worked. They still
spent only 59–67% of sampled finales within 500, versus 76.5% in the prior
successful trace whose median boss distance was 422.

The damage traces separated the remaining hazards:

- run 1's lethal 23-damage hit occurred with the boss only 53 units away,
  showing displacement commitment held too long through a boss charge;
- run 2 took three consecutive 18-damage hits amid 21–30 projectiles at
  429–593 boss distance, showing the ring needed more lateral dodge speed.

## Repair

- tighten the low-health boss ring from 90% to 82% of shortest-weapon range;
- reduce ring deadband from 70 to 50 units and raise radial correction from
  1.35 to 1.75 so automatic fire remains continuous;
- raise tangential avoidance from 1.60 to 1.85 and the critical multiplier
  from 1.20 to 1.35;
- inside 180 units of the boss, bypass/reset displacement commitment and issue
  an immediate direct contact-escape vector.

No shopping, scoring, telemetry-schema, or pre-wave-20 behavior changes.

## Gate

Run a fresh four-result focused gate with `-Runs 4 -MinWins 3`, stopping on the
second loss or any established safety trigger. Exclude every pre-v90 and partial
run. Promotion criteria remain those in `docs/ROADMAP.md`.

## Validation and deployment

- Focused source/policy suite: **38 passed**.
- Full repository suite: **67 passed** using a fresh workspace-scoped pytest
  temp directory.
- Both installed archives contain exactly the 18 source files with no missing,
  mismatched, or extra entries. Both have SHA-256
  `40E1042F7C8BE7501103271EBD23D8686CE9BF99FF5B290203C0B5F1AE22A950`.
- ModLoader smoke reached `Init`, `Ready`, and `AgentController ready`, with no
  script/parse error or post-smoke APPCRASH.
- Fresh v90 runtime evidence began with `run_1784665860_63327` on policy
  `teacher_v1-0.1.90-gun-wp1`; telemetry was fresh and healthy.
- The focused gate is active under exact tasks `BrotatoAgent-LiveMonitor-v90`
  and `BrotatoAgent-Supervisor-v90`.

## Terminal gate outcome

v90 stopped at **0W/2L** after the second loss made the 3/4 gate impossible:

- `run_1784665860_63327`: defeat on wave 20; 20,399 sampled boss damage in
  41.5 seconds, minimum 2 HP, median boss distance 433;
- `run_1784667010_12860`: defeat on wave 20; 10,293 sampled boss damage in
  14.5 seconds, minimum 2 HP, median boss distance 462.

The auto-started `run_1784668130_87690` is excluded. Both exact v90 tasks were
disabled/stopped, their scoped process trees exited, and Brotato was stopped.
Isolated telemetry validation passed **2/2**; there were no errors, hangs,
illegal actions, combine mismatches, or post-start APPCRASH events.

The offense/economy diagnostics passed in aggregate: median last-shop estimated
DPS at waves 15/18 was **2,186 / 3,233** versus **1,620 / 2,400**, with zero
wave-13–16 below-band exits above 400 materials. RSI was 100.4/108.9 and remains
diagnostic only.

v90 achieved the intended tight ring—run 1 held a 433 median distance with
83.3% of samples inside 500—but the 180-unit contact threshold activated too
late. Lethal hit chains occurred while the boss closed through 337/349/296 and
407/202 units. Commitment was already reset at most hits, so the remaining
fault is the emergency threshold, not lane duration. v90 is superseded by v91.
