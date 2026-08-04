# §44 — Gate 0 for a safety-revalidated route-conversion latch

**Pre-registration. Written 2026-08-04 after §43, before the stateful latch replay is computed.**
No mod edit, deploy, game launch, or new run is part of this gate.

## Prior result and mechanism distinction

§42 delivered 1,715 guarded final-route changes but moved realised in-range only +0.0097. §43 fixed
the ambiguity: those changes formed 1,241 episodes with median duration **0.051 s**, only **1/1,238**
matched episodes lasted 0.60 s, and median normalized forward execution was **0.377**. Gross
projection calibration passed (median absolute error 0.071, Spearman 0.685). The selected defect is
therefore temporal authority, not another PACK/deadband dose or a projection rewrite.

This is not the closed continuity-weight branch from §§31–33. Continuity remained a preference in a
ranking recomputed every tick; changing its weight did not make a delivered conversion stateful.
The proposed latch starts only after the exact §41 conversion wins, then temporarily bypasses soft
ranking while reapplying current hard safety. The existing `_finale_committed_escape` is wave-20-only;
this gate is restricted to waves 1–11 and does not cite that finale mechanism as evidence.

## Fixed archive and question

Use only the eight era-valid §40/§41 D5 Ranger route-score runs, build
`0.2.76-wp2-capture`, waves 1–11, full fresh capture stream:

- `run_1785754965_28036`
- `run_1785755965_44537`
- `run_1785756364_37779`
- `run_1785756664_17215`
- `run_1785757198_83975`
- `run_1785757742_9445`
- `run_1785758500_77660`
- `run_1785758909_7977`

The question is deliberately narrower than a trajectory counterfactual: **after a §41 conversion
trigger, does a direction within one 24-lane angular bin of that heading remain available for up to
0.60 seconds while satisfying the current tick's unchanged safety rules?** Recorded player and
threat states remain the incumbent trajectory, so a pass proves shadow availability and authority,
not realised safety or in-range benefit under the diverged path.

## Fixed state machine

The analyzer first reproduces §40's production reconstruction and §41's stateless guarded policy.
It then walks each run in fresh `capture_seq` / timestamp order.

When no latch is active:

1. only a fully reconstructable `route.exit == "ranked"` capture may trigger;
2. reconstruct PACK 80 admission, the §41 0.80 body-retention/subcritical guard, 0.60-second
   moving-threat in-range projection, and strict >0.05 deadband exactly;
3. if §41 selects a different lane, emit it and latch that normalized heading at time `t`.

While a latch is active, at each subsequent fresh capture in the same wave through `t + 600 ms`:

1. require a reconstructable current route candidate set; absence is an **unobservable release**,
   never silently treated as safe;
2. rebuild current PACK 80 admission, including the current projectile floor and enemy-penalty slack;
3. apply the unchanged §41 body guard relative to the current reconstructed production lane:

   ```
   if current_body >= 45:
       candidate_body >= max(45, 0.80 * current_body)
   else:
       candidate_body >= current_body
   ```

4. among safe candidates, choose the one with minimum angular distance to the latched heading;
5. retain only if that distance is at most **15.1°**, one fixed 24-direction lane interval plus
   telemetry quantisation tolerance; otherwise release before emitting an override;
6. release immediately on wave change, missing/reconstruction-failed route data, no safe near-heading
   candidate, or after the first safety-revalidated capture at or beyond 0.60 seconds. A released
   latch cannot retrigger until the next capture.

There is one horizon, one angular boundary, and no dose ladder. Current one-step in-range gain is
reported but is not a retention rule: requiring every retained tick to win the same myopic comparison
would recreate the §43 failure by construction.

Latch duration is `min(0.60, last_retained_ts - start_ts + median fresh same-wave interval)`.
An episode reaches the horizon only when a retained fresh capture lies within **±75 ms** of
`t + 600 ms`, the §43 future-matching boundary. Missing futures are excluded from the horizon-rate
denominator and reported; they are not assigned zero.

## Controls — printed before latch results

The result is `VOID` unless all hold:

1. exactly 8/8 fixed summaries pass §40's version, instrument, terminal, character, danger, opener,
   and era checks;
2. capture sequence and timestamps are strictly increasing after explicit stale removal, with stale,
   parse, and non-increasing counts reported;
3. §40 floor, admission, selection, and vector controls retain their original ≥99% bars;
4. stateless §41 reproduction returns exactly **11,457/23,501** guarded flips and 15,274 unguarded
   flips, with 0 disabled-policy changes;
5. at least one stateful trigger and one non-trigger occur in every run;
6. every retained candidate passes projectile, body-retention, subcritical, enemy-slack, and ≤15.1°
   checks; category sums equal their denominators;
7. self-tests cover: trigger, safe retention, expiry, unsafe release, 15.1° boundary, wave-boundary
   release, missing-route release, overlapping-trigger suppression, and a zero-future exclusion.

Controls and denominators print before any duration or authority statistic. Every zero is paired with
its denominator.

## Archive observability rule

The v129 route instrument records candidate scores only after the ranking loop is reached; early
returns such as `baseline_kept` carry no rows. Define observability as:

```
reconstructable future captures while a latch is active
-------------------------------------------------------
all fresh future captures encountered while a latch is active
```

The archive is adequate for a closing failure only if observability is at least **90%**. Unobservable
captures conservatively release the shadow latch.

- If all mechanism bars below pass despite lower observability, the lower bound is a valid `PASS`.
- If a mechanism bar fails and observability is below 90%, verdict `DATA_LIMITED`; the mechanism is
  not closed and a default-inert all-exit revalidation instrument is licensed.
- If a mechanism bar fails with observability at least 90%, verdict `FAIL` and this latch is closed.

## Preregistered mechanism bars

All must pass for `PASS`:

### Temporal availability

- median latch duration **≥0.30 s**;
- at least **25%** of eligible latch episodes reach **0.60 s**;
- at least **7/8 runs** contribute a horizon-reaching episode;
- leave-one-run-out horizon rate: minimum **≥20%**, median **≥25%**;
- largest run contributes at most **25%** of horizon-reaching episodes.

The first two are the exact failed §43 boundaries; they are not fitted to this archive.

### Safety and authority

- projectile-floor preservation: **100%** of retained steps;
- §41 body-guard satisfaction: **100%**;
- subcritical non-worsening: **100%**;
- enemy-slack admission: **100%**;
- angular bound: **100%**;
- at least **20%** of retained future steps differ from the recorded current lane. This positive
  control proves the latch has counterfactual command authority rather than merely following a route
  that the incumbent independently retained.

## Reported, not deciding

- stateful triggers and suppressed overlapping stateless triggers, by run and wave;
- release reasons with denominators;
- duration p10/median/p90 and fractions ≥0.30/0.60 s;
- retained-step angular error, body ratio, current projected in-range difference, and recorded-command
  angular difference;
- first-trigger projected gain and §42 terminal context, labeled non-causal;
- observability overall, by run, and by route exit.

## Prediction

**Prediction: `DATA_LIMITED`.** §43 makes safe temporal availability plausible, but the archive's
route candidate rows are intentionally absent on early-return captures. I expect those missing rows
to terminate enough shadow latches that the conservative lower bound will miss at least one temporal
bar while observability falls below 90%. The falsifier is a lower-bound pass: if ≥25% reach 0.60 s
despite conservative release, no new collection is needed before implementation design.

## Interpretation contract

A `PASS` licenses an exact implementation design plus source/offline parity work, followed by a
separately preregistered live mediator/safety screen. `DATA_LIMITED` licenses only the smallest
default-inert all-exit safety-revalidation instrument and its acquisition protocol. `FAIL` closes
this bounded latch. No outcome licenses a survival campaign, changes §42's null, or permits retuning
the 0.60 s / 15.1° / safety boundaries after the result.
