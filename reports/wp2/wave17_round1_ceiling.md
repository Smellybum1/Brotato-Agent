# Wave-17 dose response, round 1 — FAILED GATE (`UNINFORMATIVE_CEILING`)

Round 1 of the wave-17 clear-rate dose-response experiment is a **pilot that failed its
preregistered feasibility gate**. It is not a null and must never be cited as one. The
efficacy contrast was **never computed** and must never be computed from this data.

Preregistration: `reports/wp2/wave17_dose_response_prereg.md` (v1 rule).
Successor: `reports/wp2/wave17_dose_response_prereg_v2.md`.

## What ran

16 fixtures — one per independent source run, snapshotted at `current_wave` 16, resuming
into the wave-16 shop and playing wave 17 — x 3 arms (`C` health 1.00, `H75` 0.75, `H50`
0.50) = **48 trials**, ~4.3 min each, executed 17:09-20:30 on 2026-07-28. All 16 blocks
exited 0.

**Validity: 48/48 valid, 0 invalid in every arm** (C 16, H75 16, H50 16). No trial was
replaced.

## The gate

The v1 preregistration allowed **exactly one look** after round 1: the CONTROL arm's
failure rate, and no treatment contrast.

> Control wave-17 failure = **2/16 = 0.125**, below the **0.15** bar
> => **`UNINFORMATIVE_CEILING`** => **STOP**, do not proceed to round 2.

0.125 is a **near miss** on 0.15 — one more control failure would have cleared it. The
bar was **not relaxed after seeing the number**, and the treatment contrast was not
computed. That is the whole point of freezing the rule beforehand; a bar moved 0.025 after
the look is not a bar.

## Why it failed — measured, and NOT fixable by fixture selection

### Power

Wave-17 failure is intrinsically rare per attempt. At the observed control rate 0.125:

| target effect | trials/arm | total | wall clock |
|---|---:|---:|---:|
| 50% relative reduction (the v1 bar; 0.125 -> 0.0625) | 340 | 680 | 48.8 h |
| 75% relative reduction | 127 | 255 | 18.3 h |
| near-total rescue (0.125 -> ~0) | 59 | 118 | 8.5 h |

The v1 design asked a question that costs ~49 h to answer. That, not fixture quality, is
the binding constraint.

### The library is NOT too easy

Fixture `nominal_dps`, computed from the **first wave-17 capture** (effective in-run
stats), spans **17.29 to 66.88, median 33.48**, against Stage A's died median **28.26** /
survived median **35.25** (`reports/wp2/wave17_stageA_uptime.md`). **5 of 16** sit below
the died median; **6 of 16** at or above the survivor median. The library covers the
range. Reaching for "weaker fixtures" is not an available fix.

### Entry capacity did not rank the replay failures

The two fixtures that died read **22.10** and **49.31** — the second-highest entry
capacity in the library — while the **weakest** fixture (17.29) survived.

**n=2. This is a DESIGN SIGNAL ONLY, not a finding.** It is stated because it constrains
what a future designer may assume (selecting low-capacity fixtures would not reliably
manufacture failures), not because two trials establish anything about capacity and
outcome.

### One suggestive replication

One fixture (source `run_1785214891_49265`) came from the only collection run that itself
died at wave 17. It **died again on replay in 62.8 s**. **n=1** — suggestive that
wave-17 failure has a reproducible fixture-side component, and nothing more.

## Measurement trap: save stats are BASE TEMPLATE values

An earlier attempt to rank fixtures used the SAVE's
`players_data[0].weapons[i].stats` damage/cooldown. **Those are base template values for
the weapon + tier.** The capture's `payload.weapons` are **effective in-run** values after
player bonuses.

Same field names, same formula, **3.40x apart** on one fixture: save total **8.81** vs
capture total **29.98**. The save-based ranking concluded "all 16 fixtures are below the
died median" — **that is false**. Stage A's medians are capture-derived, so **only
capture-derived values are comparable to them**. Any future fixture ranking must read the
capture.

## What this does NOT show

- It does **not** show that wave 17 is clear-rate limited, or that it is not. The
  treatment contrast was never computed; no evidence about the enemy-health channel exists
  in this data at all.
- It does **not** show that halving enemy health fails to help, nor that it helps.
- It does **not** bound the effect size in either direction.
- It does **not** revise the Stage A finding (offense, not defense, separates wave 17);
  it neither corroborates nor challenges it.
- The 0.125 control rate is a rate **for this fixture library under replay**, not an
  estimate of the live wave-17 failure rate in full runs.

## What changed as a result

v2 (`reports/wp2/wave17_dose_response_prereg_v2.md`), **frozen before any v2 trial**:

- **H75 dropped.** `C` vs `H50` only.
- **16 fixtures x 4 reps x 2 arms = 128 trials** (64/arm, ~9.2 h).
- Tests **near-total rescue only** — the sole effect a sane budget can detect at a control
  rate of 0.125.
- **Round-1 data is NOT pooled into v2.** A rule written after seeing round 1 and then
  applied to round 1 would be preregistration in name only. v2 runs on a fresh sample.
