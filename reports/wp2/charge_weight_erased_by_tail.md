# The charge-aware weight works perfectly — and the safety tail erases it 72x

**Date:** 2026-07-29. Mod `0.2.54`, 4 trials, ~20 min.
**This is the definitive demonstration of the override blocker, on a real treatment.**

## The treatment

`calm_threat_mult` (default 1.0 = exactly inert): threat weight applied to enemies that are **not**
currently charging, where charging is `|v| / speed_stat > CHARGE_RATIO_THRESH (1.5)`. A charging
enemy keeps full weight. Written defensively — a missing velocity is treated as charging, so an
absent signal can never make the agent bolder than the shipped policy.

This directly implements the operator's model, which the archive confirmed: `pursuer` is the only
wave-17 type that charges, it causes 61-73% of damage, and the human's edge is *temporal* — it
closes on a walking pursuer (−0.087) where the agent backs away (+0.056).

**Readback, predeclared:** the charging-vs-walking differentiation must move from the agent's
**+0.061** toward the human's **+0.219**.

## The result — measured at two points in the pipeline

Wave 17, nearest pursuer within 600 u, 2 trials per arm on one fixture:

| | charging | walking | **differentiation** |
|---|---|---|---|
| **DESIRE** (`_build_desire` output) | | | |
| control (1.00) | −0.431 | −0.128 | **−0.303** |
| treatment (0.25) | −0.412 | −0.325 | **−0.087** |
| | | | **shift +0.216** |
| **FINAL COMMAND** (`teacher.action`) | | | |
| control (1.00) | +0.091 | +0.055 | **+0.036** |
| treatment (0.25) | +0.053 | +0.014 | **+0.039** |
| | | | **shift +0.003** |

**The treatment moved the desire by +0.216 — almost exactly the human's differentiation of +0.219 —
and the pipeline attenuated it to +0.003. A factor of 72.**

The knob is not broken. It does precisely what it was designed to do, at precisely the intended
magnitude, at the layer it was applied to. **Everything between `_build_desire` and the motor
command throws that away.**

Note also that the desire-level differentiations are **negative** (the desire points *toward* the
pursuer on average) while the final command's are **positive** (away). The tail does not merely
damp the signal; it inverts the sign of the underlying behaviour.

## What this establishes

The standing rule from `desire_is_discarded.md` — *assume any `_build_desire` change is inert until
a readback on the final command proves otherwise* — was inferred from angles between the desire and
the command. **It is now measured directly on a treatment: 72x attenuation.**

That converts a heuristic into a quantity. Three knobs have now failed the same way:

| knob | layer | desire-level effect | final-command effect |
|---|---|---|---|
| `engage_distance_scale` (spring) | `_build_desire` | not measured | 2.2% over a 6.7x dose |
| `engage_distance_scale` (boundary) | `_build_desire` | not measured | none (within-dose spread larger) |
| **`calm_threat_mult`** | `_build_desire` | **+0.216, as designed** | **+0.003** |

The third is the informative one, because it is the first where the desire-level effect was measured
and confirmed correct. The other two are now much more likely to have been *correct implementations
that were also erased*, rather than wrong ideas.

## Where the lever must go

**Into the safety tail** — `_finale_projectile_safety` → `_finale_wall_safety` →
`_finale_body_safety` — which owns the command on 50-88% of wave-17 ticks, with the wall path
dominant. The charge signal should modulate the tail's own threat model, not the desire field's.

Concretely, `_finale_body_safety` scores candidate directions by clearance against enemy bodies.
It almost certainly treats all enemies identically (the desire field did). A charge-aware clearance
weight there would act on the layer that actually decides.

**Do not simply move the multiplier and hope.** The same readback applies, and the tail's clearance
scoring is a different kind of computation from a force weight — this needs reading before writing.

## Caveats

- **2 trials per arm, one fixture.** The attenuation factor (72x) should not be quoted to precision.
  The qualitative result — full-magnitude effect in the desire, none in the command — is not
  n-sensitive, because the desire-level shift matches the design intent almost exactly.
- The knob does have *a* systemic effect: both charging and walking levels fell ~0.04 at the final
  command. It made the agent globally slightly less retreat-prone without differentiating. That is
  consistent with the weight applying to every non-charging enemy on the field, not only the pursuer.
- `CHARGE_RATIO_THRESH = 1.5` matches the offline analysis. Because non-charging types sit at exactly
  1.00, anything in (1.0, 1.38) would classify identically for them; the threshold only trades off
  how much of a pursuer's own charge window counts.
