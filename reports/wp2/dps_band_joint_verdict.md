# §36 — Gate 0 for the JOINT DPS-band lever: RESULT

**VERDICT: BOTH GATES FAIL. DO NOT IMPLEMENT.** Max flip rate **2/343 = 0.0058** against a **0.20**
bar — short by a factor of ~34 — and the failure is **structural, not a dose failure**.
Pre-registration `reports/wp2/dps_band_joint_prereg.md` (`22ddf02`) + §36c amendment (`75381e5`),
both committed before any flip was computed. Script `scripts/wp2_dps_band_joint_gate0.py`
(`--self-test`, 15 checks, exit 0 read directly). Data: the 16 instrumented D5 ranger runs at
`0.2.79` (`494332a`).

## §36j — Denominators

16 runs, all D5 ranger, all defeats, terminal waves 6-14 (median ~11, matching the D5 baseline).
**Analysis set 343** shop_buy decisions, waves 1-11, with `board_scores` + `board_meta` and ≥1 scored
candidate. Excluded and counted: `not_shop_buy` 623 · `no_board_scores_or_meta` 68 ·
`wave_outside_1_11` 6.

## §36k — Controls: all pass, and one of them is the whole point

| control | result |
|---|---|
| 1. cell-wise reproduction of the emitted action | **340/343 = 0.9913** pooled |
| 2. **ARM A baseline (W=13, k=1.00) must flip exactly 0** | **0 flips** ✅ |
| 3. **ARM C target-only (W=13, k=1.75) must flip exactly 0** | **0 flips** ✅ |

⭐⭐ **ARM C IS THE STRUCTURAL CONTROL AND IT HELD.** The prereg fixed in advance that raising the
target while leaving the gate at wave 13 **must** flip exactly zero at waves ≤ 11, or the source
reading is falsified and the analysis is void. It flipped zero. **The claim that the detector never
runs below wave 13 is now confirmed three ways**: from source, from the live build (`band_gate` recorded
**False on all 899** decisions across the campaign, including the 7 at wave 13), and from this
counterfactual.

Cell-wise reproduction, per the prereg's both-ways rule:

| slots_full | top is weapon | reproduction |
|---|---|---|
| no | no | 77/78 = 0.9872 |
| no | yes | 154/154 = 1.0000 |
| yes | no | 95/95 = 1.0000 |
| **yes** | **yes** | **14/16 = 0.8750** |

The fourth cell is owned by a sell-or-defer branch (archive read 0.7097 on it). **It was NOT excluded**
— the lever acts there, so excluding it would select on the quantity of interest.

## §36l — GATE 0a-i: FAIL

| W | k | n | flips | rate | excl-cell rate |
|---|---|---|---|---|---|
| 1 | 1.25 | 343 | 1 | 0.0029 | 0.0000 |
| 1 | 1.50 | 343 | 2 | **0.0058** | 0.0000 |
| 1 | 1.75 | 343 | 2 | **0.0058** | 0.0000 |
| 6 | 1.25–1.75 | 343 | 1 | 0.0029 | 0.0000 |
| 9 | 1.25–1.75 | 343 | 0 | 0.0000 | 0.0000 |

Arm B (gate-only) reads 0.0029 / 0.0029 / 0.0000 at W = 1 / 6 / 9.

⭐ **BOTH READINGS AGREE.** All-cells peaks at 0.0058; excluding the untrustworthy cell it is
**0.0000** at every dose. The prereg declared that disagreement ⇒ *fragile to the unmodelled sell
branch*; they agree, so **the verdict is robust**, and note that every flip observed lives inside the
one cell the model reproduces worst.
⚠️ **Monotonicity is VACUOUS at W = 6 and W = 9** (all doses identical) and is reported as such rather
than as support — §35's lesson applied in advance.

## §36m — GATE 0a-ii (the interaction): FAIL

Required `flip(D) > flip(B) + flip(C) + 0.10`, i.e. > 0.1029 at W=1. Observed max **0.0058**.
Since arm C is exactly 0 and arm B is 0.0029, the joint arm adds **at most 0.0029** over gate-only.
**There is no interaction to find.**

## §36n — ⭐⭐⭐ WHY: A STRUCTURAL CEILING OF 4.66%, INDEPENDENT OF THE DOSE

The gate drops a candidate only when **`slots_full` AND `not pairs_combine` AND
`proj_dps_gain < band_impact_floor`**, and a *decision* only flips when the dropped candidate is the
**winner**. Decomposed on the analysis set:

| | n | share |
|---|---|---|
| analysis set | 343 | — |
| `slots_full` | 111 | 0.3236 |
| **`slots_full` AND the winner is a WEAPON** | **16** | **0.0466** ← **CEILING** |
| …of those, **combine-exempt** (`pairs_for_combine`) | **14** | — |
| …would actually be dropped | 2 | — |

⇒ **Even if EVERY qualifying winner were dropped, the ceiling is 16/343 = 0.0466 — under a quarter of
the 0.20 bar, and completely independent of `k` or `W`.** The dose was never the binding constraint.

**The mechanism, stated plainly:** the band gate was designed for **late-game full-slot boards where
filler guns compete for gold**. At D5 the agent is still assembling its loadout — slots are full on only
32% of decisions, the winner is a weapon on only 4.7% of those, and **87.5% of that remainder is combine
fodder, which the gate deliberately exempts.** The gate is not mis-tuned for D5; it is **structurally
aimed at a board state D5 runs rarely occupy.**

## §36o — ⚠️ WHAT IS *NOT* REFUTED

⛔ **The two §36 defects are REAL and stand unrefuted.** The DPS target *is* calibrated on 41 Danger-0
victories, and the detector *is* gated at wave 13 while D5 dies at 11. Both were measured, and arm C
confirms the second behaviourally. **What is refuted is that the BAND GATE is a usable instrument for
exploiting them** — its guard conjunction is too narrow at D5.

⇒ A different mechanism acting on the same D0-calibration defect is **not excluded by this result** —
e.g. one that acts on scoring rather than on candidate admission, or that is not conditioned on
`slots_full`. Such a lever would need its own Gate 0. ⛔ But it may not be justified by re-citing §36's
measurements as though this verdict did not happen.

⚠️ **Prediction accounting:** §36h put the interaction bar at **less than even odds** and it failed.
That was on record before the data. ⛔ It does **not** license reading the failure as "expected all
along" — the *reason* it failed (a 4.66% structural ceiling from the guard conjunction) was **not**
predicted, and the prereg's stated reason (already-damage-heavy buying, §30) was **wrong**.

## §36p — What this closes

**The shop-valuation layer is closed at D5**, alongside §30's damage tilt. Combined with §31-§35
closing the movement command:

> **No reachable parameter in either the movement policy or the purchasing policy changes D5
> behaviour in a beneficial direction.**

⇒ The next move must be **structural**, not a parameter: a danger-aware decision layer (the layer is
currently danger-blind — the only `danger` hit in the whole decision tree is the literal string
`"item_dangerous_bunny"`), or re-deriving the winner trajectory at D5 — which needs a D5 victory that
does not yet exist (the bootstrap named in the scoping report).
⚠️ **Scope:** 16 runs, one character (ranger), one build, one era. This bounds the *reachability* of
this lever, not the size of the underlying deficit.
