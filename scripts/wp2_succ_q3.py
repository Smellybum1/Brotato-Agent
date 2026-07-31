"""Q3: enemy TYPE at the terminal damaging contacts, with a causal-lag sweep."""
import argparse, json, os, sys, io
from collections import Counter, defaultdict

INF = 1e17


def pctl(xs, p):
    if not xs:
        return None
    s = sorted(xs); i = min(len(s) - 1, max(0, int(round((p / 100.0) * (len(s) - 1)))))
    return s[i]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ext-dir", required=True)
    ap.add_argument("--index", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--character", default=None)
    ap.add_argument("--danger", type=int, default=None)
    ap.add_argument("--n-terminal", type=int, default=3)
    ap.add_argument("--lag-range", type=int, default=5)
    a = ap.parse_args()
    idx = {r["run_id"]: r for r in json.load(open(a.index, encoding="utf-8"))}
    lags = list(range(-a.lag_range, a.lag_range + 1))
    sweep = {L: [] for L in lags}        # min surface distances
    sweep_cov = Counter()                # contacts with a usable ctx at that lag
    sweep_notgt = Counter()              # ctx present but zero enemies
    per_run = {}
    used = Counter(); n_contacts = 0
    for fn in sorted(os.listdir(a.ext_dir)):
        rid = fn[:-5]
        m = idx.get(rid, {})
        if a.character and m.get("character") != a.character:
            continue
        if a.danger is not None and m.get("danger") != a.danger:
            continue
        r = json.load(open(os.path.join(a.ext_dir, fn), encoding="utf-8"))
        caps = r["caps"]; ctx = r["ctx"]
        if not caps:
            continue
        used[m.get("character")] += 1
        drops = []
        for i in range(1, len(caps)):
            if caps[i][1] == caps[i - 1][1] and caps[i][2] < caps[i - 1][2] \
               and caps[i][0] - caps[i - 1][0] <= 2000:
                drops.append(i)
        term = drops[-a.n_terminal:]
        per_run[rid] = {"n_drops": len(drops), "terminal_idx": term,
                        "last_wave": caps[-1][1], "result": (r.get("end") or {}).get("result"),
                        "types": {}}
        for di in term:
            n_contacts += 1
            for L in lags:
                j = di + L
                e = ctx.get(str(j))
                if e is None:
                    continue
                sweep_cov[L] += 1
                if not e:
                    sweep_notgt[L] += 1
                    continue
                sweep[L].append(e[0]["sd"])
    out = {"n_runs": sum(used.values()), "chars": dict(used), "n_terminal_contacts": n_contacts,
           "sweep": {}}
    for L in lags:
        xs = sweep[L]
        out["sweep"][L] = {"ctx_present": sweep_cov[L], "no_enemy": sweep_notgt[L],
                           "n": len(xs), "median_surface_d": pctl(xs, 50),
                           "p25": pctl(xs, 25), "p75": pctl(xs, 75)}
    best = min((L for L in lags if sweep[L]),
               key=lambda L: out["sweep"][L]["median_surface_d"])
    out["chosen_lag"] = best

    # type composition at the chosen lag
    combos = Counter(); typec = Counter(); runs_typed = 0; per_contact_typed = 0
    detail = {}
    for rid, d in per_run.items():
        r = json.load(open(os.path.join(a.ext_dir, rid + ".json"), encoding="utf-8"))
        ctx = r["ctx"]
        ts = []
        for di in d["terminal_idx"]:
            e = ctx.get(str(di + best))
            if e:
                ts.append(e[0]["t"]); typec[e[0]["t"]] += 1; per_contact_typed += 1
            else:
                ts.append(None)
        detail[rid] = ts
        known = [t for t in ts if t]
        if len(known) == a.n_terminal:
            runs_typed += 1
            combos[len(set(known))] += 1
    out["distinct_type_counts_over_last_%d" % a.n_terminal] = dict(combos)
    out["runs_with_all_%d_typed" % a.n_terminal] = runs_typed
    out["type_frequency"] = typec.most_common()
    out["contacts_typed"] = per_contact_typed
    out["per_run"] = detail
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    print("runs", out["n_runs"], dict(used), "terminal contacts", n_contacts)
    print("%-5s %10s %9s %6s %10s %8s %8s" % ("lag", "ctxPresent", "noEnemy", "n", "medSurfD", "p25", "p75"))
    for L in lags:
        s = out["sweep"][L]
        g = lambda k: "-" if s[k] is None else "%.2f" % s[k]
        print("%-5d %10d %9d %6d %10s %8s %8s" % (L, s["ctx_present"], s["no_enemy"], s["n"],
                                                  g("median_surface_d"), g("p25"), g("p75")))
    print("chosen lag", best)
    print("distinct types over last %d contacts:" % a.n_terminal, dict(combos),
          "runs fully typed", runs_typed)
    print("type frequency", typec.most_common(12))


if __name__ == "__main__":
    main()
