# Student live smoke — WP2 M3 (rung 4)

Generated 2026-07-24 · run `run_1784859783_62364` · outcome **defeat wave 11**
(planned manual-override termination, not a policy death) · **INFRASTRUCTURE
VERDICT: PASS**.

First live student-inference run: `bc_v1_s1_full` served over protocol v1
loopback, 20 Hz control, `student_enabled=true`. This audit qualifies the
**infrastructure** (handshake, fallback, override/E-stop, latency, telemetry
integrity) per the smoke-plan audit gates. Read-only over `events.jsonl`
(9,867 combat_capture + 9,867 student_tick), the two sidecar processes'
JSONL log, and `godot.log`. Behavioral (policy-quality) observations are a
separate, explicitly out-of-scope note at the end.

## Verdict — audit gates

| gate | status | evidence |
|---|---|---|
| Handshake identity block matches registry | PASS | `student_session` seq 4; 3 core hashes match `bc_v1_s1_full.json`; `best.pt` sha independently recomputed = registry hash |
| Steady-state student control (large majority) | PASS | 97.06 % of all periods; 99.71 % excluding the planned kill-test outage |
| Every period classified (no cause outside §3.5 taxonomy) | PASS | 0 unclassified of 9,859 reconstructed periods |
| Applied-student latency (end-to-end, live) p99 ≤ 25 ms | PASS | p50 15 · p95 16 · p99 19.3 · max 37 ms; 0 applied ticks > 50 ms |
| Max consecutive fallback ≤ 2 in connected steady state | PASS | max 2 outside the outage (gate ≤ 2); 262 inside the planned kill window only |
| Mid-wave kill → teacher takeover + bounded reconnect | PASS | 262 consecutive `not_connected` (wave 4), reconnect 12:24:51, student resumed; `godot.log` 2nd handshake line 126 |
| Manual override disables student, run continues | PASS | `error{kind:manual_override}` seq 20965; no further student ticks |
| Ctrl+Shift+Q → E-stop + clean sidecar `bye` | PASS | `godot.log:307` "Emergency stop engaged" ×1; sidecar `bye`, exit 0, 7,874 served / 0 errors; correctly **absent** from run telemetry (`_run_started` guard) |
| teacher.action present on every capture (label integrity) | PASS | 9,867 / 9,867 |
| prev-action continuity (applied-vector semantics §2.4) | PASS | student 9,569 / 9,569 exact; fallback stretches consistent with applied-vector rule |
| Zero nonfinite / malformed / sidecar protocol errors | PASS | 0 nonfinite components; 0 `malformed_reply`; 0 `sidecar_error`; sidecar `errors=0` |
| Existing safety audits clean on the run | PASS | `illegal_actions=0`, `hangs=0` (only "error" is the planned override) |
| No abort condition tripped | PASS | no fallback storm (>50 %), no telemetry write failure, no bridge-attributable hitch |

## Student session identity (`student_session`, seq 4)

Independently verified against `models/registry/bc_v1_s1_full.json`. `best.pt`
was re-hashed from disk this audit (`be7e8232…` = registry `checkpoints.best`
= session `model_sha256`), closing the loop model-file → registry → live
handshake.

| field | session value | registry field | match |
|---|---|---|---|
| `observation_schema_hash` | `C653D836…8BB9B2A` | `schema_hash` | ✅ |
| `model_sha256` | `BE7E8232…6D6A9F0F` | `checkpoints.best.sha256` (+ live re-hash) | ✅ |
| `normalization_sha256` | `FD3C55F6…6D27D166` | `normalization_manifest_hash` | ✅ |
| `input_config_sha256` | `CF87A0F8…D9505893` | not in registry; = rung-2 parity sidecar `hello_ack` | ✅ (cross-ref) |
| `registry_run_name` | `bc_v1_s1_full` | `run_name` | ✅ |
| `schema_id` / `backend` | `combat_obs_v1` / `torch-cpu` | — | ✅ |

Capture schema the sidecar accepted (`combat_capture_v2`,
`95B6444796…DD46D951`) equals the mod's emitted `capture_schema_hash` and the
sidecar startup log's `source_capture_schema_hash`. `godot.log` records two
`handshake OK (bc_v1_s1_full)` lines (33/53 original, 126 restart) — matching
the two sidecar PIDs (4300, 34568).

## Per-wave table (`student_wave_summary`, authoritative)

Latency columns include the late/timed-out replies (that is *why* they timed
out); applied-student-only latency is in the whole-run section. `fb` = fallback
periods by cause. All 11 wave summaries present, including wave 11's emitted on
shutdown.

| wave | ticks | ok | clamped | fallback (cause×n) | p50 | p95 | p99 | max | max-cons | stale |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 440 | 277 | 159 | not_connected×1, timeout×3 | 16 | 17 | 24 | 164 | 1 | 0 |
| 2 | 551 | 360 | 187 | timeout×4 | 16 | 17 | 24 | 173 | 1 | 2 |
| 3 | 640 | 418 | 221 | timeout×1 | 16 | 16 | 17 | 24 | 1 | 1 |
| 4 | 746 | 340 | 143 | **not_connected×262**, timeout×1 | 16 | 17 | 18 | 56 | **262** | 0 |
| 5 | 851 | 619 | 231 | timeout×1 | 15 | 16 | 17 | 25 | 1 | 1 |
| 6 | 940 | 572 | 366 | timeout×2 | 16 | 17 | 17 | 65 | 1 | 1 |
| 7 | 1051 | 606 | 445 | — | 15 | 16 | 23 | 29 | 0 | 0 |
| 8 | 1146 | 800 | 345 | timeout×1 | 15 | 16 | 19 | 164 | 1 | 0 |
| 9 | 1251 | 692 | 557 | timeout×2 | 15 | 16 | 20 | 184 | 1 | 1 |
| 10 | 1246 | 825 | 414 | timeout×7 | 13 | 16 | 21 | 200 | 1 | 1 |
| 11 | 1005 | 670 | 330 | timeout×4, disconnect×1 | 15 | 16 | 21 | 73 | 1 | 1 |

Wave totals sum to exactly 9,867 ticks = capture count = tick count (no
lost/duplicated telemetry). Wave-11 partial stats reconstructed from
`student_tick` (1,004 periods: 669 ok, 330 clamped, 4 timeout, 1 disconnect;
applied-latency p50 15 / p95 16 / p99 17 / max 37; max-cons 1) agree with the
shutdown-emitted summary (1,005; the 1-tick delta is a boundary pairing slip,
below).

## Whole-run classification & latency

- **9,859** control periods reconstructed (9,867 captures; 8 lost to
  wave-boundary pairing slips, see anomalies — immaterial, 0.08 %).
- **Student-controlled: 6,174 `ok` + 3,395 `clamped` = 9,569 (97.06 %)**;
  **99.71 %** excluding the planned 262-period kill outage.
- **Clamped: 3,395 (35.5 % of student periods).** Every clamped action has
  |a| = 1.000 exactly → the magnitude clamp renormalized saturating outputs to
  the unit circle as designed (a safety bound, not a fallback). `ok` actions
  span |a| 0.066–1.001.
- Fallback periods: **290** total — `not_connected` 263, `timeout` 26,
  `disconnect` 1. **Zero unclassified**; every (source,cause) pair inside the
  §3.5 taxonomy.
- Applied-student latency (source=student, whole run, n=9,569): **p50 15 ·
  p95 16 · p99 19.3 · max 37 ms**; **7** applied ticks in 25–37 ms, **0** > 50
  ms. The 26 `timeout` periods are replies that arrived past the 40 ms
  deadline (teacher covered them) — separate, high-latency outliers, not
  applied.
- 0 nonfinite action components across 9,859 periods.
- Sidecar model-side latency (its own histogram): p50 ≈ 1.0–1.2 ms, p99 ≈
  1.6–2.8 ms throughout — the wire/serialize/scheduling delta is the
  remainder up to the ~15 ms Godot-side figure.

## Kill-test outage & fallback taxonomy

Longest consecutive fallback streak = **262 periods**, all `not_connected`,
capture_seq 1732–1993, wave 4, ts 101889–114930 ms (~13 s) — exactly the
planned 12:24:38 kill → 12:24:51 re-handshake window. The first post-kill tick
was already `not_connected` (act_seq −1): the dead socket flipped the bridge to
`not_connected` within one control tick rather than logging a `disconnect`
phase first (a §3.6-point-2 labeling nuance; teacher covered every tick,
reconnect succeeded, student resumed — functionally correct). **Outside** this
window the max consecutive fallback is **2** (gate ≤ 2).

## prev-action continuity (§2.4 applied-vector semantics)

Each capture paired with the `student_tick` resolving the same control period;
`teacher.previous_action` of capture N+1 compared to the *applied* vector of
period N (tolerance 1e-4).

- **Student periods: 9,569 / 9,569 exact** (200-sample spot check 200/200;
  full population 9,569/9,569; clamped subset 3,395/3,395). `previous_action`
  reproduces the applied — including renormalized clamped — student vector on
  every student-controlled tick.
- `student_tick.teacher{x,y}` == `combat_capture.teacher.action`: **9,859 /
  9,859 exact** (both are the emit-time teacher snapshot).
- Fallback/teacher stretches: the 262-period outage matches the teacher
  snapshot exactly. **8 of the 26 connected `timeout` periods** show
  `previous_action` differing from the *emit-time* teacher snapshot — this is
  **correct**: on a timeout the applied vector is the teacher's fresh 60 Hz
  recompute at the 40 ms deadline, 2–3 physics frames after the 20 Hz emit
  snapshot. Every such `previous_action` is a valid unit teacher vector lying
  on the teacher's trajectory between consecutive emits (verified by tracing
  `teacher.action` around each). Zero genuine continuity breaks.

## Anomalies & observations (not smoothed over)

1. **Wave-boundary pairing slips (16 events, 8 net-unpaired captures).** At
   each wave transition the last-period `student_tick` is emitted one slot
   late — after the next capture and/or the `student_wave_summary` — so a
   strict-adjacency join drops one cap/tick pair per boundary. This is an
   **audit-reconstruction artifact only**: capture count == tick count ==
   9,867, wave summaries sum to 9,867, teacher.action present on all. No
   telemetry is lost or duplicated; the authoritative per-wave counts come from
   `student_wave_summary`.
2. **Kill-test labeled `not_connected` throughout, never `disconnect`.** See
   above — the hard kill collapsed straight to `not_connected`. Behavior is
   correct; only the intermediate `disconnect` label §3.6-2 anticipated did not
   appear.
3. **Lone `disconnect` in wave 11 is the shutdown boundary.** The single
   `disconnect` period (act_seq 9604, ts 546691) is the very last student tick,
   9 ms before the `manual_override` error (546700) and the sidecar `bye`
   (12:32:03) — the reply didn't return because the bridge was tearing down at
   the override. Teacher covered it (max-cons 1). Not a spurious mid-combat
   drop.
4. **8 `stale_discards` run-wide, 0 `stale_seq` fallbacks.** Stale replies were
   discarded by the seq-discipline and the in-order reply still resolved the
   period as `student` — sequence handling absorbed them without costing a
   fallback.
5. **Per-wave max-latency spikes (164–200 ms) are timed-out replies, not
   applied actions.** They coincide with the `timeout` counts and the applied
   p99 stays ≤ 24 ms every wave. Late waves (8–10) show the most (`timeout` 1,
   2, 7) — consistent with heavier late-wave payloads, but well inside budget
   (teacher covered each; no >2-consecutive miss outside the kill window).
6. **5 `recovery_attempt{meta_screen_stalled}` events** = the run's 5
   between-wave WP1 meta-screen recoveries (matches `summary.recoveries=5`).
   Normal out-of-combat WP1 behavior, unrelated to the student path.

## Sidecar log

Two processes: original PID 4300 (listening 12:22:31, killed 12:24:38 in the
kill test), restart PID 34568 (listening 12:24:50, handshake 12:24:51). Clean
`bye` → `shutdown` at 12:32:03, **7,874 served, 0 errors**, model p50 0.96 ms /
p99 1.95 ms in the final window. Zero protocol errors across either process.

## Behavioral note — OUT OF SCOPE for the infra verdict

Not part of the PASS/FAIL. The run reached wave 11 before the planned
override-idle termination; the defeat is the manual-override test leaving the
player idle, not a policy death. Model quality (e.g. bc_v1's known wave-20 /
high-risk weakness, median 16–31°; the 35.5 % clamp rate indicating frequent
saturating outputs) is a model finding for the M2/DAgger track, not an
infrastructure signal, and is deliberately excluded from this qualification.

## Environment / sources

- Run: `run_1784859783_62364/events.jsonl` (109 MB, 20,966 events) + `summary.json`
- Sidecar log: `.tmp/student_sidecar_smoke_20260724.jsonl`
- `godot.log` lines 33/53/126 (handshakes), 307 (E-stop)
- Registry: `models/registry/bc_v1_s1_full.json`; model `models/bc_v1/bc_v1_s1_full/best.pt`
- mod 0.2.34-wp2-capture · game 1.1.15.4 · policy `teacher_v1-0.1.125-gun-wp1` · character well_rounded / smg · danger 0
