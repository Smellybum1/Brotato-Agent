# v91 change record - pre-contact boss-charge escape

- **Date:** 2026-07-22
- **Version:** `0.1.91-gun-wp1`
- **Scope:** begin the direct boss-charge correction early enough to prevent
  the measured contact/projectile hit chains.

## Evidence

v90 stopped at **0W/2L**, although its tighter ring produced the desired firing
geometry. Run 1 held a 433 median boss distance and stayed inside 500 for 83.3%
of samples. The losses were instead decided by late emergency activation:

- one hit chain occurred as the boss closed through 337, 349, and 296 units;
- the other occurred at 407 then 202 units within roughly 0.6 seconds;
- displacement commitment was already reset at most hit samples.

## Repair

Raise `BOSS_FINALE_CONTACT_ESCAPE_DISTANCE` from 180 to 320. This remains well
inside the roughly 400–450 firing ring, so the agent keeps firing while beginning
its direct outward correction before a boss charge reaches contact range.

No other movement scalar, shopping, scoring, telemetry-schema, or pre-wave-20
behavior changes.

## Gate

Run a fresh four-result focused gate with `-Runs 4 -MinWins 3`, stopping on the
second loss or any established safety trigger. Exclude every pre-v91 and partial
run. Promotion criteria remain those in `docs/ROADMAP.md`.

## Validation and deployment

- Focused source/policy suite: **38 passed**.
- Full repository suite: **67 passed** using a fresh workspace-scoped pytest
  temp directory.
- Both installed archives contain exactly the 18 source files with no missing,
  mismatched, or extra entries. Both have SHA-256
  `AB16A00D67E59912B933145CA4F1A5D656AB4E69574D99DED080F2EC4ED6124F`.
- ModLoader smoke reached `Init`, `Ready`, and `AgentController ready`, with no
  script/parse error or post-smoke APPCRASH.
- Fresh deployment proof: both exact watchdog tasks are enabled and running;
  Brotato started `run_1784668467_37211` on
  `teacher_v1-0.1.91-gun-wp1` / `0.1.91-gun-wp1` with fresh telemetry and no
  alerts. This run is the first eligible result in the focused v91 gate.

## Terminal outcome

Per the operator's stricter decision rule, v91 stopped after its first eligible
run lost; the remaining gate allowance was not spent.

- `run_1784668467_37211`: defeat on wave 20, with 3,722 estimated DPS against
  the 2,900 target and 50 starting HP.
- The boss took 19,321 / 29,250 damage in 30.5 sampled seconds. Median boss
  distance was 404; 75.8% of samples were within 500 and 98.4% within 700.
- Four 16-damage hits ended the run at 9 minimum HP. Three were sampled with
  the boss at approximately 350, 402, and 406 units; the remaining hit occurred
  at 665 units amid 16 projectiles.
- The 320-unit escape itself worked when reached: three of four samples inside
  320 commanded directly outward. The defect was activation outside the
  measured boss-charge envelope, not failure of the override.
- Wave-15/18 estimated DPS passed at 1,766 / 2,826-plus, there was no qualifying
  >400-material below-band shop exit, combines matched 6/6, and telemetry
  validation passed 1/1. RSI was 102.9 diagnostic-only.
- No errors, hangs, illegal actions, invariant failures, cycle-guard increase,
  or post-start APPCRASH occurred.

Both exact v91 watchdog tasks were disabled and their scoped process trees and
Brotato were stopped before v92 work began. No partial successor run is counted.
