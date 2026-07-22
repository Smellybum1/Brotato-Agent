# WP2 v111 smoke stop-and-repair report

## Decision

The v111 qualification source `run_1784761715_9604` is rejected and excluded
from the WP2 dataset. It completed a wave-20 victory with structurally complete
telemetry, matching identity, and zero runtime errors, but the strengthened
safety audit rejected it.

## Evidence

- Capture audit: 21,779 valid captures, every wave represented, zero malformed
  lines, schema mismatches, invalid captures, or invalid actions.
- v112 safety re-audit: 15 violations — 10 hidden hard-wall-safe body-relief
  opportunities and 5 active-relief commands that were not within 20 units of
  the best reported relief lane.
- No hard-wall, projectile-floor, sampled-action, or avoidable-damage audit
  violation was found.
- Events SHA-256:
  `15D3BED00CA017850009EFC5BC46FEF630C07F97EA53C64EFAB94061A021958D`
- Summary SHA-256:
  `D5D2D67089E9B39E1893AFB044DD43CDF6AB996BB7CB103BBCFFF9FB625D41A7`

## Root cause

v111 allowed the wall selector to choose a bounded hard-wall-safe relief lane,
but the final body-safety pass then rebuilt a strict wall-progress-only
candidate pool. That last arbiter could replace the relief command with a
materially worse route through a pack. Its longer prediction horizon also
exposed pack conflicts the shorter wall selector did not see.

The held-command audit additionally used the preceding decision's diagnostic
clearance rather than replaying the actual action and candidate geometry in the
current capture. The v112 auditor now recomputes both, removing stale diagnostic
false positives while retaining the genuine held-command faults.

## Repair

v112 (`teacher_v1-0.1.112-gun-wp1`, mod `0.2.20-wp2-capture`) makes the final
body-safety pass authoritative for bounded wall relief. It:

- evaluates both strict wall-progress and all hard-wall-safe candidates over
  the final 1.2-second body horizon;
- preserves an already-active relief or independently activates relief when
  strict lanes remain below 120 clearance and a hard-safe lane gains at least
  60;
- keeps projectile safety authoritative and anchors projectile tiers only to
  the active candidate pool;
- requires the emitted relief command to stay within 20 units of the best
  hard-safe, projectile-tier-compatible body lane;
- continues to apply the unconditional projected hard-wall clamp.

Focused verification passed 72 tests; the full suite passed 118 tests. v112
still requires a fresh one-run live qualification before any exact-20 source
campaign may begin.
