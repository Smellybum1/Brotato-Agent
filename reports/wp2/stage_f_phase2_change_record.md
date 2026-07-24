# WP2 Stage F Phase 2 change record — bounded residual actor-critic

Stage **F (bounded residual RL)** of the WP2 learned-combat track, Phase 2.
Status: **CONCLUDED NULL 2026-07-25** — the learned residual was not shown to
beat the matched Phase-1 random control; growing-batch iteration stopped at the
predeclared §6 checkpoint. Commits `b644be2` (Phase 2 infra + rungs 1–3),
`c6dee5e` (iterations 1–2 + null diagnostics), `67d1d29` (`--actor-l2` knob +
pi3 two-arm selection), `770e5d8` (checkpoint tooling + student-pin utility),
`24a0027` (pi3 live evidence + abort investigation), `f92b514` (pi4 iteration 4),
`e9b358a` (§6 checkpoint NULL verdict). Branch `wp2-combat-learning`. Design of
record: `.tmp/wp2_stage_f_residual_design.md` (Phase 2 §1 predeclared gate, §5
offline promotion gates, §14.3 honest-classification). No mod changes; no
production change (config pin never left `bc_v2_f_s1`).

**Honest classification (applies to every run below).** All Phase 2 checkpoints
and all 13 checkpoint runs are **residual-teacher-base control (§14.3)**: the
frozen teacher policy `bc_v2_f_s1` with a bounded angular rotation of its combat
movement action (`executed_dir = rotate(teacher_dir, θ_max·tanh(z))`,
`θ_max = 5°`, magnitude preserved), shop/economy fully teacher-owned. **No
independent-policy claims.** The residual is not a student; it rotates the
teacher's action.

**Predeclared decision surface (design §1, binding before any launch).** At
~250–300k cumulative residual ticks, the learned residual must **beat the
matched Phase-1 uniform random control** (same θ bound) on damage-taken and
wave outcomes, else **stop and report**. The comparison is
`reports/wp2/residual_checkpoint_compare_v1.{json,md}`: full-capture-stream
damage, wave/risk-stratified, 10k bootstrap CIs, seed 0, no significance tests.

## Infrastructure + rungs 1–3 (`b644be2`)

The Phase 2 stack: a **zero-init residual actor** on the frozen `bc_v2_f_s1`
trunk (`δ = 5°·tanh(z)`; the untrained actor emits `z=0` ⇒ `δ=0` ⇒ teacher
exactly), a **twin-critic TD3** learner (F-2: off-policy actor-critic primary),
`reward_v2` (weights with deliberately-absent terms documented), and replay
assembly from the telemetry joins (n-step-5, fallback segmentation, 2 s recovery
exclusion, teacher-`δ`=0 mixing as the actor regularizer). Actor serving mode
added to the sidecar.

- **Rung 2 (critic sanity).** Critic converges on 107,340 Phase-1 probe
  transitions; the state-**averaged** Q dose-response is ~0 (−0.0019, ~2 %
  relative) — no constant directional bias, consistent with teacher
  cancellation. Value extraction is therefore **state-conditional** and decided
  at the live control checkpoint, not offline.
- **Rung 3 (serving parity).** Zero-init serving reproduces the teacher
  **exactly** over 1,200 payloads.
- 425 tests green.

## Iterations 1–2 + null diagnostics (`c6dee5e`)

pi1 (smoke w19 + batch w20 / w20-victory / w19) and pi2, trained on the growing
183,343-transition pool, were both **gate-clean but their residuals collapsed
toward zero**. Diagnostics located the cause and, importantly, ruled out a value
null:

- **Regularizer implicated, not the value.** The `λ₀ = 0.01` L2-to-zero on the
  actor causes the collapse; setting `λ₀ = 0` restores ~2° median residuals.
- **The advantage is real but small and targeted.** The critic's
  state-conditional advantage (p99 0.018 vs |Q| 0.075) is concentrated precisely
  in `bc_v2`'s weak strata (wave 20: 37 % of states advantaged > 0.01;
  risk ≥ 0.75: 38 %) — coherent with the M4 mechanism finding
  (`reports/wp2/m4_change_record.md`).
- **Offline cannot adjudicate.** Offline cannot separate real improvement from
  critic error; the live random-control checkpoint decides. Trainer gained
  multi-log replay pools (`run_id:conn:logpath`). Cumulative residual ticks:
  183,408. Reference: `reports/wp2/residual_null_diagnostics.md`.

## pi3 — `--actor-l2` knob + two-arm λ selection (`67d1d29`)

A backward-compatible `--actor-l2` knob (default keeps `λ₀ = 0.01`) enabled two
arms retrained on the full 10-run pool (6 Phase-1 probe + 4 pi1 batch;
183,408 states), differing **only** in `λ₀`:

| arm | λ₀ | actor sha | ruling |
|---|---|---|---|
| **A (pi3)** | 0.001 | `689C1C64…AD26F` | **SELECTED** |
| B | 0.0003 | `60E7467D…` | rejected |

Both pass all offline promotion gates (design §5: finite losses; p99 |z| 0.139 A
/ 0.285 B vs bar 2.5; serving determinism max diff 0.0; no θ_max saturation, max
|δ| 4.01° A / 4.43° B vs 5° bound). **Stratified |δ| decided**
(`reports/wp2/residual_pi3_arm_selection.md`): arm A concentrates residual mass
**7.0× in wave 20, 3.2× in risk ≥ 0.5, 7.5× in risk ≥ 0.75** (the exact strata
the null-diagnostics critic located advantage), with near-zero residual on the
low-risk early manifold. Arm B's extra pooled magnitude (p50 0.27° vs A's 0.05°)
is off-target baseline drift — the λ-to-0 noise-like pathology in miniature —
delivering no more signal in the decisive strata. **pi3 = arm A**: equal-or-more
residual where it matters, less perturbation where the teacher is already good.
24 targeted + 425 baseline tests green.

## Checkpoint tooling + student-pin utility (`770e5d8`)

The comparison tool (`residual_checkpoint_compare_v1`), and the rationale for its
**primary damage metric**:

- **Full capture-stream damage accounting is PRIMARY.** Every hp-drop between
  consecutive captures, heal-clamped, normalized by pre-drop max_hp, attributed
  to the pre-drop capture's wave band / risk stratum, all captures as the tick
  denominator. This matches the mod's `player_damage` event ground truth on all
  10 pool runs (agree within 5 hp).
- **Why the RL-usability filter was demoted to diagnostic.** The
  replay-usability-filtered RL-training view (valid student tick, 2 s recovery
  exclusion, contiguous seq) **undercounts damage in recovery-heavy runs** — it
  zeroed the damage of a recovery-heavy 18-damage **victory** run. It is retained
  only as a labeled `rl_usable_view` diagnostic, never as the decision surface.
- **Control-vs-control validation.** A 3v3 control-vs-control comparison straddles
  zero on every readable stratum — the tool does not manufacture a difference.
- Stratified wave/risk rates, 10k bootstrap CIs (seed 0), no significance tests.
- `scripts/wp2_set_student_pin.py`: auditable config pin / restore. 18 tests.

## Live evidence (`24a0027`) — smoke PASS, batch-1, abort + investigation

- **Smoke PASS.** pi3 smoke defeat wave 17 (bar ≥ 15), serving clean.
- **Batch-1 r1 (w19).** Defeat wave 19. Operator observed three **rich shop
  exits** (w10 / w17 / w18) and ~1,200 g banked into the w19 death — the classic
  WP1-era offense-starved loss signature. All rule-consistent with teacher v125
  (no gate violations); **shop is teacher-owned**, so this is v126 economy
  evidence, not a residual defect (`reports/wp2/v126_evidence_rich_exit_w10.json`).
- **Batch-1 r2 (w13) — predeclared wave-15 bar tripped → campaign aborted.**
  Per the predeclared abort bar, the campaign was aborted mid-run-3, the stack
  shut down cleanly, and config was restored idle. The **abort investigation**
  (`reports/wp2/residual_pi3_wave13_abort_investigation.json`) cleared the pi3
  mechanism:
  - *Serving clean* — 34,046 acts, |δ| p50 1.01° / p99 3.28° / max 4.55°,
    frac > 4° = 0.0006, fallbacks 2–5/wave, latency p99 20–26 ms (40 ms deadline).
  - *Economy converted* — full conversion every shop (exits ≤ 84 g), NOT the r1
    banked-gold pattern.
  - *Corner hypothesis rejected as pi3-specific* — the random **control** runs
    show the same w10 corner spikes (11 %, 22 %).
  - *Read* — attrition under a defense-light build vs w11–13 pressure, with the
    machine-load covariate active.
  - **Ruling: pi3 NOT disqualified on n=1 sub-15 with a clean mechanism scan; the
    run stays training-valid (defeat, honestly labeled).**
  - **Predeclared escalation set here:** any further run ending < wave 15 in this
    arc ⇒ pi3 declared behaviorally degraded, iteration stops, checkpoint runs on
    existing data.
- **Machine-load covariate recorded**
  (`reports/wp2/residual_checkpoint_load_covariate.json`): the learned arm was
  collected under an 8–12-worker STS2 load (operator reduced 12→8 mid-r2); the
  Phase-1 control was collected unloaded. Measured agent impact was small
  (fallback 0.3–0.5 %, latency p99 22–24 ms vs 19.3 ms baseline, within deadline)
  but game-side frame drops were operator-observed and unmeasured. Flagged as a
  covariate to call out next to any borderline checkpoint result.

## pi4 — iteration 4 (`f92b514`)

Batch-1 completed w20-**victory** (damage 76, cleanest student-path win to that
point; pi3 finished 1/4). pi4 (`λ₀ = 0.001`, seed 4, actor sha `16414822…497A4`)
retrained on the 14-run / **247,510-state** pool including the first pi3 victory;
all offline gates pass (p99 |z| 0.172, serving determinism exact). Batch-2 served
pi4 and went **3/3 victories** (damage 107 / 135 / **22** — the cleanest 20-wave
run ever recorded in this project). No further sub-wave-15 run occurred, so the
escalation rule did not fire; the arc reached the ~250–300k-tick checkpoint as
planned.

## §6 checkpoint — NULL verdict (`e9b358a`)

Verdict authority: primary session (delegated, operator standing autonomy).
Learned arm (7 runs, pi3 + pi4) vs matched Phase-1 uniform random control
(6 runs). On the predeclared full-capture-stream surface, **no metric resolves
away from zero**:

| metric (learned − control) | diff [95 % CI] |
|---|---|
| victory rate | +0.238 [−0.262, +0.714] |
| final wave | +0.26 [−2.41, +2.76] |
| overall damage rate | +0.00004 [−0.00002, +0.00010] |
| wave-20 damage rate | −0.00039 [−0.00171, +0.00076] |
| risk ≥ 0.5 damage rate | +0.00024 [−0.00135, +0.00187] |

**VERDICT: NULL — the learned residual is not shown to beat random perturbation.**
Per the predeclared rule, growing-batch iteration **stops at this checkpoint**.

**What the data honestly shows (recorded, not adjudicated):**

- Outcome point-estimates favor the learned arm: 4/7 victories (57 %) vs 2/6
  (33 %); final-wave median 20 vs 19.5. Not resolved at this n.
- Damage point-estimates are mixed: overall slightly worse for learned
  (+0.00004), wave-20 and risk ≥ 0.75 better (−0.00039, −0.00332). All unresolved.
- Within-arm trend: the three pi4-served runs went 3/3 (damage 107 / 135 / 22)
  after pi3's 1/4 — pi4 differs from pi3 by one more data batch, not architecture.
  Suggestive of iteration-over-iteration improvement; not evidence at this n.
- The learned arm carried both known handicaps: the investigated w13 defeat
  (mechanism scan clean) and the machine-load asymmetry (control collected
  unloaded).

## Predeclared rules were followed (the trail)

This arc is a clean example of predeclared bars binding the outcome:

1. **Offline promotion gates (§5)** gated every checkpoint before it served
   (finite losses, p99 |z| bar, serving determinism, θ saturation) — pi3 arms
   A and B both cleared them; selection then fell to stratified |δ|, not to a
   post-hoc metric.
2. **Wave-15 abort bar** tripped on the pi3 r2 w13 defeat → campaign aborted
   immediately, stack shut down, config restored idle — before any analysis.
3. **Abort investigation** ran the predeclared mechanism scan (serving / economy
   / corner-hypothesis vs control) → cleared pi3, kept the run training-valid,
   and **set the escalation rule** (any further sub-15 ⇒ stop).
4. **§1 checkpoint gate** (beat matched random control) returned NULL → iteration
   **stopped**, exactly as predeclared; the favorable outcome trend was recorded
   but did **not** override the null decision surface.

No production change: `bc_v2_f_s1` remains the qualified live student; machine
restored idle (`student_enabled=false`, pin `bc_v2_f`).

## Fork for the operator (decision needed; iteration halted meanwhile)

Recorded in `reports/wp2/residual_checkpoint_verdict.md`:

1. **Extend n under a new predeclared design** — the pi4 3/3 trend and the load
   confound both argue the test was underpowered; e.g. 6 more learned runs (pi4
   frozen) + 6 fresh teacher-only control runs on a load-matched machine,
   victory-rate as the primary endpoint, predeclared before launch.
2. **Larger θ** (Amendment F-1 revision) — 5° may bound the achievable effect
   below detectability; the Phase-1 dose-response was monotone, arguing headroom.
3. **Temporally-extended residuals** — the Phase-1 decay profile (teacher cancels
   within k ≈ 10–20 ticks) caps single-tick rotation; state-dependent sustained
   maneuvers are the mechanism the probe could not test.
4. **Redirect effort to the shop layer** — this session's live observations (rich
   exits w10/w17/w18, banked-gold death at w19) show large, legible headroom in
   economy conversion, where deterministic fixes have repeatedly paid off (v126).

## Artifacts

| artifact | content |
|---|---|
| `reports/wp2/residual_checkpoint_verdict.md` | §6 NULL verdict, honest labeling, 4-option fork |
| `reports/wp2/residual_checkpoint_compare_v1.{json,md}` | full-stream comparison, per-run + stratified + CIs |
| `reports/wp2/residual_pi3_arm_selection.md` | two-arm λ ruling (stratified \|δ\|) |
| `reports/wp2/residual_pi3_wave13_abort_investigation.json` | wave-15 abort + mechanism scan + escalation rule |
| `reports/wp2/residual_checkpoint_load_covariate.json` | STS2 machine-load asymmetry |
| `reports/wp2/residual_null_diagnostics.md` | regularizer-implicated collapse, targeted advantage |
| `reports/wp2/v126_evidence_rich_exit_w10.json` | teacher-owned shop evidence (v126 candidate) |
| `models/registry/residual_pi3.json`, `residual_pi4.json` | checkpoint manifests (`kind: residual_actor`) |

Residual actors: **pi3** (sha `689C1C64…AD26F`, iteration 3, arm A `λ₀ = 0.001`),
**pi4** (sha `16414822…497A4`, iteration 4, `λ₀ = 0.001`, 247,510-state pool).
Both are residual-teacher-base control (§14.3), archived, **not** production
candidates. Production student: **`bc_v2_f_s1`** (unchanged). See
`docs/MODEL_REGISTRY.md`.
