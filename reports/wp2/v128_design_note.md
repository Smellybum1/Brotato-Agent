# v128 design note — WITHDRAWN: the proposed change is INERT

> **OUTCOME: the change below was implemented, checked against the arithmetic, and
> REVERTED before shipping. It flips none of the 9 decisions it was designed to
> fix.** The version bump to policy `0.1.128` / mod `0.2.37` was kept, because a
> deploy is independently owed for the mod-ready sentinel. See "Why it is inert".
>
> This is the third time in this session that a conclusion survived until one more
> step of arithmetic was done. The pattern is worth naming: **a mechanism being
> real is not the same as a mechanism being load-bearing.**

## Why it is inert (the calculation that killed it)

`score0 = _effects_value + _late_shop_pivot_bonus`, and BOTH contain raw-point
terms besides the `gain0 * 6.0` this change removes:

- `combat_value` (inside `_effects_value`) adds
  `score += v * gain * flat_damage_value` for every key in `_DAMAGE_STATS`.
  For well_rounded `flat_damage_value = 0.55`, `dps_gain_weight = 1.45`.
  Note `_DAMAGE_STATS` **excludes `stat_attack_speed`**.
- `_late_shop_pivot_bonus` weights raw points almost equally across the three
  offense stats — mid tier (waves 9-14) `ranged 2.40/0.95`,
  `attack_speed 2.10/0.85`, `percent_damage 1.85/0.70`, gated on
  `offense < OFFENSE_FLOOR_MID (70)`.

Worked on the real wave-12 case (loadout DPS 792.1, `offense ≈ 94 > 70`):

| option | DPS term (×1.45) | flat term (×0.55) | pivot | **score0** | old rank (+gain×6) |
|---|---|---|---|---|---|
| ranged_damage+2 | 18.21% → 26.40 | 1.10 | 1.90 | **29.40** | 41.40 |
| attack_speed+15 | 13.04% → 18.91 | — | 12.75 | **31.66** | 121.66 |

`score0` alone still picks `attack_speed`. The wave-10 case behaves the same
(13.26 vs 15.87). Removing `gain0 * 6.0` changes the *margin* but not the
*ordering*, because the pivot bonus's raw-point weighting already favours the
high-raw-point option once the larger term is gone.

**The real lever is `_late_shop_pivot_bonus`'s coefficients**, which price a raw
point of attack_speed at 0.85-2.10 against a raw point of ranged_damage at
0.95-2.40 — a ratio of roughly 1.1-1.15x, where the measured DPS ratio is **6.4x**.
That was explicitly placed out of scope in this note (six string pins across the
test suite), and placing it out of scope is what made the remaining change
powerless.

**Any successor must be gated on the arithmetic BEFORE implementation:** compute
`score0` for both options on the real fixtures and show the ordering actually
flips. A replay showing "the teacher picked the worse option" is necessary but NOT
sufficient — it does not establish that the proposed edit changes that pick.

---

# Original design note (superseded, retained for the reasoning trail)

# v128 design note — remove the raw-points override in level-up ranking

Date: 2026-07-26. Status: **DESIGN, not implemented.** Predecessor evidence:
`levelup_stat_mispricing.md` (the 6-16x measurement),
`shop_conversion_verdict.md` (the four null axes).

## The defect, corrected

My first framing was "the level-up path prices stats by raw points instead of
DPS, unlike the weapon path." Code mapping shows that is **wrong in an important
way**, and the correction makes the fix smaller and safer.

`decide_levelup`'s offense-deficient branch ranks by:

```gdscript
var score0 := (_effects_value(effects0, build, wave, profile)
    + _late_shop_pivot_bonus(effects0, build, wave, profile))
var rank0 := score0 + gain0 * 6.0        # gain0 = _direct_offense_gain(effects0)
```

and `_effects_value` is **already DPS-aware**:

```gdscript
func _effects_value(effects, build, wave, profile) -> float:
    var combat := BotCombatModel.combat_value(build, _combat_deltas(effects), wave, profile)
    return combat + _utility_score(effects, wave, profile)
```

`combat_value` computes `100 * (dps1 - dps0) / dps0` over the equipped loadout.
So the base score already prices marginal DPS correctly.

**The defect is that `gain0 * 6.0` adds a raw-stat-point term on top of a correct
DPS score, and that term dominates the comparison.** Illustrative magnitudes at
wave 15 (measured marginal values: ranged 4.72%/pt, attack_speed 0.785%/pt):

| option | score0 (DPS-based) | `gain0 * 6.0` (raw) | rank0 |
|---|---|---|---|
| +6 ranged_damage | ~28 | 36 | ~64 |
| +6 attack_speed | ~4.7 | 36 | ~41 |

The DPS signal separating these two is ~23 points; the raw term contributes an
identical 36 to both and compresses the gap. The scorer is not blind — it is
being shouted over.

## The change

**Rank by `score0` alone; keep `gain0` as the filter it already is.**

The branch already filters to `gain0 > 0.0` and `score0 > 0.0` before ranking, so
`gain0`'s job of "consider only genuine offense options when offense-deficient"
is fully preserved. Deleting the `+ gain0 * 6.0` term removes the distortion and
lets the existing DPS-aware score do the ordering it was built to do.

This is a **deletion**, not a new scoring model. No new plumbing: `decide_levelup`
already receives the full loadout (`_build_dict()` supplies per-weapon `damage`,
`cooldown`, `scaling`, `crit_*`, `nb_projectiles`, `piercing`, `bounce`, `sets`).

### Explicitly OUT of scope

- **Do not touch `_direct_offense_gain()` itself.** Six other call sites use it as
  a boolean threshold against a constant (including `_board_has_gate_clearing_offense`,
  the v124/v125 reroll gate). Rescaling it would move all six at once and
  destabilise the v125/v126 evidence chain for no benefit. Two Python mirrors
  (`scripts/wp2_offer_dps_replay.py`, `test_shop_policy_source.py::_v125_direct_offense_gain`)
  would also silently desynchronise — they mirror it "exactly" and no test would
  go red.
- **Do not touch `_late_shop_pivot_bonus` coefficients** (ranged 2.75/1.75,
  attack_speed 2.40/1.50, percent_damage 2.10/1.30). They are raw-point weights
  too and they under-separate the stats (1.15x where the truth is ~6x), but they
  are string-pinned across six tests and they at least order the three stats
  correctly. One change at a time; revisit only if v128 qualifies and the effect
  is smaller than predicted.
- The dead level-up reroll branch (`reroll_price` is hardcoded `0` at
  `agent_controller.gd:1511`, and the branch requires `> 0`). Noted, not fixed here.

## The safety problem this change has to solve for itself

**No test executes `decide_levelup`.** Every pin on it is a verbatim source-string
assertion, and `test_shop_policy_source.py:94` pins the *fallback* branch's scoring
expression, not the offense branch's. So this change can alter live behaviour with
the suite fully green — the same failure mode as the v126 parse error, where a
source pin asserted a fatal line and 526 tests passed on an unloadable mod.

Therefore the gate for v128 is **not** "tests pass".

## Predeclared gate

**1. Offline counterfactual replay (primary, must run BEFORE any deploy).**
Mirror both ranking expressions in Python and replay every recorded
`level_up_decision` from the 20 F2 pure-teacher runs — the events carry
`legal_alternatives` with full effects, so the entire option set is recoverable.
Report:
- how many choices change, overall and by wave;
- for each change, the marginal DPS of the old pick vs the new pick on the
  validated loadout;
- **net predicted DPS delta per run**, and the sign of it.

PASS requires: the change is not cosmetic (>=5% of offense-branch choices move),
and net predicted DPS delta is **positive in a clear majority of runs**. If the
replay says choices barely move, v128 is not worth a deploy cycle and should be
dropped. If it says they move a lot but net DPS falls, the model of the defect is
wrong and the change must not ship.

**2. Behavioural test, new.** A Python mirror of the offense-branch ranking with
fixture option-sets, asserting the ordering is by DPS and not by raw points —
mutation-checked by reinstating `+ gain0 * 6.0` and confirming it fails. This is
the safety net the path currently lacks entirely.

**3. Smoke gate.** One isolated smoke on the bumped build: zero safety violations,
clean capture audit, and **wave >= 16 or victory** (the standing behavioural bar
from the bc_v3_a precedent). A parse check first — this build also carries the
undeployed mod-ready sentinel, whose GDScript has never been parsed.

**4. Anti-cowardice check (v117 lesson).** The predicted effect is more
ranged_damage and less attack_speed, which is a pure offense reallocation and
should not cost defence. Confirm in the smoke that `defense.total` at each shop
exit is not systematically below the v127 smoke's trajectory. If offense is being
bought with survivability, that is a fail regardless of DPS.

## GATE RESULT (run 2026-07-26) — mechanism confirmed, opportunity small

`scripts/wp2_levelup_replay_diag.py` replayed all 574 recorded level-ups across
the 20 F2 pure-teacher runs; 425 validated (149 skipped where the loadout could
not be validated — excluded, not guessed). Event integrity verified directly:
`level_up_offer` count equals `level_up_decision` count in every run sampled and
all seqs are distinct, so the repeated rows are genuinely distinct level-ups at
the same build state, not double-emission.

**The ranking term is inert in 90.6% of level-ups:**

| offense-eligible options on the board | decisions | share |
|---|---|---|
| 0 | 172 | 40.5% |
| 1 | 213 | 50.1% |
| **2** | **40** | **9.4%** |

With 0 or 1 offense option there is nothing to rank, so `gain0 * 6.0` cannot
change the outcome. Of the 40 decisions where it *could*, the teacher chose an
offense option 32 times and picked the lower-DPS one **9 times**.

**So v128 would change 9 of 425 decisions — 2.1%, or 0.45 per run.**

| wave | outcome | chose | better offense option | DPS gap | % loadout |
|---|---|---|---|---|---|
| 12 | victory | percent_damage+12 | ranged_damage+3 | 134.2 | **12.41%** |
| 12 | victory | attack_speed+15 | ranged_damage+2 | 40.9 | 5.17% |
| 12 | victory | attack_speed+15 | ranged_damage+2 | 40.9 | 5.17% |
| 10 | defeat | attack_speed+5 | ranged_damage+1 | 18.8 | 3.41% |
| 10 | defeat | attack_speed+5 | ranged_damage+1 | 18.8 | 3.41% |
| 12 | defeat | attack_speed+5 | ranged_damage+1 | 12.1 | 1.12% |
| 12 | defeat | attack_speed+5 | ranged_damage+1 | 12.1 | 1.12% |
| 11 | defeat | attack_speed+15 | percent_damage+12 | 5.1 | 0.64% |
| 11 | defeat | attack_speed+15 | percent_damage+12 | 5.1 | 0.64% |

Median 3.41% of loadout DPS, max 12.41%. Six in defeats, three in victories.

**The mechanism is confirmed exactly as predicted.** `attack_speed+15` over
`ranged_damage+2` is the raw-points failure in the wild: `gain0 * 6.0` scores them
90 vs 12, while the true marginal DPS favours ranged by 40.9. There is no doubt
about *what* is happening — only about whether it happens often enough to matter.

### Ruling

My predeclared bar ("≥5% of offense-branch choices move") was **written
ambiguously** and I am not going to let the ambiguity decide this. Against the 40
rankable decisions it is 22.5% (pass); against all 425 level-ups it is 2.1%
(fail). Ruling on substance instead:

**Implement, but bundle it — do not spend a deploy cycle on it alone.**

- The opportunity is genuinely small: ~0.45 decisions per run, median 3.4% loadout
  DPS, concentrated at waves 10-12.
- The change is **structurally safe in a way the original design could not
  guarantee**: it only reorders *within* the offense-filtered set, so it cannot
  buy offense at the cost of defence. **Predeclared gate 4 (anti-cowardice) is
  therefore moot** — there is no defensive option in the set being reordered.
- A version bump and smoke are **already owed** for the committed-undeployed
  mod-ready sentinel. v128 rides along at near-zero marginal cost, exactly as v126
  rode along with v127.

### Revised expectation, stated before implementing

This will **not** measurably move win rate and must not be claimed to. n=20 could
not resolve an effect this size, and 0.45 decisions per run at ~3% loadout DPS is
below the noise floor of any campaign this project can afford. The honest claim is
narrower: **a small, strictly-positive, zero-downside correction to a confirmed
scoring defect**, shipped because the deploy cycle is already being paid for.

If the smoke is clean, that is the whole result. No campaign should be run to
"prove" v128 works.

## Expected effect, stated in advance

A **uniform** lift in offense trajectory across all runs, not a targeted fix to
losing runs — the 6.4x mispricing is present equally in both arms (6.55x defeat,
6.52x victory). Predicting a win-rate improvement is NOT part of this gate; n=20
could not resolve one, and claiming it would be overreach. The claim being tested
is narrower and checkable: **the agent should end up with more ranged_damage and
less attack_speed for the same level-up opportunities, and higher loadout DPS as
a result.**
