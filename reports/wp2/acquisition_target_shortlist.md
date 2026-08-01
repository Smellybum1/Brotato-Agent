# Acquisition target shortlist -- `weapon_prefixes` verification for 34 gating characters

Generated 2026-08-02. Read-only analysis; no game launched, nothing deployed.

Sources: `third_party/brotatoai/src/brotato_sources/items/characters/<n>/<n>_data.tres` (each
`starting_weapons` ExtResource path resolved to that weapon's own `my_id`, never the filename);
MELEE/RANGED from the weapon `.tres` `type` field against `weapon_type.gd {MELEE=0, RANGED=1}`;
`allow_melee` from `mod/mods-unpacked/Tom-BrotatoAgent/teacher/build_profiles.gd`, default `true`
per `build_profile.gd:9`.

Current list under test: `["weapon_pistol","weapon_smg","weapon_revolver","weapon_shredder","weapon_crossbow","weapon_laser_gun","weapon_"]`

Match semantics per `run_orchestrator.gd:271` `_select_inventory_by_id_prefix` are SUBSTRING
(`id.begins_with(prefix) or id.find(prefix) >= 0`), scanned prefix-outer / inventory-inner,
first hit wins (`run_orchestrator.gd:156`).

| character | starting_weapons (ids, IN ORDER) | first entry matched | resulting weapon | MELEE/RANGED | profile `allow_melee` | VERDICT |
|---|---|---|---|---|---|---|
| bull | `[ ]` EMPTY in `bull_data.tres` | n/a | n/a | n/a | `DEFAULT(true)` | UNKNOWN -- see note |
| crazy | `weapon_knife_1, weapon_dagger_1, weapon_scissors_1, weapon_lightning_shiv_1, weapon_claw_1, weapon_shuriken_1` | `weapon_` | `weapon_knife_1` | MELEE | `DEFAULT(true)` | **NEEDS A NEW ENTRY** |
| cyborg | `weapon_wrench_1, weapon_screwdriver_1, weapon_plank_1, weapon_pistol_1, weapon_smg_1, weapon_revolver_1, weapon_double_barrel_shotgun_1, weapon_crossbow_1` | `weapon_pistol` | `weapon_pistol_1` | RANGED | `false` | OK |
| doctor | `weapon_scissors_1, weapon_medical_gun_1` | `weapon_` | `weapon_scissors_1` | MELEE | `DEFAULT(true)` | **NEEDS A NEW ENTRY** |
| engineer | `weapon_wrench_1, weapon_screwdriver_1, weapon_plank_1, weapon_hammer_2` | `weapon_` | `weapon_wrench_1` | MELEE | `DEFAULT(true)` | **NEEDS A NEW ENTRY** (melee-only character, unfixable by prefixes) |
| entrepreneur | `weapon_fist_1, weapon_hand_1, weapon_knife_1, weapon_pruner_1, weapon_dagger_1, weapon_wrench_1, weapon_pistol_1, weapon_double_barrel_shotgun_1, weapon_taser_1, weapon_wand_1, weapon_shuriken_1` | `weapon_pistol` | `weapon_pistol_1` | RANGED | `DEFAULT(true)` | OK |
| explorer | `weapon_cacti_club_1, weapon_screwdriver_1, weapon_stick_1, weapon_torch_1, weapon_chopper_1, weapon_plank_1, weapon_hatchet_1, weapon_crossbow_1, weapon_shredder_1, weapon_taser_1, weapon_wand_1` | `weapon_shredder` | `weapon_shredder_1` | RANGED | `DEFAULT(true)` | OK |
| farmer | `weapon_hand_1, weapon_spear_1, weapon_stick_1, weapon_torch_1, weapon_screwdriver_1, weapon_pruner_1, weapon_wrench_1, weapon_taser_1, weapon_wand_1, weapon_double_barrel_shotgun_1, weapon_potato_thrower_2` | `weapon_` | `weapon_hand_1` | MELEE | `DEFAULT(true)` | **NEEDS A NEW ENTRY** |
| fisherman | `weapon_knife_1, weapon_rock_1, weapon_spear_1, weapon_fighting_stick_1, weapon_screwdriver_1, weapon_spiky_shield_1, weapon_torch_1, weapon_stick_1, weapon_pistol_1, weapon_smg_1, weapon_crossbow_1, weapon_double_barrel_shotgun_1, weapon_laser_gun_1, weapon_revolver_1, weapon_shredder_1, weapon_slingshot_1` | `weapon_pistol` | `weapon_pistol_1` | RANGED | `DEFAULT(true)` | OK |
| generalist | `weapon_cacti_club_1, weapon_ghost_axe_1, weapon_lightning_shiv_1, weapon_knife_1, weapon_spear_1, weapon_shuriken_1, weapon_double_barrel_shotgun_1, weapon_pistol_1, weapon_smg_1, weapon_revolver_1, weapon_laser_gun_1, weapon_slingshot_1` | `weapon_pistol` | `weapon_pistol_1` | RANGED | `DEFAULT(true)` | OK |
| gladiator | `weapon_spear_1, weapon_jousting_lance_1, weapon_cacti_club_1, weapon_torch_1, weapon_dagger_1, weapon_knife_1, weapon_plank_1, weapon_ghost_axe_1, weapon_ghost_flint_1, weapon_fist_1, weapon_claw_1, weapon_fighting_stick_1` | `weapon_` | `weapon_spear_1` | MELEE | `DEFAULT(true)` | **NEEDS A NEW ENTRY** (melee-only character, unfixable by prefixes) |
| glutton | `weapon_pruner_1, weapon_chopper_1, weapon_dagger_1, weapon_fist_1, weapon_hatchet_1, weapon_jousting_lance_1, weapon_screwdriver_1, weapon_plank_1, weapon_shredder_1` | `weapon_shredder` | `weapon_shredder_1` | RANGED | `DEFAULT(true)` | OK |
| golem | `weapon_cacti_club_1, weapon_chopper_1, weapon_fist_1, weapon_ghost_axe_1, weapon_hatchet_1, weapon_knife_1, weapon_plank_1, weapon_rock_1, weapon_spiky_shield_1, weapon_stick_1, weapon_torch_1, weapon_pistol_1, weapon_revolver_1, weapon_slingshot_1` | `weapon_pistol` | `weapon_pistol_1` | RANGED | `DEFAULT(true)` | OK |
| lich | `weapon_scissors_1, weapon_chopper_1, weapon_dagger_1, weapon_stick_1, weapon_knife_1, weapon_ghost_flint_1, weapon_pruner_1, weapon_hatchet_1, weapon_ghost_scepter_1, weapon_medical_gun_1, weapon_smg_1, weapon_wand_1, weapon_slingshot_1, weapon_crossbow_1` | `weapon_smg` | `weapon_smg_1` | RANGED | `DEFAULT(true)` | OK |
| loud | `weapon_cacti_club_1, weapon_ghost_axe_1, weapon_ghost_flint_1, weapon_lightning_shiv_1, weapon_dagger_1, weapon_claw_1, weapon_spear_1, weapon_torch_1, weapon_rock_1, weapon_hatchet_1, weapon_plank_1, weapon_wrench_1, weapon_jousting_lance_1, weapon_fighting_stick_1, weapon_pruner_1, weapon_double_barrel_shotgun_1, weapon_pistol_1, weapon_smg_1, weapon_revolver_1, weapon_shredder_1, weapon_taser_1, weapon_wand_1, weapon_shuriken_1, weapon_slingshot_1, weapon_crossbow_1` | `weapon_pistol` | `weapon_pistol_1` | RANGED | `DEFAULT(true)` | OK |
| lucky | `weapon_stick_1, weapon_rock_1, weapon_fist_1, weapon_chopper_1, weapon_plank_1, weapon_screwdriver_1, weapon_slingshot_1, weapon_wand_1` | `weapon_` | `weapon_stick_1` | MELEE | `DEFAULT(true)` | **NEEDS A NEW ENTRY** |
| old | `weapon_scissors_1, weapon_screwdriver_1, weapon_wrench_1, weapon_rock_1, weapon_plank_1, weapon_chopper_1, weapon_pruner_1, weapon_double_barrel_shotgun_1, weapon_taser_1, weapon_wand_1` | `weapon_` | `weapon_scissors_1` | MELEE | `DEFAULT(true)` | **NEEDS A NEW ENTRY** |
| one_arm | `weapon_fist_1, weapon_claw_1, weapon_dagger_1, weapon_ghost_axe_1, weapon_ghost_flint_1, weapon_lightning_shiv_1, weapon_scissors_1, weapon_cacti_club_1, weapon_torch_1, weapon_plank_1, weapon_screwdriver_1, weapon_hatchet_1, weapon_chopper_1, weapon_pruner_1, weapon_jousting_lance_1, weapon_double_barrel_shotgun_1, weapon_laser_gun_1, weapon_pistol_1, weapon_shredder_1, weapon_smg_1, weapon_taser_1, weapon_revolver_1, weapon_wand_1, weapon_shuriken_1, weapon_slingshot_1, weapon_crossbow_1` | `weapon_pistol` | `weapon_pistol_1` | RANGED | `false` | OK |
| pacifist | `weapon_hand_1, weapon_taser_1, weapon_spiky_shield_1, weapon_pruner_1` | `weapon_` | `weapon_hand_1` | MELEE | `DEFAULT(true)` | **NEEDS A NEW ENTRY** |
| renegade | `weapon_pistol_1, weapon_revolver_1, weapon_shredder_1, weapon_smg_1, weapon_laser_gun_1, weapon_medical_gun_1, weapon_double_barrel_shotgun_1, weapon_taser_1, weapon_wand_1, weapon_ghost_scepter_1, weapon_crossbow_1` | `weapon_pistol` | `weapon_pistol_1` | RANGED | `false` | OK |
| sick | `weapon_fist_1, weapon_hand_1, weapon_scissors_1, weapon_lightning_shiv_1, weapon_ghost_scepter_1, weapon_slingshot_1, weapon_smg_1, weapon_medical_gun_1` | `weapon_smg` | `weapon_smg_1` | RANGED | `DEFAULT(true)` | OK |
| streamer | `weapon_rock_1, weapon_fist_1, weapon_claw_1, weapon_stick_1, weapon_fighting_stick_1, weapon_cacti_club_1, weapon_ghost_flint_1, weapon_ghost_axe_1, weapon_knife_1, weapon_lightning_shiv_1, weapon_scissors_1, weapon_screwdriver_1, weapon_wrench_1, weapon_spear_1, weapon_plank_1, weapon_pruner_1, weapon_jousting_lance_1, weapon_spiky_shield_1, weapon_crossbow_1, weapon_double_barrel_shotgun_1, weapon_laser_gun_1, weapon_medical_gun_1, weapon_pistol_1, weapon_shredder_1, weapon_smg_1, weapon_revolver_1, weapon_taser_1, weapon_wand_1, weapon_slingshot_1` | `weapon_pistol` | `weapon_pistol_1` | RANGED | `DEFAULT(true)` | OK |
| apprentice | `weapon_fist_1, weapon_knife_1, weapon_lightning_shiv_1, weapon_cacti_club_1, weapon_fighting_stick_1, weapon_ghost_flint_1, weapon_ghost_axe_1, weapon_hatchet_1, weapon_torch_1, weapon_plank_1, weapon_pruner_1, weapon_screwdriver_1, weapon_wrench_1, weapon_pistol_1, weapon_smg_1, weapon_double_barrel_shotgun_1, weapon_shredder_1, weapon_slingshot_1, weapon_taser_1, weapon_shuriken_1, weapon_ghost_scepter_1` | `weapon_pistol` | `weapon_pistol_1` | RANGED | `DEFAULT(true)` | OK |
| brawler | `weapon_fist_1, weapon_hand_1, weapon_claw_1` | `weapon_` | `weapon_fist_1` | MELEE | `DEFAULT(true)` | **NEEDS A NEW ENTRY** (melee-only character, unfixable by prefixes) |
| chunky | `weapon_hand_1, weapon_fist_1, weapon_cacti_club_1, weapon_rock_1, weapon_stick_1, weapon_torch_1, weapon_plank_1, weapon_chopper_1, weapon_pruner_1, weapon_spiky_shield_1, weapon_double_barrel_shotgun_1, weapon_ghost_scepter_1, weapon_shredder_1` | `weapon_shredder` | `weapon_shredder_1` | RANGED | `DEFAULT(true)` | OK |
| demon | `weapon_dagger_1, weapon_lightning_shiv_1, weapon_ghost_axe_1, weapon_ghost_flint_1, weapon_torch_1, weapon_chopper_1, weapon_ghost_scepter_1, weapon_wand_1, weapon_taser_1` | `weapon_` | `weapon_dagger_1` | MELEE | `DEFAULT(true)` | **NEEDS A NEW ENTRY** |
| hunter | `weapon_cacti_club_1, weapon_dagger_1, weapon_spear_1, weapon_claw_1, weapon_shuriken_1, weapon_crossbow_1` | `weapon_crossbow` | `weapon_crossbow_1` | RANGED | `false` | OK |
| king | `weapon_fist_2, weapon_circular_saw_2, weapon_knife_2, weapon_hatchet_2, weapon_ghost_axe_2, weapon_lightning_shiv_2, weapon_torch_2, weapon_plank_2, weapon_spear_2, weapon_sword_2, weapon_hammer_2, weapon_spiky_shield_2, weapon_pistol_2, weapon_smg_2, weapon_crossbow_2, weapon_double_barrel_shotgun_2, weapon_taser_2` | `weapon_pistol` | `weapon_pistol_2` | RANGED | `DEFAULT(true)` | OK |
| knight | `weapon_sword_2, weapon_hammer_2, weapon_spear_2, weapon_torch_2, weapon_jousting_lance_2, weapon_spiky_shield_2` | `weapon_` | `weapon_sword_2` | MELEE | `DEFAULT(true)` | **NEEDS A NEW ENTRY** (melee-only character, unfixable by prefixes) |
| mage | `weapon_wand_1, weapon_torch_1, weapon_plank_1, weapon_taser_1, weapon_lightning_shiv_1, weapon_smg_1, weapon_double_barrel_shotgun_1` | `weapon_smg` | `weapon_smg_1` | RANGED | `DEFAULT(true)` | OK |
| masochist | `weapon_rock_1, weapon_scissors_1, weapon_cacti_club_1, weapon_ghost_axe_1, weapon_spiky_shield_1, weapon_double_barrel_shotgun_1, weapon_ghost_scepter_1, weapon_medical_gun_1, weapon_wand_1` | `weapon_` | `weapon_rock_1` | MELEE | `DEFAULT(true)` | **NEEDS A NEW ENTRY** |
| multitasker | `weapon_cacti_club_1, weapon_fist_1, weapon_claw_1, weapon_knife_1, weapon_spear_1, weapon_stick_1, weapon_fighting_stick_1, weapon_lightning_shiv_1, weapon_screwdriver_1, weapon_wrench_1, weapon_ghost_axe_1, weapon_plank_1, weapon_chopper_1, weapon_hatchet_1, weapon_jousting_lance_1, weapon_pruner_1, weapon_spiky_shield_1, weapon_double_barrel_shotgun_1, weapon_pistol_1, weapon_smg_1, weapon_revolver_1, weapon_laser_gun_1, weapon_wand_1, weapon_slingshot_1, weapon_taser_1, weapon_shuriken_1, weapon_crossbow_1` | `weapon_pistol` | `weapon_pistol_1` | RANGED | `DEFAULT(true)` | OK |
| soldier | `weapon_knife_1, weapon_crossbow_1, weapon_double_barrel_shotgun_1, weapon_laser_gun_1, weapon_pistol_1, weapon_shredder_1, weapon_revolver_1, weapon_smg_1, weapon_taser_1, weapon_wand_1` | `weapon_pistol` | `weapon_pistol_1` | RANGED | `false` | OK |
| wildling | `weapon_stick_1, weapon_spear_1, weapon_torch_1, weapon_rock_1, weapon_cacti_club_1, weapon_hatchet_1, weapon_fighting_stick_1, weapon_slingshot_1` | `weapon_` | `weapon_stick_1` | MELEE | `DEFAULT(true)` | **NEEDS A NEW ENTRY** |

Already-verified four, re-derived here independently:

| character | starting_weapons (ids, IN ORDER) | first entry matched | resulting weapon | MELEE/RANGED | `allow_melee` |
|---|---|---|---|---|---|
| artificer | `weapon_plank_1, weapon_screwdriver_1, weapon_wrench_1, weapon_shredder_1` | `weapon_shredder` | `weapon_shredder_1` | RANGED | `false` |
| ranger | `weapon_pistol_1, weapon_smg_1, weapon_revolver_1, weapon_laser_gun_1, weapon_shredder_1, weapon_crossbow_1` | `weapon_pistol` | `weapon_pistol_1` | RANGED | `false` |
| mutant | `weapon_cacti_club_1, weapon_ghost_axe_1, weapon_stick_1, weapon_fighting_stick_1, weapon_rock_1, weapon_plank_1, weapon_double_barrel_shotgun_1, weapon_smg_1, weapon_revolver_1, weapon_shredder_1, weapon_taser_1, weapon_wand_1, weapon_crossbow_1` | `weapon_smg` | `weapon_smg_1` | RANGED | `DEFAULT(true)` |
| arms_dealer | `weapon_pistol_1` | `weapon_pistol` | `weapon_pistol_1` | RANGED | `DEFAULT(true)` |

## Findings

- **Zero DEFECT rows.** All nine profiles that carry `allow_melee: false` (`ranger, soldier, artificer,
  renegade, saver, wounded, cyborg, hunter, one_arm` -- the complete set in `build_profiles.gd`) already
  resolve to a RANGED weapon within the first six entries. Every character that falls through to the bare
  `weapon_` fallback sits at the DEFAULT `allow_melee: true`. The Artificer-plank failure mode is therefore
  not currently reproduced by any of the 34.
- **13 NEEDS A NEW ENTRY rows** (bare fallback reached): crazy, doctor, engineer, farmer, gladiator, lucky,
  old, pacifist, brawler, demon, knight, masochist, wildling.
- **9 of those 13 do have a ranged starting option** the list simply does not name:
  crazy `shuriken`; doctor `medical_gun`; farmer `taser / wand / double_barrel_shotgun / potato_thrower_2`;
  lucky `slingshot / wand`; old `double_barrel_shotgun / taser / wand`; pacifist `taser` (ONLY);
  demon `ghost_scepter / wand / taser`; masochist `double_barrel_shotgun / ghost_scepter / medical_gun / wand`;
  wildling `slingshot` (ONLY).
- **4 are melee-only and cannot be fixed by any prefix**: engineer, gladiator, brawler, knight. No RANGED
  entry exists anywhere in their `starting_weapons`. They are safe today only because their profiles permit
  melee. If any of those four profiles ever gains `allow_melee: false`, it becomes an instant DEFECT with no
  prefix remedy.
- **bull** has `starting_weapons = [ ]` -- literally empty in `bull_data.tres`. Nothing is statically
  resolvable; what STARTING_WEAPON_SELECT actually offers must be read back live. Not guessed here.

## Proposed list

Minimal cover of all 9 fixable rows: **4 new entries**, all inserted AFTER `weapon_laser_gun` and BEFORE the
bare `weapon_`.

```
["weapon_pistol","weapon_smg","weapon_revolver","weapon_shredder","weapon_crossbow","weapon_laser_gun",
 "weapon_medical_gun","weapon_slingshot","weapon_shuriken","weapon_taser","weapon_"]
```

**Why that position.** The loop is prefix-outer and first-hit-wins, so an entry inserted strictly after
position 6 cannot steal a match from any character that already hits within the first six. Every currently-OK
row is invariant by construction. Inserting any of these before position 6 would not be safe and was not
considered.

**Why exactly these four, and why no fewer.** Four are forced by characters with a single ranged option:
pacifist -> `taser`, wildling -> `slingshot`, crazy -> `shuriken`, doctor -> `medical_gun`. Those same four
then cover the remaining five: farmer / old / demon via `taser`, lucky via `slingshot`, masochist via
`medical_gun`. Four is the exact minimum.

**Relative order among the four is unconstrained for correctness** -- no character's inventory contains two of
`{medical_gun, slingshot, shuriken, taser}` where the choice would matter for the DEFECT/OK verdict, since all
four are RANGED.

### Recommended quality variant (6 new entries)

`taser` and `slingshot` are weak. Naming `double_barrel_shotgun` and `wand` ahead of `taser` gives
farmer / old / masochist a shotgun and demon a wand, for two extra entries:

```
["weapon_pistol","weapon_smg","weapon_revolver","weapon_shredder","weapon_crossbow","weapon_laser_gun",
 "weapon_double_barrel_shotgun","weapon_medical_gun","weapon_slingshot","weapon_shuriken","weapon_wand",
 "weapon_taser","weapon_"]
```

Here order among the new entries DOES matter: `weapon_double_barrel_shotgun` first so masochist / farmer / old
take the shotgun; `weapon_medical_gun` before `weapon_wand`/`weapon_taser` so doctor is unambiguous;
`weapon_wand` before `weapon_taser` so demon takes the wand. This is a weapon-quality preference, not a
correctness requirement.

## Re-verification against all 38 characters

Both proposed lists were re-run over all 34 candidates plus the 4 already-verified characters. Exactly 9 rows
change, all of them intended fallback rows, all MELEE -> RANGED:

| character | before | after (minimal) | after (recommended) |
|---|---|---|---|
| crazy | `weapon_knife_1` MELEE | `weapon_shuriken_1` RANGED | `weapon_shuriken_1` RANGED |
| doctor | `weapon_scissors_1` MELEE | `weapon_medical_gun_1` RANGED | `weapon_medical_gun_1` RANGED |
| farmer | `weapon_hand_1` MELEE | `weapon_taser_1` RANGED | `weapon_double_barrel_shotgun_1` RANGED |
| lucky | `weapon_stick_1` MELEE | `weapon_slingshot_1` RANGED | `weapon_slingshot_1` RANGED |
| old | `weapon_scissors_1` MELEE | `weapon_taser_1` RANGED | `weapon_double_barrel_shotgun_1` RANGED |
| pacifist | `weapon_hand_1` MELEE | `weapon_taser_1` RANGED | `weapon_taser_1` RANGED |
| demon | `weapon_dagger_1` MELEE | `weapon_taser_1` RANGED | `weapon_wand_1` RANGED |
| masochist | `weapon_rock_1` MELEE | `weapon_medical_gun_1` RANGED | `weapon_double_barrel_shotgun_1` RANGED |
| wildling | `weapon_stick_1` MELEE | `weapon_slingshot_1` RANGED | `weapon_slingshot_1` RANGED |

**The four already-verified characters are UNCHANGED under both lists:**

| character | matched entry | weapon | changed? |
|---|---|---|---|
| artificer | `weapon_shredder` | `weapon_shredder_1` | no |
| ranger | `weapon_pistol` | `weapon_pistol_1` | no |
| mutant | `weapon_smg` | `weapon_smg_1` | no |
| arms_dealer | `weapon_pistol` | `weapon_pistol_1` | no |

All 25 other unchanged rows also resolve identically to the current list.

Still on the bare fallback after the fix: engineer, gladiator, brawler, knight (melee-only, harmless while
their profiles permit melee) and bull (empty `starting_weapons`, needs a live readback before it is run).
