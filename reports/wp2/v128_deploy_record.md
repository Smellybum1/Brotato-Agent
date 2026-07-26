# v128 deploy record — mod-ready sentinel (sentinel-only, no behavioural change)

**Date:** 2026-07-26
**Policy:** `teacher_v1-0.1.128-gun-wp1`
**Mod:** `0.2.37-wp2-capture`
**Capture schema hash:** `2823CB7E7D6A6DDB7F805A76D0CD674BA7A2A908058771B66B4A8FEFF9BC1174` (unchanged)
**ZIP SHA-256:** `0733E6687064206E9A5000919DFC71C51A764D806344F7C7477C748EB8235E23`
**Supersedes deployed build:** `0.1.127` / `0.2.36`, ZIP `24F1B8C1…FD3A`

## What shipped

**Nothing behavioural.** `shop_strategy.gd` has no diff against the previously
qualified build. The v128 level-up scoring change was implemented and then
**withdrawn as inert** (commit `b9647ad`) after the arithmetic showed it flips none
of the 9 decisions it was designed to fix; only the version bump was kept, so the
sentinel could ship on a clean, well-isolated smoke rather than bundled behind a
policy change.

The functional delta vs `0.2.36` is 36 lines in `runtime/agent_controller.gd` plus
4 in `telemetry/telemetry_writer.gd`:

- `agent_controller::_write_mod_ready()`, called from `_ready()`, writes
  `user://brotato_agent/mod_ready.json` carrying policy / mod / capture-hash
  identity. It exists **only if the mod actually installed**.
- `MOD_VERSION` is now a single source of truth: the run-meta `mod_version` was
  previously a separately hardcoded literal that could drift from the manifest.
- Collector side (already committed in `b98fb4d`): `clear_mod_ready()` before
  launch, then `await_mod_ready()` requires the file with **matching identity**
  within 90 s. Deleting beats timestamp-checking — a stale sentinel is otherwise
  indistinguishable from a fresh one.

Purpose: a GDScript parse error anywhere takes the **whole** mod down and leaves
the game on the title screen, which from the collector's side is indistinguishable
from a slow start. The v127 deploy lost a full build/launch cycle to exactly that,
diagnosed only because a human noticed the title screen.

## Pre-deploy static parse sweep

The sentinel's GDScript had **never been parsed** — this deploy was its first
parse, and the repo has no headless Godot. Sweep performed before shipping:

| check | result |
|---|---|
| BOM on changed `.gd` files | none (both begin `ext…`) |
| non-ASCII in comments (em dashes in the new block) | **precedent**: the running `0.2.36` controller already carries 28 non-ASCII lines |
| `const X := "…"` inferred-const idiom | **precedent**: deployed build lines 37-41 |
| `Directory.new()` / `File.new()` / `JSON.print({…})` / `store_string` | **precedent**: deployed build lines 1923-1928, a near-identical JSON-file writer |
| `"literal" in <Autoload>` (the v126 parse killer) | absent; guarded repo-wide by `tests/unit/test_mod_gdscript_parse_hazards.py` |
| symbol resolution (`policy_version`, `MOD_VERSION`, `_WP2_CAPTURE_SCHEMA_HASH`, `_MOD_READY_PATH`, `LOG_NAME`) | all declared |

Every idiom in the new code had an exact precedent in the build that was already
running, which is what reduced the residual parse risk to near zero **before**
launch rather than discovering it at the smoke.

Suite: **537 passed**.

## Smoke

`run_1785028909_68538` — **VICTORY, wave 20**, damage taken 87, 1,152,373 ms
(~19.2 min), 20,675 captures.

**The sentinel worked on its first parse.** ModLoader log: clean install, zero
`ERROR` / `Parse Error` / `Invalid` / `FATAL` lines, `Tom-BrotatoAgent.zip loaded`,
`AgentController ready`. The sentinel appeared carrying
`0.1.128` / `0.2.37` — an identity that had never existed on disk before this
deploy, so the file can only have been written by the new build — and the
collector's identity gate accepted it.

## Audits — all clean

| audit | key counts | violations | result |
|---|---|---|---|
| `wp2_teacher_safety_audit.py` | 23,207 events; 20,675 captures; body repairs 7,376; body emergencies 4; projectile safety 887; wall recovery 2,737; wall-body relief 1,038; loot-dash captures 2,220; damage events 12 | **0** in every category incl. identity | PASS |
| `wp2_capture_audit.py` | 20,675 captures; malformed lines 0; near-dup 0.0235 | schema mismatches **0**, invalid captures **0**, invalid actions **0** | PASS |
| `wp2_v126_shop_audit.py` | 17 surplus rerolls; stale-board timeouts 0 | **0** | PASS |

Sentinel field check from the **recorded run** (not the live files): `mod_version`
and `policy_version` match in both `summary.json` meta and the `run_start` payload;
the capture schema hash is a single value across all 20,675 captures with 0
mismatches.

Artifacts: `v128_smoke_{safety,capture,v126_shop}_audit.{json,md}`.
Events SHA-256 `17D4AE96…EA00`; summary SHA-256 `677A786C…5EE1`.

Noted, non-violating: `unavailable_projectile_floor_samples` 115 (diagnostic
counter; `projectile_floor_violations` 0). Surplus rerolls 17 vs 4 in the v127
smoke — the v126 rule is exercised harder here and still never violated.

## Status

**QUALIFIED.** This build is now the deployed and qualified baseline, replacing
`0.1.127` / `0.2.36`.

Carried forward: the parse gap itself is not closed — this deploy adds *detection*,
not *prevention*. A pinned Godot 3.5.x binary with a stub-autoload harness for real
`--check-only` parse gating remains deferred; see the scorer-migration discussion
in `.tmp/pro_review_adoption_20260726b.md`, where the same harness would also let
scorer fixtures execute against the shipped GDScript instead of a reimplementation.

## Note: `agent_config.json` rewrite

`scripts/deploy_mod.py` rewrites `agent_config.json` wholesale and drops the
`student_enabled` / `student_port` / `student_model_sha256` keys. They were already
absent before this deploy (dropped by the v127 deploy) and no student work is in
flight, so nothing was lost. Restore via `scripts/wp2_set_student_pin.py` before any
student work; last pin was `bc_v2_f`, sha `1AD517B0…F331`.
