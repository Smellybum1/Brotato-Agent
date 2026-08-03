extends Reference
# Append-only JSONL telemetry writer. Failures never crash the controller.

const SCHEMA_VERSION := "1.0.0"
const POLICY_VERSION := "teacher_v1-0.1.129-gun-wp1"

var run_id: String = ""
var seq: int = 0
var path: String = ""
var enabled: bool = true
var write_failures: int = 0
var started_at_ms: int = 0
var summary: Dictionary = {}
var _last_phase: String = ""

# ── non-finite JSON guard ────────────────────────────────────────────────────
# Godot's JSON.print() writes INF/NAN as the literals `1.#INF` / `-1.#IND`,
# which are NOT valid JSON: every downstream reader raises on the line and
# silently drops the WHOLE capture. Measured at 8-18% of wave-17 captures on
# mods 0.2.53/0.2.54/0.2.55, whose desire instrument publishes `nearest_d` =
# INF whenever no threat is in range.
#
# _append() is the ONLY place a telemetry line is serialized (emit and
# emit_versioned both funnel through _emit_with_schema -> _append), so
# sanitizing here fixes the CLASS of bug: no future instrument can reintroduce
# it by publishing a raw INF.
#
# The mapping preserves sign and is unambiguous -- no real quantity in this
# telemetry approaches 1e18, so a consumer can recognise a substituted value.
const NONFINITE_POS := 1.0e18
const NONFINITE_NEG := -1.0e18
const NONFINITE_NAN := 0.0

# Cumulative over the run; per-line count rides each line as `nonfinite_fixed`.
# A SILENT repair is barely better than a silent drop, so the count travels
# with the data rather than being inferred from the 1e18 sentinel.
var nonfinite_total: int = 0
var _nonfinite_fixed: int = 0

# Cursor for deriving `materials_spent` from the gold_before series. Per-wave,
# because gold rising between shops is wave income rather than a refund.
var _spend_cursor: int = -1
var _spend_wave: int = -1

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
	nonfinite_total = 0
	_spend_cursor = -1
	_spend_wave = -1
	summary = {
		"run_id": run_id,
		"schema_version": SCHEMA_VERSION,
		"policy_version": POLICY_VERSION,
		"start_timestamp": _iso_now(),
		"character": meta.get("character", ""),
		"weapon": meta.get("weapon", ""),
		# OBSERVED danger, read from the game by the caller. Default -1, never 0:
		# a 0 meaning "unknown" is indistinguishable from a genuine Danger 0 run.
		"danger": meta.get("danger", -1),
		# What was ASKED for, so a mismatch is visible in the summary alone. This
		# dict is an allowlist -- a key absent here is silently dropped.
		"requested_danger": meta.get("requested_danger", -1),
		# Requested character. Default "" (not a real character id) so a run
		# recorded before this field existed cannot read as a matching arm.
		"requested_character": meta.get("requested_character", ""),
		# Era stamp for the shop pool. Empty dict (not zeros) when absent, so a run
		# from before this field existed cannot be read as "an empty pool".
		"unlock_pool": meta.get("unlock_pool", {}),
		"endless": meta.get("endless", false),
		"wave_retry": meta.get("wave_retry", false),
		"game_version": meta.get("game_version", ""),
		"mod_version": meta.get("mod_version", "0.2.78-wp2-capture"),
		"config_id": meta.get("config_id", "well_rounded_d0_smg"),
		# Which finale controller actually ran. policy_version cannot carry this:
		# the flag lives in agent_config.json, so a v2 run and a v1 run of the
		# same build are otherwise indistinguishable in the record -- and
		# deploy_mod.py rewrites agent_config.json wholesale, so a dropped flag
		# would silently turn a v2 arm back into v1.
		"finale_v2": meta.get("finale_v2", false),
		# Rate-only finale arm (v1 policy, 60 Hz recompute). Same reasoning.
		"finale_rate_full": meta.get("finale_rate_full", false),
		# Wave-20 dev flags. Same reasoning: they live in agent_config.json only.
		"finale_no_panic": meta.get("finale_no_panic", false),
		"finale_heal_seek": meta.get("finale_heal_seek", false),
		"finale_range_keep": meta.get("finale_range_keep", false),
		"finale_projectile_priority": meta.get("finale_projectile_priority", false),
		# Boss-mounted projectile collection. This one CHANGES WHAT THE POLICY
		# SEES, so a trial whose recorded arm disagrees with the requested arm
		# must be invalidated -- which requires the arm to be in the summary.
		"finale_pivot_projectiles": meta.get("finale_pivot_projectiles", false),
		# Co-rotation with the projectile ring. Also behaviour-changing, so the
		# arm must be recorded for a trial to be validatable.
		"finale_co_rotate": meta.get("finale_co_rotate", false),
		# Ring-radius targeting. Behaviour-changing, so same reasoning again.
		"finale_ring_radius": meta.get("finale_ring_radius", false),
		# Engagement standoff dose (float, 1.0 = inert). This dict is an
		# ALLOWLIST: without this line the value never reaches telemetry and
		# arm validation would silently pass on every trial.
		"engage_distance_scale": meta.get("engage_distance_scale", 1.0),
		# Body-clearance dose (float, 1.0 = inert). Must be forwarded here or
		# arm validation cannot see the dial and would pass on every trial.
		"body_clearance_scale": meta.get("body_clearance_scale", 1.0),
		# Route-telemetry instrument (bool, false = off). Same ALLOWLIST
		# reasoning: without this line a run cannot certify from its own summary
		# whether the instrument was armed, and an empty `route` block would be
		# indistinguishable from a ranking loop that never ran.
		"route_scores_enabled": meta.get("route_scores_enabled", false),
		# Calm-enemy threat weight dose (float, 1.0 = inert). Same ALLOWLIST
		# reasoning as above: omit the line and arm validation passes blind.
		"calm_threat_mult": meta.get("calm_threat_mult", 1.0),
		# Safety-tail calm-enemy doses (floats, 1.0 = inert). Same ALLOWLIST
		# reasoning again: omit the line and arm validation passes blind.
		"tail_calm_penalty_mult": meta.get("tail_calm_penalty_mult", 1.0),
		"tail_calm_clearance_mult": meta.get("tail_calm_clearance_mult", 1.0),
		# Rare-gun lock persistence arm (bool, false = the shipped one-visit
		# lifetime). Same ALLOWLIST reasoning: omit the line and the arm never
		# reaches the summary, so a shop-behaviour change would be invisible in
		# the archive and arm validation would pass blind on every trial.
		"rare_gun_lock_persist": meta.get("rare_gun_lock_persist", false),
		# Movement handed to a human at the keyboard while the agent keeps shop
		# and level-up control. This is the most behaviour-changing arm there is
		# -- the movement policy is not running at all -- so a trial MUST record
		# it or an agent trial and a takeover trial are indistinguishable in the
		# archive. Same failure mode as the fixture-vs-full-run contamination
		# that corrupted the headline win rate for weeks.
		"human_movement": meta.get("human_movement", false),
		# Whether the movement E-stop was gated OFF for this run. An unattended
		# campaign run and an interactive one are otherwise indistinguishable in
		# the archive, and this changes what a `manual_override` absence MEANS.
		# Defaults TRUE = the unchanged safety behaviour, so a run recorded before
		# this field existed reads correctly rather than looking gated.
		"movement_estop_enabled": meta.get("movement_estop_enabled", true),
		# Direct proof of the rate that actually ran: the ratio is 1.0 for a
		# full-rate arm and ~0.333 for the v1 1-in-3 schedule. Overwritten by
		# end_run's extra dict; zeros here mean the run never reached wave 20.
		"finale_combat_ticks": 0,
		"finale_recompute_ticks": 0,
		# Range-keeping instrument; overwritten by end_run's extra dict. Seeded
		# here because this dict is an allowlist and would otherwise drop them.
		"finale_boss_ticks": 0,
		"finale_boss_in_short_range_ticks": 0,
		"finale_boss_in_long_range_ticks": 0,
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
			# The action type is NESTED under `action`, not top-level. Reading
			# payload["type"] returned "" on every event, so `rerolls` and `locks`
			# were 0 in EVERY summary ever written while the event stream plainly
			# showed shop_reroll and shop_lock actions. Three analysis scripts
			# consume these fields and were reading vacuous zeros.
			var action: Dictionary = payload.get("action", {})
			var atype := str(action.get("type", payload.get("type", "")))
			if atype == "shop_reroll":
				summary["rerolls"] = int(summary.get("rerolls", 0)) + 1
			if atype == "shop_lock":
				summary["locks"] = int(summary.get("locks", 0)) + 1
			# `materials_spent` was initialised to 0 and NEVER accumulated
			# anywhere -- a field that could not report what it claimed.
			#
			# Derived from the recorded `gold_before` series rather than from item
			# prices, because the buy path presses a UI button and does not carry a
			# price. Within one shop visit gold only falls (buys, rerolls) or rises
			# (sells), so summing the falls is the materials OUTFLOW.
			#
			# SEMANTICS, stated because they are not obvious:
			#  * includes REROLL spend as well as purchases -- it is materials out,
			#    not items bought;
			#  * excludes sells (gold rises; the cursor follows without accruing);
			#  * resets across waves, since gold rising between shops is wave
			#    income, not a refund.
			var wave := int(payload.get("wave", -1))
			var gold := int(payload.get("gold_before", -1))
			if gold >= 0:
				if wave == _spend_wave and gold < _spend_cursor:
					summary["materials_spent"] = (
						int(summary.get("materials_spent", 0)) + (_spend_cursor - gold))
				if wave != _spend_wave:
					_spend_wave = wave
				_spend_cursor = gold
		"level_up_decision":
			summary["level_ups"].append(payload)
		"crate_decision":
			summary["crates"].append(payload)
		"player_damage":
			summary["damage_taken"] = float(summary.get("damage_taken", 0)) + float(payload.get("amount", 0))
		"phase_transition":
			if payload.has("wave"):
				summary["last_wave"] = int(payload.get("wave", summary.get("last_wave", 0)))

func _sanitize(value):
	# Returns a COPY with every non-finite float replaced, counting the
	# substitutions in _nonfinite_fixed. Never mutates the argument: payloads are
	# live controller/teacher state here, not copies, so an in-place repair would
	# feed a 1e18 sentinel back into the policy's own inputs.
	match typeof(value):
		TYPE_REAL:
			if is_nan(value):
				_nonfinite_fixed += 1
				return NONFINITE_NAN
			if is_inf(value):
				_nonfinite_fixed += 1
				return NONFINITE_POS if value > 0.0 else NONFINITE_NEG
			return value
		TYPE_DICTIONARY:
			var out := {}
			for k in value.keys():
				out[k] = _sanitize(value[k])
			return out
		TYPE_ARRAY:
			var arr := []
			for item in value:
				arr.append(_sanitize(item))
			return arr
		TYPE_VECTOR2:
			# JSON.print writes a Vector2 as a string, but a non-finite component
			# still prints as 1.#INF inside that string and breaks the line.
			return Vector2(float(_sanitize(value.x)), float(_sanitize(value.y)))
	return value

func _append(ev: Dictionary) -> void:
	_nonfinite_fixed = 0
	var safe: Dictionary = _sanitize(ev)
	# Emitted ALWAYS, including 0. A field that appeared only when non-zero could
	# not distinguish "the sanitizer ran and found nothing" from "this build has
	# no sanitizer at all", which is the readback this instrument exists for.
	safe["nonfinite_fixed"] = _nonfinite_fixed
	nonfinite_total += _nonfinite_fixed
	var f = File.new()
	var err = f.open(path, File.READ_WRITE)
	if err != OK:
		err = f.open(path, File.WRITE)
	if err != OK:
		write_failures += 1
		return
	f.seek_end()
	f.store_line(JSON.print(safe))
	f.close()

func _write_summary() -> void:
	var f = File.new()
	var p = path.get_base_dir() + "/summary.json"
	_nonfinite_fixed = 0
	var safe: Dictionary = _sanitize(summary)
	safe["nonfinite_fixed"] = _nonfinite_fixed
	safe["nonfinite_total"] = nonfinite_total
	if f.open(p, File.WRITE) == OK:
		f.store_string(JSON.print(safe))
		f.close()

func _make_run_id() -> String:
	return "run_%d_%d" % [OS.get_unix_time(), randi() % 100000]

func _iso_now() -> String:
	var t = OS.get_datetime(true)
	return "%04d-%02d-%02dT%02d:%02d:%02dZ" % [t.year, t.month, t.day, t.hour, t.minute, t.second]
