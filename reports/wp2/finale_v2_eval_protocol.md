# Finale v2 outcome evaluation — protocol (PREDECLARED, binding)

Written **before any evaluation trial was run**, 2026-07-27. Deployed build for both
arms: policy `0.1.128` / mod `0.2.39`, commit `4930e44`. Gate 1 record:
`reports/wp2/v0239_finale_v2_deploy_record.md`. Design: `reports/wp2/finale_v2_design.md`.

## Why both arms are run, rather than v2 against the published 0.700 baseline

The 28/40 = 0.700 [0.546, 0.819] baseline comes from **two fixtures captured 6 s apart
from ONE run**. The design already says it is "the paired reference, not the bar".
Comparing v2-across-11-builds against v1-on-one-build would confound arm with build —
build variation on this library is large (wave-19 HP spans 9-65, level 20-27). So **both
arms run on the same fixtures**, and the comparison is paired by build.

## Arms

| arm | `finale_v2` | controller on wave 20 |
|---|---|---|
| v2 | true | heading selection, 32 candidates, recompute every physics tick (60 Hz) |
| v1 | false | current stack: vector summation, recompute 1 tick in 3 (20 Hz) |

Everything else is identical — same ZIP, same policy version, same safety tail. The arm
is recorded by the mod in each run's `summary.json`; a trial whose recorded arm
disagrees with the arm requested is **invalidated**, not relabelled
(`finale_arm_mismatch`).

## Fixtures — fixed before running

Selection rule: `select_library(..., one_per_run=True)`, then drop the pre-shop half of
the un-provenanced legacy pair (`756e6461`, gold 619) keeping the post-shop half
(`4ab34bff`, gold 53), matching the collector's own convention so the trial does not
re-run the wave-19 shop. Ordered by `captured_at` ascending. List frozen at
`.tmp/wp2_finale_v2_eval_fixtures.json`.

**Predator — 11 builds.** Holdout rule, declared now: the **last 3 by capture time** are
held out.

| # | fixture | hp | lvl | role |
|---|---|---|---|---|
| 1 | `w19_boss_crab_20260726_134557_4ab34bffc43f89c3` | 56 | 21 | iteration |
| 2 | `w19_predator_20260726_161821_fc24b6eb79072a4d` | 47 | 21 | iteration |
| 3 | `w19_predator_20260726_165342_7149d1b7ab27f0a8` | 47 | 21 | iteration |
| 4 | `w19_predator_20260726_182307_6c32fe3d950f8d6e` | 65 | 21 | iteration |
| 5 | `w19_predator_20260726_184323_cab349ba80106a37` | 53 | 21 | iteration |
| 6 | `w19_predator_20260726_191150_a00d393ad114f2cf` | 61 | 21 | iteration |
| 7 | `w19_predator_20260726_193134_b02ffbeff221983d` | 51 | 27 | iteration |
| 8 | `w19_predator_20260726_195023_56e65a951b357b1c` | 63 | 22 | iteration |
| 9 | `w19_predator_20260726_202836_d4cdd651f7ce0001` | 55 | 21 | **holdout** |
| 10 | `w19_predator_20260726_213435_835dcfbea79f441c` | 9 | 20 | **holdout** |
| 11 | `w19_predator_20260726_221453_e76f1773eabde4a9` | 55 | 21 | **holdout** |

**Invoker — 6 builds**, all used as the internal control (no holdout).

Note build 10 carries 9 HP at wave 19 and may floor near 0% in both arms. It stays in:
dropping a build after seeing its rate is exactly the selection this protocol exists to
prevent.

## Allocation

- **Predator: 5 passes per arm** over the 11 builds, round-robin = **55 trials/arm**
  (40 on the 8 iteration builds, 15 on the 3 holdout builds).
- **Invoker: 3 passes per arm** over the 6 builds = **18 trials/arm**.
- **Total 146 trials**, ~45-75 s each, so roughly 2-2.5 h.
- **Arms alternate pass by pass** (v2 pass, v1 pass, v2 pass, ...) so that machine state
  and any time-of-night drift are balanced across arms rather than confounded with them.

## Endpoints

**Primary:** victory rate on the **8 iteration predator builds**, v2 vs v1, 40 trials
per arm. Reported as **per-build raw series**, never a pooled number alone.

**Secondary, all predeclared:**
1. The 3 held-out predator builds: v2 must **not regress** against v1.
2. **Internal control — the invoker arm.** The mechanism story predicts v2 helps
   **predator** (0% stationary projectiles) and does **little for invoker** (96.3%
   stationary). **If v2 improves invoker by a comparable margin, the mechanism story is
   wrong and the predator result must be distrusted — even if it looks good.** This
   rule binds regardless of significance.
3. **Freeze detectors** from `wp2_finale_metrics.py` reported alongside outcomes:
   `boss_hp_ratio_last`, `stationary_frac`, `straightness`. A controller that "wins" by
   surviving in a safe pocket without killing the boss must be visible as such.
4. Damage taken and boss time-to-kill, descriptive only.

## Power, declared in advance

At 40 trials/arm the CI half-width is ~14 pp. **A 0.70 -> 0.90 shift is detectable; a
5 pp shift is not.** No small effect will be claimed from this experiment, in either
direction. A null here means "not shown to be better at this sample size", not "no
difference".

## Validity and stopping

- Only trials with `valid == True` count: wave set exactly `[20]`, single boss path,
  boss entity as expected, policy/mod version match, and arm match.
- Invalid trials are reported with their reason codes and **not** silently replaced.
- **Run to completion. No interim look drives any decision.** If the campaign aborts
  early, the analysis reports what was collected and the shortfall, and does not
  substitute the partial result for the planned one.
- A pass that fails does not end the campaign; the next pass relaunches the game fresh
  and the failure is recorded.

## What would refute the change

v2 fails if any of: it does not beat v1 on the 8 iteration builds; it regresses on the
held-out builds; the invoker control moves as much as the predator arm; or it wins while
the freeze detectors show it is not killing the boss.
