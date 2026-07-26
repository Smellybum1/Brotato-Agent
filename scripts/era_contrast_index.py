"""Offline: index all run summaries for era-contrast analysis. Writes .tmp/era_index.json"""
import json, os, re, sys

RUNS = os.path.join(os.environ["APPDATA"], "Brotato", "brotato_agent", "runs")
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".tmp", "era_index.json")

rows = []
for rid in sorted(os.listdir(RUNS)):
    d = os.path.join(RUNS, rid)
    sp = os.path.join(d, "summary.json")
    if not os.path.isfile(sp):
        rows.append({"run_id": rid, "error": "no_summary", "files": sorted(os.listdir(d)) if os.path.isdir(d) else None})
        continue
    try:
        s = json.load(open(sp, encoding="utf-8"))
    except Exception as e:
        rows.append({"run_id": rid, "error": f"parse:{e}"})
        continue
    pv = s.get("policy_version", "")
    m = re.search(r"(\d+\.\d+\.\d+)", pv)
    files = sorted(os.listdir(d))
    sizes = {f: os.path.getsize(os.path.join(d, f)) for f in files}
    rows.append({
        "run_id": rid,
        "policy_version": pv,
        "ver": m.group(1) if m else None,
        "mod_version": s.get("mod_version"),
        "game_version": s.get("game_version"),
        "character": s.get("character"), "weapon": s.get("weapon"),
        "danger": s.get("danger"), "config_id": s.get("config_id"),
        "result": s.get("result"), "last_wave": s.get("last_wave"),
        "waves_completed": s.get("waves_completed"),
        "damage_taken": s.get("damage_taken"),
        "n_purchases": len(s.get("purchases") or []),
        "n_levelups": len(s.get("level_ups") or []),
        "rerolls": s.get("rerolls"), "locks": s.get("locks"),
        "materials_spent": s.get("materials_spent"),
        "duration_ms": s.get("duration_ms"),
        "start": s.get("start_timestamp"),
        "files": files, "sizes": sizes,
        "student_enabled": s.get("student_enabled"),
        "keys": sorted(s.keys()),
    })
os.makedirs(os.path.dirname(OUT), exist_ok=True)
json.dump(rows, open(OUT, "w", encoding="utf-8"), indent=1)
print("runs:", len(rows), "->", OUT)
from collections import Counter
c = Counter(r.get("ver") for r in rows)
for k in sorted(c, key=lambda x: (x is None, x)):
    print(f"  {k}: {c[k]}")
