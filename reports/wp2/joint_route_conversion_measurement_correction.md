# §40a — measurement correction before the final joint-route replay

**Written 2026-08-04 after the first §40 output and before recomputing it.** No bar, policy constant,
run, wave, or validity rule changes.

## What the initial analyzer did wrong

The analyzer stored each candidate's projected in-range fraction under the route telemetry key
`(round(x, 4), round(y, 4))`, then required the number of distinct keys to equal the number of route
rows. Production can emit duplicate candidate headings after four-decimal telemetry quantisation.
Those rows have the same movement direction and therefore the same in-range counterfactual; a key
collision is not missing geometry.

The bad check excluded **4,231** captures as `degenerate_lane`. A denominator-only diagnostic over all
**25,788** wave-1–11 ranked captures found:

- zero-length candidate vectors: **0/25,788**;
- at least one rounded-key collision: **5,944/25,788**;
- both conditions: **0/25,788**.

Thus the exclusion was entirely an analyzer artifact, not a production-data defect.

## Fixed rule

A capture is excluded as degenerate only if a candidate's `inrange_after` is actually undefined or
the reproduced current selection lacks a value. Rounded-key collisions are counted and reported but
remain in the denominator. Since equal headings have equal projected positions, sharing their
in-range value is exact for the endpoint. The production-score tie-break still operates on the
original rows.

The initial output is preserved as `joint_route_conversion_result_initial_invalid.json`. It reported
a Gate 0 failure on the two geometry-safety bars, but it is not the §40 result because its denominator
violated the preregistration. The corrected analyzer and this note are committed before the full replay
is run again. All preregistered bars remain binding.
