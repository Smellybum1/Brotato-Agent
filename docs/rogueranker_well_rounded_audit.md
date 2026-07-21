# RogueRanker item audit for the Well-Rounded gun agent

Source: [RogueRanker's Brotato item tier list](https://rogueranker.com/brotato-tier-list/),
patch 1.1.6 / March 2026. All 68 listed items are classified below.

This audit targets a six-slot, mixed-family rapid-fire ranged build whose primary
objective is an 18-of-20 win rate. A high community tier is treated as an item's
ceiling, not proof that the current build can use it.

The implementation was promoted in v58 with
`BUILD_AWARE_ROGUERANKER_ENABLED := true` after the user selected it for a fresh
gate. It was never mixed into the preceding v57 evaluation.

## Hard vetoes (7)

These are unacceptable reliability risks even when their nominal upside is high.

| Item | Reason |
| --- | --- |
| Peacock | The next-wave enemy damage spike is incompatible with a reliability gate. |
| Weird Ghost | Starting a wave at 1 HP creates avoidable run-ending variance. |
| Hourglass | Rewinds wave progress and creates a 1-HP restart. |
| Gobbler's Hat | The large speed and dodge penalties damage the agent's core survival loop. |
| Bait | Deliberately adds a dangerous enemy pack for a modest damage gain. |
| Black Flag | A dedicated Curse/naval engine card with no payoff in this build. |
| Axolotl | Random stat swapping can destroy the build's carefully balanced offense or defense. |

## Conditional vetoes (29)

The agent buys these only when the live build satisfies the listed enabler.

| Item | Required live-build condition |
| --- | --- |
| Bloody Hand | At least 8% life steal before accepting its self-damage loop. |
| Greek Fire | An equipped weapon already applies burning. |
| Giant Belt | At least 20% critical chance. |
| Explosive Shells | An equipped weapon belongs to the explosive set. |
| Retromation's Hoodie | At least 20% dodge before paying the range penalty. |
| Focus | No more than two distinct weapon families. |
| Mammoth | At least one melee weapon. |
| Diploma | Wave 10 or earlier, or an engineering-scaling weapon. |
| Lucky Coin | At least 20% critical chance. |
| Robot Arm | A melee or engineering-scaling weapon. |
| Esty's Couch | Speed is already zero or negative. |
| Frozen Heart | Burning or elemental weapon scaling. |
| Stone Skin | At least 10 armor. |
| Power Generator | At least 10 speed. |
| Vigilante Ring | Wave 14 or earlier, leaving enough scaling runway. |
| Sad Tomato | At least 5 HP regeneration before accepting the half-HP start. |
| Strange Book | At least 5 elemental damage and an engineering-scaling weapon. |
| Pile of Books | An engineering-scaling weapon. |
| Snowball | Wave 12 or earlier plus burning or elemental scaling. |
| Crown | Wave 12 or earlier and at least 10 harvesting. |
| Black Belt | Wave 8 or earlier, or a melee weapon. |
| Mouse | At least 5% life steal. |
| Alien Eyes | At least 50 max HP. |
| Handcuffs | Wave 15 or later, when the max-HP cap has less time to hurt growth. |
| Metal Detector | Wave 12 or earlier, leaving time for the economy payoff. |
| Ice Cube | Burning or elemental weapon scaling. |
| Regeneration Potion | At least 5 HP regeneration. |
| Bean Teacher | Wave 12 or earlier, leaving time for the XP payoff. |
| Ashes | Wave 16 or later and at least 8 armor to absorb its per-wave armor loss. |

## Existing dynamic safety guards (3)

| Item | Existing guard |
| --- | --- |
| Ball and Chain | Vetoed only when its cooldown floor would slow an equipped weapon. |
| Shackles | Existing stat-freeze protection rejects harmful speed caps. |
| Knot | Existing weapon-lock protection rejects it until the arsenal is fully upgraded. |

## Retained as generally useful (29)

These items are not automatically bought; normal price, effect scoring, tier bias,
wave timing, and defensive needs still decide the purchase. They are retained
because they have a credible payoff for the current ranged build.

- S: Potato; Grind's Magical Leaf.
- A: Spider; Heavy Bullets; Night Goggles; Octopus; Coil; Exoskeleton; Wisdom;
  Clover; Lure.
- B: Triangle of Power; Alloy; Tardigrade; Candle; Medikit; Extra Stomach;
  Ricochet; Jetpack; Panda.
- C: Coupon; Goblet; Sunken Bell; Sifd's Relic; Cape; Leather Vest; Dangerous
  Bunny; Fruit Basket.
- D: Whistle (loot-alien farming can still produce items for a strong gun build).

Counts: 7 hard vetoes + 29 conditional vetoes + 3 existing dynamic guards +
29 retained items = 68 audited items.
