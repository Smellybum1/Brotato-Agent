# Both engagement knobs are inert — the standoff is emergent, not commanded

**Date:** 2026-07-29. **NO-GO.** 9 trials, ~45 min of machine time.
**Supersedes the "clears Gate 0" claim in `engagement_knob_gate0.md`, which rested on a
confounded correlation.**

## What was claimed, and why it was wrong

`engagement_knob_gate0.md` argued that the standoff is set by the **shortest weapon range**, on two
grounds: the source says so (`potential_field.gd:1881`, *"Optimal DPS band = shortest weapon range"*),
and across **272 agent trials** the realised standoff tracks the shortest weapon range monotonically
by bin, Pearson **r = 0.377**.

**That correlation is between BUILDS, not within one.** Builds with longer-ranged weapons plausibly
differ in many other ways that affect positioning. Reading a causal lever off a cross-build
correlation is precisely the error a dosed experiment exists to catch — and it caught it.

## Experiment 1 — dosing the `engage` spring: INERT

Build `0.2.51`. Dev knob `engage_distance_scale`, a pure multiplier applied immediately after
`engage *= BotConfig.DPS_ENGAGE_SCALE` in `_build_desire`. One trial per dose, same fixture.

| dose | median nearest-threat | ratio to shortest weapon range |
|---|---|---|
| 0.30 | 490 | 1.055 |
| 0.65 | 502 | 1.059 |
| 1.00 | 461 | 0.973 |
| 2.00 | 500 | 1.055 |

**A 6.7x dose range moved the standoff by 11 units — 2.2% — with no monotone response.** The 0.65
arm moved the mediator the *wrong way* (in-range fraction 0.3111 → 0.2130).

## Experiment 2 — dosing the `at_weapon_range` boundary: ALSO INERT

Experiment 1 pointed at the real mechanism. `potential_field.gd:1554-1564`: when
`at_weapon_range` (`nearest_d <= weapon_max * 1.02`, `weapon_max` = **shortest** weapon range), the
"Kill residual charge into the pack" block strips `1 - ENGAGE_STRAFE_INWARD_DAMP` = **82%** of any
inward force component. That is an absorbing boundary at 1.02x the shortest weapon range, and it
matches the measured ratio of 1.062 exactly. It looked conclusive.

Build `0.2.52` re-points the knob to multiply that boundary. Prediction: dose 0.40 should park the
agent at a ratio near 0.41.

| dose | run | ratio | in-range fraction |
|---|---|---|---|
| 0.40 | run_1785310363_17664 | 0.902 | 0.2718 |
| 0.40 | run_1785310652_35284 | 1.045 | 0.2894 |
| 0.65 | run_1785310012_37066 | 0.979 | 0.2830 |
| 1.00 | run_1785309701_13186 | 0.997 | 0.2484 |

**Predicted 0.41 at dose 0.40; observed 0.902 and 1.045.** The two same-dose trials differ by 0.14,
which is larger than any trend across the doses. No dose-response.

In-range fraction drifts up slightly (0.2484 → ~0.28) but non-monotonically and well inside
trial noise at n = 1-2. It comes nowhere near the human band of 0.4417.

## Conclusion

**The ~1.0x-shortest-weapon-range standoff is EMERGENT, not commanded.** Neither the `engage` spring
nor the `at_weapon_range` boundary sets it. It presumably falls out of the balance between enemy
repulsion, the strafe term and the safety tail — where an equilibrium happens to land near weapon
range rather than being placed there.

The **diagnosis still stands**: the agent converts 1.7x less of the pack into targets than a human
(in-range fraction 0.2801 vs 0.4417, perfectly separated), and it stands at 1.062x its shortest
weapon range against the human's 0.631x. That is measurement, and it is unaffected.

What is refuted is the **lever**. We do not currently have a knob that moves the standoff.

## What this cost, and what it bought

9 trials, ~45 min. It bought the deletion of a plausible, well-argued, source-supported hypothesis
that would otherwise have been the basis of a 64-trial preregistered campaign — a campaign that
would have compared a treatment arm to a control arm **that behave identically**, and reported a
null after ~5 hours.

## Lessons recorded

1. **A cross-build correlation is not a lever.** r = 0.377 over 272 trials, monotone by bin, plus a
   source comment stating the intent — and a within-build dose refutes it. Confounding does not
   announce itself.
2. **Verify the flag's EFFECT, not its self-report — this now has two more instances.** Both builds
   reported the dose correctly in `run_start`, both passed arm validation, and both were
   behaviourally dead. Validation proves the value arrived; only a behavioural readback proves it
   did anything.
3. **Over-dose to separate "broken plumbing" from "small effect".** The 0.30-vs-2.00 pair settled in
   two trials what a 0.85/0.75/0.65 ladder would have left ambiguous for a dozen.

## Repo and machine state

The `engage_distance_scale` knob is **kept**, defaulting to **1.0**, which is exactly inert (a
multiply by one at both sites). It is documented in-source as a measured null so nobody re-derives
it. Deployed build `0.2.52` matches the repo; 707 tests green; config disarmed; machine idle.

One trial failed as `game_exited_before_summary` at dose 0.40. Re-running that dose gave **2/2 valid
victories**, so it was a transient launch failure, not an instability introduced by the change.
