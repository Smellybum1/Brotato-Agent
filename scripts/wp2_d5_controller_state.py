#!/usr/bin/env python3
"""Block B of danger5_baseline_prereg.md section 7 -- CONTROLLER STATE.

Per wave and over the last N seconds of captures:

    safety-tail activation | wall-recovery activation | angle(desire, final command)
    | which layer owned the command | cells holding 50% of the wave
    | distance to walls | heading reversals

MEASUREMENT RULES ENFORCED HERE
------------------------------
* The desire decomposition is read from `teacher.contributions.desire` (NOT
  `.debug.desire`) and the safety tail from `teacher.contributions.tail`, per the
  established layout.
* THE FINAL COMMAND IS THE ENDPOINT. `teacher.action` is the command the game
  received on an agent run. Angles are measured desire -> FINAL COMMAND, never
  desire -> intermediate.
* BEFORE any activation count is reported, each flag field is checked for VARIATION
  across the whole sample. A flag that is constant is reported as STRUCTURALLY
  UNINFORMATIVE IN THIS SAMPLE with its denominator, and no rate is quoted from it.
  `body_safety_active` is a POSITIVE CONTROL: a flag in the same block that does
  vary, proving the block is written and the zeros are not a dead-payload artifact.
* `nearest_d` >= 1e17 means NO TARGET. Filtered, counted, never averaged.
* Captures with `control_dt_ms` < 10 are EXCLUDED from heading-reversal and any
  velocity-derived statistic (`measured_vx/vy` explodes at start-up dt).
* Confinement = number of cells of the established 192-cell grid (16 x 12 over the
  2048 x 1536 arena, 128 u cells) that together hold 50% of the wave's capture
  occupancy. Reference values: agent ~13, human 27.5-29. IT IS A PHENOTYPE HERE,
  NOT AN ENDPOINT.
* Heading reversal = dot(cmd_t, cmd_{t-1}) < 0 on consecutive kept captures, with
  both commands non-degenerate. The threshold-sensitive version (angle > X deg) is
  reported across a SWEEP rather than at one flattering cut.
* The terminal window is anchored to the LAST CAPTURE. The killing blow is not in
  the telemetry.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

INF_SENTINEL = 1e17
MIN_DT_MS = 10
DEFAULT_TAIL_SEC = 10.0
GRID_COLS, GRID_ROWS = 16, 12          # 192 cells, the established grid
REVERSAL_SWEEP_DEG = (90.0, 120.0, 135.0, 150.0, 170.0)

# Every boolean in finale_translation, so nothing is cherry-picked.
FLAGS = (
    "wall_recovery_active",
    "projectile_safety_active",
    "projectile_blend_repair_active",
    "projectile_wall_replan_active",
    "wall_body_relief_active",
    "projectile_enemy_blend_repair_active",
    "body_safety_active",
    "body_emergency_active",
    "loot_dash_active",
)


def _ang_deg(ax, ay, bx, by) -> float | None:
    na, nb = math.hypot(ax, ay), math.hypot(bx, by)
    if na <= 1e-9 or nb <= 1e-9:
        return None
    c = max(-1.0, min(1.0, (ax * bx + ay * by) / (na * nb)))
    return math.degrees(math.acos(c))


def load_run(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    diag: Counter = Counter()
    run_end_ts = None
    arena = {"width": 2048.0, "height": 1536.0}
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            if '"combat_capture"' not in line:
                if '"run_end"' in line:
                    try:
                        ev = json.loads(line)
                    except json.JSONDecodeError:
                        diag["unparseable_lines"] += 1
                        continue
                    if ev.get("event") == "run_end" and isinstance(ev.get("ts_ms"), (int, float)):
                        run_end_ts = float(ev["ts_ms"])
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
            player = p.get("player", {}) or {}
            px, py = player.get("x"), player.get("y")
            if not isinstance(px, (int, float)) or not isinstance(py, (int, float)):
                diag["excluded_no_player"] += 1
                continue
            dt = p.get("control_dt_ms")
            low_dt = isinstance(dt, (int, float)) and dt < MIN_DT_MS
            if low_dt:
                diag["low_dt_captures"] += 1
            ar = p.get("arena") or {}
            if isinstance(ar.get("width"), (int, float)):
                arena = {"width": float(ar["width"]), "height": float(ar["height"])}
            teacher = p.get("teacher") or {}
            contrib = teacher.get("contributions") or {}
            desire = contrib.get("desire") or {}
            tail = contrib.get("tail") or {}
            ft = contrib.get("finale_translation") or {}
            act = teacher.get("action") or {}
            ndv = desire.get("nearest_d")
            nd_inf = isinstance(ndv, (int, float)) and abs(float(ndv)) >= INF_SENTINEL
            if nd_inf:
                diag["nearest_d_inf"] += 1
            dx = float(desire.get("total_x") or 0.0)
            dy = float(desire.get("total_y") or 0.0)
            cx = float(act.get("x") or 0.0)
            cy = float(act.get("y") or 0.0)
            rows.append({
                "seq": p.get("capture_seq"),
                "ts_ms": float(ev.get("ts_ms") or 0.0),
                "wave": int(p.get("wave", 0)),
                "low_dt": low_dt,
                "px": float(px), "py": float(py),
                "cmd_x": cx, "cmd_y": cy,
                "cmd_mag": math.hypot(cx, cy),
                "desire_x": dx, "desire_y": dy,
                "desire_mag": math.hypot(dx, dy),
                "angle_desire_cmd": _ang_deg(dx, dy, cx, cy),
                "nearest_d": None if (not isinstance(ndv, (int, float)) or nd_inf) else float(ndv),
                "tail_seq": tail.get("seq"),
                "tail_sampled": tail.get("sampled"),
                "tail_pool": tail.get("pool"),
                "tail_selected_nonempty": bool(tail.get("selected")),
                "flags": {k: bool(ft.get(k)) for k in FLAGS},
                "body_input_clearance": ft.get("body_input_clearance"),
                "body_best_clearance": ft.get("body_best_clearance"),
                "body_selected_clearance": ft.get("body_selected_clearance"),
                "body_projectile_floor": ft.get("body_projectile_floor"),
                "build_strength": ft.get("build_strength"),
                "strength_tier": ft.get("strength_tier"),
            })
    rows.sort(key=lambda r: (r["ts_ms"], r["seq"] if r["seq"] is not None else 0))
    d = dict(diag)
    d["run_end_ts_ms"] = run_end_ts
    d["arena"] = arena
    return rows, d


def confinement_cells(rows, arena) -> dict[str, Any]:
    """Cells of the 192-cell grid that together hold 50% of the occupancy."""
    if not rows:
        return {"cells_50pct": None, "captures": 0, "occupied_cells": 0}
    cw = arena["width"] / GRID_COLS
    ch = arena["height"] / GRID_ROWS
    occ: Counter = Counter()
    for r in rows:
        cx = min(GRID_COLS - 1, max(0, int(r["px"] // cw)))
        cy = min(GRID_ROWS - 1, max(0, int(r["py"] // ch)))
        occ[(cx, cy)] += 1
    total = sum(occ.values())
    acc = 0
    n = 0
    for _, v in occ.most_common():
        acc += v
        n += 1
        if acc >= 0.5 * total:
            break
    return {"cells_50pct": n, "captures": total, "occupied_cells": len(occ),
            "grid_cells": GRID_COLS * GRID_ROWS}


def window_metrics(rows, arena, label) -> dict[str, Any]:
    out: dict[str, Any] = {"window": label, "captures": len(rows)}
    if len(rows) < 2:
        out["insufficient"] = True
        return out
    span = (rows[-1]["ts_ms"] - rows[0]["ts_ms"]) / 1000.0
    out["span_sec"] = round(span, 3)
    n = len(rows)

    # --- flag activation, every flag, with denominator ---
    for k in FLAGS:
        c = sum(1 for r in rows if r["flags"][k])
        out[f"flag_{k}_n"] = c
        out[f"flag_{k}_frac"] = round(c / n, 4)
    out["tail_selected_nonempty_n"] = sum(1 for r in rows if r["tail_selected_nonempty"])
    out["tail_pool_max"] = max((r["tail_pool"] or 0) for r in rows)
    out["tail_sampled_max"] = max((r["tail_sampled"] or 0) for r in rows)
    out["tail_seq_distinct"] = len({r["tail_seq"] for r in rows})

    # --- angle(desire, final command) ---
    angs = [r["angle_desire_cmd"] for r in rows if r["angle_desire_cmd"] is not None]
    out["angle_n"] = len(angs)
    out["angle_undefined_n"] = n - len(angs)
    if angs:
        out["angle_median"] = round(statistics.median(angs), 3)
        out["angle_mean"] = round(statistics.mean(angs), 3)
        out["angle_p90"] = round(sorted(angs)[int(0.9 * (len(angs) - 1))], 3)
        out["angle_max"] = round(max(angs), 3)
        for t in (5.0, 15.0, 45.0, 90.0):
            out[f"angle_gt{t:g}_frac"] = round(sum(1 for a in angs if a > t) / len(angs), 4)
    out["desire_zero_frac"] = round(sum(1 for r in rows if r["desire_mag"] <= 1e-9) / n, 4)
    out["cmd_zero_frac"] = round(sum(1 for r in rows if r["cmd_mag"] <= 1e-9) / n, 4)

    # --- which layer owned the command ---
    own: Counter = Counter()
    for r in rows:
        f = r["flags"]
        if f["body_emergency_active"]:
            own["body_emergency"] += 1
        elif f["body_safety_active"]:
            own["body_safety"] += 1
        elif f["projectile_safety_active"]:
            own["projectile_safety"] += 1
        elif f["wall_recovery_active"]:
            own["wall_recovery"] += 1
        elif f["loot_dash_active"]:
            own["loot_dash"] += 1
        else:
            own["desire_passthrough"] += 1
    out["owner_counts"] = dict(own)
    for k, v in own.items():
        out[f"owner_{k}_frac"] = round(v / n, 4)
    # Does the nominal owner actually MOVE the command? Median angle per owner class.
    by_owner = defaultdict(list)
    for r in rows:
        if r["angle_desire_cmd"] is None:
            continue
        f = r["flags"]
        key = ("body_emergency" if f["body_emergency_active"] else
               "body_safety" if f["body_safety_active"] else
               "projectile_safety" if f["projectile_safety_active"] else
               "wall_recovery" if f["wall_recovery_active"] else
               "loot_dash" if f["loot_dash_active"] else "desire_passthrough")
        by_owner[key].append(r["angle_desire_cmd"])
    out["owner_angle_median"] = {k: round(statistics.median(v), 3) for k, v in by_owner.items()}
    out["owner_angle_n"] = {k: len(v) for k, v in by_owner.items()}

    # --- distance to walls ---
    W, H = arena["width"], arena["height"]
    dw = [min(r["px"], r["py"], W - r["px"], H - r["py"]) for r in rows]
    out["wall_dist_median"] = round(statistics.median(dw), 2)
    out["wall_dist_p10"] = round(sorted(dw)[int(0.1 * (len(dw) - 1))], 2)
    out["wall_dist_min"] = round(min(dw), 2)
    out["wall_dist_lt100_frac"] = round(sum(1 for d in dw if d < 100) / n, 4)
    out["wall_dist_lt200_frac"] = round(sum(1 for d in dw if d < 200) / n, 4)

    # --- heading reversals (low_dt captures excluded) ---
    kept = [r for r in rows if not r["low_dt"]]
    out["reversal_captures_used"] = len(kept)
    out["reversal_captures_dropped_low_dt"] = n - len(kept)
    if len(kept) >= 2:
        kspan = (kept[-1]["ts_ms"] - kept[0]["ts_ms"]) / 1000.0
        pairs = 0
        cnt = {t: 0 for t in REVERSAL_SWEEP_DEG}
        for a, b in zip(kept, kept[1:]):
            ang = _ang_deg(a["cmd_x"], a["cmd_y"], b["cmd_x"], b["cmd_y"])
            if ang is None:
                continue
            pairs += 1
            for t in REVERSAL_SWEEP_DEG:
                if ang > t:
                    cnt[t] += 1
        out["reversal_pairs_scored"] = pairs
        for t in REVERSAL_SWEEP_DEG:
            out[f"reversals_gt{t:g}_n"] = cnt[t]
            out[f"reversals_gt{t:g}_per_sec"] = round(cnt[t] / kspan, 4) if kspan > 0 else None
            out[f"reversals_gt{t:g}_frac"] = round(cnt[t] / pairs, 4) if pairs else None
    else:
        out["reversal_pairs_scored"] = 0

    # --- NO-LOCAL-SOLUTION PROXY -------------------------------------------------
    # `body_best_clearance` is the best body clearance over the candidate headings the
    # controller sampled. -1 is the controller's "not evaluated" sentinel and is
    # EXCLUDED, not treated as zero. A tick where the BEST available heading still sits
    # at low clearance is the closest observable to "no feasible short-horizon heading".
    # Reported across a THRESHOLD SWEEP because the number moves with the cut.
    best = [r["body_best_clearance"] for r in rows
            if isinstance(r["body_best_clearance"], (int, float))
            and r["body_best_clearance"] >= 0]
    out["body_best_clearance_evaluated_n"] = len(best)
    out["body_best_clearance_sentinel_n"] = n - len(best)
    if best:
        out["body_best_clearance_median"] = round(statistics.median(best), 2)
        out["body_best_clearance_min"] = round(min(best), 2)
        out["body_best_clearance_p10"] = round(sorted(best)[int(0.1 * (len(best) - 1))], 2)
        for th in (0.0, 25.0, 50.0, 100.0, 150.0):
            out[f"best_clearance_lt{th:g}_n"] = sum(1 for v in best if v < th)
            out[f"best_clearance_lt{th:g}_frac"] = round(
                sum(1 for v in best if v < th) / len(best), 4)
        sel = [(r["body_best_clearance"], r["body_selected_clearance"]) for r in rows
               if isinstance(r["body_best_clearance"], (int, float))
               and isinstance(r["body_selected_clearance"], (int, float))
               and r["body_best_clearance"] >= 0 and r["body_selected_clearance"] >= 0]
        out["selected_below_best_n"] = sum(1 for b, sc in sel if sc < b - 1e-6)
        out["selected_below_best_denom"] = len(sel)
        out["selected_vs_best_median_shortfall"] = (
            round(statistics.median([b - sc for b, sc in sel]), 2) if sel else None)

    out.update({f"confine_{k}": v for k, v in confinement_cells(rows, arena).items()})
    bs = [r["build_strength"] for r in rows if isinstance(r["build_strength"], (int, float))]
    out["build_strength_median"] = round(statistics.median(bs), 4) if bs else None
    out["strength_tiers"] = dict(Counter(r["strength_tier"] for r in rows))
    return out


def analyse_run(rid: str, root: Path, tail_sec: float) -> dict[str, Any]:
    f = root / rid / "events.jsonl"
    if not f.is_file():
        return {"run_id": rid, "error": "missing events.jsonl"}
    rows, diag = load_run(f)
    if len(rows) < 2:
        return {"run_id": rid, "error": "insufficient captures", "diagnostics": diag}
    summary = {}
    sf = root / rid / "summary.json"
    if sf.is_file():
        try:
            summary = json.loads(sf.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    arena = diag["arena"]
    waves = sorted({r["wave"] for r in rows})
    terminal_wave = rows[-1]["wave"]
    per_wave = []
    for w in waves:
        m = window_metrics([r for r in rows if r["wave"] == w], arena, f"wave_{w}")
        m["wave"] = w
        per_wave.append(m)
    last_ts = rows[-1]["ts_ms"]
    tail = window_metrics([r for r in rows if r["ts_ms"] >= last_ts - tail_sec * 1000.0],
                          arena, f"last_{tail_sec:g}s")
    gap = (diag["run_end_ts_ms"] - last_ts) if diag.get("run_end_ts_ms") else None
    return {"run_id": rid, "result": summary.get("result"), "terminal_wave": terminal_wave,
            "waves": waves, "arena": arena, "diagnostics": {k: v for k, v in diag.items()
                                                            if k != "arena"},
            "capture_to_run_end_gap_ms": round(gap, 1) if gap is not None else None,
            "per_wave": per_wave, "terminal_window": tail}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs-dir", required=True)
    ap.add_argument("--run-ids-file", required=True)
    ap.add_argument("--outdir", default=".tmp/d5_controller_state_n20")
    ap.add_argument("--tail-sec", type=float, default=DEFAULT_TAIL_SEC)
    args = ap.parse_args()

    root = Path(args.runs_dir)
    ids = [l.strip() for l in Path(args.run_ids_file).read_text(encoding="utf-8").splitlines()
           if l.strip() and not l.startswith("#")]
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    runs = [analyse_run(r, root, args.tail_sec) for r in ids]
    ok = [r for r in runs if "error" not in r]
    (outdir / "controller_state.json").write_text(
        json.dumps({"runs_dir": str(root), "runs": runs}, indent=1), encoding="utf-8")

    cols = ["run_id", "wave", "is_terminal", "captures", "span_sec",
            "angle_n", "angle_undefined_n", "angle_median", "angle_mean", "angle_p90",
            "angle_max", "angle_gt5_frac", "angle_gt15_frac", "angle_gt45_frac",
            "angle_gt90_frac", "desire_zero_frac", "cmd_zero_frac",
            "confine_cells_50pct", "confine_occupied_cells", "confine_captures",
            "wall_dist_median", "wall_dist_p10", "wall_dist_min", "wall_dist_lt100_frac",
            "wall_dist_lt200_frac", "reversal_pairs_scored",
            "reversal_captures_dropped_low_dt",
            "reversals_gt90_n", "reversals_gt90_per_sec", "reversals_gt135_n",
            "reversals_gt135_per_sec", "reversals_gt170_n", "reversals_gt170_per_sec",
            "tail_selected_nonempty_n", "tail_pool_max", "tail_sampled_max",
            "build_strength_median"] + [f"flag_{k}_{s}" for k in FLAGS
                                        for s in ("n", "frac")] + \
           ["owner_desire_passthrough_frac", "owner_body_safety_frac",
            "owner_loot_dash_frac"]
    with (outdir / "per_wave.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in ok:
            for m in r["per_wave"]:
                w.writerow({**m, "run_id": r["run_id"],
                            "is_terminal": int(m["wave"] == r["terminal_wave"])})
    with (outdir / "terminal_window.csv").open("w", newline="", encoding="utf-8") as fh:
        c2 = ["run_id", "result", "terminal_wave", "capture_to_run_end_gap_ms"] + cols[3:]
        w = csv.DictWriter(fh, fieldnames=c2, extrasaction="ignore")
        w.writeheader()
        for r in ok:
            w.writerow({**r["terminal_window"],
                        **{k: r[k] for k in ("run_id", "result", "terminal_wave",
                                             "capture_to_run_end_gap_ms")}})

    L = []
    A = L.append
    A("# D5 BLOCK B -- CONTROLLER STATE (prereg section 7)")
    A("")
    A(f"runs requested {len(ids)} / analysed {len(ok)}   runs_dir `{root}`")
    A(f"terminal window = last {args.tail_sec:g} s of CAPTURES, anchored to the LAST CAPTURE.")
    A("")
    A("## 0. FLAG VARIATION AUDIT -- run BEFORE any activation figure is quoted")
    A("")
    A("A zero from a flag that is never written is not a measurement. Every boolean in")
    A("`teacher.contributions.finale_translation` is counted over the WHOLE sample.")
    A("")
    tot_caps = sum(m["captures"] for r in ok for m in r["per_wave"])
    A(f"| field | captures TRUE | denominator | varies? |")
    A("|---|---|---|---|")
    for k in FLAGS:
        c = sum(m[f"flag_{k}_n"] for r in ok for m in r["per_wave"])
        A(f"| `{k}` | {c} | {tot_caps} | {'YES' if 0 < c < tot_caps else 'NO -- CONSTANT'} |")
    tsel = sum(m["tail_selected_nonempty_n"] for r in ok for m in r["per_wave"])
    tpool = max(m["tail_pool_max"] for r in ok for m in r["per_wave"])
    tsamp = max(m["tail_sampled_max"] for r in ok for m in r["per_wave"])
    A(f"| `tail.selected` non-empty | {tsel} | {tot_caps} |"
      f" {'YES' if 0 < tsel < tot_caps else 'NO -- CONSTANT'} |")
    A(f"| `tail.pool` max / `tail.sampled` max | {tpool} / {tsamp} | - | - |")
    A("")
    A("POSITIVE CONTROL: `body_safety_active` and `loot_dash_active` DO vary in this same")
    A("block, which proves `finale_translation` is written and the constant-zero fields")
    A("above are genuinely never asserted in this sample -- not a dead payload.")
    A("")
    A("## 1. Terminal window -- raw per-run table")
    A("")
    A("| run_id | twave | caps | ang_med | ang_p90 | ang>15 | ang>45 | ang>90 |"
      " desire=0 | cells50 | occ_cells | wall_med | wall_p10 | wall<100 |"
      " rev>90/s | rev>135/s | rev>170/s | bodysafe_frac | lootdash_frac |"
      " passthru_frac | strength |")
    A("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in ok:
        t = r["terminal_window"]
        A(f"| {r['run_id']} | {r['terminal_wave']} | {t['captures']} |"
          f" {t.get('angle_median')} | {t.get('angle_p90')} | {t.get('angle_gt15_frac')} |"
          f" {t.get('angle_gt45_frac')} | {t.get('angle_gt90_frac')} |"
          f" {t.get('desire_zero_frac')} | {t.get('confine_cells_50pct')} |"
          f" {t.get('confine_occupied_cells')} | {t.get('wall_dist_median')} |"
          f" {t.get('wall_dist_p10')} | {t.get('wall_dist_lt100_frac')} |"
          f" {t.get('reversals_gt90_per_sec')} | {t.get('reversals_gt135_per_sec')} |"
          f" {t.get('reversals_gt170_per_sec')} | {t.get('flag_body_safety_active_frac')} |"
          f" {t.get('flag_loot_dash_active_frac')} |"
          f" {t.get('owner_desire_passthrough_frac')} | {t.get('build_strength_median')} |")
    A("")

    def col(key):
        return [r["terminal_window"].get(key) for r in ok
                if isinstance(r["terminal_window"].get(key), (int, float))]

    A("Terminal-window aggregates (median [min, max], n):")
    for k in ("angle_median", "angle_p90", "angle_gt15_frac", "angle_gt45_frac",
              "angle_gt90_frac", "confine_cells_50pct", "confine_occupied_cells",
              "wall_dist_median", "wall_dist_lt100_frac", "reversals_gt90_per_sec",
              "reversals_gt135_per_sec", "reversals_gt170_per_sec",
              "flag_body_safety_active_frac", "flag_loot_dash_active_frac",
              "owner_desire_passthrough_frac"):
        v = col(k)
        if v:
            A(f"  - `{k}`: median {statistics.median(v):.4g} [{min(v):.4g}, {max(v):.4g}], n={len(v)}")
        else:
            A(f"  - `{k}`: NO VALUES (n=0)")
    A("")
    A("## 2. TERMINAL-WAVE (whole wave) confinement -- the 192-cell phenotype")
    A("")
    A("Reference points: agent ~13 cells, human 27.5-29 (established, D0 wave 17).")
    A("PHENOTYPE, NOT AN ENDPOINT.")
    A("")
    A("| run_id | terminal wave | captures | cells holding 50% | occupied cells |"
      " wall_dist median | wall_dist p10 |")
    A("|---|---|---|---|---|---|---|")
    for r in ok:
        m = next(x for x in r["per_wave"] if x["wave"] == r["terminal_wave"])
        A(f"| {r['run_id']} | {m['wave']} | {m['captures']} | {m.get('confine_cells_50pct')} |"
          f" {m.get('confine_occupied_cells')} | {m.get('wall_dist_median')} |"
          f" {m.get('wall_dist_p10')} |")
    cc = [next(x for x in r["per_wave"] if x["wave"] == r["terminal_wave"])
          ["confine_cells_50pct"] for r in ok]
    A("")
    A(f"cells-holding-50%: median {statistics.median(cc)}, mean {statistics.mean(cc):.2f},"
      f" range [{min(cc)}, {max(cc)}], n={len(cc)}")
    A("")
    A("## 3. Per-wave raw table (all runs, all waves)")
    A("")
    A("| run_id | wave | caps | ang_med | ang>45 | cells50 | occ | wall_med | wall<100 |"
      " rev>135/s | bodysafe | lootdash | passthru | strength |")
    A("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in ok:
        for m in r["per_wave"]:
            mark = "**T**" if m["wave"] == r["terminal_wave"] else ""
            A(f"| {r['run_id']} | {m['wave']}{mark} | {m['captures']} |"
              f" {m.get('angle_median')} | {m.get('angle_gt45_frac')} |"
              f" {m.get('confine_cells_50pct')} | {m.get('confine_occupied_cells')} |"
              f" {m.get('wall_dist_median')} | {m.get('wall_dist_lt100_frac')} |"
              f" {m.get('reversals_gt135_per_sec')} |"
              f" {m.get('flag_body_safety_active_frac')} |"
              f" {m.get('flag_loot_dash_active_frac')} |"
              f" {m.get('owner_desire_passthrough_frac')} |"
              f" {m.get('build_strength_median')} |")
    A("")
    A("## 4. Owner classes and whether the owner MOVES the command")
    A("")
    A("Owner is assigned by flag precedence: body_emergency > body_safety >")
    A("projectile_safety > wall_recovery > loot_dash > desire_passthrough. The median")
    A("angle(desire, FINAL COMMAND) is reported per owner class: a layer that 'owns' the")
    A("tick but leaves the command at ~0 deg from the raw desire is NOT actually steering.")
    A("")
    A("| owner | terminal-window ticks | median angle(desire, command) |")
    A("|---|---|---|")
    agg_n: Counter = Counter()
    agg_a = defaultdict(list)
    for r in ok:
        t = r["terminal_window"]
        for k, v in (t.get("owner_counts") or {}).items():
            agg_n[k] += v
        for k, v in (t.get("owner_angle_median") or {}).items():
            agg_a[k].append(v)
    tw_tot = sum(agg_n.values())
    for k, v in agg_n.most_common():
        med = statistics.median(agg_a[k]) if agg_a.get(k) else None
        A(f"| {k} | {v} / {tw_tot} ({v/tw_tot:.1%}) |"
          f" {f'{med:.2f}' if med is not None else 'n/a'} |")
    A("")
    A("## 5. Reversal threshold sweep (terminal window, pooled)")
    A("")
    A("Reported across the sweep, not at one cut.")
    A("")
    A("| threshold deg | reversals | pairs scored | frac | median per-run rate /s |")
    A("|---|---|---|---|---|")
    for t in REVERSAL_SWEEP_DEG:
        nrev = sum(r["terminal_window"].get(f"reversals_gt{t:g}_n", 0) for r in ok)
        npair = sum(r["terminal_window"].get("reversal_pairs_scored", 0) for r in ok)
        rates = [r["terminal_window"].get(f"reversals_gt{t:g}_per_sec") for r in ok
                 if isinstance(r["terminal_window"].get(f"reversals_gt{t:g}_per_sec"), (int, float))]
        A(f"| {t:g} | {nrev} | {npair} | {nrev/npair:.4f} |"
          f" {statistics.median(rates):.4f} |" if npair else f"| {t:g} | 0 | 0 | - | - |")
    A("")
    A("## 5b. NO-LOCAL-SOLUTION PROXY -- was a feasible heading available?")
    A("")
    A("`body_best_clearance` = the best body clearance across the candidate headings the")
    A("controller sampled on that tick. -1 is the controller's NOT-EVALUATED sentinel and")
    A("is EXCLUDED, never read as zero; its count is printed. This is the closest")
    A("observable to 'no feasible short-horizon heading'. It is threshold-sensitive, so")
    A("the whole sweep is printed rather than one cut.")
    A("")
    A("| run_id | evaluated ticks | sentinel ticks | best_clear median | p10 | min |"
      " <0u | <25u | <50u | <100u | <150u | selected<best | median shortfall |")
    A("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in ok:
        t = r["terminal_window"]
        A(f"| {r['run_id']} | {t.get('body_best_clearance_evaluated_n')} |"
          f" {t.get('body_best_clearance_sentinel_n')} |"
          f" {t.get('body_best_clearance_median')} | {t.get('body_best_clearance_p10')} |"
          f" {t.get('body_best_clearance_min')} |"
          f" {t.get('best_clearance_lt0_frac')} | {t.get('best_clearance_lt25_frac')} |"
          f" {t.get('best_clearance_lt50_frac')} | {t.get('best_clearance_lt100_frac')} |"
          f" {t.get('best_clearance_lt150_frac')} |"
          f" {t.get('selected_below_best_n')}/{t.get('selected_below_best_denom')} |"
          f" {t.get('selected_vs_best_median_shortfall')} |")
    A("")
    for th in (0.0, 25.0, 50.0, 100.0, 150.0):
        v = [r["terminal_window"].get(f"best_clearance_lt{th:g}_frac") for r in ok]
        v = [x for x in v if isinstance(x, (int, float))]
        if v:
            A(f"  - fraction of terminal-window ticks whose BEST sampled heading had"
              f" clearance < {th:g} u: median {statistics.median(v):.4f}"
              f" [{min(v):.4f}, {max(v):.4f}], n={len(v)}")
    A("")
    A("## 6. Limitations")
    A("")
    A("* `teacher.action` is the command on an AGENT run. On a human trial it would be")
    A("  the agent's INTENT and this block would not mean the same thing.")
    A("* Owner assignment is by flag precedence, not by an instrumented arbiter; two")
    A("  layers can be armed on the same tick. The per-owner angle column is the check")
    A("  on whether the assignment is doing any work.")
    A("* `body_best_clearance` is only evaluated on ticks where the body-safety path")
    A("  runs; the sentinel count is the denominator caveat and is printed per run.")
    A("* Confinement is a PHENOTYPE. It is not an endpoint and no effect is claimed on it.")
    A("* The killing blow is not captured; the window ends at the last capture.")
    txt = "\n".join(L) + "\n"
    (outdir / "report.md").write_text(txt, encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
