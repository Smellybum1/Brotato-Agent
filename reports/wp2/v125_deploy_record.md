# WP2 teacher v125 deploy record

## Build / deploy

- Deploy timestamp: **2026-07-24 01:14:17** local.
- Built mod ZIP SHA-256:
  **`CE15D87FFE420760180E5C322358DAEF65E9C6B23923E3BECECA3B08AD075AE0`**.
- Deployed identity: policy `teacher_v1-0.1.125-gun-wp1`, mod `0.2.33-wp2-capture`,
  capture schema hash
  `95B6444796A21FD44E94113B75BA2097BC381D5F72ED784F9B9A4A99DD46D951`
  (schema unchanged from v124).
- Collector PID 22832.

## v125 change

`teacher/shop_strategy.gd` `decide_shop` now carries a **hard reroll gate**
(`offense_reroll_gate`): while offense-deficient (`_offense_target(wave) > 0` and
`_offense_proxy(build) < target`) with an affordable gate-clearing offense item on
the board (`_board_has_gate_clearing_offense`), the `shop_reroll` action is
disallowed outright — paid **and** free. The v124 approach only removed the +8
offense-deficient reroll boost; residual worth and free rerolls still preempted the
mandatory-offense buy. Buy scoring and reroll worth are otherwise untouched; if the
buy loop bought nothing, shop-exit proceeds.

## Smoke run

- Run id: **`run_1784819688_85761`**.
- Result: **defeat** at wave **16**; duration 865412 ms (~14.4 min); damage taken 125.
- Summary faults: errors 0, hangs 0, illegal_actions 0.
- Clean shutdown confirmed: collector status `complete` (target_runs 1 / completed 1,
  completed_at 2026-07-23T15:29:14Z), Brotato.exe stopped (absent from tasklist),
  `auto_start=false` in `agent_config.json`.

## Audits (v125 expectations)

- Safety audit (`reports/wp2/v125_smoke_safety_audit.json/.md`): run_count 1, accepted 1,
  **violation_count 0** across every category (identity, summary, body tier/repair,
  body diagnostic, projectile floor, sampled action, wall recovery, wall-body relief +
  selection, hard wall, loot dash, **strength**, avoidable damage). Captures 15943;
  event_count 17818; waves 1-16 represented; late captures 0. Activations: body 7628,
  body-emergency 0, projectile 0, wall recovery 0, wall-body relief 0, loot dash 733.
  events SHA-256 `EA161790...368BDE7`, summary SHA-256 `75A4BEBF...F102F3`.
- Capture audit (`reports/wp2/v125_smoke_capture_audit.json/.md`): capture_count 15943,
  schema hash matches `95B6...D951`, schema_mismatches 0, invalid_captures 0,
  invalid_actions 0, malformed_lines 0, valid_transition_estimate 15943,
  near_duplicate_fraction 0.0226, damage_events 11.

## Strength diagnostics

All 15943 captures carry `build_strength` and `strength_tier` (100% coverage, path
`teacher.contributions.finale_translation`). build_strength range **[0.608, 1.493]**
(p50 0.815, p95 1.347, max 1.493 — reached the strong band >=1.25). Tier fractions:
**weak 0.3590, neutral 0.5645, strong 0.0765**. The safety-audit strength gate ran on
every capture (0 violations, not inert). Materially stronger than v124 (weak 0.8575 /
neutral 0.1425 / **strong 0.0000**).

## v125 rule evidence (reroll-past-qualifying-offense) — DECISIVE CHECK

Per-run shop extraction, read-only over `events.jsonl`, reproducing the live gate
exactly (`_direct_offense_gain` >= `OFFENSE_IMPACT_MIN_ITEM_GAIN` 6.0; guard condition
`offense.target > 0 and offense.total < offense.target`, using the telemetry-recorded
`build_metrics.offense.target`/`.total` — the live `_offense_target`/`_offense_proxy`
values; board affordability from the serialized per-item `affordable` + `can_buy` flags).

- **Total rerolls: 25.**
- **Applicable-condition rerolls (target>0 and proxy<target): 24.** (The one excluded
  reroll is wave-1 seq 491, where target 7.78 <= proxy 7.80, so no offense-deficit
  guard applies.)
- **Rerolls-past-qualifying-with-condition: 0.** At every one of the 24 applicable
  rerolls, NO affordable gate-clearing offense item was on the board at reroll time.
  The v125 gate is never violated: the run contains zero rerolls fired while
  offense-deficient with a mandatory-offense buy available. **v125 QUALIFIES.**

### The rule working — gate-influenced non-reroll decisions (10)

Decisions where the guard condition held AND an affordable gate-clearing offense item
was on the board, and the action taken was NOT a reroll:

| seq | wave | action | bought | gate item(s) (id / gain / price) |
|---|---|---|---|---|
| 4659 | 6 | shop_buy | item_bat | item_statue / 40.0 / 102 |
| 5827 | 7 | shop_buy | item_plant | item_pumpkin / 13.0 / 75 |
| 5829 | 7 | shop_buy | **item_pumpkin** | item_pumpkin / 13.0 / 75 (bought) |
| 7115 | 8 | shop_sell | — | item_glass_cannon / 25.0 / 143; item_missile / 6.0 / 89 |
| 7117 | 8 | shop_buy | weapon_double_barrel_shotgun_1 | item_glass_cannon / 25.0; item_missile / 6.0 |
| 7119 | 8 | shop_buy | **item_missile** | item_missile / 6.0 / 89 (bought) |
| 8507 | 9 | shop_buy | **item_small_magazine** | item_small_magazine / 6.0 / 123 (bought) |
| 12673 | 12 | shop_buy | item_baby_with_a_beard | item_dynamite / 15.0 / 56 |
| 12675 | 12 | shop_go | — | item_dynamite / 15.0 / 56 |
| 14047 | 13 | shop_buy | **item_pumpkin** | item_pumpkin / 13.0 / 105 (bought) |

Four of these bought the gate-clearing offense item outright (w7 item_pumpkin, w8
item_missile, w9 item_small_magazine, w13 item_pumpkin). seq 12675 (w12) is the gate's
exit path: the reroll was blocked with item_dynamite (gain 15) still on the board, and
the shop was exited (`shop_go`) rather than rerolled past — "exiting with gold beats
losing the board". The buy-selection cases (w6 item_bat over item_statue gain 40, w8/w12
alternate buys) are outside the reroll gate's scope; the gate governs rerolls only, not
which item the buy loop selects.

### Waves 11 and 15 offer-by-offer (every board, regardless of outcome)

**Wave 11** — offense-deficient throughout (proxy 59.41 / target 116). 5 rerolls fired
(seq 11278, 11280, 11282, 11286, 11288), plus buys (item_bag, item_tree), a lock
(item_baby_with_a_beard), and shop_go. On EVERY board at every reroll, the max
`_direct_offense_gain` across affordable non-weapon items was <= 0.0 — no gate-clearing
offense item was ever present. Boards (affordable non-weapon offense gains):
- seq 11278: item_alien_worm 0.0 (weapon_sharp_tooth_2 can_buy=False). No gate item.
- seq 11280: item_scared_sausage 0.0, item_weird_food 0.0, item_little_muscley_dude 0.0. No gate item.
- seq 11282: item_cog -4.0, item_alien_baby 0.0, item_turret_flame 0.0. No gate item.
- seq 11286: item_mushroom 0.0, item_cyberball 0.0; item_baby_with_a_beard gain 1.0 but
  **not affordable** (price 221 > 211). No gate item.
- seq 11288: item_little_frog 0.0, item_fuel_tank -1.0; item_baby_with_a_beard 1.0 (not
  affordable, price 221 > 187). No gate item.

**Wave 15** — offense-deficient throughout (proxy ~76.5→74.4→67.4 / target 265). 3
rerolls fired (seq 16810, 16820, 16822), plus buys (item_glasses, weapon_smg_3,
weapon_double_barrel_shotgun_3), sells, a combine, and shop_go. On EVERY board at every
reroll the max affordable non-weapon offense gain was <= 1.0 — no gate-clearing item:
- seq 16810: item_bat 0.0 (both weapons can_buy=False). No gate item.
- seq 16820: item_padding 0.0, item_hedgehog 1.0; item_baby_with_a_beard 1.0 but **not
  affordable** (price 265 > 209). No gate item.
- seq 16822: item_cute_monkey -1.0, item_sunglasses 0.0 (crit_chance). No gate item.

No wave-11 or wave-15 reroll board carried an affordable item with
`_direct_offense_gain >= 6.0`; the highest offense gains that appeared (item_dynamite 15
at w12, item_pumpkin 13 at w7/w13, item_glass_cannon 25 / item_missile 6 at w8,
item_small_magazine 6 at w9) all occurred at **buy** decisions, where they were bought
or the shop was exited — never rerolled past.

## Summary

Teacher v125 (`teacher_v1-0.1.125-gun-wp1`, mod `0.2.33-wp2-capture`) was deployed from a
reproducible ZIP (SHA-256 `CE15...5AE0`). The single-run smoke was a wave-16 **defeat**
(damage 125, ~14.4 min) with zero telemetry/safety faults, a fully clean capture audit,
and strength diagnostics on 100% of captures with an active gate (weak 0.359 / neutral
0.565 / strong 0.077 — first run to reach the strong band). The **v125 rule evidence is
clean**: 25 rerolls, 24 guard-applicable, and **0 rerolls fired past a qualifying
affordable gate-clearing offense item** while offense-deficient — versus v124's 5. Ten
gate-influenced non-reroll decisions show the rule working (four mandatory-offense buys,
one gated shop-exit at w12). No commits made.
