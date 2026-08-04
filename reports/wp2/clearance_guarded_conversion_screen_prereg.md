# §42 — Live mediator screen for clearance-guarded route conversion

**Pre-registration. Written 2026-08-04 before build 0.2.80 is deployed and before any §42 run is
launched.** The §41 offline result and the 0.2.80 implementation already exist; no live observation
from that implementation was available when these bars were fixed.

## Question and interpretation boundary

§41 established that the exact PACK-80 conversion rule has a large recorded action surface while
preserving its per-decision projectile and body-clearance rules. This screen asks the next, narrower
question:

> When enabled live at nominal Danger 5, does the rule reach the final command and raise realised
> in-range opportunity by a detectable amount without increasing low-HP exposure?

This is a **mediator and safety screen**, not a survival campaign. A pass licenses a separately
pre-registered survival campaign. Terminal wave and victories are context only here; neither may
rescue a failed mediator or safety bar. A victory still satisfies the project's north star as a game
event, but it does not retroactively turn this screen into a win-rate experiment.

## Fixed arms, population, order, and build

- Character: `character_ranger`.
- Nominal and observed danger: **5**.
- Opener: `weapon_pistol_1`, certified from each run's `run_start.weapon`; configuration is
  pistol-first.
- Build: `0.2.80-wp2-capture`, policy `teacher_v1-0.1.129-gun-wp1`.
- Control **C**: `clearance_guarded_conversion == false`.
- Treatment **T**: `clearance_guarded_conversion == true`.
- Every other experimental arm and scalar is inert, including `route_scores_enabled == false`,
  `body_clearance_scale == 1.0`, and the experimental profile port.
- Fixed order: **C, T, T, C, T, C, C, T**.
- Fixed sample: **4 valid trials per arm, 8 total**. No stop-on-win, outcome-based extension, or
  post-result top-up. Operationally incomplete directories created when a supervisor stops are
  accounted individually and are not trials.

The fixed order balances first/second half and adjacent drift without pretending the runs are paired.
Exact permutation tests operate on the four per-trial values in each arm.

The expected unlock-pool stamp is fixed from the era-matched §32 corpus:
`items=179`, `weapons=48`, `items_hash=2018397571`, `weapons_hash=1530875081`. Any mismatch voids
pooling. An unlock caused by a run is reported, never silently crossed.

## Exact treatment — no ladder and no tuning

The treatment is the §41 policy exactly as implemented in commit `71c0694`:

- waves 1–11 only;
- the incumbent production route is reconstructed first;
- PACK clearance 80;
- moving-threat projection horizon 0.60 s;
- maximise fraction of living enemies and bosses within the longest held weapon range;
- use production route score only as an exact in-range tie-break;
- emit only for projected gain strictly greater than 0.05;
- if incumbent body clearance is at least 45, require candidate clearance at least
  `max(45, 0.80 * incumbent)`;
- otherwise require candidate clearance at least the incumbent clearance;
- preserve the active projectile floor and enemy-penalty slack.

There is no alternative ratio, PACK value, horizon, or deadband in this screen. A failure cannot be
rescued by choosing one after seeing the runs.

## Analysis order — controls before outcomes

The analyzer prints and adjudicates these sections in order. If validity or delivery is void, the
mediator is descriptive only and cannot pass.

### 1. Run validity

Print every run ID and all denominators before any outcome:

1. exactly 4 state-collected summaries per arm and 8 unique run IDs;
2. terminal, telemetry-complete summaries with zero errors, hangs, illegal actions and non-finite
   fixes;
3. requested and observed character `character_ranger`, requested and observed danger 5, and
   `danger_ok == true`;
4. build, policy, exact era stamp and opener match the fixed values above;
5. the arm is read from each run's own `run_start`/summary record, not the config left on disk;
6. all other behaviour-changing arms and doses are inert at their declared defaults.

`character_ok` is not accepted as proof because it is historically vacuous; the observed value is
checked directly. A zero error count is always printed over 8 summaries.

### 2. Delivery and live safety invariants

For wave-1–11 `combat_capture` route blocks, print per arm and per trial:

- total route blocks; `conversion_enabled` field seen; ranked opportunities; applied conversions;
- captures with at least one guard veto and total vetoed/admitted candidates;
- projected gain distribution, each with its denominator;
- incumbent and selected body-clearance pairs on applied conversions.

Delivery passes only if:

1. `conversion_enabled` is present and false on **100%** of control route blocks and true on **100%**
   of treatment route blocks;
2. control applies exactly **0 / N** conversions, with `N > 0` ranked opportunities;
3. all 4 treatment trials apply at least one conversion and the pooled treatment applies at least
   one conversion over a nonzero ranked denominator;
4. every applied conversion has reported projected gain strictly greater than 0.05 (allowing only
   the 0.0001 telemetry quantisation at the comparison boundary);
5. every applied body pair satisfies the 0.80/45/subcritical rule, allowing 0.02 units solely for
   the two-decimal telemetry quantisation;
6. the treatment reports at least one guard-vetoed candidate and at least one ranked opportunity on
   which no conversion is applied. These are the positive and negative controls for the gate.

The offline flip-rate and gain bars are not silently reused as live outcome bars: they qualified the
policy on a fixed recorded corpus. Here the required behavioural proof is that the treatment changes
the final command in every trial and that every changed command obeys the frozen guard.

### 3. Primary mediator — realised in-range fraction

Population: all wave-1–11 captures with at least one living threat (`hp > 0`) and at least one held
weapon with positive `max_range`. Threats are `entities.enemies + entities.bosses`. At each capture:

```
in_range_fraction = living threats within max held weapon max_range / living threats
```

The endpoint is the unweighted mean of those capture fractions within each trial. Trials, not
captures, are the units of analysis. Print raw per-trial values and capture denominators. Captures
without a living threat or usable weapon range are excluded with explicit counts, never assigned
zero.

The primary passes only if both:

- treatment mean minus control mean is **at least +0.05 absolute**; and
- the exact two-sided permutation p-value on the 4+4 trial values is **at most 0.05**.

The +0.05 bar is the detection scale declared for the §31 n=4/arm instrument, not fitted to §42.
Report median and zero-in-range capture fraction as secondary geometry descriptors; neither can
rescue the primary.

### 4. Pre-declared safety veto

Over the same wave-1–11 captures with valid positive maximum HP, compute per trial:

- fraction of captures with `hp / max_hp < 0.70`;
- mean HP deficit `max(0, 1 - hp / max_hp)` (HP-deficit AUC per capture).

Print raw per-trial values and denominators. Safety passes only if **both** treatment arm means are
no greater than their control means. Any increase in either mean rejects the treatment, even if the
in-range primary passes. This deliberately conservative rule is §31's pre-declared failure mode:
the agent may not buy targets by spending low-HP exposure. No significance test or terminal-wave
result relaxes the veto.

### 5. Context only

Report terminal waves, victories, duration, damage taken and wave-11 coverage. At n=4/arm these are
not powered survival endpoints and carry no pass/fail weight.

## Decision rule

- **PASS / survival campaign licensed:** validity and delivery pass, realised in-range primary
  passes, and both safety comparisons pass.
- **INERT OR TOO SMALL:** validity passes but delivery is absent, or realised gain is below either
  primary bar. No survival campaign.
- **UNSAFE:** primary passes but either safety mean rises. Reject the treatment.
- **VOID:** a validity gate or live invariant fails. Diagnose; do not interpret outcomes.

## Prediction

**Prediction: PASS.** §41 retained conversions on 48.75% of analysable ranked decisions, every one of
the eight source runs contributed, and integrated projected gain was +0.0461 across all route blocks.
That is unusually broad authority for this project and should be large enough to move the realised
per-trial endpoint by +0.05. The main falsifier is dynamics: one-step projected gains may be cancelled
on subsequent ticks, leaving the actual in-range fraction unchanged. The main rejection risk is the
strict low-HP non-increase veto despite the per-decision body guard.

## Operational freeze

Before launch, re-read HANDOVER §6 and the arm/build/process memory files. The game must be off;
because the last recorded exit was a force-kill, repair the mods-disabled latch unconditionally.
Deploy once with auto-start off, then arm **after** deploy and read back. Diff installed zip content
against source and require a fresh `mod_ready.json` mtime on launch. Use `--no-deploy`, `--min-wins
0`, explicit state files, and no `--stop-on-win`. Kill only attributable `Brotato.exe` PIDs. Controls
are analyzed before mediator and safety results.
