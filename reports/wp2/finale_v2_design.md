# Finale controller v2 — binding design

**Status: DESIGN, 2026-07-26.** Supersedes the algorithm sketch in
`finale_clean_slate_design.md`, whose four corrected premises are in that file's
addendum. Scope decision by the operator this session: **wave 20 only.**

## What is being replaced, and what is deliberately NOT

The wave-20 path today (`potential_field.gd:190-255`) is:

```
desire   = _pure_repulsion_flee(...)         # SUM of repulsion vectors
           (or _panic_dodge at hp <= 0.85)
escape   = _projectile_escape(...) * finale urgency boost
combined = desire*(1-urgency) + escape*urgency
combined = _finale_turn_without_reversal(...)   # anti-reversal patch
combined = _late_corner_escape(...)             # wave >=16, SHARED
combined = _finale_committed_escape(...)        # commitment latch patch
smoothed = _prev_move*(1-alpha) + combined*alpha
--- safety tail ---
           _finale_projectile_safety   (wave >= 17, SHARED)
           _finale_wall_safety         (wave >= 17, SHARED)
           _finale_body_safety         (EVERY wave, SHARED)
```

**v2 replaces the policy layers only**: `_pure_repulsion_flee` / `_panic_dodge`,
`_projectile_escape` blending, `_finale_turn_without_reversal`,
`_finale_committed_escape`, and the smoothing blend.

**v2 KEEPS the safety tail and the corner guard, unchanged.** This is a deliberate
departure from "strip the finale back as far as possible", and the reasons are
measured, not stylistic:

1. **The safety tail is not finale code.** Projectile and wall safety run from wave 17;
   body safety runs on **every combat wave** since v114. Removing it for wave 20 would
   give the finale *less* protection than wave 1 — including the 45-unit contact floor
   (`BOSS_FINALE_BODY_CRITICAL_CLEARANCE`) that is explicitly never modulated, and the
   unconditional hard wall projection that is the only guard against the corner traps
   behind v93/v96/v110.
2. **It is the audit surface.** All three audits replay the emitted action against
   `teacher.contributions.finale_translation`. A controller that bypasses the tail
   would make every finale audit **vacuous while still reporting "0 violations"** — the
   same failure shape as the `can_buy` defect that voided a published result here.
3. **The thing being tested is the policy, not the safety net.** Replacing both at once
   would confound "heading selection beats vector summation" with "safety removal".

So the experimental unit is: **vector-summation-plus-patches vs heading-selection**,
with everything downstream held constant.

## The controller

At 60 Hz, evaluate K candidate headings and pick one. No summation, so no cancellation
and no need for the anti-reversal / commitment patches.

```
for k in 0..K-1:
    h = unit vector at angle 2*pi*k/K
    t_hit = min over threats of closed-form time-to-closest-approach along h
            (threats: projectiles, boss, enemies -- each with position, velocity, radius)
    score = min(t_hit, HORIZON)                        # survival first, saturating
    if h would cross the hard wall margin within HORIZON: score -= WALL_PENALTY
    if dot(h, prev_heading) > 0: score += HYSTERESIS_BONUS * dot(h, prev_heading)
pick argmax(score); ties -> lowest k for determinism
```

**Closed-form time-to-collision, never time-sampled.** v116 established that discrete
time sampling was the systemic root cause of the v84-103 collapse: 6 samples / 0.6 s
could not see threats crossing between samples. `potential_field.gd` already has the
continuous primitive; reuse it rather than reintroducing sampling.

Parameters, three instead of the 39 `BOSS_FINALE_*` constants (of which only ~8 are
genuinely wave-20-exclusive): `FINALE_V2_HEADINGS` (K), `FINALE_V2_HORIZON`,
`FINALE_V2_HYSTERESIS`. Plus `FINALE_V2_WALL_PENALTY`.

**Hysteresis replaces both the anti-reversal patch and the smoothing blend.** Chatter
in a selection method is a tie-breaking problem, not a dead-time problem.

## 60 Hz — and the trap that comes with it

`agent_controller.gd:325-327` throttles wave-20 recompute to 20 Hz via
`BOSS_FINALE_RECOMPUTE_DIVISOR`. v2 recomputes every physics tick.

**`agent_controller.gd:344-345` sets `emit_capture = recompute_move` on finale waves.**
Left alone, a 60 Hz controller silently moves **captures** to 60 Hz, tripling wave-20
capture volume and changing `control_dt_ms` from ~50 ms to ~16 ms — under a dataset and
student path fixed at 20 Hz where `control_dt` and prev-action are model inputs.

**Binding: recompute at 60 Hz, keep emitting at 20 Hz.** On the v2 path `emit_capture`
must fall back to the ordinary `_combat_tick_counter % _WP2_CAPTURE_DIVISOR == 0`.
Consequence to accept knowingly: captures then sample 1 of every 3 decisions, so the
recorded action stream is a subsample of what the controller did — the same situation
waves 1-19 have always been in. `test_v117_nonfresh_finale_captures_reject_the_run`
asserts wave-20 captures land on recompute ticks; at 60 Hz every tick is a recompute
tick, so it still holds, but verify rather than assume.

## Wiring

- `agent_config.json` gains `finale_v2` (bool, **default false**).
- `agent_controller._load_auto_config()` reads it into `var finale_v2: bool = false`,
  and `_ready()` propagates it: `_field.finale_v2_enabled = finale_v2`.
- `potential_field.gd` gains `var finale_v2_enabled: bool = false` and, inside the
  existing `if finale:` branch, takes the v2 path when the flag is set.
- **Flag off must be byte-identical.** Same standard as the `resume_from_save` change.

## Evaluation — predeclared before implementing

- **Reference:** the current stack at **28/40 = 0.700 [0.546, 0.819]** on fixtures
  `756e6461` / `4ab34bff` (`reports/wp2/finale_baseline_0.1.128.md`). That build is ONE
  build, so it is the paired reference, not the bar.
- **Bar:** v2 is run on the **11-build predator library**, holding out 3 builds never
  used during iteration. A candidate must beat baseline on the 8 iteration builds AND
  not regress on the 3 held-out builds. Report per-build rates with raw series, never a
  pooled number alone.
- **Internal control:** run the 6 **invoker** builds too. The mechanism story predicts
  v2 improves **predator** and does **little for invoker** (invoker projectiles are
  96.3% stationary, predator 0%). **If v2 improves both equally, the mechanism story is
  wrong and the result should be distrusted**, even if the numbers look good.
- **Freeze detectors** from `wp2_finale_metrics.py` are reported alongside outcomes: a
  controller that "wins" by standing in a safe pocket without killing the boss must be
  visible as such (`boss_hp_ratio_last`, `stationary_frac`, `straightness`).
- Powered to detect a large effect only: at n=40/arm the CI half-width is ~14 pp.
  0.70 -> 0.90 is detectable; 5 pp is not. Do not claim small effects.

## Risks specific to this change

1. **GDScript is never parsed by the test suite.** Before deploying, statically sweep
   every new idiom for an exact precedent in the running build (the lesson that made the
   sentinel deploy safe). The mod-ready sentinel then catches a parse failure in seconds
   rather than after a wasted launch.
2. **~120 verbatim source pins** in `tests/unit/test_shop_policy_source.py` (lines
   517-1510) assert exact strings, substring counts, `.index()` orderings, and
   **negative pins** on names that must stay absent. v2 adds code without removing the
   v1 path, so most should survive — but each failure must be judged as
   *mechanism-pin or outcome-pin*, per the parse-gap lesson that a pin once asserted a
   fatal line as a requirement.
3. **`_prev_move` and the latches** keep advancing only if the v1 path runs. On the v2
   path, set `_prev_move` to the final vector so the safety tail and any fallback see a
   current value.
