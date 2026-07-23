"""Unit tests for scripts/wp2_telemetry_stats.py.

Pins: S computation + clamp, occupancy geometry (a known corner point),
hysteresis tier state machine, shop economy extraction, dash episode edge
detection, and material saturation. Uses a small synthetic events.jsonl fixture
built in a tmp dir so the suite never touches the real run directories.
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))
import wp2_telemetry_stats as ts  # noqa: E402


# --------------------------------------------------------------------------
# pure-function pins
# --------------------------------------------------------------------------
def test_clamp_bounds():
    assert ts.clamp(-0.3, 0.0, 2.0) == 0.0
    assert ts.clamp(2.7, 0.0, 2.0) == 2.0
    assert ts.clamp(1.3, 0.0, 2.0) == 1.3


def test_percentile_linear():
    vals = [0.0, 1.0, 2.0, 3.0, 4.0]
    assert ts.percentile(vals, 50) == 2.0
    assert ts.percentile(vals, 10) == pytest.approx(0.4)
    assert ts.percentile(vals, 90) == pytest.approx(3.6)
    assert ts.percentile([5.0], 50) == 5.0


def test_summarize_empty_and_basic():
    assert ts.summarize([])["median"] is None
    s = ts.summarize([1.0, 2.0, 3.0])
    assert s["median"] == 2.0
    assert s["mean"] == 2.0
    assert s["n"] == 3


def test_s_computation_clamped():
    # weapon_dps / dps_target clamped to [0,2]
    assert ts.clamp(3000.0 / 1000.0, 0.0, 2.0) == 2.0        # over-cap -> 2
    assert ts.clamp(500.0 / 1000.0, 0.0, 2.0) == 0.5
    assert ts.clamp(1250.0 / 1000.0, 0.0, 2.0) == 1.25       # exactly strong


def test_occupancy_geometry_known_corner():
    # arena 2048x1536, margin 280. A point 100 from left AND 100 from top is a
    # true two-wall corner (and therefore also an edge).
    corner, edge = ts.occupancy_flags(100.0, 100.0, 2048.0, 1536.0)
    assert corner is True and edge is True
    # near only the left wall -> edge but NOT corner
    corner, edge = ts.occupancy_flags(100.0, 768.0, 2048.0, 1536.0)
    assert corner is False and edge is True
    # center -> neither
    corner, edge = ts.occupancy_flags(1024.0, 768.0, 2048.0, 1536.0)
    assert corner is False and edge is False
    # bottom-right corner (100 from right, 100 from bottom)
    corner, edge = ts.occupancy_flags(2048.0 - 100, 1536.0 - 100,
                                      2048.0, 1536.0)
    assert corner is True and edge is True
    # exactly on the margin boundary is NOT inside (strict <)
    corner, edge = ts.occupancy_flags(280.0, 768.0, 2048.0, 1536.0)
    assert edge is False


def test_hysteresis_tiers():
    # rises into strong, dips into the exit band (stays strong), then collapses
    series = [1.0, 1.3, 1.2, 1.3, 0.7, 0.8, 0.7]
    #  1.0 -> neutral
    #  1.3 -> strong (>=1.25)
    #  1.2 -> strong (>1.15 exit, holds)
    #  1.3 -> strong
    #  0.7 -> <=1.15 exit AND <=0.75 weak-enter -> weak
    #  0.8 -> weak (0.8 < 0.85 exit, holds)
    #  0.7 -> weak
    t = ts.strength_tiers(series)
    assert t["n"] == 7
    # 3 strong ticks, 3 weak ticks, 1 neutral tick
    assert t["strong"] == pytest.approx(3 / 7)
    assert t["weak"] == pytest.approx(3 / 7)
    assert t["neutral"] == pytest.approx(1 / 7)


def test_hysteresis_holds_in_band():
    # never leaves neutral if it only wanders inside (0.75, 1.25)
    t = ts.strength_tiers([1.0, 1.1, 0.9, 1.2, 0.8])
    assert t["neutral"] == 1.0


# --------------------------------------------------------------------------
# end-to-end streaming pass over a synthetic fixture
# --------------------------------------------------------------------------
def _ev(event, payload, seq=0):
    return {"schema_version": "1.0.0", "run_id": "run_test",
            "seq": seq, "ts_ms": seq, "event": event, "payload": payload}


def _write_fixture(run_dir):
    os.makedirs(run_dir, exist_ok=True)
    lines = []
    seq = 0

    def add(event, payload):
        nonlocal seq
        lines.append(_ev(event, payload, seq))
        seq += 1

    arena = {"width": 2048, "height": 1536}

    # ---- wave 1: two combat_ticks (S = 0.5 then 1.25), captures, dash ----
    add("run_start", {})
    add("combat_tick", {"wave": 1, "build_metrics": {"offense": {
        "weapon_dps": 500.0, "dps_target": 1000.0,
        "ranged_damage": 10, "attack_speed": 5,
        "percent_damage": 3, "crit_chance": 2}}})
    add("combat_tick", {"wave": 1, "build_metrics": {"offense": {
        "weapon_dps": 1250.0, "dps_target": 1000.0}}})

    # captures wave 1: one in a corner (100,100), one center, one edge-left.
    # materials: one capture saturated (>=48), one not.
    add("combat_capture", {"wave": 1, "arena": arena,
        "player": {"x": 100, "y": 100},
        "entities": {"materials": [0] * 50},   # saturated (>=48)
        "teacher": {"contributions": {"finale_translation": {
            "loot_dash_active": False}}}})
    add("combat_capture", {"wave": 1, "arena": arena,
        "player": {"x": 1024, "y": 768},
        "entities": {"materials": [0] * 10},   # not saturated
        "teacher": {"contributions": {"finale_translation": {
            "loot_dash_active": True}}}})       # dash episode start
    add("combat_capture", {"wave": 1, "arena": arena,
        "player": {"x": 100, "y": 768},
        "entities": {"materials": []},
        "teacher": {"contributions": {"finale_translation": {
            "loot_dash_active": True}}}})        # dash continues (len 2)
    add("combat_capture", {"wave": 1, "arena": arena,
        "player": {"x": 1024, "y": 768},
        "entities": {"materials": []},
        "teacher": {"contributions": {"finale_translation": {
            "loot_dash_active": False}}}})       # dash ends -> episode len 2

    add("player_damage", {"amount": 7, "hp": 20})   # attributed to wave 1

    # ---- shop after wave 1 ----
    add("purchase_offer", {"gold": 100, "reroll_price": 2, "items": [
        {"slot": 0, "id": "item_ranged", "price": 30, "category": "item",
         "effects": [{"key": "stat_ranged_damage", "value": 4}]},
        {"slot": 1, "id": "item_hp", "price": 25, "category": "item",
         "effects": [{"key": "stat_max_hp", "value": 5}]},
        {"slot": 2, "id": "weapon_x", "price": 40, "category": "weapon",
         "effects": []},
        {"slot": 3, "id": "item_crit", "price": 20, "category": "item",
         "effects": [{"key": "stat_crit_chance", "value": 3}]},
    ]})
    # buy the offense (ranged) item in slot 0
    add("purchase_decision", {"wave": 1, "gold_before": 100, "reroll_price": 2,
        "action": {"type": "shop_buy", "slot": 0, "item_id": "item_ranged"},
        "score_breakdown": {"type": "shop_buy", "slot": 0}})
    # reroll (cost 2)
    add("purchase_offer", {"gold": 70, "reroll_price": 2, "items": [
        {"slot": 0, "id": "item_speed", "price": 15, "category": "item",
         "effects": [{"key": "stat_speed", "value": 4}]},
        {"slot": 1, "id": "item_hp", "price": 25, "category": "item",
         "effects": [{"key": "stat_max_hp", "value": 5}]},
        {"slot": 2, "id": "item_hp2", "price": 25, "category": "item",
         "effects": [{"key": "stat_max_hp", "value": 5}]},
        {"slot": 3, "id": "item_hp3", "price": 25, "category": "item",
         "effects": [{"key": "stat_max_hp", "value": 5}]},
    ]})
    add("purchase_decision", {"wave": 1, "gold_before": 70, "reroll_price": 2,
        "action": {"type": "shop_reroll", "score": 0}})
    # leave shop with 68 idle gold
    add("purchase_decision", {"wave": 1, "gold_before": 68, "reroll_price": 2,
        "action": {"type": "shop_go"}})

    add("run_end", {})

    with open(os.path.join(run_dir, "events.jsonl"), "w",
              encoding="utf-8") as fh:
        for ln in lines:
            fh.write(json.dumps(ln) + "\n")
    with open(os.path.join(run_dir, "summary.json"), "w",
              encoding="utf-8") as fh:
        json.dump({"run_id": "run_test", "result": "victory", "last_wave": 1,
                   "waves_completed": 1,
                   "policy_version": "teacher_test",
                   "mod_version": "0.0.0-test"}, fh)


@pytest.fixture()
def run_stats(tmp_path):
    run_dir = os.path.join(str(tmp_path), "run_test")
    _write_fixture(run_dir)
    return ts.compute_run_stats(run_dir, "run_test")


def test_summary_fields(run_stats):
    assert run_stats["result"] == "victory"
    assert run_stats["last_wave"] == 1
    assert run_stats["offers_recorded"] is True
    # the fixture (like the real telemetry) records NO marginal-DPS field
    assert run_stats["offer_marginal_dps_recorded"] is False


def test_s_per_wave(run_stats):
    w1 = run_stats["per_wave"]["1"]["S"]
    # S values 0.5 and 1.25 -> median 0.875
    assert w1["median"] == pytest.approx(0.875)
    assert w1["n"] == 2
    # offense stat medians surfaced
    om = run_stats["per_wave"]["1"]["offense_stats_median"]
    assert om["ranged_damage"] == 10


def test_occupancy_per_wave(run_stats):
    occ = run_stats["per_wave"]["1"]["occupancy"]
    assert occ["captures"] == 4
    # 1 of 4 captures is a true corner (the 100,100 point)
    assert occ["corner_frac"] == pytest.approx(0.25)
    # 2 of 4 are edges (corner point + left-edge point)
    assert occ["edge_frac"] == pytest.approx(0.5)


def test_material_saturation(run_stats):
    mat = run_stats["per_wave"]["1"]["materials"]
    assert mat["captures"] == 4
    # exactly one capture had >=48 materials
    assert mat["saturation_frac"] == pytest.approx(0.25)
    assert mat["max"] == 50


def test_dash_episode_edge_detection(run_stats):
    dash = run_stats["per_wave"]["1"]["dash"]
    assert dash["episodes"] == 1
    assert dash["mean_len"] == 2          # two consecutive active captures
    assert dash["active_frac"] == pytest.approx(2 / 4)


def test_damage_attribution(run_stats):
    dmg = run_stats["per_wave"]["1"]["damage"]
    assert dmg["amount"] == 7
    assert dmg["events"] == 1


def test_shop_economy(run_stats):
    shop = run_stats["shops"]["1"]
    assert shop["gold_entering"] == 100
    assert shop["idle_gold"] == 68
    assert shop["reroll_count"] == 1
    assert shop["reroll_cost"] == 2
    assert shop["spend"] == 30                     # the ranged item price
    assert shop["offense_stat_items_bought"] == 1  # ranged item flagged
    # ranged + crit offered on the first board (offense items)
    assert shop["offense_stat_items_offered"] == 2
    bought = shop["items_bought"]
    assert len(bought) == 1
    assert bought[0]["id"] == "item_ranged"
    assert bought[0]["offense_stat"] is True
    assert bought[0]["effect_keys"] == ["stat_ranged_damage"]


def test_pooled(run_stats):
    pooled = ts.pool_runs([run_stats])
    assert pooled["run_count"] == 1
    assert "1" in pooled["per_wave"]
    assert pooled["per_wave"]["1"]["occupancy"]["corner_frac"] == pytest.approx(0.25)
