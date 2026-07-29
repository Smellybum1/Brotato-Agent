# Reading the safety tail for a charge-aware lever

Static read of `mod/mods-unpacked/Tom-BrotatoAgent/teacher/potential_field.gd` at mod 0.2.54,
before any edit. No machine time. Prompted by
`charge_weight_erased_by_tail.md`, which established that a `_build_desire` charge weight
moves the desire by +0.216 and the final command by +0.003.

## Correction 1 — the target is the WALL path, not `_finale_body_safety`

`charge_aware_threat_model.md` names `_finale_body_safety` as the place the lever must go.
The code says otherwise, and `desire_is_discarded.md`'s own measurement already agreed
(`body_safety_active` showed **no** separation, 75.4 vs 76.7; `wall_recovery_active` ran
0.370-0.869).

- `_finale_wall_safety:1100` — when the recovery latch is set and projectile safety is not
  active, `_best_finale_interior_lane` **replaces the command wholesale**. The incoming
  command survives only as `direction.dot(desired) * BOSS_FINALE_WALL_DESIRE_WEIGHT`,
  weight **25.0**, against `BOSS_FINALE_WALL_CENTER_WEIGHT` **110.0** and a wall-clearance
  term worth up to **2080** (`min(wall_clear, 520) * 4.0`). That ratio is the 72x
  attenuation, in source form.
- `_finale_body_safety:1445` — early-returns `baseline` **unchanged** whenever the incoming
  command already clears the body floor, the projectile floor, and the enemy-penalty slack.
  It is an arbiter of last resort, not the owner of the command.

At wave 17 (`LATE_SURVIVAL_WAVE = 17`, `BOSS_FINALE_WAVE = 20`) the latch is never cleared
(`compute_movement:184` only clears it below wave 17), so the 280/520 hysteresis persists
across the whole wave.

## Correction 2 — the tail is NOT type-blind; it is already velocity-aware

The premise carried forward was that the tail "almost certainly treats every enemy
identically, exactly as the desire field did". That is wrong, and the difference is
load-bearing.

Every enemy-facing computation in the tail extrapolates enemy velocity:

| function | uses `vx/vy` | used by |
|---|---|---|
| `_finale_enemy_path_penalty:786` | `enemy_pos + enemy_vel * future_sec` | wall lane selector only |
| `_predictive_enemy_path_penalty:2457` | same | body arbiter, wall replan |
| `_predictive_body_path_clearance:831` | closed-form closest approach on `rel_vel` | all three tail paths |

So a charging pursuer already scores worse than a walking one — kinematically, over a
~0.6 s horizon. **This is the most likely source of the agent's existing +0.061
differentiation**, given `_enemy_engagement_force` weights every non-boss at exactly 1.0.
That is an argument *for* the tail as the lever site: it is a channel that demonstrably
already reaches the final command.

What is uniform is not the treatment of velocity but the **thresholds and weights**:
`BOSS_FINALE_WALL_ENEMY_AVOID_CLEARANCE = 120.0` and the 45.0 critical clearance apply
identically to a 3.67x-speed, 837-HP pursuer and a 22-HP walking baby_alien. The
intervention is therefore not "add differentiation where there is none" but "the
differentiation that exists has the wrong shape" — short-horizon collision avoidance where
the human plays a longer-horizon engage/disengage.

## Which term binds — NOT determinable from the source

Two candidate constraints, and the code does not settle which one is active:

1. **The enemy penalty**, which is both a soft score term (weight **4.0**) and a *hard
   admissibility filter* (`_best_finale_interior_lane:1000`, `_finale_body_safety:1463` —
   drop any lane with `enemy_penalty > lowest + BOSS_FINALE_ENEMY_PENALTY_SLACK (20.0)`).
2. **The body-clearance floor.** `BOSS_FINALE_BODY_CRITICAL_CLEARANCE = 45.0` is a hard
   floor *when some lane achieves it*; when none does, it degrades to `highest - slack`,
   i.e. "stay near the best available". Closing head-on on a walking pursuer at ~700 u/s
   combined closure fails a 45-unit floor outright — but in a wave-17 pack the floor is
   often in its degraded form instead, and then the argmax is decided by the lane score.

Which regime holds on a typical wave-17 tick decides which knob can move anything. Guessing
here is the exact failure the record already names — reasoning from code structure about a
system where something else dominates (`brotato-measurement-discipline`, 7th instance).

## Plan

Ship **one** build, 0.2.55, carrying the instrument and both knobs, all default-inert:

- **Instrument** — per-term decomposition of `_finale_lane_score` for the selected lane and
  the runner-up, the enemy-penalty and body-clearance spread across all 24 candidates, the
  binding floor and its regime, and which sub-path owned the tick. Free-form under
  `teacher.contributions.debug.tail`, so no capture-hash move.
- **`tail_calm_penalty_mult`** — scales the avoid/critical clearance thresholds for
  non-charging enemies in `_finale_enemy_path_penalty` and `_predictive_enemy_path_penalty`.
- **`tail_calm_clearance_mult`** — scales non-charging threats' contribution in
  `_predictive_body_path_clearance`.

Kept separate from the desire-level `calm_threat_mult` so the two layers stay attributable.
Charge test reuses the shipped `CHARGE_RATIO_THRESH = 1.5` and the 0.2.54 defensive rule:
**a missing velocity counts as CHARGING**, so an absent signal never makes the agent bolder
than the shipped policy.

Then a control run reads which term binds (Gate 0 for the tail), and only the binding knob
gets dosed. Readback is unchanged: charging-vs-walking radial velocity w.r.t. the nearest
pursuer within 600 u, measured on the **final command**, from +0.061 toward the human's
+0.219.
