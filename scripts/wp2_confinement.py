#!/usr/bin/env python3
"""Confinement screen readout for `tail_calm_clearance_mult` (mod 0.2.55).

This script REPORTS.  It does not decide.  The decision rule it evaluates is
fixed in `reports/wp2/confinement_screen_prereg.md` and is transcribed here
mechanically, with every one of its inputs printed next to the verdict so it
can be checked by hand.

PRIMARY ENDPOINT -- occupancy concentration.  Wave-17 player positions are
binned into 128 u cells (16 x 12 = 192 cells for a 2048x1536 arena; the count
is COMPUTED from the capture's own `arena`, never hardcoded).  Cells are sorted
by occupancy descending and we count how many are needed to reach >= 50% of
captures.  Higher = roams more = more human-like.  Observed: human 33, agent
controls 10 and 12.

SECONDARY (recorded, not decision-bearing):
  * distinct cells visited
  * corner occupancy at 300/400/500 u, ALWAYS printed next to its
    uniform-random baseline 4*R^2/(W*H) and the ratio to it -- a bare corner
    fraction is misleading because a 400 u corner box is ~20% of the arena
  * radius of gyration (RMS distance of positions from their own centroid)
  * median distance from arena centre and median distance to the nearest wall
    -- these are the metrics that FAILED to separate human from agent on this
    fixture; they stay visible so nobody re-derives them
  * pooled approach velocity to the nearest `pursuer` within 600 u

DISCIPLINE baked into the output:
  * ACTUAL DISPLACEMENT between consecutive captures is used for every
    directional quantity.  `teacher.action` is the agent's INTENT and in a
    human trial is not what executed -- it is never read here.
  * captures with `control_dt_ms` < 10 are excluded (measured velocity
    explodes at start-up).
  * every ratio is printed next to its denominator; a zero denominator prints
    `n/a`, never 0.
  * a run with no events.jsonl or no wave-17 captures is named explicitly and
    excluded from the aggregates with a stated count.
  * NO body-clearance diagnostic is printed: at a non-unit dose
    `_predictive_body_path_clearance` returns an inflated value, so those
    fields are not comparable across arms.

No gameplay is run; nothing is written to the runs dir.

Usage (repo root, venv python):

    set APPDATA=C:\\Users\\moxhe\\AppData\\Roaming
    .venv\\Scripts\\python.exe scripts\\wp2_confinement.py \\
        --trials .tmp/gate0/conf_screen.jsonl [--json out.json]

    .venv\\Scripts\\python.exe scripts\\wp2_confinement.py \\
        --run-id run_1785322175_88461 [--run-id ...] [--runs-dir DIR] \\
        [--wave 17]
"""
from __future__ import annotations

import argparse
import json
import math
import os
import statistics
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Sequence, Tuple

# ---------------------------------------------------------------------------
# constants (all echoed in the output so nothing is hidden)
# ---------------------------------------------------------------------------

DEFAULT_WAVE = 17
CELL_SIZE = 128.0              # prereg: 128 u cells
DEFAULT_ARENA_W = 2048.0
DEFAULT_ARENA_H = 1536.0
CORNER_RADII = (300.0, 400.0, 500.0)
PURSUER_RADIUS = 600.0
MIN_CONTROL_DT_MS = 10.0
HUMAN_PRIMARY = 33             # the human reference value the rule points at
CONTROL_DOSE = 1.0             # tail_calm_clearance_mult == 1.0 is exactly inert
DOSE_KEY = "tail_calm_clearance_mult"
SURVIVAL_WAVE = 18             # wave-17 trial "survived" iff wave 18 was captured


# ---------------------------------------------------------------------------
# locating runs / captures -- same convention as scripts/wp2_tail_decomposition.py
# ---------------------------------------------------------------------------


def runs_dir(override: Optional[str] = None) -> Path:
    if override:
        return Path(override)
    env = os.environ.get("WP2_RUNS_DIR")
    if env:
        return Path(env)
    return Path(os.environ["APPDATA"]) / "Brotato" / "brotato_agent" / "runs"


def iter_captures(run_dir: Path) -> Iterator[Dict[str, Any]]:
    """Yield ``payload`` dicts of combat_capture events, in file order."""
    path = run_dir / "events.jsonl"
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                evt = json.loads(line)
            except json.JSONDecodeError:
                continue           # malformed/truncated line
            if evt.get("event") != "combat_capture":
                continue
            payload = evt.get("payload")
            if isinstance(payload, dict):
                yield payload


def load_summary(run_dir: Path) -> Dict[str, Any]:
    path = run_dir / "summary.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def dig(obj: Any, *keys, default=None):
    for key in keys:
        if not isinstance(obj, dict):
            return default
        obj = obj.get(key)
        if obj is None:
            return default
    return obj


def read_trials(path: Path) -> List[Dict[str, Any]]:
    """Rows of a wp2_finale_loop trials jsonl, in file order, deduped by run_id.

    Each row carries `label`, `tail_calm_clearance_mult` (the arm assignment)
    and `damage_taken` (a safety-guard input).
    """
    rows: List[Dict[str, Any]] = []
    seen = set()
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            rid = rec.get("run_id")
            if isinstance(rid, str) and rid and rid not in seen:
                seen.add(rid)
                rows.append(rec)
    return rows


def arm_of(dose: Any, human_movement: Any = None) -> str:
    """Three arms: `human`, `control`, `treatment` (or `unknown`).

    MISLABELLING TRAP THIS CLOSES.  A human-handover trial runs with the dose
    at its inert 1.0, so a dose-only rule labels it `control` and it pools
    silently into the AGENT control arm.  That is the same failure shape
    already recorded on this project as "an entry-build fingerprint does not
    identify a trial's arm": grouping on a key that CANNOT SEE the treatment.
    The dose is not the treatment here -- who holds the controller is.

    Order matters and is not negotiable:

      1. `human_movement is True`  -> `human`, WHATEVER the dose.
      2. `human_movement` ABSENT   -> `unknown`.  The field only exists on
         newer builds, so its absence is silence, not a denial.  Never assume
         agent.
      3. only once the run is a CONFIRMED agent run does the dose decide
         control (exactly the inert 1.0) vs treatment.

    The three arms are reported separately and are NEVER merged.
    """
    if human_movement is True:
        return "human"
    if human_movement is not False:
        # None (field absent) or any non-boolean -- provenance unknown.
        return "unknown"
    if dose is None:
        return "unknown"
    try:
        return "control" if float(dose) == CONTROL_DOSE else "treatment"
    except (TypeError, ValueError):
        return "unknown"


def human_movement_of(run_dir: Path) -> Any:
    """`summary.json`'s `human_movement`, or None when the field is ABSENT.

    Read from the RUN's own summary, not from the trials row: the summary is
    what the build actually recorded.  A missing summary.json is also None ->
    `unknown`, never `control`.
    """
    return load_summary(run_dir).get("human_movement")


# ---------------------------------------------------------------------------
# metrics
# ---------------------------------------------------------------------------


def arena_of(payloads: Sequence[Dict[str, Any]]) -> Tuple[float, float]:
    """(W, H) from the first capture that carries an `arena`; else the default."""
    for p in payloads:
        arena = p.get("arena")
        if isinstance(arena, dict):
            w = float(arena.get("width", DEFAULT_ARENA_W) or DEFAULT_ARENA_W)
            h = float(arena.get("height", DEFAULT_ARENA_H) or DEFAULT_ARENA_H)
            if w > 0 and h > 0:
                return w, h
    return DEFAULT_ARENA_W, DEFAULT_ARENA_H


def grid_shape(w: float, h: float, cell: float = CELL_SIZE) -> Tuple[int, int, int]:
    """(ncols, nrows, total cells).  COMPUTED, never hardcoded to 192."""
    ncols = max(1, int(math.ceil(w / cell)))
    nrows = max(1, int(math.ceil(h / cell)))
    return ncols, nrows, ncols * nrows


def occupancy_concentration(positions: Sequence[Tuple[float, float]],
                            w: float, h: float,
                            cell: float = CELL_SIZE) -> Dict[str, Any]:
    """PRIMARY.  Cells needed (largest-first) to cover >= 50% of captures."""
    ncols, nrows, total_cells = grid_shape(w, h, cell)
    counts: Dict[Tuple[int, int], int] = {}
    n = 0
    for x, y in positions:
        cx = min(ncols - 1, max(0, int(x // cell)))
        cy = min(nrows - 1, max(0, int(y // cell)))
        counts[(cx, cy)] = counts.get((cx, cy), 0) + 1
        n += 1
    if n == 0:
        return {"n": 0, "total_cells": total_cells, "grid": (ncols, nrows),
                "cells_visited": 0, "cells_50pct": None,
                "cells_50pct_fraction": None}
    ordered = sorted(counts.values(), reverse=True)
    need = n * 0.5
    acc = 0
    used = 0
    for c in ordered:
        acc += c
        used += 1
        if acc >= need:
            break
    return {
        "n": n,
        "total_cells": total_cells,
        "grid": (ncols, nrows),
        "cell_size": cell,
        "cells_visited": len(counts),
        "cells_visited_fraction": len(counts) / total_cells,
        "cells_50pct": used,
        "cells_50pct_fraction": used / total_cells,
    }


def corner_occupancy(positions: Sequence[Tuple[float, float]],
                     w: float, h: float,
                     radii: Sequence[float] = CORNER_RADII) -> Dict[str, Any]:
    """Within R of TWO walls, each next to its uniform baseline 4R^2/(W*H)."""
    n = len(positions)
    out: Dict[str, Any] = {"n": n, "radii": {}}
    for r in radii:
        baseline = 4.0 * r * r / (w * h)
        if n == 0:
            out["radii"][r] = {"count": 0, "n": 0, "fraction": None,
                               "baseline": baseline, "ratio": None}
            continue
        hits = 0
        for x, y in positions:
            near_x = (x <= r) or (x >= w - r)
            near_y = (y <= r) or (y >= h - r)
            if near_x and near_y:
                hits += 1
        frac = hits / n
        out["radii"][r] = {
            "count": hits, "n": n, "fraction": frac,
            "baseline": baseline,
            "ratio": (frac / baseline) if baseline > 0 else None,
        }
    return out


def radius_of_gyration(positions: Sequence[Tuple[float, float]]
                       ) -> Dict[str, Any]:
    n = len(positions)
    if n == 0:
        return {"n": 0, "centroid": None, "rg": None}
    cx = statistics.fmean(p[0] for p in positions)
    cy = statistics.fmean(p[1] for p in positions)
    ss = statistics.fmean((p[0] - cx) ** 2 + (p[1] - cy) ** 2 for p in positions)
    return {"n": n, "centroid": (cx, cy), "rg": math.sqrt(ss)}


def centre_and_wall(positions: Sequence[Tuple[float, float]],
                    w: float, h: float) -> Dict[str, Any]:
    """The two metrics that FAILED to separate the arms.  Kept visible."""
    n = len(positions)
    if n == 0:
        return {"n": 0, "median_dist_centre": None, "median_dist_wall": None}
    cx, cy = w / 2.0, h / 2.0
    dc = sorted(math.hypot(x - cx, y - cy) for x, y in positions)
    dw = sorted(min(x, w - x, y, h - y) for x, y in positions)
    return {
        "n": n,
        "median_dist_centre": statistics.median(dc),
        "median_dist_wall": statistics.median(dw),
    }


def is_pursuer(enemy: Dict[str, Any]) -> bool:
    """The `pursuer` entity class.

    UNIFIED with scripts/wp2_tail_decomposition.py -- one definition of the
    entity class across both scripts, or the two eventually give two different
    answers to the same question.  A plain substring test for "pursuer" was
    REJECTED: it would also match any future type whose name merely contains
    the word (e.g. a hypothetical "pursuer_spawner" or "anti_pursuer").
    """
    text = f"{enemy.get('type_id', '')}|{enemy.get('script_path', '')}"
    return "/pursuer/" in text or "pursuer_stats" in text


def nearest_pursuer(payload: Dict[str, Any],
                    radius: float = PURSUER_RADIUS) -> Optional[Dict[str, Any]]:
    px = float(dig(payload, "player", "x", default=0.0))
    py = float(dig(payload, "player", "y", default=0.0))
    best = None
    best_d = radius
    for enemy in (dig(payload, "entities", "enemies", default=[]) or []):
        if not isinstance(enemy, dict) or not is_pursuer(enemy):
            continue
        dx = float(enemy.get("x", 0.0)) - px
        dy = float(enemy.get("y", 0.0)) - py
        dist = math.hypot(dx, dy)
        if 0.0 < dist <= best_d:
            best_d = dist
            best = enemy
    return best


def approach_velocity(payloads: Sequence[Dict[str, Any]],
                      radius: float = PURSUER_RADIUS) -> Dict[str, Any]:
    """Pooled approach velocity to the nearest pursuer within `radius`.

    The direction is the ACTUAL DISPLACEMENT between consecutive kept captures,
    unit-normalised, dotted with the unit player->pursuer vector and NEGATED so
    +1 = moving straight AWAY.  `teacher.action` is deliberately not read: in a
    human trial it is the agent's intent, not what executed.

    BEARING EPOCH -- the player->pursuer vector is taken at the PREVIOUS
    capture, the same capture the displacement starts from.  The causal pairing
    is: the controller observed state `prev`, and the displacement prev->cur is
    its RESPONSE to that state.  Taking the bearing at `cur` would score the
    response against a state that partly resulted from it.
    """
    vals: List[float] = []
    dists: List[float] = []
    dt_excluded = 0
    no_pursuer = 0
    zero_disp = 0
    considered = 0
    prev: Optional[Dict[str, Any]] = None
    for payload in payloads:
        dt = payload.get("control_dt_ms")
        if dt is not None:
            try:
                if float(dt) < MIN_CONTROL_DT_MS:
                    dt_excluded += 1
                    prev = None       # the gap breaks the displacement chain
                    continue
            except (TypeError, ValueError):
                pass
        if prev is None:
            prev = payload
            continue
        considered += 1
        ppx = float(dig(prev, "player", "x", default=0.0))
        ppy = float(dig(prev, "player", "y", default=0.0))
        px = float(dig(payload, "player", "x", default=0.0))
        py = float(dig(payload, "player", "y", default=0.0))
        enemy = nearest_pursuer(prev, radius)
        if enemy is None:
            no_pursuer += 1
            prev = payload
            continue
        dx = float(enemy.get("x", 0.0)) - ppx
        dy = float(enemy.get("y", 0.0)) - ppy
        dist = math.hypot(dx, dy)
        mx, my = px - ppx, py - ppy
        mmag = math.hypot(mx, my)
        prev = payload
        if dist <= 0.0:
            continue
        if mmag <= 0.0:
            zero_disp += 1
            vals.append(0.0)
            dists.append(dist)
            continue
        vals.append(-((mx / mmag) * dx + (my / mmag) * dy) / dist)
        dists.append(dist)
    return {
        "captures_seen": len(payloads),
        "excluded_low_control_dt": dt_excluded,
        "pairs_considered": considered,
        "no_pursuer_within_radius": no_pursuer,
        "zero_displacement_ticks": zero_disp,
        "radius": radius,
        "n": len(vals),
        "mean": statistics.fmean(vals) if vals else None,
        "median": statistics.median(vals) if vals else None,
        "median_dist_to_pursuer": statistics.median(dists) if dists else None,
    }


# ---------------------------------------------------------------------------
# per-run driver
# ---------------------------------------------------------------------------


def analyze_run(run_dir: Path, wave: int) -> Dict[str, Any]:
    payloads_all = list(iter_captures(run_dir))
    waves_seen = sorted({int(p.get("wave", 0) or 0) for p in payloads_all})
    kept: List[Dict[str, Any]] = []
    dt_excluded = 0
    for p in payloads_all:
        if int(p.get("wave", 0) or 0) != wave:
            continue
        dt = p.get("control_dt_ms")
        if dt is not None:
            try:
                if float(dt) < MIN_CONTROL_DT_MS:
                    dt_excluded += 1
                    continue
            except (TypeError, ValueError):
                pass
        kept.append(p)
    w, h = arena_of(kept or payloads_all)
    positions = [(float(dig(p, "player", "x", default=0.0)),
                  float(dig(p, "player", "y", default=0.0))) for p in kept]
    summary = load_summary(run_dir)
    return {
        "run_id": run_dir.name,
        "missing": False,
        "missing_reason": None,
        "mod_version": summary.get("mod_version"),
        "result": summary.get("result"),
        "waves_captured": waves_seen,
        "survived": SURVIVAL_WAVE in waves_seen,
        "wave": wave,
        "captures_wave_raw": sum(1 for p in payloads_all
                                 if int(p.get("wave", 0) or 0) == wave),
        "excluded_low_control_dt": dt_excluded,
        "captures_used": len(kept),
        "arena": {"width": w, "height": h},
        "concentration": occupancy_concentration(positions, w, h),
        "corners": corner_occupancy(positions, w, h),
        "gyration": radius_of_gyration(positions),
        "centre_wall": centre_and_wall(positions, w, h),
        "approach": approach_velocity(kept),
    }


def missing_run(run_id: str, reason: str) -> Dict[str, Any]:
    return {"run_id": run_id, "missing": True, "missing_reason": reason,
            "waves_captured": [], "survived": False, "concentration": None}


# ---------------------------------------------------------------------------
# the pre-registered decision rule -- transcribed, not invented
# ---------------------------------------------------------------------------


def prereg_rule(ctrl_primary: Sequence[float],
                treat_primary: Sequence[float],
                ctrl_survived: Sequence[bool],
                treat_survived: Sequence[bool],
                ctrl_damage: Sequence[float],
                treat_damage: Sequence[float],
                human_value: float = HUMAN_PRIMARY) -> Dict[str, Any]:
    """GO iff treat_mean - ctrl_mean >= 2*sd_ctrl AND the difference is
    positive (toward the human value).  Either safety guard trips -> NO-GO
    regardless of the primary endpoint.
    """
    out: Dict[str, Any] = {
        "ctrl_n": len(ctrl_primary),
        "treat_n": len(treat_primary),
        "ctrl_values": list(ctrl_primary),
        "treat_values": list(treat_primary),
        "human_value": human_value,
    }
    out["ctrl_mean"] = statistics.fmean(ctrl_primary) if ctrl_primary else None
    out["treat_mean"] = statistics.fmean(treat_primary) if treat_primary else None
    out["sd_ctrl"] = (statistics.stdev(ctrl_primary)
                      if len(ctrl_primary) >= 2 else None)
    out["treat_sd"] = (statistics.stdev(treat_primary)
                       if len(treat_primary) >= 2 else None)
    if out["ctrl_mean"] is None or out["treat_mean"] is None:
        out["diff"] = None
        out["diff_in_sd_ctrl"] = None
    else:
        out["diff"] = out["treat_mean"] - out["ctrl_mean"]
        out["diff_in_sd_ctrl"] = (
            (out["diff"] / out["sd_ctrl"]) if out["sd_ctrl"] else None)

    # --- safety guards -----------------------------------------------------
    cs = (sum(1 for s in ctrl_survived if s) / len(ctrl_survived)
          if ctrl_survived else None)
    ts = (sum(1 for s in treat_survived if s) / len(treat_survived)
          if treat_survived else None)
    out["ctrl_survival"] = cs
    out["treat_survival"] = ts
    out["ctrl_survival_denominator"] = len(ctrl_survived)
    out["treat_survival_denominator"] = len(treat_survived)
    out["guard_survival_tripped"] = bool(
        cs is not None and ts is not None and ts < cs)

    cd = statistics.median(ctrl_damage) if ctrl_damage else None
    td = statistics.median(treat_damage) if treat_damage else None
    out["ctrl_median_damage"] = cd
    out["treat_median_damage"] = td
    out["damage_threshold_1_5x"] = (1.5 * cd) if cd is not None else None
    out["guard_damage_tripped"] = bool(
        cd is not None and td is not None and td > 1.5 * cd)
    out["guards_tripped"] = (out["guard_survival_tripped"]
                             or out["guard_damage_tripped"])

    # --- primary ------------------------------------------------------------
    if out["diff"] is None or out["sd_ctrl"] is None:
        out["primary_passed"] = None
        out["verdict"] = "INDETERMINATE"
        out["reason"] = "insufficient data for the primary comparison"
        return out
    out["primary_passed"] = bool(out["diff"] > 0.0
                                 and out["diff"] >= 2.0 * out["sd_ctrl"])
    if out["guards_tripped"]:
        out["verdict"] = "NO-GO"
        which = []
        if out["guard_survival_tripped"]:
            which.append("treatment survival below control")
        if out["guard_damage_tripped"]:
            which.append("treatment median damage > 1.5x control")
        out["reason"] = "SAFETY GUARD: " + " and ".join(which)
    elif out["primary_passed"]:
        out["verdict"] = "GO"
        out["reason"] = "diff >= 2*sd_ctrl and positive toward the human value"
    else:
        out["verdict"] = "NO-GO"
        out["reason"] = ("diff < 2*sd_ctrl" if out["diff"] > 0
                         else "effect not positive (wrong direction or zero)")
    return out


# ---------------------------------------------------------------------------
# printing
# ---------------------------------------------------------------------------


def _fmt(x: Optional[float], nd: int = 4) -> str:
    if x is None:
        return "n/a"
    if isinstance(x, float) and (math.isinf(x) or math.isnan(x)):
        return str(x)
    return f"{x:.{nd}f}"


def report(results: Sequence[Dict[str, Any]],
           arms: Dict[str, str],
           doses: Dict[str, Any],
           labels: Dict[str, str],
           damage: Dict[str, Any],
           wave: int) -> Dict[str, Any]:
    print("=" * 82)
    print(f"WP2 CONFINEMENT SCREEN  --  wave {wave} only, control_dt_ms >= "
          f"{MIN_CONTROL_DT_MS:g}")
    print("  reports against reports/wp2/confinement_screen_prereg.md; "
          "it does not decide")
    print("=" * 82)

    dosed = sorted({v for v in doses.values()
                    if v is not None and float(v) != CONTROL_DOSE})
    if dosed:
        print(f"  NOTE: treatment dose {dosed} != 1.0 -- "
              "_predictive_body_path_clearance returns an INFLATED value under "
              "the dose, so those fields are not comparable across arms "
              "(none are printed here).")

    present = [r for r in results if not r["missing"]]
    absent = [r for r in results if r["missing"]]
    empty = [r for r in present if r["captures_used"] == 0]
    usable = [r for r in present if r["captures_used"] > 0]

    if absent or empty:
        print()
        print("-- EXCLUDED RUNS (stated, never silent) --------------------------")
        for r in absent:
            print(f"  {r['run_id']:<28} EXCLUDED: {r['missing_reason']}")
        for r in empty:
            print(f"  {r['run_id']:<28} EXCLUDED: no usable wave-{wave} "
                  f"captures (raw wave-{wave}={r['captures_wave_raw']}, "
                  f"dt-excluded={r['excluded_low_control_dt']})")
        print(f"  excluded total: {len(absent) + len(empty)} of {len(results)}")

    print()
    print("-- PER-RUN -------------------------------------------------------")
    hdr = (f"  {'run_id':<26} {'arm':<10} {'dose':>5} {'caps':>6} "
           f"{'cells50':>8} {'frac':>7} {'visited':>8} {'Rg':>8} "
           f"{'dCentre':>8} {'dWall':>7} {'approach':>9} {'surv':>5} {'dmg':>6}")
    print(hdr)
    for r in usable:
        rid = r["run_id"]
        c = r["concentration"]
        print(f"  {rid:<26} {arms.get(rid, 'unknown'):<10} "
              f"{str(doses.get(rid)):>5} {r['captures_used']:>6} "
              f"{c['cells_50pct']:>8} {c['cells_50pct_fraction']:>7.4f} "
              f"{c['cells_visited']:>4}/{c['total_cells']:<3} "
              f"{_fmt(r['gyration']['rg'], 1):>8} "
              f"{_fmt(r['centre_wall']['median_dist_centre'], 1):>8} "
              f"{_fmt(r['centre_wall']['median_dist_wall'], 1):>7} "
              f"{_fmt(r['approach']['mean'], 4):>9} "
              f"{'Y' if r['survived'] else 'n':>5} "
              f"{str(damage.get(rid)):>6}")
    print(f"  runs in table (denominator): {len(usable)} of {len(results)} "
          f"requested")
    print("  cells50 = 128 u cells needed to hold >= 50% of wave-"
          f"{wave} captures (HIGHER = roams more; human {HUMAN_PRIMARY})")
    print("  approach = pooled unit DISPLACEMENT . unit(player->nearest pursuer "
          f"within {PURSUER_RADIUS:g} u), NEGATED (+1 = moving away). "
          "teacher.action is NOT used.")

    print()
    print("-- CORNER OCCUPANCY vs UNIFORM BASELINE 4R^2/(W*H) ---------------")
    for r in usable:
        for radius in CORNER_RADII:
            d = r["corners"]["radii"][radius]
            print(f"  {r['run_id']:<26} R={radius:>5.0f}  "
                  f"frac={_fmt(d['fraction'])} ({d['count']}/{d['n']})  "
                  f"baseline={_fmt(d['baseline'])}  ratio={_fmt(d['ratio'], 3)}x")

    print()
    print("-- MEDIANS THAT FAILED TO SEPARATE (kept visible on purpose) -----")
    print("  distance-from-centre and distance-to-nearest-wall did NOT "
          "separate human from agent on this fixture; see the per-run table.")

    # ---- per-arm aggregates ------------------------------------------------
    by_arm: Dict[str, List[Dict[str, Any]]] = {}
    for r in usable:
        by_arm.setdefault(arms.get(r["run_id"], "unknown"), []).append(r)

    print()
    print("-- PER-ARM AGGREGATES (raw values ALWAYS printed) ----------------")
    print("  THREE ARMS, NEVER MERGED: control / treatment / human.  `human` is")
    print("  assigned from summary.json's human_movement == true REGARDLESS of")
    print("  dose (a human trial carries the inert dose 1.0).  A run whose")
    print("  human_movement field is ABSENT is `unknown`, never assumed agent.")
    n_human = len(by_arm.get("human") or [])
    n_unknown = len(by_arm.get("unknown") or [])
    print(f"  human runs held out of the prereg comparison: {n_human} of "
          f"{len(usable)} usable;  unknown-provenance: {n_unknown}")
    arm_stats: Dict[str, Any] = {}
    for arm in ("control", "treatment", "human", "unknown"):
        rows = by_arm.get(arm) or []
        if not rows:
            continue
        vals = [float(r["concentration"]["cells_50pct"]) for r in rows]
        appr = [r["approach"]["mean"] for r in rows
                if r["approach"]["mean"] is not None]
        rg = [r["gyration"]["rg"] for r in rows if r["gyration"]["rg"] is not None]
        mean = statistics.fmean(vals)
        sd = statistics.stdev(vals) if len(vals) >= 2 else None
        arm_stats[arm] = {
            "n": len(rows),
            "run_ids": [r["run_id"] for r in rows],
            "cells_50pct_values": vals,
            "cells_50pct_mean": mean,
            "cells_50pct_sd": sd,
            "approach_values": appr,
            "approach_mean": statistics.fmean(appr) if appr else None,
            "rg_values": rg,
            "rg_mean": statistics.fmean(rg) if rg else None,
            "survived": [bool(r["survived"]) for r in rows],
            "damage": [damage.get(r["run_id"]) for r in rows],
        }
        print(f"  {arm.upper()}  n={len(rows)}   runs={[r['run_id'] for r in rows]}")
        print(f"    cells50 RAW    : {[int(v) for v in vals]}")
        print(f"    cells50 mean   : {_fmt(mean, 3)}   sample SD: "
              f"{_fmt(sd, 4)}  (n={len(vals)})")
        print(f"    approach RAW   : {[round(a, 4) for a in appr]}"
              f"   mean={_fmt(statistics.fmean(appr) if appr else None)}"
              f"  (n={len(appr)})")
        print(f"    Rg RAW         : {[round(v, 1) for v in rg]}"
              f"   mean={_fmt(statistics.fmean(rg) if rg else None, 1)}"
              f"  (n={len(rg)})")
        print(f"    survived to w{SURVIVAL_WAVE}: "
              f"{sum(1 for r in rows if r['survived'])}/{len(rows)}")
        print(f"    damage_taken RAW: {[damage.get(r['run_id']) for r in rows]}")

    # ---- prereg block ------------------------------------------------------
    ctrl = by_arm.get("control") or []
    treat = by_arm.get("treatment") or []
    ctrl_dmg = [float(damage[r["run_id"]]) for r in ctrl
                if damage.get(r["run_id"]) is not None]
    treat_dmg = [float(damage[r["run_id"]]) for r in treat
                 if damage.get(r["run_id"]) is not None]
    rule = prereg_rule(
        [float(r["concentration"]["cells_50pct"]) for r in ctrl],
        [float(r["concentration"]["cells_50pct"]) for r in treat],
        [bool(r["survived"]) for r in ctrl],
        [bool(r["survived"]) for r in treat],
        ctrl_dmg, treat_dmg,
    )

    print()
    print("=" * 82)
    print("PREREG BLOCK -- mechanical evaluation of the FIXED rule")
    print("  rule: GO iff (treat_mean - ctrl_mean) >= 2 * sd_ctrl AND the")
    print("        difference is positive (toward the human value of "
          f"{HUMAN_PRIMARY}); either safety guard -> NO-GO regardless.")
    print("=" * 82)
    print(f"  control values (raw)    : {[int(v) for v in rule['ctrl_values']]}"
          f"  (n={rule['ctrl_n']})")
    print(f"  treatment values (raw)  : {[int(v) for v in rule['treat_values']]}"
          f"  (n={rule['treat_n']})")
    print(f"  ctrl_mean               : {_fmt(rule['ctrl_mean'], 4)}")
    print(f"  treat_mean              : {_fmt(rule['treat_mean'], 4)}")
    print(f"  sd_ctrl (sample SD)     : {_fmt(rule['sd_ctrl'], 4)}"
          f"  (n={rule['ctrl_n']})")
    print(f"  diff (treat - ctrl)     : {_fmt(rule['diff'], 4)}")
    print(f"  2 * sd_ctrl             : "
          f"{_fmt(2 * rule['sd_ctrl'] if rule['sd_ctrl'] is not None else None, 4)}")
    print(f"  diff in units of sd_ctrl: {_fmt(rule['diff_in_sd_ctrl'], 4)}")
    print(f"  primary passed          : {rule['primary_passed']}")
    print("  -- safety guards --")
    print(f"  control survival        : {_fmt(rule['ctrl_survival'])} "
          f"({sum(1 for r in ctrl if r['survived'])}/"
          f"{rule['ctrl_survival_denominator']})")
    print(f"  treatment survival      : {_fmt(rule['treat_survival'])} "
          f"({sum(1 for r in treat if r['survived'])}/"
          f"{rule['treat_survival_denominator']})")
    print(f"  guard 1 (treat < ctrl)  : {rule['guard_survival_tripped']}")
    print(f"  ctrl median damage      : {_fmt(rule['ctrl_median_damage'], 2)}"
          f"  (n={len(ctrl_dmg)})   raw={ctrl_dmg}")
    print(f"  treat median damage     : {_fmt(rule['treat_median_damage'], 2)}"
          f"  (n={len(treat_dmg)})   raw={treat_dmg}")
    print(f"  1.5x control threshold  : {_fmt(rule['damage_threshold_1_5x'], 2)}")
    print(f"  guard 2 (treat > 1.5x)  : {rule['guard_damage_tripped']}")
    print()
    print(f"  VERDICT: {rule['verdict']}   ({rule['reason']})")
    print("=" * 82)

    return {
        "wave": wave,
        "runs": results,
        "arms": arms,
        "doses": doses,
        "labels": labels,
        "damage_taken": damage,
        "arm_stats": arm_stats,
        "prereg": rule,
    }


# ---------------------------------------------------------------------------
# driver
# ---------------------------------------------------------------------------


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--trials", help="wp2_finale_loop trials jsonl "
                                     "(run ids, label, dose, damage_taken)")
    ap.add_argument("--run-id", action="append", default=[], help="repeatable")
    ap.add_argument("--runs-dir", default=None)
    ap.add_argument("--wave", type=int, default=DEFAULT_WAVE)
    ap.add_argument("--json", default=None, help="write the full result dict here")
    args = ap.parse_args(argv)

    ids: List[str] = list(args.run_id)
    arms: Dict[str, str] = {rid: "unknown" for rid in ids}
    doses: Dict[str, Any] = {rid: None for rid in ids}
    labels: Dict[str, str] = {}
    damage: Dict[str, Any] = {}
    if args.trials:
        for row in read_trials(Path(args.trials)):
            rid = row["run_id"]
            if rid not in ids:
                ids.append(rid)
            doses[rid] = row.get(DOSE_KEY)
            labels[rid] = row.get("label")
            damage[rid] = row.get("damage_taken")
    if not ids:
        ap.error("no run ids: pass --trials and/or --run-id")

    base = runs_dir(args.runs_dir)
    results: List[Dict[str, Any]] = []
    for rid in ids:
        rdir = base / rid
        # ARM ASSIGNMENT reads the RUN's own summary.json, not the dose alone.
        # A human-handover trial carries the inert dose 1.0 and would otherwise
        # be filed as `control`.
        arms[rid] = arm_of(doses.get(rid), human_movement_of(rdir))
        if not (rdir / "events.jsonl").exists():
            results.append(missing_run(rid, f"no events.jsonl under {base}"))
            continue
        results.append(analyze_run(rdir, args.wave))

    out = report(results, arms, doses, labels, damage, args.wave)
    if args.json:
        Path(args.json).write_text(json.dumps(out, indent=2, default=str),
                                   encoding="utf-8")
        print(f"\nwrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
