# v75 offense-first purchase guarantee

Date: 2026-07-21 Australia/Brisbane

## Purpose

v72 remains the certified WP1 policy at 18W/2L. v74 demonstrated that a wave-10 score pivot alone did not prevent sustain-heavy builds or guarantee affordable offense while the build was materially below target. v75 is the user-approved focused follow-up and retains the v73 rare-gun workflow.

## Focused policy

- Treat max HP, armor, regeneration, and lifesteal as defense; mixed sustain no longer receives a blanket exemption.
- Evaluate adequacy prospectively: a defensive purchase is capped when it would bring the relevant layer to or above the existing wave-10 or late adequacy floor.
- Preserve a mixed purchase only when it also supplies measurable direct ranged offense or crowd clear.
- While offense is below its wave target, buy an affordable, policy-safe, net-positive ranged-damage, attack-speed, percent-damage, piercing, bounce, explosion, death-projectile, or burning-spread item before applying the ordinary purchase-value threshold.
- Apply the same safe net-positive direct-offense preference to level-up choices below target.
- Do not allow a non-rare utility lock to precede an affordable direct-offense purchase.
- Reject enemy-density increases that add no direct offense while the build is below target.
- Preserve v73's exact Minigun III+ and Chain Gun IV buy/save attempt, strictly-lower-tier replacement rule, and lock lifecycle.

## Verification

- Focused policy tests: 26 passed.
- Full unit suite: 53 passed.
- Full suite: 55 passed with an isolated workspace temp root.
- Workshop and installed zips: 309255 bytes each, SHA-256 `F32F1AC924253597F783145226E6C5205D0AA1FA9123A5426496D0F8C6B8B600`.
- Zip inspection confirmed v75 identifiers, wave-10 offense targets, prospective defense caps, offense-first purchase routing, the enemy-density veto, and preserved Minigun III+/Chain Gun IV tiers.
- Deployment used `scripts/deploy_mod.py --target agent --no-clear-latch`; no unrelated process was touched.

## Short comparison

- Started: 2026-07-21 14:20 Australia/Brisbane, from a fresh supervisor baseline.
- Eight fresh runs, requiring at least seven victories.
- Stop early on any defeat before wave 15, two defeats total, infrastructure/safety failure, or all eight completed runs.
- Primary comparison remains victory mean per-wave p90 enemy density against v72's 15.26 baseline.
- Track offense proxy at waves 10, 12, 15, and 18, sustain purchases, affordable direct-offense decisions, utility locks, and rare-gun outcomes.

## Outcome

- Stopped after the first run, which completed as a wave-19 defeat (0W/1L), after live evidence showed the hard sustain cap was not applied at wave 15 while the event-derived offense proxy remained below 120.
- See `reports/v75_comparison_analysis.md` for the preserved evidence. No v76 was started.
