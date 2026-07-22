# v98 late-survival wall-safety change record

Date: 2026-07-22

## Trigger

The first v97 collection run, `run_1784714504_75459`, ended in defeat on wave
17. At low health the survival branch returned before the final projectile and
wall constraints. The player reached 12.1 units from the bottom boundary while
emitting strongly outward movement, was pinned among 52–55 enemies, and died in
a late hit chain. Completed defect run `run_1784714504_75459` and partial
successor `run_1784715449_23026` are excluded from repaired training data.

## Reversible repair

- Preserve the existing wave-17–19 panic/pure-repulsion survival objective and
  smoothing.
- Before the early return, run the smoothed action through final projectile
  safety and then predictive hard-wall safety.
- Persist and return only the constrained action.
- Preserve the v97 wave-20 centered-finale behavior without a boss-range ring.
- Advance policy identity to `teacher_v1-0.1.98-gun-wp1` and mod identity to
  `0.2.6-wp2-capture`; the capture schema remains unchanged.

## Verification and deployment

- Focused policy/capture/collector/monitor tests: `71 passed`.
- Full repository suite: `94 passed`.
- Workshop and local deployment archives match byte-for-byte: SHA-256
  `E2D737DBF3EC41679DD7D26956BEA8E3460E0ED97149889EDA10D419D9284130`,
  with 18 entries in each archive.
- Stopped smoke launch loaded the v98 controller successfully
  (`AgentController ready`) with zero post-ready script/parse/load errors and
  zero post-start APPCRASH events.
- The positively identified smoke process (PID `34472`) was stopped, and
  agent auto-start remained `false` after the exercise.
