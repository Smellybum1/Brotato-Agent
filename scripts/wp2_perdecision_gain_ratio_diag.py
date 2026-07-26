#!/usr/bin/env python3
"""Per-DECISION (not per-point) theoretical %DPS gain ratios, level-up AND shop.

Motivation: the 6.4x ranged/attack_speed figure from
`wp2_stat_marginal_value_diag.py` is a PER-POINT ratio. Real boards offer stats in
different CHUNK sizes (+2 ranged vs +15 attack_speed), so the per-DECISION ratio is
what actually decides whether the raw-points mispricing changes a pick. This
computes that distribution on recorded data.

M1  level-up: per-decision best/picked %DPS gain ratio, full raw table.
M2  break-even realisation ratio on boards offering BOTH ranged and attack_speed.
M3  shop path: stat-item buys while offense-deficient with >=1 affordable
    alternative offense stat item -> DPS-authoritative ranking vs what was bought.
M4  mechanism check on the 6.4x: per-weapon flat damage, sum of ranged scaling
    coefficients, predicted vs measured per-point ranged %gain, and the
    correlation between weapon COUNT and the ranged/attack_speed per-point ratio.

Loadout reconstruction/validation/silent-combine reconcile are reused verbatim from
`scripts/wp2_offer_dps_replay.py`. Unvalidated loadouts are SKIPPED and counted.

Usage:
  python -m scripts.wp2_perdecision_gain_ratio_diag --runs-dir DIR --run-ids-file F [--json OUT]
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path

from scripts.wp2_offer_dps_replay import (
    DEFAULT_RUNS, LoadoutReconstructor, build_metrics_stats, effect_signed_value,
    effective_weapon_dps, harvest_weapon_stats, sig_ids, _f,
)

DPS_KEYS = frozenset({
    "stat_ranged_damage", "stat_melee_damage", "stat_elemental_damage",
    "stat_damage", "stat_percent_damage", "stat_attack_speed",
    "stat_crit_chance", "stat_crit_damage",
})
UNRECORDED_BASELINE_KEYS = frozenset({
    "stat_melee_damage", "stat_elemental_damage", "stat_damage", "stat_crit_damage",
})
RELEVANT_EVENTS = ("run_start", "run_end", "purchase_offer", "purchase_decision",
                   "shop_combine_confirmed", "level_up_decision")
EPS = 1e-9


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
    d: dict = {}
    for e in effects or []:
        key = e.get("key", "")
        if key in DPS_KEYS:
            d[key] = d.get(key, 0.0) + effect_signed_value(e)
    return d


def deltas_label(deltas: dict) -> str:
    if not deltas:
        return "(no dps effect)"
    short = {"stat_ranged_damage": "ranged", "stat_percent_damage": "pct_dmg",
             "stat_attack_speed": "atk_spd", "stat_crit_chance": "crit_ch",
             "stat_crit_damage": "crit_dmg", "stat_damage": "damage",
             "stat_melee_damage": "melee", "stat_elemental_damage": "elem"}
    return ",".join(f"{short.get(k, k)}{v:+g}" for k, v in sorted(deltas.items()))


def loadout_dps(wstats: dict, loadout: list[str], stats: dict) -> float:
    return sum(effective_weapon_dps(wstats[w], stats) for w in loadout)


def gain_pct(wstats, loadout, stats, base, deltas) -> float:
    if not deltas or base <= 0:
        return 0.0
    after = dict(stats)
    for k, dv in deltas.items():
        after[k] = float(after.get(k) or 0.0) + dv
    return 100.0 * (loadout_dps(wstats, loadout, after) - base) / base


def pearson(xs, ys):
    n = len(xs)
    if n < 3:
        return None
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    sx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    sy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if sx == 0 or sy == 0:
        return None
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (sx * sy)


def spearman(xs, ys):
    def rank(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1
            for k in range(i, j + 1):
                r[order[k]] = avg
            i = j + 1
        return r
    return pearson(rank(xs), rank(ys))


def dist(name, vals, unit=""):
    if not vals:
        print(f"  {name}: n=0")
        return
    s = sorted(vals)
    print(f"  {name}: n={len(s)} min={s[0]:.4f}{unit} p25={s[len(s)//4]:.4f}{unit} "
          f"median={statistics.median(s):.4f}{unit} p75={s[(3*len(s))//4]:.4f}{unit} "
          f"max={s[-1]:.4f}{unit} mean={statistics.fmean(s):.4f}{unit}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs-dir", type=Path, default=DEFAULT_RUNS)
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
            print(f"  !! MISSING events file for {run_id}")
            continue
        events = load_events(path)
        runs[run_id] = events
        for e in events:
            if e.get("event") == "run_end":
                results[run_id] = str((e.get("payload") or {}).get("result", "")).lower()
        results.setdefault(run_id, "unknown")

    wstats = harvest_weapon_stats(runs)
    recon = LoadoutReconstructor(wstats)
    print(f"runs loaded: {len(runs)}/{len(run_ids)}   weapons harvested: {len(wstats)}")
    print("outcomes: " + ", ".join(f"{k}={v}" for k, v in
                                   sorted(Counter(results.values()).items())))
    print()

    lu_rows: list[dict] = []
    shop_rows: list[dict] = []
    m4_rows: list[dict] = []
    c = Counter()

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

            if ev in ("purchase_decision", "level_up_decision"):
                bm = pl.get("build_metrics") or {}
                off = bm.get("offense") or {}
                stats = build_metrics_stats(off)
                rec_dps = off.get("weapon_dps")
                rec_count = off.get("weapon_count")
                rec_tsum = off.get("weapon_tier_sum")
                wave = pl.get("wave", bm.get("wave"))
                action = pl.get("action") or {}
                atype = str(action.get("type", ""))

                trusted = recon.validate(loadout, stats, rec_dps, rec_count, rec_tsum)
                if not trusted:
                    fixed = recon.reconcile(loadout, stats, rec_dps, rec_count, rec_tsum)
                    if fixed is not None:
                        loadout, trusted = fixed, True

                # ---------------- M4: per shop exit, validated loadout ----------
                if ev == "purchase_decision" and atype == "shop_go":
                    c["m4_exits"] += 1
                    if trusted and rec_dps:
                        c["m4_exits_validated"] += 1
                        base = loadout_dps(wstats, loadout, stats)
                        A = _f(stats.get("stat_attack_speed"))
                        flats, coefs = [], []
                        num = 0.0
                        for w in loadout:
                            ws = wstats[w]
                            flat = _f(ws.get("damage"))
                            cr = 0.0
                            for s in (ws.get("scaling") or []):
                                if isinstance(s, (list, tuple)) and len(s) >= 2:
                                    flat += _f(stats.get(s[0])) * _f(s[1])
                                    if s[0] == "stat_ranged_damage":
                                        cr += _f(s[1])
                            flat = max(1.0, flat)
                            flats.append(flat)
                            coefs.append(cr)
                            num += cr / flat * effective_weapon_dps(ws, stats)
                        pred = 100.0 * num / base if base > 0 else 0.0
                        meas_r = gain_pct(wstats, loadout, stats, base,
                                          {"stat_ranged_damage": 1.0})
                        meas_a = gain_pct(wstats, loadout, stats, base,
                                          {"stat_attack_speed": 1.0})
                        m4_rows.append({
                            "run_id": run_id, "result": result, "wave": int(wave or -1),
                            "n_weapons": len(loadout),
                            "flats": flats, "ranged_coefs": coefs,
                            "sum_ranged_coef": sum(coefs),
                            "attack_speed_stat": A,
                            "pred_ranged_pct": pred,
                            "meas_ranged_pct": meas_r,
                            "meas_atkspd_pct": meas_a,
                            "ratio_r_over_a": (meas_r / meas_a) if meas_a > EPS else None,
                            "loadout_dps": base,
                        })

                # ---------------- M3: shop stat-item buys -----------------------
                if ev == "purchase_decision" and atype == "shop_buy":
                    c["shop_buys"] += 1
                    total, target = off.get("total"), off.get("target")
                    deficient = (total is not None and target is not None
                                 and float(target) > 0 and float(total) < float(target))
                    if deficient:
                        c["shop_deficit_buys"] += 1
                    board = (last_offer or {}).get("items", []) or []
                    chosen = next((i for i in board
                                   if i.get("slot") == action.get("slot")), None)
                    if deficient and chosen is not None:
                        if not (trusted and rec_dps):
                            c["shop_deficit_buys_unvalidated_loadout"] += 1
                        else:
                            c["shop_deficit_buys_validated"] += 1
                            base = loadout_dps(wstats, loadout, stats)
                            ch_d = option_deltas(chosen.get("effects") or [])
                            ch_is_stat = (chosen.get("category") != "weapon"
                                          and bool(ch_d))
                            alts = []
                            for it in board:
                                if it.get("slot") == action.get("slot"):
                                    continue
                                # NOTE: `can_buy` is only populated for WEAPONS in the
                                # recorded board (it is null on every non-weapon item).
                                # Requiring it truthy -- as wp2_shop_selection_diag's
                                # affordable_items() does -- silently drops ALL stat
                                # items from the alternative set. Treat null as "no
                                # weapon-slot constraint applies".
                                if not it.get("affordable"):
                                    continue
                                if it.get("can_buy") is False:
                                    continue
                                if it.get("category") == "weapon":
                                    continue
                                d = option_deltas(it.get("effects") or [])
                                if not d:
                                    continue
                                alts.append({
                                    "id": it.get("id"), "slot": it.get("slot"),
                                    "price": it.get("price"), "deltas": d,
                                    "label": deltas_label(d),
                                    "gain_pct": gain_pct(wstats, loadout, stats, base, d),
                                })
                            if ch_is_stat and alts:
                                c["shop_rankable"] += 1
                                ch_gain = gain_pct(wstats, loadout, stats, base, ch_d)
                                best = max(alts, key=lambda a: a["gain_pct"])
                                flip = best["gain_pct"] > ch_gain + EPS
                                shop_rows.append({
                                    "run_id": run_id, "result": result,
                                    "wave": int(wave or -1),
                                    "gold_before": pl.get("gold_before"),
                                    "offense_total": total, "offense_target": target,
                                    "chosen_id": chosen.get("id"),
                                    "chosen_price": chosen.get("price"),
                                    "chosen_label": deltas_label(ch_d),
                                    "chosen_gain_pct": ch_gain,
                                    "best_id": best["id"], "best_price": best["price"],
                                    "best_label": best["label"],
                                    "best_gain_pct": best["gain_pct"],
                                    "ratio": (best["gain_pct"] / ch_gain
                                              if ch_gain > EPS else None),
                                    "n_alts": len(alts), "flip": flip,
                                    "alts": alts, "loadout_dps": base,
                                })

                # ---------------- M1/M2: level-ups ------------------------------
                if ev == "level_up_decision":
                    c["levelups_seen"] += 1
                    alts_raw = pl.get("legal_alternatives") or []
                    chosen_idx = action.get("index")
                    if not (trusted and rec_dps):
                        c["lu_skipped_unvalidated"] += 1
                    elif not alts_raw or chosen_idx is None:
                        c["lu_skipped_no_alts"] += 1
                    else:
                        c["lu_validated"] += 1
                        base = loadout_dps(wstats, loadout, stats)
                        opts = []
                        for a in alts_raw:
                            d = option_deltas(a.get("effects") or [])
                            opts.append({
                                "index": a.get("index"), "deltas": d,
                                "label": deltas_label(d),
                                "gain_pct": gain_pct(wstats, loadout, stats, base, d),
                                "unrecorded_baseline": bool(set(d) & UNRECORDED_BASELINE_KEYS),
                            })
                        offense_opts = [o for o in opts if o["gain_pct"] > EPS]
                        ch = next((o for o in opts if o["index"] == chosen_idx), None)
                        if ch is None:
                            c["lu_skipped_chosen_absent"] += 1
                        else:
                            if len(offense_opts) >= 2:
                                c["lu_rankable"] += 1
                            elif len(offense_opts) == 1:
                                c["lu_one_offense"] += 1
                            else:
                                c["lu_zero_offense"] += 1
                            lu_rows.append({
                                "run_id": run_id, "result": result,
                                "wave": int(wave or -1),
                                "loadout_dps": base, "n_options": len(opts),
                                "n_offense_options": len(offense_opts),
                                "rankable": len(offense_opts) >= 2,
                                "chosen_index": chosen_idx,
                                "chosen_label": ch["label"],
                                "chosen_gain_pct": ch["gain_pct"],
                                "best_index": max(opts, key=lambda o: o["gain_pct"])["index"],
                                "best_label": max(opts, key=lambda o: o["gain_pct"])["label"],
                                "best_gain_pct": max(opts, key=lambda o: o["gain_pct"])["gain_pct"],
                                "options": opts,
                            })

            # ---- loadout mutation AFTER scoring ----
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

    # ================================ OUTPUT ================================
    print("== counts ==")
    for k in sorted(c):
        print(f"  {k:>42}: {c[k]}")
    print()

    # ---------------------------- M1 ----------------------------
    print("=" * 100)
    print("M1. LEVEL-UP per-decision theoretical %DPS gain ratio (RANKABLE = >=2 offense options)")
    print("=" * 100)
    rank = [r for r in lu_rows if r["rankable"]]
    print(f"validated level-ups: {len(lu_rows)}   rankable: {len(rank)}")
    print()
    for i, r in enumerate(sorted(rank, key=lambda r: (r["run_id"], r["wave"])), 1):
        ratio = (r["best_gain_pct"] / r["chosen_gain_pct"]
                 if r["chosen_gain_pct"] > EPS else None)
        r["ratio"] = ratio
        r["mispick"] = r["best_gain_pct"] > r["chosen_gain_pct"] + EPS
        print(f"[{i:>2}] run={r['run_id']} w{r['wave']:<3} {r['result']:<8} "
              f"loadout_dps={r['loadout_dps']:.1f}  n_off={r['n_offense_options']}")
        for o in r["options"]:
            mark = ""
            if o["index"] == r["chosen_index"]:
                mark += " <-PICKED"
            if o["index"] == r["best_index"]:
                mark += " <-BEST"
            if o["unrecorded_baseline"]:
                mark += " [unrec_baseline]"
            print(f"       opt[{o['index']}] {o['label']:<34} gain={o['gain_pct']:8.4f}%{mark}")
        rs = f"{ratio:.4f}x" if ratio is not None else "UNDEFINED (picked gain == 0)"
        print(f"       -> picked={r['chosen_gain_pct']:.4f}%  best={r['best_gain_pct']:.4f}%  "
              f"ratio={rs}  mispick={r['mispick']}")
    print()
    mis = [r for r in rank if r["mispick"]]
    ratios = [r["ratio"] for r in rank if r["ratio"] is not None]
    mis_ratios = [r["ratio"] for r in mis if r["ratio"] is not None]
    mis_undef = [r for r in mis if r["ratio"] is None]
    print("== M1 summary ==")
    print(f"  rankable decisions      : {len(rank)}")
    print(f"  mispicks (best > picked): {len(mis)}")
    dist("all rankable ratios", ratios, "x")
    dist("mispick ratios", mis_ratios, "x")
    print(f"  RAW rankable ratio series (asc): "
          + " ".join(f"{v:.4f}" for v in sorted(ratios)))
    print(f"  RAW mispick  ratio series (asc): "
          + " ".join(f"{v:.4f}" for v in sorted(mis_ratios)))
    print(f"  mispicks with ratio > 1.4x : {sum(1 for v in mis_ratios if v > 1.4)}")
    print(f"  mispicks with ratio <= 1.4x: {sum(1 for v in mis_ratios if v <= 1.4)}")
    print(f"  mispicks with UNDEFINED ratio (picked gain == 0): {len(mis_undef)}")
    print()

    # ---------------------------- M2 ----------------------------
    print("=" * 100)
    print("M2. Break-even realisation ratio (boards offering BOTH ranged_damage AND attack_speed)")
    print("=" * 100)
    pairs = []
    for r in lu_rows:
        rr = [o for o in r["options"] if "stat_ranged_damage" in o["deltas"]]
        aa = [o for o in r["options"] if "stat_attack_speed" in o["deltas"]]
        if rr and aa:
            bo_r = max(rr, key=lambda o: o["gain_pct"])
            bo_a = max(aa, key=lambda o: o["gain_pct"])
            be = (bo_a["gain_pct"] / bo_r["gain_pct"]
                  if bo_r["gain_pct"] > EPS else None)
            pairs.append({"run_id": r["run_id"], "wave": r["wave"], "result": r["result"],
                          "path": "levelup",
                          "ranged_label": bo_r["label"], "ranged_gain": bo_r["gain_pct"],
                          "atkspd_label": bo_a["label"], "atkspd_gain": bo_a["gain_pct"],
                          "breakeven": be,
                          "picked_index": r["chosen_index"],
                          "picked_label": r["chosen_label"]})
    print(f"level-up pairings: {len(pairs)}")
    for i, p in enumerate(pairs, 1):
        be = f"{p['breakeven']:.4f}" if p["breakeven"] is not None else "UNDEF"
        print(f"[{i:>2}] run={p['run_id']} w{p['wave']:<3} {p['result']:<8} "
              f"ranged {p['ranged_label']:<20} {p['ranged_gain']:8.4f}%   "
              f"atkspd {p['atkspd_label']:<20} {p['atkspd_gain']:8.4f}%   "
              f"breakeven={be}   picked={p['picked_label']}")
    bes = [p["breakeven"] for p in pairs if p["breakeven"] is not None]
    dist("breakeven", bes)
    if bes:
        print("  RAW breakeven series (asc): " + " ".join(f"{v:.4f}" for v in sorted(bes)))
    print()

    # ---------------------------- M3 ----------------------------
    print("=" * 100)
    print("M3. SHOP path: stat-item buys while offense-deficient, DPS-authoritative ranking")
    print("=" * 100)
    print(f"  shop_buy decisions total                  : {c['shop_buys']}")
    print(f"  ...offense-deficient                      : {c['shop_deficit_buys']}")
    print(f"  ......loadout VALIDATED                   : {c['shop_deficit_buys_validated']}")
    print(f"  ......loadout UNVALIDATED (excluded)      : {c['shop_deficit_buys_unvalidated_loadout']}")
    denom = c['shop_deficit_buys_validated'] + c['shop_deficit_buys_unvalidated_loadout']
    if denom:
        print(f"  ......validation rate                     : "
              f"{c['shop_deficit_buys_validated']/denom:.1%}")
    print(f"  RANKABLE (bought stat item w/ dps effect AND >=1 affordable stat-item alt): "
          f"{len(shop_rows)}")
    flips = [r for r in shop_rows if r["flip"]]
    print(f"  FLIPS (DPS ranking disagrees with the buy) : {len(flips)}"
          + (f" ({len(flips)/len(shop_rows):.1%})" if shop_rows else ""))
    print()
    print("== RAW FLIP TABLE (full) ==")
    for i, r in enumerate(sorted(flips, key=lambda r: -(r["best_gain_pct"] - r["chosen_gain_pct"])), 1):
        rs = f"{r['ratio']:.4f}x" if r["ratio"] is not None else "UNDEF(picked 0%)"
        print(f"[{i:>3}] run={r['run_id']} w{r['wave']:<3} {r['result']:<8} "
              f"gold={r['gold_before']} off {r['offense_total']}/{r['offense_target']} "
              f"loadout_dps={r['loadout_dps']:.1f}")
        print(f"      BOUGHT {str(r['chosen_id'])[:34]:<34} p={r['chosen_price']:<5} "
              f"{r['chosen_label']:<28} gain={r['chosen_gain_pct']:8.4f}%")
        print(f"      DPS-BEST {str(r['best_id'])[:32]:<32} p={r['best_price']:<5} "
              f"{r['best_label']:<28} gain={r['best_gain_pct']:8.4f}%   ratio={rs}")
    print()
    fr = [r["ratio"] for r in flips if r["ratio"] is not None]
    dist("flip ratios", fr, "x")
    if fr:
        print("  RAW flip ratio series (asc): " + " ".join(f"{v:.4f}" for v in sorted(fr)))
    print(f"  flips with UNDEFINED ratio (bought 0% gain): "
          f"{sum(1 for r in flips if r['ratio'] is None)}")
    fa = [r["best_gain_pct"] - r["chosen_gain_pct"] for r in flips]
    dist("flip forgone %DPS (abs)", fa, "%")
    if fa:
        print("  RAW flip forgone %DPS series (asc): " + " ".join(f"{v:.4f}" for v in sorted(fa)))
    print("  flips by outcome: " + str(dict(Counter(r["result"] for r in flips))))
    print("  rankable by outcome: " + str(dict(Counter(r["result"] for r in shop_rows))))
    print("  flips by wave: " + str(dict(sorted(Counter(r["wave"] for r in flips).items()))))
    print()

    # ---------------------------- M4 ----------------------------
    print("=" * 100)
    print("M4. Mechanism check on the 6.4x (validated shop exits)")
    print("=" * 100)
    print(f"  validated exits used: {len(m4_rows)} / {c['m4_exits']} exits "
          f"({len(m4_rows)/max(1,c['m4_exits']):.1%})")
    all_flats = [f for r in m4_rows for f in r["flats"]]
    all_coefs = [k for r in m4_rows for k in r["ranged_coefs"]]
    dist("per-weapon flat damage (incl. stat scaling)", all_flats)
    dist("per-weapon ranged scaling coef c_i", all_coefs)
    dist("sum(ranged coef) per loadout", [r["sum_ranged_coef"] for r in m4_rows])
    dist("weapon count", [float(r["n_weapons"]) for r in m4_rows])
    dist("attack_speed stat A", [r["attack_speed_stat"] for r in m4_rows])
    dist("measured +1 ranged %gain", [r["meas_ranged_pct"] for r in m4_rows], "%")
    dist("predicted sum(c_i*E_i/flat_i)/sum(E_i)", [r["pred_ranged_pct"] for r in m4_rows], "%")
    dist("measured +1 atk_spd %gain", [r["meas_atkspd_pct"] for r in m4_rows], "%")
    rr = [r for r in m4_rows if r["ratio_r_over_a"] is not None]
    dist("ranged/atk_spd per-point ratio", [r["ratio_r_over_a"] for r in rr], "x")
    print()
    if len(m4_rows) >= 3:
        print("  corr(predicted, measured ranged %gain): "
              f"pearson={pearson([r['pred_ranged_pct'] for r in m4_rows], [r['meas_ranged_pct'] for r in m4_rows]):.4f} "
              f"spearman={spearman([r['pred_ranged_pct'] for r in m4_rows], [r['meas_ranged_pct'] for r in m4_rows]):.4f}")
        wc = [float(r["n_weapons"]) for r in rr]
        ra = [r["ratio_r_over_a"] for r in rr]
        pc, sc = pearson(wc, ra), spearman(wc, ra)
        print(f"  corr(weapon COUNT, ranged/atk_spd ratio): "
              f"pearson={pc if pc is None else round(pc,4)} spearman={sc if sc is None else round(sc,4)}  (n={len(rr)})")
        pf = [statistics.fmean(r["flats"]) for r in rr]
        print(f"  corr(mean per-weapon flat, ranged/AS ratio): "
              f"pearson={pearson(pf, ra):.4f} spearman={spearman(pf, ra):.4f}")
        sc2 = [r["sum_ranged_coef"] for r in rr]
        print(f"  corr(sum ranged coef, ranged/AS ratio): "
              f"pearson={pearson(sc2, ra):.4f} spearman={spearman(sc2, ra):.4f}")
        print()
        print("  == ranged/AS per-point ratio BY WEAPON COUNT ==")
        byn = defaultdict(list)
        for r in rr:
            byn[r["n_weapons"]].append(r["ratio_r_over_a"])
        for n in sorted(byn):
            v = byn[n]
            print(f"    n_weapons={n}: count={len(v)} median={statistics.median(v):.4f}x "
                  f"mean={statistics.fmean(v):.4f}x min={min(v):.4f} max={max(v):.4f}")
        print()
        print("  == RAW M4 per-exit series (weapon_count, sum_coef, mean_flat, meas_ranged%, pred%, meas_AS%, ratio) ==")
        for r in rr:
            print(f"    w{r['wave']:<3} {r['result'][:4]:<4} nw={r['n_weapons']} "
                  f"sumc={r['sum_ranged_coef']:.3f} meanflat={statistics.fmean(r['flats']):.3f} "
                  f"meas_r={r['meas_ranged_pct']:.4f}% pred={r['pred_ranged_pct']:.4f}% "
                  f"meas_a={r['meas_atkspd_pct']:.4f}% ratio={r['ratio_r_over_a']:.4f}")

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps({
            "counts": dict(c), "results": results,
            "levelup_rows": lu_rows, "m2_pairs": pairs,
            "shop_rows": shop_rows, "m4_rows": m4_rows,
        }, indent=2), encoding="utf-8")
        print(f"\nwrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
