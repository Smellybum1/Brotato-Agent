"""Contract pins for the fixed §45 acquisition driver."""
from pathlib import Path
import importlib.util
import sys


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/wp2_route_latch_revalidation_acquisition.py"


def load_module():
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("s45_acquisition", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_fixed_four_slot_instrument_arm_and_parked_arm():
    module = load_module()
    assert module.SLOTS == (1, 2, 3, 4)
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


def test_driver_has_no_optional_stopping_or_topup_path():
    text = SCRIPT.read_text(encoding="utf-8")
    assert '"--runs", "1"' in text
    assert "--min-wins" not in text  # this bounded collector has no win gate
    assert "stop-on-win" not in text
    assert "automatic top-up is forbidden" in text
    assert '"--repair-launch"' in text
