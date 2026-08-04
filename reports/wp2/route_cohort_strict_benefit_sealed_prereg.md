# §47 strict-benefit cohort commitment — sealed acquisition and offline Gate 0

Date: 2026-08-04  
Operator authorization: granted after the §46 verdict  
Live scope: six fixed observational-instrument runs; the §47 mechanism is shadow-only

## Question

Does §46's objective-persistence mechanism become implementation-worthy if it is forbidden to
change direction unless the best current safety-admitted candidate improves projected engagement of
the original threat cohort by at least **0.05** over the recorded emitted command?

The 0.05 deadband is carried from §46's frozen conditional-benefit bar. It is not selected from a
new dose sweep. The state still retains only original threat identities and expiry time for 0.60
seconds; every candidate heading is recomputed from current geometry. A step below the deadband
emits the recorded command and keeps the episode active.

§46 is and remains `FAIL`. Its four runs are discovery data only and are excluded from every §47
confirmatory calculation. §47 uses six newly acquired, sealed runs.

## Prediction

**Prediction: PASS.** The post-§46 discovery screen found strictly positive authority on
2,420/8,529 = 28.37% of retained steps, with per-run rates 27.28–31.86%, median positive advantage
0.162–0.200, and positive-only integrated advantage 0.0547–0.0711. Those figures motivate this
test; they do not count toward it. The principal falsifier is a sealed run with <20% strict-benefit
surface or <0.02 integrated advantage. A second falsifier is loss of the §46 persistence/safety
properties on new runs.

## Frozen acquisition

- Exactly **six valid terminal runs**, fixed slots 1–6, one instrument arm `I`.
- Ranger, nominal and observed Danger 5, pistol-first opener.
- Installed build `0.2.81-wp2-capture`; policy `teacher_v1-0.1.129-gun-wp1`.
- Exact starting era: items 179, weapons 48, hashes `2018397571` / `1530875081`.
- `clearance_guarded_conversion=true`, `route_scores_enabled=true`, and
  `route_latch_revalidation_enabled=true`; the §47 strict-benefit mechanism is **not** implemented
  live and cannot affect actions.
- All other experimental arms inert; body/engagement/calm scalars 1.0; `time_scale=1.0`.
- No stop-on-win, outcome-based extension, replacement of a valid defeat, automatic top-up, or
  optional stopping. Terminal wave and victory are context only for this gate. A nominal D5 victory
  still satisfies North Star 1 as an event but does not alter the fixed six-run analysis.
- Any infrastructure-invalid slot pauses acquisition. It is not automatically replaced; fault and
  remedy must be recorded before another launch. Era drift stops acquisition before another launch.

The driver, analyzer, and synthetic tests must be committed before slot 1 launches. The six run IDs
are written to the acquisition manifest in slot order; analysis may use only those IDs.

## Operational sequence

1. Verify no `Brotato.exe` or acquisition driver is running and read back `auto_start=false`.
2. Verify the installed mod archive is byte-identical to repo source and re-read build/policy
   constants from the installed archive. No version bump or deploy is planned.
3. Because the preceding §45 acquisition ended with a force-kill, run
   `deploy_mod.py --repair-launch` before slot 1. This rewrites config, so arm only afterward.
4. For each slot, arm and read back every fixed config field, baseline `mod_ready.json`, launch one
   bounded `--runs 1 --min-wins 0 --no-deploy` collection with a distinct state file, require a fresh
   exact `mod_ready.json`, and certify the terminal summary before recording the run ID.
5. After every force-killed terminal run, run `deploy_mod.py --repair-launch` before the next slot.
6. After slot 6, stop the attributed Brotato PID if any, set `auto_start=false`, disarm conversion and
   both route instruments, and read the parked config back from disk.

`auto_start=false` is never treated as proof that a live game stopped. A process check is required.

## Controls before any result

The analyzer prints controls and denominators first and returns `VOID` without result bars unless all
hold:

1. exactly six unique manifest-owned terminal summaries match build, policy, Ranger,
   requested/observed D5, pistol opener, fixed arm, and exact era; errors, hangs, illegal actions,
   and summary nonfinite fixes are zero;
2. fresh waves-1–11 capture sequences and timestamps are strictly increasing after explicit stale
   removal; parse/stale/non-increasing counts are printed;
3. all-exit revalidation is enabled on 100% of fresh route blocks, includes nonzero ready and honest
   not-ready denominators, reproduces ranked `x/y/body/proj/pen` rows ≥99.9%, and supplies ready rows
   on ≥99% of living `baseline_kept` captures;
4. emitted action matches the route-selected heading on ≥99.9% of a nonzero denominator;
5. live clearance conversion occurs in every run and its gain/body/subcritical guards pass 100%;
6. living threat `instance_id` is nonmissing and unique on ≥99.9% of living captures, pooled and in
   every run;
7. trigger exclusions are categorized; each run has ≥50 eligible episodes and ≥500 retained future
   steps, at least one strict override, and at least one deadband/no-override step;
8. synthetic tests cover trigger, suppression, current-tick revalidation, strict threshold at
   0.049999/0.050000, deterministic ties, resolved cohorts, horizon, wave change, missing input,
   no-safe-candidate release, and zero-denominator handling.

Every zero is printed with its denominator. A required zero denominator makes the gate `VOID`.

## Exact shadow state machine

The trigger population and 0.60-second state are §46 unchanged:

- start on a delivered `conversion_applied == true` capture with ready revalidation, a nonempty
  uniquely identified living cohort, complete player/range/action input, and a same-wave capture in
  the 600 ± 75 ms future window;
- retain only run, wave, start/expiry timestamps, and original living threat IDs;
- suppress new triggers while active; a release capture cannot retrigger;
- release on horizon, wave change, missing/nonfinite required input, identity failure, no current
  safety-admitted candidate, missed future window, or stream end;
- keep an input-complete resolved cohort active through the horizon while retaining the recorded
  command.

On each active future capture, reconstruct candidates from current revalidation rows. A candidate
must satisfy current projectile floor, body floor, `lowest_penalty + 20`, and §41's body guard:
reference body ≥45 requires candidate body ≥`max(45, 0.8 × reference_body)`; below 45 requires
candidate body ≥reference body.

Project player and original-cohort threats 0.60 seconds using current positions, velocities, speed,
and current maximum positive weapon range. Resolved or projected-in-range original members score 1;
others score 0. Select greatest cohort value, then higher body clearance, higher projectile
clearance, lower enemy penalty, and lexicographic rounded heading.

Let `advantage = selected cohort value - recorded-action cohort value`.

- If advantage ≥ **0.05**, shadow-emit the selected candidate (`strict override`).
- If advantage < 0.05, shadow-emit the recorded command (`deadband retention`) while preserving the
  active cohort state.
- If the cohort is fully resolved, shadow-emit the recorded command with zero advantage.

No angular latch or prior heading exists. The 0.05 comparison uses unrounded values with a numerical
tolerance of `1e-12` only for floating representation; 0.049999 fails and 0.050000 passes.

## Equal-run result surface

The independent evidence unit is the terminal run. Capture counts differ mechanically with terminal
wave and therefore are not allowed to make a long run dominate the primary result. For each run,
compute:

- eligible episode count and horizon rate;
- duration median;
- retained-step count;
- strict override rate = strict overrides / retained steps;
- integrated strict advantage = sum of advantage on strict overrides / all retained steps;
- median strict-override advantage;
- safety and deadband correctness counts.

Pooled capture-weighted values are reported as descriptive context only. No subsampling, run cap, or
post-result weighting is permitted. This run-level design is a new sealed test motivated by §46's
concentration failure; it does not revise or rescue §46.

## Frozen PASS bars

All must pass:

1. Every run has median episode duration ≥0.30 s.
2. Every run has horizon rate ≥25%, and all six contribute at least one horizon episode.
3. Every selected strict override satisfies projectile, body, subcritical-body, and enemy-admission
   invariants; deadband correctness is 100% (`advantage ≥0.05` iff strict override, excluding resolved
   cohorts which never override).
4. Every run has strict override rate ≥20%; the equal-run median is ≥25%.
5. Every run has integrated strict advantage ≥0.02; the equal-run median is ≥0.03.
6. Every run's median strict-override advantage is ≥0.05.

`PASS` requires every control and bar. `FAIL` means controls passed but one or more bars failed.
`VOID` means validity, instrumentation, branch, or denominator controls failed. There is no
insufficient-sample label because the per-run episode/step minima are controls fixed above.

## Interpretation contract

A PASS licenses implementation of this exact strict-benefit cohort mediator plus parity tests, then
a separately preregistered live mediator/safety screen. It does not license a survival campaign.
A FAIL closes this exact deadband mechanism. A VOID licenses only repair of the identified validity
fault under a separately documented continuation; it does not permit silent replacement or top-up.
