# Danger 5 damage-attribution lag — derived, not inherited

Date: 2026-07-30. Script: `scripts/wp2_d5_damage_lag.py`. Output: `.tmp/d5_lag_060.json`.
Sample: the **9 valid D5 attempts on mod `0.2.60`**, waves ≥ 6, `run_1785372250_76725` excluded.
**61,722 captures, 124 HP-drop events.**

This satisfies `danger5_baseline_prereg.md` §7's requirement that the causal lag be **re-derived per
context and never inherited**. Danger 5 deaths cluster at waves 8-15, which is neither of the two
previously measured contexts.

## Result

Median **minimum surface distance** (centre distance − the entity's own radius) from the player to
each hazard class, at capture `i + lag`, over all HP-drop events:

| lag | enemies (median / p25 / n) | projectiles | bosses |
|---|---|---|---|
| −3 | 65.82 / 46.29 / 113 | 198.50 / 127.47 / 78 | 448.90 / 97.80 / 13 |
| −2 | 46.74 / 31.60 / 113 | 205.62 / 118.80 / 79 | 450.19 / 72.96 / 13 |
| −1 | 24.81 / 9.05 / 113 | 186.79 / 111.39 / 78 | 451.87 / 42.92 / 13 |
| **0** | **10.50 / −3.84 / 113** | 214.67 / 137.72 / 72 | 445.74 / 24.28 / 13 |
| +1 | 31.22 / 7.00 / 113 | 223.06 / 151.40 / 71 | 444.06 / 24.81 / 13 |

**Random-tick baseline** (median over all 61,722 captures — what "no information" looks like):
enemies **296.23**, projectiles **339.35**, bosses **413.75**.

## Verdict

**Lag 0 — the HP-drop tick itself — and the hazard class is MELEE BODIES (`entities.enemies`).**

Three independent reasons this is an identification and not a coincidence:

1. **A clean V-shape with a single minimum at lag 0** (65.8 → 46.7 → 24.8 → **10.5** → 31.2). A
   spurious result would not be monotone on both sides.
2. **p25 at lag 0 is NEGATIVE (−3.84).** Negative surface distance means the enemy body is
   *overlapping* the player. That is physically what melee contact is, so the statistic is picking out
   the mechanism rather than a correlate.
3. **Separation against baseline is huge for enemies and small for projectiles.** Enemies go
   10.50 vs 296.23 (~28x); projectiles only reach 186.79 vs 339.35 (~1.8x) and are *worse* at lag 0
   than at lag −1.

So **Danger 5 at waves 6-15 behaves like the wave-17 melee context, not the wave-20 projectile
context** — which is exactly why the lag had to be re-derived rather than inherited from the finale
work.

| context | causal lag | median at that lag |
|---|---|---|
| wave 20, projectiles | **−1** | 18.7 u |
| wave 17, melee bodies | **0** | 0.9 u |
| **D5 waves 6-15 (this)** | **0** | **10.5 u** |

## What must NOT be read into this

- **This is an attribution lag, not a cause of death.** It says which capture to look at when a hit
  lands. It does not say melee bodies cause the losses.
- **10.5 u is 10x the wave-17 figure (0.9 u)** at the same lag. Not over-interpreted here: plausible
  causes include a mixed hazard set at D5, dodge/armor absorbing some contacts, or non-contact damage
  sources. **Not established.**
- **Bosses carry no signal** (445-452 vs a 413.75 baseline) and n = 13 is too small to quote a spread
  from at all — the standing bar is n ≥ 6 for a spread, and 13 barely clears it while the medians sit
  *above* baseline. Do not conclude bosses are harmless; conclude this sample cannot speak to them.
- **The baseline itself must not be inherited either.** Prior work quoted a 114-218 u random-tick
  baseline; here it is 296.23 u for enemies, because waves 6-15 are less crowded than waves 17-20. A
  baseline is a property of the context in exactly the way the lag is.

## Known limitations, stated

- `hp_regeneration` is non-zero, so HP climbs between hits; a decrease is still damage.
- Self-damage items and burn DoT also decrease HP with no adjacent body. These inflate **every** lag
  equally, so they cannot manufacture a lag preference, but they do raise the floor.
- **Dodged hits produce no HP drop and are invisible here.** The agent's `dodge` is non-zero.
- Captures with `control_dt_ms < 10` are excluded (start-up, not steady state).
- A bug found and fixed before the numbers were believed: the between-run sentinel initially
  manufactured **one false HP drop per run seam**, because the first real capture of each run compared
  against it. The boundary is now explicitly marked and inert from both directions.

## Next

Use **lag 0 against `entities.enemies`** for the §7 multi-label failure-channel attribution on the
`0.2.61` campaign. Re-run this script on the `0.2.61` set when it completes and confirm the lag is
unchanged — it is a property of the damage mechanism, so a difference between builds would itself be a
finding worth chasing.
