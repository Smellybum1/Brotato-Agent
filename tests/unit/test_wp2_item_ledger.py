"""Unit tests for scripts/wp2_item_ledger.py.

All fixtures are synthetic run-stats dicts (the compute_run_stats output shape),
so no real telemetry is streamed. Cover: classification, matched-wave baseline
selection, KPI contrast arithmetic, insufficient-n flagging, tier tension, and
merge pooling correctness.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))

import wp2_item_ledger as L  # noqa: E402


# --------------------------------------------------------------------------- #
# helpers to build synthetic run-stats dicts
# --------------------------------------------------------------------------- #
def _run(run_id, result, per_wave_sat, buys=None, damage=None, gold=None):
    """per_wave_sat: {wave:int -> saturation_frac}. buys: [(wave, item_id)]."""
    per_wave = {}
    for w, sat in per_wave_sat.items():
        per_wave[str(w)] = {
            "materials": {"saturation_frac": sat, "mean": sat * 50.0},
            "damage": {"amount": (damage or {}).get(w, 0.0)},
        }
    shops = {}
    for w, item_id in (buys or []):
        shops.setdefault(str(w), {"items_bought": [],
                                  "gold_entering": (gold or {}).get(w)})
        shops[str(w)]["items_bought"].append(
            {"id": item_id, "price": 50, "category": "item"})
    # ensure gold-only shop waves exist
    for w, g in (gold or {}).items():
        shops.setdefault(str(w), {"items_bought": [], "gold_entering": g})
    return {"run_id": run_id, "result": result,
            "per_wave": per_wave, "shops": shops}


# --------------------------------------------------------------------------- #
# classification
# --------------------------------------------------------------------------- #
def test_classify_pickup_tag_is_collection():
    classes, primary = L.classify_item(["pickup", "stat_range"],
                                        ["instant_gold_attracting"])
    assert "collection" in classes
    assert primary == "collection"


def test_classify_collection_wins_over_offense():
    # metal-detector-like: pickup + percent_damage -> collection is primary.
    classes, primary = L.classify_item(["pickup", "economy"],
                                        ["stat_percent_damage", "chance_double_gold"])
    assert set(classes) >= {"collection", "offense", "economy"}
    assert primary == "collection"


def test_classify_pure_offense():
    classes, primary = L.classify_item([], ["stat_ranged_damage"])
    assert classes == ["offense"]
    assert primary == "offense"


def test_classify_defensive_and_other():
    _, primary = L.classify_item([], ["stat_armor"])
    assert primary == "defensive"
    classes, primary = L.classify_item([], ["stat_speed"])
    assert primary == "other" and classes == ["other"]


# --------------------------------------------------------------------------- #
# purchases + holdings
# --------------------------------------------------------------------------- #
def test_extract_purchases_and_earliest_buy():
    r = _run("rA", "victory", {5: 0.2, 6: 0.3},
             buys=[(5, "item_x"), (6, "item_x"), (6, "item_y")])
    purchases = L.extract_purchases(r)
    assert len(purchases) == 3
    eb = L.earliest_buy_by_run(purchases, "item_x")
    assert eb == {"rA": 5}  # earliest of waves 5 and 6


# --------------------------------------------------------------------------- #
# matched-wave baseline selection + contrast arithmetic
# --------------------------------------------------------------------------- #
def test_matched_contrast_baseline_excludes_holders_and_arithmetic():
    # holder buys item at w1; baseline at each wave = mean over NON-holders.
    holder = _run("h", "victory", {1: 0.5, 2: 0.9, 3: 0.9}, buys=[(1, "item_g")])
    n1 = _run("n1", "defeat", {2: 0.5, 3: 0.5})          # never buys
    n2 = _run("n2", "defeat", {2: 0.3, 3: 0.3})          # never buys
    runs = {r["run_id"]: r for r in (holder, n1, n2)}
    eb = {"h": 1}  # only holder holds item_g

    c = L.finalize_contrast(
        L.matched_contrast("item_g", "materials_saturation_frac", runs, eb))
    # post-waves for holder: 2 and 3. baseline w2 = mean(0.5,0.3)=0.4,
    # w3 = mean(0.5,0.3)=0.4. deltas: 0.9-0.4=0.5 each.
    assert c["n_obs"] == 2
    assert c["sum_delta"] == pytest.approx(1.0)
    assert c["mean_delta"] == pytest.approx(0.5)
    assert c["mean_effect"] == pytest.approx(0.5)   # higher_better -> +delta
    assert c["n_obs_positive"] == 2
    assert c["obs_sign_consistency"] == pytest.approx(1.0)
    assert c["n_holdings"] == 1
    assert c["holding_sign_consistency"] == pytest.approx(1.0)


def test_matched_contrast_holder_excluded_from_own_baseline():
    # Two holders that acquire at different waves. A run is a non-holder for a
    # wave only until (and excluding) its own acquisition wave.
    hA = _run("A", "victory", {1: 0.9, 2: 0.9, 3: 0.9}, buys=[(1, "item_g")])
    hB = _run("B", "victory", {1: 0.1, 2: 0.1, 3: 0.9}, buys=[(3, "item_g")])
    runs = {"A": hA, "B": hB}
    eb = {"A": 1, "B": 3}

    c = L.finalize_contrast(
        L.matched_contrast("item_g", "materials_saturation_frac", runs, eb))
    # holder A post-waves 2,3. At w2 non-holders = {B(acq3 >2)} -> baseline 0.1,
    # delta 0.8. At w3 non-holders: B acquired at w3 (eb<=w) -> holder, so no
    # non-holder baseline -> skipped. holder B post-wave: none (>3). So 1 obs.
    assert c["n_obs"] == 1
    assert c["mean_delta"] == pytest.approx(0.8)


def test_matched_contrast_defensive_direction_inverts_effect():
    # damage taken: lower is better -> negative delta is a positive effect.
    holder = _run("h", "victory", {1: 0.0, 2: 0.0}, buys=[(1, "item_armor")],
                  damage={2: 10.0})
    other = _run("o", "defeat", {2: 0.0}, damage={2: 30.0})
    runs = {"h": holder, "o": other}
    eb = {"h": 1}
    c = L.finalize_contrast(
        L.matched_contrast("item_armor", "damage_amount", runs, eb))
    # delta = 10 - 30 = -20 (took less damage); effect = -delta = +20.
    assert c["mean_delta"] == pytest.approx(-20.0)
    assert c["mean_effect"] == pytest.approx(20.0)
    assert c["obs_sign_consistency"] == pytest.approx(1.0)


def test_matched_contrast_skips_waves_without_baseline():
    holder = _run("h", "victory", {1: 0.5, 2: 0.9}, buys=[(1, "item_g")])
    runs = {"h": holder}  # no non-holder runs at all
    eb = {"h": 1}
    c = L.finalize_contrast(
        L.matched_contrast("item_g", "materials_saturation_frac", runs, eb))
    assert c["n_obs"] == 0
    assert c["mean_delta"] is None
    assert c["n_holdings"] == 0


# --------------------------------------------------------------------------- #
# build ledger: insufficient-n flagging
# --------------------------------------------------------------------------- #
def test_build_ledger_insufficient_n_flagging():
    catalog = {"item_g": {"tags": ["pickup"], "effect_keys": []}}
    tiers = {}
    # item bought in only 2 runs -> INSUFFICIENT (min 3).
    r1 = _run("r1", "victory", {1: 0.1, 2: 0.5}, buys=[(1, "item_g")])
    r2 = _run("r2", "defeat", {1: 0.1, 2: 0.5}, buys=[(1, "item_g")])
    r3 = _run("r3", "victory", {1: 0.1, 2: 0.1})
    led = L.build_ledger([r1, r2, r3], catalog, tiers, {}, {}, "camp")
    e = led["items"]["item_g"]
    assert e["n_runs"] == 2
    assert e["insufficient"] is True
    assert e["primary_class"] == "collection"


def test_build_ledger_sufficient_n_collection_is_ambiguous():
    catalog = {"item_g": {"tags": ["pickup"], "effect_keys": []}}
    tiers = {"item_g": {"tier": "D", "source": "wiki"}}
    # 3 holders with higher saturation than a non-holder baseline.
    holders = [_run("h%d" % i, "victory", {1: 0.1, 2: 0.9, 3: 0.9},
                    buys=[(1, "item_g")]) for i in range(3)]
    non = [_run("n%d" % i, "defeat", {2: 0.1, 3: 0.1}) for i in range(3)]
    led = L.build_ledger(holders + non, catalog, tiers, {}, {}, "camp")
    e = led["items"]["item_g"]
    assert e["insufficient"] is False
    assert e["n_runs"] == 3
    sat = e["contrasts"]["materials_saturation_frac"]
    assert sat["value_direction"] == "ambiguous"
    assert sat["mean_delta"] > 0
    assert sat["holding_sign_consistency"] == pytest.approx(1.0)
    # Ambiguous KPI cannot contradict a tier -> no tension claim.
    assert e["tier_tension"] is None


def test_tier_tension_fires_for_good_low_defensive():
    catalog = {"item_a": {"tags": [], "effect_keys": ["stat_armor"]}}
    tiers = {"item_a": {"tier": "A", "source": "wiki"}}
    # 3 holders take MORE damage than baseline (no defensive benefit), tier A.
    holders = [_run("h%d" % i, "victory", {1: 0.0, 2: 0.0, 3: 0.0},
                    buys=[(1, "item_a")], damage={2: 40.0, 3: 40.0})
               for i in range(3)]
    non = [_run("n%d" % i, "defeat", {2: 0.0, 3: 0.0},
               damage={2: 10.0, 3: 10.0}) for i in range(3)]
    led = L.build_ledger(holders + non, catalog, tiers, {}, {}, "camp")
    e = led["items"]["item_a"]
    assert e["primary_class"] == "defensive"
    dmg = e["contrasts"]["damage_amount"]
    assert dmg["mean_effect"] < 0          # took more damage -> negative effect
    assert e["tier_tension"] is not None
    assert "other axes" in e["tier_tension"]


def test_calibration_finalize_median_mean():
    cal = L.finalize_calibration({"values": [10.0, 20.0, 30.0], "per_buy": []})
    assert cal["n"] == 3
    assert cal["median"] == pytest.approx(20.0)
    assert cal["mean"] == pytest.approx(20.0)
    assert cal["sum"] == pytest.approx(60.0)


# --------------------------------------------------------------------------- #
# merge correctness
# --------------------------------------------------------------------------- #
def _tiny_ledger(campaign, sat_delta_run):
    """Build a one-item ledger from a single holder vs single non-holder."""
    catalog = {"item_g": {"tags": ["pickup"], "effect_keys": []}}
    holder = _run("%s_h" % campaign, "victory",
                  {1: 0.0, 2: sat_delta_run}, buys=[(1, "item_g")])
    non = _run("%s_n" % campaign, "defeat", {2: 0.0})
    return L.build_ledger([holder, non], catalog, {}, {}, {}, campaign)


def test_merge_pools_counts_and_contrasts():
    a = _tiny_ledger("cA", 0.4)   # 1 obs, delta 0.4
    b = _tiny_ledger("cB", 0.6)   # 1 obs, delta 0.6
    merged = L.merge_ledgers([a, b])
    assert merged["campaigns"] == ["cA", "cB"]
    assert merged["run_count"] == 4
    e = merged["items"]["item_g"]
    assert e["n_buys"] == 2
    assert e["n_runs"] == 2
    c = e["contrasts"]["materials_saturation_frac"]
    assert c["n_obs"] == 2
    assert c["sum_delta"] == pytest.approx(1.0)
    assert c["mean_delta"] == pytest.approx(0.5)     # pooled mean of 0.4,0.6
    assert c["n_holdings"] == 2
    assert len(c["per_holding"]) == 2


def test_merge_recomputes_insufficiency():
    # each campaign has the item in 2 runs; merged -> 4 runs -> sufficient.
    catalog = {"item_g": {"tags": ["pickup"], "effect_keys": []}}

    def led(camp):
        runs = [_run("%s_h%d" % (camp, i), "victory",
                     {1: 0.0, 2: 0.9}, buys=[(1, "item_g")]) for i in range(2)]
        runs += [_run("%s_n" % camp, "defeat", {2: 0.1})]
        return L.build_ledger(runs, catalog, {}, {}, {}, camp)

    a, b = led("cA"), led("cB")
    assert a["items"]["item_g"]["insufficient"] is True   # 2 runs each
    merged = L.merge_ledgers([a, b])
    assert merged["items"]["item_g"]["n_runs"] == 4
    assert merged["items"]["item_g"]["insufficient"] is False


def test_merge_calibration_pools_values():
    a = {"tool": "wp2_item_ledger", "schema_version": 1, "campaigns": ["a"],
         "run_count": 1, "victory": 1, "defeat": 0, "items": {
             "item_o": {"item_id": "item_o", "classes": ["offense"],
                        "primary_class": "offense", "tags": [], "effect_keys": [],
                        "tier": "A", "tier_source": "wiki", "n_buys": 1,
                        "n_runs": 1, "insufficient": True, "contrasts": {},
                        "calibration": L.finalize_calibration(
                            {"values": [12.0], "per_buy": []}),
                        "tier_tension": None}}}
    b = {"tool": "wp2_item_ledger", "schema_version": 1, "campaigns": ["b"],
         "run_count": 1, "victory": 0, "defeat": 1, "items": {
             "item_o": {"item_id": "item_o", "classes": ["offense"],
                        "primary_class": "offense", "tags": [], "effect_keys": [],
                        "tier": "A", "tier_source": "wiki", "n_buys": 2,
                        "n_runs": 1, "insufficient": True, "contrasts": {},
                        "calibration": L.finalize_calibration(
                            {"values": [8.0, 16.0], "per_buy": []}),
                        "tier_tension": None}}}
    merged = L.merge_ledgers([a, b])
    cal = merged["items"]["item_o"]["calibration"]
    assert cal["n"] == 3
    assert sorted(cal["values"]) == [8.0, 12.0, 16.0]
    assert cal["median"] == pytest.approx(12.0)


# --------------------------------------------------------------------------- #
# tier-table parsing
# --------------------------------------------------------------------------- #
def test_parse_gd_tier_block():
    text = (
        'const ROGUERANKER_ITEM_TIERS := {\n'
        '\t"item_metal_detector": "C",\n'
        '\t"item_potato": "S",\n'
        '}\n'
        'const WIKI_USEFUL_ITEM_TIERS := {\n'
        '\t"item_baby_gecko": "B",\n'
        '\t"item_metal_detector": "A",\n'  # rogueranker should win
        '}\n')
    tiers = L.load_item_tiers(text)
    assert tiers["item_metal_detector"] == {"tier": "C", "source": "rogueranker"}
    assert tiers["item_potato"]["tier"] == "S"
    assert tiers["item_baby_gecko"] == {"tier": "B", "source": "wiki"}
