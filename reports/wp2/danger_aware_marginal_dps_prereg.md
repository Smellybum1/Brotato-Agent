# §37 — Gate 0 for a target-free danger-aware marginal-DPS buy override

**Written 2026-08-04, BEFORE any counterfactual choice or flip is computed.** This follows §36's
surface-limited null (`reports/wp2/dps_band_joint_verdict.md`). The exposure disclosure is in §37h.

## §37a — Why this is a genuinely different mechanism

The established facts are:

- nominal D5 failure is **clearance-limited**, not survival-limited (§28); health doses move terminal
  wave and damage doses do not;
- the decision layer is **danger-blind** — no policy decision consumes the danger tier;
- D5 dies at median wave **11**, while the existing DPS-band detector starts at wave 13;
- the §30 damage tilt could flip only the 13.1% of buys where a non-damage winner faced a scored
  damage alternative;
- §36's joint band gate has a **4.66% ceiling** because it requires a full loadout, a winning weapon,
  no combine pair, and a sub-floor marginal gain. D5 is still assembling its loadout.

This test does **not** lower §36's gate, scale its D0 winner curve, or multiply all damage-bearing
items. It adds a new danger-conditioned preference among candidates on an already-authorized buy:
the candidate's **marginal effective weapon DPS**. It can therefore change damage-vs-damage choices
and it acts while slots are still free, the population §36's mechanism could not reach.

It is deliberately **target-free**. A D5 winner trajectory cannot be fitted because there are zero
nominal-D5 victories. This mechanism asks the smaller question that is answerable now: when the game
is nominal D5 and the policy has already decided to spend, is its existing score leaving enough
immediate effective DPS on the same board to matter?

## §37b — Exact counterfactual policy

The source population is the **16 completed `0.2.79-wp2-capture` D5 ranger runs**, all era
`179/48/2018397571`, used by §36. Analysis is restricted to purchase decisions with:

1. `action.type == "shop_buy"`;
2. wave 1 through 11 inclusive;
3. `board_meta.slots_full == false`;
4. a non-empty, non-truncated `board_scores` array with at least one scored candidate; and
5. a complete join from each scored row to the immediately preceding `purchase_offer` by slot and id.

Everything outside that set is **unchanged by definition**, not silently excluded from reach. Two
denominators are reported:

- **policy denominator:** every `shop_buy` decision at waves 1-11 in the 16 runs;
- **eligible denominator:** the five-condition set above.

The policy-level flip rate, not the conditional eligible rate, owns the bar. This prevents an
instrumented subset from making a narrow mechanism look broad.

At eligible decision `j`, let `s_ij` be the recorded `board_scores.score` for candidate `i`, and let
`D_j` be the recorded current `build_metrics.offense.weapon_dps`. Define `g_ij` as the immediate
change in total effective weapon DPS if candidate `i` is bought:

- **ordinary weapon, free slot:** add `effective_weapon_dps(i, current_stats)`; this must agree with
  the recorded `proj_dps_gain` within the control tolerance;
- **same-id/same-tier combine pair:** replace the owned copy with the next-tier weapon and use the
  exact before/after effective-DPS difference. The loadout is replayed from run start and combine
  signatures, and the next-tier stats come from recorded offer catalogs. If either is unavailable,
  the **whole decision** is uncomputable rather than treating the gain as zero;
- **item with combat-stat effects:** apply the item's recorded effects to the current stats and
  compute exact before/after total effective weapon DPS over the reconstructed loadout;
- **candidate with no modeled weapon-DPS effect:** `g_ij = 0`. Its existing score remains intact.

The current offense block records ranged damage, percent damage, attack speed and crit chance, but
not every possible combat stat (notably current crit-damage bonus). If any scored candidate's modeled
DPS change depends on unrecorded current state, the **whole decision is uncomputable**; the missing
state is never filled with a plausible-looking zero. Items whose effects are outside this mechanism's
weapon-DPS model keep `g_ij = 0` only when their weapon-DPS contribution is zero by the mechanism's
definition, not when the contribution is unknown.

Negative gains are retained. The normalized marginal-clearance term is:

`m_ij = 100 * g_ij / max(D_j, 1)`.

At dose `lambda`, the counterfactual score is:

`s'_ij = s_ij + lambda * m_ij`.

The counterfactual buys the maximum `s'_ij`, with the recorded row order as the deterministic tie
break. It changes only the selected slot; it never creates a buy, reroll, lock, sell, or combine
action that the incumbent did not already authorize. At Danger 0-4, after wave 11, on full slots,
and outside the ranked-buy surface, it is exactly inert.

### Dose ladder

`lambda ∈ {0.0, 0.5, 1.0, 2.0, 4.0}`.

`lambda=1` adds one extra copy of the existing combat model's natural percent-DPS score unit. The
0.5/2.0 doses bracket it; 4.0 is a high-dose reachability probe. A failure at 4.0 is evidence of a
surface/score-margin ceiling, not a request for an even larger production coefficient.

## §37c — Controls, evaluated before results

All denominators and exclusions print before any dose result.

1. **Arm validity:** 16/16 summaries must read mod `0.2.79-wp2-capture`, danger 5, ranger, the same
   unlock-pool stamp, and a terminal result. Any mismatch stops the analysis.
2. **Offer/row join:** at least **99%** of scored board rows must match the immediately preceding offer
   by both slot and id. Every missing/unmatched/truncated case is counted. Below 99% stops the
   analysis.
3. **Loadout reconstruction:** before every eligible decision, reconstructed weapon count, tier sum,
   and total effective weapon DPS must match recorded `build_metrics.offense` (DPS relative error
   ≤1%). At least **95%** of otherwise-eligible decisions must be trusted. Below 95% stops the
   analysis; untrusted decisions remain in the policy denominator as unchanged.
4. **Independent weapon-gain parity:** for ordinary non-combine weapons on trusted free-slot boards,
   independently computed `effective_weapon_dps` must match recorded `proj_dps_gain` within 1% or
   0.01 absolute, whichever is larger, on at least **99%** of rows. Below 99% stops the analysis.
5. **Baseline choice reproduction:** `argmax(s_ij)` must match the emitted `action.item_id` on at
   least **99%** of eligible decisions. Mismatches are reported and retained in the policy
   denominator as unchanged; they are not allowed into the dose analysis.
6. **Null dose:** `lambda=0` must flip **exactly zero** decisions. A nonzero result voids the analysis.
7. **Positive synthetic controls:** self-tests must contain (a) a board that flips toward a higher-DPS
   candidate, (b) a board that cannot flip because the incumbent already has the highest marginal
   DPS, (c) an item-stat gain, (d) a combine gain, and (e) an untrusted decision that contributes
   zero flips but remains in the policy denominator.

A zero from any control is printed next to a positive control from the same operation.

## §37d — Gate 0a: reachable surface before dose

A baseline-reproduced eligible decision is **reachable** when at least one alternative has
`m_alt > m_incumbent` (strictly, beyond numerical tolerance). This is the weight-free ceiling: no
positive `lambda` can improve marginal DPS on any other decision.

- **GATE 0a:** reachable decisions must be at least **20% of the policy denominator**.

If this fails, the mechanism is surface-limited and the dose ladder is descriptive only. No larger
`lambda` is licensed.

## §37e — Gate 0b: dose must change enough buys in the right magnitude

At some positive dose, all of the following must hold:

1. **policy-level flip rate ≥20%;**
2. **median marginal-DPS improvement among flips ≥5% of current loadout DPS**
   (`median(m_new - m_incumbent) ≥ 5` percentage points);
3. **at least 90% of flips have strictly positive marginal-DPS improvement;** and
4. the per-run sum of one-step fractional improvements has median **≥0.33** across the 16 runs.

The fourth quantity is explicitly an **optimistic static upper bound**, not a simulated DPS
trajectory: counterfactual purchases would change later loadouts, gold and offers, so observed-state
gains cannot be accumulated causally. Its only valid use is a necessary-condition rejection: if even
this optimistic sum cannot reach §28's rough +33% planning ask, a live screen is not licensed. Passing
it does not establish a 33% realized gain.

Flip rate and the reachable surface use the full policy denominator. Magnitude summaries use only
valid baseline-reproduced eligible decisions and always print their denominator.

## §37f — Monotonicity and interpretation

With linear scores and fixed candidate slopes, policy-level flip rate should be non-decreasing in
`lambda`, and the selected `m` should never decrease. Any violation beyond tolerance is an
implementation error and voids the analysis, not noise.

**All of Gate 0a and Gate 0b must pass.** A pass licenses only a fixed-build live screen of realized
weapon-DPS trajectory through wave 11. It does not license shipping and is not survival evidence.

A failure is reported by cause:

- reachable surface <20% → **surface-limited**;
- reach exists but only very large lambda flips → **score-margin/dose-limited**;
- flips are common but median gain <5% → **magnitude-limited**;
- optimistic per-run sum <0.33 → **planning-deficit-limited**;
- controls fail → **measurement failure**, no policy verdict.

## §37g — Reported diagnostics, not barred

- all exclusions and coverage by run and wave;
- eligible and policy denominators;
- baseline score margin and marginal-DPS spread;
- flip counts/rates by dose, wave, candidate-category transition, and run;
- the fraction of flips that are weapon→weapon, item→weapon, weapon→item, and item→item;
- combine-pair involvement;
- score sacrificed versus marginal DPS gained;
- results with the two baseline-choice mismatches, if any, charged adversarially as non-flips;
- `lambda` at first flip for each reachable decision.

No p-value is used: this is a deterministic counterfactual over a fixed archived decision surface.
Runs, not decisions, remain the unit for the per-run upper-bound distribution.

## §37h — Exposure disclosure

Known before this preregistration: §30's 66.3% damage-bearing buys and 13.1% binary-tilt surface;
§36's 343-decision analysis set, 4.66% band-gate ceiling, and 340/343 pooled ranking reproduction;
the current sample contains 16 completed D5 ranger defeats at `0.2.79`, with terminal waves 6-14;
and one wave-1 offer/decision pair was inspected to verify the join schema and that `proj_dps_gain`
varies across candidates. No candidate marginal-DPS bonus, reachable count, counterfactual argmax,
flip, or Gate 0 statistic has been computed.

## §37i — Prediction, fixed before the result

**Prediction: Gate 0 is more likely to FAIL than pass, but for a different reason from §30 or §36.**

I expect the marginal-DPS term to expose some weapon→weapon flips that the binary damage tilt could
not see, so the reachable surface should exceed §30's 13.1%. I do **not** expect it to reach the 20%
policy-level bar once early-return buys, unranked decisions and already-DPS-maximal boards remain in
the denominator. If it does clear reach, I expect `lambda=1` or `2` to produce meaningful per-flip
gains; the least likely bar is the optimistic per-run 0.33 planning total.

This prediction is deliberately directional and falsifiable: a pass would show that the incumbent's
family/synergy score, not offer scarcity alone, leaves enough immediate clearance on early D5 boards
to justify a live screen. A surface-limited failure would rule out one more scoring mechanism without
re-running §30's binary tilt or §36's late full-slot gate.

## §37j — Measurement amendment after a control-only VOID, before any policy result

The first analyzer execution returned **VOID before computing Gate 0**: loadout trust was 44.8% and
ordinary-weapon gain parity was 88.3%, below the fixed 95% / 99% bars. No reachable count, dose flip,
or policy verdict was computed or printed.

The first failed loadout control exposed an omitted initial-state fact. `run_start.weapon` records the
selected weapon id once, but on **16/16** source runs the first shop decision reports weapon count 2,
tier sum 2, and effective DPS consistent with **two copies of that tier-I pistol**. There are zero
earlier shop decisions in each event stream. For this ranger population the replay must therefore
initialize with two copies of `run_start.weapon`, not one. This is a recovery of the actual initial
loadout from three recorded positive controls (count, tier sum, DPS), not a policy change.

The analyzer is amended only to use that two-copy initial state and to print row-level parity failures
if the independent `proj_dps_gain` control still misses. **No dose, denominator, bar, prediction, or
counterfactual rule changes.** The fixed controls remain binding; if the repair does not lift loadout
trust to 95% and weapon-gain parity to 99%, the result remains VOID.

## §37k — Second measurement amendment after a second control-only VOID

The two-copy initial-state repair lifted loadout trust **44.8% → 88.4%**, but the fixed 95% bar still
failed; independent ordinary-weapon parity remained 88.1% against its 99% bar. The analyzer again
returned **VOID before computing or printing any reachable count, dose flip, or Gate 0 result.**

All 27 printed parity failures identify the omitted state precisely: Crossbow (scales with range),
Taser/Icicle (elemental damage), or Shuriken (melee damage). `build_metrics.offense` records only
ranged damage, percent damage, attack speed and crit chance, while the live
`_projected_weapon_dps_gain` consumes the full build stats. Filling the missing scaling stats with
zero is therefore wrong; the positive parity failures caught it.

Those stats are recoverable without approximation from the same immutable event streams:

- Ranger starts with source-established **range +50**; the other missing weapon-scaling stats start
  at zero;
- every level-up choice records its selected effects;
- every bought shop item is joined to its recorded offer effects; and
- every crate choice is paired with its recorded crate-offer effects.

The replay will maintain the missing stat ledger from those transitions, while continuing to take the
four directly recorded offense stats from each decision. Loadout DPS validation and independent
`proj_dps_gain` parity remain the adjudicators: a missed dynamic/stat transition will fail the same
unchanged 95% / 99% bars. **No policy definition, dose, denominator, bar, or prediction changes.**
