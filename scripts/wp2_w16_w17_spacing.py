#!/usr/bin/env python3
"""Wave 16 vs wave 17 spacing — paired within-run.

Tests a prediction from the Brotato-successor team: wave 17 is the only wave in
the run that is pure homogeneous contact (261 contact units, zero chargers, zero
ranged) while carrying LESS body threat per second than wave 16. If the agent
over-extends when threat becomes homogeneous, its nearest-enemy distance on wave
17 should be LOWER than on wave 16 despite fewer enemies.

Paired within-run: each run contributes its own w16 and w17 medians, so build
strength and run quality cancel. A cross-run comparison would confound both.

nearest_d >= 1e17 is an INF sentinel meaning NO TARGET (100% coincident with
n_enemies == 0). It is filtered, never averaged - a mean becomes ~1e17 and a
median silently survives, which is what makes it dangerous.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import statistics as st

INF_SENTINEL = 1e17


def run_waves(path: Path, waves: set[int]) -> dict[int, dict[str, list]]:
    """Stream one run's captures, deriving nearest-enemy distance per wave.

    `nearest_d` and `n_enemies` are NOT payload fields - they are derived. The
    enemies are in `entities.enemies` with absolute x/y, as is the player, so
    distance is computed here. Centre-to-centre (no radius in the payload);
    that is a constant offset per archetype and the comparison is PAIRED across
    waves within a run, so it cannot bias the w16-vs-w17 delta.

    Captures with NO enemies are the real "no target" case - counted, never
    folded into the distance distribution as a large number.
    """
    out: dict[int, dict[str, list]] = {w: {"d": [], "n": [], "inf": 0} for w in waves}
    with path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if '"combat_capture"' not in line:
                continue
            try:
                payload = json.loads(line)["payload"]
            except (json.JSONDecodeError, KeyError):
                continue
            wave = payload.get("wave")
            if wave not in waves:
                continue
            dt = payload.get("control_dt_ms")
            if isinstance(dt, (int, float)) and dt < 10:
                continue  # start-up artifact
            player = payload.get("player") or {}
            px, py = player.get("x"), player.get("y")
            if not isinstance(px, (int, float)) or not isinstance(py, (int, float)):
                continue
            enemies = (payload.get("entities") or {}).get("enemies") or []
            bucket = out[wave]
            bucket["n"].append(len(enemies))
            best = None
            for e in enemies:
                ex, ey = e.get("x"), e.get("y")
                if not isinstance(ex, (int, float)) or not isinstance(ey, (int, float)):
                    continue
                d = ((ex - px) ** 2 + (ey - py) ** 2) ** 0.5
                if best is None or d < best:
                    best = d
            if best is None:
                bucket["inf"] += 1  # genuinely no target on this tick
                continue
            bucket["d"].append(best)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs-dir", required=True, type=Path)
    ap.add_argument("--limit", type=int, default=40)
    ap.add_argument("--out", type=Path, default=Path(".tmp/w16_w17_spacing.json"))
    args = ap.parse_args()

    dirs = sorted(
        (p for p in args.runs_dir.iterdir() if p.is_dir()),
        key=lambda p: p.name,
        reverse=True,
    )

    rows = []
    scanned = 0
    for d in dirs:
        if len(rows) >= args.limit:
            break
        summary = d / "summary.json"
        events = d / "events.jsonl"
        if not summary.exists() or not events.exists():
            continue
        try:
            s = json.loads(summary.read_text(encoding="utf-8-sig"))
        except (json.JSONDecodeError, OSError):
            continue
        # well_rounded D0 only, and must have REACHED wave 17
        if s.get("character") != "character_well_rounded":
            continue
        if int(s.get("requested_danger", 0) or 0) != 0:
            continue
        if int(s.get("last_wave", 0) or 0) < 17:
            continue
        scanned += 1
        w = run_waves(events, {16, 17})
        if len(w[16]["d"]) < 50 or len(w[17]["d"]) < 50:
            continue  # need both waves populated to pair
        rows.append(
            {
                "run": d.name,
                "result": s.get("result"),
                "terminal_wave": s.get("last_wave"),
                "d16": st.median(w[16]["d"]),
                "d17": st.median(w[17]["d"]),
                "n16": st.median(w[16]["n"]) if w[16]["n"] else None,
                "n17": st.median(w[17]["n"]) if w[17]["n"] else None,
                "caps16": len(w[16]["d"]),
                "caps17": len(w[17]["d"]),
                "inf16": w[16]["inf"],
                "inf17": w[17]["inf"],
            }
        )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(rows, indent=2), encoding="utf-8")

    print(f"runs scanned {scanned}, paired runs used {len(rows)}")
    if not rows:
        print("NO PAIRED RUNS - cannot answer")
        return 1

    print()
    print(f"{'run':24s} {'res':8s} {'med d w16':>9s} {'med d w17':>9s} {'delta':>7s} "
          f"{'n w16':>6s} {'n w17':>6s}")
    for r in rows:
        print(f"{r['run']:24s} {str(r['result']):8s} {r['d16']:9.1f} {r['d17']:9.1f} "
              f"{r['d17'] - r['d16']:7.1f} {r['n16'] or 0:6.1f} {r['n17'] or 0:6.1f}")

    d16 = [r["d16"] for r in rows]
    d17 = [r["d17"] for r in rows]
    deltas = [r["d17"] - r["d16"] for r in rows]
    n16 = [r["n16"] for r in rows if r["n16"] is not None]
    n17 = [r["n17"] for r in rows if r["n17"] is not None]
    closer = sum(1 for x in deltas if x < 0)

    print()
    print(f"median nearest-enemy distance  w16 {st.median(d16):.1f} u   "
          f"w17 {st.median(d17):.1f} u")
    print(f"median paired delta (w17 - w16): {st.median(deltas):+.1f} u")
    print(f"runs CLOSER on w17: {closer}/{len(deltas)}")
    print(f"median enemies alive  w16 {st.median(n16):.1f}   w17 {st.median(n17):.1f}")
    print(f"INF (no-target) captures filtered: w16 {sum(r['inf16'] for r in rows)}, "
          f"w17 {sum(r['inf17'] for r in rows)}")

    # exact two-sided sign test on the paired deltas
    n = len(deltas)
    from math import comb
    tail = sum(comb(n, k) for k in range(0, min(closer, n - closer) + 1))
    p = min(1.0, 2 * tail / (2 ** n))
    print(f"sign test, two-sided: p = {p:.4f}")
    print()
    print("PREDICTION (agent over-extends on the homogeneous wave):",
          "SUPPORTED - closer on w17 despite fewer enemies"
          if st.median(deltas) < 0 and st.median(n17) < st.median(n16)
          else "NOT SUPPORTED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
