# Stage F2 interim look — 10 per arm (runs 1-20)

Date: 2026-07-25. Design: `.tmp/wp2_stage_f2_design.md` (BINDING).
Schedule: `reports/wp2/f2_schedule.json`.

## Scope of this look — predeclared

The design permits ONE interim look after 10 per arm, and restricts it to
**SAFETY and FUTILITY only**. No efficacy peeking. No extension beyond
20/arm regardless of what is seen here.

Accordingly the primary hierarchical endpoint (victory > combat progress >
HP-AUC, as P(random P run outranks random T run) with bootstrap CI) was
**NOT computed** at this look. `scripts/wp2_f2_endpoint.py` was not run.

## Raw series (from `reports/wp2/f2/r*.json`, not from a running tally)

| idx | arm | result | wave | dmg |
|---|---|---|---|---|
| 1 | T | defeat | 20 | 168 |
| 2 | P | defeat | 20 | 164 |
| 3 | T | victory | 20 | 24 |
| 4 | P | defeat | 17 | 78 |
| 5 | P | defeat | 20 | 64 |
| 6 | T | defeat | 13 | 51 |
| 7 | T | defeat | 17 | 61 |
| 8 | P | victory | 20 | 112 |
| 9 | T | victory | 20 | 73 |
| 10 | P | victory | 20 | 124 |
| 11 | P | victory | 20 | 19 |
| 12 | T | defeat | 20 | 101 |
| 13 | T | defeat | 20 | 60 |
| 14 | P | defeat | 20 | 249 |
| 15 | T | victory | 20 | 43 |
| 16 | P | defeat | 17 | 168 |
| 17 | P | defeat | 20 | 164 |
| 18 | T | defeat | 17 | 136 |
| 19 | P | victory | 20 | 84 |
| 20 | T | victory | 20 | 272 |

T last_wave series: `[20, 20, 13, 17, 20, 20, 20, 20, 17, 20]`
P last_wave series: `[20, 17, 20, 20, 20, 20, 20, 17, 20, 20]`

## Gate 1 — SAFETY

Criterion: the pi4 (P) arm showing sub-wave-15 deaths at a rate the teacher
arm does not.

- P: **0** sub-15 deaths out of 10.
- T: **1** sub-15 death out of 10 (run 6, wave 13).

**No safety signal.** The direction is the opposite of the concern — the
only early death in the campaign so far is in the control arm. At n=10 this
is one event and carries no inferential weight either way; it simply does
not trip the gate.

## Gate 2 — FUTILITY

Criterion: win-probability CI already excluding any meaningful benefit.

Victory rate is 4/10 in both arms. At this n the interval on the difference
is far too wide to exclude a meaningful benefit in either direction, so the
futility condition is **not met**. Note the logic: futility requires the CI
to be *narrow enough* to rule benefit out; a wide CI is a reason to
continue, not to stop.

## VERDICT: CONTINUE to 20 per arm

Neither gate fires. Runs 21-40 proceed on the committed schedule.

## Provenance / integrity at this look

- Policy version across all 20 runs: `teacher_v1-0.1.125-gun-wp1` (single value).
- Capture schema hash across all 20 runs: `95B6444796A21FD44E94113B75BA2097BC381D5F72ED784F9B9A4A99DD46D951`
  (single value) — i.e. no v127 build contaminated the campaign.
- Exclusions: **none**. No game crash, no corrupted telemetry, no collector
  abort, no control-loop breach. Every P-arm sidecar stream ended with
  0 fallbacks and 0 errors; observed `model_ms` p99 stayed near 2 ms against
  a 40 ms breach threshold.
- One aborted run is logged separately in `aborted_runs.jsonl` (the r11
  sidecar-less start); it was killed at wave 1, its artifacts deleted, and
  run 11 was relaunched correctly. It is not among the 20 above.

## Covariate note (recorded, not adjusted for)

Machine load changed mid-campaign: STS2 worker count ran 9-12 for most of
runs 1-14, dropped to 0 for runs 15-20, and returned to 6 by run 21. Per-run
counts are in `covariates.jsonl`. The randomized blocking is the design's
mechanism for absorbing this; no analysis change is made on account of it,
and the primary endpoint remains as predeclared.

## P-arm serving verification (the r11 lesson)

Every P run since r11 was verified twice: sidecar `listening` confirmed in
its log BEFORE the collector launched, and mid-run serving confirmed via
`handshake_ok == 1` plus a `sigma == 0.0` delta distribution.

A refinement worth recording: the handoff's delta signature band
(p50 ~0.04-0.06 deg, p99 ~0.23-0.36) is a **mid-run prefix** heuristic, not
a run-level invariant. Measured full-stream values vary materially across
runs of the same frozen policy — p50 0.038 / 0.052 / 0.093, p99 0.51 / 0.61 /
1.36, max 2.02 / 2.26 / 3.71 (all within the +-5 deg cap). This is expected:
pi4 is deterministic in its policy, not in the states it meets. Arm identity
is therefore established by `handshake_ok`, the `sigma` field, and non-zero
serving volume — not by the delta magnitude falling in a narrow band.
