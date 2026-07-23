"""Unit tests for scripts/wp2_skip_diagnosis.py.

Pins the offense-target formula (config-parsed floors + density bonuses), the
band_gate / offense_deficient annotation, and the skip classification + root
cause against synthetic records.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))
import wp2_skip_diagnosis as D  # noqa: E402


def _consts():
    return D.parse_consts()


def test_parse_consts_has_expected_floors():
    c = _consts()
    assert c["MID_SHOP_PIVOT_WAVE"] == 9
    assert c["LATE_SHOP_WAVE"] == 15
    assert c["OFFENSE_FLOOR_MID"] == 70.0
    assert c["OFFENSE_FLOOR_LATE"] == 120.0
    assert c["OFFENSE_BAND_FROM_WAVE"] == 13


def test_offense_target_mid_wave_base_plus_margin():
    c = _consts()
    # wave 9-14: 70 base + 25 margin, no density bonus at goal density.
    assert D.offense_target(10, 15.0, 25.0, c) == pytest.approx(95.0)
    # below wave 9: 0 (no floor).
    assert D.offense_target(8, 15.0, 25.0, c) == pytest.approx(0.0)
    # wave 15+: 120 base + 25.
    assert D.offense_target(15, 15.0, 25.0, c) == pytest.approx(145.0)


def test_offense_target_density_bonus_clamped():
    c = _consts()
    # p90 well above goal -> density bonus clamped at 90; peak at 30.
    t = D.offense_target(10, 1000.0, 1000.0, c)
    assert t == pytest.approx(70.0 + 25.0 + 90.0 + 30.0)


def _rec(**kw):
    base = dict(wave=10, prev_p90_density=15, prev_peak_density=25,
                offense_total=40.0, weapon_dps=400.0, dps_target=765.0,
                direct_gain=5.0, affordable=True, action_type="shop_reroll",
                action_slot=None, result="defeat", bought=False, item_id="i",
                slot=0, price=50, gold_before=200)
    base.update(kw)
    return base


def test_annotate_offense_deficient_and_band_gate():
    c = _consts()
    r = D.annotate(_rec(wave=14, offense_total=40.0, weapon_dps=400.0,
                        dps_target=800.0), c)
    assert r["offense_deficient"] is True          # 40 < 95
    assert r["band_gate"] is True                   # wave14 >=13 and 400<800


def test_annotate_band_gate_off_below_wave_13():
    c = _consts()
    r = D.annotate(_rec(wave=11, weapon_dps=1.0, dps_target=999.0), c)
    assert r["band_gate"] is False                  # wave 11 < 13


def test_classify_buckets():
    assert D.classify(_rec(affordable=False))[0] == "gold_blocked"
    assert D.classify(_rec(action_type="shop_buy"))[0] == "outscored"
    assert D.classify(_rec(action_type="shop_reroll")) == ("loop_exit", "shop_reroll")
    assert D.classify(_rec(action_type="shop_go")) == ("loop_exit", "shop_go")
    assert D.classify(_rec(action_type="shop_sell")) == ("other", "shop_sell")


def test_root_cause_distinguishes_actions():
    c = _consts()
    # deficient + reroll
    r = D.annotate(_rec(action_type="shop_reroll", offense_total=10.0), c)
    assert D.root_cause(r) == "deficient_but_rerolled_for_more_impact"
    # deficient + buy
    r = D.annotate(_rec(action_type="shop_buy", offense_total=10.0), c)
    assert D.root_cause(r) == "deficient_but_outranked_this_board"
    # deficient + sell
    r = D.annotate(_rec(action_type="shop_sell", offense_total=10.0), c)
    assert D.root_cause(r) == "deficient_but_board_did_shop_sell"
    # unaffordable dominates
    r = D.annotate(_rec(affordable=False, offense_total=10.0), c)
    assert D.root_cause(r) == "unaffordable"
    # offense adequate -> mandatory path never fires
    r = D.annotate(_rec(offense_total=10_000.0), c)
    assert D.root_cause(r) == "offense_adequate_no_mandatory_path"
