# §33 — Gate 0 for lowering `BOSS_FINALE_BODY_PACK_CLEARANCE` (the admission floor)

**Written 2026-08-03, before the analysis is run.** It reuses §32's already-collected data, so see the
exposure disclosure below — the bars are carried over UNCHANGED from §32 precisely so there is no new
bar to tune.

## The lead, and why it is worth one exact calculation

§32 established that the lane RANKING is not where in-range opportunity is lost (Gate 0a median
headroom 0.0455 < 0.05; p25 = 0.0000). The exploratory follow-up pointed at the ADMISSION GATE
instead: it withholds a median 0.0968 in-range on 60.1% of captures, ~3x what the ranking withholds.

The gate's binding constant is **`BOSS_FINALE_BODY_PACK_CLEARANCE = 160`**. The floor is
`body_floor = max(45, min(PACK, highest_body_clearance − body_slack))`, and because median
`highest_body_clearance` is 365 the `min()` **saturates at PACK on ~75% of captures**. §31 dosed
`body_slack` and deliberately left PACK unscaled (scaling both breaks monotonicity), so **the constant
that actually sets the floor at D5 has never been dosed.**

## ⚠️ I PREDICT THIS FAILS. That is why it is worth pre-registering.

§32's own reasoning says lowering the floor raises only the CEILING (mean best-in-range 0.5830 → 0.6344
at floor ≤80) while **the ranking selects by continuity, not in-range, so it will not spend what the
gate releases.** This document therefore pre-registers a test of **my own prediction of a null.**
Recording the prediction in advance is what stops a null being reported as "expected all along" and a
hit being reported as "obvious in hindsight".

⭐ There is a real chance of a non-null in an unwelcome direction: the newly admitted lanes are the
LOW-clearance ones, and if the agent's momentum points into the pack they may be MORE aligned with
`_prev_move` than the current pick. That would flip decisions while making position and safety worse.
**Both directions are reported; a flip is not scored as a success unless it also improves in-range.**

## Method — an EXACT offline counterfactual, no new runs

The §32 campaign (8 D5 ranger runs, `0.2.76`, era 179/48) recorded every candidate lane's
`x, y, body, proj, pen, skip` plus the floors and `prev_move`. That is everything the admission rule
consumes, so the rule can be re-evaluated at any PACK value P:

```
highest_body_clearance = max(body) over lanes with proj >= projectile_floor
body_floor(P)          = max(45, min(P, highest_body_clearance − slack))     slack = 35 (wave<=12) else 20
admitted(P)            = {proj >= projectile_floor} ∩ {body >= body_floor(P)}
                         ∩ {pen <= min(pen over that set) + 20}
chosen(P)              = argmax over admitted(P) of score
```

⚠️ `0.2.76` zeroed the score terms on SKIPPED lanes, so a gated-out lane's score is not stored. It is
**recovered**, not assumed: `align_i = 14.0 · dot(cand_i, baseline)` is an overdetermined linear system
once two non-parallel lanes are admitted (median admitted is 15), so `baseline` is solved by least
squares and every lane's score re-derived as `(proj − pen) + 14·dot(cand,baseline) + 85·dot(cand,prev)`.
*(`0.2.77` now records the baseline directly; this recovery is what makes §33 answerable without it.)*

### ⛔ THREE CONTROLS. The counterfactual is VOID unless all three pass.

1. **Baseline recovery fidelity.** The recovered baseline must reproduce every admitted lane's recorded
   `align` to **≤ 1e-2**. That tolerance is set by the instrument, not by convenience: `align` is
   `stepify`-quantised to 0.01, so the achievable floor is ~5e-3 and a tighter bar would fail on
   rounding alone. Pilot on one run: recovered on **3958/4000 = 0.9895**, max-residual p50 4.26e-03.
   Captures that fail are EXCLUDED AND COUNTED, never silently dropped.
2. **Admission reproduction at P = 160.** Simulated `admitted(160)` must equal the recorded skip flags.
   (Already measured at 6016/6018 = 0.9997 in §32's exploratory pass.)
3. **Selection reproduction at P = 160.** `chosen(160)` must equal the recorded `sel_x/sel_y`. This is
   the control §32's pass did NOT have — reproducing the admitted SET does not prove the re-derived
   SCORES rank it correctly, and the scores are what the counterfactual turns on.

**Bar: controls 2 and 3 must each hold on ≥99% of analysable captures.** Below that, report the failure
and stop; do not report a counterfactual built on a rule that cannot reproduce the observed decision.

## Analysis set

Ranked captures (`route.exit == "ranked"`) with ≥2 admitted lanes, ≥1 living threat, a resolvable
baseline, and a weapon range. All exclusions printed with counts before any result.
Runs: the 8 §32 runs. `run_1785754086_12860` stays excluded (force-killed, truncated).

## Bars — CARRIED OVER FROM §32 UNCHANGED

- **GATE 0a (decision flip):** at some **P ∈ {120, 80, 45}**, the emitted lane changes on **≥20%** of
  analysis-set captures.
- **GATE 0b (realised improvement):** on FLIPPED captures, **median in-range gain ≥ 0.05**, using the
  same moving-threat `inrange_after(cand, 0.60s)` definition as §32.
- ⛔ **MONOTONICITY:** realised gain must be non-decreasing as P falls, up to saturation. Non-monotone
  ⇒ NOISE, not partial success. (§31's signature; declared before the data, again.)

**Both gates must pass.** A flip rate without a gain is the damage-tilt failure repeating: flipping a
decision is not improving it.

## Exposure disclosure

This reuses data I have already analysed on the in-range endpoint (§32), so I am not blind to it. Two
mitigations, both structural rather than promissory: **(a)** the numeric bars are §32's, carried over
verbatim rather than chosen after seeing anything; **(b)** the primary quantity here — the emitted lane
under a counterfactual floor — was **never computed in §32**, because `0.2.76` did not store the scores
needed to compute it. So the specific number the gates turn on is genuinely new.

## Reported, not barred

- Safety: median body clearance of the new lane vs the old, and how far below the ORIGINAL floor the
  new pick sits. By construction every flip takes a lane today's gate rejects — that is the mechanism,
  and it is exactly why a pass here would still need the §31 low-HP-exposure veto in a live screen.
- Reach: analysis-set share of all captures, so any flip rate can be converted to a share of ALL
  decisions.
- The direction of the change in in-range on flipped captures, including if it is negative.

## What passing or failing means

Passing licenses a live screen of a lowered PACK constant on the in-range mediator, still subject to
the §31 safety veto and still short of any survival claim. Failing closes the admission-gate branch —
and with §31, §32 and the continuity check already closed, that would close the movement-lever class
opened by [[brotato-in-range-headroom]] at a total cost of two campaigns and zero shipped behaviour
change.
