# Next session: the six-item plan, with everything needed to start cold

State at handoff: commit `e26f614` + this, **704 tests green**, machine **idle**, mod `0.2.50` /
policy `0.1.129` deployed, `agent_config.json` disarmed (`human_movement=false`,
`auto_start=false`, `time_scale=1.0`, `finale_pivot_projectiles=true`).

Read first: `pro_brief_20260729_human_vs_agent.md` (what we asked) and
`pro_answer_20260729_human_vs_agent.md` (what came back). This file is the agreed plan.

---

## The two claims that changed, and must be corrected in the record

**1. WAVE 17 IS REOPENED AS MOVEMENT-ACTIONABLE.** The prior closure said "build-limited, movement
refuted". A human, given movement only, rescued a build the agent loses 17/21 times — **on the same
entry build**, 5/5 wave-17 survival vs 4/21 (p=0.0019, exploratory: the predeclared endpoint was
terminal win and it FAILED at 1/5).

Materials collected *during* wave 17 are spent *after* it, so collection cannot be the cause of that
wave's survival. **The correct model is an interaction, not a competition:**

```
weak build -> higher crowd pressure -> enters the controller's failure stratum
           -> the movement/arbitration defect becomes consequential
```

This reconciles the enemy-health dose response with the human result: both rescue the same fixture.

**2. `damage_taken` IS RETIRED AS THE PRIMARY ENDPOINT.** It is a **gross** counter — it sums
`player_damage` and never subtracts healing. Healing varied **15-171** across six agent runs. The
whole standing sizing table (32 detects 19 damage / 64 detects 13 / 128 detects 9) rests on it and
**does not transfer**.

Replacement, per the review: **terminal win from the wave-16 landmark** as confirmatory primary;
**death-adjusted HP-deficit AUC** for fixed-wave mechanism screens; gross damage retained as a
reported component, never as the primary.

```
h(t) = HP(t)/max_HP(t) while alive;  h(t) = 0 after death for the rest of the horizon
HP_deficit_AUC = (1/T) * integral[0..T] (1 - h(t)) dt      # lower is better
```

---

## ⛔ MY OWN ERROR, RETRACTED — do not repeat it

I published "the human collected 5x more while taking a quarter of the damage." **The damage half
was wrong** — it was inferred from minimum HP ratio (0.61 vs 0.13), which is not a damage statistic.

Measured on the same fixture: **agent median 80, human median 156 — the human took 1.95x MORE gross
damage.** The defensible statement is: the human reached more waves (2-4 vs 1) and took **less
damage per wave reached** (53 vs 74) with a far healthier HP floor.

---

## The plan, in order. Items 1-5 cost NO machine time.

### 1. Correct the record
Wave 17 reopened; the damage claim retracted; `damage_taken` demoted. Partly done in memory — verify
against this file before relying on anything older.

### 2. Recompute endpoints from the existing archive
No new gameplay. HP-deficit AUC, threshold exposures (<70/50/30%) with **absorbing death**, healing
by source, consumables picked, useful-material-value-before-next-shop. `scripts/wp2_material_bag_audit.py`
already does the bag half and bakes in the **pre-sweep instant** (captures continue ~40-55 ticks past
the wave timer and the sweep lands inside that window).

### 3. Rebuild the sizing table — WE ARE PARTLY AHEAD HERE
The review says rebuild from scratch. For terminal-win-from-landmark the variance components are
**already measured** (`landmark_continuation_pilot.md`): `sigma2_between = 0.0418`,
`sigma2_within = 0.1437`, **ICC 0.225**, continuation cost 3.76 min. Paired at the landmark is ~7x
more efficient than paired full runs; unpaired only 1.73x. Source state is the inferential unit —
K continuations from one save are NOT K independent builds. **Ticks are never the sample size.**

### 4. ⭐ THE JOINT CONTINGENCY + SHADOW ABLATION — start here
This is the item that can stop the whole line, so it should go first. Build the cross-tab, separately
for waves 15-19 and wave 20:

```
density_veto_zeroed_loot = true
AND useful_resource_route_exists = true
AND dash_active = false
AND final_heading_moves_away = true
```

Then replay the same archived states through deterministic shadow variants — `CURRENT`,
`NO_DENSITY_ZERO`, `NO_STALL_REQUIREMENT`, `NO_HP_SUPPRESSION`, `NO_FINALE_SUPPRESSION` — and answer
the only question that matters:

> **Which single component changes the FINAL command, after every downstream override?**

**If nothing changes the final command, the density-veto diagnosis is inert and everything
downstream is wasted effort.** This is the v128 lesson: a real defect is not automatically a
load-bearing one.

### 5. Triage past conclusions that rested on gross damage
Do NOT reopen every historical null. Triage by: did the decision depend on gross damage, AND could
the treatment have shifted healing / consumable pickup / lifesteal / willingness to spend HP?
Results resting on terminal survival or win are unaffected. The wave-20 pivot fix is unaffected —
it changed survival and had a structural readback.

### 6. The economic-rescue arm — CHEAPER THAN THE REVIEW PROPOSES
The review proposes crediting stranded value mid-run, which needs a controller hook. Instead:
**edit the wave-16 landmark save to credit the historically-stranded value, then run normally.**
Same question — "would a richer build have helped?" — using the existing save-edit precedent
(`enemy_scaling` is the template) with **zero controller change**.

Three-arm landmark diagnostic once that exists:

| arm | intervention | identifies |
|---|---|---|
| `C` | current policy | baseline |
| `M` | constrained safe-resource movement | deployable movement + natural collection |
| `E` | current movement + credited economy | upper bound on the slow economic pathway |

Prefer **more distinct source states** over more repeats — 24-32 unique states, ~5-7 machine hours.

---

## The intervention design, when we get there

**Do NOT:** loosen `not_armed_no_stall`; add another dash trigger; use `bag > 0` as the arming rule
(refuted — when the bag is non-empty the agent is ALREADY more loot-directed than the human, gap
−10.5 deg); disable `suppressed_survival` globally; seek ordinary materials at wave 20 (economically
too late for a shop — but healing consumables still have immediate survival value there).

**DO:** replace binary `loot attraction = 0` with a **safety-constrained resource tie-break** —
survival defines an admissible set, useful collection breaks ties inside it, lexicographic, with an
explicit reason code per decision. **First version risk-NONINFERIOR**: only take resource routes
predicted no less safe than the incumbent. Scope it inert outside waves 15-19 + density-suppression
active. Prove offline that final commands change in the target stratum and leakage outside is ~zero
BEFORE any gameplay.

---

## Evidence inventory (so nothing is re-derived)

- **Instrument:** movement-only handover, `human_movement` flag, mod `0.2.50`. Verified by EFFECT
  not self-report — flag on + no input gives 577/577 stationary (1.0000) vs agent controls 0.068 /
  0.063. Agent-driven agreement between realised velocity and commanded action is 0.7 deg; human
  trials 75 deg. **The agent logs its intended vector every tick while the human drives**, so every
  tick is a triple (state, agent intent, human action).
- **Data:** 5 human fixture trials + 21 agent trials on one wave-16 save; 1 human full run
  (`run_1785296333_7237`, ~20,576 ticks, reached w20); 36 agent full runs; 5 agent runs used for the
  own-run control (95,630 ticks).
- **Loot-directedness** (angle to nearest material, lower = greedier), crowd-matched — **the gap
  SURVIVES matching and grows**: −6.3 deg at 0-4 enemies (agent MORE loot-directed when safe),
  +15.7 / +17.9 / +33.9 / +37.5 through 20-29 enemies. Agent's own runs reproduce it (w17-20 median
  77.3 vs 85.2 on human states) — **intrinsic, not an artifact of human-visited states**.
- **Bimodal**: agent own runs w17-20 p10 = 10.7 deg, median 77.3, p90 = 158.6 — heads either at loot
  or away, the signature of a binary veto. Corroborates, does not prove.
- **Dash telemetry, w17-20:** agent `suppressed_finale` 30.4%, `not_armed_no_stall` 29.3%,
  `suppressed_survival` 21.7%, `active` 6.9%.
- **Bag:** pooled 36 agent runs, 709 wave-observations, drained 94.8% overall but **w17-20 76.7%**
  (w19 0.697, w20 0.548). Human full run 20/20, 0 stranded. On the doomed fixture: agent 1/21 vs
  human 5/5, p=0.0001.
- **Risk:** human full run spent 0.022 of ticks below 70% HP vs agent median 0.033; healed back 120
  vs agent median 38.

## Known-weak claims — do not harden without more work

- "No enemy between the agent and the loot" is **not** proven. The data show the material was closer
  than the *nearest* enemy in 90% of cases; that is not a collision-free corridor. Needs a
  short-horizon **swept-path** test over the full threat set.
- The human's stronger full-run build (58.78 vs died-median 28.26 / survived 35.25) is **one
  trajectory**, not a causal mediator analysis.
- The five human fixture trials were **sequential** — practice/learning effects are unrecorded.
- Nearest-material angle is an incomplete collection metric; target identity can switch and
  manufacture two modes. Consider cluster value, signed radial velocity, target persistence.
- **Do not merge materials and healing consumables under one "loot" label** in the next analysis.
