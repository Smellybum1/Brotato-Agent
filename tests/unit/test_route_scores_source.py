"""Source-text pins for the v129 route_scores telemetry instrument.

The mod GDScript is never parsed by this suite, so source-text assertions are the
only guard available. This is an INSTRUMENT, not a knob: it is a bool defaulting
false, and with the flag off the recorder returns before touching any state, so
the emitted command is byte-identical. It is the movement analogue of the shop's
purchase_decision.board_scores.
"""

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
POTENTIAL_FIELD = ROOT / "mod/mods-unpacked/Tom-BrotatoAgent/teacher/potential_field.gd"
CONTROLLER = ROOT / "mod/mods-unpacked/Tom-BrotatoAgent/runtime/agent_controller.gd"
TELEMETRY = ROOT / "mod/mods-unpacked/Tom-BrotatoAgent/telemetry/telemetry_writer.gd"


def _func(text: str, name: str) -> str:
    return text.split("func %s" % name, 1)[1].split("\nfunc ", 1)[0]


def test_declared_on_both_sides_defaulting_false():
    potential = POTENTIAL_FIELD.read_text(encoding="utf-8")
    controller = CONTROLLER.read_text(encoding="utf-8")
    for name, text in (("potential_field.gd", potential), ("agent_controller.gd", controller)):
        assert re.search(
            r"^var route_scores_enabled: bool = false$", text, re.M
        ), (
            "%s must declare route_scores_enabled as a bool defaulting false: the "
            "instrument is default-inert, and a non-false default would arm a "
            "~24-dict-per-decision array on every run of a ~110 GB archive" % name
        )


def test_controller_wiring_is_complete():
    controller = CONTROLLER.read_text(encoding="utf-8")
    assert "_field.route_scores_enabled = route_scores_enabled" in controller, (
        "without propagation to the field the flag can be armed in config and "
        "still record nothing -- a silent no-op arm"
    )
    assert controller.count('"route_scores_enabled": route_scores_enabled,') == 2, (
        "the flag must appear in exactly 2 summary dicts (mod_ready + run-summary "
        "meta) so an arm is certifiable from the run's own record; got %d"
        % controller.count('"route_scores_enabled": route_scores_enabled,')
    )
    assert 'route_scores_enabled = bool(cfg["route_scores_enabled"])' in controller, (
        "without the _load_auto_config read, agent_config.json cannot arm the "
        "instrument at all and every campaign would run with it off"
    )


def test_recorded_in_telemetry_allowlist():
    telemetry = TELEMETRY.read_text(encoding="utf-8")
    assert 'meta.get("route_scores_enabled", false)' in telemetry, (
        "that meta dict is an ALLOWLIST that silently drops unknown keys; without "
        "this line a run could not certify whether the instrument was armed, and "
        "an empty route block would be indistinguishable from a loop never run"
    )


def test_route_record_returns_before_any_append_when_disabled():
    potential = POTENTIAL_FIELD.read_text(encoding="utf-8")
    body = _func(potential, "_route_record")
    guard = body.index("if not route_scores_enabled:")
    ret = body.index("return", guard)
    append = body.index("_finale_route_scores.append(")
    assert ret < append, (
        "the early return must precede any append: it is the ONLY thing making "
        "flag-off exactly inert (no allocation, no state touched)"
    )
    # And the guard is the first statement -- nothing executes before it.
    head = body[:guard]
    for line in head.splitlines():
        stripped = line.strip()
        assert stripped == "" or stripped.startswith("#") or stripped.endswith("-> void:") \
            or stripped.endswith(",") or stripped.startswith("projectile_clearance"), (
            "unexpected executable statement before the inertness guard: %r" % line
        )


def test_route_reset_happens_on_entry_before_any_return():
    potential = POTENTIAL_FIELD.read_text(encoding="utf-8")
    body = _func(potential, "_finale_body_safety")
    reset = body.index("_reset_finale_route()")
    first_return = body.index("return baseline")
    assert reset < first_return, (
        "the clear must be on ENTRY, not in the ranking loop: this function has "
        "six return paths, and a loop-scoped clear would emit the PREVIOUS tick's "
        "candidates against this decision"
    )


def test_all_exit_tags_present():
    potential = POTENTIAL_FIELD.read_text(encoding="utf-8")
    body = _func(potential, "_finale_body_safety") + _func(potential, "_reset_finale_route")
    for tag in ("not_reached", "entered", "no_threats", "rows_empty",
                "no_body_tier", "relief_underflow", "baseline_kept", "ranked"):
        assert '"%s"' % tag in body, (
            "exit tag %r missing: without every return path naming itself, an "
            "empty scores array cannot be told apart from a path that never "
            "reached the ranking loop" % tag
        )


def test_score_arithmetic_is_unchanged():
    potential = POTENTIAL_FIELD.read_text(encoding="utf-8")
    body = _func(potential, "_finale_body_safety")
    base = body.index("var score := projectile_clearance - enemy_penalty")
    align = body.index("score += align_term", base)
    cont = body.index("score += continuity_term", align)
    assert base < align < cont, (
        "accumulation order must remain ((proj - pen) + align) + continuity; "
        "reordering float accumulation would change the emitted command and the "
        "instrumentation is supposed to be behaviour-neutral"
    )
    assert ("var align_term := BotConfig.ESCAPE_ALIGN_BONUS * candidate.dot(baseline)"
            in body), "align term must be the shipped ESCAPE_ALIGN_BONUS expression, hoisted unchanged"
    guard = body.index("if _prev_move.length() > 0.1:")
    assign = body.index("continuity_term = (BotConfig.BOSS_FINALE_ESCAPE_CONTINUITY", guard)
    assert guard < assign < cont, (
        "continuity_term must be assigned inside the _prev_move guard and before "
        "it is accumulated, or a stationary tick would gain a term it never had"
    )


def test_body_clearance_is_a_gate_never_a_preference():
    potential = POTENTIAL_FIELD.read_text(encoding="utf-8")
    body = _func(potential, "_finale_body_safety")
    for line in body.splitlines():
        if "score +=" in line or "var score :=" in line:
            assert "body_clearance" not in line, (
                "body_clearance must never enter the lane SCORE -- it is an "
                "admission gate only. That asymmetry is the premise the whole "
                "instrument exists to test; offending line: %r" % line
            )


def test_selected_lane_is_recorded_so_the_block_can_self_reconcile():
    potential = POTENTIAL_FIELD.read_text(encoding="utf-8")
    body = _func(potential, "_finale_body_safety")
    # Assigned from the SAME locals the decision used, after the ranking loop.
    assert "_finale_route_selected = best_dir" in body
    assert "_finale_route_best_score = best_score" in body
    debug = _func(potential, "finale_route_debug")
    for key in ('"sel_x"', '"sel_y"', '"best_score"'):
        assert key in debug, (
            "%s must be exposed: without the emitted lane the block proves "
            "DELIVERY (rows exist) but not CORRECTNESS (that those rows are the "
            "ones the decision was made from). With it, the max-scoring "
            "non-skipped row must BE the selected lane -- an exact check, the "
            "same reconciliation that validated board_scores" % key
        )


def test_route_scalars_are_not_gated_by_the_flag():
    potential = POTENTIAL_FIELD.read_text(encoding="utf-8")
    debug = _func(potential, "finale_route_debug")
    # Only the per-candidate array is expensive; the scalars are ~10 keys and
    # carry the admitted-lane count, which is the open question. If these ever
    # became flag-gated, a default-off build would answer nothing.
    assert "if not route_scores_enabled" not in debug, (
        "finale_route_debug must return its scalars unconditionally -- the "
        "admitted-lane count must be available with the array flag OFF"
    )
    for key in ('"exit"', '"sampled"', '"floor_admitted"', '"enabled"'):
        assert key in debug


def test_route_debug_is_wired_into_the_movement_debug_bag():
    controller = CONTROLLER.read_text(encoding="utf-8")
    assert '"route": route_debug,' in controller, (
        "the route block must ride in the choose_movement debug bag or nothing "
        "reaches teacher.contributions.route in the capture"
    )
    assert 'if _field.has_method("finale_route_debug"):' in controller, (
        "the has_method guard keeps an older field build from crashing the "
        "controller, the same pattern as tail_debug"
    )
