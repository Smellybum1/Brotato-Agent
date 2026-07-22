# WP2 WP1 handoff audit

Audit date: 2026-07-22 (Australia/Brisbane)
Result: **PASS**
WP1 tag: `wp1-baseline`
WP1 commit: `9a390f47c5c5268d36d27cca5e47ff04ab9317e8`
WP2 branch: `wp2-combat-learning`

## Required predecessor checks

| # | Requirement | Result | Evidence |
|---:|---|---|---|
| 1 | Exactly 20 valid unattended, no-retry, non-Endless Well-Rounded/SMG/D0 runs | PASS | The v72 certified table and raw `run_start` records contain exactly 20 eligible runs with one fixed configuration. |
| 2 | At least 18 victories | PASS | v72 result is 18 victories and 2 defeats (90%). |
| 3 | Zero automation hangs/indefinite loops | PASS | All 20 summaries report zero hangs and every run has a terminal; the two natural defeat paths chain onward. |
| 4 | Zero illegal meta-game actions | PASS | All 20 summaries report zero illegal actions; lock/combine safety evidence is clean. |
| 5 | Valid terminal and compact summary for every run | PASS | Exactly one `run_start`, one `run_end`, and one summary exist for each of 20 runs. |
| 6 | Raw telemetry passes validation | PASS | Isolated v72 corpus validation on 2026-07-22: 20 passed, 0 failed. |
| 7 | Successive-run chaining handles victory and defeat | PASS | Repeated victory chaining plus defeat chains `run_1784573193_53233` → `run_1784573591_74360` and `run_1784593331_58683` → `run_1784594223_91323`. |
| 8 | Manual override and emergency stop actually tested | PASS | Excluded v92 exercise run `run_1784677381_46728`: `manual_override` seq 728, `emergency_stop` seq 729, physical movement transfer, clean shutdown. |
| 9 | Backup integrity and installed data intact | PASS | `backups/userdata_20260722_081559`: 776 files, 355,794,972 bytes; active v3 JSON files readable; Steam executable/package hashes unchanged. |
| 10 | Bootstrap/deploy/launch/test/report commands documented | PASS | `README.md`, `docs/ENVIRONMENT.md`, and the WP1 final report contain the non-interactive commands. |
| 11 | Tests pass from clean bootstrap | PASS | Fresh copied checkout ran `scripts/bootstrap.py`; final source suite passed 67/67 with local pytest basetemp. |
| 12 | Clean repository, local tag, commit hash recorded | PASS | `wp1-baseline^{commit}` is `9a390f47c5c5268d36d27cca5e47ff04ab9317e8`; the WP2 branch was created directly from it; no push occurred. |

## Frozen teacher and evaluation baseline

- Statistically certified reference: v72, 20 runs, 18W/2L.
- Promoted WP2 teacher candidate: v92 (`0.1.92-gun-wp1`,
  `teacher_v1-0.1.92-gun-wp1`), decision run
  `run_1784670237_52694`.
- Fixed benchmark: Well-Rounded, SMG, Danger 0, default settings, normal speed,
  Endless off, wave retry off.
- Installed v92 archive SHA-256:
  `A0911C7F56BA8233C48E3B5D60AB4F4AFF4BD00FA2E5FAD070CAC5AA2DFAA639`.
- The complete frozen artifact list and hashes are in
  `data/manifests/wp1_frozen_interface_v1.json`.
- Large/raw telemetry remains outside git. The v72 certification corpus used by
  this audit is the isolated read-only working copy at
  `.tmp/v72-certification-20260722-081318`; its 20 runs validated 20/20.

## Scope and exclusions

The safeguard run and all partial v92/v920 runs remain excluded from evaluation.
WP2 may extend telemetry using a new compatible schema version, but may not
rewrite the historical WP1 schema or teacher evidence. The deterministic v92
controller remains the fallback and continues to own every non-combat action.
