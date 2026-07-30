# Unlock campaign plan — what is actually locked, and what unlocking buys us

Date: 2026-07-30. Author: primary session. Status: **PLAN, pre-registration pending Gate 0.**

Written while the 12-attempt Danger 5 baseline was still running (9/12 at time of writing). No
deploys, no identity-constant edits, no config changes were made.

---

## 1. Measured state — from the save file, not from a wiki

Source of truth: `%APPDATA%\Brotato\76561198030888875\save_v3_0.json`.

Character / item / weapon ids are stored as **djb2 hashes** (Godot `String.hash()`:
`h = 5381; h = h*33 + c`). Mapping method and its readback:

- 50 character ids are available in cleartext in `difficulties_unlocked[].character_id`.
- djb2 over those 50 matched **43 of the 43** entries in `characters_unlocked`, with **0 orphans**.
  A complete, exact, zero-residual mapping — this is the readback that makes the rest trustworthy.
- Same method against ids extracted from `third_party/brotatoai/src/brotato_sources/`.

### Progression counters (`data`)

| field | value | consequence |
|---|---|---|
| `enemies_killed` | 3,241,915 | every kill-count unlock satisfied ~160x over |
| `materials_collected` | 2,455,254 | every material-count unlock satisfied ~120x over |
| `trees_killed` | 34,441 | Explorer (50 trees) long done |
| `fruit_eaten_full_hp` | 25,141 | Fruit Basket (100 fruits at max HP) long done |
| `run_won` | 1,275 | ⚠️ `run_started` reads 696 — **fewer started than won**. Field is internally inconsistent; do not cite it. |
| `is_unlock_all_save` | 0 | not a cheat save |

### Danger tiers — already fully unlocked

`character_saver` carries `max_difficulty_beaten.difficulty_value = 5`, and **all 50** characters
read `max_selectable_difficulty: 5`. Danger unlock is global on this save and is **complete**.
There is no danger grind. (Consistent with the live campaign: D5 runs are executing right now with
`danger_ok: true`.)

Per-character wins on record — only three:

| character | max difficulty beaten |
|---|---|
| `character_saver` | 5 |
| `character_ranger` | 2 |
| `character_well_rounded` | 0 |

Everything else reads `-1`. The agent's ~1,275 wins are essentially all `well_rounded` at D0,
because `run_orchestrator.gd:23` defaults `target_character_id = "character_well_rounded"`.

### What is locked

| kind | unlocked | locked | confidence |
|---|---|---|---|
| Characters | 43 / 50 | **7** | exact (0-residual mapping) |
| Items | 171 | **28** exactly enumerated | exact *among the 177 the extracted source knows*; treat 28 as a **floor** |
| Weapons | 46 | **≥5** | 5 confirmed; remainder **unresolved** |
| Consumables | 3 / 3 | 0 | exact |

**Locked characters (7):** `ghost`, `speedy`, `cryptid`, `baby`, `vampire`, `beast_master`,
`wounded`.

**Locked items (28)** — all are "win a run with character X" rewards:

| tier | locked items |
|---|---|
| 0 | *(none — tier 0 is fully unlocked)* |
| 1 | compass, lure, ritual, snail, spicy_sauce, tentacle, whetstone |
| 2 | bowler_hat, community_support, fairy, fin, hunting_trophy, improved_tools, lucky_charm, rip_and_tear, stone_skin, wheat |
| 3 | anvil, big_arms, explosive_shells, focus, giant_belt, gnome, medikit, octopus, panda, robot_arm, spider |

**Locked weapons (5 confirmed):** chopper, claw, fighting_stick, hatchet, spiky_shield — **all
melee.**

### Independent cross-validation

The Steam guide (RainbowStaple, *ALL UNLOCKS & How to get them*, updated for 1.1.8.1) lists **31**
"win a run with X" items. The three it names that our measurement shows **unlocked** are Padding
(Saver), Night Goggles (Ranger), Potato (Well-Rounded) — *exactly* the three characters with
recorded wins. **28/28 agreement** between the hash mapping and the guide. It also names the same
5 melee weapon unlocks. Two independent sources, no discrepancy.

---

## 2. The premise, corrected

The request was "unlock a lot of the locked stuff to make Danger 5 easier." Three parts of that
need adjusting, and one part is stronger than expected.

1. **There is no danger grind and no count grind.** Both are finished. ~90% of the game's
   progression on this save is already done.
2. **The entire remaining surface is "win a run with character X."** There is no other lever. 28
   items and ≥5 weapons all sit behind character wins.
3. **⚠️ Unlocking is not free, and it is not reversible through play.**
   `singletons/item_service.gd:71-83` (`init_unlocked_pool`) builds each tier's pool **strictly by
   filtering on the unlocked list**, and offers are a uniform draw within a tier
   (`Utils.get_rand_element`). Every unlock permanently **adds a competitor to its tier pool**:

   | tier | pool now | pool after all unlocks | change |
   |---|---|---|---|
   | 0 | 53 | 53 | — |
   | 1 | 39 | 46 | +18% |
   | 2 | 37 | 47 | +27% |
   | 3 | **20** | **31** | **+55%** |

4. **But the locked items are concentrated where it matters.** Tier 0 is untouched and tier 3 —
   the small, precious pool — gains 11 items that include much of Brotato's top end (Focus, Giant
   Belt, Explosive Shells, Anvil, Medikit, Octopus, Robot Arm, Spider). Enriching a 20-item
   legendary pool is a plausibly large effect, and it is the strongest argument for the campaign.

**The precedent that decides this.** [Piggy Bank, measurement-discipline instance 19] — an item
that enters the pool but our scorer never buys is not neutral, it is **dilution**. `item_glass_cannon`,
`item_goat_skull` and `item_toxic_sludge` were bought **0 times in 600 runs despite being offered
and affordable**. So the question is not "are these good items in Brotato" but **"would OUR shop
scorer buy them?"**

That question is answerable offline, for free, before any machine time is spent.

---

## 2c. ⭐ MEASURED 2026-07-30 — THIS SUPERSEDES §2.4's "tier 3 is the strongest argument"

Measured with `scripts/wp2_item_offer_ledger.py` over **600 runs / 15,519 boards / 51,320 offer
slots / 5,680 buys**, `buys_unmatched_to_board = 0`. Verified in the primary session against the raw
JSON, not taken from a delegate's summary.

First, a correction to a scare of my own: the ledger reports 66 distinct tier-3 ids, which looked like
it contradicted the 31-item tier-3 pool in §2.4. It does not — that figure pools items and weapons
(**22 tier-3 items + 44 tier-3 weapons**). And the `.tres` `tier` field is trustworthy for items:
**148 of 149 ids agree** with the observed offer tier (only `item_tyler`, 2 vs 1). §2.4's table stands.

**But splitting purchases by category kills the tier-3 argument.**

| category / tier | offer slots | bought | buy rate |
|---|---|---|---|
| item t0 | 13,922 | 1,592 | 11.4% |
| item t1 | 10,874 | 1,153 | 10.6% |
| item t2 | 6,593 | 479 | 7.3% |
| **item t3** | **759** | **50** | **6.6%** |

Tier-3 items are bought **50 times per 600 runs = 0.083 per run.** Adding 11 items to a ~22-item pool
makes ~1/3 of tier-3 item offers new, yielding **~0.03 new legendary purchases per run — one every
~36 runs.** I called this the strongest argument for the campaign. It is nearly irrelevant.

Expected effect of unlocking **all 28** items, per run:

| tier | new / pool | share of offers | slots/run | × buy rate | new purchases/run |
|---|---|---|---|---|---|
| 1 | 7 / 55 | 12.7% | 18.1 | 10.6% | 0.24 |
| 2 | 10 / 54 | 18.5% | 11.0 | 7.3% | 0.15 |
| 3 | 11 / 33 | 33% | 1.27 | 6.6% | 0.03 |
| | | | | **total** | **≈0.42** |

**⛔⛔ AND THE DECISIVE FRAMING: unlocking SUBSTITUTES, it does not ADD.** The pool change does not
create extra purchases — the shop buys about 9.5 items per run either way. It only changes *which*
item fills a slot. So the benefit is not 0.42 items/run, it is **0.42 substitutions/run × the marginal
quality gain of the new item over the one it displaced.** Unless the locked items are dramatically
better than what they replace, the effect on D5 survival is very small.

**Consequence for experiment design — this is a design-time kill, not a result.** A treatment worth
~0.42 substitutions per run has no chance of moving a D5 terminal-wave endpoint whose own baseline
spread is **sd 2.65 waves** (n=9). No feasible campaign detects it. Running the broad §7 option-C pool
experiment would have been a statistic that cannot return the positive — the 11(c) family. **Do not
run it.**

### Revised recommendation: ONE character win, not 28

The only locked item with a specific, externally-argued case is **`item_fairy`** — the D5 guide's
first-named S-tier universal item. It is **tier 2**, and a single tier-2 item in a 54-item pool is
offered **~0.20 times per run (~1 run in 5)**. Its reward character, **Renegade, is already unlocked.**

So: **win one D0 run as Renegade (~48 min expected at the 0.395 baseline) to unlock Fairy.** That
captures the single highest-value item on the board for ~1/50th of the 40-60 h the full grind costs.
Everything else on the item list should wait for a reason better than "it is an unlock".

### ⭐ The honest answer to the original question

**Measured, unlocking is NOT a viable lever for making Danger 5 easier.** The remaining unlocks are
substitutions inside a pool the policy already buys from ~9.5 times a run, concentrated at tiers 1-2,
worth ~0.42 substitutions per run, against an endpoint with sd 2.65 waves. The premise does not
survive contact with the offer/buy data.

What the unlock campaign IS good for, and these are real:
- **The stated learning goal** — playing and getting good with each character. 64 build profiles
  already cover all 50 roster characters.
- **The 7 locked characters**, which are access rather than power, and `ghost`/`speedy` are cheap
  in-run stat gates needing no win at all.
- **Variety and completeness** as ends in themselves.

If the goal is specifically *beat Danger 5*, the leverage is elsewhere — the guide's own #1 failure
point ("neglecting dodge/armor → one-shot deaths mid-run") against our 9 deaths at median wave 11 is
a far better lead than any unlock.

## 3. Gate 0 — free, offline, blocking

Per standing practice ("prove a candidate changes a real decision at a reachable dose BEFORE
spending"):

**G0-a — Score the 28 locked items with our own scorer.** Run each locked item's stat block through
`teacher/shop_strategy.gd`'s valuation and rank it against the *current* pool of the same tier.
Report, per tier: how many locked items would score above the current pool median, and how many
would be **rejected outright** by the safety filter that produces `EXIT_NO_SAFE_POSITIVE_ITEM`
(items with negative stat components are the ones it rejects).

*Pre-registered decision rule:* proceed to the full campaign only if **≥6 of the 11 tier-3 items**
score above the current tier-3 pool median AND fewer than 3 of them would be rejected outright.
Otherwise the campaign is re-scoped to the subset that passes.

**G0-b — Price the 5 melee weapons, separately.** Our policy is gun-based
(`teacher_v1-0.1.129-gun-wp1`) and build profiles carry an explicit `allow_melee: false`. The
weapon pool shares `_tiers_data[tier][ALL_ITEMS]` with items, so melee weapons a gun build will
never take are **pure dilution of every offer slot**.

If that holds, then the five character wins whose *only* reward is a melee weapon —
**Multitasker → Chopper, Wildling → Hatchet, Masochist → Spiky Shield, Apprentice → Fighting
Stick, Cryptid → Claw** — have **negative expected value for the current policy** and should be
deliberately *skipped*, not merely deprioritised. This is the least obvious and possibly most
valuable conclusion in this document, and it is a hypothesis to test at G0-b, not yet a finding.

**G0-c — Trivial-copy sanity.** Confirm the scorer actually produces different scores across these
28 items (i.e. the ranking is not degenerate) before reading anything off the ranking.

---

## 4. Verify the character lever before trusting it

The mod already supports character selection:
`agent_config.json` → `agent_controller.gd:2749-2750` → `run_orchestrator.gd:23`
`target_character_id` → `_select_inventory_by_id` at `run_orchestrator.gd:150`.

**This is the exact shape of the Danger 0 bug.** `danger` was a real config key whose call sites
passed a hardcoded literal, so 1,873 runs silently ran at D0 while reporting what the config asked
for. Assume nothing here.

Required before any grind run counts:

- **Readback:** observed character (`RunData.get_player_character(0)` via `_character_id()`) must
  equal the requested id, latched on the first combat tick — same pattern as the 0.2.58 danger
  latch, where an earlier read reports a false mismatch.
- **Fail closed:** 7 characters are **locked**, so a request for one of them cannot be satisfied.
  It must abort the run, never silently fall back to `well_rounded`. A run that quietly plays the
  default character while the summary says otherwise is the danger bug again.
- Note `build_profiles.gd:53-56` `get_profile()` **returns `_default` on a miss rather than
  raising.** In this case that is benign — **64 profiles are defined and all 50 roster characters
  are covered, 0 fall back** — but the silent-default shape is worth a raise.

---

## 5. Ordering, and what it costs

Do **not** assume `well_rounded`'s D0 win rate (0.395 baseline) transfers to 63 other profiles.

- **Screen first:** ~4 D0 runs per candidate character to get an observed win rate, then order the
  grind by `(G0-a item value) / (expected runs per win)`.
- **Grind at Danger 0.** The reward item is identical at every danger, so D0 is strictly cheapest.
- **Cost:** full runs are ~19 min and the standing rule is **1.0x for full runs** (2.0x is approved
  for paired fixture campaigns only). At a 0.395 win rate that is ~2.5 runs ≈ 48 min per character
  win. 28 characters ⇒ **≈22 h of machine time as a floor**, and realistically 40-60 h once
  hard characters (Pacifist, One-Armed, Golem, Sick) are priced in. This is days, not hours.

---

## 6. The 7 locked characters

These need targeted one-off builds, not wins. Conditions, with provenance stated:

| character | condition | source |
|---|---|---|
| `ghost` | `stat_dodge >= 60` | game source — `challenges/hallucination_data.tres:9,14,21` (`chal_hallucination`) |
| `speedy` | `stat_speed >= 50` | game source — `challenges/fast_data.tres:9,14,21` (`chal_fast`) |
| `cryptid` | ≥10 neutrals (trees) alive at wave end | game source — `challenges/forest_data.tres`; semantics from `main.gd:887-888`, which is **commented out in that tree**, so weaker evidence |
| `baby` | reach level 10 before wave 6 | **guide/wiki only** — absent from the extracted source |
| `vampire` | +40% life steal | **guide/wiki only** — absent from the extracted source |
| `beast_master` | **not established** | absent from source, absent from the guide (newer than Jan 2025) |
| `wounded` | **not established** | absent from source, absent from the guide |

Caveat on the source tree: it is an older build (44 characters vs the installed 50) and has been
patched — `singletons/run_data.gd:95-96` unconditionally completes every challenge on `_ready()`
with the debug guard commented out. Treat it as indicative for mechanism, not authoritative for the
installed version.

`ghost` and `speedy` are stat gates evaluated **any time in-run** (`challenge_service.gd:130-152`),
so they are cheap: build dodge/speed deliberately on a throwaway D0 run, no win required.

---

## 7. Three ways to run this — recommendation

Unlocks are irreversible through play, but `items_unlocked` is a plain list in a JSON save that we
already manipulate for fixtures. That opens an option worth naming explicitly, because it is the
operator's call and not mine:

- **(A) Legitimate grind only.** Win with each character. Honest, satisfies the "learn every
  character" goal, costs 22-60 h and risks discovering afterwards that the enriched pool did not
  help.
- **(B) Save-edit the unlocks directly.** Minutes instead of days. But it is no longer "unlocked",
  it changes the save's meaning, and it forfeits the learning goal.
- **(C) ⭐ Save-edit a COPY as a measurement, then grind for real.** Build a save with the 28 items
  added to `items_unlocked`, run a **paired D5 campaign** against the current save, and *price the
  enriched pool* before committing 22-60 h. If it pays, grind legitimately for the items that
  earned it. If it does not, we saved days and learned something publishable.

**Recommendation: C.** It is the only option that answers "does this actually make D5 easier?"
before paying for it, and it preserves the legitimate grind for the unlocks that survive the test.
It also converts the whole exercise from a chore into a measured experiment.

## 7b. ⚠️ The unlock campaign creates a new measurement era

`init_unlocked_pool` means the item pool **is part of the game being measured**. Changing
`items_unlocked` changes the distribution every future run draws from.

Consequence: **the 12-attempt D5 baseline finishing right now is not comparable to any post-unlock
run.** This is the [WIN-RATE HISTORY] failure exactly — a 47-point collapse ran ~20 versions
invisibly because results were pooled across eras.

**Required before any unlock lands:** stamp the pool identity into every run summary — at minimum
`len(items_unlocked)`, `len(weapons_unlocked)` and a hash of each sorted list — so era-matching is
mechanical rather than remembered. `begin_run`'s summary dict is an **allowlist that silently drops
unknown keys**, so the field has to be added there too, and new instruments here default to `-1`
so "never written" cannot masquerade as a real zero.

---

## 8. The learning goal

64 build profiles already exist and cover all 50 roster characters, so per-character runs are
immediately possible and each one yields per-character telemetry. That gives the "get good with
every character" objective a real substrate: per-character win rate, terminal-wave distribution and
failure phenotype, measured on the same instruments as the D5 work.

---

## 9. Immediate next actions

1. **Wait** for `.tmp/d5_campaign/report.json`; disarm `auto_start` and `danger` in
   `agent_config.json`; analyse against `danger5_baseline_prereg.md`. *(Unchanged — this plan does
   not touch the running campaign.)*
2. **G0-a / G0-b / G0-c** — offline, zero machine time, no deploy. Blocking.
3. Resolve `beast_master` / `wounded` unlock conditions from the installed game's own data.
4. Pre-register the option-C paired pool experiment, including the era-stamp from §7b, before any
   save is edited.
