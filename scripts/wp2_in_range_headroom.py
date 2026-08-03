"""How much in-range fraction is ACHIEVABLE by positioning at D5?

The in-range gap (human 0.4417 vs agent 0.2801, d=4.03) is the best-evidenced
clearance deficit on file, and S31 showed one knob does not close it. Before
building another knob, price the whole lever class:

  actual    = fraction of living enemies within weapon range at the agent's
              ACTUAL position
  reachable = the best that fraction could have been at any position the agent
              could physically have reached within REACH_SEC
  global    = the best at any position in the arena (an upper bound the agent
              cannot generally attain -- reported to bound the question, never
              as a target)

If `reachable` is barely above `actual`, positioning cannot deliver the gap and
the whole movement-lever class is dead at D5 regardless of which knob is used.
If it is far above, the headroom is real and this quantifies the target.
"""
import json
import math
import os
import statistics as st

RUNS = os.path.join(os.environ["APPDATA"], "Brotato", "brotato_agent", "runs")
STRIDE = 37          # sample captures; prime, to avoid aliasing with any cadence
GRID = 9             # GRID x GRID candidate positions
REACH_SEC = 1.0      # how far ahead the agent could actually move


def arms():
    out = []
    for tag in ("d05", "d10", "d20", "d30"):
        sf = ".tmp/s31_bcs/%s/state.json" % tag
        if os.path.exists(sf):
            out += json.load(open(sf, encoding="utf-8-sig"))["collected_run_ids"]
    return out


def frac_at(px, py, enemies, rng):
    if not enemies:
        return None
    n = 0
    for e in enemies:
        ex, ey = e.get("x"), e.get("y")
        if ex is None or ey is None:
            continue
        if math.hypot(ex - px, ey - py) <= rng:
            n += 1
    return n / float(len(enemies))


def main():
    ids = arms()
    print("runs (denominator):", len(ids))
    actual, reach, glob, gaps, speeds = [], [], [], [], []
    dist_to_best = []
    sampled = skipped_no_arena = 0

    for rid in ids:
        path = os.path.join(RUNS, rid, "events.jsonl")
        if not os.path.exists(path):
            continue
        k = 0
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if '"combat_capture"' not in line:
                    continue
                try:
                    e = json.loads(line)
                except Exception:
                    continue
                if e.get("event") != "combat_capture":
                    continue
                k += 1
                if k % STRIDE:
                    continue
                p = e.get("payload") or {}
                pl = p.get("player") or {}
                enemies = (p.get("entities") or {}).get("enemies") or []
                weps = p.get("weapons") or []
                rng = max([float(w.get("max_range", 0) or 0) for w in weps] or [0.0])
                px, py = pl.get("x"), pl.get("y")
                spd = pl.get("speed")
                if not enemies or rng <= 0 or px is None or py is None:
                    continue
                arena = p.get("arena") or {}
                xs = [arena.get(k2) for k2 in ("min_x", "x_min", "left")]
                # Arena bounds are not guaranteed present under a known key --
                # derive from entity extents rather than assume a schema.
                exs = [en.get("x") for en in enemies if en.get("x") is not None] + [px]
                eys = [en.get("y") for en in enemies if en.get("y") is not None] + [py]
                if len(exs) < 2:
                    skipped_no_arena += 1
                    continue
                x0, x1 = min(exs), max(exs)
                y0, y1 = min(eys), max(eys)
                if x1 - x0 < 1 or y1 - y0 < 1:
                    continue
                a = frac_at(px, py, enemies, rng)
                if a is None:
                    continue
                sampled += 1
                if isinstance(spd, (int, float)) and spd > 0:
                    speeds.append(float(spd))
                reach_r = (float(spd) if isinstance(spd, (int, float)) and spd > 0
                           else 470.0) * REACH_SEC
                best_g = a
                best_r = a
                best_r_d = 0.0
                for i in range(GRID):
                    for j in range(GRID):
                        cx = x0 + (x1 - x0) * i / (GRID - 1.0)
                        cy = y0 + (y1 - y0) * j / (GRID - 1.0)
                        f = frac_at(cx, cy, enemies, rng)
                        if f is None:
                            continue
                        if f > best_g:
                            best_g = f
                        d = math.hypot(cx - px, cy - py)
                        if d <= reach_r and f > best_r:
                            best_r = f
                            best_r_d = d
                actual.append(a)
                reach.append(best_r)
                glob.append(best_g)
                gaps.append(best_r - a)
                dist_to_best.append(best_r_d)

    print("captures sampled (denominator):", sampled,
          " skipped for missing geometry:", skipped_no_arena)
    if not sampled:
        print("NO SAMPLES -- a zero here would be VACUOUS; stopping.")
        return 1
    print("median player speed (u/s):", round(st.median(speeds), 1) if speeds else "n/a",
          " => reach radius at %.1fs = %.0f u" % (REACH_SEC, (st.median(speeds) if speeds else 470.0) * REACH_SEC))
    print()
    print("IN-RANGE FRACTION, sampled captures")
    for name, series in (("actual (where it stood)", actual),
                         ("best REACHABLE in %.1fs" % REACH_SEC, reach),
                         ("best ANYWHERE (upper bound)", glob)):
        print("  %-28s mean=%.4f  median=%.4f  p90=%.4f"
              % (name, st.mean(series), st.median(series),
                 sorted(series)[int(0.9 * (len(series) - 1))]))
    print()
    print("  POSITIONING HEADROOM (reachable - actual): mean=%.4f  median=%.4f"
          % (st.mean(gaps), st.median(gaps)))
    print("  median distance to the better spot: %.0f u" % st.median(dist_to_best))
    print()
    print("  human band 0.4417 ; agent recorded 0.2801")
    print("  Is the human band even REACHABLE from where the agent stands?")
    n_reach = sum(1 for r in reach if r >= 0.4417)
    print("    captures whose best-reachable fraction >= 0.4417 : %d / %d = %.1f%%"
          % (n_reach, sampled, 100.0 * n_reach / sampled))
    n_act = sum(1 for a in actual if a >= 0.4417)
    print("    captures already at    >= 0.4417                 : %d / %d = %.1f%%"
          % (n_act, sampled, 100.0 * n_act / sampled))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
