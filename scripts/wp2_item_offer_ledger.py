#!/usr/bin/env python3
"""Per-item offer -> affordable -> bought ledger over archived teacher runs.

WHY THIS EXISTS
---------------
"Item X was bought 0 times" is equally consistent with "item X was never
offered". A zero is only interpretable next to the size of the input set, so
every row here carries `offers` and the global `boards` denominator alongside
`bought`.

AFFORDABILITY IS COMPUTED HERE, NOT READ FROM `can_buy`
-------------------------------------------------------
`scripts/wp2_shop_selection_diag.py` filtered candidates with
`i.get("affordable") and i.get("can_buy")`. `can_buy` is emitted only for
weapon offers; it is null on non-weapon items. That filter therefore silently
collapsed to WEAPONS ONLY and produced a confident, meaningless zero for items.

This tool defines affordability as `gold >= price` from the board's own `gold`
field, and separately reports how often the `affordable`, `can_buy` and `price`
fields are present/non-null per category, so the filter can be seen to be
non-vacuous.

TELEMETRY LOCATION
------------------
  runs/<run_id>/events.jsonl
    event "purchase_offer"    payload.items[]  (slot, id, price, tier,
                              category, affordable, locked, can_buy, ...)
                              payload.gold, payload.reroll_price
    event "purchase_decision" payload.action = {"type": "shop_buy", "slot": N}
A board is one `purchase_offer` event. The purchase is attributed by matching
`action.slot` against `slot` on the most recent preceding `purchase_offer` of
the same run.

CAUTION: `purchase_offer` is emitted once per shop DECISION TICK, not once per
shop visit. A board the teacher declines to act on is re-emitted byte-identical
on the next tick, so the raw event count over-counts standing offers. Every
count is therefore reported twice: raw (`offers`, `boards`) and with runs of
consecutive identical snapshots collapsed (`offers_dedup`, `boards_dedup`).
Use the dedup figures for "how often was this item ever put in front of the
teacher"; use the raw figures for "how many decision points saw it".

Usage:
  python scripts/wp2_item_offer_ledger.py --runs-dir runs --out ledger.json
        [--run-ids-file F] [--limit-runs N]
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path


def iter_events(path: Path):
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def build_ledger(run_dirs: list[Path]) -> dict:
    offers: Counter = Counter()
    affordable: Counter = Counter()
    bought: Counter = Counter()
    item_tier: dict[str, object] = {}
    item_cat: dict[str, object] = {}

    offers_dedup: Counter = Counter()
    affordable_dedup: Counter = Counter()
    boards_dedup = 0

    boards = 0
    runs_scanned = 0
    runs_without_boards = 0
    buy_decisions = 0
    buys_unmatched = 0

    # field-presence audit, per category
    field_present: dict[str, Counter] = defaultdict(Counter)
    offers_by_cat: Counter = Counter()
    # cross-check: our gold>=price verdict vs the emitted `affordable` flag
    affordable_agree = 0
    affordable_disagree = 0
    affordable_flag_absent = 0
    gold_missing_boards = 0

    for run_dir in run_dirs:
        ev_path = run_dir / "events.jsonl"
        if not ev_path.exists():
            continue
        runs_scanned += 1
        run_boards = 0
        pending: list[dict] = []
        pending_gold = None
        prev_snapshot = None

        for evt in iter_events(ev_path):
            kind = evt.get("event")
            if kind == "purchase_offer":
                payload = evt.get("payload") or {}
                pending = payload.get("items") or []
                pending_gold = payload.get("gold")
                if pending_gold is None:
                    gold_missing_boards += 1
                boards += 1
                run_boards += 1
                snapshot = (pending_gold,
                            tuple((i.get("slot"), i.get("id")) for i in pending))
                is_new_board = snapshot != prev_snapshot
                prev_snapshot = snapshot
                if is_new_board:
                    boards_dedup += 1
                for it in pending:
                    iid = it.get("id")
                    if iid is None:
                        continue
                    cat = it.get("category")
                    offers[iid] += 1
                    if is_new_board:
                        offers_dedup[iid] += 1
                    offers_by_cat[cat] += 1
                    item_tier.setdefault(iid, it.get("tier"))
                    item_cat.setdefault(iid, cat)
                    for f in ("price", "affordable", "can_buy", "tier", "effects"):
                        if it.get(f) is not None:
                            field_present[cat][f] += 1

                    price = it.get("price")
                    aff = None
                    if price is not None and pending_gold is not None:
                        aff = float(pending_gold) >= float(price)
                        if aff:
                            affordable[iid] += 1
                            if is_new_board:
                                affordable_dedup[iid] += 1
                    flag = it.get("affordable")
                    if flag is None:
                        affordable_flag_absent += 1
                    elif aff is not None:
                        if bool(flag) == aff:
                            affordable_agree += 1
                        else:
                            affordable_disagree += 1
                continue

            if kind == "purchase_decision":
                action = (evt.get("payload") or {}).get("action") or {}
                if str(action.get("type", "")) != "shop_buy":
                    continue
                buy_decisions += 1
                slot = action.get("slot")
                hit = next((i for i in pending if i.get("slot") == slot), None)
                if hit is None or hit.get("id") is None:
                    buys_unmatched += 1
                    continue
                bought[hit["id"]] += 1
                # the bought slot is consumed; it cannot be bought again off
                # this same board snapshot
                pending = [i for i in pending if i.get("slot") != slot]

        if run_boards == 0:
            runs_without_boards += 1

    rows = []
    for iid in sorted(offers, key=lambda k: (-offers[k], k)):
        rows.append({
            "id": iid,
            "category": item_cat.get(iid),
            "tier": item_tier.get(iid),
            "offers": offers[iid],
            "affordable": affordable[iid],
            "bought": bought[iid],
            "boards": boards,
            "offers_dedup": offers_dedup[iid],
            "affordable_dedup": affordable_dedup[iid],
            "boards_dedup": boards_dedup,
        })

    never_offered_but_bought = sorted(set(bought) - set(offers))

    per_tier: dict[str, dict] = {}
    for iid in offers:
        key = str(item_tier.get(iid))
        d = per_tier.setdefault(key, {"distinct_ids": 0, "offers": 0,
                                      "affordable": 0, "bought": 0,
                                      "offers_dedup": 0,
                                      "affordable_dedup": 0})
        d["distinct_ids"] += 1
        d["offers"] += offers[iid]
        d["affordable"] += affordable[iid]
        d["bought"] += bought[iid]
        d["offers_dedup"] += offers_dedup[iid]
        d["affordable_dedup"] += affordable_dedup[iid]

    return {
        "totals": {
            "runs_scanned": runs_scanned,
            "runs_without_boards": runs_without_boards,
            "boards": boards,
            "boards_dedup": boards_dedup,
            "offer_slots": sum(offers.values()),
            "offer_slots_dedup": sum(offers_dedup.values()),
            "distinct_ids": len(offers),
            "affordable_offer_slots": sum(affordable.values()),
            "buy_decisions": buy_decisions,
            "buys_attributed": sum(bought.values()),
            "buys_unmatched_to_board": buys_unmatched,
        },
        "field_audit": {
            "offers_by_category": dict(offers_by_cat),
            "non_null_field_counts_by_category":
                {k: dict(v) for k, v in field_present.items()},
            "gold_missing_boards": gold_missing_boards,
            "affordable_flag_vs_gold_ge_price": {
                "agree": affordable_agree,
                "disagree": affordable_disagree,
                "flag_absent": affordable_flag_absent,
            },
        },
        "per_tier": per_tier,
        "items": rows,
        "bought_but_never_seen_on_a_board": never_offered_but_bought,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs-dir", required=True, type=Path)
    ap.add_argument("--run-ids-file", type=Path, default=None)
    ap.add_argument("--limit-runs", type=int, default=None)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    if args.run_ids_file:
        ids = [l.strip() for l in args.run_ids_file.read_text(
            encoding="utf-8").splitlines() if l.strip()]
        run_dirs = [args.runs_dir / i for i in ids]
        missing = [d.name for d in run_dirs if not d.is_dir()]
        if missing:
            print(f"WARNING: {len(missing)} listed run ids absent under "
                  f"{args.runs_dir}: {missing[:5]}")
        run_dirs = [d for d in run_dirs if d.is_dir()]
    else:
        run_dirs = sorted(p for p in args.runs_dir.iterdir() if p.is_dir())

    if args.limit_runs is not None:
        run_dirs = run_dirs[:args.limit_runs]

    ledger = build_ledger(run_dirs)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(ledger, indent=2), encoding="utf-8")

    t = ledger["totals"]
    print(f"runs_scanned={t['runs_scanned']} boards={t['boards']} "
          f"offer_slots={t['offer_slots']} distinct_ids={t['distinct_ids']} "
          f"buys_attributed={t['buys_attributed']} "
          f"unmatched={t['buys_unmatched_to_board']}")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
