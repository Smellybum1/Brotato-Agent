# Stage F Phase 2 — §6 checkpoint verdict (2026-07-25)

Verdict authority: primary session (delegated, operator standing autonomy).
Predeclared gate (phase2 design §1): at ~250-300k cumulative residual
ticks, the learned residual must beat the matched random control (Phase-1
uniform probe, same theta bound) on damage taken and wave outcomes; else
stop and report. Comparison: `residual_checkpoint_compare_v1.{json,md}`
(full-capture-stream damage, stratified, 10k bootstrap, seed 0).

## Verdict: NULL — gate not passed; Phase 2 iteration stops here

No metric on the predeclared surface resolves away from zero:

| metric (learned − control) | diff [95% CI] |
|---|---|
| victory rate | +0.238 [−0.262, +0.714] |
| final wave | +0.26 [−2.41, +2.76] |
| overall damage rate | +0.00004 [−0.00002, +0.00010] |
| wave-20 damage rate | −0.00039 [−0.00171, +0.00076] |
| risk≥0.5 damage rate | +0.00024 [−0.00135, +0.00187] |

The learned residual is NOT shown to beat random perturbation. Per the
predeclared rule, growing-batch iteration stops at this checkpoint.

## What the data does show (honestly labeled, not adjudicated)

- Outcome point-estimates favor the learned arm: 4/7 victories (57%) vs
  2/6 (33%); final-wave median 20 vs 19.5. Not resolved at this n.
- Damage point-estimates are mixed: overall slightly WORSE for learned
  (+0.00004), wave-20 and risk≥0.75 better (−0.00039, −0.00332), risk
  0.5-0.75 worse. All unresolved.
- Within-arm trend worth recording: the three pi4-served runs went 3/3
  victories (damage 107/135/22 — 22 is the cleanest 20-wave run ever
  recorded in this project), after pi3's 1/4. Small n, and pi4 differs
  from pi3 by one more data batch, not architecture. Suggestive of
  iteration-over-iteration improvement; not evidence at this n.
- The learned arm carried both known handicaps: the wave-13 defeat
  (investigated, mechanism scan clean — `residual_pi3_wave13_abort_
  investigation.json`) and the machine-load asymmetry (control collected
  unloaded; learned under 8-12 STS2 workers —
  `residual_checkpoint_load_covariate.json`).

## Honest classification

All 13 runs are residual-teacher-base control (§14.3): teacher policy
with bounded angular rotation of its combat movement action (|delta| ≤ 5
deg), shop/economy fully teacher-owned. No independent-policy claims.

## Fork for the operator (decision needed; iteration halted meanwhile)

1. **Extend n under a new predeclared design** — the outcome trend
   (pi4 3/3) and the load confound both argue the test was underpowered;
   e.g. 6 more learned runs (pi4 frozen) + 6 fresh teacher-only control
   runs on a load-matched machine, victory-rate as primary endpoint,
   predeclared before launch.
2. **Larger theta** (Amendment F-1 revision) — 5 deg may bound the
   achievable effect below detectability; Phase-1 dose-response was
   monotone, arguing headroom exists.
3. **Temporally-extended residuals** — the Phase-1 decay profile
   (teacher cancels within k≈10-20 ticks) caps single-tick rotation
   effects; state-dependent sustained maneuvers are the mechanism the
   probe could not test.
4. **Redirect effort to the shop layer** — this session's live
   observations (rich exits w10/w17/w18, banked-gold death at w19,
   `v126_evidence_rich_exit_w10.json`) show large, legible headroom in
   economy conversion, where deterministic fixes have repeatedly paid off.

No production change: bc_v2_f_s1 remains the qualified student; machine
restored idle (student_enabled=false, pin bc_v2_f).
