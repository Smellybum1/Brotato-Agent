"""Offline: dump non-tick event key structure + tick cadence per era."""
import json, os
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNS = os.path.join(os.environ["APPDATA"], "Brotato", "brotato_agent", "runs")
IDX = json.load(open(os.path.join(ROOT, ".tmp", "era_index.json"), encoding="utf-8"))
vt = lambda v: tuple(int(x) for x in v.split(".")) if v else None


def paths(o, pre=""):
    out = []
    if isinstance(o, dict):
        for k, v in o.items():
            out += paths(v, (pre + "." + k) if pre else k)
    elif isinstance(o, list):
        out.append((pre + "[]", "list<%s>" % (type(o[0]).__name__ if o else "empty")))
    else:
        out.append((pre, type(o).__name__))
    return out


TARGET = ["player_damage", "run_start", "run_end", "level_up_offer", "level_up_decision",
          "purchase_decision", "recovery_attempt", "crate_decision"]


def scan(ids, label, maxr=8):
    byev = defaultdict(Counter)
    ex = {}
    dts = Counter()
    prev = {}
    for rid in ids[:maxr]:
        p = os.path.join(RUNS, rid, "events.jsonl")
        if not os.path.isfile(p):
            continue
        last = None
        for line in open(p, encoding="utf-8", errors="replace"):
            try:
                e = json.loads(line)
            except Exception:
                continue
            t = e.get("event")
            if t == "combat_tick":
                if last is not None:
                    dts[e["ts_ms"] - last] += 1
                last = e["ts_ms"]
            if t in TARGET:
                for pa, ty in paths(e):
                    byev[t][(pa, ty)] += 1
                    if (t, pa) not in ex:
                        ex[(t, pa)] = json.dumps(e)[:400]
    print("=" * 70)
    print("COHORT", label)
    print("combat_tick dt_ms histogram (top 12):", dts.most_common(12))
    for t in TARGET:
        if not byev[t]:
            print(f"-- {t}: ABSENT")
            continue
        print(f"-- {t} --")
        for (pa, ty), c in sorted(byev[t].items()):
            print(f"     {pa:50s} {ty:8s} n={c}")
        k = sorted(byev[t])[0]
        print("     EXAMPLE:", ex[(t, k[0])])
    return byev


old = [r["run_id"] for r in IDX if r.get("ver") and (0, 1, 60) <= vt(r["ver"]) <= (0, 1, 72)]
cur = [l.strip() for l in open(os.path.join(ROOT, ".tmp", "f2_teacher_run_ids.txt")) if l.strip()]
a = scan(old, "STRONG 0.1.60-0.1.72")
b = scan(cur, "CURRENT f2 teacher")
print("=" * 70)
for t in TARGET:
    sa = set(p for p, _ in a[t]); sb = set(p for p, _ in b[t])
    print(f"{t}: both={sorted(sa&sb)} | oldonly={sorted(sa-sb)} | newonly={sorted(sb-sa)}")
