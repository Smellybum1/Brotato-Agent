"""Offline: dump combat_tick (and event-type) key structure per era. No writes outside .tmp."""
import json, os, sys, gzip
from collections import Counter, defaultdict

RUNS = os.path.join(os.environ["APPDATA"], "Brotato", "brotato_agent", "runs")
IDX = json.load(open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".tmp", "era_index.json"), encoding="utf-8"))


def vtup(v):
    return tuple(int(x) for x in v.split(".")) if v else None


def open_events(d):
    p = os.path.join(d, "events.jsonl")
    if os.path.isfile(p):
        return open(p, encoding="utf-8", errors="replace")
    p2 = p + ".gz"
    if os.path.isfile(p2):
        return gzip.open(p2, "rt", encoding="utf-8", errors="replace")
    return None


def paths(o, pre=""):
    out = []
    if isinstance(o, dict):
        for k, v in o.items():
            out += paths(v, pre + "." + k if pre else k)
    elif isinstance(o, list):
        out.append((pre + "[]", "list<%s>" % (type(o[0]).__name__ if o else "empty")))
    else:
        out.append((pre, type(o).__name__))
    return out


def scan(run_ids, label, max_runs=8):
    tick_paths = Counter()
    tick_examples = {}
    evtypes = Counter()
    nrun = 0
    tickcount = []
    for rid in run_ids[:max_runs]:
        f = open_events(os.path.join(RUNS, rid))
        if f is None:
            continue
        nrun += 1
        n = 0
        with f:
            for line in f:
                try:
                    e = json.loads(line)
                except Exception:
                    continue
                t = e.get("type") or e.get("event") or e.get("event_type")
                evtypes[t] += 1
                if t == "combat_tick":
                    n += 1
                    for p, ty in paths(e):
                        tick_paths[(p, ty)] += 1
                        if p not in tick_examples:
                            cur = e
                            try:
                                for part in p.replace("[]", "").split("."):
                                    cur = cur[part]
                                tick_examples[p] = cur
                            except Exception:
                                pass
        tickcount.append(n)
    print("=" * 70)
    print(f"COHORT {label}: runs scanned={nrun}, combat_tick per run={tickcount}")
    print("-- event types --")
    for k, v in evtypes.most_common():
        print(f"   {k}: {v}")
    print("-- combat_tick paths --")
    for (p, ty), c in sorted(tick_paths.items()):
        ex = tick_examples.get(p)
        exs = repr(ex)[:70]
        print(f"   {p:45s} {ty:8s} n={c:6d} eg={exs}")
    return set(p for (p, _) in tick_paths)


old = [r["run_id"] for r in IDX if r.get("ver") and (0, 1, 60) <= vtup(r["ver"]) <= (0, 1, 72)]
cur = [l.strip() for l in open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".tmp", "f2_teacher_run_ids.txt")) if l.strip()]
print("old cohort n=", len(old), " current cohort n=", len(cur))
so = scan(old, "STRONG 0.1.60-0.1.72")
sc = scan(cur, "CURRENT f2 teacher")
print("=" * 70)
print("BOTH:", sorted(so & sc))
print("OLD ONLY:", sorted(so - sc))
print("NEW ONLY:", sorted(sc - so))
