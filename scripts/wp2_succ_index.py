"""Index runs from summary.json only (cheap). Classifies full runs vs fixtures."""
import argparse, json, os, sys, io

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs-dir", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    rows = []
    for name in sorted(os.listdir(a.runs_dir)):
        d = os.path.join(a.runs_dir, name)
        sp = os.path.join(d, "summary.json")
        if not os.path.isfile(sp):
            rows.append({"run_id": name, "class": "no_summary"})
            continue
        try:
            s = json.load(open(sp, encoding="utf-8", errors="replace"))
        except Exception as e:
            rows.append({"run_id": name, "class": "bad_summary", "err": str(e)[:120]})
            continue
        pur = s.get("purchases") or []
        waves = sorted({p.get("wave") for p in pur if isinstance(p.get("wave"), int)})
        first_wave = waves[0] if waves else None
        up = s.get("unlock_pool") or {}
        rows.append({
            "run_id": name,
            "class": "full" if first_wave == 1 else ("fixture_w17" if first_wave == 16 else
                     ("fixture_w20" if first_wave == 19 else ("other_first_%s" % first_wave))),
            "first_shop_wave": first_wave,
            "n_shop_waves": len(waves),
            "last_wave": s.get("last_wave"),
            "waves_completed": s.get("waves_completed"),
            "result": s.get("result"),
            "character": s.get("character"),
            "danger": s.get("danger"),
            "mod_version": s.get("mod_version"),
            "policy_version": s.get("policy_version"),
            "era": "%s/%s" % (up.get("items"), up.get("weapons")),
            "start": s.get("start_timestamp"),
            "n_purchase_decisions": len(pur),
            "telemetry_complete": s.get("telemetry_complete"),
            "size_mb": round(os.path.getsize(os.path.join(d, "events.jsonl")) / 1e6, 1)
                        if os.path.isfile(os.path.join(d, "events.jsonl")) else None,
        })
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(rows, f)
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    from collections import Counter
    print("total", len(rows))
    print(Counter(r["class"] for r in rows).most_common())
    print(Counter(r.get("era") for r in rows if r.get("class") == "full").most_common())

if __name__ == "__main__":
    main()
