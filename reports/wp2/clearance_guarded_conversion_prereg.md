# §41 — Gate 0 for clearance-guarded route conversion

**Written 2026-08-04 before the guarded counterfactual is computed.** No live run, deploy, or game
launch is part of this gate.

## Prior result and the one new question

§40's joint PACK-80 plus lexicographic conversion controller passed every exposure and conversion bar
by a wide margin: 64.99% flips, median conditional in-range gain 0.25, integrated gain 0.0651. It
failed the geometry veto because median/p10 body-clearance retention fell to 0.726/0.516 and 10 lanes
newly worsened subcritical clearance.

This gate does not reinterpret §40 as a pass and does not adjust a failed boundary. It asks one new
question: **if the exact safety constraints declared before §40's result are made per-decision
admission rules, is enough conversion authority left to clear the unchanged bars?**

The constants are not fitted to §40's output:

- retain at least **80%** of the recorded lane's body clearance — §40's preregistered median bar;
- never newly worsen a lane below the production critical clearance of **45** — §40's preregistered
  subcritical rule and the existing production constant.

## Fixed policy — no ladder

Population, wave band, route reconstruction, moving-threat horizon and in-range definition are
identical to §40: the eight completed era-valid §32 D5 Ranger runs, waves 1–11, full capture stream,
`route.exit == "ranked"`, PACK fixed at **80**, horizon 0.60 s, and a strict in-range deadband of 0.05.

For each PACK-80-admitted candidate, retain it only when:

```
if recorded_body >= 45:
    candidate_body >= max(45, 0.80 * recorded_body)
else:
    candidate_body >= recorded_body
```

The recorded lane is always eligible. Among guarded candidates, choose the highest projected in-range
fraction, breaking exact ties with reconstructed production score, and emit it only for an in-range
gain strictly greater than 0.05. Projectile-floor admission and every other §40 route rule remain
unchanged.

There is one policy and no sensitivity dose. Lowering the ratio after seeing the result is forbidden.

## Denominators and controls — before results

The analyzer re-runs §40's full validity chain and prints all denominators and exclusions before any
guarded result. The counterfactual is `VOID` unless:

1. exactly 8/8 expected runs pass terminal-summary, version, instrument, character, danger, opener and
   era checks;
2. floor, PACK-160 admission and PACK-160 selection reproduction each pass at ≥99%;
3. a disabled policy changes exactly 0 analysis-set decisions;
4. PACK 80 both adds lanes and adds none on nonzero denominators;
5. the safety guard vetoes at least one PACK-80 candidate and is a no-op on at least one capture;
6. every selected guarded lane preserves the projectile floor and the two body-clearance rules;
7. the self-test demonstrates a guarded positive, an unsafe high-gain veto, a safe no-gain negative,
   a subcritical non-worsening case, and the inherited moving-enemy/joint-only controls.

The analysis denominator remains every §40-analysis-set capture, including captures on which the guard
leaves no improving alternative. Non-flips are not dropped. A zero requires that denominator.

## Preregistered bars — carried from §40 unchanged

All must pass:

### Exposure and stability

- guarded flips: **≥20%** of the analysis set;
- at least **7/8 runs** contribute a guarded flip;
- leave-one-run-out flip rate: minimum **≥18%**, median **≥20%**;
- largest run contributes **≤25%** of guarded flips.

### Conversion magnitude

- median in-range gain over guarded flips: **≥0.10**;
- integrated one-step gain across **all** wave-1–11 route blocks, assigning zero to non-flips and
  out-of-analysis captures: **≥0.02**.

### Safety invariants

- projectile-floor preservation: **100%**;
- body-clearance guard satisfaction: **100%**;
- subcritical non-worsening: **100%**.

The safety checks are design invariants now, not evidence of survival. A Gate 0 pass would still need
the §31 live low-HP-exposure veto.

## Reported, not barred

- Guard cost: guarded flips retained from §40's 15,274 unguarded flips.
- Captures/candidates vetoed by the guard, with denominators.
- Conditional body-clearance ratio distribution after guarding. It should be bounded by construction;
  reporting it verifies implementation rather than claiming a treatment effect.
- Per-wave flips and integrated gain, to expose a result confined to irrelevant early waves.

## Prediction

**Prediction: PASS.** §40 has enough margin—64.99% flips against a 20% bar and integrated gain 0.0651
against 0.02—that the preregistered guard can discard a large unsafe fraction and still retain a
material action surface. The main falsifier is integrated gain: safe alternatives may preserve many
small conditional wins while losing too much total conversion authority.

## Interpretation contract

A pass licenses implementing exactly this guard and running a separately preregistered mediator/safety
screen. It does not license a survival claim or a D5 campaign. A failure closes the ranked-route
conversion branch: the remaining measured opportunity would require giving up more clearance than the
project allowed before seeing it.
