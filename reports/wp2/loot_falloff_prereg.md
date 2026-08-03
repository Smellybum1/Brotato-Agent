# §35 — Gate 0 for the loot falloff exponent (the desire layer at D5)

**Written 2026-08-03, BEFORE the counterfactual is computed.** Exposure disclosure in §35g.

## §35a — The lead, and why it is not the closed movement-lever class

§34 established, on the 8 D5 ranger runs at `0.2.76` (76,543 captures, zero new runs):

- The desire **reaches the command** at D5 waves ≤ 11 — median `angle(action, desire)` **11.29°** on
  `baseline_kept` (52.1% of the band) and **2.84°** on `no_threats` (5.7%). ~**58%** of target-band
  ticks carry the desire to the command. (D0 wave-17 reference: pooled **54.7°**.)
- Within that band, **`loot` is the only desire term with command authority**: nonzero 0.9226,
  median |loot| **111.111**, median rotation if removed **65.91°**. Every other term is ≤ 0.11°.
- **No config knob exists on it.** The two knobs that do exist both failed §34.

⛔ **The "movement-lever class is closed" verdict does not cover this.** §31 (`body_slack`),
continuity-removal, §32 (positional term) and §33 (PACK floor) all acted on the **route / body-safety**
layer and were all analysed on **`ranked`** captures. This lever acts on the **desire**, and its tick
set is `baseline_kept` + `no_threats` — **disjoint** from all four.

## §35b — The lever: the EXPONENT, not a scale

`_loot_attraction` (`teacher/potential_field.gd:3551-3585`) sums over every loot item:

```
force += (diff/dist) * LOOT_ATTRACTION * greed * safety * clear_mult / falloff
falloff = pow(dist, 0.65)   if early (wave <= EARLY_LOOT_WAVE = 15)   # :3579-3580
```

At 500 u, `d^0.65` decays ~**8.6x** more weakly than `1/d`, so distant loot pulls nearly as hard as
near loot. That is why |loot| reaches 111 with ~10 materials on the ground — no anomaly required.

⛔ **A SCALE CANNOT BE THE LEVER.** The pipeline is **direction-only** — `||teacher.action|| == 1.0000`
on 76,502/76,502 captures — so multiplying the whole resultant changes nothing until it collapses to
the residual's order (|loot| ~111 vs residual ~0.6 ⇒ scale ~**0.005**), then flips wholesale. **A
scale is a cliff; a conventional dose ladder on it would read as a clean null and close this branch
falsely.**

**The exponent reweights WHICH items dominate the sum**, so it rotates the resultant continuously and
monotonically. That is a real dose.

**Doses: `e ∈ {0.65 (control), 0.9, 1.2, 1.6}`.** 1.0 is the natural `1/d` law and sits inside the
ladder. `LOOT_ATTRACTION`, `greed`, `safety`, `clear_mult` and both vetoes are **left untouched** —
this is a one-parameter dose, deliberately, after §31's monotonicity trap (one scalar on two terms
that push opposite ways is a design-time lie that can only return a null).

## §35c — Method: exact offline recomputation, no new runs

Every input `_loot_attraction` consumes is in the capture. Verified, keys dumped before any test:

- `entities.materials` **IS the mod's `loot` argument** — `game_adapter.gd:113-114` assigns the same
  list object to `state["loot"]` and `state["materials"]`, and `agent_controller.gd:1054` writes the
  telemetry from `state["loot"]`. Items carry `x, y, radius, value` (95,098 items over 9,452 captures
  in the probe run).
  ⚠️ **There is no `entities.loot` key.** Testing for one returns 0 and reads as "not captured" — a
  vacuous filter that would have bought a fresh campaign. The key dump is what caught it.
- `entities.enemies` carry `x, y, vx, vy, hp, radius`; `player` carries position and `speed`.
- Constants: `LOOT_ATTRACTION 120.0`, `EARLY_LOOT_WAVE 15`, `SPARSE_LOOT_ENEMIES 14`,
  `EARLY_LOOT_SAFETY_FLOOR 0.92`, `EARLY_LOOT_CONTACT_ABORT 0.28`, `LOOT_PACK_ALLOW 2`,
  `SAFETY_DISTANCE 280.0`, `CONTACT_DANGER 130.0`, `PACK_DENSITY_SOFT 8.0`.

Counterfactual desire at exponent `e`:

```
desire(e) = total_recorded − loot_recorded + loot(e)
```

valid because §34 established the exact decomposition
`early_force_mult * enemy_engagement + Σ(other 11) == total` at **35,255/35,255 = 1.0000**.

Implementation: `scripts/wp2_loot_falloff_gate0.py`, with `--self-test`.

### ⛔ CONTROLS. The counterfactual is VOID unless all pass.

1. **Loot reproduction at e = 0.65.** The recomputed loot vector must reproduce the **recorded** `loot`
   term. This is the make-or-break control: it validates my reimplementation of `greed`, `safety`,
   `clear_mult`, the `nearby >= PACK_DENSITY_SOFT` **return-ZERO** veto (`:3559-3560`) and the
   `blockers > LOOT_PACK_ALLOW` item skip (`:3574`). **Bar: ≥ 0.99 of analysable captures within a
   relative error of 1e-3.** Below that, report the failure and STOP — reproducing a rule is not the
   same as knowing it (§33 control 2a read 0.9302 and exposed a missing branch).
2. **Sum reproduction.** `early_force_mult * enemy_engagement + Σ(other 11) == total`, re-asserted per
   capture, ≥ 0.99 at 1e-3. (§34 measured 1.0000; it is re-run, not inherited.)
3. **The statistic must return the NEGATIVE.** At the null dose `e = 0.65` the rotation must be
   **exactly 0.0** on every capture. A gate that cannot report "no change" is 11(c).

## §35d — Analysis set

Wave ≤ 11 (the band a D5 lever must act in; D5 dies at median wave 11), `route.exit ∈ {baseline_kept,
no_threats}` (the ticks where the desire is the command), fresh `desire.seq`, non-degenerate desire,
≥ 1 material present. Runs: the 8 §32 runs; `run_1785754086_12860` stays excluded (force-killed,
truncated). **Every exclusion printed with a count before any result.**

## §35e — BARS, fixed here

- **GATE 0a (the desire actually moves):** at some dose, the desire direction rotates by **≥ 15°** on
  **≥ 20%** of analysis-set captures.
  ⭐ The 15° bar is **derived, not chosen**: §34d measured the pipeline's own median
  `angle(action, desire)` at **11.29°** on `baseline_kept`. A rotation below the pipeline's own
  transmission noise cannot be expected to survive to the command. The 20% is §32/§33's flip bar,
  carried over unchanged.
- **GATE 0b (it buys something):** on rotated captures, **median in-range gain ≥ 0.05**, using the
  identical moving-threat `inrange_after(dir, 0.60 s)` definition as §32 and §33 — threats advance by
  their own `vx/vy`; enemies are **not** frozen.
- ⛔ **MONOTONICITY:** realised gain must be non-decreasing in `e` up to saturation. **Non-monotone ⇒
  NOISE, not partial success.** (§31's signature, declared in advance for the third time.)

**Both gates must pass.** A rotation without a gain is the damage-tilt failure repeating.

## §35f — ⚠️ DECLARED LIMITATIONS. Two of these bias the gate OPTIMISTIC.

1. ⛔ **THE EXIT-FLIP RISK IS UNMODELLED, AND IT BIASES TOWARD A PASS.** `route.scores` is **empty on
   `baseline_kept` (0/4,321) and `no_threats` (0/1,135)** and populated only on `ranked`
   (3,996/3,996) — verified, not assumed. So I **cannot** evaluate whether a rotated baseline would
   still clear the body floor. If it does not, the tick diverts to the `ranked` exit, where the
   command is **orthogonal to the desire** (88.57°) and simply repeats the previous action. **Some
   fraction of Gate 0a's rotations would therefore never reach the command, and I cannot say which.**
   Reported alongside: the `baseline_admitted`, `body_floor` and `floor_admitted` distributions, which
   are recorded on all exits. ⇒ **A pass licenses a screen; it does not license a ship.**
2. ⛔ **SINGLE-TICK COUNTERFACTUAL.** The controller is stateful and closed-loop (`_prev_move` feeds
   the next tick's continuity term at 85.0). After one tick the trajectory diverges — different
   position, different materials, different pack. **This cannot predict a run outcome and is not
   evidence about survival.** Same scope as §32/§33, stated again because the desire layer makes it
   tempting to over-read.
3. **Smoothing** (`_prev_move*0.70 + combined*0.30`, `MOVE_SMOOTHING = 0.30`, `:398-400`) attenuates a
   single-tick rotation but **not** a sustained policy change. The desire-level statistic is the
   correct one for a knob that is on for the whole run; a per-tick command delta would understate it.
   Stated in advance so neither reading can be selected after the fact.
4. **The §31 low-HP-exposure safety veto cannot be evaluated offline.** It therefore binds on the
   **live screen**, not on Gate 0: reject any dose that buys in-range with low-HP exposure.

## §35g — Exposure disclosure

I have already measured, and am not blind to: |loot| = 111.111 median, its 65.91° leave-one-out
rotation, the full 12-term inventory, and the transmissivity table. **I have NOT computed
`_loot_attraction` at any counterfactual exponent, nor any in-range number for this lever** — the
quantity both gates turn on is genuinely uncomputed.

Mitigations, structural rather than promissory: the **20%** flip bar and the **0.05** in-range bar are
§32/§33's, carried over verbatim; the **15°** bar is derived from a §34 measurement (11.29°) rather
than picked; the dose ladder is fixed here and is one-parameter.

## §35h — ⚠️ I DO NOT PREDICT A NULL, AND THAT IS NEW

§33's prereg predicted its own failure and was right. **I am not making that prediction here**, and
the difference is worth recording: §31-§33 all acted on layers whose authority over the command was
either unmeasured or measured weak, whereas this lever acts on **the one term measured to own the
command**, on a tick set none of them touched.

My honest split: **Gate 0a probably PASSES** — an exponent change genuinely reweights a ~10-item sum
and 0.65 → 1.6 is a large reweighting. **Gate 0b is genuinely uncertain**, and it is where I expect
this to live or die. The mechanism I am betting on is that steeper falloff keeps the agent near
recently-killed ground, which is where the pack is, raising in-range. The mechanism against is that
`safety` and the `PACK_DENSITY_SOFT` veto already suppress loot-seeking near dense packs, so a steeper
exponent may only make the agent hover without closing distance.

**Recording an uncertain prediction is the point** — it is what stops a pass being reported as
"obviously right" and a failure as "expected all along".

## §35i — What passing or failing means

**Passing** licenses a **live dose screen** on the in-range mediator, subject to the §31 low-HP veto,
and still short of any survival claim.

**Failing** closes the **desire layer** at D5. Together with §31-§33 that would close both the route
layer and the desire layer — a materially stronger statement than the current verdict, and it would
mean the movement command at D5 is not reachable by any parameter this controller exposes. That would
redirect the North Star 1 effort away from movement entirely.
