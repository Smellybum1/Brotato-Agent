# v92 change record - boss-charge envelope floor

- **Date:** 2026-07-22
- **Version:** `0.1.92-gun-wp1`
- **Scope:** begin the existing direct outward boss correction outside v91's
  measured lethal charge envelope while preserving gun-range pressure.

## Evidence

v91's only eligible run, `run_1784668467_37211`, entered wave 20 with 3,722
estimated DPS and dealt 19,321 boss damage in 30.5 sampled seconds. It held a
404 median boss distance and kept the boss within 500 for 75.8% of samples, so
the firing-ring repair was working. It nevertheless died after four 16-damage
hits. Three were sampled with the boss at roughly 350-406 units. At 300 boss
speed, the 320-unit emergency floor did not provide enough pre-contact margin.

The existing override behaved correctly once inside 320: three of four samples
commanded directly outward. This isolates the activation distance rather than
the override direction, shopping policy, or boss-range controller.

## Repair

Raise `BOSS_FINALE_CONTACT_ESCAPE_DISTANCE` from 320 to 420. This is just beyond
the observed 406-unit lethal envelope and remains inside the live shortest-gun
range for the measured build. No other movement scalar, shopping or scoring
policy, telemetry schema, or pre-wave-20 behavior changes.

## Validation and deployment

- Isolated v91 telemetry validation: **1 passed / 0 failed**.
- Focused source/policy suite: **38 passed**.
- Full repository suite: **67 passed** using fresh basetemp
  `.tmp/pytest-v92-20260722-073944`.
- ModLoader smoke: **1/1**, reaching `Init`, `Ready`, and
  `AgentController ready` with no script/parse error.
- Both installed archives contain exactly the 18 source files with no missing,
  mismatched, or extra entries. Both have SHA-256
  `A0911C7F56BA8233C48E3B5D60AB4F4AFF4BD00FA2E5FAD070CAC5AA2DFAA639`.
- Fresh v92 runtime proof: both exact v92 watchdog tasks are enabled and
  running; Brotato started eligible run `run_1784670237_52694` on
  `teacher_v1-0.1.92-gun-wp1` / `0.1.92-gun-wp1` with fresh telemetry,
  severity OK, and no alerts.

## Gate

Run a fresh four-result focused gate with `-Runs 4 -MinWins 3`. Per the current
operator instruction, the first active v92 loss is itself a repair decision;
otherwise complete the gate and stop on a later second loss or any established
safety trigger. Exclude every pre-v92 and partial run.

## Terminal outcome and operator promotion

The first eligible v92 decision run, `run_1784670237_52694`, won. The operator's
explicit branch was: repair and redeploy if this run failed; if it succeeded,
advance to the next roadmap part. The win therefore ends the live repair loop
and promotes v92 as the WP2 teacher candidate without claiming that the planned
3/4 statistical gate was completed.

- Result: victory, wave 20.
- Estimated DPS: 2,510.59 at wave 15 and 3,784.59 at wave 18, above the
  1,620 / 2,400 acceptance bands.
- Economy: no wave-13-16 below-band shop exit with more than 400 unspent.
- Boss application: 29,250 maximum HP, 505 HP last sampled, and 28,745 sampled
  damage over 33.0 seconds.
- Geometry: 506.8 median boss distance; 17.9% at or inside 420, 46.3% at or
  inside 500, and 86.6% at or inside 700. Inside 420, 10 movement samples were
  outward and 2 inward.
- Survival/safety: minimum player HP 27, two wave-20 damage events, 9/9 combines,
  zero errors, hangs, illegal actions, cycle-guard events, or post-start
  APPCRASH evidence; telemetry complete.
- Policy checks: no Statue, early Snowball, or early Ice Cube purchase. Honey
  and Pumpkin were not offered in this run.
- Validation: isolated telemetry validation passed 1/1. RSI was 112.2
  (diagnostic only; wave-15 RSI 113).

The exact v92 tasks, their scoped command/Python process trees, and Brotato were
stopped after the win. The automatically started partial successor
`run_1784671380_41100` is excluded, as are safeguard-exercise partial runs
`run_1784671580_93166` and `run_1784671796_43736`. The successor overwrote the
live monitor snapshot, so terminal HUD-vs-`build_metrics` parity for the winning
run is not independently recoverable; source formatting assertions remain
green, but this one runtime criterion is recorded as unavailable rather than
inferred.
