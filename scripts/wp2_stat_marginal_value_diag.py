#!/usr/bin/env python3
"""What is +1 offense stat point ACTUALLY worth, against the real equipped loadout?

`shop_strategy.gd::_direct_offense_gain()` scores stat_ranged_damage,
stat_percent_damage and stat_attack_speed as **equal raw points**, and
`decide_levelup()` ranks offense-deficient options by `score0 + gain0 * 6.0`, so
that equal-weight term dominates level-up selection. The same file prices WEAPONS
by real marginal DPS. This measures the size of that inconsistency.

attack_speed and percent_damage are closed-form (`1/(100+stat)`) and were already
quantified without a loadout. **ranged_damage is not** — it enters `flat` damage
through each weapon's own scaling coefficient, so it needs the equipped loadout,
and it is exactly the stat the outcome data points at (losers end ~27% lower on
it). This closes that gap by reconstructing the loadout at every shop and pricing
all three stats identically:

    marginal_dps(stat) = effective(loadout, stats + 1 point) - effective(loadout, stats)

Loadout reconstruction, validation (recorded weapon_dps within 1%, weapon_count,
weapon_tier_sum) and silent-combine reconciliation are reused verbatim from the
v124 replay. **Only validated ("trusted") shops are used** — an unvalidated
loadout would silently produce a wrong flat-damage base, which is the whole
quantity ranged_damage depends on.

Usage:
  python -m scripts.wp2_stat_marginal_value_diag --runs-dir DIR --run-ids-file F [--json OUT]
"""
from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path

from scripts.wp2_offer_dps_replay import (
    LoadoutReconstructor, build_metrics_stats, harvest_weapon_stats, sig_ids,
)

STATS = ("stat_ranged_damage", "stat_percent_damage", "stat_attack_speed")
SHORT = {"stat_ranged_damage": "ranged", "stat_percent_damage": "pct_dmg",
         "stat_attack_speed": "atk_spd"}


def load_events(path: Path) -> list[dict]:
    out = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                evt = json.loads(line)
            except json.JSONDecodeError:
                continue
            if evt.get("event") in ("run_start", "run_end", "purchase_offer",
                                    "purchase_decision", "shop_combine_confirmed"):
                out.append(evt)
    return out


def marginal(recon: LoadoutReconstructor, loadout: list[str], stats: dict,
             key: str, step: float = 1.0) -> float | None:
    base = recon.effective(loadout, stats)
    if base is None:
        return None
    bumped = dict(stats)
    bumped[key] = float(stats.get(key) or 0.0) + step
    after = recon.effective(loadout, bumped)
    if after is None:
        return None
    return after - base


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs-dir", required=True, type=Path)
    ap.add_argument("--run-ids-file", required=True, type=Path)
    ap.add_argument("--json", type=Path)
    args = ap.parse_args()

    run_ids = [ln.strip() for ln in
               args.run_ids_file.read_text(encoding="utf-8").splitlines() if ln.strip()]

    runs: dict[str, list[dict]] = {}
    results: dict[str, str] = {}
    for run_id in run_ids:
        path = args.runs_dir / run_id / "events.jsonl"
        if not path.exists():
            print(f"  !! missing events for {run_id}")
            continue
        events = load_events(path)
        runs[run_id] = events
        for e in events:
            if e.get("event") == "run_end":
                results[run_id] = str(e["payload"].get("result", "")).lower()

    wstats = harvest_weapon_stats(runs)
    recon = LoadoutReconstructor(wstats)
    print(f"runs: {len(runs)}   distinct weapons harvested: {len(wstats)}")

    rows: list[dict] = []
    trust = Counter()
    for run_id, events in runs.items():
        result = results.get(run_id)
        start = next((e["payload"].get("weapon") for e in events
                      if e.get("event") == "run_start"), None)
        loadout = [start] if start else []
        last_offer = None
        for e in events:
            ev, pl = e.get("event"), e.get("payload", {})
            if ev == "purchase_offer":
                last_offer = pl
                continue
            if ev == "shop_combine_confirmed" and pl.get("state_changed"):
                loadout = sig_ids(pl["after_signature"])
                continue
            if ev != "purchase_decision":
                continue

            off = (pl.get("build_metrics") or {}).get("offense") or {}
            action = pl.get("action") or {}
            stats = build_metrics_stats(off)
            rec_dps, rec_count = off.get("weapon_dps"), off.get("weapon_count")
            rec_tsum = off.get("weapon_tier_sum")

            trusted = recon.validate(loadout, stats, rec_dps, rec_count, rec_tsum)
            if not trusted:
                fixed = recon.reconcile(loadout, stats, rec_dps, rec_count, rec_tsum)
                if fixed is not None:
                    loadout, trusted = fixed, True

            if str(action.get("type", "")) == "shop_go":
                trust["total"] += 1
                trust["trusted"] += int(trusted)
                if trusted and rec_dps:
                    vals = {k: marginal(recon, loadout, stats, k) for k in STATS}
                    if all(v is not None for v in vals.values()):
                        rows.append({
                            "run_id": run_id, "result": result,
                            "wave": int(pl.get("wave", -1)),
                            "loadout_dps": float(rec_dps),
                            **{SHORT[k]: vals[k] for k in STATS},
                            **{f"{SHORT[k]}_pct": 100.0 * vals[k] / float(rec_dps)
                               for k in STATS},
                        })

            if str(action.get("type", "")) == "shop_buy" and last_offer:
                for it in last_offer.get("items", []):
                    if it.get("slot") == action.get("slot") and it.get("category") == "weapon":
                        loadout.append(it["id"])
            elif str(action.get("type", "")) == "shop_sell":
                idx = action.get("index")
                if idx is not None and 0 <= idx < len(loadout):
                    loadout.pop(idx)

    print(f"shop exits: {trust['total']}   loadout-validated: {trust['trusted']} "
          f"({trust['trusted'] / max(1, trust['total']):.1%})")
    print(f"usable measurements: {len(rows)}")
    print()

    print("== marginal %DPS of +1 stat point, on validated loadouts ==")
    print("   _direct_offense_gain scores all three as 1.0 point, identically.")
    print(f"{'wave':>5} {'n':>4} {'ranged':>9} {'pct_dmg':>9} {'atk_spd':>9} "
          f"{'best/worst':>11} {'best stat':>10}")
    by_wave = defaultdict(list)
    for r in rows:
        by_wave[r["wave"]].append(r)
    for wave in sorted(by_wave):
        group = by_wave[wave]
        means = {s: statistics.fmean(r[f"{s}_pct"] for r in group)
                 for s in ("ranged", "pct_dmg", "atk_spd")}
        best = max(means, key=means.get)
        worst = min(means, key=means.get)
        ratio = means[best] / means[worst] if means[worst] > 0 else float("inf")
        print(f"{wave:>5} {len(group):>4} {means['ranged']:>8.3f}% "
              f"{means['pct_dmg']:>8.3f}% {means['atk_spd']:>8.3f}% "
              f"{ratio:>11.2f}x {best:>10}")
    print()

    print("== by outcome, waves 12-19 (where the DPS gap opens) ==")
    late = [r for r in rows if 12 <= r["wave"] <= 19]
    for outcome in sorted({str(r["result"]) for r in late}):
        group = [r for r in late if str(r["result"]) == outcome]
        if not group:
            continue
        means = {s: statistics.fmean(r[f"{s}_pct"] for r in group)
                 for s in ("ranged", "pct_dmg", "atk_spd")}
        print(f"  {outcome:>8} (n={len(group):>3}): ranged {means['ranged']:.3f}%  "
              f"pct_dmg {means['pct_dmg']:.3f}%  atk_spd {means['atk_spd']:.3f}%   "
              f"ranged/atk_spd = {means['ranged'] / means['atk_spd']:.2f}x")

    if args.json:
        args.json.write_text(json.dumps({
            "trusted": trust["trusted"], "total_exits": trust["total"], "rows": rows,
        }, indent=2), encoding="utf-8")
        print(f"\nwrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
