# WP2 v116 route-quality stop/repair report

Independent stewardship review, 2026-07-23. The v115 qualification is
**revoked** and the exact-20 campaign remains blocked pending a v116 smoke.

## Operator observation positively identified

The reported death through an enemy pack is the v112 qualification smoke
`run_1784763667_57757` (defeat, wave 20, four 23-damage hits between ts
1,122,104 and 1,146,474 ms). Its stop/repair report already recorded the
route as user-observed; replaying captures 20170-20185 confirms the emitted
action reversing direction nearly 180 degrees on consecutive 50 ms ticks
while wall recovery stayed latched and wall-selected body clearance (52-67)
sat far below the best sampled lane (121-154). That run is frozen, rejected
smoke evidence and was never dataset-eligible, so the observation does not
contradict the v115 victory — but re-examining v115 with fresh eyes exposed
a deeper defect the accepted audit could not see.

## Root cause: discrete clearance sampling hides fast crossings

Both clearance primitives evaluated threats only at fixed times
(`ESCAPE_TIME_SAMPLES = 6` over `ESCAPE_HORIZON = 0.60`, i.e. 120 ms steps;
body clearance additionally skipped t=0). Any threat crossing the player's
path between samples was invisible: at ~400 u/s relative speed the crossing
fits entirely inside one step. The audit mirrored the same formula, so gates
passed while behavior looked poor — precisely the reported symptom class.

Reproduced from immutable v115 smoke telemetry (`run_1784768114_34909`;
reproductions match recorded diagnostics to 6 decimals):

| Wave | Capture | Recorded clearance | True continuous minimum |
|---|---|---|---|
| 17 | 17447 | body 26.2 | -1.3 (contact) |
| 19 | 19180 | body 97.7 | 40.5 |
| 19 | 19293 | body 118.1 | 13.5 |
| 19 | 19557 | body 95.3 | -10.5 (contact) |
| 19 | 19817 | body 101.5 | 42.0 |
| 20 | 20479 | projectile 18.6 | 2.2 |
| 20 | 20505 | projectile 28.1 | 1.7 |
| 20 | 20563 | projectile 23.9 | 5.8 |
| 20 | 20790 | projectile 17.6 | 7.5 |

Wave 19: both 16-damage hits came from the same horned bruiser
(instance 446798) charging at ~940 u/s; its recorded velocity made the
closed-form closest approach contact at t≈38 ms, while the first evaluated
sample at t=120 ms already lay beyond the crossing. Wave 20: capture 20505's
emitted escape walked through a stationary radius-23 bullet at t≈56 ms; the
t=0 and t=0.12 samples both read ~28 units. At every wave-20 hit, sampled
values tied many lanes at identical numbers, so continuity/alignment bonuses
chose among apparently-equal lanes — sometimes the truly worst. Lanes with
materially better true clearance existed at all four wave-20 hits.

## Repair (policy v116, mod 0.2.24)

- `_predictive_body_path_clearance` and `_dir_clearance` now compute the
  continuous closest-approach minimum in closed form (relative motion is
  linear over the hold). Body clearance starts one decision interval out
  (`ESCAPE_CLEARANCE_MIN_TIME = 0.05`), preserving the shared-overlap
  contract while surfacing in-hold crossings; projectile clearance covers
  [0, horizon] as before. All call sites, tiers, and floors are unchanged.
- The safety audit uses the identical continuous formulas, adds
  damage-route gates that replay each damage event's emitted command
  against raw entity motion (flagging crossings when a hard-wall-safe
  sampled lane offered >= 20 more units without trading the other clearance
  family), and gains `--legacy-sampled-diagnostics` so frozen v107-v115
  evidence replays with parity while the new route gates still run.

## Verification

- Focused tests: 80 passed (audit, collector, source assertions), including
  frozen regressions for captures 19557 and 20505.
- Full suite: 126 passed.
- Offline replay: re-auditing the v115 smoke with the new gates
  (`reports/wp2/v115_smoke_safety_reaudit_v116.*`) rejects it with 3
  avoidable-damage violations (captures 20479, 20505, 20563); capture 20790
  misses the 20-unit relative-gain threshold by 1.1 units and is
  deliberately not chased. All legacy parity/tier checks remain clean,
  isolating the new defect class.

## Decisions and dataset status

- v115 smoke `run_1784768114_34909`: qualification revoked; retained as
  frozen, rejected smoke evidence. Never dataset-eligible (smoke).
- Dataset inclusion list: still empty. Exclusion list unchanged plus the
  v115 smoke.
- Next step: deploy v116 (`scripts/deploy_mod.py`), run one isolated
  qualification smoke under a new state/contract file, audit with the v116
  gates (no legacy flag), and only then start the exact-20 campaign.
- Known remaining limitation (documented, not blocking): the soft scoring
  integrals (`_finale_enemy_path_penalty`, `_predictive_enemy_path_penalty`,
  `_finale_lane_score` path loops) still sample discretely. They shape
  preferences, not safety floors; revisit only if v116 smoke evidence
  implicates them.
