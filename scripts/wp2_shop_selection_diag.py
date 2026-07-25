#!/usr/bin/env python3
"""Shop-layer selection diagnostic: when the teacher bought, was something better offered?

The conversion diagnostic (`wp2_shop_conversion_diag.py`) showed that banked gold
and rich exits do NOT separate wins from losses on the v125 build, while offense
deficit does. That leaves two candidate explanations, which imply opposite work:

  selection   the boards DID offer offense and the buy loop picked something else;
  offer luck  the boards did not offer offense and no policy change can help.

This separates them. For every `shop_buy`, it re-scores the board the teacher was
actually looking at using an exact port of the live
`shop_strategy.gd::_direct_offense_gain()` (imported from `wp2_offer_dps_replay`,
the v124 mirror validated at 121/121 parity), and compares what was bought against
the best affordable alternative.

WHAT THIS DOES NOT CLAIM
------------------------
The teacher maximises `combat_value()`, which prices defence and utility too. It
is therefore NOT an error to buy an item with lower offense gain — often it is
correct. So a raw "bought lower offense than available" count would be a
meaningless indictment.

The measurement is restricted to the condition where the teacher's OWN policy says
offense is the priority: the offense proxy is below the offense target, i.e. the
same guard the v125 reroll gate fires on. Within that, the sharp case is:

  gate-miss   bought an item scoring BELOW the live gate threshold
              (`OFFENSE_IMPACT_MIN_ITEM_GAIN`, currently 6.0) while an affordable
              alternative scoring AT OR ABOVE it sat on the same board.

That is the documented open item from the v125 deploy record — the reroll gate
governs rerolls only, never which item the buy loop selects.

Usage:
  python scripts/wp2_shop_selection_diag.py --runs-dir DIR --run-ids-file F [--json OUT]
"""
from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path

from scripts.wp2_offer_dps_replay import direct_offense_gain, parse_threshold


def iter_shop_stream(path: Path):
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                evt = json.loads(line)
            except json.JSONDecodeError:
                continue
            if evt.get("event") in ("purchase_offer", "purchase_decision", "run_end"):
                yield evt


def affordable_items(board: list[dict]) -> list[dict]:
    return [i for i in board if i.get("affordable") and i.get("can_buy")]


def analyse_run(run_dir: Path, threshold: float) -> tuple[list[dict], str | None]:
    """One record per shop_buy taken while the teacher was offense-deficient."""
    records: list[dict] = []
    pending_board: list[dict] = []
    result: str | None = None

    for evt in iter_shop_stream(run_dir / "events.jsonl"):
        payload = evt.get("payload", {})
        kind = evt.get("event")
        if kind == "run_end":
            result = str(payload.get("result", "")).lower()
            continue
        if kind == "purchase_offer":
            pending_board = payload.get("items", []) or []
            continue

        action = payload.get("action") or {}
        if str(action.get("type", "")) != "shop_buy":
            continue

        offense = (payload.get("build_metrics") or {}).get("offense") or {}
        total, target = offense.get("total"), offense.get("target")
        if total is None or target is None:
            continue
        if not (float(target) > 0 and float(total) < float(target)):
            continue  # not offense-deficient: the gate's guard does not hold

        board = pending_board
        chosen_slot = action.get("slot")
        chosen = next((i for i in board if i.get("slot") == chosen_slot), None)
        if chosen is None:
            continue

        chosen_gain = direct_offense_gain(chosen.get("effects", []) or [])
        alternatives = [i for i in affordable_items(board)
                        if i.get("slot") != chosen_slot]
        alt_gains = [(direct_offense_gain(i.get("effects", []) or []), i)
                     for i in alternatives]
        best_gain, best_item = max(alt_gains, key=lambda t: t[0]) if alt_gains else (None, None)

        records.append({
            "wave": int(payload.get("wave", -1)),
            "gold_before": payload.get("gold_before"),
            "chosen_id": chosen.get("id"),
            "chosen_category": chosen.get("category"),
            "chosen_price": chosen.get("price"),
            "chosen_gain": round(chosen_gain, 2),
            "best_alt_id": best_item.get("id") if best_item else None,
            "best_alt_gain": round(best_gain, 2) if best_gain is not None else None,
            "best_alt_price": best_item.get("price") if best_item else None,
            "n_affordable_alts": len(alternatives),
            "offense_total": round(float(total), 2),
            "offense_target": round(float(target), 2),
            # The sharp case: bought below the gate while a gate-clearing item sat there.
            "gate_miss": (best_gain is not None
                          and chosen_gain < threshold <= best_gain),
            "board_had_gate_clearing": any(g >= threshold for g, _ in alt_gains)
                                       or chosen_gain >= threshold,
        })
    return records, result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs-dir", required=True, type=Path)
    ap.add_argument("--run-ids-file", required=True, type=Path)
    ap.add_argument("--json", type=Path)
    args = ap.parse_args()

    threshold = parse_threshold()
    run_ids = [ln.strip() for ln in
               args.run_ids_file.read_text(encoding="utf-8").splitlines() if ln.strip()]

    all_records: list[dict] = []
    per_run: list[dict] = []
    for run_id in run_ids:
        run_dir = args.runs_dir / run_id
        if not (run_dir / "events.jsonl").exists():
            print(f"  !! missing events for {run_id}")
            continue
        records, result = analyse_run(run_dir, threshold)
        for rec in records:
            rec["run_id"] = run_id
            rec["result"] = result
        all_records.extend(records)
        per_run.append({
            "run_id": run_id, "result": result,
            "deficit_buys": len(records),
            "gate_misses": sum(1 for r in records if r["gate_miss"]),
            "boards_with_gate_item": sum(1 for r in records if r["board_had_gate_clearing"]),
        })

    print(f"live gate threshold OFFENSE_IMPACT_MIN_ITEM_GAIN = {threshold}")
    print(f"runs analysed: {len(per_run)}")
    print(f"buys while offense-deficient: {len(all_records)}")
    print()

    print("== per-run (RAW) ==")
    print(f"{'run':>22} {'res':>8} {'defbuys':>8} {'gatemiss':>9} {'boards_w_gate':>14}")
    for row in per_run:
        print(f"{row['run_id'][-22:]:>22} {str(row['result']):>8} {row['deficit_buys']:>8} "
              f"{row['gate_misses']:>9} {row['boards_with_gate_item']:>14}")
    print()

    total_miss = sum(1 for r in all_records if r["gate_miss"])
    with_gate = sum(1 for r in all_records if r["board_had_gate_clearing"])
    print("== headline ==")
    print(f"  deficit buys                                  : {len(all_records)}")
    print(f"  ...where board had a gate-clearing offense item: {with_gate} "
          f"({with_gate / len(all_records):.1%})" if all_records else "")
    print(f"  ...GATE MISSES (bought < {threshold} with >= {threshold} available): {total_miss} "
          f"({total_miss / len(all_records):.1%})" if all_records else "")
    print()

    by_outcome: dict[str, list[dict]] = defaultdict(list)
    for r in all_records:
        by_outcome[str(r["result"])].append(r)
    print("== by outcome ==")
    for outcome in sorted(by_outcome):
        rows = by_outcome[outcome]
        miss = sum(1 for r in rows if r["gate_miss"])
        gated = sum(1 for r in rows if r["board_had_gate_clearing"])
        print(f"  {outcome:>8}: deficit buys {len(rows):>4}   "
              f"board had gate item {gated:>4} ({gated / len(rows):.1%})   "
              f"gate misses {miss:>3} ({miss / len(rows):.1%})")
    print()

    misses = [r for r in all_records if r["gate_miss"]]
    if misses:
        print("== gate misses, worst 15 by forgone offense gain ==")
        misses.sort(key=lambda r: (r["best_alt_gain"] or 0) - r["chosen_gain"], reverse=True)
        print(f"{'wave':>5} {'res':>8} {'bought':>26} {'gain':>7} {'passed over':>26} "
              f"{'gain':>7} {'gold':>6}")
        for r in misses[:15]:
            print(f"{r['wave']:>5} {str(r['result'])[:8]:>8} {str(r['chosen_id'])[:26]:>26} "
                  f"{r['chosen_gain']:>7} {str(r['best_alt_id'])[:26]:>26} "
                  f"{r['best_alt_gain']:>7} {str(r['gold_before']):>6}")
        print()
        by_wave = Counter(r["wave"] for r in misses)
        print("  gate misses by wave:", dict(sorted(by_wave.items())))
        forgone = [(r["best_alt_gain"] or 0) - r["chosen_gain"] for r in misses]
        print(f"  forgone gain: median {statistics.median(forgone):.1f}, "
              f"max {max(forgone):.1f}")

    if args.json:
        args.json.write_text(json.dumps({
            "threshold": threshold,
            "per_run": per_run,
            "records": all_records,
        }, indent=2), encoding="utf-8")
        print(f"\nwrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
