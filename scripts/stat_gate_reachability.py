"""READ-ONLY Gate-0 reachability scan for the two stat-gated character unlocks.

chal_hallucination: stat_dodge >= 60  -> character_ghost
chal_fast:          stat_speed >= 50  -> character_speedy

Field semantics (read from source, see report):
  * combat_capture.player.dodge = Player.max_stats.dodge = min(dodge_cap,stat_dodge)/100  (FRACTION, CAPPED)
  * combat_capture.player.speed = Player.max_stats.speed = stats.speed*(1+min(stat_speed,speed_cap)/100)  (units/sec)
  * run_end.summary.purchases[].build_metrics.defense.dodge = Utils.get_stat("stat_dodge")  (RAW PERCENT, UNCAPPED)
  * stat_speed is NOT captured anywhere; derived here as 100*(speed/base_speed - 1) with
    base_speed taken from the run's own first combat_capture (self-calibrating, lower bound).

Cheap I/O: only the first 512 KB and last 3 MB of each events.jsonl are read.
"""
import json
import os
import statistics
import sys

RUNS = os.path.expandvars(r"%APPDATA%\Brotato\brotato_agent\runs")
HEAD = 512 * 1024
TAIL = 3 * 1024 * 1024
N = int(sys.argv[1]) if len(sys.argv) > 1 else 300


def iter_json(buf, skip_first=False, skip_last=True):
    lines = buf.split(b"\n")
    if skip_first:
        lines = lines[1:]
    if skip_last:
        lines = lines[:-1]
    for ln in lines:
        ln = ln.strip()
        if not ln.startswith(b"{"):
            continue
        try:
            yield json.loads(ln)
        except Exception:
            continue


def scan(path):
    out = {"base_speed": None, "speed_max": None, "dodge_stat_max": None,
           "dodge_field_max": None, "has_run_end": False, "result": None,
           "last_wave": None, "character": None, "n_speed_samples": 0,
           "n_dodge_samples": 0, "first_wave": None}
    size = os.path.getsize(path)
    with open(path, "rb") as f:
        head = f.read(min(HEAD, size))
        for e in iter_json(head, skip_last=True):
            if e.get("event") == "combat_capture":
                p = e.get("payload", {}).get("player") or {}
                if "speed" in p:
                    out["base_speed"] = float(p["speed"])
                    out["first_wave"] = e.get("payload", {}).get("wave")
                    break
        f.seek(max(0, size - TAIL))
        tail = f.read()
    for e in iter_json(tail, skip_first=size > TAIL, skip_last=False):
        ev = e.get("event")
        if ev == "combat_capture":
            p = e.get("payload", {}).get("player") or {}
            if "speed" in p:
                v = float(p["speed"])
                out["n_speed_samples"] += 1
                if out["speed_max"] is None or v > out["speed_max"]:
                    out["speed_max"] = v
            if "dodge" in p:
                v = float(p["dodge"])
                if out["dodge_field_max"] is None or v > out["dodge_field_max"]:
                    out["dodge_field_max"] = v
        elif ev == "run_end":
            out["has_run_end"] = True
            s = e.get("payload", {}).get("summary", {}) or {}
            out["result"] = s.get("result")
            out["last_wave"] = s.get("last_wave")
            out["character"] = s.get("character")
            for group in ("purchases", "level_ups", "crates"):
                for rec in s.get(group) or []:
                    bm = rec.get("build_metrics") if isinstance(rec, dict) else None
                    if not isinstance(bm, dict):
                        continue
                    d = bm.get("defense", {}).get("dodge")
                    if d is None:
                        continue
                    out["n_dodge_samples"] += 1
                    d = float(d)
                    if out["dodge_stat_max"] is None or d > out["dodge_stat_max"]:
                        out["dodge_stat_max"] = d
    return out


def pct(vals, q):
    if not vals:
        return None
    v = sorted(vals)
    i = min(len(v) - 1, max(0, int(round(q * (len(v) - 1)))))
    return v[i]


def main():
    dirs = [d for d in os.listdir(RUNS) if d.startswith("run_")]

    def key(d):
        try:
            return int(d.split("_")[1])
        except Exception:
            return -1

    dirs.sort(key=key)
    sample = dirs[-N:]
    rows = []
    for d in sample:
        p = os.path.join(RUNS, d, "events.jsonl")
        if not os.path.exists(p):
            rows.append({"run": d, "error": "no_events"})
            continue
        try:
            r = scan(p)
        except Exception as exc:  # noqa: BLE001
            rows.append({"run": d, "error": repr(exc)})
            continue
        r["run"] = d
        # stat_speed derivation is only valid when the run started at wave 1;
        # wave-17 fixture runs begin with a prebuilt loadout, so their first
        # capture already includes stat_speed and the base is contaminated.
        if r["base_speed"] and r["speed_max"] and r.get("first_wave") == 1:
            r["stat_speed_derived"] = 100.0 * (r["speed_max"] / r["base_speed"] - 1.0)
        else:
            r["stat_speed_derived"] = None
        rows.append(r)

    os.makedirs(".tmp/stat_gate_reach", exist_ok=True)
    with open(".tmp/stat_gate_reach/per_run.json", "w") as f:
        json.dump(rows, f, indent=1)

    ok = [r for r in rows if not r.get("error")]
    withend = [r for r in ok if r["has_run_end"]]
    full = [r for r in ok if r.get("first_wave") == 1]
    fixture = [r for r in ok if r.get("first_wave") not in (1, None)]
    print(f"full runs (first capture wave 1)={len(full)}  "
          f"fixture runs (first capture wave!=1)={len(fixture)}")
    ds = [r["dodge_stat_max"] for r in withend if r["dodge_stat_max"] is not None]
    ds_full = [r["dodge_stat_max"] for r in full
               if r["has_run_end"] and r["dodge_stat_max"] is not None]
    ss = [r["stat_speed_derived"] for r in ok if r["stat_speed_derived"] is not None]
    df = [r["dodge_field_max"] for r in ok if r["dodge_field_max"] is not None]
    bs = sorted({r["base_speed"] for r in ok if r["base_speed"]})
    sp = [r["speed_max"] for r in ok if r["speed_max"] is not None]

    def block(name, v):
        if not v:
            print(f"{name}: NO DATA")
            return
        print(f"{name}: n={len(v)} max={max(v):.4g} p99={pct(v,0.99):.4g} "
              f"p95={pct(v,0.95):.4g} median={statistics.median(v):.4g} "
              f"min={min(v):.4g} distinct={len(set(v))}")

    print(f"sampled dirs={len(sample)} parsed={len(ok)} with_run_end={len(withend)} "
          f"errors={len(rows)-len(ok)}")
    block("stat_dodge ALL (build_metrics.defense.dodge, RAW PCT)", ds)
    block("stat_dodge FULL-RUNS-ONLY", ds_full)
    print(f"full runs reaching stat_dodge>=60: "
          f"{sum(1 for v in ds_full if v >= 60)}/{len(ds_full)}")
    block("player.dodge (capped fraction)", df)
    block("player.speed (units/sec)", sp)
    block("stat_speed derived (pct, lower bound)", ss)
    print("distinct base_speed values:", bs[:20], "count", len(bs))
    print(f"runs reaching stat_dodge>=60: {sum(1 for v in ds if v >= 60)}/{len(ds)}")
    print(f"runs reaching stat_speed>=50: {sum(1 for v in ss if v >= 50)}/{len(ss)}")
    print(f"runs reaching player.dodge>=0.60: {sum(1 for v in df if v >= 0.60)}/{len(df)}")
    top = sorted([r for r in withend if r["dodge_stat_max"] is not None],
                 key=lambda r: -r["dodge_stat_max"])[:5]
    for r in top:
        print("TOP dodge", r["run"], r["character"], r["result"], r["last_wave"],
              r["dodge_stat_max"])
    top = sorted([r for r in ok if r["stat_speed_derived"] is not None],
                 key=lambda r: -r["stat_speed_derived"])[:5]
    for r in top:
        print("TOP speed", r["run"], r["character"], r["result"], r["last_wave"],
              round(r["stat_speed_derived"], 2), r["base_speed"], r["speed_max"])


if __name__ == "__main__":
    main()
