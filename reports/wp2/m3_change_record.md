# WP2 M3 change record — student-inference path (bc_v1 live behind teacher rails)

Milestone **M3 (student inference / serving)** of the WP2 learned-combat track.
Status: **QUALIFIED 2026-07-24** (infrastructure). Commit
`541e8ff` (M3 torch path) + `a29fc8a` (Stage G ONNX path). Branch
`wp2-combat-learning`. Design of record: `.tmp/wp2_m3_inference_architecture.md`
(packet §4.4/4.5/9.1/9.2/14.1-14.3).

M3 makes the qualified M2 behavior-cloning baseline `bc_v1_s1_full` (4.80°
teacher-val median; registry `models/registry/bc_v1_s1_full.json`, best.pt
sha256 `BE7E8232…6D6A9F0F`, 651,202 params) play the game live, and proves the
serving path is safe: the teacher is the fallback on every fault, and the
student never disturbs the teacher's own computation.

## What was built

**Godot side** (mod `0.2.34-wp2-capture`, `student_enabled` **default-off** in
code and absent-in-config ⇒ teacher-only):

- `learned/combat_bridge.gd` — StreamPeerTCP loopback client: framing (4-byte
  LE u32 length + UTF-8 JSON, 1 MiB cap), versioned handshake, connection state
  machine, bounded reconnect (retry 3 s, ≤5/wave). No gameplay logic.
- `learned/learned_combat_controller.gd` — control-tick orchestration: builds/
  sends `act` on the 20 Hz capture tick, polls replies each 60 Hz physics
  frame, 40 ms deadline + stale bookkeeping, per-period source resolution,
  applied-vector (`_wp2_previous_action`) tracking per design §2.4, telemetry.
- `learned/safety_fallback.gd` — action validation (finite, |a|≤1 clamp-and-
  classify), fallback-cause taxonomy (design §3.5), per-wave counters.
- `runtime/agent_controller.gd` — minimal integration only; teacher path
  byte-identical when the flag is off or the bridge dies.

**Python side:**

- `trainer/bridge/protocol.py` — protocol-v1 frame codec + message schema.
- `trainer/bridge/sidecar.py` — server: load + sha-verify `best.pt`, hash-gate
  normalization manifest + schemas, torch-CPU `.eval()` deterministic serving,
  health/latency stats, clean shutdown/reconnect. Refuses to serve on any hash
  mismatch (exit ≠ 0).
- `scripts/run_student_sidecar.py` — non-interactive entry.
- `docs/IPC_PROTOCOL.md` — protocol spec (packet-required doc).

**New telemetry** (versioned): `student_tick` (per control period: source,
cause, latency, student/teacher vectors), `student_wave_summary`,
`student_session` (handshake identity block). Audit gates read these.

## Evidence chain (validation ladder, each rung gates the next)

**Rung 1 — unit tests.** 337 tests green (frame codec round-trip / partial /
oversize / endianness; handshake accept-reject matrix per hash field; FIFO +
seq discipline; deadline/stale state machine; non-finite / malformed handling;
artifact-verification exit codes). `a29fc8a` raised this to 349 with the Stage G
suite.

**Rung 2 — offline replay parity** (`reports/wp2/student_replay_parity_v1.md`).
Frozen `combat_obs_v1` val payloads streamed live through the sidecar socket vs
the `bc_offline` reference (CPU float32, batch-1). **max |Δaction| = 0.000e+00
over 81,790/81,790 val ticks**, 0 unmatched, 0 NaN/Inf, 0 sidecar errors across
4 runs. Exact float32 parity, as designed.

**Rung 3 — latency benchmark** (`reports/wp2/student_latency_bench_v1.md`;
early/late/boss/peak payloads × 15/20/30 Hz). Offline gates PASS:
**model p99 2.07 ms** (≤10), **end-to-end p99 3.48 ms** (≤25), **100.000%
within 50 ms** (≥99.9), **0 deadline misses** (≤2 consecutive). Peak band =
top-5% entity load (14–36 enemies+projectiles).

**Rung 4 — one isolated live smoke** (`reports/wp2/student_smoke_v1_report.md`;
run `run_1784859783_62364`, defeat wave 11 = *planned manual-override
termination*, not a policy death). **INFRASTRUCTURE VERDICT: PASS** — all 13
audit gates:

- Handshake identity matches registry (`best.pt` independently re-hashed to
  `BE7E8232…6D6A9F0F` = registry = live `model_sha256`).
- **97.06 % student control** (6,174 ok + 3,395 clamped of 9,569); **99.71 %**
  excluding the planned 262-period kill-test outage.
- Applied-student latency (live, n=9,569): **p50 15 · p95 16 · p99 19.3 · max
  37 ms**; 0 applied ticks > 50 ms.
- Mid-wave sidecar kill → teacher takeover + bounded reconnect verified (262
  consecutive `not_connected`, then re-handshake and resume); manual override
  and Ctrl+Shift+Q E-stop both verified live; clean sidecar `bye`, exit 0.
- `teacher.action` present 9,867/9,867 (label integrity); prev-action
  applied-vector continuity 9,569/9,569 exact; 0 nonfinite / malformed /
  sidecar protocol errors; every period classified inside the §3.5 taxonomy;
  `illegal_actions=0`, `hangs=0`.

Behavioral quality (bc_v1's known wave-20 / high-risk weakness; 35.5 % clamp
rate) was declared **out of scope** for this infra qualification and routed to
the DAgger track (see `reports/wp2/m4_change_record.md`).

## Stage G — ONNX path (commit `a29fc8a`, separate change behind the same protocol)

Exported `bc_v1_s1_full` best.pt to ONNX opset-18
(`models/registry/bc_v1_s1_full_onnx.json`, onnx sha256 `1DF7E70A…3940`).
Parity per packet §14.1 (`reports/wp2/onnx_parity_v1.md`): **max |Δ| =
1.132e-06 over 10,000 fixtures** (threshold 1e-04 ⇒ ~88× margin; mean 1.587e-07,
p99 5.246e-07), 0 NaN/Inf both backends. Fixtures: 8,000 stratified + 1,000
empty-group + 500 capacity-overflow + 500 edge-normalization. `OnnxModelService`
sits behind the unchanged protocol; **torch-CPU remains the default and the sole
live-qualified backend** — a live ONNX smoke is deferred pending operator
authorization. ONNX-backend offline latency: model p99 1.29 ms, e2e p99 2.66 ms.
Env pinned: ORT 1.27.0 / onnx 1.22.0 / torch 2.13.0+cu126
(`reports/wp2/inference_env_lock.md`); 349 tests green.

## Qualified status

Serving infrastructure is qualified for live student inference behind the
teacher rails on the torch-CPU backend. `bc_v1_s1_full` is the served model;
the ONNX artifact is byte-parity-verified but not yet live-qualified. This M3
path is what the M4 DAgger campaigns run on unchanged.
