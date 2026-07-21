# v76 shortened-comparison analysis

Updated: 2026-07-21 16:00 Australia/Brisbane

## Preserved result

- Completed record: 1W/1L. A third run was stopped at wave 5 only after the
  user explicitly authorized v77.
- `run_1784610239_10475`: victory on wave 20, but HP reached 4 while boss
  projectiles peaked at 30.
- `run_1784611376_66003`: defeat on wave 20. HP reached 9 while projectiles
  again peaked at 30; waves 16 and 18 took no damage and cleared normally.
- There were no telemetry errors, hangs, illegal actions, missing summaries,
  watchdog failures, or post-start APPCRASH events.

## Movement finding

Both wave-20 runs showed the same cancellation signature. At the 2 Hz
telemetry sample rate, the victory contained 19 direct reversals and the loss
contained 13. Net movement was only 3.7% and 9.8% of commanded path length,
respectively. This agrees with the visually observed rapid micro-movements in
one place: the 60 Hz finale selector repeatedly chose opposing directions and
the movement component spent its time braking instead of escaping.

## Offense-metric finding

The v76 HUD and adequacy threshold used only ranged damage + percent damage +
attack speed. It did not account for equipped weapons or tiers. Wave 16 of the
defeat scored only 97/120 but averaged 8.06 living enemies, spent 45/124 samples
at density 5 or lower, and took zero damage. Its upgraded SMGs, revolvers and
shotguns supplied clear power that the stat-only score could not represent.

## Decision

The user authorized a focused v77 repair: stabilize wave-20 escape movement and
replace the gun-blind offense proxy with a weapon-aware estimate. WP1 remains
certified from v72; this comparison remains an improvement experiment.
