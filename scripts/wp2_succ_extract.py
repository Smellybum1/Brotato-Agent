"""Per-run compact extraction for successor-design questions Q1/Q2/Q3.

Reads events.jsonl once per run. Captures are scanned with a byte regex (fast);
only capture lines in a +/-6 window around an HP-drop are fully JSON-parsed so
enemy types are available for the causal-lag sweep.

Writes one compact JSON per run into --out-dir. READ-ONLY on the archive.
"""
import argparse, json, os, re, sys, io
from collections import deque

RX_CAP = re.compile(
    rb'"ts_ms":(\d+).*?"control_dt_ms":([0-9.eE+-]+),"valid":(true|false),"wave":(\d+)'
    rb'.*?"player":\{"x":([0-9.eE+-]+),"y":([0-9.eE+-]+),"vx":[0-9.eE+-]+,"vy":[0-9.eE+-]+,"hp":([0-9.eE+-]+)')

WINDOW = 6  # captures kept either side of an HP drop


def enemy_summary(payload):
    ents = payload.get("entities") or {}
    out = []
    for key in ("enemies", "bosses"):
        for e in ents.get(key) or []:
            nx, ny = e.get("nx"), e.get("ny")
            if nx is None:
                continue
            d = (nx * nx + ny * ny) ** 0.5
            tid = e.get("type_id") or ""
            t = tid.rsplit("/", 2)[-2] if "/" in tid else tid
            out.append({"t": t, "d": round(d, 2),
                        "sd": round(d - (e.get("radius") or 0), 2),
                        "cat": key})
    out.sort(key=lambda r: r["sd"])
    out = out[:4]
    proj = []
    for e in ents.get("projectiles") or []:
        nx, ny = e.get("nx"), e.get("ny")
        if nx is None:
            continue
        d = (nx * nx + ny * ny) ** 0.5
        tid = e.get("type_id") or ""
        proj.append({"t": tid.rsplit("/", 1)[-1], "d": round(d, 2),
                     "sd": round(d - (e.get("radius") or 0), 2), "cat": "projectile"})
    proj.sort(key=lambda r: r["sd"])
    return {"e": out, "p": proj[:3]}


def process(path, out_path):
    caps = []          # (ts, wave, hp, dt, valid, x, y)
    ctx = {}           # capture index -> enemy summary
    line_buf = deque(maxlen=WINDOW + 1)
    pending = []       # capture indices still needing forward context
    offers = []        # (ts, items[slot,price,cat,id])
    decisions = []
    meta = {}
    end = {}
    prev_hp = None
    idx = -1
    with open(path, "rb") as f:
        for raw in f:
            if b'"combat_capture"' in raw:
                m = RX_CAP.search(raw)
                if not m:
                    continue
                idx += 1
                ts = int(m.group(1)); dt = float(m.group(2))
                valid = m.group(3) == b"true"; wave = int(m.group(4))
                x = float(m.group(5)); y = float(m.group(6)); hp = float(m.group(7))
                caps.append((ts, wave, hp, dt, valid, x, y))
                line_buf.append((idx, raw))
                # forward context for pending drops
                if pending:
                    still = []
                    for di in pending:
                        if idx - di <= WINDOW:
                            ctx.setdefault(idx, None)
                            still.append(di)
                    pending = still
                    if idx in ctx and ctx[idx] is None:
                        try:
                            ctx[idx] = enemy_summary(json.loads(raw)["payload"])
                        except Exception:
                            ctx[idx] = []
                if prev_hp is not None and hp < prev_hp:
                    for bi, braw in line_buf:
                        if bi not in ctx or ctx[bi] is None:
                            try:
                                ctx[bi] = enemy_summary(json.loads(braw)["payload"])
                            except Exception:
                                ctx[bi] = []
                    pending.append(idx)
                prev_hp = hp
                continue
            if b'"purchase_offer"' in raw:
                e = json.loads(raw)
                if e.get("event") != "purchase_offer":
                    continue
                items = [{"slot": i.get("slot"), "price": i.get("price"),
                          "cat": i.get("category"), "tier": i.get("tier"),
                          "id": i.get("id"), "aff": i.get("affordable"),
                          "locked": i.get("locked")}
                         for i in e["payload"].get("items") or []]
                offers.append({"ts": e.get("ts_ms"), "seq": e.get("seq"), "items": items})
            elif b'"purchase_decision"' in raw:
                e = json.loads(raw)
                if e.get("event") != "purchase_decision":
                    continue
                p = e["payload"]
                a = p.get("action") or {}
                decisions.append({"ts": e.get("ts_ms"), "seq": e.get("seq"),
                                  "wave": p.get("wave"), "gold": p.get("gold_before"),
                                  "type": a.get("type"), "slot": a.get("slot"),
                                  "item_id": a.get("item_id"),
                                  "exit_reason": a.get("exit_reason"),
                                  "reroll_price": p.get("reroll_price")})
            elif b'"run_start"' in raw:
                e = json.loads(raw)
                if e.get("event") == "run_start":
                    p = e["payload"]
                    meta = {"character": p.get("character"), "danger": p.get("requested_danger"),
                            "mod_version": p.get("mod_version"),
                            "policy_version": p.get("policy_version"),
                            "unlock_pool": p.get("unlock_pool"), "ts": e.get("ts_ms")}
            elif b'"run_end"' in raw:
                e = json.loads(raw)
                if e.get("event") == "run_end":
                    end = {k: e["payload"].get(k) for k in
                           ("result", "last_wave", "waves_completed")}
                    end["ts"] = e.get("ts_ms")
    out = {"run_id": os.path.basename(os.path.dirname(path)), "meta": meta, "end": end,
           "n_caps": len(caps), "caps": caps, "ctx": {str(k): v for k, v in ctx.items()},
           "offers": offers, "decisions": decisions}
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f)
    return len(caps), len(ctx), len(decisions)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs-dir", required=True)
    ap.add_argument("--run-list", required=True)
    ap.add_argument("--out-dir", required=True)
    a = ap.parse_args()
    os.makedirs(a.out_dir, exist_ok=True)
    ids = [x.strip() for x in open(a.run_list, encoding="utf-8") if x.strip()]
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    for i, rid in enumerate(ids):
        op = os.path.join(a.out_dir, rid + ".json")
        if os.path.exists(op):
            continue
        p = os.path.join(a.runs_dir, rid, "events.jsonl")
        if not os.path.isfile(p):
            print("MISSING", rid); continue
        try:
            n = process(p, op)
        except Exception as e:
            print("FAIL", rid, type(e).__name__, str(e)[:160]); continue
        if i % 10 == 0:
            print(i, rid, n, flush=True)


if __name__ == "__main__":
    main()
