"""Q1: shop visits with an affordable offer that end in no purchase, by wave."""
import argparse, json, os, sys, io
from collections import defaultdict, Counter


def visits_for_run(r):
    """Yield dicts per shop visit: wave, entry gold, entry offer, buys, exit reason."""
    dec = r["decisions"]
    off = r["offers"]
    if not dec:
        return
    # attach the latest offer with seq < decision seq
    oi = 0
    cur = None
    events = []
    for d in dec:
        while oi < len(off) and off[oi]["seq"] < d["seq"]:
            cur = off[oi]; oi += 1
        events.append((d, cur))
    visits = defaultdict(list)
    for d, o in events:
        visits[d["wave"]].append((d, o))
    for wave in sorted(visits):
        seq = visits[wave]
        d0, o0 = seq[0]
        yield {
            "wave": wave,
            "entry_gold": d0["gold"],
            "entry_offer": o0,
            "n_dec": len(seq),
            "buys": [d for d, _ in seq if d["type"] == "shop_buy"],
            "rerolls": sum(1 for d, _ in seq if d["type"] == "shop_reroll"),
            "exit": seq[-1][0],
            "seq": seq,
        }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ext-dir", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    files = sorted(os.listdir(a.ext_dir))
    per_wave = defaultdict(lambda: {"visits": 0, "aff_visits": 0, "aff_nobuy": 0,
                                    "runs": set(), "exits": 0, "exit_aff": 0,
                                    "reasons": Counter(), "reasons_aff": Counter(),
                                    "n_aff_slots": []})
    cls = Counter()
    meta_eras = Counter(); chars = Counter(); dangers = Counter()
    n_runs = 0
    no_offer = 0
    for fn in files:
        r = json.load(open(os.path.join(a.ext_dir, fn), encoding="utf-8"))
        m = r.get("meta") or {}
        ch = m.get("character"); dg = m.get("danger")
        up = m.get("unlock_pool") or {}
        era = "%s/%s" % (up.get("items"), up.get("weapons"))
        waves = sorted({v["wave"] for v in visits_for_run(r)})
        if not waves or waves[0] != 1:
            cls["not_full"] += 1
            continue
        cls["full"] += 1
        n_runs += 1
        meta_eras[era] += 1; chars[ch] += 1; dangers[dg] += 1
        for v in visits_for_run(r):
            w = v["wave"]; s = per_wave[w]
            s["visits"] += 1; s["runs"].add(r["run_id"])
            o = v["entry_offer"]
            if not o:
                no_offer += 1
                continue
            g = v["entry_gold"]
            aff = [i for i in o["items"]
                   if isinstance(i.get("price"), (int, float)) and i["price"] <= g]
            if aff:
                s["aff_visits"] += 1
                s["n_aff_slots"].append(len(aff))
                if not v["buys"]:
                    s["aff_nobuy"] += 1
                    s["reasons_aff"][v["exit"].get("exit_reason") or v["exit"]["type"]] += 1
            # exit-time affordability (cross-check of the prior 16.6% figure)
            bought = set()
            curoff = o
            for d, od in v["seq"]:
                if od:
                    curoff = od
                if d["type"] == "shop_buy":
                    bought.add(d.get("slot"))
                if d["type"] == "shop_go":
                    s["exits"] += 1
                    rem = [i for i in curoff["items"]
                           if i.get("slot") not in bought
                           and isinstance(i.get("price"), (int, float))
                           and i["price"] <= (d["gold"] or 0)]
                    if rem:
                        s["exit_aff"] += 1
                    s["reasons"][d.get("exit_reason") or "none"] += 1
    res = {"n_runs": n_runs, "classes": dict(cls), "eras": dict(meta_eras),
           "chars": dict(chars), "dangers": dict(dangers), "visits_without_offer": no_offer,
           "waves": {}}
    for w in sorted(per_wave):
        s = per_wave[w]
        res["waves"][w] = {
            "visits": s["visits"], "runs": len(s["runs"]),
            "aff_visits": s["aff_visits"], "aff_nobuy": s["aff_nobuy"],
            "pct_aff_nobuy": (100.0 * s["aff_nobuy"] / s["aff_visits"]) if s["aff_visits"] else None,
            "median_aff_slots": sorted(s["n_aff_slots"])[len(s["n_aff_slots"]) // 2] if s["n_aff_slots"] else None,
            "exits": s["exits"], "exit_aff": s["exit_aff"],
            "pct_exit_aff": (100.0 * s["exit_aff"] / s["exits"]) if s["exits"] else None,
            "reasons_aff_nobuy": dict(s["reasons_aff"]),
            "exit_reasons": dict(s["reasons"]),
        }
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1)
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    print("runs", n_runs, "classes", dict(cls), "no_offer_visits", no_offer)
    print("eras", dict(meta_eras)); print("chars", dict(chars)); print("dangers", dict(dangers))
    print("%-5s %6s %5s %8s %8s %8s %6s %8s %8s" % (
        "wave", "visits", "runs", "affVis", "affNoBuy", "pct", "medAff", "exits", "pctExitAff"))
    for w in sorted(res["waves"]):
        d = res["waves"][w]
        print("%-5d %6d %5d %8d %8d %7s %6s %8d %9s" % (
            w, d["visits"], d["runs"], d["aff_visits"], d["aff_nobuy"],
            "-" if d["pct_aff_nobuy"] is None else "%.1f" % d["pct_aff_nobuy"],
            d["median_aff_slots"], d["exits"],
            "-" if d["pct_exit_aff"] is None else "%.1f" % d["pct_exit_aff"]))


if __name__ == "__main__":
    main()
