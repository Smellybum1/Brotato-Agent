# §36 — Gate 0 for the JOINT DPS-band lever (target scale × gate wave)

**Written 2026-08-04, BEFORE the counterfactual is computed.** Scoping that motivates it:
`reports/wp2/d5_clearance_channel_scoping.md` (`fccde13`). Exposure disclosure in §36g.

## §36a — The claim being tested

Two D0-calibrated defects, each predicted **inert alone**:

- **(i) the DETECTOR is gated too late.** `_dps_below_band` (`shop_strategy.gd:654-659`) returns
  **false** below `OFFENSE_BAND_FROM_WAVE` = **13**; D5 dies at median wave **11**.
- **(ii) the TARGET is calibrated on the wrong tier.** `OFFENSE_DPS_TARGETS_BY_WAVE` was
  *"recalibrated on 41 victories"* (`config.gd:627`) — **all Danger 0**. Measured over 10,275 D5
  decisions the agent sits a **median 1.314x ABOVE** it and dies anyway; below-band only **17.07%**.

⇒ **The hypothesis is an INTERACTION, not a main effect.** Lowering the gate alone switches on a
detector that finds the agent already above target on 83% of decisions (the damage-tilt failure shape,
which died at a 13.1% surface). Raising the target alone feeds a detector that never runs. **This
document tests whether the two together do materially more than the sum of their parts.**

## §36b — Design: a 2x2 factorial, not a dose ladder

| arm | gate wave `W` | target scale `k` | role |
|---|---|---|---|
| **A baseline** | 13 | 1.00 | control — must reproduce the recorded decisions |
| **B gate-only** | 1 | 1.00 | predicted near-inert |
| **C target-only** | 13 | 1.75 | ⭐ **predicted EXACTLY 0 flips at waves ≤ 11** |
| **D joint** | 1 | 1.25 / 1.50 / **1.75** | the test |

`W = 1` (gate removed) is the primary rather than an arbitrary threshold; `W ∈ {6, 9}` are reported as
sensitivities. `k` scales `offense_dps_target(wave)`; nothing else is touched — one factor per knob,
after §31's monotonicity trap.

⭐⭐ **ARM C IS A BUILT-IN POSITIVE CONTROL ON THE WHOLE MODEL.** If the wave gate really blocks the
detector below wave 13, then raising the target while leaving `W = 13` **must** flip **exactly zero**
decisions at waves ≤ 11. **A non-zero result in arm C falsifies my source reading and voids the
analysis** — it does not get explained away.

## §36c — Method: exact offline counterfactual, no new runs

Data: **30 D5 runs at ≥ 0.2.74** (`board_scores` ships there). ⚠️ **Pooled across `0.2.74` (6) /
`0.2.75` (16) / `0.2.76` (8) — reported, not hidden**; per-build results printed.
`purchase_decision.build_metrics.offense` carries **`weapon_dps` AND `dps_target`** on every decision
(10,275/10,275, 0 missing), so `_dps_below_band` is computable at any `(W, k)`.
Analysis set: `action.type == "shop_buy"` decisions carrying `board_scores` with ≥1 scored candidate,
waves 1-11. **Every exclusion printed with a count before any result.**

### ⛔ CONTROL — cell-wise reproduction of the recorded decision. Measured FIRST, and it is NOT uniform.

`argmax(board_scores)` vs the recorded `action.item_id`, on 804 shop_buy decisions:

| slots full (`weapon_count ≥ 6`) | top is weapon | match | n |
|---|---|---|---|
| no | either | 467/468 = 0.9979 | 468 |
| yes | no | **274/274 = 1.0000** | 274 |
| **yes** | **yes** | **44/62 = 0.7097** | **62** |
| pooled | — | 785/804 = 0.9764 | 804 |

⭐ **The ranking loop determines the emitted action perfectly in three of four cells (741/742 = 0.9987)
and breaks in exactly one** — slots full AND the ranking winner is a weapon, where a sell-or-defer
branch takes over. **18 of the 19 pooled mismatches sit in that cell**, and in 18/19 the top candidate
was a weapon while an item was bought.

⛔ **THAT CELL IS WHERE THIS LEVER ACTS, so it may NOT simply be excluded.** Dropping non-reproducing
decisions would drop precisely the weapon-vs-item conflicts the lever is about — selection on the
quantity of interest.
⇒ **Choice-free resolution (27b): the counterfactual is reported BOTH over all cells AND excluding the
full-slots/top-weapon cell, with equal standing, and their AGREEMENT is a reported result.** If the two
disagree across the §36e bar, the arm is declared **FRAGILE TO THE UNMODELLED SELL BRANCH**, not a pass.

Second control: **arm A must reproduce the recorded action** at the cell-wise rates above — i.e. the
simulation at `(W=13, k=1.00)` must flip **0** decisions. A non-zero baseline flip rate voids everything.

## §36d — ⛔ THERE IS NO GATE 0b, AND THAT IS A DESIGN FACT, NOT AN OMISSION

§32/§33/§35 all carried a realised-gain gate because their endpoint (in-range fraction 0.6 s ahead) is
a **geometric function of a single decision** and is computable from one capture. **This lever's
endpoint is not.** Whether a changed purchase raises the `weapon_dps` trajectory depends on the run
continuing — different build, different boards, different income. It is **closed-loop and cannot be
simulated offline**.

⇒ **Gate 0a is the only barred gate here.** A pass therefore licenses a **live SCREEN** whose primary
is the realised `weapon_dps` trajectory at waves ≤ 11, with terminal wave as the confirmatory endpoint
— it does **not** license a ship, and it is **not** evidence about survival.
⚠️ Stating this in advance so that a directional descriptor computed later (e.g. "flips move toward
damage-bearing candidates") cannot be quietly promoted into the missing gate.

## §36e — BARS, fixed here

- **GATE 0a-i (reach):** at some joint dose D, the emitted purchase changes on **≥ 20%** of
  analysis-set decisions. (§32/§33/§35's flip bar, carried over verbatim.)
- **GATE 0a-ii (INTERACTION — the actual claim):** the joint flip rate must exceed
  **`flip(B) + flip(C) + 0.10`**. Sub-additive or merely additive ⇒ **the joint hypothesis FAILS**,
  regardless of whether 0a-i passes. *This is the bar that makes the design a test of joint necessity
  rather than of "does a bigger tilt flip more".*
- ⛔ **MONOTONICITY:** flip rate must be non-decreasing in `k` at fixed `W`. Non-monotone ⇒ **NOISE**.
  ⚠️ And a monotonicity check evaluated on identical values is **VACUOUS** (§35's three zeros) — it is
  scored only if the values actually differ.

**Both 0a-i and 0a-ii must pass.**

## §36f — Reported, not barred

Direction of flips (damage-bearing / weapon share, resolving item effects as §30 did with 0
unresolved); median score sacrificed by the flip (§30 found flips that swapped `item_glasses` 18.5 for
`weapon_medical_gun_1` 14.59 — **flipping is not improving**); per-build split; per-wave flip rate; the
share of the band-gated candidates that are filler guns; and the **`+8.0` reroll-pressure count**, which
is a *count of decisions where search pressure would rise*, **not** a simulated search outcome.

## §36g — Exposure disclosure

I have measured and am not blind to: the below-band rate (0.1707), the median `dps/target` (1.314) and
its per-wave profile, and the cell-wise reproduction table. **I have NOT computed a single
counterfactual flip at any `(W, k)`.** Mitigations: the 20% flip bar is carried over verbatim from
three prior preregs; the 0.10 interaction margin and the `k` ladder are fixed here before any flip is
computed; arm C is a structural control whose expected value (exactly 0) is fixed by source, not by
preference.

## §36h — Prediction, stated in advance

**Arm C: exactly 0 flips** (structural). **Arm B: non-zero but small** — I expect roughly the 0.10-0.17
below-band rate to translate into a materially smaller flip rate, because being below band only matters
when it changes the argmax. **Arm D: genuinely uncertain**, and it is where this lives or dies.

⚠️ **I give the interaction bar (0a-ii) less than even odds.** The honest prior is §30: the agent
already buys damage on 66.3% of purchases and the flippable surface was 13.1%. The reason to run it
anyway is that **no previous test moved the TARGET** — every shop lever to date re-weighted scores
against an unchanged, D0-calibrated bar.

## §36i — What passing or failing means

**Passing** licenses a live screen of `(W, k)` on the realised DPS trajectory, still short of any
survival claim, and supplies the behavioural readback that §36's scoping could not obtain (the
`band_gate` positive control failed for want of any D0 run at ≥ 0.2.74).

**Failing** closes the shop-valuation layer at D5 alongside §30's damage tilt — and with movement closed
by §31-§35, that would leave **no reachable parameter in either the movement or the purchasing policy**.
The next move would then have to be structural (a danger-aware policy, or re-deriving the winner
trajectory at D5, which needs a D5 victory that does not yet exist) — the bootstrap named in §36c of
the scoping report.
