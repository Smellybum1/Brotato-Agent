"""§32 Gate 0: would a POSITIONAL preference term change the body-safety route?

Implements reports/wp2/route_position_term_prereg.md exactly. Authored BLIND,
while the collection campaign was still running.

The term under test:  score += w * inrange_after(cand, h)
  inrange_after = fraction of LIVING threats within weapon range after advancing
  the player along `cand` at player.speed for h = ESCAPE_HORIZON (0.60 s), AND
  advancing each threat by its own recorded (vx, vy) for the same h.

GATE 0a (weight-free, necessary): median headroom >= 0.05 AND share with
         headroom > 0.01 >= 50%.  No knob to turn until this passes.
GATE 0b: some w <= 300 with flip_rate >= 0.20 AND median realised_gain >= 0.05,
         and realised_gain non-decreasing in w up to its max (non-monotone =>
         NOISE, per the S31 body_clearance_scale trap).

Usage:
    python scripts/wp2_position_term_gate0.py --runs-dir <dir> [--stride N]
    python scripts/wp2_position_term_gate0.py --self-test
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from collections import Counter

HORIZON = 0.60          # BotConfig.ESCAPE_HORIZON -- fixed in the prereg
WEIGHTS = [10, 25, 50, 85, 150, 300]   # 85 == BOSS_FINALE_ESCAPE_CONTINUITY
EXCLUDE_RUNS = {"run_1785754086_12860"}   # force-killed smoke; excluded in the prereg


def inrange_after(px, py, speed, ux, uy, threats, max_range, h=HORIZON):
    """Fraction of living threats within max_range after both sides move for h."""
    if not threats:
        return None
    n = math.hypot(ux, uy)
    if n <= 1e-9:
        return None
    nx, ny = px + (ux / n) * speed * h, py + (uy / n) * speed * h
    hit = 0
    for t in threats:
        ex = t["x"] + t.get("vx", 0.0) * h
        ey = t["y"] + t.get("vy", 0.0) * h
        if math.hypot(ex - nx, ey - ny) <= max_range:
            hit += 1
    return hit / float(len(threats))


def capture_rows(payload, route):
    """Return (admitted_rows_with_inrange, chosen_row) or None with a reason."""
    adm = [r for r in route.get("scores", []) if not r.get("skip")]
    if len(adm) < 2:
        return None, "fewer_than_2_admitted"
    ents = payload.get("entities") or {}
    threats = [e for e in (ents.get("enemies") or []) + (ents.get("bosses") or [])
               if float(e.get("hp", 0)) > 0]
    if not threats:
        return None, "no_living_threats"
    weapons = payload.get("weapons") or []
    ranges = [float(w.get("max_range", 0)) for w in weapons if w.get("max_range")]
    if not ranges:
        return None, "no_weapon_range"
    max_range = max(ranges)
    p = payload.get("player") or {}
    px, py = float(p.get("x", 0)), float(p.get("y", 0))
    speed = float(p.get("speed", 0))
    if speed <= 0:
        return None, "no_speed"

    out = []
    for r in adm:
        ir = inrange_after(px, py, speed, r.get("x", 0.0), r.get("y", 0.0),
                           threats, max_range)
        if ir is None:
            return None, "degenerate_lane"
        out.append((r, ir))

    chosen = None
    for r, ir in out:
        if (abs(r.get("x", 0) - route.get("sel_x", 1e9)) < 1e-4
                and abs(r.get("y", 0) - route.get("sel_y", 1e9)) < 1e-4):
            chosen = (r, ir)
            break
    if chosen is None:
        return None, "chosen_lane_not_in_admitted"
    return (out, chosen), None


def analyse(runs_dir, run_ids, stride):
    rows = []
    skipped = Counter()
    per_run = Counter()
    n_route = n_ranked = 0

    for rid in run_ids:
        path = os.path.join(runs_dir, rid, "events.jsonl")
        if not os.path.exists(path):
            skipped["missing_events_file"] += 1
            continue
        kept = 0
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if '"combat_capture"' not in line:
                    continue
                kept += 1
                if stride > 1 and kept % stride:
                    continue
                try:
                    ev = json.loads(line)
                except ValueError:
                    skipped["unparseable_line"] += 1
                    continue
                pl = ev.get("payload") or {}
                route = ((pl.get("teacher") or {}).get("contributions") or {}).get("route")
                if not route:
                    continue
                n_route += 1
                if route.get("exit") != "ranked" or not route.get("scores"):
                    continue
                n_ranked += 1
                res, why = capture_rows(pl, route)
                if res is None:
                    skipped[why] += 1
                    continue
                lanes, chosen = res
                rows.append((rid, lanes, chosen))
                per_run[rid] += 1

    print("=" * 70)
    print("DENOMINATORS (printed before any result computed on them)")
    print("=" * 70)
    print(f"  runs analysed                       : {len(run_ids)}")
    print(f"  captures carrying a route block     : {n_route}")
    print(f"  ...exit == 'ranked' with rows       : {n_ranked}")
    print(f"  ...in the ANALYSIS SET              : {len(rows)}")
    print("  excluded, with reasons (never silent):")
    for k, v in skipped.most_common():
        print(f"    {k:28s} {v}")
    print("  per-run analysis-set size:")
    for k in sorted(per_run):
        print(f"    {k:28s} {per_run[k]}")
    if len(rows) == 0:
        print("\n  !! EMPTY ANALYSIS SET -- refusing to report any statistic.")
        return 1
    if len(per_run) < 6:
        print(f"\n  !! WARNING: only {len(per_run)} runs contribute. The prereg "
              f"requires >= 6. Treat everything below as a SMOKE.")

    def med(v):
        v = sorted(v)
        return v[len(v) // 2] if v else float("nan")

    # ---------------- GATE 0a ----------------
    print("\n" + "=" * 70)
    print("GATE 0a -- WEIGHT-FREE HEADROOM")
    print("  bars: median >= 0.05  AND  share(headroom > 0.01) >= 0.50")
    print("=" * 70)
    heads = []
    for _rid, lanes, chosen in rows:
        best = max(ir for _r, ir in lanes)
        heads.append(best - chosen[1])
    m = med(heads)
    share = sum(1 for h in heads if h > 0.01) / float(len(heads))
    hs = sorted(heads)
    print(f"  n = {len(heads)}")
    print(f"  headroom  min {hs[0]:.4f}  p25 {hs[len(hs)//4]:.4f}  MEDIAN {m:.4f}"
          f"  p75 {hs[3*len(hs)//4]:.4f}  max {hs[-1]:.4f}")
    print(f"  share with headroom > 0.01          : {share:.4f}")
    print(f"  mean in-range of the CHOSEN lane    : "
          f"{sum(c[1] for _r, _l, c in rows)/len(rows):.4f}")
    print(f"  mean in-range of the BEST admitted  : "
          f"{sum(max(ir for _r, ir in l) for _r, l, _c in rows)/len(rows):.4f}")
    a_pass = (m >= 0.05) and (share >= 0.50)
    print(f"\n  GATE 0a: {'PASS' if a_pass else 'FAIL'}"
          f"   (median {m:.4f} vs 0.05; share {share:.4f} vs 0.50)")
    if not a_pass:
        print("  => The chosen lane is already at/near the best in-range among lanes")
        print("     the gates allowed. NO weight on any positional term can help.")
        print("     Branch closed at zero implementation cost.")

    # ---------------- GATE 0b ----------------
    print("\n" + "=" * 70)
    print("GATE 0b -- FLIP RATE AND REALISED GAIN")
    print("  bars: some w <= 300 with flip >= 0.20 AND median gain >= 0.05")
    print("=" * 70)
    print(f"  {'w':>5} {'flip_rate':>10} {'median_gain':>12} {'n_flipped':>10}"
          f" {'body_clr chosen->new':>24}")
    gains_by_w = []
    b_pass = False
    for w in WEIGHTS:
        flips = 0
        gains = []
        bc_old, bc_new = [], []
        for _rid, lanes, chosen in rows:
            new = max(lanes, key=lambda t: t[0].get("score", 0.0) + w * t[1])
            if (abs(new[0].get("x", 0) - chosen[0].get("x", 0)) > 1e-4
                    or abs(new[0].get("y", 0) - chosen[0].get("y", 0)) > 1e-4):
                flips += 1
                gains.append(new[1] - chosen[1])
                bc_old.append(float(chosen[0].get("body", 0)))
                bc_new.append(float(new[0].get("body", 0)))
        fr = flips / float(len(rows))
        g = med(gains) if gains else float("nan")
        gains_by_w.append(g if gains else -1.0)
        bc = (f"{med(bc_old):.0f} -> {med(bc_new):.0f}" if bc_old else "-")
        print(f"  {w:>5} {fr:>10.4f} {g:>12.4f} {flips:>10} {bc:>24}")
        if fr >= 0.20 and gains and g >= 0.05:
            b_pass = True

    finite = [g for g in gains_by_w if g > -0.5]
    mono = all(finite[i] <= finite[i + 1] + 1e-9 for i in range(len(finite) - 1))
    if not mono:
        peak = finite.index(max(finite))
        mono = all(finite[i] <= finite[i + 1] + 1e-9 for i in range(peak))
    print(f"\n  realised_gain non-decreasing in w up to its max : {mono}")
    if not mono:
        print("  ⛔ NON-MONOTONE => declared in advance as NOISE, not partial success.")
        b_pass = False
    print(f"  GATE 0b: {'PASS' if b_pass else 'FAIL'}")

    # ---------------- reach ----------------
    print("\n" + "=" * 70)
    print("REPORTED, NOT BARRED")
    print("=" * 70)
    ranked_share = n_ranked / float(n_route) if n_route else 0.0
    print(f"  ranked share of all route captures  : {ranked_share:.4f}")
    print(f"  analysis-set share of all captures  : {len(rows)/float(n_route):.4f}")
    print("  => multiply any flip_rate above by the analysis-set share to get the")
    print("     fraction of ALL decisions this term could move.")

    print("\n" + "=" * 70)
    print(f"VERDICT: Gate 0a {'PASS' if a_pass else 'FAIL'}, "
          f"Gate 0b {'PASS' if b_pass else 'FAIL'} => "
          f"{'IMPLEMENT AND SCREEN' if (a_pass and b_pass) else 'DO NOT IMPLEMENT'}")
    print("=" * 70)
    return 0


def _self_test():
    ok = True

    def check(name, cond):
        nonlocal ok
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")
        ok = ok and cond

    # Enemy directly east at 500u, range 460: standing still leaves it OUT of
    # range; moving east at 450 u/s for 0.6 s (270u) brings it IN.
    threats = [{"x": 500.0, "y": 0.0, "vx": 0.0, "vy": 0.0, "hp": 5}]
    east = inrange_after(0, 0, 450, 1, 0, threats, 460.0)
    west = inrange_after(0, 0, 450, -1, 0, threats, 460.0)
    check("moving toward the threat puts it in range", east == 1.0)
    check("moving away leaves it out of range", west == 0.0)

    # A FLEEING threat must be able to defeat an approach -- proves enemy motion
    # is actually applied, not silently dropped.
    fleeing = [{"x": 500.0, "y": 0.0, "vx": 900.0, "vy": 0.0, "hp": 5}]
    check("enemy velocity is applied (fleeing threat stays out of range)",
          inrange_after(0, 0, 450, 1, 0, fleeing, 460.0) == 0.0)

    # Degenerate inputs must return None, not 0.0 -- a plausible-looking zero is
    # exactly the failure mode this project keeps hitting.
    check("zero-length lane returns None, not 0.0",
          inrange_after(0, 0, 450, 0, 0, threats, 460.0) is None)
    check("empty threat list returns None, not 0.0",
          inrange_after(0, 0, 450, 1, 0, [], 460.0) is None)

    # capture_rows must reject a capture whose chosen lane is not in the pool
    # rather than silently picking another.
    pay = {"entities": {"enemies": threats}, "weapons": [{"max_range": 460}],
           "player": {"x": 0, "y": 0, "speed": 450}}
    route = {"scores": [{"x": 1.0, "y": 0.0, "skip": "", "score": 1.0, "body": 200},
                        {"x": -1.0, "y": 0.0, "skip": "", "score": 0.0, "body": 200}],
             "sel_x": 0.0, "sel_y": 1.0}
    res, why = capture_rows(pay, route)
    check("unmatched chosen lane is rejected", res is None and why == "chosen_lane_not_in_admitted")

    route["sel_x"], route["sel_y"] = -1.0, 0.0
    res, why = capture_rows(pay, route)
    check("well-formed capture is accepted", res is not None)
    if res:
        lanes, chosen = res
        check("headroom is positive when a better lane exists",
              max(ir for _r, ir in lanes) - chosen[1] == 1.0)

    # Single-admitted-lane captures are excluded (no choice existed).
    one = {"scores": [{"x": 1.0, "y": 0.0, "skip": "", "score": 1.0}],
           "sel_x": 1.0, "sel_y": 0.0}
    res, why = capture_rows(pay, one)
    check("single-lane capture excluded", res is None and why == "fewer_than_2_admitted")

    print("\nSELF-TEST", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs-dir")
    ap.add_argument("--mod-version", default="0.2.76-wp2-capture")
    ap.add_argument("--stride", type=int, default=3)
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        return _self_test()
    if not args.runs_dir:
        ap.error("--runs-dir required unless --self-test")

    ids, scanned, armed = [], 0, 0
    for d in sorted(os.listdir(args.runs_dir)):
        sp = os.path.join(args.runs_dir, d, "summary.json")
        if not os.path.isfile(sp):
            continue
        scanned += 1
        try:
            s = json.load(open(sp, encoding="utf-8-sig"))
        except ValueError:
            continue
        if str(s.get("mod_version")) != args.mod_version:
            continue
        if not s.get("route_scores_enabled"):
            continue
        armed += 1
        if d in EXCLUDE_RUNS:
            continue
        ids.append(d)
    print(f"summaries scanned {scanned}; at {args.mod_version} with the instrument "
          f"ARMED {armed}; after prereg exclusions {len(ids)}")
    return analyse(args.runs_dir, ids, args.stride)


if __name__ == "__main__":
    sys.exit(main())
