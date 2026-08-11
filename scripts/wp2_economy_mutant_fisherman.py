"""READ-ONLY economy comparison: character_mutant vs character_fisherman.

Streams events.jsonl per run, extracts per-wave economy and build-strength series.

Fields used (all verified to vary):
  combat_capture.payload.player.materials      -> live gold/materials counter
  combat_capture.payload.entities.materials    -> ground piles (list; game caps at MAX_GOLDS=50)
  combat_capture.payload.wave_time.remaining_sec -> measurement-instant guard
  combat_capture.payload.weapons[].damage/.cooldown -> build strength proxy
  purchase_decision.payload.gold_before        -> gold at each shop decision
  purchase_decision.payload.action.type/.slot/.item_id
  purchase_offer.payload.items[].price/.category -> price join for spend

Dead fields deliberately NOT used: materials_spent, rerolls, locks, config_id,
summary.danger, profile.starting_weapon.
"""
import json
import os
import sys
import statistics
from collections import defaultdict

RUNS_DIR = r"C:\Users\moxhe\AppData\Roaming\Brotato\brotato_agent\runs"
OUT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    ".tmp", "economy_mutant_fisherman",
)

MUTANT = [
    "run_1785438259_55252", "run_1785439201_12867",
    "run_1785440072_83646", "run_1785441152_78936",
]
FISHERMAN = [
    "run_1785442479_69789", "run_1785442943_62985", "run_1785443861_62691",
    "run_1785444373_44167", "run_1785445288_89855", "run_1785445807_93565",
    "run_1785446411_69244", "run_1785446886_81439",
]


def build_strength(weapons):
    """sum(damage/cooldown) over held weapons. cooldown in frames; 0 -> skip."""
    tot = 0.0
    for w in weapons or []:
        cd = w.get("cooldown") or 0
        dmg = w.get("damage") or 0
        if cd > 0:
            tot += float(dmg) / float(cd)
    return tot


def parse_run(run_id):
    path = os.path.join(RUNS_DIR, run_id, "events.jsonl")
    waves = {}          # wave -> dict
    pending_offer = None
    purchases = []      # (wave, item_id, price, category, gold_before)
    shop_gold = {}      # wave -> list of gold_before
    meta = {}
    seen_purchase = set()

    def wv(w):
        if w not in waves:
            waves[w] = {
                "mat_first": None, "mat_last_valid": None,
                "ground_last_valid": None, "ground_max": 0,
                "bs_first": None, "bs_last": None,
                "wcount_first": None, "wcount_last": None,
                "captures": 0, "valid_captures": 0,
                "mat_at_first_capture": None,
            }
        return waves[w]

    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except Exception:
                continue
            ev = e.get("event")
            pl = e.get("payload") or {}

            if ev == "run_start":
                meta["character"] = pl.get("character")
                meta["weapon"] = pl.get("weapon")
                meta["mod_version"] = pl.get("mod_version")
                meta["unlock_pool"] = pl.get("unlock_pool")
            elif ev == "run_end":
                s = pl.get("summary") or {}
                meta["result"] = pl.get("result")
                meta["last_wave"] = s.get("last_wave")
                meta["waves_completed"] = s.get("waves_completed")
            elif ev == "combat_capture":
                w = pl.get("wave")
                if w is None:
                    continue
                d = wv(w)
                d["captures"] += 1
                mats = ((pl.get("player") or {}).get("materials"))
                ground = len(((pl.get("entities") or {}).get("materials")) or [])
                bs = build_strength(pl.get("weapons"))
                wc = len(pl.get("weapons") or [])
                if d["mat_at_first_capture"] is None:
                    d["mat_at_first_capture"] = mats
                if d["bs_first"] is None:
                    d["bs_first"] = bs
                    d["wcount_first"] = wc
                d["bs_last"] = bs
                d["wcount_last"] = wc
                rem = ((pl.get("wave_time") or {}).get("remaining_sec"))
                # TRAP 3: only captures with remaining_sec > 0 are inside the wave.
                if rem is not None and rem > 0:
                    d["valid_captures"] += 1
                    if d["mat_first"] is None:
                        d["mat_first"] = mats
                    d["mat_last_valid"] = mats
                    d["ground_last_valid"] = ground
                    if ground > d["ground_max"]:
                        d["ground_max"] = ground
            elif ev == "purchase_offer":
                pending_offer = pl.get("items") or []
            elif ev == "purchase_decision":
                act = pl.get("action") or {}
                w = pl.get("wave")
                gb = pl.get("gold_before")
                key = (e.get("seq"),)
                if key in seen_purchase:
                    continue
                seen_purchase.add(key)
                shop_gold.setdefault(w, []).append(gb)
                if act.get("type") == "shop_buy":
                    slot = act.get("slot")
                    price, cat, item_id = None, None, act.get("item_id")
                    for it in (pending_offer or []):
                        if it.get("slot") == slot:
                            price = it.get("price")
                            cat = it.get("category")
                            break
                    purchases.append({
                        "wave": w, "item_id": item_id, "price": price,
                        "category": cat, "gold_before": gb,
                    })

    return {"run_id": run_id, "meta": meta, "waves": waves,
            "purchases": purchases, "shop_gold": shop_gold}


def summarize(run):
    """Per-wave record for one run."""
    waves = run["waves"]
    rows = []
    wave_ids = sorted(waves.keys())
    buys_by_wave = defaultdict(list)
    for p in run["purchases"]:
        buys_by_wave[p["wave"]].append(p)

    cum_items = 0
    for w in wave_ids:
        d = waves[w]
        gained = None
        if d["mat_first"] is not None and d["mat_last_valid"] is not None:
            gained = d["mat_last_valid"] - d["mat_first"]
        # spend for the shop AFTER wave w: gold at shop entry minus
        # materials observed at the first capture of wave w+1.
        spend = None
        gold_entry = None
        gl = run["shop_gold"].get(w) or []
        if gl:
            gold_entry = gl[0]
            nxt = waves.get(w + 1)
            if nxt is not None and nxt["mat_at_first_capture"] is not None:
                spend = gold_entry - nxt["mat_at_first_capture"]
        bws = buys_by_wave.get(w, [])
        n_buys = len(bws)
        price_sum = sum(b["price"] for b in bws if b["price"] is not None)
        n_item_cat = sum(1 for b in bws if b["category"] == "item")
        cum_items += n_item_cat
        rows.append({
            "wave": w,
            "materials_gained": gained,
            "materials_end_of_wave": d["mat_last_valid"],
            "gold_at_shop_entry": gold_entry,
            "shop_spend": spend,
            "price_sum_bought": price_sum,
            "items_bought": n_buys,
            "item_category_bought": n_item_cat,
            "cum_item_category": cum_items,
            "ground_left_at_wave_end": d["ground_left"] if "ground_left" in d else d["ground_last_valid"],
            "ground_max_in_wave": d["ground_max"],
            "build_strength_start": d["bs_first"],
            "build_strength_end": d["bs_last"],
            "weapon_count_end": d["wcount_last"],
            "captures": d["captures"],
            "valid_captures": d["valid_captures"],
        })
    return rows


def mean(xs):
    xs = [x for x in xs if x is not None]
    return statistics.mean(xs) if xs else None


def med(xs):
    xs = [x for x in xs if x is not None]
    return statistics.median(xs) if xs else None


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    data = {"mutant": [], "fisherman": []}
    for name, ids in (("mutant", MUTANT), ("fisherman", FISHERMAN)):
        for rid in ids:
            r = parse_run(rid)
            r["rows"] = summarize(r)
            data[name].append(r)

    out = {}
    for name in data:
        out[name] = [{
            "run_id": r["run_id"],
            "meta": r["meta"],
            "rows": r["rows"],
        } for r in data[name]]

    with open(os.path.join(OUT_DIR, "per_wave.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)

    # matched-wave aggregation
    metrics = ["materials_gained", "shop_spend", "items_bought",
               "price_sum_bought", "ground_left_at_wave_end",
               "ground_max_in_wave", "build_strength_end", "weapon_count_end",
               "cum_item_category"]
    agg = {}
    for name in data:
        per = defaultdict(lambda: defaultdict(list))
        for r in data[name]:
            for row in r["rows"]:
                for m in metrics:
                    per[row["wave"]][m].append(row.get(m))
        agg[name] = per

    lines = []
    lines.append("wave,metric,mutant_n,mutant_mean,mutant_median,fisher_n,fisher_mean,fisher_median")
    all_waves = sorted(set(list(agg["mutant"].keys()) + list(agg["fisherman"].keys())))
    for w in all_waves:
        for m in metrics:
            a = [x for x in agg["mutant"][w][m] if x is not None]
            b = [x for x in agg["fisherman"][w][m] if x is not None]
            lines.append("%d,%s,%d,%s,%s,%d,%s,%s" % (
                w, m, len(a),
                ("%.3f" % mean(a)) if a else "",
                ("%.3f" % med(a)) if a else "",
                len(b),
                ("%.3f" % mean(b)) if b else "",
                ("%.3f" % med(b)) if b else "",
            ))
    csv_path = os.path.join(OUT_DIR, "matched_wave.csv")
    with open(csv_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    print("wrote", csv_path)
    for name in data:
        for r in data[name]:
            m = r["meta"]
            print(name, r["run_id"], m.get("result"), "last_wave=", m.get("last_wave"),
                  "waves=", len(r["rows"]))


if __name__ == "__main__":
    main()
