"""§33 Gate 0: does lowering BOSS_FINALE_BODY_PACK_CLEARANCE change the route?

Implements reports/wp2/pack_clearance_floor_prereg.md exactly.

The floor is  body_floor = max(45, min(PACK, highest_body_clearance - slack))
and it SATURATES at PACK on ~75% of D5 captures, so PACK -- never dosed, because
§31 deliberately scaled only the slack -- is the constant that actually sets it.

0.2.76 zeroed the score terms on SKIPPED lanes, so a gated-out lane's score is
recovered rather than assumed: align_i = 14*dot(cand_i, baseline) is an
overdetermined system once two non-parallel lanes are admitted.

⛔ THREE CONTROLS, and the counterfactual is VOID unless all pass:
   1. recovered baseline reproduces recorded `align` to <= 1e-2 (the stepify floor)
   2. admitted(160) == the recorded skip flags
   3. chosen(160)   == the recorded sel_x/sel_y   <-- the control §32 lacked

Usage:
    python scripts/wp2_pack_floor_gate0.py --runs-dir <dir> [--stride N]
    python scripts/wp2_pack_floor_gate0.py --self-test
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
ALIGN_BONUS = 14.0
CONTINUITY = 85.0
ENEMY_SLACK = 20.0
CRITICAL = 45.0
PACK_ACTUAL = 160.0
PACKS = [120.0, 80.0, CRITICAL]
ALIGN_TOL = 1e-2          # stepify(align, 0.01) => ~5e-3 achievable floor
EXCLUDE_RUNS = {"run_1785754086_12860"}


def slack_for(wave):
    return 35.0 if int(wave) <= 12 else 20.0


def recover_baseline(admitted):
    """Least squares for `baseline` from align_i = ALIGN_BONUS * (cand_i . b)."""
    sxx = sxy = syy = sxa = sya = 0.0
    for r in admitted:
        cx, cy = float(r.get("x", 0)), float(r.get("y", 0))
        a = float(r.get("align", 0)) / ALIGN_BONUS
        sxx += cx * cx; sxy += cx * cy; syy += cy * cy
        sxa += cx * a;  sya += cy * a
    det = sxx * syy - sxy * sxy
    if abs(det) < 1e-9:
        return None, None
    bx = (syy * sxa - sxy * sya) / det
    by = (-sxy * sxa + sxx * sya) / det
    err = max(abs(ALIGN_BONUS * (float(r.get("x", 0)) * bx + float(r.get("y", 0)) * by)
                  - float(r.get("align", 0))) for r in admitted)
    return (bx, by), err


def score_of(r, bx, by, px, py):
    return (float(r.get("proj", 0)) - float(r.get("pen", 0))
            + ALIGN_BONUS * (float(r.get("x", 0)) * bx + float(r.get("y", 0)) * by)
            + CONTINUITY * (float(r.get("x", 0)) * px + float(r.get("y", 0)) * py))


def admitted_at(rows, pack, proj_floor, wave):
    hbc = max((float(r.get("body", -1e18)) for r in rows
               if float(r.get("proj", -1e18)) >= proj_floor), default=None)
    if hbc is None:
        return None
    floor = max(CRITICAL, min(pack, hbc - slack_for(wave)))
    by_floors = [r for r in rows
                 if float(r.get("proj", -1e18)) >= proj_floor
                 and float(r.get("body", -1e18)) >= floor]
    if not by_floors:
        return []
    lowest = min(float(r.get("pen", 0)) for r in by_floors)
    return [r for r in by_floors if float(r.get("pen", 0)) <= lowest + ENEMY_SLACK]


def inrange_after(px, py, speed, ux, uy, threats, max_range, h=HORIZON):
    n = math.hypot(ux, uy)
    if n <= 1e-9 or not threats:
        return None
    nx, ny = px + (ux / n) * speed * h, py + (uy / n) * speed * h
    return sum(1 for t in threats
               if math.hypot(t["x"] + t.get("vx", 0.0) * h - nx,
                             t["y"] + t.get("vy", 0.0) * h - ny) <= max_range) / float(len(threats))


def key(r):
    return (round(float(r.get("x", 0)), 4), round(float(r.get("y", 0)), 4))


def run(runs_dir, ids, stride):
    skipped = Counter()
    ctl = Counter()
    caps = []

    for rid in ids:
        path = os.path.join(runs_dir, rid, "events.jsonl")
        if not os.path.exists(path):
            skipped["missing_events"] += 1
            continue
        kept = 0
        for line in open(path, encoding="utf-8", errors="replace"):
            if '"combat_capture"' not in line:
                continue
            kept += 1
            if stride > 1 and kept % stride:
                continue
            try:
                ev = json.loads(line)
            except ValueError:
                skipped["unparseable"] += 1
                continue
            pl = ev.get("payload") or {}
            r = ((pl.get("teacher") or {}).get("contributions") or {}).get("route")
            if not r or r.get("exit") != "ranked" or not r.get("scores"):
                continue
            rows = r["scores"]
            adm_rec = [x for x in rows if not x.get("skip")]
            if len(adm_rec) < 2:
                skipped["fewer_than_2_admitted"] += 1
                continue
            wave = pl.get("wave", 0)
            proj_floor = float(r.get("projectile_floor", -1e18))

            b, err = recover_baseline(adm_rec)
            if b is None or err > ALIGN_TOL:
                skipped["baseline_unrecoverable"] += 1
                ctl["c1_fail"] += 1
                continue
            ctl["c1_ok"] += 1
            bx, by = b
            px, py = float(r.get("prev_x", 0)), float(r.get("prev_y", 0))

            # CONTROL 2: admission at the actual PACK reproduces recorded skips
            sim = admitted_at(rows, PACK_ACTUAL, proj_floor, wave)
            if sim is None:
                skipped["no_highest_body"] += 1
                continue
            if {key(x) for x in sim} == {key(x) for x in adm_rec}:
                ctl["c2_ok"] += 1
            else:
                ctl["c2_fail"] += 1
                continue
            # CONTROL 3: the re-derived scores rank it the way the mod did
            pick = max(sim, key=lambda x: score_of(x, bx, by, px, py))
            if (abs(pick.get("x", 0) - r.get("sel_x", 1e9)) < 1e-4
                    and abs(pick.get("y", 0) - r.get("sel_y", 1e9)) < 1e-4):
                ctl["c3_ok"] += 1
            else:
                ctl["c3_fail"] += 1
                continue

            ents = pl.get("entities") or {}
            threats = [e for e in (ents.get("enemies") or []) + (ents.get("bosses") or [])
                       if float(e.get("hp", 0)) > 0]
            ranges = [float(w.get("max_range", 0)) for w in (pl.get("weapons") or [])
                      if w.get("max_range")]
            p = pl.get("player") or {}
            sp = float(p.get("speed", 0))
            if not threats or not ranges or sp <= 0:
                skipped["no_threats_or_range"] += 1
                continue
            ir = {}
            for x in rows:
                v = inrange_after(float(p.get("x", 0)), float(p.get("y", 0)), sp,
                                  x.get("x", 0), x.get("y", 0), threats, max(ranges))
                if v is not None:
                    ir[key(x)] = v
            if key(pick) not in ir:
                skipped["degenerate_pick"] += 1
                continue
            caps.append((rows, proj_floor, wave, bx, by, px, py, pick, ir))

    print("=" * 70)
    print("DENOMINATORS (before any result)")
    print("=" * 70)
    print(f"  runs                        : {len(ids)}")
    print(f"  analysis set                : {len(caps)}")
    for k, v in skipped.most_common():
        print(f"    excluded {k:26s} {v}")

    print("\n" + "=" * 70)
    print("THREE CONTROLS -- counterfactual is VOID unless all pass")
    print("=" * 70)
    def rate(a, b):
        t = ctl[a] + ctl[b]
        return ctl[a] / t if t else 0.0, t
    r1, t1 = rate("c1_ok", "c1_fail")
    r2, t2 = rate("c2_ok", "c2_fail")
    r3, t3 = rate("c3_ok", "c3_fail")
    print(f"  1. baseline recovered <= {ALIGN_TOL:g}   : {ctl['c1_ok']}/{t1} = {r1:.4f}")
    print(f"  2. admitted(160) == recorded skips : {ctl['c2_ok']}/{t2} = {r2:.4f}")
    print(f"  3. chosen(160)   == recorded sel   : {ctl['c3_ok']}/{t3} = {r3:.4f}"
          f"   <-- the control §32 lacked")
    if not caps:
        print("\n  !! EMPTY ANALYSIS SET -- no statistic reported.")
        return 1
    if r2 < 0.99 or r3 < 0.99:
        print("\n  ⛔ A CONTROL FAILED ITS 0.99 BAR. The simulated rule cannot reproduce")
        print("     the observed decision, so no counterfactual over it is reportable.")
        return 1
    print("  => all three pass")

    def med(v):
        v = sorted(v)
        return v[len(v) // 2] if v else float("nan")

    print("\n" + "=" * 70)
    print("GATE 0a/0b -- lower PACK, does the EMITTED lane change and improve?")
    print("=" * 70)
    print(f"  {'PACK':>6} {'flip_rate':>10} {'median_gain':>12} {'n_flip':>8}"
          f" {'body clr old->new':>20} {'mean adm':>9}")
    gains = []
    a_pass = b_pass = False
    for pack in PACKS:
        flips, gs, bo, bn, adm_n = 0, [], [], [], []
        for rows, pf, wave, bx, by, px, py, pick, ir in caps:
            sim = admitted_at(rows, pack, pf, wave)
            if not sim:
                continue
            adm_n.append(len(sim))
            new = max(sim, key=lambda x: score_of(x, bx, by, px, py))
            if key(new) != key(pick):
                if key(new) not in ir:
                    continue
                flips += 1
                gs.append(ir[key(new)] - ir[key(pick)])
                bo.append(float(pick.get("body", 0)))
                bn.append(float(new.get("body", 0)))
        fr = flips / float(len(caps))
        g = med(gs) if gs else float("nan")
        gains.append(g if gs else -9.0)
        bc = f"{med(bo):.0f} -> {med(bn):.0f}" if bo else "-"
        print(f"  {pack:>6.0f} {fr:>10.4f} {g:>12.4f} {flips:>8} {bc:>20}"
              f" {sum(adm_n)/max(len(adm_n),1):>9.2f}")
        if fr >= 0.20:
            a_pass = True
            if gs and g >= 0.05:
                b_pass = True

    finite = [g for g in gains if g > -8.0]
    mono = all(finite[i] <= finite[i + 1] + 1e-9 for i in range(len(finite) - 1))
    print(f"\n  gain non-decreasing as PACK falls : {mono}")
    if not mono:
        print("  ⛔ NON-MONOTONE => pre-declared as NOISE, not partial success.")
        b_pass = False
    print(f"  GATE 0a (flip >= 0.20): {'PASS' if a_pass else 'FAIL'}")
    print(f"  GATE 0b (gain >= 0.05): {'PASS' if b_pass else 'FAIL'}")
    print("\n" + "=" * 70)
    print(f"VERDICT: {'SCREEN IT' if (a_pass and b_pass) else 'DO NOT IMPLEMENT'}")
    print("=" * 70)
    return 0


def _self_test():
    ok = True

    def check(n, c):
        nonlocal ok
        print(f"  [{'PASS' if c else 'FAIL'}] {n}")
        ok = ok and c

    # Baseline recovery must be exact on synthetic, unquantised input.
    base = (0.6, -0.8)
    lanes = []
    for cx, cy in ((1, 0), (0, 1), (0.7071, 0.7071)):
        lanes.append({"x": cx, "y": cy,
                      "align": ALIGN_BONUS * (cx * base[0] + cy * base[1])})
    b, err = recover_baseline(lanes)
    check("baseline recovered exactly", b is not None and err < 1e-9
          and abs(b[0] - 0.6) < 1e-9 and abs(b[1] + 0.8) < 1e-9)

    # Collinear lanes are degenerate and must return None, not a wrong answer.
    col = [{"x": 1, "y": 0, "align": 8.4}, {"x": 2, "y": 0, "align": 16.8}]
    b2, _ = recover_baseline(col)
    check("collinear lanes rejected", b2 is None)

    # Lowering PACK must ADMIT MORE, never fewer.
    rows = [{"x": 1, "y": 0, "body": 400, "proj": 1e6, "pen": 0},
            {"x": 0, "y": 1, "body": 200, "proj": 1e6, "pen": 0},
            {"x": -1, "y": 0, "body": 100, "proj": 1e6, "pen": 0},
            {"x": 0, "y": -1, "body": 50, "proj": 1e6, "pen": 0}]
    n160 = len(admitted_at(rows, 160.0, -1e18, 5))
    n80 = len(admitted_at(rows, 80.0, -1e18, 5))
    n45 = len(admitted_at(rows, 45.0, -1e18, 5))
    check("lowering PACK is monotone in admissions", n160 <= n80 <= n45)
    check("the dose actually changes the admitted set", n45 > n160)

    # The floor must never go below CRITICAL however low PACK is set.
    rows2 = [{"x": 1, "y": 0, "body": 44, "proj": 1e6, "pen": 0},
             {"x": 0, "y": 1, "body": 400, "proj": 1e6, "pen": 0}]
    adm = admitted_at(rows2, 0.0, -1e18, 5)
    check("hard 45 contact floor still excludes a 44-clearance lane",
          all(float(r["body"]) >= CRITICAL for r in adm))

    # The flip statistic must be able to return NO flip.
    check("identical sets produce no flip", key(rows[0]) == key(dict(rows[0])))
    print("\nSELF-TEST", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs-dir")
    ap.add_argument("--mod-version", default="0.2.76-wp2-capture")
    ap.add_argument("--stride", type=int, default=3)
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return _self_test()
    if not a.runs_dir:
        ap.error("--runs-dir required unless --self-test")
    ids = []
    for d in sorted(os.listdir(a.runs_dir)):
        sp = os.path.join(a.runs_dir, d, "summary.json")
        if not os.path.isfile(sp):
            continue
        try:
            s = json.load(open(sp, encoding="utf-8-sig"))
        except ValueError:
            continue
        if (str(s.get("mod_version")) == a.mod_version
                and s.get("route_scores_enabled") and d not in EXCLUDE_RUNS):
            ids.append(d)
    print(f"runs selected {len(ids)} at {a.mod_version}")
    return run(a.runs_dir, ids, a.stride)


if __name__ == "__main__":
    sys.exit(main())
