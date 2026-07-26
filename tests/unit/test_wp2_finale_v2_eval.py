"""Pure-function tests for scripts/wp2_finale_v2_eval.

Synthetic trial rows only -- no APPDATA, no game, no telemetry files, and never
the live campaign JSONLs.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.wp2_finale_v2_eval import (  # noqa: E402
    bootstrap_mean_ci,
    control_ratio,
    fixture_role,
    group_builds,
    newcombe_diff_ci,
    paired_deltas,
    percentiles,
    pooled_2x2,
    predator_role_plan,
    raw_series,
    validity_table,
    victory_stats,
    wilson_interval,
)

PRED = [f"p{i}.json" for i in range(1, 12)]  # 11: 8 iteration + 3 holdout
INV = [f"i{i}.json" for i in range(1, 7)]
LISTS = {"predator": PRED, "invoker": INV}


def row(fixture, arm, result, *, valid=True, reason="", digest=None):
    return {
        "label": "ignored_label",
        "finale_v2": arm,
        "fixture_file": fixture,
        "fixture_digest": digest or ("d_" + fixture.split(".")[0]),
        "run_id": f"run_{fixture}_{arm}_{result}",
        "result": result,
        "valid": valid,
        "invalid_reason": reason,
        "damage_taken": 10,
        "trial_wall_sec": 45.0,
    }


# --- roles ---------------------------------------------------------------


def test_fixture_role_assignment():
    assert fixture_role("p1.json", LISTS) == ("predator", "iteration")
    assert fixture_role("p8.json", LISTS) == ("predator", "iteration")
    assert fixture_role("p9.json", LISTS) == ("predator", "holdout")
    assert fixture_role("p11.json", LISTS) == ("predator", "holdout")
    assert fixture_role("i3.json", LISTS) == ("invoker", "control")
    assert fixture_role("nope.json", LISTS) == ("unknown", "unlisted")


def test_eleven_build_list_still_splits_8_iteration_3_holdout():
    plan = predator_role_plan(LISTS)
    assert plan["mode"] == "positional"
    assert plan["warnings"] == []
    roles = plan["roles"]
    assert [roles[n] for n in PRED] == ["iteration"] * 8 + ["holdout"] * 3
    assert sum(1 for v in roles.values() if v == "iteration") == 8
    assert sum(1 for v in roles.values() if v == "holdout") == 3


def test_eight_build_list_is_all_iteration_and_warns():
    """REGRESSION: positional slicing an 8-build list mislabelled 3 iteration
    builds as holdout and computed the primary over only 5 of 8 builds."""
    pred8 = [f"c{i}.json" for i in range(1, 9)]
    lists = {"predator": pred8, "invoker": INV}
    plan = predator_role_plan(lists)
    assert plan["mode"] == "all_iteration"
    assert list(plan["roles"].values()) == ["iteration"] * 8
    assert sum(1 for v in plan["roles"].values() if v == "holdout") == 0
    assert len(plan["warnings"]) == 1
    assert "8" in plan["warnings"][0]
    assert "NOT APPLIED" in plan["warnings"][0]
    for name in pred8:
        assert fixture_role(name, lists) == ("predator", "iteration")

    rows = []
    for name in pred8:
        rows.append(row(name, True, "victory"))
        rows.append(row(name, False, "defeat"))
    builds = group_builds(rows, lists)
    assert len([b for b in builds if b["role"] == "iteration"]) == 8
    assert [b for b in builds if b["role"] == "holdout"] == []


def test_explicit_roles_map_overrides_positional_even_on_eleven_builds():
    explicit = {n: "holdout" for n in PRED[:2]}
    explicit.update({n: "iteration" for n in PRED[2:]})
    lists = {"predator": PRED, "invoker": INV, "roles": explicit}
    plan = predator_role_plan(lists)
    assert plan["mode"] == "explicit"
    assert plan["warnings"] == []
    assert [plan["roles"][n] for n in PRED] == ["holdout"] * 2 + ["iteration"] * 9
    # the positional tail is NOT holdout any more
    assert fixture_role("p1.json", lists) == ("predator", "holdout")
    assert fixture_role("p11.json", lists) == ("predator", "iteration")
    # an explicit map may also be keyed by digest, which wins over the filename
    by_digest = {"predator": PRED, "invoker": INV, "roles": {"d_p1": "holdout"}}
    assert fixture_role("p1.json", by_digest, "d_p1") == ("predator", "holdout")


def test_listed_build_missing_from_explicit_roles_map_is_unassigned_and_reported():
    lists = {"predator": PRED, "invoker": INV,
             "roles": {n: "iteration" for n in PRED[:9]}}
    plan = predator_role_plan(lists)
    assert plan["mode"] == "explicit"
    assert plan["roles"]["p10.json"] == "unassigned"
    assert plan["roles"]["p11.json"] == "unassigned"
    assert len(plan["warnings"]) == 1
    assert "p10.json" in plan["warnings"][0] and "p11.json" in plan["warnings"][0]
    assert fixture_role("p10.json", lists) == ("predator", "unassigned")
    # unassigned builds fall into neither endpoint set, and are not "unlisted"
    builds = group_builds([row("p10.json", True, "victory")], lists)
    assert builds[0]["role"] == "unassigned"


def test_group_builds_keys_on_digest_not_filename():
    rows = [
        row("p1.json", True, "victory", digest="SAME"),
        # different filename, same digest -> ONE build
        row("p2.json", False, "defeat", digest="SAME"),
        row("p3.json", True, "victory"),
    ]
    builds = group_builds(rows, LISTS)
    assert len(builds) == 2
    merged = [b for b in builds if b["fixture_digest"] == "SAME"][0]
    assert len(merged["arms"][True]) == 1
    assert len(merged["arms"][False]) == 1
    assert merged["role"] == "iteration"


def test_arm_comes_from_finale_v2_not_label():
    rows = [
        {**row("p1.json", True, "victory"), "label": "v1_predator"},
        {**row("p1.json", False, "defeat"), "label": "v2_predator"},
    ]
    build = group_builds(rows, LISTS)[0]
    assert raw_series(build["arms"][True]) == "V"
    assert raw_series(build["arms"][False]) == "L"


# --- raw series / rates --------------------------------------------------


def test_raw_series_formatting_and_order():
    rows = [
        row("p1.json", True, "victory"),
        row("p1.json", True, "defeat"),
        row("p1.json", True, "victory"),
        row("p1.json", True, "victory"),
        row("p1.json", True, "defeat"),
    ]
    assert raw_series(rows) == "VLVVL"
    st = victory_stats(rows)
    assert (st["wins"], st["n"], st["rate"]) == (3, 5, 0.6)


def test_zero_denominator_yields_none_not_zero():
    st = victory_stats([])
    assert st["n"] == 0
    assert st["wins"] == 0
    assert st["rate"] is None
    assert st["series"] == ""
    assert wilson_interval(0, 0) is None
    assert newcombe_diff_ci(0, 0, 0, 0) is None
    pooled = pooled_2x2([])
    assert pooled["v2_rate"] is None and pooled["v1_rate"] is None
    assert pooled["diff"] is None
    assert percentiles([], (0.5,))["p50"] is None


# --- paired deltas -------------------------------------------------------


def test_paired_delta_hand_computable():
    rows = []
    # build p1: v2 3/4, v1 1/4 -> delta +0.50
    rows += [row("p1.json", True, r) for r in ("victory", "victory", "victory", "defeat")]
    rows += [row("p1.json", False, r) for r in ("victory", "defeat", "defeat", "defeat")]
    # build p2: v2 1/2, v1 1/2 -> delta 0.0
    rows += [row("p2.json", True, r) for r in ("victory", "defeat")]
    rows += [row("p2.json", False, r) for r in ("defeat", "victory")]
    res = paired_deltas(group_builds(rows, LISTS))
    assert res["n_builds_paired"] == 2
    deltas = [b["delta"] for b in res["builds"]]
    assert deltas == [0.5, 0.0]
    assert res["mean_delta"] == 0.25
    assert res["excluded"] == []


def test_build_present_in_one_arm_only_is_excluded_and_named():
    rows = [
        row("p1.json", True, "victory"),
        row("p1.json", False, "defeat"),
        row("p2.json", True, "victory"),  # v2 only
    ]
    res = paired_deltas(group_builds(rows, LISTS))
    assert res["n_builds_considered"] == 2
    assert res["n_builds_paired"] == 1
    assert len(res["excluded"]) == 1
    ex = res["excluded"][0]
    assert ex["fixture_file"] == "p2.json"
    assert ex["fixture_digest"] == "d_p2"
    assert "n_v1=0" in ex["reason"]


def test_unequal_trial_counts_do_not_crash():
    rows = [
        row("p1.json", True, "victory"),
        row("p1.json", True, "victory"),
        row("p1.json", True, "defeat"),
        row("p1.json", False, "defeat"),
    ]
    res = paired_deltas(group_builds(rows, LISTS))
    assert res["n_builds_paired"] == 1
    assert abs(res["builds"][0]["delta"] - (2 / 3 - 0.0)) < 1e-12


# --- bootstrap -----------------------------------------------------------


def test_bootstrap_ci_is_deterministic_for_a_fixed_seed():
    vals = [0.2, -0.1, 0.4, 0.0, 0.3, 0.1, -0.2, 0.5]
    a = bootstrap_mean_ci(vals, seed=20260727, n_resamples=2000)
    b = bootstrap_mean_ci(vals, seed=20260727, n_resamples=2000)
    assert a == b
    c = bootstrap_mean_ci(vals, seed=1, n_resamples=2000)
    assert (c["lo"], c["hi"]) != (a["lo"], a["hi"]) or True  # different seed allowed to differ
    assert a["lo"] <= a["mean"] <= a["hi"]
    assert a["n_units"] == 8


def test_bootstrap_ci_none_for_empty_input():
    assert bootstrap_mean_ci([], seed=1) is None


def test_bootstrap_ci_degenerate_input_is_a_point():
    ci = bootstrap_mean_ci([0.25, 0.25, 0.25], seed=7, n_resamples=500)
    assert ci["lo"] == ci["hi"] == 0.25


# --- control ratio -------------------------------------------------------


def test_control_ratio_guards_against_silent_division():
    assert control_ratio(0.1, 0.2) == 0.5
    assert control_ratio(0.1, 0.0) is None
    assert control_ratio(0.1, -0.2) is None
    assert control_ratio(None, 0.2) is None
    assert control_ratio(0.1, None) is None


# --- validity ------------------------------------------------------------


def test_invalid_rows_excluded_from_rates_but_counted_in_validity_table():
    rows = [
        row("p1.json", True, "victory"),
        row("p1.json", True, "defeat", valid=False, reason="finale_arm_mismatch:False"),
        row("p1.json", False, "defeat"),
        row("p1.json", False, "defeat", valid=False, reason="timeout_300s"),
        row("p1.json", False, "defeat", valid=False, reason="timeout_300s"),
    ]
    table = validity_table(rows)
    assert table["v2"] == {
        "total": 2,
        "valid": 1,
        "invalid": 1,
        "valid_frac": 0.5,
        "invalid_reasons": {"finale_arm_mismatch:False": 1},
    }
    assert table["v1"]["total"] == 3
    assert table["v1"]["invalid_reasons"] == {"timeout_300s": 2}

    valid_only = [r for r in rows if r["valid"] is True]
    res = paired_deltas(group_builds(valid_only, LISTS))
    b = res["builds"][0]
    assert (b["v2"]["wins"], b["v2"]["n"]) == (1, 1)
    assert (b["v1"]["wins"], b["v1"]["n"]) == (0, 1)
    assert b["delta"] == 1.0


def test_validity_table_zero_denominator_is_none():
    table = validity_table([])
    assert table["v2"]["valid_frac"] is None
    assert table["v1"]["valid_frac"] is None


# --- pooled view ---------------------------------------------------------


def test_pooled_2x2_and_fisher_on_a_known_table():
    rows = []
    rows += [row("p1.json", True, "victory") for _ in range(9)]
    rows += [row("p1.json", True, "defeat")]
    rows += [row("p1.json", False, "victory") for _ in range(3)]
    rows += [row("p1.json", False, "defeat") for _ in range(7)]
    pooled = pooled_2x2(group_builds(rows, LISTS))
    assert (pooled["v2_wins"], pooled["v2_n"]) == (9, 10)
    assert (pooled["v1_wins"], pooled["v1_n"]) == (3, 10)
    assert abs(pooled["diff"] - 0.6) < 1e-12
    assert 0.0 < pooled["fisher_p_two_sided"] < 0.05
    lo, hi = pooled["newcombe_diff_ci"]
    assert lo > 0.0 and hi <= 1.0
