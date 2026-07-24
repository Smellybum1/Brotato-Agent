# Student-inference IPC protocol (v1)

Normative wire contract between the Godot mod (`learned/combat_bridge.gd`) and
the Python sidecar (`trainer/bridge/sidecar.py`). Implements packet §9.1
(versioned, length-prefixed loopback protocol). The reference codec is
`trainer/bridge/protocol.py`; this document is authoritative for interop.

## Transport

- **TCP, loopback only.** The sidecar binds `127.0.0.1` and re-verifies each
  accepted peer address is loopback; a non-loopback peer is closed without a
  reply. Single client at a time.
- **Port** default `51888`, overridable via `agent_config.json` (`student_port`)
  on the mod side and `--port` on the sidecar. The mod must connect
  asynchronously; a refused/absent connection is a fallback, never a stall.

## Framing

Each frame is a **4-byte little-endian unsigned u32 payload length** followed by
that many bytes of **UTF-8 JSON**. Little-endian matches the Godot `StreamPeer`
default. Every frame is a single JSON object with at least `{"type": <str>,
"v": 1}`.

- Maximum payload is **1 MiB** (`MAX_FRAME_BYTES`). A declared length above the
  ceiling, an oversize body on encode, invalid UTF-8/JSON, or a non-object
  payload is a **protocol error**: the sidecar sends a best-effort `error`
  (with `seq: null`) and closes the connection.
- Both sides handle partial reads and writes explicitly (loopback kernel buffers
  are large, but large frames may still fragment).
- Non-finite floats are never serialized (`allow_nan=False`).

## Messages

All messages carry `"v": 1`. Fields below are additional to `type`/`v`.

| type        | dir      | fields |
|-------------|----------|--------|
| `hello`     | mod→side | `protocol` (=1), `capture_schema_id`, `capture_schema_hash`, `control_hz`, `run_id`, optional `expected_model_sha256` |
| `hello_ack` | side→mod | `protocol` (=1), `schema_id`, `observation_schema_hash`, `input_config_sha256`, `model_sha256`, `normalization_sha256`, `registry_run_name`, `backend` (`"torch-cpu"`), `pid` |
| `act`       | mod→side | `seq` (monotonic), `ts_ms`, `wave`, `payload` (raw `combat_capture_v2` dict) |
| `action`    | side→mod | `seq`, `ax`, `ay`, `model_ms`, `total_ms` |
| `error`     | side→mod | `seq` (mirrors the request, or `null` for handshake/frame errors), `reason` |
| `ping`      | mod→side | optional `ts_ms` |
| `pong`      | side→mod | `served`, `errors`, `model_ms_p50`, `model_ms_p99` |
| `bye`       | either   | `reason` |

## Handshake

1. Mod connects and sends `hello`.
2. The sidecar **rejects** (sends `error`, closes, disables student mode for the
   run — cause `handshake_mismatch`) if any of:
   - `v` != 1 (`protocol_version_mismatch`);
   - `capture_schema_hash` != the sidecar's observation schema
     `source_capture_schema_hash` (`capture_schema_hash_mismatch`);
   - `expected_model_sha256` is present and does not match the served
     `model_sha256`, case-insensitive (`model_sha256_mismatch`).
3. Otherwise the sidecar replies `hello_ack` with its full identity block. The
   mod logs the identity to telemetry (`student_session`) and may additionally
   pin any field; a mismatch against a mod-side pin also disables student mode.

The identity block ties a live session to exact frozen artifacts:
`observation_schema_hash` (schema file hash), `input_config_sha256`
(`bc_input_v1.yaml`), `model_sha256` (`best.pt`), `normalization_sha256`
(`normalization_manifest.json`), and `registry_run_name`.

## Sequence, deadline, and staleness (mod-side judgment)

- `seq` is monotonically increasing per `act`. The sidecar processes requests
  **strictly FIFO** and echoes `seq` on the matching `action`/`error`.
- The mod discards any reply whose `seq` is not the most recent outstanding
  request (`stale_seq`). Staleness is entirely the mod's judgment; the sidecar
  never drops or reorders.
- The mod applies a per-request **deadline** (default 40 ms after send, i.e.
  before the next 20 Hz capture tick). A reply that lands within the deadline,
  matches `seq`, and passes safety validation is applied as the student action;
  otherwise the mod falls back to the teacher's fresh vector for that control
  period. Deadlines are not represented on the wire.

## Fallback causes (§3.5)

Every student-mode control period resolves to exactly one source + cause. The
sidecar surfaces the italicized wire-level ones; the rest are mod-side:

- `student` — action applied (`ok`; `clamped` if magnitude exceeded 1+1e-3 and
  was renormalized — a safety intervention, not a fallback).
- `teacher_fallback` (infrastructure): `not_connected`, `handshake_mismatch`,
  `timeout`, `disconnect`, *`stale_seq`*, *`malformed_reply`*,
  *`nonfinite_action`*, *`sidecar_error`*.
  - The sidecar emits `error` with `reason` in {`encode_error: …`,
    `nonfinite_action`, `sidecar_error: …`, `unknown_message: …`,
    `protocol_error: …`}; the mod maps these onto the taxonomy.
- `residual_base` — reserved (N/A for the BC stage).
- Disabled states (manual override, E-stop, `student_enabled=false`) are mode
  transitions, not per-tick fallbacks.

## Heartbeat, shutdown, reconnect

- The mod sends `ping` (~1 Hz outside combat); the sidecar replies `pong` with
  rolling health stats from a bounded window.
- Clean shutdown: the sidecar exits (code 0) on `bye`, on `SIGINT`/`SIGTERM`,
  and after client disconnect with no reconnect within `--idle-exit-sec`
  (default 120 s). A best-effort `bye` is sent on E-stop/manual override.
- Reconnect within the idle window is accepted and requires a **fresh
  handshake**.

## Versioning

`v` is the single protocol version, currently `1`; `hello`/`hello_ack` also carry
`protocol` as an explicit alias. A peer that sends a different `v` is rejected at
handshake. Any change to framing, message fields, or handshake semantics is a new
version — never a silent field addition that an older peer would misread. The
serving backend (`backend`, currently `torch-cpu`) may change (e.g. to an ONNX
backend) **without** a protocol bump, because the wire contract is identical; the
backend is reported in `hello_ack` for telemetry only.
