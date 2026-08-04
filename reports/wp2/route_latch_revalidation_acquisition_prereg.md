# §45 — All-exit route-revalidation instrument and acquisition protocol

**Pre-registration. Written 2026-08-04 before the instrument is implemented, build 0.2.81 is
deployed, or any §45 run is launched.** §44 is `DATA_LIMITED`, not a latch pass or failure.

## Question and authority

§44's archive replay sees only **9,400/12,429 = 75.63%** of active future captures because the v129
route-score instrument records candidate rows after the `baseline_kept` early return. That return
alone forces 2,854/4,039 conservative latch releases. The raw 24-lane geometry already exists before
the return; it is simply not serialized.

This protocol has one purpose: collect enough **observational** all-exit candidate telemetry to rerun
the exact §44 state machine without the known missing-row defect. It does not implement the latch and
does not compare survival outcomes.

## Fixed instrument

Build `0.2.81-wp2-capture`, policy remains `teacher_v1-0.1.129-gun-wp1`. Add one default-false flag:
`route_latch_revalidation_enabled`.

When false, the new helper must return before allocating, iterating, or mutating any record. When true,
inside `_finale_body_safety` it serializes only values already computed for the current decision:

- every current sampled candidate's quantized `x`, `y`, body clearance, projectile clearance, and
  enemy penalty;
- the current projectile floor and enemy-slack reference;
- the incumbent pre-conversion body and projectile clearance used by the §41 guard;
- a readiness/reason field distinguishing a reconstructable candidate set from an earlier return.

The snapshot is taken before `baseline_kept` can return and, on ranked captures, before §41 may
replace the incumbent. It must not write `best_dir`, route score, conversion state, `_prev_move`, or
the emitted action. Existing `route_scores_enabled` remains a separate instrument.

Source/default-inert tests must prove the flag is false in field/controller/config plumbing, the
disabled branch returns before record mutation, telemetry summary and `mod_ready` expose the arm, and
all version literals move together. On ranked captures with both instruments enabled, the new raw
rows must reproduce existing route-score `x/y/body/proj/pen` values.

## Fixed acquisition

- **4 valid terminal runs**, all one acquisition arm `I`; no comparator and no outcome analysis.
- Ranger, nominal and observed Danger 5, pistol-first opener.
- Build `0.2.81-wp2-capture`, policy `teacher_v1-0.1.129-gun-wp1`.
- Exact era: items 179, weapons 48, hashes `2018397571` / `1530875081`.
- `clearance_guarded_conversion=true` so genuine §41 trigger episodes exist.
- `route_latch_revalidation_enabled=true` and `route_scores_enabled=true` for row-parity control.
- All other experimental arms inert; body/engagement/calm scalars 1.0; `time_scale=1.0`.
- Fixed sample of four. No stop-on-win, outcome-based extension, automatic top-up, or optional
  stopping. An infrastructure-invalid slot may be replaced only after its outcome-independent fault
  is documented. A valid defeat remains a trial. Era drift stops acquisition before another launch.

Terminal wave and victory are context only. A game victory would still satisfy North Star 1 as an
event, but cannot rescue a failed instrument gate or turn this into a win-rate experiment.

## Operational sequence

The acquisition driver and analyzer are committed before deployment. Then:

1. verify no `Brotato.exe` is running and config `auto_start=false`;
2. bump all version sites together, run focused then full tests;
3. deploy once with `--no-auto-start`; verify installed zip content equals repo bytes;
4. arm **after deploy**, read back every fixed field, and baseline/remove `mod_ready.json`;
5. launch one bounded slot at a time; require a fresh exact `mod_ready.json` and terminal summary;
6. after any force-kill, run `deploy_mod.py --repair-launch` before the next launch;
7. after slot 4, stop the attributed game PID if needed, set `auto_start=false`, disarm both route
   instruments and conversion, and read back the parked config.

The driver uses `--runs 1 --min-wins 0 --no-deploy` semantics per slot and a distinct state file.
The four slot IDs are committed to a manifest as collected; no run discovery by outcome.

## Controls — before any latch result

The acquisition is `VOID` unless all hold:

1. exactly 4 unique manifest-owned terminal summaries match build, policy, Ranger, requested/observed
   D5, opener, era, and every fixed arm; errors/hangs/illegal/nonfinite fixes are **0/4**;
2. fresh `combat_capture` sequence/timestamps are strictly increasing after explicit stale removal;
3. revalidation `enabled=true` is present on 100% of wave-1–11 route blocks and both a ready and an
   earlier-return/not-ready reason occur on nonzero denominators;
4. on ranked captures with both arrays present, one-to-one row-key coverage is ≥99.9% and
   `x/y/body/proj/pen` agree within their telemetry quantisation on ≥99.9%;
5. revalidation reports a positive candidate denominator on ≥99% of `baseline_kept` captures with
   living threats;
6. emitted action continues to match the route-selected heading on ≥99.9% of a nonzero ranked
   denominator; conversion applies on at least one capture in every run and obeys the §41 live guard
   on 100%;
7. source/self-tests cover flag-off null, ranked row parity, `baseline_kept` readiness, early-return
   reason, reset/no-stale behavior, and zero-denominator handling.

Controls, per-run denominators, and every zero print before any §44 replay statistic.

## Fixed data-sufficiency bars

After controls pass, reconstruct the §44 state machine without changing any §44 mechanism boundary.
The new dataset is sufficient only if:

- at least **1,000** stateful trigger episodes exist across all four runs;
- active-future revalidation observability is **≥99%** pooled and **≥98% in every run**;
- at least **99%** of `baseline_kept` active-future captures are reconstructable;
- at least **30** future-eligible episodes exist in every run.

If any fails, verdict `INSUFFICIENT_INSTRUMENT`; no latch result is computed and there is no post-hoc
run extension.

## Frozen §44 replay and decisions

If data sufficiency passes, apply §44 unchanged: 0.60-second latch, ±75 ms future window, PACK 80,
current projectile/enemy-slack admission, §41 0.80/45/subcritical body guard, nearest safe lane within
15.1°, immediate unsafe release, and current one-step in-range excluded from retention.

The §44 bars remain:

- median duration ≥0.30 s;
- ≥25% of eligible episodes reach 0.60 s;
- ≥7/8 is replaced only where the new population makes it nonsensical: **all 4/4 acquisition runs**
  must contribute a horizon episode;
- leave-one-run-out horizon rate minimum ≥20%, median ≥25%;
- largest run ≤35% of horizon episodes (four-run concentration analogue fixed before collection);
- projectile/body/subcritical/enemy/angular invariants 100%;
- ≥20% of retained future steps differ from recorded current route.

All other thresholds are carried exactly. The explicit 8-run-to-4-run coverage/concentration
translation is the only population change and is fixed before acquisition.

Decision labels:

- `PASS`: instrument controls/sufficiency and every latch bar pass; licenses exact latch
  implementation design and parity work, not live treatment;
- `FAIL`: instrument is sufficient and at least one latch bar fails; closes this bounded latch;
- `INSUFFICIENT_INSTRUMENT`: controls valid but a sufficiency bar fails;
- `VOID`: validity, parity, delivery, or invariant control fails.

No label licenses a survival campaign.

## Prediction

**Prediction: instrument sufficiency PASS and latch Gate 0 PASS.** The missingness is architectural,
not geometric: candidate rows are already computed before `baseline_kept`. On the visible subset,
8,469/8,469 retained steps were safe, 89.13% overrode the incumbent, median retained/current
in-range delta was +0.154, and median heading difference was 105°. I expect the newly visible
`baseline_kept` states to supply the sustained portion suppressed by §44's conservative release.
The falsifier is the unchanged 25% horizon bar after ≥99% observability; if it fails, the latch is
closed rather than widened or lengthened.

## Interpretation contract

This is instrument acquisition plus an offline shadow replay on recorded incumbent trajectories.
Even `PASS` cannot prove safety after the player diverges, mediator improvement, or survival benefit.
It licenses implementation engineering only, followed by a separately preregistered live
mediator/safety screen. Boundaries are not retuned and no extra acquisition runs are added after the
result.
