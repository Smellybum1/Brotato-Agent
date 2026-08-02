# §27 Acquisition Block 1 — Result

**Completed 2026-08-02.** 5 characters x 8 runs = **40/40 collected**, `character_ok` **40/40**,
0 technical failures. Build `0.2.73-wp2-capture`, port INERT, danger 0, no `--stop-on-win`.
Prereg: `acquisition_block_prereg.md`. Driver `scripts/acq_campaign.sh`.

## Result

| cell | victories | rate | terminal waves | era (items/weapons) | reward | acquired |
|---|---:|---:|---|---|---|---|
| soldier | 3/8 | 0.375 | 20,20,20,13,20,19,20,20 | 177/46 → 177/47 (**spans**) | `weapon_nuclear_launcher` | ✅ |
| renegade | 1/8 | 0.125 | 20,15,17,19,13,20,17,20 | 177/47 | `item_fairy` | ✅ |
| cyborg | 0/8 | 0.000 | 17,17,16,17,13,10,17,13 | 178/47 | `item_improved_tools` | ❌ |
| hunter | 2/8 | 0.250 | 20,19,20,20,6,13,19,17 | 178/47 → 178/48 (**spans**) | `weapon_sniper_gun` | ✅ |
| one_arm | 2/8 | 0.250 | 19,10,9,9,20,17,9,20 | 178/48 → 179/48 (**spans**) | `item_focus` | ✅ |

**Final era: 179 items / 48 weapons / 59 challenges.** Verifier: `.tmp/acq_verify.py <character>
[reward_id]`, which asserts 5 positive controls across all three unlock lists before reading a target.

**4 of 5 targets acquired.** Two RANGED weapon families (tiers 2-3 each), one A-tier item, and one
item our own scorer vetoes (below).

## ⛔ Do not pool 8/40

The per-cell spread **0.000-0.375** is a mixture. Quote per character, alongside the prior figures:

**ranger 0.625 · well_rounded 0.384 · soldier 0.375 · hunter 0.250 · one_arm 0.250 · renegade 0.125 ·
cyborg 0.000 (n=16, two cells).**

The reopening decision was vindicated **on acquisition** — 4 of 5 cells landed, against the old
pooled-0.049 expectation of P=0.33 for a single 8-run campaign. That is an outcome, **not a validated
selection rule**: nothing predicted *which* four, and cyborg — the closest structural match to
`well_rounded`'s runtime config of any candidate — is the one that failed.

## ⭐ Three findings this block established

### 1. `weapons_unlocked` stores djb2 of `weapon_id`, not `my_id` — and the prereg was wrong
`progress_data.gd:225,259` push `weapon.weapon_id`; `item_service.gd:81` filters the pool on the same.
`my_id` is never stored. They differ by the tier suffix (`weapon_nuclear_launcher_3` vs
`weapon_nuclear_launcher`), so the list holds **weapon FAMILIES** — 47 entries against 182 `my_id`s.

The old `my_id` test returned **0/182**: structurally incapable of returning True. It survived because
every positive control in use was an **item**, and controls validate the test, not the collection.

- **Retrospective**: diffing `weapons_unlocked` against the 2026-07-30 save backup isolates exactly one
  added integer, `356968361` = `djb2("weapon_nuclear_launcher")` — soldier's reward.
- **Prospective**: hunter's unlock was then caught **in advance** by the corrected check, one integer
  added matching `djb2("weapon_sniper_gun")`, controls passing.

**A win admits the WHOLE FAMILY**, not the rewarded tier — `init_unlocked_pool()` iterates every tier
variant and filters each on the family id. Weapon rewards are worth more than a one-item framing.

Re-derived from this: **12 locked weapon families, 3 of them RANGED** (`obliterator`,
`potato_thrower`, `sniper_gun`) — superseding the old "≥5 locked, all melee". Floor, not a census:
4 stored hashes match no family in the decompiled snapshot, so the installed build has families that
tree lacks.

### 2. `item_fairy` is acquired and our own scorer hard-vetoes it
Verified against the **installed zip**: `ROGUERANKER_ITEM_TIERS` (68) ∪ `WIKI_USEFUL_ITEM_TIERS` (98)
= 166, fairy absent, four known-bought items present (control passes). With
`EXPERIMENT_ROGUERANKER_ITEMS_ONLY := true` and `ROGUERANKER_ITEMS_ONLY_FROM_WAVE := 11`, fairy scores
**-1e9 from wave 11** — buyable only in waves 1-10 while permanently competing for tier-2 offer slots.
On our own terms this acquisition is **dilution**, which is what memory predicted when it flagged
renegade as a skip.

**The upside is that the divergence is now testable.** An external D5 guide ranks Fairy its first
S-tier universal item while our allowlist omits it entirely. Both cannot be right, and owning the item
makes offer→buy in waves 1-10 measurable. If the guide is right, the blind spot affects
**already-unlocked** items too — a larger finding than any single unlock.

### 3. The era-drift signature replicated three times
In soldier, hunter and one_arm the cell contained a **second victory after the reward was claimed**,
and every one granted nothing (era static across the later wins). Independent confirmation that
unlocks are per-challenge and one-shot.

⚠️ Consequence: **three of five cells span an era boundary** and must not be pooled as one era. Only
renegade and cyborg are era-homogeneous.

## ⚠️ Caveats and one correction

- **The `weapon_prefixes` pre-flight was over-claimed.** It was reported as "validated behaviourally,
  24/24" when only three characters had run; the validation was then extended to two unobserved ones.
  **one_arm opened on `weapon_smg_1`, not the predicted `weapon_pistol_1`** (8/8). Not a walk bug —
  one_arm's snapshot inventory has pistol at index 10 ahead of smg at 11, so against the snapshot the
  prediction was right; the older 44-character tree disagrees with the installed build. Harmless in
  outcome (smg is RANGED and the agent's known-good opener). **A behavioural validation is a property
  of the characters observed and does not transfer** — check the opener on the first run of each cell.
- **cyborg 0/16** pools two cells across two eras with **identical mean terminal wave 15.0**;
  rule-of-three 95% upper bound 0.1875, P(0/16 | 0.384) = 4.3e-4. The two-cell permutation p = 1.0000
  is **vacuous by construction** (observed difference exactly 0) and should not be quoted.
- Win rates here are **not era-matched** — the era drifts by design in an acquisition campaign.

## Machine state at completion

Driver exited rc=0; **0 Brotato processes, 0 repo-matching survivors**, `auto_start` **false**,
verified by readback. ⚠️ The block ends on `taskkill /F`, so the ModLoader mods-disabled latch may be
set — check `modloader.log` and `mod_list` before the next campaign and run
`deploy_mod.py --repair-launch` regardless (it does not rewrite `agent_config.json`).
