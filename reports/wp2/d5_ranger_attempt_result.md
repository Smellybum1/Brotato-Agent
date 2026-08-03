# §29 Results — First Danger 5 victory attempt on `ranger`: 0/16

**Campaign complete 2026-08-03, 16/16 trials.** Pre-registration:
`reports/wp2/d5_ranger_attempt_prereg.md` (§29a-§29j, written before any §29 run existed).
Analysis: `scripts/wp2_d5_ranger_analysis.py` (authored blind, 36 self-test checks).
Authoritative output regenerated for this report with
`.venv\Scripts\python.exe scripts\wp2_d5_ranger_analysis.py --state-file .tmp/d5_ranger/state.json`.
⚠️ `.tmp/d5_ranger/analysis.txt` predates a reconciliation bug fix (see §6) and is **superseded**.

## 1. Executive verdict

**No victory: 0/16, Wilson 95% [0.0000, 0.1936].** `ranger` was the first character ever selected on
evidence — a **2.4x** higher era-matched D0 win rate than `mutant` (.688 vs .281) — and that advantage
produced **no detectable difference at Danger 5**; terminal wave landed at median 11.0 / mean 10.125,
essentially where `mutant` sat. §29c fixed this outcome as **fully expected and non-falsifying** before
data: D0 competence was already measured not to carry to D5. The premise that died is *"some existing
character can clear D5 today"* — the selection logic itself is intact, and the result coheres with §28's
finding that D5 failure is a property of the agent's **clearance capability**, not of the character.

## 2. Validity before outcome (§29e / §29f)

Per §29e.5 these counts are reported **before any outcome statistic**, exactly as the analysis prints
them.

### 2a. Trial counts — denominator 16

| | |
|---|---|
| design n (§29d) | **16, FIXED** |
| `collected_run_ids` | 16 |
| summaries loaded | 16 |
| summaries MISSING | 0 |
| **valid** | **16** |
| **censored** | **0** |
| **invalid** | **0** |

### 2b. Aggregate gates — denominator 16 on every row

| gate | expected | observed |
|---|---|---|
| `character_observed` | `character_ranger` | **16/16** |
| observed danger | 5 | **16/16** |
| `danger_ok` **PRESENT** | present on every run | **16/16** |
| `mod_version` | `0.2.73-wp2-capture` | **16/16** |
| opener, from `run_start.weapon` | `weapon_pistol_1` | **16/16** |
| era stamp `unlock_pool` | `179/48/2018397571` | **16/16, CONSTANT** |

Opener values from events `['weapon_pistol_1']` and from summary `['weapon_pistol_1']` — the two
sources agree, and the certified value is the behavioural one (§29d). Per §29e.1/§29e.2 the vacuous
flags `character_ok` / `danger_ok` are **never gated on**; the observed value is asserted and only
`danger_ok`'s *presence* is counted.

**Era did not drift.** §29h's per-run stamp requirement is met and the arm is internally poolable.

### 2c. §29f reconciliation — vanished-run check

Both denominators printed, as §29f demands (a zero here means nothing otherwise):

| | |
|---|---|
| directories in runs dir, total | 2529 |
| `baseline_run_ids` (SUMMARIES, not dirs) | 2236 — **not** used as the window; see §6 |
| campaign floor epoch (earliest collected run) | 1785724093 |
| **DENOMINATOR A**: directories in the campaign window (run-id epoch ≥ floor) | **17** |
| **DENOMINATOR B**: `len(collected_run_ids)` | **16** |
| excess (A not in B) | **1** |

The single excess directory, listed individually and never silently dropped:

- `run_1785731852_60447` — `last_event=combat_capture`, `last_wave=3`,
  `terminal_hp=9` (`combat_capture.payload.player.hp`).

**Disposition: this is the run in flight, not a vanished death.** It started 9 s before campaign end,
was at **wave 3 and ALIVE at HP 9**, and was terminated by the driver's final `kill_game()`. §29f's
concern is specifically `dead_stuck`, which fires only at `hp == 0` and can therefore silently drop only
**deaths** — outcome-selection that would flatter the arm. A live run at HP 9 killed by campaign
teardown is not that path. **Vanished-run check: CLEAN.**

⚠️ **Inconsistency between prereg and analysis, reported rather than smoothed over.** §29f states the
two denominators *"must match"*, with no exemption for an in-flight trial. They do not (17 vs 16), so
the blind analysis flags a VALIDITY PROBLEM and **exits 3**. The script's own note anticipates this
(*"one of these may simply be the run in flight"*), and its rule — list every excess individually with
its last event and terminal HP — is what makes the disposition auditable. The literal §29f bar is
therefore **not met as written**; it is met on the intent of the check. Recorded here as a defect in the
pre-registration's wording, not resolved by reinterpreting the data.

### 2d. Supervisor log greps (§29f)

`.tmp/d5_ranger/supervisor.log`, **lines scanned (denominator) = 479**:

| pattern | count |
|---|---|
| `Death screen stuck` | **0** |
| `Telemetry stall` | **0** |
| `Run timeout` | **0** |

No restart path fired. **Zero technical failures across the campaign.**

## 3. Primary endpoint (§29g) — victory, binary, era-independent

Candidate set size (runs with a summary) = **16**. Distinct `result` values observed: `['defeat']`.

> **VICTORIES: 0/16.** Rate 0.0000, **Wilson 95% [0.0000, 0.1936]** — descriptive only, not a test, and
> nothing branches on it.

**North star 1 is NOT satisfied.** No Danger 5 run was won.

## 4. Secondary endpoint (§29g) — terminal wave (characterisation)

Candidate set size = 16; runs with a numeric `last_wave` = 16. **Full raw series, sorted** (a summary
statistic alone is never sufficient):

```
[6, 6, 7, 7, 7, 10, 11, 11, 11, 11, 12, 12, 12, 12, 13, 14]
```

Paired to run id, in collection order:

| # | run_id | terminal wave | result |
|---|---|---|---|
| 1 | `run_1785724093_34897` | 11 | defeat |
| 2 | `run_1785724634_65034` | 12 | defeat |
| 3 | `run_1785725230_65556` | 13 | defeat |
| 4 | `run_1785725919_86033` | 7 | defeat |
| 5 | `run_1785726209_46799` | 12 | defeat |
| 6 | `run_1785726826_28` | 10 | defeat |
| 7 | `run_1785727317_86461` | 12 | defeat |
| 8 | `run_1785727911_17646` | 6 | defeat |
| 9 | `run_1785728134_80069` | 7 | defeat |
| 10 | `run_1785728408_14235` | 7 | defeat |
| 11 | `run_1785728679_28404` | 11 | defeat |
| 12 | `run_1785729225_76369` | 11 | defeat |
| 13 | `run_1785729746_55624` | 14 | defeat |
| 14 | `run_1785730480_61862` | 11 | defeat |
| 15 | `run_1785731016_38858` | 6 | defeat |
| 16 | `run_1785731239_56630` | 12 | defeat |

**n=16 · median 11.0 · mean 10.1250 · sd 2.6300 · min 6 · max 14.**

**Runs at wave ≥ 20: 0/16 = 0.0000.** The §28g ceiling rule (≥50% at wave 20) **does not fire**, so
terminal wave is a point characterisation here, not a floor. No arm was ceilinged.

## 5. The finding

A **2.4x** D0 win-rate gap between `ranger` (11/16 = .688) and `mutant` (9/32 = .281), measured at a
common era, produced **no detectable D5 difference**. Both arms are **0/16**. Terminal-wave
distributions are near-identical: ranger median **11**, mean **10.125** (§29, this campaign) against
mutant's median **11**, mean **10.56** (§26 context, different era). The best character we have, run on
its own verified entry build, dies in the same place as the character chosen for era stability.

## 6. What this does and does not establish

**⛔ The ranger-vs-mutant D5 comparison is ERA-CONFOUNDED and no statistic exists for it.**
Ranger D5 sits at `179/48/2018397571`; mutant D5 sits at `177/46/2286319327`. **Different era ⇒ NOT
POOLABLE.** §29g pre-registered this comparison as **INDICATIVE ONLY** before data, precisely so it
could not be decided afterwards. **No p-value, no test, no effect size is computed for it, by design** —
and none should be computed later. Everything in §5 above beyond ranger's own numbers is *context*.

**⛔ 0/16 vs 0/16 cannot resolve a small difference.** Both arms are bounded above at **0.194** by the
descriptive Wilson interval. Two zeros at n=16 are consistent with a real ranger advantage of up to
roughly that size. **"No difference detected" is not "no difference."** This arm has no power to
separate small true win rates from zero.

**✅ The selection logic was sound; §29c called this outcome in advance.** §29c, fixed before data:
*"D0 competence is MEASURED not to carry to D5"* — same character, build and era, **mutant D0 5/16 =
.3125 → D5 0/16 = .000, p = 0.043** (§25/§26 context). Ranger's .688 was declared a **SCREENING signal,
never a prediction**, and a ranger 0/16 was declared *fully expected and non-falsifying*. It is also
recorded and **not upgraded** (§29b) that ranger being the top D0 cell is **best-of-N outcome
selection**: the non-selected statistic is the exact 4-group homogeneity test on §25's bare arm,
**p = 0.00606** (licenses *"characters differ"*), while bare ranger vs bare mutant is **5/8 vs 1/8,
p = 0.119** (does not license *"ranger beats mutant"*). §29 replicates the one D0→D5 transfer
measurement we have. **What died is not the selection method — it is the premise that any character
available today clears D5.**

**✅ Coheres with §28.** §28 measured D5 failure to be **CLEARANCE-limited, not survival-limited**
(health moved terminal wave +3.500 / +7.375; damage did not). A character swap changes the stat block,
not the agent's rate of killing. §29 is the behavioural corollary: picking a better character does not
buy clearance, so it does not buy D5.

**Numbers by provenance.** §29 (this campaign): 0/16, Wilson [0, 0.1936], the raw terminal-wave series
and its descriptives, all validity counts, the reconciliation and log greps. Quoted context, **not §29
evidence**: mutant D5 0/16 / mean 10.56 / median 11 at era `177/46/2286319327` (§26); mutant D0 .3125 →
D5 .000, p = 0.043 (§25/§26); D0 selection rates and p = 0.00606 / p = 0.119 (§29b, from §25's bare
arm); §28's clearance result.

## 7. Defects found

**(a) The §29f reconciliation initially reported 277 "vanished runs" — a false positive from a wrong
denominator.** The campaign window was computed as `all_dirs − baseline_run_ids`. But
`baseline_run_ids` is built by `overnight_supervisor.py:42-52` from **`list_summaries()` — SUMMARIES,
not directories**. Every historical run that never wrote a summary is therefore absent from the
baseline and was misread as campaign-window excess: 293 window dirs and **277 "vanished runs"**, dating
back to `run_1784xxx`, weeks before the campaign existed. A wrong denominator manufacturing a large,
alarming and entirely false positive — on a check whose whole purpose is to detect silent
outcome-selection.

**(b) The 36-check self-test passed anyway, because the bug was unreachable in the fixture.** The
fixture built its baseline from directories it had just created, so the summary set and the directory
set **coincided** and the defective subtraction was indistinguishable from the correct one. A green
self-test on a fixture that cannot express the failure mode.

**Fix:** derive the window from the run-id epoch — ids are `run_<epoch>_<rand>`, so the campaign window
is bounded below by the **earliest collected run** (floor 1785724093 here).

**(c) Fixing it then broke 2 of the 36 checks — and that failure was the informative part.** The
fixtures used opaque run names like `camp_null_run_00`, from which no epoch is derivable, so those
checks had been exercising the **"window underivable / NOT COMPUTED" fallback branch** rather than the
real reconciliation they claimed to test. Fixtures were repointed at realistic `run_<epoch>_<rand>` ids,
with baseline runs placed **below** the floor and excess dirs **above** it — the only arrangement in
which the vanished-run check can test what it advertises. **All 36 checks now pass.**

## 8. Recommended next step — as a question, not an answer

**The lever must be a capability change, not a character pick.** §29 exhausts the character-selection
route: the best-evidenced character available, run on its verified entry build with zero technical
failures, produced 0/16 and a terminal-wave distribution indistinguishable from the previous baseline.
There is no further character to try that carries stronger prior evidence than `ranger` did.

The open question is therefore: **which reachable change raises the agent's clearance rate at D5 — and
can it be shown to flip a real decision before any trials are spent on it?**

⛔ **Gate 0 still binds.** Prove a candidate flips a real decision at a reachable dose BEFORE spending;
measure on the FINAL command; and prove the endpoint's **within-arm spread is smaller than the effect**
first — for this endpoint that spread is **sd 2.6300** on the §29 arm (n=16, raw series in §4), against
§26's D5 within-arm sd of 1.590. ⛔ A defensive lever justified by *"D5 kills us"* remains **not
licensed** (§28).
