"""Stage A steps 2-4: wave-17 per-run metrics for died-at-17 vs matched survivors.

Reuses wp2_wave_uptime / wp2_enemy_aggregate primitives. Adds:
  * coverage: DPS-weighted mean over captures of (live enemies in weapon range)
    / (live enemies), conditioned on >=1 live enemy.
  * crowding-binned uptime/coverage (bins by number of live enemies).

Writes .tmp/stageA/wave17_metrics.jsonl (one row per run).
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from wp2_enemy_aggregate import (  # noqa: E402
    capture_elapsed_sec,
    enemies_alive,
    enemy_hp_pool,
    iter_wave_payloads,
)
from wp2_wave_uptime import (  # noqa: E402
    MIN_CONTROL_DT_MS,
    _f,
    _live_entities,
    nominal_dps,
    prepare_wave_payloads,
    surface_distance,
    weapon_dps,
)

RUNS = os.path.join(
    os.environ.get("APPDATA", r"C:\Users\moxhe\AppData\Roaming"), "Brotato", "brotato_agent", "runs"
)
OUT_DIR = os.path.join(ROOT, ".tmp", "stageA")
WAVE = 17
WINDOWS = [(0.0, 10.0), (10.0, 20.0), (15.0, 25.0), (20.0, 30.0), (30.0, 40.0)]
CROWD_BINS = [(0, 4), (5, 9), (10, 14), (15, 19), (20, 10**6)]
CROWD_LABELS = ["0-4", "5-9", "10-14", "15-19", "20+"]
FULL_RUN_MIN_MS = 900000


def _policy_num(pv):
    m = re.search(r"0\.1\.(\d+)", pv or "")
    return int(m.group(1)) if m else -1


def capture_stats(payload):
    """Per-capture DPS-weighted uptime indicator and coverage fraction.

    Returns (n_alive, dps_total, uptime_num, coverage_num) or None if no live
    enemies or no positive-DPS weapon.
    """
    live = _live_entities(payload, include_bosses=False)
    n = len(live)
    if n == 0:
        return None
    pl = payload.get("player") or {}
    px, py = _f(pl.get("x")), _f(pl.get("y"))
    dists = [surface_distance(px, py, e) for e in live]
    dps_tot = 0.0
    up_num = 0.0
    cov_num = 0.0
    for w in payload.get("weapons") or []:
        if not isinstance(w, dict):
            continue
        d = weapon_dps(w)
        if d <= 0.0:
            continue
        rng = _f(w.get("max_range"), -1.0)
        if rng < 0.0:
            continue
        k = sum(1 for dd in dists if dd <= rng)
        dps_tot += d
        up_num += d * (1.0 if k > 0 else 0.0)
        cov_num += d * (k / float(n))
    if dps_tot <= 0.0:
        return None
    return n, dps_tot, up_num, cov_num


def _mean(v):
    return (sum(v) / len(v)) if v else None


def window_metrics(payloads, lo, hi):
    sel = []
    for p in payloads:
        t = capture_elapsed_sec(p)
        if t is not None and lo <= t < hi:
            sel.append(p)
    up_n = up_d = cov_n = cov_d = 0.0
    n_eng = 0
    counts, pools, nearest, speeds = [], [], [], []
    for p in sel:
        na = enemies_alive(p)
        counts.append(na)
        pools.append(enemy_hp_pool(p))
        if _f(p.get("control_dt_ms"), 0.0) >= MIN_CONTROL_DT_MS:
            speeds.append(_f((p.get("player") or {}).get("speed")))
        st = capture_stats(p)
        if st is None:
            continue
        n, dt, un, cn = st
        n_eng += 1
        up_n += un
        up_d += dt
        cov_n += cn
        cov_d += dt
        pl = p.get("player") or {}
        px, py = _f(pl.get("x")), _f(pl.get("y"))
        nearest.append(min(surface_distance(px, py, e) for e in _live_entities(p, False)))
    return {
        "t_lo": lo,
        "t_hi": hi,
        "n_captures": len(sel),
        "n_captures_engaged": n_eng,
        "uptime_engaged": (up_n / up_d) if up_d > 0 else None,
        "coverage": (cov_n / cov_d) if cov_d > 0 else None,
        "mean_enemies_alive": _mean(counts),
        "max_enemies_alive": max(counts) if counts else None,
        "mean_enemy_hp_pool": _mean(pools),
        "mean_nearest_surface_dist": _mean(nearest),
        "mean_player_speed": _mean(speeds),
        "n_speed_samples": len(speeds),
    }


def crowd_metrics(payloads, lo, hi):
    acc = {lab: [0.0, 0.0, 0.0, 0] for lab in CROWD_LABELS}  # up_n, cov_n, dps_d, n_caps
    for p in payloads:
        t = capture_elapsed_sec(p)
        if t is None or not (lo <= t < hi):
            continue
        st = capture_stats(p)
        if st is None:
            continue
        n, dt, un, cn = st
        for (blo, bhi), lab in zip(CROWD_BINS, CROWD_LABELS):
            if blo <= n <= bhi:
                a = acc[lab]
                a[0] += un
                a[1] += cn
                a[2] += dt
                a[3] += 1
                break
    out = {}
    for lab in CROWD_LABELS:
        un, cn, dd, nc = acc[lab]
        out[lab] = {
            "n_captures": nc,
            "uptime_engaged": (un / dd) if dd > 0 else None,
            "coverage": (cn / dd) if dd > 0 else None,
        }
    return out


def entry_state(payloads):
    if not payloads:
        return {"found": False}
    first = payloads[0]
    pl = first.get("player") or {}
    nd = nominal_dps(first.get("weapons") or [])
    return {
        "found": True,
        "entry_elapsed_sec": capture_elapsed_sec(first),
        "hp": _f(pl.get("hp")),
        "max_hp": _f(pl.get("max_hp")),
        "armor": _f(pl.get("armor")),
        "dodge": _f(pl.get("dodge")),
        "lifesteal": _f(pl.get("lifesteal")),
        "hp_regeneration": _f(pl.get("hp_regeneration")),
        "speed": _f(pl.get("speed")),
        "nominal_dps": nd["total"],
        "n_weapons": nd["n_weapons"],
    }


def process(run):
    path = os.path.join(RUNS, run["dir"], "events.jsonl")
    payloads = prepare_wave_payloads(iter_wave_payloads(path, WAVE))
    row = {
        "run_id": run["run_id"],
        "dir": run["dir"],
        "cls": run["cls"],
        "result": run["result"],
        "last_wave": run["last_wave"],
        "duration_ms": run["duration_ms"],
        "policy_version": run["policy_version"],
        "mod_version": run["mod_version"],
        "n_wave17_payloads": len(payloads),
        "entry": entry_state(payloads),
        "windows": {"%g-%g" % (lo, hi): window_metrics(payloads, lo, hi) for lo, hi in WINDOWS},
        "crowd_0_10": crowd_metrics(payloads, 0.0, 10.0),
        "crowd_15_25": crowd_metrics(payloads, 15.0, 25.0),
        "crowd_0_40": crowd_metrics(payloads, 0.0, 40.0),
    }
    return row


def select_runs():
    idx = [json.loads(l) for l in open(os.path.join(OUT_DIR, "run_index.jsonl"), encoding="utf-8")]
    full = [r for r in idx if isinstance(r["duration_ms"], (int, float))
            and r["duration_ms"] >= FULL_RUN_MIN_MS and r["has_events"]]
    died = [r for r in full if r["result"] == "defeat" and r["last_wave"] == 17]
    surv = [r for r in full if isinstance(r["last_wave"], int) and r["last_wave"] >= 18]
    for r in died:
        r["cls"] = "died17"
    for r in surv:
        r["cls"] = "survivor"

    # Version-matched sampling: for each died run, take the survivor with the
    # closest policy minor number that has not yet been used. Deterministic
    # (survivors pre-sorted by run_id), cap 45.
    surv_sorted = sorted(surv, key=lambda r: r["run_id"])
    used = set()
    picked = []
    for d in sorted(died, key=lambda r: r["run_id"]):
        dn = _policy_num(d["policy_version"])
        cands = [s for s in surv_sorted if id(s) not in used]
        if not cands:
            break
        best = min(cands, key=lambda s: (abs(_policy_num(s["policy_version"]) - dn), s["run_id"]))
        used.add(id(best))
        picked.append(best)
        if len(picked) >= 45:
            break
    return died, picked


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    died, surv = select_runs()
    runs = died + surv
    print("processing died=%d survivors=%d total=%d" % (len(died), len(surv), len(runs)))
    out_path = os.path.join(OUT_DIR, "wave17_metrics.jsonl")
    import time
    t0 = time.time()
    with open(out_path, "w", encoding="utf-8") as out:
        for i, r in enumerate(runs, 1):
            try:
                row = process(r)
            except Exception as exc:  # noqa: BLE001
                print("ERROR %s: %r" % (r["dir"], exc))
                continue
            out.write(json.dumps(row) + "\n")
            if i % 10 == 0:
                print("  %d/%d  %.1fs elapsed (%.1f s/run)" % (i, len(runs), time.time() - t0, (time.time() - t0) / i))
    print("wrote %s in %.1fs" % (out_path, time.time() - t0))


if __name__ == "__main__":
    main()
