#!/usr/bin/env python3
"""§45 instrument controls, sufficiency gate, and frozen §44 replay."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
import math
import os
from pathlib import Path
import statistics as stats
import sys

import wp2_joint_route_conversion_gate0 as base
import wp2_clearance_guarded_conversion_gate0 as guard
import wp2_route_conversion_latch_gate0 as latch


BUILD = "0.2.81-wp2-capture"
POLICY = "teacher_v1-0.1.129-gun-wp1"
ERA = {"items": 179, "weapons": 48, "items_hash": "2018397571", "weapons_hash": "1530875081"}


def default_runs_dir() -> Path:
    return Path(os.environ["APPDATA"]) / "Brotato" / "brotato_agent" / "runs"


def row_tuple(row: dict) -> tuple:
    return tuple(float(row.get(key, 0)) for key in ("x", "y", "body", "proj", "pen"))


def unit_xy(x: object, y: object) -> tuple[float, float] | None:
    try:
        x, y = float(x), float(y)
    except (TypeError, ValueError):
        return None
    length = math.hypot(x, y)
    return (x / length, y / length) if length > 1e-12 else None


def summary_faults(summary: dict) -> list[str]:
    expected = {
        "mod_version": BUILD,
        "policy_version": POLICY,
        "character_observed": "character_ranger",
        "danger": 5,
        "requested_danger": 5,
        "danger_ok": True,
        "weapon": "weapon_pistol_1",
        "telemetry_complete": True,
        "clearance_guarded_conversion": True,
        "route_scores_enabled": True,
        "route_latch_revalidation_enabled": True,
        "body_clearance_scale": 1,
        "unlock_pool": ERA,
    }
    faults = [f"{key}={summary.get(key)!r}" for key, value in expected.items() if summary.get(key) != value]
    for key in ("errors", "hangs", "illegal_actions", "nonfinite_fixed"):
        if int(summary.get(key, 0) or 0):
            faults.append(f"{key}={summary.get(key)!r}")
    if summary.get("result") not in {"victory", "defeat"}:
        faults.append(f"result={summary.get('result')!r}")
    return faults


def inrange_map(payload: dict, rows: list[dict], current: dict) -> dict | None:
    entities = payload.get("entities") or {}
    threats = [
        threat
        for threat in (entities.get("enemies") or []) + (entities.get("bosses") or [])
        if float(threat.get("hp", 0) or 0) > 0
    ]
    ranges = [
        float(weapon.get("max_range", 0) or 0)
        for weapon in payload.get("weapons") or []
        if float(weapon.get("max_range", 0) or 0) > 0
    ]
    player = payload.get("player") or {}
    try:
        px, py = float(player["x"]), float(player["y"])
        speed = float(player.get("speed", 0) or 0)
    except (KeyError, TypeError, ValueError):
        return None
    if not threats or not ranges or speed <= 0:
        return None
    out = {}
    for row in rows + [current]:
        value = base.inrange_after(
            px, py, speed, float(row["x"]), float(row["y"]), threats, max(ranges)
        )
        if value is None:
            return None
        out[base.key(row)] = value
    return out


def analysis_capture(run_id: str, payload: dict, route: dict, revalidation: dict) -> dict | None:
    if revalidation.get("ready") is not True:
        return None
    rows = list(revalidation.get("rows") or [])
    reference = unit_xy(revalidation.get("reference_x"), revalidation.get("reference_y"))
    if not rows or reference is None:
        return None
    try:
        reference_body = float(revalidation["reference_body"])
        reference_projectile = float(revalidation["reference_projectile"])
        projectile_floor = float(revalidation["projectile_floor"])
        body_floor = float(revalidation["body_floor"])
        lowest_penalty = float(revalidation["lowest_penalty"])
    except (KeyError, TypeError, ValueError):
        return None
    current = {
        "x": reference[0], "y": reference[1], "body": reference_body,
        "proj": reference_projectile, "pen": lowest_penalty,
    }
    admitted = [
        row for row in rows
        if float(row.get("proj", -1e18)) >= projectile_floor
        and float(row.get("body", -1e18)) >= body_floor
        and float(row.get("pen", 1e18)) <= lowest_penalty + base.ENEMY_SLACK
    ]
    values = inrange_map(payload, rows, current)
    if not admitted or values is None:
        return None
    trigger_selected = current
    applied = route.get("conversion_applied") is True
    if applied:
        selected_key = (round(float(route.get("sel_x", 1e9)), 4), round(float(route.get("sel_y", 1e9)), 4))
        matches = [row for row in rows if base.key(row) == selected_key]
        if not matches:
            return None
        trigger_selected = matches[0]
    translation = (((payload.get("teacher") or {}).get("contributions") or {}).get("finale_translation") or {})
    return {
        "run_id": run_id,
        "wave": int(payload["wave"]),
        "rows": rows,
        "projectile_floor": projectile_floor,
        "loot_dash": bool(translation.get("loot_dash_active")),
        "baseline": reference,
        "previous": reference,
        "current": current,
        "inrange": values,
        "revalidation_admitted": admitted,
        "trigger_evaluated": True,
        "trigger_selected": trigger_selected,
    }


def scan_run(root: Path, run_id: str) -> dict:
    stream = []
    counters = Counter()
    last_seq = last_ts = None
    with (root / run_id / "events.jsonl").open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if '"combat_capture"' not in line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                counters["parse_errors"] += 1
                continue
            if event.get("event") != "combat_capture":
                continue
            payload = event.get("payload") or {}
            wave, seq, ts = payload.get("wave"), payload.get("capture_seq"), event.get("ts_ms")
            if not isinstance(wave, int) or not 1 <= wave <= 11:
                continue
            counters["raw"] += 1
            if not isinstance(seq, int) or not isinstance(ts, int) or (last_seq is not None and seq <= last_seq):
                counters["stale"] += 1
                continue
            if last_ts is not None and ts <= last_ts:
                counters["nonincreasing_ts"] += 1
                continue
            last_seq, last_ts = seq, ts
            counters["fresh"] += 1
            route = (((payload.get("teacher") or {}).get("contributions") or {}).get("route") or {})
            revalidation = route.get("revalidation") or {}
            counters["instrument_enabled"] += revalidation.get("enabled") is True
            ready = revalidation.get("ready") is True
            counters["ready"] += ready
            counters["not_ready"] += not ready
            counters[f"reason:{revalidation.get('reason', 'missing')}"] += 1
            scores = list(route.get("scores") or [])
            if ready and scores:
                counters["parity_captures"] += 1
                left, right = Counter(row_tuple(row) for row in revalidation.get("rows") or []), Counter(row_tuple(row) for row in scores)
                total = sum(right.values())
                matched = sum((left & right).values())
                counters["parity_rows"] += total
                counters["parity_rows_matched"] += matched
                counters["parity_capture_exact"] += left == right
            entities = payload.get("entities") or {}
            living = any(float(t.get("hp", 0) or 0) > 0 for t in (entities.get("enemies") or []) + (entities.get("bosses") or []))
            if route.get("exit") == "baseline_kept" and living:
                counters["baseline_living"] += 1
                counters["baseline_living_ready"] += ready and bool(revalidation.get("rows"))
            if route.get("exit") in {"ranked", "conversion"}:
                action = (payload.get("teacher") or {}).get("action") or {}
                selected = unit_xy(route.get("sel_x"), route.get("sel_y"))
                emitted = unit_xy(action.get("x"), action.get("y"))
                if selected is not None and emitted is not None:
                    counters["heading_seen"] += 1
                    counters["heading_match"] += math.hypot(selected[0] - emitted[0], selected[1] - emitted[1]) <= 0.001
            if route.get("conversion_applied") is True:
                counters["applied"] += 1
                try:
                    gain = float(route["conversion_gain"])
                    old_body = float(route["conversion_input_body"])
                    new_body = float(route["conversion_selected_body"])
                    counters["gain_ok"] += gain > 0.0499
                    counters["body_ok"] += guard.body_guard_ok(new_body + 0.02, old_body)
                    counters["subcritical_ok"] += new_body + 0.02 >= base.CRITICAL or new_body + 0.02 >= old_body
                except (KeyError, TypeError, ValueError):
                    pass
            capture = analysis_capture(run_id, payload, route, revalidation)
            stream.append({"run_id": run_id, "capture_seq": seq, "ts_ms": ts, "wave": wave, "route_exit": route.get("exit", "missing"), "analysis": capture})
    return {"stream": stream, "counters": counters}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=Path(".tmp/s45_route_latch_revalidation/manifest.json"))
    parser.add_argument("--runs-dir", type=Path, default=default_runs_dir())
    parser.add_argument("--output", type=Path, default=Path("reports/wp2/route_latch_revalidation_result.json"))
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8-sig"))
    slots = manifest.get("slots") or []
    run_ids = [str(row["run_id"]) for row in slots]

    print("=" * 88)
    print("STEP 1 — RUN, INSTRUMENT, PARITY, AND DELIVERY CONTROLS")
    print("=" * 88)
    faults = []
    if len(run_ids) != 4 or len(set(run_ids)) != 4:
        faults.append(f"manifest run count/uniqueness={len(run_ids)}/{len(set(run_ids))}")
    scans = {}
    summaries = {}
    for run_id in run_ids:
        summary = json.loads((args.runs_dir / run_id / "summary.json").read_text(encoding="utf-8"))
        summaries[run_id] = summary
        run_faults = summary_faults(summary)
        scans[run_id] = scan_run(args.runs_dir, run_id)
        c = scans[run_id]["counters"]
        if c["applied"] <= 0:
            run_faults.append("no applied conversion")
        faults.extend(f"{run_id}: {fault}" for fault in run_faults)
        print(f"{run_id}: fresh={c['fresh']}/{c['raw']} enabled={c['instrument_enabled']}/{c['fresh']} ready/not={c['ready']}/{c['not_ready']} applied={c['applied']} faults={run_faults}")
    pooled = sum((scan["counters"] for scan in scans.values()), Counter())
    parity_rate = pooled["parity_rows_matched"] / pooled["parity_rows"] if pooled["parity_rows"] else 0.0
    parity_capture_rate = pooled["parity_capture_exact"] / pooled["parity_captures"] if pooled["parity_captures"] else 0.0
    baseline_rate = pooled["baseline_living_ready"] / pooled["baseline_living"] if pooled["baseline_living"] else 0.0
    heading_rate = pooled["heading_match"] / pooled["heading_seen"] if pooled["heading_seen"] else 0.0
    print(f"stale/nonincreasing/parse: {pooled['stale']}/{pooled['nonincreasing_ts']}/{pooled['parse_errors']} over fresh={pooled['fresh']}")
    print(f"instrument enabled: {pooled['instrument_enabled']}/{pooled['fresh']}")
    print(f"ranked row parity: {pooled['parity_rows_matched']}/{pooled['parity_rows']}={parity_rate:.6f}; exact captures={parity_capture_rate:.6f}")
    print(f"baseline_kept living ready: {pooled['baseline_living_ready']}/{pooled['baseline_living']}={baseline_rate:.6f}")
    print(f"emitted/selected heading: {pooled['heading_match']}/{pooled['heading_seen']}={heading_rate:.6f}")
    print(f"conversion guard gain/body/subcritical: {pooled['gain_ok']}/{pooled['body_ok']}/{pooled['subcritical_ok']} denominator={pooled['applied']}")
    if pooled["stale"] or pooled["nonincreasing_ts"] or pooled["parse_errors"]:
        faults.append("fresh sequence")
    if pooled["instrument_enabled"] != pooled["fresh"] or not pooled["ready"] or not pooled["not_ready"]:
        faults.append("instrument enable/readiness controls")
    if parity_rate < 0.999 or parity_capture_rate < 0.999:
        faults.append("ranked row parity")
    if baseline_rate < 0.99:
        faults.append("baseline_kept readiness")
    if heading_rate < 0.999:
        faults.append("action delivery")
    if any(pooled[key] != pooled["applied"] for key in ("gain_ok", "body_ok", "subcritical_ok")):
        faults.append("conversion guard")
    print(f"CONTROL VERDICT: {'PASS' if not faults else 'VOID'} faults={faults}")
    if faults:
        result = {"status": "VOID", "faults": faults}
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        return 2

    simulations = {run_id: latch.simulate_run(scans[run_id]["stream"]) for run_id in run_ids}
    state = sum((sim["counters"] for sim in simulations.values()), Counter())
    episodes = [episode for sim in simulations.values() for episode in sim["episodes"]]
    eligible = [episode for episode in episodes if episode["future_matched"]]
    reached = [episode for episode in eligible if episode["reached_horizon"]]
    obs = state["observable_future_captures"] / state["active_future_captures"] if state["active_future_captures"] else 0.0
    obs_by_run = {}
    eligible_by_run = Counter(ep["run_id"] for ep in eligible)
    for run_id, sim in simulations.items():
        denominator = sim["counters"]["active_future_captures"]
        obs_by_run[run_id] = sim["counters"]["observable_future_captures"] / denominator if denominator else 0.0
    baseline_active = state["active_exit:baseline_kept"]
    baseline_observable = state["observable_exit:baseline_kept"]
    baseline_active_rate = baseline_observable / baseline_active if baseline_active else 0.0
    sufficiency = {
        "episodes": len(episodes) >= 1000,
        "pooled_observability": obs >= 0.99,
        "per_run_observability": all(value >= 0.98 for value in obs_by_run.values()),
        "baseline_observability": baseline_active_rate >= 0.99,
        "per_run_future_eligible": all(eligible_by_run[run_id] >= 30 for run_id in run_ids),
    }
    print("\n" + "=" * 88)
    print("STEP 2 — DATA SUFFICIENCY BEFORE LATCH RESULT")
    print("=" * 88)
    print(f"episodes={len(episodes)}; active observability={state['observable_future_captures']}/{state['active_future_captures']}={obs:.6f}; by_run={obs_by_run}")
    print(f"baseline active observability={baseline_observable}/{baseline_active}={baseline_active_rate:.6f}; future eligible by run={dict(eligible_by_run)}")
    print(f"SUFFICIENCY: {sufficiency}")
    if not all(sufficiency.values()):
        status = "INSUFFICIENT_INSTRUMENT"
        result = {"status": status, "controls": dict(pooled), "sufficiency": sufficiency, "observability": {"pooled": obs, "by_run": obs_by_run, "baseline": baseline_active_rate}, "episodes": len(episodes)}
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(f"VERDICT: {status}; latch result not computed")
        return 0

    durations = [ep["duration_sec"] for ep in episodes]
    duration_q = latch.quantiles(durations)
    horizon_rate = len(reached) / len(eligible)
    reached_by_run = Counter(ep["run_id"] for ep in reached)
    loo = []
    for run_id in run_ids:
        n = len(reached) - reached_by_run[run_id]
        d = len(eligible) - eligible_by_run[run_id]
        loo.append(n / d if d else 0.0)
    contributing = sum(reached_by_run[run_id] > 0 for run_id in run_ids)
    largest = max(reached_by_run.values(), default=0) / len(reached) if reached else 0.0
    retained_n = state["retained_steps"]
    override_rate = state["override_steps"] / retained_n if retained_n else 0.0
    invariant_keys = ("projectile_ok", "body_ok", "subcritical_ok", "enemy_ok", "angle_ok")
    bars = {
        "median_duration": duration_q["median"] is not None and duration_q["median"] >= 0.30,
        "horizon_rate": horizon_rate >= 0.25,
        "all_runs_contribute": contributing == 4,
        "loo_min": min(loo) >= 0.20,
        "loo_median": stats.median(loo) >= 0.25,
        "largest_run_share": largest <= 0.35,
        "safety": all(state[key] == retained_n for key in invariant_keys),
        "override_rate": override_rate >= 0.20,
    }
    status = "PASS" if all(bars.values()) else "FAIL"
    print("\n" + "=" * 88)
    print("STEP 3 — FROZEN §44 LATCH RESULT")
    print("=" * 88)
    print(f"duration={duration_q}; horizon={len(reached)}/{len(eligible)}={horizon_rate:.6f}; contributing={contributing}/4; LOO={loo}; largest={largest:.6f}")
    print(f"retained overrides={state['override_steps']}/{retained_n}={override_rate:.6f}; invariants=" + "/".join(str(state[key]) for key in invariant_keys))
    print(f"bars={bars}")
    print(f"VERDICT: {status}")
    result = {"status": status, "controls": dict(pooled), "sufficiency": sufficiency, "observability": {"pooled": obs, "by_run": obs_by_run, "baseline": baseline_active_rate}, "temporal": {"episodes": len(episodes), "duration": duration_q, "eligible": len(eligible), "reached": len(reached), "horizon_rate": horizon_rate, "contributing_runs": contributing, "loo": loo, "largest_share": largest}, "authority": {"retained": retained_n, "overrides": state["override_steps"], "override_rate": override_rate, "invariants": {key: state[key] for key in invariant_keys}}, "bars": bars, "runs": run_ids, "terminal_context": {run_id: summaries[run_id].get("last_wave") for run_id in run_ids}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
