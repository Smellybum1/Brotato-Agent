# Audit check inventory (read-only survey, 2026-07-26)

Scope: `scripts/wp2_teacher_safety_audit.py` (1037 lines, read in full),
`scripts/wp2_capture_audit.py` (42 lines, read in full) plus its implementation
`trainer/data/combat_capture_audit.py` (304 lines, read in full), and
`scripts/wp2_v126_shop_audit.py` (266 lines, read in full). Nothing was skipped.

Classification proposals only — final calls belong to the requester. "Blocks?"
means the counter contributes to a non-zero process exit code.

## A. `scripts/wp2_teacher_safety_audit.py`

Single exit path: `main():1033` returns `2` iff the summed `violation_count`
across all runs is non-zero. **Every one of the 19 contributors below is
weighted equally at 1 violation each and all of them block.** There is no
severity tiering, no diagnostic-only bucket, and no way to run a check as
non-blocking. The sum is assembled at `audit_run():862-882`.

| # | check_id / violation key | What it asserts | Location | Reads | Magic numbers | Proposed class |
|---|---|---|---|---|---|---|
| 1 | `malformed_lines` | Every line of `events.jsonl` parses as JSON. | `wp2_teacher_safety_audit.py:627-631` | raw event file | — | **HARD_INVARIANT** — telemetry corruption; nothing downstream is trustworthy. |
| 2 | `identity_violations` (`summary policy mismatch`) | `summary.policy_version` equals `--expected-policy`. | `:839-840` | `summary.json`, CLI arg | — | **HARD_INVARIANT** — build identity: you audited what you asked for. |
| 3 | `identity_violations` (`summary mod mismatch`) | `summary.mod_version` equals `--expected-mod`. | `:841-842` | `summary.json`, CLI arg | — | **HARD_INVARIANT** — same. |
| 4 | `identity_violations` (`N capture schema mismatches`) | Every capture's `capture_schema_hash` equals `--expected-schema-hash`. | `:843-848` | `payload.capture_schema_hash` | — | **HARD_INVARIANT** — schema conformance / capture-format identity. |
| 5 | `summary_violations` (`telemetry_complete is false`) | The run's summary declares telemetry complete. | `:852-853` | `summary.telemetry_complete` | — | **HARD_INVARIANT** — data completeness. |
| 6 | `summary_violations` (`summary errors/hangs/illegal_actions is nonzero`) | Three summary counters are exactly 0. | `:854-856` | `summary.errors`, `.hangs`, `.illegal_actions` | 0 | **HARD_INVARIANT** — `illegal_actions` is action legality; `hangs`/`errors` are runtime health. (Note: this trusts the mod's own self-report; it is not independently recomputed.) |
| 7 | `telemetry_error_events` | No `event == "error"` rows in the stream. Counted **per event**, so one noisy run can dominate the total. | `:850`, summed `:880` | event stream | — | **HARD_INVARIANT** — runtime error. Flag: the per-event weighting is a scaling quirk, not a classification issue. |
| 8 | `terminal_valid` (contributes `1` when false) | The final event in the stream is `run_end`. | `:849`, `:881` | last event | — | **HARD_INVARIANT** — clean termination / not truncated. |
| 9 | `body_tier_violations` | The emitted move's recorded body clearance is at least a wave/state-dependent "near-best" floor derived from `body_best_clearance`. | `:774-783`, floor at `_required_body_floor:105-133` | `finale_translation.body_selected_clearance`, `body_best_clearance`, `body_emergency_active`, `loot_dash_active`, `build_strength`, `wave` | `BODY_TIER 45.0`, `BODY_SLACK 20.0`, `BODY_SLACK_EARLY 35.0`, `BODY_PACK_CLEARANCE 160.0`, `BODY_EMERGENCY_SLACK 5.0`, `EARLY_GREED_MAX_WAVE 12` | **HEURISTIC_COMPLIANCE** — "stay 45 units off enemy bodies and give up at most 20 units versus the best sampled lane" is a survival hypothesis, and a strong candidate for the kind of positioning rule that could itself be depressing win rate. |
| 10 | `body_repair_violations` | If the incoming command was below the 45 tier and a sampled lane cleared it, the emitted command must also clear 45. | `:794-807` | same three clearance diagnostics | `BODY_TIER 45.0`, `FLOAT_TOLERANCE 0.002` | **HEURISTIC_COMPLIANCE** — asserts a repair the designer believed helps; the outcome value of forcing the repair is untested. |
| 11 | `body_diagnostic_mismatches` | Recomputing body clearance from raw entity state reproduces the logged `body_selected_clearance` to 0.002. | `:826-834`, `_body_clearance:251-289` | `player.x/y/speed`, `entities.enemies/bosses` (x, y, vx, vy, radius), `teacher.action` | `FLOAT_TOLERANCE 0.002`, `ESCAPE_HORIZON_SEC 0.60`, `ESCAPE_CLEARANCE_MIN_TIME 0.05`, default radius `18.0` | **HARD_INVARIANT** — this is a reproducibility/consistency check between the mod's self-reported diagnostic and an independent recomputation. **Caveat worth flagging: the horizon (0.60 s) and min-time (0.05 s) are tunables; if the audit's mirror ever drifts from `config.gd` this fires as a false invariant breach.** |
| 12 | `missing_body_diagnostic_captures` | When enemies/bosses are present on a fresh capture, a body diagnostic must have been emitted (not the `-1` sentinel). | `:764-767` | `body_selected_clearance == -1.0`, `entities.enemies/bosses` | `-1.0` sentinel | **HARD_INVARIANT** — telemetry completeness, not behaviour. |
| 13 | `projectile_floor_violations` | The selected lane's projectile clearance is at least the logged `body_projectile_floor`. | `:818-825`, exemption `_body_projectile_floor_unavailable:198-229` | `body_projectile_floor`, `body_selected_projectile_clearance`, plus the exemption's five diagnostics | `BODY_TIER 45.0`, `FLOAT_TOLERANCE`, sentinels `-1.0`, `-1.0e17/-1.0e18` | **UNCLEAR** — the *floor value itself* comes from telemetry, so this reads as "the runtime obeyed its own constraint" (invariant-shaped). But the constraint is a threat-avoidance heuristic, so obeying it may be exactly what hurts. To decide: is `body_projectile_floor` a fixed engine/legality quantity or a tuned config number? (It is emitted by the teacher, which points to tuned.) |
| 14 | `sampled_action_violations` | Whenever body safety was active, the emitted direction lies exactly on the 24-way sample grid. | `:787-788`, `_is_sampled_direction:504-513` | `teacher.action` | `ESCAPE_DIRECTIONS 24`, dot ≥ `0.99999` | **HARD_INVARIANT (weak)** — it verifies the emitted action came from the declared candidate set, i.e. implementation integrity rather than survival value. But note it also *forbids* a continuous/finer-grained action whenever repair is active; if the grid were widened this fires spuriously. |
| 15 | `wall_recovery_violations` | During wall recovery with body safety active (and no relief exception), the command must strictly increase distance from the wall. | `:835-837`, `_wall_recovery_progress_violation:455-476` | `wall_recovery_active`, `body_safety_active`, `wall_body_relief_active`, player/arena geometry | `WALL_RECOVERY_RELEASE 520.0`, `WALL_LOOKAHEAD 260.0`, `FLOAT_TOLERANCE` | **HEURISTIC_COMPLIANCE** — "always move inward when near a wall" is a positioning belief. 520 and 260 are pure tunables. |
| 16 | `wall_body_relief_violations` | At wave ≥ 20 under wall recovery with no projectiles, if the emitted lane's body clearance is under 200 and a hard-safe lane offered ≥ 60 more, that is a violation. | `:672-674`, `_wall_body_relief_violation:402-435` | `wall_recovery_active`, `projectile_safety_active`, `loot_dash_active`, `entities.projectiles`, geometry | `WALL_BODY_RELIEF_TRIGGER 200.0`, `WALL_BODY_RELIEF_MIN_GAIN 60.0`, wave `20`, `HARD_WALL_MARGIN 96.0` | **HEURISTIC_COMPLIANCE** — pure "you should have picked the roomier lane" positioning judgment, with two hand-tuned magnitudes and a hard-coded wave number. Highest-confidence demotion candidate. |
| 17 | `wall_body_relief_selection_violations` | While wall-body relief is active, the selected clearance must be within `BODY_SLACK` of the relief pool best, and a negative pool best is itself a fault unless the sanctioned fallback is diagnosed. | `:702-713` | `wall_relief_best_body_clearance`, `body_selected_clearance`, `action_fresh`, `entities.projectiles` | `BODY_SLACK 20.0`, `FLOAT_TOLERANCE` | **HEURISTIC_COMPLIANCE** — same family as #16. |
| 18 | `hard_wall_violations` | On late waves (≥ 17), the emitted command must never push the player within 96 units of any arena edge over a 0.30 s horizon. A zero-magnitude action also counts (`"zero final action"`). | `:667-671`, `_hard_wall_faults:479-501` | `teacher.action`, `player.x/y/speed`, `arena.width/height` | `LATE_WAVE 17`, `HARD_WALL_MARGIN 96.0`, `COMMAND_HORIZON_SEC 0.30`, arena defaults `2048.0 x 1536.0`, `_normalise` magnitude floor `0.1` | **HEURISTIC_COMPLIANCE** — this is the clearest case of an audit that *reads* like a hard rule ("never touch the wall") but is a 96-unit tunable buffer plus a wave cutoff. Walls are not illegal in Brotato; hugging one may be correct play. Flagging: the embedded `"zero final action"` sub-fault is arguably a separate HARD_INVARIANT (a null command) and might deserve splitting out. |
| 19 | `avoidable_damage_violations` | For each `player_damage` event, the preceding capture's route must not show (a) a projectile-clearance concession > 60 units, (b) a missed near-best body tier, (c) an emitted route crossing a projectile path while a ≥ 20-unit-clearer lane existed, or (d) same for an enemy body. | `:861`, `_avoidable_damage_violations:562-613`, replay `_route_replay:371-399` | damage rows joined to prior capture; `projectile_escape_clearance`, `projectile_final_clearance`, `body_best/selected_clearance`, raw entity kinematics | concession `60.0`, `ROUTE_PROJ_CONTACT 12.0`, `ROUTE_BODY_CONTACT 15.0`, `ROUTE_MIN_GAIN 20.0`, `BODY_TIER 45.0`, `BODY_EMERGENCY_SLACK 5.0` | **HEURISTIC_COMPLIANCE** — the name says "avoidable damage" but the assertion is "a counterfactual lane my own sampler scored better existed". In a game where taking chip damage to collect materials is often correct, this is a survival hypothesis, not an invariant. Four hand-tuned magnitudes. |
| 20 | `loot_dash_violations` (`dash episode exceeded the runtime commit bound`) | A contiguous loot-dash run never exceeds 26 captures. | `:730-736` | `loot_dash_active` streak | `LOOT_DASH_MAX_CAPTURES 26` (derived: 72 ticks @60 Hz → ~24 @20 Hz, +2 margin) | **UNCLEAR** — intended as a mirror of a runtime commit bound (invariant-shaped: the runtime *cannot* dash longer), but the `+2` margin and the Hz conversion make it a derived approximation. To decide: is `LOOT_DASH_MAX_TICKS` a hard runtime cap that terminates the dash, or a soft preference? If hard, HARD_INVARIANT. |
| 21 | `loot_dash_violations` (`dash active below the HP floor`) | A dash is never active below a wave/strength-derived HP-ratio floor. | `:749-757`, `_dash_audit_hp_floor:150-152` | `player.hp`, `player.max_hp`, `wave`, `strength_tier`, `build_strength` | `DASH_ARM_FLOOR_EARLY 0.35`, `_LATE 0.5`, `_MIN 0.30`, strong delta `-0.05`, weak `+0.05`, `DASH_ABORT_ARM_FRACTION 0.8`, `DASH_AUDIT_FLOOR_MARGIN 0.05`, legacy flat `0.35` | **HEURISTIC_COMPLIANCE** — "do not go looting while hurt" is a survival belief with seven tunable numbers stacked on it. |
| 22 | `strength_violations` | Recorded `build_strength` lies in [0,2] and `strength_tier` is consistent with it under the hysteresis band. | `:724-726`, `_strength_violation:170-195`, `_strength_tier_consistent:155-167` | `finale_translation.build_strength`, `strength_tier` | `STRENGTH_MIN 0.0`, `MAX 2.0`, `ENTER_STRONG 1.25`, `EXIT_STRONG 1.15`, `ENTER_WEAK 0.75`, `EXIT_WEAK 0.85`, `FLOAT_TOLERANCE` | **HARD_INVARIANT** — internal consistency of two telemetry fields; says nothing about play quality. Caveat: the four hysteresis constants are duplicated from `config.gd` **by hand**, so a config change silently turns this into a false alarm. |
| 23 | `nonfresh_finale_captures` (contributes `1` if the list is non-empty) | Every wave-20 capture landed on a recompute tick (`action_fresh`). Skipped entirely under `--legacy-sampled-diagnostics`. | `:658-665`, `:879` | `payload.teacher.action_fresh`, `wave` | wave `20` | **HARD_INVARIANT** — measurement validity: it exists because the v116 smoke had 0/496 fresh wave-20 captures, so every fresh-gated check silently skipped the fatal wave. This one guards the audit against itself. |

Counters that are **printed but never block**: `unavailable_projectile_floor_samples`,
`active_body_repairs`, `active_body_emergencies`, `active_projectile_safety`,
`active_wall_recovery`, `active_wall_body_relief`, `body_diagnostic_capture_count`,
`damage_events`, `late/fresh/fresh_late_capture_count`, `waves_represented`,
`events_sha256`, `summary_sha256`. Notably **`result` and `last_wave` — the actual
outcome — are recorded and printed but contribute nothing to acceptance.** A run
that dies on wave 3 with zero rule breaches is `accepted: true`.

## B. `scripts/wp2_capture_audit.py` + `trainer/data/combat_capture_audit.py`

Exit path: `wp2_capture_audit.py:38` returns `2` iff `schema_mismatches != 0`
**or** `invalid_actions != 0`. Only those two block; everything else in the
report is descriptive.

| # | key | What it asserts | Location | Reads | Magic numbers | Proposed class | Blocks? |
|---|---|---|---|---|---|---|---|
| 24 | `schema_mismatches` | Each capture's `schema_version` is `2.0.0` and `capture_schema_hash` equals the SHA-256 of `configs/wp2/combat_capture_v2.schema.json`. | `combat_capture_audit.py:134-139`, hash `:69-70` | envelope `schema_version`, `payload.capture_schema_hash`, schema file bytes | `CAPTURE_ENVELOPE_VERSION "2.0.0"` | **HARD_INVARIANT** — schema conformance/identity. | yes |
| 25 | `invalid_actions` | Every capture's `teacher.action` is a dict with finite `x` and `y`. | `:170-175`, `_finite_vector:52-58` | `teacher.action` | — | **HARD_INVARIANT** — NaN/missing action is an unusable/illegal command. | yes |
| 26 | `malformed_lines` | JSON-parse failures in the event stream. | `:119-122` | raw file | — | **HARD_INVARIANT** in nature, but **currently non-blocking** — flagging this as an inconsistency: the same condition blocks in audit A (#1) and does not here. | no |
| 27 | `invalid_captures` | Payload is a dict, `entities` is a dict, and `payload.valid` is true. | `:130-132`, `:146-148`, `:166-169` | `payload`, `payload.entities`, `payload.valid` | — | **HARD_INVARIANT** in nature, **non-blocking** today. | no |
| 28 | `near_duplicate_fraction` | Fraction of captures sharing a coarse state+action signature (dataset diversity). | `:210-220`, `:234`, `:266` | wave, player x/y, hp_ratio, seven group sizes, action | position bucket `/16`, hp round `2dp`, action round `2dp` | **UNCLEAR** — a training-data quality metric with no threshold attached. Would need a stated bar to be a check at all. | no |
| 29 | `severe_state_counts.low_health` | Counts captures at `hp_ratio <= 0.35`. | `:183-185` | `player.hp_ratio` | `0.35` | **HEURISTIC_COMPLIANCE**-adjacent, but purely descriptive (no assertion). | no |
| 30 | `severe_state_counts.near_wall` / `corner` | Counts captures within 128 of a wall, or with ≥2 clearances ≤ 192. | `:189-194` | `arena.width/height`, `player.x/y` | `128`, `192`, `2` | descriptive coverage counters; same positional belief as #18 but not asserted. | no |
| 31 | `severe_state_counts.dense_projectiles` / `boss` | ≥10 projectiles; any boss present. | `:195-198` | group sizes | `10` | descriptive. | no |
| 32 | `severe_state_counts.elite` / `charger` | **Substring match** for `"elite"` / `"charg"` across enemy `name`, `type_id`, `script_path`, `attack_path`. | `:199-209` | enemy record string fields | substrings `"elite"`, `"charg"` | descriptive, but note it is string-matching on game-asset paths — brittle to a Brotato content update. | no |
| 33 | `gap_to_200000` | Distance from the estimated valid-transition count to a 200,000-sample dataset target. | `:250` | `valid_transition_estimate` | `200_000` | project milestone, not a check. | no |
| 34 | `terminal_run_count`, `errors`, `damage_events` per run | Bookkeeping. | `:125-127`, `:222-232` | event types | — | descriptive. | no |

Wave bands `((1,5),(6,10),(11,15),(16,19),(20,20))` at `:15` are reporting
buckets only.

## C. `scripts/wp2_v126_shop_audit.py`

Exit path: `:262` returns `2` iff `violation_count != 0`, where
`violation_count` (`:191-192`) is the sum of exactly four lists. All four block
equally.

| # | key | What it asserts | Location | Reads | Magic numbers | Proposed class |
|---|---|---|---|---|---|---|
| 35 | `surplus_exit_violations` | The shop was never exited (`shop_go`) while the v126 surplus-reroll rule still held: in window, budget remaining, and `spendable_surplus - reroll_price > 0`. | `:164-168`, `rule_holds:65-73` | `purchase_decision.surplus.{in_window,surplus_rerolls,surplus_rerolls_max,spendable_surplus,reroll_price}`, `action.type` | `> 0` surplus test; `SURPLUS_REROLLS_MAX` default 3 | **HEURISTIC_COMPLIANCE** — this is the purest example in the whole survey. v126 exists on the belief that "leaving the shop with spendable gold is a mistake"; the audit defines compliance with that belief as success. If rerolling to the last coin is bad play, this check enforces the error. |
| 36 | `reason_code_violations` | The logged `exit_reason` matches the code recomputed from the logged surplus arithmetic (budget-exhausted codes treated as one bucket). | `:170-177`, `recompute_reason:76-107` | same `surplus` dict fields | reserve precedence order; `BUDGET_CODES` bucket | **HARD_INVARIANT** — self-consistency between a logged label and the logged numbers behind it. Says nothing about whether exiting was right. |
| 37 | `surplus_budget_violations` | Per-wave surplus rerolls never exceed `SURPLUS_REROLLS_MAX`. | `:145-150` | `action.surplus_reroll`, `wave` | `SURPLUS_REROLLS_MAX` (parsed, default `3`) | **UNCLEAR** — invariant-shaped (a declared cap was respected) but the cap itself is a tunable budget. Decide by whether exceeding 3 indicates a code bug versus merely different play. |
| 38 | `unknown_reason_codes` | Every logged `exit_reason` is one of the seven known codes. | `:159-162` | `payload.exit_reason` / `action.exit_reason` | seven-code frozenset `:46-50` | **HARD_INVARIANT** — enum conformance. |
| 39 | `stale_board_timeouts`, `confirmed_board_refreshes`, `surplus_rerolls`, `reason_code_counts`, `purchase_decisions` | Bookkeeping. | `:119-125`, `:179-193` | event names | — | descriptive, non-blocking. |

Also parsed but unused in any assertion: `SURPLUS_MIN_WAVE` (6),
`SURPLUS_MAX_WAVE` (19), `SHOP_MAX_REROLLS_CAP` (28) — read at `:60-62`, never
referenced. Dead constants.

---

## Notes

### Exit-code summary
- **Audit A**: one exit path, 19 blocking contributors, all weight 1, no severity
  tiering. Roughly 9 of the 19 are behavioural/positioning rules. There is no
  mechanism today to demote a check to diagnostic without editing the sum at
  `:862-882`.
- **Audit B**: 2 of ~11 counters block. `malformed_lines` and `invalid_captures`
  are structural faults that do **not** block here while the equivalent does in
  Audit A — an inconsistency worth resolving in whichever direction.
- **Audit C**: 4 of ~9 counters block, all weight 1.
- **None of the three audits consults the run outcome.** `result` and `last_wave`
  are carried in Audit A's output purely as display fields.

### Thresholds changed over time (from `git log -p`)
- `WALL_BODY_RELIEF_TRIGGER`: introduced `120.0` (`0c89408`) → `140.0`
  (`15c9cdc`) → `200.0` (`491f296`). The v117 comment at `:43-45` states the
  reason plainly: the previous smoke *died* with references at 140.7-151.1, so
  the threshold was widened to make the audit fire on that case. This is a
  threshold tuned against a single observed death — a hypothesis, not an
  invariant.
- `LOOT_DASH_MIN_HP_RATIO 0.35` introduced in `b815bf3`, then renamed to
  `LEGACY_LOOT_DASH_MIN_HP_RATIO` in `0f7008d` (v123) and superseded by the
  seven-constant wave/strength-derived floor. Old captures keep the old
  strictness by design.
- `0f7008d` (v123) added the entire strength block, `BODY_SLACK_EARLY 35.0`, and
  `EARLY_GREED_MAX_WAVE 12` — i.e. body slack became wave-indexed, loosening the
  early game.
- `94d6a7c` added the whole continuous-route family (`ROUTE_PROJ_CONTACT 12.0`,
  `ROUTE_BODY_CONTACT 15.0`, `ROUTE_MIN_GAIN 20.0`, `ESCAPE_CLEARANCE_MIN_TIME 0.05`).
- `0be6c80` "Correct three over-firing audit gates; qualify all 20 campaign runs"
  — worth reading directly: a commit that relaxes gates and in the same breath
  qualifies the runs is exactly the failure mode this task is investigating.
- Original constants (`14810ec`): `LATE_WAVE 17`, `BODY_TIER 45.0`,
  `BODY_SLACK 20.0`, `HARD_WALL_MARGIN 96.0`, `COMMAND_HORIZON_SEC 0.30`,
  `WALL_LOOKAHEAD 260.0`, `WALL_RECOVERY_RELEASE 520.0`, `ESCAPE_HORIZON_SEC 0.60`,
  `ESCAPE_TIME_SAMPLES 6`, `ESCAPE_DIRECTIONS 24` — none has ever been changed.
- `scripts/wp2_capture_audit.py` and `trainer/data/combat_capture_audit.py`: no
  threshold changes found. `scripts/wp2_v126_shop_audit.py`: single-commit file,
  no threshold churn.

### Source-text assertions
- **`wp2_v126_shop_audit.py:53-62` `config_int()` regex-parses `teacher/config.gd`
  source text** with `^const NAME := (-?\d+)$`. This is the one live source-text
  dependency found. It is *safer* than a pin (it reads the value rather than
  asserting it), but it fails silently: any formatting change (a type hint, a
  trailing comment, an expression instead of a literal) makes the regex miss and
  the audit falls back to a hardcoded default (`3`/`6`/`19`/`28`) with no warning.
  A drifted `SURPLUS_REROLLS_MAX` would be audited against `3` regardless of what
  the deployed mod uses.
- **`wp2_teacher_safety_audit.py:16-72` duplicates ~20 `config.gd` constants as
  Python literals by hand** (each annotated with a `# config X` comment). This is
  not a source-text *assertion*, but it is the same drift hazard in the opposite
  direction: nothing checks that these still match the deployed mod, and checks
  #11 and #22 are exactly the ones that turn into false invariant breaches if
  they drift.
- No literal source-text pin (asserting the presence of a code line) was found in
  any of the three scripts.

### Genuine judgment calls flagged
1. **#13 `projectile_floor_violations`** — reads a floor *from telemetry*, so it
   is formally "the runtime obeyed itself", yet the floor is a tuned avoidance
   threshold. Depends on whether `body_projectile_floor` is engine-fixed or config.
2. **#20 dash commit bound (26)** — mirror of a runtime cap or an approximation?
   The `+2 captures` margin and the 60 Hz → 20 Hz conversion suggest the latter.
3. **#37 `surplus_budget_violations`** — cap-respected (invariant-shaped) versus
   tunable budget.
4. **#14 `sampled_action_violations`** — implementation integrity, but it
   simultaneously *forbids* finer-grained actions during repair.
5. **#18 `hard_wall_violations`** — the `"zero final action"` sub-fault is a real
   invariant (null command) bundled into an otherwise heuristic positioning check;
   consider splitting.
6. **#19 `avoidable_damage_violations`** — the name asserts causality the code
   does not establish. It proves a counterfactual lane the *same sampler* scored
   higher existed; it does not prove the damage was avoidable, nor that avoiding
   it was correct.
