"""Per-wave Material Bag audit: how much deferred value does the policy strand?

The wave-end sweep converts uncollected materials into `bonus_materials` (the
Material Bag), which then redeems INCREMENTALLY through pickups during the next
wave. So under-collection is doubly costly: the current wave's drops are deferred
AND the previous wave's bag goes unredeemed. Anything still in the bag when the
run ends is lost outright.

Measured at the PRE-SWEEP instant only (last capture with remaining_sec > 0):
combat_capture events continue for ~40-55 ticks after the wave timer expires and
the sweep happens inside that window, so a naive "last capture" lands after it.

Usage:
    python scripts/wp2_material_bag_audit.py --out .tmp/bag_audit.json [--limit N]
"""

from __future__ import annotations

import argparse
import json
import statistics as st
from pathlib import Path

RUNS = Path(r"C:\Users\moxhe\AppData\Roaming\Brotato\brotato_agent\runs")
FULL_RUN_MS = 900_000  # a wave-20 FIXTURE trial and a FULL run both read last_wave=20


def per_wave(rid: Path) -> dict:
    out: dict[int, dict] = {}
    ev = rid / "events.jsonl"
    if not ev.exists():
        return out
    try:
        with ev.open(encoding="utf-8") as fh:
            for line in fh:
                if '"combat_capture"' not in line:
                    continue
                p = json.loads(line)["payload"]
                if not p.get("valid"):
                    continue
                w = p.get("wave")
                rem = (p.get("wave_time") or {}).get("remaining_sec")
                if w is None or rem is None or rem <= 0:
                    continue
                pl = p.get("player") or {}
                ent = p.get("entities") or {}
                d = out.setdefault(w, {"mat": [], "bag": [], "gnd": None, "rem": rem})
                d["mat"].append(pl.get("materials") or 0)
                d["bag"].append(pl.get("bonus_materials") or 0)
                if rem <= d["rem"]:
                    d["rem"] = rem
                    d["gnd"] = sum((m.get("value") or 0) for m in (ent.get("materials") or []))
    except (OSError, json.JSONDecodeError):
        return {}
    return out


def summarise(pw: dict) -> list[dict]:
    rows = []
    for w in sorted(pw):
        d = pw[w]
        if not d["mat"]:
            continue
        rows.append({
            "wave": w,
            "gained": d["mat"][-1] - d["mat"][0],
            "bag_in": d["bag"][0],
            "stranded": min(d["bag"]),
            "drained": min(d["bag"]) == 0,
            "ground_left": d["gnd"],
        })
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--limit", type=int, default=0, help="cap agent runs scanned (0 = all)")
    ap.add_argument("--mod", default="0.2.49-wp2-capture")
    args = ap.parse_args()

    agent_dirs = []
    for d in RUNS.iterdir():
        s = d / "summary.json"
        if not s.exists():
            continue
        try:
            j = json.loads(s.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            continue
        # duration filter is REQUIRED: fixture trials also read last_wave=20.
        if j.get("mod_version") == args.mod and (j.get("duration_ms") or 0) >= FULL_RUN_MS:
            agent_dirs.append(d)
    agent_dirs.sort()
    if args.limit:
        agent_dirs = agent_dirs[: args.limit]
    print(f"agent full runs matched: {len(agent_dirs)}")

    results = {}
    for i, d in enumerate(agent_dirs, 1):
        rows = summarise(per_wave(d))
        if rows:
            results[d.name] = rows
        print(f"  [{i}/{len(agent_dirs)}] {d.name}: {len(rows)} waves", flush=True)

    args.out.write_text(json.dumps(results, indent=1), encoding="utf-8")
    print(f"\nwrote {args.out}  ({len(results)} runs)")

    allrows = [r for rows in results.values() for r in rows]
    if not allrows:
        print("NO ROWS — check the filters before believing any zero here.")
        return
    drained = sum(1 for r in allrows if r["drained"])
    print(f"\nAGENT, pooled: {len(allrows)} wave-observations from {len(results)} runs")
    print(f"  waves with bag FULLY drained: {drained}/{len(allrows)} = {drained/len(allrows):.3f}")
    print(f"  stranded per wave: median={st.median([r['stranded'] for r in allrows]):.0f}")
    gl = [r["ground_left"] for r in allrows if r["ground_left"] is not None]
    if gl:
        print(f"  ground value left at wave end: median={st.median(gl):.0f}")
    print("\n  by wave band:")
    for lo, hi in ((1, 6), (7, 12), (13, 16), (17, 20)):
        band = [r for r in allrows if lo <= r["wave"] <= hi]
        if not band:
            continue
        dr = sum(1 for r in band if r["drained"])
        print(f"    w{lo}-{hi}: n={len(band):>4}  drained={dr/len(band):.3f}  "
              f"stranded_med={st.median([r['stranded'] for r in band]):.0f}")


if __name__ == "__main__":
    main()
