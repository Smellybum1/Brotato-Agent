# §38 — Gate 0 for a positive-score lexicographic DPS constraint

**Written 2026-08-04, BEFORE computing any §38 constrained surface, choice, flip, or stability
result.** §37 is fully exposed input: its weak additive doses through `lambda=4` failed because only
63/409 decisions flipped, while the unconstrained higher-DPS surface passed at 100/409. This packet
does not extend that dose ladder.

## §38a — Mechanism and rationale

Nominal-D5 failure is clearance-limited (§28), the decision layer is danger-blind, and §37 showed
that immediate effective-DPS alternatives exist often enough but weak additive score perturbations
cannot overcome the incumbent margins. The mechanism tested here changes the ordering rule rather
than increasing the coefficient:

> On an already-authorized nominal-D5 buy, preserve the incumbent scorer's positive/negative
> acceptability boundary, then make immediate effective weapon DPS lexicographically decisive among
> candidates whose incumbent score is strictly positive.

The `score > 0` boundary is the safeguard. It is not fitted to §37's margins: zero is the existing
shop action's natural boundary against `shop_go`, and negative/vetoed/unscored candidates remain
unavailable. The constraint cannot create a buy, spend extra gold, admit a skipped candidate, or
override a hard negative. It only chooses which already-affordable, already-positive candidate is
bought.

## §38b — Fixed population, replay, and exact choice rule

Use the same immutable population and reconstruction as adjudicated §37:

- 16 terminal, era-matched `0.2.79-wp2-capture` nominal-D5 Ranger runs;
- every `shop_buy` in waves 1–11 remains the **policy denominator** (known from §37: 409);
- only free-slot, non-truncated, fully joined, trusted, baseline-reproduced boards are rankable;
- all other decisions remain unchanged while staying in the policy denominator;
- marginal term `m_i = 100 * immediate_effective_weapon_DPS_gain_i / max(current_DPS, 1)` uses the
  §37 replay, permanent-stat ledger, Gun-set bonus, and exact item/weapon/combine handling.

For each rankable decision:

1. reproduce the incumbent as `argmax(score)`;
2. form shortlist `P = {candidate i: score_i > 0}`;
3. if the incumbent is not in `P`, leave the decision unchanged;
4. otherwise select the member of `P` with maximum `m_i`;
5. ties in `m` retain the incumbent; remaining ties use recorded row order.

The rule is single-dose and deterministic. There is no coefficient, searched threshold, or fallback
ladder. Danger 0–4, waves after 11, full-slot boards, non-buy actions, and all untrusted surfaces are
exactly inert.

## §38c — Controls before results

The analyzer must print denominators and these controls before any §38 result. A failure returns
**VOID** without computing the constrained surface:

1. **arm validity:** exactly 16 terminal D5 Ranger runs at the fixed mod and unlock stamp;
2. **offer/row join:** at least 99%;
3. **loadout trust:** at least 95% of otherwise-eligible decisions;
4. **ordinary-weapon gain parity:** at least 99% within the §37 1%/0.01 tolerance;
5. **baseline reproduction:** at least 99%;
6. **null constraint:** disabling the lexicographic rule flips exactly 0 decisions;
7. **positive-boundary control:** synthetic negative- and zero-score high-DPS alternatives cannot
   enter `P`, while a positive-score high-DPS alternative does;
8. **tie control:** equal-`m` alternatives retain the incumbent.

The §37 control bars are unchanged. The three earlier control-only VOID files remain measurement
history, not evidence for or against §38.

## §38d — Gate bars

All bars must pass:

1. **constrained reachable/flip surface ≥20% of the full policy denominator;** a decision is
   constrained-reachable exactly when a strictly positive-score alternative in `P` has
   `m_alt > m_incumbent`. Under the fixed rule every such decision must flip.
2. **median `m_new - m_incumbent ≥5` percentage points** among flips;
3. **strictly positive marginal-DPS gain on at least 90% of flips;**
4. **median per-run sum of optimistic one-step fractional improvements ≥0.33** across all 16 runs.

The per-run sum is the same necessary-condition upper bound as §37, not a causal trajectory.

## §38e — Stability and concentration safeguards

Because decisions within a run are dependent, the mechanism must not pass by one-run concentration:

- compute 16 leave-one-run-out policy flip rates; **all must be ≥18% and their median must be ≥20%;**
- at least **12/16 runs** must contain one or more flips;
- no single run may contribute more than **20% of all flips**.

These are deterministic stability checks over the fixed archive, not inferential confidence bounds.

## §38f — Reported diagnostics

Report controls and exclusions first, then:

- constrained reach/flips over the 409 policy decisions and over eligible decisions;
- delta-`m`, incumbent score, selected score, score sacrifice, and selected/incumbent score ratio;
- flips by wave, run, and category transition;
- per-run optimistic sums, run coverage, maximum run contribution, and all 16 leave-one-out rates;
- zero/negative candidates vetoed by the safeguard, always with their denominator.

A passing Gate 0 licenses only implementation planning and a separately preregistered fixed-build
live screen. It does not license a campaign automatically and does not establish realized DPS.

## §38g — Prediction fixed before computation

**Prediction: PASS, narrowly on exposure.** §37 already establishes a 24.45% unconstrained ceiling
and 15.40% flips under `lambda=4`. I expect the natural positive-score boundary to admit enough of
the remaining score-margin cases to land between 20% and 24.45%, with the already-observed positive
gain/magnitude/planning properties preserved. I expect the leave-one-run-out and concentration bars
to pass because §37's opportunity surface spans the 16-run cohort rather than a single run.

The main falsifier is explicit: if fewer than 82/409 decisions have a positive-score higher-DPS
alternative, the mechanism remains too narrow and no campaign is licensed.
