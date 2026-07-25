# Stage F2 VERDICT — deterministic pi4 vs pure teacher (40/40 runs complete)

Date: 2026-07-26. Binding design: `.tmp/wp2_stage_f2_design.md` (predeclared
before run 1). Schedule: `reports/wp2/f2_schedule.json` (seed 20260725,
committed `f1bc027`). Endpoint calculator: `scripts/wp2_f2_endpoint.py`
(committed `9a39840`, 26 tests). Full output: `f2_endpoint.md` / `f2_endpoint.json`.

## VERDICT: NULL — combat-residual work CLOSES

The predeclared POSITIVE condition (win-probability CI excluding 0.5 upward)
is **not met**. Per the design's verdict rules, this triggers the
NULL/NEGATIVE branch:

- **bc_v2_f_s1 remains the production student.** Unchanged.
- **pi4 is archived.** No further combat-residual iteration.
- **Effort redirects to the shop layer** (v126+).
- **theta stays 5 degrees.** The design forbids raising it either way, and
  nothing here argues for it.

## Primary endpoint (predeclared)

Hierarchical run outcome (victory > combat progress > alive-and-healthy AUC),
as P(random P run outranks random T run). Run-level cluster bootstrap,
10,000 resamples, seed 0. Ticks were never units of analysis.

| statistic | value |
|---|---|
| **P(P outranks T)** | **0.4500** — 95% CI **[0.2725, 0.6350]** |
| CI vs 0.5 | **straddles 0.5** |
| point-estimate direction | T (teacher) favored |
| pairs | 400 (20 x 20) |

## Secondaries (non-gating, reported as predeclared)

| metric | T (pure teacher) | P (deterministic pi4) |
|---|---|---|
| n_runs | 20 | 20 |
| **victory_rate** | **0.5000** (10/20) | **0.3500** (7/20) |
| final_wave mean | 18.700 | 18.950 |
| final_wave median | 20.000 | 20.000 |
| combat_progress mean | 19.0528 | 19.0622 |
| auc_norm mean | 0.9046 | 0.9121 |

## Reading this honestly

**This is a null, not a demonstration that pi4 is worse.** The CI
[0.2725, 0.6350] is wide and contains values on both sides of 0.5. The
campaign was powered to detect a large effect, not to certify equivalence;
a real benefit smaller than the design could resolve is not excluded by
these data, and neither is a real harm.

**The secondaries disagree with each other, and that disagreement is
informative.** Victory rate favors the teacher (0.50 vs 0.35) while mean
combat progress (19.062 vs 19.053) and mean AUC (0.9121 vs 0.9046)
marginally favor pi4. The primary is victory-first by construction, so it
follows the victory rate. The honest summary is that pi4 runs survived
fractionally longer and healthier on average while converting fewer of
those runs into wins. At n=20/arm none of these gaps is resolvable —
the progress and AUC differences are third-decimal and carry no weight.

**The deployment question is what was asked, and it is answered.** The
design framed F2 as the DEPLOYMENT question: should the frozen residual ship
on top of the production teacher? On the predeclared endpoint the answer is
no — there is no demonstrated gain to justify the added serving dependency,
and the North Star secondary (victory rate) points the wrong way.

## Consistency with Stage F phase 2

This is the second consecutive null on the residual line. The
§6 checkpoint verdict (`e9b358a`, `residual_checkpoint_verdict.md`) found
all CIs straddling zero against a random control. F2 asked the different
and more decision-relevant question — frozen deterministic pi4 vs the
actual production teacher — and also returns null. Two independent nulls
on the same mechanism is the basis for closing the line rather than
iterating further, which is exactly what the predeclared rule specifies.

The pi4 3/3 victory sweep noted at the end of Stage F phase 2 did not
reproduce: across 20 deterministic pi4 runs the victory rate is 0.35. That
sweep was flagged at the time as "suggestive, not evidence." It was
correctly discounted.

## Data integrity

- **40/40 runs completed. Zero exclusions.** No game crash, no corrupted or
  incomplete telemetry, no collector abort, no control-loop breach.
- **Single build throughout**: policy `teacher_v1-0.1.125-gun-wp1`, mod
  `0.2.34-wp2-capture`, capture schema hash
  `95B6444796A21FD44E94113B75BA2097BC381D5F72ED784F9B9A4A99DD46D951`.
  No v127 build touched the campaign.
- **Every P run verified served**, twice: sidecar `listening` confirmed in its
  own log before the collector launched, and mid-run `handshake_ok == 1` with
  `sigma` observed exclusively as 0.0. Across all 20 P runs: **0 fallbacks,
  0 errors**; `model_ms` p99 stayed near 2 ms against a 40 ms breach bar.
- One aborted run (`aborted_runs.jsonl`): the r11 sidecar-less start, killed
  at wave 1, artifacts deleted, relaunched correctly. Not among the 40.
- Interim look at 10/arm (`interim_look_10_per_arm.md`) was safety/futility
  only; the primary was not computed there.

### Covariate note (recorded, not adjusted for)

Machine load varied across the campaign (STS2 workers 9-12 for most of runs
1-14, 0 for runs 15-20, 0-6 thereafter; per-run counts in
`covariates.jsonl`). Randomized blocking is the design's mechanism for
absorbing this and no analysis change was made on its account. One covariate
line (run 22) was written malformed by a PowerShell `.Count` quirk on a
single-object result and was repaired to the measured value before analysis;
all 40 rows parse.

### Correction carried from this session

The handoff's delta-signature band (p50 ~0.04-0.06 deg, p99 ~0.23-0.36) is a
mid-run PREFIX heuristic, not a run-level invariant. Full-stream values across
P runs ranged p50 0.026-0.093 and p99 0.24-2.02 (max 3.71, all within the
+-5 deg cap). Arm identity is established by `handshake_ok`, the `sigma`
field, and serving volume — not by delta magnitude landing in a narrow band.
Any future residual campaign should use the former, not the latter.

## What happens next

1. **Deploy obligations unblock.** F2 is done and the machine is idle, so the
   v126 + v127 + loot-dash bump can proceed (one version bump, one smoke,
   zero-violation audit). Authoritative branch is `claude/keen-wu-fa36b5`;
   the handoff's pointer at `elastic-mcnulty-7aa022` is stale.
2. **Shop layer becomes the active line**, per the verdict rule. v126's
   surplus-reroll evidence chain is the natural starting point.
3. **pi4 archived**; `.tmp/residual_pi4.pt` should be moved somewhere durable
   rather than left in `.tmp/` if the checkpoint is worth keeping for the
   record.
4. Any future student/residual campaign on a v127 build needs the
   capture-schema compatibility fix first (encoder + sidecar handshake gate on
   exact hash equality).
