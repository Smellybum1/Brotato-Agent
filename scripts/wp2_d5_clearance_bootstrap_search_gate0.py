#!/usr/bin/env python3
"""§39 offline Gate 0 for the D5 target-backed one-reroll search planner."""
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

MOD = "0.2.79-wp2-capture"
CHARACTER = "character_ranger"
DANGER = 5
EXPECTED_RUNS = 16
EXPECTED_UNLOCK = (179, 48, "2018397571", "1530875081")
WAVE_MIN = 1
WAVE_MAX = 10
K_PRIMARY = 1.75
K_HIGH = 2.63
D0_TARGETS = (45.0, 110.0, 175.0, 230.0, 300.0, 380.0, 450.0, 540.0,
              645.0, 765.0, 935.0, 1150.0, 1280.0, 1430.0, 1620.0, 1900.0,
              2150.0, 2400.0, 2650.0, 2900.0)

COMPLETENESS_BAR = 0.99
ACTIONABLE_BAR = 0.20
RUN_COVERAGE_BAR = 12
LOO_FLOOR = 0.18
LOO_MEDIAN_BAR = 0.20
RUN_SHARE_CAP = 0.20
YIELD_N_BAR = 30
YIELD_JOIN_BAR = 0.99
YIELD_RATE_BAR = 0.30
IMPACT_FRAC = 0.05
COST_MEDIAN_CAP = 0.10
COST_P90_CAP = 0.25


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _pct(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    pos = (len(ordered) - 1) * q
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return ordered[lo]
    return ordered[lo] * (hi - pos) + ordered[hi] * (pos - lo)


def _summary(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"n": 0}
    return {
        "n": len(values), "min": min(values), "p10": _pct(values, 0.10),
        "p25": _pct(values, 0.25), "median": statistics.median(values),
        "p75": _pct(values, 0.75), "p90": _pct(values, 0.90), "max": max(values),
    }


def _unlock_stamp(summary: dict[str, Any]) -> tuple[Any, ...]:
    pool = summary.get("unlock_pool") or {}
    return (pool.get("items"), pool.get("weapons"), str(pool.get("items_hash")),
            str(pool.get("weapons_hash")))


def _read_purchase_events(path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", errors="replace") as stream:
        for line in stream:
            if '"purchase_decision"' not in line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("event") == "purchase_decision":
                events.append(event)
    return events


def _legal_reroll(payload: dict[str, Any]) -> bool:
    return any(alternative == "shop_reroll"
               or (isinstance(alternative, dict)
                   and alternative.get("type") == "shop_reroll")
               for alternative in payload.get("legal_alternatives", []) or [])


def _operands(payload: dict[str, Any]) -> dict[str, Any]:
    action = payload.get("action") or {}
    offense = ((payload.get("build_metrics") or {}).get("offense") or {})
    surplus = action.get("surplus") or payload.get("surplus") or {}
    return {
        "wave": payload.get("wave"),
        "dps": offense.get("weapon_dps"),
        "target": offense.get("dps_target"),
        "gold": payload.get("gold_before"),
        "reroll_price": payload.get("reroll_price"),
        "locked_reserve": surplus.get("locked_item_reserve"),
        "legal": _legal_reroll(payload),
    }


def _actionable(operands: dict[str, Any], k: float, enabled: bool = True) -> tuple[bool, str]:
    if not enabled:
        return False, "disabled"
    wave = operands.get("wave")
    if not isinstance(wave, int) or not WAVE_MIN <= wave <= WAVE_MAX:
        return False, "wave_outside"
    dps, target = operands.get("dps"), operands.get("target")
    if not _is_number(dps) or not _is_number(target):
        return False, "target_missing"
    if float(dps) >= k * float(target):
        return False, "no_clearance_debt"
    if not operands.get("legal"):
        return False, "reroll_illegal"
    gold = operands.get("gold")
    price = operands.get("reroll_price")
    locked = operands.get("locked_reserve")
    if not all(_is_number(value) for value in (gold, price, locked)):
        return False, "budget_missing"
    if float(gold) - float(locked) < float(price):
        return False, "unaffordable_after_lock"
    return True, "actionable"


def _useful_board(payload: dict[str, Any]) -> tuple[bool, int, int]:
    offense = ((payload.get("build_metrics") or {}).get("offense") or {})
    dps = offense.get("weapon_dps")
    board = payload.get("board_scores")
    if not _is_number(dps) or not isinstance(board, list):
        return False, 0, 0
    useful = 0
    scored_weapons = 0
    for row in board:
        if not isinstance(row, dict) or row.get("category") != "weapon":
            continue
        if row.get("skipped") not in (None, "") or not _is_number(row.get("score")):
            continue
        if float(row["score"]) <= 0.0 or row.get("affordable") is not True:
            continue
        scored_weapons += 1
        gain = row.get("proj_dps_gain")
        if _is_number(gain) and float(gain) >= IMPACT_FRAC * max(float(dps), 1.0):
            useful += 1
    return useful > 0, useful, scored_weapons


def _load_runs(runs_dir: Path) -> tuple[dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    summaries: dict[str, dict[str, Any]] = {}
    for path in runs_dir.glob("*/summary.json"):
        try:
            summary = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            continue
        if str(summary.get("mod_version")) == MOD:
            summaries[path.parent.name] = summary
    events = {run_id: _read_purchase_events(runs_dir / run_id / "events.jsonl")
              for run_id in summaries}
    return summaries, events


def collect(runs_dir: Path) -> dict[str, Any]:
    summaries, events_by_run = _load_runs(runs_dir)
    arm_errors: list[str] = []
    for run_id, summary in summaries.items():
        if summary.get("result") not in ("victory", "defeat"):
            arm_errors.append(f"{run_id}: nonterminal")
        if int(summary.get("danger", -1)) != DANGER or not bool(summary.get("danger_ok")):
            arm_errors.append(f"{run_id}: danger")
        if str(summary.get("character")) != CHARACTER or not bool(summary.get("character_ok")):
            arm_errors.append(f"{run_id}: character")
        if _unlock_stamp(summary) != EXPECTED_UNLOCK:
            arm_errors.append(f"{run_id}: unlock {_unlock_stamp(summary)!r}")

    exits_by_run: Counter = Counter({run_id: 0 for run_id in summaries})
    actionable_by_run: Counter = Counter({run_id: 0 for run_id in summaries})
    high_actionable_by_run: Counter = Counter({run_id: 0 for run_id in summaries})
    unchanged: Counter = Counter()
    target_complete = budget_complete = 0
    legal_count = legal_unaffordable = 0
    exit_n = 0
    actionables: list[dict[str, Any]] = []
    high_actionable_n = 0
    null_flips = 0

    deficient_actual_rerolls = 0
    reroll_joined = 0
    useful_boards = 0
    useful_rows = 0
    scored_weapon_rows = 0
    reroll_by_wave: Counter = Counter()
    useful_by_wave: Counter = Counter()

    for run_id in sorted(events_by_run):
        purchase_events = events_by_run[run_id]
        for index, event in enumerate(purchase_events):
            payload = event.get("payload") or {}
            action = payload.get("action") or {}
            operands = _operands(payload)
            wave = operands.get("wave")

            if action.get("type") == "shop_go" and isinstance(wave, int) and WAVE_MIN <= wave <= WAVE_MAX:
                exit_n += 1
                exits_by_run[run_id] += 1
                if _is_number(operands["dps"]) and _is_number(operands["target"]):
                    target_complete += 1
                if all(_is_number(operands[key])
                       for key in ("gold", "reroll_price", "locked_reserve")):
                    budget_complete += 1
                if operands["legal"]:
                    legal_count += 1
                    if (all(_is_number(operands[key])
                            for key in ("gold", "reroll_price", "locked_reserve"))
                            and float(operands["gold"]) - float(operands["locked_reserve"])
                            < float(operands["reroll_price"])):
                        legal_unaffordable += 1
                is_actionable, reason = _actionable(operands, K_PRIMARY)
                unchanged[reason] += 1
                disabled, _ = _actionable(operands, K_PRIMARY, enabled=False)
                null_flips += int(disabled)
                if is_actionable:
                    actionable_by_run[run_id] += 1
                    cost_ratio = float(operands["reroll_price"]) / max(float(operands["gold"]), 1.0)
                    actionables.append({
                        "run_id": run_id, "wave": wave, "dps": float(operands["dps"]),
                        "target": K_PRIMARY * float(operands["target"]),
                        "target_ratio": float(operands["dps"]) / (K_PRIMARY * float(operands["target"])),
                        "gold": float(operands["gold"]),
                        "reroll_price": float(operands["reroll_price"]),
                        "locked_reserve": float(operands["locked_reserve"]),
                        "cost_ratio": cost_ratio,
                    })
                high_actionable, _ = _actionable(operands, K_HIGH)
                if high_actionable:
                    high_actionable_n += 1
                    high_actionable_by_run[run_id] += 1

            if action.get("type") != "shop_reroll" or not isinstance(wave, int):
                continue
            if not WAVE_MIN <= wave <= WAVE_MAX:
                continue
            if not (_is_number(operands["dps"]) and _is_number(operands["target"])):
                continue
            if float(operands["dps"]) >= K_PRIMARY * float(operands["target"]):
                continue
            deficient_actual_rerolls += 1
            reroll_by_wave[wave] += 1
            if index + 1 >= len(purchase_events):
                continue
            next_payload = purchase_events[index + 1].get("payload") or {}
            if next_payload.get("wave") != wave or not isinstance(next_payload.get("board_scores"), list):
                continue
            reroll_joined += 1
            hit, n_useful, n_scored = _useful_board(next_payload)
            useful_boards += int(hit)
            useful_rows += n_useful
            scored_weapon_rows += n_scored
            useful_by_wave[wave] += int(hit)

    return {
        "run_ids": sorted(summaries), "arm_errors": arm_errors,
        "exit_n": exit_n, "exits_by_run": exits_by_run,
        "actionable_by_run": actionable_by_run,
        "high_actionable_by_run": high_actionable_by_run,
        "actionables": actionables, "high_actionable_n": high_actionable_n,
        "unchanged": unchanged, "target_complete": target_complete,
        "budget_complete": budget_complete, "legal_count": legal_count,
        "legal_unaffordable": legal_unaffordable, "null_flips": null_flips,
        "deficient_actual_rerolls": deficient_actual_rerolls,
        "reroll_joined": reroll_joined, "useful_boards": useful_boards,
        "useful_rows": useful_rows, "scored_weapon_rows": scored_weapon_rows,
        "reroll_by_wave": reroll_by_wave, "useful_by_wave": useful_by_wave,
    }


def build_result(data: dict[str, Any]) -> dict[str, Any]:
    exit_n = data["exit_n"]
    target_rate = data["target_complete"] / max(exit_n, 1)
    budget_rate = data["budget_complete"] / max(exit_n, 1)
    control_failures: list[str] = []
    if len(data["run_ids"]) != EXPECTED_RUNS:
        control_failures.append(f"run_count {len(data['run_ids'])} != {EXPECTED_RUNS}")
    control_failures.extend(data["arm_errors"])
    if target_rate < COMPLETENESS_BAR:
        control_failures.append(f"target_complete {target_rate:.4f} < {COMPLETENESS_BAR}")
    if budget_rate < COMPLETENESS_BAR:
        control_failures.append(f"budget_complete {budget_rate:.4f} < {COMPLETENESS_BAR}")
    if data["legal_count"] == 0:
        control_failures.append("no legal reroll positive control")
    if data["legal_unaffordable"] == 0:
        control_failures.append("no unaffordable-after-lock negative branch")
    if data["null_flips"] != 0:
        control_failures.append(f"null rule changed {data['null_flips']} exits")

    controls = {
        "run_count": len(data["run_ids"]), "arm_errors": data["arm_errors"],
        "exit_n": exit_n,
        "target_complete": {"ok": data["target_complete"], "total": exit_n,
                            "rate": target_rate, "bar": COMPLETENESS_BAR},
        "budget_complete": {"ok": data["budget_complete"], "total": exit_n,
                            "rate": budget_rate, "bar": COMPLETENESS_BAR},
        "legal_rerolls": {"legal": data["legal_count"], "total": exit_n},
        "unaffordable_after_lock": data["legal_unaffordable"],
        "null_flips": data["null_flips"],
    }
    if control_failures:
        return {"status": "VOID", "control_failures": control_failures, "controls": controls}

    actionable_n = len(data["actionables"])
    actionable_rate = actionable_n / max(exit_n, 1)
    run_ids = data["run_ids"]
    run_coverage = sum(data["actionable_by_run"][run_id] > 0 for run_id in run_ids)
    loo: list[dict[str, Any]] = []
    for run_id in run_ids:
        denominator = exit_n - data["exits_by_run"][run_id]
        numerator = actionable_n - data["actionable_by_run"][run_id]
        loo.append({"left_out_run": run_id, "actionable": numerator,
                    "exits": denominator, "rate": numerator / max(denominator, 1)})
    loo_rates = [row["rate"] for row in loo]
    max_run_actions = max(data["actionable_by_run"].values(), default=0)
    max_run_share = max_run_actions / max(actionable_n, 1)

    yield_join_rate = data["reroll_joined"] / max(data["deficient_actual_rerolls"], 1)
    yield_rate = data["useful_boards"] / max(data["reroll_joined"], 1)
    cost_ratios = [row["cost_ratio"] for row in data["actionables"]]
    cost_summary = _summary(cost_ratios)
    locked_preserved = sum(
        row["gold"] - row["locked_reserve"] >= row["reroll_price"]
        for row in data["actionables"])
    locked_rate = locked_preserved / max(actionable_n, 1)

    bars = {
        "actionable_rate": {"value": actionable_rate, "bar": ACTIONABLE_BAR,
                            "pass": actionable_rate >= ACTIONABLE_BAR},
        "run_coverage": {"value": run_coverage, "bar": RUN_COVERAGE_BAR,
                         "pass": run_coverage >= RUN_COVERAGE_BAR},
        "loo_min": {"value": min(loo_rates) if loo_rates else 0.0, "bar": LOO_FLOOR,
                    "pass": bool(loo_rates) and min(loo_rates) >= LOO_FLOOR},
        "loo_median": {"value": statistics.median(loo_rates) if loo_rates else 0.0,
                       "bar": LOO_MEDIAN_BAR,
                       "pass": bool(loo_rates) and statistics.median(loo_rates) >= LOO_MEDIAN_BAR},
        "max_run_share": {"value": max_run_share, "cap": RUN_SHARE_CAP,
                          "pass": max_run_share <= RUN_SHARE_CAP},
        "yield_n": {"value": data["reroll_joined"], "bar": YIELD_N_BAR,
                    "pass": data["reroll_joined"] >= YIELD_N_BAR},
        "yield_join": {"value": yield_join_rate, "bar": YIELD_JOIN_BAR,
                       "pass": yield_join_rate >= YIELD_JOIN_BAR},
        "useful_board_yield": {"value": yield_rate, "bar": YIELD_RATE_BAR,
                               "pass": yield_rate >= YIELD_RATE_BAR},
        "cost_median": {"value": cost_summary.get("median"), "cap": COST_MEDIAN_CAP,
                        "pass": cost_summary.get("median") is not None
                        and cost_summary["median"] <= COST_MEDIAN_CAP},
        "cost_p90": {"value": cost_summary.get("p90"), "cap": COST_P90_CAP,
                     "pass": cost_summary.get("p90") is not None
                     and cost_summary["p90"] <= COST_P90_CAP},
        "locked_preserved": {"value": locked_rate, "bar": 1.0,
                             "pass": locked_rate == 1.0},
    }
    failed = [name for name, row in bars.items() if not row["pass"]]
    targets = {str(wave): {"d0": D0_TARGETS[wave - 1],
                           "primary": K_PRIMARY * D0_TARGETS[wave - 1],
                           "high": K_HIGH * D0_TARGETS[wave - 1]}
               for wave in range(WAVE_MIN, WAVE_MAX + 1)}
    return {
        "status": "PASS" if not failed else "FAIL",
        "reason": "pass" if not failed else "+".join(failed),
        "controls": controls,
        "derivation": {"observed_d5_ratio": 1.314, "health_low": 0.75,
                       "k_primary": K_PRIMARY, "health_high": 0.50,
                       "k_high": K_HIGH, "targets": targets},
        "exits": {"total": exit_n, "unchanged_reasons": dict(data["unchanged"]),
                  "by_run": dict(data["exits_by_run"])},
        "primary": {"actionable": actionable_n, "rate": actionable_rate,
                    "by_run": dict(data["actionable_by_run"]),
                    "details": data["actionables"]},
        "high_sensitivity": {"actionable": data["high_actionable_n"],
                             "rate": data["high_actionable_n"] / max(exit_n, 1),
                             "by_run": dict(data["high_actionable_by_run"])},
        "stability": {"run_coverage": run_coverage, "max_run_actions": max_run_actions,
                      "max_run_share": max_run_share, "leave_one_run_out": loo,
                      "loo_rates": _summary(loo_rates)},
        "observed_search_yield": {
            "target_deficient_actual_rerolls": data["deficient_actual_rerolls"],
            "joined_next_boards": data["reroll_joined"],
            "join_rate": yield_join_rate, "useful_boards": data["useful_boards"],
            "useful_board_rate": yield_rate, "useful_weapon_rows": data["useful_rows"],
            "positive_affordable_scored_weapon_rows": data["scored_weapon_rows"],
            "actual_rerolls_by_wave": dict(sorted(data["reroll_by_wave"].items())),
            "useful_boards_by_wave": dict(sorted(data["useful_by_wave"].items())),
        },
        "cost_ratio": cost_summary, "bars": bars,
    }


def _print_result(result: dict[str, Any]) -> None:
    controls = result["controls"]
    print("=" * 79)
    print("DENOMINATORS AND CONTROLS — BEFORE RESULTS")
    print("=" * 79)
    print(f"runs: {controls['run_count']} (required {EXPECTED_RUNS})")
    print(f"shop_go denominator, waves {WAVE_MIN}-{WAVE_MAX}: {controls['exit_n']}")
    for key in ("target_complete", "budget_complete"):
        row = controls[key]
        print(f"{key:24s}: {row['ok']}/{row['total']} = {row['rate']:.4f} "
              f"(bar {row['bar']:.2f})")
    print(f"legal rerolls: {controls['legal_rerolls']['legal']}/"
          f"{controls['legal_rerolls']['total']}")
    print(f"unaffordable-after-lock negative branch: {controls['unaffordable_after_lock']}/"
          f"{controls['exit_n']}")
    print(f"disabled/null flips: {controls['null_flips']}/{controls['exit_n']} (required 0)")
    print("\n" + "=" * 79)
    print("§39 PREREGISTERED RESULT")
    print("=" * 79)
    if result["status"] == "VOID":
        print("VERDICT: VOID — controls failed")
        for failure in result["control_failures"]:
            print(f"  - {failure}")
        return
    primary = result["primary"]
    print(f"target-backed rerolls: {primary['actionable']}/{result['exits']['total']} = "
          f"{primary['rate']:.4f}")
    observed = result["observed_search_yield"]
    print(f"observed deficient reroll yield: {observed['useful_boards']}/"
          f"{observed['joined_next_boards']} = {observed['useful_board_rate']:.4f} "
          f"(joined {observed['joined_next_boards']}/"
          f"{observed['target_deficient_actual_rerolls']})")
    for name, row in result["bars"].items():
        bound = row.get("bar", row.get("cap"))
        print(f"{name:24s}: {row['value']}  bound={bound}  "
              f"=> {'PASS' if row['pass'] else 'FAIL'}")
    print(f"VERDICT: {result['status']} — {result['reason']}")


def _self_test() -> int:
    base = {"wave": 10, "dps": 100.0, "target": 100.0, "gold": 20,
            "reroll_price": 5, "locked_reserve": 10, "legal": True}
    assert _actionable(base, 1.75) == (True, "actionable")
    assert _actionable({**base, "dps": 180.0}, 1.75)[1] == "no_clearance_debt"
    assert _actionable({**base, "legal": False}, 1.75)[1] == "reroll_illegal"
    assert _actionable({**base, "gold": 14}, 1.75)[1] == "unaffordable_after_lock"
    assert _actionable({**base, "wave": 11}, 1.75)[1] == "wave_outside"
    assert _actionable(base, 1.75, enabled=False) == (False, "disabled")
    useful_payload = {
        "build_metrics": {"offense": {"weapon_dps": 100}},
        "board_scores": [
            {"category": "weapon", "score": 1, "affordable": True,
             "proj_dps_gain": 5, "skipped": None},
            {"category": "weapon", "score": 10, "affordable": True,
             "proj_dps_gain": 4, "skipped": None},
        ],
    }
    assert _useful_board(useful_payload) == (True, 1, 2)
    useful_payload["board_scores"][0]["score"] = 0
    assert _useful_board(useful_payload) == (False, 0, 1)
    print("self-test PASS (debt action, no-debt/illegal/locked/wave/null vetoes, "
          "useful-board positive and zero-score negative controls)")
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
    result = build_result(collect(args.runs_dir))
    _print_result(result)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(f"\nwrote {args.json}")
    return 1 if result["status"] == "VOID" else 0


if __name__ == "__main__":
    raise SystemExit(main())
