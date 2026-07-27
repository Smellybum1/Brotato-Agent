# Pre-registration — is 2x or 4x safe when 8x is not?

**Committed BEFORE trial 1.** Build mod `0.2.49-wp2-capture`, policy
`teacher_v1-0.1.129-gun-wp1`, repo FROZEN against identity-constant edits for the
duration. Driver `scripts/wp2_timescale_doseresponse.sh`, out `.tmp/ts_dose/`.

## Why this is not a repeat of a settled question

8x is refuted and stays refuted (`timescale_equivalence_verdict.md`). But that
arm was **CPU-SATURATED: it requested 8x and achieved 6.20x**, only 0.78 of
nominal. Two different mechanisms fit the same result:

- **Saturation** — the engine cannot keep up and defers or reorders something.
  Then any scale the machine sustains is CLEAN, and the failure is a **cliff**.
- **Acceleration itself** — some game logic is not scale-invariant at any speed.
  Then degradation is a **slope** and appears at 2x and 4x too, smaller.

**These make opposite predictions and one campaign separates them.** That is the
whole point; without it, "use a smaller scale" is a guess.

## Design

- Arms **1.0x (control), 2.0x, 4.0x** — all three in EVERY round, same 8 predator
  fixtures, so the control is never stale relative to a treatment arm.
- 8 fixtures x 4 rounds x 3 arms = **96 trials, 32 pairs per comparison.**
- Pairing is by **(fixture, round)**; between-fixture SD (20.7) exceeds
  within-fixture SD (18.8), so pairing is not optional.
- Two comparisons: 2.0x vs 1.0x, and 4.0x vs 1.0x, each against the SAME
  contemporaneous control.

## Primary outcome and margin

**`damage_taken`, paired difference (accelerated − 1.0x).** Win rate is pinned at
1.000 for the control on these fixtures and cannot discriminate.

**Equivalence margin Δ = 19 damage**, unchanged from the 8x protocol: the
resolution of the screen-tier campaigns acceleration would serve. At 32 pairs the
expected CI half-width is ~13 < 19, so the margin is attainable and the test is
not vacuous.

**No multiplicity correction, deliberately.** Two comparisons share one control.
Correcting would WIDEN the intervals and make it EASIER to declare equivalence —
the wrong direction when the burden of proof is on acceleration being safe.

## Decision rule (amendment A1 rules from the 8x protocol, applied per arm)

Evaluated in order; exhaustive and mutually exclusive:

1. any structural gate fails → **FAIL**
2. CI wholly outside `[−19, +19]` → **FAIL**
3. `CI ⊂ [−19, +19]` and `0 ∈ CI` → **EQUIVALENT**
4. `CI ⊂ [−19, +19]` and `0 ∉ CI` → **SMALL SHIFT** (usable only for paired
   same-scale campaigns; never pooled with 1.0x data or archived baselines)
5. otherwise → **INCONCLUSIVE**

**A5 loss clause carries over and OUTRANKS the CI:** an accelerated arm recording
**≥ 3 more losses** than the control yields INCONCLUSIVE regardless of the damage
CI. Win rate can only move downward from a pinned 1.000, so that is the one
direction in which a ceiling-pinned metric carries information.

**If both 2x and 4x are EQUIVALENT, 4x supersedes** — there is no reason to take
the smaller speedup. **No escalation is pre-registered in any branch.** One
campaign, one answer.

## Structural gates

**G1 — acceleration took effect. WRITTEN TO ITS OWN PURPOSE THIS TIME.** In the
8x protocol I required the achieved ratio to land in `[6.5, 9.5]`, which
conflated *acceleration took effect* with *acceleration hit its nominal figure* —
a throughput fact about this machine that has nothing to do with validity. The
observed 6.20 failed that band while proving the effect decisively. So:

- **2.0x arm: achieved ratio > 1.5.  4.0x arm: achieved ratio > 2.5.**
- **NO UPPER BOUND.** An upper bound tests throughput, not effect.

Ratio = median(`n_captures`/`duration_ms`) of the arm ÷ the control's.
`duration_ms` is `OS.get_ticks_msec()`, real time and unscaled, so this is a
signature the control arm structurally cannot produce.

**G2 — validity.** ≥ 28/32 valid per arm; every valid trial has wave set exactly
`[20]`, `len(boss_paths) == 1`, `boss_entity == "predator"`.

**G3 — build identity.** Every trial: `finale_pivot_projectiles == true`,
`mod_version == "0.2.49-wp2-capture"`,
`policy_version == "teacher_v1-0.1.129-gun-wp1"`.

**G4 — no dead rounds.** Every arm produces ≥ 1 valid trial in every round.

**G5 — precision (INCONCLUSIVE, not FAIL).** ≥ 28 pairs must form per comparison.

## THE MECHANISM TEST — declared in advance so it cannot be fitted afterwards

Record **achieved ÷ nominal** per arm. The 8x arm scored **0.78**.

- If 2x and 4x both achieve **≥ 0.95** of nominal **and** come back EQUIVALENT,
  **saturation is implicated** and the safe operating rule is "any scale this
  machine sustains", with headroom checked per machine.
- If an arm achieves **< 0.90** of nominal, it was itself saturated. Its result
  must be read as *"saturated at this scale"*, **not** *"this scale is unsafe"* —
  and the honest conclusion is that this machine's ceiling sits below it.
- If an arm achieves ≥ 0.95 of nominal and STILL degrades, saturation is refuted
  and acceleration is unsafe in principle. **Close the line permanently.**

## Reporting

Raw 32-pair table per comparison BEFORE any summary statistic, per
`brotato-measurement-discipline`. Achieved-ratio series printed per arm, not just
its median.
