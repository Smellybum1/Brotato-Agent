#!/usr/bin/env python3
"""v126 surplus-reroll audit mirror.

Read-only. Replays the shop stream of one or more runs and re-derives the v126
bounded surplus-reroll decision from the arithmetic the teacher itself logged
(`purchase_decision.surplus`), then reports two classes of violation:

  * ``surplus_exit`` — the shop was exited (``shop_go``) while every surplus-rule
    condition still held (in window, reroll budget available, and
    ``spendable_surplus - reroll_price > 0``). That is the v125 rich-exit failure
    v126 exists to remove; under v126 it must never happen.
  * ``reason_code`` — the logged ``exit_reason`` does not match the code
    recomputed from the logged state. This is the reason-code consistency check
    from the design note (v2 §"Exit reason codes").

Supporting counts: surplus rerolls per shop (must never exceed
``SURPLUS_REROLLS_MAX``), unknown reason codes, and stale-board barrier events.

The recomputation below is an exact mirror of
``teacher/shop_strategy.gd::_surplus_state``; the constants are parsed out of
``teacher/config.gd`` so the two cannot drift silently.

Usage:
    python scripts/wp2_v126_shop_audit.py --runs-dir PATH [--run-id ID ...]
"""
from __future__ import annotations

import argparse
import json
import os
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "mod" / "mods-unpacked" / "Tom-BrotatoAgent" / "teacher" / "config.gd"

EXIT_NO_SURPLUS = "EXIT_NO_SURPLUS"
EXIT_REROLL_LIMIT = "EXIT_REROLL_LIMIT"
EXIT_LOCKED_RESERVE = "EXIT_LOCKED_RESERVE"
EXIT_MATERIAL_VALUE_RESERVE = "EXIT_MATERIAL_VALUE_RESERVE"
EXIT_NEXT_SHOP_RESERVE = "EXIT_NEXT_SHOP_RESERVE"
EXIT_NO_SAFE_POSITIVE_ITEM = "EXIT_NO_SAFE_POSITIVE_ITEM"
EXIT_BOARD_STALE_TIMEOUT = "EXIT_BOARD_STALE_TIMEOUT"

REASON_CODES = frozenset({
    EXIT_NO_SURPLUS, EXIT_REROLL_LIMIT, EXIT_LOCKED_RESERVE,
    EXIT_MATERIAL_VALUE_RESERVE, EXIT_NEXT_SHOP_RESERVE,
    EXIT_NO_SAFE_POSITIVE_ITEM, EXIT_BOARD_STALE_TIMEOUT,
})


def config_int(name: str, default: int) -> int:
    """Read a policy constant out of config.gd, or FAIL LOUDLY.

    This used to fall back to `default` when the regex missed. That is the same
    defect class as an audit filter that can never match: a renamed, reformatted or
    deleted constant would leave the audit silently checking the WRONG value and
    still reporting zero violations. `can_buy` (null for every non-weapon offer, so
    "0 gate misses" was vacuous) and `dropped_counts` (hardcoded 0) are the two
    other instances in this project.

    The default is retained only as the documented expected value, so a drift is
    reported with both numbers rather than swallowed.
    """
    match = re.search(rf"^const {name} := (-?\d+)$", CONFIG.read_text(encoding="utf-8"),
                      re.MULTILINE)
    if match is None:
        raise SystemExit(
            f"AUDIT ABORTED: could not parse `const {name} := <int>` from {CONFIG}.\n"
            f"The audit mirrors this policy constant; without it the mirror would be "
            f"checked against a stale hardcoded {default} and would report zero "
            f"violations while testing the wrong rule. Fix the parser or the "
            f"constant -- do not let this fall back."
        )
    return int(match.group(1))


SURPLUS_REROLLS_MAX = config_int("SURPLUS_REROLLS_MAX", 3)
SURPLUS_MIN_WAVE = config_int("SURPLUS_MIN_WAVE", 6)
SURPLUS_MAX_WAVE = config_int("SURPLUS_MAX_WAVE", 19)
SHOP_MAX_REROLLS_CAP = config_int("SHOP_MAX_REROLLS_CAP", 28)


def rule_holds(surplus: dict) -> bool:
    """Exact mirror of the surplus rule's fire condition."""
    if not surplus.get("in_window", False):
        return False
    if int(surplus.get("surplus_rerolls", 0)) >= int(
            surplus.get("surplus_rerolls_max", SURPLUS_REROLLS_MAX)):
        return False
    spendable = int(surplus.get("spendable_surplus", 0))
    return spendable - int(surplus.get("reroll_price", 0)) > 0


def recompute_reason(surplus: dict, board_has_safe_positive_item: bool | None) -> str:
    """Exact mirror of `_surplus_state`'s reason-code precedence.

    ``board_has_safe_positive_item`` is not recoverable from the logged
    arithmetic alone; when it is unknown, the two budget-exhausted codes are
    both accepted (the caller treats them as one bucket).
    """
    if not surplus.get("in_window", False):
        return EXIT_NO_SURPLUS
    budget_exhausted = (
        int(surplus.get("surplus_rerolls", 0))
        >= int(surplus.get("surplus_rerolls_max", SURPLUS_REROLLS_MAX))
    )
    if budget_exhausted:
        if board_has_safe_positive_item is None:
            return EXIT_REROLL_LIMIT
        return (EXIT_REROLL_LIMIT if board_has_safe_positive_item
                else EXIT_NO_SAFE_POSITIVE_ITEM)
    spendable = int(surplus.get("spendable_surplus", 0))
    price = int(surplus.get("reroll_price", 0))
    if spendable - price > 0:
        return ""  # the rule fires; there is no exit
    locked = int(surplus.get("locked_item_reserve", 0))
    material = int(surplus.get("material_value_reserve", 0))
    next_shop = int(surplus.get("next_shop_reserve", 0))
    if locked > 0 and spendable + locked - price > 0:
        return EXIT_LOCKED_RESERVE
    if material > 0 and spendable + material - price > 0:
        return EXIT_MATERIAL_VALUE_RESERVE
    if next_shop > 0 and spendable + next_shop - price > 0:
        return EXIT_NEXT_SHOP_RESERVE
    return EXIT_NO_SURPLUS


BUDGET_CODES = frozenset({EXIT_REROLL_LIMIT, EXIT_NO_SAFE_POSITIVE_ITEM})


def audit_events(events, run_id: str = "") -> dict:
    """Audit one run's event stream (an iterable of decoded telemetry events)."""
    surplus_exit_violations: list[dict] = []
    reason_code_violations: list[dict] = []
    budget_violations: list[dict] = []
    unknown_reason_codes: list[dict] = []
    surplus_rerolls_by_wave: dict[int, int] = defaultdict(int)
    decisions = 0
    surplus_rerolls = 0
    exits_with_reason = 0
    reason_counts: dict[str, int] = defaultdict(int)
    stale_timeouts = 0
    confirmed_refreshes = 0

    for event in events:
        name = event.get("event")
        payload = event.get("payload", {}) or {}
        if name == "shop_surplus_stale_timeout":
            stale_timeouts += 1
            continue
        if name == "shop_surplus_reroll_confirmed":
            confirmed_refreshes += 1
            continue
        if name != "purchase_decision":
            continue
        decisions += 1
        action = payload.get("action", {}) or {}
        surplus = payload.get("surplus", {}) or {}
        wave = payload.get("wave")
        if action.get("type") == "shop_reroll" and action.get("surplus_reroll", False):
            surplus_rerolls += 1
            surplus_rerolls_by_wave[wave] += 1
            if surplus_rerolls_by_wave[wave] > SURPLUS_REROLLS_MAX:
                budget_violations.append({
                    "run": run_id, "wave": wave,
                    "surplus_rerolls": surplus_rerolls_by_wave[wave],
                    "max": SURPLUS_REROLLS_MAX,
                })
            continue
        if action.get("type") != "shop_go":
            continue
        logged_reason = str(payload.get("exit_reason", "") or action.get("exit_reason", ""))
        if not surplus:
            continue  # pre-v126 stream, or an exit produced by a guard path
        exits_with_reason += 1
        reason_counts[logged_reason] += 1
        if logged_reason not in REASON_CODES:
            unknown_reason_codes.append({
                "run": run_id, "wave": wave, "exit_reason": logged_reason,
            })
        # 1) The surplus rule must not have held at a bare exit.
        if rule_holds(surplus):
            surplus_exit_violations.append({
                "run": run_id, "wave": wave, "exit_reason": logged_reason,
                "surplus": surplus,
            })
        # 2) Reason-code consistency against the logged state.
        expected = recompute_reason(surplus, None)
        consistent = (logged_reason == expected
                      or (expected in BUDGET_CODES and logged_reason in BUDGET_CODES))
        if not consistent:
            reason_code_violations.append({
                "run": run_id, "wave": wave, "logged": logged_reason,
                "expected": expected, "surplus": surplus,
            })

    return {
        "run": run_id,
        "purchase_decisions": decisions,
        "surplus_rerolls": surplus_rerolls,
        "surplus_exits_with_reason": exits_with_reason,
        "reason_code_counts": dict(reason_counts),
        "confirmed_board_refreshes": confirmed_refreshes,
        "stale_board_timeouts": stale_timeouts,
        "surplus_exit_violations": surplus_exit_violations,
        "reason_code_violations": reason_code_violations,
        "surplus_budget_violations": budget_violations,
        "unknown_reason_codes": unknown_reason_codes,
        "violation_count": (len(surplus_exit_violations) + len(reason_code_violations)
                            + len(budget_violations) + len(unknown_reason_codes)),
    }


def iter_events(path: Path):
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def audit_runs(runs_dir: Path, run_ids=None) -> dict:
    runs = []
    for run_dir in sorted(runs_dir.iterdir()):
        if run_ids and run_dir.name not in run_ids:
            continue
        events_path = run_dir / "events.jsonl"
        if not events_path.is_file():
            continue
        runs.append(audit_events(iter_events(events_path), run_dir.name))
    return {
        "run_count": len(runs),
        "violation_count": sum(r["violation_count"] for r in runs),
        "surplus_rerolls": sum(r["surplus_rerolls"] for r in runs),
        "stale_board_timeouts": sum(r["stale_board_timeouts"] for r in runs),
        "runs": runs,
    }


def render_markdown(audit: dict) -> str:
    lines = [
        "# v126 surplus-reroll audit",
        "",
        f"- runs: **{audit['run_count']}**",
        f"- surplus rerolls: **{audit['surplus_rerolls']}**",
        f"- stale-board timeouts: **{audit['stale_board_timeouts']}**",
        f"- violations: **{audit['violation_count']}**",
        "",
        "| run | decisions | surplus rerolls | reasoned exits | violations |",
        "|---|---|---|---|---|",
    ]
    for run in audit["runs"]:
        lines.append(
            f"| {run['run']} | {run['purchase_decisions']} | {run['surplus_rerolls']} | "
            f"{run['surplus_exits_with_reason']} | {run['violation_count']} |"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--runs-dir", type=Path,
        default=Path(os.environ.get("APPDATA", "")) / "Brotato" / "brotato_agent" / "runs")
    parser.add_argument("--run-id", action="append", default=[])
    parser.add_argument("--output-prefix", default="v126_surplus_audit")
    args = parser.parse_args()
    audit = audit_runs(args.runs_dir, set(args.run_id) or None)
    output_dir = ROOT / "reports" / "wp2"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / f"{args.output_prefix}.json").write_text(
        json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    (output_dir / f"{args.output_prefix}.md").write_text(
        render_markdown(audit), encoding="utf-8")
    print(json.dumps({k: v for k, v in audit.items() if k != "runs"}, indent=2))
    return 0 if audit["violation_count"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
