# v74 wave-10 offense-pivot record

Date: 2026-07-21 Australia/Brisbane

## Purpose

v72 remains the certified WP1 policy at 18W/2L. v73's short comparison stopped at 1W/2L because its defense veto began too late and did not reproduce the high-offense profile of v72's lowest-density victories. v74 is the user-approved follow-up experiment: emphasize DPS over defense from wave 10, lower defense-adequacy thresholds modestly, and preserve v73's Minigun/Chain Gun workflow.

## Focused policy

- Start the mid-game pivot at wave 10 rather than wave 12.
- Use offense target 70 for waves 10-14 and 120 from wave 15 onward.
- From wave 10, hard-reject an option whose only positive effects add max HP, armor, or regeneration to an already-adequate layer while offense is below target. Lifesteal and mixed offensive, crowd-clear, or mobility effects remain eligible.
- Wave-10 adequacy floors: 45 max HP, 5 armor, and 8 combined regeneration plus lifesteal.
- Lower late adequacy modestly from 65/10/12 to 60 max HP, 8 armor, and 10 combined sustain.
- Increase below-target scoring for ranged damage, attack speed, percent damage, piercing/bounce, explosions, death projectiles, and burning spread; reduce below-target HP/armor/dodge/regeneration/lifesteal bonuses.
- While below the applicable offense target, increase the shop reroll threshold by 8 points so the agent uses its existing search budget rather than settling for utility.
- Preserve v73's exact Minigun III+ and Chain Gun IV priority, lower-tier-only replacement, one-visit lock/save/buy, and inherited-lock release behavior.

## Verification and deployment

- Policy source tests: 25 passed.
- Full unit suite: 52 passed.
- Full suite: 54 passed with an isolated workspace temp root.
- Workshop and installed zips: 308491 bytes each, SHA-256 `9AF16FB276626D0F89279DD1127417150F4654E371FC217833D047947E1EF0F4`.
- Zip inspection confirmed v74 identifiers, wave-10 pivot, both mid and late adequacy thresholds, stronger offense search, and preserved rare-gun tiers.
- Deployment used `scripts/deploy_mod.py --target agent --no-clear-latch`; no unrelated process was touched.

## Short comparison

- Eight fresh runs, requiring at least seven victories.
- Stop early on any defeat before wave 15, two defeats total, infrastructure/safety failure, or all eight completed runs.
- Primary comparison remains victory mean per-wave p90 enemy density against v72's 15.26 baseline.
- Track offense proxy at waves 10, 12, 15, and 18 to verify that v74 changes the trajectory rather than merely changing terminal purchases.

## Outcome

- Stopped by explicit user direction after one completed defeat at wave 16; a second run was active at wave 16 when stopped and is excluded from the comparison.
- The completed run reached only 19 offense at wave 10, 28 at wave 12, 36 at wave 15, and 36 at defeat while continuing to buy substantial sustain.
- Wave-16 enemy density reached p90 35 and maximum 48, followed by fatal hit chains of 23, 18, and 15 damage.
- Evidence showed that mixed/lifesteal sustain remained eligible and that an affordable direct-offense item could be skipped while a more expensive utility item was locked. Merely increasing offense scores was therefore insufficient.
- The exact v74 watchdogs, their scoped process trees, and the positively identified Brotato process were stopped; no unrelated process was touched.
