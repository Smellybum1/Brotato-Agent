#!/usr/bin/env python3
"""Jack wave-16/17 wall: matched-window contact control + wave-band contrast.

Supplements wp2_d5_pressure_clearance.py (which supplies backlog/clearance
percentiles but NOT a matched control on the CONTACT rate, which is the statistic
that carried the D5 survival verdict).

RULES ENFORCED (each a past failure on this project)
* Matched within-run control: 10 s windows lying entirely inside ONE wave >= 6 of the
  SAME run and entirely BEFORE the terminal window. Never a whole-wave cut -- a
  survived wave clears what it spawns, so whole-wave backlog is 0.000 BY CONSTRUCTION.
* `nearest_d` >= 1e17 is the NO-TARGET sentinel. Filtered, counted, never averaged.
* Terminal window anchored to the LAST CAPTURE. The killing blow is not captured.
* Contacts from the HP-DROP DIFF, never `player_damage` events.
* control_dt_ms < 10 excluded from velocity-derived statistics only.
* Every count prints its denominator; constant fields are reported N/A, not as zeros.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from pathlib import Path
from typing import Any

INF_SENTINEL = 1e17
MIN_DT_MS = 10
TAIL_SEC = 10.0
BAND_LO = (10, 11, 12, 13, 14, 15)
BAND_HI = (16, 17)


def _minsurf(px, py, items):
    best = None
    for it in items:
        x, y = it.get("x"), it.get("y")
        if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
            continue
        d = math.hypot(x - px, y - py) - float(it.get("radius") or 0.0)
        if best is None or d < best:
            best = d
    return best


def load(path: Path):
    rows, diag = [], {"captures_seen": 0, "nd_inf": 0, "nd_inf_zero_enemies": 0,
                      "low_dt": 0, "no_player": 0, "invalid": 0}
    run_end_ts = None
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            if '"combat_capture"' not in line:
                if '"run_end"' in line:
                    try:
                        ev = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if ev.get("event") == "run_end":
                        run_end_ts = float(ev.get("ts_ms") or 0)
                continue
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            if ev.get("event") != "combat_capture":
                continue
            p = ev.get("payload") or {}
            diag["captures_seen"] += 1
            if p.get("valid") is False:
                diag["invalid"] += 1
                continue
            pl = p.get("player") or {}
            hp, px, py = pl.get("hp"), pl.get("x"), pl.get("y")
            if not isinstance(hp, (int, float)) or not isinstance(px, (int, float)):
                diag["no_player"] += 1
                continue
            dt = p.get("control_dt_ms")
            low = isinstance(dt, (int, float)) and dt < MIN_DT_MS
            diag["low_dt"] += int(low)
            ent = p.get("entities") or {}
            enemies = ent.get("enemies") or []
            bosses = ent.get("bosses") or []
            des = ((p.get("teacher") or {}).get("contributions") or {}).get("desire") or {}
            ndv = des.get("nearest_d")
            nd_inf = isinstance(ndv, (int, float)) and abs(float(ndv)) >= INF_SENTINEL
            if nd_inf:
                diag["nd_inf"] += 1
                diag["nd_inf_zero_enemies"] += int(not enemies)
            hp_by_id = {int(e["instance_id"]): float(e["hp"]) for e in enemies
                        if e.get("instance_id") is not None
                        and isinstance(e.get("hp"), (int, float))}
            rows.append({
                "ts": float(ev.get("ts_ms") or 0.0), "wave": int(p.get("wave", 0)),
                "low_dt": low, "hp": float(hp),
                "max_hp": float(pl.get("max_hp") or 0.0),
                "armor": pl.get("armor"), "dodge": pl.get("dodge"),
                "speed": pl.get("speed"), "lifesteal": pl.get("lifesteal"),
                "hp_regen": pl.get("hp_regeneration"),
                "n_enemies": len(enemies) + len(bosses),
                "enemy_hp": sum(hp_by_id.values()) + sum(
                    float(b.get("hp") or 0) for b in bosses),
                "hp_by_id": hp_by_id,
                "minsurf": _minsurf(px, py, enemies),
                "nearest_d": None if (not isinstance(ndv, (int, float)) or nd_inf)
                else float(ndv),
                "weapon_max": des.get("weapon_max"),
            })
    rows.sort(key=lambda r: r["ts"])
    return rows, diag, run_end_ts


def wmet(rows):
    """Window metrics. Returns None when the window cannot support a rate."""
    if len(rows) < 20:
        return None
    span = (rows[-1]["ts"] - rows[0]["ts"]) / 1000.0
    if span <= 0:
        return None
    spawns = kills = 0
    dmg_out = 0.0
    for i in range(1, len(rows)):
        a, b = rows[i - 1]["hp_by_id"], rows[i]["hp_by_id"]
        new, gone = b.keys() - a.keys(), a.keys() - b.keys()
        spawns += len(new)
        kills += len(gone)
        dmg_out += sum(a[k] for k in gone)
        dmg_out += sum(max(0.0, a[k] - b[k]) for k in a.keys() & b.keys())
    drops = [rows[i - 1]["hp"] - rows[i]["hp"] for i in range(1, len(rows))
             if rows[i]["hp"] < rows[i - 1]["hp"]]
    n = len(rows)
    inr = sum(1 for r in rows if r["nearest_d"] is not None
              and isinstance(r["weapon_max"], (int, float))
              and r["nearest_d"] <= float(r["weapon_max"]))
    fin = [r["minsurf"] for r in rows if r["minsurf"] is not None]
    return {
        "span": span, "captures": n,
        "contacts": len(drops), "contacts_per_sec": len(drops) / span,
        "hp_lost": sum(drops), "hp_lost_per_sec": sum(drops) / span,
        "max_hp": rows[-1]["max_hp"],
        "hp_lost_frac_maxhp": (sum(drops) / rows[-1]["max_hp"]) if rows[-1]["max_hp"] else None,
        "enemies_alive_mean": statistics.mean(r["n_enemies"] for r in rows),
        "enemy_hp_mean": statistics.mean(r["enemy_hp"] for r in rows),
        "spawns": spawns, "kills": kills,
        "spawn_per_sec": spawns / span, "kill_per_sec": kills / span,
        "net_backlog_per_sec": (spawns - kills) / span,
        "kill_over_spawn": (kills / spawns) if spawns else None,
        "dmg_out_per_sec": dmg_out / span,
        "frac_in_weapon_range": inr / n,
        "frac_any_enemy": sum(1 for r in rows if r["n_enemies"] > 0) / n,
        "minsurf_median": statistics.median(fin) if fin else None,
    }


def pctile(vals, x):
    vals = [v for v in vals if isinstance(v, (int, float))]
    if not vals or not isinstance(x, (int, float)):
        return None
    return sum(1 for v in vals if v <= x) / len(vals)


def matched_ref(rows, term_lo_ts, min_wave=6):
    """10 s windows entirely inside ONE wave >= min_wave and entirely before terminal."""
    W = TAIL_SEC * 1000.0
    by_wave = {}
    for i, r in enumerate(rows):
        by_wave.setdefault(r["wave"], []).append(i)
    out = {"contacts_per_sec": [], "hp_lost_per_sec": [], "hp_lost_frac_maxhp": [],
           "net_backlog_per_sec": [], "kill_over_spawn": [], "enemies_alive_mean": [],
           "frac_in_weapon_range": [], "dmg_out_per_sec": []}
    for w, idxs in by_wave.items():
        if w < min_wave:
            continue
        j = 0
        for k in range(len(idxs)):
            hi = rows[idxs[k]]["ts"]
            while rows[idxs[j]]["ts"] < hi - W:
                j += 1
            if k - j < 20:
                continue
            if rows[idxs[k]]["ts"] > term_lo_ts:
                continue
            m = wmet([rows[i] for i in idxs[j:k + 1]])
            if not m:
                continue
            for key in out:
                if m.get(key) is not None:
                    out[key].append(m[key])
    return out


def band(rows, waves):
    sub = [r for r in rows if r["wave"] in waves]
    if len(sub) < 20:
        return None
    # split by wave so a wave gap does not fabricate a span
    tot = {"span": 0.0, "contacts": 0, "hp_lost": 0.0, "spawns": 0, "kills": 0,
           "dmg_out": 0.0, "caps": 0, "inr": 0, "anyen": 0}
    ens, ehp, msf = [], [], []
    for w in sorted(set(waves)):
        wr = [r for r in sub if r["wave"] == w]
        m = wmet(wr)
        if not m:
            continue
        tot["span"] += m["span"]
        tot["contacts"] += m["contacts"]
        tot["hp_lost"] += m["hp_lost"]
        tot["spawns"] += m["spawns"]
        tot["kills"] += m["kills"]
        tot["dmg_out"] += m["dmg_out_per_sec"] * m["span"]
        tot["caps"] += m["captures"]
        tot["inr"] += m["frac_in_weapon_range"] * m["captures"]
        tot["anyen"] += m["frac_any_enemy"] * m["captures"]
        ens.append(m["enemies_alive_mean"])
        ehp.append(m["enemy_hp_mean"])
        if m["minsurf_median"] is not None:
            msf.append(m["minsurf_median"])
    if tot["span"] <= 0:
        return None
    return {
        "waves_used": len([w for w in sorted(set(waves))
                           if any(r["wave"] == w for r in sub)]),
        "span": tot["span"], "captures": tot["caps"],
        "enemies_alive_mean": statistics.mean(ens) if ens else None,
        "enemy_hp_mean": statistics.mean(ehp) if ehp else None,
        "spawn_per_sec": tot["spawns"] / tot["span"],
        "kill_per_sec": tot["kills"] / tot["span"],
        "dmg_out_per_sec": tot["dmg_out"] / tot["span"],
        "contacts_per_sec": tot["contacts"] / tot["span"],
        "hp_lost_per_sec": tot["hp_lost"] / tot["span"],
        "frac_in_weapon_range": tot["inr"] / tot["caps"],
        "frac_any_enemy": tot["anyen"] / tot["caps"],
        "minsurf_median": statistics.median(msf) if msf else None,
    }


def analyse(rid, root):
    f = root / rid / "events.jsonl"
    rows, diag, run_end = load(f)
    if len(rows) < 50:
        return {"run_id": rid, "error": "insufficient captures", "diag": diag}
    summ = {}
    sf = root / rid / "summary.json"
    if sf.is_file():
        summ = json.loads(sf.read_text(encoding="utf-8"))
    last = rows[-1]["ts"]
    term_lo = last - TAIL_SEC * 1000.0
    term = wmet([r for r in rows if r["ts"] >= term_lo])
    ref = matched_ref(rows, term_lo)

    def mult(key):
        base = ref.get(key) or []
        if not base or term is None or term.get(key) is None:
            return None, None, None
        med = statistics.median(base)
        return (term[key], med,
                (term[key] / med) if med else None)

    per_wave = {}
    for w in sorted({r["wave"] for r in rows}):
        wr = [r for r in rows if r["wave"] == w]
        per_wave[w] = {
            "max_hp": wr[-1]["max_hp"], "armor": wr[-1]["armor"],
            "dodge": wr[-1]["dodge"], "speed": wr[-1]["speed"],
            "lifesteal": wr[-1]["lifesteal"], "hp_regen": wr[-1]["hp_regen"],
            "hp_min": min(r["hp"] for r in wr),
        }
    # uncapped dodge from run_end build_metrics if present
    bm = None
    try:
        for s in (summ.get("finale_combat_ticks"), ):
            pass
        bmroot = summ.get("build_metrics")
        if isinstance(bmroot, dict):
            bm = bmroot
    except Exception:
        bm = None
    return {
        "run_id": rid, "result": summ.get("result"),
        "character": summ.get("character"), "weapon": summ.get("weapon"),
        "terminal_wave": rows[-1]["wave"],
        "capture_to_run_end_gap_ms": (run_end - last) if run_end else None,
        "hp_at_last_capture": rows[-1]["hp"],
        "fatal_drop_captured": rows[-1]["hp"] <= 0,
        "diag": diag,
        "terminal": term,
        "ref_windows": len(ref["contacts_per_sec"]),
        "ref_median_contacts_per_sec": (statistics.median(ref["contacts_per_sec"])
                                        if ref["contacts_per_sec"] else None),
        "ref_p90_contacts_per_sec": (sorted(ref["contacts_per_sec"])[
            int(0.9 * (len(ref["contacts_per_sec"]) - 1))]
            if ref["contacts_per_sec"] else None),
        "contact_mult": mult("contacts_per_sec")[2],
        "hp_loss_mult": mult("hp_lost_per_sec")[2],
        "term_pctile_contacts": pctile(ref["contacts_per_sec"],
                                       term["contacts_per_sec"] if term else None),
        "term_pctile_net_backlog": pctile(ref["net_backlog_per_sec"],
                                          term["net_backlog_per_sec"] if term else None),
        "term_pctile_kill_over_spawn": pctile(ref["kill_over_spawn"],
                                              term["kill_over_spawn"] if term else None),
        "band_lo": band(rows, BAND_LO),
        "band_hi": band(rows, [w for w in BAND_HI]),
        "per_wave_build": per_wave,
        "build_metrics": bm,
    }


def fmt(v, nd=3):
    if v is None:
        return "N/A"
    if isinstance(v, float):
        return f"{v:.{nd}f}"
    return str(v)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs-dir", required=True)
    ap.add_argument("--run-ids-file", required=True)
    ap.add_argument("--outdir", default=".tmp/jack_wall/contrast")
    a = ap.parse_args()
    root = Path(a.runs_dir)
    ids = [x.strip() for x in Path(a.run_ids_file).read_text(encoding="utf-8").splitlines()
           if x.strip() and not x.startswith("#")]
    out = Path(a.outdir)
    out.mkdir(parents=True, exist_ok=True)
    runs = [analyse(r, root, ) for r in ids]
    ok = [r for r in runs if "error" not in r]

    L = []
    A = L.append
    A("# JACK WAVE-16/17 WALL -- matched-window contact control + wave-band contrast")
    A("")
    A(f"runs {len(ok)}/{len(ids)}   runs_dir `{root}`")
    A("Terminal window = last 10 s of CAPTURES, anchored to the LAST CAPTURE.")
    A("Matched control = every 10 s window lying entirely inside ONE wave >= 6 of the")
    A("SAME run and entirely before the terminal window. NOT a whole-wave cut.")
    A("")
    A("## 1. Terminal window vs MATCHED within-run control")
    A("")
    A("| run_id | twave | gap_ms | last-cap HP | max_hp | ref windows | contacts/s TERM |"
      " contacts/s ref med | ref p90 | MULT | PCTILE | hp_lost TERM | /max_hp |"
      " hp_loss/s mult | net-backlog PCTILE | k/s PCTILE |")
    A("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in ok:
        t = r["terminal"] or {}
        A(f"| {r['run_id']} | {r['terminal_wave']} |"
          f" {fmt(r['capture_to_run_end_gap_ms'],1)} | {r['hp_at_last_capture']} |"
          f" {fmt(t.get('max_hp'),0)} | {r['ref_windows']} |"
          f" {fmt(t.get('contacts_per_sec'),4)} |"
          f" {fmt(r['ref_median_contacts_per_sec'],4)} |"
          f" {fmt(r['ref_p90_contacts_per_sec'],4)} | {fmt(r['contact_mult'],2)} |"
          f" {fmt(r['term_pctile_contacts'],4)} | {fmt(t.get('hp_lost'),1)} |"
          f" {fmt(t.get('hp_lost_frac_maxhp'),3)} | {fmt(r['hp_loss_mult'],2)} |"
          f" {fmt(r['term_pctile_net_backlog'],4)} |"
          f" {fmt(r['term_pctile_kill_over_spawn'],4)} |")
    A("")
    for key, lbl in (("contact_mult", "contact-rate multiplier"),
                     ("hp_loss_mult", "hp-loss-rate multiplier"),
                     ("term_pctile_contacts", "terminal contact-rate percentile")):
        v = [r[key] for r in ok if isinstance(r.get(key), (int, float))]
        if v:
            A(f"- {lbl}: median {statistics.median(v):.3f}"
              f" [{min(v):.3f}, {max(v):.3f}], n={len(v)}")
        else:
            A(f"- {lbl}: NO VALUES (n=0)")
    fr = [r["terminal"]["hp_lost_frac_maxhp"] for r in ok
          if r["terminal"] and r["terminal"].get("hp_lost_frac_maxhp") is not None]
    if fr:
        A(f"- HP lost in terminal 10 s as fraction of max_hp: median"
          f" {statistics.median(fr):.3f} [{min(fr):.3f}, {max(fr):.3f}], n={len(fr)}")
    ct = [r["terminal"]["contacts"] for r in ok if r["terminal"]]
    if ct:
        A(f"- damaging contacts in terminal 10 s (count): median"
          f" {statistics.median(ct)} [{min(ct)}, {max(ct)}], n={len(ct)}")
    A("")
    A("## 2. Wave-band contrast: waves 10-15 vs waves 16-17, SAME runs")
    A("")
    A("| run_id | band | waves | span_s | caps | en_alive_mean | enHP_mean | spawn/s |"
      " kill/s | dmg_out/s | contacts/s | hp_lost/s | frac_in_range | frac_any_enemy |"
      " minsurf_med |")
    A("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in ok:
        for lbl, b in (("10-15", r["band_lo"]), ("16-17", r["band_hi"])):
            if not b:
                A(f"| {r['run_id']} | {lbl} | NONE | - | - | - | - | - | - | - | - |"
                  " - | - | - | - |")
                continue
            A(f"| {r['run_id']} | {lbl} | {b['waves_used']} | {fmt(b['span'],1)} |"
              f" {b['captures']} | {fmt(b['enemies_alive_mean'],2)} |"
              f" {fmt(b['enemy_hp_mean'],1)} | {fmt(b['spawn_per_sec'],3)} |"
              f" {fmt(b['kill_per_sec'],3)} | {fmt(b['dmg_out_per_sec'],1)} |"
              f" {fmt(b['contacts_per_sec'],4)} | {fmt(b['hp_lost_per_sec'],3)} |"
              f" {fmt(b['frac_in_weapon_range'],4)} | {fmt(b['frac_any_enemy'],4)} |"
              f" {fmt(b['minsurf_median'],1)} |")
    A("")
    A("Paired band ratios (16-17 / 10-15), per run then median:")
    for key in ("enemies_alive_mean", "enemy_hp_mean", "spawn_per_sec", "kill_per_sec",
                "dmg_out_per_sec", "contacts_per_sec", "hp_lost_per_sec",
                "frac_in_weapon_range", "minsurf_median"):
        rat = []
        for r in ok:
            lo, hi = r["band_lo"], r["band_hi"]
            if lo and hi and lo.get(key):
                rat.append(hi[key] / lo[key])
        if rat:
            A(f"  - `{key}`: median x{statistics.median(rat):.3f}"
              f" [{min(rat):.3f}, {max(rat):.3f}], n={len(rat)}")
        else:
            A(f"  - `{key}`: NO VALUES (n=0)")
    A("")
    A("## 3. Build trajectory by wave (end-of-wave capture values)")
    A("")
    allw = sorted({w for r in ok for w in r["per_wave_build"]})
    A("| run_id | " + " | ".join(f"w{w}" for w in allw) + " |")
    A("|---|" + "---|" * len(allw))
    for fld, lbl in (("max_hp", "max_hp"), ("armor", "armor"), ("dodge", "dodge"),
                     ("speed", "speed"), ("lifesteal", "lifesteal"),
                     ("hp_regen", "hp_regen")):
        A(f"| **{lbl}** |" + "|" * len(allw))
        for r in ok:
            cells = []
            for w in allw:
                pw = r["per_wave_build"].get(w)
                cells.append("-" if pw is None else str(pw[fld]))
            A(f"| {r['run_id']} | " + " | ".join(cells) + " |")
    A("")
    A("## 4. Denominators / sentinel audit")
    A("")
    A("| run_id | captures | invalid | no_player | low_dt(<10ms) | nearest_d INF |"
      " INF with 0 enemies |")
    A("|---|---|---|---|---|---|---|")
    for r in ok:
        d = r["diag"]
        A(f"| {r['run_id']} | {d['captures_seen']} | {d['invalid']} | {d['no_player']} |"
          f" {d['low_dt']} | {d['nd_inf']} | {d['nd_inf_zero_enemies']} |")
    txt = "\n".join(L) + "\n"
    (out / "report.md").write_text(txt, encoding="utf-8")
    (out / "contrast.json").write_text(json.dumps(runs, indent=1), encoding="utf-8")
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    print(txt)


if __name__ == "__main__":
    main()
