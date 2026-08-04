# Handover — Brotato Agent

You are taking over an ongoing research project. This is not a greenfield build. A large amount of
work has already been done, most of it consisting of **ruling things out**, and the single most
expensive mistake you can make is re-running an experiment that has already returned a null.

Read this file, then read `AGENTS.md` and `docs/ROADMAP.md`.

---

## 1. The objective

- **North Star 1: win a single run at nominal Danger 5.** Not achieved. This is the whole job.
- **North Star 2: win a D5 run with every character.** Later. It has a bootstrap problem —
  characters must be won to be unlocked.

"Nominal" matters: there are 4 D5 victories in the archive, but they were produced with a save-edit
dial that reduced enemy health. **They are not NS1 victories.**

## 2. Where things stand

The agent is a scripted policy (GDScript mod) that plays Brotato autonomously and emits telemetry.
At **Danger 0** it wins roughly 40% of runs with the `well_rounded` character. At **Danger 5** it has
never won, and dies at **median wave 11** out of 20.

**The binding constraint is known.** §28 ran an interventional dose ladder (40 trials, 0 censored):
scaling enemy **health** down moves terminal wave significantly (+3.5 at 0.75x, +7.4 at 0.50x);
scaling enemy **damage** down does essentially nothing. Therefore:

> **The agent does not die at D5 because it is too fragile. It dies because it kills too slowly.**

⛔ **This de-licenses defensive levers.** Do not propose "reduce incoming damage" work; halving
incoming damage was measured and did not produce a single victory.

There is also a structural reason wave 11 specifically kills it: Brotato's waves have a period-3
"relief" rhythm, but waves 11 and 17 *overshoot*, trading body count for HP-per-body. At D5 wave 11
presents **+44% HP/sec** over wave 10. The median D5 death lands exactly there.

## 3. What is CLOSED — do not re-litigate without new evidence

Each of these cost real machine time. The reasons matter more than the verdicts, because the reason
tells you whether a *different* mechanism on the same defect is still live.

| Area | Verdict | Why |
|---|---|---|
| **Movement — route layer** (§31, §32, §33, continuity) | 4 levers, all dead | Body clearance is an **admission gate, never a preference**. The lane score is dominated by continuity (spread 170) over alignment (26.9) over everything else (0.00) — a 20 Hz momentum loop. |
| **Movement — desire layer** (§34, §35) | both config knobs inert; `loot` lever **adverse** | Deleting `enemy_engagement` *entirely* rotates the command **0.11°**. `loot` is the only term with authority (65.91°) and steepening its falloff made in-range **worse**. |
| **Shop valuation — damage tilt** (§30) | fails Gate 0 | 66.3% of buys are already damage-bearing; flippable surface only 13.1%. |
| **Shop valuation — DPS band** (§36) | fails Gate 0 on a **structural ceiling** | The gate's guard needs `slots_full AND not pairs_combine AND gain < floor`; that conjunction is reachable on only **4.66%** of D5 decisions **at any dose**. |
| **Shop valuation — danger-aware marginal DPS** (§37) | weak additive doses `lambda <= 4` fail Gate 0; broader defect still live | Higher-DPS surface passes at **100/409 = 24.45%**, but the strongest fixed dose flips only **63/409 = 15.40%** against 20%. Every flip is positive and magnitude/planning bars pass: this is **score-margin-limited, not surface-limited**. Do not merely extend lambda post hoc; a different constraint mechanism remains viable. |
| **Character selection** (§29) | excluded | ranger 0/16 despite a 2.4x D0 edge; cyborg 0/23 despite the largest offensive multiplier in the game. **Stat block does not predict win rate.** |
| **Build / economy** | excluded | Same DPS, HP, weapons and materials-per-wave at D0 and D5 (matched pair, 16/arm). There is no economic starvation. |
| **Idle materials** | not a problem | Post-shop balance is **13** at wave 9 against a 436 budget — it converts ~97%. |
| **Weapon tier progression** | works | 293 combine events across 64/67 runs. |

⇒ **No parameter currently exposed in either the movement policy or the purchasing policy changes D5
behaviour enough to license a campaign.** The next move has to be structural. §37 is important nuance:
danger-aware DPS prioritization has enough surface, but a weak additive score dose does not cross the
predeclared intervention bar.

⚠️ **Scope this honestly.** These bound the *reachability of specific levers*, mostly on ranger/mutant
at specific builds. They do **not** bound the size of the underlying deficit.

## 4. What is still OPEN

1. **The in-range gap is real and unexplained.** A human player keeps **0.4417** of the living pack
   inside weapon range; the agent manages **0.2801** (d = 4.03, every human trial above every agent
   trial). Enemy presence is nearly identical, so this is a *conversion* difference, not exposure.
   **Five levers have failed to convert this gap. The gap itself is untouched.**
2. **The decision layer is danger-blind.** Verified from source: the only occurrence of `danger` in
   the entire decision tree is the literal string `"item_dangerous_bunny"`. The agent plays D5 with a
   policy tuned at D0, and its wave constants assume 20-wave runs. §37 tested the first target-free
   mechanism: its surface passes, but additive doses through 4 are score-margin-limited.
3. **The DPS target is calibrated on the wrong tier.** `OFFENSE_DPS_TARGETS_BY_WAVE` was fitted to
   **41 Danger-0 victories**. Measured over 10,275 D5 decisions, the agent sits a **median 1.314x
   above** that target and dies anyway. §36 showed the *band gate* cannot exploit this. A different
   mechanism might. **But it may not be justified by re-citing §36 as though that verdict never
   happened.**
4. **The bootstrap.** A D5 target curve cannot be fitted the way the D0 one was, because there are
   zero nominal-D5 victories to fit to. Any D5 curve must be *derived*, which makes the derivation a
   modelling assumption rather than a measurement.

**Direction chosen by the operator on 2026-08-04:** price the danger-aware decision layer offline
before attacking the bootstrap. §37 closes weak additive marginal-DPS doses but leaves a
mechanism-distinct constraint/lexicographic version viable. The next decision is whether to
preregister that stricter offline mechanism or return to the bootstrap; no campaign is licensed.

## 5. ⭐ The methodology — this is the most valuable thing here

This project's results are trustworthy because of a specific discipline. Please keep it; it is what
stops months of work from being noise.

- **Gate 0 before any campaign.** Never run trials to find out whether a lever works. First compute
  *offline, from existing telemetry*, whether the change would flip enough decisions to matter. Most
  proposed levers die here for free. Two instruments exist to make this cheap: `board_scores` (shop,
  per-candidate scores) and `route_scores` (movement, per-lane scores).
- **Pre-register.** Write the bars, the dose ladder, the analysis, and **a prediction** to
  `reports/wp2/<name>_prereg.md` and **commit it before computing the result**. Recording the
  prediction is what stops a null being reported as "expected all along".
- **Controls, before results.** A counterfactual is void unless the simulated rule reproduces the
  decision the agent actually made. Print denominators before any rate.
- **A zero needs a denominator.** Repeatedly, a clean-looking zero has turned out to be a filter that
  could not return the positive — a wrong key, a wrong type, a query that errored. Always pair a zero
  with a positive control in the same output.
- **A self-report proves delivery, never correctness.** A flag reading `true` means a value arrived,
  not that it took effect. Verify behaviour.
- **Report the reason, not just the verdict.** A dose-limited null invites a bigger dose; a
  surface-limited null means the mechanism is aimed at a state that rarely occurs and no tuning helps.

**`.claude/projects/C--Codex-Brotato-Agent/memory/brotato-measurement-discipline.md` contains 33
worked instances of these failures, each with the measurement that caught it.** It is ~80 KB and does
not fit in one read; the newest and most useful entries are at the END. Grep for `^### 3` rather than
reading front-to-back. **If you read only one thing from the old project, read that file.**

## 6. ⛔ Operational rules that destroy data when violated

These were all learned expensively. Violating any one of them silently invalidates a campaign.

- **`deploy_mod.py` rewrites `agent_config.json` from a hardcoded dict** — resetting danger to 0 and
  dropping the E-stop flag. **Always arm the config AFTER deploying, and read it back from disk.**
- **`auto_start` is read once at `_ready()`.** Writing `auto_start=false` does **not** stop a running
  game — it only affects the next launch. **The only way to stop a live game is to kill it by PID.**
  Leaving it running produces unsupervised runs that can drift the unlock pool and invalidate the era.
- **After any force-kill, run `deploy_mod.py --repair-launch` before the next launch, unconditionally.**
  A force-kill makes the mod loader latch "mods disabled"; the latch is applied at the *next* launch,
  so a pre-launch inspection **cannot** detect it. Skipping this once ran the game vanilla for 5
  minutes and produced nothing. **The only proof the mod loaded is a fresh `mod_ready.json` mtime —
  baseline it before launching.**
- **Never bump version constants or deploy while a campaign is running.** The collector's identity
  gate compares the installed build against a *repo* constant; a repo-only edit killed 87% of one
  campaign. Bump only immediately before the deploy that ships it, at all 8 sites, in one edit.
- **"Installed == repo" must mean CONTENT, not the version string.** The identity gate compares
  strings and is blind to a content divergence. Diff the installed zip against the source before any
  campaign — it costs one unzip.
- **`--runs` is a TOTAL, not "additional".** Use `--min-wins 0` for any campaign that is not a
  win-rate gate (the default of 18 aborts instantly). Use `--no-deploy` to freeze a build. Always pass
  `--state-file`.
- **`--stop-on-win` is optional stopping.** Fine for acquisition; poison for anything later reused as
  a comparison arm.
- **Era-match before pooling anything.** The shop's offer pool depends on what has been unlocked, so a
  run collected before an unlock is not comparable to one after. Every summary carries an
  `unlock_pool` stamp. A 47-point win-rate collapse once ran ~20 versions unnoticed for want of this.
- **Never kill processes belonging to other projects.** This machine runs several concurrently.
  Attribute every PID before terminating it. `Brotato.exe` is this project's exclusively.
- **No test parses the mod's GDScript.** A syntax error surfaces as the game sitting on the title
  screen. Source-text assertions in `tests/unit/test_shop_policy_source.py` are the only substitute —
  they use exact strings as positional anchors, so edits there need care.

## 7. Where things are

| What | Where |
|---|---|
| Mod source (GDScript) | `mod/mods-unpacked/Tom-BrotatoAgent/` — decisions in `teacher/shop_strategy.gd`, movement in `teacher/potential_field.gd`, constants in `teacher/config.gd` |
| Pre-registrations and verdicts | `reports/wp2/*_prereg.md`, `reports/wp2/*_verdict.md` |
| Analysis scripts (most have `--self-test`) | `scripts/wp2_*.py` |
| Run archive (authoritative) | `%APPDATA%\Brotato\brotato_agent\runs` — always pass `--runs-dir` explicitly |
| **Accumulated findings** | `.claude/projects/C--Codex-Brotato-Agent/memory/` — start at `MEMORY.md`, which indexes ~30 topic files |

The `memory/` directory was written by the previous agent for its own recall, but it is plain
Markdown and is the densest record of what is known. `MEMORY.md` is the index and is kept under ~140
lines deliberately; detail lives in the topic files it links.

## 8. Suggested first moves

1. Read `MEMORY.md`, then `brotato-measurement-discipline.md` (grep, don't read linearly).
2. Verify machine state before doing anything: no `Brotato.exe` running, `auto_start` false, git
   clean, installed build matches the repo by content.
3. **Do not start a campaign in your first session.** Everything in §3 above was a plausible-sounding
   idea that measurement killed. Form a hypothesis, then find the Gate 0 that prices it offline.
4. When you do propose a lever, write the pre-registration first and commit it.

⚠️ Finally: several verdicts in the record were **corrected by later work** — a pooled statistic that
was a mixture, a headline that contradicted a later intervention, a measurement taken at the wrong
instant. The corrections are marked in place. If you find a claim that looks load-bearing, check
whether a later section supersedes it before you build on it.
