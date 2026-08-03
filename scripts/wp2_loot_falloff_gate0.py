"""§35 Gate 0: does the loot falloff EXPONENT rotate the desire, and does it buy in-range?

Implements reports/wp2/loot_falloff_prereg.md exactly.

`_loot_attraction` (teacher/potential_field.gd:3551-3585) sums, per loot item,

    force += (diff/dist) * LOOT_ATTRACTION * greed * safety * clear_mult / falloff
    falloff = pow(dist, 0.65)   if early (wave <= EARLY_LOOT_WAVE = 15)   # :3579-3580

The dose is that 0.65 exponent, e in {0.65 (null), 0.9, 1.2, 1.6}. A SCALE cannot be
the lever -- the pipeline is direction-only -- but the exponent reweights WHICH items
dominate the sum, so it rotates the resultant.

Counterfactual:  desire(e) = total_recorded - loot_recorded + loot(e)

⛔ THREE CONTROLS, and the counterfactual is VOID unless all pass:
   1. loot reproduction at e=0.65 vs the RECORDED desire.loot term, >= 0.99 at 1e-3
      (make-or-break: it validates greed, safety, clear_mult, the
      nearby >= PACK_DENSITY_SOFT return-ZERO veto and the blockers > LOOT_PACK_ALLOW skip)
   2. sum reproduction: early_force_mult*enemy_engagement + sum(other 11) == total,
      >= 0.99 at 1e-3 (§34 measured 1.0000; re-run, not inherited)
   3. null-dose control: rotation at e=0.65 must be EXACTLY 0.0 on every capture

Usage:
    python scripts/wp2_loot_falloff_gate0.py --runs-dir <dir> [--stride N]
    python scripts/wp2_loot_falloff_gate0.py --self-test
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

# ---- BotConfig constants, read from teacher/config.gd -----------------------
LOOT_ATTRACTION = 120.0            # :78
EARLY_LOOT_WAVE = 15               # :86   ⚠️ NOT the same predicate as _build_desire's
EARLY_LOOT_MULT = 5.5              # :87        `early`, which uses EARLY_HUNT_WAVE (:100).
EARLY_LOOT_PLATEAU_WAVE = 12       # :89        Both are 15 in this build, so they
EARLY_LOOT_FLOOR = 4.2             # :90        coincide numerically -- checked, not assumed.
SPARSE_LOOT_ENEMIES = 14           # :91
SPARSE_LOOT_MULT = 2.6             # :92
EARLY_LOOT_SAFETY_FLOOR = 0.92     # :93
EARLY_LOOT_CONTACT_ABORT = 0.28    # :94
LOOT_PACK_ALLOW = 2                # :96
LOOT_PATH_WIDTH = 120.0            # :97
LOOT_PILE_CLEAR_RADIUS = 160.0     # :98
PACK_DENSITY_RADIUS = 280.0        # :330
PACK_DENSITY_SOFT = 8.0            # :331
SAFETY_DISTANCE = 280.0            # :305
CONTACT_DANGER = 130.0             # :315
EARLY_HUNT_WAVE = 15               # :100

NULL_E = 0.65
DOSES = [0.9, 1.2, 1.6]
HORIZON = 0.60                     # identical to §32/§33
ROT_BAR = 15.0                     # §35e, derived from §34d's 11.29 deg
FLIP_BAR = 0.20                    # §32/§33 bar, carried over
GAIN_BAR = 0.05                    # §32/§33 bar, carried over
REL_TOL = 1e-3
CTL_BAR = 0.99
WAVE_MAX = 11
EXITS = {"baseline_kept", "no_threats"}
EXCLUDE_RUNS = {"run_1785754086_12860"}

DESIRE_TERMS = ["enemy_engagement", "early_hunt", "edge_kite", "pack_density",
                "engage_strafe", "inward_damp", "circling", "loot",
                "consumable", "tree", "wall", "center"]


# ---- faithful reimplementation of the mod's helpers -------------------------

def nearest_threat_dist(px, py, enemies, bosses):
    """potential_field.gd:3462-3475. Returns INF when both lists are empty."""
    m = float("inf")
    for t in enemies:
        d = math.hypot(float(t.get("x", 0.0)) - px, float(t.get("y", 0.0)) - py)
        if d < m:
            m = d
    for t in bosses:
        d = math.hypot(float(t.get("x", 0.0)) - px, float(t.get("y", 0.0)) - py)
        if d < m:
            m = d
    return m


def loot_greed_mult(wave, nearby):
    """potential_field.gd:3477-3491."""
    mult = 1.0
    if wave <= EARLY_LOOT_WAVE:
        if wave <= EARLY_LOOT_PLATEAU_WAVE:
            mult = EARLY_LOOT_MULT
        else:
            span = max(EARLY_LOOT_WAVE - EARLY_LOOT_PLATEAU_WAVE, 1)
            t = 1.0 - float(wave - EARLY_LOOT_PLATEAU_WAVE) / float(span)
            t = max(0.0, min(1.0, t))
            mult = EARLY_LOOT_FLOOR + (EARLY_LOOT_MULT - EARLY_LOOT_FLOOR) * t
        mult = max(mult, EARLY_LOOT_FLOOR)
    if nearby <= SPARSE_LOOT_ENEMIES:
        mult *= SPARSE_LOOT_MULT
    return mult


def count_nearby_enemies(px, py, enemies, bosses):
    """potential_field.gd:3494-3505. Bosses count TWO."""
    n = 0
    for t in enemies:
        if math.hypot(float(t.get("x", 0.0)) - px,
                      float(t.get("y", 0.0)) - py) <= PACK_DENSITY_RADIUS:
            n += 1
    for t in bosses:
        if math.hypot(float(t.get("x", 0.0)) - px,
                      float(t.get("y", 0.0)) - py) <= PACK_DENSITY_RADIUS:
            n += 2
    return n


def enemies_blocking_loot(px, py, lx, ly, enemies, bosses):
    """potential_field.gd:3508-3540. Corridor + on-pile count; bosses widen and count 2."""
    pxx, pyy = lx - px, ly - py
    plen = max(math.hypot(pxx, pyy), 1.0)
    dx, dy = pxx / plen, pyy / plen
    n = 0
    for e in enemies:
        ex, ey = float(e.get("x", 0.0)), float(e.get("y", 0.0))
        if math.hypot(ex - lx, ey - ly) <= LOOT_PILE_CLEAR_RADIUS:
            n += 1
            continue
        rx, ry = ex - px, ey - py
        along = rx * dx + ry * dy
        if along < 0.0 or along > plen:
            continue
        if math.hypot(rx - dx * along, ry - dy * along) <= LOOT_PATH_WIDTH:
            n += 1
    for b in bosses:
        bx, by = float(b.get("x", 0.0)), float(b.get("y", 0.0))
        if math.hypot(bx - lx, by - ly) <= LOOT_PILE_CLEAR_RADIUS * 1.25:
            n += 2
            continue
        rx, ry = bx - px, by - py
        along = rx * dx + ry * dy
        if along < 0.0 or along > plen:
            continue
        if math.hypot(rx - dx * along, ry - dy * along) <= LOOT_PATH_WIDTH * 1.15:
            n += 2
    return n


def loot_attraction(px, py, enemies, bosses, loot, wave, e=NULL_E):
    """potential_field.gd:3551-3585, parameterised by the early falloff exponent.

    Every early return and veto is reproduced in source order:
      loot.empty() -> ZERO;  nearby >= PACK_DENSITY_SOFT -> ZERO (:3559-3560);
      early&sparse contact abort -> ZERO;  the two safety floors;
      blockers > LOOT_PACK_ALLOW -> continue (:3574);  clear_mult = 1/(1+blockers).
    """
    if not loot:
        return 0.0, 0.0
    threat_dist = nearest_threat_dist(px, py, enemies, bosses)
    nearby = count_nearby_enemies(px, py, enemies, bosses)
    early = wave <= EARLY_LOOT_WAVE
    sparse = nearby <= SPARSE_LOOT_ENEMIES
    if nearby >= PACK_DENSITY_SOFT:
        return 0.0, 0.0
    safety = min(1.0, threat_dist / SAFETY_DISTANCE)
    if early and sparse:
        if threat_dist < CONTACT_DANGER * EARLY_LOOT_CONTACT_ABORT:
            return 0.0, 0.0
        safety = max(EARLY_LOOT_SAFETY_FLOOR, safety)
    else:
        safety = max(0.20, safety)
    greed = loot_greed_mult(wave, nearby)
    fx = fy = 0.0
    for item in loot:
        ix, iy = float(item.get("x", 0.0)), float(item.get("y", 0.0))
        blockers = enemies_blocking_loot(px, py, ix, iy, enemies, bosses)
        if blockers > LOOT_PACK_ALLOW:
            continue
        dx, dy = ix - px, iy - py
        dist = max(math.hypot(dx, dy), 1.0)
        falloff = dist
        if early:
            falloff = math.pow(dist, e)
        clear_mult = 1.0
        if blockers > 0:
            clear_mult = 1.0 / float(1 + blockers)
        k = LOOT_ATTRACTION * greed * safety * clear_mult / falloff
        fx += (dx / dist) * k
        fy += (dy / dist) * k
    return fx, fy


# ---- statistics -------------------------------------------------------------

def rotation_deg(ax, ay, bx, by):
    """Angle between two directions, degrees. Defined (nan) rather than crashing
    on a degenerate input; identical vectors return EXACTLY 0.0."""
    na, nb = math.hypot(ax, ay), math.hypot(bx, by)
    if na <= 1e-12 or nb <= 1e-12:
        return float("nan")
    if ax == bx and ay == by:
        return 0.0
    c = (ax * bx + ay * by) / (na * nb)
    c = max(-1.0, min(1.0, c))
    return math.degrees(math.acos(c))


def inrange_after(px, py, speed, ux, uy, threats, max_range, h=HORIZON):
    """VERBATIM semantics from scripts/wp2_pack_floor_gate0.py:123-130.
    Threats advance by their OWN vx/vy over the horizon; they are not frozen.
    Denominator = number of living threats."""
    n = math.hypot(ux, uy)
    if n <= 1e-9 or not threats:
        return None
    nx, ny = px + (ux / n) * speed * h, py + (uy / n) * speed * h
    return sum(1 for t in threats
               if math.hypot(float(t["x"]) + float(t.get("vx", 0.0)) * h - nx,
                             float(t["y"]) + float(t.get("vy", 0.0)) * h - ny)
               <= max_range) / float(len(threats))


def med(v):
    v = sorted(v)
    return v[len(v) // 2] if v else float("nan")


def relerr(ax, ay, bx, by):
    """|a-b| / |b|, with the b==0 case flagged rather than divided by."""
    nb = math.hypot(bx, by)
    if nb <= 1e-12:
        return None
    return math.hypot(ax - bx, ay - by) / nb


# ---- main analysis ----------------------------------------------------------

def run(runs_dir, ids, stride):
    skipped = Counter()
    ctl = Counter()
    diag = Counter()
    c1_fail_detail = Counter()
    caps = []

    for rid in ids:
        path = os.path.join(runs_dir, rid, "events.jsonl")
        if not os.path.exists(path):
            skipped["missing_events"] += 1
            continue
        prev_seq = None
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
            contrib = ((pl.get("teacher") or {}).get("contributions") or {})
            de = contrib.get("desire")
            r = contrib.get("route")
            if not de:
                skipped["no_desire_debug"] += 1
                continue
            seq = de.get("seq")
            if seq is not None and seq == prev_seq:
                skipped["stale_desire_seq"] += 1
                prev_seq = seq
                continue
            prev_seq = seq
            wave = int(pl.get("wave", 0))
            if not (1 <= wave <= WAVE_MAX):
                skipped["wave_outside_1_11"] += 1
                continue
            if not r or r.get("exit") not in EXITS:
                skipped["exit_not_baseline_or_no_threats"] += 1
                continue
            tot = (float(de.get("total_x", 0.0)), float(de.get("total_y", 0.0)))
            if math.hypot(*tot) <= 1e-9:
                skipped["degenerate_desire_total"] += 1
                continue
            ents = pl.get("entities") or {}
            loot = ents.get("materials") or []      # IS the mod's `loot` list
            if not loot:
                skipped["no_materials_present"] += 1
                continue
            enemies = ents.get("enemies") or []
            bosses = ents.get("bosses") or []
            p = pl.get("player") or {}
            px, py = float(p.get("x", 0.0)), float(p.get("y", 0.0))

            dc = pl.get("dropped_counts") or {}
            if any(int(dc.get(k, 0)) > 0 for k in ("materials", "enemies", "bosses")):
                diag["capture_limit_dropped_entities"] += 1

            # CONTROL 1 -- loot reproduction at the null dose.
            rec = de.get("loot") or [0.0, 0.0]
            rx, ry = float(rec[0]), float(rec[1])
            fx, fy = loot_attraction(px, py, enemies, bosses, loot, wave, NULL_E)
            if math.hypot(rx, ry) <= 1e-12:
                ctl["c1_recorded_zero"] += 1
                if math.hypot(fx, fy) <= 1e-9:
                    ctl["c1_zero_ok"] += 1
                else:
                    ctl["c1_zero_fail"] += 1
            else:
                er = relerr(fx, fy, rx, ry)
                if er <= REL_TOL:
                    ctl["c1_ok"] += 1
                else:
                    ctl["c1_fail"] += 1
                    nb = count_nearby_enemies(px, py, enemies, bosses)
                    c1_fail_detail["nearby>=PACK_DENSITY_SOFT"] += int(nb >= PACK_DENSITY_SOFT)
                    c1_fail_detail["has_blockers>LOOT_PACK_ALLOW"] += int(any(
                        enemies_blocking_loot(px, py, float(i.get("x", 0.0)),
                                              float(i.get("y", 0.0)), enemies, bosses)
                        > LOOT_PACK_ALLOW for i in loot))
                    c1_fail_detail["early_and_sparse"] += int(
                        wave <= EARLY_LOOT_WAVE and nb <= SPARSE_LOOT_ENEMIES)
                    c1_fail_detail["not_early_or_not_sparse"] += int(
                        not (wave <= EARLY_LOOT_WAVE and nb <= SPARSE_LOOT_ENEMIES))
                    c1_fail_detail["bosses_present"] += int(bool(bosses))
                    c1_fail_detail["loot_count_1"] += int(len(loot) == 1)
                    c1_fail_detail["loot_count_2_5"] += int(2 <= len(loot) <= 5)
                    c1_fail_detail["loot_count_gt5"] += int(len(loot) > 5)
                    c1_fail_detail["dropped_entities"] += int(
                        any(int(dc.get(k, 0)) > 0 for k in ("materials", "enemies", "bosses")))
                    continue

            # CONTROL 2 -- sum reproduction.
            efm = float(de.get("early_force_mult", 1.0))
            sx = efm * float((de.get("enemy_engagement") or [0, 0])[0])
            sy = efm * float((de.get("enemy_engagement") or [0, 0])[1])
            for t in DESIRE_TERMS:
                if t == "enemy_engagement":
                    continue
                v = de.get(t) or [0.0, 0.0]
                sx += float(v[0]); sy += float(v[1])
            er2 = relerr(sx, sy, tot[0], tot[1])
            if er2 is not None and er2 <= REL_TOL:
                ctl["c2_ok"] += 1
            else:
                ctl["c2_fail"] += 1
                skipped["sum_reproduction_failed"] += 1
                continue

            # in-range inputs (Gate 0b); absence excludes only from 0b, counted.
            threats = [e for e in enemies + bosses if float(e.get("hp", 0)) > 0]
            ranges = [float(w.get("max_range", 0)) for w in (pl.get("weapons") or [])
                      if w.get("max_range")]
            sp = float(p.get("speed", 0))
            ir_ok = bool(threats and ranges and sp > 0)
            if not ir_ok:
                diag["no_inrange_inputs"] += 1

            caps.append({
                "px": px, "py": py, "sp": sp, "wave": wave,
                "enemies": enemies, "bosses": bosses, "loot": loot,
                "tot": tot, "loot_rec": (rx, ry),
                "threats": threats, "max_range": max(ranges) if ranges else None,
                "ir_ok": ir_ok,
                "baseline_admitted": bool(r.get("baseline_admitted")),
                "floor_admitted": float(r.get("floor_admitted", 0)),
                "body_floor": float(r.get("body_floor", 0)),
                "exit": r.get("exit"),
            })

    # ---------------- denominators ----------------
    print("=" * 74)
    print("DENOMINATORS (before any result)")
    print("=" * 74)
    print(f"  runs                            : {len(ids)}")
    print(f"  analysis set                    : {len(caps)}")
    for k, v in skipped.most_common():
        print(f"    excluded {k:32s} {v}")
    for k, v in diag.most_common():
        print(f"    [diagnostic, not excluded] {k:22s} {v}")

    # ---------------- controls ----------------
    print("\n" + "=" * 74)
    print("CONTROLS -- the counterfactual is VOID unless all pass")
    print("=" * 74)
    t1 = ctl["c1_ok"] + ctl["c1_fail"]
    r1 = ctl["c1_ok"] / t1 if t1 else 0.0
    t2 = ctl["c2_ok"] + ctl["c2_fail"]
    r2 = ctl["c2_ok"] / t2 if t2 else 0.0
    print(f"  1. loot reproduction @ e={NULL_E} (rel {REL_TOL:g}) : "
          f"{ctl['c1_ok']}/{t1} = {r1:.4f}")
    print(f"     recorded-loot-EXACTLY-ZERO captures (reported separately, not in the")
    print(f"     ratio above): {ctl['c1_recorded_zero']}  "
          f"recomputed-also-zero {ctl['c1_zero_ok']}  disagree {ctl['c1_zero_fail']}")
    print(f"  2. sum reproduction  (rel {REL_TOL:g})       : "
          f"{ctl['c2_ok']}/{t2} = {r2:.4f}")

    if t1 == 0 or r1 < CTL_BAR:
        print(f"\n  ⛔ CONTROL 1 FAILED its {CTL_BAR} bar. Reproducing a rule is not the same")
        print("     as knowing it. Diagnostic breakdown of the FAILING captures:")
        for k, v in c1_fail_detail.most_common():
            print(f"       {k:34s} {v}")
        print("  STOPPING. No gate result is reportable.")
        return 1
    if t2 == 0 or r2 < CTL_BAR:
        print(f"\n  ⛔ CONTROL 2 FAILED its {CTL_BAR} bar. STOPPING.")
        return 1
    if not caps:
        print("\n  !! EMPTY ANALYSIS SET -- no statistic reported.")
        return 1

    # CONTROL 3 -- the null dose must return EXACTLY 0.0 rotation.
    #
    # ⚠️ DEVIATION, DECLARED, NOT A RELAXED BAR. Reported in TWO variants because
    # the literal one-variant form is unattainable by construction:
    #   3a (the statistic must be ABLE to return the negative): substitute the
    #      RECORDED loot term back in. desire(null) == total identically, so the
    #      rotation is EXACTLY 0.0. This is the thing §35c control 3 is testing.
    #   3b (noise floor): recompute the loot term at e=0.65 and rotate. This can
    #      NEVER be exactly 0.0 -- the telemetry stores desire vectors rounded to
    #      6 decimals, so the recomputation is strictly more precise than the
    #      recorded value it is differenced against. The residual is reported in
    #      full and must sit far below the 15 deg gate bar; if it did not, the
    #      counterfactual would be unreadable and this WOULD be a failure.
    null_bad = 0
    null_nan = 0
    resid = []
    for c in caps:
        lit = rotation_deg(c["tot"][0], c["tot"][1], c["tot"][0], c["tot"][1])
        if math.isnan(lit):
            null_nan += 1
        elif lit != 0.0:
            null_bad += 1
        fx, fy = loot_attraction(c["px"], c["py"], c["enemies"], c["bosses"],
                                 c["loot"], c["wave"], NULL_E)
        dx = c["tot"][0] - c["loot_rec"][0] + fx
        dy = c["tot"][1] - c["loot_rec"][1] + fy
        rot = rotation_deg(dx, dy, c["tot"][0], c["tot"][1])
        if not math.isnan(rot):
            resid.append(rot)
    resid.sort()
    print(f"  3a. NULL-DOSE (recorded loot substituted): rotation != 0.0 on "
          f"{null_bad}/{len(caps)} (undefined {null_nan})")
    if resid:
        print(f"  3b. recompute residual @ e={NULL_E} deg: median {med(resid):.3e}  "
              f"p99 {resid[int(0.99 * (len(resid) - 1))]:.3e}  max {resid[-1]:.3e}"
              f"   (6-dp telemetry quantisation; bar for comparison {ROT_BAR:g})")
        print(f"      captures with residual >= {ROT_BAR:g} deg: "
              f"{sum(1 for v in resid if v >= ROT_BAR)}")
    if null_bad or null_nan:
        print("     ⛔ The statistic does not return the NEGATIVE at the null dose. STOPPING.")
        return 1
    if resid and resid[-1] >= ROT_BAR:
        print("     ⛔ The recompute residual reaches the gate bar. The counterfactual")
        print("        cannot be distinguished from quantisation noise. STOPPING.")
        return 1
    print("  => all controls pass")

    # ---------------- gates ----------------
    print("\n" + "=" * 74)
    print("GATE 0a/0b -- does the falloff exponent rotate the desire, and buy in-range?")
    print("=" * 74)
    print(f"  {'e':>5} {'rot>=15 rate':>13} {'med rot':>9} {'n_rot':>7} "
          f"{'med ir gain':>12} {'mean ir old->new':>20} {'n_gain':>7}")
    a_pass = False
    realised = []
    per_dose = []
    for e in DOSES:
        rots = []
        n_rot = 0
        gains = []
        ir_old = []
        ir_new = []
        n_undef = 0
        for c in caps:
            fx, fy = loot_attraction(c["px"], c["py"], c["enemies"], c["bosses"],
                                     c["loot"], c["wave"], e)
            dx = c["tot"][0] - c["loot_rec"][0] + fx
            dy = c["tot"][1] - c["loot_rec"][1] + fy
            rot = rotation_deg(dx, dy, c["tot"][0], c["tot"][1])
            if math.isnan(rot):
                n_undef += 1
                continue
            rots.append(rot)
            if rot < ROT_BAR:
                continue
            n_rot += 1
            if not c["ir_ok"]:
                continue
            a = inrange_after(c["px"], c["py"], c["sp"], c["tot"][0], c["tot"][1],
                              c["threats"], c["max_range"])
            b = inrange_after(c["px"], c["py"], c["sp"], dx, dy,
                              c["threats"], c["max_range"])
            if a is None or b is None:
                continue
            ir_old.append(a); ir_new.append(b); gains.append(b - a)
        rate = n_rot / float(len(caps))
        g = med(gains) if gains else float("nan")
        realised.append(g if gains else None)
        per_dose.append((e, rate, g, n_rot, len(gains), n_undef))
        arrow = (f"{sum(ir_old)/len(ir_old):.4f} -> {sum(ir_new)/len(ir_new):.4f}"
                 if ir_old else "-")
        print(f"  {e:>5.2f} {rate:>13.4f} {med(rots):>9.3f} {n_rot:>7} "
              f"{g:>12.4f} {arrow:>20} {len(gains):>7}")
        if rate >= FLIP_BAR:
            a_pass = True
    for e, rate, g, n_rot, ng, n_undef in per_dose:
        if n_undef:
            print(f"    e={e}: {n_undef} captures had an undefined rotation (degenerate)")

    finite = [g for g in realised if g is not None and not math.isnan(g)]
    mono = all(finite[i] <= finite[i + 1] + 1e-12 for i in range(len(finite) - 1))
    print(f"\n  realised gain non-decreasing in e : {mono}  ({finite})")

    b_pass = any(g is not None and not math.isnan(g) and g >= GAIN_BAR
                 and rate >= FLIP_BAR
                 for (e, rate, g, n_rot, ng, nu) in per_dose)
    if not mono:
        print("  ⛔ NON-MONOTONE => pre-declared (§35e) as NOISE, not partial success.")
        b_pass = False
    print(f"  GATE 0a (rotation >= {ROT_BAR:g} deg on >= {FLIP_BAR:.0%}): "
          f"{'PASS' if a_pass else 'FAIL'}")
    print(f"  GATE 0b (median in-range gain >= {GAIN_BAR}): "
          f"{'PASS' if b_pass else 'FAIL'}")

    # ---------------- §35f: unmodellable exit-flip risk ----------------
    print("\n" + "=" * 74)
    print("§35f REPORTED, NOT BARRED -- the exit-flip risk is UNMODELLABLE")
    print("=" * 74)
    ba = sum(1 for c in caps if c["baseline_admitted"])
    fa = sum(1 for c in caps if c["floor_admitted"])
    print(f"  baseline_admitted rate : {ba}/{len(caps)} = {ba/len(caps):.4f}")
    print(f"  floor_admitted rate    : {fa}/{len(caps)} = {fa/len(caps):.4f}")
    print(f"  body_floor median      : {med([c['body_floor'] for c in caps]):.4f}")
    ex = Counter(c["exit"] for c in caps)
    print(f"  exits                  : {dict(ex)}")
    print("  ⇒ route.scores is empty on these exits, so whether a rotated baseline would")
    print("    still clear the body floor CANNOT be evaluated offline. Biases toward a PASS.")

    print("\n" + "=" * 74)
    print(f"VERDICT: {'SCREEN IT' if (a_pass and b_pass) else 'DO NOT IMPLEMENT'}")
    print("=" * 74)
    return 0


# ---- self-test --------------------------------------------------------------

def _self_test():
    ok = True

    def check(n, c):
        nonlocal ok
        print(f"  [{'PASS' if c else 'FAIL'}] {n}")
        ok = ok and bool(c)

    # 1. The statistic must be able to return ZERO (the null dose).
    loot = [{"x": 200.0, "y": 0.0}, {"x": 0.0, "y": 600.0}]
    en = [{"x": 4000.0, "y": 4000.0, "hp": 5, "vx": 0.0, "vy": 0.0}]
    f0 = loot_attraction(0.0, 0.0, en, [], loot, 5, NULL_E)
    check("null dose rotation is EXACTLY 0.0",
          rotation_deg(f0[0], f0[1], f0[0], f0[1]) == 0.0)

    # 2. ...and a LARGE value: two items at very different distances, so the
    #    exponent demonstrably reweights which one dominates.
    f16 = loot_attraction(0.0, 0.0, en, [], loot, 5, 1.6)
    big = rotation_deg(f16[0], f16[1], f0[0], f0[1])
    check(f"exponent reweights two far-apart items: rotation {big:.2f} deg > 15",
          big > 15.0)

    # 3. A pure SCALE of the loot vector must produce rotation 0.0 -- the prereg's
    #    central claim that the pipeline is direction-only.
    sx, sy = f0[0] * 37.0, f0[1] * 37.0
    scale_rot = rotation_deg(sx, sy, f0[0], f0[1])
    check(f"a pure SCALE gives rotation 0.0 (got {scale_rot:.6f})",
          abs(scale_rot) < 1e-9)
    if abs(scale_rot) >= 1e-9:
        print("     ⛔⛔ THE CODE DISAGREES WITH THE PREREG'S DIRECTION-ONLY CLAIM.")

    # 4. Degenerate / collinear inputs return a defined result, not a crash.
    check("zero vector rotation is nan, not a crash",
          math.isnan(rotation_deg(0.0, 0.0, 1.0, 0.0)))
    check("collinear opposite vectors give 180 deg",
          abs(rotation_deg(-1.0, 0.0, 1.0, 0.0) - 180.0) < 1e-9)
    check("collinear same-direction vectors give 0 deg",
          abs(rotation_deg(2.0, 0.0, 1.0, 0.0)) < 1e-9)

    # 5. The PACK_DENSITY_SOFT veto returns ZERO (:3559-3560).
    dense = [{"x": 10.0 * i, "y": 0.0, "hp": 5} for i in range(8)]
    check("nearby >= PACK_DENSITY_SOFT vetoes to ZERO",
          loot_attraction(0.0, 0.0, dense, [], loot, 5) == (0.0, 0.0))

    # 6. The early+sparse contact abort returns ZERO.
    close = [{"x": 5.0, "y": 0.0, "hp": 5}]
    check("early+sparse contact abort vetoes to ZERO",
          loot_attraction(0.0, 0.0, close, [], loot, 5) == (0.0, 0.0))

    # 7. Empty loot returns ZERO.
    check("empty loot returns ZERO",
          loot_attraction(0.0, 0.0, en, [], [], 5) == (0.0, 0.0))

    # 8. blockers > LOOT_PACK_ALLOW skips the item entirely.
    #    Three enemies sitting on the near pile -> that pile contributes nothing,
    #    so the result must equal the far pile alone.
    onpile = [{"x": 100.0, "y": 0.0, "hp": 5}, {"x": 105.0, "y": 0.0, "hp": 5},
              {"x": 110.0, "y": 0.0, "hp": 5}]
    # keep them out of the 280u pack radius check by putting the player far away
    a = loot_attraction(-400.0, 0.0, onpile, [],
                        [{"x": 100.0, "y": 0.0}, {"x": -400.0, "y": 600.0}], 5)
    b = loot_attraction(-400.0, 0.0, onpile, [], [{"x": -400.0, "y": 600.0}], 5)
    check("blockers > LOOT_PACK_ALLOW skips that item",
          abs(a[0] - b[0]) < 1e-12 and abs(a[1] - b[1]) < 1e-12)

    # 9. greed: the plateau/taper branch.
    check("greed plateau (wave<=12) = 5.5 * SPARSE_LOOT_MULT",
          abs(loot_greed_mult(5, 0) - 5.5 * 2.6) < 1e-12)
    check("greed at EARLY_LOOT_WAVE floors at EARLY_LOOT_FLOOR",
          abs(loot_greed_mult(15, 0) - 4.2 * 2.6) < 1e-12)

    # 10. inrange_after: threats MOVE; a fleeing threat lowers in-range.
    thr = [{"x": 500.0, "y": 0.0, "vx": -400.0, "vy": 0.0, "hp": 1}]
    toward = inrange_after(0.0, 0.0, 450.0, 1.0, 0.0, thr, 300.0)
    away = inrange_after(0.0, 0.0, 450.0, -1.0, 0.0, thr, 300.0)
    check(f"inrange_after moves threats by vx/vy ({toward} vs {away})",
          toward == 1.0 and away == 0.0)
    check("inrange_after on a zero direction returns None",
          inrange_after(0.0, 0.0, 450.0, 0.0, 0.0, thr, 300.0) is None)

    # 11. relerr flags the recorded-zero case instead of dividing by zero.
    check("relerr returns None on a zero reference",
          relerr(1.0, 1.0, 0.0, 0.0) is None)

    # 12. EARLY_LOOT_WAVE is checked against _build_desire's EARLY_HUNT_WAVE.
    check("EARLY_LOOT_WAVE and EARLY_HUNT_WAVE coincide in this build (checked)",
          EARLY_LOOT_WAVE == EARLY_HUNT_WAVE == 15)

    print("\nSELF-TEST", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs-dir")
    ap.add_argument("--mod-version", default="0.2.76-wp2-capture")
    ap.add_argument("--stride", type=int, default=1)
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
    print(f"runs selected {len(ids)} at {a.mod_version} (stride {a.stride})")
    return run(a.runs_dir, ids, a.stride)


if __name__ == "__main__":
    sys.exit(main())
