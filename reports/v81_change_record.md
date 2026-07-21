# v81 change record — Run Strength Index (observability only), NOT deployed

- **Date:** 2026-07-21, authored by Claude (Fable), operator-requested follow-on to v80.
- **Status:** code + tests complete (**63/63 passing**). **No gameplay-policy change** — v81 is purely observability on top of v80; the v80 impactful-offense band gate is the only pending gameplay change. Not deployed, not launched; Codex owns deployment.
- **Version:** `0.1.81-gun-wp1` (all five version sites; live_monitor tuples extended with `"0.1.81"`; fail-open guard shape preserved).

## What the RSI is

Per-wave composite, **100 = tracking the median winning run at this wave**, computed in `combat_model.run_strength_index()` and emitted in `build_metrics.rsi` (combat ticks, shop decisions, level-ups) plus a HUD line `rsi: <total> (P.. C.. D.. E..) w<N>`:

| Component | Definition | Weight |
|---|---|---|
| Power | `est_dps / OFFENSE_DPS_TARGETS_BY_WAVE[w]`, cap 1.3 | 0.55 |
| Control | `15 / max(live p90 enemy density, 15)`, cap 1.0 | 0.20 |
| Durability | `ehp_index / DEFENSE_EHP_TARGETS_BY_WAVE[w]`, **hard cap 1.0** (excess EHP never discriminated wins) | 0.15 |
| Conversion | 1.0 unless the shop exits below the DPS band with unspent gold: `1 − leftover_beyond_reserve / entry_gold` (waves ≥ 13) | 0.10 |

Conversion is tracked in the controller (`_track_shop_conversion`, reset per run); live p90 uses the current wave's density samples. Constants in `config.gd` (`RSI_*`); run-level aggregation window `RSI_WINDOW_FROM_WAVE..TO_WAVE = 13..19`.

## Backtest validation (scripts/rsi_backtest.py, run against all 14 scored metric-carrying runs)

The tool parses weights/curves **directly out of config.gd** (no Python/GDScript drift) and reproduces the index offline:

- Wins (n=9): median run-RSI ≈ **101**; losses (n=5): median ≈ **79**, max **88.2**.
- **Every run with run-RSI ≥ 89 won (5/5); no loss exceeded 88.2.** The v79 loss scores 78.6 with band-deficit 1.48 — flagged as below-winning-strength from wave 13 onward.
- Perfect separation does NOT hold at the low end (a 39.8-RSI run won; three wins sit at 60–65): these are the known slow-attrition wave-20 survivors (60–90 s clears at <2,700 DPS). **Interpretation: RSI is a strength metric, not a win predictor — high RSI ⇒ near-certain win; low RSI ⇒ coin-flip dependent on attrition/movement.** That asymmetry is exactly what a training objective wants: pushing runs into the ≥89 region is pushing them into the deterministic-win region.

## Intended uses

1. **Live HUD needle** for "how strong is the agent right now" (with per-component attribution).
2. **Analysis**: version comparisons via median wave-15 RSI / run-RSI / band-deficit; loss postmortems via "which component broke first."
3. **Training objective (future)**: dense per-wave shaping reward alongside the terminal win/loss — never RSI alone. Known Goodhart soft spot: the DPS estimator overrates slow single-target mixes; the Control term is the counterweight. Re-fit weights (or graduate to a fitted win-probability model) once ~30+ metric-carrying runs exist.

## Touchpoints

`teacher/config.gd` (RSI consts), `teacher/combat_model.gd` (`run_strength_index`), `runtime/agent_controller.gd` (conversion tracking + `build_metrics.rsi` + HUD line + run-start resets), `ui/agent_hud.gd` (order key `rsi`), `scripts/rsi_backtest.py` (new tool), tests (`test_v81_policy_versions_are_consistent`, `test_v81_run_strength_index_is_computed_and_displayed`).

## Acceptance for the next launch

- HUD shows the `rsi` line and it matches telemetry `build_metrics.rsi`.
- `rsi_backtest.py` on new runs continues to show: no loss above ~89, wins clustering ≥ 100.
- If a future run wins with run-RSI < 40 or loses with run-RSI > 95 repeatedly, the weights need re-fitting (more data or a component is misbehaving).
