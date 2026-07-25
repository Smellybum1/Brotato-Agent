# Shop-layer conversion: PARTIAL verdict — gold conversion is exhausted, weapon selection is UNTESTED

> **CORRECTION, same day, before acting on this.** The first version of this
> document concluded the whole offense-conversion mechanism was exhausted. That
> overclaimed, and the error is mine. The selection test below scores
> `_direct_offense_gain`, which sums stat-item effects and feeds `stat_score`.
> But `combat_model.gd::offense_rating` returns
> `total = max(stat_score, weapon_score)`, and measured at shop exit across all
> 20 runs the **weapon term is the max in ~90% of exits at every wave**, by a
> widening margin (wave 19: weapon 273.8 vs stat 130.1; wave 10: 58.1 vs 40.8).
>
> So the quantity that discriminates winners from losers — `offense.total` — is
> **weapon DPS**, and the selection test measured the component that is almost
> never the max. The gold-side findings (banked gold, rich exits, economy) are
> unaffected: they are about gold, not about which term dominates. The selection
> finding is real but **narrow** — it establishes only that the buy loop does not
> pass over stat items. **Weapon purchase and combine selection remains
> untested**, and that is where the discriminating quantity actually lives.
>
> Corrected headline: gold conversion is exhausted. The shop layer is NOT closed.

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

**Established: gold conversion is exhausted.** At waves 14-16, losing runs have
the same gold as winning runs, bank no more of it, and do not pass over stat-item
offense. Nothing on the *gold* axis separates the outcomes, and three policy
versions have now been spent on that axis. **Do not ship a v128 aimed at gold
conversion.**

**Not established: that the shop layer is done.** The discriminating quantity is
weapon DPS (see the correction at the top), and no test here touches how weapons
are bought, upgraded or combined.

## The actual open question

`offense.total = max(stat_score, weapon_score)`, and the weapon term is the max in
~90% of shop exits. Winners reach above-target offense from wave 16 while losers
never do, on equal gold and equal boards. Since the stat axis is clean, the
divergence has to be arriving through **weapons** — which weapons get bought, which
families get committed to, and whether tier upgrades (combines) land.

That is squarely a shop-policy question, it is where `item_score` routes weapons
through a completely separate scorer (`_weapon_score`, not the effects path the
selection test exercised), and it is untested.

**Next measurement** — the weapon analogue of the selection diagnostic:

1. Reconstruct each run's equipped loadout at every shop (the v124 replay already
   does this, with per-shop validation against the recorded `weapon_dps`,
   `weapon_count` and `weapon_tier_sum`, so untrusted shops can be excluded).
2. For each weapon buy, compute the marginal `total_effective_weapon_dps` gain of
   what was bought versus every affordable weapon alternative on that board.
3. Split by outcome, focusing on waves 12-16 where the divergence opens.
4. Separately: count combines achieved per run by outcome, and how often a
   combine-completing weapon was affordable and not bought.

That distinguishes three live hypotheses which imply different work — bad weapon
selection (fixable in `_weapon_score`), missed combines (fixable in the combine
path), or weapon offer luck (not fixable, and would genuinely close the layer).

## A caveat that stays live either way

Of the 1,037 offense-deficient buys, ~939 bought a non-gate-clearing item, i.e.
gold went to defence and utility rather than to rerolls that would draw more
boards. That reroll-versus-buy allocation is still unexplored. It is ranked below
the weapon question because it is a gold-axis idea and the gold axis is where three
versions have already come back null — and because v117's cowardice lesson cuts
directly against buying less defence.

Honest limits on all of the above: n=20, one build, one policy, teacher only.
