"""Unit tests for scripts/wp2_offer_dps_replay.py.

Pins the exact ports of combat_model.gd (weapon_dps / effective_weapon_dps /
apply_deltas / combat_value dps term) and shop_strategy.gd
(_effect_signed_value / _direct_offense_gain / _combat_deltas) against
hand-computed fixtures, plus the closed-form loadout-free gain identity, the
silent-combine reconciliation, config parsing, and the offer-record replay end
to end on a tiny synthetic run.
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))
import wp2_offer_dps_replay as R  # noqa: E402


# Tier-0 SMG exactly as recorded on the boards (also the well_rounded start).
SMG0 = {
    "damage": 3, "cooldown": 4, "scaling": [["stat_ranged_damage", 0.5]],
    "crit_chance": 0.01, "crit_damage": 1.5, "nb_projectiles": 1,
    "piercing": 0, "piercing_dmg_reduction": 0.5, "bounce": 0,
    "bounce_dmg_reduction": 0.5, "sets": ["set_gun"],
}


# ───────────────────────────── weapon_dps ──────────────────────────────────

def test_weapon_dps_zero_stats_matches_recorded_start():
    # flat=3, hit=3*1.005 (crit 0.01*(1.5-1)), rate=60/4=15 -> 45.225
    assert R.weapon_dps(SMG0, {}) == pytest.approx(45.225)


def test_weapon_dps_with_stats_hand_computed():
    stats = {"stat_ranged_damage": 10, "stat_percent_damage": 20,
             "stat_attack_speed": 50, "stat_crit_chance": 0}
    # flat = 3 + 0.5*10 = 8
    # hit  = 8 * 1.20 = 9.6 ; crit 0.01*(1.5-1)=0.005 -> *1.005 = 9.648
    # rate = 1.5 * 60/4 = 22.5 -> dps = 217.08
    assert R.weapon_dps(SMG0, stats) == pytest.approx(9.648 * 22.5)
    assert R.weapon_dps(SMG0, stats) == pytest.approx(217.08)


def test_weapon_dps_flat_floor_and_default_crit():
    # damage 0, no scaling -> flat floored to 1; crit_damage 0 -> default 2.0
    w = {"damage": 0, "cooldown": 6, "crit_chance": 0.0, "crit_damage": 0}
    # flat=1, hit=1, crit 0 -> hit=1, rate=60/6=10 -> 10
    assert R.weapon_dps(w, {}) == pytest.approx(10.0)


def test_weapon_dps_crit_chance_clamped_to_one():
    w = {"damage": 10, "cooldown": 60, "crit_chance": 0.5, "crit_damage": 3.0}
    stats = {"stat_crit_chance": 200}  # 0.5 + 2.0 -> clamp to 1.0
    # hit = 10 * (1 + 1.0*(3-1)) = 30 ; rate = 60/60 = 1 -> 30
    assert R.weapon_dps(w, stats) == pytest.approx(30.0)


def test_effective_weapon_dps_projectiles_and_piercing():
    w = dict(SMG0, nb_projectiles=4, piercing=2, piercing_dmg_reduction=0.5)
    # crowd = 1 + 2*0.5*0.35 = 1.35 ; *4 projectiles
    assert R.effective_weapon_dps(w, {}) == pytest.approx(45.225 * 4 * 1.35)


def test_effective_equals_direct_for_plain_gun():
    assert R.effective_weapon_dps(SMG0, {}) == pytest.approx(R.weapon_dps(SMG0, {}))


def test_effective_explosive_set_multiplier():
    w = dict(SMG0, sets=["set_gun", "set_explosive"])
    assert R.effective_weapon_dps(w, {}) == pytest.approx(45.225 * 1.15)


# ───────────────────────── apply_deltas / combat_value ─────────────────────

def test_apply_deltas_no_gain_mods():
    out = R.apply_deltas({"stat_ranged_damage": 8}, {"stat_ranged_damage": 2})
    assert out["stat_ranged_damage"] == pytest.approx(10.0)


def test_apply_deltas_with_gain_mod():
    # Ranger-style +50% ranged gain amplifies the delta.
    out = R.apply_deltas({"stat_ranged_damage": 8}, {"stat_ranged_damage": 2},
                         {"stat_ranged_damage": 50})
    assert out["stat_ranged_damage"] == pytest.approx(8 + 2 * 1.5)


def test_combat_value_dps_gain_ranged_damage():
    weapons = [SMG0]
    stats = {"stat_ranged_damage": 10, "stat_percent_damage": 20,
             "stat_attack_speed": 50}
    # dps0 flat=8 ; dps1 flat=9 (ranged +2 -> +1 flat). ratio of dps = 9/8 hit.
    dps0 = R.total_dps(weapons, stats)
    gain = R.combat_value_dps_gain(weapons, stats, {"stat_ranged_damage": 2})
    # flat 8 -> 9 ; multipliers constant -> +12.5%
    assert gain == pytest.approx(12.5)
    assert dps0 > 0


def test_combat_value_from_zero_dps_capped_100():
    # dps0 == 0 (empty loadout) but dps1 positive -> capped to 100.0
    # Force via a weapon whose flat becomes positive only after the delta is
    # not possible (flat is floored); instead test the empty-loadout branch.
    assert R.combat_value_dps_gain([], {}, {"stat_ranged_damage": 5}) == 0.0


def test_speed_delta_does_not_change_dps_gain():
    weapons = [SMG0]
    stats = {"stat_ranged_damage": 8, "stat_percent_damage": 11,
             "stat_attack_speed": 35}
    g_ranged = R.combat_value_dps_gain(weapons, stats, {"stat_ranged_damage": 2})
    g_ranged_speed = R.combat_value_dps_gain(
        weapons, stats, {"stat_ranged_damage": 2, "stat_speed": -3})
    assert g_ranged == pytest.approx(g_ranged_speed)


# ───────────────────────── closed-form identity ────────────────────────────

def test_closed_form_attack_speed_matches_model():
    weapons = [SMG0, dict(SMG0, damage=15, cooldown=14)]
    stats = {"stat_percent_damage": 20, "stat_attack_speed": 50,
             "stat_ranged_damage": 12}
    deltas = {"stat_attack_speed": 10}
    cf = R.closed_form_dps_gain(stats, deltas)
    model = R.combat_value_dps_gain(weapons, stats, deltas)
    assert cf == pytest.approx(model)
    # (1+60/100)/(1+50/100) - 1 = 1.6/1.5 - 1
    assert cf == pytest.approx(100.0 * (1.6 / 1.5 - 1.0))


def test_closed_form_percent_damage_matches_model():
    weapons = [SMG0, dict(SMG0, damage=15, cooldown=14, crit_chance=0.05)]
    stats = {"stat_percent_damage": 20, "stat_attack_speed": 35}
    deltas = {"stat_percent_damage": 30}
    cf = R.closed_form_dps_gain(stats, deltas)
    model = R.combat_value_dps_gain(weapons, stats, deltas)
    assert cf == pytest.approx(model)
    assert cf == pytest.approx(100.0 * (1.5 / 1.2 - 1.0))  # 25%


def test_closed_form_mixed_pct_and_speed_matches_model():
    weapons = [SMG0, dict(SMG0, damage=20, cooldown=8)]
    stats = {"stat_percent_damage": 10, "stat_attack_speed": 40}
    deltas = {"stat_percent_damage": 15, "stat_attack_speed": 5}
    assert R.closed_form_dps_gain(stats, deltas) == pytest.approx(
        R.combat_value_dps_gain(weapons, stats, deltas))


# ───────────────────────── shop_strategy ports ─────────────────────────────

def test_effect_signed_value_signs():
    assert R.effect_signed_value({"value": 5, "sign": R._SIGN_POSITIVE}) == 5.0
    assert R.effect_signed_value({"value": 5, "sign": R._SIGN_NEGATIVE}) == -5.0
    assert R.effect_signed_value({"value": 5, "sign": R._SIGN_NEUTRAL}) == 0.0
    assert R.effect_signed_value({"value": -3, "sign": R._SIGN_FROM_VALUE}) == -3.0
    assert R.effect_signed_value({"value": None, "sign": R._SIGN_FROM_VALUE}) == 0.0


def test_direct_offense_gain_sums_offense_stats_only():
    effects = [
        {"key": "stat_ranged_damage", "value": 2, "sign": 3},
        {"key": "stat_percent_damage", "value": 4, "sign": 3},
        {"key": "stat_attack_speed", "value": 3, "sign": 3},
        {"key": "stat_engineering", "value": 5, "sign": 3},  # ignored
    ]
    assert R.direct_offense_gain(effects) == pytest.approx(9.0)


def test_direct_offense_gain_excludes_crit():
    effects = [{"key": "stat_crit_chance", "value": 6, "sign": 3}]
    assert R.direct_offense_gain(effects) == pytest.approx(0.0)


def test_direct_offense_gain_explosive_min_one():
    effects = [{"key": "piercing", "value": 1, "sign": 3}]
    assert R.direct_offense_gain(effects) == pytest.approx(1.0)


def test_combat_deltas_keeps_only_combat_stats():
    effects = [
        {"key": "stat_ranged_damage", "value": 2, "sign": 3},
        {"key": "stat_speed", "value": -3, "sign": 3},
        {"key": "stat_engineering", "value": 3, "sign": 3},  # not a combat stat
    ]
    d = R.combat_deltas(effects)
    assert d == {"stat_ranged_damage": 2.0, "stat_speed": -3.0}


# ───────────────────────── loadout reconstruction ──────────────────────────

def test_tier_and_combine_id_helpers():
    assert R.tier_of("weapon_smg_1") == 0
    assert R.tier_of("weapon_smg_4") == 3
    assert R.base_of("weapon_double_barrel_shotgun_2") == "weapon_double_barrel_shotgun"
    assert R.combined_id("weapon_smg_2") == "weapon_smg_3"


def test_reconcile_recovers_silent_combine():
    # Two smg_1 should silently combine to smg_2; table has both tiers.
    wstats = {
        "weapon_smg_1": SMG0,
        "weapon_smg_2": dict(SMG0, damage=4),
    }
    recon = R.LoadoutReconstructor(wstats)
    stats = {}
    # true loadout: one smg_2 (tier1). recorded metrics from that:
    true_load = ["weapon_smg_2"]
    rec_dps = R.total_effective_weapon_dps([wstats[w] for w in true_load], stats)
    rec_count = 1
    rec_tsum = R.tier_of("weapon_smg_2") + 1  # = 2
    # my drifted tracking still has two smg_1:
    fixed = recon.reconcile(["weapon_smg_1", "weapon_smg_1"], stats,
                            rec_dps, rec_count, rec_tsum)
    assert fixed == ["weapon_smg_2"]


def test_validate_rejects_wrong_count():
    recon = R.LoadoutReconstructor({"weapon_smg_1": SMG0})
    assert not recon.validate(["weapon_smg_1"], {}, 45.225, 2, 1)
    assert recon.validate(["weapon_smg_1"], {}, 45.225, 1, 1)


# ───────────────────────────── config parse ────────────────────────────────

def test_parse_threshold_reads_config():
    val = R.parse_threshold()
    assert val == pytest.approx(6.0)


# ───────────────────────── end-to-end mini replay ──────────────────────────

def _ev(seq, event, payload):
    return {"seq": seq, "event": event, "payload": payload}


def test_replay_records_offer_and_flat_gain():
    # One run, one w9 shop offering a +5 ranged item (bought) and a +2 pct item
    # (skipped). Loadout is the start SMG so it validates against a matching dps.
    stats_dps = R.total_effective_weapon_dps([SMG0], {"stat_ranged_damage": 0,
                                                      "stat_percent_damage": 0,
                                                      "stat_attack_speed": 0,
                                                      "stat_crit_chance": 0})
    off = {"ranged_damage": 0, "percent_damage": 0, "attack_speed": 0,
           "crit_chance": 0, "weapon_dps": stats_dps, "weapon_count": 1,
           "weapon_tier_sum": 1}
    board = {"items": [
        {"slot": 0, "category": "item", "affordable": True,
         "id": "item_ranged", "effects": [
             {"key": "stat_ranged_damage", "value": 5, "sign": 3}]},
        {"slot": 1, "category": "item", "affordable": True,
         "id": "item_pct", "effects": [
             {"key": "stat_percent_damage", "value": 2, "sign": 3}]},
    ], "gold": 50}
    events = [
        _ev(1, "run_start", {"weapon": "weapon_smg_1"}),
        _ev(2, "purchase_offer", board),
        _ev(3, "purchase_decision", {
            "wave": 9, "action": {"type": "shop_buy", "slot": 0},
            "build_metrics": {"offense": off}}),
    ]
    runs = {"run_x": events}
    results = {"run_x": "defeat"}
    wstats = R.harvest_weapon_stats({"seed": [
        _ev(0, "purchase_offer", {"items": [
            dict(SMG0, slot=0, category="weapon", id="weapon_smg_1")]})]})
    records, parity, trust = R.replay(runs, results, wstats)
    by_id = {r["item_id"]: r for r in records}
    assert set(by_id) == {"item_ranged", "item_pct"}
    assert by_id["item_ranged"]["bought"] is True
    assert by_id["item_pct"]["bought"] is False
    # flat gains
    assert by_id["item_ranged"]["direct_gain"] == pytest.approx(5.0)
    assert by_id["item_pct"]["direct_gain"] == pytest.approx(2.0)
    # pct item is loadout-free -> closed form computed
    assert by_id["item_pct"]["dps_method"] == "closed_form"
    # ranged item needs loadout -> model (loadout trusted here)
    assert by_id["item_ranged"]["dps_method"] == "model"
    assert by_id["item_ranged"]["dps_gain"] is not None
