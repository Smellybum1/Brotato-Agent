# v80 change record — implemented, NOT deployed

- **Date:** 2026-07-21, authored by Claude (Fable) at the operator's request following the FABLE_V79_AGENT_IMPROVEMENT_PROMPT review.
- **Status:** code + tests complete (**62/62 passing**, was 61). **Not deployed, not launched — Brotato stays stopped; Codex owns deployment and the next evaluation.**
- **Version:** `0.1.80-gun-wp1` / `teacher_v1-0.1.80-gun-wp1` (manifest.json, agent_controller.gd ×2, telemetry_writer.gd ×2). live_monitor.py: `"0.1.80"` added to all six gated tuples; the two historical tuples (zero-combine, final-shop-combine) intentionally still exclude it — fail-open guard test enforces this shape.

## Evidence basis (v69–v79 review)

- Lineage verified against reports + raw gate/summary evidence. One bookkeeping note: v78 was 0W/**1L** completed plus a lock-loop **safety stop** (partial, wave 15) — not two completed losses. v75's defeat is documented in its record but absent from gate_state (0 collected).
- Per-wave metric trajectories extracted from all 11 `build_metrics`-carrying completed runs (5 v77 + 4 v79 wins/losses; v72 predates the telemetry): **wins and losses are statistically identical through wave 12; the estimated-DPS curve separates them decisively from wave 13** (w15: win-median 2076 vs loss 1456; w20: 5382 vs 3494). Defense/EHP does **not** separate wins from losses at any wave. Wave-20 clear time is strongly predicted by est_dps (every >5,000 win cleared ≤42 s; <2,700 forced 60–90 s attrition).
- Postmortem of `run_1784633480_66139` (v79 loss, 240/265): the decisive divergence was the **wave-15 shop** — 719 gold converted to +7% DPS (Mushroom, Fresh Meat, Cake, Broken Mouth, tier-1 filler guns) while passing t2 Shuriken ($145), t2 Knife ($127), and later t2 Flamethrower twice. Mandatory offense was *satisfied* by cheap filler; the run trailed its adaptive target at **every wave of the run** and died on wave 20 in 23.5 s (burst crowd death, not timeout).
- v79 adaptive target verdict: **retain, later recalibrate for its one-wave lag** (it under-warned before both the v78 and v79 density surges). It correctly ranked the loss below the wins at every wave — not replaced in v80.

## Change 1 (gameplay): impactful-offense band gate from wave 13

New winner-trajectory DPS band = `BotConfig.OFFENSE_DPS_TARGETS_BY_WAVE` (winner-median estimated DPS per wave, from the 8 v77/v79 victories). While `estimated weapon DPS < band[wave]` and `wave >= OFFENSE_BAND_FROM_WAVE (13)`:

1. **Mandatory offense** (`_offense_first_item_action`) only accepts: shop weapons of tier ≥ `OFFENSE_IMPACT_MIN_TIER (1, zero-indexed = human tier 2+)`, tier-1 weapons that pair with an owned same-id/same-tier upgradeable copy for an immediate combine (`_pairs_for_combine`), or items with direct-offense gain ≥ `OFFENSE_IMPACT_MIN_ITEM_GAIN (6.0)`. Marginal trinkets and filler guns no longer satisfy the requirement.
2. **Ordinary scoring** (decide_shop step 1) skips tier-1 filler guns while slots are full (combine-pair exception preserved; the step-2.5 empty-slot fill path is untouched).
3. **Reroll pressure**: +`OFFENSE_BAND_REROLL_PRESSURE (8.0)` to reroll worth while below the band (stacks with the v74 offense-deficient +8; caps/budget guards unchanged).

This targets the exact observed failure: gold reaching wave-13–16 shops must produce tier jumps, not fillers. All combine/lock invariants, the shop_cycle_guard, sustain caps, rare-gun workflow, vetoes, and the any-gun pool are untouched.

## Change 2 (observability): winner-trajectory HUD metrics with per-wave targets

New formulations (single-source, shared by HUD + telemetry):

- **OFF index** = estimated effective weapon DPS (the existing v77 weapon-aware estimator: tier, base damage, cooldown, scaling, crit, projectile count, piercing, bounce, explosion, burning) versus `OFFENSE_DPS_TARGETS_BY_WAVE[wave]`. HUD line `off_dps: <dps> / <target> win-median DPS w<N> (<pct>%)`.
- **DEF index** = `combat_model.defense_ehp_index(stats, wave)` = wave-scaled effective HP (armor mitigation via the enemy-hit model, dodge clamped at cap, regen window) **+ lifesteal × LIFESTEAL_EHP_WEIGHT (3.0)**, versus `DEFENSE_EHP_TARGETS_BY_WAVE[wave]` (winner-median EHP curve). HUD line `def_ehp: <ehp> / <target> win-median EHP w<N> (<pct>%)`. Documented explicitly: the EHP curve is a demonstrated-sufficient floor, **not** a win/loss discriminator — do not chase it past 100%.

Wiring: `_build_metrics` adds `offense.dps_target`, `defense.ehp`, `defense.ehp_target` (telemetry via the existing ≥3 `build_metrics` emit sites); `_update_build_metrics_hud` adds the two lines; `agent_hud.gd` order gains `off_dps`, `def_ehp` after `defense_sustain` (test-protected key runs preserved). The live band used by the policy and the HUD target are the **same constant** — no policy/display drift for the new metrics.

### Target curves (from winner telemetry, waves 1–20)

- DPS: 45, 110, 185, 210, 290, 340, 400, 430, 550, 640, 950, 1230, 1620, 1730, 2080, 2290, 2910, 3740, 4160, 5380
- EHP: 16, 18, 28, 32, 44, 54, 62, 71, 78, 97, 97, 96, 98, 104, 108, 110, 110, 115, 126, 131

## Tests

62/62. `test_v79_policy_versions_are_consistent` → `test_v80_policy_versions_are_consistent`; new `test_v80_winner_trajectory_curves_and_impactful_offense_band` (20-entry curves, accessor funcs, band constants, both mandatory-offense filters, the slots-full filler guard, reroll pressure, EHP index, HUD/telemetry wiring). Existing HUD substring and `_build_metrics` no-or-idiom guards still pass.

## Acceptance metrics for the next evaluation

- Median est_dps at waves 15 / 18 ≥ **1800 / 3000** (v79 loss was 1498 / 2010; win band 2076 / 3742).
- No wave-13–16 shop exits with >400 gold unspent while below the band.
- Zero increase in `shop_cycle_guard` events; no lock-loop recurrence; no new early (<w15) deaths from over-banking or over-rerolling.
- HUD `off_dps` / `def_ehp` lines visible and matching telemetry `build_metrics` values.

## Falsification / rollback

- If runs lose at waves 17–20 **while inside the DPS band at w15/w18**, offense reachability is not the binding constraint — move to the adaptive-target lag (forward density term) or finale-movement work.
- If runs hit the band but over-bank into empty shops and die early or reroll-starve, loosen: drop `OFFENSE_BAND_REROLL_PRESSURE` first, then the step-1 filler guard, before abandoning the band gate.
- Recommended evaluation: a short 8-run A/B against the v79 baseline first (enough to read the w15/w18 DPS medians, not enough to certify), then a full 20-run campaign if the medians move without new failure modes. v72 remains the certified baseline.

## Queued next candidates (NOT implemented)

1. Forward-looking density target (fix the one-wave lag with a trend/two-wave-peak term) — both v78 and v79 losses were under-warned before their surge wave.
2. Wave-20 observability (boss HP/IDs, wave timer, kills-per-second, player displacement) before any further finale-movement tuning.
