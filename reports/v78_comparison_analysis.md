# v78 shortened-comparison trigger analysis

Updated: 2026-07-21 19:49 Australia/Brisbane

## Outcome and scoped stop

- The comparison produced one completed **wave-19 defeat** and one partial run
  stopped in its wave-15 shop.
- The partial run entered a deterministic lock/unlock loop, an explicit
  shop-safety trigger. The exact v78 tasks were disabled and stopped, their
  identified workspace descendants were removed, and Brotato was stopped.
- The completed summary is telemetry-complete with zero errors, hangs, and
  illegal actions. The partial event stream is preserved. No post-start
  APPCRASH occurred.
- No v79, WP2 work, or commit was started.

## Run evidence

| Run | Result/state | Last wave | Mean per-wave p90 | Late-wave p90 | Mean wave max | Peak | Final offense | Est. DPS | Tier sum | Defense | Sustain |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `run_1784625123_14638` | Defeat | 19 | 17.12 | 32.10 | 22.53 | 71 | 199.88/159 | 2,998 | 20 | 255.83 | 9 |
| `run_1784626214_92387` | Stopped in shop | 15 | 12.59 | 24.70 | 17.07 | 34 | 138.36/153 | 2,075 | 18 | 233.33 | 11 |

Run 1 exceeded the v72 victory density baseline of 15.26 and was already a
loss, so v78 supplied no evidence of a win-rate or density improvement before
the safety trigger ended the comparison.

## Run 1: offense score overestimated practical clear

- The adaptive target did react to prior pressure, and the final score was
  comfortably above target: 199.88/159 with 2,998 estimated DPS.
- Practical clearing diverged sharply. Wave-15 p90 density was 31, wave 17 was
  29, and wave 19 jumped to **59.5 p90 / 71 peak** with no projectile pressure.
- The terminal build had 62 max HP, 5 armor, 17 dodge, defense 255.83 and
  sustain 9. It recovered repeatedly but could not remove the crowd quickly
  enough. This is a crowd-clear failure, not proof that more sustain would have
  solved the run.
- The prior-wave input was 23 when wave 19 surged to 59.5. A one-wave-lagged
  target cannot anticipate an abrupt density regime change, and the scalar
  estimated-DPS model still gives too much credit to mixed single-target or
  slow weapons relative to demonstrated clear rate.
- Whole-run commanded net/path movement was 3.53% with 422 direct reversals.
  The new finale displacement controller was not exercised because the run
  died before wave 20.

## Run 2: deterministic lock/unlock safety loop

- Through wave 15, density was better than run 1: 12.59 mean per-wave p90,
  p90 24.7 and peak 34 on wave 15.
- It reached the wave-15 shop at offense 138.36/153, defense 233.33 and sustain
  11 with only 11 materials. An unaffordable Revolver I was a reasonable
  offensive save target.
- Instead of banking the lock, the agent alternated `shop_lock` and
  `shop_unlock` roughly every 0.55 seconds. Preserved events contain **120
  locks, 112 unlocks, and 224 adjacent alternating transitions**; the last 20
  decisions continue the same pattern on Revolver I.

### Exact cause

The v78 offense-deficiency block unlocks a non-rare locked item when
`_direct_offense_gain(locked_item.effects) <= 0`. Weapon power is represented
by the weapon-aware model, not necessarily by generic item effects, so Revolver
I evaluates as zero direct gain and is incorrectly treated as a utility lock.
Later in the same decision function, the premium lock path sees an unaffordable
weapon with a positive weapon score and locks it again. Session state does not
mark this offense-first unlock as expired, so neither path prevents the next
toggle.

This is a policy safety bug introduced by combining the v78 utility-lock veto
with the existing weapon premium-lock path; it is not an infrastructure issue.

## Sustain and utility findings

- The earlier sustain cutoff substantially worked: run 1 moved from sustain 10
  around the pivot to 9 at death, while run 2 remained at 11 through the stop.
  There is no evidence of late sustain accumulation resembling v77's 27-point
  failure build.
- Normal utility locks were released while offense was deficient, but weapon
  locks need their own weapon-aware classification. Treating all zero-effect
  entries alike is unsafe.
- Run 2 also confirms that a cycle guard is needed independently of scoring:
  the decision layer should never repeat the same lock/unlock pair indefinitely.

## Finale movement finding

Neither run reached wave 20, so the 120-pixel/16-tick finale displacement
commitment remains unvalidated. It should be retained as an unproven change,
not credited as a success or reverted from this evidence alone.

## Recommended next repair (not implemented)

1. Exclude weapons from the generic utility-lock veto and classify them with
   the weapon-aware offense model.
2. Mark an offense-first unlock as expired for that visit so the same item
   cannot be relocked immediately.
3. Add a hard bounded cycle guard for repeated identical or alternating shop
   decisions, falling back to `shop_go` while preserving evidence.
4. Calibrate effective offense with observed clear performance: discount
   weapon mixtures that permit high recent p90 density, and carry a stronger
   density trend/peak penalty into the next shop rather than relying on one
   previous-wave p90 value alone.
5. Keep the earlier sustain cap and the untested finale displacement controller
   until clean evidence evaluates them.

These changes require explicit user authorization for a new version and
deployment.
