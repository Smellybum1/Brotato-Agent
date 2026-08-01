# §27 — Acquisition block 1, pre-registration

Written 2026-08-02, **before** collection. Queued behind §26; do not launch while §26 runs.

## §27a Why this is allowed to run at all

`brotato-unlock-surface` closed this line with an explicit gate: *"Do not reopen any unlock branch
without a demonstrated policy/build change first,"* reasoning that **the agent plays only
`well_rounded` well**. §25 supplied the change by accident:

- The **0/24** win-branch record **predates the gun-first `weapon_prefixes` fix.**
- §25's BARE arm, post-fix, era-matched (177/46), one build: **ranger 5/8 = 0.625**, mutant 1/8,
  artificer 0/8, arms_dealer 0/8.

⇒ "Plays only well_rounded well" is **falsified**; capability is character-specific.
⛔ **Only the WIN branch reopens.** The stat gates stay closed — `stat_dodge` **0/282** against a gate
of 60 (best ever 49 fixture / 30 full run), `stat_speed` **0/80** against 50 (best 36), cryptid
assessed unreliable. Nothing in §25 touches them.

## §27b This is an ACQUISITION campaign, not a measurement one

⛔ **The era WILL drift, by design.** Every gating character here has a LOCKED reward, so a win
unlocks an item and moves the shop pool — that is the objective, not a threat. Consequences, declared
now so they are not rationalised later:

- **Win rates from this campaign are NOT era-matched** and must NOT be pooled with §25's bare arm, nor
  compared against ranger's 0.625. Record the `unlock_pool` stamp **per run** and report how many
  distinct eras each character's block spans.
- A character whose block spans an era change has its rate reported **with that fact attached**, never
  as a clean figure.
- ⛔ **A differing era is NOT a validity failure here** (it is in §25/§26). `character_ok` still is.

**No `--stop-on-win`** (§22 / §20a): the unlock is granted at the win either way, so running all 8
costs ~1 h and keeps the win-rate estimate uncensored. Stopping on a victory censors the arm at its
highest possible endpoint value.

## §27c Targets — the five verified in the primary session

Selected by a stated rule, not by preference: gating characters with a still-locked reward whose build
profile sets **`allow_melee: false`** (the ranger-shaped profile that produced 5/8) **and** whose
starting inventory resolves cleanly inside the first six prefix entries — no bare `weapon_` fallback.

| character | reward | kind | first prefix match | opener | type |
|---|---|---|---|---|---|
| `soldier` | `weapon_nuclear_launcher_3` | weapon | `weapon_pistol` | `weapon_pistol_1` | RANGED |
| `renegade` | `item_fairy` | item | `weapon_pistol` | `weapon_pistol_1` | RANGED |
| `cyborg` | `item_improved_tools` | item | `weapon_pistol` | `weapon_pistol_1` | RANGED |
| `hunter` | `weapon_sniper_gun_3` | weapon | `weapon_crossbow` | `weapon_crossbow_1` | RANGED |
| `one_arm` | `item_focus` | item | `weapon_pistol` | `weapon_pistol_1` | RANGED |

**8 runs each, 40 total, fixed n.** Verified in the primary session against each character's own
`starting_weapons`, resolving every id from the weapon's `my_id` (never a filename) and its `type`
against `weapon_type.gd {MELEE=0, RANGED=1}`.

⚠️ **`allow_melee: false` is a HYPOTHESIS about what made ranger win, not an established cause.** It is
a defensible selection rule; it is not evidence. If all five come back 0/8 that refutes the rule, not
the reopening.

## §27d Config

Build **`0.2.73-wp2-capture`**, port **INERT**. Danger **0**. `movement_estop_enabled` **false**.
Prefixes: `[weapon_pistol, weapon_smg, weapon_revolver, weapon_shredder, weapon_crossbow,
weapon_laser_gun, weapon_]` — unchanged, since all five resolve within the first six.
⛔ **Do NOT adopt the 4 proposed new prefix entries here.** They are for characters that reach the bare
fallback; none of these five do, and changing the list would alter the arm for no benefit.

## §27e Acquisition verification — the check that has failed twice

After each character's block, verify the unlock **in the save**:
- ids are **INTEGER djb2 hashes**; `str in list[int]` is **structurally incapable of returning True**.
- hash the entity's own **`my_id`**, never a filename (`anvil` vs `item_anvil` hash differently).
- **Assert positive controls that MUST return True**: `item_potato`, `item_padding`,
  `item_night_goggles`, `item_lens`, and reference `item_anvil` = 2275354477.
  If any reads False the method is broken — report that and stop, do not report results.
- Also record `unlock_pool` items/weapons before and after; **an unlock that does not move the count
  did not land.**

## §27f Pre-declared interpretation

- **Primary objective: acquisitions.** Report which of the five rewards were unlocked, verified in the
  save by djb2 with passing positive controls.
- Win rates are **secondary and descriptive**, reported per character with era spans attached.
- ⛔ **A 0/8 is not a proven zero** — rule-of-three upper bound **0.31**. A character that fails here is
  UNRESOLVED, not hopeless.
- ⛔ **Do not conclude anything about `allow_melee` as a cause** from this block. Five characters
  sharing a profile flag and a win rate is a correlation across a hand-picked set.
- ⚠️ The gating table came from a **decompiled snapshot older than the installed build** (12 completed
  challenge hashes in the save have no counterpart in it), so the reward list may be incomplete. The
  five rows here were each read from a real `.tres`, but do not treat the 37-row table as exhaustive.
