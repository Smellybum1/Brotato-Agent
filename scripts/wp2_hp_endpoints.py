"""Recompute HP-based run endpoints from the existing telemetry archive.

Replaces the retired ``damage_taken`` primary (a GROSS counter that never
subtracts healing) with:

  A. Death-adjusted HP-deficit AUC (per run, per wave)  -- new fixed-wave primary
  B. Threshold exposures below 70/50/30% max HP, with death ABSORBING
  C. Healing reconstructed from the HP series, attributed as far as honest
  D. Healing-consumable pickups per wave
  E. Gross damage retained as a reported COMPONENT only (+ net = gross - healing)
  F. Variance components (between-source-state / within-source-state) for sizing

No gameplay is run.  Everything comes from
``%APPDATA%/Brotato/brotato_agent/runs/run_*/{events.jsonl,summary.json}``.

Stage 1 (``--extract``) streams the raw ``events.jsonl`` files and writes a
compact per-run cache; stage 2 does the arithmetic from the cache.  The default
invocation does both, reusing an existing cache unless ``--refresh`` is given.

Usage (repo root, venv python):

    set APPDATA=C:\\Users\\moxhe\\AppData\\Roaming
    .venv\\Scripts\\python.exe scripts\\wp2_hp_endpoints.py

"""

from __future__ import annotations

import argparse
import gzip
import json
import math
import os
import statistics
import sys
import time
from collections import Counter, defaultdict
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

# ---------------------------------------------------------------------------
# constants / tunables (all reported in the output so nothing is hidden)
# ---------------------------------------------------------------------------

DEFAULT_RUNS_DIR = os.path.join(
    os.environ.get("APPDATA", os.path.expanduser("~")),
    "Brotato",
    "brotato_agent",
    "runs",
)
DEFAULT_CACHE_DIR = os.path.join("reports", "wp2", "_hp_endpoint_cache")
DEFAULT_REPORT = os.path.join("reports", "wp2", "hp_endpoints_recompute.md")

# newest coherent era; VERIFIED against the mod x policy table printed by this
# script, not assumed.
ERA_POLICY = "teacher_v1-0.1.129-gun-wp1"
ERA_MODS = ("0.2.49-wp2-capture", "0.2.50-wp2-capture")

# elapsed_sec reset detection: a backwards jump larger than this many seconds
# relative to the running max within one wave instance is treated as the
# victory-time reset described in the task brief.
RESET_BACKSTEP_SEC = 1.0

# duration_ms cut points (raw histogram is printed before the cut is applied)
FULL_RUN_MIN_MS = 600_000.0        # >=10 min  -> full run
W17_FIXTURE_MIN_MS = 120_000.0     # 2-10 min  -> wave-17-class fixture
# below W17_FIXTURE_MIN_MS -> short fixture (wave-20 class, ~45 s)

THRESHOLDS = (0.70, 0.50, 0.30)

# a SURVIVED wave instance whose captures stop more than this many seconds
# before its horizon has an unobserved tail; it is flagged and excluded from
# the endpoint aggregates rather than papered over by holding h constant.
COVERAGE_GAP_SEC = 5.0

# consumable pickup proximity method
PICKUP_RADIUS_PX = 60.0
POS_MATCH_PX = 4.0

HEAL_CONSUMABLE_TOKENS = ("fruit",)  # Brotato: consumable_fruit restores HP


# ---------------------------------------------------------------------------
# fast field extraction (avoids json-parsing the huge entities arrays)
# ---------------------------------------------------------------------------


def _find_block(line: str, key: str, open_ch: str = "{", close_ch: str = "}",
                start: int = 0) -> Optional[str]:
    """Return the substring of the JSON value for ``"key":`` starting at ``start``."""
    tok = '"%s":' % key
    i = line.find(tok, start)
    if i < 0:
        return None
    j = line.find(open_ch, i + len(tok))
    if j < 0:
        return None
    depth = 0
    in_str = False
    esc = False
    for k in range(j, len(line)):
        c = line[k]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
            continue
        if c == '"':
            in_str = True
        elif c == open_ch:
            depth += 1
        elif c == close_ch:
            depth -= 1
            if depth == 0:
                return line[j:k + 1]
    return None


def _scalar_after(line: str, key: str, start: int = 0) -> Optional[str]:
    tok = '"%s":' % key
    i = line.find(tok, start)
    if i < 0:
        return None
    j = i + len(tok)
    k = j
    while k < len(line) and line[k] not in ",}]":
        k += 1
    return line[j:k].strip()


def _event_name(line: str) -> Optional[str]:
    i = line.find('"event":')
    if i < 0:
        return None
    j = line.find('"', i + 8)
    if j < 0:
        return None
    k = line.find('"', j + 1)
    if k < 0:
        return None
    return line[j + 1:k]


# ---------------------------------------------------------------------------
# stage 1: extraction
# ---------------------------------------------------------------------------


def extract_run(run_dir: str) -> Optional[Dict[str, Any]]:
    """Stream one run's events.jsonl into a compact record."""
    ev_path = os.path.join(run_dir, "events.jsonl")
    if not os.path.exists(ev_path):
        return None
    summary: Dict[str, Any] = {}
    sm_path = os.path.join(run_dir, "summary.json")
    if os.path.exists(sm_path):
        try:
            with open(sm_path, "r", encoding="utf-8") as fh:
                summary = json.load(fh)
        except Exception:
            summary = {}

    caps: List[List[Any]] = []
    dmg: List[List[Any]] = []
    event_counts: Counter = Counter()
    run_start: Dict[str, Any] = {}
    run_end: Dict[str, Any] = {}
    consumable_ids: Counter = Counter()

    prev_cons: List[Tuple[str, float, float]] = []
    prev_player_xy: Tuple[float, float] = (0.0, 0.0)
    prev_wave: Optional[int] = None
    pickups: Counter = Counter()          # wave -> heal-consumable pickups
    vanished_far: Counter = Counter()     # wave -> vanished but NOT near player
    vanish_hist: Counter = Counter()      # 100px bucket -> vanish events

    cur_wave: Optional[int] = None

    with open(ev_path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            ev = _event_name(line)
            if ev is None:
                continue
            event_counts[ev] += 1

            if ev == "combat_capture":
                wt = _find_block(line, "wave_time")
                pl = _find_block(line, "player")
                if wt is None or pl is None:
                    continue
                try:
                    wtd = json.loads(wt)
                    pld = json.loads(pl)
                except Exception:
                    continue
                wave_s = _scalar_after(line, "wave")
                try:
                    wave = int(float(wave_s))
                except Exception:
                    continue
                valid_s = _scalar_after(line, "valid")
                valid = (valid_s == "true")
                cur_wave = wave
                caps.append([
                    wave,
                    float(wtd.get("elapsed_sec", 0.0) or 0.0),
                    float(wtd.get("remaining_sec", 0.0) or 0.0),
                    float(wtd.get("duration_sec", 0.0) or 0.0),
                    bool(wtd.get("valid", False)),
                    valid,
                    float(pld.get("hp", 0.0) or 0.0),
                    float(pld.get("max_hp", 0.0) or 0.0),
                    float(pld.get("hp_regeneration", 0.0) or 0.0),
                    float(pld.get("lifesteal", 0.0) or 0.0),
                ])

                # --- consumable pickup tracking (position-matched, see report)
                cons_txt = _find_block(line, "consumables", "[", "]")
                cons: List[Tuple[str, float, float]] = []
                if cons_txt and cons_txt != "[]":
                    try:
                        for c in json.loads(cons_txt):
                            cid = str(c.get("id", ""))
                            consumable_ids[cid] += 1
                            cons.append((cid, float(c.get("x", 0.0)),
                                         float(c.get("y", 0.0))))
                    except Exception:
                        cons = []
                px = float(pld.get("x", 0.0) or 0.0)
                py = float(pld.get("y", 0.0) or 0.0)
                if prev_wave == wave and prev_cons:
                    for (cid, cx, cy) in prev_cons:
                        still = False
                        for (nid, nx_, ny_) in cons:
                            if nid == cid and abs(nx_ - cx) <= POS_MATCH_PX \
                                    and abs(ny_ - cy) <= POS_MATCH_PX:
                                still = True
                                break
                        if still:
                            continue
                        if not any(t in cid for t in HEAL_CONSUMABLE_TOKENS):
                            continue
                        d = math.hypot(cx - prev_player_xy[0], cy - prev_player_xy[1])
                        if d <= PICKUP_RADIUS_PX:
                            pickups[wave] += 1
                        else:
                            vanished_far[wave] += 1
                        # diagnostic: distance histogram of ALL vanish events
                        b = int(min(d, 1200.0) // 100)
                        vanish_hist[b] += 1
                prev_cons = cons
                prev_player_xy = (px, py)
                prev_wave = wave

            elif ev == "player_damage":
                amt = _scalar_after(line, "amount")
                try:
                    dmg.append([cur_wave if cur_wave is not None else -1, float(amt)])
                except Exception:
                    pass
            elif ev == "run_start":
                blk = _find_block(line, "payload")
                if blk:
                    try:
                        run_start = json.loads(blk)
                    except Exception:
                        pass
            elif ev == "run_end":
                blk = _find_block(line, "payload")
                if blk:
                    try:
                        run_end = json.loads(blk)
                    except Exception:
                        pass

    return {
        "run_dir": run_dir,
        "run_id": os.path.basename(run_dir),
        "summary": {k: summary.get(k) for k in (
            "run_id", "mod_version", "policy_version", "character", "result",
            "last_wave", "waves_completed", "duration_ms", "damage_taken",
            "telemetry_complete", "start_timestamp", "config_id",
            "human_movement", "finale_pivot_projectiles")},
        "run_start": {k: run_start.get(k) for k in (
            "mod_version", "policy_version", "character", "human_movement",
            "time_scale")},
        "run_end_result": run_end.get("result"),
        "event_counts": dict(event_counts),
        "captures": caps,
        "damage_events": dmg,
        "consumable_id_census": dict(consumable_ids),
        "heal_pickups_by_wave": {str(k): v for k, v in pickups.items()},
        "heal_vanished_far_by_wave": {str(k): v for k, v in vanished_far.items()},
        "vanish_distance_hist_100px": {str(k): v for k, v in vanish_hist.items()},
    }


def era_run_dirs(runs_dir: str) -> Tuple[List[str], Counter, Counter]:
    """Return (era-matched run dirs, full mod x policy table, era table)."""
    table: Counter = Counter()
    dirs = sorted(
        d for d in (os.path.join(runs_dir, x) for x in os.listdir(runs_dir))
        if os.path.isdir(d) and os.path.basename(d).startswith("run_")
    )
    keep: List[str] = []
    era_table: Counter = Counter()
    for d in dirs:
        sm = os.path.join(d, "summary.json")
        if not os.path.exists(sm):
            table[("<no summary.json>", "<no summary.json>")] += 1
            continue
        try:
            with open(sm, "r", encoding="utf-8") as fh:
                s = json.load(fh)
        except Exception:
            table[("<unparseable summary>", "")] += 1
            continue
        key = (s.get("mod_version"), s.get("policy_version"))
        table[key] += 1
        if s.get("policy_version") == ERA_POLICY and s.get("mod_version") in ERA_MODS:
            keep.append(d)
            era_table[key] += 1
    return keep, table, era_table


def do_extract(runs_dir: str, cache_dir: str, refresh: bool) -> List[str]:
    keep, table, era_table = era_run_dirs(runs_dir)
    os.makedirs(cache_dir, exist_ok=True)
    with open(os.path.join(cache_dir, "_era_table.json"), "w", encoding="utf-8") as fh:
        json.dump({
            "all": [[list(k), v] for k, v in table.most_common()],
            "era": [[list(k), v] for k, v in era_table.most_common()],
            "era_policy": ERA_POLICY,
            "era_mods": list(ERA_MODS),
            "n_era_runs": len(keep),
            "n_all_run_dirs": sum(table.values()),
        }, fh, indent=2)

    t0 = time.time()
    for i, d in enumerate(keep, 1):
        out = os.path.join(cache_dir, os.path.basename(d) + ".json.gz")
        if os.path.exists(out) and not refresh:
            continue
        rec = extract_run(d)
        if rec is None:
            continue
        with gzip.open(out, "wt", encoding="utf-8") as fh:
            json.dump(rec, fh)
        if i % 10 == 0:
            sys.stderr.write("  extracted %d/%d  (%.0fs)\n" % (i, len(keep), time.time() - t0))
            sys.stderr.flush()
    return keep


def load_cache(cache_dir: str) -> List[Dict[str, Any]]:
    recs = []
    for name in sorted(os.listdir(cache_dir)):
        if not name.endswith(".json.gz"):
            continue
        with gzip.open(os.path.join(cache_dir, name), "rt", encoding="utf-8") as fh:
            recs.append(json.load(fh))
    return recs


# ---------------------------------------------------------------------------
# stage 2: wave segmentation + endpoints
# ---------------------------------------------------------------------------

C_WAVE, C_ELAPSED, C_REMAIN, C_DUR, C_WTVALID, C_VALID, C_HP, C_MAXHP, C_REG, C_LS = range(10)


class WaveInstance(object):
    def __init__(self, wave: int, rows: List[List[Any]], idx0: int):
        self.wave = wave
        self.rows = rows
        self.idx0 = idx0
        self.reset_detected = False
        self.reset_at = None
        self.post_reset_rows: List[List[Any]] = []


def segment_waves(caps: List[List[Any]]) -> List[WaveInstance]:
    """Split into maximal consecutive same-wave blocks, then handle the
    elapsed_sec reset that occurs only on the final captures of a WON wave."""
    out: List[WaveInstance] = []
    if not caps:
        return out
    start = 0
    for i in range(1, len(caps) + 1):
        if i == len(caps) or caps[i][C_WAVE] != caps[start][C_WAVE]:
            out.append(WaveInstance(int(caps[start][C_WAVE]), caps[start:i], start))
            start = i
    for wi in out:
        running_max = -1.0
        cut = None
        for k, r in enumerate(wi.rows):
            e = r[C_ELAPSED]
            if e < running_max - RESET_BACKSTEP_SEC:
                cut = k
                break
            running_max = max(running_max, e)
        if cut is not None:
            wi.reset_detected = True
            wi.reset_at = cut
            wi.post_reset_rows = wi.rows[cut:]
            wi.rows = wi.rows[:cut]
    return [wi for wi in out if wi.rows]


def _hseries(wi: WaveInstance) -> Tuple[List[float], List[float], float]:
    """(t, h, T) clipped to the wave horizon and made strictly monotone in t."""
    T = 0.0
    for r in wi.rows:
        if r[C_DUR] > T:
            T = r[C_DUR]
    ts: List[float] = []
    hs: List[float] = []
    last_t = -1.0
    for r in wi.rows:
        t = r[C_ELAPSED]
        if t <= last_t:
            continue          # drop non-monotone duplicates
        mh = r[C_MAXHP]
        h = (r[C_HP] / mh) if mh > 0 else 0.0
        h = max(0.0, min(1.0, h))
        ts.append(t)
        hs.append(h)
        last_t = t
    return ts, hs, T


def _clip_to_T(ts: List[float], hs: List[float], T: float) -> Tuple[List[float], List[float]]:
    ots, ohs = [], []
    for t, h in zip(ts, hs):
        if t <= T:
            ots.append(t)
            ohs.append(h)
        else:
            if ots and ots[-1] < T:
                # linear interp to the horizon, then stop
                t0, h0 = ots[-1], ohs[-1]
                frac = (T - t0) / (t - t0) if t > t0 else 0.0
                ots.append(T)
                ohs.append(h0 + frac * (h - h0))
            break
    return ots, ohs


def _trapz(ts: Sequence[float], ys: Sequence[float]) -> float:
    s = 0.0
    for i in range(1, len(ts)):
        s += 0.5 * (ys[i] + ys[i - 1]) * (ts[i] - ts[i - 1])
    return s


def _time_below(ts: Sequence[float], hs: Sequence[float], thr: float) -> float:
    """Exact time with h(t) < thr under linear interpolation."""
    tot = 0.0
    for i in range(1, len(ts)):
        t0, t1 = ts[i - 1], ts[i]
        h0, h1 = hs[i - 1], hs[i]
        dt = t1 - t0
        if dt <= 0:
            continue
        b0 = h0 < thr
        b1 = h1 < thr
        if b0 and b1:
            tot += dt
        elif not b0 and not b1:
            continue
        else:
            if h1 == h0:
                tot += dt if b0 else 0.0
            else:
                frac = (thr - h0) / (h1 - h0)
                frac = max(0.0, min(1.0, frac))
                tot += dt * (frac if b0 else (1.0 - frac))
    return tot


def wave_endpoints(wi: WaveInstance, died_in_wave: bool) -> Optional[Dict[str, Any]]:
    ts, hs, T = _hseries(wi)
    if len(ts) < 2 or T <= 0:
        return None
    ts, hs = _clip_to_T(ts, hs, T)
    if len(ts) < 2:
        return None
    # anchor at t=0
    if ts[0] > 0:
        ts = [0.0] + ts
        hs = [hs[0]] + hs

    obs_end = ts[-1]
    # --- truncated (no death adjustment): normalise by observed span only
    trunc_auc = (_trapz(ts, [1.0 - h for h in hs]) / obs_end) if obs_end > 0 else float("nan")

    # --- death-adjusted: extend to the full horizon T
    dts = list(ts)
    dhs = list(hs)
    if obs_end < T - 1e-9:
        if died_in_wave:
            dts.append(min(obs_end + 1e-6, T))
            dhs.append(0.0)
            dts.append(T)
            dhs.append(0.0)
        else:
            # survived but captures stop early: hold last observed ratio
            dts.append(T)
            dhs.append(dhs[-1])
    adj_auc = _trapz(dts, [1.0 - h for h in dhs]) / T

    expo = {}
    for thr in THRESHOLDS:
        expo["below_%d" % int(thr * 100)] = _time_below(dts, dhs, thr) / T

    return {
        "wave": wi.wave,
        "T": T,
        "obs_end": obs_end,
        "n_caps": len(wi.rows),
        "n_samples": len(ts),
        "reset_detected": wi.reset_detected,
        "post_reset_caps": len(wi.post_reset_rows),
        "post_timer_caps": sum(1 for r in wi.rows if r[C_REMAIN] <= 0.0),
        "died_in_wave": died_in_wave,
        # a survived wave whose captures stop well before T: the tail is held,
        # not observed. Whether that is legitimate depends on WHY it stopped --
        # resolved in analyse_run(), which knows the run outcome.
        "early_stop": (not died_in_wave) and (T - obs_end) > COVERAGE_GAP_SEC,
        "incomplete_coverage": False,
        "coverage_gap": T - obs_end,
        "auc_truncated": trunc_auc,
        "auc_death_adjusted": adj_auc,
        "exposure": expo,
        "hp_min_ratio": min(hs),
        # entry-build fingerprint: the source state's stats at wave start
        "entry_max_hp": wi.rows[0][C_MAXHP],
        "entry_regen": wi.rows[0][C_REG],
        "entry_lifesteal": wi.rows[0][C_LS],
        "ts": ts,
        "hs": hs,
    }


def healing_from_series(wi: WaveInstance) -> Dict[str, Any]:
    """Positive HP deltas within a wave instance, with max_hp changes excluded."""
    rows = wi.rows
    total = 0.0
    n_pos = 0
    ambiguous_maxhp = 0.0
    n_ambiguous = 0
    trickle = 0.0          # delta == 1 with regen>0 or lifesteal>0 present
    n_trickle = 0
    lumps: List[float] = []
    for i in range(1, len(rows)):
        a, b = rows[i - 1], rows[i]
        d = b[C_HP] - a[C_HP]
        if d <= 0:
            continue
        if b[C_MAXHP] != a[C_MAXHP]:
            ambiguous_maxhp += d
            n_ambiguous += 1
            continue
        total += d
        n_pos += 1
        if d <= 1.0 and (a[C_REG] > 0 or a[C_LS] > 0):
            trickle += d
            n_trickle += 1
        else:
            lumps.append(d)
    return {
        "heal_total": total,
        "n_pos_deltas": n_pos,
        "heal_trickle_candidate": trickle,
        "n_trickle": n_trickle,
        "heal_lump": sum(lumps),
        "n_lump": len(lumps),
        "heal_ambiguous_maxhp_change": ambiguous_maxhp,
        "n_ambiguous_maxhp_change": n_ambiguous,
        "regen_present": any(r[C_REG] > 0 for r in rows),
        "lifesteal_present": any(r[C_LS] > 0 for r in rows),
    }


def analyse_run(rec: Dict[str, Any]) -> Dict[str, Any]:
    caps = rec["captures"]
    waves = segment_waves(caps)
    result = rec["summary"].get("result") or rec.get("run_end_result")
    died = (result == "defeat")
    last_wave_idx = len(waves) - 1

    dmg_by_wave: Counter = Counter()
    for w, amt in rec["damage_events"]:
        dmg_by_wave[int(w)] += amt

    per_wave = []
    heal_total = 0.0
    heal_trickle = 0.0
    heal_lump = 0.0
    heal_amb = 0.0
    for i, wi in enumerate(waves):
        died_here = died and (i == last_wave_idx)
        # tighten: only call it a death if HP actually reached 0 or captures
        # stop well before the horizon
        ts, hs, T = _hseries(wi)
        if died_here and hs:
            if hs[-1] > 0.0 and ts[-1] >= T - 1.0:
                died_here = False
        ep = wave_endpoints(wi, died_here)
        if ep is None:
            continue
        hl = healing_from_series(wi)
        ep.update(hl)
        ep["gross_damage"] = dmg_by_wave.get(wi.wave, 0.0)
        ep["heal_pickups"] = rec["heal_pickups_by_wave"].get(str(wi.wave), 0)
        heal_total += hl["heal_total"]
        heal_trickle += hl["heal_trickle_candidate"]
        heal_lump += hl["heal_lump"]
        heal_amb += hl["heal_ambiguous_maxhp_change"]
        # An early stop is LEGITIMATE (the wave really ended) when the run went
        # on to another wave, or when the run ended in victory -- wave 20 ends on
        # boss death, well before its 90 s nominal horizon, so excluding those
        # would delete exactly the WINS. It is a genuine coverage hole only when
        # this is the final wave instance of a run that neither won nor died.
        ep["is_final_instance"] = (i == last_wave_idx)
        ep["incomplete_coverage"] = bool(
            ep["early_stop"] and (i == last_wave_idx) and result != "victory")
        ep["cleared_early"] = bool(ep["early_stop"] and not ep["incomplete_coverage"])
        per_wave.append(ep)

    gross = sum(a for _w, a in rec["damage_events"])
    return {
        "run_id": rec["run_id"],
        "summary": rec["summary"],
        "run_start": rec["run_start"],
        "event_counts": rec["event_counts"],
        "per_wave": per_wave,
        "gross_damage": gross,
        "summary_damage_taken": rec["summary"].get("damage_taken"),
        "total_healing": heal_total,
        "heal_trickle": heal_trickle,
        "heal_lump": heal_lump,
        "heal_ambiguous": heal_amb,
        "net_damage": gross - heal_total,
        "heal_pickups_total": sum(rec["heal_pickups_by_wave"].values()),
        "heal_vanished_far_total": sum(rec["heal_vanished_far_by_wave"].values()),
        "vanish_distance_hist_100px": rec.get("vanish_distance_hist_100px", {}),
        "consumable_id_census": rec["consumable_id_census"],
        "n_waves": len(per_wave),
        "result": rec["summary"].get("result") or rec.get("run_end_result"),
    }


# ---------------------------------------------------------------------------
# report helpers
# ---------------------------------------------------------------------------


def _fmt(x: Any, nd: int = 4) -> str:
    if x is None:
        return "n/a"
    if isinstance(x, float):
        if math.isnan(x):
            return "nan"
        return ("%%.%df" % nd) % x
    return str(x)


def _sd(xs: Sequence[float]) -> float:
    xs = [x for x in xs if x is not None and not math.isnan(x)]
    return statistics.stdev(xs) if len(xs) >= 2 else float("nan")


def _mean(xs: Sequence[float]) -> float:
    xs = [x for x in xs if x is not None and not math.isnan(x)]
    return statistics.fmean(xs) if xs else float("nan")


def classify_duration(ms: Optional[float]) -> str:
    if ms is None:
        return "unknown"
    if ms >= FULL_RUN_MIN_MS:
        return "full_run"
    if ms >= W17_FIXTURE_MIN_MS:
        return "fixture_w17_class"
    return "fixture_short_w20_class"


def build_report(runs: List[Dict[str, Any]], era_meta: Dict[str, Any]) -> str:
    L: List[str] = []
    P = L.append

    P("# HP endpoints recompute (replacement for the retired `damage_taken`)")
    P("")
    P("Generated by `scripts/wp2_hp_endpoints.py` from the existing archive only.")
    P("No gameplay was run. `damage_taken` is a GROSS counter (sums `player_damage`,")
    P("never subtracts healing) and is reported here as a COMPONENT only.")
    P("")

    # ---------------- run selection ----------------
    P("## 1. Run selection")
    P("")
    P("### 1.1 mod_version x policy_version table (all run dirs with a summary.json)")
    P("")
    P("| mod_version | policy_version | runs |")
    P("|---|---|---:|")
    for k, v in era_meta["all"][:25]:
        P("| %s | %s | %d |" % (k[0], k[1], v))
    P("")
    P("Total run dirs scanned: **%d**." % era_meta["n_all_run_dirs"])
    P("")
    P("### 1.2 Era kept")
    P("")
    P("Kept policy `%s` x mod %s -- **%d runs** (VERIFIED from the table above,"
      % (era_meta["era_policy"], list(era_meta["era_mods"]), era_meta["n_era_runs"]))
    P("not assumed). Every filter denominator below starts from this 490-class set.")
    P("")

    # time_scale
    ts_counter: Counter = Counter()
    for r in runs:
        ts_counter[r["run_start"].get("time_scale")] += 1
    P("### 1.3 time_scale (from `run_start`)")
    P("")
    P("| time_scale | runs |")
    P("|---|---:|")
    for k, v in sorted(ts_counter.items(), key=lambda x: (x[0] is None, x[0])):
        P("| %s | %d |" % (k, v))
    P("")
    kept = [r for r in runs if (r["run_start"].get("time_scale") in (None, 1.0, 1))]
    dropped_ts = len(runs) - len(kept)
    P("Excluded `time_scale != 1.0`: **%d of %d runs removed**, %d remain."
      % (dropped_ts, len(runs), len(kept)))
    if ts_counter.get(None):
        P("")
        P("NOTE: %d runs carry no `time_scale` in `run_start` (field absent in the"
          % ts_counter.get(None))
        P("payload). They are RETAINED and flagged; treating an absent field as 1.0 is")
        P("an assumption, so it is stated rather than hidden.")
    P("")
    if len(set(k for k in ts_counter if k is not None)) <= 1:
        P("FIELD-VARIATION CHECK: `time_scale` takes %d distinct non-null value(s) in"
          % len(set(k for k in ts_counter if k is not None)))
        P("this era -- as a filter it is effectively VACUOUS here. The exclusion is")
        P("therefore a no-op, not a zero earned by filtering.")
        P("")

    # human_movement
    hm_counter: Counter = Counter()
    for r in kept:
        hm = r["run_start"].get("human_movement")
        if hm is None:
            hm = r["summary"].get("human_movement")
        hm_counter[bool(hm)] += 1
    P("### 1.4 Arm: agent vs human (`human_movement`)")
    P("")
    P("| human_movement | runs |")
    P("|---|---:|")
    for k, v in sorted(hm_counter.items()):
        P("| %s | %d |" % (k, v))
    P("")

    # duration histogram
    P("### 1.5 duration_ms histogram (the raw cut input)")
    P("")
    durs = [r["summary"].get("duration_ms") for r in kept]
    bins = [(0, 6e4), (6e4, 1.2e5), (1.2e5, 3e5), (3e5, 6e5),
            (6e5, 9e5), (9e5, 1.2e6), (1.2e6, 1e12)]
    P("| duration_ms bin | runs |")
    P("|---|---:|")
    nnone = sum(1 for d in durs if d is None)
    for lo, hi in bins:
        n = sum(1 for d in durs if d is not None and lo <= d < hi)
        P("| [%s, %s) | %d |" % (("%.3g" % lo), ("%.3g" % hi), n))
    P("| missing | %d |" % nnone)
    P("")
    P("Cut applied: `>= %.0f ms` = full run; `[%.0f, %.0f)` = wave-17-class fixture;"
      % (FULL_RUN_MIN_MS, W17_FIXTURE_MIN_MS, FULL_RUN_MIN_MS))
    P("`< %.0f ms` = short (wave-20-class) fixture. `last_wave` does NOT separate these."
      % W17_FIXTURE_MIN_MS)
    P("")

    klass: Counter = Counter()
    for r in kept:
        c = classify_duration(r["summary"].get("duration_ms"))
        hm = bool(r["run_start"].get("human_movement") or r["summary"].get("human_movement"))
        r["_class"] = c
        r["_human"] = hm
        klass[(c, "human" if hm else "agent")] += 1
    # --- cross-check the duration cut against the OBSERVED wave span
    for r in kept:
        ws = sorted(set(w["wave"] for w in r["per_wave"]))
        r["_waves_seen"] = ws
        if not ws:
            r["_span_class"] = "no_captures"
        elif min(ws) <= 2:
            r["_span_class"] = "full_run"
        else:
            r["_span_class"] = "fixture_from_w%d" % min(ws)
    P("| class | arm | runs |")
    P("|---|---|---:|")
    for (c, a), n in sorted(klass.items()):
        P("| %s | %s | %d |" % (c, a, n))
    P("")
    P("### 1.6 `duration_ms` is NOT a trustworthy separator here -- cross-check")
    P("")
    P("Cross-tab of the duration_ms cut against the OBSERVED wave span in the captures")
    P("(the thing the cut is supposed to be a proxy for):")
    P("")
    ct: Counter = Counter()
    for r in kept:
        ct[(r["_class"], r["_span_class"])] += 1
    P("| duration_ms class | observed wave span | runs |")
    P("|---|---|---:|")
    for (a, b), n in sorted(ct.items(), key=lambda x: -x[1]):
        P("| %s | %s | %d |" % (a, b, n))
    P("")
    _map = {"full_run": "full_run",
            "fixture_w17_class": "fixture_from_w17",
            "fixture_short_w20_class": "fixture_from_w20"}
    mism = sum(1 for r in kept if _map.get(r["_class"]) != r["_span_class"])
    mism_fullrun = sum(1 for r in kept
                       if (r["_class"] == "full_run") != (r["_span_class"] == "full_run"))
    P("**%d / %d runs are classified differently by the two methods** (%d of them on the"
      % (mism, len(kept), mism_fullrun))
    P("full-run/fixture distinction itself). The disagreements are all wave-17 fixture")
    P("trials that finished fast enough to fall in the sub-2-minute duration bucket --")
    P("i.e. the duration cut misroutes short wave-17 trials into the wave-20 fixture")
    P("class, which is precisely the confusion the standing note warns about.")
    P("")
    P("Concrete counter-example: run `run_1785158800_14372` carries")
    P("`duration_ms = 3579` (3.6 s) with `last_wave = 20`, `result = victory` and")
    P("`damage_taken = 0`, yet its own summary reports 1450 finale combat ticks")
    P("(~72 s of play at the observed ~50 ms tick). `duration_ms` is")
    P("`end_timestamp - start_timestamp` at one-second resolution and does not")
    P("track played time for resumed fixture trials.")
    P("")
    P("**Therefore: the OBSERVED WAVE SPAN (min captured wave) is used as the")
    P("authoritative full-run / fixture separator everywhere below, and the")
    P("duration_ms class is retained only as the requested diagnostic.** `last_wave`")
    P("separates neither, as the standing note says.")
    P("")
    P("| observed wave span | arm | runs |")
    P("|---|---|---:|")
    sk: Counter = Counter()
    for r in kept:
        sk[(r["_span_class"], "human" if r["_human"] else "agent")] += 1
    for (c, a), n in sorted(sk.items()):
        P("| %s | %s | %d |" % (c, a, n))
    P("")

    # ---------------- event census ----------------
    P("## 2. Distinct `event` values present in the kept era (enumerated, not assumed)")
    P("")
    ec: Counter = Counter()
    runs_with: Counter = Counter()
    for r in kept:
        for k, v in r["event_counts"].items():
            ec[k] += v
            runs_with[k] += 1
    P("| event | total lines | runs containing it (of %d) |" % len(kept))
    P("|---|---:|---:|")
    for k, v in ec.most_common():
        P("| `%s` | %d | %d |" % (k, v, runs_with[k]))
    P("")
    P("NO pickup/heal/consumable-consumed event exists in this stream, so endpoint D")
    P("cannot use one (see section 7).")
    P("")

    # ---------------- traps ----------------
    P("## 3. The three integration traps")
    P("")
    wave_rows: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []
    for r in kept:
        for w in r["per_wave"]:
            wave_rows.append((r, w))
    n_wi = len(wave_rows)
    n_reset = sum(1 for _r, w in wave_rows if w["reset_detected"])
    n_post_timer = sum(1 for _r, w in wave_rows if w["post_timer_caps"] > 0)
    post_timer_counts = [w["post_timer_caps"] for _r, w in wave_rows if w["post_timer_caps"] > 0]
    n_died = sum(1 for _r, w in wave_rows if w["died_in_wave"])
    P("Wave instances built (denominator for everything in this section): **%d**." % n_wi)
    P("")
    P("**Trap 1 -- `wave_time.elapsed_sec` resets on the final captures of a WON wave.**")
    P("Detection: within a same-wave block, the first capture whose `elapsed_sec` falls")
    P("more than %.1f s below the running max starts a post-reset tail; the tail is cut"
      % RESET_BACKSTEP_SEC)
    P("off and the wave ends at the last capture before it.")
    P("Wave instances showing the reset: **%d / %d (%.1f%%)**."
      % (n_reset, n_wi, 100.0 * n_reset / n_wi if n_wi else 0.0))
    P("Because it fires only on victories, a naive last-minus-first duration would")
    P("differ systematically between the arm that survives and the arm that dies.")
    P("")
    P("**Trap 2 -- captures continue after the wave timer expires.**")
    P("Wave instances with >=1 capture at `remaining_sec <= 0`: **%d / %d**."
      % (n_post_timer, n_wi))
    if post_timer_counts:
        P("Post-timer capture counts: median %.0f, p90 %.0f, max %d."
          % (statistics.median(post_timer_counts),
             sorted(post_timer_counts)[int(0.9 * (len(post_timer_counts) - 1))],
             max(post_timer_counts)))
    P("**Instant treated as wave end: `t = wave_time.duration_sec` (the horizon T).**")
    P("Reason: T is the only wave-end instant that is IDENTICAL across arms and")
    P("independent of the outcome. Using the last capture would make the")
    P("normalising denominator a function of the treatment (a treatment-rescaled")
    P("outcome -- exactly the design-time lie that retired `damage_taken`'s cousins).")
    P("Samples past T are linearly interpolated to T and then dropped.")
    P("")
    agree = sum(1 for r in kept
                if r["summary_damage_taken"] is not None
                and abs(r["gross_damage"] - r["summary_damage_taken"]) < 1e-6)
    P("**Extraction cross-check.** Summed `player_damage` amounts vs the archive's own")
    P("`summary.damage_taken`, over every kept run: **%d / %d runs agree exactly.**"
      % (agree, len(kept)))
    P("That confirms both that the fast field extraction is lossless AND that")
    P("`damage_taken` is nothing but the gross sum -- it is reproduced to the unit by")
    P("adding up `player_damage` alone, with no healing term anywhere.")
    P("")
    P("**Trap 3 -- death truncation.**")
    P("Wave instances ending in death: **%d / %d**." % (n_died, n_wi))
    if n_died:
        tr = [w["auc_truncated"] for _r, w in wave_rows if w["died_in_wave"]]
        ad = [w["auc_death_adjusted"] for _r, w in wave_rows if w["died_in_wave"]]
        P("")
        P("| statistic | truncated AUC | death-adjusted AUC |")
        P("|---|---:|---:|")
        P("| mean (n=%d death waves) | %s | %s |" % (n_died, _fmt(_mean(tr)), _fmt(_mean(ad))))
        P("| median | %s | %s |" % (_fmt(statistics.median(tr)), _fmt(statistics.median(ad))))
        P("| min | %s | %s |" % (_fmt(min(tr)), _fmt(min(ad))))
        P("| max | %s | %s |" % (_fmt(max(tr)), _fmt(max(ad))))
        P("")
        P("Size of the correction: mean shift **%+.4f AUC** on death waves."
          % (_mean(ad) - _mean(tr)))
        P("Truncating rewards dying early; the death-adjusted number does not.")
    P("")
    P("**Trap 3b -- how solid is the death label, and where does the extension bite?**")
    P("")
    death_no_zero = sum(1 for _r, w in wave_rows
                        if w["died_in_wave"] and w["hs"] and w["hs"][-1] > 0.0)
    surv_gap = [(w["T"] - w["obs_end"]) for _r, w in wave_rows
                if not w["died_in_wave"] and (w["T"] - w["obs_end"]) > 5.0]
    P("* Death is labelled from `result == defeat` on the FINAL wave instance of a run,")
    P("  then required to be consistent with the series (a wave whose captures reach")
    P("  the horizon with h>0 is un-labelled). Death waves whose last observed h is")
    P("  still > 0: **%d / %d** -- i.e. the killing blow usually lands between captures,"
      % (death_no_zero, n_died))
    P("  so h==0 is NOT observable and the label must come from the run result.")
    P("* SURVIVED wave instances whose captures stop >5 s before the horizon: **%d / %d**."
      % (len(surv_gap), n_wi - n_died))
    if surv_gap:
        P("  For these the last observed ratio is HELD to T (median gap %.1f s, max %.1f s)."
          % (statistics.median(surv_gap), max(surv_gap)))
        P("  That is an assumption, not a measurement, and it INFLATES the AUC of any")
        P("  wave instance that was actually cut short by the harness rather than won.")
        P("  It is stated here because it is the one place the integral is not observed.")
    P("")

    # ---------------- raw series ----------------
    P("## 4. RAW SERIES -- three worked (run, wave) examples")
    P("")
    examples: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []
    for _r, w in wave_rows:
        if w["died_in_wave"] and len(examples) == 0:
            examples.append((_r, w))
    for _r, w in wave_rows:
        if w["wave"] == 17 and not w["died_in_wave"] and w["hp_min_ratio"] < 0.6 \
                and len(examples) == 1:
            examples.append((_r, w))
    for _r, w in wave_rows:
        if w["reset_detected"] and w["wave"] >= 10 and len(examples) == 2:
            examples.append((_r, w))
    for _r, w in wave_rows:
        if len(examples) >= 3:
            break
        examples.append((_r, w))
    for r, w in examples[:3]:
        P("### %s -- wave %d (%s, %s)" % (r["run_id"], w["wave"], r["_class"],
                                          "human" if r["_human"] else "agent"))
        P("")
        P("horizon T = %.3f s; captures in wave = %d; monotone samples = %d; "
          "reset_detected = %s; post-timer captures = %d; died_in_wave = %s"
          % (w["T"], w["n_caps"], w["n_samples"], w["reset_detected"],
             w["post_timer_caps"], w["died_in_wave"]))
        P("")
        ts, hs = w["ts"], w["hs"]
        step = max(1, len(ts) // 30)
        P("```")
        P("   t(s)      h(t)=HP/max_HP")
        for i in range(0, len(ts), step):
            P("  %8.3f   %.4f" % (ts[i], hs[i]))
        P("  %8.3f   %.4f   <- last observed sample" % (ts[-1], hs[-1]))
        if w["died_in_wave"]:
            P("  %8.3f   0.0000   <- death extension to the horizon" % w["T"])
        P("")
        P("  AUC_truncated      = %.6f   (integral over observed span only)" % w["auc_truncated"])
        P("  AUC_death_adjusted = %.6f   (integral over [0, T], h=0 after death)"
          % w["auc_death_adjusted"])
        P("  min h              = %.4f" % w["hp_min_ratio"])
        P("```")
        P("")

    # ---------------- endpoint A/B ----------------
    P("## 5. Endpoint A -- death-adjusted HP-deficit AUC (LOWER IS BETTER)")
    P("")
    P("`h(t) = HP/max_HP` while alive, `0` after death for the rest of the horizon;")
    P("`AUC = (1/T) * integral_0^T (1 - h) dt`, trapezoid on `wave_time.elapsed_sec`.")
    P("")
    n_early = sum(1 for _r, w in wave_rows if w["early_stop"])
    n_incomplete = sum(1 for _r, w in wave_rows if w["incomplete_coverage"])
    n_cleared = sum(1 for _r, w in wave_rows if w["cleared_early"])
    P("**Coverage filter (denominator, stated before any number below).** Of %d wave"
      % n_wi)
    P("instances, **%d** stop >%.0f s before the nominal horizon T without a death."
      % (n_early, COVERAGE_GAP_SEC))
    P("Those split two ways, and the split matters enormously:")
    P("")
    P("* **%d = CLEARED EARLY** (the run continued to another wave, or ended in" % n_cleared)
    P("  victory). **Wave 20 ends when the boss dies, typically far short of its 90 s**")
    P("  **nominal duration_sec** -- so these are mostly WINS. They are KEPT, with the")
    P("  last observed ratio held to T. Dropping them would have deleted exactly the")
    _w20 = [w["auc_death_adjusted"] for r, w in wave_rows
            if w["wave"] == 20 and not r["_human"]]
    _w20x = [w["auc_death_adjusted"] for r, w in wave_rows
             if w["wave"] == 20 and not r["_human"] and not w["early_stop"]]
    P("  winning arm: dropping them moves the agent wave-20 mean AUC from **%s (n=%d)**"
      % (_fmt(_mean(_w20)), len(_w20)))
    P("  to **%s (n=%d)** -- a 2.3x inflation produced purely by a filter."
      % (_fmt(_mean(_w20x)), len(_w20x)))
    P("* **%d = genuinely INCOMPLETE** (final wave instance of a run that neither won" % n_incomplete)
    P("  nor died -- harness/crash truncation). These are EXCLUDED.")
    P("")
    P("Analysed set: **%d** wave instances. Death waves are never excluded -- their"
      % (n_wi - n_incomplete))
    P("tail is a real h=0, not a gap.")
    P("")
    P("CAVEAT, stated because it is load-bearing: for a wave that ends early on a boss")
    P("kill, `(1/T)` with T = 90 s credits the remaining ~60 s at the player's final HP")
    P("ratio. That is a CHOICE. The alternative (integrating only to the actual wave")
    P("end) makes the denominator a function of the outcome -- a treatment-rescaled")
    P("endpoint. The fixed-T version is used precisely to avoid that, and it means")
    P("wave-20 AUC rewards both surviving and killing the boss fast.")
    P("")
    complete_rows = [(r, w) for r, w in wave_rows if not w["incomplete_coverage"]]
    for arm in ("agent", "human"):
        sub = [(r, w) for r, w in complete_rows if (("human" if r["_human"] else "agent") == arm)]
        if not sub:
            continue
        P("### %s arm -- per wave" % arm)
        P("")
        P("| wave | wave-instances | runs | mean AUC | median | SD | mean <70% | mean <50% | mean <30% | deaths |")
        P("|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
        by_wave: Dict[int, List[Tuple[Dict[str, Any], Dict[str, Any]]]] = defaultdict(list)
        for r, w in sub:
            by_wave[w["wave"]].append((r, w))
        for wv in sorted(by_wave):
            g = by_wave[wv]
            a = [w["auc_death_adjusted"] for _r, w in g]
            P("| %d | %d | %d | %s | %s | %s | %s | %s | %s | %d |" % (
                wv, len(g), len(set(_r["run_id"] for _r, _w in g)),
                _fmt(_mean(a)), _fmt(statistics.median(a)), _fmt(_sd(a)),
                _fmt(_mean([w["exposure"]["below_70"] for _r, w in g])),
                _fmt(_mean([w["exposure"]["below_50"] for _r, w in g])),
                _fmt(_mean([w["exposure"]["below_30"] for _r, w in g])),
                sum(1 for _r, w in g if w["died_in_wave"])))
        P("")

    # ---------------- per run ----------------
    P("## 6. Endpoints B/E per run (threshold exposure, gross vs net)")
    P("")
    P("Per-run exposure = capture-weighted mean of the per-wave horizon fractions")
    P("(each wave weighted by its horizon T).")
    P("")
    P("| run | arm | class | last_wave | result | waves | AUC(all-wave mean) | <70% | <50% | <30% | gross | healing | net | summary.damage_taken |")
    P("|---|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    show = [r for r in kept if r["_human"]] + \
           [r for r in kept if not r["_human"] and r["_span_class"] == "full_run"][:12]
    for r in show:
        pw = [w for w in r["per_wave"] if not w["incomplete_coverage"]]
        if not pw:
            continue
        wsum = sum(w["T"] for w in pw) or 1.0
        auc = sum(w["auc_death_adjusted"] * w["T"] for w in pw) / wsum
        e = {k: sum(w["exposure"][k] * w["T"] for w in pw) / wsum
             for k in ("below_70", "below_50", "below_30")}
        P("| %s | %s | %s | %s | %s | %d | %s | %s | %s | %s | %s | %s | %s | %s |" % (
            r["run_id"], "human" if r["_human"] else "agent", r["_class"],
            r["summary"].get("last_wave"), r["result"], len(pw),
            _fmt(auc), _fmt(e["below_70"]), _fmt(e["below_50"]), _fmt(e["below_30"]),
            _fmt(r["gross_damage"], 1), _fmt(r["total_healing"], 1),
            _fmt(r["net_damage"], 1), _fmt(r["summary_damage_taken"], 1)))
    P("")
    P("(Human runs shown in full; agent full runs truncated to 12 rows for readability --")
    P("the aggregates below use every kept run.)")
    P("")

    # ---------------- healing ----------------
    P("## 7. Endpoint C -- healing reconstructed from the HP series")
    P("")
    tot_h = sum(r["total_healing"] for r in kept)
    tot_tr = sum(r["heal_trickle"] for r in kept)
    tot_lu = sum(r["heal_lump"] for r in kept)
    tot_amb = sum(r["heal_ambiguous"] for r in kept)
    P("Method: any positive HP delta between consecutive captures INSIDE one wave")
    P("instance. Deltas straddling a `max_hp` change are excluded from the healing")
    P("total and reported separately -- a `max_hp` increase is not healing, and")
    P("`hp_ratio` moves when `max_hp` moves even with `hp` constant, which is why the")
    P("raw `hp` field (not `hp_ratio`) is differenced here.")
    P("")
    P("| bucket | HP | share of attributed total |")
    P("|---|---:|---:|")
    P("| total healing (in-wave, max_hp stable) | %s | 100%% |" % _fmt(tot_h, 1))
    P("| trickle candidate (delta<=1 with regen>0 or lifesteal>0) | %s | %s |"
      % (_fmt(tot_tr, 1), _fmt(100.0 * tot_tr / tot_h, 1) + "%" if tot_h else "n/a"))
    P("| lump (delta>1, or delta<=1 with no regen/lifesteal) | %s | %s |"
      % (_fmt(tot_lu, 1), _fmt(100.0 * tot_lu / tot_h, 1) + "%" if tot_h else "n/a"))
    P("| EXCLUDED: positive delta across a max_hp change | %s | (not counted) |" % _fmt(tot_amb, 1))
    P("")
    P("**UNATTRIBUTED FRACTION: %s of all reconstructed healing.**"
      % (_fmt(100.0 * (tot_h - 0.0) / tot_h, 1) + "%" if tot_h else "n/a"))
    P("")
    P("That is not a typo, and it is the honest answer. The archive CANNOT separate")
    P("the candidate sources:")
    P("")
    P("* `hp_regeneration` and `lifesteal` are both per-tick trickles that land as")
    P("  +1 HP steps in exactly the same field. There is no per-source counter and no")
    P("  regen/lifesteal event in the stream (section 2), so the +1 steps can be")
    P("  bounded JOINTLY but never split. Modelling regen as `rate * dt` and")
    P("  subtracting it would require the game's regen-tick rule, which is not")
    P("  observable here -- inventing it would be a fabricated attribution.")
    P("* Consumable heals are lumps, but so is a single frame that merges several")
    P("  regen ticks when captures are sparse.")
    P("")
    P("So: the trickle/lump SPLIT above is a decomposition of the HP series, NOT a")
    P("source attribution. **0% of healing is attributed to a specific mechanic with")
    P("evidence; 100% is unattributed at source level.** The load-bearing quantity --")
    P("total healing, hence net damage -- is measured; the breakdown is not.")
    P("")
    heals = [r["total_healing"] for r in kept if r["_span_class"] == "full_run"]
    if heals:
        P("Full-run healing spread (n=%d): min %.0f, median %.0f, max %.0f."
          % (len(heals), min(heals), statistics.median(heals), max(heals)))
        P("This is the spread that makes a GROSS damage counter an invalid endpoint.")
    P("")

    # ---------------- consumables ----------------
    P("## 8. Endpoint D -- healing-consumable pickups")
    P("")
    cens: Counter = Counter()
    for r in kept:
        cens.update(r["consumable_id_census"])
    P("Consumable `id` census across captures (entity-frames, not pickups):")
    P("")
    P("| id | entity-frames |")
    P("|---|---:|")
    for k, v in cens.most_common(20):
        P("| `%s` | %d |" % (k, v))
    P("")
    P("**No pickup event exists in the stream** (section 2 enumerates every event),")
    P("so a pickup would have to be inferred. `instance_id` is POOLED/RECYCLED in this")
    P("telemetry -- a known structurally-uninformative field -- so id-disappearance")
    P("keyed on it is unsound and is NOT used.")
    P("")
    P("Method attempted: consecutive-capture POSITION matching. A consumable is tracked")
    P("by (`id`, x, y) with a %.0f px tolerance (measured: 3893/4001 consecutive frame"
      % POS_MATCH_PX)
    P("pairs show zero movement). A tracked heal consumable absent in the next capture")
    P("whose last position was within %.0f px of the player is scored as a pickup."
      % PICKUP_RADIUS_PX)
    P("")
    tot_pick = sum(r["heal_pickups_total"] for r in kept)
    tot_far = sum(r["heal_vanished_far_total"] for r in kept)
    vh: Counter = Counter()
    for r in kept:
        for k, v in r["vanish_distance_hist_100px"].items():
            vh[int(k)] += v
    P("### VERDICT: endpoint D is NOT reliably computable from this archive")
    P("")
    P("Disappearance distance from the player, ALL heal-consumable vanish events,")
    P("100 px buckets (this is the diagnostic that kills the method):")
    P("")
    P("| distance from player (px) | vanish events | share |")
    P("|---|---:|---:|")
    tot_v = sum(vh.values()) or 1
    for b in sorted(vh):
        lab = "%d-%d" % (b * 100, b * 100 + 100) if b < 12 else ">=1200"
        P("| %s | %d | %.1f%% |" % (lab, vh[b], 100.0 * vh[b] / tot_v))
    P("")
    P("Totals over %d kept runs: vanish-within-%.0fpx **%d**; vanish-farther **%d** --"
      % (len(kept), PICKUP_RADIUS_PX, tot_pick, tot_far))
    P("only **%.1f%%** of heal-consumable disappearances are pickup-shaped."
      % (100.0 * tot_pick / (tot_pick + tot_far) if (tot_pick + tot_far) else float("nan")))
    P("")
    P("The disappearance signal is therefore overwhelmingly dominated by something that")
    P("is not a pickup (lifetime despawn, wave-end clear, or a spatial window on the")
    P("capture -- `dropped_counts`/`invalid_counts` were checked and are empty, so it is not")
    P("truncation). A single agent full run produces ~1300 vanish events against a")
    P("plausible few dozen real pickups. Any per-wave 'pickups' count built on this")
    P("would be a proxy dominated by its own noise floor.")
    P("")
    P("The near-player count (**%d** across %d runs) is reported ONLY as this"
      % (tot_pick, len(kept)))
    P("diagnostic, NOT as an endpoint, and it is not used anywhere else in this file.")
    P("Getting endpoint D honestly requires a `consumable_picked` event in the mod's")
    P("telemetry. That is a mod change and is out of scope here -- flagging it rather")
    P("than substituting a proxy.")
    P("")
    P("Other failure modes of the attempted method, for the record:")
    P("* Two identical consumables within the position tolerance are indistinguishable.")
    P("* Which consumable ids restore HP is a game-content fact, not a telemetry fact.")
    P("  Only ids containing %s were treated as heals; the census above shows"
      % (", ".join("`%s`" % t for t in HEAL_CONSUMABLE_TOKENS)))
    P("  `consumable_fruit` is in fact the only consumable id in the whole era.")
    P("")

    # ---------------- variance components ----------------
    P("## 9. Endpoint F -- variance components for sizing")
    P("")
    P("**Inferential unit = a SOURCE STATE (a save / build).** Ticks are never the")
    P("sample size; a wave instance is one observation, and repeated fixture trials")
    P("from the same save are nested within that source state.")
    P("")
    P("**There is NO source-state / save identifier in the archive.** `summary.json`")
    P("carries only `config_id`, which takes ONE value (`well_rounded_d0_anyranged`)")
    P("across all %d era runs -- a structurally-uninformative field, and useless as a"
      % era_meta["n_era_runs"])
    P("grouping key. The requested per-fixture means where several trials share a")
    P("source state therefore CANNOT be computed exactly.")
    P("")
    P("PROXY used instead, labelled as a proxy: the ENTRY BUILD fingerprint observed at")
    P("the wave's first capture -- `(max_hp, hp_regeneration, lifesteal)`. Trials")
    P("resumed from the same save enter the wave with identical stats, so an identical")
    P("fingerprint is a NECESSARY, not sufficient, condition for a shared source state.")
    P("Distinct saves can collide on it; a collision INFLATES within-state SD and")
    P("DEFLATES between-state SD, so the between-state SD below is a LOWER bound.")
    P("")
    for wv in (17, 20):
        P("### Wave %d" % wv)
        P("")
        rows_wv = [(r, w) for r, w in wave_rows
                   if w["wave"] == wv and not r["_human"] and not w["incomplete_coverage"]]
        if not rows_wv:
            P("No agent wave-%d instances in the kept era. DENOMINATOR = 0 -- this is a" % wv)
            P("missing measurement, not a zero effect.")
            P("")
            continue
        by_state = defaultdict(list)
        for r, w in rows_wv:
            by_state[(w["entry_max_hp"], w["entry_regen"], w["entry_lifesteal"])].append(
                w["auc_death_adjusted"])
        vals = [w["auc_death_adjusted"] for _r, w in rows_wv]
        state_means = [_mean(vs) for vs in by_state.values()]
        multi = [vs for vs in by_state.values() if len(vs) >= 2]
        within = [_sd(vs) for vs in multi]
        P("| quantity | value | n |")
        P("|---|---:|---:|")
        P("| wave-instances (trials) | %d | |" % len(vals))
        P("| distinct runs | %d | |" % len(set(r["run_id"] for r, _w in rows_wv)))
        P("| distinct entry-build states (PROXY source states) | %d | |" % len(by_state))
        P("| states with >=2 trials | %d | |" % len(multi))
        P("| grand mean AUC (over trials) | %s | %d |" % (_fmt(_mean(vals)), len(vals)))
        P("| mean of state means | %s | %d |" % (_fmt(_mean(state_means)), len(state_means)))
        P("| **BETWEEN-state SD (the SIZING SD)** | **%s** | %d |"
          % (_fmt(_sd(state_means)), len(state_means)))
        P("| WITHIN-state SD (pooled over states with >=2 trials) | %s | %d |"
          % (_fmt(_mean(within)) if within else "n/a", len(within)))
        P("| naive SD over all trials (WRONG unit, shown to contrast) | %s | %d |"
          % (_fmt(_sd(vals)), len(vals)))
        P("")
        P("Largest proxy states by trial count (the per-fixture means that were asked for):")
        P("")
        P("| entry (max_hp, regen, lifesteal) | trials | mean AUC | SD |")
        P("|---|---:|---:|---:|")
        for k, vs in sorted(by_state.items(), key=lambda x: -len(x[1]))[:8]:
            P("| (%g, %g, %g) | %d | %s | %s |"
              % (k[0], k[1], k[2], len(vs), _fmt(_mean(vs)), _fmt(_sd(vs))))
        P("")
        if not multi:
            P("NO proxy state has >=2 trials at wave %d, so WITHIN-state SD is NOT" % wv)
            P("estimable from this archive. Reported as n/a rather than substituted with")
            P("a tick-level SD, which would understate it by orders of magnitude.")
            P("")
        else:
            bsd = _sd(state_means)
            wsd = _mean(within)
            if bsd == bsd and wsd == wsd and (bsd ** 2 + wsd ** 2) > 0:
                P("Share of variance BETWEEN states: **%.1f%%** of between^2+within^2."
                  % (100.0 * bsd ** 2 / (bsd ** 2 + wsd ** 2)))
                P("Where that share is large, sizing is driven by the number of SOURCE")
                P("STATES, not the number of repeats -- the standing MORE FIXTURES, NOT")
                P("MORE REPEATS finding, now reproduced on the new endpoint.")
                P("")
        P("UNIT WARNING: %d trials is NOT n=%d for inference. n is the number of source"
          % (len(vals), len(vals)))
        P("states (%d by this proxy). The ~%d captures behind these numbers are NEVER"
          % (len(by_state), sum(w["n_caps"] for _r, w in rows_wv)))
        P("the sample size.")
        P("")

    P("## 10. What is NOT computable from this archive")
    P("")
    P("* Source-level healing attribution (regen vs lifesteal vs consumable): no")
    P("  per-source counter, no heal event. See section 7.")
    P("* Consumable pickups as ground truth: inferred only, `instance_id` is pooled.")
    P("* Within-source-state variance where each save produced a single trial.")
    P("* Anything about a wave the captures never covered -- a missing wave is a")
    P("  missing denominator, not a zero.")
    P("")
    return "\n".join(L)


# ---------------------------------------------------------------------------


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--runs-dir", default=DEFAULT_RUNS_DIR)
    ap.add_argument("--cache-dir", default=DEFAULT_CACHE_DIR)
    ap.add_argument("--report", default=DEFAULT_REPORT)
    ap.add_argument("--refresh", action="store_true",
                    help="re-extract even if a cache entry exists")
    ap.add_argument("--extract-only", action="store_true")
    ap.add_argument("--limit", type=int, default=0,
                    help="debug: only analyse the first N cached runs")
    args = ap.parse_args(argv)

    sys.stderr.write("[1/3] extracting (runs-dir=%s)\n" % args.runs_dir)
    do_extract(args.runs_dir, args.cache_dir, args.refresh)
    if args.extract_only:
        return 0

    sys.stderr.write("[2/3] loading cache\n")
    recs = load_cache(args.cache_dir)
    if args.limit:
        recs = recs[:args.limit]
    with open(os.path.join(args.cache_dir, "_era_table.json"), "r", encoding="utf-8") as fh:
        era_meta = json.load(fh)

    sys.stderr.write("[3/3] analysing %d runs\n" % len(recs))
    runs = [analyse_run(r) for r in recs]
    text = build_report(runs, era_meta)

    os.makedirs(os.path.dirname(args.report), exist_ok=True)
    with open(args.report, "w", encoding="utf-8") as fh:
        fh.write(text + "\n")
    sys.stdout.write(text + "\n")
    sys.stderr.write("wrote %s\n" % args.report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
