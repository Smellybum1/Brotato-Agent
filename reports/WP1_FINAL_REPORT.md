# Work Package 1 final evidence report

Report date: 2026-07-22 (Australia/Brisbane)  
Certified evaluation policy: v72  
Promoted teacher candidate: v92 (`0.1.92-gun-wp1`)  
Current verdict: **PASS**

## 1. Executive verdict

The gameplay and telemetry gate is passed: the authoritative v72 campaign has
exactly 20 valid fixed-config runs, 18 victories and 2 defeats, complete terminal
evidence, and zero errors, hangs, illegal actions, or post-start APPCRASH evidence.
The subsequent v92 boss-range repair won its operator-designated decision run and
is the teacher candidate for WP2.

The two final director requirements are closed. Manual override and emergency
stop were independently exercised through physical input during live v92 run
`run_1784677381_46728`, with telemetry events at sequences 728 and 729 and a
clean shutdown afterward. The operator then explicitly authorized the prepared
baseline staging, initial local commit, and local `wp1-baseline` tag. The tag is
the authoritative WP1 repository baseline. Nothing was pushed.

## 2. Scope and fixed benchmark configuration

The certified campaign used Well-Rounded (`character_well_rounded`), SMG,
Danger 0, enemy damage/health/speed multipliers at 1.0, Endless off, wave retry
off, solo play, no retries, and no manual rescue. These values were re-read from
every `run_start`/summary in the v72 set; no run deviated.

The authoritative artifacts are:

- `reports/gate_state_v72.json`
- `reports/batch_overnight_20_v72.csv`
- `reports/batch_overnight_20_v72.md`
- `runs/<run_id>/events.jsonl` and `runs/<run_id>/summary.json`

## 3. Teacher candidate and Step-1 decision

v92 raised only `BOSS_FINALE_CONTACT_ESCAPE_DISTANCE` from 320 to 420 after
v91 showed lethal boss-charge samples at roughly 350-406 range. Its first
eligible decision run, `run_1784670237_52694`, won. The operator explicitly
directed that a failure be repaired/redeployed and a success advance the
roadmap, so v92 is promoted without completing the originally planned 3/4 gate.

The win recorded estimated DPS of 2,510.59 at wave 15 and 3,784.59 at wave 18;
no below-band wave-13-16 shop exit with more than 400 unspent; 28,745 sampled
boss damage from 29,250 maximum HP over 33.0 seconds; 506.8 median boss distance;
minimum player HP 27; 9/9 combines; and zero error, hang, illegal-action,
cycle-guard, or APPCRASH evidence. Isolated telemetry validation passed 1/1.
RSI was 112.2 and remains diagnostic only.

This is an acceptance/promotion result, not a new win-rate certification. v72
remains the statistically certified teacher. Excluded partial runs are
`run_1784671380_41100`, `run_1784671580_93166`, and
`run_1784671796_43736`. The first partial overwrote the live terminal snapshot,
so runtime HUD-vs-`build_metrics` parity for the win is unavailable rather than
inferred; HUD source assertions pass.

## 4. Complete certified 20-run table

| # | run_id | result | last wave | duration ms | recoveries |
|---:|---|---|---:|---:|---:|
| 1 | `run_1784573193_53233` | defeat | 9 | 396023 | 3 |
| 2 | `run_1784573591_74360` | victory | 20 | 1156310 | 14 |
| 3 | `run_1784574748_23466` | victory | 20 | 1150568 | 14 |
| 4 | `run_1784575900_67865` | victory | 20 | 1204481 | 14 |
| 5 | `run_1784577106_32149` | victory | 20 | 1141251 | 14 |
| 6 | `run_1784578248_64761` | victory | 20 | 1177442 | 14 |
| 7 | `run_1784579427_97655` | victory | 20 | 1172075 | 14 |
| 8 | `run_1784580600_85567` | victory | 20 | 1158551 | 14 |
| 9 | `run_1784581760_10742` | victory | 20 | 1131833 | 14 |
| 10 | `run_1784582893_33112` | victory | 20 | 1172153 | 14 |
| 11 | `run_1784584067_93061` | victory | 20 | 1148215 | 14 |
| 12 | `run_1784585216_1710` | victory | 20 | 1201736 | 14 |
| 13 | `run_1784586419_74481` | victory | 20 | 1160482 | 14 |
| 14 | `run_1784587581_2974` | victory | 20 | 1151530 | 14 |
| 15 | `run_1784588734_4891` | victory | 20 | 1143368 | 14 |
| 16 | `run_1784589879_83585` | victory | 20 | 1124707 | 14 |
| 17 | `run_1784591005_31080` | victory | 20 | 1186265 | 14 |
| 18 | `run_1784592192_98412` | victory | 20 | 1137378 | 14 |
| 19 | `run_1784593331_58683` | defeat | 16 | 890818 | 10 |
| 20 | `run_1784594223_91323` | victory | 20 | 1162338 | 14 |

Totals: 20 runs, 18 victories, 2 defeats, win rate 0.900 (reported Wilson
95% CI 0.699-0.972). No outlier or interrupted run was removed from this set.

## 5. Terminal completeness and chaining

Each of the 20 run directories contains exactly one `run_start`, exactly one
`run_end`, and a summary. All ordered transitions are present. Victory-to-next
chaining is demonstrated repeatedly (for example
`run_1784573591_74360` -> `run_1784574748_23466`, one-second gap).
Defeat-to-next chaining is demonstrated naturally twice:

- `run_1784573193_53233` -> `run_1784573591_74360`, two-second gap;
- `run_1784593331_58683` -> `run_1784594223_91323`, one-second gap.

The director required a separate synthetic controlled defeat only for a 20/20
batch. Because this campaign contains two natural defeats and both chain cleanly,
the death-screen path is directly exercised without manufacturing another run.

## 6. Telemetry and report integrity

An isolated copy at `.tmp/v72-certification-20260722-081318` was validated with
`scripts/validate_telemetry.py`: 20 passed, 0 failed. Schema version, sequence
ordering, required fields, run identifiers, settings, and terminal completeness
all passed. Every summary reports zero errors, hangs, and illegal actions.

The CSV contains exactly the same 20 run IDs and its result, last-wave, and
duration values agree with raw summaries. The Markdown report contains and
agrees with all 20 rows. No retry was counted as a win.

## 7. Operational safeguards

Status: **PASS**.

The source paths are present: any movement key calls `on_manual_override()` and
Ctrl+Shift+Q triggers `_check_emergency_stop()`, with telemetry kinds
`manual_override` and `emergency_stop`. A supervised live exercise was attempted
after the v92 win. In its first form Brotato reached live wave 3, but Windows
capture continued to show a stale main-menu frame and injected movement/
emergency keys produced no telemetry event. A second, windowed attempt produced
a current Brotato main-menu capture and the same helper successfully confirmed
Steam's custom-argument dialog, but Godot still rejected its clicks and Enter;
gameplay could not be resumed. The direct-launch detour temporarily reset the
ModLoader profile to empty. The same v92 deployment/profile was immediately
restored with auto-start disabled, both archive hashes remained identical, and
no run started. The temporary v920 tasks and all scoped processes were stopped,
Brotato was stopped, and the partial runs were excluded.

The final supervised exercise used a verified live physical input surface on
v92 run `run_1784677381_46728`. During live wave 8, a physical movement-key
press transferred movement control to the operator, disabled agent movement,
changed the HUD to `enabled: False`, and emitted `manual_override` at telemetry
sequence 728 (332724 ms). The operator then pressed Ctrl+Shift+Q; because
auto-start remained armed independently of agent activity, the emergency path
emitted `emergency_stop` at sequence 729 (407223 ms), and ModLoader logged
`Emergency stop engaged` at 09:49:42.

Brotato was closed through the scoped deployment helper, the identical v92
archive was restored with auto-start false, and no v92/v920 process tree or
Brotato process remained. The exercise is intentionally excluded from every
evaluation claim because the two error events are expected safety-test signals
and it has no natural terminal. Exact event, hash, and scope evidence is in
`reports/WP1_SAFEGUARD_EXERCISE.md`.

## 8. Reproducibility commands and clean bootstrap

Documented daily commands are:

```powershell
python scripts\bootstrap.py
.\.venv\Scripts\python.exe scripts\deploy_mod.py --target agent
.\.venv\Scripts\python.exe scripts\launch_benchmark.py
.\.venv\Scripts\python.exe -m pytest -q --basetemp=.tmp\pytest-local
.\.venv\Scripts\python.exe scripts\run_batch.py --runs 20 --launch
```

The clean-copy audit initially found a real defect: editable installation failed
because setuptools auto-discovered several non-package top-level directories.
`pyproject.toml` now declares the setuptools build backend and `packages = []`,
which is correct for this scripts/mod repository. A fresh copied checkout at
`.tmp/wp1-clean-bootstrap-20260722-081746` then ran the actual
`scripts/bootstrap.py` successfully, rediscovered Brotato, and passed 67/67 tests
with a workspace-local basetemp. Plain pytest encountered an unrelated denied
global `%TEMP%/pytest-of-moxhe`; the explicit local basetemp is the documented
Windows-safe invocation.

## 9. User-data, Steam, and save integrity

Fresh backup: `backups/userdata_20260722_081559`.

- 776 copied files, 355,794,972 bytes.
- Steam userdata copied from `C:\Games\Steam\userdata\70623147\1942280`.
- Both profile trees' `save_v3_0.json`, `run_v3_0.json`, and `settings.json`
  parse successfully, as does `BACKUP_MANIFEST.json`.
- Three legacy files (`save.json`, `save_latest.json`, `save_stable.json`) are
  not valid single JSON documents; they pre-existed the backup and were
  preserved verbatim. They are not the active v3 save files.
- Current Brotato executable SHA-256:
  `F69A1217FD15DAF46300CC6224DD34F7ECD4F56288FC71E95ED6344EFF753AE4`.
- Current `Brotato.pck` SHA-256:
  `BE303F0A320CB099001FDC39C3B807CDD657E93426DC09867CEE1D36F5385ACF`.
- Steam build ID remains 23429717 and depot manifest remains
  5289220193624029472.

The hashes match `docs/ENVIRONMENT.md`; no Steam binary or active save was
modified by the closeout audit.

## 10. Third-party pins and licensing

Both local dependency Git trees are clean and match
`docs/THIRD_PARTY_PINS.txt`. `.gitmodules` records their paths and origins so
the initial repository commit can preserve them as reproducible pinned
submodules rather than accidental embedded repositories:

- `brotato-full-autobot`: commit
  `b5190436b85a99000327f2908e25e07b60509bd3`, GPL-3.0;
- `brotatoai`: commit
  `34172206de5e3ee590e140d0c02d7d62ebeefa1f`, MIT.

Origin URLs, licenses, authorship references, derivative-use statement, Brotato
non-redistribution statement, and wiki/guide attribution are recorded in
`docs/THIRD_PARTY_NOTICES.md`. License files exist in both third-party trees;
the project root is GPL-3.0.

## 11. Tests, deployment, and stopped-state integrity

v92 pre-deployment verification passed 38/38 focused tests and 67/67 full tests.
ModLoader smoke reached `Init`, `Ready`, and `AgentController ready` with no
parse/script error. The clean-copy regression repeated 67/67 after the bootstrap
repair.

The Workshop and game-local installed archives are both 320,704 bytes and have
SHA-256
`A0911C7F56BA8233C48E3B5D60AB4F4AFF4BD00FA2E5FAD070CAC5AA2DFAA639`;
the v92 deployment audit found exact 18-file source parity. All exact v92 and
temporary v920 scheduled tasks are disabled, their scoped command/Python trees
are stopped, and Brotato is stopped. No evaluation is currently running.

## 12. Repository closeout and WP2 handoff

Status: **CLOSED**.

The operator explicitly authorized the prepared initial local commit and
`wp1-baseline` tag after the safeguard exercise. The tag identifies the exact
passing repository state; its commit identifier is reported by `git rev-parse
wp1-baseline^{commit}`. No remote push was authorized or performed.

The commit preflight covered `.tmp/`, backups,
raw runs, binaries, logs, local environments, and `.env` files are ignored;
the remaining ordinary-file candidate set is 252 paths and approximately
2.3 MB. A filename/content signature scan found no private-key, GitHub-token,
OpenAI-key, API-key, client-secret, or password-shaped candidate. The two
third-party repositories must be staged as mode-160000 submodule gitlinks and
verified against the commits in section 10; they must not be flattened or
accidentally committed as unregistered embedded repositories.

The unchanged WP2 packet is
`docs/pro/Grok_4.5_Brotato_Work_Package_2_Prompt.md`, current SHA-256
`EFADF505ED05BF760E55FEE7CA0379842F93A783D53C565EB29164C9CF971399`,
matching the director record. The second director-listed copy at
`C:\Tools\Downloads\Grok_4.5_Brotato_Work_Package_2_Prompt.md` exists and has
the same hash. Sections 7 and 12 are now closed and this report is PASS. WP2 may
begin using v92 as the promoted teacher candidate and v72 as the certified D0
reference.
