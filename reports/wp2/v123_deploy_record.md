# WP2 teacher v123 deploy record

## Build / deploy

- Deploy timestamp: **2026-07-23 22:36:02** local (log-latch archive `reports/logs_archive_20260723_223602`).
- Built mod ZIP SHA-256: **`B9C692C15770295D59741B954078FA494DDF5028F3D8DAA9EE8E53D990284B38`**
  (339157 bytes). Identical bytes at both installed paths:
  - `C:/Games/Steam/steamapps/workshop/content/1942280/3737864106/Tom-BrotatoAgent.zip`
  - `C:/Games/Steam/steamapps/common/Brotato/mods/Tom-BrotatoAgent.zip`
- Deployed identity: policy `teacher_v1-0.1.123-gun-wp1`, mod `0.2.31-wp2-capture`,
  capture schema hash `95B6444796A21FD44E94113B75BA2097BC381D5F72ED784F9B9A4A99DD46D951`
  (schema deliberately NOT bumped).

## Version bump (mirrors the v121->v122 bump commit `d76f6d5`)

Mod files (policy_version already at 0.1.123 from the committed v123 code; only mod_version bumped):

- `mod/mods-unpacked/Tom-BrotatoAgent/manifest.json`: `version_number` `0.2.30` -> `0.2.31`
- `mod/mods-unpacked/Tom-BrotatoAgent/runtime/agent_controller.gd`: `mod_version` `0.2.30-wp2-capture` -> `0.2.31-wp2-capture`
- `mod/mods-unpacked/Tom-BrotatoAgent/telemetry/telemetry_writer.gd`: `mod_version` default `0.2.30-wp2-capture` -> `0.2.31-wp2-capture`

Collector gate (the v121->v122 bump also touched these; required so `summary_fault`
accepts the v123 run — otherwise the collector false-faults on policy/mod mismatch):

- `scripts/wp2_collect_teacher.py`: `POLICY_VERSION` `0.1.122` -> `0.1.123`, `MOD_VERSION` `0.2.30-wp2-capture` -> `0.2.31-wp2-capture`
- `tests/unit/test_wp2_teacher_collector.py`: matching literals `0.1.122`/`0.2.30` -> `0.1.123`/`0.2.31` (8/8 unit tests pass)

## Smoke run

- Run id: **`run_1784810419_25652`**
- Result: **victory** through wave **20**; duration 1177198 ms (~19.6 min); damage taken 102.
- Summary faults: errors 0, hangs 0, illegal_actions 0.
- Clean shutdown confirmed: collector exit 0, Brotato.exe stopped, `auto_start=false`.

## Audits (v123 expectations)

- Safety audit (`reports/wp2/v123_smoke_safety.json/.md`): run_count 1, accepted 1,
  **violation_count 0** across every category (identity, summary, body tier/repair/diagnostic,
  projectile floor, sampled action, wall recovery, wall-body relief + selection, hard wall,
  loot dash, **strength**, avoidable damage). Activations: body 8405, body-emergency 1,
  projectile 1539, wall 3761, wall-body relief 1335, loot-dash captures 1255.
  events SHA-256 `265C18E0...0CE4DC39`, summary SHA-256 `8D58CB24...B182B9AB`.
- Capture audit (`reports/wp2/v123_smoke_capture_audit.json/.md`): capture_count 21268,
  schema hash matches `95B6...D951`, schema_mismatches 0, invalid_actions 0,
  invalid_captures 0, malformed_lines 0, valid_transition_estimate 21268,
  near_duplicate_fraction 0.0273.

## Strength diagnostics (v123 new)

All 21268 captures carry `build_strength` and `strength_tier` (100%). build_strength
range [0.554, 2.000]. Tier fractions: strong 0.4645, neutral 0.3625, weak 0.1730.
The safety-audit strength gate ran on every capture (0 violations, not inert).

## Summary

Teacher v123 (`teacher_v1-0.1.123-gun-wp1`, mod `0.2.31-wp2-capture`) was deployed from a
reproducible ZIP (SHA-256 `B9C6...84B38`) and passed its single-run qualification smoke:
a wave-20 victory with zero telemetry/safety faults, a fully clean capture audit, and the new
v123 build-strength diagnostics present on 100% of captures with an active (non-inert) strength
gate. The collector version gate and its unit test were synced to v123 alongside the mod bump
(mirroring the v121->v122 bump); without that sync the collector would have false-faulted the
run on a policy/mod mismatch. No commits made.
