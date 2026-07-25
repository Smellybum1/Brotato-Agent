"""v127 loot-dash observability: source pins + consumer arithmetic.

The v118 loot dash is the sanctioned pile-clearing mechanism, but the only signal
it ever emitted was ``loot_dash_active`` (nested inside ``finale_translation``).
Uptime was therefore measurable, yet the question that decides the fix was not:
a dash that fires and fails to clear the pile is a CAPACITY problem, while one the
cooldown / HP floor / MAX_TICKS bounds keep from arming is a TUNING problem, and
the two imply opposite changes. See reports/wp2/late_wave_collection_mechanism.md.

v127 adds a compact ``loot_dash`` block to the teacher debug bag, which reaches the
20 Hz capture (``teacher.contributions.loot_dash``) and the 0.5 s ``combat_tick``
(``debug.loot_dash``) through existing plumbing.

GDScript is pinned by source assertion (no headless Godot in CI, per the v125/v126
precedent); the arithmetic a consumer runs over the fields is exercised in Python.
"""
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FIELD = ROOT / "mod/mods-unpacked/Tom-BrotatoAgent/teacher/potential_field.gd"
CONTROLLER = ROOT / "mod/mods-unpacked/Tom-BrotatoAgent/runtime/agent_controller.gd"

# The seven scalars of the per-tick block. Deliberately flat and small: it is built
# once per movement decision (60 Hz), so anything nested or string-heavy here is
# paid 60 times a second for the whole run.
EXPECTED_FIELDS = ("active", "state", "seq", "ticks", "cooldown", "scan", "pile")

# Every documented outcome code, and the exit each one belongs to.
EXPECTED_STATES = {
    "idle",
    "active",
    "armed",
    "aborted_ticks",
    "aborted_pile_gone",
    "aborted_arrived",
    "aborted_hp",
    "suppressed_survival",
    "suppressed_finale",
    "not_armed_cooldown",
    "not_armed_hp_floor",
    "not_armed_no_stall",
    "not_armed_no_pile",
    "not_armed_degenerate",
    "not_armed_window_clearance",
    "not_armed_projectile_context",
}

# Codes that advance _loot_dash_seq, i.e. real state transitions rather than the
# per-tick "here is why I did not arm" reading.
EDGE_STATES = {
    "armed",
    "aborted_ticks",
    "aborted_pile_gone",
    "aborted_arrived",
    "aborted_hp",
}


def _field_source() -> str:
    return FIELD.read_text(encoding="utf-8")


def _dash_function() -> str:
    source = _field_source()
    start = source.index("func _apply_loot_dash(")
    end = source.index("\nfunc ", start + 1)
    return source[start:end]


# ────────────────────────────── emission plumbing ───────────────────────────────

def test_debug_block_exposes_exactly_the_seven_documented_scalars():
    source = _field_source()
    block = source[source.index("func loot_dash_debug()"):]
    block = block[: block.index("\n\n\n")] if "\n\n\n" in block else block
    emitted = re.findall(r'^\t\t"(\w+)":', block, flags=re.MULTILINE)
    assert emitted == list(EXPECTED_FIELDS)


def test_controller_emits_loot_dash_into_the_shared_debug_bag():
    controller = CONTROLLER.read_text(encoding="utf-8")
    assert 'if _field.has_method("loot_dash_debug"):' in controller
    assert "loot_dash_debug = _field.loot_dash_debug()" in controller
    assert '"loot_dash": loot_dash_debug,' in controller
    # It must ride the same dict as finale_translation so both the 20 Hz capture
    # (teacher.contributions) and the 0.5 s combat_tick pick it up unchanged.
    debug_bag = controller[controller.index('"debug": {'):]
    debug_bag = debug_bag[: debug_bag.index("},")]
    assert '"finale_translation": translation_debug,' in debug_bag
    assert '"loot_dash": loot_dash_debug,' in debug_bag


def test_legacy_loot_dash_active_flag_is_retained_for_pre_v127_analysis():
    """finale_translation.loot_dash_active is what existing uptime analysis reads."""
    assert '"loot_dash_active": _loot_dash_active,' in _field_source()


# ─────────────────────────── exit-coverage completeness ─────────────────────────

def test_every_exit_of_the_dash_decision_records_a_state():
    """No silent exit: a `return` with no preceding state write would leave the
    block reporting the PREVIOUS tick's reason, which reads as a real measurement
    and is the exact failure this telemetry exists to prevent."""
    lines = _dash_function().splitlines()
    unrecorded = []
    for index, line in enumerate(lines):
        if not re.match(r"\s*return (desire|direction|_normalize)", line):
            continue
        for previous in reversed(lines[:index]):
            if "_loot_dash_state" in previous or "_note_loot_dash_edge(" in previous:
                break
            if re.match(r"\s*return ", previous):
                unrecorded.append(line.strip())
                break
    assert not unrecorded, f"exits with no state recorded: {unrecorded}"


def test_state_codes_in_source_match_the_documented_list_exactly():
    source = _field_source()
    declared = set(re.findall(r'^\t"(\w+)",', source, flags=re.MULTILINE))
    assert declared == EXPECTED_STATES, "LOOT_DASH_STATES drifted from the pin"

    # Every declared code must also occur in executable source, so the list cannot
    # accumulate codes nothing emits. Compare against the file with the declaration
    # block removed, since assignments take several syntactic forms (direct, helper
    # call, and the parenthesised cooldown/HP-floor ternary).
    executable = source.replace(
        source[source.index("const LOOT_DASH_STATES"):source.index("var _loot_dash_state")], ""
    )
    # "idle" is the initial value and must never be assigned at an exit.
    assert 'var _loot_dash_state := "idle"' in executable
    executable = executable.replace('var _loot_dash_state := "idle"', "")
    assigned = {code for code in EXPECTED_STATES if f'"{code}"' in executable}
    assert assigned == EXPECTED_STATES - {"idle"}, "a declared code is never emitted"


def test_only_real_transitions_advance_the_sequence_counter():
    source = _field_source()
    for state in EDGE_STATES:
        assert f'_note_loot_dash_edge("{state}")' in source
    # Per-tick blocking reasons must NOT advance seq, or every not-armed tick would
    # register as a transition and the edge count would be meaningless.
    for state in ("not_armed_cooldown", "not_armed_no_pile", "active"):
        assert f'_note_loot_dash_edge("{state}")' not in source
    assert source.count("_loot_dash_seq += 1") == 2  # edge helper + suppression drop


def test_suppression_branches_are_instrumented_rather_than_bare_assignments():
    """Late-survival and finale return before _apply_loot_dash runs; without this
    the block would keep reporting the last pre-suppression tick indefinitely."""
    source = _field_source()
    assert '_suppress_loot_dash("suppressed_survival")' in source
    assert '_suppress_loot_dash("suppressed_finale")' in source
    # The bare drops those two calls replaced must be gone, so no path can clear
    # the dash without recording that it did. Scoped to compute_movement's own body
    # — _suppress_loot_dash and the abort path clear the flag legitimately.
    body = source[source.index("func compute_movement"):]
    body = body[: body.index("\nfunc ")]
    assert "_loot_dash_active = false" not in body
    assert body.count("_suppress_loot_dash(") == 2


def test_scan_and_pile_are_sentinel_marked_when_the_check_short_circuits():
    """The arming check computes scan_count and the cluster lazily; reporting a
    stale or zero value where nothing was computed would fabricate measurements."""
    dash = _dash_function()
    assert "_loot_dash_scan_count = scan_count" in dash
    assert "_loot_dash_pile = int(cluster[1])" in dash
    assert "_loot_dash_pile = int(reacquired[1])" in dash
    # Cooldown / HP-floor exit happens before either is computed.
    cooldown_exit = dash[dash.index('"not_armed_cooldown"'):]
    cooldown_exit = cooldown_exit[: cooldown_exit.index("return desire")]
    assert "_loot_dash_scan_count = -1" in cooldown_exit
    assert "_loot_dash_pile = -1" in cooldown_exit


def test_instrumentation_does_not_touch_behavioural_dash_state():
    """v127 must be a pure telemetry change: any behaviour delta in the smoke is a
    real regression, not an instrumentation artefact."""
    dash = _dash_function()
    writes = re.findall(r"(_loot_dash_(?:active|target|ticks|cooldown)) (?:=|-=|\+=)", dash)
    assert sorted(writes) == [
        "_loot_dash_active",   # cleared on abort
        "_loot_dash_active",   # set on arm
        "_loot_dash_cooldown", # decremented each tick
        "_loot_dash_cooldown", # reset on abort
        "_loot_dash_target",   # reacquired while active
        "_loot_dash_target",   # set on arm
        "_loot_dash_ticks",    # decremented while active
        "_loot_dash_ticks",    # set on arm
    ]


# ────────────────────────────── consumer arithmetic ─────────────────────────────

def _tick(state: str, seq: int, **kwargs) -> dict:
    block = {
        "active": state in ("active", "armed"),
        "state": state,
        "seq": seq,
        "ticks": kwargs.get("ticks", 0),
        "cooldown": kwargs.get("cooldown", 0),
        "scan": kwargs.get("scan", -1),
        "pile": kwargs.get("pile", -1),
    }
    return {
        "player": {"materials": kwargs.get("materials", 0)},
        "teacher": {"contributions": {"loot_dash": block}},
    }


def loot_dash_of(capture: dict) -> dict:
    return capture["teacher"]["contributions"]["loot_dash"]


def uptime(captures: list[dict]) -> float:
    return sum(loot_dash_of(c)["active"] for c in captures) / max(len(captures), 1)


def blocking_histogram(captures: list[dict]) -> dict[str, int]:
    """Why the dash was NOT running, per tick — the suppression measurement."""
    histogram: dict[str, int] = {}
    for capture in captures:
        state = loot_dash_of(capture)["state"]
        if state.startswith("not_armed_") or state.startswith("suppressed_"):
            histogram[state] = histogram.get(state, 0) + 1
    return histogram


def episodes(captures: list[dict]) -> list[dict]:
    """Segment into dash episodes on the seq edges, with the material each yielded.

    Yield is a downstream difference over player.materials rather than an in-mod
    counter: v127 emits the spendable counter on every capture, so the gain across
    a dash window is exact and costs the 60 Hz path nothing.
    """
    out, start = [], None
    for capture in captures:
        block = loot_dash_of(capture)
        if block["state"] == "armed":
            start = capture
        elif block["state"].startswith("aborted_") and start is not None:
            out.append({
                "outcome": block["state"],
                "yield": capture["player"]["materials"] - start["player"]["materials"],
                "pile_at_arm": loot_dash_of(start)["pile"],
                "pile_at_end": block["pile"],
            })
            start = None
    return out


def test_uptime_and_blocking_histogram_separate_the_two_diagnoses():
    captures = [
        _tick("not_armed_cooldown", 4, cooldown=30),
        _tick("not_armed_cooldown", 4, cooldown=29),
        _tick("not_armed_no_pile", 4, scan=3, pile=2),
        _tick("armed", 5, scan=9, pile=7),
        _tick("active", 5, ticks=20, pile=7),
    ]
    assert uptime(captures) == 0.4
    assert blocking_histogram(captures) == {
        "not_armed_cooldown": 2,
        "not_armed_no_pile": 1,
    }


def test_episode_yield_distinguishes_a_cleared_pile_from_a_failed_dash():
    cleared = [
        _tick("armed", 1, pile=8, materials=100),
        _tick("active", 1, ticks=20, pile=8, materials=104),
        _tick("aborted_pile_gone", 2, pile=0, materials=108),
    ]
    assert episodes(cleared) == [
        {"outcome": "aborted_pile_gone", "yield": 8, "pile_at_arm": 8, "pile_at_end": 0}
    ]

    # Same arming pile, ticks exhausted, pile barely dented — the capacity failure.
    failed = [
        _tick("armed", 3, pile=8, materials=200),
        _tick("active", 3, ticks=1, pile=7, materials=201),
        _tick("aborted_ticks", 4, pile=7, materials=201),
    ]
    assert episodes(failed) == [
        {"outcome": "aborted_ticks", "yield": 1, "pile_at_arm": 8, "pile_at_end": 7}
    ]


def test_sequence_counter_recovers_transitions_without_per_tick_reason_parsing():
    captures = [
        _tick("not_armed_no_pile", 0),
        _tick("armed", 1),
        _tick("active", 1),
        _tick("active", 1),
        _tick("aborted_arrived", 2),
        _tick("not_armed_cooldown", 2),
    ]
    edges = [
        c for previous, c in zip(captures, captures[1:])
        if loot_dash_of(c)["seq"] != loot_dash_of(previous)["seq"]
    ]
    assert [loot_dash_of(c)["state"] for c in edges] == ["armed", "aborted_arrived"]


def test_sentinels_are_excluded_from_pile_statistics():
    """-1 means 'the check never got that far', not 'a pile of size -1'."""
    captures = [
        _tick("not_armed_cooldown", 0),          # pile not computed
        _tick("not_armed_no_pile", 0, pile=2),
        _tick("armed", 1, pile=9),
    ]
    piles = [loot_dash_of(c)["pile"] for c in captures if loot_dash_of(c)["pile"] >= 0]
    assert piles == [2, 9]
