#!/usr/bin/env python3
"""Shop-layer conversion diagnostic: does banked gold discriminate wins from losses?

The whole shop evidence chain (v124 rejected, v125 reroll gate, v126 surplus
reroll) rests on one claim: *losers die offense-starved with gold banked*. That
claim was formed on v122-era data and drove three policy versions. Before
designing a fourth, this re-measures it on a matched set of runs where the only
thing that differs is the outcome.

Per shop visit it records what the teacher itself logged — gold entering, gold
left on exit, what it bought, its own offense proxy against its own target, the
exit reason, and whether anything on the exit board was still affordable. It then
splits by run outcome.

Definitions that matter:

  shop exit   the `shop_go` decision. `gold_before` on that decision is the gold
              actually carried out of the shop.
  rich exit   exited while at least one board item was affordable AND the
              teacher's own offense proxy was below its own target. This is the
              v125/v126 failure signature, expressed in the teacher's own terms
              rather than an outside judgement of what it "should" have bought.

Deliberately NOT computed here: whether a given purchase was *correct*. That
needs the marginal-DPS model and is a different question. This answers the prior
one — is there still gold being left behind at all, and does it separate winners
from losers?

Usage:
  python scripts/wp2_shop_conversion_diag.py --runs-dir DIR --run-ids-file F [--json OUT]
"""
from __future__ import annotations

import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any


def iter_events(path: Path):
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


def shop_visits(run_dir: Path) -> tuple[list[dict], str | None]:
    """Reconstruct per-wave shop visits by pairing each offer with its decision."""
    visits: dict[int, dict] = {}
    pending_offer: dict | None = None
    result: str | None = None

    for evt in iter_events(run_dir / "events.jsonl"):
        payload = evt.get("payload", {})
        kind = evt.get("event")
        if kind == "run_end":
            result = str(payload.get("result", "")).lower()
            continue
        if kind == "purchase_offer":
            pending_offer = payload
            continue

        # purchase_decision
        wave = int(payload.get("wave", -1))
        visit = visits.setdefault(wave, {
            "wave": wave, "gold_in": None, "gold_out": None, "bought": [],
            "rerolls": 0, "offense_total": None, "offense_target": None,
            "exit_reason": "", "affordable_at_exit": 0,
            "cheapest_affordable_at_exit": None, "decisions": 0,
        })
        visit["decisions"] += 1

        gold = payload.get("gold_before")
        if visit["gold_in"] is None and gold is not None:
            visit["gold_in"] = int(gold)

        action = payload.get("action") or {}
        atype = str(action.get("type", ""))
        if atype == "shop_buy":
            visit["bought"].append(action.get("item_id"))
        elif atype == "shop_reroll":
            visit["rerolls"] += 1
        elif atype == "shop_go":
            if gold is not None:
                visit["gold_out"] = int(gold)
            visit["exit_reason"] = str(payload.get("exit_reason", ""))
            offense = (payload.get("build_metrics") or {}).get("offense") or {}
            visit["offense_total"] = offense.get("total")
            visit["offense_target"] = offense.get("target")
            # The board the teacher was looking at when it chose to leave.
            board = (pending_offer or {}).get("items", []) or []
            prices = [int(i.get("price", 0)) for i in board
                      if i.get("affordable") and i.get("can_buy")]
            visit["affordable_at_exit"] = len(prices)
            visit["cheapest_affordable_at_exit"] = min(prices) if prices else None

    return [visits[w] for w in sorted(visits)], result


def is_rich_exit(visit: dict) -> bool:
    if visit.get("affordable_at_exit", 0) <= 0:
        return False
    total, target = visit.get("offense_total"), visit.get("offense_target")
    if total is None or target is None:
        return False
    return float(target) > 0 and float(total) < float(target)


def summarize(visits: list[dict]) -> dict:
    mid = [v for v in visits if 9 <= v["wave"] <= 15]
    rich = [v for v in visits if is_rich_exit(v)]
    banked = [v["gold_out"] for v in visits if v["gold_out"] is not None]
    banked_mid = [v["gold_out"] for v in mid if v["gold_out"] is not None]
    deficit = [
        float(v["offense_target"]) - float(v["offense_total"])
        for v in visits
        if v.get("offense_total") is not None and v.get("offense_target") is not None
    ]
    return {
        "shops": len(visits),
        "rich_exits": len(rich),
        "rich_exit_waves": [v["wave"] for v in rich],
        "banked_mean": round(statistics.fmean(banked), 1) if banked else None,
        "banked_max": max(banked) if banked else None,
        "banked_mid_mean": round(statistics.fmean(banked_mid), 1) if banked_mid else None,
        "items_bought": sum(len(v["bought"]) for v in visits),
        "rerolls": sum(v["rerolls"] for v in visits),
        "offense_deficit_mean": round(statistics.fmean(deficit), 2) if deficit else None,
        "final_offense_deficit": round(deficit[-1], 2) if deficit else None,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs-dir", required=True, type=Path)
    ap.add_argument("--run-ids-file", required=True, type=Path)
    ap.add_argument("--json", type=Path)
    args = ap.parse_args()

    run_ids = [ln.strip() for ln in
               args.run_ids_file.read_text(encoding="utf-8").splitlines() if ln.strip()]

    per_run: list[dict] = []
    for run_id in run_ids:
        run_dir = args.runs_dir / run_id
        if not (run_dir / "events.jsonl").exists():
            print(f"  !! missing events for {run_id}")
            continue
        visits, result = shop_visits(run_dir)
        row = {"run_id": run_id, "result": result, **summarize(visits)}
        row["_visits"] = visits
        per_run.append(row)

    print(f"runs analysed: {len(per_run)}")
    print()
    print("== per-run (RAW) ==")
    header = (f"{'run':>22} {'res':>8} {'shops':>5} {'rich':>4} {'bank_mu':>8} "
              f"{'bank_max':>8} {'bank_mid':>8} {'buys':>5} {'rr':>4} {'def_mu':>8} {'def_end':>8}")
    print(header)
    for r in per_run:
        print(f"{r['run_id'][-22:]:>22} {str(r['result']):>8} {r['shops']:>5} "
              f"{r['rich_exits']:>4} {str(r['banked_mean']):>8} {str(r['banked_max']):>8} "
              f"{str(r['banked_mid_mean']):>8} {r['items_bought']:>5} {r['rerolls']:>4} "
              f"{str(r['offense_deficit_mean']):>8} {str(r['final_offense_deficit']):>8}")
    print()

    groups = defaultdict(list)
    for r in per_run:
        groups[r["result"]].append(r)

    print("== by outcome ==")
    fields = ["rich_exits", "banked_mean", "banked_mid_mean", "items_bought",
              "rerolls", "offense_deficit_mean", "final_offense_deficit"]
    print(f"{'metric':>22} " + "".join(f"{g:>14}" for g in sorted(groups)))
    contrasts = {}
    for field in fields:
        cells = []
        vals_by_group = {}
        for g in sorted(groups):
            vals = [r[field] for r in groups[g] if r[field] is not None]
            mu = statistics.fmean(vals) if vals else None
            vals_by_group[g] = mu
            cells.append(f"{mu:>14.2f}" if mu is not None else f"{'-':>14}")
        print(f"{field:>22} " + "".join(cells))
        contrasts[field] = vals_by_group
    print()

    # Rich exits by wave, pooled — where in the run does conversion actually fail?
    by_wave: dict[int, int] = defaultdict(int)
    shops_by_wave: dict[int, int] = defaultdict(int)
    for r in per_run:
        for v in r["_visits"]:
            shops_by_wave[v["wave"]] += 1
            if is_rich_exit(v):
                by_wave[v["wave"]] += 1
    print("== rich exits by wave (pooled over all runs) ==")
    print(f"{'wave':>5} {'shops':>6} {'rich':>5} {'rate':>7}")
    for wave in sorted(shops_by_wave):
        n, k = shops_by_wave[wave], by_wave.get(wave, 0)
        print(f"{wave:>5} {n:>6} {k:>5} {k / n:>7.2f}")
    print()

    # Exit-reason distribution: v126 reason codes are absent pre-v126 runs.
    reasons: dict[str, int] = defaultdict(int)
    for r in per_run:
        for v in r["_visits"]:
            if v["exit_reason"]:
                reasons[v["exit_reason"]] += 1
    print("== exit reasons ==")
    print(dict(sorted(reasons.items(), key=lambda kv: -kv[1])) or "(none logged)")

    if args.json:
        args.json.write_text(json.dumps({
            "runs": [{k: v for k, v in r.items() if k != "_visits"} for r in per_run],
            "per_run_visits": {r["run_id"]: r["_visits"] for r in per_run},
            "contrasts": contrasts,
            "rich_by_wave": {str(w): {"shops": shops_by_wave[w], "rich": by_wave.get(w, 0)}
                             for w in sorted(shops_by_wave)},
            "exit_reasons": dict(reasons),
        }, indent=2), encoding="utf-8")
        print(f"\nwrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
