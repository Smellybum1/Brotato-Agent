# WP2 v113 smoke stop/repair report

The one-run v113 qualification smoke was rejected and stopped. It is incomplete
and must not enter the teacher dataset.

- Run: `run_1784765399_1627`
- Identity: `teacher_v1-0.1.113-gun-wp1`, `0.2.21-wp2-capture`
- Observed fault: wave-12 capture 11040 emitted a nearly due-left route with
  13.0 units of predicted body clearance while a hard-wall-safe due-right
  sampled lane offered 269.6, a 256.6-unit improvement.
- Consequence: the route continued through the dense pack and an 11-damage
  event followed at capture 11059.
- Root cause: the final predictive body-safety arbiter only ran on waves 17-20.
  Wave 12 therefore emitted no body-safety diagnostics and retained the unsafe
  potential-field route.
- Containment: exact collector PID 44932 and scoped Brotato PID 41800 were
  stopped, auto-start was forced false, and the monitor automation was paused.
- Raw evidence was preserved unchanged. `events.jsonl` SHA-256:
  `1B2F9DF78BB40E9E224F74EAB803B991156B2390D481A60843CF4010E8D0DB9B`.

The repair must apply the final predictive body gate throughout the campaign,
enforce the open-pack tier whenever a materially clearer sampled lane exists,
and extend the safety audit from late waves to all fresh combat decisions.
