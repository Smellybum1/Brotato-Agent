"""Frozen-run regression pin for the wp2_telemetry_stats per-wave path.

Whenever ``strength_tiers`` computes over a run's S series, the same S values
(and the capture-derived occupancy) MUST also be surfaced per wave: every wave
that has ticks/captures must report a populated ``S`` (n > 0, median not None)
and a populated ``occupancy`` (captures > 0, corner_frac / edge_frac not None).

Motivation: on 2026-07-24 a stewardship session reported that per_wave ``S`` and
``occupancy`` came back ``None`` for the v125 smoke run while ``strength_tiers``
computed fine. That did not reproduce against the frozen run (the script is
correct). This test pins the correct, measured behavior against the real frozen
run so any future capture-payload key/shape drift that silently drops the
per-wave extraction path is caught, rather than re-litigated by inspection.

The run is read read-only. If the frozen runs directory is absent (machines
without the archived runs), the module skips so the suite stays green.
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))
import wp2_telemetry_stats as ts  # noqa: E402

RUNS_DIR = os.environ.get(
    "BROTATO_RUNS_DIR",
    "C:/Users/moxhe/AppData/Roaming/Brotato/brotato_agent/runs",
)
RUN_ID = "run_1784819688_85761"
RUN_DIR = os.path.join(RUNS_DIR, RUN_ID)

if not os.path.isdir(RUN_DIR):
    pytest.skip(
        "frozen run %s not present under %s" % (RUN_ID, RUNS_DIR),
        allow_module_level=True,
    )


@pytest.fixture(scope="module")
def stats():
    """Stream the ~16k-event frozen run exactly once for the whole module."""
    return ts.compute_run_stats(RUN_DIR, RUN_ID)


def test_per_wave_populated_invariant(stats):
    """Waves 1..16 all present; S and occupancy populated wherever tiers ran."""
    per_wave = stats["per_wave"]
    assert set(per_wave) == {str(w) for w in range(1, 17)}
    for w in (str(i) for i in range(1, 17)):
        wd = per_wave[w]
        assert wd["S"]["n"] > 0, "wave %s S empty" % w
        assert wd["S"]["median"] is not None, "wave %s S median None" % w
        occ = wd["occupancy"]
        assert occ["captures"] > 0, "wave %s no captures" % w
        assert occ["corner_frac"] is not None, "wave %s corner_frac None" % w
        assert occ["edge_frac"] is not None, "wave %s edge_frac None" % w


def test_wave_1_exact_pins(stats):
    """Exact wave-1 S / occupancy values measured from the frozen capture."""
    w1 = stats["per_wave"]["1"]
    assert w1["S"]["n"] == 44
    # raw weapon_dps 45.225 / dps_target 45 = 1.005 (well inside the [0,2] clamp)
    assert w1["S"]["median"] == pytest.approx(1.005)
    occ = w1["occupancy"]
    assert occ["captures"] == 440
    assert occ["corner_frac"] == 0.0
    assert occ["edge_frac"] == pytest.approx(95 / 440)


def test_tier_and_consistency_totals(stats):
    """Per-wave S/capture counts sum to the pooled totals; tier fractions pin."""
    per_wave = stats["per_wave"]
    tiers = stats["strength_tiers"]
    s_total = sum(per_wave[w]["S"]["n"] for w in per_wave)
    cap_total = sum(per_wave[w]["occupancy"]["captures"] for w in per_wave)
    assert s_total == tiers["n"] == 1594
    assert cap_total == 15943
    assert tiers["strong"] == pytest.approx(0.0740276035131744)
    assert tiers["weak"] == pytest.approx(0.36260978670012545)


def test_summary_passthrough(stats):
    """summary.json fields flow through unchanged."""
    assert stats["result"] == "defeat"
    assert stats["last_wave"] == 16
    assert stats["policy_version"] == "teacher_v1-0.1.125-gun-wp1"


def test_cli_serialization_path(tmp_path):
    """main() CLI path writes JSON with the per-wave extraction intact."""
    out_path = tmp_path / "out.json"
    ts.main([
        "--runs-dir", RUNS_DIR,
        "--run-id", RUN_ID,
        "--out", str(out_path),
    ])
    with open(str(out_path), "r", encoding="utf-8") as fh:
        out = json.load(fh)
    assert out["runs"][0]["per_wave"]["1"]["S"]["median"] is not None
    assert out["pooled"]["per_wave"]["1"]["occupancy"]["captures"] == 440
