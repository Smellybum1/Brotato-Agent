# WP2 v121 change record — diagnosed relief-floor fallback

## Trigger evidence (v120 smoke, run_1784780790_52579)

The v120 smoke was behaviorally the strongest run of the qualification
chain: wave-20 victory, dash validated live (17 episodes, all within the
24-capture bound, 86% stall uptake, zero dash-time damage, zero material
cap-saturation in every band, 1,115 gold entering the wave-15 shop), zero
behavioral violations. It was rejected on exactly one audit violation:
capture 18555 emitted a command with no selected body diagnostic.

Root cause: with wall-body relief active the body floor rises to the
45-unit contact tier; at 18555 every sampled lane offered <= 13.3 while the
incoming command held 46.5. The selection loop admitted nothing, silently
kept the (clearer) baseline, and never wrote `body_selected_clearance`.
Correct command, missing bookkeeping.

## Change (policy v121, mod 0.2.29 — behavior-preserving)

- `_finale_body_safety`: when the relief floor exceeds every sampled lane,
  the fallback is explicit — the selected diagnostic mirrors the input
  clearance and the baseline returns immediately.
- Audit: `_body_projectile_floor_unavailable` gains the matching signature
  (relief active, selected == input, best below the contact tier) so the
  preserved command is informational, not a projectile-floor violation.

## Verification

Full suite: 136 passed (new audit-signature test and source assertion with
the frozen 18555 numbers). The v120 run remains rejected (its frozen
telemetry carries the -1 sentinel); v121 requires its own smoke.
