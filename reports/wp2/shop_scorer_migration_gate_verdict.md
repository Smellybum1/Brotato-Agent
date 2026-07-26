# Shop scorer-migration gate — VERDICT: does not clear. Line closed.

**Date:** 2026-07-26. Evidence base: the 20 F2 pure-teacher runs (10W/10L, policy
`0.1.125`), ids in `.tmp/f2_teacher_run_ids.txt`.
Tool: `scripts/wp2_perdecision_gain_ratio_diag.py`; raw output
`.tmp/perdecision_gain_ratio_full.txt` (884 lines) and `.tmp/perdecision_gain_ratio.json`.
Design context: `.tmp/pro_review_adoption_20260726b.md`.

## The predeclared gate

Written before the numbers were seen (adoption record §R2):

> If the shop path yields a materially larger flip count than the level-up path's
> 9/425, the collapsed-scorer migration is worth its program cost and the overkill
> telemetry becomes worth pricing. If the shop path also flips only a handful, then
> the entire raw-points defect is a real but low-yield uniform mispricing, and the
> correct action is to record it and redirect effort off this layer.

**Result: it flips a handful. NULL branch. The layer closes.**

## Two tooling defects found first — one voids a published result

**D1 — `can_buy` is null for every non-weapon offer.** Verified in the primary
session over all 20 runs: **5,044 non-weapon offers, 100% with `can_buy = None`**;
only weapons (3,107) ever carry a boolean (1,450 True / 1,657 False).
`wp2_shop_selection_diag.py::affordable_items()` filters
`i.get("affordable") and i.get("can_buy")`, so its "affordable alternatives" set
contained **weapons only**.

Therefore the published result — *"selection is clean: 0 gate misses, 0 soft misses
over 1,037 offense-deficient buys"* — did not find zero stat-item misses. **It could
not find one, by construction.** That result is VOID.

This is the `dropped_counts` failure mode repeated: an inference built on a field
without confirming the field varies. Before trusting the replacement, `affordable`
was checked and does vary for non-weapons (796 False / 4,248 True).

**D2 — `level_up_decision` events are duplicated in the raw logs.** Verified
independently: **574 events, 171 exact duplicates (29.8%), 403 distinct**, present
in every one of the 20 runs at 6-12 per run. The previously published
574 / 425 / 40 / 9 chain is inflated by ~30%; the "9 mispicks" is **5 distinct
decisions**.

## The measurement

### Level-up path (deduplicated)
66 rankable decisions / 20 runs. 24 mispicks, but **19 of those the teacher picked
an option with zero DPS gain** (defensive/utility — a DPS-only ranking is not
authoritative over them). **5 defined mispick ratios: 1.0618, 1.2686, 1.3960,
1.9207, 2.5616** — median 1.396x, only 2 above 1.4x. Across all rankable decisions
the median ratio is **1.0000x**.

### Shop path — the surface I claimed was ~100x larger
It is not. Of 1,037 offense-deficient buys: 457 bought a weapon, 294 bought an item
with no DPS-key effect, 286 bought a stat item with one. The **rankable denominator
is 91** — about 4.6/run against the level-up path's 3.3/run, i.e. **~1.4x, not
100x**. My "~52 per run" framing was wrong; it counted deficit buys, not decisions
with a rankable alternative.

Raw flips: **31 / 91 (34.1%)**, victory 16 / defeat 15 against a rankable split of
46/45 — **no W/L separation**, consistent with a uniform defect rather than a cause
of losing. Concentrated at waves 6-9.

Then three successive filters, each verified in the primary session:

| filter | remaining | reason |
|---|---|---|
| all flips | 31 | |
| teacher's pick had **positive** DPS gain | 11 | in 20, the teacher bought a zero/negative-DPS item (defence/utility); DPS ranking is not authoritative over those |
| DPS-best item was **not also bought** the same visit | 9 | a shop visit permits multiple buys, so buying the cheaper item first is not forgoing the better one. Checked: only **2 of 11** were also bought |
| best item carries **no unpriced drawback** | **4** | 5 involve `item_handcuffs` (×3) or `item_glass_cannon` (×2) |

On the drawback items: `item_glass_cannon` is `pct_damage +25, armor −3` — a real
defensive cost the DPS-only ranking ignores. `item_handcuffs` is
`melee+8, ranged+8, elemental+8` plus an `hp_cap` effect recorded as
**value 0, sign 0** — the telemetry does not carry the magnitude of its drawback at
all. A third structurally uninformative field.

**Clean, defensible flips: 4 across 20 runs = 0.20/run.** Counting all 9 that
survive the multi-buy check: **0.45/run**.

## Ruling

v128 was withdrawn partly because it changed **0.45 decisions per run**, explicitly
ruled *below the noise floor of any affordable campaign*. The shop path, measured
properly for the first time, delivers **0.20-0.45 defensible decisions per run**.
Adding the level-up path's 5 distinct mispicks (0.25/run) gives a combined
**~0.45-0.70/run**.

That is the same order as the change already judged not worth a cycle. The
five-stage collapsed-scorer migration — new combat metric, per-hit overkill
telemetry behind a mod deploy, atomic B/C/D collapse, fixture corpus, differential
audit, shadow scorer, evaluation campaign — cannot be justified by it.

**Per the predeclared rule: record and redirect off this layer.**

## What survives as durable findings

1. **The raw-point scoring is genuinely mis-dimensioned.** One point of ranged
   damage and one of attack_speed are not interchangeable; the measured per-point
   ratio is **median 9.40x** across all waves (p25 7.17, p75 12.16, range
   4.19-20.78). The earlier "6.4x" was the w12-19 mean.
2. **But the per-DECISION margin is ~1.4x**, because boards deliver the stats in
   different chunk sizes. Break-even realisation ratio across the 10 distinct
   boards offering both: median **~0.62**, and **2 of 10 exceed 1.0** (attack_speed
   is theoretically better there and no overkill story rescues ranged).
   **Do not ship a 6.4x corrective coefficient.**
3. **The "compounds six times" mechanism is falsified, with the sign backwards.**
   corr(weapon count, ranged/AS ratio) = **−0.67 pearson / −0.55 spearman**; by
   count the median ratio *falls* 16.67x (2 weapons) → 7.86x (6 weapons). The
   strongest predictor is mean per-weapon flat damage (**spearman −0.80**), exactly
   as the external review predicted. `ΔD/D = Σ(K_i·c_i)/Σ(D_i)` reproduces the
   measured gain to **pearson 1.0000** on all 244 validated exits.
4. The shop mispicks are **not** the ranged-vs-attack_speed story: no rankable shop
   board ever offered both simultaneously.

## Honest limits

- 32% of deficit buys (332) and 31% of shop exits (110) failed loadout
  reconstruction and are excluded. **Not missing at random** — they skew to
  loadouts containing weapons that never appeared on a recorded board. The verdict
  does not cover them.
- n=20, one build, teacher only; ~10 comparisons run across this line, so some will
  look significant by chance.
- The DPS ranking prices only DPS-key effects; no item drawback is priced anywhere.
- `stat_melee_damage`, `stat_elemental_damage`, `stat_damage`, `stat_crit_damage`
  have no recorded baseline in `build_metrics.offense`; baseline assumed 0.
