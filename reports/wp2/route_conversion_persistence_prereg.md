# §43 — Why delivered route conversion did not persist

**Pre-registration. Written 2026-08-04 after the §42 verdict but before any trajectory-persistence
aggregate is computed.** Schema inspection was limited to one applied capture to verify that
`ts_ms`, `capture_seq`, `teacher.action`, and threat `instance_id` exist. No episode duration,
future-geometry, displacement, or calibration result was inspected.

## Prior result and question

§42 is closed: the exact guarded policy changed the live final route **1,715/9,026** times across
4/4 treatment runs, with median one-step projected gain **0.1538** and zero live guard violations,
but realised trial-level in-range fraction moved only **+0.0097** (`p = 0.9429`). Safety was clean.

This diagnostic does not rerun §42 or try another dose. It asks which structural failure occurred:

1. **TRANSIENT / REVERSAL:** the 20 Hz controller immediately replaces conversion headings, so the
   player never executes the projected 0.60-second path;
2. **PROJECTION MISCALIBRATION:** the selected path is executed, but moving-threat projection does
   not predict the cohort that is resolved or inside weapon range 0.60 seconds later;
3. **PERSISTENT BUT INSUFFICIENT:** the path is executed and prediction is calibrated, implying that
   one-step in-range opportunity is not the load-bearing clearance quantity.

The result selects the *kind* of structural fork worth instrumenting next. It cannot reopen §42 and
does not license a live campaign.

## Fixed population and data

Only the four §42 treatment runs, fixed before this analysis:

- `run_1785820603_11732`
- `run_1785821156_74146`
- `run_1785822002_63879`
- `run_1785823323_53547`

Build `0.2.80-wp2-capture`, Ranger, Danger 5, exact §42 era, waves 1–11. Every fresh
`combat_capture` is retained in timestamp order. Primary episode population begins at captures where
`route.conversion_applied == true` and the immediately preceding fresh capture is absent or did not
apply conversion.

An **episode** is a maximal sequence of fresh captures with `conversion_applied == true` on every
member and adjacent timestamp gaps at most **100 ms**. The 100 ms boundary is fixed from the 50 ms
controller period and permits one delayed capture; it is not fitted to episode durations. A route
block without conversion ends the episode. Stale or non-increasing `capture_seq` is excluded and
reported.

For each episode start at time `t`:

- initial heading = normalized `teacher.action` / route selected heading;
- target future time = `t + 600 ms`, matching the fixed §41 horizon;
- future capture = nearest fresh capture in the same wave within **±75 ms** of that target;
- original cohort = living enemies plus bosses at `t`, keyed by `instance_id`;
- weapon range = longest positive held `max_range` at `t`.

Episode starts without a living identified cohort, positive range, player position, or matched future
capture are excluded with separate denominators. No missing future is assigned zero.

## Controls — printed before diagnostics

The result is `VOID` unless all hold:

1. exactly 4/4 fixed run summaries pass the §42 build, policy, character, danger, opener, era,
   terminal-completeness, and treatment-arm checks;
2. fresh capture timestamps and `capture_seq` are strictly increasing after explicit stale removal;
3. at least one applied conversion and one non-conversion route block occur in every run;
4. on applied captures, route selected heading and emitted `teacher.action` agree within Euclidean
   distance **0.001** on at least **99.9%** of a nonzero denominator;
5. at least **90%** of eligible episode starts have a future capture within the fixed ±75 ms window;
6. at least **99.9%** of living threats have a non-null `instance_id`, and IDs are unique within each
   capture;
7. for every analysed episode, original-cohort categories at +0.60 s — disappeared/resolved,
   surviving in range, surviving out of range — sum exactly to the original cohort denominator;
8. self-tests cover a one-capture episode, a multi-capture episode, a 101 ms split, future matching,
   heading normalization, cohort resolution, and a zero-denominator exclusion.

A disappeared original threat is reported as **resolved**, not assumed killed: telemetry cannot
distinguish death from despawn. Early waves make despawn uncommon, but the label stays honest.

## Fixed diagnostics and thresholds

### A. Temporal persistence

Episode duration is `(last_ts - first_ts) + median fresh capture interval for that run`. Report raw
per-run and pooled episode counts, duration median/p10/p90, and:

- fraction lasting at least **0.30 s**;
- fraction lasting at least the full **0.60 s**.

Declare **TRANSIENT** if median duration is below **0.30 s** **or** fewer than **25%** of episodes last
0.60 s. These are controller-scale boundaries: six and twelve nominal 50 ms decisions.

### B. Executed displacement at 0.60 s

For each matched episode, compute player displacement from the episode start to the future capture.
Let `u` be the initial conversion heading and `speed` the start speed:

```
forward_progress = dot(displacement, u) / (speed * 0.60)
lateral_progress = abs(cross(displacement, u)) / (speed * 0.60)
```

Report distributions and per-run medians. Declare **REVERSAL / NON-EXECUTION** if pooled median
forward progress is below **0.50**. Negative values explicitly count as reversal; they are never
clipped to zero.

### C. Moving-threat projection calibration

At the future capture, match the original cohort by `instance_id` and calculate:

```
resolved_or_in_range = (resolved + surviving within start max_range) / original cohort
survivor_in_range     = surviving within start max_range / surviving original cohort
```

The first treats resolving a projected target as at least as useful as keeping it targetable. The
second is reported with its surviving-cohort denominator. Compare `resolved_or_in_range` with the
episode start's `conversion_selected_inrange` using median absolute error (MAE) and Spearman rank
correlation.

Declare **PROJECTION MISCALIBRATION** if MAE exceeds **0.20** or Spearman correlation is below
**0.30**, provided at least 30 matched episodes exist. Report both resolved and survivor-only forms;
only the preregistered resolved-or-in-range form decides the label.

### D. Diagnostic decision

Labels are not mutually exclusive and are reported in this priority order:

1. `TRANSIENT_REVERSAL` if A or B fails;
2. `PROJECTION_MISCALIBRATION` if C fails, whether or not A/B also fail;
3. `PERSISTENT_BUT_INSUFFICIENT` only if A, B, and C all pass despite §42's realised null.

If transient/reversal is present, the next viable mechanism is temporal commitment or hysteresis,
not another PACK/deadband dose. If calibration fails while execution passes, the next work is a
trajectory or direct-clearance objective, not commitment. If all pass, the in-range surrogate itself
is deprioritized in favor of direct kill/clearance consequences.

## Reported, not deciding

- All-capture conversion rate and per-run episode concentration.
- Initial projected gain by episode duration band.
- Heading changes on the first 0.20 s and 0.60 s.
- Original cohort size, resolved share, survivor-only in-range share, and wave distribution.
- §42 terminal waves, explicitly context only.

These may explain the diagnosis but cannot rescue or change it.

## Prediction

**Prediction: TRANSIENT_REVERSAL.** The route controller recomputes at roughly 20 Hz and §41 added no
commitment state. A conversion can be locally optimal at one capture and disappear as soon as the
candidate pool, continuity term, or threat positions move. The main falsifier is forward progress:
if the player executes at least half of the intended 0.60-second displacement and episodes commonly
last the full horizon, then projection calibration or the surrogate itself—not command persistence—
must explain §42.

## Interpretation contract

This is a post-null mechanistic diagnostic on already-collected data. It does not estimate a survival
effect, does not turn correlated captures into independent trials, and does not license implementation
by itself. Its only authority is to select one mechanism for a separately preregistered offline gate
or new instrument. No machine time is part of §43.
