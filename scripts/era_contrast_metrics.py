"""Offline era contrast: STRONG (0.1.60-0.1.72) vs CURRENT (f2 pure-teacher 0.1.125).

Computes ONLY on combat_tick / player_damage / summary fields positively
established as present-and-same-shape in both eras. Prints raw series.
"""
import json, math, os, bisect
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNS = os.path.join(os.environ["APPDATA"], "Brotato", "brotato_agent", "runs")
IDX = json.load(open(os.path.join(ROOT, ".tmp", "era_index.json"), encoding="utf-8"))
vt = lambda v: tuple(int(x) for x in v.split(".")) if v else None


def pct(xs, p):
    if not xs:
        return float("nan")
    s = sorted(xs)
    k = (len(s) - 1) * p / 100.0
    lo = int(math.floor(k)); hi = int(math.ceil(k))
    return s[lo] if lo == hi else s[lo] + (s[hi] - s[lo]) * (k - lo)


def mean(xs):
    return sum(xs) / len(xs) if xs else float("nan")


def load(rid):
    ticks = []       # (ts_ms, wave, mx, my, hp, loot, cons, enemies, proj)
    dmg = []         # (ts_ms, amount, hp)
    with open(os.path.join(RUNS, rid, "events.jsonl"), encoding="utf-8", errors="replace") as f:
        for line in f:
            try:
                e = json.loads(line)
            except Exception:
                continue
            ev = e.get("event")
            if ev == "combat_tick":
                p = e["payload"]; d = p.get("debug", {}) or {}
                mv = p.get("move", {}) or {}
                ticks.append((e["ts_ms"], int(p.get("wave", 0)), float(mv.get("x", 0.0)),
                              float(mv.get("y", 0.0)), p.get("hp"), p.get("loot"),
                              p.get("consumables"), d.get("enemies"), d.get("projectiles")))
            elif ev == "player_damage":
                dmg.append((e["ts_ms"], e["payload"].get("amount"), e["payload"].get("hp")))
    return ticks, dmg


def run_metrics(rid):
    ticks, dmg = load(rid)
    if not ticks:
        return None
    tts = [t[0] for t in ticks]
    m = {"run_id": rid, "n_ticks": len(ticks), "span_ms": tts[-1] - tts[0],
         "waves_seen": sorted(set(t[1] for t in ticks))}
    per = defaultdict(lambda: {"mag": [], "turn": [], "n": 0, "stat": 0, "dmg_n": 0,
                               "dmg_amt": [], "enemies": [], "ms": 0})
    prev = None
    for i, t in enumerate(ticks):
        w = t[1]; mx, my = t[2], t[3]
        mag = math.hypot(mx, my)
        b = per[w]; b["n"] += 1; b["mag"].append(mag)
        if mag < 0.01:
            b["stat"] += 1
        if t[7] is not None:
            b["enemies"].append(t[7])
        if prev is not None and prev[1] == w:
            pm = math.hypot(prev[2], prev[3])
            if pm > 0.01 and mag > 0.01:
                c = max(-1.0, min(1.0, (prev[2] * mx + prev[3] * my) / (pm * mag)))
                b["turn"].append(math.degrees(math.acos(c)))
            b["ms"] += t[0] - prev[0]
        prev = t
    # damage -> wave via tick timeline
    for ts, amt, hp in dmg:
        j = min(bisect.bisect_left(tts, ts), len(ticks) - 1)
        w = ticks[j][1]
        per[w]["dmg_n"] += 1
        per[w]["dmg_amt"].append(amt or 0)
    m["per_wave"] = {w: {
        "ticks": b["n"], "wave_ms": b["ms"],
        "mag_mean": mean(b["mag"]), "mag_p50": pct(b["mag"], 50),
        "stationary_frac": b["stat"] / b["n"],
        "turn_mean": mean(b["turn"]), "turn_p50": pct(b["turn"], 50),
        "reversal_frac": (sum(1 for a in b["turn"] if a > 90) / len(b["turn"])) if b["turn"] else float("nan"),
        "dmg_events": b["dmg_n"], "dmg_total": sum(b["dmg_amt"]),
        "enemies_mean": mean(b["enemies"]) if b["enemies"] else float("nan"),
    } for w, b in sorted(per.items())}
    m["all_mag"] = [math.hypot(t[2], t[3]) for t in ticks]
    m["dmg_events"] = len(dmg)
    m["dmg_total"] = sum((d[1] or 0) for d in dmg)
    return m


def cohort(ids, label):
    out = []
    for rid in ids:
        try:
            r = run_metrics(rid)
        except Exception as e:
            print(f"  !! {rid}: {e}")
            continue
        if r:
            out.append(r)
    print(f"\n### COHORT {label}: n_runs_with_ticks={len(out)} / requested {len(ids)}")
    return out


def show(co, label, meta):
    print("\n" + "=" * 78)
    print(f"COHORT {label}  n={len(co)}")
    print("-- RAW PER-RUN SERIES --")
    print(f"{'run_id':26s} {'ver':8s} {'res':8s} {'lw':>3s} {'ticks':>6s} {'span_s':>7s} "
          f"{'mag_mu':>7s} {'stat%':>6s} {'turn_mu':>8s} {'rev%':>6s} {'dmgN':>5s} {'dmgTot':>7s} {'lvl':>4s} {'buy':>4s} {'rrl':>4s}")
    for r in co:
        mm = meta[r["run_id"]]
        allmag = r["all_mag"]
        turns = [v for w, b in r["per_wave"].items() for v in [b["turn_mean"]] if v == v]
        pw = r["per_wave"]
        tot_t = sum(b["ticks"] for b in pw.values())
        stat = sum(b["stationary_frac"] * b["ticks"] for b in pw.values()) / tot_t
        # weighted reversal
        wt = [(b, b["ticks"]) for b in pw.values() if b["reversal_frac"] == b["reversal_frac"]]
        rev = sum(b["reversal_frac"] * n for b, n in wt) / sum(n for _, n in wt) if wt else float("nan")
        tmu = sum(b["turn_mean"] * n for b, n in wt if b["turn_mean"] == b["turn_mean"]) / sum(n for _, n in wt) if wt else float("nan")
        print(f"{r['run_id']:26s} {str(mm['ver']):8s} {str(mm['result'])[:8]:8s} {mm['last_wave']:3d} "
              f"{r['n_ticks']:6d} {r['span_ms']/1000:7.1f} {mean(allmag):7.4f} {stat*100:6.2f} "
              f"{tmu:8.2f} {rev*100:6.2f} {r['dmg_events']:5d} {r['dmg_total']:7d} "
              f"{mm['n_levelups']:4d} {mm['n_purchases']:4d} {str(mm['rerolls']):>4s}")


def agg_per_wave(co, key, weight="ticks"):
    """pooled mean of per-wave metric across runs, tick-weighted"""
    num = defaultdict(float); den = defaultdict(float)
    for r in co:
        for w, b in r["per_wave"].items():
            v = b[key]
            if v != v:
                continue
            wt = b[weight]
            num[w] += v * wt; den[w] += wt
    return {w: num[w] / den[w] for w in sorted(num) if den[w]}


def agg_sum(co, key):
    tot = defaultdict(float); runs = defaultdict(int)
    for r in co:
        for w, b in r["per_wave"].items():
            tot[w] += b[key]; runs[w] += 1
    return {w: (tot[w], runs[w], tot[w] / runs[w]) for w in sorted(tot)}


old_meta = {r["run_id"]: r for r in IDX if r.get("ver") and (0, 1, 60) <= vt(r["ver"]) <= (0, 1, 72)}
cur_ids = [l.strip() for l in open(os.path.join(ROOT, ".tmp", "f2_teacher_run_ids.txt")) if l.strip()]
cur_meta = {r["run_id"]: r for r in IDX if r["run_id"] in set(cur_ids)}
meta = dict(old_meta); meta.update(cur_meta)

O = cohort(sorted(old_meta), "STRONG 0.1.60-0.1.72")
C = cohort(cur_ids, "CURRENT 0.1.125 pure-teacher")
show(O, "STRONG 0.1.60-0.1.72", meta)
show(C, "CURRENT 0.1.125 pure-teacher", meta)

print("\n" + "=" * 78)
print("PER-WAVE POOLED COMPARISON (tick-weighted where applicable)")
for key, fmt in [("mag_mean", "%8.4f"), ("stationary_frac", "%8.4f"), ("turn_mean", "%8.2f"),
                 ("reversal_frac", "%8.4f"), ("enemies_mean", "%8.3f")]:
    a = agg_per_wave(O, key); b = agg_per_wave(C, key)
    print(f"\n-- {key} --")
    print(f"{'wave':>4s} {'STRONG':>9s} {'CURRENT':>9s} {'delta':>9s}")
    for w in sorted(set(a) | set(b)):
        va = a.get(w, float("nan")); vb = b.get(w, float("nan"))
        print(f"{w:4d} " + (fmt % va) + " " + (fmt % vb) + " " + (fmt % (vb - va)))

print("\n-- damage events per run-wave (total, n_runs_reaching, per-run mean) --")
a = agg_sum(O, "dmg_events"); b = agg_sum(C, "dmg_events")
ad = agg_sum(O, "dmg_total"); bd = agg_sum(C, "dmg_total")
print(f"{'wave':>4s} | {'S_tot':>6s} {'S_runs':>6s} {'S_ev/run':>9s} {'S_dmg/run':>10s} | {'C_tot':>6s} {'C_runs':>6s} {'C_ev/run':>9s} {'C_dmg/run':>10s}")
for w in sorted(set(a) | set(b)):
    x = a.get(w, (0, 0, 0)); y = b.get(w, (0, 0, 0)); xd = ad.get(w, (0, 0, 0)); yd = bd.get(w, (0, 0, 0))
    print(f"{w:4d} | {x[0]:6.0f} {x[1]:6d} {x[2]:9.3f} {xd[2]:10.3f} | {y[0]:6.0f} {y[1]:6d} {y[2]:9.3f} {yd[2]:10.3f}")

print("\n-- wave duration (ms of tick coverage per wave, per-run mean) --")
a = agg_sum(O, "wave_ms"); b = agg_sum(C, "wave_ms")
print(f"{'wave':>4s} {'STRONG_ms':>10s} {'CURRENT_ms':>11s}")
for w in sorted(set(a) | set(b)):
    print(f"{w:4d} {a.get(w,(0,0,0))[2]:10.0f} {b.get(w,(0,0,0))[2]:11.0f}")

print("\n" + "=" * 78)
print("MOVEMENT MAGNITUDE DISTRIBUTION (all ticks pooled)")
for lbl, co in (("STRONG", O), ("CURRENT", C)):
    allm = [v for r in co for v in r["all_mag"]]
    h = Counter()
    for v in allm:
        h[round(min(v, 1.0), 1)] += 1
    print(f"{lbl}: N={len(allm)} mean={mean(allm):.4f} p10={pct(allm,10):.4f} p50={pct(allm,50):.4f} p90={pct(allm,90):.4f} max={max(allm):.4f}")
    print("   hist(|move| rounded to 0.1):", dict(sorted(h.items())))

print("\n" + "=" * 78)
print("OUTCOMES / ECONOMY (summary.json fields, present in both eras)")
for lbl, ids in (("STRONG", sorted(old_meta)), ("CURRENT", cur_ids)):
    ms = [meta[i] for i in ids]
    res = Counter(m["result"] for m in ms)
    dl = Counter(m["last_wave"] for m in ms if m["result"] == "defeat")
    vl = Counter(m["last_wave"] for m in ms if m["result"] == "victory")
    print(f"\n{lbl}: n={len(ms)} result={dict(res)} victory_rate={res['victory']/len(ms):.4f}")
    print(f"   defeat last_wave dist: {dict(sorted(dl.items()))}")
    print(f"   victory last_wave dist: {dict(sorted(vl.items()))}")
    for k in ["n_levelups", "n_purchases", "rerolls", "locks", "materials_spent", "damage_taken", "duration_ms", "recoveries"]:
        xs = [m[k] for m in ms if m.get(k) is not None]
        if xs:
            print(f"   {k:16s} mean={mean(xs):10.2f} p10={pct(xs,10):9.1f} p50={pct(xs,50):9.1f} p90={pct(xs,90):9.1f}")
    print(f"   RAW {['%s:%s/%s/%s' % (m['ver'], m['n_levelups'], m['n_purchases'], m['rerolls']) for m in ms]}")
