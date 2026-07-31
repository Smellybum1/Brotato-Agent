"""Q1b: exit-time 'affordable item declined' rate + reasons + tier mix, by wave."""
import argparse, json, os, sys, io
from collections import defaultdict, Counter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wp2_succ_q1 import visits_for_run


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ext-dir", required=True)
    ap.add_argument("--index", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--character", default=None)
    ap.add_argument("--danger", type=int, default=None)
    a = ap.parse_args()
    idx = {r["run_id"]: r for r in json.load(open(a.index, encoding="utf-8"))}
    W = defaultdict(lambda: {"exits": 0, "exit_aff": 0, "reasons": Counter(),
                             "reasons_all": Counter(), "runs": set(),
                             "tiers": Counter(), "cats": Counter(),
                             "declined_tiers": Counter()})
    used = Counter(); eras = Counter()
    for fn in sorted(os.listdir(a.ext_dir)):
        rid = fn[:-5]
        meta = idx.get(rid, {})
        if a.character and meta.get("character") != a.character:
            continue
        if a.danger is not None and meta.get("danger") != a.danger:
            continue
        r = json.load(open(os.path.join(a.ext_dir, fn), encoding="utf-8"))
        vs = list(visits_for_run(r))
        if not vs or vs[0]["wave"] != 1:
            continue
        used[meta.get("character")] += 1
        eras[meta.get("era")] += 1
        for v in vs:
            s = W[v["wave"]]
            s["runs"].add(rid)
            bought = set(); curoff = v["entry_offer"]
            for d, od in v["seq"]:
                if od:
                    curoff = od
                if d["type"] == "shop_buy":
                    bought.add(d.get("slot"))
                elif d["type"] == "shop_go":
                    s["exits"] += 1
                    reason = d.get("exit_reason") or "none"
                    s["reasons_all"][reason] += 1
                    rem = [i for i in (curoff["items"] if curoff else [])
                           if i.get("slot") not in bought
                           and isinstance(i.get("price"), (int, float))
                           and i["price"] <= (d["gold"] or 0)]
                    for i in (curoff["items"] if curoff else []):
                        s["tiers"][i.get("tier")] += 1
                        s["cats"][i.get("cat")] += 1
                    if rem:
                        s["exit_aff"] += 1
                        s["reasons"][reason] += 1
                        for i in rem:
                            s["declined_tiers"][i.get("tier")] += 1
    out = {"runs_used": dict(used), "n_runs": sum(used.values()), "eras": dict(eras), "waves": {}}
    for w in sorted(W):
        s = W[w]
        out["waves"][w] = {"exits": s["exits"], "runs": len(s["runs"]),
                           "exit_with_affordable_remaining": s["exit_aff"],
                           "pct": 100.0 * s["exit_aff"] / s["exits"] if s["exits"] else None,
                           "reasons_when_affordable_remained": dict(s["reasons"]),
                           "all_exit_reasons": dict(s["reasons_all"]),
                           "offered_tier_mix": {str(k): v for k, v in s["tiers"].items()},
                           "declined_affordable_tier_mix": {str(k): v for k, v in s["declined_tiers"].items()}}
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    print("n_runs", out["n_runs"], dict(used))
    print("eras", dict(eras))
    hdr = "%-5s %6s %5s %8s %7s  %s" % ("wave", "exits", "runs", "affRem", "pct", "reasons_when_affordable_remained")
    print(hdr)
    for w in sorted(out["waves"]):
        d = out["waves"][w]
        print("%-5d %6d %5d %8d %6s  %s" % (
            w, d["exits"], d["runs"], d["exit_with_affordable_remaining"],
            "-" if d["pct"] is None else "%.1f" % d["pct"],
            sorted(d["reasons_when_affordable_remained"].items(), key=lambda x: -x[1])))
    print()
    print("declined affordable tier mix by wave (tier: count)")
    for w in sorted(out["waves"]):
        print(w, out["waves"][w]["declined_affordable_tier_mix"])


if __name__ == "__main__":
    main()
