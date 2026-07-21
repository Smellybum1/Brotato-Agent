# v89 change record - post-projectile finale ring guard

- **Date:** 2026-07-22
- **Version:** `0.1.89-gun-wp1`
- **Scope:** preserve the boss-range ring after projectile-escape blending.

## Evidence

v88 stopped at **1W/2L**. Its ring controller materially improved applied boss
damage, but the two losses still died at 7 HP. The closer loss applied 26,282
sampled damage and left only 2,968 boss HP.

The remaining defect is ordering. v88 projects the generic low-health survival
direction onto the boss-ring tangent, then the later projectile-escape sampler
blends a new full direction over it. In the two losses, 8/11 and 7/9 low-HP,
out-of-range samples had active projectile pressure; movement was equally
likely to continue away from the boss as return toward it. Below 50% HP, median
boss distance expanded to 636 / 738 and damage application collapsed.

## Repair

After projectile blending, v89 reuses `_boss_finale_recovery_desire` to project
the blended safe direction back onto the boss-range ring before reversal,
corner, and displacement-continuity guards. Projectile avoidance still chooses
the safer orbit tangent; it can no longer restore a radial disengagement.

No shopping, scoring, telemetry-schema, healthy-finale, or pre-wave-20 behavior
changes.

## Gate

Run a fresh four-result focused gate with `-Runs 4 -MinWins 3`, stopping on the
second loss or any established safety trigger. Exclude every pre-v89 and partial
run. Promotion criteria remain those in `docs/ROADMAP.md`.

## Validation and deployment

- Focused source/policy suite: **38 passed**.
- Full repository suite: **67 passed** using a fresh workspace-scoped pytest
  temp directory.
- Both installed archives contain exactly the 18 source files with no missing,
  mismatched, or extra entries. Both have SHA-256
  `838AD682E10E07F0D69C49A3ED1E4F3ED10C4AFC8FBAC55AB7F8DBB3F192FAAC`.
- ModLoader smoke reached `Init`, `Ready`, and `AgentController ready`, with no
  script/parse error or post-smoke APPCRASH.
- Fresh v89 runtime evidence began with `run_1784663164_93060` on policy
  `teacher_v1-0.1.89-gun-wp1`; telemetry was fresh and healthy.
- The focused gate is active under exact tasks `BrotatoAgent-LiveMonitor-v89`
  and `BrotatoAgent-Supervisor-v89`.

## Terminal gate outcome

v89 stopped at **0W/2L** after the second loss made the 3/4 gate impossible:

- `run_1784663164_93060`: defeat on wave 20; 16,468 sampled boss damage in
  24.0 seconds, minimum 12 HP, median boss distance 470;
- `run_1784664267_21814`: defeat on wave 20; 16,683 sampled boss damage in
  15.5 seconds, minimum 3 HP, median boss distance 480.

The auto-started `run_1784665381_74388` is excluded. Both exact v89 tasks were
disabled/stopped, their scoped process trees exited, and Brotato was stopped.
Isolated telemetry validation passed **2/2**; there were no errors, hangs,
illegal actions, combine mismatches, or post-start APPCRASH events.

The offense/economy acceptance diagnostics passed: median last-shop estimated
DPS at waves 15/18 was **3,254 / 4,692** versus **1,620 / 2,400**, with zero
wave-13–16 below-band exits above 400 materials. RSI was 112.3/112.9 and remains
diagnostic only.

v89 successfully removed the radial disengagement: its median boss distances
were 470/480 and 87.5–98% of samples stayed within 700. The remaining failures
were a 23-damage boss-contact hit at 53 range while displacement commitment was
active, and three consecutive 18-damage projectile hits amid 21–30 projectiles.
v89 therefore fails Step 1 on wins and is superseded by v90.
