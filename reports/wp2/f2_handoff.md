# Stage F2 handoff — HISTORICAL (superseded 2026-07-26)

> **THIS DOCUMENT IS NO LONGER THE ENTRY POINT.** Stage F2 completed
> 2026-07-26 at 40/40 runs with a NULL verdict. Read
> **`reports/wp2/f2/f2_verdict.md`** instead.
>
> Two things below are now WRONG and must not be acted on:
> - the "Progress (11 of 40 launched)" table and "NEXT RUN IS 12" — the
>   campaign is finished; do not resume it;
> - the v127 deploy pointer at worktree `elastic-mcnulty-7aa022` — that copy
>   is stale/redundant. The authoritative branch is `claude/keen-wu-fa36b5`
>   (commit `cfade0f`), which bundles materials + dropped_counts + loot-dash.
>
> One claim below is also wrong: the loot-dash telemetry was NOT an
> unobservable gap. `finale_translation.loot_dash_active` is emitted and
> uptime was measured at 10.5% overall (not shut off in late waves).
>
> Still accurate and reusable: the exact per-run T/P procedure, the r11
> sidecar-integrity gotcha, and the authority/delegation notes.

READ FIRST, then `.tmp/wp2_stage_f2_design.md` (BINDING), then memory
`brotato-agent-project-state` + `brotato-v127-materials-telemetry`.

## Authority

Operator granted STANDING DECISION AUTHORITY 2026-07-25: "for decisions
like those you posed to me I give you approval to make the decisions
yourself, and also for the project going forward." Fork/design/experiment
calls are the primary agent's. Predeclared bars remain binding as written;
report honestly. Operator also relays questions to Pro (external GPT) on
request — write self-contained briefs (no file refs, full context inline;
pattern: `.tmp/pro_consultation_briefs_20260725.md`), operator pastes back
a share link (fetch with the in-app browser; WebFetch returns only the JS
shell), then selective adoption with reasons.

Delegation: `subagent_type: "opus-delegate"` (Opus 5, effort LOW,
guardrails in `.claude/agents/opus-delegate.md`). Escalate effort
deliberately for hard slices and say so. LESSON LEARNED THIS SESSION:
contested, load-bearing MEASUREMENTS must be computed and eyeballed by
the primary agent — two delegated attempts mismeasured the same quantity
and produced a confidently wrong conclusion.

## THE ACTIVE JOB: finish Stage F2 (40 runs)

Binding design `.tmp/wp2_stage_f2_design.md`. Question: does frozen
DETERMINISTIC pi4 (sigma=0) beat the PURE TEACHER? Schedule is
predeclared and committed: `reports/wp2/f2_schedule.json` (seed
20260725, 10 randomized blocks of 4, 20 runs per arm).

### Progress (11 of 40 launched)

| # | arm | outcome |
|---|---|---|
| 1 | T | defeat w20, dmg 168 |
| 2 | P | defeat w20, dmg 164 |
| 3 | T | VICTORY w20, dmg 24 |
| 4 | P | defeat w17, dmg 78 |
| 5 | P | defeat w20, dmg 64 |
| 6 | T | defeat w13, dmg 51 |
| 7 | T | defeat w17, dmg 61 |
| 8 | P | VICTORY w20, dmg 112 |
| 9 | T | VICTORY w20, dmg 73 |
| 10 | P | VICTORY w20, dmg 124 |
| 11 | P | VICTORY w20, dmg 19 (cleanest run of the campaign) |

Standing after 11: T 2/5 victories, P 3/6. Dead even in rate — expected
at this n (Pro's power table: ~8% power at 10/arm). DO NOT read anything
into it. NEXT RUN IS 12 (T arm).

Remaining arms per schedule: 12 T, 13 T, 14 P, 15 T, 16 P, then blocks
5-10 (`PTPT`, `TPTP`, `PTTP`, `PTTP`, `TPPT`, `TPTP` = runs 17-40).

Per-run artifacts: `reports/wp2/f2/r<NN>_<ARM>.json`, state files
`.tmp/f2_r<NN>_<ARM>_state.json`, sidecar logs
`.tmp/f2_r<NN>_P_sidecar.jsonl`, covariates appended to
`reports/wp2/f2/covariates.jsonl` (STS2 worker count per launch),
aborted runs in `reports/wp2/f2/aborted_runs.jsonl`.

### EXACT per-run procedure

T arm (pure teacher — NO sidecar):
```
APPDATA='C:\Users\moxhe\AppData\Roaming' .venv/Scripts/python.exe \
  scripts/wp2_collect_teacher.py --runs 1 \
  --state-file .tmp/f2_r<NN>_T_state.json \
  --report-file reports/wp2/f2/r<NN>_T.json --launch
```
Config must be idle: `student_enabled=false`. Verify before launching.

P arm (deterministic pi4):
```
APPDATA='...' .venv/Scripts/python.exe scripts/wp2_set_student_pin.py \
  --enable --sha 16414822D39D1344DA24AC9BF3A9522A8DFB2CE1ED536E13DA628B4F5AA497A4
.venv/Scripts/python.exe scripts/run_student_sidecar.py --mode residual-actor \
  --actor-checkpoint .tmp/residual_pi4.pt \
  --actor-parent-registry models/registry/bc_v2_f_s1.json \
  --explore-sigma 0.0 --actor-seed 0 --idle-exit-sec 3600 \
  --log-path .tmp/f2_r<NN>_P_sidecar.jsonl
# WAIT for '"listening"' in that log BEFORE launching the collector
<then the same collector command with _P names>
```
After every P run: kill the sidecar by the PID in its startup line, then
`wp2_set_student_pin.py --disable --sha 1AD517B04843B69966841C7B795B927AE86B2727789456224321FC091F29F331`.

**HARD-WON GOTCHA:** launching a P-arm collector WITHOUT the sidecar
silently produces a pure-teacher run labelled P. This happened at run 11;
it was killed at wave 1, artifacts deleted, and logged in
`aborted_runs.jsonl`. ALWAYS confirm the sidecar is listening first, and
after ~wave 3 verify serving: `grep -c handshake_ok <sidecar log>` == 1
and |delta| p50 ~0.04-0.06 deg, p99 ~0.23-0.36 (pi4's deterministic
signature; sigma=0.3 would show ~1 deg medians).

Monitor pattern that works (poll 120-150 s; treat `starting` and
`state-read-error` as NON-terminal or the monitor exits early):
see any of the recent Monitor calls in the transcript.

### Analysis when all 40 are in

`scripts/wp2_f2_endpoint.py` (committed 9a39840, 26 tests) computes the
predeclared PRIMARY: hierarchical run outcome (victory > combat progress
> HP-AUC) as P(random P run outranks random T run), run-level bootstrap
CIs. Victory rate is the key SECONDARY. Interim look at 10/arm is
SAFETY/FUTILITY ONLY — no efficacy peeking, no extension past 20/arm.
Known soft spot: the wave-20 defeat denominator uses a boss-kill-
terminated median.

Verdict rules (predeclared): CI excludes 0.5 upward -> next residual work
is a TEMPORALLY-EXTENDED design (commitment-duration actor, theta stays
5 deg). Null/negative -> close combat-residual work, redirect to the shop
layer. Do NOT raise theta either way.

## DEPLOY OBLIGATIONS — all blocked until F2's 40 runs finish

Merge into ONE version bump + ONE smoke + zero-violation audit:
1. **v126 surplus-reroll** — committed `663d641`, policy 0.1.126, NOT
   deployed. Design `.tmp/wp2_v126_design_note.md` (v2, Pro-reviewed).
   Watch item at smoke: BANK_CAP calibrated to 0 at every wave (income
   dominates costs), so surplus rerolls fire on most exhausted boards —
   check for reroll churn on poor boards.
2. **v127 materials telemetry + derived dropped_counts** — implemented
   UNCOMMITTED in worktree `.claude/worktrees/elastic-mcnulty-7aa022`
   (branch `claude/elastic-mcnulty-7aa022`), policy 0.1.127 / mod
   0.2.36. Adds `player.materials`, `player.bonus_materials`,
   `entities.materials[].value`.
3. **Loot-dash telemetry** — task started in a separate session; status
   unknown at handoff. Should fold into the same bump.

**CRITICAL SEQUENCING:** v127 moves the capture schema hash to
`2823CB7E...BC1174`. `encoder_v1.py` and the sidecar handshake gate on
EXACT hash equality, so **bc_v2_f and the residual actors CANNOT run on a
v127 build** until a compatibility-list change lands. Teacher collection
is unaffected. Therefore: finish F2 -> deploy -> teacher-side work is
fine, but any further student/residual campaign needs the compatibility
fix first.

## Materials thread — CLOSED this session (operator was right)

Operator observed the agent leaving currency on the ground from ~wave 10.
Chain of findings (all committed):

- Leftover at the TRUE wave-timer end (last tick with
  `remaining_sec > 0`): median 28 non-terminal; by band 5 / 31 / 44 / 49
  (w1-5 / 6-10 / 11-15 / 16-19); terminal wave median 30.
  `reports/wp2/materials_leftover_corrected.md`.
- **Crediting mechanic = Model B, confirmed from decompiled game source**
  (not inference): `clean_up_room()` -> `RunData.add_bonus_gold` (pool
  separate from spendable gold), drained by `spawn_gold()` boosting later
  drops. Uncollected material is DEFERRED income; genuine loss is the
  terminal strand.
- `MAX_GOLDS = 50` is the ENGINE's ceiling; past 50 a new drop spawns
  nothing and an existing entity ABSORBS its value -> materials are NOT
  unit-valued and **entity counts are censored proxies for worth**. All
  leftover figures above are LOWER BOUNDS on value.
- Mechanism of the late-wave degradation: NOT the density veto (measured
  0% of loot-present ticks w1-15) and NOT edge-kite (needs w>=16).
  Cumulative: more drops, mean distance +28% (535->684u) against a
  1/dist falloff, ~12% of piles vetoed by the corridor rule.
  `reports/wp2/late_wave_collection_mechanism.md`.
- Recommendation standing: do NOT loosen collection aggression or safety
  gates (v119 precedent). Instead measure the LOOT DASH — its telemetry
  field exists in `potential_field.gd` but is never emitted, so uptime
  and clearance yield are unobservable. Tune the bounded, already
  safety-gated dash after v127+dash telemetry ships.

Three of my own claims were retracted in this chain (no headroom;
in-wave pickup; telemetry censoring). The retractions are inline in the
reports so the wrong numbers cannot be re-cited.

## Session commits (wp2-combat-learning)

`67d1d29` pi3 + actor-l2 knob -> `770e5d8` checkpoint tool + pin utility
-> `24a0027` pi3 live evidence -> `f92b514` pi4 -> `e9b358a` §6 NULL
verdict -> `1fb2432` docs -> `f1bc027` F2 schedule -> `9a39840` F2
endpoint calculator -> `663d641` v126 -> `83be808` materials analysis ->
`80b3ea3` retraction -> `32ad80b` corrected leftover -> `c26d03a`
mechanism + sweep model rejected -> `83787d7` no-capture-cap correction
-> `9059609` Model B source-confirmed.

Tests: 496 green as of `663d641` (plus the F2 endpoint's 26).

## Machine state at handoff

Verify before anything: `tasklist | grep -i brotato` (should be empty
between runs), no orphan sidecars, and
`agent_config.json` -> `student_enabled=false`, pin
`1AD517B0...F331` (bc_v2_f) when idle. Production student remains
bc_v2_f_s1. Other projects (STS2 ~10-12 workers, Mindustry, Backpack
Battles) share this machine — record the worker count per F2 launch as a
covariate; the count is already logged in `covariates.jsonl`.
