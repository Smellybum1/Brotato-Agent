extends Node

# WP2 M3 student-inference bridge: non-blocking StreamPeerTCP client to the
# loopback Python sidecar (architecture note §3.2). No gameplay logic — framing,
# handshake, connection state machine, bounded reconnect only.
#
# Absolutely no blocking calls: connect is async and advanced by get_status()
# polling; reads drain get_available_bytes() into a buffer and decode only whole
# frames; writes go through put_partial_data() with an explicit unsent-byte
# carry. Any fault leaves the teacher in control (the learned controller reads
# is_ready()/take_messages() and falls back).
#
# Framing: 4-byte little-endian u32 payload length + UTF-8 JSON. The length
# prefix is hand-encoded so byte order never depends on StreamPeer state; we
# still set big_endian=false explicitly per the note.

const LOG_NAME := "Tom:BrotatoAgent:Bridge"

enum { DISCONNECTED, CONNECTING, HANDSHAKING, READY, HANDSHAKE_FAILED }
const _STATE_NAMES := ["disconnected", "connecting", "handshaking", "ready", "handshake_failed"]

const MAX_FRAME := 1048576            # 1 MiB oversize guard (note §3.2).
const RETRY_MS := 3000                # Bounded reconnect cadence (note §3.6.2).
const MAX_ATTEMPTS := 5               # Per wave; reset on notify_wave_start().
const CONNECT_TIMEOUT_MS := 2000      # Give up on a stuck CONNECTING socket.
const HANDSHAKE_TIMEOUT_MS := 3000    # Connected but no valid hello_ack.
const PING_INTERVAL_MS := 1000        # Heartbeat when READY and not in combat.

# hello_ack.schema_id is the OBSERVATION schema the sidecar serves (the capture
# schema is validated sidecar-side from hello.capture_schema_hash). This pin
# only changes when the observation schema revs — which requires retraining.
const OBSERVATION_SCHEMA_ID := "combat_obs_v1"

var state: int = DISCONNECTED

var _sock: StreamPeerTCP = null
var _read_buf: PoolByteArray = PoolByteArray()
var _write_buf: PoolByteArray = PoolByteArray()
var _inbound: Array = []
var _identity: Dictionary = {}

var _started: bool = false
var _shutdown: bool = false
var _reconnect_attempts: int = 0
var _next_retry_ms: int = 0
var _connect_started_ms: int = 0
var _handshake_started_ms: int = 0
var _last_act_ms: int = 0
var _last_ping_ms: int = 0

# Config / mod-side pins.
var _port: int = 51888
var _capture_schema_id: String = ""
var _capture_schema_hash: String = ""
var _control_hz: int = 20
var _expected_model_sha256: String = ""
var _telem = null


func configure(port: int, capture_schema_id: String, capture_schema_hash: String,
		control_hz: int, expected_model_sha256: String, telem) -> void:
	_port = port
	_capture_schema_id = capture_schema_id
	_capture_schema_hash = capture_schema_hash
	_control_hz = control_hz
	_expected_model_sha256 = expected_model_sha256
	_telem = telem


# ── lifecycle ──────────────────────────────────────────────────────────────────

func notify_wave_start() -> void:
	# Reset the per-wave reconnect budget and, on the first wave, begin connecting.
	# A handshake failure is terminal for the run and is never re-armed here.
	if state == HANDSHAKE_FAILED:
		return
	_reconnect_attempts = 0
	_next_retry_ms = 0
	_started = true
	if state == DISCONNECTED and not _shutdown:
		_begin_connect(OS.get_ticks_msec())


func shutdown() -> void:
	# Best-effort, non-blocking bye then close (E-stop / manual override / exit).
	if _shutdown:
		return
	if state == READY and _sock != null:
		_send_frame({"v": 1, "type": "bye"})
		_flush()
	_close_socket()
	state = DISCONNECTED
	_shutdown = true


func is_ready() -> bool:
	return state == READY


func get_state_name() -> String:
	return _STATE_NAMES[state]


func get_identity() -> Dictionary:
	return _identity


# ── send ───────────────────────────────────────────────────────────────────────

func send_act(seq: int, ts_ms: int, wave: int, payload: Dictionary) -> bool:
	if state != READY:
		return false
	_last_act_ms = OS.get_ticks_msec()
	return _send_frame({
		"v": 1, "type": "act", "seq": seq, "ts_ms": ts_ms,
		"wave": wave, "payload": payload,
	})


func take_messages() -> Array:
	# Whole decoded messages received while READY (action / error / pong).
	var out := _inbound
	_inbound = []
	return out


# ── poll (advances the state machine; never blocks) ────────────────────────────

func poll() -> void:
	if _shutdown or not _started:
		return
	var now := OS.get_ticks_msec()
	match state:
		CONNECTING:
			if _sock == null:
				_drop_and_schedule(now)
				return
			var st := _sock.get_status()
			if st == StreamPeerTCP.STATUS_CONNECTED:
				state = HANDSHAKING
				_handshake_started_ms = now
				_send_hello()
				_flush()
			elif st == StreamPeerTCP.STATUS_ERROR:
				_drop_and_schedule(now)
			elif now - _connect_started_ms > CONNECT_TIMEOUT_MS:
				_drop_and_schedule(now)
		HANDSHAKING:
			if _sock == null or _sock.get_status() != StreamPeerTCP.STATUS_CONNECTED:
				_drop_and_schedule(now)
				return
			_flush()
			_read_into_buffer()
			_decode_frames()
			# _decode_frames() may drop the link on a protocol error.
			if state == HANDSHAKING:
				_consume_handshake()
			# A peer that connects but never sends a valid hello_ack must not
			# wedge the state machine — treat as a failed attempt and retry.
			if state == HANDSHAKING and now - _handshake_started_ms > HANDSHAKE_TIMEOUT_MS:
				_drop_and_schedule(now)
		READY:
			if _sock == null or _sock.get_status() != StreamPeerTCP.STATUS_CONNECTED:
				_drop_and_schedule(now)
				return
			_flush()
			_read_into_buffer()
			_decode_frames()
			if state != READY:
				return  # protocol error dropped the link during decode
			if now - _last_act_ms > PING_INTERVAL_MS and now - _last_ping_ms > PING_INTERVAL_MS:
				_last_ping_ms = now
				_send_frame({"v": 1, "type": "ping", "ts_ms": now})
				_flush()
		DISCONNECTED:
			if _reconnect_attempts < MAX_ATTEMPTS and now >= _next_retry_ms:
				_begin_connect(now)
		HANDSHAKE_FAILED:
			pass


# ── connection helpers ─────────────────────────────────────────────────────────

func _begin_connect(now: int) -> void:
	_close_socket()
	_reconnect_attempts += 1
	_next_retry_ms = now + RETRY_MS
	_connect_started_ms = now
	_sock = StreamPeerTCP.new()
	_sock.set_big_endian(false)
	var err := _sock.connect_to_host("127.0.0.1", _port)
	if err != OK:
		_drop_and_schedule(now)
		return
	state = CONNECTING


func _drop_and_schedule(now: int) -> void:
	_close_socket()
	state = DISCONNECTED
	_next_retry_ms = now + RETRY_MS


func _close_socket() -> void:
	if _sock != null:
		_sock.disconnect_from_host()
		_sock = null
	_read_buf = PoolByteArray()
	_write_buf = PoolByteArray()


func _send_hello() -> void:
	var run_id := ""
	if _telem != null and ("run_id" in _telem):
		run_id = str(_telem.run_id)
	var hello := {
		"v": 1,
		"type": "hello",
		"capture_schema_id": _capture_schema_id,
		"capture_schema_hash": _capture_schema_hash,
		"control_hz": _control_hz,
		"run_id": run_id,
	}
	if _expected_model_sha256 != "":
		hello["expected_model_sha256"] = _expected_model_sha256
	_send_frame(hello)


func _consume_handshake() -> void:
	# Drain buffered messages looking for hello_ack; validate against mod pins.
	while _inbound.size() > 0:
		var m = _inbound.pop_front()
		if typeof(m) != TYPE_DICTIONARY:
			continue
		if str(m.get("type", "")) == "error":
			# The sidecar explicitly rejected our hello (capture-hash / model-pin /
			# protocol mismatch). Retrying cannot succeed — terminal for the run.
			state = HANDSHAKE_FAILED
			ModLoaderLog.warning("Student sidecar rejected handshake: %s — teacher only for this run" % str(m.get("reason", "?")), LOG_NAME)
			_close_socket()
			return
		if str(m.get("type", "")) != "hello_ack":
			continue
		if _validate_ack(m):
			_identity = _extract_identity(m)
			state = READY
			ModLoaderLog.info("Student sidecar handshake OK (%s)" % str(_identity.get("registry_run_name", "?")), LOG_NAME)
		else:
			state = HANDSHAKE_FAILED
			ModLoaderLog.warning("Student sidecar handshake rejected — teacher only for this run", LOG_NAME)
			_close_socket()
		return


func _validate_ack(m: Dictionary) -> bool:
	if int(m.get("v", -1)) != 1:
		return false
	if str(m.get("schema_id", "")) != OBSERVATION_SCHEMA_ID:
		return false
	if _expected_model_sha256 != "":
		if str(m.get("model_sha256", "")).to_lower() != _expected_model_sha256.to_lower():
			return false
	return true


func _extract_identity(m: Dictionary) -> Dictionary:
	# The full identity block, logged once to student_session telemetry.
	return {
		"schema_id": str(m.get("schema_id", "")),
		"observation_schema_hash": str(m.get("observation_schema_hash", "")),
		"input_config_sha256": str(m.get("input_config_sha256", "")),
		"model_sha256": str(m.get("model_sha256", "")),
		"normalization_sha256": str(m.get("normalization_sha256", "")),
		"registry_run_name": str(m.get("registry_run_name", "")),
		"backend": str(m.get("backend", "")),
		"pid": int(m.get("pid", -1)),
	}


# ── framing ────────────────────────────────────────────────────────────────────

func _send_frame(msg: Dictionary) -> bool:
	var payload_bytes := JSON.print(msg).to_utf8()
	var n := payload_bytes.size()
	if n > MAX_FRAME:
		return false
	var frame := PoolByteArray()
	frame.append(n & 0xFF)
	frame.append((n >> 8) & 0xFF)
	frame.append((n >> 16) & 0xFF)
	frame.append((n >> 24) & 0xFF)
	frame.append_array(payload_bytes)
	_write_buf.append_array(frame)
	_flush()
	return true


func _flush() -> void:
	if _sock == null or _write_buf.size() == 0:
		return
	if _sock.get_status() != StreamPeerTCP.STATUS_CONNECTED:
		return
	var res = _sock.put_partial_data(_write_buf)
	if typeof(res) != TYPE_ARRAY or res.size() < 2:
		return
	if res[0] != OK:
		return  # surfaced by the status check on the next poll
	var sent := int(res[1])
	if sent >= _write_buf.size():
		_write_buf = PoolByteArray()
	elif sent > 0:
		_write_buf = _drop_front(_write_buf, sent)


func _read_into_buffer() -> void:
	if _sock == null:
		return
	var avail := _sock.get_available_bytes()
	if avail <= 0:
		return
	var res = _sock.get_partial_data(avail)
	if typeof(res) != TYPE_ARRAY or res.size() < 2:
		return
	if res[0] != OK:
		return
	var chunk = res[1]
	if typeof(chunk) == TYPE_RAW_ARRAY and chunk.size() > 0:
		_read_buf.append_array(chunk)


func _decode_frames() -> void:
	while _read_buf.size() >= 4:
		var plen := int(_read_buf[0]) | (int(_read_buf[1]) << 8) \
			| (int(_read_buf[2]) << 16) | (int(_read_buf[3]) << 24)
		if plen < 0 or plen > MAX_FRAME:
			# Corrupt / oversize length prefix ⇒ protocol error ⇒ disconnect.
			_drop_and_schedule(OS.get_ticks_msec())
			return
		if plen == 0:
			_read_buf = _drop_front(_read_buf, 4)
			continue
		if _read_buf.size() < 4 + plen:
			return  # frame not fully arrived yet
		var payload_bytes := _read_buf.subarray(4, 4 + plen - 1)
		_read_buf = _drop_front(_read_buf, 4 + plen)
		var txt := payload_bytes.get_string_from_utf8()
		var parsed := JSON.parse(txt)
		if parsed.error == OK and typeof(parsed.result) == TYPE_DICTIONARY:
			_inbound.append(parsed.result)
		else:
			_inbound.append({"type": "__malformed__"})


func _drop_front(buf: PoolByteArray, n: int) -> PoolByteArray:
	if n <= 0:
		return buf
	if n >= buf.size():
		return PoolByteArray()
	return buf.subarray(n, buf.size() - 1)
