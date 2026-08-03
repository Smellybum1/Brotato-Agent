# §29 — First Danger 5 victory attempt: `ranger`

**Pre-registration. Written 2026-08-03, BEFORE any §29 run exists.**
Supersedes nothing. Companion to `d5_scaling_intervention_prereg.md` (§28) and
`d0_d5_matched_pair_prereg.md` (§26).

---

## 29a. Objective

**North star 1: win a Danger 5 run** (`docs/ROADMAP.md`). This campaign is an **ATTEMPT**, not a
comparison. The deliverable is a victory if one occurs, plus a fixed-n, uncensored, era-stamped
`ranger` D5 arm that later work can reuse.

Every prior D5 attempt ran `mutant`, selected for **era stability, not capability**. §29 is the first
campaign whose *character* was chosen on evidence.

## 29b. Why `ranger` — the selection, fixed before this campaign

Era-matched D0 evidence at `177/46/2286319327` (see `.tmp/char_census/census.md`):

| character | wins | rate |
|---|---|---|
| **ranger** | **11/16** | **.688** |
| jack (ported) | 17/32 | .531 |
| mutant | 9/32 | .281 |
| arms_dealer / artificer / cyborg / fisherman | 0/17, 0/16, 0/15, 0/8 | .000 |

- Ranger being the top cell is **best-of-N**, i.e. outcome selection. The non-selected statistic is
  the **exact 4-group homogeneity test on §25's bare arm: p = 0.00606**. That licenses *"characters
  differ"*. It does **not** license *"ranger beats mutant"* — bare-vs-bare is 5/8 vs 1/8, **p = 0.119**.
  Both are reported; neither is upgraded.
- Ranger is strong **BARE** (5/8) as well as ported (6/8). Jack competes only when ported, and §25
  measured the port **Jack-specific**. §29 runs the port **INERT**.
- Rejected on source inspection, not on summaries: **`soldier`** carries `can_attack_while_moving = 0`
  and gates both damage bonuses on `temp_stats_while_not_moving` — disqualifying for a movement-only
  agent. **`cyborg`** has the largest offensive multiplier in the game
  (`effect_increase_stat_gains +250` on `stat_ranged_damage`) and is measured **0/23** ⇒ stat block
  does not predict win rate. **`one_arm`** has `weapon_slot −5` (1 weapon) against a shop policy that
  buys six.

## 29c. ⛔ THE CAVEAT THAT BINDS — declared before data

**D0 competence is MEASURED not to carry to D5.** Same character, build and era:
**mutant D0 5/16 = .3125 → D5 0/16 = .000, p = 0.043.**

⇒ **Ranger's .688 is a SCREENING signal, not a prediction.** A ranger 0/16 at D5 is a fully expected
outcome and **does not falsify the selection** — it would replicate the only D0→D5 transfer
measurement we have. Nothing in this pre-registration should be read as predicting a win.

## 29d. Arm — fixed before data

| | |
|---|---|
| character | `character_ranger` |
| danger | **5** |
| build | `0.2.73-wp2-capture`, **frozen for the whole campaign** |
| profile port | **INERT** (`EXPERIMENT_PORT_WR_PROFILE_TO = ""`) |
| `movement_estop_enabled` | **false** (unattended) |
| `weapon_prefixes` | **`weapon_pistol` FIRST** — see below |
| n | **16, FIXED** |
| stopping | **NO `--stop-on-win`.** Operator decision, 2026-08-03. |

⛔ **THE PREFIX IS LOAD-BEARING AND TODAY'S CONFIG IS WRONG FOR RANGER.** All 16 ranger evidence runs
opened `weapon_pistol_1`, verified **behaviourally** from `run_start.weapon`, 16/16. Ranger's
inventory is pistol, smg, revolver, laser_gun, shredder, crossbow — **all RANGED** — and
`_select_inventory_by_id_prefix` (`run_orchestrator.gd:271`) is a **SUBSTRING match tried IN ORDER**.
The config in place on 2026-08-03 begins `weapon_smg`, and **ranger has an smg**, so it would open on
SMG — a different entry build from every run in the evidence base.
⇒ `weapon_prefixes = ["weapon_pistol", "weapon_smg", "weapon_shredder", "weapon_"]`.
⚠️ **A disk readback of this key proves nothing** (§6 passed exactly that readback while nothing
consumed the key). **Certify from `run_start.weapon` on trial 1 and abort if it is not
`weapon_pistol_1`.**

## 29e. Validity gates — checked and REPORTED PER ARM BEFORE any outcome statistic

1. `character_observed == "character_ranger"` on all 16. ⚠️ **`character_ok` is CONSTANT True across
   all 276 era-stamped runs ⇒ VACUOUS as a filter.** Assert the observed value, never `character_ok`.
2. `danger_ok` **present** and observed danger **5**. ⚠️ Its VALUE is constant True; only its
   PRESENCE is informative.
3. **Era stamp `unlock_pool` recorded per run and reported.** Expected constant at
   `179/48/2018397571`.
4. Opener `weapon_pistol_1`, from `run_start.weapon`.
5. Trial counts — valid / censored / invalid — reported **per arm before any outcome**.

## 29f. ⛔ REJECT-BY-OUTCOME AUDIT — audited against the driver this campaign ACTUALLY uses

11(b), the 17th, 25th and 27th measurement-discipline instances are all this defect. **Fixing one
instance does not close the class**, and a guard audit of the wrong file closes nothing at all.

⚠️ **First draft of this section audited `wp2_finale_loop.py` — the FIXTURE loop, which §29 does not
use.** §29 collects **full runs** via `scripts/d5_pair_campaign.sh` → **`overnight_supervisor.py`**.
Corrected audit, read from that source:

**The supervisor applies NO validity filter at collection.** `:356-370` lists new summaries and
appends **every** one to `collected`. There is no `valid` flag, no wave gate, no boss check. ⇒ **There
is no reject-by-outcome path at collection.** This is structurally safer than the fixture loop.

| path | discards a collected run? | selects on outcome? |
|---|---|---|
| `--stop-on-win` (`:377`) | no | ⛔ **YES** — censors the arm on its highest value (§22). **NOT USED in §29.** |
| `--min-wins` early abort (`:382`) | ends the campaign | ⛔ Would, but `max_losses = runs − min_wins`. **`--min-wins 0` ⇒ max_losses = 16 ⇒ unreachable in a 16-run campaign.** MUST pass `--min-wins 0`. |
| `run_timeout_sec` (`:479`, default 2700) | no — `relaunch()` only | **No.** Measured from **last PROGRESS**, not from run start, so a long *successful* run keeps resetting it. Correct by construction — unlike the fixture loop's absolute cap. |
| `stall_sec` (`:472`) | no | No — same last-progress basis. |
| `dead_stuck` (`:459`) | no, but see below | ⚠️ **Fires only when `hp == 0`**, i.e. only on DEATHS. |
| game-exited / no-re-arm | no | No. |

⛔ **THE ONE RESIDUAL RISK — runs that are INVISIBLE rather than rejected.** Every restart path calls
`relaunch()`, which kills the game. A run killed **before its summary is written produces no summary
and is therefore never collected** — it does not appear as an invalid trial, it simply never existed.
**`dead_stuck` is the concerning one: it fires on `hp == 0` with no summary for 45 s, so the only runs
it can silently drop are DEATHS.** That is outcome-selecting in the direction that flatters the arm.

⇒ **PRE-REGISTERED CHECK, run before any outcome statistic:** count the **run directories created in
`%APPDATA%\Brotato\brotato_agent\runs` during the campaign window** and compare against
`len(collected_run_ids)`. **They must match.** Any excess directory is a run that vanished; each is
listed individually with its last event and terminal HP, and reported as a **known unmeasured trial**,
never silently dropped. Also grep the supervisor log for `Death screen stuck`, `Telemetry stall` and
`Run timeout` and report the counts.
⚠️ **A count of zero here means nothing unless the directory-vs-summary reconciliation was actually
computed** — print both denominators, not just the difference.

## 29g. Endpoint and analysis — fixed in advance

- **PRIMARY (objective): victory, binary.** Era-independent. A win at any point satisfies north star 1.
- **SECONDARY (characterisation): terminal wave**, full raw per-run series printed, median/mean/sd.
- ⛔ **NO comparison to mutant's D5 0/16 may be reported as evidence.** Mutant's D5 arm sits at era
  **177/46/2286319327**; §29 runs at **179/48/2018397571**. **Different era ⇒ NOT POOLABLE.** Any
  ranger-vs-mutant D5 statement is **ERA-CONFOUNDED and INDICATIVE ONLY.** This is declared now so it
  cannot be decided after seeing the result.
- ⛔ **No extension, no top-up-and-retest, no interim interpretation.** §26's D5 within-arm sd is
  **1.590**; n < 16 does not discriminate.
- ⚠️ If ranger reaches wave 20 in ≥50% of trials, terminal wave becomes a **FLOOR** (§28g ceiling
  rule) and its effect must be reported as a bound, not a point estimate.

## 29h. Era drift — re-derived for THIS population, not inherited

✅ Verified in the live save 2026-08-03, positive **and** negative controls passing:
`chal_ranger`'s reward is `item_night_goggles` (djb2 3604644852, `my_id` read from the reward's own
file) — **already unlocked**; `chal_ranger` — **already completed**. ⇒ **A ranger victory grants
nothing and cannot move the pool.**

⚠️ **This is a re-derivation, not an inheritance.** §25 inherited Jack's era-safety onto four new
characters without re-checking and lost a campaign. ⛔ **The stamp is still recorded PER RUN and
reported.** If it moves, that is disclosed; it voids the comparative use of the arm but **not** the
victory objective, which is era-independent.

## 29i. Launch preconditions — all must pass, in order

1. `deploy_mod.py --repair-launch` — **unconditional.** The §28 driver's `finally` calls
   `stop_game()` (a `Stop-Process -Force`) and **nothing repaired after it**. The mods-disabled latch
   is applied at the NEXT launch, so **a pre-launch inspection cannot detect it**; skipping this once
   already cost 5 minutes of VANILLA play.
2. Installed-vs-repo **CONTENT** diff (not the version string).
3. Arm written **AFTER** any deploy — `deploy_mod.py` rewrites `agent_config.json` from a hardcoded
   dict (`danger: 0`, no `movement_estop_enabled` key). Read back from disk.
4. Baseline `mod_ready.json` mtime **BEFORE** launching; a stale-but-present file reads as healthy.
5. Trial 1 opener certified `weapon_pistol_1` before letting the campaign run on.

## 29j. Exposure disclosure

The author has seen: all D0 per-character win rates (they are the selection basis), mutant's D5
0/16, and §28's control terminal-wave mean 9.625. **No §29 outcome existed at the time §29a-§29i were
written.**

### Exposure accrued AFTER the rules were fixed — disclosed, not hidden

1. **The analysis script was authored BLIND** (`scripts/wp2_d5_ranger_analysis.py`), while the
   campaign was running and before any §29 outcome was read. Verified in the primary session:
   **36 self-test checks pass, exit 0**, and importing the module prints nothing and computes no
   verdict. It validates `wilson` against an independent quadratic-root derivation, exercises the
   §28g ceiling rule at its exact `>=` boundary in both directions, and proves the victory branch is
   reachable and distinct from the null branch — i.e. **the statistic can return the positive.**
2. ⚠️ **The blind author incidentally opened §29 run 1's `events.jsonl`** for schema reconnaissance
   and saw **event names and payload KEYS only — no result, wave, HP or summary** — then stopped.
   Self-disclosed. Recorded here because an undisclosed look is the problem, not a schema read.
3. ⚠️ **The primary agent sees per-run outcomes AS THEY ARRIVE** while supervising (run 1:
   `defeat`, wave 11). This is unavoidable in a supervised campaign and is **harmless here by
   construction**: n is FIXED at 16, there is no `--stop-on-win`, no extension and no top-up clause,
   the endpoints were fixed in §29g before collection, and the analysis is already written and
   self-tested. **No analyst degree of freedom remains to be exercised.** Same disposition as §28i —
   disclose exposure and rely on a choice-free design, never on one's own blindness after looking.
