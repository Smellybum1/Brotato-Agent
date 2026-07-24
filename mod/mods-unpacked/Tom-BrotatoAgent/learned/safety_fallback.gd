extends Reference

# WP2 M3 student-inference safety layer (pure logic, no I/O).
#
# Two jobs, both side-effect free except for the per-wave counters this object
# owns:
#   1. validate_action(reply) — finiteness + unit-magnitude gate on a decoded
#      sidecar reply, classifying the outcome per architecture note §3.5.
#   2. Per-wave bookkeeping — {source x cause} counters, end-to-end latency
#      samples (p50/p95/p99 over a sorted copy — cheap at 20 Hz), and the
#      longest consecutive teacher-fallback streak, for student_wave_summary.
#
# No File / OS / socket calls live here so the resolution math stays unit
# testable and mirror-able in the Python parity harness.

# ── Fallback-cause taxonomy (note §3.5) ────────────────────────────────────────
# Student-applied outcomes.
const CAUSE_OK := "ok"
const CAUSE_CLAMPED := "clamped"
# teacher_fallback — infrastructure faults.
const CAUSE_NOT_CONNECTED := "not_connected"
const CAUSE_HANDSHAKE_MISMATCH := "handshake_mismatch"
const CAUSE_TIMEOUT := "timeout"
const CAUSE_DISCONNECT := "disconnect"
const CAUSE_STALE_SEQ := "stale_seq"
const CAUSE_MALFORMED_REPLY := "malformed_reply"
const CAUSE_NONFINITE_ACTION := "nonfinite_action"
const CAUSE_SIDECAR_ERROR := "sidecar_error"

const SOURCE_STUDENT := "student"
const SOURCE_TEACHER := "teacher_fallback"

# A student action within 1 + MAG_EPS of the unit circle is applied verbatim;
# beyond it the vector is renormalized and flagged as a safety clamp.
const MAG_EPS := 0.001

var _counters: Dictionary = {}
var _latencies: Array = []
var _streak: int = 0
var _max_streak: int = 0
var _stale_discards: int = 0
var _ticks: int = 0
var _wave: int = -1


func reset_wave(wave: int) -> void:
	_wave = wave
	_counters = {}
	_latencies = []
	_streak = 0
	_max_streak = 0
	_stale_discards = 0
	_ticks = 0


func validate_action(reply: Dictionary) -> Dictionary:
	# Protocol carries the action as ax/ay; accept x/y defensively too.
	var ax = reply.get("ax", reply.get("x", null))
	var ay = reply.get("ay", reply.get("y", null))
	if not _is_finite_number(ax) or not _is_finite_number(ay):
		return {"ok": false, "x": 0.0, "y": 0.0, "cause": CAUSE_NONFINITE_ACTION}
	var fx := float(ax)
	var fy := float(ay)
	var mag := sqrt(fx * fx + fy * fy)
	if mag > 1.0 + MAG_EPS:
		if mag > 0.0:
			fx = fx / mag
			fy = fy / mag
		return {"ok": true, "x": fx, "y": fy, "cause": CAUSE_CLAMPED}
	return {"ok": true, "x": fx, "y": fy, "cause": CAUSE_OK}


func record(source: String, cause: String, latency_ms: int) -> void:
	# One resolved control period => exactly one source+cause (note §3.5).
	_ticks += 1
	if not _counters.has(source):
		_counters[source] = {}
	var bucket: Dictionary = _counters[source]
	bucket[cause] = int(bucket.get(cause, 0)) + 1
	if source == SOURCE_TEACHER:
		_streak += 1
		if _streak > _max_streak:
			_max_streak = _streak
	else:
		_streak = 0
	if latency_ms >= 0:
		_latencies.append(latency_ms)


func note_stale() -> void:
	# A reply whose seq != the in-flight request is discarded, not resolved
	# (note §3.2). Counted for observability without touching period state.
	_stale_discards += 1


func summary() -> Dictionary:
	return {
		"wave": _wave,
		"ticks": _ticks,
		"counters": _counters.duplicate(true),
		"latency_ms": _latency_stats(),
		"max_consecutive_fallback": _max_streak,
		"stale_discards": _stale_discards,
	}


func _latency_stats() -> Dictionary:
	var n := _latencies.size()
	if n == 0:
		return {"n": 0, "p50": 0.0, "p95": 0.0, "p99": 0.0, "max": 0.0}
	var ordered := _latencies.duplicate()
	ordered.sort()
	return {
		"n": n,
		"p50": _percentile(ordered, 0.50),
		"p95": _percentile(ordered, 0.95),
		"p99": _percentile(ordered, 0.99),
		"max": float(ordered[n - 1]),
	}


func _percentile(ordered: Array, quantile: float) -> float:
	# Match _sample_percentile() in agent_controller for consistency.
	if ordered.empty():
		return 0.0
	var idx := int(ceil(clamp(quantile, 0.0, 1.0) * ordered.size())) - 1
	idx = int(clamp(idx, 0, ordered.size() - 1))
	return float(ordered[idx])


func _is_finite_number(v) -> bool:
	if typeof(v) != TYPE_REAL and typeof(v) != TYPE_INT:
		return false
	var f := float(v)
	return not is_nan(f) and not is_inf(f)
