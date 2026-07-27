# Pivot-fix qualification verdict — **PASS. Shipped default-ON.**

Protocol: `reports/wp2/pivot_fix_qualification_protocol.md`, committed `2a5636c` **before
trial 1**. Evaluator `scripts/wp2_pivot_qual_eval.py`. Build 0.2.48, 64 trials,
8 fixtures x 4 x 2 arms, arms alternating per round.

## Result

| | control (no fix) | treatment (pivot fix) |
|---|---|---|
| victory rate | **22/32 = 0.688** | **32/32 = 1.000** |
| damage mean | 67.2 | 23.2 |
| damage median | 64.0 | **20.0** |

**Difference +0.312, one-sided Fisher exact p = 0.000426.** Predeclared rule was
p < 0.05 AND treatment > control. **Both satisfied — PASS.**

Per fixture, treatment won **4/4 on all eight**. Control ranged 0/4 to 4/4:

| fixture | control | treatment |
|---|---|---|
| a00d393ad114f2cf | 0/4 | 4/4 |
| 6c32fe3d950f8d6e | 1/4 | 4/4 |
| 4ab34bffc43f89c3 | 3/4 | 4/4 |
| 56e65a951b357b1c | 3/4 | 4/4 |
| 7149d1b7ab27f0a8 | 3/4 | 4/4 |
| b02ffbeff221983d | 4/4 | 4/4 |
| cab349ba80106a37 | 4/4 | 4/4 |
| fc24b6eb79072a4d | 4/4 | 4/4 |

## Both gates passed, including the one that could have killed it

**Arm recording:** 0 mismatches, 0 infrastructure losses, 64/64 valid.

**Structural signature** — the claim this campaign rests on, and one the control arm
cannot fake: **0 rotating projectiles in 245,057 control observations** vs **326,151 in
617,798 treatment observations**. The arms could not have been confused.

**THE PRE-REGISTERED SURPRISE CHECK CAME BACK CLEAN.** The protocol stated in advance
that if the control arm landed near ceiling, something other than the fix had improved
the agent between builds and the earlier 111/111 attribution would be wrong. **Control
came in at 0.688, sitting squarely on its historical 0.651 / 0.703.** The historical
baseline was not confounded, and the attribution holds.

## What this closes

The wave-20 predator hazard — real since the beginning of this line, ~25-30% of runs
reaching wave 20 died there, and unexplained after two clean nulls (heading selection,
control rate). **It was a perception defect, not a steering one.** Nine
`enemy_projectile_rotating.gd` nodes parented under `Boss/Pivot` were invisible to a
collector that read only the direct children of one `Projectiles` node, and they
accounted for 84-91% of wave-20 damage.

Chain of evidence, each step measured rather than argued:
1. 84-91% of wave-20 damage had no cause within 80 u in the agent's own state; the
   invoker control showed **0%**.
2. A live scene dump found the nine nodes, `visible: true`, `damage: 23`, never collected.
3. Collecting them (with world velocity derived from the transform, since their own
   `velocity` reads 0) took unexplained damage to **0.0%**.
4. This campaign: 0.688 -> 1.000, p = 0.000426.

## Shipped

`finale_pivot_projectiles` flipped to **default-ON** in mod **0.2.49**.

**Policy version bumped 0.1.128 -> 0.1.129.** The policy CODE is unchanged, but the
teacher now sees a class of projectile it was blind to, so its decisions genuinely
differ. Without the bump, runs before and after would be indistinguishable in the
record — which is precisely how a 47-point win-rate collapse once ran ~20 versions
invisibly on this project.

## Honest limits

- **Predator only.** The invoker never had this defect (0% unexplained damage) and was
  not re-tested here. The fix iterates `es.bosses`, so it is inert on non-boss waves.
- **These 8 fixtures.** All are wave-19 predator snapshots from one character build
  (`character_well_rounded`, smg/stick). Generalisation to other characters is untested.
- **A ceiling, not a proof of perfection.** 32/32 means the fixtures no longer
  discriminate; it does not mean the agent is unbeatable. Harder fixtures would be
  needed to measure any remaining gap.
- **Downstream note:** captures now contain ~2.5x more projectile observations. Any
  student model or dataset built on pre-fix captures sees a different input
  distribution. `capture_schema_hash` is unchanged (`2823CB7E...1174`), so nothing
  breaks mechanically, but the distribution shift is real and matters for the student
  path.
