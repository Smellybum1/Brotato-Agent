"""EXPLORATORY (post-hoc, after §32's pre-registered Gate 0 FAILED).

§32 asked whether the lane RANKING throws away in-range opportunity. It does not:
the chosen lane is already at/near the best in-range among ADMITTED lanes.

That leaves the obvious next question, which §32 did not ask: is the opportunity
thrown away by the ADMISSION GATE instead? `body_floor` drops ~34% of candidates.
If the high-in-range lanes are the ones being gated out, the lever is the FLOOR,
not the score.

⛔ THIS IS HYPOTHESIS GENERATION, NOT A TEST. It runs on the data that just failed
a pre-registered gate, so it is exposed to the outcome. Anything it finds needs
its own pre-registration and its own fresh runs before it means anything.

⭐ POSITIVE CONTROL, and the analysis is void without it: simulating the recorded
floor must reproduce the recorded skip flags EXACTLY. A counterfactual over the
admission rule cannot be trusted unless the rule is reconstructed correctly first.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from collections import Counter

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HORIZON = 0.60
ENEMY_PENALTY_SLACK = 20.0     # BotConfig.BOSS_FINALE_ENEMY_PENALTY_SLACK
CRITICAL = 45.0                # BOSS_FINALE_BODY_CRITICAL_CLEARANCE (never scaled)
EXCLUDE_RUNS = {"run_1785754086_12860"}


def inrange_after(px, py, speed, ux, uy, threats, max_range, h=HORIZON):
    n = math.hypot(ux, uy)
    if n <= 1e-9 or not threats:
        return None
    nx, ny = px + (ux / n) * speed * h, py + (uy / n) * speed * h
    hit = 0
    for t in threats:
        if math.hypot(t["x"] + t.get("vx", 0.0) * h - nx,
                      t["y"] + t.get("vy", 0.0) * h - ny) <= max_range:
            hit += 1
    return hit / float(len(threats))


def admit(rows, body_floor, proj_floor):
    """Reproduce the mod's admission rule from recorded per-lane values."""
    by_floors = [r for r in rows
                 if float(r.get("proj", -1e18)) >= proj_floor
                 and float(r.get("body", -1e18)) >= body_floor]
    if not by_floors:
        return []
    lowest = min(float(r.get("pen", 0.0)) for r in by_floors)
    return [r for r in by_floors
            if float(r.get("pen", 0.0)) <= lowest + ENEMY_PENALTY_SLACK]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs-dir", required=True)
    ap.add_argument("--stride", type=int, default=3)
    args = ap.parse_args()

    ids = []
    for d in sorted(os.listdir(args.runs_dir)):
        sp = os.path.join(args.runs_dir, d, "summary.json")
        if not os.path.isfile(sp):
            continue
        try:
            s = json.load(open(sp, encoding="utf-8-sig"))
        except ValueError:
            continue
        if (str(s.get("mod_version")) == "0.2.76-wp2-capture"
                and s.get("route_scores_enabled") and d not in EXCLUDE_RUNS):
            ids.append(d)
    print(f"runs: {len(ids)}")

    control_ok = control_bad = 0
    caps = []
    for rid in ids:
        p = os.path.join(args.runs_dir, rid, "events.jsonl")
        if not os.path.exists(p):
            continue
        kept = 0
        for line in open(p, encoding="utf-8", errors="replace"):
            if '"combat_capture"' not in line:
                continue
            kept += 1
            if args.stride > 1 and kept % args.stride:
                continue
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            pl = ev.get("payload") or {}
            r = ((pl.get("teacher") or {}).get("contributions") or {}).get("route")
            if not r or r.get("exit") != "ranked" or not r.get("scores"):
                continue
            rows = r["scores"]
            bf, pf = float(r.get("body_floor", -1e18)), float(r.get("projectile_floor", -1e18))

            # ---- POSITIVE CONTROL: reconstruct the ACTUAL admission ----
            sim = admit(rows, bf, pf)
            sim_xy = {(round(x.get("x", 0), 4), round(x.get("y", 0), 4)) for x in sim}
            act_xy = {(round(x.get("x", 0), 4), round(x.get("y", 0), 4))
                      for x in rows if not x.get("skip")}
            if sim_xy == act_xy:
                control_ok += 1
            else:
                control_bad += 1
                continue

            ents = pl.get("entities") or {}
            threats = [e for e in (ents.get("enemies") or []) + (ents.get("bosses") or [])
                       if float(e.get("hp", 0)) > 0]
            ranges = [float(w.get("max_range", 0)) for w in (pl.get("weapons") or [])
                      if w.get("max_range")]
            if not threats or not ranges:
                continue
            player = pl.get("player") or {}
            px, py, sp = float(player.get("x", 0)), float(player.get("y", 0)), float(player.get("speed", 0))
            if sp <= 0:
                continue
            ir = {}
            for x in rows:
                v = inrange_after(px, py, sp, x.get("x", 0), x.get("y", 0), threats, max(ranges))
                if v is not None:
                    ir[(round(x.get("x", 0), 4), round(x.get("y", 0), 4))] = v
            if not ir:
                continue
            caps.append((rows, bf, pf, ir))

    print(f"\nPOSITIVE CONTROL -- simulated admission reproduces recorded skips:")
    tot = control_ok + control_bad
    print(f"  {control_ok}/{tot} = {control_ok/max(tot,1):.4f}   mismatches {control_bad}")
    if tot and control_ok / tot < 0.99:
        print("  !! Reconstruction does not match production. Counterfactual VOID.")
        return 1
    print(f"  analysable captures: {len(caps)}")
    if not caps:
        print("  !! empty set")
        return 1

    def med(v):
        v = sorted(v)
        return v[len(v) // 2]

    print("\n" + "=" * 70)
    print("IS THE OPPORTUNITY GATED OUT, OR OUT-RANKED?")
    print("=" * 70)
    best_adm, best_all = [], []
    for rows, bf, pf, ir in caps:
        adm = admit(rows, bf, pf)
        ba = max((ir[(round(x.get('x',0),4), round(x.get('y',0),4))] for x in adm
                  if (round(x.get('x',0),4), round(x.get('y',0),4)) in ir), default=None)
        bl = max(ir.values())
        if ba is None:
            continue
        best_adm.append(ba)
        best_all.append(bl)
    print(f"  n = {len(best_adm)}")
    print(f"  mean best in-range among ADMITTED lanes : {sum(best_adm)/len(best_adm):.4f}")
    print(f"  mean best in-range among ALL 24 lanes   : {sum(best_all)/len(best_all):.4f}")
    gated = [b - a for a, b in zip(best_adm, best_all)]
    print(f"  GATED-OUT opportunity  median {med(gated):.4f}   mean {sum(gated)/len(gated):.4f}")
    print(f"  share of captures where the gate costs > 0.01 : "
          f"{sum(1 for g in gated if g > 0.01)/len(gated):.4f}")

    print("\n" + "=" * 70)
    print("COUNTERFACTUAL: lower the body floor (the PACK 160 constant binds it)")
    print("  reported: best in-range reachable at each floor, and lanes admitted")
    print("=" * 70)
    print(f"  {'floor':>8} {'mean best in-range':>20} {'mean admitted lanes':>21}")
    for F in (None, 160.0, 120.0, 80.0, CRITICAL):
        vals, counts = [], []
        for rows, bf, pf, ir in caps:
            f = bf if F is None else min(bf, F)
            adm = admit(rows, f, pf)
            v = [ir[(round(x.get('x',0),4), round(x.get('y',0),4))] for x in adm
                 if (round(x.get('x',0),4), round(x.get('y',0),4)) in ir]
            if v:
                vals.append(max(v))
                counts.append(len(adm))
        label = "actual" if F is None else f"<= {F:.0f}"
        print(f"  {label:>8} {sum(vals)/len(vals):>20.4f} {sum(counts)/len(counts):>21.2f}")
    print("\n  NOTE: lowering the floor admits lanes with LESS body clearance. This")
    print("  prices OPPORTUNITY only. The §31 low-HP-exposure veto still binds, and")
    print("  nothing here says the agent would survive taking those lanes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
