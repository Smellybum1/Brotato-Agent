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

Arms Dealer → Artificer → Jack. Re-verify the pool fingerprint after each, and treat any change in
`items` other than **+1 per win** as a defect to investigate before continuing.

## 9. First action when the D5 baseline completes

1. Confirm `.tmp/d5_campaign_v261/report.json` exists; disarm `auto_start`.
2. Bump to `0.2.62` (four code sites + three pin tests **in the same edit**), run the suite, deploy.
3. Set config AFTER deploying — `deploy_mod.py` rewrites `agent_config.json` wholesale and reset
   `danger` to 0 last time. Read back from disk before launching.
4. Smoke ONE attempt and verify `character_ok == true` and a populated `unlock_pool` **before**
   committing to the campaign. A flag's self-report proves delivery, not correctness.
