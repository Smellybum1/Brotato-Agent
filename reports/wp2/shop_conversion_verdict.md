# Shop-layer conversion: VERDICT — the offense-conversion mechanism is exhausted

Date: 2026-07-26. Evidence: the 20 pure-teacher runs of the Stage F2 campaign
(10 victories / 10 defeats), all on policy `0.1.125` / mod `0.2.34`, randomized,
same build. Tools: `scripts/wp2_shop_conversion_diag.py`,
`scripts/wp2_shop_selection_diag.py` (the latter reusing the v124 offer-replay
port of `_direct_offense_gain`, validated at 121/121 parity).

## The claim under test

Three policy versions were built on one premise, first formed on v122-era data:

> Losers die offense-starved with gold banked at waves 9-15.

v124 (rejected), v125 (reroll gate, qualified), v126 (bounded surplus reroll,
deployed) all attack the "with gold banked" half — the conversion of gold into
offense. Before building a fourth, the premise was re-measured.

## Result: the premise is half wrong, and the half the policy chain attacks is the wrong half

**1. Losers do die offense-starved.** Confirmed, strongly. Mean per-shop offense
deficit (the teacher's own `target - total`) is 38.4 in defeats vs 21.6 in
victories; at the final shop, 72.7 vs **-33.7** — winners finish *above* their own
target. This survives the wave confound in the conservative direction, since
defeats end at earlier waves where targets are lower.

**2. But not "with gold banked."** Banked gold does not discriminate at all —
mean carried out of shop 66.8 (defeat) vs 80.4 (victory). **Victories bank more.**
Restricted to waves 9-15: 94.8 vs 97.2. No separation.

**3. And rich exits are an early-game phenomenon, not a mid-game one.** Rate of
exiting a shop while offense-deficient with an affordable item still on the board:

| wave | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13-14 | 15 | 16 | 17-19 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| rate | .35 | .50 | .50 | .30 | .10 | .10 | .15 | **0** | **0** | .10 | **0** | .10 | **0** | .06 | .11 | **0** |

Zero at eight of the last twelve waves. Per run: 2.30 (defeat) vs 2.40 (victory) —
no separation. The mid-game rich-exit failure the chain was built to remove is
not present on this build.

## The selection hypothesis is also dead

If conversion is not the problem, the next candidate is *selection* — the v125
deploy record's own open item, that the reroll gate "governs rerolls only, not
which item the buy loop selects", evidenced by a wave-6 buy of `item_bat` over
`item_statue` at offense gain 40.

Re-scoring every board with the live gate's own arithmetic, restricted to buys
made **while offense-deficient** (the condition under which the teacher's own
policy says offense is the priority), over 1,037 such buys:

| test | result |
|---|---|
| **gate misses** — bought below the 6.0 gate while a gate-clearing item was affordable | **0** (0.0%) |
| **soft misses** — both clear the gate, but passed over a strictly stronger one | **0** |
| **big forgone** — an affordable alternative ≥6.0 and ≥6.0 better than what was bought | **0** |
| any affordable alternative with higher offense gain at all | 8 / 314 (2.5%), median forgone 2.0, **max 5.0** — all below the gate |

The buy loop never passes over offense. The largest offense gain it ever forgoes
is 5.0, beneath the threshold at which the policy considers an item to be
offense-relevant at all.

## It is not an economy problem either

Gold entering each shop is **the same** for winners and losers at every wave
(ratio victory/defeat 0.87-1.20, mostly ~1.00). At waves 14 and 15 — exactly where
the offense deficit begins to diverge — **defeats enter with *more* gold** (420 vs
368, 578 vs 521).

## Where the divergence actually is

Offense deficit by wave, defeat minus victory:

| wave | 1-8 | 9 | 10-13 | 14 | 15 | 16 | 17 | 18 | 19 |
|---|---|---|---|---|---|---|---|---|---|
| gap | 0.4-7.6 | 11.6 | -3.9 to 5.4 | 14.2 | 38.0 | 62.0 | 37.0 | 41.8 | 68.5 |

Winners and losers are indistinguishable through wave 13. The split happens at
**waves 14-16**, and winners cross to *above* target from wave 16. (Survivorship
caveat: only 4 defeats survive to waves 17-19, so the last three columns are
attenuated; the divergence is already unambiguous at 14-15 where 8 defeats remain.)

This reproduces the v82-era finding — "wins and losses identical through wave 12,
separated by est-DPS from wave 13" — on a completely different build and a
different campaign.

## Verdict

At waves 14-16, losing runs have **the same gold** as winning runs, **bank no more
of it**, and **select optimally from what they are offered**. Every decision the
shop policy actually controls is already being made correctly, and the losses
happen anyway.

**The offense-conversion mechanism is exhausted. Do not ship a v128 aimed at it.**

The surviving explanation is what the boards offer. A gate-clearing offense item
is present on only **9.5%** of offense-deficient boards, and that rate is
*identical* between defeats (9.4%) and victories (9.5%) — consistent with the v122
strength-drivers conclusion that run strength is late multiplier-stat offer luck.

## What is genuinely still open

One lever remains that the data supports and no version has tried. Of the 1,037
offense-deficient buys, roughly 939 bought an item that does **not** clear the
offense gate — legitimately, since no qualifying item was on the board. That gold
is spent on defence and utility, and it is gold that could instead have funded
**rerolls to draw more boards**. The existing gate blocks rerolling *past* a
qualifying item; nothing governs the reverse allocation — spending down the purse
on non-offense items while offense-deficient, leaving nothing to reroll with.

This is a real, unexplored, evidence-grounded hypothesis. It is also the kind of
change that the v117 "cowardice" lesson warns about: buying less defence to chase
offense can trade a survivable run for a dead one, and defence purchases are not
free to skip.

Two honest caveats on the whole analysis: n=20 on a single build and a single
policy, and this measures the *teacher* only. Nothing here establishes that more
board draws would convert into wins — only that draw count, not decision quality,
is where the remaining variance lives.
