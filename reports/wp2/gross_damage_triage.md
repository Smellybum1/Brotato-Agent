# Triage: which past conclusions rested on gross `damage_taken`?

**Item 5 of `reports/wp2/NEXT_SESSION_PLAN.md`.** No gameplay was run, no analysis was
re-run, no number below was re-derived. This is a classification pass over the existing
verdict documents.

`damage_taken` is a GROSS counter: it sums `player_damage` and never subtracts healing.
`hp_endpoints_recompute.md` §3 confirms this to the unit — **368/368 kept runs reproduce
`summary.damage_taken` exactly by summing `player_damage` alone, with no healing term
anywhere** — and §7 measures full-run healing spread at **min 0, median 72, max 288 (n=40)**.

## The triage rule (from the plan)

> Did the decision depend on gross damage, **AND** could the treatment plausibly have
> shifted healing, consumable pickup, lifesteal, or willingness to spend HP?

Both halves must be true. If either fails, the defect is a wash between arms.

---

## Summary table

| document | treatment | endpoint | verdict | n | classification | re-adjudicable offline? |
|---|---|---|---|---|---|---|
| `co_rotate_eval_verdict.md` | `finale_co_rotate` steering term, weight 0.50 (both arms pivot-fix ON) | **gross damage taken, PRIMARY, predeclared** | NOT CONFIRMED (null); mean paired diff **−3.05**, Wilcoxon **W=7.0, p=0.1484** | 128 trials, 8 fixtures x 8 x 2 arms (127 valid) | **AT RISK** | **YES — free.** 127/127 run dirs present |
| `campaign_sizing.md` | n/a (sizing guidance) | **gross damage taken** — SDs taken from the co-rotation control arm | sizing table: 32 detects 19 dmg, 64 detects 13, 128 detects 9; control mean ~20.7 | 64 control trials, 8 fixtures | **AT RISK** (already superseded by the plan) | **YES — free**, same 64 runs |
| `timescale_equivalence_verdict.md` | `time_scale` 8.0x vs 1.0x | gross damage (paired) **plus** victories and zero-damage trials | **FAIL**; damage +23.16 CI [+10.53,+35.78]; **victories 32/32 → 26/32, Fisher p=0.024**; zero-damage 16/32 → 6/32, p=0.017; sign test p=0.0009 | 64 trials, 32 pairs | **STANDS** — second half of the rule is moot because the verdict is independently carried by terminal survival | YES (96+64 runs present) but not needed |
| `timescale_doseresponse_verdict.md` | `time_scale` 2.0x and 4.0x vs 1.0x | **gross damage (paired), primary**; a loss clause as a secondary | **2.0x EQUIVALENT** (−2.66, CI [−13.42,+8.10], **32/32 victories in both arms** so the loss clause never fired); 4.0x INCONCLUSIVE (+7.56, 28/32) | 96 trials, 32 pairs per comparison | **UNDECIDABLE FROM THE RECORD** | **YES — free.** 96/96 run dirs present |
| `pivot_fix_qualification_verdict.md` | `finale_pivot_projectiles` | **victory rate** (damage reported descriptively: 67.2 → 23.2 mean) | **PASS**, 22/32 = 0.688 → 32/32 = 1.000, one-sided Fisher **p = 0.000426**; structural readback 0 vs 326,151 rotating-projectile observations | 64 trials, 8 fixtures x 4 x 2 | **STANDS** (explicitly excluded by the plan) | n/a |
| `finale_v2_eval_verdict.md` | `finale_v2` heading-selection controller | **win rate**, paired by build | PROMISING BUT NOT ESTABLISHED; +0.1875, bootstrap [0.0375,0.35], **Wilcoxon p=0.125**, Fisher p=0.1024 | 146 trials | **STANDS** | n/a |
| `finale_v2_confirmation_verdict.md` | same | **win rate** | **NOT CONFIRMED**, effect reversed: 40/64 = 0.625 vs 45/64 = 0.7031, **−0.0781**, Fisher p=0.4543 | 128 trials, 128/128 valid | **STANDS** | n/a |
| `finale_rate_test_verdict.md` | `finale_rate_full` (20 Hz → 60 Hz on wave 20) | **win rate** | **NOT SHOWN**, 39/64 = 0.6094 vs 41/63 = 0.6508, −0.0414, Fisher p=0.7140, tight CI [−0.1250,+0.0312] | 128 trials, 127 valid | **STANDS** | n/a |
| `f2/f2_verdict.md` | deterministic pi4 residual vs pure teacher | hierarchical **victory > combat progress > alive-and-healthy HP-ratio AUC** | **NULL**; P(P outranks T) = **0.4500**, CI [0.2725, 0.6350]; victory 0.3500 vs 0.5000 | 40 runs (20 per arm) | **STANDS** | n/a |
| `residual_checkpoint_verdict.md` | learned combat residual (theta 5°) vs matched random probe | predeclared surface = **damage rate (gross, per-tick)** AND wave outcomes | **NULL**, gate not passed; overall damage rate **+0.00004 [−0.00002,+0.00010]**, wave-20 **−0.00039 [−0.00171,+0.00076]**; victory +0.238 [−0.262,+0.714] | **7 learned vs 6 control runs** | **AT RISK** | **YES — free**; `learned_run_ids` / `control_run_ids` are in `residual_checkpoint_compare_v1.json` |
| `item_ledger_v122_campaign.md`, "Defensive items" | item purchase (observational, wave-matched) | **gross "player damage taken per wave"**, stated KPI | per-item verdicts: `plant` −2.070 and `acid` −4.457 "beats baseline"; `helmet` +4.988, `leather_vest` +5.730, `padding` +5.657, `wheelbarrow` +14.897 "below baseline"; many "mixed / null" | n_buys **1 to 9** per item; 19 items | **AT RISK** | **YES — free** for the damage side; the healing side needs the same HP-delta reconstruction |
| `ring_radius_eval_protocol.md` | `finale_ring_radius` (+ co-rotation) | gross damage taken (predeclared) | **NO VERDICT EXISTS.** Campaign abandoned; 67 trials sit in `.tmp/abandoned_ring_radius/` | 67 trials (36 control / 32 treatment lines, 67 with run ids) | **no conclusion to triage** | data present, 67/67 run dirs |
| `winrate_history_verdict.md` | version eras (observational) | **win rate** | peak 92/132 = 69.7%; v84-103 12/53 = 22.6% (−47.1 pp, p=8.9e-09); v104-128 41/76 = 53.9% | 642 archived attempts | **STANDS** | n/a |
| `shop_conversion_verdict.md`, `shop_scorer_migration_gate_verdict.md` | shop scorer / conversion | gold, offense score, decision-flip counts | conversion exhausted / gate does not clear | 20 F2 teacher runs | **STANDS** | n/a |
| wave-17 series (`wave17_conclusion.md`, `wave17_v2_rescue_result.md`, `wave17_min_dose_prereg_v4.md`, `landmark_continuation_pilot.md`) | `enemy_scaling` dose; human movement handover | **wave-17 survival / terminal win** | v2 `NEAR_TOTAL_RESCUE` 7/64 vs 0/64, p=0.0066; v4 `MIN_DOSE_ABOVE_25%`; human 5/5 vs 4/21, p=0.0019 | 232 dose trials + 21/5 handover | **STANDS** | n/a |
| `loss_budget_after_the_fix.md`, `fullrun_derivation_corrected.md` | n/a (accounting) | **win/loss shares by `last_wave`** | 0.284 die before w20, 0.320 at w20, 0.396 win; projected win 0.577 | 197 WP2-era full runs | **STANDS** | n/a |
| `materials_collection_analysis.md`, `v122_campaign_strength_drivers.md`, `finale_baseline_0.1.128.md` | none — observational/descriptive | gross damage shares and correlations | e.g. "wave 20 is 3.3% of ticks but **45.4% of all damage taken**"; `corr(median late-S, total damage taken) = −0.62`; baseline median damage 52.5 | 20-ish runs / v122 campaign / baseline set | **STANDS** as descriptive (see caveat below) | n/a |

**Nothing outside `reports/wp2/` reached a verdict on damage taken.** The `reports/*.md`
top-level material is WP1 gate logs and `batch_overnight_*` run tables; those report
per-run damage as a column but their conclusions are win-rate conclusions.

---

## Per-item reasoning

### AT RISK

#### 1. Co-rotation eval — the most important entry in this table

Both halves of the rule are true, and this is the dangerous shape the plan warned about:
**a null on a treatment that could have moved healing.**

- *Half 1 — decision depended on gross damage.* The protocol fixed it in advance and said
  so explicitly: "Damage taken is continuous and has visible spread… Win rate is recorded
  as a SECONDARY metric and is explicitly NOT the decision variable." Win rate could not
  adjudicate: **control 64/64 = 1.000, treatment 62/63 = 0.984** — pinned at ceiling, by
  design.
- *Half 2 — the treatment could plausibly move healing.* Co-rotation is a **steering**
  change; it alters the agent's path around the arena for the whole wave. That changes
  which `consumable_fruit` drops it walks over, and it changes engagement geometry and
  therefore kill rate, which drives **lifesteal** (a live stat: the player payload carries
  `lifesteal` and `hp_regeneration` per capture). A path change is exactly the class of
  treatment that moves healing without anyone intending it to.

The observed direction is **−3.05 damage, p=0.1484, 6/8 fixtures favouring treatment**.
If the treatment also recovered less (or more) HP than the control, the net-damage
difference is not −3.05. At an effect this small relative to measured healing (a single
wave-20 control trial spot-checked below healed 63 HP against 102 gross), the net endpoint
can plausibly sit on either side of the gross one.

**The verdict document forbids re-analysis** ("do not re-analyse with a different metric —
all three are optional stopping"). That prohibition was written against *outcome-shopping*,
not against *repairing a defective instrument*. Re-adjudication on net damage or on
death-adjusted HP-deficit AUC is a different act from picking a friendlier metric, but it
must be **predeclared before the numbers are computed**, or it becomes exactly the thing
the prohibition names.

#### 2. Campaign sizing

Its variance components — between-fixture SD **20.7**, within-fixture SD **18.8**, control
mean **~20.7** — are all gross-damage quantities taken from the co-rotation control arm. The
sizing table converts them to detectable effects (32 → 19 dmg, 64 → 13, 128 → 9). If the
endpoint changes, the SD changes and the whole table is void. The plan already records this
("the 32/64/128 sizing table does NOT transfer"); it is listed here for completeness.

The one part that survives the endpoint change is the **structural** conclusion — precision
depends on F x k, so spend on more fixtures — and `hp_endpoints_recompute.md` §9
independently reproduces it on the new endpoint (**92.5% of wave-17 variance and 82.0% of
wave-20 variance is BETWEEN source states**).

#### 3. Residual checkpoint verdict

- *Half 1.* The predeclared gate required the learned residual to beat the random control
  "on damage taken and wave outcomes". Three of the five reported metrics are gross damage
  rates.
- *Half 2.* The treatment perturbs the movement command by up to 5°, continuously, for the
  whole run. Same argument as co-rotation: different path, different pickups, different
  engagement geometry, different lifesteal.

Two things soften it. The gate was **conjunctive** — the wave-outcome half was null too
(victory +0.238 [−0.262, +0.714]) — so a repaired damage endpoint alone does not obviously
flip the verdict. And **n = 7 vs 6 runs** is small enough that nothing here was ever going
to resolve. But it is a NULL on a path-changing treatment scored partly on gross damage,
so it belongs in this bucket rather than in STANDS.

#### 4. Item ledger — defensive items

This is the clearest case in the whole triage, and it is worse than the general defect.

- *Half 1.* The KPI is stated outright: "player damage taken per wave (lower better)".
- *Half 2.* The treatments **are** healing items. `plant`, `mushroom`, `fresh_meat`,
  `extra_stomach`, `alien_worm`, `shady_potion`, `weird_food` and `acid` are HP / regen /
  lifesteal / max-HP items. An item that grants regeneration does not reduce the
  `player_damage` sum at all — it changes what the damage costs. Scoring it on gross damage
  measures the wrong quantity by construction, and a regen item can score as "mixed / null"
  while being straightforwardly good.

Note the per-item n: **1 to 9 buys**. Several verdicts rest on a single purchase
(`alien_magic` −11.589 from n=1, `weird_food` +41.643 from n=1). The document already
labels those INSUFFICIENT and already warns the wave-matched baseline "controls difficulty
but not build/skill selection into buying defense". The gross-damage defect is a third
problem on top of two acknowledged ones.

### UNDECIDABLE FROM THE RECORD

#### 5. Time-scale dose-response — the 2.0x equivalence claim

Half 1 is unambiguously true: **2.0x was declared EQUIVALENT on a paired gross-damage CI**
(−2.66, [−13.42, +8.10] against a ±19 margin), and the terminal endpoint carried no
information because **both arms went 32/32**. The whole verdict is the damage CI.

Half 2 cannot be settled from the record, because **the verdict document states the
mechanism of acceleration damage is UNIDENTIFIED** — it refutes decision starvation,
orbiter velocity inflation, and real-time gates, and then says "Do not record a cause". An
unidentified mechanism cannot be argued to leave healing alone. Naively, healing should be
a wash: regen and lifesteal accrue in game time, and both arms play the same game seconds.
But the verdict also records a live real-time defect at `agent_controller.gd:928-930`
inflating `measured_vx/vy` ~6.2x under acceleration, which is evidence that the real-time
/ game-time boundary is not clean in this build. I am not willing to assert either way.

**The single piece of evidence that settles it:** per-trial reconstructed healing in the
1.0x and 2.0x arms of `.tmp/ts_dose/{s1,s2}.jsonl`. If healing does not differ between
arms, the equivalence verdict stands unchanged. This matters operationally — 2.0x
acceleration is currently APPROVED for all paired fixture campaigns on the strength of this
one CI.

This is the entry I would check first after co-rotation, because it is the one whose
failure would silently contaminate future campaigns rather than one past verdict.

### STANDS

- **Pivot fix** — half 1 fails. The endpoint is victory rate (0.688 → 1.000, p = 0.000426)
  with a structural readback (0 rotating projectiles in 245,057 control observations vs
  326,151 in 617,798 treatment observations). Damage 67.2 → 23.2 is descriptive. Confirmed
  unaffected, not reopened, as the plan directs.
- **Finale v2 (both campaigns), finale rate test** — half 1 fails; the endpoint is win rate.
  `damage_taken` appears only as a SECONDARY freeze detector.
  **One narrow caveat:** the v2 eval's sub-claim "v2 is **not** freezing or turtling —
  `stationary_frac` 0, damage taken unchanged" leans on gross damage at the median (64 in
  both arms). The `stationary_frac` = 0 half of that claim is untouched and is the stronger
  half, so the conclusion survives on the other leg.
- **Stage F2** — half 1 fails. The endpoint is hierarchical victory > combat progress >
  **alive-and-healthy HP-ratio AUC**, and that AUC is an HP-*state* integral, which is net
  of healing by construction — it is the same family as the replacement endpoint now being
  adopted. This one was already right.
- **Time-scale 8x equivalence** — half 1 fails in the sense that matters: the FAIL verdict
  is carried independently by terminal survival (**32/32 → 26/32, Fisher p = 0.024**) and by
  zero-damage trial counts. Even if the +23.16 damage figure is inflated or deflated by a
  healing difference, the arm that lost 6 runs lost 6 runs. The *magnitude* ("+105% damage")
  is a gross figure and should be quoted as such, but the decision is safe.
- **Wave-17 series and landmark continuation** — half 1 fails; endpoints are wave-17
  survival and terminal win throughout.
- **Win-rate history, shop verdicts, loss budget, full-run derivation** — half 1 fails;
  endpoints are win rate, gold/score, and outcome shares.
- **Descriptive documents** (`materials_collection_analysis.md`,
  `v122_campaign_strength_drivers.md`, `finale_baseline_0.1.128.md`) — half 2 fails: there
  is no treatment, so there is no pair of arms for the defect to differ between. **Caveat
  worth carrying:** their gross-damage statements should be read as gross. "Wave 20 is 3.3%
  of ticks but 45.4% of all damage taken" is a statement about where the *hits* land, not
  about where HP is *lost net*; healing between waves 1-19 is exactly the term that is
  missing. It does not overturn the conclusion (wave 20 really is where the damage lands)
  but it does mean the 45.4% is an upper bound on wave 20's share of net HP cost only if
  healing is uniform across waves, which nobody has checked.

---

## Re-adjudication cost — the operative answer

**Everything marked AT RISK or UNDECIDABLE can be re-adjudicated from the existing archive
with no new gameplay.** Verified, not assumed:

1. **Every campaign's raw jsonl carries a per-trial `run_id`** joining it to the run
   archive. Checked coverage against
   `C:\Users\moxhe\AppData\Roaming\Brotato\brotato_agent\runs\`:

   | campaign | trials in jsonl | run dirs present |
   |---|---:|---:|
   | `.tmp/co_rotate` | 127 | **127** |
   | `.tmp/pivot_qual` | 64 | **64** |
   | `.tmp/ts_dose` | 96 | **96** |
   | `.tmp/abandoned_ring_radius` | 67 | **67** |

   The jsonl lines also carry the arm directly (all eleven `finale_*` flags), plus
   `fixture_digest` for pairing, `damage_taken`, `result`, `mod_version`, `policy_version`
   and `capture_schema_hash`. Arm recovery needs no inference.

2. **The HP series needed to reconstruct healing exists in these older eras**, not just in
   the 0.1.129 era that `hp_endpoints_recompute.md` covered. Spot-checked one run from each
   of the co-rotation (mod `0.2.47`) and pivot-qual (mod `0.2.48`) campaigns: every
   `combat_capture` payload carries `player.{hp, max_hp, hp_ratio, hp_regeneration,
   lifesteal, armor, dodge}`. The same positive-HP-delta method used in
   `hp_endpoints_recompute.md` §7 applies unchanged.

   **Feasibility spot-check, reported as a spot-check and not as an analysis:** pivot-qual
   control trial `run_1785148142_54629` carries `damage_taken = 102` and reconstructs
   **63 HP of in-wave healing** — i.e. ~62% of its gross damage was recovered, in a single
   wave-20 fixture trial lasting 58 s. The co-rotation trial sampled
   (`run_1785129963_33533`) reconstructed **0**. Two runs is not a distribution, but the
   spread between them is the entire reason this triage exists, and it shows the term is
   large and non-constant on *wave-20 fixture trials*, not only on full runs.

3. **Cost.** Re-adjudicating co-rotation, the 2.0x equivalence arm, and the residual
   checkpoint is **zero machine time and zero gameplay** — it is one pass of an
   HP-series extractor over ~290 already-archived run directories. The item-ledger
   defensive section is the same pass over the v122 campaign runs.

**The one thing that is NOT free.** `hp_endpoints_recompute.md` §7-8 establishes two hard
limits that re-adjudication inherits and cannot escape:

- **Healing cannot be attributed to a source.** Regen and lifesteal are both +1 HP trickles
  in the same field, with no per-source counter and no heal event: **100% of reconstructed
  healing is unattributed at source level.** Total healing (hence net damage) is measurable;
  "the treatment changed *lifesteal*" is not.
- **Consumable pickups are not computable.** There is no `consumable_picked` event, and the
  position-matching fallback fails — only **2.7%** of heal-consumable disappearances
  (3,370 of 122,963) are pickup-shaped. So the *consumable pickup* half of the risk
  hypothesis can only be tested by adding mod telemetry — which is new instrumentation and
  new gameplay, not an archive pass.

So: **net damage and HP-deficit AUC are free. Mechanism attribution is not.** Any
re-adjudication should be predeclared to decide on the net endpoint alone, and should not
promise to say *why*.
