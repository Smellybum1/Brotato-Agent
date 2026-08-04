"""Contract tests for the preregistered §45 analyzer."""
from pathlib import Path
import importlib.util
import sys


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/wp2_route_latch_revalidation_analysis.py"


def load_module():
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("s45_analysis", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_fixed_identity_and_row_tuple():
    module = load_module()
    assert module.BUILD == "0.2.81-wp2-capture"
    assert module.POLICY == "teacher_v1-0.1.129-gun-wp1"
    assert module.row_tuple({"x": 1, "y": 2, "body": 3, "proj": 4, "pen": 5}) == (1, 2, 3, 4, 5)


def test_summary_contract_requires_both_instruments_and_conversion():
    module = load_module()
    summary = {
        "mod_version": module.BUILD, "policy_version": module.POLICY,
        "character_observed": "character_ranger", "danger": 5,
        "requested_danger": 5, "danger_ok": True, "weapon": "weapon_pistol_1",
        "telemetry_complete": True, "clearance_guarded_conversion": True,
        "route_scores_enabled": True, "route_latch_revalidation_enabled": True,
        "body_clearance_scale": 1, "unlock_pool": module.ERA, "result": "defeat",
    }
    assert module.summary_faults(summary) == []
    summary["route_latch_revalidation_enabled"] = False
    assert module.summary_faults(summary)


def test_controls_and_sufficiency_precede_latch_result():
    text = SCRIPT.read_text(encoding="utf-8")
    controls = text.index("STEP 1 — RUN")
    sufficiency = text.index("STEP 2 — DATA")
    result = text.index("STEP 3 — FROZEN")
    assert controls < sufficiency < result
    assert '"INSUFFICIENT_INSTRUMENT"' in text
    assert 'horizon_rate >= 0.25' in text
    assert 'duration_q["median"] >= 0.30' in text


def test_live_trigger_override_hook_is_explicit_and_tested():
    latch_source = (ROOT / "scripts/wp2_route_conversion_latch_gate0.py").read_text(encoding="utf-8")
    assert 'capture.get("trigger_evaluated")' in latch_source
    assert 'capture.get("revalidation_admitted")' in latch_source
