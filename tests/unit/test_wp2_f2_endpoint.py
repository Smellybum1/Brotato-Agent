"""Unit tests for scripts/wp2_f2_endpoint.py (Stage F2 primary endpoint).

Synthetic fixtures only -- no run dirs, no live processes. Covers:
  * hierarchy ordering (victory beats any defeat; deeper defeat beats shallower;
    AUC tie-break; exact tie = 0.5);
  * win-probability arithmetic and bootstrap determinism under a fixed seed;
  * the expected-ticks / horizon estimator edge cases (no completer of a wave;
    all victories; all defeats).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import wp2_f2_endpoint as ep  # noqa: E402


# ---------------------------------------------------------------------------
# fixture helpers
# ---------------------------------------------------------------------------
def mk_run(
    run_id: str,
    *,
    victory: bool,
    last_wave: int,
    wave_ticks: dict[int, int] | None = None,
    combat_time: float = 100.0,
    hp_frac: float = 1.0,
) -> ep.RunRaw:
    """Synthetic RunRaw. auc_raw = hp_frac * combat_time (constant HP ratio)."""
    if wave_ticks is None:
        wave_ticks = {w: 100 for w in range(1, last_wave + 1)}
    return ep.RunRaw(
        run_id=run_id,
        victory=victory,
        last_wave=last_wave,
        result=("victory" if victory else "defeat"),
        wave_tick_counts=dict(wave_ticks),
        combat_time_sec=combat_time,
        auc_raw=hp_frac * combat_time,
        n_captures=sum(wave_ticks.values()),
    )


def out(run_id: str, arm: str, victory: bool, progress: float, auc: float) -> ep.Outcome:
    return ep.Outcome(
        run_id=run_id, arm=arm, victory=victory,
        combat_progress=progress, auc_norm=auc,
        final_wave=(20 if victory else int(progress) + 1),
    )


# ---------------------------------------------------------------------------
# hierarchy
# ---------------------------------------------------------------------------
def test_victory_beats_any_defeat():
    v = out("v", "P", True, ep.VICTORY_PROGRESS, 0.10)   # low AUC on purpose
    d = out("d", "T", False, 19.99, 0.99)                # deep defeat, high AUC
    assert ep.compare_runs(v, d) == 1.0
    assert ep.compare_runs(d, v) == 0.0


def test_deeper_defeat_beats_shallower():
    deep = out("deep", "P", False, 18.5, 0.10)
    shallow = out("shallow", "T", False, 12.5, 0.95)
    assert ep.compare_runs(deep, shallow) == 1.0
    assert ep.compare_runs(shallow, deep) == 0.0


def test_auc_tiebreak_on_equal_progress():
    hi = out("hi", "P", False, 15.25, 0.60)
    lo = out("lo", "T", False, 15.25, 0.55)
    assert ep.compare_runs(hi, lo) == 1.0
    assert ep.compare_runs(lo, hi) == 0.0


def test_progress_within_eps_falls_through_to_auc():
    a = out("a", "P", False, 15.0, 0.40)
    b = out("b", "T", False, 15.0 + ep.PROGRESS_TIE_EPS / 10.0, 0.50)
    # progress differs by less than the epsilon -> AUC decides, B wins.
    assert ep.compare_runs(a, b) == 0.0


def test_progress_beyond_eps_decides_before_auc():
    a = out("a", "P", False, 15.0 + 1e-6, 0.10)
    b = out("b", "T", False, 15.0, 0.90)
    assert ep.compare_runs(a, b) == 1.0


def test_exact_tie_is_half():
    a = out("a", "P", False, 15.25, 0.60)
    b = out("b", "T", False, 15.25, 0.60)
    assert ep.compare_runs(a, b) == 0.5
    v1 = out("v1", "P", True, ep.VICTORY_PROGRESS, 0.7)
    v2 = out("v2", "T", True, ep.VICTORY_PROGRESS, 0.7)
    assert ep.compare_runs(v1, v2) == 0.5


def test_victory_progress_sorts_above_every_defeat():
    # Even a defeat that completed all 20 waves' worth of progress stays below.
    assert ep.VICTORY_PROGRESS > 20.0


# ---------------------------------------------------------------------------
# win probability
# ---------------------------------------------------------------------------
def test_win_probability_all_p_win_and_all_t_win():
    p = [out("p1", "P", True, ep.VICTORY_PROGRESS, 0.5),
         out("p2", "P", True, ep.VICTORY_PROGRESS, 0.5)]
    t = [out("t1", "T", False, 10.0, 0.5), out("t2", "T", False, 12.0, 0.5)]
    assert ep.win_probability(t, p) == 1.0
    assert ep.win_probability(p, t) == 0.0


def test_win_probability_mixed_and_ties():
    p = [out("p1", "P", True, ep.VICTORY_PROGRESS, 0.5),
         out("p2", "P", False, 10.0, 0.5)]
    t = [out("t1", "T", False, 10.0, 0.5),   # exact tie with p2
         out("t2", "T", False, 15.0, 0.5)]
    # pairs: p1/t1=1, p1/t2=1, p2/t1=0.5, p2/t2=0 -> 2.5/4
    assert ep.win_probability(t, p) == pytest.approx(0.625)


def test_win_probability_empty_arm_is_nan():
    p = [out("p1", "P", True, ep.VICTORY_PROGRESS, 0.5)]
    assert np.isnan(ep.win_probability([], p))
    assert np.isnan(ep.win_probability(p, []))


# ---------------------------------------------------------------------------
# bootstrap
# ---------------------------------------------------------------------------
def _boot_fixture():
    p = [out(f"p{i}", "P", i < 2, 12.0 + i, 0.4 + 0.01 * i) for i in range(4)]
    t = [out(f"t{i}", "T", i < 1, 11.0 + i, 0.3 + 0.01 * i) for i in range(4)]
    return t, p


def test_bootstrap_is_deterministic_under_fixed_seed():
    t, p = _boot_fixture()
    a = ep.bootstrap_win_probability(t, p, seed=0, n_boot=500)
    b = ep.bootstrap_win_probability(t, p, seed=0, n_boot=500)
    assert a == b
    assert a["point"] == pytest.approx(ep.win_probability(t, p))
    assert a["lo"] <= a["point"] <= a["hi"]
    assert a["n_pairs"] == 16
    assert a["bootstrap_n"] == 500


def test_bootstrap_differs_across_seeds():
    t, p = _boot_fixture()
    a = ep.bootstrap_win_probability(t, p, seed=0, n_boot=500)
    b = ep.bootstrap_win_probability(t, p, seed=1, n_boot=500)
    assert (a["lo"], a["hi"]) != (b["lo"], b["hi"])


def test_bootstrap_degenerate_arm_gives_point_ci():
    p = [out(f"p{i}", "P", True, ep.VICTORY_PROGRESS, 0.5) for i in range(3)]
    t = [out(f"t{i}", "T", False, 10.0, 0.5) for i in range(3)]
    r = ep.bootstrap_win_probability(t, p, seed=0, n_boot=200)
    assert r["point"] == 1.0 and r["lo"] == 1.0 and r["hi"] == 1.0
    assert r["excludes_0p5"] is True
    assert r["direction"] == "P favored"


def test_bootstrap_empty_arm_returns_nulls():
    r = ep.bootstrap_win_probability([], [], seed=0, n_boot=10)
    assert r["point"] is None and r["excludes_0p5"] is None


# ---------------------------------------------------------------------------
# estimators: expected ticks per wave
# ---------------------------------------------------------------------------
def test_expected_ticks_uses_median_of_completers_only():
    # Two runs complete wave 3 with 100/200 ticks; a third dies in wave 3 with 10.
    runs = [
        mk_run("a", victory=False, last_wave=5, wave_ticks={3: 100, 5: 50}),
        mk_run("b", victory=False, last_wave=5, wave_ticks={3: 200, 5: 50}),
        mk_run("c", victory=False, last_wave=3, wave_ticks={3: 10}),
    ]
    est = ep.expected_ticks_per_wave(runs)
    assert est[3]["source"] == "median_of_completers"
    assert est[3]["expected_ticks"] == pytest.approx(150.0)
    assert est[3]["n_completers"] == 2
    assert est[3]["n_observers"] == 3


def test_expected_ticks_falls_back_to_max_when_no_completer():
    runs = [
        mk_run("a", victory=False, last_wave=7, wave_ticks={7: 300}),
        mk_run("b", victory=False, last_wave=7, wave_ticks={7: 450}),
    ]
    est = ep.expected_ticks_per_wave(runs)
    assert est[7]["source"] == "max_observed_no_completer"
    assert est[7]["expected_ticks"] == pytest.approx(450.0)
    assert est[7]["n_completers"] == 0


def test_no_completer_fallback_keeps_fraction_at_or_below_one():
    runs = [
        mk_run("a", victory=False, last_wave=7, wave_ticks={7: 300}),
        mk_run("b", victory=False, last_wave=7, wave_ticks={7: 450}),
    ]
    outs, _ = ep.build_outcomes(runs, {"a": "T", "b": "P"})
    by_id = {o.run_id: o for o in outs}
    assert by_id["b"].death_wave_fraction == pytest.approx(1.0)
    assert by_id["b"].combat_progress == pytest.approx(7.0)
    assert by_id["a"].death_wave_fraction == pytest.approx(300.0 / 450.0)
    assert all(o.death_wave_fraction <= 1.0 for o in outs)


def test_victory_completes_its_last_wave_defeat_does_not():
    v = mk_run("v", victory=True, last_wave=20)
    d = mk_run("d", victory=False, last_wave=20)
    assert v.completed_wave(20) is True
    assert d.completed_wave(20) is False
    assert d.completed_wave(19) is True


# ---------------------------------------------------------------------------
# estimators: horizon / reference duration
# ---------------------------------------------------------------------------
def test_reference_duration_all_victories_uses_victory_median():
    runs = [
        mk_run("v1", victory=True, last_wave=20, combat_time=1000.0),
        mk_run("v2", victory=True, last_wave=20, combat_time=1200.0),
        mk_run("v3", victory=True, last_wave=20, combat_time=1400.0),
    ]
    ref = ep.reference_full_duration(runs)
    assert ref["source"] == "median_victory_duration"
    assert ref["seconds"] == pytest.approx(1200.0)
    assert ref["n_victories"] == 3
    outs, est = ep.build_outcomes(runs, {r.run_id: "T" for r in runs})
    # All victories: horizon = own combat time, no remainder; progress = 21.
    for o in outs:
        assert o.horizon_sec == pytest.approx(o.combat_time_sec)
        assert o.combat_progress == ep.VICTORY_PROGRESS
        assert o.auc_norm == pytest.approx(1.0)
    assert est["reference_full_duration"]["source"] == "median_victory_duration"


def test_reference_duration_all_defeats_falls_back_to_longest():
    runs = [
        mk_run("d1", victory=False, last_wave=10, combat_time=400.0),
        mk_run("d2", victory=False, last_wave=15, combat_time=700.0),
    ]
    ref = ep.reference_full_duration(runs)
    assert ref["source"] == "fallback_longest_observed"
    assert ref["seconds"] == pytest.approx(700.0)
    assert ref["n_victories"] == 0
    outs, _ = ep.build_outcomes(runs, {r.run_id: "T" for r in runs})
    by_id = {o.run_id: o for o in outs}
    # The longest defeat is its own reference -> horizon == its combat time.
    assert by_id["d2"].horizon_sec == pytest.approx(700.0)
    # The short run is normalized by the full reference horizon.
    assert by_id["d1"].horizon_sec == pytest.approx(700.0)
    assert by_id["d1"].auc_norm == pytest.approx(400.0 / 700.0)


def test_dead_run_auc_is_penalized_by_post_death_remainder():
    runs = [
        mk_run("v", victory=True, last_wave=20, combat_time=1000.0, hp_frac=0.5),
        mk_run("d", victory=False, last_wave=10, combat_time=500.0, hp_frac=1.0),
    ]
    outs, _ = ep.build_outcomes(runs, {"v": "T", "d": "P"})
    by_id = {o.run_id: o for o in outs}
    # Dead run was at FULL hp the whole time but only played half the horizon.
    assert by_id["d"].horizon_sec == pytest.approx(1000.0)
    assert by_id["d"].auc_norm == pytest.approx(0.5)
    assert by_id["v"].auc_norm == pytest.approx(0.5)


def test_zero_horizon_run_gets_zero_auc():
    runs = [mk_run("empty", victory=False, last_wave=1, wave_ticks={1: 0},
                   combat_time=0.0, hp_frac=0.0)]
    outs, _ = ep.build_outcomes(runs, {"empty": "T"})
    assert outs[0].auc_norm == 0.0


# ---------------------------------------------------------------------------
# dt / capture-stream helpers
# ---------------------------------------------------------------------------
def test_capture_dts_clamps_interludes_and_backfills_median():
    ts = np.asarray([0.0, 10.0, 20.0, 50_000.0, 50_010.0], dtype=np.float64)
    dts = ep.capture_dts(ts)
    assert dts.shape[0] == 5
    # gaps: 10, 10, 49980 (clamped -> median 10), 10; last capture -> median 10
    assert dts.tolist() == pytest.approx([10.0, 10.0, 10.0, 10.0, 10.0])


def test_capture_dts_edge_cases():
    assert ep.capture_dts(np.zeros(0)).shape[0] == 0
    assert ep.capture_dts(np.asarray([5.0])).tolist() == [0.0]


# ---------------------------------------------------------------------------
# end-to-end analyze()
# ---------------------------------------------------------------------------
def test_analyze_end_to_end_and_markdown():
    t_runs = [
        mk_run("t1", victory=False, last_wave=13, combat_time=600.0, hp_frac=0.8),
        mk_run("t2", victory=False, last_wave=15, combat_time=700.0, hp_frac=0.8),
    ]
    p_runs = [
        mk_run("p1", victory=True, last_wave=20, combat_time=1100.0, hp_frac=0.9),
        mk_run("p2", victory=False, last_wave=17, combat_time=900.0, hp_frac=0.8),
    ]
    rep = ep.analyze(t_runs, p_runs, seed=0, n_boot=200, validation_only=True)
    assert rep["primary"]["win_probability"]["point"] == pytest.approx(1.0)
    assert rep["secondaries"]["P"]["victory_rate"] == pytest.approx(0.5)
    assert rep["secondaries"]["T"]["victory_rate"] == pytest.approx(0.0)
    assert "VALIDATION_ONLY" in rep
    assert rep["labels"]["T"] == ep.T_LABEL and rep["labels"]["P"] == ep.P_LABEL
    md = ep.render_markdown(rep)
    assert "TOOL VALIDATION ONLY" in md
    assert "P(P outranks T)" in md
    assert all(r["run_id"] in md for r in rep["runs"])


def test_analyze_estimators_are_arm_blind():
    """Swapping arm membership must not change any run's outcome tuple."""
    runs_a = [mk_run("a", victory=False, last_wave=13, combat_time=600.0),
              mk_run("b", victory=True, last_wave=20, combat_time=1100.0)]
    runs_b = [mk_run("a", victory=False, last_wave=13, combat_time=600.0),
              mk_run("b", victory=True, last_wave=20, combat_time=1100.0)]
    r1 = ep.analyze([runs_a[0]], [runs_a[1]], seed=0, n_boot=50)
    r2 = ep.analyze([runs_b[1]], [runs_b[0]], seed=0, n_boot=50)
    tup = lambda rep: {r["run_id"]: (r["combat_progress"], r["auc_norm"])
                       for r in rep["runs"]}
    assert tup(r1) == tup(r2)
