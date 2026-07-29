"""Per-term decomposition of the desire vector: source pins.

The agent parks at ~1.0x its shortest weapon range and two dosed constants were
both measured inert, so the term that actually holds the standoff out is still
unidentified. ``_build_desire`` sums ~12 separately-computed vectors and only the
NORMALIZED total was ever observable, which cannot answer "which term pushes
outward" — magnitudes alone do not, either, hence raw (x, y) components that a
consumer projects onto arbitrary reference directions offline.

GDScript is pinned by source assertion (no headless Godot in CI, per the
v125/v126/v127 precedent). This is pure instrumentation: the pins below exist to
catch a term silently going unrecorded, a stale value being reported as a fresh
measurement, or the block drifting out of the free-form contributions bag.
"""
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FIELD = ROOT / "mod/mods-unpacked/Tom-BrotatoAgent/teacher/potential_field.gd"
CONTROLLER = ROOT / "mod/mods-unpacked/Tom-BrotatoAgent/runtime/agent_controller.gd"

# The twelve accumulated terms, in accumulation order.
TERMS = (
    "enemy_engagement",
    "early_hunt",
    "edge_kite",
    "pack_density",
    "engage_strafe",
    "inward_damp",
    "circling",
    "loot",
    "consumable",
    "tree",
    "wall",
    "center",
)

# Context scalars/booleans that make a decomposition interpretable.
CONTEXT_FIELDS = (
    "seq",
    "early_force_mult",
    "early",
    "edge_kite_branch",
    "out_of_range",
    "at_weapon_range",
    "engage",
    "weapon_max",
    "nearest_d",
    "total_x",
    "total_y",
)


def _field_source() -> str:
    return FIELD.read_text(encoding="utf-8")


def _function(source: str, name: str) -> str:
    start = source.index("func %s(" % name)
    end = source.index("\nfunc ", start + 1)
    return source[start:end]


def _build_desire() -> str:
    return _function(_field_source(), "_build_desire")


def test_every_term_is_zeroed_before_the_accumulation_runs():
    """A branch that does not run this tick must read 0, not last tick's value —
    a stale component reads as a real measurement and is exactly the failure this
    instrumentation exists to avoid."""
    reset = _function(_field_source(), "_reset_desire_debug")
    missing = [
        term for term in TERMS
        if "_t_%s_x = 0.0" % term not in reset or "_t_%s_y = 0.0" % term not in reset
    ]
    assert not missing, "terms not zeroed: %s" % missing
    # And the reset must be the first statement of _build_desire, ahead of any
    # term computation.
    body = _build_desire().splitlines()
    assert body[1].strip() == "_reset_desire_debug()"


def test_the_sequence_counter_advances_once_per_build_desire_call():
    """_build_desire is NOT called on the finale or late-survival paths, so a
    consumer needs seq to tell a fresh decomposition from a carried-over one."""
    source = _field_source()
    assert "_desire_seq += 1" in _function(source, "_reset_desire_debug")
    assert source.count("_desire_seq += 1") == 1
    assert '"seq": _desire_seq,' in _function(source, "desire_debug")


def test_every_term_is_recorded_inside_build_desire():
    body = _build_desire()
    missing = [
        term for term in TERMS
        if "_t_%s_x = " % term not in body or "_t_%s_y = " % term not in body
    ]
    assert not missing, "terms never assigned in _build_desire: %s" % missing


def test_debug_accessor_exposes_every_term_and_the_context_scalars():
    accessor = _function(_field_source(), "desire_debug")
    emitted = re.findall(r'^\t\t"(\w+)":', accessor, flags=re.MULTILINE)
    assert [t for t in TERMS if t not in emitted] == []
    assert [c for c in CONTEXT_FIELDS if c not in emitted] == []
    # Components, not magnitudes: each term is a two-element [x, y] pair.
    for term in TERMS:
        assert '"%s": [_t_%s_x, _t_%s_y],' % (term, term, term) in accessor


def test_pack_density_is_recorded_in_both_branches_after_its_multipliers():
    """It is accumulated in two mutually exclusive branches with different
    scaling; recording only one would report 0 for half the ticks."""
    body = _build_desire()
    assert "BotConfig.EDGE_PACK_SHOVE * _strength_pack_mult())" in body
    assert body.count("_t_pack_density_x = ") == 2
    assert body.count("_t_pack_density_y = ") == 2


def test_inward_damp_is_recorded_as_the_signed_vector_subtracted():
    """Recorded negated so it sums with the other terms without a sign convention."""
    body = _build_desire()
    assert "var damp = dir_in * inward * (1.0 - BotConfig.ENGAGE_STRAFE_INWARD_DAMP)" in body
    assert "_t_inward_damp_x = -damp.x" in body
    assert "_t_inward_damp_y = -damp.y" in body
    assert "force -= damp" in body


def test_instrumentation_does_not_alter_the_returned_vector():
    """Behaviour neutrality: the terms are hoisted into locals and then added in
    the same order, and the function still returns the normalized total."""
    body = _build_desire()
    assert body.rstrip().endswith("return _normalize(force)")
    # No recorded field is ever read back into the accumulation.
    for term in TERMS:
        assert "force += _t_%s" % term not in body
        assert "* _t_%s" % term not in body


def test_controller_attaches_desire_to_the_free_form_contributions_bag():
    controller = CONTROLLER.read_text(encoding="utf-8")
    assert 'if _field.has_method("desire_debug"):' in controller
    assert "desire_debug = _field.desire_debug()" in controller
    debug_bag = controller[controller.index('"debug": {'):]
    debug_bag = debug_bag[: debug_bag.index("},")]
    # Same dict as loot_dash, which is why this costs no capture-schema change.
    assert '"loot_dash": loot_dash_debug,' in debug_bag
    assert '"desire": desire_debug,' in debug_bag
