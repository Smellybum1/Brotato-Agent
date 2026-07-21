# Prompt for Fable: WP1 win-rate log review

You are taking over a read-only analysis pass on BrotatoAgent WP1 in `C:\Codex\Brotato Agent`. The gate is deliberately paused. Do not edit code, deploy, restart Brotato, start watchdog tasks, commit, or start WP2. Analyze the available logs and propose evidence-backed ways to improve the agent's win percentage.

Start by reading:

1. `reports\WP1_ACTIVE_GATE.md`
2. `reports\v67_deploy_record.md`
3. `reports\v68_deploy_record.md`
4. `reports\overnight_supervisor_v66.log`
5. `reports\overnight_supervisor_v67.log`
6. `reports\overnight_supervisor_v68.log`
7. `%APPDATA%\Brotato\brotato_agent\runs\run_*\summary.json` and `events.jsonl` for the relevant runs
8. `reports\live_monitor_v66.log`, `reports\live_monitor_v67.log`, and `reports\live_monitor_v68.log` as needed

## What changed after your v66 handoff

Your v66 implementation remains the gameplay baseline:

- stronger below-target max-HP valuation before wave 15;
- crate weapon identity fix;
- combine-timeout barrier release;
- v66 monitor-version coverage;
- Blood Donation and Ball and Chain vetoes retained;
- Sharp Bullet remains allowed and must not be treated as a trap;
- the intentional any-gun pool remains enabled;
- one fully safeguarded wave-19 combine remains allowed.

After Codex resumed control, these changes occurred:

### v66 outcome and v67 gameplay repair

v66 became impossible at 8W/3L after 11 completed runs. All three defeats ended at telemetry wave 17:

- `run_1784525978_54680`
- `run_1784531567_60545`
- `run_1784532527_90900`

They were operationally clean: no APPCRASH, telemetry failure, hang, illegal action, or combine-safety failure. The shared failure signature was continued engagement after meaningful damage, followed by chained hits.

v67 made exactly one gameplay-policy change:

- from wave 17 onward, when HP is at or below 85% of max and threats are live, the standard kiter returns early through panic dodge or pure-repulsion flee with 0.70 smoothing;
- normal movement resumes after recovery above the threshold;
- the v63 corner guard and every v66 shop/item/weapon/combine policy remained unchanged.

The implementation is in:

- `mod\mods-unpacked\Tom-BrotatoAgent\teacher\config.gd`
- `mod\mods-unpacked\Tom-BrotatoAgent\teacher\potential_field.gd`

v67 passed its full test suite before deployment.

### v67 observed result

v67 completed four runs at 2W/2L before an unrelated watchdog-orchestration failure paused run 5:

- defeat: `run_1784533992_75711`, final combat telemetry wave 19;
- victory: `run_1784535084_15950`, wave 20;
- victory: `run_1784536257_73939`, wave 20;
- defeat: `run_1784537410_90913`, final combat telemetry wave 19;
- incomplete/orphaned by watchdog failure: `run_1784538504_9547` — do not score it as a win or loss.

The wave-17 repair showed real survival value:

- first v67 defeat survived wave 17 despite 74 enemies and a 21-HP low, then recovered before losing in the final wave as density reached 91 enemies;
- the second victory recovered from 23 to 48 HP through wave 17 after taking 53 damage;
- the second defeat survived an especially harsh wave 17 with 121 damage and a 16-HP low, recovered to full HP, then lost in the final wave when density stayed around 100–109 enemies and chained 19/9/8 damage hits landed.

This suggests the repair moved the dominant failure regime later rather than fully solving win rate. Validate that inference from the raw logs instead of assuming it.

### v68 orchestration-only repair

At 19:18:52 Australia/Brisbane, both exact v67 watchdog tasks exited together without a Python exception or intended supervisor shutdown while Brotato continued. No APPCRASH occurred. v68 made exactly one orchestration-resilience change in `scripts\start_gate_watchdogs.ps1`:

- `RestartCount=999`
- `RestartInterval=PT1M`
- `StopOnIdleEnd=false`

No gameplay policy changed from v67 to v68. v68 only version-bumped the mod/policy and live-monitor coverage, added a source test for the task settings, passed 46/46 tests, and was deployed.

v68 completed two clean victories before the user paused it for this review:

- victory: `run_1784539456_49033`
- victory: `run_1784540594_18397`
- in-progress when stopped: `run_1784541801_96700` — do not score it.

The v68 tasks are now `Ready`, their scoped descendants are stopped, Brotato is stopped, and the Codex heartbeat automation has been deleted. The user's phrase “2 wins and 2 losses this run” corresponds to completed v67 results; v68 itself was paused at 2W/0L.

## Analysis requested

Use the raw summaries and event streams to determine what most strongly separates wins from defeats, with emphasis on the new final-wave failure regime. Please:

1. Build a compact comparison of relevant v63–v68 completed wins and losses. Separate versions and do not count aborted/incomplete runs.
2. Compare wave-entry HP/max HP, armor, dodge, speed, sustain, ranged damage, attack speed, percent damage, weapon tiers/families, item purchases, materials spent/unspent, enemy density, projectile density, damage timing, recovery timing, and terminal hit chains.
3. Determine whether final-wave defeats are primarily caused by insufficient killing speed and density accumulation, insufficient effective HP, movement/escape behavior, unlucky damage spikes, final-shop spending, weapon-family dilution, or another measurable factor.
4. Inspect whether the v67 low-HP repulsion override is behaving as intended and whether it creates any tradeoff in damage output or positioning that contributes to final-wave density.
5. Examine final-shop decisions in the two v67 defeats, including weapon replacements, combines, defensive purchases, rerolls, and unspent materials. Do not classify a compliant safeguarded wave-19 combine as a violation.
6. Check the v66 crate weapon fix empirically: identify any crate weapon takes and whether they helped or diluted the build.
7. Rank 3–5 possible next repairs by expected win-rate impact, evidence strength, implementation risk, and overlap with existing policy dimensions.
8. Recommend exactly one focused next gameplay-policy change for a hypothetical v69. Give the precise rationale, likely code touchpoints, acceptance metrics, and tests that should be added. Do not implement it.
9. Explicitly state what evidence would falsify your recommendation.

## Guardrails

- Analysis only; do not change files or external state.
- Do not restart the gate or Brotato.
- Do not commit.
- Do not start WP2.
- Preserve the any-gun experiment unless the evidence strongly supports changing it; if so, distinguish a pool problem from a scoring/upgrade problem.
- Blood Donation and Ball and Chain remain vetoed.
- Sharp Bullet is net-positive for this zero-piercing gun build and is not a trap.
- Preserve combine invariants: six slots before combining, upgradeable non-max-tier pair, at most one per shop visit, deferred dispatch, visible mouse, at least 1000 ms before confirmed state change, mouse restoration, and never combine equal max-tier IDs.
- A compliant wave-19 combine is allowed.
- Treat the known off-plan gun-family and early zero-projectile warnings as informational when telemetry is otherwise fresh.
- Distinguish gameplay-policy evidence from v68's orchestration-only task change.

Return a concise evidence table, your diagnosis, ranked options, and the single recommended v69 repair. Cite run IDs and event sequences wherever possible so Codex can verify the claims before authorizing any edit.
