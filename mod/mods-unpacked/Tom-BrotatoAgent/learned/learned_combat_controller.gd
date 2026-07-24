extends Node

# WP2 M3 student-inference orchestration (architecture note §3.4).
#
# agent_controller hands this object the raw capture payload + the teacher's
# fresh movement vector on each 20 Hz capture tick (on_capture), and calls
# poll() every physics frame. Per control period we:
#   - send one act{seq} (non-blocking) and record the send time;
#   - hold the previous applied vector until the reply lands (get_override_vector
#     returns it while pending — the teacher's 60 Hz recompute must not leak to
#     the player during the ~1-frame wait);
#   - on a valid, seq-matched reply within the deadline ⇒ apply the student
#     action; on deadline / disconnect / malformed / non-finite / stale ⇒ leave
#     the teacher's fresh vector in control (has_override()==false) and log the
#     cause.
# The resolved applied vector of each finished period becomes teacher.previous_
# action at the next capture tick (get_resolved_applied_vector, note §2.4).
#
# All fault handling routes to the teacher — the mod never blocks and never
# depends on the sidecar being present.

const _SAFETY_SCRIPT = preload("res://mods-unpacked/Tom-BrotatoAgent/learned/safety_fallback.gd")

# Override modes for the vector the player applies this frame.
enum { MODE_HOLD, MODE_STUDENT, MODE_TEACHER }

# Reply must arrive within 40 ms of send — before the next 50 ms capture tick.
const DEADLINE_MS := 40

var _bridge = null
var _telem = null
var _fb = null

var _shutdown: bool = false
var _seq: int = 0
var _pending: bool = false
var _pending_seq: int = -1
var _pending_send_ms: int = 0
var _pending_teacher: Vector2 = Vector2.ZERO
var _pending_wave: int = 0

var _mode: int = MODE_TEACHER
var _held_vector: Vector2 = Vector2.ZERO
var _student_vector: Vector2 = Vector2.ZERO
var _resolved_applied: Vector2 = Vector2.ZERO

var _current_wave: int = -1
var _session_emitted: bool = false


func setup(bridge, telem, cfg: Dictionary) -> void:
	_bridge = bridge
	_telem = telem
	_fb = _SAFETY_SCRIPT.new()
	if _bridge != null:
		_bridge.configure(
			int(cfg.get("port", 51888)),
			str(cfg.get("capture_schema_id", "")),
			str(cfg.get("capture_schema_hash", "")),
			int(cfg.get("control_hz", 20)),
			str(cfg.get("expected_model_sha256", "")),
			telem)


# ── per-frame poll (called every physics frame by agent_controller) ────────────

func poll() -> void:
	if _shutdown or _bridge == null:
		return
	_bridge.poll()
	if not _session_emitted and _bridge.is_ready():
		_emit_session(_bridge.get_identity())
		_session_emitted = true
	for m in _bridge.take_messages():
		_handle_message(m)
	# Resolve a pending period on disconnect or deadline expiry.
	if _pending:
		if not _bridge.is_ready():
			_resolve_fallback(_SAFETY_SCRIPT.CAUSE_DISCONNECT)
		elif OS.get_ticks_msec() - _pending_send_ms > DEADLINE_MS:
			_resolve_fallback(_SAFETY_SCRIPT.CAUSE_TIMEOUT)


# ── per capture-tick entry (called by agent_controller after emit) ─────────────

func on_capture(payload: Dictionary, teacher_vec: Vector2, wave: int) -> void:
	if _shutdown:
		return
	# Wave boundary: flush the finished wave's summary, arm a fresh reconnect
	# budget, reset counters.
	if wave != _current_wave:
		if _current_wave >= 0:
			_emit_wave_summary(_current_wave)
		_current_wave = wave
		if _fb != null:
			_fb.reset_wave(wave)
		if _bridge != null:
			_bridge.notify_wave_start()
	# Defensive: a period should always resolve before the next tick (deadline
	# 40 ms < 50 ms period). If one is somehow still open, close it as timeout.
	if _pending:
		_resolve_fallback(_SAFETY_SCRIPT.CAUSE_TIMEOUT)
	# Begin the new control period. Hold the previous applied vector meanwhile.
	_held_vector = _resolved_applied
	_pending_teacher = teacher_vec
	_pending_wave = wave
	_mode = MODE_HOLD
	if _bridge != null and _bridge.is_ready():
		_seq += 1
		_pending_seq = _seq
		_pending_send_ms = OS.get_ticks_msec()
		_pending = true
		if not _bridge.send_act(_seq, _pending_send_ms, wave, payload):
			_pending = false
			_resolve_fallback(_SAFETY_SCRIPT.CAUSE_DISCONNECT)
	else:
		# No live sidecar ⇒ pure teacher play for this period.
		_pending_seq = -1
		_pending_wave = wave
		_resolve_fallback(_not_ready_cause())


# ── vectors consumed by agent_controller ───────────────────────────────────────

func has_override() -> bool:
	# True only while we impose a vector (holding for a reply, or student action).
	# In teacher-fallback mode the caller keeps its fresh teacher vector.
	return _mode == MODE_HOLD or _mode == MODE_STUDENT


func get_override_vector() -> Vector2:
	if _mode == MODE_HOLD:
		return _held_vector
	if _mode == MODE_STUDENT:
		return _student_vector
	return Vector2.ZERO


func get_resolved_applied_vector() -> Vector2:
	# The applied vector of the most recently resolved period — feeds
	# teacher.previous_action at the next capture tick (note §2.4).
	return _resolved_applied


func shutdown() -> void:
	if _shutdown:
		return
	if _pending:
		_resolve_fallback(_SAFETY_SCRIPT.CAUSE_DISCONNECT)
	if _current_wave >= 0:
		_emit_wave_summary(_current_wave)
	if _bridge != null:
		_bridge.shutdown()
	_mode = MODE_TEACHER
	_shutdown = true


# ── message handling / resolution ──────────────────────────────────────────────

func _handle_message(m) -> void:
	if typeof(m) != TYPE_DICTIONARY:
		return
	var mtype := str(m.get("type", ""))
	if mtype == "action" or (mtype == "" and m.has("ax")):
		if not _pending:
			return
		var seq := int(m.get("seq", -1))
		if seq != _pending_seq:
			# Late reply from a prior period — discard, keep waiting (note §3.2).
			if _fb != null:
				_fb.note_stale()
			return
		# Strict deadline: poll() runs at frame granularity, so a reply drained
		# this frame may already be past the 40 ms budget — resolve as timeout
		# rather than applying a stale action.
		if OS.get_ticks_msec() - _pending_send_ms > DEADLINE_MS:
			_resolve_fallback(_SAFETY_SCRIPT.CAUSE_TIMEOUT)
			return
		var res: Dictionary = _fb.validate_action(m)
		if not res.get("ok", false):
			_resolve_fallback(_SAFETY_SCRIPT.CAUSE_NONFINITE_ACTION)
			return
		_student_vector = Vector2(float(res.get("x", 0.0)), float(res.get("y", 0.0)))
		_resolve_student(str(res.get("cause", _SAFETY_SCRIPT.CAUSE_OK)))
	elif mtype == "error":
		if _pending and int(m.get("seq", -1)) == _pending_seq:
			_resolve_fallback(_SAFETY_SCRIPT.CAUSE_SIDECAR_ERROR)
	elif mtype == "__malformed__":
		if _pending:
			_resolve_fallback(_SAFETY_SCRIPT.CAUSE_MALFORMED_REPLY)
	# pong / unknown types: ignore.


func _resolve_student(cause: String) -> void:
	_mode = MODE_STUDENT
	_resolved_applied = _student_vector
	var lat := OS.get_ticks_msec() - _pending_send_ms
	_pending = false
	if _fb != null:
		_fb.record(_SAFETY_SCRIPT.SOURCE_STUDENT, cause, lat)
	_emit_tick(_pending_seq, _pending_wave, _SAFETY_SCRIPT.SOURCE_STUDENT, cause,
		lat, _student_vector, _pending_teacher)


func _resolve_fallback(cause: String) -> void:
	_mode = MODE_TEACHER
	_resolved_applied = _pending_teacher
	var lat := -1
	if _pending:
		lat = OS.get_ticks_msec() - _pending_send_ms
	_pending = false
	if _fb != null:
		_fb.record(_SAFETY_SCRIPT.SOURCE_TEACHER, cause, lat)
	_emit_tick(_pending_seq, _pending_wave, _SAFETY_SCRIPT.SOURCE_TEACHER, cause,
		lat, Vector2.ZERO, _pending_teacher)


func _not_ready_cause() -> String:
	if _bridge != null and _bridge.state == _bridge.HANDSHAKE_FAILED:
		return _SAFETY_SCRIPT.CAUSE_HANDSHAKE_MISMATCH
	return _SAFETY_SCRIPT.CAUSE_NOT_CONNECTED


# ── telemetry (shares the agent_controller TelemetryWriter instance) ───────────

func _emit_tick(seq: int, wave: int, source: String, cause: String,
		latency_ms: int, student: Vector2, teacher: Vector2) -> void:
	_emit_versioned_or_plain("student_tick", {
		"seq": seq,
		"wave": wave,
		"source": source,
		"cause": cause,
		"latency_ms": latency_ms,
		"student": {"x": student.x, "y": student.y},
		"teacher": {"x": teacher.x, "y": teacher.y},
	})


func _emit_wave_summary(wave: int) -> void:
	if _fb == null:
		return
	var s: Dictionary = _fb.summary()
	s["wave"] = wave
	_emit_versioned_or_plain("student_wave_summary", s)


func _emit_session(identity: Dictionary) -> void:
	var block := identity.duplicate(true)
	block["control_hz"] = 20
	_emit_versioned_or_plain("student_session", block)


func _emit_versioned_or_plain(event: String, payload: Dictionary) -> void:
	if _telem == null:
		return
	if _telem.has_method("emit_versioned"):
		_telem.emit_versioned(event, payload, "1.0.0")
	elif _telem.has_method("emit"):
		_telem.emit(event, payload)
