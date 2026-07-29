"""Source-text pins for the non-finite JSON guard and the human input label.

The mod GDScript is never parsed by this suite, so source-text assertions are
the only guard available.

Two independent data-integrity fixes are pinned here:

1. `JSON.print()` writes INF/NAN as `1.#INF` / `-1.#IND`, which is NOT valid
   JSON, so a reader drops the WHOLE line. `_append` is the single serialization
   choke point for every telemetry line, so the sanitizer lives there and covers
   any future instrument -- these tests pin that it is applied at the choke
   point and not merely defined.
2. On a `human_movement` run `teacher.action` is the AGENT's vector. The human
   label needs the raw keyboard vector PLUS the two aliasing fields, because
   physics rate (~60 Hz) is ~3x the capture rate and a bare "latest vector"
   cannot be distinguished from an aliased one.
"""

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MOD = ROOT / "mod/mods-unpacked/Tom-BrotatoAgent"
TELEMETRY = MOD / "telemetry/telemetry_writer.gd"
CONTROLLER = MOD / "runtime/agent_controller.gd"
MOVEMENT = MOD / "extensions/entities/units/movement_behaviors/player_movement_behavior.gd"


def _func(text: str, name: str) -> str:
    return text.split("func %s" % name, 1)[1].split("\nfunc ", 1)[0]


# ── 1. non-finite guard ──────────────────────────────────────────────────────


def test_sanitizer_exists_with_the_three_declared_mappings():
    telemetry = TELEMETRY.read_text(encoding="utf-8")
    assert re.search(r"^const NONFINITE_POS := 1\.0e18$", telemetry, re.M)
    assert re.search(r"^const NONFINITE_NEG := -1\.0e18$", telemetry, re.M)
    assert re.search(r"^const NONFINITE_NAN := 0\.0$", telemetry, re.M)
    body = _func(telemetry, "_sanitize")
    # Godot 3 helpers, not a hand-rolled comparison.
    assert "is_nan(value)" in body
    assert "is_inf(value)" in body
    # Sign is PRESERVED: -INF must not collapse onto +1e18.
    assert "return NONFINITE_POS if value > 0.0 else NONFINITE_NEG" in body
    assert "return NONFINITE_NAN" in body
    # Recursive over both containers, plus Vector2 whose components print inside
    # the serialized string.
    for branch in ("TYPE_REAL:", "TYPE_DICTIONARY:", "TYPE_ARRAY:", "TYPE_VECTOR2:"):
        assert branch in body, branch
    assert "_sanitize(value[k])" in body
    assert "_sanitize(item)" in body


def test_sanitizer_is_applied_at_the_single_serialization_choke_point():
    telemetry = TELEMETRY.read_text(encoding="utf-8")
    # Both emit paths funnel through _emit_with_schema -> _append, and _append is
    # the ONLY JSON.print of a telemetry LINE. If a second one ever appears this
    # count changes and the test fails, which is the point.
    code = [
        ln for ln in telemetry.splitlines() if not ln.strip().startswith("#")
    ]
    serializations = [ln for ln in code if "JSON.print(" in ln]
    assert len(serializations) == 2, serializations  # _append + _write_summary
    # ...and BOTH of them serialize the sanitized copy, never the raw dict.
    assert all("(safe)" in ln for ln in serializations), serializations
    append = _func(telemetry, "_append")
    assert "var safe: Dictionary = _sanitize(ev)" in append
    assert "f.store_line(JSON.print(safe))" in append
    assert "JSON.print(ev)" not in append
    summary = _func(telemetry, "_write_summary")
    assert "var safe: Dictionary = _sanitize(summary)" in summary
    assert "f.store_string(JSON.print(safe))" in summary


def test_substitution_count_travels_with_the_data_and_is_never_omitted():
    telemetry = TELEMETRY.read_text(encoding="utf-8")
    append = _func(telemetry, "_append")
    # Reset per line, then attached UNCONDITIONALLY: a field present only when
    # non-zero cannot distinguish a clean line from a build with no sanitizer.
    assert "_nonfinite_fixed = 0" in append
    assert 'safe["nonfinite_fixed"] = _nonfinite_fixed' in append
    assert "if _nonfinite_fixed" not in append
    assert "nonfinite_total += _nonfinite_fixed" in append
    summary = _func(telemetry, "_write_summary")
    assert 'safe["nonfinite_total"] = nonfinite_total' in summary
    assert re.search(r"^var nonfinite_total: int = 0$", telemetry, re.M)
    # Cleared per run, or a rerun in the same process inherits a stale total.
    assert "nonfinite_total = 0" in _func(telemetry, "begin_run")


def test_sanitizer_copies_rather_than_mutating_live_state():
    # The payload dicts handed to emit() are live controller/teacher state, so an
    # in-place repair would feed a 1e18 sentinel back into the policy's inputs.
    body = _func(TELEMETRY.read_text(encoding="utf-8"), "_sanitize")
    assert "var out := {}" in body
    assert "var arr := []" in body


# ── 2. human input label ─────────────────────────────────────────────────────


def test_note_human_movement_is_called_under_a_has_method_guard():
    movement = MOVEMENT.read_text(encoding="utf-8")
    body = _func(movement, "get_movement")
    assert 'if runner.has_method("note_human_movement"):' in body
    assert "runner.note_human_movement(human)" in body
    # It must sit on the human_movement branch, above the E-stop takeover.
    assert body.index('runner.get("human_movement")') < body.index(
        "note_human_movement"
    )
    # ...and strictly before the E-stop, which would disable the agent for the run.
    assert body.index("note_human_movement") < body.index('runner.set("active", false)')


def test_human_debug_carries_the_two_aliasing_fields():
    controller = CONTROLLER.read_text(encoding="utf-8")
    assert "func note_human_movement(v: Vector2) -> void:" in controller
    assert "func human_debug() -> Dictionary:" in controller
    body = _func(controller, "human_debug")
    # Without samples + all_identical there is no way to tell "the human held one
    # direction" from "we aliased away two of three inputs".
    for key in ('"x"', '"y"', '"samples"', '"all_identical"'):
        assert key in body, key
    note = _func(controller, "note_human_movement")
    assert "_human_move_samples += 1" in note
    assert "_human_move_all_identical = false" in note
    assert "_human_move_latest = v" in note


def test_human_block_is_empty_when_the_handover_is_off():
    body = _func(CONTROLLER.read_text(encoding="utf-8"), "human_debug")
    assert "if not human_movement:" in body
    assert body.index("if not human_movement:") < body.index('"samples"')
    assert "return {}" in body


def test_human_block_attached_under_the_human_key_beside_desire_and_tail():
    controller = CONTROLLER.read_text(encoding="utf-8")
    body = _func(controller, "choose_movement")
    assert '"human": human_debug(),' in body
    assert '"desire": desire_debug,' in body
    assert '"tail": tail_debug,' in body


def test_human_counters_reset_once_per_capture_not_per_recompute():
    # choose_movement runs at physics rate (~3x the capture rate), so resetting
    # there would pin samples at 1 and destroy the aliasing check.
    controller = CONTROLLER.read_text(encoding="utf-8")
    capture = _func(controller, "_emit_wp2_combat_capture")
    assert "_human_move_samples = 0" in capture
    assert "_human_move_all_identical = true" in capture
    assert "_human_move_samples = 0" not in _func(controller, "choose_movement")


def test_capture_schema_hash_is_untouched_by_the_debug_bag():
    # teacher.contributions is free-form (schema: {"type": "object"}), so the
    # human block rides it at no schema/hash cost. Pinned so a future edit that
    # moves the block OUT of contributions fails here.
    import hashlib
    import json

    schema_path = ROOT / "configs/wp2/combat_capture_v2.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    assert schema["$defs"]["teacher"]["properties"]["contributions"] == {
        "type": "object"
    }
    digest = hashlib.sha256(schema_path.read_bytes()).hexdigest().upper()
    controller = CONTROLLER.read_text(encoding="utf-8")
    assert 'const _WP2_CAPTURE_SCHEMA_HASH := "%s"' % digest in controller
