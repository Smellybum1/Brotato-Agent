#!/usr/bin/env python3
"""§38 Gate 0: positive-score lexicographic immediate-DPS constraint.

Implements reports/wp2/danger_aware_dps_lexicographic_prereg.md using the
validated §37 replay. Read-only apart from an explicitly requested JSON output.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.wp2_danger_aware_marginal_dps_gate0 import (
    Analysis,
    Decision,
    MEDIAN_GAIN_BAR,
    PER_RUN_UPPER_BAR,
    POSITIVE_FLIP_BAR,
    SURFACE_BAR,
    TOL,
    _argmax,
    _controls,
    _print_controls,
    _summary,
    analyse,
)

LOO_FLOOR = 0.18
LOO_MEDIAN_BAR = 0.20
RUN_COVERAGE_BAR = 12
RUN_CONCENTRATION_CAP = 0.20


def _lexicographic_choice(decision: Decision) -> tuple[dict[str, Any], dict[str, Any] | None]:
    incumbent = _argmax(decision.rows, "score")
    assert incumbent is not None
    if float(incumbent["score"]) <= 0.0:
        return incumbent, None
    positive = [row for row in decision.rows if float(row["score"]) > 0.0]
    best_m = max(float(row["m"]) for row in positive)
    if abs(float(incumbent["m"]) - best_m) <= TOL:
        return incumbent, incumbent
    selected = next(row for row in positive if abs(float(row["m"]) - best_m) <= TOL)
    return incumbent, selected


def constrained_result(analysis: Analysis) -> dict[str, Any]:
    controls, control_failures = _controls(analysis)
    if control_failures:
        return {"status": "VOID", "control_failures": control_failures, "controls": controls}

    flips: list[dict[str, Any]] = []
    per_run_upper: Counter = Counter({run_id: 0.0 for run_id in analysis.run_ids})
    flips_by_run: Counter = Counter({run_id: 0 for run_id in analysis.run_ids})
    flips_by_wave: Counter = Counter()
    transitions: Counter = Counter()
    veto_rows = 0
    total_rows = 0
    higher_m_veto_rows = 0
    nonpositive_incumbents = 0

    for decision in analysis.decisions:
        incumbent, selected = _lexicographic_choice(decision)
        total_rows += len(decision.rows)
        veto_rows += sum(float(row["score"]) <= 0.0 for row in decision.rows)
        higher_m_veto_rows += sum(
            float(row["score"]) <= 0.0
            and float(row["m"]) > float(incumbent["m"]) + TOL
            for row in decision.rows)
        if float(incumbent["score"]) <= 0.0:
            nonpositive_incumbents += 1
        if selected is None or str(selected.get("id")) == str(incumbent.get("id")):
            continue

        delta_m = float(selected["m"]) - float(incumbent["m"])
        score_old = float(incumbent["score"])
        score_new = float(selected["score"])
        per_run_upper[decision.run_id] += delta_m / 100.0
        flips_by_run[decision.run_id] += 1
        flips_by_wave[decision.wave] += 1
        transition = f"{incumbent.get('category')}->{selected.get('category')}"
        transitions[transition] += 1
        flips.append({
            "run_id": decision.run_id,
            "wave": decision.wave,
            "old_id": str(incumbent.get("id")),
            "new_id": str(selected.get("id")),
            "old_category": str(incumbent.get("category")),
            "new_category": str(selected.get("category")),
            "old_m": float(incumbent["m"]),
            "new_m": float(selected["m"]),
            "delta_m": delta_m,
            "old_score": score_old,
            "new_score": score_new,
            "score_sacrificed": score_old - score_new,
            "score_ratio": score_new / score_old,
            "new_method": str(selected.get("gain_method")),
        })

    flip_n = len(flips)
    policy_n = analysis.policy_n
    flip_rate = flip_n / max(policy_n, 1)
    delta_m = [row["delta_m"] for row in flips]
    score_ratio = [row["score_ratio"] for row in flips]
    score_sacrificed = [row["score_sacrificed"] for row in flips]
    per_run_values = [per_run_upper[run_id] for run_id in analysis.run_ids]
    positive_share = (sum(value > TOL for value in delta_m) / flip_n if flip_n else None)

    loo_rows: list[dict[str, Any]] = []
    for run_id in analysis.run_ids:
        denominator = policy_n - int(analysis.policy_by_run[run_id])
        numerator = flip_n - int(flips_by_run[run_id])
        loo_rows.append({
            "left_out_run": run_id,
            "flips": numerator,
            "policy_n": denominator,
            "rate": numerator / max(denominator, 1),
        })
    loo_rates = [row["rate"] for row in loo_rows]
    loo_min = min(loo_rates) if loo_rates else 0.0
    loo_median = statistics.median(loo_rates) if loo_rates else 0.0
    run_coverage = sum(flips_by_run[run_id] > 0 for run_id in analysis.run_ids)
    max_run_flips = max(flips_by_run.values(), default=0)
    max_run_share = max_run_flips / max(flip_n, 1)

    median_gain = statistics.median(delta_m) if delta_m else None
    median_upper = statistics.median(per_run_values) if per_run_values else None
    bars = {
        "flip_surface": {"value": flip_rate, "bar": SURFACE_BAR,
                         "pass": flip_rate >= SURFACE_BAR},
        "median_delta_m": {"value": median_gain, "bar": MEDIAN_GAIN_BAR,
                           "pass": median_gain is not None and median_gain >= MEDIAN_GAIN_BAR},
        "positive_flip_share": {"value": positive_share, "bar": POSITIVE_FLIP_BAR,
                                "pass": positive_share is not None
                                and positive_share >= POSITIVE_FLIP_BAR},
        "median_per_run_upper": {"value": median_upper, "bar": PER_RUN_UPPER_BAR,
                                 "pass": median_upper is not None
                                 and median_upper >= PER_RUN_UPPER_BAR},
        "loo_min": {"value": loo_min, "bar": LOO_FLOOR, "pass": loo_min >= LOO_FLOOR},
        "loo_median": {"value": loo_median, "bar": LOO_MEDIAN_BAR,
                       "pass": loo_median >= LOO_MEDIAN_BAR},
        "run_coverage": {"value": run_coverage, "bar": RUN_COVERAGE_BAR,
                         "pass": run_coverage >= RUN_COVERAGE_BAR},
        "max_run_share": {"value": max_run_share, "cap": RUN_CONCENTRATION_CAP,
                          "pass": max_run_share <= RUN_CONCENTRATION_CAP},
    }
    status = "PASS" if all(row["pass"] for row in bars.values()) else "FAIL"
    failed_bars = [name for name, row in bars.items() if not row["pass"]]

    return {
        "status": status,
        "reason": "pass" if status == "PASS" else "+".join(failed_bars),
        "controls": controls,
        "policy_n": policy_n,
        "eligible_n": len(analysis.decisions),
        "flips": flip_n,
        "flip_rate_policy": flip_rate,
        "bars": bars,
        "gain": {
            "delta_m": _summary(delta_m),
            "positive_flips": sum(value > TOL for value in delta_m),
            "positive_share": positive_share,
            "per_run_upper": _summary(per_run_values),
        },
        "score_safeguard": {
            "vetoed_nonpositive_rows": veto_rows,
            "total_rows": total_rows,
            "veto_rate": veto_rows / max(total_rows, 1),
            "higher_m_rows_vetoed": higher_m_veto_rows,
            "nonpositive_incumbent_decisions": nonpositive_incumbents,
            "selected_to_incumbent_ratio": _summary(score_ratio),
            "score_sacrificed": _summary(score_sacrificed),
        },
        "stability": {
            "flips_by_run": dict(flips_by_run),
            "run_coverage": run_coverage,
            "max_run_flips": max_run_flips,
            "max_run_share": max_run_share,
            "leave_one_run_out": loo_rows,
            "loo_rate": _summary(loo_rates),
        },
        "flips_by_wave": dict(sorted(flips_by_wave.items())),
        "category_transitions": dict(transitions),
        "flips_detail": flips,
    }


def _print_result(result: dict[str, Any]) -> None:
    _print_controls(result)
    print("\n" + "=" * 79)
    print("§38 PREREGISTERED RESULT")
    print("=" * 79)
    if result["status"] == "VOID":
        print("VERDICT: VOID — controls failed")
        for failure in result["control_failures"]:
            print(f"  - {failure}")
        return
    print(f"positive-score lexicographic flips: {result['flips']}/{result['policy_n']} = "
          f"{result['flip_rate_policy']:.4f}")
    for name, row in result["bars"].items():
        bound = row.get("bar", row.get("cap"))
        print(f"{name:24s}: {row['value']}  bound={bound}  "
              f"=> {'PASS' if row['pass'] else 'FAIL'}")
    guard = result["score_safeguard"]
    print(f"nonpositive safeguard veto: {guard['vetoed_nonpositive_rows']}/"
          f"{guard['total_rows']} rows; higher-m vetoed={guard['higher_m_rows_vetoed']}")
    print(f"VERDICT: {result['status']} — {result['reason']}")


def _self_test() -> int:
    base_rows = [
        {"id": "inc", "category": "item", "score": 10.0, "m": 1.0},
        {"id": "pos", "category": "weapon", "score": 1.0, "m": 20.0},
        {"id": "zero", "category": "weapon", "score": 0.0, "m": 30.0},
        {"id": "neg", "category": "weapon", "score": -1.0, "m": 40.0},
    ]
    decision = Decision("r", 1, "inc", 100.0, base_rows, True)
    incumbent, selected = _lexicographic_choice(decision)
    assert incumbent["id"] == "inc" and selected is not None and selected["id"] == "pos"

    tie = Decision("r", 1, "inc", 100.0, [
        {"id": "inc", "category": "item", "score": 10.0, "m": 5.0},
        {"id": "alt", "category": "weapon", "score": 1.0, "m": 5.0},
    ], False)
    incumbent2, selected2 = _lexicographic_choice(tie)
    assert incumbent2["id"] == "inc" and selected2 is not None and selected2["id"] == "inc"

    nonpositive = Decision("r", 1, "inc", 100.0, [
        {"id": "inc", "category": "item", "score": 0.0, "m": 1.0},
        {"id": "alt", "category": "weapon", "score": -1.0, "m": 50.0},
    ], False)
    incumbent3, selected3 = _lexicographic_choice(nonpositive)
    assert incumbent3["id"] == "inc" and selected3 is None
    print("self-test PASS (positive alternative selected, zero/negative vetoed, "
          "DPS tie retains incumbent, nonpositive incumbent unchanged)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs-dir", type=Path)
    parser.add_argument("--json", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        return _self_test()
    if args.runs_dir is None:
        parser.error("--runs-dir is required unless --self-test")
    result = constrained_result(analyse(args.runs_dir))
    _print_result(result)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(f"\nwrote {args.json}")
    return 1 if result["status"] == "VOID" else 0


if __name__ == "__main__":
    raise SystemExit(main())
