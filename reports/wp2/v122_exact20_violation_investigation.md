# WP2 v122 exact-20 campaign — single-capture violation investigation

Source of truth for deployed v122 teacher: `git show b1cc3fc:mod/mods-unpacked/Tom-BrotatoAgent/teacher/potential_field.gd`
(the working tree carries v123 edits; all line numbers below are the **b1cc3fc** numbers).
Audit: `scripts/wp2_teacher_safety_audit.py` (working-tree copy; v123 additions are inert on these v122 legacy captures — `build_strength` absent).

Frozen replay fixtures written (schema `95B6444796A2...`, policy `teacher_v1-0.1.122-gun-wp1`, mod `0.2.30-wp2-capture`):
- `tests/fixtures/wp2/v122_exact20_viol_a_1784787688.json` (capture 18676 + 18674-18678)
- `tests/fixtures/wp2/v122_exact20_viol_b_1784804435.json` (capture 17442 + 17437-17447)
- `tests/fixtures/wp2/v122_exact20_viol_c_1784805636.json` (capture 9722 + 9720-9724)

Common root cause: the v121 fix (663c691) added an **explicit unattainable-relief-floor fallback**
in the teacher (source 1077-1085) AND, on the audit side, only taught **one** gate about it —
`_body_projectile_floor_unavailable` (script lines ~214-221). The other v122 body gates were never
made aware of that fallback (or of the boundary snap in C). All three campaign violations are those
un-taught gates firing on correct v122 behavior.

---

## A. run_1784787688_32406, capture_seq 18676 — wall_body_relief_selection_violations

Recorded (wave 18, fresh, 11 projectiles, player (1816,703) near right wall, action (-0.866,0.5) inward):
- body_input_clearance = body_selected_clearance = **131.635452**
- body_best_clearance = wall_relief_best_body_clearance = **-21.009933**
- wall_body_relief_active = wall_recovery_active = true; body_safety_active = false; loot_dash_active = false

Gate branch (audit lines 668-695): relief active, dash inactive, projectiles present + fresh →
reads recorded `selected=131.64`, `relief_best=-21.01`, `required = -21.01 - 20 = -41.01`. Fires on the
FIRST disjunct `relief_best < 0.0`, NOT `selected < required` (131.64 >> -41.01).

Teacher path (source `_finale_body_safety`, line 869): relief active → `rows = hard_safe_rows` (955).
Every hard-safe sampled lane near the wall is body-contacting → `highest_body_clearance = -21.01`;
`_finale_wall_relief_best_body_clearance = -21.01` (1067). Relief branch body_floor = `max(45, -21.01-slack) = 45`
(1072-1076). `highest(-21.01) < body_floor(45)` → **v121 fallback** (1083-1085): keep incoming command,
`body_selected_clearance = body_input_clearance = 131.64`, `return baseline`. The preserved command
(wall_selected_body_clearance 153.3, recomputed body clearance 131.64, projectiles 500+ units away) is safe.

The audit's own `_body_projectile_floor_unavailable` (215-221) DOES recognize this exact capture as the
v121 fallback (so it raises no projectile violation), but the relief-**selection** gate never consults it and
its `relief_best < 0.0` disqualifier fires on the negative pool-best.

**VERDICT: AUDIT_DEFECT.** Behavior safe.
**Fix (recommend):** in the relief-selection gate (668-695), suppress the `relief_best < 0.0` disqualifier
when the v121 fallback is in effect — i.e. when `selected >= relief_best` (the preserved command is at least
as clear as the pool best). A negative pool-best with a far-clearer preserved command is the sanctioned
fallback, not a hidden lane. Equivalent: gate only on `selected < required`.

---

## B. run_1784804435_39794, capture_seq 17442 — body_tier_violations

Recorded (wave 17 [not 20], fresh, 2 far projectiles, player (280,1248) bottom-left corner, HP 38/38,
action (0.71,-0.71) inward, **loot_dash_active = true**, wall_body_relief_active + wall_recovery_active = true):
- body_input_clearance = body_selected_clearance = **19.031828**
- body_best_clearance = wall_relief_best_body_clearance = **43.438971**; body_safety_active = false

Gate (audit fresh loop 754-765): `body_floor = _required_body_floor(debug, True, 17)`.
In `_required_body_floor`: not emergency; loot_dash → `enforce_pack_clearance = False` (removes only the pack CAP);
legacy slack 20; `best(43.44) >= 45`? no → falls through to `return best - slack = 43.44 - 20 = 23.44`.
`selected(19.03) < 23.44` → violation. **The dash exemption did nothing because it only guards the `best>=45`
pack-cap branch; when `best<45` the near-best floor still binds.**

Teacher path: relief active → relief branch body_floor = `max(45, 43.44-slack) = 45`; `highest(43.44) < 45`
→ same **v121 fallback** (1083-1085): keep incoming dash command (19.03), `return baseline`.

Neighbor sweep 17437-17447 (fixture): a single continuous loot-dash episode in the corner, HP pinned at 38/38
(no damage), emitting routes at body clearances 18.6 / 28.1 / 26.8 / 19.2 / 35.7 throughout. Those neighbors
do NOT trip because relief is inactive there (best==input==selected, so required=best-20 is trivially met).
17442 trips ONLY because relief momentarily activated and surfaced the pool-best 43.44 while the dash route
stayed at 19.03. 17445 (19.16) and 17440 (18.6) — same behavior, lower clearance — pass. The fired capture is
strictly indistinguishable in safety from its un-flagged neighbors; the trip is a relief-transient artifact.

Not the v121 crossing-range pattern (d76f6d5): only 2 projectiles, clearances 588/632, floor 576.6 easily met —
projectiles are not the binding constraint.

Note (latent, benign here): the v121 fallback's premise is "keep the *clearer* incoming command"; here input
(19.03) is BELOW the pool-best (43.44), the inverse case, so the fallback preserves a below-pool route. That is
harmless in this capture because the incoming command IS the deliberate loot-dash route (positive clearance,
no damage, inward progress), which is exactly what a dash is meant to preserve.

**VERDICT: AUDIT_DEFECT.** Behavior safe (deliberate bounded dash; no damage; positive clearance; consistent
with neighbors).
**Fix (recommend):** complete the loot-dash exemption in `_required_body_floor` — when `loot_dash_active`, waive
the near-best floor entirely (apply only the contact-safe / critical floor), i.e. short-circuit the
`return best - slack` path for dashes, matching the function's own comment ("only the contact-safe floor applies
while it runs"). Alternatively (or additionally) have the body_tier gate consult the v121 fallback recognizer
as the projectile gate already does.

---

## C. run_1784805636_10804, capture_seq 9722 — body_repair_violations

Recorded (wave 11 [not 20], fresh, 2 projectiles, player (1798,1162), action (0.5,-0.866025) = clean 300° grid dir,
NO active layers — dash/relief/wall-recovery/projectile-safety/emergency all false):
- body_input_clearance = **44.944609** (0.055 below the 45 tier)
- body_best_clearance = body_selected_clearance = **45.668119** (chose the best lane, above tier)
- body_selected_projectile_clearance = 227.07 (floor 207.07 met); body_safety_active = **false**

Gate (audit 771-781): `input(44.94) < 45` and `best(45.67) >= 45` → enter; violation if `not active OR selected<45`.
`selected(45.67) >= 45` so the second disjunct is false, but `not active` is true → violation. **Fires purely on
the missing flag; the emitted route is above tier.**

Teacher path: no early keep-baseline (1113 requires `input >= body_floor`; 44.94 < 45 → fails) → runs the
selection loop (1123-1145). Best admissible lane = the 45.668 grid sample. The incoming command (baseline) is a
near-grid direction at 44.94; the winning grid lane sits within the align threshold of it, so
`best_dir.dot(baseline) >= 0.999` → `_finale_body_safety_active = false` (line 1145). I.e. the teacher SNAPPED
its 44.94 baseline to the nearest sampled lane (45.668), crossing the tier by 0.72 units with essentially zero
directional deviation, and correctly did not flag a "repair" (there was none). (input!=selected proves best_dir!=
baseline; active=false proves they are within 2.56° — the boundary snap.)

**VERDICT: AUDIT_DEFECT.** Behavior safe (emitted 45.668 >= 45 critical tier). The `body_safety_active` flag is
NOT semantically required here: the source sets it only on genuine deviation (`dot < 0.999`), and a sub-degree
snap across the tier boundary is not a repair.
**Fix (recommend):** in the repair gate (771-781), drop the `not active` disjunct and gate only on the outcome:
`if selected_clearance < BODY_TIER - FLOAT_TOLERANCE:` (a >=45 emitted route satisfies the tier regardless of
whether a deviation flag was toggled). Optionally exempt when the emitted direction is within the align
threshold of the input.

---

## Bottom line

All three campaign violations are **AUDIT_DEFECTS**; none is a teacher defect. In every case the emitted route
was safe:
- A: preserved command, body clearance ~131.6, projectiles 500+ away.
- B: deliberate bounded loot-dash, 19.03 clearance, no damage (HP 38/38 across the episode), inward progress.
- C: snapped to the best sampled lane at 45.67 (above the 45 critical tier).

Dataset bearing: the three excluded runs (1784787688, 1784804435, 1784805636) show no unsafe teacher behavior
at the flagged captures. If the audit gates are corrected (or these captures individually cleared), all three
runs qualify for inclusion, lifting the campaign to 20/20. Primary agent decides inclusion.

Recommended audit changes are the minimal, behavior-neutral edits above; each is a gate the v121 change should
have updated alongside `_body_projectile_floor_unavailable`. Not implemented per task scope (read-only on audit
source).
