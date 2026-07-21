# v77 change record

Updated: 2026-07-21 16:00 Australia/Brisbane

v77 is a focused repair over v76 and preserves the v73 rare-gun behavior, v75
affordable-offense priority, v76 hard sustain cap, and all existing safety
guards.

## Weapon-aware offense

- The policy and HUD now share `BotCombatModel.offense_rating(build)`.
- Estimated loadout DPS includes each equipped weapon's tier-derived base
  damage and cooldown, stat scaling, crit, projectile count, piercing, bounce,
  explosive-set bonus, and burning bonus.
- Estimated DPS is translated onto the historic 70/120 scale at 15 DPS per
  offense point. The total is `max(legacy stat score, weapon score)` to avoid
  double-counting stats already present in weapon DPS while retaining a safe
  fallback for effects the estimator cannot model.
- Telemetry/HUD expose legacy stat score, estimated weapon DPS, weapon score,
  equipped weapon count, and tier sum.

## Wave-20 movement

- Finale movement recomputes at 20 Hz and holds the command between decisions,
  instead of selecting a new vector at 60 Hz.
- Projectile escape rewards continuity with the current open lane.
- Boss orbit sides require a material safety advantage before switching.
- A requested direct reversal is converted into a perpendicular committed turn
  toward the safer/central lane, preventing opposing inputs from cancelling in
  place. Corner escape still overrides this continuity rule.

## Verification

- Targeted policy/movement checks: 29 passed.
- Full suite: 58 passed using an isolated workspace pytest temp directory.
- Python compile validation passed.
- Workshop/local deployment zips are byte-identical, SHA-256
  `4F167B231CB3DEFFA0CEF7D2713102BED4578817EB3F48A76D8F5D7C4AED3BD0`.
- Packaged manifest/policy: `0.1.77` / `teacher_v1-0.1.77-gun-wp1`.
