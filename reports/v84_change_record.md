# v84 change record - conditional item scoring guardrails

- **Date:** 2026-07-22
- **Version:** `0.1.84-gun-wp1`
- **Scope:** narrow pre-campaign correction to v83; no movement, weapon, band-gate, RSI, HUD, or orchestration changes.

## Changes

1. `item_statue` is now `{"never": true}` in
   `BUILD_AWARE_ITEM_REQUIREMENTS`. Removing it from the late-wave allowlist was
   insufficient because the allowlist gate starts at wave 11. Statue's +40
   attack speed uses `temp_stats_while_not_moving`, while its -10 speed is
   unconditional; a continuously-kiting agent should never buy it.
2. `item_triangle_of_power` is demoted B -> C. Its +20% damage and +1 armor are
   unconditional, but its stacking -2% damage on hit is flattened into a single
   value by the current snapshot. It remains buyable without outranking clean
   offense.
3. `item_wisdom` is demoted A -> C. Its +5% stacking damage is conditional and
   its -20% damage is unconditional. The old A label was misleading even though
   the flattened net score already made purchases unlikely.
4. `item_honey` remains B. Direct extraction from the installed
   `C:\Games\Steam\steamapps\common\Brotato\Brotato.pck` found five effects:
   ranged damage +3, explosion damage +10, explosion size +5, speed -3, and
   dodge -3. Every effect has `custom_key = ""`; none is conditional.

The hard allowlist remains 98 wiki ids / 166 union ids. Build-aware
requirements increase from 58 to 59 because Statue is now an all-wave veto.

## Deferred systemic work

Carrying `custom_key` through `_effects_to_list` and discounting all
`temp_stats_*` effects remains queued for WP2 telemetry/scoring work. That
changes scoring semantics across every item and is intentionally outside this
narrow pre-campaign patch.

## Campaign evidence boundary

The v83 partial `run_1784644121_75697` was stopped at wave 6 and is excluded.
The v84 eight-run gate starts fresh with `-Runs 8 -MinWins 6` and uses the Step-1
acceptance criteria in `docs/ROADMAP.md`.

## Validation and deployment

- Focused policy tests: **36 passed**.
- Full suite: **65 passed** (rerun with a workspace-local pytest temp root after
  the Windows global temp directory returned `WinError 5`).
- Workshop and local archives: exactly 18 source files, no missing, extra, or
  mismatched entries; both SHA-256
  `D3F45BE7B2195859C0E179BE31D6225744DD880B9C22C8B4119F7741EB430C12`.
- Godot/ModLoader smoke: `Tom-BrotatoAgent.zip` loaded; `Init`, `Ready`, and
  `AgentController ready` logged with no post-start APPCRASH.
- Fresh gate run: `run_1784644704_49016`, policy
  `teacher_v1-0.1.84-gun-wp1`; initial telemetry healthy.
