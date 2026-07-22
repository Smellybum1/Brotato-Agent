# WP2 v110 exact-20 stop and repair

The v110 exact-20 campaign was stopped at 2026-07-23 08:56 AEST after the
user directly observed an avoidable route into and through an enemy pack on
wave 20 of `run_1784759417_37573`.

## Evidence and disposition

- Collector PID `22760` and scoped Brotato PID `44880` were positively
  identified and stopped. Auto-start was set to false and verified.
- Terminal v110 runs `run_1784758292_31305` and
  `run_1784759417_37573` remain structurally complete, but neither is eligible
  for the dataset. The strengthened v111 audit finds 7 and 25 hidden
  wall-relief body-lane faults respectively.
- Interrupted run `run_1784760578_83805` stopped during wave 9 at capture
  7472 and is excluded. Its preserved partial `events.jsonl` SHA-256 is
  `89095268B00767DFD48C330F31C78D3E9C9419145C6E9F0CBB998F7F0E553893`.
- No raw telemetry was rewritten.

The observed failure is reproduced at captures 20520-20524. Strict wall
recovery discarded all lanes that did not increase the minimum 260-unit wall
lookahead. It therefore emitted an inward-right command whose body clearance
was only 73-99 units. Hard-wall-safe relief lanes exposed 154-267 units of
clearance, but the old audit examined only the strict wall-progress pool and
fresh decisions, so it incorrectly accepted the run.

## Repair

v111 (`teacher_v1-0.1.111-gun-wp1`, mod `0.2.19-wp2-capture`) retains strict
inward wall recovery whenever it has at least 120 units of body clearance. If
that pool is below 120 and a hard-wall-safe sampled lane improves body
clearance by at least 60, it temporarily selects from the relief pool and
requires the final choice to remain within 20 units of the best relief lane.
The hard-wall projection remains unconditional.

The safety audit now scans held wave-20 commands for hard-safe lanes hidden by
strict wall recovery and checks every active relief command against its
reported best lane. The frozen v110 runs are rejected by this new gate.

## Verification before deployment

- Focused tests: 70 passed.
- Full suite: 116 passed.
- Frozen v110 re-audit: 32 violations total; both terminal runs rejected.
