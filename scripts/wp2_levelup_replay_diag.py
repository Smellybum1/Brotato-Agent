#!/usr/bin/env python3
"""How much weapon DPS do the teacher's level-up picks leave on the table?

Every `level_up_decision` event logs `legal_alternatives` -- the FULL option list,
each with its `effects` array -- plus `action.index` (the option actually taken)
and `build_metrics`. The counterfactual is therefore exactly recoverable offline:
for each option we apply its stat deltas to the offense stats recorded at that
moment and re-price the CURRENT equipped loadout with the exact port of
`combat_model.gd` (`effective_weapon_dps`), then compare the chosen option's
marginal DPS against the best option available.

Loadout tracking / validation / silent-combine reconciliation are reused verbatim
from `scripts/wp2_offer_dps_replay.py` (via `scripts/wp2_stat_marginal_value_diag.py`'s
pattern): start weapon from `run_start`, weapon buys from the paired
`purchase_offer` on `shop_buy`, pop on `shop_sell`, reset to the
`after_signature` on a state-changing `shop_combine_confirmed`. Level-ups
interleave with shop events in the same stream, so the loadout carried into each
`level_up_decision` is whatever the shop replay last produced. Every level-up is
validated against the recorded `weapon_dps` / `weapon_count` / `weapon_tier_sum`
(within 1%), with a bounded reconcile pass; **unvalidated level-ups are SKIPPED
and counted**, never guessed.

LIMITATIONS (read before using these numbers)
---------------------------------------------
* This measures **marginal weapon DPS only**. The live scorer (`decide_levelup`)
  also weighs EHP (max_hp / armor / dodge / hp_regeneration / lifesteal) and pure
  utility (harvesting, speed, luck, engineering, range). An option that looks
  "suboptimal" here may be a deliberate, correct defensive or economic pick.
  A high forgone-DPS number is therefore an upper bound on the DPS cost, NOT
  evidence of a scoring error.
* Only these keys move weapon DPS and are counted; every other key contributes
  exactly 0 here: stat_ranged_damage, stat_melee_damage, stat_elemental_damage,
  stat_damage, stat_percent_damage, stat_attack_speed, stat_crit_chance,
  stat_crit_damage.
* `build_metrics.offense` records only ranged_damage / percent_damage /
  attack_speed / crit_chance. stat_melee_damage, stat_elemental_damage,
  stat_damage and stat_crit_damage are NOT recorded, so their *baseline* is
  assumed 0. Their marginal effect is still computed against that baseline
  (correct for crit_damage's additive term and for flat scaling terms whose base
  is genuinely 0, i.e. the well_rounded ranged builds these runs use; would be
  biased on a build that had accumulated melee/elemental damage). Options whose
  effects touch one of those four keys are flagged `unrecorded_baseline` and
  counted separately.
* `effects` values use the `shop_strategy.gd` sign convention; we import
  `effect_signed_value` from `scripts/wp2_offer_dps_replay.py` (not replicated).

Usage:
  python -m scripts.wp2_levelup_replay_diag --runs-dir DIR --run-ids-file F [--json OUT]
"""
from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path

from scripts.wp2_offer_dps_replay import (
    LoadoutReconstructor, build_metrics_stats, effect_signed_value,
    effective_weapon_dps, harvest_weapon_stats, sig_ids,
)

# Keys that move weapon DPS in combat_model.gd. Everything else is 0 DPS here.
DPS_KEYS = frozenset({
    "stat_ranged_damage", "stat_melee_damage", "stat_elemental_damage",
    "stat_damage", "stat_percent_damage", "stat_attack_speed",
    "stat_crit_chance", "stat_crit_damage",
})
# DPS keys whose BASELINE is not present in build_metrics.offense.
UNRECORDED_BASELINE_KEYS = frozenset({
    "stat_melee_damage", "stat_elemental_damage", "stat_damage",
    "stat_crit_damage",
})

RELEVANT_EVENTS = ("run_start", "run_end", "purchase_offer", "purchase_decision",
                   "shop_combine_confirmed", "level_up_decision")


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
            if evt.get("event") in RELEVANT_EVENTS:
                out.append(evt)
    return out


def option_deltas(effects: list) -> dict:
    """Signed stat deltas restricted to the DPS-relevant keys."""
    d: dict = {}
    for e in effects or []:
        key = e.get("key", "")
        if key in DPS_KEYS:
            d[key] = d.get(key, 0.0) + effect_signed_value(e)
    return d


def effect_label(effects: list) -> str:
    parts = []
    for e in effects or []:
        parts.append(f"{e.get('key')}{effect_signed_value(e):+g}")
    return ",".join(parts) if parts else "(no effects)"


def loadout_dps(wstats: dict, loadout: list[str], stats: dict) -> float:
    return sum(effective_weapon_dps(wstats[w], stats) for w in loadout)


def pctl(values: list[float], q: float):
    if not values:
        return None
    s = sorted(values)
    idx = max(0, min(len(s) - 1, int(round((q / 100.0) * (len(s) - 1)))))
    return s[idx]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs-dir", required=True, type=Path)
    ap.add_argument("--run-ids-file", required=True, type=Path)
    ap.add_argument("--json", type=Path)
    args = ap.parse_args()

    run_ids = [ln.strip() for ln in
               args.run_ids_file.read_text(encoding="utf-8").splitlines() if ln.strip()]

    # ---- FIRST PASS: load events and read run_end outcomes (run_end is LAST) ----
    runs: dict[str, list[dict]] = {}
    results: dict[str, str] = {}
    missing_files, missing_outcome = [], []
    for run_id in run_ids:
        path = args.runs_dir / run_id / "events.jsonl"
        if not path.exists():
            print(f"  !! MISSING events file for {run_id}")
            missing_files.append(run_id)
            continue
        events = load_events(path)
        runs[run_id] = events
        for e in events:
            if e.get("event") == "run_end":
                results[run_id] = str((e.get("payload") or {}).get("result", "")).lower()
        if run_id not in results:
            print(f"  !! NO run_end/result for {run_id}")
            missing_outcome.append(run_id)
            results[run_id] = "unknown"

    wstats = harvest_weapon_stats(runs)
    recon = LoadoutReconstructor(wstats)
    print(f"runs loaded: {len(runs)}/{len(run_ids)}   "
          f"distinct weapons harvested: {len(wstats)}")
    print("outcomes: " + ", ".join(f"{k}={v}" for k, v in
                                   sorted(Counter(results.values()).items())))
    print()

    # ---- SECOND PASS: replay ----
    counts = Counter()
    rows: list[dict] = []
    for run_id, events in runs.items():
        result = results.get(run_id, "unknown")
        start = next((e["payload"].get("weapon") for e in events
                      if e.get("event") == "run_start"), None)
        loadout = [start] if start else []
        last_offer = None
        for e in events:
            ev, pl = e.get("event"), e.get("payload") or {}

            if ev == "purchase_offer":
                last_offer = pl
                continue
            if ev == "shop_combine_confirmed" and pl.get("state_changed"):
                loadout = sig_ids(pl["after_signature"])
                continue
            if ev == "purchase_decision":
                action = pl.get("action") or {}
                if str(action.get("type", "")) == "shop_buy" and last_offer:
                    for it in last_offer.get("items", []):
                        if (it.get("slot") == action.get("slot")
                                and it.get("category") == "weapon"):
                            loadout.append(it["id"])
                elif str(action.get("type", "")) == "shop_sell":
                    idx = action.get("index")
                    if idx is not None and 0 <= idx < len(loadout):
                        loadout.pop(idx)
                continue
            if ev != "level_up_decision":
                continue

            counts["levelups_seen"] += 1
            bm = pl.get("build_metrics") or {}
            off = bm.get("offense") or {}
            stats = build_metrics_stats(off)
            rec_dps = off.get("weapon_dps")
            rec_count = off.get("weapon_count")
            rec_tsum = off.get("weapon_tier_sum")
            wave = pl.get("wave", bm.get("wave"))

            trusted = recon.validate(loadout, stats, rec_dps, rec_count, rec_tsum)
            if not trusted:
                fixed = recon.reconcile(loadout, stats, rec_dps, rec_count, rec_tsum)
                if fixed is not None:
                    loadout, trusted = fixed, True
            if not trusted or not rec_dps:
                counts["skipped_unvalidated"] += 1
                continue

            alts = pl.get("legal_alternatives") or []
            chosen_idx = (pl.get("action") or {}).get("index")
            if not alts or chosen_idx is None:
                counts["skipped_no_alternatives_or_index"] += 1
                continue

            base = loadout_dps(wstats, loadout, stats)
            opts = []
            for a in alts:
                effects = a.get("effects") or []
                deltas = option_deltas(effects)
                after = dict(stats)
                for k, dv in deltas.items():
                    after[k] = float(after.get(k) or 0.0) + dv
                marg = loadout_dps(wstats, loadout, after) - base if deltas else 0.0
                opts.append({
                    "index": a.get("index"),
                    "label": effect_label(effects),
                    "marginal_dps": marg,
                    "unrecorded_baseline": bool(set(deltas) & UNRECORDED_BASELINE_KEYS),
                })

            chosen = next((o for o in opts if o["index"] == chosen_idx), None)
            if chosen is None:
                counts["skipped_chosen_index_not_in_alternatives"] += 1
                continue

            counts["validated"] += 1
            best = max(opts, key=lambda o: o["marginal_dps"])
            forgone = best["marginal_dps"] - chosen["marginal_dps"]
            if any(o["unrecorded_baseline"] for o in opts):
                counts["with_unrecorded_baseline_option"] += 1
            rows.append({
                "run_id": run_id, "result": result, "wave": wave,
                "n_options": len(opts),
                "loadout": list(loadout),
                "loadout_dps": base,
                "chosen_index": chosen_idx,
                "chosen_label": chosen["label"],
                "chosen_marginal_dps": chosen["marginal_dps"],
                "best_index": best["index"],
                "best_label": best["label"],
                "best_marginal_dps": best["marginal_dps"],
                "forgone_dps": forgone,
                "forgone_pct": 100.0 * forgone / base if base > 0 else None,
                "suboptimal": forgone > 0.0,
                "unrecorded_baseline": any(o["unrecorded_baseline"] for o in opts),
                "options": opts,
            })

    # ---------------------------- output ----------------------------
    print("== counts ==")
    print(f"  level-ups seen            : {counts['levelups_seen']}")
    print(f"  validated (usable)        : {counts['validated']}")
    print(f"  skipped: unvalidated load : {counts['skipped_unvalidated']}")
    print(f"  skipped: no alts/index    : {counts['skipped_no_alternatives_or_index']}")
    print(f"  skipped: chosen idx absent: {counts['skipped_chosen_index_not_in_alternatives']}")
    print(f"  MISSING event files       : {len(missing_files)} {missing_files}")
    print(f"  MISSING run_end outcome   : {len(missing_outcome)} {missing_outcome}")
    print(f"  validated decisions where >=1 option has an unrecorded baseline key: "
          f"{counts['with_unrecorded_baseline_option']}")
    print()

    n = len(rows)
    if n == 0:
        print("!! NO validated level-up decisions -- nothing further to report.")
        return 1

    sub = [r for r in rows if r["suboptimal"]]
    print("== overall ==")
    print(f"  decisions with marginal DPS strictly below the best available: "
          f"{len(sub)}/{n} ({100.0*len(sub)/n:.1f}%)")
    print()

    abs_all = [r["forgone_dps"] for r in rows]
    pct_all = [r["forgone_pct"] for r in rows if r["forgone_pct"] is not None]
    abs_sub = [r["forgone_dps"] for r in sub]
    pct_sub = [r["forgone_pct"] for r in sub if r["forgone_pct"] is not None]
    n_nopct = sum(1 for r in rows if r["forgone_pct"] is None)
    print("== forgone DPS distribution ==")
    for name, a, p in (("all validated", abs_all, pct_all),
                       ("suboptimal only", abs_sub, pct_sub)):
        if not a:
            print(f"  {name}: n=0")
            continue
        print(f"  {name} (n={len(a)}): "
              f"abs median={statistics.median(a):.3f} p90={pctl(a,90):.3f} max={max(a):.3f}"
              f"   |   pct median={statistics.median(p):.3f}% "
              f"p90={pctl(p,90):.3f}% max={max(p):.3f}%")
    if n_nopct:
        print(f"  !! {n_nopct} decisions had loadout_dps<=0 -> forgone_pct UNCOMPUTABLE "
              f"(excluded from pct stats, kept in abs)")
    print()

    print("== per-wave ==")
    print(f"{'wave':>5} {'n':>5} {'mean_forgone_pct':>17} {'frac_suboptimal':>16} "
          f"{'median_loadout_dps':>19}")
    by_wave = defaultdict(list)
    for r in rows:
        by_wave[r["wave"]].append(r)
    wave_tbl = []
    for wave in sorted(by_wave, key=lambda w: (w is None, w)):
        g = by_wave[wave]
        ps = [r["forgone_pct"] for r in g if r["forgone_pct"] is not None]
        mean_pct = statistics.fmean(ps) if ps else float("nan")
        frac = sum(1 for r in g if r["suboptimal"]) / len(g)
        mdps = statistics.median([r["loadout_dps"] for r in g])
        print(f"{str(wave):>5} {len(g):>5} {mean_pct:>16.3f}% {frac:>15.1%} {mdps:>19.1f}")
        wave_tbl.append({"wave": wave, "n": len(g), "mean_forgone_pct": mean_pct,
                         "frac_suboptimal": frac, "median_loadout_dps": mdps})
    print()

    print("== by run outcome ==")
    outcome_tbl = []
    for outcome in sorted({r["result"] for r in rows}):
        g = [r for r in rows if r["result"] == outcome]
        ps = [r["forgone_pct"] for r in g if r["forgone_pct"] is not None]
        frac = sum(1 for r in g if r["suboptimal"]) / len(g)
        runs_n = len({r["run_id"] for r in g})
        print(f"  {outcome:>8} (runs={runs_n}, n={len(g):>4}): "
              f"suboptimal {frac:.1%}   forgone% mean={statistics.fmean(ps):.3f} "
              f"median={statistics.median(ps):.3f} p90={pctl(ps,90):.3f} max={max(ps):.3f}")
        outcome_tbl.append({"outcome": outcome, "runs": runs_n, "n": len(g),
                            "frac_suboptimal": frac,
                            "mean_forgone_pct": statistics.fmean(ps),
                            "median_forgone_pct": statistics.median(ps),
                            "p90_forgone_pct": pctl(ps, 90), "max_forgone_pct": max(ps)})
    print()

    print("== 20 worst decisions by forgone DPS % ==")
    worst = sorted([r for r in rows if r["forgone_pct"] is not None],
                   key=lambda r: -r["forgone_pct"])[:20]
    for i, r in enumerate(worst, 1):
        print(f"{i:>3}. w{r['wave']:<3} {r['result']:<8} forgone={r['forgone_pct']:7.3f}% "
              f"({r['forgone_dps']:8.2f} of {r['loadout_dps']:9.2f})")
        print(f"      chosen[{r['chosen_index']}]: {r['chosen_label']}  "
              f"(marg {r['chosen_marginal_dps']:.3f})")
        print(f"      best  [{r['best_index']}]: {r['best_label']}  "
              f"(marg {r['best_marginal_dps']:.3f})"
              + ("   [unrecorded_baseline]" if r["unrecorded_baseline"] else ""))
    print()

    print("== RAW forgone % series (all validated, ascending) ==")
    series = sorted(r["forgone_pct"] for r in rows if r["forgone_pct"] is not None)
    print(" ".join(f"{v:.3f}" for v in series))
    print()
    print("== RAW forgone abs series (all validated, ascending) ==")
    series_abs = sorted(abs_all)
    print(" ".join(f"{v:.3f}" for v in series_abs))
    print()

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps({
            "counts": dict(counts),
            "missing_files": missing_files,
            "missing_outcome": missing_outcome,
            "results": results,
            "per_wave": wave_tbl,
            "per_outcome": outcome_tbl,
            "rows": rows,
        }, indent=2), encoding="utf-8")
        print(f"wrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
