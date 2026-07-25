#!/usr/bin/env python3
"""Weapon-axis selection diagnostic — the component that actually discriminates.

`combat_model.gd::offense_rating` returns ``total = max(stat_score, weapon_score)``
and, measured at shop exit across the F2 teacher runs, the WEAPON term is the max
in ~90% of exits at every wave (wave 19: weapon 273.8 vs stat 130.1). The earlier
selection diagnostic (`wp2_shop_selection_diag.py`) scored `_direct_offense_gain`,
which sums stat-item effects and feeds `stat_score` — the term that is almost
never the max. This tests the term that is.

Method. `total_effective_weapon_dps` is a plain SUM over equipped weapons, so the
marginal DPS of ADDING a weapon is exactly `effective_weapon_dps(w, stats)` for
that weapon alone — no loadout reconstruction required. Current-loadout DPS and
the offense stats are both logged on every purchase_decision, so each board weapon
can be priced exactly against the build that was actually standing there.

Three questions, matching three hypotheses with different consequences:

  A. weapon-vs-weapon   when it bought a weapon, was a better one affordable?
                        -> fixable in `_weapon_score`
  B. cross-category     did it buy a non-weapon while an affordable weapon offered
                        a large fractional DPS gain? (>=5% of loadout DPS, the v82
                        fractional-DeltaDPS rule) -> fixable in `item_score`
  C. combines           do winners land more tier upgrades than losers?
                        -> fixable in the combine path, or evidence of offer luck

KNOWN LIMITATIONS, stated because they bound the conclusion:
  * `stat_melee_damage` / `stat_elemental_damage` are not in the recorded offense
    block, so weapons scaling on them are UNDER-valued here. Melee is reported
    separately and never drives the headline; the build is a gun build and the
    teacher already applies a -3.0 melee penalty in `_weapon_score`.
  * Marginal DPS is exact only when a weapon SLOT IS FREE. With slots full the
    real delta is (added - removed) and the removed weapon is not recoverable
    from telemetry alone; those decisions are counted and reported separately,
    never pooled into the headline.

Usage:
  python -m scripts.wp2_weapon_selection_diag --runs-dir DIR --run-ids-file F [--json OUT]
"""
from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path

from scripts.wp2_offer_dps_replay import build_metrics_stats, effective_weapon_dps

WEAPON_SLOTS_DEFAULT = 6
FRACTIONAL_GAIN_BAR = 0.05  # v82 fractional-DeltaDPS rule: >=5% of loadout DPS


def iter_stream(path: Path):
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                evt = json.loads(line)
            except json.JSONDecodeError:
                continue
            kind = evt.get("event")
            if kind in ("purchase_offer", "purchase_decision", "run_end",
                        "shop_combine_confirmed"):
                yield evt


def analyse_run(run_dir: Path) -> tuple[list[dict], dict]:
    records: list[dict] = []
    board: list[dict] = []
    combines = 0
    result: str | None = None

    for evt in iter_stream(run_dir / "events.jsonl"):
        kind = evt.get("event")
        payload = evt.get("payload", {})
        if kind == "run_end":
            result = str(payload.get("result", "")).lower()
            continue
        if kind == "shop_combine_confirmed":
            combines += 1
            continue
        if kind == "purchase_offer":
            board = payload.get("items", []) or []
            continue

        action = payload.get("action") or {}
        atype = str(action.get("type", ""))
        if atype not in ("shop_buy", "shop_go"):
            continue

        offense = (payload.get("build_metrics") or {}).get("offense") or {}
        loadout_dps = offense.get("weapon_dps")
        weapon_count = offense.get("weapon_count")
        if loadout_dps is None or weapon_count is None:
            continue
        stats = build_metrics_stats(offense)

        affordable_weapons = [
            i for i in board
            if i.get("category") == "weapon" and i.get("affordable") and i.get("can_buy")
        ]
        priced = []
        for w in affordable_weapons:
            priced.append({
                "id": w.get("id"),
                "slot": w.get("slot"),
                "price": w.get("price"),
                "melee": w.get("weapon_type") == "melee",
                "mdps": effective_weapon_dps(w, stats),
            })
        ranged = [p for p in priced if not p["melee"]]
        best = max(ranged, key=lambda p: p["mdps"]) if ranged else None

        chosen_slot = action.get("slot")
        chosen = next((i for i in board if i.get("slot") == chosen_slot), None) \
            if atype == "shop_buy" else None
        chosen_is_weapon = bool(chosen and chosen.get("category") == "weapon")
        chosen_mdps = (effective_weapon_dps(chosen, stats)
                       if chosen_is_weapon else None)

        records.append({
            "wave": int(payload.get("wave", -1)),
            "action": atype,
            "slots_full": int(weapon_count) >= WEAPON_SLOTS_DEFAULT,
            "weapon_count": int(weapon_count),
            "loadout_dps": float(loadout_dps),
            "chosen_id": (chosen or {}).get("id"),
            "chosen_is_weapon": chosen_is_weapon,
            "chosen_mdps": round(chosen_mdps, 1) if chosen_mdps is not None else None,
            "n_affordable_ranged_weapons": len(ranged),
            "best_id": best["id"] if best else None,
            "best_mdps": round(best["mdps"], 1) if best else None,
            "best_price": best["price"] if best else None,
            "best_frac_gain": (round(best["mdps"] / float(loadout_dps), 3)
                               if best and float(loadout_dps) > 0 else None),
        })
    return records, {"combines": combines, "result": result}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs-dir", required=True, type=Path)
    ap.add_argument("--run-ids-file", required=True, type=Path)
    ap.add_argument("--json", type=Path)
    args = ap.parse_args()

    run_ids = [ln.strip() for ln in
               args.run_ids_file.read_text(encoding="utf-8").splitlines() if ln.strip()]

    all_recs: list[dict] = []
    per_run: list[dict] = []
    for run_id in run_ids:
        run_dir = args.runs_dir / run_id
        if not (run_dir / "events.jsonl").exists():
            print(f"  !! missing events for {run_id}")
            continue
        recs, meta = analyse_run(run_dir)
        for r in recs:
            r["run_id"] = run_id
            r["result"] = meta["result"]
        all_recs.extend(recs)
        per_run.append({"run_id": run_id, **meta,
                        "weapon_buys": sum(1 for r in recs if r["chosen_is_weapon"])})

    # ── C. combines by outcome ────────────────────────────────────────────────
    print("== C. combines (tier upgrades) by outcome ==")
    by_out = defaultdict(list)
    for row in per_run:
        by_out[str(row["result"])].append(row)
    for outcome in sorted(by_out):
        rows = by_out[outcome]
        combines = [r["combines"] for r in rows]
        buys = [r["weapon_buys"] for r in rows]
        print(f"  {outcome:>8}: n={len(rows):>2}  combines mean {statistics.fmean(combines):>5.2f} "
              f"(median {statistics.median(combines):>4.1f}, range {min(combines)}-{max(combines)})   "
              f"weapon buys mean {statistics.fmean(buys):>5.2f}")
    print()

    # ── A. weapon-vs-weapon ───────────────────────────────────────────────────
    wbuys = [r for r in all_recs
             if r["chosen_is_weapon"] and r["best_mdps"] is not None and not r["slots_full"]]
    print("== A. weapon buys: was a better affordable ranged weapon on the board? ==")
    print(f"  weapon buys with a free slot and >=1 affordable ranged alternative: {len(wbuys)}")
    if wbuys:
        forgone = [r["best_mdps"] - (r["chosen_mdps"] or 0.0) for r in wbuys]
        pos = [f for f in forgone if f > 1e-9]
        print(f"  bought something with LOWER marginal DPS than an affordable option: "
              f"{len(pos)} ({len(pos) / len(wbuys):.1%})")
        if pos:
            print(f"    forgone marginal DPS: median {statistics.median(pos):.1f}  "
                  f"max {max(pos):.1f}")
            rel = [(r["best_mdps"] - (r["chosen_mdps"] or 0.0)) / r["loadout_dps"]
                   for r in wbuys
                   if r["loadout_dps"] > 0 and r["best_mdps"] > (r["chosen_mdps"] or 0.0)]
            if rel:
                print(f"    as a fraction of loadout DPS: median {statistics.median(rel):.1%}  "
                      f"max {max(rel):.1%}")
        for outcome in sorted({r["result"] for r in wbuys}):
            rows = [r for r in wbuys if r["result"] == outcome]
            bad = [r for r in rows if r["best_mdps"] > (r["chosen_mdps"] or 0.0)]
            print(f"    {outcome:>8}: {len(bad)}/{len(rows)} ({len(bad) / len(rows):.1%})")
    slots_full_buys = sum(1 for r in all_recs if r["chosen_is_weapon"] and r["slots_full"])
    print(f"  (excluded: {slots_full_buys} weapon buys with slots full — marginal DPS "
          f"is not the right delta there)")
    print()

    # ── B. cross-category ─────────────────────────────────────────────────────
    print(f"== B. bought a NON-weapon while an affordable ranged weapon offered "
          f">={FRACTIONAL_GAIN_BAR:.0%} loadout DPS ==")
    cross = [r for r in all_recs
             if r["action"] == "shop_buy" and not r["chosen_is_weapon"]
             and r["best_frac_gain"] is not None and not r["slots_full"]]
    flagged = [r for r in cross if r["best_frac_gain"] >= FRACTIONAL_GAIN_BAR]
    print(f"  non-weapon buys with a free slot and an affordable ranged weapon: {len(cross)}")
    if cross:
        print(f"  ...where that weapon offered >={FRACTIONAL_GAIN_BAR:.0%}: "
              f"{len(flagged)} ({len(flagged) / len(cross):.1%})")
    for outcome in sorted({r["result"] for r in cross}):
        rows = [r for r in cross if r["result"] == outcome]
        bad = [r for r in rows if r["best_frac_gain"] >= FRACTIONAL_GAIN_BAR]
        if rows:
            print(f"    {outcome:>8}: {len(bad)}/{len(rows)} ({len(bad) / len(rows):.1%})")
    if flagged:
        print(f"  by wave: {dict(sorted(Counter(r['wave'] for r in flagged).items()))}")
        fr = [r["best_frac_gain"] for r in flagged]
        print(f"  forgone fractional gain: median {statistics.median(fr):.1%}  max {max(fr):.1%}")
        print()
        print("  worst 15:")
        print(f"  {'wave':>5} {'res':>8} {'bought':>24} {'passed over':>26} {'mdps':>8} {'frac':>7}")
        for r in sorted(flagged, key=lambda r: -r["best_frac_gain"])[:15]:
            print(f"  {r['wave']:>5} {str(r['result'])[:8]:>8} {str(r['chosen_id'])[:24]:>24} "
                  f"{str(r['best_id'])[:26]:>26} {r['best_mdps']:>8} {r['best_frac_gain']:>7.1%}")

    if args.json:
        args.json.write_text(json.dumps({
            "per_run": per_run, "records": all_recs,
            "fractional_gain_bar": FRACTIONAL_GAIN_BAR,
        }, indent=2), encoding="utf-8")
        print(f"\nwrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
