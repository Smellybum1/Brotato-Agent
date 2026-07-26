# Fixture-library campaign — 26 runs, policy 0.1.128 / mod 0.2.38

**COMPLETE 2026-07-26.** Driver `scripts/wp2_fixture_campaign.py`, snapshot collector
alongside. 26/26 runs, **0 restarts, 0 faults**, machine left idle and config restored.
Report `.tmp/fixture_campaign_report.json`, index `.tmp/snapshots/index.jsonl`.

## 1. The library (the campaign's purpose)

| boss | builds | note |
|---|---|---|
| **predator** | **11** | 10 new + the legacy pair, which is ONE build (see below) |
| **invoker** | **6** | the design's internal control |

`select_library(..., one_per_run=True)` reports 12 predator groups, but the two legacy
rows (`source_run_id` null) are `run_1785036448_61774` captured 6 s apart — **one
build**. The function cannot know that and must not merge un-provenanced rows, so
**subtract 1 by hand**. Every fixture archived during this campaign carries
`source_run_id`, so this ambiguity does not recur.

Library spread is real, not cosmetic: HP at wave 19 ranges **9-65**, level 20-27,
items 38-75, weapons 5-6. One fixture (`835dcfbe`, hp 9) is a near-death entry to the
finale — a genuinely different regime from the hp 56 build the baseline was measured on.

**Invoker fixtures are not waste.** `finale_clean_slate_design.md` predicts a latency
fix should improve **predator** outcomes and do **little for invoker** (invoker
projectiles are 96.3% stationary, predator 0%). Six invoker builds make that internal
control runnable.

## 2. RAW OUTCOMES

```
last_wave: 20 15 17 20 17 20 20 17 20 17 20 20 10 20 20 20 20 20 13 20 17 20 20 20 10 17
result   :  V  D  D  V  D  V  D  D  D  D  V  V  D  D  V  V  D  V  D  V  D  V  V  V  D  D
```

| quantity | value | 95% Wilson CI |
|---|---|---|
| overall win rate | 12/26 = **0.462** | [0.288, 0.645] |
| reached wave 20 | 16/26 = 0.615 | [0.425, 0.776] |
| **finale hazard** (died at w20 \| reached w20) | 4/16 = **0.250** | [0.102, 0.495] |

Last-wave distribution: `{10: 2, 13: 1, 15: 1, 17: 6, 20: 16}`. **Wave 17 carries 6 of
the 14 defeats** — reproducing the known wave-17 concentration on a fresh sample.

## 3. THE FINALE LEAD SURVIVES ITS PREDECLARED TEST

`brotato-winrate-regression` recorded the finale hazard as **"HYPOTHESIS, NOT A
FINDING"** — strong era 4/86 = 4.7% vs current 4/14 = 28.6%, p = 0.0126, clearing
neither Bonferroni nor BH across 13 wave comparisons, on 4 deaths in 14 runs. It
predeclared the drop rule:

> *"if the bank's finale hazard comes back near 4.7%, DROP the lead."*

**It came back at 25.0% [10.2%, 49.5%]. The strong era's 4.7% lies OUTSIDE that CI.**
Pooled with the prior observation: **8/30 = 26.7% [14.2%, 44.4%]**.

This is an independent, **pre-registered** replication rather than a re-analysis of the
sample that generated the hypothesis, which is exactly what the original result lacked.
**The finale line is now a replicated finding, and the wave-20 work is justified on
outcome evidence rather than on a lead.**

Honest limits: n=16 reaching wave 20 keeps the CI wide; the strong-era comparison is
still across eras with different builds and versions; and this measures the CURRENT
hazard, not the size of the gap.

## 4. Win rate: 46.2%, BUT MEASURED UNDER LOAD

12/26 = 0.462 [0.288, 0.645] is the largest single-version teacher sample on 0.1.128
(prior estimates rested on n=21) and is consistent with the recorded current-era 53.9%.

**Do NOT bank this as the frozen champion.** Other projects were running on the machine
throughout (two Backpack Battles `run_m2c_rail` processes and a `sim27l_solver`). This
project has a documented machine-load confound — the F2 campaign ran its control arm
unloaded and its learned arm under 8-12 workers, which argued underpower. A champion
number that future candidates are gated against must be collected under known
conditions. **Treat 46.2% as "win rate under load", and re-run the bank clean if the
frozen champion is needed.**

The finale hazard in §3 is far more robust to this caveat than the win rate is: load
would have to act specifically at wave 20, conditional on reaching it.

## 5. Method notes worth keeping

- **0 restarts over 26 runs / ~9 h.** The watchdog never fired; the rearm guard added
  for "summary written but no new run starts" was never exercised and remains untested
  in the field.
- Defeats and faulty runs were **counted, not discarded** — they still donate wave-19
  saves, and dropping them would bias the library toward runs that went well. 10 of the
  26 runs never reached wave 19 and donated nothing; that is the real yield cost.
- Yield ran at 0.22 predator builds/run at the 9-run mark and finished at 0.38/run.
  The early shortfall was binomial noise on the predator/invoker draw, not a broken
  assumption. **Do not re-project a rate off the first third of a campaign.**
