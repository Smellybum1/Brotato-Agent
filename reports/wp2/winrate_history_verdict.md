# Win-rate history: verdict, and a correction to my own claim

**Date:** 2026-07-26. Evidence: 642 archived attempts, attempt-level ledger at
`.tmp/winrate/ledger.jsonl`. Every headline number below was recomputed in the
primary session from the ledger, not taken from a delegate summary.

---

## What I claimed this morning, and what is actually true

I reported a **"~40-point regression, 90% → 50%"**. That was wrong in framing and
overstated in magnitude. Corrected:

**The trajectory is not a monotone regression. It is peak → collapse → partial
recovery.** Teacher-only attempts, change points fitted from outcome data alone
before any change record was read (segmented Bernoulli, min segment 20, BIC):

| segment | W/n | rate | vs previous |
|---|---|---|---|
| v60-83 (peak) | 92/132 | **69.7%** | — |
| v84-103 | 12/53 | **22.6%** | **−47.1 pp, Fisher p = 8.9e-09** |
| v104-128 (current) | 41/76 | **53.9%** | +31.3 pp, p = 0.0005 |

**Residual gap, peak → current: −15.7 pp (p = 0.0253)** — but those segment
boundaries were chosen from the same data, so that p-value is not calibrated. The
cleaner pre-specified contrast, peak teacher v60-79 (92/132 = 69.7%) vs recent
teacher v>=122 (25/46 = 54.3%), gives **−15.3 pp at p = 0.0717 — not significant at
0.05.**

So: **a residual gap of roughly 15 points is likely but not statistically
established.** My "40 points" came from comparing the single best-selected version
(v72, 18/20) against one recent arm, and ignoring that the trajectory had already
recovered most of the way.

### The mode-mixing trap, confirmed empirically
v125 decomposed: **teacher 10/21 = 47.6%**, residual 14/37 = 37.8%,
**student 1/18 = 5.6%**. The pooled 25/76 = 32.9% I originally quoted was dragged
down almost entirely by the student arm. Quoting it as a teacher rate manufactures a
regression the teacher does not show.

### Adaptive-stopping bias is real
Run-weighted teacher rate 0.429 vs **equal-version weighted 0.327** — worth ~10 pp.
Early campaigns stopped after 3 losses, so strong versions contributed more runs.

### Missingness does not support the regression
186 of the 642 attempts have no recoverable outcome. Decisive detail: **187/188
summary-absent streams end with the player ALIVE, mid-wave, with no `run_end`** —
these are process terminations, not deaths or wins. Across the sensitivity grid the
**sign of the early-vs-current gap flips**, and it sits near zero (−0.1 pp) when both
eras' unknowns are treated alike. The corner that would support a regression requires
believing every early unknown was a win and every current unknown a loss.

---

## What survives, and is STRONGER than I stated

**The governance failure is established beyond argument.** A **47-point collapse**
(69.7% → 22.6%, **p = 8.9e-09**) ran for roughly twenty versions and was completely
invisible, because from ~v84 qualification was one smoke run plus internal audits —
a procedure with no power against a win-rate change, checking internal consistency
rather than outcomes. The recovery to 53.9% was real but never restored the peak, and
nobody could have known either fact at the time. This is the finding that matters and
it does not depend on the contested magnitude.

---

## The mechanism hypothesis is REFUTED — and the refutation is more useful

I hypothesised that the accumulated movement/safety layer (density veto, relief
fallback, corner guard, edge-kite rail, pack repulsion, loot dash, strength tiers,
finale override, greed budgets) was **net-negative**. The archive says the opposite.

**The safety layer works. Damage taken fell 2.46x and the win rate fell anyway.**

| | STRONG v60-72 (n=113) | CURRENT v125 teacher (n=21) |
|---|---|---|
| win rate | 72.6% | 47.6% |
| damage taken, mean | **295.9** | **120.3** |
| damage taken, median | 230.0 | 98.0 |

The current agent's 90th percentile damage sits below the strong era's *median*. Any
account of the gap must explain **losing more while being hit less**.

### Where the failure actually is: the finale

Defeat distribution by final wave:

```
STRONG   n=31 defeats: {9:2, 10:1, 13:2, 16:6, 17:8, 19:8, 20:4}
CURRENT  n=11 defeats: {13:2,        16:1, 17:4,       20:4}
```

The current policy **eliminated early and mid-game deaths outright** and collapsed
the failure onto two waves:

- **Wave-20 defeats: 4/113 = 3.5% of strong-era runs → 4/21 = 19.0% of current runs.
  A 5.4x increase in finale failure.**
- **Wave 17 is the ONLY wave where the current policy takes as much damage as the
  strong era** (30.2 vs 29.2 per run), and it carries 4 of 11 defeats.

Movement itself shows almost no drift: command magnitude is unit in both eras,
`stationary_frac` is 0.0000 at every wave in both, and reversal rate differs only at
waves 18-19 (P=0.69, n=14 — not decisive). Economy is indistinguishable: level-ups
28.9 vs 28.7, purchases 132.9 vs 129.8.

**So the regression is not a safety failure and not a movement failure. It is a
finale failure.** The policy survives to wave 20 far more reliably than it used to,
and then loses there.

---

## Honest limits

- Current cohort is n=21 (thin: n=14 at waves 18-20); strong cohort spans 13 versions.
- **Corner-parking is not comparable** — the strong era emits no `player.x/y` at all.
  Largest single gap in the contrast.
- **Internal layer activation is untestable** — all 40+ `finale_translation.*` fields
  exist only in the current era. The accretion hypothesis's *internal* predictions
  (override frequency, layers cancelling) could not be evaluated; refutation rests on
  the outcome and damage evidence, not on layer telemetry.
- Telemetry load differs 10x between eras. Weakened as a confound by near-identical
  per-wave wall-clock (within ~1%) and run duration (1,099 s vs 1,067 s).
- `debug.enemies` is higher in the current era at nearly every wave, which would fit
  "avoids more, kills less, density accumulates" — but the field's old-era
  construction could not be verified. **Flagged, not concluded.**
- v72 remains permanently unrecoverable, so no anchor experiment can ever settle the
  peak era's true rate.

## Consequences

1. **Do not pursue "strip back the safety layer."** It is refuted. Removing it would
   likely restore the early- and mid-game deaths it eliminated.
2. **The target is the finale** — wave 17 and wave 20. That is where the strong era
   beat the current one, and it is the only place it did.
3. **The process fix (three-gate model, champion/challenger sequential gate) is
   justified independently** of the magnitude question, by the 47-point invisible
   collapse alone.
