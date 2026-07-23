# WP2 teacher v124 deploy record

## Build / deploy

- Deploy timestamp: **2026-07-24 00:30:23** local (log-latch archive
  `reports/logs_archive_20260724_003023`).
- Built mod ZIP SHA-256: **`10321CBB30AE94824E6A8D57EDBBA54F8624A40FBFF3B9973D9D4CFA39809ACD`**
  (339430 bytes). Identical bytes at both installed paths:
  - `C:/Games/Steam/steamapps/workshop/content/1942280/3737864106/Tom-BrotatoAgent.zip`
  - `C:/Games/Steam/steamapps/common/Brotato/mods/Tom-BrotatoAgent.zip`
- Deployed identity: policy `teacher_v1-0.1.124-gun-wp1`, mod `0.2.32-wp2-capture`,
  capture schema hash `95B6444796A21FD44E94113B75BA2097BC381D5F72ED784F9B9A4A99DD46D951`
  (schema unchanged from v123).

## Version bump

All version bumps for v124 were already committed at HEAD `59c0989` (commit `97aff20`):
manifest `0.2.32`, controller `mod_version 0.2.32-wp2-capture`, telemetry default
`0.2.32-wp2-capture`, controller `policy_version teacher_v1-0.1.124-gun-wp1`,
telemetry `POLICY_VERSION`, and the collector identity gate
(`wp2_collect_teacher.py` POLICY_VERSION/MOD_VERSION) plus live-monitor tuples.
No repo files were edited during this deploy-and-smoke except the reports below.

## Smoke run

- Run id: **`run_1784817058_71742`**
- Result: **defeat** at wave **17**; duration 954302 ms (~15.9 min); damage taken 80.
- Summary faults: errors 0, hangs 0, illegal_actions 0.
- Clean shutdown confirmed: collector exit 0, status `complete`
  (stop_reason "target reached"), Brotato.exe stopped, `auto_start=false`
  in both collector state and `agent_config.json`.

## Audits (v124 expectations)

- Safety audit (`reports/wp2/v124_smoke_safety_audit.json/.md`): run_count 1, accepted 1,
  **violation_count 0** across every category (identity, summary, body tier/repair,
  projectile floor, sampled action, wall recovery, wall-body relief + selection,
  hard wall, loot dash, **strength**, avoidable damage). Captures 17188; event_count
  19266; waves 1-17 represented; late captures 880. Activations: body 7622,
  body-emergency 0, projectile 153, wall 564, wall-body relief 297.
  events SHA-256 `681D36B2...32A08319`, summary SHA-256 `848E8E8D...B01B1B6131`.
- Capture audit (`reports/wp2/v124_smoke_capture_audit.json/.md`): capture_count 17188,
  schema hash matches `95B6...D951`, schema_mismatches 0, invalid_actions 0,
  invalid_captures 0, malformed_lines 0, valid_transition_estimate 17188,
  near_duplicate_fraction 0.0226, damage_events 7.

## Strength diagnostics

All 17188 captures carry `build_strength` and `strength_tier` (100% coverage,
located in `teacher.contributions.finale_translation`). build_strength range
[0.477, 1.005] (never reached the strong band >=1.25). Tier fractions:
**weak 0.8575, neutral 0.1425, strong 0.0000**. The safety-audit strength gate
ran on every capture (0 violations, not inert). The all-weak/neutral profile is
consistent with a persistently offense-deficient build and the wave-17 defeat.

## v124 rule evidence (reroll-past-qualifying-offense)

The v124 guard `_board_has_gate_clearing_offense` suppresses the +8 offense-deficient
reroll boost while an affordable non-weapon item with
`_direct_offense_gain(effects) >= OFFENSE_IMPACT_MIN_ITEM_GAIN (6.0)` is on the board.
The guard is only reached inside the offense-deficient block
(`_offense_target(wave) > 0 and _offense_proxy(build) < _offense_target`), i.e. at
wave >= `MID_SHOP_PIVOT_WAVE (9)` (`LATE_SHOP_WAVE = 15`).

Per-run shop extraction (read-only over `events.jsonl`, reproducing the gd port exactly):

- Total shops 16, total rerolls 34, offense-stat items bought 13.
- **Board-level count — rerolls that fired while an affordable, gate-clearing offense
  item (direct_offense_gain >= 6.0) sat on the board: 5** (wave 6: 1, wave 11: 2,
  wave 15: 2). NOT the expected 0.
- **Guard-applicable subset (offense-deficient shop, wave >= 9): 4** (wave 11: 2,
  wave 15: 2). The wave-6 case is excluded: at wave 6 (< pivot 9) `_offense_target`
  returns 0.0, so the guard block is never evaluated.

Guard-applicable rerolls (proxy vs target confirm deficiency; buying the item was a
recorded legal alternative in every case; `can_buy` is not serialized for `category:item`
entries, so the guard's default `can_buy=true` applies):

| seq | wave | reroll_price | gold_before | offense proxy(total)/target(>=) | gate-clearing items on board (id / effect keys / direct_gain / price / affordable) |
|---|---|---:|---:|---|---|
| 11315 | 11 | 12 (paid) | 342 | 53.5 / >=95 | item_potato / [attack_speed,percent_damage] / 10.0 / 189 / true |
| 11319 | 11 | 20 (paid) | 314 | 53.5 / >=95 | item_bait / [percent_damage] / 8.0 / 57 / true; item_cyclops_worm / [percent_damage] / 12.0 / 94 / true |
| 16880 | 15 | 0 (free) | 403 | 79.3 / >=145 | item_bait / [percent_damage] / 8.0 / 69 / true |
| 16882 | 15 | 0 (free) | 403 | 79.3 / >=145 | item_dynamite / [] (explosive) / 15.0 / 58 / true |

Notes: of the 4 guard-applicable rerolls, 2 were **paid** (wave 11, reroll cost 12 and
20 gold) and 2 were **free** rerolls (wave 15, reroll_price 0). item_dynamite carries no
offense-*stat* key but clears the gate via the explosive term of `_direct_offense_gain`
(15.0). Recorded action score for the chosen reroll was low in every case (0, 0, 0, -1).
Wave 13 (4 rerolls, 1 offense-stat offer) had **no** gate-clearing item on any board at
reroll time (0 guard-applicable). The guard removes only the +8 boost; it does not
otherwise forbid a reroll, so a reroll can still fire on a gate-clearing board.

Offense-stat items bought (id / wave / direct_offense_gain): item_pumpkin/4/13.0,
item_claw_tree/5/0.0, item_sharp_bullet/6/-4.0, item_metal_detector/7/-5.0,
item_metal_detector/8/-5.0, item_coffee/8/8.0, item_pumpkin/8/13.0,
item_small_magazine/9/6.0, item_metal_plate/9/-3.0, item_alloy/10/3.0,
item_coffee/12/8.0, item_pumpkin/16/13.0, item_bandana/16/-9.0.

## Summary

Teacher v124 (`teacher_v1-0.1.124-gun-wp1`, mod `0.2.32-wp2-capture`) was deployed from a
reproducible ZIP (SHA-256 `1032...9ACD`). The single-run smoke was a wave-17 **defeat**
(damage 80, ~15.9 min) with zero telemetry/safety faults and a fully clean capture audit;
strength diagnostics present on 100% of captures with an active gate (all weak/neutral).
The v124 rule evidence is **not clean**: 5 rerolls (4 guard-applicable, at waves 11 and 15)
fired while an affordable gate-clearing offense item was on the board, versus the expected 0.
Two of the guard-applicable rerolls were paid (wave 11); two were free (wave 15). No commits made.
