extends Reference
# Append-only JSONL telemetry writer. Failures never crash the controller.

const SCHEMA_VERSION := "1.0.0"
const POLICY_VERSION := "teacher_v1-0.1.94-gun-wp1"

var run_id: String = ""
var seq: int = 0
var path: String = ""
var enabled: bool = true
var write_failures: int = 0
var started_at_ms: int = 0
var summary: Dictionary = {}
var _last_phase: String = ""

func begin_run(meta: Dictionary) -> void:
	run_id = str(meta.get("run_id", _make_run_id()))
	seq = 0
	started_at_ms = OS.get_ticks_msec()
	write_failures = 0
	_last_phase = ""
	var dir = "user://brotato_agent/runs/" + run_id
	var d = Directory.new()
	d.make_dir_recursive(dir)
	path = dir + "/events.jsonl"
	summary = {
		"run_id": run_id,
		"schema_version": SCHEMA_VERSION,
		"policy_version": POLICY_VERSION,
		"start_timestamp": _iso_now(),
		"character": meta.get("character", ""),
		"weapon": meta.get("weapon", ""),
		"danger": meta.get("danger", 0),
		"endless": meta.get("endless", false),
		"wave_retry": meta.get("wave_retry", false),
		"game_version": meta.get("game_version", ""),
		"mod_version": meta.get("mod_version", "0.2.2-wp2-capture"),
		"config_id": meta.get("config_id", "well_rounded_d0_smg"),
		"result": "incomplete",
		"last_wave": 0,
		"waves_completed": 0,
		"recoveries": 0,
		"errors": 0,
		"hangs": 0,
		"illegal_actions": 0,
		"purchases": [],
		"level_ups": [],
		"crates": [],
		"rerolls": 0,
		"locks": 0,
		"materials_spent": 0,
		"damage_taken": 0,
		"telemetry_complete": false,
	}
	emit("run_start", meta)

func emit(event_type: String, payload: Dictionary = {}) -> void:
	_emit_with_schema(event_type, payload, SCHEMA_VERSION)

func emit_versioned(event_type: String, payload: Dictionary, schema_version: String) -> void:
	# New append-only event families can opt into a new envelope version without
	# changing the certified v1 records or rewriting historical telemetry.
	_emit_with_schema(event_type, payload, schema_version)

func _emit_with_schema(event_type: String, payload: Dictionary, schema_version: String) -> void:
	if not enabled:
		return
	seq += 1
	var ev = {
		"schema_version": schema_version,
		"run_id": run_id,
		"seq": seq,
		"ts_ms": OS.get_ticks_msec(),
		"event": event_type,
		"payload": payload,
	}
	_append(ev)
	_update_summary(event_type, payload)

func phase_transition(from_phase: String, to_phase: String, extra: Dictionary = {}) -> void:
	if from_phase == to_phase:
		return
	var p = extra.duplicate()
	p["from"] = from_phase
	p["to"] = to_phase
	emit("phase_transition", p)
	_last_phase = to_phase

func end_run(result: String, extra: Dictionary = {}) -> void:
	summary["result"] = result
	summary["end_timestamp"] = _iso_now()
	summary["duration_ms"] = OS.get_ticks_msec() - started_at_ms
	summary["last_wave"] = int(extra.get("last_wave", summary.get("last_wave", 0)))
	summary["waves_completed"] = int(extra.get("waves_completed", summary.get("last_wave", 0)))
	summary["telemetry_complete"] = write_failures == 0 and result != "incomplete"
	for k in extra.keys():
		summary[k] = extra[k]
	emit("run_end", {"result": result, "summary": summary})
	_write_summary()

func _update_summary(event_type: String, payload: Dictionary) -> void:
	match event_type:
		"recovery_attempt":
			summary["recoveries"] = int(summary.get("recoveries", 0)) + 1
		"error":
			summary["errors"] = int(summary.get("errors", 0)) + 1
		"purchase_decision":
			summary["purchases"].append(payload)
			if payload.get("type", "") == "shop_reroll":
				summary["rerolls"] = int(summary.get("rerolls", 0)) + 1
			if payload.get("type", "") == "shop_lock":
				summary["locks"] = int(summary.get("locks", 0)) + 1
		"level_up_decision":
			summary["level_ups"].append(payload)
		"crate_decision":
			summary["crates"].append(payload)
		"player_damage":
			summary["damage_taken"] = float(summary.get("damage_taken", 0)) + float(payload.get("amount", 0))
		"phase_transition":
			if payload.has("wave"):
				summary["last_wave"] = int(payload.get("wave", summary.get("last_wave", 0)))

func _append(ev: Dictionary) -> void:
	var f = File.new()
	var err = f.open(path, File.READ_WRITE)
	if err != OK:
		err = f.open(path, File.WRITE)
	if err != OK:
		write_failures += 1
		return
	f.seek_end()
	f.store_line(JSON.print(ev))
	f.close()

func _write_summary() -> void:
	var f = File.new()
	var p = path.get_base_dir() + "/summary.json"
	if f.open(p, File.WRITE) == OK:
		f.store_string(JSON.print(summary))
		f.close()

func _make_run_id() -> String:
	return "run_%d_%d" % [OS.get_unix_time(), randi() % 100000]

func _iso_now() -> String:
	var t = OS.get_datetime(true)
	return "%04d-%02d-%02dT%02d:%02d:%02dZ" % [t.year, t.month, t.day, t.hour, t.minute, t.second]
