# v85 change record - preserve boss engagement at low health

- **Date:** 2026-07-22
- **Version:** `0.1.85-gun-wp1`
- **Scope:** one focused movement repair after the operator-designated v84
  decision run; shop policy, item tiers, DPS bands, RSI, HUD, and orchestration
  remain unchanged.

## Evidence

v84 stopped at **2W/2L** after four completed runs. Both defeats reached wave
20 with estimated DPS well above the 2900 finale target:

- `run_1784646999_92668`: 5210 estimated DPS, survived the full sampled finale
  at 19 HP, but spent 74.2% of wave-20 ticks below the generic low-health flee
  threshold and did not clear the boss.
- `run_1784648190_6693`: 3942 estimated DPS, entered wave 20 at 13/59 HP, spent
  all 17 sampled seconds in the generic flee path, and died.

The generic wave-17+ survival override returned from `compute_movement` before
`_boss_finale_desire` could hold the boss at gun range. This matches the
operator's visual observation that the agent spent most of the first loss
avoiding threats instead of applying its available DPS.

## Single repair

The generic low-health panic/pure-repulsion override is now limited to waves
17-19. Wave 20 always uses the dedicated finale controller, which already:

- holds the nearest boss on the shortest-weapon range ring;
- strongly blends projectile escape by urgency;
- repels nearby adds and walls;
- prevents direct movement reversals; and
- commits to an escape lane until real displacement or timeout.

This is not a request to ignore danger at low HP. It removes a preemption bug
so the finale-specific controller can combine boss engagement with its existing
avoidance mechanisms.

## Evidence boundary and next gate

- v84 completed evidence: `run_1784644704_49016`,
  `run_1784645853_42564`, `run_1784646999_92668`, and
  `run_1784648190_6693`.
- The automatically started v84 partial `run_1784649311_52302` was stopped at
  wave 2 and is excluded.
- v85 uses a focused four-run gate with `-Runs 4 -MinWins 3`, retaining the
  Step-1 DPS, shop-exit, safety, HUD-parity, and item-behavior criteria.

## Validation and deployment

- Focused policy tests: **37 passed**.
- Full regression suite: **66 passed**.
- Workshop and local archives: 18 source files, no missing, extra, or
  mismatched entries; both SHA-256
  `C6B91E35C01F02003C3A84188F3C36AF5F83B679FA515C8F3C68ECB0FB00611C`.
- Godot/ModLoader smoke: archive loaded; `Init`, `Ready`, and
  `AgentController ready` logged with no post-start APPCRASH.
- Fresh focused gate: `run_1784649695_76233`, policy
  `teacher_v1-0.1.85-gun-wp1`; initial telemetry healthy.

## Focused gate outcome

v85 stopped at **0W/2L**, as required by the second-loss threshold. Both runs
used the dedicated finale controller for every sampled wave-20 tick, proving
the v85 preemption repair worked mechanically, but both died quickly:

- `run_1784649695_76233`: 4490 estimated DPS; 29.5-second finale; 45 HP down to
  a sampled minimum of 5.
- `run_1784650837_80690`: 5020 estimated DPS; 22.5-second finale; 54 HP down to
  a sampled minimum of 15.

The automatically started partial `run_1784651960_18420` was stopped at wave 1
and is excluded. v85 restored engagement but removed too much of the proven
low-health survival behavior; it is superseded by the balanced v86 repair.
