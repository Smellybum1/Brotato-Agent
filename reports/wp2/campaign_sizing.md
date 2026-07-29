# How long should a campaign be?

> ## ⛔ CORRECTION 2026-07-29 — THE SIZING TABLE BELOW DOES NOT TRANSFER
>
> **What was claimed:** paired `damage_taken` is the standing primary endpoint, and
> 32 trials detects 19 damage / 64 detects 13 / 128 detects 9 against a control mean ~20.7.
>
> **What is now known:** `damage_taken` is a **GROSS** counter — it sums `player_damage`
> and **never subtracts healing**. Healing varied **15 to 171** across six agent runs
> checked. Any treatment that shifts healing, consumable pickup, lifesteal, or willingness
> to spend HP moves this endpoint without moving actual risk (or masks a real change). The
> variance structure in §"Measured variance" is therefore the variance of a contaminated
> quantity, and **every number in the sizing table rests on it**.
>
> **Replacement:**
> - **Terminal win from the wave-16 landmark** — confirmatory primary for run-to-terminal
>   campaigns. Variance components already measured: `sigma2_between = 0.0418`,
>   `sigma2_within = 0.1437`, **ICC 0.225** (`reports/wp2/landmark_continuation_pilot.md`).
> - **Death-adjusted HP-deficit AUC** — for fixed-wave mechanism screens.
>   `h(t) = HP(t)/max_HP(t)` while alive, `h(t) = 0` after death for the rest of the
>   horizon; `HP_deficit_AUC = (1/T)·∫₀ᵀ (1 − h(t)) dt`, lower is better.
> - **Gross damage is retained as a reported component only, never as primary.**
>
> **The power table must be rebuilt from scratch for the new endpoints. Do not size a
> campaign from the table below.** The structural guidance that survives is
> qualitative: pairing is not optional, precision depends on F × k, and the budget goes to
> **more fixtures, not more repeats**.
>
> **Evidence:** `reports/wp2/NEXT_SESSION_PLAN.md`,
> `reports/wp2/pro_answer_20260729_human_vs_agent.md`.

Standing guidance, derived from measured variance rather than habit. Written after
noticing that campaigns were being sized by precedent (128, then 64) instead of by the
effect they needed to detect.

## Measured variance — damage taken, wave-20 predator fixtures

From the co-rotation campaign's control arm (64 trials, 8 fixtures):

- between-fixture SD of the means: **20.7**
- within-fixture SD (pooled): **18.8**
- per-fixture means: 6.0, 7.9, 8.0, 8.5, 8.5, 20.8, 48.1, 58.1
- per-fixture within-SDs: 9.1 … 38.4

Fixtures are wildly heterogeneous, so **pairing is not optional** — it cancels the
between-fixture term. Only within-fixture noise sets the precision of a paired design.

## Sizing table (paired, damage taken, ~80% power, two-sided a=0.05)

| fixtures F | reps k / arm | trials | smallest detectable effect |
|---|---|---|---|
| 4 | 2 | 16 | 26 dmg |
| 8 | 2 | **32** | **19 dmg** |
| 6 | 3 | 36 | 17 dmg |
| 8 | 3 | 48 | 15 dmg |
| 8 | 4 | 64 | 13 dmg |
| 8 | 8 | 128 | 9 dmg |

Control-arm mean damage is ~20.7, so 32 trials sees anything that roughly halves damage.
128 trials only buys sensitivity to a ~9-damage effect.

**Precision depends only on the product F x k.** 8x2 and 4x4 are equally precise at 32
trials — so **always spend the budget on MORE FIXTURES, not more repeats**, because
distinct source builds are the generalisation unit. Prefer k=2 across many fixtures.

## The tiers

**SCREEN — 32 trials (8 fixtures x 2 x 2 arms), ~10-15 min at time_scale 8.**
Triage only. Read the EFFECT SIZE, not a p-value. Purpose is "does this do anything
large enough to care about?" No decision rule, no verdict, no shipping.

**CONFIRM — 64 trials, fresh sample, pre-registered decision rule.**
Only for candidates that survive the screen. Must be a FRESH sample: topping up a screen
and re-testing is optional stopping, which is exactly what made finale v2's campaign 1
look real before it reversed.

**QUALIFY — 64 trials, or fewer when the expected effect is large.**
The pivot fix qualification ran 64 for an effect of 0.688 -> 1.000; 32 would have
cleared p<0.05 comfortably. Size against the effect you expect, not the last campaign.

## When you still need the long form

- Effects under ~10 damage, or under ~15 pp on a binary outcome.
- Any binary outcome where an arm sits near the ceiling — win rate on the shipped build
  is pinned at 1.000 on these fixtures and cannot discriminate at any n. Use damage.
- Recorded power error worth not repeating: "64/arm gives ~80% power against ~19 pp" was
  wrong. It gives **61%**; 80% needs ~100/arm. Binary outcomes are expensive.

## Cheaper still

Damage (continuous) already carries far more information per trial than win rate
(binary). If more power is needed without more trials, reduce within-fixture variance
before adding trials — but never by selecting low-variance fixtures, which silently
selects easy ones.
