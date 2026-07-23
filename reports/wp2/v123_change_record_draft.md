# WP2 v123 change record (DRAFT) — unified risk budget

Implements `.tmp/wp2_v123_architecture.md` (sections A-G, incl. the C2 final-shop
greed window). Built during the v122 exact-20 campaign; DEPLOY ONLY after the
campaign completes and a fresh v123 smoke passes a zero-violation audit. No
workshop ZIP rebuild while Brotato.exe runs.

## Intent

Movement aggression now knows how strong the build is (strength signal + tiers),
snowballs collection early and in the final pre-boss shop wave, and traverses the
rail instead of corner-parking. Every safety floor and the ordered safety tail are
unchanged and never modulated.

## A. Strength signal

- `agent_controller.gd`: new member `_build_strength := 1.0`. In the existing
  `% 30 == 0` block, immediately after `build_metrics` is computed and BEFORE the
  HUD/telemetry consume it: `raw = clamp(weapon_dps / max(dps_target, 1.0), 0,
  2)`; `_build_strength = _build_strength*0.75 + raw*0.25` (tau ~1.7-2.0 s at the
  0.5 s cadence). Injected into `_gather_combat_state` as `state["build_strength"]`
  — the block runs after `choose_movement`, so movement consumes the previous
  0.5 s value (intentional one-update staleness).
- `potential_field.gd`: per-decision hysteretic tier (`_update_strength_tier`),
  and per-capture visibility — `finale_translation_debug()` now emits
  `build_strength` (float, 3 decimals via `stepify(..., 0.001)`) and
  `strength_tier` next to `loot_dash_active`, so audit reads them from
  `contributions.finale_translation`.

### Schema-hash decision: NO bump (kept 2.0.0 / hash unchanged)

`_WP2_CAPTURE_SCHEMA_HASH` is the SHA-256 of `configs/wp2/combat_capture_v2.schema.json`
(proven by `test_wp2_combat_capture_source.py`, which recomputes
`sha256(SCHEMA.read_bytes())` and asserts it equals the controller constant). The
schema types `teacher.contributions` as an open `{"type": "object"}` (schema line
93) with no `additionalProperties: false` and no enumerated keys; `finale_translation`
is not described at all. The new `build_strength`/`strength_tier` keys live inside
that open object, so the schema file is unchanged, its bytes and hash are unchanged,
and captures still validate against the same schema. Per the spec rule ("if the hash
only covers top-level payload fields, leave it"), the contribution-dict keys are not
part of the hashed shape → no version bump, no hash regeneration. The frozen
`test_combat_capture_schema_hash_and_required_groups_are_frozen` stays green.

## B. Strength-conditioned aggression (discrete tiers, hysteresis)

Tiers on smoothed S: enter strong `S >= 1.25` / exit `S <= 1.15`; enter weak
`S <= 0.75` / exit `S >= 0.85`; else neutral. Large jumps demote to neutral first,
then re-promote in the same update (a crash from strong lands directly in weak).

Deltas applied only where the base value is consumed on the ordinary kiter path:

| Term | base | strong | weak | site |
| --- | --- | --- | --- | --- |
| LATE_EDGE_KITE_NEARBY | 10 | 14 (+4) | 6 (-4) | `_build_desire` edge-kite gate via `_strength_edge_kite_nearby()` |
| pack-repulsion weight | x1.0 | x0.85 | x1.15 | `_build_desire` (both `_pack_density_repulsion` call sites) via `_strength_pack_mult()` |
| dash window clearance | getter | -10.0 | +10.0 | `_effective_dash_window_clearance(wave)` |
| dash arm HP floor | getter | -0.05 | +0.05 | `_effective_dash_arm_hp_floor(wave)` |

NEVER modulated (unchanged): the ordered safety tail `_finale_projectile_safety`
-> `_finale_wall_safety` -> `_finale_body_safety`, the late-survival branch,
`BOSS_FINALE_WALL_HARD_MARGIN` 96, `ESCAPE_PANIC_CLEARANCE` 55,
`BOSS_FINALE_BODY_CRITICAL_CLEARANCE` 45, the dash abort relation (abort = 0.8 x
effective arm), and the dash bullet gate.

## C / C2. Early-greed budget (wave-indexed getters)

New config getters (offense_dps_target precedent). Early tier = `wave <= 12`; late
= otherwise; the three persistence-only getters re-enter the greedy tier at
`wave == FINAL_SHOP_WAVE` (19) per C2 (v122 run-1 corner-parked wave 19 with near-zero
pickup; wave 19 funds the last shop before the boss).

| Getter | early (<=12) | wave 19 | late (13-18, 20) |
| --- | --- | --- | --- |
| loot_dash_arm_hp_floor | 0.35 | 0.5 (LATE) | 0.5 |
| loot_dash_window_clearance | 30.0 | 45.0 (LATE) | 45.0 |
| loot_dash_stall_count | 8 | 8 (greedy) | 12 |
| loot_dash_cooldown_ticks | 90 | 90 (greedy) | 180 |
| engage_strafe_loot_cap | 0.6 | 0.6 (greedy) | 0.35 |
| body_clearance_slack | 35.0 | 20.0 (LATE) | 20.0 |

`_finale_body_safety` gained a required `wave` argument for the near-best slack;
both call sites (late-survival branch, ordinary-tail) updated. The 45-unit contact
floor is unchanged and not wave-indexed.

Dash-gate stacking rule: `effective = getter(wave) + tier delta`, then hard clamp
(arm HP floor >= `LOOT_DASH_ARM_FLOOR_MIN` 0.30; window >= `LOOT_DASH_WINDOW_MIN`
20.0). Cooldown/stall/strafe-cap take the wave getter directly (no tier delta).

## D. Rail traversal (anti corner-parking)

`_edge_kite_force` gains `loot`/`wave`. A bounded loot/open-space bias runs BEFORE
the continuity flip (continuity keeps the final say), reusing `_score_strafe_side`
whose loot term is capped by `engage_strafe_loot_cap(wave)` so enemy pressure and
wall openness dominate. When no enemy/boss is ahead on the rail within
`RAIL_CLEAR_RADIUS` (240.0), a tangential drift `tangent * EDGE_RAIL_DRIFT` (0.45,
provisional) is added. The corner guard (`_late_corner_escape`, margins, blend) is
unchanged.

## E. Versioning

Both policy_version strings bumped `teacher_v1-0.1.122-gun-wp1` ->
`teacher_v1-0.1.123-gun-wp1` (agent_controller.gd:16, telemetry_writer.gd:5).
`mod_version` (0.2.30-wp2-capture) and the manifest are NOT bumped (deploy-time
only). See the open item on live_monitor.py below.

## Constants: old -> new (config.gd)

Removed (replaced by wave-indexed getters):

| removed const | old value | replacement getter |
| --- | --- | --- |
| LOOT_DASH_MIN_HP_RATIO | 0.5 | loot_dash_arm_hp_floor(wave) |
| LOOT_DASH_WINDOW_CLEARANCE | 45.0 | loot_dash_window_clearance(wave) |
| LOOT_DASH_STALL_COUNT | 12 | loot_dash_stall_count(wave) |
| LOOT_DASH_COOLDOWN_TICKS | 180 | loot_dash_cooldown_ticks(wave) |
| ENGAGE_STRAFE_LOOT_CAP | 0.35 | engage_strafe_loot_cap(wave) |

New constants:

| const | value |
| --- | --- |
| STRENGTH_ENTER_STRONG / EXIT_STRONG | 1.25 / 1.15 |
| STRENGTH_ENTER_WEAK / EXIT_WEAK | 0.75 / 0.85 |
| STRENGTH_STRONG_EDGE_KITE_DELTA / WEAK | +4 / -4 |
| STRENGTH_STRONG_PACK_MULT / WEAK | 0.85 / 1.15 |
| STRENGTH_STRONG_DASH_WINDOW_DELTA / WEAK | -10.0 / +10.0 |
| STRENGTH_STRONG_DASH_HP_FLOOR_DELTA / WEAK | -0.05 / +0.05 |
| EARLY_GREED_MAX_WAVE | 12 |
| LOOT_DASH_ARM_FLOOR_MIN | 0.30 |
| LOOT_DASH_WINDOW_MIN | 20.0 |
| RAIL_CLEAR_RADIUS | 240.0 |
| EDGE_RAIL_DRIFT | 0.45 (CALIBRATION TARGET) |

Unchanged: `BOSS_FINALE_BODY_CLEARANCE_SLACK` 20.0 (still used by the wave-20-only
interior-lane / projectile-escape selectors), `FINAL_SHOP_WAVE` 19 (reused as the
greedy re-entry key), all safety floors.

## F. Audit mirrors (scripts/wp2_teacher_safety_audit.py)

### Legacy-strictness rule (v122-campaign safety)

Every v123 audit loosening is gated on the capture actually carrying the v123
strength diagnostics — `_is_v123_capture(debug)` is true iff `build_strength` is
present and non-`None`. Legacy (v122 and earlier) captures have no strength
diagnostics, so they are audited with the exact pre-v123 strictness: the flat dash
floor `LEGACY_LOOT_DASH_MIN_HP_RATIO = 0.35` and body slack `BODY_SLACK = 20` at
every wave. This makes the imminent v122 exact-20 campaign audit reproduce v122
strictness exactly. The v123 wave/tier dash floor and wave-indexed body slack apply
only to v123 captures. The strength diagnostics are also propagated into the
damage-review rows (`_damage_rows`) so the all-wave damage body-floor honours the
same gate.

Bounds table (header literals; each names its config counterpart):

| audit literal | value | config counterpart |
| --- | --- | --- |
| BODY_SLACK_EARLY | 35.0 | body_clearance_slack(wave <= 12) |
| BODY_SLACK | 20.0 | body_clearance_slack(otherwise) |
| EARLY_GREED_MAX_WAVE | 12 | EARLY_GREED_MAX_WAVE |
| FINAL_SHOP_WAVE | 19 | FINAL_SHOP_WAVE |
| STRENGTH_ENTER/EXIT_STRONG | 1.25 / 1.15 | STRENGTH_ENTER/EXIT_STRONG |
| STRENGTH_ENTER/EXIT_WEAK | 0.75 / 0.85 | STRENGTH_ENTER/EXIT_WEAK |
| DASH_ARM_FLOOR_EARLY / LATE | 0.35 / 0.5 | loot_dash_arm_hp_floor |
| DASH_ARM_FLOOR_MIN | 0.30 | LOOT_DASH_ARM_FLOOR_MIN |
| DASH_ARM_STRONG/WEAK_DELTA | -0.05 / +0.05 | STRENGTH_*_DASH_HP_FLOOR_DELTA |
| DASH_ABORT_ARM_FRACTION | 0.8 | dash abort = 0.8 x effective arm |
| DASH_AUDIT_FLOOR_MARGIN | 0.05 | audit floor = abort - 0.05 |

- `_required_body_floor` is wave-aware for v123 captures only (slack 35 for wave
  <= 12, else 20); legacy captures keep slack 20 at every wave. BODY_TIER 45
  unchanged.
- Dash-active HP floor: v123 captures use `_dash_audit_hp_floor(wave, tier) =
  0.8 x effective_arm - 0.05`, where `effective_arm = clamp(loot_dash_arm_hp_floor(
  wave) + strength delta, >= 0.30)` (neutral late = 0.5 -> 0.40 -> 0.35, identical to
  the retired flat literal); legacy captures use the flat
  `LEGACY_LOOT_DASH_MIN_HP_RATIO = 0.35`.
- New strength gate (`_strength_violation`, inert on legacy captures): flags a
  recorded `build_strength` outside [0, 2], an unknown tier, or a tier that cannot
  hold at the recorded strength (single-sample hysteresis necessary band). Added to
  the run's `violation_count` and to the returned `strength_violations`.

## G. Test evidence

`.venv/Scripts/python -m pytest -q --basetemp=.tmp/pytest-basetemp`:
**148 passed, 0 failed** (baseline before this work: 138 passed; live_monitor.py
version tuples extended by the primary for the E version bump).

New tests (source-parity, `test_shop_policy_source.py`):
`test_v123_strength_signal_is_plumbed_through_controller_and_field`,
`test_v123_strength_tiers_are_hysteretic_and_bounded`,
`test_v123_wave_indexed_greed_getters_and_boundaries` (pins 12/13, 18/19, 19/20),
`test_v123_rail_traversal_drift_avoids_corner_parking`.

New tests (audit units, `test_wp2_teacher_safety_audit.py`):
`test_v123_required_body_floor_is_wave_indexed` (12 vs 13 boundary, v123-gated),
`test_v123_legacy_captures_keep_pre_v123_body_slack` (legacy wave-10 slack 20 vs
v123 wave-10 slack 35), `test_v123_dash_hp_floor_clamp_arithmetic` (early+strong =
0.30 exactly, never below), `test_v123_legacy_dash_floor_is_strict_while_v123_dash_floor_loosens`
(legacy wave-8 dash hp 0.30 flagged at 0.35; v123 neutral not flagged at 0.23),
`test_v123_strength_tier_consistency_gate`,
`test_v123_audit_run_rejects_inconsistent_strength_and_low_hp_dash`.

Existing source-parity tests EXTENDED for the getter conversion / version bump /
new call signatures (no frozen numeric evidence altered):
`test_wp2_capture_build_versions_...` (policy v123), `test_v110_final_body_gate_...`
(wave-indexed body_slack), `test_v119_...`, `test_v118_...`, `test_v114_...`.

### live_monitor.py version coverage (resolved by primary)

Bumping the deployed policy version to `0.1.123` required appending `"0.1.123"` to
the safety-check version tuples in `trainer/evaluation/live_monitor.py` (outside
this task's ownership). The primary agent applied that edit; `test_v77_live_monitor_version_gates_cover_the_deployed_policy_version`
now passes and the suite is fully green.

## Open calibration items

RUN-5 CALIBRATION RESOLVED (2026-07-23, reports/wp2/v123_run5_calibration.md,
5 runs / ~2100 combat_ticks + ~21k captures each):

- Strength tiers 1.25/0.75: CONFIRMED unchanged. Pooled tick-time strong
  25.5% / neutral 51.8% / weak 22.7%; thresholds at ~p79/p19 of wave-median
  S; no within-run flapping (S driven by build quality + progression). The
  weak-tier / early-greed overlap (weak fires w5-12) makes the stacking
  clamps (arm floor >= 0.30, window >= 20.0) load-bearing — both pinned by
  tests.
- `EDGE_RAIL_DRIFT` 0.45: HELD for first deploy (new force term, one
  calibrated step). Metric RE-AIMED: two-wall corner dwell is already ~3%
  at wave 19; the real defect is single-wall edge-hug (47-73% of wave-19
  captures within 280 of one wall) with ground loot saturating the ~50
  field cap (29% pooled / 70% run-1 wave-19) while wave-19 shops are
  gold-rich (722-1022). v123 success metrics: wave-19 single-wall-280
  occupancy and loot-saturation fraction, NOT corner occupancy or gold.
  Escalate to 0.6-0.7 (stay under EDGE_BIAS 0.85) in v124 if edge dwell
  does not drop.
- Early/wave-19 greed literals: HELD as implemented. The strafe-cap raise
  (0.35 -> 0.6) is the meaningful wave-19 lever (paths toward spread loot);
  stall 8 / cooldown 90 are low-yield (dash already fires 9-10 episodes /
  12.5% of wave-19 captures — it is position-pinned, not gated). Rail drift
  is expected to do the heavy lifting.
- Re-check all of the above against the full 20-run set at campaign end
  before deploy.
