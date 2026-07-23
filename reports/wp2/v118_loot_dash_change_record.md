# WP2 v118 change record — opportunistic loot dash

## Trigger evidence

The v117 exact-20 campaign was halted after run 2/20. The operator directly
observed run 2 (`run_1784776602_32853`) starving: over-cautious movement left
accumulated currency uncollected, and the run died on wave 16 — anomalously
early — at 79% of the wave-15 DPS target with 30% of wave-11-15 captures at
the 50-material ground cap and 207 gold entering the wave-15 shop (baselines:
592-649). The economy comparison (`.tmp/wp2_economy_comparison.md`, 7 runs
v110-v117) shows the starvation is danger-conditional and high-variance, and
predates v116 (v115's ground-cap saturation was already 17-22% versus 0-10%
for v110 baselines). Runs 1-2 of the halted campaign are preserved; all v117
runs are excluded from the dataset.

## Mechanism

Under local density `_loot_attraction` returns zero outright
(`nearby >= PACK_DENSITY_SOFT`), per-pile corridor blockers veto piles
entirely, and the safety-selected sampled lanes score with no loot term. A
pressured agent therefore has literally zero collection influence exactly
when falling behind makes collection most valuable — a positive-feedback
starvation loop.

## Behavior (operator-directed): bounded dash-and-retreat

When ordinary attraction is density-suppressed and a substantial pile is
near, wait for a window, dash, collect, and hand control back to evasion —
accepting that it may cost a hit or two when the value justifies it. Not
reckless: hard-wall margins and projectile floors are never waived.

Implementation (`_apply_loot_dash` in potential_field.gd):
- Trigger: density suppression active; densest material cluster within 420
  units has >= 10 items; hp_ratio >= 0.5; corridor window verified with the
  continuous closest-approach body clearance (>= 45 over the dash duration)
  and, when bullets exist, the caution-scaled panic projectile clearance.
- Commit: <= 72 decision ticks (~1.2 s at 60 Hz), retargeting the live
  cluster; ends on arrival, pile collected, timeout, or HP dropping below
  80% of the floor; 180-tick (~3 s) cooldown between dashes.
- Safety: the dash desire passes the unchanged projectile / wall / body
  tail. During a dash the final body arbiter drops only the near-best pack
  preference tier to the 45-unit contact floor and keeps the dash route
  despite crowd penalty when floors are met. Survival branches and the boss
  finale drop any active dash unconditionally.
- Diagnostics: `loot_dash_active` recorded per capture (inside the
  free-form `contributions` object — capture schema hash unchanged).

## Audit

- `_required_body_floor` applies the 45-unit contact floor when
  `loot_dash_active` is set (emergency tier still dominates).
- Wall-body-relief gates skip dash captures (deliberate crowd acceptance).
- New `loot_dash_violations` family: episodes longer than 26 captures or
  dashes below 0.35 hp_ratio reject the run; `loot_dash_capture_count`
  reported per run.

## Verification

- Full suite: 133 passed (3 new tests: source assertions, dash floor
  semantics, dash duration/HP audit gates).
- Frozen-evidence regression: re-auditing the accepted v117 smoke under the
  v118 audit yields identical results (0 violations, 0 dash captures) —
  legacy runs are unaffected.

## Status

Policy `teacher_v1-0.1.118-gun-wp1`, mod `0.2.26-wp2-capture`. Requires a
one-run qualification smoke; the exact-20 campaign restarts fresh under
v118 only if every gate passes. Dataset inclusion list remains empty.
