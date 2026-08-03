# §36 scoping — where the D5 clearance headroom actually is

**Scoping only. No lever is proposed as ready; nothing here is a Gate 0 result.** Offline scan of the
archive, zero new runs, no deploy, no launch.

Context: §28 established D5 is **CLEARANCE-limited** (enemy-health doses move terminal wave, enemy-
damage doses do not) and put the requirement at roughly **+33% effective DPS** for ~1-in-8 wins
(planning estimate off n=8, not a dose-response). §31-§35 closed the entire movement command. This
asks which remaining channel has headroom.

## §36a — Two channels sized and CLOSED

**(1) IDLE MATERIALS — CLOSED. There is no unconverted-materials problem.**

⛔ **The instant is the whole measurement, again.** The end-of-wave balance (last capture with
`remaining_sec > 0`) is the **shop BUDGET** — the wave-N shop runs after it. Measured there, the agent
looks like it is sitting on 436 materials at wave 9. The unconverted figure is the balance at the
**first capture of wave N+1**, after the shop:

| wave | pre-shop median (budget) | **post-shop median (idle)** | post/pre |
|---|---|---|---|
| 7 | 232 | **18** | 0.078 |
| 8 | 227 | **15** | 0.066 |
| **9** | **436** | **13** | **0.030** |
| 10 | 336 | 15 | 0.045 |
| 11 | 328 | 20 | 0.061 |

**The agent converts ~97% of its wave-9 budget.** 148 D5 runs. ⇒ The recorded *"the agent sat on 445
materials"* observation was a pre-shop reading; post-shop it is **13**. A **34x** difference in
meaning. **Do not build a spend/reserve lever on it.**

**(2) WEAPON TIER — CLOSED as a defect.** The agent does combine: **293 combine events across 64/67**
runs of the largest coherent cell (`0.2.73` / era `2018397571` / mutant, n=67), and 59.6% of weapon
buys are same-family-same-tier combine fodder — i.e. deliberate. Mean tier held rises 1.000 (w1) →
**2.400** (w11), max observed 3.000 against a ceiling of 4. Progression works; it is not idle.

## §36b — ⭐⭐⭐ THE FINDING: TWO D0-CALIBRATED DEFECTS THAT ARE EACH INERT ALONE

### (i) The DETECTOR is gated later than a D5 run lives

`shop_strategy.gd:654-659`, `_dps_below_band` returns **false** when `wave < OFFENSE_BAND_FROM_WAVE`
(**= 13**, `config.gd:652`). D5 dies at **median wave 11**. So the winner-DPS-band mechanism — which
excludes sub-floor filler guns from scoring and adds **+8.0 reroll pressure**
(`OFFENSE_BAND_REROLL_PRESSURE`, consumed at `:1793`) — **never runs for an entire D5 run.**

Related, same ladder: `_offense_target` (`:628-635`) returns **0.0 below wave 9**, so
`_offense_deficient` is **structurally false for waves 1-8**. The agent has **no offense floor at all**
for the majority of a D5 run, the MID floor for waves 9-11, and never reaches the LATE floor.

⚠️ **SOURCE-VERIFIED, NOT BEHAVIOURALLY CONFIRMED.** The readback was attempted and **could not be
run**: `board_scores` ships in `0.2.74` and there are **0 Danger-0 runs at ≥0.2.74** (all 30 are D5),
so the intended D0-vs-D5 control was impossible. A within-D5 wave split (wave≥13 as the positive arm,
75 decisions / 228 candidate rows) returned **0 `band_gate` skips in both arms**, so the positive
control FAILED and nothing is concluded from the data. `_board_note(it, null, "band_gate")` **does**
exist (`:1640`) but additionally requires `slots_full`, so the zero means *untriggered in this sample*,
not *dead code*. **Treat (i) as a source reading pending a live readback.**

### (ii) The TARGET is calibrated on a tier the agent is not playing

`config.gd:627-632`, verbatim: *"winner-trajectory DPS curve recalibrated on **41 victories** (v70:2,
v71:11, v72:18, v73:1, v76:1, v77:5, v79:3)"*. **Every one of those is a Danger 0 victory — there has
never been a nominal-D5 win.** It is the only target the D5 agent has.

Measured against it, on **10,275 D5 purchase decisions, waves 1-11, 148 runs** (0 excluded for missing
metrics — `build_metrics.offense` carries both `weapon_dps` and `dps_target` on every decision):

| wave | n | below band | rate | dps/target p25 | **median** | p75 |
|---|---|---|---|---|---|---|
| 3 | 875 | 250 | 0.2857 | 0.959 | 1.187 | 1.430 |
| 8 | 989 | 168 | 0.1699 | 1.088 | 1.251 | 1.551 |
| 9 | 1225 | 101 | 0.0824 | 1.175 | 1.392 | 1.630 |
| 11 | 455 | 47 | 0.1033 | 1.259 | 1.457 | 1.729 |
| **ALL** | **10,275** | **1,754** | **0.1707** | 1.076 | **1.314** | 1.609 |

⇒ **The agent is not below its DPS target at D5 — it sits a median 31% ABOVE it, and dies anyway.**
It is on track by a yardstick that describes a different game.

### ⭐⭐ Why each fix ALONE is predicted inert

- **Lower the wave gate alone** ⇒ the detector switches on and finds the agent already above target on
  **83%** of decisions (and 90-92% at waves 9-11). Firing rate ~0.10-0.17. **That is the damage-tilt
  failure shape**, which failed Gate 0 at a 13.1% flippable surface.
- **Raise the target alone** ⇒ the detector that would consume it **never runs below wave 13**.

**They are jointly necessary and have never been tested together.** This is the same joint-insufficiency
shape §32/§33 recorded on the movement side (*"floor and score are each insufficient alone and jointly
untested"*), now in the shop layer — and it is a plausible reason every single-parameter shop lever has
failed.

## §36c — ⛔ THE BOOTSTRAP PROBLEM, stated before anyone designs the dose

**A D5 target curve cannot be calibrated the way the D0 one was, because there are zero nominal-D5
victories to calibrate on.** Any D5 curve must therefore be *derived* (e.g. scaling the D0 curve by the
enemy-HP multiplier), which is a **modelling assumption, not a measurement** — and the scale factor
becomes the dose. That must be stated in the pre-registration, not discovered at analysis time.
⚠️ Anchor for sizing, not a target: §28's planning estimate is ~+33% effective DPS for ~1-in-8. The
agent sits at median **1.314x** the D0 curve, so ~1.75x would be the rough ask. Wave 11 specifically
presents **+44% HP/sec** over wave 10 at D5, and D5's median death is exactly wave 11.

## §36d — What a Gate 0 here can and cannot answer

✅ **Computable exactly offline**: with target scaled by `k` and the gate lowered to wave `W`, which
decisions become band-gated and whether the **emitted choice changes**. `board_scores` carries
per-candidate `{slot, id, category, price, affordable, score}` and `build_metrics.offense` carries
`weapon_dps`/`dps_target`. 30 D5 runs at ≥0.2.74 (**pooled across 0.2.74/75/76 — must be reported, not
hidden**).
⛔ **NOT computable offline**: the **reroll-pressure half**. `+8.0` search pressure changes which
boards the agent ever sees, which is sequential and closed-loop. Same limitation as §35, and it means a
pass licenses a **screen**, never a ship.
⛔ Also not answerable offline: whether more DPS at waves ≤11 actually converts to survival. §28 says
clearance converts (4/4 wave-20 arrivals were wins) — **at modified difficulty**.

## §36e — Status

**No lever is ready.** (i) needs a live readback before it is treated as established; (ii) is measured
and solid. The joint test is the first candidate in this project that is *predicted inert as two
separate levers and untested as one*, which is exactly the class §32/§33 left open on the other layer.
Next step if pursued: a pre-registration fixing `k`, `W`, the flip bar and the DPS-gain bar **before**
the counterfactual is computed.
