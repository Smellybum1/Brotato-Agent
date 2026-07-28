"""Stage A step 5: rank-biserial comparison with a calibrated null band."""
from __future__ import annotations

import json
import math
import os
import re
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(ROOT, ".tmp", "stageA", "wave17_metrics.jsonl")
CROWD_LABELS = ["0-4", "5-9", "10-14", "15-19", "20+"]


def rank_biserial(a, b):
    """P(A > B) + 0.5 P(tie). a=died, b=survivor."""
    n1, n2 = len(a), len(b)
    if n1 == 0 or n2 == 0:
        return None, n1, n2, None
    gt = tie = 0
    for x in a:
        for y in b:
            if x > y:
                gt += 1
            elif x == y:
                tie += 1
    p = (gt + 0.5 * tie) / (n1 * n2)
    se = math.sqrt((n1 + n2 + 1) / (12.0 * n1 * n2))
    return p, n1, n2, se


def band(se):
    return 0.5 - 1.96 * se, 0.5 + 1.96 * se


def med(v):
    v = sorted(v)
    n = len(v)
    if n == 0:
        return None
    return v[n // 2] if n % 2 else 0.5 * (v[n // 2 - 1] + v[n // 2])


def main():
    rows = [json.loads(l) for l in open(P, encoding="utf-8")]
    print("rows=%d" % len(rows))
    empty = [r for r in rows if r["n_wave17_payloads"] == 0]
    print("rows with ZERO wave-17 captures: %d" % len(empty))
    ec = Counter((r["cls"], r["policy_version"]) for r in empty)
    for k, v in ec.most_common():
        print("   EMPTY %s %s x%d" % (k[0], k[1], v))

    usable = [r for r in rows if r["n_wave17_payloads"] > 0]
    print("\nUSABLE rows=%d  died=%d survivor=%d"
          % (len(usable), sum(1 for r in usable if r["cls"] == "died17"),
             sum(1 for r in usable if r["cls"] == "survivor")))
    print("usable version distribution:")
    for cls in ("died17", "survivor"):
        c = Counter(r["policy_version"] for r in usable if r["cls"] == cls)
        print("  %s: %s" % (cls, dict(sorted(c.items(), key=lambda x: -x[1]))))

    D = [r for r in usable if r["cls"] == "died17"]
    S = [r for r in usable if r["cls"] == "survivor"]

    W = "15-25"
    print("\n=== WINDOW [15,25) — primary ===")
    metrics = [
        ("uptime_engaged", lambda r: r["windows"][W]["uptime_engaged"]),
        ("coverage", lambda r: r["windows"][W]["coverage"]),
        ("mean_enemies_alive", lambda r: r["windows"][W]["mean_enemies_alive"]),
        ("max_enemies_alive", lambda r: r["windows"][W]["max_enemies_alive"]),
        ("mean_enemy_hp_pool", lambda r: r["windows"][W]["mean_enemy_hp_pool"]),
        ("mean_nearest_surface_dist", lambda r: r["windows"][W]["mean_nearest_surface_dist"]),
        ("mean_player_speed", lambda r: r["windows"][W]["mean_player_speed"]),
        ("entry_hp", lambda r: r["entry"].get("hp")),
        ("entry_max_hp", lambda r: r["entry"].get("max_hp")),
        ("entry_armor", lambda r: r["entry"].get("armor")),
        ("entry_dodge", lambda r: r["entry"].get("dodge")),
        ("entry_lifesteal", lambda r: r["entry"].get("lifesteal")),
        ("entry_hp_regeneration", lambda r: r["entry"].get("hp_regeneration")),
        ("entry_speed", lambda r: r["entry"].get("speed")),
        ("entry_nominal_dps", lambda r: r["entry"].get("nominal_dps")),
        ("entry_n_weapons", lambda r: r["entry"].get("n_weapons")),
    ]
    print("%-28s %5s %5s %10s %10s %8s %s" % ("metric", "nD", "nS", "medD", "medS", "P(D>S)", "null band"))
    for name, fn in metrics:
        a = [fn(r) for r in D]
        a = [x for x in a if x is not None]
        b = [fn(r) for r in S]
        b = [x for x in b if x is not None]
        p, n1, n2, se = rank_biserial(a, b)
        if p is None:
            print("%-28s DEGENERATE candidate sets nD=%d nS=%d" % (name, len(a), len(b)))
            continue
        lo, hi = band(se)
        sig = "*" if (p < lo or p > hi) else " "
        print("%-28s %5d %5d %10.4g %10.4g %8.3f%s [%.3f,%.3f]"
              % (name, n1, n2, med(a), med(b), p, sig, lo, hi))

    print("\n=== MATCHED BY CROWDING, window [15,25) ===")
    print("%-6s %5s %5s %9s %9s %8s %-15s %9s %9s %8s %s"
          % ("bin", "nD", "nS", "upD", "upS", "P(D>S)", "band", "covD", "covS", "P(D>S)", "band"))
    for lab in CROWD_LABELS:
        for key, tag in (("uptime_engaged", "up"), ("coverage", "cov")):
            pass
        a_u = [r["crowd_15_25"][lab]["uptime_engaged"] for r in D if r["crowd_15_25"][lab]["uptime_engaged"] is not None]
        b_u = [r["crowd_15_25"][lab]["uptime_engaged"] for r in S if r["crowd_15_25"][lab]["uptime_engaged"] is not None]
        a_c = [r["crowd_15_25"][lab]["coverage"] for r in D if r["crowd_15_25"][lab]["coverage"] is not None]
        b_c = [r["crowd_15_25"][lab]["coverage"] for r in S if r["crowd_15_25"][lab]["coverage"] is not None]
        pu, n1, n2, seu = rank_biserial(a_u, b_u)
        pc, m1, m2, sec = rank_biserial(a_c, b_c)
        if pu is None or pc is None:
            print("%-6s %5d %5d  DEGENERATE (candidate set too small)" % (lab, len(a_u), len(b_u)))
            continue
        lu, hu = band(seu)
        lc, hc = band(sec)
        print("%-6s %5d %5d %9.4f %9.4f %8.3f%s [%.2f,%.2f] %9.4f %9.4f %8.3f%s [%.2f,%.2f]"
              % (lab, n1, n2, med(a_u), med(b_u), pu, "*" if (pu < lu or pu > hu) else " ", lu, hu,
                 med(a_c), med(b_c), pc, "*" if (pc < lc or pc > hc) else " ", lc, hc))

    print("\n=== MATCHED BY CROWDING, window [0,10) — pre-divergence check ===")
    for lab in CROWD_LABELS:
        a_u = [r["crowd_0_10"][lab]["uptime_engaged"] for r in D if r["crowd_0_10"][lab]["uptime_engaged"] is not None]
        b_u = [r["crowd_0_10"][lab]["uptime_engaged"] for r in S if r["crowd_0_10"][lab]["uptime_engaged"] is not None]
        a_c = [r["crowd_0_10"][lab]["coverage"] for r in D if r["crowd_0_10"][lab]["coverage"] is not None]
        b_c = [r["crowd_0_10"][lab]["coverage"] for r in S if r["crowd_0_10"][lab]["coverage"] is not None]
        pu, n1, n2, seu = rank_biserial(a_u, b_u)
        pc, _, _, sec = rank_biserial(a_c, b_c)
        if pu is None or pc is None:
            print("%-6s nD=%d nS=%d DEGENERATE" % (lab, len(a_u), len(b_u)))
            continue
        lu, hu = band(seu)
        lc, hc = band(sec)
        print("%-6s nD=%2d nS=%2d up medD=%.4f medS=%.4f P=%.3f%s[%.2f,%.2f] | cov medD=%.4f medS=%.4f P=%.3f%s[%.2f,%.2f]"
              % (lab, n1, n2, med(a_u), med(b_u), pu, "*" if (pu < lu or pu > hu) else " ", lu, hu,
                 med(a_c), med(b_c), pc, "*" if (pc < lc or pc > hc) else " ", lc, hc))

    print("\n=== CROWD GAP BY WINDOW (mean_enemies_alive) ===")
    for W2 in ("0-10", "10-20", "15-25", "20-30", "30-40"):
        a = [r["windows"][W2]["mean_enemies_alive"] for r in D if r["windows"][W2]["mean_enemies_alive"] is not None]
        b = [r["windows"][W2]["mean_enemies_alive"] for r in S if r["windows"][W2]["mean_enemies_alive"] is not None]
        p, n1, n2, se = rank_biserial(a, b)
        lo, hi = band(se)
        print("%-6s nD=%2d nS=%2d medD=%.2f medS=%.2f P=%.3f%s band[%.3f,%.3f]"
              % (W2, n1, n2, med(a), med(b), p, "*" if (p < lo or p > hi) else " ", lo, hi))

    print("\n=== SECONDARY WINDOWS (uptime_engaged / coverage) ===")
    for W2 in ("0-10", "10-20", "15-25", "20-30", "30-40"):
        for key in ("uptime_engaged", "coverage"):
            a = [r["windows"][W2][key] for r in D if r["windows"][W2][key] is not None]
            b = [r["windows"][W2][key] for r in S if r["windows"][W2][key] is not None]
            p, n1, n2, se = rank_biserial(a, b)
            if p is None:
                print("%-6s %-16s DEGENERATE nD=%d nS=%d" % (W2, key, len(a), len(b)))
                continue
            lo, hi = band(se)
            print("%-6s %-16s nD=%2d nS=%2d medD=%.4f medS=%.4f P=%.3f%s band[%.3f,%.3f]"
                  % (W2, key, n1, n2, med(a), med(b), p, "*" if (p < lo or p > hi) else " ", lo, hi))


if __name__ == "__main__":
    main()
