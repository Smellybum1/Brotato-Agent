from pathlib import Path
import json
from collections import Counter

run = Path(r"C:\Users\moxhe\AppData\Roaming\Brotato\brotato_agent\runs\run_1784343069_17775")
ev = run / "events.jsonl"
summary = json.loads((run / "summary.json").read_text(encoding="utf-8"))
print("result", summary.get("result"), "wave", summary.get("last_wave"), "pol", summary.get("policy_version"))

damages_by_wave = Counter()
offers = []
decisions = []
for line in ev.open(encoding="utf-8", errors="replace"):
    w = json.loads(line)
    t = w.get("event")
    p = w.get("payload") or {}
    if t == "purchase_offer":
        offers.append(p)
    elif t == "purchase_decision":
        decisions.append(p)
    elif t == "player_damage":
        damages_by_wave[p.get("wave")] += 1

print("damage events by wave", dict(damages_by_wave))
print("offers", len(offers), "decisions", len(decisions))

out_lines = []
for i, d in enumerate(decisions):
    act = d.get("action") or {}
    at = act.get("type") if isinstance(act, dict) else act
    wave = d.get("wave")
    offer = offers[i] if i < len(offers) else {}
    items = offer.get("items") or []
    if at == "shop_buy" and isinstance(act, dict):
        slot = act.get("slot")
        chosen = None
        if isinstance(slot, int) and 0 <= slot < len(items):
            chosen = items[slot]
        else:
            for it in items:
                if it.get("slot") == slot:
                    chosen = it
                    break
        cid = chosen.get("id") if chosen else "?"
        effects = []
        if chosen:
            effects = [e.get("key") for e in (chosen.get("effects") or []) if isinstance(e, dict)][:8]
        out_lines.append(f"w{wave} BUY {cid} effects={effects} gold={offer.get('gold')}")
    else:
        out_lines.append(f"w{wave} {at} gold={offer.get('gold')}")

(Path(__file__).resolve().parent / "_late_shop_buys.txt").write_text("\n".join(out_lines) + "\n", encoding="utf-8")
print("--- all decisions wave>=11 ---")
for line in out_lines:
    try:
        wv = int(line.split()[0][1:])
    except Exception:
        continue
    if wv >= 11:
        print(line)

if decisions:
    print("sample decision keys", sorted(decisions[0].keys()))
    print("sample action", decisions[0].get("action"))
if offers:
    print("sample offer keys", sorted(offers[0].keys()))
    if offers[0].get("items"):
        print("sample item keys", sorted(offers[0]["items"][0].keys()))
