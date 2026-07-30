# Danger 5 — the dodge/armor hypothesis, priced

Date: 2026-07-30. Sample: the **9 valid D5 attempts on `0.2.60`** (`run_1785372250_76725` excluded).
Prompted by the external D5 guide (B the No-Self), whose **#1 named failure point** is *"neglecting
dodge/armor → one-shot deaths mid-run"* and which targets **20-30 dodge by wave 10, cap 60 by wave 15**.

## 1. The observation is real

End-of-wave medians across the 9 runs:

| wave | n | dodge | armor | max_hp |
|---|---|---|---|---|
| 1-10 | 7-9 | **0.000** | 0.0 → 2.0 | 16 → 50 |
| 11 | 5 | 0.050 | 1.0 | 48 |
| 12 | 4 | 0.025 | 0.5 | 47.5 |
| 13 | 3 | 0.060 | 2.0 | 51 |
| 14 | 3 | 0.110 | 2.0 | 49 |

**The agent reaches wave 10 with median dodge 0.000 in every run**, and armor never exceeds ~3.
Dodge at the terminal capture: `0, 0.06, 0.03, 0.13, 0.05, −0.03, 0, 0.11, 0.21` (median 0.05) — one
run is **negative**, i.e. it took a dodge-penalty item.

## 2. It is NOT a blanket rejection — the zero has a denominator

Over 612 deduplicated shop boards in those 9 runs:

| | count |
|---|---|
| dodge/armor-positive item offers | **106** |
| ...affordable | **84** |
| ...**bought** | **20 (24% of affordable)** |

So the scorer **does** buy defensive items. "The policy refuses defense" would have been wrong, and
this is exactly the check that made the Piggy Bank zero meaningful.

Dodge-positive purchases by wave: **6 in waves 1-10** (blindfold w6, blindfold w8, chameleon w9,
gambling_token w9, blindfold w10, clover w10) and 4 at waves 11+. **So a "buys defense too late"
hypothesis is also refuted** — it buys dodge before wave 10 when offered.

**The median is 0.000 because most runs acquire NONE:** dodge items appear only **25 times across 9
runs in waves 1-10** (~2.8 per run) and carry small values (+5 blindfold, +6 clover, +8
gambling_token, +23 chameleon).

## 3. ⭐ The causal-vs-actionable check (prereg §9) — the target is at or above the ceiling

Total `stat_dodge` points **on offer** per run, deduplicated boards, all waves:

| run | offered | affordable |
|---|---|---|
| 375783_49189 | 73 | 73 |
| 376267_17317 | 61 | 61 |
| 379065_79119 | 58 | 41 |
| 1785378099_4 | 38 | 33 |
| 377362_39811 | 22 | 22 |
| 379553_81292 | 16 | 16 |
| 375041_58384 | 10 | 4 |
| 377081_97257 | 4 | 4 |
| **378663_61620** | **0** | **0** |

**Median affordable: 22 points, across ALL waves.** Pro-rated to waves 1-10 (25 of 34 dodge offers sit
there) that is **~16 points**.

The guide asks for **20-30 by wave 10**. So:

- A policy that bought **every affordable dodge item in the entire run** would reach a **median of 22**
  — the bottom edge of the target — and only **~16 by wave 10**.
- **One run had literally zero dodge points offered**, so the target was unreachable there at *any*
  policy.
- And that ceiling is not free: buying the whole dodge budget means **forgoing offense**, which is the
  measured separator at wave 17 ([[brotato-wave17-offense]]).

**Verdict: the dodge gap is substantially an OFFER-SCARCITY constraint, not purely a valuation
failure.** "Neglecting dodge" is not the free lever the guide implies *for this agent at this offer
rate*. This is the §9 pattern exactly: a real, correctly-described deficit that the policy could not
realistically close through the shop.

## 4. ⚠️ What must NOT be concluded

- **Dodge-at-death correlates weakly with terminal wave** (0→w7, 0.06→w9, 0.03/0.13→w10, 0.05→w11,
  −0.03→w12, 0/0.11→w14, 0.21→w15). **This is CONFOUNDED exactly like `materials_spent`:** surviving
  longer means more shops means more chances to buy dodge. The arrow is unidentified. **Not a finding.**
- Nothing here shows dodge *would* rescue these deaths. The guide's claim is untested on our agent.
- Armor values of 1-3 are near-noise; no separate armor analysis is attempted at this n.

## 5. The experiment this selects

The cheap causal test is a **dosed grant, not a policy change**: set dodge directly via a save edit at
a wave-10 D5 fixture and ask whether the same states survive. That establishes whether dodge is
**causal** at Danger 5 at all — and it costs no scoring work.

Then apply §9: if a rescue needs ~30 dodge and the shop offers a median of 16 by wave 10, the mechanism
is **causal but not actionable**, and the correct outcome is to close the path rather than build another
scoring layer. Gets its own pre-registration.

Related: [[brotato-wave17-offense]] (offense is the separator), [[brotato-measurement-discipline]] §9.
