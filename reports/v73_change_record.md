# v73 post-pass comparison record

Date: 2026-07-21 Australia/Brisbane

## Purpose

WP1 passed on v72 at 18W/2L. v73 is a short, user-approved post-pass experiment using the full-campaign low-density analysis; it is not another 18-win certification gate and does not start WP2.

## Focused policy change

- Keep all v72 defensive adequacy thresholds.
- When wave 15+ offense is below 120, hard-reject an option whose only positive effects add max HP, armor, or regeneration to an already adequate layer. Lifesteal and any offensive, crowd-clear, mobility, or mixed benefit keep the option eligible.
- Increase late valuation of piercing-adjacent crowd clear: explosions, explosion size, death explosions/projectiles, and burning spread.
- Before wave 19, strongly deprioritize Silver Bullet while general offense is below 120; restore boss-only valuation in the final shop.
- Add Minigun to the priority ladder. Explicitly buy/save Minigun III+ and Chain Gun IV: buy when possible, sell only a strictly lower-tier gun when that makes the purchase reachable, lock an unaffordable offer once, bank the remainder of that shop, then buy or release the inherited lock on the next shop visit.

## Evidence

- The five lowest-density v72 victories carried 68% more telemetry-derived offense and 37% less extra HP than the other victories, with essentially the same sustain.
- The wave-16 defeat entered a fatal 56-enemy peak after spending scarce wave-15 money on boss-only and extra-defense items while below the general offense floor.
- All four v72 Minigun purchases won; Chain Gun had never been purchased because every historical offer was beyond the generic lock's price-reach rule.
- The supplied Well Rounded guide recommends SMG/shotgun concentration, flat ranged damage followed by attack speed/% damage, roughly bounded sustain, and piercing as a major ranged wave-clear multiplier. The v73 change follows those principles without discarding defensive breakpoints.

## Comparison acceptance

- Eight fresh v73 runs, at least seven victories.
- No early defeat (before wave 15), telemetry/orchestration error, hang, APPCRASH, or shop safety violation.
- Primary metric: mean per-wave p90 enemy density across victories, below the v72 victory baseline of 15.26.
- Secondary: mean per-wave maxima, 30+ density waves, hit chains/recovery, offense proxy, and rare-gun offer/lock/buy outcomes.

## Verification and deployment

- Targeted policy/monitor tests: 44 passed.
- Full suite with an isolated workspace temp root: 53 passed.
- Workshop and installed zips: 308165 bytes each, SHA-256 `83DD17E3A055FD8C69817CAE95EC2EE6DBF193F4910AC3F3900C8885F6D5302B`.
- Zip inspection confirmed manifest/controller v73 identifiers, Minigun and Chain Gun tier gates, the explicit rare-gun action, and the saturated-defense-only veto.
- Deployment used `scripts/deploy_mod.py --target agent --no-clear-latch`; no unrelated process was touched.
- The eight-run comparison started at 2026-07-21 11:15 Australia/Brisbane with run `run_1784596517_3802`. Both exact v73 tasks, their scoped process trees, Brotato, HUD, and fresh policy/mod telemetry were verified in agreement.
