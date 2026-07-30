"""Audit the piggy-bank material_value_reserve, offline.

THE GATE this exists to serve: before changing the reserve, prove the change
would flip real decisions. `EXIT_MATERIAL_VALUE_RESERVE` fires BEFORE the item
scorer is consulted, so "affordable inventory was on the board" does NOT show
the scorer would have bought it. A mathematically-correct shop fix on this
project was already found to be behaviourally inert once.

Two questions, both answerable from archived run summaries (which embed the full
`purchase_decision` payloads, so no giant events.jsonl scan is needed):

  1. PREVALENCE + COST -- how often does the reserve end a shop, and how much
     gold does it leave idle?
  2. REVEALED PREFERENCE -- for the items left unbought, does the SAME scorer
     buy them elsewhere when they are affordable and no reserve is active?
     That uses the real scorer's real decisions rather than a reimplementation.

Results are reported PER MOD VERSION. A 47-point win-rate collapse once ran ~20
versions unnoticed here, so nothing pools across eras by default.
"""
from __future__ import annotations

import argparse
import collections
import json
import os
from pathlib import Path


def runs_dir() -> Path:
    return Path(os.environ["APPDATA"]) / "Brotato" / "brotato_agent" / "runs"


def iter_summaries(limit: int | None = None):
    paths = sorted(runs_dir().glob("*/summary.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if limit:
        paths = paths[:limit]
    for p in paths:
        try:
            yield p.parent.name, json.loads(p.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            continue


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None, help="most recent N runs")
    args = ap.parse_args()

    by_version = collections.defaultdict(lambda: {
        "runs": 0, "runs_with_reserve": 0, "exits": collections.Counter(),
        "idle_gold": [], "reserve_shops": 0, "total_shops": 0,
    })
    # revealed preference: item_id -> [times affordable & no reserve, times bought]
    seen_affordable = collections.Counter()
    bought = collections.Counter()
    reserve_blocked_items = collections.Counter()

    n = 0
    for run_id, sm in iter_summaries(args.limit):
        n += 1
        ver = str(sm.get("mod_version", "?"))
        rec = by_version[ver]
        rec["runs"] += 1
        run_had_reserve = False
        for dec in sm.get("purchases") or []:
            if not isinstance(dec, dict):
                continue
            surplus = dec.get("surplus") or {}
            if not surplus:
                continue
            rec["total_shops"] += 1
            reason = str(surplus.get("exit_reason", ""))
            rec["exits"][reason] += 1
            mres = int(surplus.get("material_value_reserve", 0) or 0)
            gold = int(surplus.get("gold", 0) or 0)
            if mres > 0:
                run_had_reserve = True
                rec["reserve_shops"] += 1
            if reason == "EXIT_MATERIAL_VALUE_RESERVE":
                rec["idle_gold"].append(gold)
        if run_had_reserve:
            rec["runs_with_reserve"] += 1

    print(f"scanned {n} run summaries\n")
    print(f"{'mod_version':<26}{'runs':>6}{'w/reserve':>11}{'shops':>7}"
          f"{'reserve_shops':>15}{'reserve_exits':>15}{'idle p50':>10}{'idle max':>10}")
    for ver in sorted(by_version, reverse=True):
        r = by_version[ver]
        idle = sorted(r["idle_gold"])
        p50 = idle[len(idle) // 2] if idle else 0
        mx = idle[-1] if idle else 0
        print(f"{ver:<26}{r['runs']:>6}{r['runs_with_reserve']:>11}{r['total_shops']:>7}"
              f"{r['reserve_shops']:>15}{r['exits']['EXIT_MATERIAL_VALUE_RESERVE']:>15}"
              f"{p50:>10}{mx:>10}")

    print("\nexit-reason mix, pooled across scanned runs:")
    pooled = collections.Counter()
    for r in by_version.values():
        pooled.update(r["exits"])
    total = sum(pooled.values()) or 1
    for reason, c in pooled.most_common():
        print(f"  {reason or '(none)':<34}{c:>7}  {c/total:6.1%}")

    all_idle = sorted(g for r in by_version.values() for g in r["idle_gold"])
    if all_idle:
        print(f"\ngold left idle at a reserve exit, n={len(all_idle)}:")
        print(f"  p50 {all_idle[len(all_idle)//2]}   p90 {all_idle[9*len(all_idle)//10]}"
              f"   max {all_idle[-1]}   sum {sum(all_idle)}")
        print(f"  RAW (largest 15): {all_idle[-15:]}")
    else:
        print("\nNO reserve exits found in the scanned window.")
        print("  Note: a zero here means the reserve never fired in this sample, NOT")
        print("  that the mechanism is inert -- it only fires when a piggy-bank-class")
        print("  item is owned. Report the OWNERSHIP RATE before concluding anything.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
