# §39 — D5 clearance bootstrap and target-backed search Gate 0

**Written 2026-08-04, BEFORE computing any §39 target-deficit exit, actionable reroll, empirical
search yield, or Gate 0 result.** Existing exposures are stated explicitly below.

## §39a — Why this is the bootstrap, and what remains an assumption

There are zero nominal-D5 victories, so a D5 winner trajectory cannot be measured in the same way as
the 41-win Danger-0 `OFFENSE_DPS_TARGETS_BY_WAVE` curve. §28 establishes causally that D5 failure is
clearance-limited, but its enemy-health dial is not unit-identical to player DPS: killing earlier also
reduces incoming damage. Any conversion is therefore a **planning model**, not a measured target.

The low-dose bootstrap is fixed as:

`k_primary = round(1.314 * (1 / 0.75), 2) = 1.75`

- `1.314` is the already-published median D5 `weapon_dps / D0_target` over 10,275 waves 1–11 purchase
  decisions (§36 scoping);
- `1/0.75 ≈ 1.33` is the outgoing-clearance equivalent of §28's H75 enemy-health arm, which produced
  1/8 modified-difficulty victories and significantly moved terminal wave;
- therefore `T_w = 1.75 * OFFENSE_DPS_TARGETS_BY_WAVE[w]` is the primary **derived requirement**.

This targets approximately one low-dose rescue opportunity, not certainty of winning. Because H75
also carries an indirect defensive benefit, `T_w` is more likely optimistic than conservative.

The H50-derived `k_high = round(1.314 * 2.0, 2) = 2.63` is reported only as a sensitivity. It cannot
rescue a primary failure and cannot license a different arm. The wave-11 demand shock—D5 HP arrival
260/s versus 181/s at wave 10, +44%—is a structural cross-check explaining why the planner must act
by the wave-10 shop; it is not multiplied into the target a second time.

## §39b — New mechanism: one target-backed search action

§§37–38 close target-free re-ranking for campaign purposes. Applying the new target only to those
same buy choices would re-run a known null on a subset and is prohibited. The new surface is the
shop **exit/search** decision that the old band mechanism could not replay offline.

Population: the same 16 terminal, era-matched `0.2.79-wp2-capture` nominal-D5 Ranger runs used in
§§36–38. The analysis unit and denominator are every recorded `shop_go` decision at shop waves
1–10 inclusive. Wave 10 is included because that shop prepares the build for the modal killer wave
11; a wave-11 shop occurs only after surviving wave 11 and is too late for that demand shock.

At an exit decision, define clearance debt when:

`current_weapon_dps < 1.75 * recorded_d0_dps_target`.

The counterfactual replaces `shop_go` with **one additional `shop_reroll`** iff all are true:

1. clearance debt is positive;
2. `shop_reroll` appears in `legal_alternatives`;
3. `gold_before`, `reroll_price`, and the action's `locked_item_reserve` are recorded and numeric;
4. `gold_before - locked_item_reserve >= reroll_price`.

Only locked-item commitments are preserved. `next_shop_reserve` and generic material-value reserve
are deliberately subordinated to the externally derived clearance requirement; otherwise the D0
reserve policy would remain the deciding authority. The rule adds at most one search action at each
observed exit. It does not fabricate the next offer, choose a counterfactual item, or count the
unknown offer as a success.

Danger 0–4, shops after wave 10, non-exit decisions, non-debt exits, illegal/unaffordable rerolls,
and exits with missing operands remain exactly unchanged.

## §39c — Controls before results

Print denominators, exclusions, and controls before any Gate 0 result. A failure returns **VOID**:

1. **arm validity:** exactly 16 terminal D5 Ranger summaries at mod `0.2.79-wp2-capture` and unlock
   stamp `179/48/2018397571/1530875081`;
2. **target completeness:** `weapon_dps` and `dps_target` numeric on at least 99% of waves 1–10
   `shop_go` decisions;
3. **budget completeness:** gold, reroll price, and locked reserve numeric on at least 99%;
4. **legality variation:** report legal rerolls with all exits as denominator; at least one legal and
   at least one unaffordable/locked-out exit must exist, so the affordability branch is proven able
   to return both values;
5. **disabled/null rule:** exactly zero exits change when the bootstrap rule is disabled;
6. **synthetic controls:** debt+legal+affordable changes to reroll; no debt, illegal reroll, and
   insufficient post-lock gold remain unchanged; wave 11 remains out of scope.

Every zero is printed with its denominator and the relevant positive control.

## §39d — Gate 0a: reachable search surface and stability

All are required:

1. actionable target-backed rerolls are **≥20% of the full waves 1–10 shop-exit denominator**;
2. actionable exits occur in at least **12/16 runs**;
3. all 16 leave-one-run-out actionable rates are **≥18%**, with median **≥20%**;
4. no single run contributes more than **20%** of actionable exits.

These bars prevent a few long-surviving runs or one economy trajectory from creating the result.

## §39e — Gate 0b: search has demonstrated yield at acceptable cost

The counterfactual next board is unknowable offline. Search usefulness is therefore a separate,
empirical manipulation check from **actual** rerolls in the same fixed runs, restricted to waves
1–10 states that are below the same primary target.

Pair each actual `shop_reroll` with the immediately following purchase decision in the same shop.
A useful-board hit occurs when that next decision's `board_scores` contains at least one scored
(`score > 0`), affordable weapon whose recorded `proj_dps_gain` is at least **5% of current weapon
DPS**. The 5% floor is carried unchanged from `OFFENSE_IMPACT_MIN_DPS_GAIN_FRAC`; this conservative
readback ignores useful damage items rather than guessing their effects.

Required:

1. at least **30** target-deficient actual rerolls have a joined next board;
2. next-board join completeness is **≥99%**;
3. useful-board yield is **≥30%** (roughly at least one qualifying weapon board per 3.3 searches);
4. for actionable counterfactual exits, median `reroll_price / gold_before` is **≤10%** and p90 is
   **≤25%**;
5. locked commitments are preserved on **100%** of actionable exits by construction/readback.

The yield is a transport assumption from observed rerolls to the actionable exits, not a causal
counterfactual. Passing licenses only a fixed-build live screen that measures realized next-board
yield and DPS trajectory. Failing means the search planner lacks either exposure, evidence of useful
offers, or acceptable cost.

## §39f — Reported diagnostics

- primary and high-sensitivity target values by wave;
- exit, debt, legal, affordable-after-lock, and actionable counts by wave and run;
- reasons unchanged with full denominators;
- leave-one-run-out rates and run concentration;
- actual-reroll join and useful-board counts by wave;
- qualifying weapon rows / all scored weapon rows;
- reroll-cost ratios and locked reserve distribution;
- high-target (`k=2.63`) actionable rate, descriptive only.

No terminal-wave or victory claim is made from this deterministic archived screen.

## §39g — Exposure disclosure and prediction

Known before this packet: the D5 median is 1.314× the D0 curve; §28's planning equivalents are
approximately 1.33× and 2× current clearance; §36's candidate-drop band gate had only a 4.66%
structural surface; §37's unconstrained higher-DPS buy surface was 24.45%; §38 reached 19.07% behind
the positive-score boundary. I have **not** counted waves 1–10 exits, target-debt exits, affordable
post-lock rerolls, actual-reroll joins, or useful next boards.

**Prediction: Gate 0a passes; Gate 0b is genuinely uncertain and less than even odds.** The target is
well above the observed trajectory, so debt should be common, and preserving only locked commitments
should expose many exits. The risk is search yield: §30 showed the agent already buys damage often,
so additional boards may not produce a positive, ≥5%-impact weapon often enough. A surface pass with
yield below 30% is a planner failure, not permission to lower the yield bar.
