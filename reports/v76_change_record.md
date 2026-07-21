# v76 change record

Date: 2026-07-21 Australia/Brisbane

## Purpose

v76 is a focused repair over v75. It preserves v75's affordable-offense path and
v73's Minigun/Chain Gun behavior, closes the observed hard sustain-cap fail-open
path, and exposes the live offense/defense state in both the HUD and telemetry.

## Hard defense-layer cap

- From wave 10 onward, a pure max-HP, armor, regeneration, or lifesteal purchase
  is vetoed when the prospective purchase reaches that layer's adequacy threshold.
- The veto no longer depends on profile identity, offense target availability, or
  the offense proxy being below target. This removes the v75 path that allowed
  Blood Leech, Butterfly, Mushroom, and Fresh Meat after offense appeared at/above
  target to the scorer.
- Live numeric stats are now extracted without boolean fallback operators. The
  v75 helper collapsed any nonzero regeneration/lifesteal value to `1`, preventing
  combined sustain from ever reaching its 8/10 cap; v76 preserves the real values.
- Mixed items remain eligible only when they have measurable direct offense or
  crowd-clear gain.
- Adequacy remains 45 HP / 5 armor / 8 sustain for waves 10-14 and
  60 HP / 8 armor / 10 sustain from wave 15.

## Observable build metrics

- Offense total is the exact shop-policy proxy: ranged damage + percent damage +
  attack speed. The HUD also shows those components and crit chance.
- Offense target is 70 for waves 10-14 and 120 from wave 15. A display-only early
  ramp reaches 70 at wave 10.
- Defense shows true live max HP, armor, dodge, regeneration, lifesteal, and
  combined sustain. Telemetry also retains the policy's raw max-HP stat field so
  the displayed total is not confused with a stat-bonus value.
- Defense total normalizes HP, armor, and sustain to 100 points apiece at their
  wave targets. The ideal total is 300 and the value is intentionally uncapped so
  over-defense remains visible.
- The same metric object is emitted on combat ticks, shop decisions, and level-up
  decisions and is rendered by the live monitor.

## Preserved behavior

- Affordable policy-safe net-positive offense is considered before ordinary shop
  thresholds and non-rare utility locks while offense is below target.
- Minigun III+ and Chain Gun IV keep explicit buy/save and lower-tier replacement.
- Existing movement, combine, lock-lifetime, item-veto, telemetry, and watchdog
  safeguards are unchanged.

## Verification

- Focused shop-policy source checks: 27 passed.
- Unit suite: 54 passed.
- Full suite: 56 passed.
- Installed workshop/local zip SHA-256:
  `D3F32E04D1C35021D985C8A2861D2190BCFE8527546857B1D16E97F39F06C0C3`.
- Fresh accepted telemetry (`run_1784610239_10475`) confirmed the final artifact,
  numeric offense/defense values, HUD/telemetry flow, and healthy watchdogs.
- No commit was created.
