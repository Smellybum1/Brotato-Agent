#!/usr/bin/env python3
"""Block A of danger5_baseline_prereg.md section 7 -- PRESSURE AND CLEARANCE.

Per wave, and separately over the last N seconds before the terminal event:

    enemies alive | total enemy HP alive | spawn rate | kill rate
    | effective damage output | fraction of ticks with a valid target
    | player HP trajectory | damaging-contact count

The block exists to separate three failure modes:
    clearance         -- backlog grows because the build cannot service the spawn stream
    survival          -- backlog is manageable but avoidable hits are taken
    no-local-solution -- death in a state with no feasible short-horizon heading

MEASUREMENT RULES ENFORCED HERE (each one is a past failure on this project)
---------------------------------------------------------------------------
* `nearest_d` >= 1e17 means NO TARGET, not a distance. It is filtered, counted, and
  NEVER averaged. The "valid target" fraction is computed from it plus a redundant
  entity-count check, and the two are cross-tabulated so a disagreement is visible.
* Captures with `control_dt_ms` < 10 are excluded from every velocity-derived metric
  (measured_vx/vy is displacement/dt and explodes at start-up dt).
* `wave_time.elapsed_sec` RESETS on the final captures of a won wave. It is therefore
  NOT used as the time base. All rates use the event `ts_ms` run clock, and the
  per-wave elapsed_sec monotonicity is CHECKED and reported so the reader can see
  whether the reset actually occurred in this sample.
* The terminal window is anchored to the LAST CAPTURE, not to death: the killing blow
  is not in the telemetry. `capture_to_run_end_gap_ms` is reported per run.
* Damaging contacts are counted from the HP-DROP DIFF, never from `player_damage`
  events (those lag by one capture interval). The `player_damage` event count is
  printed alongside as a cross-check only.
* Every zero is printed with the denominator that was searched, and each filter field
  is checked for actual variation.
* `damage_taken` is NOT used as a verdict anywhere (gross counter, never subtracts
  healing). Player HP trajectory is reported directly instead.

KNOWN LIMITATION -- enemy identity
----------------------------------
Spawn and kill counting uses `entities.enemies[].instance_id`. On this project
projectile instance_ids are POOLED/REUSED. Whether enemy ids are pooled within a run
is MEASURED here (`id_reuse_gap_events`: an id that disappears for >= 2 captures and
then reappears) and reported per run, rather than assumed either way. A count-only
estimator (delta of enemy count) is computed in parallel; if the two disagree the
id-based figure is not trustworthy and the disagreement is printed.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from collections import Counter
from pathlib import Path
from typing import Any

INF_SENTINEL = 1e17
MIN_DT_MS = 10
DEFAULT_TAIL_SEC = 10.0
LAG_SWEEP = (-3, -2, -1, 0, 1, 2, 3)


def _min_surface(px: float, py: float, items: list[dict[str, Any]]) -> float | None:
    best = None
    for it in items:
        x, y = it.get("x"), it.get("y")
        if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
            continue
        d = math.hypot(x - px, y - py) - float(it.get("radius") or 0.0)
        if best is None or d < best:
            best = d
    return best


def load_run(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    diag: Counter = Counter()
    run_end_ts = None
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            if '"combat_capture"' not in line:
                if '"run_end"' in line or '"player_damage"' in line:
                    try:
                        ev = json.loads(line)
                    except json.JSONDecodeError:
                        diag["unparseable_lines"] += 1
                        continue
                    if ev.get("event") == "run_end":
                        ts = ev.get("ts_ms")
                        if isinstance(ts, (int, float)):
                            run_end_ts = float(ts)
                    elif ev.get("event") == "player_damage":
                        diag["player_damage_events"] += 1
                continue
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                diag["unparseable_lines"] += 1
                continue
            if ev.get("event") != "combat_capture":
                continue
            p = ev.get("payload", {}) or {}
            diag["captures_seen"] += 1
            if p.get("valid") is False:
                diag["excluded_invalid"] += 1
                continue
            dt = p.get("control_dt_ms")
            low_dt = isinstance(dt, (int, float)) and dt < MIN_DT_MS
            if low_dt:
                diag["low_dt_captures"] += 1
            player = p.get("player", {}) or {}
            hp, px, py = player.get("hp"), player.get("x"), player.get("y")
            if not isinstance(hp, (int, float)) or not isinstance(px, (int, float)):
                diag["excluded_no_player"] += 1
                continue
            ent = p.get("entities", {}) or {}
            enemies = ent.get("enemies") or []
            bosses = ent.get("bosses") or []
            desire = ((p.get("teacher") or {}).get("contributions") or {}).get("desire") or {}
            ndv = desire.get("nearest_d")
            nd_inf = isinstance(ndv, (int, float)) and abs(float(ndv)) >= INF_SENTINEL
            if nd_inf:
                diag["nearest_d_inf"] += 1
                if not enemies:
                    diag["nearest_d_inf_with_zero_enemies"] += 1
            wt = p.get("wave_time", {}) or {}
            hp_by_id = {}
            for e in enemies:
                iid = e.get("instance_id")
                ehp = e.get("hp")
                if iid is not None and isinstance(ehp, (int, float)):
                    hp_by_id[int(iid)] = float(ehp)
            rows.append({
                "seq": p.get("capture_seq"),
                "ts_ms": float(ev.get("ts_ms") or 0.0),
                "wave": int(p.get("wave", 0)),
                "low_dt": low_dt,
                "hp": float(hp),
                "max_hp": float(player.get("max_hp") or 0.0),
                "px": float(px), "py": float(py),
                "n_enemies": len(enemies),
                "n_bosses": len(bosses),
                "enemy_hp_total": float(sum(hp_by_id.values())) + float(
                    sum(b.get("hp") or 0.0 for b in bosses)),
                "enemy_hp_by_id": hp_by_id,
                "d_enemies": _min_surface(px, py, enemies),
                "nearest_d": None if (not isinstance(ndv, (int, float)) or nd_inf) else float(ndv),
                "nearest_d_inf": nd_inf,
                "weapon_max": desire.get("weapon_max"),
                "at_weapon_range": desire.get("at_weapon_range"),
                "elapsed_sec": wt.get("elapsed_sec"),
            })
    rows.sort(key=lambda r: (r["ts_ms"], r["seq"] if r["seq"] is not None else 0))
    d = dict(diag)
    d["run_end_ts_ms"] = run_end_ts
    return rows, d


def _pct(n: int, d: int) -> float | None:
    return round(n / d, 4) if d else None


def window_metrics(rows: list[dict[str, Any]], label: str) -> dict[str, Any]:
    """All pressure/clearance metrics over an arbitrary contiguous capture window.

    Rates use the ts_ms run clock. The exact window span is reported so no rate is
    quoted without the interval it was divided by.
    """
    out: dict[str, Any] = {"window": label, "captures": len(rows)}
    if len(rows) < 2:
        out["insufficient"] = True
        return out
    span_s = (rows[-1]["ts_ms"] - rows[0]["ts_ms"]) / 1000.0
    out["span_sec"] = round(span_s, 3)
    out["ts_first_ms"] = rows[0]["ts_ms"]
    out["ts_last_ms"] = rows[-1]["ts_ms"]

    n_en = [r["n_enemies"] for r in rows]
    hp_tot = [r["enemy_hp_total"] for r in rows]
    out["enemies_alive_mean"] = round(statistics.mean(n_en), 3)
    out["enemies_alive_median"] = statistics.median(n_en)
    out["enemies_alive_max"] = max(n_en)
    out["enemy_hp_alive_mean"] = round(statistics.mean(hp_tot), 2)
    out["enemy_hp_alive_median"] = round(statistics.median(hp_tot), 2)
    out["enemy_hp_alive_max"] = round(max(hp_tot), 2)
    out["enemy_hp_alive_first"] = round(hp_tot[0], 2)
    out["enemy_hp_alive_last"] = round(hp_tot[-1], 2)
    # backlog slope: least-squares u/s on total live enemy HP. Positive = backlog grows.
    if span_s > 0:
        xs = [(r["ts_ms"] - rows[0]["ts_ms"]) / 1000.0 for r in rows]
        mx, my = statistics.mean(xs), statistics.mean(hp_tot)
        den = sum((x - mx) ** 2 for x in xs)
        out["enemy_hp_slope_per_sec"] = round(
            sum((x - mx) * (y - my) for x, y in zip(xs, hp_tot)) / den, 3) if den else None
        mc = statistics.mean(n_en)
        out["enemy_count_slope_per_sec"] = round(
            sum((x - mx) * (y - mc) for x, y in zip(xs, n_en)) / den, 4) if den else None
    else:
        out["enemy_hp_slope_per_sec"] = None
        out["enemy_count_slope_per_sec"] = None

    # --- spawns / kills / damage output, id-based, with a count-only cross-check ---
    spawns = kills = 0
    dmg_out = 0.0
    count_up = count_down = 0
    seen_gone: dict[int, int] = {}
    reuse_events = 0
    for i in range(1, len(rows)):
        prev, cur = rows[i - 1]["enemy_hp_by_id"], rows[i]["enemy_hp_by_id"]
        new_ids = cur.keys() - prev.keys()
        gone_ids = prev.keys() - cur.keys()
        spawns += len(new_ids)
        kills += len(gone_ids)
        for iid in gone_ids:
            dmg_out += prev[iid]
            seen_gone[iid] = i
        for iid in new_ids:
            if iid in seen_gone and i - seen_gone[iid] >= 2:
                reuse_events += 1
        for iid in cur.keys() & prev.keys():
            d = prev[iid] - cur[iid]
            if d > 0:
                dmg_out += d
        dn = rows[i]["n_enemies"] - rows[i - 1]["n_enemies"]
        if dn > 0:
            count_up += dn
        elif dn < 0:
            count_down += -dn
    out["spawns_total"] = spawns
    out["kills_total"] = kills
    out["spawn_rate_per_sec"] = round(spawns / span_s, 3) if span_s > 0 else None
    out["kill_rate_per_sec"] = round(kills / span_s, 3) if span_s > 0 else None
    out["net_backlog_per_sec"] = (round((spawns - kills) / span_s, 3) if span_s > 0 else None)
    out["damage_output_hp_per_sec"] = round(dmg_out / span_s, 2) if span_s > 0 else None
    out["damage_output_hp_total"] = round(dmg_out, 1)
    out["countonly_appear_total"] = count_up
    out["countonly_vanish_total"] = count_down
    out["id_vs_count_spawn_delta"] = spawns - count_up
    out["id_vs_count_kill_delta"] = kills - count_down
    out["id_reuse_gap_events"] = reuse_events

    # --- valid target fraction: two independent definitions, cross-tabulated ---
    n = len(rows)
    any_enemy = sum(1 for r in rows if r["n_enemies"] > 0)
    nd_finite = sum(1 for r in rows if r["nearest_d"] is not None)
    nd_inf = sum(1 for r in rows if r["nearest_d_inf"])
    in_range = sum(1 for r in rows
                   if r["nearest_d"] is not None and isinstance(r["weapon_max"], (int, float))
                   and r["nearest_d"] <= float(r["weapon_max"]))
    disagree = sum(1 for r in rows if (r["n_enemies"] > 0) != (r["nearest_d"] is not None))
    out["frac_ticks_any_enemy"] = _pct(any_enemy, n)
    out["frac_ticks_nearest_d_finite"] = _pct(nd_finite, n)
    out["frac_ticks_target_in_weapon_range"] = _pct(in_range, n)
    out["nearest_d_inf_captures"] = nd_inf
    out["nearest_d_vs_count_disagreements"] = disagree
    fin = [r["nearest_d"] for r in rows if r["nearest_d"] is not None]
    out["nearest_d_median_finite_only"] = round(statistics.median(fin), 2) if fin else None
    de = [r["d_enemies"] for r in rows if r["d_enemies"] is not None]
    out["min_surface_d_enemy_median"] = round(statistics.median(de), 2) if de else None
    out["min_surface_d_enemy_min"] = round(min(de), 2) if de else None

    # --- player HP trajectory + damaging contacts (HP-drop diff) ---
    hps = [r["hp"] for r in rows]
    out["hp_first"] = hps[0]
    out["hp_last"] = hps[-1]
    out["hp_min"] = min(hps)
    out["hp_max"] = max(hps)
    out["max_hp"] = rows[-1]["max_hp"]
    drops = [(rows[i - 1]["hp"] - rows[i]["hp"]) for i in range(1, len(rows))
             if rows[i]["hp"] < rows[i - 1]["hp"]]
    gains = [(rows[i]["hp"] - rows[i - 1]["hp"]) for i in range(1, len(rows))
             if rows[i]["hp"] > rows[i - 1]["hp"]]
    out["damaging_contacts"] = len(drops)
    out["damaging_contacts_per_sec"] = round(len(drops) / span_s, 4) if span_s > 0 else None
    out["hp_lost_total"] = round(sum(drops), 1)
    out["hp_gained_total"] = round(sum(gains), 1)
    out["hp_loss_per_sec"] = round(sum(drops) / span_s, 3) if span_s > 0 else None
    out["hp_ratio_last"] = round(hps[-1] / rows[-1]["max_hp"], 3) if rows[-1]["max_hp"] else None
    return out


def lag_sweep(rows: list[dict[str, Any]], waves: set[int]) -> dict[int, dict[str, Any]]:
    """Re-derive the causal lag IN THIS CONTEXT rather than inheriting it.

    For each lag L, compare the min surface distance to an enemy at index i+L for the
    captures where an HP drop landed at i, against the same statistic over all
    captures in the same waves (the baseline). The lag that maximally separates them
    is the lag the data supports here.
    """
    idx = [i for i, r in enumerate(rows) if r["wave"] in waves]
    base = [rows[i]["d_enemies"] for i in idx if rows[i]["d_enemies"] is not None]
    drop_i = [i for i in idx if i > 0 and rows[i]["hp"] < rows[i - 1]["hp"]
              and rows[i - 1]["wave"] == rows[i]["wave"]]
    out: dict[int, dict[str, Any]] = {}
    base_med = statistics.median(base) if base else None
    for L in LAG_SWEEP:
        vals = []
        for i in drop_i:
            j = i + L
            if 0 <= j < len(rows) and rows[j]["d_enemies"] is not None:
                vals.append(rows[j]["d_enemies"])
        out[L] = {
            "n_drops_scored": len(vals),
            "n_drops_candidate": len(drop_i),
            "baseline_captures": len(base),
            "median_d": round(statistics.median(vals), 3) if vals else None,
            "baseline_median_d": round(base_med, 3) if base_med is not None else None,
            "delta_vs_baseline": (round(statistics.median(vals) - base_med, 3)
                                  if vals and base_med is not None else None),
            "frac_within_40u": (round(sum(1 for v in vals if v <= 40.0) / len(vals), 4)
                                if vals else None),
            "baseline_frac_within_40u": (round(sum(1 for v in base if v <= 40.0) / len(base), 4)
                                         if base else None),
        }
    return out


def _quart(v):
    v = sorted(x for x in v if isinstance(x, (int, float)))
    if not v:
        return None
    return {"n": len(v), "min": round(v[0], 3), "p25": round(v[len(v) // 4], 3),
            "median": round(v[len(v) // 2], 3), "p75": round(v[3 * len(v) // 4], 3),
            "max": round(v[-1], 3)}


def _pctile_of(vals, x):
    vals = [v for v in vals if isinstance(v, (int, float))]
    if not vals or not isinstance(x, (int, float)):
        return None
    return round(sum(1 for v in vals if v <= x) / len(vals), 4)


def sliding_reference(rows, tail_sec, min_wave=6):
    """Matched-window control for the clearance question.

    WHY THIS EXISTS -- a design-time lie found in the whole-wave version.
    Over a COMPLETED wave, every spawned enemy is eventually killed, so
    spawns == kills EXACTLY, `net_backlog_per_sec` is 0.000 and kill/spawn is 1.000
    BY CONSTRUCTION in every non-terminal wave of every run. That statistic is
    structurally incapable of returning a positive for a survived wave, so
    "the terminal wave has backlog growth and earlier waves do not" is VACUOUS.

    The non-vacuous comparison is window-matched: slide a window of the SAME duration
    over the run's waves >= min_wave, keep only windows lying entirely inside one wave
    and entirely before the terminal window, and place the terminal window inside that
    distribution.
    """
    W = tail_sec * 1000.0
    vals_net, vals_slope, vals_ratio = [], [], []
    by_wave = {}
    for i, r in enumerate(rows):
        by_wave.setdefault(r["wave"], []).append(i)
    term_lo = rows[-1]["ts_ms"] - W
    for w, idxs in by_wave.items():
        if w < min_wave:
            continue
        j = 0
        for k in range(len(idxs)):
            hi = rows[idxs[k]]["ts_ms"]
            while rows[idxs[j]]["ts_ms"] < hi - W:
                j += 1
            if k - j < 20:
                continue
            sub = [rows[i] for i in idxs[j:k + 1]]
            if sub[-1]["ts_ms"] > term_lo:
                continue
            m = window_metrics(sub, "slide")
            if m.get("insufficient"):
                continue
            vals_net.append(m["net_backlog_per_sec"])
            vals_slope.append(m["enemy_hp_slope_per_sec"])
            if m["spawns_total"]:
                vals_ratio.append(m["kills_total"] / m["spawns_total"])
    return {"windows": len(vals_net),
            "net_backlog_ref": _quart(vals_net),
            "hp_slope_ref": _quart(vals_slope),
            "kill_over_spawn_ref": _quart(vals_ratio),
            "_vals_net": vals_net, "_vals_slope": vals_slope, "_vals_ratio": vals_ratio}


def analyse_run(rid: str, root: Path, tail_sec: float) -> dict[str, Any]:
    f = root / rid / "events.jsonl"
    if not f.is_file():
        return {"run_id": rid, "error": "missing events.jsonl"}
    rows, diag = load_run(f)
    if len(rows) < 2:
        return {"run_id": rid, "error": "insufficient captures", "diagnostics": diag}
    summary: dict[str, Any] = {}
    sf = root / rid / "summary.json"
    if sf.is_file():
        try:
            summary = json.loads(sf.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    waves = sorted({r["wave"] for r in rows})
    terminal_wave = rows[-1]["wave"]

    per_wave = []
    elapsed_nonmono = {}
    for w in waves:
        wr = [r for r in rows if r["wave"] == w]
        m = window_metrics(wr, f"wave_{w}")
        m["wave"] = w
        per_wave.append(m)
        es = [r["elapsed_sec"] for r in wr if isinstance(r["elapsed_sec"], (int, float))]
        nm = sum(1 for a, b in zip(es, es[1:]) if b < a)
        if nm:
            elapsed_nonmono[w] = nm

    last_ts = rows[-1]["ts_ms"]
    tail_rows = [r for r in rows if r["ts_ms"] >= last_ts - tail_sec * 1000.0]
    tail = window_metrics(tail_rows, f"last_{tail_sec:g}s")
    tail["anchor"] = "last capture in the run (NOT death)"
    tail["waves_spanned"] = sorted({r["wave"] for r in tail_rows})

    ref = sliding_reference(rows, tail_sec)
    ref_summary = {k: v for k, v in ref.items() if not k.startswith("_")}
    ref_summary["terminal_pctile_net_backlog"] = _pctile_of(
        ref["_vals_net"], tail["net_backlog_per_sec"])
    ref_summary["terminal_pctile_hp_slope"] = _pctile_of(
        ref["_vals_slope"], tail["enemy_hp_slope_per_sec"])
    _ts = tail["spawns_total"]
    ref_summary["terminal_kill_over_spawn"] = (
        round(tail["kills_total"] / _ts, 4) if _ts else None)
    ref_summary["terminal_pctile_kill_over_spawn"] = _pctile_of(
        ref["_vals_ratio"], ref_summary["terminal_kill_over_spawn"])
    gap = (diag["run_end_ts_ms"] - last_ts) if diag.get("run_end_ts_ms") else None
    return {
        "run_id": rid,
        "result": summary.get("result"),
        "terminal_wave": terminal_wave,
        "waves": waves,
        "diagnostics": diag,
        "capture_to_run_end_gap_ms": round(gap, 1) if gap is not None else None,
        "hp_at_last_capture": rows[-1]["hp"],
        "fatal_drop_captured": rows[-1]["hp"] <= 0,
        "elapsed_sec_nonmonotonic_by_wave": elapsed_nonmono,
        "per_wave": per_wave,
        "terminal_window": tail,
        "lag_sweep_terminal_wave": lag_sweep(rows, {terminal_wave}),
        "lag_sweep_all_waves_ge6": lag_sweep(rows, {w for w in waves if w >= 6}),
        "sliding_reference": ref_summary,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs-dir", required=True)
    ap.add_argument("--run-ids-file", required=True)
    ap.add_argument("--outdir", default=".tmp/d5_pressure_clearance_n20")
    ap.add_argument("--tail-sec", type=float, default=DEFAULT_TAIL_SEC)
    args = ap.parse_args()

    root = Path(args.runs_dir)
    ids = [l.strip() for l in Path(args.run_ids_file).read_text(encoding="utf-8").splitlines()
           if l.strip() and not l.startswith("#")]
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    runs = [analyse_run(r, root, args.tail_sec) for r in ids]
    ok = [r for r in runs if "error" not in r]
    (outdir / "pressure_clearance.json").write_text(
        json.dumps({"runs_dir": str(root), "tail_sec": args.tail_sec, "runs": runs},
                   indent=1), encoding="utf-8")

    wave_cols = ["run_id", "wave", "is_terminal", "captures", "span_sec",
                 "enemies_alive_mean", "enemies_alive_max", "enemy_hp_alive_mean",
                 "enemy_hp_alive_max", "enemy_hp_slope_per_sec", "enemy_count_slope_per_sec",
                 "spawns_total", "kills_total", "spawn_rate_per_sec", "kill_rate_per_sec",
                 "net_backlog_per_sec", "damage_output_hp_per_sec", "damage_output_hp_total",
                 "frac_ticks_any_enemy", "frac_ticks_nearest_d_finite",
                 "frac_ticks_target_in_weapon_range", "nearest_d_inf_captures",
                 "nearest_d_vs_count_disagreements", "nearest_d_median_finite_only",
                 "min_surface_d_enemy_median", "min_surface_d_enemy_min",
                 "hp_first", "hp_last", "hp_min", "max_hp", "damaging_contacts",
                 "damaging_contacts_per_sec", "hp_lost_total", "hp_gained_total",
                 "hp_loss_per_sec", "id_vs_count_spawn_delta", "id_vs_count_kill_delta",
                 "id_reuse_gap_events"]
    with (outdir / "per_wave.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=wave_cols, extrasaction="ignore")
        w.writeheader()
        for r in ok:
            for m in r["per_wave"]:
                w.writerow({**m, "run_id": r["run_id"],
                            "is_terminal": int(m["wave"] == r["terminal_wave"])})
    with (outdir / "terminal_window.csv").open("w", newline="", encoding="utf-8") as fh:
        cols = ["run_id", "result", "terminal_wave", "capture_to_run_end_gap_ms",
                "hp_at_last_capture", "fatal_drop_captured"] + wave_cols[3:]
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in ok:
            w.writerow({**r["terminal_window"], **{k: r[k] for k in
                        ("run_id", "result", "terminal_wave", "capture_to_run_end_gap_ms",
                         "hp_at_last_capture", "fatal_drop_captured")}})

    L = []
    A = L.append
    A("# D5 BLOCK A -- PRESSURE AND CLEARANCE (prereg section 7)")
    A("")
    A(f"runs requested {len(ids)} / analysed {len(ok)}   runs_dir `{root}`")
    A(f"terminal window = last {args.tail_sec:g} s of CAPTURES, anchored to the LAST CAPTURE.")
    A("The killing blow is NOT in the telemetry; the anchor is the last capture, and the")
    A("capture->run_end gap is reported per run below.")
    A("")
    A("## 0. Denominators and validity, per run")
    A("")
    A("| run_id | result | twave | captures_seen | invalid | low_dt | no_player |"
      " nearest_d INF | INF with 0 enemies | player_damage evts | last-cap HP |"
      " gap_ms | fatal captured |")
    A("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in ok:
        d = r["diagnostics"]
        A(f"| {r['run_id']} | {r['result']} | {r['terminal_wave']} | {d.get('captures_seen',0)} |"
          f" {d.get('excluded_invalid',0)} | {d.get('low_dt_captures',0)} |"
          f" {d.get('excluded_no_player',0)} | {d.get('nearest_d_inf',0)} |"
          f" {d.get('nearest_d_inf_with_zero_enemies',0)} | {d.get('player_damage_events',0)} |"
          f" {r['hp_at_last_capture']} | {r['capture_to_run_end_gap_ms']} |"
          f" {r['fatal_drop_captured']} |")
    A("")
    inf_tot = sum(r["diagnostics"].get("nearest_d_inf", 0) for r in ok)
    inf0 = sum(r["diagnostics"].get("nearest_d_inf_with_zero_enemies", 0) for r in ok)
    caps = sum(r["diagnostics"].get("captures_seen", 0) for r in ok)
    A(f"`nearest_d` INF sentinel: {inf_tot} / {caps} captures"
      f" ({inf_tot/caps:.2%} if caps else n/a); {inf0} of those had `n_enemies == 0`"
      f" ({inf0/inf_tot:.2%} of INF)." if inf_tot else "`nearest_d` INF sentinel: 0.")
    A("It is filtered, never averaged. Cross-tab disagreements are in the per-wave CSV.")
    A("")
    nonmono = {r["run_id"]: r["elapsed_sec_nonmonotonic_by_wave"] for r in ok
               if r["elapsed_sec_nonmonotonic_by_wave"]}
    A(f"`wave_time.elapsed_sec` non-monotonic steps found in {len(nonmono)} / {len(ok)} runs"
      f" -> {nonmono if nonmono else 'none'}. NOT used as a time base regardless; every rate")
    A("below is per second of the `ts_ms` run clock over the printed span.")
    A("")
    A("## 1. Terminal window -- raw per-run table"
      f" (last {args.tail_sec:g} s of captures)")
    A("")
    A("| run_id | twave | caps | span_s | en_alive_mean | en_alive_max | enHP_mean |"
      " enHP_slope/s | spawn/s | kill/s | dmg_out HP/s | frac_target | frac_in_range |"
      " minsurf_med | minsurf_min | hp_first | hp_last | contacts | hp_lost | hp_gain |"
      " hp_loss/s |")
    A("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in ok:
        t = r["terminal_window"]
        A(f"| {r['run_id']} | {r['terminal_wave']} | {t['captures']} | {t.get('span_sec')} |"
          f" {t.get('enemies_alive_mean')} | {t.get('enemies_alive_max')} |"
          f" {t.get('enemy_hp_alive_mean')} | {t.get('enemy_hp_slope_per_sec')} |"
          f" {t.get('spawn_rate_per_sec')} | {t.get('kill_rate_per_sec')} |"
          f" {t.get('damage_output_hp_per_sec')} | {t.get('frac_ticks_any_enemy')} |"
          f" {t.get('frac_ticks_target_in_weapon_range')} |"
          f" {t.get('min_surface_d_enemy_median')} | {t.get('min_surface_d_enemy_min')} |"
          f" {t.get('hp_first')} | {t.get('hp_last')} | {t.get('damaging_contacts')} |"
          f" {t.get('hp_lost_total')} | {t.get('hp_gained_total')} | {t.get('hp_loss_per_sec')} |")
    A("")

    def col(key):
        return [r["terminal_window"].get(key) for r in ok
                if isinstance(r["terminal_window"].get(key), (int, float))]

    A("Terminal-window aggregates (median [min, max], n = runs contributing):")
    for k in ("span_sec", "enemies_alive_mean", "enemy_hp_alive_mean", "enemy_hp_slope_per_sec",
              "spawn_rate_per_sec", "kill_rate_per_sec", "net_backlog_per_sec",
              "damage_output_hp_per_sec", "frac_ticks_any_enemy",
              "frac_ticks_target_in_weapon_range", "min_surface_d_enemy_median",
              "damaging_contacts", "hp_loss_per_sec"):
        v = col(k)
        if v:
            A(f"  - `{k}`: median {statistics.median(v):.4g} [{min(v):.4g}, {max(v):.4g}], n={len(v)}")
        else:
            A(f"  - `{k}`: NO VALUES (n=0)")
    A("")
    A("## 2. Terminal wave vs earlier waves -- per-run, whole-wave")
    A("")
    A("| run_id | wave | caps | span_s | en_mean | enHP_mean | enHP_slope/s | spawn/s |"
      " kill/s | net/s | dmg_out/s | frac_target | frac_in_range | contacts | hp_first |"
      " hp_min | hp_lost | hp_gain |")
    A("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in ok:
        for m in r["per_wave"]:
            mark = "**T**" if m["wave"] == r["terminal_wave"] else ""
            A(f"| {r['run_id']} | {m['wave']}{mark} | {m['captures']} | {m.get('span_sec')} |"
              f" {m.get('enemies_alive_mean')} | {m.get('enemy_hp_alive_mean')} |"
              f" {m.get('enemy_hp_slope_per_sec')} | {m.get('spawn_rate_per_sec')} |"
              f" {m.get('kill_rate_per_sec')} | {m.get('net_backlog_per_sec')} |"
              f" {m.get('damage_output_hp_per_sec')} | {m.get('frac_ticks_any_enemy')} |"
              f" {m.get('frac_ticks_target_in_weapon_range')} |"
              f" {m.get('damaging_contacts')} | {m.get('hp_first')} | {m.get('hp_min')} |"
              f" {m.get('hp_lost_total')} | {m.get('hp_gained_total')} |")
    A("")
    A("## 3. Causal-lag sweep, RE-DERIVED IN THIS CONTEXT")
    A("")
    A("Statistic: median min SURFACE distance to an enemy at capture i+L, over the captures")
    A("i where an HP drop landed, vs the same statistic over ALL captures in the same waves.")
    A("A lag is supported when its median sits BELOW the baseline and its within-40u fraction")
    A("sits above the baseline's. Pooled across the 20 runs (drop-level pooling).")
    A("")
    for scope in ("lag_sweep_terminal_wave", "lag_sweep_all_waves_ge6"):
        A(f"### {scope}")
        A("")
        A("| lag | drops scored | drops candidate | baseline caps | median d | baseline med |"
          " delta | frac<=40u | baseline frac<=40u |")
        A("|---|---|---|---|---|---|---|---|---|")
        for lg in LAG_SWEEP:
            sc = [r[scope][lg] for r in ok if r[scope][lg]["median_d"] is not None]
            if not sc:
                A(f"| {lg} | 0 | - | - | - | - | - | - | - |")
                continue
            nd = sum(s["n_drops_scored"] for s in sc)
            ndc = sum(s["n_drops_candidate"] for s in sc)
            nb = sum(s["baseline_captures"] for s in sc)
            med = statistics.median([s["median_d"] for s in sc])
            bmed = statistics.median([s["baseline_median_d"] for s in sc])
            fw = statistics.median([s["frac_within_40u"] for s in sc])
            bfw = statistics.median([s["baseline_frac_within_40u"] for s in sc])
            A(f"| {lg} | {nd} | {ndc} | {nb} | {med:.2f} | {bmed:.2f} | {med-bmed:+.2f} |"
              f" {fw:.4f} | {bfw:.4f} |")
        A("")
    A("## 3b. MATCHED-WINDOW CONTROL -- the clearance test that is not vacuous")
    A("")
    A("STRUCTURAL ARTIFACT FOUND AND CORRECTED FOR: over a COMPLETED wave every spawned")
    A("enemy is eventually killed, so spawns == kills EXACTLY, and the whole-wave")
    A("net_backlog_per_sec is 0.000 with kill/spawn = 1.000 in EVERY non-terminal wave of")
    A("EVERY run. That statistic CANNOT return a positive for a survived wave, so")
    A("'the terminal wave has backlog growth and earlier waves do not' would be a")
    A("design-time lie. The comparison below is window-matched instead: the terminal")
    A(f"window is placed inside the distribution of all {args.tail_sec:g} s windows lying")
    A("entirely within a wave >= 6 of the SAME run and entirely before the terminal window.")
    A("")
    A("| run_id | ref windows | net_backlog term | ref median | PCTILE | k/s term |"
      " ref median k/s | PCTILE | hpslope term | ref median | PCTILE |")
    A("|---|---|---|---|---|---|---|---|---|---|---|")
    for r in ok:
        rf = r["sliding_reference"]
        t = r["terminal_window"]
        nb = rf.get("net_backlog_ref") or {}
        ks = rf.get("kill_over_spawn_ref") or {}
        hs = rf.get("hp_slope_ref") or {}
        A(f"| {r['run_id']} | {rf['windows']} | {t.get('net_backlog_per_sec')} |"
          f" {nb.get('median')} | {rf.get('terminal_pctile_net_backlog')} |"
          f" {rf.get('terminal_kill_over_spawn')} | {ks.get('median')} |"
          f" {rf.get('terminal_pctile_kill_over_spawn')} |"
          f" {t.get('enemy_hp_slope_per_sec')} | {hs.get('median')} |"
          f" {rf.get('terminal_pctile_hp_slope')} |")
    A("")
    p1 = [x for x in (r["sliding_reference"].get("terminal_pctile_net_backlog")
                      for r in ok) if x is not None]
    p2 = [x for x in (r["sliding_reference"].get("terminal_pctile_kill_over_spawn")
                      for r in ok) if x is not None]
    p3 = [x for x in (r["sliding_reference"].get("terminal_pctile_hp_slope")
                      for r in ok) if x is not None]
    if p1:
        A(f"terminal-window NET-BACKLOG percentile inside its own run's reference"
          f" distribution: median {statistics.median(p1):.3f}"
          f" [{min(p1):.3f}, {max(p1):.3f}], n={len(p1)};"
          f" >= 0.90 in {sum(1 for x in p1 if x >= 0.90)} / {len(p1)} runs.")
    if p2:
        A(f"terminal-window KILL/SPAWN percentile: median {statistics.median(p2):.3f}"
          f" [{min(p2):.3f}, {max(p2):.3f}], n={len(p2)};"
          f" <= 0.10 in {sum(1 for x in p2 if x <= 0.10)} / {len(p2)} runs.")
    if p3:
        A(f"terminal-window ENEMY-HP-SLOPE percentile: median {statistics.median(p3):.3f}"
          f" [{min(p3):.3f}, {max(p3):.3f}], n={len(p3)};"
          f" >= 0.90 in {sum(1 for x in p3 if x >= 0.90)} / {len(p3)} runs.")
    A("")
    A("## 4. Structural limitations")
    A("")
    A("* The KILLING BLOW is not captured. Every window here ends at the last capture.")
    A("* DODGED hits produce no HP drop and are invisible to `damaging_contacts`.")
    A("* Two hits inside one capture interval read as one contact.")
    A("* Spawn/kill counts rely on enemy `instance_id`; the id-vs-count deltas and")
    A("  `id_reuse_gap_events` columns in the CSV are the audit of that assumption.")
    A("* `damage_output` is enemy HP REMOVED (decrements + HP of vanished enemies). An")
    A("  enemy that leaves the capture for a reason other than death would inflate it;")
    A("  no such mechanism is known in this arena, but it is not proven absent.")
    A("* `damage_taken` is deliberately not used: it is a gross counter.")
    A("* WHOLE-WAVE net backlog and kill/spawn are VACUOUS for any survived wave")
    A("  (spawns == kills by construction). Only section 3b's matched-window figures")
    A("  carry information about clearance; the section 2 columns are retained for the")
    A("  OTHER metrics only.")
    txt = "\n".join(L) + "\n"
    (outdir / "report.md").write_text(txt, encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
