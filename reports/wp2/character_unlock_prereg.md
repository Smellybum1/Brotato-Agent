# Pre-registration — three-character unlock campaign (S-tier item acquisition)

Date: 2026-07-30. Recorded **before any attempt is collected.**
Supersedes the 28-character grind in `unlock_campaign_plan.md` §7; rationale in that document's
§2c / §2d / §2e.

## 1. What this is, and what it is NOT

This is an **acquisition task**, not a hypothesis test. The deliverable is three unlocked items. There
is no endpoint, no arm comparison and no p-value, so this document fixes **validity and stopping
rules** rather than a decision rule.

**It is explicitly NOT a claim that unlocking improves Danger 5.** Measured leverage is: sign positive
(substitutions run toward items the scorer ranks +18/+28 above the B-tier median that is 55.4% of its
current buys), volume ~2-4 new-item purchases per full run of ~30. **Effect on the D5 terminal wave is
NOT established and this campaign does not test it.**

## 2. Targets

| item | scorer tier | win with | character unlocked? |
|---|---|---|---|
| `item_anvil` | **S** (+28) | `character_arms_dealer` | yes |
| `item_explosive_shells` | **S** (+28) | `character_artificer` | yes |
| `item_giant_belt` | **S** (+28) | `character_jack` | yes |

Effect on the pool, computed exactly as `save.items_unlocked` ∩ scorer allowlist:
**S-tier 8 → 11 (+38%).**

**Danger 0**, because the reward is identical at every danger and D0 is cheapest.

## 3. Frozen for the campaign

```
mod version            0.2.62-wp2-capture   (to be deployed AFTER the D5 baseline finishes)
policy version         teacher_v1-0.1.129-gun-wp1
danger                 0
movement_estop_enabled false
time_scale             1.0
student_enabled        false
all dev knobs          inert defaults
```

⛔ **Do not deploy or bump identity constants once this starts.** The installed build and the repo's
`MOD_VERSION` must agree for the whole campaign — a repo-only edit breaks the identity gate exactly as
a deploy would.

## 4. Per-attempt validity — evaluated before any outcome

```
requested_character == the configured target
character_observed  == requested_character      (latched on the FIRST COMBAT TICK)
character_ok        == true
requested_danger    == 0  and  observed danger == 0  and  danger_ok == true
mod_version         == 0.2.62-wp2-capture
capture stream parses to EOF
```

`character_observed == "(never-read)"` means **no combat tick ever ran** — a technical failure, NOT a
character mismatch, and never silently a pass. `requested_character == ""` fails `character_ok` by
construction rather than passing vacuously.

**A technical failure is recorded and reported separately. It is NEVER excluded on the basis of its
outcome.**

## 5. Stopping rule — fixed in advance

- **Up to 8 attempts per character.** Stop that character early on its first victory (the item is
  unlocked; further runs add nothing).
- If a character reaches 8 attempts with no win, **stop and report it** rather than extending. The
  `0.395` D0 baseline is `well_rounded`'s and does **not** transfer — Jack in particular is a
  glass-cannon character. An unexpectedly low win rate is a finding about that character, not a reason
  to keep paying.
- Total cap **24 attempts** (~7.6 h at ~19 min/run). Reaching the cap ends the campaign.

## 6. Known operational risk — the weapon-select stall

`run_orchestrator.step()` handles `STARTING_WEAPON_SELECT` by trying each entry of
`target_weapon_prefixes` and, on no match, falling through to `{"acted": false}` — i.e. **it stalls at
the weapon screen rather than picking something.** The default prefixes are `weapon_smg` /
`weapon_stick`, which are `well_rounded`'s; a different character's screen may offer neither.

**Mitigation, config-only:** set `weapon_prefixes = ["weapon_smg", "weapon_stick", "weapon_"]`.
`_select_inventory_by_id_prefix` matches by substring, so the bare `weapon_` fallback matches any
weapon and cannot stall.

A stall is a **technical failure to fix**, never evidence about the character.

## 7. ⚠️ Each unlock creates a new measurement era

`item_service.init_unlocked_pool()` filters on `items_unlocked` / `weapons_unlocked`, so every unlock
changes the distribution all later runs sample from.

- **`unlock_pool` era stamp ships in `0.2.62`** — `{items, weapons, items_hash, weapons_hash}` in every
  run summary, `-1` / `""` when unread. Era-matching becomes mechanical instead of remembered.
- **The D5 baseline on `0.2.61` was collected PRE-unlock and must never be pooled with post-unlock
  runs.** Expected stamp for the pre-unlock era: `items = 171`, `weapons = 46`.
- Verify the stamp changes after each win. If it does not, the unlock did not land.

## 8. Order

Arms Dealer → Artificer → Jack. Re-verify the pool fingerprint after each.

### 8b. AMENDMENT 2026-07-30, recorded BEFORE any campaign attempt is collected

Three corrections, all forced by evidence found during the pre-campaign smoke. Dated ahead of
collection deliberately; the §5 stopping rule is untouched.

**(a) The version pin moves to `0.2.63-wp2-capture`.** §3 and §4 pinned `0.2.62`. The smoke exposed a
weapon-select stall that made two of the three target characters unplayable (see (c)); fixing it
required a deploy. Everything in §4 otherwise stands, with `mod_version == 0.2.63-wp2-capture`.

**(b) "+1 per win" IS WRONG — items unlock on DEFEATS, via challenges.** Measured across six Arms
Dealer runs, every one a defeat: `unlock_pool.items` went **171 → 172 → 173** with matching hash
changes. Root cause read from the game source: `ChallengeService.unlock_reward` appends to
`ProgressData.items_unlocked` when a **challenge** completes, and challenges are conditions like waves
reached — they do not require a victory. **So the shop pool drifts from ordinary play, and a 24-attempt
campaign will change its own sampling distribution several times.** The rule is replaced: **record the
stamp on every run and era-match on it; never assert an expected delta.** A change is data, not a
defect. Verified against the save file that **none of `item_anvil` / `item_explosive_shells` /
`item_giant_belt` is unlocked**, so all three targets remain genuinely locked and the campaign stands.

**(c) Four already-collected Arms Dealer runs COUNT as attempts 1-4.** After each smoke driver exited,
`auto_start` stayed true in `agent_config.json` and the game kept starting runs unsupervised, producing
six Arms Dealer defeats — two on `0.2.62` and **four on `0.2.63`** (terminal waves 5, 11, 15, 17). The
four on `0.2.63` are arm-identical and era-matched to this campaign, and **all four are known
defeats**. Counting them spends budget rather than flattering the result; discarding known-defeat
attempts and replacing them with fresh ones would select on outcome, which §4 forbids. **Arms Dealer
therefore has 4 attempts remaining, not 8.** The two `0.2.62` runs are excluded by the version pin and
recorded here rather than deleted.

**Operational rule added:** `auto_start` must be disarmed **when a driver exits**, not only when a
campaign ends — a finished driver does not stop the game.

## 9. First action when the D5 baseline completes

1. Confirm `.tmp/d5_campaign_v261/report.json` exists; disarm `auto_start`.
2. Bump to `0.2.62` (four code sites + three pin tests **in the same edit**), run the suite, deploy.
3. Set config AFTER deploying — `deploy_mod.py` rewrites `agent_config.json` wholesale and reset
   `danger` to 0 last time. Read back from disk before launching.
4. Smoke ONE attempt and verify `character_ok == true` and a populated `unlock_pool` **before**
   committing to the campaign. A flag's self-report proves delivery, not correctness.

### 8c. AMENDMENT 2026-07-31, recorded BEFORE Artificer attempt 3 is collected

**Attempts 1 and 2 are already collected (both defeats, terminal waves 7 and 5). They COUNT as
attempts 1-2 and are NOT discarded** — §8b established that discarding known-defeat attempts and
recollecting selects on outcome, and that reasoning binds here too. This amendment changes the
configuration for attempts 3-8 only, and both arms are reported separately.

**The defect.** `run_orchestrator.gd:156` tries each entry of `target_weapon_prefixes` in order and,
on a total miss, falls through to the `0.2.63` last-resort `"weapon_"` match, which selects **the
first** matching inventory entry. Artificer's `starting_weapons` are plank / screwdriver / wrench /
shredder; the configured prefixes were `["weapon_smg", "weapon_stick", "weapon_"]`, which match none
of the first three, so the fallback hands it **`weapon_plank_1` — MELEE**. Confirmed in both collected
attempts (`run_start.weapon == weapon_plank_1`).

**Why that is a technical failure and not a property of the character.** `build_profiles.gd:148-155`
gives `character_artificer` **`allow_melee: false`**, and that flag is binding, not cosmetic:
`shop_strategy.gd:261` returns **`-1e9`** for a melee weapon in `_weapon_value()`, `:1859` discards
melee crate drops, and `_owned_weapon_value()` (`:342-346`) routes an *already-held* melee weapon
through the same `-1e9`, which makes it the lowest-valued weapon and therefore the standing sell
victim at `:1618-1625`. So the fallback starts Artificer with a weapon its own shop policy can never
upgrade and will always sell first. §6 already classifies weapon-select behaviour as **"a technical
failure to fix, never evidence about the character"**; this is the same family, one step downstream of
the stall that §8b(a) fixed.

**Evidence that `allow_melee` is live** (positive control, 1,627 weapon purchases over 50 recent runs):
melee share **0/665 well_rounded** and **0/15 artificer** (both `allow_melee: false`) against
**463/947 = 48.9% arms_dealer** (default `true`). The zeros are informative, not vacuous.

**The fix is CONFIG-ONLY — no deploy, no rebuild, `MOD_VERSION` untouched, the build stays frozen at
`0.2.63-wp2-capture` and §3/§4 are unaffected.** `weapon_prefixes` becomes
`["weapon_shredder", "weapon_smg", "weapon_stick", "weapon_"]`. `weapon_shredder_1` is **RANGED**
(`weapons/ranged/shredder/1/shredder_data.tres`, `type: 1` against `weapon_type.gd` `{MELEE=0,
RANGED=1}`) and carries `sets = [gun_set_data, explosive_set_data]`, matching the profile's own
`preferred_sets: ["set_explosive"]`. **It fails safe:** if `weapon_shredder` matches nothing the loop
falls through to exactly today's behaviour.

**Honest statement of the adaptive element.** This change is being made after observing two defeats.
The justification is mechanistic and outcome-independent — the plank/`allow_melee` conflict is a
source-level fact that would hold identically had both attempts won — and no attempt is being
discarded. It is recorded here rather than folded silently into the campaign.

**Readback required before attempt 3 counts under the new arm:** `run_start.weapon` must read
`weapon_shredder_1`. A disk readback of `weapon_prefixes` is NOT sufficient — that exact readback
passed in §6 while nothing consumed the key. The proof is behavioural.

⚠️ `_load_auto_config()` runs once at `_ready()` (`agent_controller.gd:304`), so a config edit does
**not** reach the live game. The game must be restarted for this to take effect.

**Arms Dealer is NOT affected by this defect** — pistol is RANGED and its profile leaves `allow_melee`
at the default `true`. Its 0/8 has a different cause, still unexplained.

## 10. RESULTS — Artificer, recorded 2026-07-31 at the §5 stopping rule

**8/8 attempts collected, 8/8 VALID, 0 technical failures, 0 VICTORIES.
`item_explosive_shells` NOT unlocked.** Verified after collection by djb2 membership with the four
positive controls (`item_potato`, `item_padding`, `item_night_goggles`, `item_lens`) all reading True,
so the test was capable of returning the positive.

Terminal waves, raw, collection order: **[7, 5, 9, 9, 7, 20, 11, 7]**. Attempt 6 reached **wave 20** —
Artificer is not incapable of reaching the finale.

Every attempt: `character_ok` true, `requested_character == character_observed == character_artificer`,
`danger_ok` true, `requested_danger` 0, `mod_version == 0.2.63-wp2-capture`.

**Era stamp `174 / 46`, hash `1654160608`, UNCHANGED across all eight.** §8b(b) predicted the pool
would drift because challenges complete on defeats; it did not, because the wave-reached challenges
were already exhausted by well_rounded's ~1,275 prior runs. The mechanism stands; the stock was empty.
All eight attempts are therefore era-matched to each other.

Arms per §8c — **bookkeeping, NOT a controlled comparison** (sequential, n=2 vs 6, changed after two
observed defeats): A_melee_plank [7, 5] · B_ranged_shredder [9, 9, 7, 20, 11, 7].

**§5 applied as written: STOP at 8, report, do not extend the cap.** An unexpectedly low win rate is a
finding about the character, not a reason to keep paying.

### 10b. The `0.395` D0 baseline does not transfer — now measured on two characters
`well_rounded` wins **0.395** of D0 full runs. **Arms Dealer 0/8 + Artificer 0/8 = 0 wins in 16 formal
attempts**, which under a common 0.395 rate has probability **0.605^16 ≈ 1.7e-4**. Pooling two
characters assumes a shared rate, so treat the exact figure loosely — but the direction is firm: **the
agent is tuned for `well_rounded` and plays other characters far worse.** §5 anticipated exactly this.

⚠️ The one acquisition to date (`item_anvil`) came from an **unsupervised** Arms Dealer run, not a
formal attempt. It confirms the campaign's premise; it does **not** show the win rate is workable.

**Artifacts:** `.tmp/unlock_artificer/ledger.{csv,md}`, `reports/unlock_artificer.{csv,md}`,
driver `DONE runs=8 wins=0 gate=0 exit=0`.

### 10c. Jack campaign armed 2026-07-31 02:43
`weapon_prefixes = ["weapon_smg", "weapon_shredder", "weapon_knife", "weapon_"]` — verified
entry-by-entry against all four characters' real `starting_weapons`. **`weapon_smg` MUST precede
`weapon_knife`**: `well_rounded`'s inventory lists knife FIRST, and its profile has `allow_melee`
false, so a knife-first list would hand it a `-1e9` weapon. Bare `"weapon_"` stays last as the
anti-stall fallback. Jack permits melee (`build_profile.gd:9` default `allow_melee = true`; Jack sets
no key) and its `set_precise` preference matches `weapon_knife_1`.
✅ Smoke verified BEHAVIOURALLY: `run_1785429819_7851` `weapon == weapon_knife_1`,
`character == requested_character == character_jack`.

## 11. RESULTS — Jack, recorded 2026-07-31 at the §5 stopping rule

**8/8 attempts collected, 8/8 VALID, 0 technical failures, 0 VICTORIES.
`item_giant_belt` NOT unlocked**, `chal_jack` not completed — verified after collection by djb2
membership with the four positive controls all reading True.

Terminal waves, raw, collection order: **[16, 16, 16, 12, 16, 17, 17, 17]**.
**Single arm throughout: `weapon_knife_1` (MELEE), 8/8** — the §8c arm change was Artificer-only.
Every attempt: `character_ok` true, `requested_character == character_observed == character_jack`,
`danger_ok` true, `requested_danger` 0, `mod_version == 0.2.63-wp2-capture`.
Era stamp **174 / 46, hash `1654160608`, unchanged across all eight.**

### 11b. Jack's failure is a WALL at wave 16-17, not a diffuse spread
6 of 8 attempts ended at wave 16 or 17; the deepest was 17 and the shallowest 12. Artificer, by
contrast, spread 5-20. **This is a phenotype worth its own investigation** — and it sits exactly at
the project's wave-16 terminal-win landmark endpoint.

⚠️ **An artifact was ruled out before this was believed.** The first three attempts ended at *exactly*
wave 16 with **HP RISING** in the final captures (17→21, 24→27, 14→18), which looks like a harness
truncation mislabelled `defeat`. Checks that settled it:
- **Positive control on `result`:** the known victory `run_1785422399_74522` reads `'victory'`, and
  282 recent summaries split **138 defeat / 144 victory** — the field varies and can return the positive.
- **No fixed cut-point:** the deaths land at different points *inside* wave 16 (timer remaining
  4.62 / 10.33 / 0.40 s) at different HP. A truncation would cut at a fixed instant.
- **The gap to `run_end` is 96-119 ms**, inside the documented 83-200 ms window where the killing blow
  is never captured (0/20 in the D5 baseline). At wave 16 a burst across 2-4 unlogged ticks takes 18-27 HP.
- Attempt 4 then ended at wave **12**, which a truncation at 16 could not produce.

## 12. CAMPAIGN STATUS — 1 of 3 targets acquired, 24-attempt cap NOT reached

| target | character | attempts | result |
|---|---|---|---|
| `item_anvil` | Arms Dealer | 8/8 formal, 0 wins | ✅ **ACQUIRED** — but by an UNSUPERVISED run, not a formal attempt |
| `item_explosive_shells` | Artificer | 8/8, 0 wins | ❌ not acquired |
| `item_giant_belt` | Jack | 8/8, 0 wins | ❌ not acquired |

**24/24 attempts spent. The cap is exhausted and the campaign ENDS here per §5.**
S-tier pool went **8 → 9**, not the projected 8 → 11.

**0 wins in 24 formal attempts across three characters** against well_rounded's 0.395 D0 baseline.
Under a common 0.395 rate that has probability **0.605^24 ≈ 3.6e-6**. The characters differ, so treat
the pooled figure as indicative rather than exact — but the conclusion is not in doubt: **the agent is
tuned for `well_rounded` and plays other characters far worse.** §5 anticipated precisely this and
forbade extending the cap on a disappointing rate; that bar is honoured.

**Not a null about the premise.** "Win a D0 run with character X unlocks item Y" is CONFIRMED
(`item_anvil`). What failed is the agent's ability to win with characters it was not tuned for.

## 13. AMENDMENT — reopening on WINNABILITY, target `character_mutant` (2026-07-31, pre-collection)

### 13a. The campaign optimised the wrong axis
§2 picked its three targets by **ITEM VALUE** (all S-tier). Measured, the binding constraint was
**win probability**, which was never estimated for any character but `well_rounded`:

| character | full-run record | rate |
|---|---|---|
| `well_rounded` | **103 / 268** | **0.384** |
| `arms_dealer` | 1 / 15 | 0.067 |
| `artificer` | 0 / 8 | 0.000 |
| `jack` | 0 / 8 | 0.000 |

⛔ **CORRECTION to §10b's "0 wins in 24".** That counted FORMAL attempts only and excluded the real
Arms Dealer victory. The honest figure is **1 win in 31 non-well_rounded runs (0.032)**. The
conclusion is unchanged — P(<=1 win in 31 | rate 0.384) ≈ **8.7e-6** — but "0 wins" overstated it.
⚠️ A **0.669** figure for `well_rounded` computed over all 1,909 archived runs is **fixture-contaminated**
(fixtures start at wave 17/19 and win easily). Split by first captured wave, full runs give **0.384**,
matching the recorded 0.395. **Always split full-run vs fixture before quoting a win rate.**

### 13b. New target, selected on structural compatibility
**`character_mutant` → `item_octopus`** (A-tier on the scorer's own RogueRanker allowlist, so not
hard-vetoed). Chosen because it is the only unlocked character with an incomplete challenge whose
**entire effect set is `xp_gain +200` / `items_price +50`** — no stat-gain rewrite, no HP drain, no
weapon-slot cap, no enemy-scaling change, no weapon-class restriction. Its 13-weapon starting pool
contains **`weapon_smg`** (verified in source, `ExtResource(14)`), so with the existing
`weapon_prefixes = ["weapon_smg","weapon_shredder","weapon_knife","weapon_"]` it opens in the agent's
known-good weapon. **No config change needed; `weapon_smg` is already first.**

### 13c. ⚠️ PRE-REGISTERED SCOPE — what a null here does and does NOT mean
`character_mutant`'s profile is **BARE**: `wanted_tags: ["xp_gain"]` and nothing else, so
`allow_melee` takes its **default `true`**. `character_well_rounded` is the ONLY profile of 61 carrying
the tuned spec, and `_apply_experiments()` (`build_profiles.gd:43`, gated on
`BotConfig.EXPERIMENT_ANY_GUNS` = true) additionally gives it at runtime
`allow_melee=false`, `allowed_weapon_sets=["set_gun"]`, `preferred_sets=["set_gun"]`.
**All 1,275 wins ran that spec. No other character inherits any of it.**

**Therefore this attempt tests "smg opening + DEFAULT profile", NOT "the agent's well_rounded game".**
Declared in advance: **a 0/8 here does NOT distinguish** (a) character choice cannot help from
(b) the *profile tuning* is the actual carrier of the win rate. If this returns null, the matched
follow-up is **porting `well_rounded`'s profile spec to the target character** — a mod change needing
its own pre-registration, version bump and deploy. Do not read a null as closing the winnability line.

### 13d. Rules
Unchanged from §4 (validity) and §5 (stopping): **8 attempts, D0, stop on first victory**, build frozen
at **`0.2.63-wp2-capture`**, config-only, era stamp recorded per run. Technical failures recorded and
never excluded on outcome. Smoke gate must verify **behaviourally** that `run_start.weapon` is an smg
before the campaign is trusted.
**Explicit SKIP list stands:** 18 characters whose reward is OFF the scorer allowlist (hard-vetoed at
`-1e9` from wave 11) — including `renegade`/`item_fairy` — and the structurally gun-hostile set
(`one_arm` 1 weapon slot, `gladiator`/`engineer` no ranged pool, `pacifist` hand-only, `golem` no_heal).

## 14. RESULTS — Mutant: ✅ **VICTORY, `item_octopus` ACQUIRED** (2026-07-31)

**4 attempts collected, 4/4 VALID, 0 technical failures, 1 VICTORY.** `--stop-on-win` fired at
attempt 4; the remaining 4 of the 8-attempt budget were not spent.

Terminal waves, collection order: **[17, 16, 19, 20-VICTORY]**. All four opened on **`weapon_smg_1`**
(RANGED), `character_ok` true, `danger_ok` true, `requested_danger` 0,
`mod_version == 0.2.63-wp2-capture`.

**Unlock verified in the save**, djb2, with five positive controls passing (`item_potato`,
`item_padding`, `item_night_goggles`, `item_lens`, `chal_arms_dealer` — so the test could return the
positive): **`item_octopus` = True**, **`chal_mutant` = True**.
✅ **The era stamp MOVED — items `174 → 175`, challenges `51 → 53`** — independent confirmation the
unlock landed rather than the challenge merely firing. ⚠️ **A NEW MEASUREMENT ERA STARTS HERE.** Runs
collected from now sample a different shop pool; do not pool them with the 174/46 era (which covers
the entire Artificer and Jack campaigns and the D5 baseline's successor era).

### 14a. ⚠️ THE SELECTION STRATEGY IS NOT PROVEN — the acquisition is
Selecting on **winnability** rather than item value produced **1 win in 4** where item-value selection
produced **0 in 24**. Tempting, and it is the reason the campaign was reopened — but measured honestly:

**Fisher one-sided, 1/4 vs 0/24: p = 0.1429.** That is just `4/28` — the chance the single win lands
in the small arm by luck. **NOT significant.** The arms are also sequential, not randomised, and the
switch was made after observing the failures.

**What IS established: the objective was achieved** — an A-tier S-list item unlocked from a formal,
supervised, pre-registered attempt, the campaign's first. **What is NOT established: that structural
similarity to `well_rounded` predicts winnability.** That needs a fresh, larger sample
(`fisherman` is the pre-declared next candidate) before it is quoted as a finding.

⚠️ Terminal-wave floors are **less separated than they look**: mutant [17,16,19,20] vs Jack
[16,16,16,12,16,17,17,17] — Jack also reached ≥16 in 7 of 8. **The difference is conversion in the
TAIL (19-20), not the floor.** n=4 vs n=8; do not over-read it.

### 14b. Campaign standing after Mutant
| target | character | attempts | outcome |
|---|---|---|---|
| `item_anvil` | Arms Dealer | 8 formal | ✅ acquired (by an unsupervised run) |
| `item_explosive_shells` | Artificer | 8 | ❌ |
| `item_giant_belt` | Jack | 8 | ❌ |
| **`item_octopus`** | **Mutant** | **4** | ✅ **ACQUIRED — first formal-attempt win** |

**2 items acquired. Non-well_rounded record now 2 wins / 35 runs.**
Next pre-declared candidate on the winnability shortlist: **`fisherman` → `item_lure`** (A-tier;
`+20 harvesting`, which is `well_rounded`'s own highest-weighted utility override at 2.8).

## 15. RESULTS — Fisherman: ❌ 0/8, and it DISCONFIRMS the selection rule (2026-07-31)

**8 attempts, 8/8 VALID, 0 technical failures, 0 VICTORIES.** `item_lure` NOT unlocked,
`chal_fisherman` not completed (verified djb2, positive controls passing).
Terminal waves: **[10, 17, 11, 17, 11, 12, 10, 13]**, median **11.5**. All eight opened on
**`weapon_smg_1`**, era stable at the new post-mutant stamp **175 / 46, hash `1464012540`**.

### 15a. This is a genuine disconfirmation, not a wobble
`fisherman` was ranked **#2** by the same structural-compatibility reasoning that ranked `mutant` #1,
opened on the **same weapon**, and had the **same sparse-profile caveat**. It produced a median
terminal wave of **11.5** against mutant's **[17, 16, 19, 20]**.

**So "has `weapon_smg` + no gross structural penalty + sparse profile" is NOT sufficient**, and the
ranking's predictive value is now actively in doubt rather than merely unproven. Combined with §14a's
Fisher p = 0.1429, the honest position is:

> **Mutant's win may simply have been a lucky draw.** 2 wins in 35 non-well_rounded runs is consistent
> with a low-but-nonzero rate shared across characters, with no selection effect at all.

**Do NOT carry "select on winnability" forward as an established method.** It has one success and one
clean failure at n=1 character each.

### 15b. The competing explanation, being MEASURED not asserted
`fisherman` carries **`enemy_gold_drops −50`**, which the shortlist called "mild". D5 prereg §7b
records economy as a first-class phenotype on operator domain knowledge (*"you have to pick up as much
currency as possible"*). A 50% cut to drops is a plausible binding handicap that the ranking
under-weighted.
⚠️ **This is currently a JUST-SO STORY and is being tested directly** (materials and items-bought per
wave, mutant vs fisherman, **at matched waves** — a run-total would conflate rate with duration since
fisherman died earlier). **If the economy gap is small or absent, the story dies and the ranking is
simply wrong.** Recorded here before the result is known.
⚠️ `materials_spent` is a DEAD field (never accumulated); the measurement must use a field that is
actually written, and "materials left at wave end" must be read at the **last capture with
`remaining_sec > 0`** — the sweep happens inside the post-timer capture window and reading past it
produced a 1-vs-28 error twice.

### 15c. Standing record
| target | character | attempts | outcome |
|---|---|---|---|
| `item_anvil` | Arms Dealer | 8 formal | ✅ (unsupervised run) |
| `item_explosive_shells` | Artificer | 8 | ❌ |
| `item_giant_belt` | Jack | 8 | ❌ |
| `item_octopus` | **Mutant** | 4 | ✅ **first formal win** |
| `item_lure` | Fisherman | 8 | ❌ |

**2 items acquired; non-well_rounded record 2 wins / 43 runs (0.047)** vs `well_rounded` full-run
**0.384**. **Do not start another character campaign on the strength of the ranking alone** — the next
one needs either the economy result to come back supportive, or the profile-port test from §13c.

## 16. The economy explanation is REFUTED; `xp_gain` survives (2026-07-31)

§15b recorded `enemy_gold_drops −50` as a just-so story pending measurement. **Measured: NOT SUPPORTED.**

The gold penalty is real and precise — materials/wave at ratio **~0.50, no trend**, waves 1-10
completely separated (**p = 0.002-0.004**), present at **wave 1** with build strength identical
(0.75 vs 0.75). **It does not bind.** `mutant`'s **`items_price +50` applies to weapons too — median
price ratio 1.540** across shared offered ids (verified in the primary session). Net of it,
**fisherman's purchasing power is at parity or better, waves 4-16**, and **buy counts are equal**.

⛔ **The shortlist mis-scored the economy in BOTH directions** — fisherman's drop penalty counted
without netting its cheaper shop; mutant's `items_price +50` called "no structural penalty" when it is
a 1.5x price rise. **Net an economy effect against everything else that scales prices before scoring it.**

**Surviving hypothesis: `xp_gain +200` → level-up rate.** Deduped, wave derived from the nearest
preceding capture: **level-ups by wave 10, mutant [20,20,22,22] vs fisherman [10,10,10,11,11,11,11,12]
— COMPLETE SEPARATION**, a clean 2x.
⚠️ **Ruled out more confidently than ruled in.** Purchasing-power parity is a direct measurement; the
xp attribution is a correlation against a **stat-contaminated** build-strength proxy. **The two
characters differ on ≥3 large axes simultaneously and this design cannot isolate any one of them.**

### 16a. Pre-declared next step — NOT to be run on this evidence alone
Two candidates, in preference order:
1. **Port `well_rounded`'s tuned profile spec** to a target character (§13c) — 14 `utility_overrides`,
   6 `tag_bonus_overrides`, `dodge_caution 1.55`, `gold_reserve 40`. **All 1,275 wins ran that one
   spec**; no other character inherits any of it. Needs its own prereg, version bump and deploy.
2. **Test the refined criterion** — prefer characters with XP/level-up bonuses — on a fresh candidate.
   This is a HYPOTHESIS from a 3-axis-confounded comparison, not a finding.

⛔ **Do not start another character campaign on the structural ranking alone.** It has one success
(`mutant`), one clean failure (`fisherman`), and a demonstrated scoring error on economy effects.

## 17. PROFILE-PORT EXPERIMENT — `0.2.64`, target `character_jack` (recorded PRE-collection)

### 17a. Hypothesis
`character_well_rounded` is the **only profile of 61** carrying the tuned spec (14 `utility_overrides`,
6 `tag_bonus_overrides`, `dodge_caution 1.55`, `gold_reserve 40`, `min_buy_score 5`,
`dps_gain_weight 1.45`, `ehp_value_multiplier 1.45`), and **all ~1,275 recorded wins ran it.**
Measured this session: **2 wins / 43 non-well_rounded runs (0.047)** vs well_rounded's **0.384** on
full runs. **H: the PROFILE, not the character, carries the win rate.**

### 17b. The change (`0.2.64-wp2-capture`, deployed)
`BotConfig.EXPERIMENT_PORT_WR_PROFILE_TO` (**"" = inert**, set to `"character_jack"`) +
`build_profiles._port_wr_profile()`, called at the end of `_apply_experiments()` so it copies the
**runtime** well_rounded (post-`EXPERIMENT_ANY_GUNS`), not the raw spec.
⛔ **`tgt.name` is set to `"well_rounded"` DELIBERATELY and is load-bearing, not cosmetic.** Three
scoring paths gate on `str(profile.name) == "well_rounded"` — `combat_model.gd:206` (late-shop),
`shop_strategy.gd:579`, `shop_strategy.gd:766`. **Copying the values while leaving `name = "jack"`
would have left the port PARTIALLY INERT** — the `_build_desire` failure mode, where a change looks
applied and does nothing. Arm certification is unaffected: `requested_character` /
`character_observed` still read `character_jack`.
✅ Build gate passed: **850 tests pass**, version bumped at all 4 code sites + 3 pin test files in one
edit, and installed-vs-repo verified **21/21 byte-identical** at `0.2.64`.

### 17c. ⚠️ THE PORT SETS `allow_melee = false` — the weapon prefix MUST change with it
Jack's pool has **no smg**; the previous list resolved to `weapon_knife` (**MELEE**). Porting
`allow_melee=false` without changing the prefix would hand Jack a starting weapon its own shop policy
scores **`-1e9`** — un-upgradeable and the standing sell victim — i.e. **an exact re-run of the
Artificer plank defect diagnosed in §8c today.** Prefix set to
`["weapon_revolver","weapon_pistol","weapon_laser_gun","weapon_smg","weapon_"]`; revolver/pistol/
laser_gun are Jack's `set_gun` weapons (read from source `type`/`sets`). Bare `"weapon_"` stays last
as the anti-stall fallback. **Must be verified BEHAVIOURALLY via `run_start.weapon`.**

### 17d. Pre-declared readbacks — a self-report proves delivery, never correctness
1. **Arm**: `character_ok` true, `requested == observed == character_jack`, `danger_ok`,
   `mod_version == 0.2.64-wp2-capture`.
2. **Weapon**: `run_start.weapon` is a **gun**, not `weapon_knife_1`.
3. **PORT EFFECT — the behavioural one that matters**: with `allow_melee=false` the shop must buy
   **ZERO melee weapons**. Jack's 8 pre-port runs are the **matched control** (same character, same
   danger, bare profile with `allow_melee` defaulting **true**). Positive control for the instrument:
   `arms_dealer` bought melee on **463/947 = 48.9%** of weapon buys while `well_rounded`/`artificer`
   (`allow_melee=false`) bought **0/665** and **0/15**. **If Jack's pre-port runs show 0 melee buys
   too, this readback is VACUOUS and proves nothing — check the control before believing the result.**

### 17e. Rules and honest scope
**8 attempts, D0, stop on first victory**, build frozen at `0.2.64`, era recorded per run
(**expect the post-mutant 175/46 stamp**). §4 validity and §5 stopping unchanged. Technical failures
recorded, never excluded on outcome.
⚠️ **This is NOT a clean experiment.** Jack's 8 pre-port runs are era **174**; post-port runs are era
**175** (mutant's unlock added one item) — a small but real confound. The arms are **sequential, not
randomised**. A win would be an acquisition, not proof; **8 v 8 cannot resolve a difference smaller
than roughly a doubling of the win rate.**
⚠️ **Jack is also a hard case on its own merits**: `enemy_health +250`, `enemy_damage +50`,
`number_of_enemies −75`, and its pre-port failure was diagnosed as a **smooth ramp** — 2-3 hits from
death since wave 8 — **not a localised defect the profile obviously fixes.** A null here does not
refute the profile-port hypothesis generally; it would argue for retrying the port on a
structurally easier character.

## 18. RESULTS — Jack PROFILE-PORT: ✅ **VICTORY, `item_giant_belt` (S-tier) ACQUIRED**

**4 attempts, 4/4 valid, 0 technical failures, 1 VICTORY at wave 20**, `--stop-on-win` at attempt 4.
Terminal waves **[19, 17, 16, 20-VICTORY]**, all opening on **`weapon_revolver_1`**, all
`mod_version == 0.2.64-wp2-capture`, era **176/46** post-unlock.
Verified djb2 with five positive controls: **`item_giant_belt` True, `chal_jack` True**; era moved
**175 → 176**, challenges **53 → 54**.

### 18a. ✅ THE PORT DEMONSTRABLY ENGAGED — behavioural readback, with its control
`allow_melee=false` ⇒ zero melee weapon purchases.

| arm | weapon buys | melee | share |
|---|---|---|---|
| Jack **pre-port** (bare profile, `allow_melee` default true) | 253 | 135 | **0.534** |
| Jack **post-port** (ported profile) | 31+ | **0** | **0.000** |

**The pre-port arm is what makes the zero meaningful** — the instrument demonstrably registers melee
buys for this exact character. Not a self-report; a signature the other arm produced 135 times.

### 18b. ⚠️ THE EFFECT IS SUGGESTIVE, NOT SIGNIFICANT — stated before it gets quoted
Jack pre-port **[16,16,16,12,16,17,17,17]** (max 17) vs post-port **[19,17,16,20]**:

| test | result |
|---|---|
| exact permutation on terminal-wave sum, one-sided | **p = 0.0525** |
| post-port runs exceeding the entire pre-port max | **2 / 4** (P(both top-2 in the 4-arm) = 0.0909) |
| binary win 0/8 vs 1/4, Fisher one-sided | p = 0.3333 |

**p = 0.0525 is NOT below 0.05.** The arms are **sequential, not randomised**; pre-port is era **174**
and post-port era **175**; and §17e pre-declared that 8 v 8 cannot resolve less than roughly a
doubling. **The acquisition is established. The profile-port hypothesis is STRENGTHENED, not proven.**
The terminal-wave endpoint is the honest one to quote — the binary win discards most of the data.

### 18c. Campaign standing — 3 of 5 targets, 2 of 3 original S-tier
| target | tier | character | attempts | outcome |
|---|---|---|---|---|
| `item_anvil` | **S** | Arms Dealer | 8 | ✅ (unsupervised run) |
| `item_octopus` | A | Mutant | 4 | ✅ |
| **`item_giant_belt`** | **S** | **Jack (ported)** | **4** | ✅ **profile-port** |
| `item_explosive_shells` | **S** | Artificer | 8 | ❌ — bare profile |
| `item_lure` | A | Fisherman | 8 | ❌ — bare profile |

**Both remaining failures ran the BARE profile.** `artificer` is the last original S-tier target and
already carries `allow_melee:false`; its one ranged starting weapon is **`weapon_shredder_1`**, so the
port is directly applicable. **Next: port to `character_artificer`.**

## 19. RESULTS — Artificer PROFILE-PORT: ✅ **VICTORY, `item_explosive_shells` (S) ACQUIRED**
## ⭐ THE ORIGINAL CAMPAIGN GOAL IS COMPLETE — ALL THREE S-TIER TARGETS

**5 attempts, 5/5 valid, 0 technical failures, 1 VICTORY at wave 20**, `--stop-on-win` at attempt 5,
after **0/8 with the bare profile**. Terminal waves **[10, 10, 10, 13, 20-VICTORY]**, all opening on
**`weapon_shredder_1`** under `0.2.65-wp2-capture`. `item_explosive_shells` + `chal_artificer` verified
djb2 with positive controls; era **176 → 177**, challenges **54 → 55**.

| target | tier | character | outcome |
|---|---|---|---|
| `item_anvil` | **S** | Arms Dealer | ✅ |
| `item_explosive_shells` | **S** | **Artificer (PORTED)** | ✅ |
| `item_giant_belt` | **S** | **Jack (PORTED)** | ✅ |
| `item_octopus` | A | Mutant | ✅ (bonus) |
| `item_lure` | A | Fisherman | ❌ (bare profile) |

**S-tier pool 8 → 11 (+38%)** — exactly the §2 projection, reached by a route §2 did not anticipate.

### 19a. Port engaged — behavioural, with a control chosen because the obvious one was vacuous
The melee readback is **vacuous for Artificer** (already `allow_melee:false`, 0/15 pre-port).
Replacement signature with a verified non-zero control: **non-`set_gun` weapon buys, pre-port
20/137 = 14.6% → post-port 0/16 = 0.000.**
✅ Also checked the wave-10 cluster was genuine, not a truncation: last-capture HP **2/37, 6/25, 9/27**
(dying, not healthy), **different points inside the wave** (timer remaining 11.95 / 15.65 / 33.08 s),
`run_end` gaps 58-73 ms, and attempt 4 ended at wave 13. A fixed cut-point would show none of that.

### 19b. Combined evidence — and exactly how far it goes
| test | p |
|---|---|
| binary, pooled pre-port **0/16** vs post-port **2/9**, Fisher one-sided | 0.1200 |
| Jack terminal wave, exact permutation | 0.0525 |
| Artificer terminal wave, exact permutation | 0.1290 |
| **combined (Fisher's method, 2 independent tests)** | **0.0406** |

⚠️ **The terminal-wave permutation endpoint was introduced AFTER seeing Jack's data**, so Jack's
0.0525 is partly post-hoc and the combined figure inherits that. **Artificer's 0.1290 is a clean
out-of-sample application** of the same endpoint. Both comparisons are **sequential, not randomised**,
and span an era change (174 → 175/176).
⇒ **Honest verdict: the profile-port hypothesis is now supported by TWO independent replications with
a confirmed mechanism in each, but it is not established at conventional significance.** A clean test
would pre-register the endpoint and randomise arm order on a third character.
⚠️ Artificer's port did **not** raise its floor (post [10,10,10,13,20] vs pre [7,5,9,9,7,20,11,7]) — it
converted the tail. Same pattern as mutant vs Jack: **the effect is in CONVERSION, not the floor.**

### 19c. What this reframes
**Both remaining/earlier failures ran the BARE profile.** The 0/24 stretch that looked like "the agent
cannot play other characters" is better explained as **"no other character has ever had a tuned
profile"** — `character_well_rounded` is the only one of 61 that does, and all ~1,275 wins ran it.
▶ Next, if the line is continued: **port to `character_fisherman`** (the one bare-profile failure left,
`item_lure` A-tier) as a third replication with a **pre-registered endpoint and randomised arm order**.

## 20. PRE-REGISTRATION — Fisherman profile-port, THIRD replication (2026-07-31)
### Recorded BEFORE the build is changed and BEFORE any attempt is collected.

### 20a. ⛔ FIRST, A DEFECT IN §18b/§19b's OWN STATISTICS: `--stop-on-win` IS OPTIONAL STOPPING
Both prior port arms ran `--stop-on-win`, so each **terminated precisely on a victory** — the largest
possible terminal wave. Jack's post-port arm is [19, 17, 16, **20**] and stopped *because* of the 20;
Artificer's [10, 10, 10, 13, **20**] likewise. **The treatment arm is censored on a high value, which
inflates the permutation statistic.** The reported **Jack p = 0.0525 and Artificer p = 0.1290 are
therefore OPTIMISTIC**, and the combined **0.0406 inherits it**. The control arms (0/8 each) ran to
their cap and are unaffected, so the bias is one-directional and favours my own hypothesis.

**This does not touch the acquisitions** — the items unlocked and are verified in the save. It touches
only the strength-of-evidence claim. §19b's "supported, not established" verdict stands; if anything it
was more generous than the design earned.

**Fix, applied here:** this campaign runs **all 8 attempts regardless of a victory — NO
`--stop-on-win`.** The reward is granted by the first win whether or not collection continues, so the
only cost is ~1 h of machine time, and it buys an **uncensored** treatment arm.

### 20b. Pre-specified PRIMARY endpoint — fixed now, before any data
**Terminal wave, exact permutation test on the arm sum, one-sided (post-port ≥ pre-port), α = 0.05.**
- **Control arm, ALREADY COLLECTED AND FROZEN:** fisherman bare-profile, n=8, terminal waves
  **[10, 17, 11, 17, 11, 12, 10, 13]** (era 175, `0.2.63`).
- **Treatment arm:** fisherman ported, **n=8, run to completion**, `0.2.66`.
- **SECONDARY (reported, not decisive):** binary victory count; and the acquisition of `item_lure`.
- **No other endpoint will be substituted after seeing the data.** This is the specific weakness §19b
  named — Jack's endpoint was chosen after Jack's data.

### 20c. Pre-declared confounds — stated because they CANNOT be fixed
- **Arm order cannot be randomised.** The control arm already exists; §5 forbids discarding collected
  attempts, and re-collecting them would select on outcome. Sequential arms are therefore inherent.
- **Era differs**: control era **175/46**, treatment era **177/46** (three unlocks landed between).
  The pool the shop samples from is not identical. **This alone prevents a clean causal claim** and is
  the reason a positive result here is still only a third replication, not proof.
- n=8 v 8 cannot resolve less than roughly a doubling (§17e).

### 20d. Port-engagement readback — control verified NON-VACUOUS in advance
The port sets `allow_melee=false`. Fisherman's bare profile leaves `allow_melee` at its default
**true**, and it **did** buy melee: **20/150 = 13.3%** of weapon purchases
(jousting_lance 4, fist 3, circular_saw 3, rock 3, knife 2, spear 2, stick 2, torch 1).
**Expected post-port: 0.** Unlike Artificer, the melee signature is usable here — checked first.

### 20e. Arm and validity
`character_fisherman`, D0, build **`0.2.66-wp2-capture`** frozen for the campaign, era recorded per run.
`weapon_prefixes = ["weapon_smg", "weapon_"]` — fisherman's pool contains `weapon_smg` (a `set_gun`
weapon), so it opens on a gun, as the port's `allow_melee=false` requires. §4 validity unchanged.
**Smoke must verify BEHAVIOURALLY** that `run_start.weapon` is an smg before the campaign is trusted.

## 21. RESULTS — Fisherman profile-port: ❌ **NULL. The pre-registered test FAILS TO REJECT.**

**8/8 attempts, 8/8 valid, 0 technical failures, 0 VICTORIES.** `item_lure` NOT unlocked,
`chal_fisherman` not completed (djb2, positive controls passing). All eight opened on `weapon_smg_1`
under `0.2.66-wp2-capture`, era stable **177/46**.

**§20b PRIMARY, run exactly as pre-registered — no endpoint substituted:**
- control (bare, frozen) **[10, 17, 11, 17, 11, 12, 10, 13]**, sum 101, median 12
- treatment (ported) **[9, 16, 16, 10, 16, 17, 10, 13]**, sum 107, median 16
- **exact permutation, one-sided: p = 4341/12870 = 0.3373** → **FAIL TO REJECT at α=0.05.**
- Secondary, binary victories: **0/8 ported vs 0/8 bare.**

✅ The port **did** engage — melee weapon buys **20/150 = 13.3% bare → 0/12+ ported**, control verified
non-vacuous *before* collection. **Engagement is not benefit.** This is the 19th-instance pattern
(Piggy Bank): a mechanism that is real, dosed, controlled and confirmed live, and still changes nothing.

### 21a. ⛔ THIS SUBSTANTIALLY WEAKENS THE PROFILE-PORT CLAIM
The only **uncensored, pre-registered** test of the hypothesis is this one, and it is **null**.

| arm | ported | stopping rule | status |
|---|---|---|---|
| Jack | 1/4 | `--stop-on-win`, censored ON the victory | **OPTIMISTIC** |
| Artificer | 1/5 | `--stop-on-win`, censored ON the victory | **OPTIMISTIC** |
| **Fisherman** | **0/8** | ran to cap, no stop-on-win | **CLEAN — and NULL** |

Pooled: bare **0/24** vs ported **2/17**, Fisher one-sided **p = 0.1659** — not significant either.

**Honest verdict, replacing §19b's:** the profile port is **NOT established as the cause** of the two
wins. Both wins came from arms whose stopping rule was correlated with the outcome; the one arm
designed to be unbiased produced nothing. A low base rate shared across characters (2 wins in 17
ported runs ≈ 0.12, against well_rounded's 0.384) remains fully consistent with the data.

⚠️ **What IS still established, and is not in doubt:** the three S-tier items and `item_octopus` are
unlocked, verified in the save by djb2 with positive controls, and the era stamp moved on each. **The
acquisitions are real regardless of why the wins happened.**

### 21b. What would actually settle it
n=8 per arm cannot resolve less than ~a doubling (§17e), and three characters at that size is
underpowered for an effect this small. Either:
1. **A much larger single-character comparison** (≥32/arm, no stop-on-win, one character), or
2. **Drop the causal question** and treat the port as an unproven convenience, judging future
   campaigns only on whether they acquire the item.
⛔ **Do NOT run a fourth character expecting a different answer** — that is optional stopping at the
level of the experiment.

## 22. Cyborg → `item_improved_tools` (A) — ACQUISITION ONLY (2026-07-31, pre-collection)

### 22a. This is §1's acquisition task again, NOT a hypothesis test
No arm comparison, no endpoint, no p-value. The deliverable is one unlocked item.
⛔ **Therefore `--stop-on-win` IS used, and these runs are PERMANENTLY DISQUALIFIED from serving as a
treatment arm in any later comparison** — the stopping rule is correlated with the outcome
(measurement-discipline 22nd). Recorded now so the trap cannot recur by someone reusing this data.

### 22b. Target selection, re-derived from the CURRENT save (era 177)
43 of 88 challenges complete; **34 incomplete challenges have their character already unlocked.**
Rewards ranked by the scorer's own tables (`ROGUERANKER_ITEM_TIERS` 68 + `WIKI_USEFUL_ITEM_TIERS` 98):
A-tier reachable = `focus`(one_arm), `lure`(fisherman), `robot_arm`(engineer), `spider`(gladiator),
`stone_skin`(golem), `big_arms`(generalist), **`improved_tools`(cyborg)**, `tentacle`(lich).

Excluded on **mechanical** grounds — impossibilities for a gun policy, not the disconfirmed winnability
ranking: `one_arm` (`weapon_slot −5` ⇒ ONE weapon slot), `engineer` (0 ranged in pool),
`gladiator` (`no_ranged_weapons`, 0/12 ranged). `fisherman` is exhausted (16 attempts, 0 wins).
⛔ 6 rewards are **OFF the scorer allowlist** and hard-vetoed `-1e9` from wave 11
(`bowler_hat`, `compass`, **`fairy`**, `gnome`, `rip_and_tear`, `spicy_sauce`) — worth less than nothing.
⛔ Weapon rewards (12 characters) are structurally off-list — the allowlist covers items only.

**Chosen: `character_cyborg`.** Its profile ALREADY carries `allow_melee: false` and
`preferred_sets: ["set_gun"]` — the closest of any candidate to `well_rounded`'s runtime config,
**without needing the unproven profile port**. Its pool contains `weapon_smg`, so it opens on a gun.
⚠️ Known risk, stated up front: cyborg carries **`effect_reduce_stat_gains`** entries (−75/−100/−100
with a +250) that rewrite stat scaling and may break the shop's linear valuation. **No prediction is
made about the win rate** — the structural ranking was disconfirmed on fisherman and is not being
relied on again.

### 22c. Arm
`character_cyborg`, D0, build **frozen at `0.2.66-wp2-capture`** (which ports to `fisherman`, so cyborg
uses its OWN profile — **config-only, no deploy**). `weapon_prefixes = ["weapon_smg", "weapon_"]`.
**8 attempts, stop on first victory.** §4 validity unchanged. Smoke must verify BEHAVIOURALLY that
`run_start.weapon` is an smg.

## 23. RESULTS — Cyborg: ❌ 0/8, `item_improved_tools` NOT acquired (2026-07-31)

**8/8 attempts, 8/8 valid, 0 technical failures, 0 victories.** Terminal waves
**[17, 17, 16, 13, 11, 19, 14, 13]** — a deep floor (6 of 8 reached ≥13, one hit 19) with no
conversion. All eight opened on `weapon_smg_1`, build frozen `0.2.66`, era stable **177/46**.
`item_improved_tools` and `chal_cyborg` verified still locked (djb2, positive controls passing).
⛔ Per §22a these runs are **DISQUALIFIED from any later comparison** (`--stop-on-win` armed).

### 23a. The cumulative record is the durable result of this session
| arm | wins/runs |
|---|---|
| arms_dealer bare | 0/8 |
| artificer bare / **PORTED** | 0/8 / **1/5** |
| jack bare / **PORTED** | 0/8 / **1/4** |
| mutant bare | 1/4 |
| fisherman bare / **PORTED** | 0/8 / **0/8** |
| cyborg bare | 0/8 |
| **TOTAL** | **3 / 61 = 0.049** |

**Non-`well_rounded` characters win 4.9% of D0 full runs; `well_rounded` wins 38.4% (103/268).**
That ~8x gap is measured over 61 formal attempts across 6 characters and is the most solid quantitative
finding here — far better evidenced than any explanation for it.

**The explanation remains open.** The profile port was the leading candidate and its only unbiased test
was null (§21). Both port "successes" sit in arms censored on their own victory. 3 wins in 61 runs is
consistent with a single low rate shared across characters, with neither character choice nor the port
doing measurable work.

### 23b. Stop expanding; the acquisition branch is spent at this power
Six characters, 61 attempts, 4 items acquired (all three original S-tier + `item_octopus`). Every
remaining A-tier reward is behind a character that is either mechanically gun-hostile, already
exhausted, or (cyborg, generalist, golem, lich) carries stat-rewrites of the kind just measured to be
worth 0/8. **Another 8-attempt campaign has ~1 - (1-0.049)^8 ≈ 33% chance of acquiring anything**,
and no selection rule survives to pick the target better than chance.

⛔ **Do not queue further 8-attempt character campaigns as the default.** The two honest options:
1. **Fix capability** — the 8x gap is the real lever. Any change that moves the non-`well_rounded` rate
   toward 0.384 unlocks the whole remaining branch at once. That needs a properly powered test
   (**≥32/arm on ONE character**, no stop-on-win), not more acquisition attempts.
2. **Accept the surface as-is.** 4 of the highest-value items are acquired; S-tier pool 8 → 11 (+38%),
   which was the campaign's stated goal in §2.

## 24. PRE-REGISTRATION — properly powered test of the profile port, on JACK
### Recorded BEFORE any build change and BEFORE any attempt. This is §23b option 1.

### 24a. Why Jack, and why this design is cleaner than §18/§21
**`item_giant_belt` is ALREADY ACQUIRED**, so no unlock can fire during this experiment ⇒ **the shop-pool
era stays FROZEN at 177/46 for all 64 runs.** That removes the era confound that weakened every earlier
port comparison (174 vs 175/176). Jack also has the largest observed port effect, so if the effect is
real this is where it shows.

**This is NOT another acquisition campaign** — §23b bars those. Nothing is being acquired; this is the
capability question, which §23b names as the lever worth paying for.

### 24b. Design — fixed now
- **n = 32 per arm, 64 runs total.** Honours §21b/§23b's own stated bar of ≥32/arm. (~16 h at ~15 min
  per Jack run.) n=8 could not resolve less than ~a doubling; that is why §21 was inconclusive.
- **NO `--stop-on-win` in either arm.** Both run to their cap. The §20a optional-stopping defect must
  not recur.
- **BLOCKED and RANDOMISED**: four blocks of 16, alternating arms, **first arm chosen by
  `secrets.randbelow` = PORTED** → order **PORTED, BARE, PORTED, BARE**. Blocking controls for drift
  (machine load, time of day) that a single sequential switch cannot. **This is the randomisation §20c
  said was impossible when the control arm already existed — here BOTH arms are fresh, so it is
  possible and is being done.**
- **Two builds**, differing in **exactly two lines**: `MOD_VERSION` and
  `EXPERIMENT_PORT_WR_PROFILE_TO`. Control = `""` (inert). Treatment = `"character_jack"`. The content
  diff between the two zips will be verified to be exactly those two lines — the only difference
  between arms IS the treatment.

### 24c. PRIMARY endpoint — fixed before data, no substitution
**Terminal wave, exact permutation on the arm sum (or Monte-Carlo at ≥200k draws if the exact
enumeration is infeasible at n=32), one-sided (ported ≥ bare), α = 0.05.**
**SECONDARY, reported not decisive:** binary victory count; median terminal wave.
⛔ **No other endpoint will be substituted after seeing the data** — that was the §18b failure.

#### 24c-i. Analysis code written BLIND — provenance
`scripts/wp2_jack_power_analysis.py` was written **2026-08-01, while block A2 stood at 8/16 and block
B2 had not been started**, i.e. with half the design uncollected. The endpoint, the statistic, the
direction and the α are fixed in that file.
- The exact-enumeration escape hatch above is **not needed**: the permutation null is computed
  **exactly** by dynamic programming over (subset size, subset sum) — terminal waves are small
  integers, so all **C(64,32) = 1,832,624,140,942,590,534** splits are *counted* rather than
  enumerated. No Monte-Carlo approximation is used.
- The statistics are validated by `--self-test` before they decide anything: DP counts vs brute-force
  enumeration; permutation p vs full enumeration; **Fisher reproduces the canonical tea table
  17/70 = 0.242857** (the closed form that catches a wrong-tail sum, cf. §11c); and both tests are
  shown to be able to return **the positive** (complete separation → the 1/C floor) and **the null**
  (identical arms → 1, reversed arms → 1). At 32/arm the p-value floor is 5.46e-19, so the design is
  capable of significance.
- The script **refuses to run** unless all four blocks hold 16 runs, printing the optional-stopping
  rationale. `--allow-incomplete` exists for plumbing checks only and prints a loud non-preregistered
  banner. The data path was verified end-to-end on a **synthetic** tree so that no partial real result
  was ever computed.

### 24d. Port-engagement readback, control already known non-vacuous
`allow_melee=false` ⇒ zero melee weapon buys. Jack bare bought melee on **135/253 = 53.4%** of weapon
purchases. **Expected: bare arm ≈ 0.53, ported arm = 0.** If the ported arm is not 0, the build is
mis-armed and the block is void.

⚠️ **MEASURED AT BLOCK LEVEL 2026-08-01, and the expected bare rate above is WRONG:**
**A1 PORTED 0/444 = 0.0000** vs **B1 BARE 61/327 = 0.1865**. The bare arm buys melee at **18.65%**,
not 53.4% — both arms now start on a gun under the shared `weapon_prefixes`, so the older 53.4%
figure does not transfer. **The readback still passes decisively**: under the bare rate,
P(0 of 444) ≈ e⁻⁹². The direction and the zero are what the gate needs; the specific bare rate was
never load-bearing. ⚠️ A 3-run spot check of the same quantity read **8.7%** — less than half the
block figure, so quote the block number.
⚠️ **Method note:** `weapon_type` is on the `purchase_offer`, the buy is on the `purchase_decision`
(`payload.action.type == "shop_buy"`); the two must be joined via the most recent offer board. Reading
`e["type"]` (it is `e["event"]`) or expecting `payload.items` on a decision yields **0/0** — a vacuous
zero that reads as a clean pass. The bare control is what exposed it.

### 24e. Pre-declared interpretation
- **Reject** ⇒ the profile port is established as improving a non-`well_rounded` character.
- **Fail to reject at n=32/arm** ⇒ the port is **not** a usable capability lever, and §23b option 2
  (accept the surface) becomes the answer. **This is a real possible outcome and will be reported as
  such**, not followed by a fifth character.
⚠️ Still uncontrolled: one character only, so a positive result generalises no further than Jack.

---

# §25. DOES THE PROFILE PORT GENERALISE BEYOND JACK?

Written 2026-08-01, **before any §25 data exists.** §24 established the port on Jack
(terminal wave p = 0.0186; victories 17/32 vs 4/32). §24e pre-registered that this
"generalises no further than Jack". §25 tests whether it generalises at all.

**The existing evidence is genuinely mixed and that is why this is worth running:**
Jack ported = large positive at 32/arm; **fisherman ported = 0/8 vs bare 0/8, p = 0.3373**,
a clean null but at n=8, which can detect almost nothing. One positive and one
uninformative null is not a generalisation claim in either direction.

## 25a. Design — characters are the generalisation unit

Four characters x 8 runs x 2 arms = **64 runs**, Danger 0, full runs.

Per `campaign_sizing_v2.md`: precision depends on (units x reps) and **the generalisation
unit is the thing you want to generalise over**. §24 spent 32 reps on one character and can
say nothing about a second. §25 spends the same 64 runs on **four** characters to buy a
generalisation claim instead of a tighter single-character estimate.

**Characters, and why exactly these four.** The port sets `allow_melee = false`, so a
character whose reachable starting weapon is MELEE would open on a weapon its own shop
scores -1e9 — the Artificer plank defect. Verified from the game's own `*_data.tres`:

| character | starting weapons | first matching prefix | weapon | type |
|---|---|---|---|---|
| `arms_dealer` | 1 | `weapon_pistol` | pistol | **RANGED** |
| `cyborg` | 8 (3 melee / 5 ranged) | `weapon_pistol` | pistol | **RANGED** |
| `fisherman` | 16 (8 melee / 8 ranged) | `weapon_pistol` | pistol | **RANGED** |
| `mutant` | 13 (6 melee / 7 ranged) | *no pistol* -> `weapon_smg` | smg | **RANGED** |

**EXCLUDED and why:** `crazy` (1 ranged of 6), `lucky` (2 of 8), `multitasker` (10 of 27 but
melee-first) — all would hand the ported arm a melee opener. Excluding them is a
**restriction on the claim**, stated here: §25 tests generalisation across
*ranged-capable* characters only.

**Weapon prefixes, identical in both arms** (order-sensitive, walked per character above):
`["weapon_pistol","weapon_smg","weapon_revolver","weapon_shredder","weapon_crossbow","weapon_laser_gun","weapon_"]`

## 25b. Arms differ in exactly one constant

- **PORTED:** `EXPERIMENT_PORT_WR_PROFILE_TO = "*"` (new in this build — ports onto every
  cached profile except well_rounded). A run uses one character, so "*" is behaviourally
  identical for that run to naming its character, while letting **one build serve all four**.
  Without it the campaign needs 8 deploys and 8 version bumps, each an identity-gate risk.
- **BARE:** `EXPERIMENT_PORT_WR_PROFILE_TO = ""`.
- Each arm ships its **own version** (different content must never wear the same version
  string — the identity gate compares strings and cannot see content).
- `agent_config.json` **byte-identical across arms** except `character`.
- Guarded by `test_v70_port_supports_wildcard_so_one_build_serves_a_multi_character_block`,
  which asserts both branches route through one copier, the wildcard skips well_rounded, and
  the load-bearing `tgt.name = "well_rounded"` survives.

**Order drawn with `secrets` BEFORE collection: BARE first, then PORTED.**
Character order within each arm: **cyborg, fisherman, mutant, arms_dealer.**

## 25c. PRIMARY endpoint — fixed before data, no substitution

**Terminal wave. STRATIFIED exact permutation: arm labels are permuted WITHIN each
character; statistic = total ported terminal-wave sum across all four strata; one-sided
(ported > bare); alpha = 0.05.**

Stratification is not optional. Characters differ enormously in baseline strength, and an
unstratified test would let between-character variance swamp the treatment — the same reason
fixture campaigns here are always paired. The null distribution is computed **exactly**: per
character, DP over (subset size, subset sum) gives that stratum's exact distribution; the
four are then **convolved**. No Monte-Carlo.

**SECONDARY, reported not decisive:** pooled victories (Fisher one-sided); per-character
terminal-wave means and victory counts, reported for all four **whatever they show**.

## 25d. Engagement readback, with its control

`allow_melee = false` ⇒ **zero melee weapon buys on the ported arm.** The bare arm supplies
the non-vacuous control. **Measured at BLOCK level, never per run** — a single bare run
bought 0/31 melee in §24 purely by chance. Method: `weapon_type` is on the `purchase_offer`,
the buy on the `purchase_decision`; the two must be joined via the most recent offer board.
**If the ported arm is not 0 melee across the block, the build is mis-armed and the block is void.**

## 25e. Pre-declared interpretation

- **Reject** ⇒ the port generalises across ranged-capable characters. This becomes a
  shipping decision, not another experiment.
- **Fail to reject** ⇒ the port is **Jack-specific**, §24 stands as a single-character
  result, and the "fix capability" branch is far weaker than §24 alone suggested.
  **This is a real possible outcome and will be reported as such.**
- **Heterogeneity is expected and is not a licence to pick.** If the pooled test is null but
  one character looks strong, that is a HYPOTHESIS for a future powered test on that
  character — **not** a finding. Selecting the best of four post hoc is exactly the
  multiplicity error this document exists to prevent.

⛔ **No `--stop-on-win` in any block** (§22). All 8 attempts per character-arm run regardless.
⛔ Era must stay **177/46** throughout; any unlock invalidates pooling.

## §25f. AMENDMENT, 2026-08-01 — character set changed for ERA SAFETY, before any outcome was examined

**The flaw.** §24 could not suffer shop-pool drift because Jack's reward was already unlocked, so no
victory could change the pool. I carried that immunity into §25 **without re-deriving it for the new
characters.** Checked in the save by djb2 (positive controls `item_potato`/`item_padding`/
`item_night_goggles`/`item_lens` all True; negative control False):

| character | challenge done | reward | unlocked | a win would |
|---|---|---|---|---|
| cyborg | ✗ | `item_improved_tools` | **✗** | **move the era** |
| fisherman | ✗ | `item_lure` | **✗** | **move the era** |
| mutant | ✓ | `item_octopus` | ✓ | safe |
| arms_dealer | ✓ | `item_anvil` | ✓ | safe |

**The ported arm is the arm expected to win**, so drift was the likely case, not a tail risk — and
§25b already declares that any unlock invalidates pooling. The campaign was **stopped at 7/64**.

**The fix — no save modification.** Enumerated all 41 playable characters for (a) reward already
unlocked and (b) a RANGED opener under the §25 prefix list. **Seven qualify**: arms_dealer, artificer,
jack, mutant, ranger, saver, well_rounded. Excluding `well_rounded` (the source profile — porting to
it is a no-op) and `jack` (already the §24 subject), the set becomes:

**`artificer, ranger, mutant, arms_dealer`** — cyborg → artificer, fisherman → ranger, substituted in
place so the drawn order is otherwise preserved. Openers re-verified: artificer `weapon_shredder_1`,
ranger `weapon_pistol_1`, mutant `weapon_smg_1`, arms_dealer `weapon_pistol_1` — **all RANGED under the
unchanged prefix list.**

⚠️ **The substitution is driven by a STRUCTURAL, pre-data property (which rewards are unlocked in the
save), not by any outcome.** No fisherman run was ever collected. Seven cyborg runs were collected and
are **discarded unused**; one of them was inspected for arm certification (defeat, wave 16) before the
flaw was found. Cyborg's removal is caused by its locked reward, not by that result.

⚠️ **§25d's melee readback is VACUOUS for artificer and ranger** — both profiles already set
`allow_melee:false`, so their bare arms buy no melee either. **Their readback is instead the share of
weapon buys OUTSIDE `set_gun`**, since the port sets `allowed_weapon_sets = ["set_gun"]` (artificer is
already known to go 14.6% → 0 on that signature). arms_dealer and mutant keep the melee readback
(`allow_melee` defaults true for both). **The bare arm's non-vacuity must be confirmed per character
before any zero is believed.**
