#!/usr/bin/env python3
"""Multi-label failure-channel attribution for the Danger 5 terminal wave.

WHAT THIS DOES
--------------
For each run, take the HP drops that occur in the run's TERMINAL wave (the last wave
with captures) and attach zero or more channel labels to each drop:

    melee body | moving projectile | stationary projectile
    other visible hazard | unexplained/absent-from-observation

Multi-label on purpose: several hazards can be in contact range on the same tick and
there is no ground truth that picks one. Forcing exclusivity would manufacture a story.
Co-occurrence is reported instead.

METHOD, and why each piece is fixed
-----------------------------------
* Attribution uses the HP-DROP DIFF between consecutive captures, never the
  `player_damage` event: that event lags the damage tick by ~one capture interval and
  has produced a false residual before.
* The causal lag is NOT re-derived here. It is taken from
  `reports/wp2/d5_damage_lag_result.md` / `scripts/wp2_d5_damage_lag.py`:
  **LAG 0 on `entities.enemies` (melee bodies) for D5 waves 6-15.**
  That derivation explicitly did NOT establish a lag for BOSSES (n=13, medians ABOVE
  baseline), so boss-bearing terminal waves are flagged and their boss channel is
  reported as lag-uncertain rather than asserted.
* Geometry is SURFACE distance, matching `wp2_d5_damage_lag.py` exactly:
  hypot(dx, dy) - entity.radius. The player's own radius is NOT subtracted, because the
  reference derivation did not subtract it and the numbers must remain comparable.
* Projectiles carried NO lag signal in that derivation, so this script reports the
  projectile channel at BOTH lag 0 and lag -1 and never silently picks one.
* `nearest_d` (teacher/debug) is never used as a distance. It is sanitized to 1e18 when
  the game means "no target" (exactly when n_enemies == 0). Captures with >= 1e17 are
  counted and excluded; it is never averaged.
* Every count is printed with the denominator that was searched, and the filter fields
  are checked for actual variation so a zero cannot come from a vacuous filter.

STRUCTURAL LIMITATIONS (stated, not papered over)
-------------------------------------------------
* DODGED HITS PRODUCE NO HP DROP and are therefore completely invisible to this
  instrument. A run can be dominated by near-misses and this will not see it.
* Self-damage items, burn/DoT, and any off-screen or non-entity damage source appear as
  HP drops with nothing adjacent, and land in `unexplained`. `unexplained` is therefore
  an upper bound on "absent from observation", not a measurement of it.
* `hp_regeneration` raises HP between hits; a decrease is still damage, but two hits
  inside one capture interval read as one drop.
* A proximity label is an OPPORTUNITY, not a proof of causation.
* MEASURED IN THIS SAMPLE, NOT ASSUMED: the FATAL drop is NOT in the telemetry. Every
  run's last capture still shows hp > 0, and the capture stream stops a short interval
  before `run_end` -- that interval is COMPUTED per run into `capture_to_run_end_gap_ms`
  and its range is printed in the LIMITATIONS block, rather than quoted from memory here.
  What this script calls `last_observed_hp_drop` is exactly that -- the last
  HP drop that was captured -- and it is NOT the killing blow. The killing blow lands in
  the ~2-4 uncaptured ticks after the final capture and CANNOT BE ATTRIBUTED AT ALL.
  The field `fatal_drop_captured` records this per run rather than hiding it.
* Projectile `instance_id` is POOLED/REUSED (the same id reappears at a different
  position within one run), so it cannot be used as a stable projectile identity.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import statistics
from collections import Counter
from pathlib import Path
from typing import Any

# Fixed by the prior derivation. Do not change without re-deriving.
MELEE_LAG = 0
PROJ_LAGS = (0, -1)

# Contact thresholds on SURFACE distance (u). Primary + sensitivity sweep; the
# false-positive rate of each against random terminal-wave captures is reported so the
# reader can see what the threshold costs.
T_PRIMARY = 40.0
T_SWEEP = (10.0, 20.0, 40.0, 80.0)

INF_SENTINEL = 1e17

CHANNELS = (
    "melee_body",
    "moving_projectile",
    "stationary_projectile",
    "other_visible_hazard",
    "unexplained",
)


def _min_surface(px: float, py: float, items: list[dict[str, Any]]) -> float | None:
    """Match wp2_d5_damage_lag.py geometry exactly: centre distance minus entity radius."""
    best = None
    for it in items:
        x, y = it.get("x"), it.get("y")
        if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
            continue
        r = it.get("radius") or 0.0
        d = math.hypot(x - px, y - py) - float(r)
        if best is None or d < best:
            best = d
    return best


def _split_projectiles(items: list[dict[str, Any]]) -> tuple[list, list]:
    moving, still = [], []
    for it in items or []:
        vx = it.get("vx") or 0.0
        vy = it.get("vy") or 0.0
        (moving if (abs(float(vx)) + abs(float(vy))) > 0.0 else still).append(it)
    return moving, still


def load_series(path: Path) -> tuple[list[dict[str, Any]], dict[str, int], float | None]:
    rows: list[dict[str, Any]] = []
    diag = Counter()
    run_end_ts: float | None = None
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            if '"run_end"' in line:
                # Needed to MEASURE the capture-stream-to-run_end gap rather than
                # quoting a remembered range for it.
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    diag["unparseable_lines"] += 1
                    continue
                if ev.get("event") == "run_end":
                    ts = ev.get("ts_ms")
                    if isinstance(ts, (int, float)):
                        run_end_ts = float(ts)
                continue
            if '"combat_capture"' not in line:
                continue
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                diag["unparseable_lines"] += 1
                continue
            p = ev.get("payload", {})
            diag["captures_seen"] += 1
            if p.get("valid") is False:
                diag["excluded_invalid"] += 1
                continue
            dt = p.get("control_dt_ms")
            if isinstance(dt, (int, float)) and dt < 10:
                diag["excluded_low_dt"] += 1
                continue
            player = p.get("player", {}) or {}
            hp, px, py = player.get("hp"), player.get("x"), player.get("y")
            if not isinstance(hp, (int, float)) or not isinstance(px, (int, float)):
                diag["excluded_no_player"] += 1
                continue
            ent = p.get("entities", {}) or {}
            enemies = ent.get("enemies") or []
            bosses = ent.get("bosses") or []
            obstacles = ent.get("obstacles") or []
            moving, still = _split_projectiles(ent.get("projectiles") or [])

            # nearest_d hygiene: counted, never averaged, never used as a distance.
            nd = ((p.get("teacher") or {}).get("contributions") or {}).get("desire") or {}
            ndv = nd.get("nearest_d")
            if isinstance(ndv, (int, float)) and abs(float(ndv)) >= INF_SENTINEL:
                diag["nearest_d_inf_sentinel"] += 1
                if not enemies:
                    diag["nearest_d_inf_with_zero_enemies"] += 1

            rows.append({
                "seq": p.get("capture_seq"),
                "ts_ms": ev.get("ts_ms"),
                "wave": int(p.get("wave", 0)),
                "hp": float(hp),
                "n_enemies": len(enemies),
                "n_bosses": len(bosses),
                "n_moving_proj": len(moving),
                "n_still_proj": len(still),
                "n_obstacles": len(obstacles),
                "d_enemies": _min_surface(px, py, enemies),
                "d_bosses": _min_surface(px, py, bosses),
                "d_moving_proj": _min_surface(px, py, moving),
                "d_still_proj": _min_surface(px, py, still),
                "d_obstacles": _min_surface(px, py, obstacles),
            })
    rows.sort(key=lambda r: (r["wave"], r["seq"] if r["seq"] is not None else 0))
    return rows, dict(diag), run_end_ts


def _at(rows, i, lag, key):
    j = i + lag
    if 0 <= j < len(rows):
        return rows[j][key]
    return None


def _near(v, t):
    return v is not None and v <= t


def label_drop(rows, i, t) -> dict[str, Any]:
    """Multi-label one HP drop at index i (rows[i].hp < rows[i-1].hp)."""
    lab = set()
    ev: dict[str, Any] = {}

    ev["d_enemies_lag0"] = _at(rows, i, MELEE_LAG, "d_enemies")
    if _near(ev["d_enemies_lag0"], t):
        lab.add("melee_body")

    for key, chan in (("d_moving_proj", "moving_projectile"),
                      ("d_still_proj", "stationary_projectile")):
        for lag in PROJ_LAGS:
            v = _at(rows, i, lag, key)
            ev[f"{key}_lag{lag}"] = v
            if _near(v, t):
                lab.add(chan)

    ev["d_bosses_lag0"] = _at(rows, i, 0, "d_bosses")
    ev["d_obstacles_lag0"] = _at(rows, i, 0, "d_obstacles")
    if _near(ev["d_bosses_lag0"], t) or _near(ev["d_obstacles_lag0"], t):
        lab.add("other_visible_hazard")

    if not lab:
        lab.add("unexplained")
    return {"labels": sorted(lab), "evidence": {k: (round(v, 2) if isinstance(v, float) else v)
                                                for k, v in ev.items()}}


def fp_rate(rows, key, t) -> dict[str, Any]:
    """What fraction of ordinary captures already sit inside the threshold.

    This is the denominator that makes a channel count mean something: a channel whose
    FP rate is near 1.0 is not discriminating, and a channel whose candidate field never
    varies cannot return a positive at all.
    """
    vals = [r[key] for r in rows if r[key] is not None]
    n_present = sum(1 for r in rows if r[key] is not None)
    return {
        "captures": len(rows),
        "captures_with_any_such_entity": n_present,
        "rate_present": round(n_present / len(rows), 4) if rows else None,
        "fp_rate_at_threshold": round(sum(1 for v in vals if v <= t) / len(rows), 4) if rows else None,
        "min": round(min(vals), 2) if vals else None,
        "median": round(statistics.median(vals), 2) if vals else None,
        "max": round(max(vals), 2) if vals else None,
        "distinct_values": len({round(v, 3) for v in vals}),
    }


def analyse_run(rid: str, root: Path, t: float) -> dict[str, Any]:
    f = root / rid / "events.jsonl"
    if not f.is_file():
        return {"run_id": rid, "error": "missing events.jsonl"}
    rows, diag, run_end_ts = load_series(f)
    if not rows:
        return {"run_id": rid, "error": "no usable captures", "diagnostics": diag}

    summary = {}
    sf = root / rid / "summary.json"
    if sf.is_file():
        try:
            summary = json.loads(sf.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            summary = {}

    terminal_wave = max(r["wave"] for r in rows)
    tw_idx = [i for i, r in enumerate(rows) if r["wave"] == terminal_wave]
    tw_rows = [rows[i] for i in tw_idx]
    lo = min(tw_idx)

    # A drop needs both neighbours inside the terminal wave, else the wave seam
    # manufactures a false drop (the shop heals/levels between waves).
    drops = [i for i in tw_idx if i - 1 in tw_idx and rows[i]["hp"] < rows[i - 1]["hp"]]

    labelled = []
    for i in drops:
        d = label_drop(rows, i, t)
        d["seq"] = rows[i]["seq"]
        d["hp_before"] = rows[i - 1]["hp"]
        d["hp_after"] = rows[i]["hp"]
        d["magnitude"] = round(rows[i - 1]["hp"] - rows[i]["hp"], 3)
        labelled.append(d)

    last_drop = labelled[-1] if labelled else None
    min_hp = min(r["hp"] for r in tw_rows)
    hp_reached_zero = min_hp <= 0

    per_channel = Counter()
    for d in labelled:
        for c in d["labels"]:
            per_channel[c] += 1

    return {
        "run_id": rid,
        "result": summary.get("result"),
        "last_wave_summary": summary.get("last_wave"),
        "terminal_wave": terminal_wave,
        "terminal_wave_captures": len(tw_rows),
        "terminal_wave_has_bosses": any(r["n_bosses"] > 0 for r in tw_rows),
        "boss_capture_count": sum(1 for r in tw_rows if r["n_bosses"] > 0),
        "n_hp_drops_terminal_wave": len(drops),
        "min_hp_in_terminal_wave": min_hp,
        "hp_reached_zero_in_captures": hp_reached_zero,
        "last_observed_hp_drop": last_drop,
        "fatal_drop_captured": hp_reached_zero,
        "hp_at_last_capture": tw_rows[-1]["hp"],
        # MEASURED, not remembered: how long the capture stream stops before run_end.
        # The killing blow lands inside this window, which is why it is unattributable.
        "capture_to_run_end_gap_ms": (
            round(run_end_ts - tw_rows[-1]["ts_ms"], 1)
            if run_end_ts is not None and isinstance(tw_rows[-1].get("ts_ms"), (int, float))
            else None
        ),
        "per_channel_counts": dict(per_channel),
        "drops": labelled,
        "diagnostics": diag,
        "field_variation_terminal_wave": {
            k: fp_rate(tw_rows, k, t)
            for k in ("d_enemies", "d_moving_proj", "d_still_proj", "d_bosses", "d_obstacles")
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-ids-file", required=True)
    ap.add_argument("--runs-dir", default=None,
                    help="defaults to %%APPDATA%%/Brotato/brotato_agent/runs")
    ap.add_argument("--out", required=True, help="output directory")
    ap.add_argument("--threshold", type=float, default=T_PRIMARY)
    args = ap.parse_args()

    ids = [x.strip() for x in Path(args.run_ids_file).read_text(encoding="utf-8").splitlines()
           if x.strip()]
    root = Path(args.runs_dir) if args.runs_dir else \
        Path(os.environ["APPDATA"]) / "Brotato" / "brotato_agent" / "runs"
    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)

    runs = [analyse_run(rid, root, args.threshold) for rid in ids]
    ok = [r for r in runs if "error" not in r]

    # Sensitivity: the whole picture as a function of the contact threshold.
    sweep = {}
    for t in T_SWEEP:
        rs = [analyse_run(rid, root, t) for rid in ids]
        rs = [r for r in rs if "error" not in r]
        c = Counter()
        tot = 0
        killc = Counter()
        for r in rs:
            tot += r["n_hp_drops_terminal_wave"]
            for k, v in r["per_channel_counts"].items():
                c[k] += v
            if r["last_observed_hp_drop"]:
                for k in r["last_observed_hp_drop"]["labels"]:
                    killc[k] += 1
        sweep[str(t)] = {"drops_total": tot, "drop_channel_counts": dict(c),
                         "last_drop_channel_counts": dict(killc),
                         "runs_with_a_last_drop": sum(1 for r in rs if r["last_observed_hp_drop"])}

    total_drops = sum(r["n_hp_drops_terminal_wave"] for r in ok)
    drop_chan = Counter()
    for r in ok:
        for k, v in r["per_channel_counts"].items():
            drop_chan[k] += v
    kill_chan = Counter()
    kill_combo = Counter()
    n_kill = 0
    for r in ok:
        if r["last_observed_hp_drop"]:
            n_kill += 1
            for k in r["last_observed_hp_drop"]["labels"]:
                kill_chan[k] += 1
            kill_combo["+".join(r["last_observed_hp_drop"]["labels"])] += 1
    combo = Counter()
    for r in ok:
        for d in r["drops"]:
            combo["+".join(d["labels"])] += 1

    result = {
        "runs_requested": len(ids),
        "runs_analysed": len(ok),
        "threshold_surface_u": args.threshold,
        "lag_policy": {"melee": MELEE_LAG, "projectiles": list(PROJ_LAGS),
                       "source": "reports/wp2/d5_damage_lag_result.md",
                       "boss_lag": "NOT ESTABLISHED - not inherited"},
        "totals": {
            "terminal_wave_hp_drops": total_drops,
            "drop_channel_counts": dict(drop_chan),
            "drop_label_combinations": dict(combo),
            "last_observed_drops_found": n_kill,
            "fatal_drops_captured": 0,
            "last_drop_channel_counts": dict(kill_chan),
            "last_drop_label_combinations": dict(kill_combo),
        },
        "threshold_sensitivity": sweep,
        "per_run": runs,
    }
    (outdir / "channels.json").write_text(json.dumps(result, indent=1), encoding="utf-8")

    lines = []
    A = lines.append
    A("D5 TERMINAL-WAVE FAILURE-CHANNEL ATTRIBUTION (multi-label)")
    A(f"runs requested {len(ids)} / analysed {len(ok)}   threshold {args.threshold} u surface")
    A(f"lag: melee={MELEE_LAG} on entities.enemies (inherited from the D5 derivation);"
      f" projectiles evaluated at lags {PROJ_LAGS}; boss lag NOT established.")
    A("")
    A("RAW PER-RUN TABLE")
    hdr = (f"{'run_id':<24}{'res':<8}{'twave':>6}{'boss':>6}{'drops':>7}{'minHP':>7}"
           f"{'melee':>7}{'mproj':>7}{'sproj':>7}{'other':>7}{'unexp':>7}  last-drop labels")
    A(hdr)
    A("-" * len(hdr))
    for r in runs:
        if "error" in r:
            A(f"{r['run_id']:<24}ERROR {r['error']}")
            continue
        pc = r["per_channel_counts"]
        kl = "+".join(r["last_observed_hp_drop"]["labels"]) if r["last_observed_hp_drop"] else "NO DROP FOUND"
        A(f"{r['run_id']:<24}{str(r['result']):<8}{r['terminal_wave']:>6}"
          f"{('Y' if r['terminal_wave_has_bosses'] else 'n'):>6}"
          f"{r['n_hp_drops_terminal_wave']:>7}{r['min_hp_in_terminal_wave']:>7}"
          f"{pc.get('melee_body',0):>7}{pc.get('moving_projectile',0):>7}"
          f"{pc.get('stationary_projectile',0):>7}{pc.get('other_visible_hazard',0):>7}"
          f"{pc.get('unexplained',0):>7}  {kl}")
    A("")
    A(f"CHANNEL SUMMARY - denominator = {total_drops} terminal-wave HP drops across {len(ok)} runs")
    for c in CHANNELS:
        n = drop_chan.get(c, 0)
        A(f"  {c:<24}{n:>5} / {total_drops}"
          + (f"  ({n/total_drops:.1%})" if total_drops else ""))
    A("")
    A(f"LAST OBSERVED HP DROP (NOT the fatal blow) - denominator = {n_kill} / {len(ok)} runs")
    for c in CHANNELS:
        n = kill_chan.get(c, 0)
        A(f"  {c:<24}{n:>5} / {n_kill}" + (f"  ({n/n_kill:.1%})" if n_kill else ""))
    A("")
    A("LABEL CO-OCCURRENCE (all drops):")
    for k, v in combo.most_common():
        A(f"  {k:<50}{v:>6} / {total_drops}")
    A("")
    A("LABEL CO-OCCURRENCE (last observed drops):")
    for k, v in kill_combo.most_common():
        A(f"  {k:<50}{v:>6} / {n_kill}")
    A("")
    A("THRESHOLD SENSITIVITY")
    for t, s in sweep.items():
        A(f"  t={t:>6}  drops={s['drops_total']:<6} {s['drop_channel_counts']}")
        A(f"           last({s['runs_with_a_last_drop']}): {s['last_drop_channel_counts']}")
    A("")
    A("FILTER-FIELD VARIATION IN THE TERMINAL WAVE (a zero must not come from a dead field)")
    for r in ok:
        A(f"  {r['run_id']}  captures={r['terminal_wave_captures']}")
        for k, v in r["field_variation_terminal_wave"].items():
            A(f"    {k:<16} present {v['captures_with_any_such_entity']:>5}/{v['captures']}"
              f"  distinct={v['distinct_values']:<5} min={v['min']} med={v['median']}"
              f" max={v['max']}  fp@thr={v['fp_rate_at_threshold']}")
    A("")
    A("LIMITATIONS")
    A("  * DODGED HITS PRODUCE NO HP DROP and are structurally invisible to this instrument.")
    A("  * A proximity label is an OPPORTUNITY, not proof of causation.")
    A("  * 'unexplained' is an UPPER BOUND on absent-from-observation: it also absorbs")
    A("    self-damage, burn/DoT, and any two-hits-in-one-capture-interval merge.")
    A("  * Boss lag was NOT established by the D5 derivation (n=13, medians above baseline);")
    A("    boss-bearing terminal waves are flagged, not asserted.")
    n_alive = sum(1 for r in ok if not r["fatal_drop_captured"])
    gaps = sorted(r["capture_to_run_end_gap_ms"] for r in ok
                  if r.get("capture_to_run_end_gap_ms") is not None)
    A(f"  * THE FATAL DROP IS NOT IN THE TELEMETRY: hp > 0 at the last capture in"
      f" {n_alive} / {len(ok)} runs,")
    if gaps:
        med = (gaps[len(gaps) // 2] if len(gaps) % 2
               else (gaps[len(gaps) // 2 - 1] + gaps[len(gaps) // 2]) / 2)
        A(f"    and captures stop {gaps[0]:.0f}-{gaps[-1]:.0f} ms before run_end"
          f" (median {med:.0f}, n={len(gaps)}). MEASURED, not assumed.")
    else:
        A("    and the capture-to-run_end gap could NOT be measured (no run_end ts_ms).")
    A("    The killing blow is UNATTRIBUTABLE. 'last observed HP drop' below is the last")
    A("    CAPTURED drop, not the killing blow.")
    A("  * Projectile instance_id is POOLED/REUSED and is not a stable identity.")
    A("  * nearest_d is never used as a distance (INF sentinel = 'no target'); see diagnostics.")
    (outdir / "report.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
