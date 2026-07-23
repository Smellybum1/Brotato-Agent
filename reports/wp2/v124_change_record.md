# WP2 v124 change record (DRAFT) — mid-game offense conversion via reroll-boost guard

DRAFT — built on branch `wp2-combat-learning`, NOT deployed, NOT committed.
Implements the FINAL DESIGN v2 section of `.tmp/wp2_v124_design_note.md`
(OPERATOR-APPROVED 2026-07-23). Build/deploy only AFTER v123 qualifies. No
game run, no ZIP rebuild while Brotato.exe runs.

## Intent

Losing runs die offense-starved with gold banked — a waves-9-15 *conversion*
failure, not an allocation or threshold failure. v124 is ONE additive rule that
stops the offense-deficient reroll boost from rerolling past an affordable board
offense item that already clears the impact gate.

## Evidence

- `reports/wp2/v124_skip_diagnosis.md`: of the 118 skipped positive-gain offense
  offers in defeat runs (w9-15), the dominant fixable blocker is the offense-
  deficient reroll boost — **35/36 true board-leavings** were rerolled away
  (`deficient_but_rerolled_for_more_impact` = 35; only 1 left by shop-exit). The
  6.0 gate is exonerated: 64% (75/118) of skipped offers already cleared it, and
  `band_gate` is active in only 16/118 skips (structurally off below wave 13).
- `reports/wp2/v124_offer_dps_distribution.md` (offer distribution, per design note).
- Source anchors cited by the diagnosis: `shop_strategy.gd:1514-1518` (+8 boost),
  `:1525-1527` (reroll fires when `best_here < worth`) — pre-edit line numbers.

## The rule (single, additive)

While the existing offense-deficient / mandatory-offense condition holds at a
shop, if the current board holds an affordable offense-stat item that clears the
existing impact gate, that BUY must not be preempted by the reroll — equivalently
the offense-deficient reroll worth boost (+8) fires only when no such item remains
on the board. Normal scoring still picks WHICH item (item_score ordering is not
bypassed); the rule only removes the reroll's ability to jump the board.

No threshold change (6.0 exonerated), no gold_reserve change (gold-blocked skips
are median 60 short vs reserve 40 — untouchable without next-shop risk), no
engine/scoring change. The pinned v69/v74/v78 coefficient strings are untouched.

## Implementation anchors (`teacher/shop_strategy.gd`, post-edit)

- New helper `_board_has_gate_clearing_offense(items) -> bool` at **line 1046**.
  Reuses the EXACT mandatory-offense definitions: skips weapons, requires the
  existing per-item `affordable` + `can_buy` flags, and requires
  `_direct_offense_gain(effects) >= BotConfig.OFFENSE_IMPACT_MIN_ITEM_GAIN`
  (6.0). Crit is excluded by construction (`_direct_offense_gain` never counts
  `stat_crit_*`). No new config constant, no gold_reserve reference.
- Guard on the +8 boost at the reroll block: the existing
  `if offense_target > 0.0 and _offense_proxy(build) < offense_target:` gained a
  third conjunct `and not _board_has_gate_clearing_offense(items)` (**lines
  1531-1532**); the `worth += 8.0` value (line 1538) and the v80
  `worth += BotConfig.OFFENSE_BAND_REROLL_PRESSURE` line are preserved verbatim.
  Reroll still fires at `return {"type": "shop_reroll", "score": best_here}`
  (line 1547) — the guard is strictly upstream of it.

## Versioning (own bump only)

- `policy_version` bumped `teacher_v1-0.1.123-gun-wp1` -> `teacher_v1-0.1.124-gun-wp1`
  in both places: `runtime/agent_controller.gd:16` and `telemetry/telemetry_writer.gd:5`.
- `mod_version` (`0.2.31-wp2-capture`) and the manifest are NOT bumped here
  (deploy-time).

## Deploy checklist (primary / operator — NOT done in this task)

1. **mod_version -> `0.2.32-wp2-capture`** (`agent_controller.gd` mod_version dict;
   currently `0.2.31-wp2-capture`).
2. **manifest** `mod/mods-unpacked/Tom-BrotatoAgent/manifest.json`:
   `"version_number"` `0.2.31` -> `0.2.32`; description `v123` -> `v124`.
3. **live_monitor.py version tuples** (`trainer/evaluation/live_monitor.py`):
   append `"0.1.124"` to every gated safety-check tuple that currently ends at
   `"0.1.123"` (5 tuples at lines ~204, ~230, ~244, ~279, ~303, ~371 — all except
   the v48-58 zero-combine and v55-64 final-shop-combine tuples). This is the
   fix `test_v77_live_monitor_version_gates_cover_the_deployed_policy_version`
   requires — see Test evidence below.
4. **Collector identity gate** — update the accepted policy-version allowlist to
   admit `teacher_v1-0.1.124-gun-wp1`.
5. Rebuild ZIP, isolated v124 smoke, zero-violation safety + capture audit.

## Test evidence

`.venv/Scripts/python -m pytest -q --basetemp=.tmp/pytest-basetemp`:
**207 passed, 2 failed** (205 pre-existing + 2 new v124 tests).

New tests (`tests/unit/test_shop_policy_source.py`, additive):
- `test_v124_offense_deficient_reroll_boost_yields_to_board_offense_buys` — pins
  the helper's source shape (weapon skip, affordability, `_direct_offense_gain`
  vs `OFFENSE_IMPACT_MIN_ITEM_GAIN`), the guard conjunct on the +8 boost, the
  preserved v74/v80 lines, guard-before-reroll ordering, and the policy-version
  bump in both files.
- `test_v124_reroll_boost_decision_table_mirror` — pure-Python mirror of the rule:
  deficient + affordable gate-clearing item -> no boost; deficient + none
  (empty / unaffordable / sub-gate / crit-only / weapon) -> +8 boost; adequate ->
  unchanged regardless of board.

### Expected failures (deploy-time reconciliation — DO NOT paper over)

Both are the direct consequence of the mandated policy bump colliding with the
deploy-time edits this task is forbidden to make; both clear when the deploy
checklist above is applied (same pattern as v123, where the primary applied the
live_monitor edit):

1. `test_v77_live_monitor_version_gates_cover_the_deployed_policy_version` — reads
   the deployed policy (`0.1.124`) and requires it in the live_monitor tuples,
   which still end at `0.1.123`. Fixed by checklist item 3 (primary owns
   live_monitor.py).
2. `test_wp2_capture_build_versions_the_v122_crossing_tier_policy` — asserts the
   `0.1.123` policy literal and the `0.2.31` mod/manifest identity as a matched
   pair. Reconciles when the policy literal and mod/manifest are advanced together
   to `0.1.124` / `0.2.32` at deploy (checklist items 1-2).

## Success metrics (from the design note)

- Defeat-run offense conversion 30% -> toward the 42% victory baseline.
- Fewer offense-deficient deaths at waves 17-20.
- Reroll count at offense-deficient shops may drop (expected, benign).
