# v66 deployment record

- **Date:** 2026-07-20 (Australia/Brisbane), deployed ~14:3x by Claude (Fable), under the operator's one-time edit-and-redeploy authorization.
- **Version:** `0.1.66-gun-wp1` / policy `teacher_v1-0.1.66-gun-wp1` (bumped in `manifest.json`, `runtime/agent_controller.gd` ×2, `telemetry/telemetry_writer.gd` ×2).
- **Superseded gate:** v65 stopped at **3W/2L after 5 runs** (defeats: wave 9 `run_1784517601_71472`, wave 17 `run_1784518010_84533`). With both loss slots spent it needed 15 straight wins (~21% pass chance even at a true 90% win rate). Run 6 was killed mid-run; its orphan run dir (no summary.json) is expected.

## Changes in v66

1. **Below-target max-HP valuation floor** (`teacher/shop_strategy.gd`, `_late_shop_pivot_bonus`) — the one policy-dimension change:
   - Early (pre-wave-12, max_hp < 55): HP effect weight 0.55 → **1.15**.
   - Mid (waves 12–14, max_hp < 90): 0.85 → **1.35**.
   - Late weights (1.25/<110) unchanged. Applies to shop items, level-ups (since v62), and crates.
   - Evidence: across 27 v63–v65 gate runs, bought-HP at wave 9 is the strongest win/loss discriminator (wins +12.2 vs losses +0.5, d≈2.1; d≈1.45 at wave 12); losses' stat budgets leaked into crit/luck/regen instead.
2. **Crate weapons no longer auto-discarded** (`runtime/agent_controller.gd`, `_handle_crate_overlay`): the crate item dict now carries `weapon_id`, `sets`, `is_healing` mirroring shop entries. Previously `_weapon_matches_allowlist` saw an empty `sets` array and discarded **every** crate weapon.
3. **Combine-confirmation timeout now releases the shop barrier** (`runtime/agent_controller.gd`): after the one-shot `shop_combine_confirmation_timeout` telemetry + mouse-mode restore, pending-combine state is cleared so `shop_go` remains reachable. Previously a silently-failed combine soft-locked the shop forever (reachable in the wave-19 shop since v65). The visit's combine budget is already spent at dispatch, so no second combine can occur; all other combine invariants unchanged (six-slot loadout, upgradeable pair, ≤1/visit, deferred_core_combine, visible mouse, ≥1000 ms, confirmed state change, restored mouse mode, no equal-max-tier pairs). A timeout remains an **error** signal in the live monitor.
4. **Monitoring:** `trainer/evaluation/live_monitor.py` version tuples extended with `0.1.66` for: six-slot combine precondition, Ball-and-Chain purchase, paced-combine safety (outer + dispatch + confirmation), and lock-expiry policy. The final-shop-combine prohibition tuple intentionally still excludes v65/v66 (one safeguarded wave-19 combine is allowed).

## Explicitly NOT changed

- `item_sharp_bullet` was **not** penalized. Telemetry (`run_1784518968_53657` seq 627 purchase_offer) shows it grants **piercing +1** (with piercing_damage −20, %damage −5, knockback −3) — a net-positive item for a zero-piercing gun build. The earlier "trap" classification was wrong.
- No crit/luck/regen demotion (overlaps the HP-floor dimension; deferred to keep causality interpretable).
- Blood Donation / Ball-and-Chain vetoes, lock rules, reroll caps, harvesting valuation: unchanged.

## Tests

`pytest tests -q`: **44 passed** (was 38). New/updated:
- `test_v66_policy_versions_are_consistent` (was v65).
- `test_v66_below_target_hp_outbids_utility_fillers_early_and_mid`.
- `test_v66_crate_weapons_carry_identity_keys_for_the_allowlist`.
- `test_v66_combine_confirmation_timeout_releases_the_shop_barrier`.
- `test_v66_live_monitor_version_gates_cover_the_deployed_policy_version` (fail-open guard: the deployed POLICY_VERSION must appear in every monitor version tuple except the two intentionally-historical ones).

## Gate

- Scheduled tasks: `BrotatoAgent-LiveMonitor-v66`, `BrotatoAgent-Supervisor-v66` (registered + started via `scripts/start_gate_watchdogs.ps1 -Version v66`).
- Logs: `reports/live_monitor_v66.log`, `reports/overnight_supervisor_v66.log`.
- Gate: fresh 20 runs, ≥18 wins, max 2 losses (threshold unchanged).
- v65 task registrations remain (Ready, not running), consistent with prior versions.

## Acceptance metrics to watch (beyond W/L)

- Bought-HP proxy at wave 9 ≥ +10 on most runs (v63–v65 winner median ≈ +12).
- Offense proxies at wave 12 not degraded vs v65 winners.
- `crate_decision` weapon takes > 0 (was 0% for all of v63–v65).
- Any `shop_combine_confirmation_timeout` event: run continues past the shop (and the monitor flags the timeout as an error for review).
