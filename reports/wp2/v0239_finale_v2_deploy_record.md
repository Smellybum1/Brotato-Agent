# v0.2.39 deploy record — finale controller v2 (flag-gated, default OFF)

**Date:** 2026-07-26 (deploy 23:55) / 2026-07-27 (smoke trials, just after midnight)
**Policy:** `teacher_v1-0.1.128-gun-wp1` (**unchanged**)
**Mod:** `0.2.38-wp2-capture` -> `0.2.39-wp2-capture`
**ZIP SHA-256:** `1B03259E5614B5EEA09C3F943B5C1D0919690AFA0CD823DF31C2C8A3759D9E12`
**Gate reached:** Gate 1 (executability / determinism) only — see Scope limit

## Scope limit — read this first

This is **Gate 1 (executability/determinism) only**, per `docs/RELEASE_GATE.md`. It is
**not** an outcome result. The trial counts are **n=1 per arm**; the victory/defeat
split between the two arms carries **no information about whether v2 is better** and
must not be cited as if it did.

The outcome gate is the predeclared evaluation in `reports/wp2/finale_v2_design.md`:
the 11-build predator library with **3 builds held out**, per-build raw series against
the 0.700 baseline, plus the **6 invoker builds as an internal control** — if v2
improves invoker equally, the mechanism story is wrong and the result must be
distrusted. That evaluation is powered for roughly **0.70 -> 0.90 only**.

## What shipped

The **finale controller v2** (commit `1bb2bf9`, design `reports/wp2/finale_v2_design.md`):
heading selection at 60 Hz on wave 20 only, behind the `finale_v2` flag in
`agent_config.json`, **default FALSE**.

**Policy version was deliberately not bumped.** Flag-off behaviour is byte-identical,
so the existing wave-20 fixture baseline of **28/40 = 0.700 [0.546, 0.819]** stays a
same-version comparison rather than becoming a cross-version one.

One further change was made during this deploy: **the finale ARM is now recorded in
telemetry.** `finale_v2` is written into the run summary (`summary.json`) and into the
mod-ready sentinel (`mod_ready.json`).

- Rationale: `policy_version` cannot carry the arm, because the flag lives in
  `agent_config.json`, and `scripts/deploy_mod.py::write_agent_config` rewrites that
  file from a fixed dict — so a v2 arm could silently revert to v1 and still be
  recorded as v2.
- `telemetry_writer.begin_run` builds the summary from an explicit key allowlist, so
  the key had to be added there too or it would have been silently dropped.

Loop side: `scripts/wp2_finale_loop.py` gained `--finale-v2`, which arms the flag,
records the arm on every trial row, restores it to false in the `finally` block, and —
via `validate_trial` — **INVALIDATES** any trial whose recorded arm disagrees with the
arm requested (reason code `finale_arm_mismatch:<value>`).

Suite: **600 passed, 2 skipped** (596 at the version bump, plus 4 new arm-guard tests
covering `finale_arm_mismatch` in both directions and the missing-key case).

## Pre-launch static idiom sweep

Performed **before** launching, as the risk control. Every idiom in the added GDScript
was checked for an exact precedent in the already-parsing build.

| check | result |
|---|---|
| idiom classes with precedent | **18 of 18** |
| referenced symbols resolving | **12 of 12** |
| called safety functions matching on arity and argument order | **4 of 4** |
| non-ASCII / BOM / mixed indentation | none |
| `"literal" in <Autoload>` (the idiom that caused a fatal parse error on the v127 deploy) | absent |

Recorded for honesty: two idioms — a typed `bool` class var, and `continue` at loop
depth >= 2 — had precedent only in **other** mod scripts rather than in
`potential_field.gd` itself. Godot 3 parses per file and both are core language.

## Smoke — two paired fixture trials, same fixture, same build

Fixture `w19_predator_20260726_161821_fc24b6eb79072a4d.json` (predator, hp 47,
level 21, source `run_1785045585_48491`). Both trials validated by the loop: waves
exactly `[20]`, single boss path, boss = predator, `valid=True`.

| arm | run_id | `run_start.finale_v2` | result | damage | captures | wall |
|---|---|---|---|---|---|---|
| flag ON (v2) | run_1785074372_39190 | True | victory | 64 | 1204 | 72.6 s |
| flag OFF (v1) | run_1785074590_34831 | False | defeat | 48 | 717 | 46.4 s |

## Independent confirmation that v2 actually executed

The summary field is the mod's **self-report**, so execution was cross-checked
behaviourally. v2 selects among 32 candidate headings, i.e. multiples of
**11.25 degrees**. The pre-existing v1 samplers use `ESCAPE_DIRECTIONS = 24` (15 deg)
and `FLEE_DIRECTIONS = 36` (10 deg); both of those grids intersect the 11.25 deg grid
only at multiples of 45 deg. So headings on the 11.25 deg grid **excluding** multiples
of 45 deg are producible only by v2.

Classification of commanded `teacher.action` headings (tolerance 0.005 deg):

| arm | n actions | 11.25 deg exclusive | 45 deg (ambiguous) | 15 deg (safety tail) | off grid |
|---|---|---|---|---|---|
| v2 | 1204 | **197 (0.1636)** | 351 (0.2915) | 558 (0.4635) | 98 (0.0814) |
| v1 | 717 | **0 (0.0000)** | 142 (0.1980) | 422 (0.5886) | 153 (0.2134) |

**Correction that produced this number.** A first pass counted 45.5% "on grid" using a
naive 11.25 deg modulo test. That was **wrong**: action components are rounded to 6
decimal places in the JSON, which flattened the epsilon sweep, and the exact hits were
only 45 deg multiples — which v1 produces too. The number became evidence only once the
grids that v1 can also produce were excluded.

## The 60 Hz trap is confirmed guarded

v2 recomputes movement every physics tick, while captures must stay on the 20 Hz
schedule (the dataset and student path are fixed at 20 Hz). Measured `control_dt_ms`,
excluding sub-10 ms start-up captures:

| arm | median | p99 |
|---|---|---|
| v2 | 51.0 ms | 54.0 ms |
| v1 | 51.0 ms | 54.0 ms |

Identical, against the absolute 50 ms standard. Had the guard failed, the v2 arm would
read ~16 ms.

## Audits — 0 violations on both arms

| audit | result (both runs) |
|---|---|
| `wp2_capture_audit.py` | schema_mismatches 0, invalid_captures 0, invalid_actions 0 |
| `wp2_teacher_safety_audit.py` | `violation_count: 0`, `accepted: true` |
| `wp2_v126_shop_audit.py` | `violation_count: 0`, surplus_rerolls 0, stale_board_timeouts 0 |

`wp2_audit.py` was also run. It is the WP1-era combat_tick audit against the v72
corpus and reports structural capacity/semantic blockers, not violations — it is **not
a gate** for this change.

## Machine state at close

Game closed; `auto_start=false`, `resume_from_save=false`, and `finale_v2=false` in the
deployed `agent_config.json` (verified by reading the file).
