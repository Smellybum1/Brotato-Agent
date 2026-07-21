# v88 change record - ring-preserving finale recovery

- **Date:** 2026-07-22
- **Version:** `0.1.88-gun-wp1`
- **Scope:** replace v87's low-health direction blend with a dedicated
  boss-range recovery controller.

## Evidence

v87 stopped at **1W/2L**. All three complete runs passed telemetry validation
and the Step-1 offense/economy checks; the blocker remained wave-20 movement.
The two losses applied 15,075 and 17,884 sampled boss damage, but reached 7 and
9 HP. The victory proved the build can finish the boss when movement survives.

The decisive defect was directional: v87 blended the complete generic
panic/repulsion vector into the boss controller. At low health, that vector
often pointed radially away from the boss, producing range excursions and
interrupted damage. The operator independently observed the same behavior: the
agent had ample DPS but spent too much of the fight avoiding rather than holding
gun range.

## Repair

Above 85% HP, the existing boss controller is unchanged. At or below 85% HP:

- the radial component is dedicated to a spring around 90% of the shortest
  weapon's maximum range, with a 70-unit deadband;
- panic/pure-repulsion is projected onto the tangent of that ring, so it selects
  the safer orbit side without dragging the agent out of range;
- critical health increases tangential motion by 20%;
- the existing projectile sampler, reversal prevention, corner escape, and
  displacement commitment still run afterward.

This keeps automatic fire applied while converting threat avoidance into orbit
choice rather than disengagement.

## Gate

Run a fresh four-result focused gate with `-Runs 4 -MinWins 3`, stopping on the
second loss or any established safety trigger. Exclude all pre-v88 and partial
runs. Promotion criteria remain those in `docs/ROADMAP.md`.

## Validation and deployment

- Focused source/policy suite: **38 passed**.
- Full repository suite: **67 passed** (using a fresh workspace-scoped pytest
  temp directory after the global Windows temp directory rejected access).
- Both installed archives contain exactly the 18 source files with no missing,
  mismatched, or extra entries; both have SHA-256
  `AA7D4ECCA78E2383C3408BEF83C997AC1F3F66597EE642858FDD77D749D7C171`.
- ModLoader smoke reached `Init`, `Ready`, and `AgentController ready`, with no
  script error or post-start APPCRASH.
- Fresh v88 runtime evidence began with `run_1784659157_63590` on policy
  `teacher_v1-0.1.88-gun-wp1`; telemetry was fresh and healthy.
- The focused gate is active under exact tasks `BrotatoAgent-LiveMonitor-v88`
  and `BrotatoAgent-Supervisor-v88`.

## Terminal gate outcome

v88 stopped at **1W/2L** after the second loss made the 3/4 gate impossible:

- `run_1784659157_63590`: defeat on wave 20; 19,897 sampled boss damage in
  27.5 seconds, minimum 7 HP, median boss distance 527;
- `run_1784660301_1872`: victory on wave 20; 31,448 sampled boss damage in
  8.0 seconds, minimum 57 HP, median boss distance 422;
- `run_1784661425_40940`: defeat on wave 20; 26,282 sampled boss damage in
  28.5 seconds, minimum 7 HP, median boss distance 506, leaving only 2,968
  sampled boss HP.

The auto-started `run_1784662567_68076` is excluded. Both exact v88 tasks were
disabled/stopped, their scoped process trees exited, and Brotato was stopped.
Isolated telemetry validation passed **3/3**; there were no errors, hangs,
illegal actions, cycle/invariant failures, or post-start APPCRASH events.

Acceptance diagnostics were healthy except for wins: median last-shop
estimated DPS at waves 15/18 was **3,068 / 5,475** versus **1,620 / 2,400**;
there were zero wave-13–16 below-band exits above 400 materials; Honey and
Pumpkin were purchased when offered; Statue, Snowball, and Ice Cube were not
purchased. RSI separated this tiny sample (win 115.4; losses 111.2/114.1) but
remains diagnostic only. v88 therefore fails Step 1 solely on the required
win count and is superseded by v89.
