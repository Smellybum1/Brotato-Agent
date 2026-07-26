"""Offline: per-run late-wave dither + damage series, raw, for rank tests."""
import json, math, os, bisect
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNS = os.path.join(os.environ["APPDATA"], "Brotato", "brotato_agent", "runs")
IDX = json.load(open(os.path.join(ROOT, ".tmp", "era_index.json"), encoding="utf-8"))
vt = lambda v: tuple(int(x) for x in v.split(".")) if v else None


def mean(x):
    return sum(x) / len(x) if x else float("nan")


def med(x):
    s = sorted(x); n = len(s)
    return float("nan") if not n else (s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2)


def per_run(rid):
    ticks = []; dmg = []
    for line in open(os.path.join(RUNS, rid, "events.jsonl"), encoding="utf-8", errors="replace"):
        try:
            e = json.loads(line)
        except Exception:
            continue
        if e.get("event") == "combat_tick":
            p = e["payload"]; mv = p.get("move", {}) or {}
            ticks.append((e["ts_ms"], int(p.get("wave", 0)), float(mv.get("x", 0)), float(mv.get("y", 0))))
        elif e.get("event") == "player_damage":
            dmg.append((e["ts_ms"], e["payload"].get("amount") or 0))
    tts = [t[0] for t in ticks]
    rev = defaultdict(list); dm = defaultdict(int); dn = defaultdict(int)
    prev = None
    for t in ticks:
        if prev is not None and prev[1] == t[1]:
            a = math.hypot(prev[2], prev[3]); b = math.hypot(t[2], t[3])
            if a > .01 and b > .01:
                c = max(-1., min(1., (prev[2] * t[2] + prev[3] * t[3]) / (a * b)))
                rev[t[1]].append(math.degrees(math.acos(c)))
        prev = t
    for ts, amt in dmg:
        j = min(bisect.bisect_left(tts, ts), len(ticks) - 1)
        dm[ticks[j][1]] += amt; dn[ticks[j][1]] += 1
    return {w: {"rev": sum(1 for x in v if x > 90) / len(v), "turn": mean(v), "n": len(v),
                "dmg": dm.get(w, 0), "dn": dn.get(w, 0)} for w, v in rev.items()}


old = sorted(r["run_id"] for r in IDX if r.get("ver") and (0, 1, 60) <= vt(r["ver"]) <= (0, 1, 72))
cur = [l.strip() for l in open(os.path.join(ROOT, ".tmp", "f2_teacher_run_ids.txt")) if l.strip()]
data = {"STRONG": {r: per_run(r) for r in old}, "CURRENT": {r: per_run(r) for r in cur}}

for W in (16, 17, 18, 19, 20):
    print("=" * 70)
    print(f"WAVE {W}")
    for lbl in ("STRONG", "CURRENT"):
        rv = [d[W]["rev"] for d in data[lbl].values() if W in d]
        tn = [d[W]["turn"] for d in data[lbl].values() if W in d]
        dg = [d[W]["dmg"] for d in data[lbl].values() if W in d]
        print(f"  {lbl:8s} n_runs={len(rv):3d} reversal_frac mean={mean(rv):.4f} med={med(rv):.4f} "
              f"min={min(rv):.4f} max={max(rv):.4f} | turn_deg mean={mean(tn):.2f} med={med(tn):.2f} "
              f"| dmg/run mean={mean(dg):.2f} med={med(dg):.1f}")
        print(f"     RAW rev: {[round(x,4) for x in sorted(rv)]}")
        print(f"     RAW dmg: {sorted(dg)}")
    a = sorted(d[W]["rev"] for d in data["STRONG"].values() if W in d)
    b = [d[W]["rev"] for d in data["CURRENT"].values() if W in d]
    gt = sum(1 for y in b for x in a if y > x); ties = sum(1 for y in b for x in a if y == x)
    print(f"  P(CURRENT reversal > STRONG reversal) = {(gt + .5*ties)/(len(a)*len(b)):.4f}  (n={len(a)}x{len(b)})")
