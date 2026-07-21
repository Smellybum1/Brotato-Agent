# v82 change record — recalibrated curves + ΔDPS gate, NOT deployed

- **Date:** 2026-07-21, authored by Claude (Fable) following Codex's v80/v81 assessment and an expanded 41-win calibration study. Supersedes v81 as the deploy candidate (v81 never ran; its 8-run campaign was stopped at run 1 by the operator for this revision).
- **Status:** code + tests complete (**64/64**). Not deployed, not launched; Codex owns deployment.
- **Version:** `0.1.82-gun-wp1` (all five sites; monitor tuples extended; fail-open guard shape preserved).
- **Gameplay delta vs v79 remains exactly one dimension:** the impactful-offense band gate (v80), now with v82's better-calibrated curve and impact test. v81's RSI rides along unchanged in code (interpretation updated below).

## Evidence basis (expanded calibration, 41 wins + 14 losses, v70–v79)

A per-wave DPS reconstructor (weapon-stats DB harvested from all 416 run dirs' offers; combine signatures as resync points) was validated against v76–v79 `build_metrics` ground truth: **6–8% residual median error in every wave band** after a per-wave correction for null-item-id sell noise. This expanded the calibration base from 8 wins to **41** (v70:2, v71:11, v72:18, v73:1, v76:1, v77:5, v79:3).

Findings that drove the changes:
1. **The v80 curve was overfit.** The winning population clears late waves far flatter than the 8 lean-build wins suggested: old targets were 18–48% too high at waves 13–20 and 17–26% too low at waves 8–10. Confirmed as policy heterogeneity, not reconstruction artifact (divergence appears only from wave 13, where the v77+ experiments changed shopping).
2. **The tier proxy was misaligned with impact** (Codex's critique, confirmed hard): across 436 wave-13+ weapon buys, tier-1 purchases had *higher* median ΔDPS (209) than tier-2+ purchases (154, p25 = 0); a tier gate and a ΔDPS gate disagree on **55%** of buys; tier-gating would reject 113 impactful tier-1 buys and admit 128 filler duplicates.
3. **Fractional thresholds are wave-stable** (median winning-buy ΔDPS ≈ 7–8% of loadout DPS at every late band) while absolutes drift +82% from w13 to w20.
4. **Per-purchase ΔDPS does not separate wins from losses** (win-buy median 177 vs loss 173) — the gate's value is shopping efficiency along the cumulative trajectory, not per-decision win prediction. Honest negative result, recorded.
5. **EHP curve deliberately unchanged**: expanded data confirms losses carry equal-or-higher EHP than wins mid-game; raising the floor would reward the over-defense failure mode.

## Changes

1. **`OFFENSE_DPS_TARGETS_BY_WAVE` recalibrated** to the pooled 41-win median (monotonic): `45, 110, 175, 230, 300, 380, 450, 540, 645, 765, 935, 1150, 1280, 1430, 1620, 1900, 2150, 2400, 2650, 2900`. Still flags every observed loss at its decisive shops (v79 loss w15: 1498 < 1620; w18: 2010 < 2400) while no longer gating typical winning builds late — reduces the over-rerolling/banking risk Codex flagged.
2. **ΔDPS gate replaces the tier proxy** (`teacher/shop_strategy.gd`): a weapon satisfies the band gate if `_projected_weapon_dps_gain` (full effective DPS into an empty slot; candidate-minus-weakest on a full loadout) ≥ `OFFENSE_IMPACT_MIN_DPS_GAIN_FRAC (0.05)` × current loadout effective DPS, OR it completes an immediate combine pair (`_pairs_for_combine` kept — the tier-up gain is invisible to replacement math). Applied in both the mandatory-offense path and the step-1 filler guard. `OFFENSE_IMPACT_MIN_TIER` removed.
3. Reroll pressure, item-gain threshold, band start wave, EHP curve, RSI code: unchanged.

## RSI interpretation update (important)

Re-running `scripts/rsi_backtest.py` under the recalibrated curve: wins median run-RSI ≈ 109, losses median ≈ 93, but **the old "≥89 ⇒ win" separation no longer holds** (a loss reaches 104.3). This is informative, not a defect: the two high-scoring losses (v78 w19 density surge, v77 w20 movement death) genuinely were near-typical *strength* — they died to target-lag and movement, which run-level RSI correctly declines to blame on shopping. **RSI is hereby demoted from promotion criterion to diagnostic**: use per-wave components (Control collapse at surge waves, band deficit) for postmortems, not the run aggregate as a gate. The roadmap Step-1 criteria are updated accordingly.

## Updated Step-1 campaign acceptance (8 runs, v82)

- ≥ 6/8 wins, no new failure modes (cycle guard, early deaths, reroll starvation);
- median est_dps at waves 15 / 18 ≥ **1620 / 2400** (the recalibrated targets; replaces 1800/3000 which were pinned to the overfit curve);
- no wave-13–16 shop exit with > 400 gold unspent while below the band;
- HUD `off_dps` / `def_ehp` / `rsi` lines render and match telemetry;
- RSI reported as diagnostic only.

## Falsification / rollback

- Losses at waves 17–20 while inside the band at w15/w18 → the binding constraint is the adaptive-target lag or movement, not shopping; stop tuning the gate.
- Gate admits filler (many sub-5%-gain buys observed at wave 13+) → raise `OFFENSE_IMPACT_MIN_DPS_GAIN_FRAC` toward 0.07; gate starves combines or rejects good buys → check `_pairs_for_combine` coverage before touching the fraction.
- Over-banking → reduce `OFFENSE_BAND_REROLL_PRESSURE` first (unchanged this version).

## Caveats

- The 41-win population mixes policies (31/41 wins predate the DPS-band era); the curve reflects what *winning runs* looked like, not what the current policy needs — the campaign is the arbiter.
- v70–v75 points rest on corrected reconstruction (6–8% residual); v72's null-item-id sells (56/191) are the main irreducible noise source.
- Codex's synthetic shop-scenario list (below-band filler-vs-tier2, combine exception, at/above band, reroll exhaustion, pre-wave-13 preservation) remains queued for the WP2 headless-Godot combat lab.
