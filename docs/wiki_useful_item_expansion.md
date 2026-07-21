# Full wiki item-catalogue expansion

Source: [Brotato Wiki items](https://brotato.wiki.spellsandguns.com/Items),
updated for game version 1.1.15.4. The page reports 208 vanilla items plus 33
Abyssal Terrors items (241 catalogue rows). Its generated table currently repeats
Candy Bag, leaving 240 unique normalized item names.

## Result

- Existing RogueRanker table: 68 items.
- Missing unique wiki items reviewed: 172.
- Useful missing items added: 96.
- Expanded late-game allowlist: 164 unique items.
- Missing items deliberately not added: 76.

The new items live in `WIKI_USEFUL_ITEM_TIERS`, separate from
`ROGUERANKER_ITEM_TIERS`, so the project does not attribute our build-specific
judgments to RogueRanker. The legacy allowlist and bonus functions read the union
for compatibility.

These edits were promoted in v58 after the v57 game and watchdogs were stopped.
The v58 deployment starts a fresh gate so results are not mixed across policies.

## Added items

### S (6)

Anvil; Catling Gun; Jellyshield; Scapegoat; Seashell; White Flag.

These provide automatic weapon upgrades, ranged-scaling damage, projectile
protection, enemy diversion, exceptional rapid-fire projectile scaling, or a
particularly safe harvesting/enemy-count trade.

### A (27)

Adrenaline; Alien Magic; Alien Worm; Baby with a Beard; Bandana; Banner; Big
Arms; Blindfold; Doc Moth; Fin; Goldfish; Improved Tools; Jelly; Lantern; Medal;
Mirror; Poisonous Tonic; Reinforced Steel; Ritual; Sharp Bullet; Silver Bullet;
Small Magazine; Tentacle; Ugly Tooth; Wandering Bot; Warrior Helmet; Wings.

These are strong direct ranged-offense, sustain, movement, crowd-control, shop,
or survivability options with manageable downsides.

### B (49)

Acid; Baby Elephant; Baby Gecko; Bag; Bat; Beanie; Blood Leech; Broken Mouth;
Butterfly; Cake; Coffee; Community Support; Crystal; Cyberball; Cyclops Worm;
Eyepatch; Feather; Fertilizer; Fresh Meat; Gambling Token; Garden; Glass Cannon;
Glasses; Gummy Berserker; Head Injury; Helmet; Hunting Trophy; Injection;
Insanity; Lens; Lootworm; Lost Duck; Lucky Charm; Medical Turret; Metal Plate;
Missile; Mushroom; Mutation; Padding; Pearl; Plant; Scope; Shmoop; Small Fish;
Snail; Sunglasses; Terrified Onion; Wheat; Whetstone.

These remain options rather than forced purchases: live effect scoring, price,
wave, and defensive needs still decide whether they are worth buying.

### C (14)

Alien Tongue; Clockwork Wasp; Lemonade; Little Frog; Lumberjack Shirt; Piggy
Bank; Propeller Hat; Recycling Machine; Scar; Scared Sausage; Spyglass; Treasure
Map; Tree; Weird Food.

These have modest, early-economy, pickup, healing, reroll, crate, tree, or XP
utility. Their small tier bonus prevents the allowlist from turning them into
priority buys.

## Additional conditional guards

The following newly allowed items are vetoed unless their live-build condition is
met once the build-aware feature is enabled:

- Baby Elephant and Cyberball: at least 20 Luck.
- Bag: wave 15 or earlier.
- Community Support: at least 5 Armor.
- Eyepatch: at least 15% Crit Chance.
- Fertilizer: wave 12 or earlier.
- Gambling Token and Gummy Berserker: at least 3 Armor.
- Glass Cannon: at least 8 Armor.
- Hunting Trophy: at least 20% Crit Chance.
- Injection: at least 25 Max HP.
- Little Frog: wave 10 or earlier and at least 8% Dodge.
- Pearl: at least 20 Luck.
- Piggy Bank, Propeller Hat, and Scar: wave 12 or earlier.
- Recycling Machine and Spyglass: wave 16 or earlier.
- Sunglasses: at least 4 Armor.
- Treasure Map: wave 15 or earlier.
- Tree: wave 14 or earlier.

## Why the other 76 were not added

The remaining missing cards are dominated by one or more of these problems for
the current agent:

- melee, elemental, engineering, structure, burning, consumable, or Curse engines
  without a live payoff;
- stand-still mechanics that conflict with continuous evasive movement;
- self-damage, added enemy health/damage/speed, extra elite, or random-stat risk;
- ranged-damage penalties whose compensation is irrelevant to the gun build;
- weak late-game economy or scaling that cannot repay its price before wave 20;
- duplicate functionality already represented by safer cards.

They are not globally declared bad. They remain excluded only from this
Well-Rounded rapid-fire gun allowlist and can be reconsidered for another profile.
