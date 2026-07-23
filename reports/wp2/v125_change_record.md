# WP2 v125 change record (DRAFT) — the ordering rule proper (hard reroll gate)

DRAFT — built on branch `wp2-combat-learning`, NOT deployed, NOT committed. No
game run, no ZIP rebuild. Supersedes the REJECTED v124
(`reports/wp2/v124_change_record.md`).

## Why v124 failed

v124 tried to enforce "buy the board offense item before rerolling" by stripping
the +8 offense-deficient reroll-worth boost. Smoke `run_1784817058_71742`
(`reports/wp2/v124_deploy_record.md`) proved that insufficient: **4
guard-applicable rerolls** still fired past an affordable gate-clearing offense
item — residual reroll worth cleared the (unboosted) bar on **paid** rerolls
(wave 11) and **free** rerolls bypass the worth check entirely (wave 15):

| decision seq | wave | reroll | gold | proxy/target | gate-clearing item(s) left on board |
|---:|---:|---|---:|---|---|
| 11315 | 11 | paid (12) | 342 | 53.5 / 95 | item_potato (gain 10, price 189) |
| 11319 | 11 | paid (20) | 314 | 53.5 / 95 | item_bait (8/57), item_cyclops_worm (12/94) |
| 16880 | 15 | free (0) | 403 | 79.3 / 257 | item_bait (8/69) |
| 16882 | 15 | free (0) | 403 | 79.3 / 257 | item_dynamite (15/58, explosive key) |

(Coordinator confirmed the v124 spec error was the design's, not the impl's.)

## The v125 rule (hard reroll gate)

While **offense-deficient** (`_offense_target(wave) > 0` and
`_offense_proxy(build) < _offense_target`) AND
`_board_has_gate_clearing_offense(items)` holds, the **reroll action is disallowed
outright — paid AND free**. Buy scoring and the reroll-worth computation are
untouched; the gate only denies the reroll return. If the buy loop then buys
nothing and the reroll is gated, the existing shop-exit proceeds (exiting with
gold beats losing the board — intended). The v124 +8-boost guard is kept as-is
(correct and cheap belt-and-braces).

## Implementation anchor (`teacher/shop_strategy.gd`, step 4 reroll branch)

A new boolean `offense_reroll_gate` is computed just before the reroll fires and
added as a conjunct to the fire condition (**`shop_strategy.gd:~1544-1550`**):

```
var offense_reroll_gate: bool = (offense_target > 0.0
        and _offense_proxy(build) < offense_target
        and _board_has_gate_clearing_offense(items))
if (best_here < worth or need_fill) and not offense_reroll_gate:
    _session_rerolls += 1
    return {"type": "shop_reroll", "score": best_here}
```

`offense_target` is the existing local (`var offense_target := _offense_target(
wave, build)`); `_board_has_gate_clearing_offense` is the unchanged v124 helper
(non-weapon, `affordable`+`can_buy`, `_direct_offense_gain >=
OFFENSE_IMPACT_MIN_ITEM_GAIN` 6.0; crit excluded by construction). No new config
constant, no gold_reserve change, no worth/scoring change. Scope: only the step-4
reroll branch (the branch that produced every smoke instance); the profile-specific
`shop_must_items` / `shop_must_tag` / weapon-fill rerolls are intentionally NOT
gated (those builds must keep searching for their target item).

## Versioning + full deploy surface (bumped together, per v124 commit `97aff20`)

policy `teacher_v1-0.1.124` -> **`teacher_v1-0.1.125-gun-wp1`**; mod
`0.2.32-wp2-capture` -> **`0.2.33-wp2-capture`**. All edited in-repo now:

- `runtime/agent_controller.gd`: `policy_version` (line 16) + `mod_version` meta
  (line 1641) `0.2.33-wp2-capture`.
- `telemetry/telemetry_writer.gd`: `POLICY_VERSION` (line 5) + default
  `mod_version` (line 37) `0.2.33-wp2-capture`.
- `manifest.json`: `version_number` `0.2.33`; description "v125 deterministic teacher".
- `scripts/wp2_collect_teacher.py`: collector identity gate `POLICY_VERSION` /
  `MOD_VERSION` `0.1.125` / `0.2.33`.
- `trainer/evaluation/live_monitor.py`: appended `"0.1.125"` to all 6 gated
  safety-check version tuples.
- Identity tests advanced: `test_shop_policy_source.test_wp2_capture_build_versions_...`
  (deployed-identity block -> 0.1.125 / 0.2.33) and
  `test_wp2_teacher_collector.test_summary_fault_accepts_clean_current_terminal_summary`
  (summary fixture -> 0.1.125 / 0.2.33).

## Deploy checklist (primary / operator — NOT done here)

Rebuild the mod ZIP, install to both workshop + game mod paths, isolated v125
smoke, zero-violation safety + capture audit, and a v125 deploy record. Verify
the schema hash is unchanged (no capture-schema change in v125).

## Frozen regression fixtures + tests

- `tests/fixtures/wp2/v124_smoke_reroll_boards_w11.json` and `_w15.json`:
  extracted from `run_1784817058_71742` telemetry (read-only). Each holds the two
  guard-applicable boards for its wave — full offer items (effects, prices,
  affordability, precomputed `direct_offense_gain`), `gold`, `reroll_price`,
  `reroll_kind` (paid/free), the recorded `action_taken` (`shop_reroll`), and the
  build's `offense_proxy_total` / `offense_target`. w11 = 2 paid rerolls
  (item_potato; item_bait+item_cyclops_worm); w15 = 2 free rerolls (item_bait;
  item_dynamite via the explosive key). Note: `offense_target` for w15 is the
  live-computed 257 (density-adjusted), vs. the deploy record's base-floor 145 —
  deficiency (79.3 < target) holds either way.
- `tests/unit/test_shop_policy_source.py` (additive):
  - `test_v125_reroll_gate_source_shape_denies_paid_and_free_rerolls` — pins the
    gate boolean, its presence in the fire condition, gate<fire<shop_go ordering,
    and the retained v124 +8-boost guard.
  - `test_v125_reroll_gate_decision_table_mirror` — pure-Python mirror: deficient
    + qualifying -> reroll disallowed (even free); deficient + none
    (empty/unaffordable/sub-gate/crit/weapon) -> allowed; adequate -> unchanged.
  - `test_v125_reroll_gate_replays_frozen_smoke_boards` — replays all four frozen
    boards through the mirror gate; asserts every one is reroll-disallowed, both
    budget regimes (paid+free) are covered, the explosive-key item is covered, and
    cross-checks the frozen `direct_offense_gain` / `gate_clearing_ids`.

## Test evidence

`.venv/Scripts/python -m pytest -q --basetemp=.tmp/pytest-basetemp`: see the
implementation report for exact counts (target: full green).

## Success metrics (unchanged from v124 design note)

- Defeat-run offense conversion 30% -> toward the 42% victory baseline.
- Fewer offense-deficient deaths at waves 17-20.
- **New primary check:** guard-applicable rerolls over gate-clearing boards = 0 in
  the v125 smoke (v124 had 4).

## QUALIFIED 2026-07-24

Smoke run_1784819688_85761 (defeat wave 16, weak-build RNG): zero safety
violations, clean capture audit (15,943), and the decisive rule evidence:
24 applicable rerolls with ZERO past a qualifying offense item, plus 10
gate-influenced correct decisions (4 mandatory-offense buys, 1 gated
shop-exit). Waves 11/15 reroll boards held no affordable gain>=6 offense
items (max <=1). ZIP CE15D87FFE420760180E5C322358DAEF65E9C6B23923E3BECECA3B08AD075AE0.
v126 refinement candidates (non-blocking): align the gate gain definition
with build-relevant scaling (w12 gated exit left off-build dynamite gain
15 unbought); wave-6 buy-selection preferred bat over statue gain 40
(outside this rule, pre-existing).
