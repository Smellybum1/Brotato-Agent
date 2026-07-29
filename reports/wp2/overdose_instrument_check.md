# `enemy_scaling.health` works ABOVE 1.0 — the fixture-supply blocker is false

**Date:** 2026-07-29. Instrument check, 2 trials, ~6 minutes of machine time.
**Result: PASS. The dial is exact above baseline, so discriminating fixtures can be
manufactured instead of harvested.**

## Why this was run

`campaign_sizing_v2.md` identified the blocker on the next wave-17 campaign: **only 7 of 72
(fixture, dose) states discriminate on terminal survival**; the rest sit at 0% or 100% and cannot
move the endpoint at any `n`. The stated fix was to harvest more fixtures — ~19 min of full run per
candidate, plus screening trials, with no guarantee any given save lands in the useful band.

Re-reading the dose ladder made a cheaper possibility obvious. Every dose ever run was **at or
below baseline**: measured `buffer` `max_hp` of 34 / 51 / 58 / 61 / 65 / 68 corresponds to
`health` = 0.50 / 0.75 / 0.85 / 0.90 / 0.955 / 1.00. The ladder was built to *rescue* a failing
fixture, so it only ever made enemies weaker.

Per-fixture, that leaves almost nothing usable: of 25 distinct wave-17 fixtures, 16 were tested at
≥2 doses, and **only 2 span a usable survival range. 14 of 16 are still 100% survivable at the
hardest dose ever tried**, which is merely baseline.

So the question was never "do we have enough fixtures" — it was **"can we make the ones we have
harder?"** That had never been tested.

## Design

Structural readback, not an outcome test. `enemy_scaling` is a deterministic per-entity multiplier,
so **one valid trial per arm settles it** — no power calculation, no outcome statistic. Over-dose
deliberately (1.5x) so an inert dial cannot hide in noise.

Both arms were produced from **one** source save (`w16_predator_20260728_112824_7f124906e6bb49cb`)
through the same `wp2_build_dose_fixtures.build_arm` round trip, including the control. A
byte-copied control would confound "the dial is inert" with "re-serialisation broke the save".
Each written file was re-read from disk and asserted against its intended dose and the source's
invariant fields before launch.

## Result — exact to the dose across six independent enemy types

Wave-17 `max_hp` by `type_id`:

| type_id | control (health 1.00) | over-dose (health 1.50) | ratio |
|---|---|---|---|
| buffer | 68 | 102 | **1.500** |
| fin_alien | 44 | 66 | **1.500** |
| helmet_alien | 72 | 108 | **1.500** |
| junkie | 85 | 128 | 1.506 |
| pursuer | 394 / 985 | 591 / 1478 | **1.500** |
| spawner | 26 | 39 | **1.500** |

Junkie's 1.506 is integer rounding (85 × 1.5 = 127.5 → 128). **Nothing clamps at 1.0.** The
sanitize path in `run_orchestrator.gd` that forces `1/1/1` still does not reach the run-state copy,
exactly as it does not below baseline.

Outcome, reported but **not** the evidence (n=1 per arm): control **victory**, waves 17-20, 293 s;
over-dose **died in wave 17** at 52 s. Consistent with a large real effect, but a single trial
cannot establish a survival rate and no rate is claimed here.

## What this changes

**The fixture-supply blocker is dissolved.** Any of the 25 existing wave-17 fixtures can be
titrated upward to a discriminating operating point. The campaign design in `campaign_sizing_v2.md`
that was capped at **F = 7** is no longer capped there, at **zero harvest cost**.

It also means 1.5 is too strong for this fixture — it converts a 100%-survival state into what looks
like a near-0% one. **The titration target is between 1.0 and 1.5 here**, and per-fixture.

## What must NOT be concluded

- **This is an instrument check, not an outcome result.** It proves the dial takes effect above
  baseline. It says nothing about where any fixture's 50% point sits.
- **Titration is a design choice with an external-validity cost.** Tuning a fixture to ~50%
  maximises the endpoint's sensitivity (a binomial is most informative at p = 0.5), which is right
  for a **screen**. But an effect measured at `health` = 1.3 is measured on a harder game than the
  one we ship. **Confirmation should still be run at baseline** on genuinely discriminating states,
  or the transfer argument has to be made explicitly.
- Doses above baseline have **never been used in an outcome campaign**. Before one is commissioned,
  the titration itself needs a protocol — how many trials per candidate dose, and a preregistered
  rule for selecting the operating point — or dose selection becomes a garden of forking paths.

## Machine state

Config restored by the harness (`restored original save from ...` on both arms). Fixtures live in
`.tmp/overdose_check/`; trial rows in `.tmp/overdose_check/trials.jsonl`. Runs:
control `run_1785305683_66667`, over-dose `run_1785305989_47473`.
