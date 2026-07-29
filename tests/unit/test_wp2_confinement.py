"""Unit tests for scripts.wp2_confinement.

Synthetic capture dicts only -- no game, no runs dir, no I/O.
"""
from __future__ import annotations

import importlib.util
import json
import math
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_SPEC = importlib.util.spec_from_file_location(
    "wp2_confinement", _ROOT / "scripts" / "wp2_confinement.py")
conf = importlib.util.module_from_spec(_SPEC)
sys.modules["wp2_confinement"] = conf
_SPEC.loader.exec_module(conf)


W, H = 2048.0, 1536.0


# ---------------------------------------------------------------------------
# grid / primary endpoint
# ---------------------------------------------------------------------------


def test_grid_shape_is_192_for_the_standard_arena():
    assert conf.grid_shape(W, H) == (16, 12, 192)


def test_grid_shape_is_computed_not_hardcoded():
    # a half-size arena must NOT report 192 cells
    assert conf.grid_shape(1024.0, 768.0) == (8, 6, 48)


def test_cells_50pct_on_a_known_distribution():
    """4 captures in cell A, 3 in B, 2 in C, 1 in D (n=10, need >= 5).

    Largest-first: 4 (<5), +3 = 7 (>=5) -> 2 cells.
    """
    positions = ([(10.0, 10.0)] * 4          # cell (0,0)
                 + [(200.0, 10.0)] * 3       # cell (1,0)
                 + [(330.0, 10.0)] * 2       # cell (2,0)
                 + [(460.0, 10.0)] * 1)      # cell (3,0)
    out = conf.occupancy_concentration(positions, W, H)
    assert out["n"] == 10
    assert out["cells_visited"] == 4
    assert out["cells_50pct"] == 2
    assert out["total_cells"] == 192
    assert out["cells_50pct_fraction"] == pytest.approx(2 / 192)


def test_cells_50pct_uniform_spread_needs_half_the_visited_cells():
    positions = [(64.0 + 128.0 * i, 64.0) for i in range(16)]  # 16 distinct cells
    out = conf.occupancy_concentration(positions, W, H)
    assert out["cells_visited"] == 16
    assert out["cells_50pct"] == 8


def test_cells_50pct_single_cell_is_one():
    out = conf.occupancy_concentration([(5.0, 5.0)] * 50, W, H)
    assert out["cells_50pct"] == 1
    assert out["cells_visited"] == 1


def test_cells_50pct_empty_is_none_not_zero():
    out = conf.occupancy_concentration([], W, H)
    assert out["n"] == 0
    assert out["cells_50pct"] is None
    assert out["cells_50pct_fraction"] is None


# ---------------------------------------------------------------------------
# corner baseline arithmetic
# ---------------------------------------------------------------------------


def test_corner_baseline_arithmetic_matches_4r2_over_area():
    out = conf.corner_occupancy([(1.0, 1.0)], W, H)
    for r in (300.0, 400.0, 500.0):
        assert out["radii"][r]["baseline"] == pytest.approx(4.0 * r * r / (W * H))
    # the published values
    assert out["radii"][300.0]["baseline"] == pytest.approx(0.114441, abs=1e-6)
    assert out["radii"][400.0]["baseline"] == pytest.approx(0.203451, abs=1e-6)
    assert out["radii"][500.0]["baseline"] == pytest.approx(0.317891, abs=1e-6)


def test_corner_requires_TWO_walls_and_ratio_uses_the_baseline():
    positions = [
        (100.0, 100.0),      # near left AND top -> corner at all radii
        (100.0, 768.0),      # near left only -> not a corner
        (1024.0, 768.0),     # centre -> not a corner
        (1948.0, 1436.0),    # near right AND bottom -> corner
    ]
    out = conf.corner_occupancy(positions, W, H)
    d = out["radii"][300.0]
    assert d["count"] == 2 and d["n"] == 4
    assert d["fraction"] == pytest.approx(0.5)
    assert d["ratio"] == pytest.approx(0.5 / d["baseline"])


def test_corner_empty_is_none_not_zero():
    out = conf.corner_occupancy([], W, H)
    assert out["radii"][400.0]["fraction"] is None
    assert out["radii"][400.0]["ratio"] is None


# ---------------------------------------------------------------------------
# gyration / centre-wall
# ---------------------------------------------------------------------------


def test_radius_of_gyration_on_a_square():
    pts = [(-10.0, 0.0), (10.0, 0.0), (0.0, -10.0), (0.0, 10.0)]
    out = conf.radius_of_gyration(pts)
    assert out["centroid"] == pytest.approx((0.0, 0.0))
    assert out["rg"] == pytest.approx(10.0)


def test_centre_and_wall_medians():
    out = conf.centre_and_wall([(1024.0, 1536.0 / 2)], W, H)
    assert out["median_dist_centre"] == pytest.approx(0.0)
    assert out["median_dist_wall"] == pytest.approx(768.0)


# ---------------------------------------------------------------------------
# dt filter + displacement-based approach velocity
# ---------------------------------------------------------------------------


def _cap(px, py, ex, ey, dt=16.0, wave=17):
    return {
        "wave": wave,
        "control_dt_ms": dt,
        "arena": {"width": W, "height": H},
        "player": {"x": px, "y": py},
        "entities": {"enemies": [
            {"type_id": "pursuer_1", "script_path": "res://enemies/pursuer/x.gd",
             "x": ex, "y": ey},
        ]},
        # intent deliberately points the OPPOSITE way: it must be ignored
        "teacher": {"action": {"x": -1.0, "y": 0.0}},
    }


def test_approach_velocity_sign_moving_away_is_positive():
    caps = [_cap(500.0, 500.0, 900.0, 500.0),
            _cap(480.0, 500.0, 900.0, 500.0)]   # moved -x, pursuer at +x
    out = conf.approach_velocity(caps)
    assert out["n"] == 1
    assert out["mean"] == pytest.approx(1.0)


def test_approach_velocity_sign_moving_toward_is_negative():
    caps = [_cap(500.0, 500.0, 900.0, 500.0),
            _cap(520.0, 500.0, 900.0, 500.0)]
    out = conf.approach_velocity(caps)
    assert out["n"] == 1
    assert out["mean"] == pytest.approx(-1.0)


def test_approach_velocity_ignores_teacher_action():
    """teacher.action points -x (away) on every capture; the player actually
    moves +x (toward).  The result must be negative."""
    caps = [_cap(500.0, 500.0, 900.0, 500.0),
            _cap(530.0, 500.0, 900.0, 500.0),
            _cap(560.0, 500.0, 900.0, 500.0)]
    out = conf.approach_velocity(caps)
    assert out["n"] == 2
    assert out["mean"] < 0.0


def test_approach_velocity_perpendicular_is_zero():
    caps = [_cap(500.0, 500.0, 900.0, 500.0),
            _cap(500.0, 540.0, 900.0, 500.0)]
    out = conf.approach_velocity(caps)
    assert out["mean"] == pytest.approx(0.0)


def test_approach_velocity_bearing_is_taken_at_the_PREVIOUS_capture():
    """The two bearing epochs disagree in SIGN here, so this pins the choice.

    prev: player (500,500), pursuer (550,500) -> bearing +x.  The player moves
    +x to (600,500), i.e. straight TOWARD the pursuer it observed -> -1.
    At the CURRENT capture the pursuer is behind the player (bearing -x), which
    would score the same displacement as +1.  The causal pairing is the
    previous state: the displacement is the RESPONSE to it.
    """
    caps = [_cap(500.0, 500.0, 550.0, 500.0),
            _cap(600.0, 500.0, 550.0, 500.0)]
    out = conf.approach_velocity(caps)
    assert out["n"] == 1
    assert out["mean"] == pytest.approx(-1.0)     # prev epoch
    assert out["mean"] != pytest.approx(+1.0)     # not the cur epoch
    assert out["median_dist_to_pursuer"] == pytest.approx(50.0)


def test_pursuer_predicate_matches_wp2_tail_decomposition():
    import importlib.util as _ilu
    spec = _ilu.spec_from_file_location(
        "wp2_tail_decomposition", _ROOT / "scripts" / "wp2_tail_decomposition.py")
    tail = _ilu.module_from_spec(spec)
    spec.loader.exec_module(tail)
    cases = [
        {"type_id": "pursuer_1", "script_path": "res://enemies/pursuer/a.gd"},
        {"type_id": "", "script_path": "res://.../pursuer_stats.tres"},
        {"type_id": "charger", "script_path": "res://enemies/charger/a.gd"},
        {"type_id": "pursuer_spawner", "script_path": "res://enemies/other/a.gd"},
        {"type_id": "anti_pursuer", "script_path": ""},
    ]
    for c in cases:
        assert conf.is_pursuer(c) == tail.is_pursuer(c), c
    # the two rejected-by-design cases: plain substring would have matched
    assert conf.is_pursuer(cases[3]) is False
    assert conf.is_pursuer(cases[4]) is False


def test_approach_velocity_excludes_low_control_dt_and_breaks_the_chain():
    caps = [_cap(500.0, 500.0, 900.0, 500.0),
            _cap(480.0, 500.0, 900.0, 500.0, dt=5.0),   # excluded
            _cap(460.0, 500.0, 900.0, 500.0)]
    out = conf.approach_velocity(caps)
    assert out["excluded_low_control_dt"] == 1
    # the excluded capture breaks the displacement chain: no pair survives
    assert out["n"] == 0
    assert out["mean"] is None


def test_approach_velocity_pursuer_beyond_radius_is_not_counted():
    caps = [_cap(100.0, 500.0, 1500.0, 500.0),
            _cap(120.0, 500.0, 1500.0, 500.0)]
    out = conf.approach_velocity(caps)
    assert out["no_pursuer_within_radius"] == 1
    assert out["n"] == 0


def test_non_pursuer_enemies_are_ignored():
    caps = [_cap(500.0, 500.0, 900.0, 500.0),
            _cap(480.0, 500.0, 900.0, 500.0)]
    for c in caps:
        c["entities"]["enemies"] = [
            {"type_id": "charger", "script_path": "res://enemies/charger/x.gd",
             "x": 900.0, "y": 500.0}]
    out = conf.approach_velocity(caps)
    assert out["no_pursuer_within_radius"] == 1
    assert out["n"] == 0


def test_analyze_run_dt_filter_drops_captures_from_the_primary(tmp_path):
    run = tmp_path / "run_x"
    run.mkdir()
    rows = []
    for i in range(4):
        rows.append({"event": "combat_capture",
                     "payload": _cap(10.0, 10.0, 900.0, 500.0,
                                     dt=(5.0 if i < 2 else 16.0))})
    rows.append({"event": "combat_capture",
                 "payload": _cap(10.0, 10.0, 900.0, 500.0, wave=18)})
    run.joinpath("events.jsonl").write_text(
        "\n".join(__import__("json").dumps(r) for r in rows), encoding="utf-8")
    out = conf.analyze_run(run, 17)
    assert out["captures_wave_raw"] == 4
    assert out["excluded_low_control_dt"] == 2
    assert out["captures_used"] == 2
    assert out["waves_captured"] == [17, 18]
    assert out["survived"] is True


# ---------------------------------------------------------------------------
# arm assignment
# ---------------------------------------------------------------------------


def test_arm_of():
    # AGENT runs (human_movement explicitly false) -- the dose decides.
    assert conf.arm_of(1.0, False) == "control"
    assert conf.arm_of(0.0, False) == "treatment"
    assert conf.arm_of(0.5, False) == "treatment"
    assert conf.arm_of(None, False) == "unknown"


def test_dose_one_human_run_is_not_control():
    """THE TRAP.  A human trial runs at the inert dose 1.0.

    A dose-only rule files it as `control` and it pools silently into the
    AGENT control arm -- the same failure shape as "an entry-build fingerprint
    does not identify a trial's arm".
    """
    assert conf.arm_of(1.0, True) == "human"
    assert conf.arm_of(1.0, True) != "control"
    # the dose is irrelevant once human_movement is true
    for dose in (1.0, 0.0, 0.5, 2.0, None):
        assert conf.arm_of(dose, True) == "human"


def test_absent_human_movement_is_unknown_never_agent():
    """The field only exists on newer builds; its absence is silence."""
    for dose in (1.0, 0.0, 0.5, None):
        assert conf.arm_of(dose) == "unknown"
        assert conf.arm_of(dose, None) == "unknown"


def test_human_movement_of_reads_summary(tmp_path):
    run = tmp_path / "run_x"
    run.mkdir()
    # no summary.json at all -> None -> unknown
    assert conf.human_movement_of(run) is None
    assert conf.arm_of(1.0, conf.human_movement_of(run)) == "unknown"
    (run / "summary.json").write_text(
        json.dumps({"human_movement": True}), encoding="utf-8")
    assert conf.human_movement_of(run) is True
    assert conf.arm_of(1.0, conf.human_movement_of(run)) == "human"
    (run / "summary.json").write_text(
        json.dumps({"human_movement": False}), encoding="utf-8")
    assert conf.arm_of(1.0, conf.human_movement_of(run)) == "control"
    # field absent from an otherwise-valid summary -> unknown
    (run / "summary.json").write_text(
        json.dumps({"result": "victory"}), encoding="utf-8")
    assert conf.human_movement_of(run) is None
    assert conf.arm_of(1.0, conf.human_movement_of(run)) == "unknown"


# ---------------------------------------------------------------------------
# the pre-registered rule
# ---------------------------------------------------------------------------


def _rule(ctrl, treat, cs=None, ts=None, cd=None, td=None):
    cs = [True] * len(ctrl) if cs is None else cs
    ts = [True] * len(treat) if ts is None else ts
    cd = [50.0] * len(ctrl) if cd is None else cd
    td = [50.0] * len(treat) if td is None else td
    return conf.prereg_rule(ctrl, treat, cs, ts, cd, td)


def test_prereg_rule_go():
    # sd_ctrl of [10,12,10,12,11,11] is small; treatment far above
    out = _rule([10.0, 12.0, 10.0, 12.0, 11.0, 11.0], [25.0, 27.0, 26.0, 28.0])
    assert out["verdict"] == "GO"
    assert out["primary_passed"] is True
    assert out["diff"] > 2 * out["sd_ctrl"]
    assert out["guards_tripped"] is False


def test_prereg_rule_no_go_effect_too_small():
    out = _rule([10.0, 14.0, 8.0, 16.0, 9.0, 15.0], [13.0, 12.0, 13.0, 12.0])
    assert out["verdict"] == "NO-GO"
    assert out["primary_passed"] is False
    assert out["diff"] > 0
    assert out["diff"] < 2 * out["sd_ctrl"]


def test_prereg_rule_no_go_wrong_direction():
    out = _rule([10.0, 12.0, 10.0, 12.0], [2.0, 3.0, 2.0, 3.0])
    assert out["verdict"] == "NO-GO"
    assert out["diff"] < 0
    assert out["primary_passed"] is False


def test_prereg_rule_survival_guard_overrides_a_passing_primary():
    out = _rule([10.0, 12.0, 10.0, 12.0], [25.0, 27.0, 26.0, 28.0],
                cs=[True, True, True, True],
                ts=[True, True, False, True])
    assert out["primary_passed"] is True          # primary would have passed
    assert out["guard_survival_tripped"] is True
    assert out["verdict"] == "NO-GO"
    assert "SAFETY GUARD" in out["reason"]
    assert out["ctrl_survival"] == pytest.approx(1.0)
    assert out["treat_survival"] == pytest.approx(0.75)


def test_prereg_rule_damage_guard_overrides_a_passing_primary():
    out = _rule([10.0, 12.0, 10.0, 12.0], [25.0, 27.0, 26.0, 28.0],
                cd=[40.0, 40.0, 40.0, 40.0],
                td=[70.0, 70.0, 70.0, 70.0])       # 70 > 1.5*40 = 60
    assert out["primary_passed"] is True
    assert out["guard_damage_tripped"] is True
    assert out["verdict"] == "NO-GO"
    assert out["damage_threshold_1_5x"] == pytest.approx(60.0)


def test_prereg_rule_damage_guard_not_tripped_at_exactly_1_5x():
    out = _rule([10.0, 12.0, 10.0, 12.0], [25.0, 27.0, 26.0, 28.0],
                cd=[40.0] * 4, td=[60.0] * 4)      # "more than 1.5x" -> strict
    assert out["guard_damage_tripped"] is False
    assert out["verdict"] == "GO"


def test_prereg_rule_indeterminate_without_a_control_sd():
    out = _rule([10.0], [25.0])
    assert out["sd_ctrl"] is None
    assert out["verdict"] == "INDETERMINATE"


def test_prereg_rule_reports_every_input():
    out = _rule([10.0, 12.0], [25.0, 27.0])
    for key in ("ctrl_values", "treat_values", "ctrl_mean", "treat_mean",
                "sd_ctrl", "diff", "diff_in_sd_ctrl", "ctrl_survival",
                "treat_survival", "ctrl_median_damage", "treat_median_damage",
                "damage_threshold_1_5x", "human_value"):
        assert key in out
    assert out["human_value"] == 33


# ---------------------------------------------------------------------------
# import safety
# ---------------------------------------------------------------------------


def test_module_has_main_guard():
    src = (_ROOT / "scripts" / "wp2_confinement.py").read_text(encoding="utf-8")
    assert 'if __name__ == "__main__":' in src


def test_no_body_clearance_diagnostic_is_printed():
    src = (_ROOT / "scripts" / "wp2_confinement.py").read_text(encoding="utf-8")
    for banned in ("highest_body_clearance", "body_floor_passed",
                   "lowest_enemy_penalty"):
        assert banned not in src


def test_teacher_action_is_never_read():
    src = (_ROOT / "scripts" / "wp2_confinement.py").read_text(encoding="utf-8")
    assert '"teacher", "action"' not in src
