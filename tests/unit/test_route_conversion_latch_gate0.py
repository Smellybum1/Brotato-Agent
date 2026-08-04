"""Contract and state-machine tests for the preregistered §44 latch gate."""
from __future__ import annotations

import importlib.util
import math
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/wp2_route_conversion_latch_gate0.py"


def load_module():
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("s44_latch", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_fixed_boundaries_and_runs_match_preregistration():
    module = load_module()
    prereg = (ROOT / "reports/wp2/route_conversion_latch_gate0_prereg.md").read_text(encoding="utf-8")
    assert module.HORIZON_MS == 600
    assert module.FUTURE_TOLERANCE_MS == 75
    assert module.ANGLE_LIMIT_DEG == 15.1
    assert module.OBSERVABILITY_BAR == 0.90
    assert len(module.base.EXPECTED_RUNS) == 8
    for run_id in module.base.EXPECTED_RUNS:
        assert run_id in prereg


def test_angular_boundary_reaches_both_sides():
    module = load_module()
    c15 = {"x": math.cos(math.radians(15)), "y": math.sin(math.radians(15))}
    c16 = {"x": math.cos(math.radians(16)), "y": math.sin(math.radians(16))}
    assert module.choose_near_heading([c15], (1, 0))[1] <= 15.1
    assert module.choose_near_heading([c16], (1, 0))[1] > 15.1


def test_self_test_covers_state_machine_branches():
    module = load_module()
    module.self_test()


def test_controls_precede_all_result_sections():
    text = SCRIPT.read_text(encoding="utf-8")
    controls = text.index("STEP 1 — DENOMINATORS")
    observability = text.index("STEP 2 — ARCHIVE")
    temporal = text.index("STEP 3 — TEMPORAL")
    safety = text.index("STEP 4 — SAFETY")
    decision = text.index("STEP 5 — GATE")
    assert controls < observability < temporal < safety < decision
    assert '"DATA_LIMITED" if observability < OBSERVABILITY_BAR else "FAIL"' in text


def test_prior_analyzer_join_fields_are_observational_only():
    source = (ROOT / "scripts/wp2_joint_route_conversion_gate0.py").read_text(encoding="utf-8")
    assert '"capture_seq": payload.get("capture_seq")' in source
    assert '"ts_ms": event.get("ts_ms")' in source
