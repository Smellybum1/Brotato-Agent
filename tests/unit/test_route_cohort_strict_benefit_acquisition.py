"""Contract pins for the fixed §47 acquisition driver."""
from pathlib import Path
import importlib.util
import sys


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/wp2_route_cohort_strict_benefit_acquisition.py"


def load_module():
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("s47_acquisition", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_fixed_six_slot_arm_identity_and_park():
    module = load_module()
    assert module.SLOTS == (1, 2, 3, 4, 5, 6)
    assert module.EXPECTED_BUILD == "0.2.81-wp2-capture"
    armed = module.fixed_config(True)
    assert armed["character"] == "character_ranger"
    assert armed["danger"] == 5
    assert armed["clearance_guarded_conversion"] is True
    assert armed["route_scores_enabled"] is True
    assert armed["route_latch_revalidation_enabled"] is True
    assert armed["time_scale"] == 1.0
    parked = module.fixed_config(False)
    assert parked["auto_start"] is False
    assert parked["clearance_guarded_conversion"] is False
    assert parked["route_scores_enabled"] is False
    assert parked["route_latch_revalidation_enabled"] is False


def test_driver_repairs_before_every_slot_and_has_no_optional_stop():
    text = SCRIPT.read_text(encoding="utf-8")
    assert text.count('"--repair-launch"') == 1
    assert text.index('"--repair-launch"') > text.index("for slot in SLOTS")
    assert '"--runs", "1"' in text
    assert "stop-on-win" not in text
    assert "automatic replacement/top-up is forbidden" in text
    assert "verify_installed_identity" in text
