# Wave 17 kills by MELEE CROWDING, and the separator is OFFENSE, not defense

22 wave-17 deaths (all of them) against 40 controls sampled from the 150 WP2-era
full runs that reached wave ≥18. 70,995 wave-17 captures. Archive only, no
machine time.

Wave 17 is **39% of all pre-wave-20 deaths**, and pre-20 deaths are **67% of the
loss budget that survives the pivot fix** (`loss_budget_after_the_fix.md`).

## What kills: ordinary melee enemies, fully visible

Attribution at the causal tick, all 7 buckets, player radius 12,
surface-to-surface:

| source | died at 17 (84 events) | survived 17 (31 events) |
|---|---|---|
| **enemies** | **78 = 92.9%** (med surface dist **−1.0 u**, 74/78 moving) | 22 = 71.0% |
| materials *(artifact, see below)* | 5 = 6.0% | 8 = 25.8% |
| projectiles | 1 = 1.2% | 1 |
| bosses / consumables / crates / obstacles | **0** | 0 |

**Unexplained residual: 0 of 115 events.** Nothing like the predator's blind spot.

Attacker identity: `pursuer` 51, `fin_alien` 17, `helmet_alien` 8, `baby_alien` 2
— all melee-contact types. **Enemy projectiles are near-irrelevant here** (1-4 of
84 depending on lag) despite the bucket being present on 42.6% of ticks. Wave 17
is the mirror image of the invoker, where 77% of damage was stationary
projectile fields.

Enemy composition at damage ticks is enriched ~2-3x across *every* type
(`fin_alien` 6.77 vs 1.92 at random ticks, `pursuer` 6.55 vs 4.25,
`helmet_alien` 4.39 vs 1.96) — **crowding, not one dangerous enemy.**

The `materials` rows are an attribution artifact: the player is standing on a
`gold.gd` pickup. Reassigning them raises the died-run enemy share to 98.8%; they
cannot be projectiles (nearest projectile 236-921 u in five of six).

**Zeros with their candidate-set sizes:** `bosses` is 0 observations in 70,995
captures — genuinely empty at wave 17, so that zero carries no information.
Crates appear on 12.8% of ticks, obstacles 25.0%, consumables 66.1% — all
non-vacuous candidate sets, all zero attributions.

## Instrument: wave 17's causal tick is lag 0, NOT lag −1

Median min surface distance over 115 HP-drop events:

| lag | −3 | −2 | −1 | **0** | +1 | random |
|---|---|---|---|---|---|---|
| median u | 46.1 | 33.1 | 12.7 | **0.9** | 3.5 | **217.8** |

At wave 20 the causal tick is the capture *before* the drop, because projectiles
despawn on impact. At wave 17 the attacker is a body that is **still touching**,
so the drop tick itself is correct. **The lag is a property of the damage
mechanism, not of the telemetry** — verify it per context rather than carrying
one over.

## THE SEPARATOR IS OFFENSE

Era-matched (18 died / 25 survived), Mann-Whitney rank-biserial P(died > surv);
0.5 = no separation:

| covariate | died | survived | P(died>surv) |
|---|---|---|---|
| **sum weapon damage** | **162.5** | **335** | **0.188** |
| dps proxy | 1,687 | 2,139 | 0.304 |
| mean enemies alive | 12.7 | 10.4 | 0.718 |
| speed | 526.5 | 499 | 0.697 |
| max_hp | 48.0 | 49 | 0.479 |
| armor | 3.0 | 3 | 0.426 |

**Doomed runs enter wave 17 with half the weapon damage. Defensive stats do not
separate at all.** The arena then fills: enemies alive at the death tick is 32
(median) against 9 at a random wave-17 tick, and the gap opens from ~25 s — enemy
HP pool alive at t=50 s is 2,839 for died runs vs 1,760 for survivors.

Wave 17 lasts exactly 60 s. Survivors reach it; died runs end at median 50.8 s.
Damage arrives in a few enormous hits — **median 0.333 of max HP per hit**, median
4 hits to die — while **23 of 40 survivors take zero damage all wave.**

## What this means, and the question it raises

This is not a movement or perception failure. It is a **build/offense** failure:
the agent kills too slowly, the arena saturates, and melee contact becomes
unavoidable.

**That sits in tension with the shop layer being closed as NULL**
(`brotato-shop-layer-findings`: rankable surface 91 decisions, ordering does not
flip). Both can be true — and the unresolved question is which:

- **(a) the shop policy chooses badly** — actionable, and would reopen that file; or
- **(b) low weapon damage is a SYMPTOM** of a run that was already gold- or
  XP-starved earlier, in which case wave 17 is where an earlier failure becomes
  fatal and intervening at wave 17 would be treating the wrong thing.

**This analysis cannot separate them**, and the distinction decides whether there
is anything to build. Per the standing rule, no fix should be designed until it
is settled — the same gate that returned NO-GO on the invoker.

## Caveats

1. **The fatal blow is never captured.** All 22 died runs' final wave-17 capture
   shows HP > 0 (2 to 16), then HP freezes and `run_end` fires. Every figure here
   is over *observed* hits, excluding the killing one.
2. `sum weapon damage` and the dps proxy disagree in magnitude (2x vs 1.27x)
   because median cooldown differs 7.0 vs 19.0 — different weapon classes, and
   the cooldown unit is unverified against this build. **Only the raw-damage gap
   is large; the dps proxy's absolute scale is not trustworthy.** Both point the
   same way.
3. `player_damage` amounts match HP drops 1:1 at wave 17 (no aggregation), but
   carry no position or attacker id — all attribution is proximity inference.
4. 22 deaths is the entire population, not a sample, but it is still 22.
