# v99 all-late-wave final-safety change record

Date: 2026-07-22

## Trigger

The first v98 collection run, `run_1784716192_4720`, reached wave 17 with full
health. Its emitted actions never pointed outward while already inside the
96-unit hard margin, and actual wall clearance remained at least 135.76 units.
However, 13 captures failed the required 300 ms held-command projection. At
capture seq 16343 the player was at x=213.85 with action x=-0.946; at seq 16346
it was at x=148.74 with action x=-0.846. Both commands projected across the
left hard margin.

The v98 repair constrained the low-health early-return path, while ordinary
full-health movement on waves 17-19 still applied final projectile and wall
safety only on wave 20. The incomplete v98 run is excluded from repaired data.

## Reversible repair

- Preserve the existing low-health safety tail.
- Apply final projectile safety and then predictive hard-wall safety to every
  ordinary command on waves 17-20 after movement smoothing.
- Preserve the v97 centered wave-20 behavior without a boss-range ring.
- Advance policy identity to `teacher_v1-0.1.99-gun-wp1` and mod identity to
  `0.2.7-wp2-capture`; the capture schema remains unchanged.

## Verification and deployment

- Focused policy/capture/collector/monitor tests: `74 passed`.
- Full repository suite: `95 passed`.
- Workshop and local deployment archives match byte-for-byte: SHA-256
  `4E19D4FD137C889A544E5918B16726849947D7A697342C72E697B30491447CEE`,
  with 18 entries in each archive.
- Stopped smoke launch loaded the v99 controller successfully
  (`AgentController ready`) with zero post-ready script/parse/load errors and
  zero post-start APPCRASH events.
- The positively identified smoke process (PID `21240`) was stopped, and
  auto-start remained `false`.
