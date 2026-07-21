# v83 change record — item-allowlist audit (conservative), SUPERSEDED

- **Date:** 2026-07-22, authored by Claude (Fable) at the operator's request: full audit of the agent's purchasable-item list against the complete Brotato item pool.
- **Status:** deployed and visually verified, then intentionally stopped at wave 6 of its first run (`run_1784644121_75697`) so Fable's conditional-effect follow-up could be folded into v84. The partial run has no terminal summary and is excluded from campaign evidence.
- **Version:** `0.1.83-gun-wp1` (all five sites; monitor tuples extended; fail-open guard shape preserved).

## Audit method (read-only, three evidence sources)

1. **Telemetry**: all 416 run dirs — 170 distinct item ids observed in offers; per-id buy counts and win/loss association (270 decided runs, 44.0% baseline win-share).
2. **Decompiled base-game catalog** (`third_party/brotatoai`): authoritative base-1.1.15.4 id list with unlock flags.
3. **Wiki** (https://brotato.wiki.spellsandguns.com/Items): rarity/DLC classification.

## Findings

- **Zero typos** in the 164-id allowlist — every id resolves to a real item (long-standing silent-veto worry closed).
- **46 allowlisted ids are unreachable on this install** (22 unlock-gated base items, 24 DLC/post-1.1.15.4). Harmless — never offered, never bought — and deliberately NOT pruned (some may unlock later; Proposal B in the audit declined).
- **52 observed ids are not allowlisted**; most are correctly excluded (melee/elemental/engineering items with 27–33% win-shares). `item_blood_donation` stays `"never"`-vetoed (15% win-share confirms), `item_ball_and_chain` stays cooldown-floor-vetoed (7%), `item_sharp_bullet` stays allowed (71% win-share — the telemetry vindicates the earlier reversal).

## Changes (Proposal A — conservative)

**Two additions** to `WIKI_USEFUL_ITEM_TIERS` (hard allowlist grows 164 → **166**; ids telemetry-verified):
- `item_honey` → **B** (ranged +3, explosion_damage +10, explosion_size +5; 55% win-share).
- `item_pumpkin` → **B** (piercing_damage +15, %damage −2): piercing is high-value for this build.

`item_statue` was removed during Codex's pre-deployment review. Its +40 attack
speed uses the conditional `temp_stats_while_not_moving` effect, but the live
shop snapshot drops that condition and would score it as unconditional offense.
The agent continuously kites and would still pay Statue's unconditional −10
speed cost, so its historical 10W/8L association does not justify admitting it.

**Four tier corrections** (letter only; membership unchanged):
- `item_snowball` B→**D**, `item_ice_cube` C→**D**: elemental scalers with zero gun synergy and the worst win-shares on the list (14% / 25%) — the old +10/+3 bonuses were pulling them into early buys where the hard gate doesn't apply.
- `item_pile_of_books` B→**C**: engineering/structures item, irrelevant to guns (39%).
- `item_acid` B→**A**: strongest signal of any allowlisted item (68% win-share, 144 buys) and genuine AoE offense.

**Not changed**: `BUILD_AWARE_ITEM_REQUIREMENTS` (58) and `WR_ITEM_PENALTIES` (6) — all existing vetoes verified working; marginal candidates (gentle_alien, plastic_explosive, barricade, landmines/ratzilla/tyler) deliberately held pending better evidence.

## Deploy-candidate composition (v83 = what the campaign tests vs v79)

Two gameplay deltas + observability: (1) the v80/v82 impactful-offense band gate (recalibrated 41-win curve, ΔDPS impact test), (2) this allowlist tune, (3) v81 RSI + winner-trajectory HUD (no behavior). Attribution note: if the campaign misbehaves, the shop telemetry separates the two — band-gate effects appear as changed reroll/skip patterns at waves 13+, allowlist effects appear as purchases of the two new ids / absence of snowball-class early buys.

## Tests

65/65. `test_v83_policy_versions_are_consistent` (was v82); new `test_v83_item_audit_additions_and_retiers`; wiki-audit count assertions updated 96→98, 164→166, with a regression assertion keeping conditional Statue out.

## Acceptance additions for the Step-1 campaign

- The two new items appear in buy decisions when offered at sane scores; no Statue or early snowball/ice_cube purchases.
- All prior v82 acceptance criteria unchanged (≥6/8 wins, DPS medians ≥1620/2400 at w15/w18, no >400-gold band-deficient exits, HUD/telemetry match, RSI diagnostic-only).
