"""Contract tests for the preregistered §42 collector and analyzer."""
from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def load(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_driver_encodes_the_committed_order_and_inert_control_surface(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    driver = load("s42_driver", "scripts/wp2_guarded_conversion_screen.py")
    assert driver.ORDER == ("C", "T", "T", "C", "T", "C", "C", "T")
    control = driver.fixed_config(False)
    treatment = driver.fixed_config(True)
    assert control["character"] == treatment["character"] == "character_ranger"
    assert control["danger"] == treatment["danger"] == 5
    assert control["weapon_prefixes"][0] == "weapon_pistol"
    assert control["clearance_guarded_conversion"] is False
    assert treatment["clearance_guarded_conversion"] is True
    assert control["route_scores_enabled"] is False
    assert control["body_clearance_scale"] == 1.0
    changed = {key for key in control if control[key] != treatment[key]}
    assert changed == {"clearance_guarded_conversion"}
    source = (ROOT / "scripts/wp2_guarded_conversion_screen.py").read_text(
        encoding="utf-8"
    )
    assert "automatic top-up is forbidden" in source
    assert "EXPERIMENT_PORT_WR_PROFILE_TO" in source


def test_analyzer_statistic_has_positive_and_negative_controls():
    analysis = load("s42_analysis", "scripts/wp2_guarded_conversion_screen_analysis.py")
    assert analysis.exact_permutation([1, 1, 1], [1, 1, 1]) == 1.0
    assert analysis.exact_permutation([10, 11, 12], [1, 2, 3]) == 0.1
    assert analysis.exact_permutation([10, 11, 12, 13], [1, 2, 3, 4]) < 0.05


def test_analyzer_keeps_validity_and_delivery_before_outcomes():
    text = (ROOT / "scripts/wp2_guarded_conversion_screen_analysis.py").read_text(
        encoding="utf-8"
    )
    validity = text.index("STEP 1 — VALIDITY")
    delivery = text.index("STEP 2 — DELIVERY")
    primary = text.index("STEP 3 — PRIMARY")
    safety = text.index("STEP 4 — LOW-HP")
    context = text.index("STEP 5 — CONTEXT")
    assert validity < delivery < primary < safety < context
    assert 'delta >= 0.05 and p_value <= 0.05' in text
    assert 'stats.mean(safety[m]["T"]) <= stats.mean(safety[m]["C"])' in text
    assert 'if all_faults:' in text
    assert 'elif delivery_faults:' in text


def test_prereg_and_analyzer_share_fixed_population_and_build():
    prereg = (
        ROOT / "reports/wp2/clearance_guarded_conversion_screen_prereg.md"
    ).read_text(encoding="utf-8")
    analysis = load("s42_analysis_contract", "scripts/wp2_guarded_conversion_screen_analysis.py")
    assert "C, T, T, C, T, C, C, T" in prereg
    assert analysis.BUILD in prereg
    for value in analysis.ERA.values():
        assert str(value) in prereg
