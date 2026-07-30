#!/usr/bin/env python3
"""Derive the causal damage-attribution lag for Danger 5, per hazard class.

WHY THIS SCRIPT EXISTS
----------------------
Attributing a player HP drop to a cause means choosing WHICH CAPTURE caused it, and
the right choice is not a property of the telemetry -- it is a property of what did
the damage. Measured previously by lag sweep of median min surface distance:

    context                       lag -1      lag 0 (the HP-drop tick)
    wave 20 (projectiles)         18.7 u  <--   59.8 u
    wave 17 (melee bodies)        12.7 u        0.9 u  <--

Projectiles despawn on impact, so by the drop tick the cause is already gone; a melee
body is still touching. Random-tick baseline was 114-218 u, so carrying the wrong
context's lag degrades attribution to near-noise.

Danger 5 deaths cluster around waves 8-15, which is neither of the measured contexts
and has a different hazard mix. **The lag must therefore be re-derived here and never
inherited.** That is the whole purpose of this file.

METHOD
------
Per run, stream `combat_capture` in `capture_seq` order and keep only a small tuple per
capture. An HP-drop tick is `hp[i] < hp[i-1]`. For each lag L, measure the minimum
SURFACE distance (centre distance minus the entity's own radius) from the player to
each hazard class at capture i+L, and take the median over all drop events. The lag
whose median sits far below the random-tick baseline is the causal one.

Reported per hazard class separately (enemies vs projectiles) because that is exactly
the distinction the two prior contexts turned on.

CAVEATS, stated rather than hidden
----------------------------------
* Captures with `control_dt_ms < 10` are excluded: `measured_vx/vy` explodes at
  start-up dt and such captures are not steady state.
* `hp_regeneration` is non-zero, so HP rises between hits; a decrease is still damage.
* Self-damage items and burn DoT also decrease HP with no adjacent body. Those inflate
  every lag equally and so cannot fake a lag preference, but they do raise the floor.
* Dodged hits produce no HP drop at all and are invisible here.
* This identifies an ATTRIBUTION LAG. It does not establish that any hazard caused a
  death.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
from pathlib import Path
from typing import Any

LAGS = (-3, -2, -1, 0, 1)
HAZARDS = ("enemies", "projectiles", "bosses")


def _min_surface_dist(px: float, py: float, items: list[dict[str, Any]]) -> float | None:
    best = None
    for it in items:
        x, y = it.get("x"), it.get("y")
        if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
            continue
        r = it.get("radius") or 0.0
        d = math.hypot(x - px, y - py) - float(r)
        if best is None or d < best:
            best = d
    return best


def load_series(path: Path, min_wave: int) -> list[dict[str, Any]]:
    """One compact row per capture. Streams; never holds the raw payloads."""
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            if '"combat_capture"' not in line:
                continue
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            p = ev.get("payload", {})
            if p.get("valid") is False:
                continue
            dt = p.get("control_dt_ms")
            if isinstance(dt, (int, float)) and dt < 10:
                continue
            if int(p.get("wave", 0)) < min_wave:
                continue
            player = p.get("player", {})
            hp = player.get("hp")
            px, py = player.get("x"), player.get("y")
            if not isinstance(hp, (int, float)) or not isinstance(px, (int, float)):
                continue
            ent = p.get("entities", {}) or {}
            row: dict[str, Any] = {
                "seq": p.get("capture_seq"),
                "wave": int(p.get("wave", 0)),
                "hp": float(hp),
                "n_enemies": len(ent.get("enemies", []) or []),
                "n_proj": len(ent.get("projectiles", []) or []),
            }
            for h in HAZARDS:
                row[h] = _min_surface_dist(px, py, ent.get(h, []) or [])
            rows.append(row)
    rows.sort(key=lambda r: (r["wave"], r["seq"] if r["seq"] is not None else 0))
    return rows


def analyse(rows: list[dict[str, Any]]) -> dict[str, Any]:
    # A drop requires BOTH neighbours to be real captures. Without the boundary
    # guard, a run seam manufactures one false drop per run: the first capture of
    # run B compares against the sentinel, and any finite hp is "less than" a
    # sentinel set high (or the sentinel itself registers as a drop if set low).
    # Marking the seam is the only way to make it inert from both directions.
    drops = [
        i for i in range(1, len(rows))
        if not rows[i].get("boundary") and not rows[i - 1].get("boundary")
        and rows[i]["hp"] < rows[i - 1]["hp"]
    ]
    out: dict[str, Any] = {
        "captures": sum(1 for r in rows if not r.get("boundary")),
        "hp_drop_events": len(drops),
        "baseline": {},
        "by_lag": {},
    }
    # Random-tick baseline: the median over ALL captures, i.e. what "no information"
    # looks like. A lag only means something relative to this.
    for h in HAZARDS:
        vals = [r[h] for r in rows if r[h] is not None]
        out["baseline"][h] = {
            "n": len(vals),
            "median": round(statistics.median(vals), 2) if vals else None,
        }
    for lag in LAGS:
        per: dict[str, Any] = {}
        for h in HAZARDS:
            vals = []
            for i in drops:
                j = i + lag
                if 0 <= j < len(rows) and rows[j][h] is not None:
                    vals.append(rows[j][h])
            per[h] = {
                "n": len(vals),
                "median": round(statistics.median(vals), 2) if vals else None,
                "p25": round(statistics.quantiles(vals, n=4)[0], 2) if len(vals) >= 4 else None,
            }
        out["by_lag"][str(lag)] = per
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-ids-file", required=True)
    ap.add_argument("--runs-dir", required=True)
    ap.add_argument("--min-wave", type=int, default=1)
    ap.add_argument("--out", required=True)
    ap.add_argument("--label", default="")
    args = ap.parse_args()

    ids = [x.strip() for x in Path(args.run_ids_file).read_text(encoding="utf-8").splitlines() if x.strip()]
    root = Path(args.runs_dir)
    pooled: list[dict[str, Any]] = []
    per_run = []
    for rid in ids:
        f = root / rid / "events.jsonl"
        if not f.is_file():
            per_run.append({"run_id": rid, "error": "missing events.jsonl"})
            continue
        rows = load_series(f, args.min_wave)
        res = analyse(rows)
        per_run.append({"run_id": rid, **{k: res[k] for k in ("captures", "hp_drop_events")}})
        pooled.extend(rows)
        # Reset the seam between runs so a drop is never attributed across a run
        # boundary: insert a sentinel with impossible hp so no cross-run diff fires.
        pooled.append({"seq": -1, "wave": -1, "hp": float("inf"), "n_enemies": 0,
                       "n_proj": 0, "boundary": True, **{h: None for h in HAZARDS}})

    result = {
        "label": args.label,
        "runs": len(ids),
        "min_wave": args.min_wave,
        "per_run": per_run,
        "pooled": analyse(pooled),
    }
    Path(args.out).write_text(json.dumps(result, indent=1), encoding="utf-8")
    print(json.dumps(result["pooled"], indent=1))
    print()
    print("per-run capture / hp-drop counts:")
    for r in per_run:
        print("  ", r)


if __name__ == "__main__":
    main()
