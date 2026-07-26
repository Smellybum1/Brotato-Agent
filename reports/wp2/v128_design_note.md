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

## Expected effect, stated in advance

A **uniform** lift in offense trajectory across all runs, not a targeted fix to
losing runs — the 6.4x mispricing is present equally in both arms (6.55x defeat,
6.52x victory). Predicting a win-rate improvement is NOT part of this gate; n=20
could not resolve one, and claiming it would be overreach. The claim being tested
is narrower and checkable: **the agent should end up with more ranged_damage and
less attack_speed for the same level-up opportunities, and higher loadout DPS as
a result.**
