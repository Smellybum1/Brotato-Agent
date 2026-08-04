# §46 route-cohort commitment — offline Gate 0 preregistration

Date: 2026-08-04  
Decision owner: primary agent  
Machine-time authorization: **none** — this gate is restricted to the fixed §45 archive.

## Question

Can the conversion mechanism persist its *objective* for 0.60 seconds without persisting a
movement heading?  At a qualified conversion, latch the identities of the living threats present
at that capture.  On every subsequent capture, recompute the safest currently admitted heading
that maximizes projected resolution or weapon-range engagement of that original cohort.

This is mechanism-distinct from the §44/§45 heading latch.  No heading, angular window, or prior
candidate is retained.  Only the original threat identities and the expiry time persist.

## Frozen population

Use only the four manifest-owned §45 runs, build `0.2.81-wp2-capture`, policy
`teacher_v1-0.1.129-gun-wp1`, Danger 5 Ranger/pistol, waves 1–11:

- `run_1785826116_89378`
- `run_1785826737_53506`
- `run_1785827267_71832`
- `run_1785827488_46830`

The source manifest is `.tmp/s45_route_latch_revalidation/manifest.json`.  No additional run,
wave, capture, resampling, or replacement is permitted.  The §45 1,000-episode sufficiency bar
belonged to that acquisition question and is not retroactively changed.  This gate fully
enumerates the fixed archive; it does not impose a new minimum count after observing §45's 885
heading-latch episodes.

## Gate sequence

1. Validate run identity, summary/build/policy/danger/unlock-pool fields, fresh capture ordering,
   instrument enablement, row parity, baseline coverage, emitted-heading delivery, and conversion
   guard controls against §45's committed counts.
2. Validate threat identity and input completeness before computing any mechanism result.
3. Run deterministic synthetic state-machine tests, including positive and negative branches.
4. Only if all controls pass, compute the cohort-commitment result and compare it with the frozen
   bars below.

Any failed control yields `VOID`; no result bars are computed.

## Exact state machine

### Trigger

A state episode starts only on a fresh waves-1–11 capture where the recorded route has
`conversion_applied == true`, revalidation is ready, the original living enemy/boss cohort is
nonempty and has unique nonmissing `instance_id` values, player position/speed and at least one
positive weapon `max_range` are present, and the recorded emitted action heading is finite and
nonzero.  A trigger with no same-wave capture in the preregistered 600 ± 75 ms future window is
ineligible and reported with a denominator.

The episode stores only: run, wave, start timestamp, expiry timestamp, and the original cohort's
instance IDs.  New triggers while active are suppressed and counted.  A capture that releases an
episode cannot also retrigger it.

### Current safety-admitted pool

On every active future capture, reconstruct candidates from the capture's revalidation rows.
Candidates must satisfy all of:

- projectile clearance ≥ the current `projectile_floor`;
- body clearance ≥ the current `body_floor`;
- enemy penalty ≤ current `lowest_penalty + 20`;
- §41 body guard against the current reference body clearance: when reference body ≥ 45,
  candidate body ≥ `max(45, 0.8 * reference_body)`; otherwise candidate body ≥ reference body.

These are current-tick constraints.  No value is inherited from the trigger capture.

### Cohort objective and selection

For each candidate, project the player for 0.60 seconds using current player position, current
speed, and the candidate unit heading.  Project each still-living original-cohort threat for the
same interval using its current position and velocity.  A cohort member scores 1 if it is already
absent from the current living threat set (resolved), or if its projected distance from the player
is no greater than the current maximum positive weapon range; otherwise it scores 0.  Cohort value
is the mean score over the original cohort.

Select the safety-admitted candidate with greatest cohort value.  Frozen deterministic ties are:
higher body clearance, then higher projectile clearance, then lower enemy penalty, then
lexicographic `(round(x, 4), round(y, 4))`.  If every original cohort member is already resolved,
retain the recorded emitted command and count an objective-complete step rather than manufacture
an override.

The comparison command is the recorded emitted teacher action at that capture, projected by the
same calculation.  An override means the selected candidate's rounded heading differs from the
recorded action's rounded heading.  Advantage is `selected cohort value - recorded-action cohort
value`.  No angular restriction exists.

### Release and duration

Release on the first of:

- same-wave capture at 600 ± 75 ms after the trigger (`horizon`);
- wave change;
- missing/nonfinite player, weapon-range, threat-identity, action, or revalidation input;
- no current safety-admitted candidate;
- passage beyond the 600 ± 75 ms window without a matching capture;
- stream end.

Duration is capped at 0.60 seconds and is computed using retained captures plus that run's median
same-wave capture interval, matching §44.  Resolved cohorts remain active to the horizon when
inputs remain valid; they do not release early.

## Controls and denominators

All must pass before result computation:

- exactly the four frozen unique runs and §45 summary invariants;
- raw/fresh/instrument-enabled `28,173/28,173/28,173`;
- revalidation-ranked row parity `215,901/215,901`, exact in `9,079/9,079` captures;
- living `baseline_kept` ready rows `15,457/15,457`;
- emitted/selected delivery `9,079/9,079`;
- conversion gain/body/subcritical guards each `1,824/1,824`;
- no parse, stale-sequence, or nonincreasing-timestamp faults;
- nonmissing and unique living threat `instance_id` on at least 99.9% of fresh captures with living
  threats, pooled and in every run;
- nonempty original cohort, complete trigger player/range/action input, and a matched future window
  on every eligible episode; every exclusion is categorized and counted;
- at least one eligible episode per run, at least one selected override per run, and at least one
  retained recorded-command/no-override step per run;
- synthetic tests prove trigger, suppression, current-tick revalidation, tie ordering, resolved
  cohort handling, horizon, wave-change, missing-input, and no-safe-candidate branches.

A zero numerator is reported with its denominator.  A zero denominator for any required rate makes
the gate `VOID`.

## Frozen PASS bars

All bars must pass:

1. Median episode duration ≥ 0.30 s.
2. At least 25% of eligible episodes reach the 0.60 s horizon.
3. Every run contributes at least one horizon episode.
4. Leave-one-run-out horizon rate is ≥ 20% for every exclusion and has median ≥ 25%.
5. No run contributes more than 35% of eligible episodes.
6. Projectile, body, subcritical-body, and enemy-admission invariants each hold on 100% of selected
   retained steps.
7. Overrides occur on at least 20% of retained future steps.
8. On override steps, median cohort advantage over the recorded action is ≥ 0.05.
9. Across all retained future steps, assigning zero advantage to no-override/objective-complete
   steps, mean cohort advantage is ≥ 0.02.

`PASS` requires every control and every bar.  `FAIL` means controls passed but at least one result
bar failed.  `VOID` means controls or required denominators failed.

## Prediction and interpretation

Prediction: **PASS**.  §44 found useful current-tick conversion authority but a fixed heading was
usually invalidated quickly.  Retaining only target identity should allow the chosen heading to
rotate as geometry changes while preserving the clearance constraints.  The most likely falsifier
is still short persistence: horizon rate below 25%, especially in a leave-one-run-out slice.

A PASS licenses implementation of this exact cohort-objective mediator for a separately
preregistered live qualification.  It does not license a campaign.  A FAIL closes this exact
0.60-second cohort-commitment mechanism on the fixed evidence; thresholds will not be altered
post-result.
