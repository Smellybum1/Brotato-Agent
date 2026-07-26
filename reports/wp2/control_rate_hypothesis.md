# The control-rate hypothesis: one mechanism behind the finale hazard AND the imitation gap

**Status 2026-07-26: HYPOTHESIS.** Found while checking whether the finale lead was
offline-testable. Tested for free by the running 36-run champion bank. If it holds it
is the most consequential structural fact in WP2.

## The mechanical facts (verified in source, not inferred)

`agent_controller.gd::_physics_process` runs at **60 Hz**
(`_WP2_CAPTURE_DIVISOR := 3 # 60 Hz physics / 3 = 20 capture decisions per second`).

| regime | movement vector recomputed at | source |
|---|---|---|
| teacher, waves 1-19 | **60 Hz** — `recompute_move := true` every tick | `agent_controller.gd:268` |
| teacher, wave 20 | **20 Hz** — `BOSS_FINALE_RECOMPUTE_DIVISOR := 3` | `agent_controller.gd:269-271`, `config.gd:131` |
| student / residual, all waves | **20 Hz** — action arrives on the capture tick and the override is applied every physics frame until replaced | `agent_controller.gd:290-301`, `learned_combat_controller.gd:5-17` |

The learned controller's own header states the design intent outright:

> "hold the previous applied vector until the reply lands (get_override_vector
> returns it while pending — **the teacher's 60 Hz recompute must not leak to the
> player** during the ~1-frame wait)"

So the 60 Hz/20 Hz asymmetry is deliberate and documented. What appears never to have
been asked is **what it costs**.

## The convergence

Two separate open problems reduce to the same quantity:

1. **The finale hazard.** Conditional on reaching wave 20, the current teacher dies
   there 28.6% of the time (4/14) versus 4.7% (4/86) in the strong era.
   **Wave 20 is the only wave where the teacher itself drops from 60 Hz to 20 Hz.**
2. **The imitation gap.** The production student bc_v2_f achieved roughly 1 victory in
   10 runs against a teacher at ~50%, and the project's recorded mechanism finding was
   *"imitation != survival"* — bc_v3_a agreed with the teacher **more** than bc_v2_f
   and died **more**. **Every student runs at 20 Hz against a 60 Hz teacher.**

If dropping movement control from 60 Hz to 20 Hz materially costs survival, then one
mechanism explains both, and *"imitation != survival"* may be substantially
*"20 Hz != 60 Hz"* — a structural handicap independent of imitation quality.

**Wave 20 is a natural experiment for this**, because there the teacher imposes the
handicap on itself. The champion bank measures it at no extra cost.

## What this does and does not do to the residual line

Careful, because the residual line was closed on two nulls and they are not alike:

- **The §6 checkpoint (learned residual vs matched random control) is CLEAN.** Both
  arms ran through the sidecar at 20 Hz, so control rate is matched. That null stands.
- **Stage F2 (deterministic pi4 vs PURE teacher) is CONFOUNDED.** The P arm ran at
  20 Hz through the sidecar; the T arm ran at 60 Hz. A residual of exactly zero would
  still have lost ground to the teacher on control rate alone. F2's headline —
  P(P outranks T) = 0.45 [0.2725, 0.6350] — therefore does not cleanly measure the
  residual's effect.

So the residual line's closure is **weakened, not overturned**: the rate-matched null
survives, the teacher-comparison null does not. Anyone reopening that line should
re-run F2 with a rate-matched control (teacher routed through the sidecar at 20 Hz),
not against the raw 60 Hz teacher.

The same caution applies to the earlier paired student evaluations (bc_v3_a vs
bc_v2_f): those were student-vs-student, so rate-matched and unaffected. It is
specifically **anything compared against the unmediated teacher** that is confounded.

## Predictions, predeclared

If the control-rate hypothesis is right, the 36-run champion bank should show:
- a wave-20 conditional hazard **materially above** the pre-wave-20 hazard in the same
  runs (the internal control — same policy, same runs, only the rate differs);
- and roughly consistent with the 28.6% seen at n=14.

If instead the bank shows a wave-20 hazard near the ~5% seen at other late waves,
**both** the finale lead and this hypothesis lose their main support and should be
dropped without a follow-up experiment.

## Why it is not offline-testable

The held physics ticks are never captured. At wave 20 `emit_capture = recompute_move`,
so captures fire exactly on recompute ticks; at other waves captures fire every 3rd
tick while the teacher recomputes on all three. Measured on the v128 qualifying smoke,
capture inter-arrival is **51 ms median at every wave including 20** — identical
sampling, different underlying decision rate. The telemetry is structurally blind to
the difference, so no replay or archive analysis can settle this. Only live runs can.

## If confirmed, the cheap tests in order

1. `BOSS_FINALE_RECOMPUTE_DIVISOR` 3 -> 1 (one constant, one wave, wave <20 acts as
   an internal control). Gate via `docs/RELEASE_GATE.md`, not a smoke.
2. Only then consider the student path, where raising the rate is a genuine
   architecture change: the dataset is 20 Hz and `control_dt` plus prev-action are
   model inputs, so a 60 Hz student is not a config flip. Establishing the *size* of
   the effect at wave 20 first is what tells you whether that cost is worth paying.

Do not do 2 before 1.
