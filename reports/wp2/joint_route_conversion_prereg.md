# §40 — Gate 0 for a joint admission-plus-conversion route controller

**Written 2026-08-04 before the joint counterfactual is computed.** This reuses the eight §32 D5
Ranger runs, so the component results are already known; the exact joint policy below has not been
computed. No live run, deploy, or game launch is part of this gate.

## Why this is not a rerun

The in-range deficit remains open: the agent converts a median 0.2801 of the living pack into
shootable targets versus 0.4417 for the human comparison. The comparison is a D0 mediator, not a D5
outcome, but §28 independently establishes that D5 is clearance-limited.

The two route mechanisms already tested are closed individually:

- §32 added an in-range preference **inside the existing admitted set**. Median weight-free headroom
  was 0.0455, below its 0.05 bar.
- §33 lowered the PACK admission floor while retaining the existing continuity ranking. It flipped at
  most 11.05% and produced exactly zero median in-range gain while reducing body clearance.

Those results do not answer whether a newly admitted, conversion-improving lane can be selected,
because §32 could not see the lane and §33 did not prefer it. The reports explicitly left the
conjunction untested. This gate tests that conjunction once.

## Fixed policy

Population: the eight completed §32 runs at `0.2.76-wp2-capture`, nominal Danger 5, Ranger,
`route_scores_enabled=true`, unlock era `179/48/2018397571`. The force-killed smoke
`run_1785754086_12860` remains excluded for the already-recorded outcome-independent reason.

Target band: combat waves **1–11 only**. Later waves cannot repair the median D5 death at wave 11 and
the single long survivor must not redefine the mechanism.

At every `route.exit == "ranked"` capture with at least two recorded admitted lanes, a recoverable
baseline and previous-move vector, at least one living threat, a weapon range, and positive player
speed:

1. Rebuild the route admission set with `PACK = 80`, preserving the production projectile floor,
   enemy-penalty slack (20), loot-dash branch, wave-dependent slack, and emergency branch. The body
   critical constant remains 45; it is never lowered.
2. Advance the player along every admitted candidate at recorded speed for 0.60 s and advance each
   living enemy/boss by its recorded velocity for the same horizon.
3. Compute the fraction of living threats within the maximum held-weapon range.
4. Let `best` be the highest-in-range admitted lane, breaking exact ties with the reconstructed
   production score.
5. Select `best` only when its in-range fraction exceeds the recorded selected lane by **strictly more
   than 0.05**. Otherwise retain the recorded lane.

This is a lexicographic conversion controller with a fixed five-point deadband, not another weight
ladder. `PACK=80` is fixed as primary because §33 showed admission saturation by 80. `PACK=120` is a
conservative sensitivity and `PACK=45` is an extreme ceiling; neither can rescue a primary failure or
license implementation by itself.

## Denominators and exclusions

The analyzer prints, before results:

- summaries scanned, selected runs, and every arm-validity failure;
- all wave-1–11 combat captures carrying a route block;
- ranked captures and the final analysis-set denominator;
- every exclusion reason and per-run contribution.

A zero is reportable only with its denominator. The full capture stream is used (`stride=1`); there
is no post-result sampling choice.

## Controls — evaluated before results

The counterfactual is **VOID** unless all controls pass:

1. Exactly eight runs pass version, instrument, terminal-summary, character, danger, opener and era
   checks.
2. Recovered `align` and `cont` vectors reproduce their recorded terms within 0.01; failures are
   excluded and counted.
3. The production floor model matches recorded `body_floor` on at least 99% of eligible captures.
4. Reconstructed admission at `PACK=160` matches recorded skips on at least 99%.
5. Reconstructed production selection at `PACK=160` matches recorded `sel_x/sel_y` on at least 99%.
6. A disabled policy changes exactly 0 analysis-set decisions.
7. The primary policy has both a branch where `PACK=80` adds lanes and a branch where it adds none.
   Otherwise the mechanism or its negative control is vacuous.
8. The self-test must demonstrate: a synthetic joint-only positive (neither component alone selects
   the good lane, the conjunction does), a no-gain negative, moving-enemy sensitivity, monotone
   admission as PACK falls, and preservation of projectile/critical safety.

Controls precede results in console and JSON. If a bar in 1 or 3–6 fails, the analyzer emits `VOID`
and refuses to compute the policy verdict.

## Preregistered bars — primary `PACK=80` only

All must pass to license implementation:

### Exposure and stability

- Primary flips: **at least 20%** of the analysis-set denominator.
- At least **7/8 runs** contribute a primary flip.
- Leave-one-run-out flip rate: minimum **18%**, median **20%**.
- Largest run contributes at most **25%** of primary flips.

### Conversion magnitude

- Median in-range gain over flipped captures: **at least 0.10**. This is deliberately above the 0.05
  deadband, so the statistic is not guaranteed to pass by construction.
- Integrated one-step gain, treating every non-flipped and out-of-analysis wave-1–11 route capture as
  zero: **at least 0.02**. This prevents a large conditional gain on a tiny tick surface from passing.

### Geometry safety

- Median `new_body_clearance / old_body_clearance` over flips: **at least 0.80**.
- 10th percentile of that ratio: **at least 0.60**.
- On 100% of flips, the chosen lane preserves the recorded projectile floor.
- On 100% of flips where the new lane is below 45 body clearance, it is no worse than the recorded
  lane. This preserves the production emergency branch rather than manufacturing new subcritical
  exposure.

Low-HP exposure is not inferable from a single-tick replay. These geometry bars are necessary but not
sufficient; a passing Gate 0 would still require the §31 low-HP veto in a live mediator screen.

## Prediction

**Prediction:** the joint policy will pass exposure and conditional conversion, because §33 measured
withheld in-range opportunity that §32's current admitted set could not express. I put the geometry
safety bars at **less than even odds**: the mechanism deliberately admits lower-clearance lanes, and
§33 already measured a roughly 24% clearance cost without benefit. Overall Gate 0 pass is therefore
less than even odds.

## Interpretation contract

A pass licenses implementation and a short, preregistered in-range/low-HP mediator screen. It does
not establish survival benefit and does not license a D5 win claim. A failure closes this exact joint
route mechanism. It does not erase the measured in-range gap, but it forbids another PACK/route-score
variant unless it reaches a different tick surface or supplies new information unavailable here.
