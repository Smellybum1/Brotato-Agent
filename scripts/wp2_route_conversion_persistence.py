#!/usr/bin/env python3
"""§43 trajectory-persistence diagnostic for the fixed §42 treatment runs."""
from __future__ import annotations

import argparse
from bisect import bisect_left
import json
import math
import os
from pathlib import Path
import statistics as stats
from typing import Any


RUN_IDS = (
    "run_1785820603_11732",
    "run_1785821156_74146",
    "run_1785822002_63879",
    "run_1785823323_53547",
)
BUILD = "0.2.80-wp2-capture"
POLICY = "teacher_v1-0.1.129-gun-wp1"
ERA = {
    "items": 179,
    "weapons": 48,
    "items_hash": "2018397571",
    "weapons_hash": "1530875081",
}
EPISODE_MAX_GAP_MS = 100
HORIZON_MS = 600
FUTURE_TOLERANCE_MS = 75


def runs_dir() -> Path:
    return Path(os.environ["APPDATA"]) / "Brotato" / "brotato_agent" / "runs"


def normalized(x: float, y: float) -> tuple[float, float] | None:
    length = math.hypot(x, y)
    if length <= 1e-12:
        return None
    return x / length, y / length


def average_ranks(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=values.__getitem__)
    ranks = [0.0] * len(values)
    start = 0
    while start < len(order):
        end = start + 1
        while end < len(order) and values[order[end]] == values[order[start]]:
            end += 1
        rank = (start + 1 + end) / 2.0
        for position in range(start, end):
            ranks[order[position]] = rank
        start = end
    return ranks


def pearson(a: list[float], b: list[float]) -> float | None:
    if len(a) != len(b) or len(a) < 2:
        return None
    ma, mb = stats.mean(a), stats.mean(b)
    da = [value - ma for value in a]
    db = [value - mb for value in b]
    denominator = math.sqrt(sum(value * value for value in da) * sum(value * value for value in db))
    if denominator <= 1e-15:
        return None
    return sum(x * y for x, y in zip(da, db)) / denominator


def spearman(a: list[float], b: list[float]) -> float | None:
    return pearson(average_ranks(a), average_ranks(b))


def split_episodes(captures: list[dict]) -> list[list[dict]]:
    episodes: list[list[dict]] = []
    current: list[dict] = []
    previous: dict | None = None
    for capture in captures:
        applied = bool(capture.get("applied"))
        adjacent = (
            previous is not None
            and bool(previous.get("applied"))
            and capture["wave"] == previous["wave"]
            and 0 < capture["ts_ms"] - previous["ts_ms"] <= EPISODE_MAX_GAP_MS
        )
        if applied:
            if not adjacent and current:
                episodes.append(current)
                current = []
            current.append(capture)
        elif current:
            episodes.append(current)
            current = []
        previous = capture
    if current:
        episodes.append(current)
    return episodes


def nearest_future(
    captures: list[dict], timestamps: list[int], start_index: int, offset_ms: int
) -> dict | None:
    target = captures[start_index]["ts_ms"] + offset_ms
    position = bisect_left(timestamps, target, lo=start_index + 1)
    candidates = []
    for index in (position - 1, position):
        if index <= start_index or index >= len(captures):
            continue
        candidate = captures[index]
        if candidate["wave"] != captures[start_index]["wave"]:
            continue
        candidates.append(candidate)
    if not candidates:
        return None
    best = min(candidates, key=lambda row: abs(row["ts_ms"] - target))
    return best if abs(best["ts_ms"] - target) <= FUTURE_TOLERANCE_MS else None


def living_threats(payload: dict, counters: dict[str, int]) -> dict[int, dict]:
    out: dict[int, dict] = {}
    seen: set[int] = set()
    duplicate = False
    entities = payload.get("entities") or {}
    for threat in (entities.get("enemies") or []) + (entities.get("bosses") or []):
        try:
            if float(threat.get("hp", 1.0)) <= 0:
                continue
        except (TypeError, ValueError):
            continue
        counters["living_threats"] += 1
        instance_id = threat.get("instance_id")
        if instance_id is None:
            counters["missing_instance_id"] += 1
            continue
        try:
            key = int(instance_id)
        except (TypeError, ValueError):
            counters["missing_instance_id"] += 1
            continue
        counters["identified_threats"] += 1
        if key in seen:
            duplicate = True
            continue
        seen.add(key)
        out[key] = threat
    counters["duplicate_id_captures"] += duplicate
    return out


def scan_run(run_id: str) -> dict:
    run_path = runs_dir() / run_id
    summary = json.loads((run_path / "summary.json").read_text(encoding="utf-8"))
    counters = {
        "raw_captures": 0,
        "fresh_captures": 0,
        "stale_captures": 0,
        "nonincreasing_ts": 0,
        "applied": 0,
        "nonconversion_routes": 0,
        "heading_seen": 0,
        "heading_match": 0,
        "living_threats": 0,
        "identified_threats": 0,
        "missing_instance_id": 0,
        "duplicate_id_captures": 0,
        "parse_errors": 0,
    }
    captures = []
    last_capture_seq: int | None = None
    last_ts: int | None = None
    with (run_path / "events.jsonl").open(encoding="utf-8", errors="replace") as handle:
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
            wave = payload.get("wave")
            if not isinstance(wave, int) or not 1 <= wave <= 11:
                continue
            counters["raw_captures"] += 1
            capture_seq = payload.get("capture_seq")
            ts_ms = event.get("ts_ms")
            if not isinstance(capture_seq, int) or not isinstance(ts_ms, int):
                counters["stale_captures"] += 1
                continue
            if last_capture_seq is not None and capture_seq <= last_capture_seq:
                counters["stale_captures"] += 1
                continue
            if last_ts is not None and ts_ms <= last_ts:
                counters["nonincreasing_ts"] += 1
                continue
            last_capture_seq, last_ts = capture_seq, ts_ms
            counters["fresh_captures"] += 1
            route = (((payload.get("teacher") or {}).get("contributions") or {}).get("route") or {})
            action = (payload.get("teacher") or {}).get("action") or {}
            applied = bool(route.get("conversion_applied", False))
            counters["applied"] += applied
            counters["nonconversion_routes"] += bool(route) and not applied
            if applied:
                try:
                    route_heading = normalized(float(route["sel_x"]), float(route["sel_y"]))
                    action_heading = normalized(float(action["x"]), float(action["y"]))
                except (KeyError, TypeError, ValueError):
                    route_heading = action_heading = None
                if route_heading is not None and action_heading is not None:
                    counters["heading_seen"] += 1
                    distance = math.hypot(
                        route_heading[0] - action_heading[0],
                        route_heading[1] - action_heading[1],
                    )
                    counters["heading_match"] += distance <= 0.001
            threat_counters = {
                "living_threats": 0,
                "identified_threats": 0,
                "missing_instance_id": 0,
                "duplicate_id_captures": 0,
            }
            threats = living_threats(payload, threat_counters)
            for key, value in threat_counters.items():
                counters[key] += value
            player = payload.get("player") or {}
            ranges = []
            for weapon in payload.get("weapons") or []:
                try:
                    value = float(weapon.get("max_range", 0) or 0)
                except (TypeError, ValueError):
                    continue
                if value > 0:
                    ranges.append(value)
            try:
                position = (float(player["x"]), float(player["y"]))
                speed = float(player.get("speed", 0) or 0)
            except (KeyError, TypeError, ValueError):
                position, speed = None, 0.0
            try:
                action_heading = normalized(float(action["x"]), float(action["y"]))
            except (KeyError, TypeError, ValueError):
                action_heading = None
            captures.append(
                {
                    "run_id": run_id,
                    "index": len(captures),
                    "capture_seq": capture_seq,
                    "ts_ms": ts_ms,
                    "wave": wave,
                    "applied": applied,
                    "route": route,
                    "action_heading": action_heading,
                    "position": position,
                    "speed": speed,
                    "max_range": max(ranges, default=0.0),
                    "threats": threats,
                }
            )
    intervals = [
        captures[index]["ts_ms"] - captures[index - 1]["ts_ms"]
        for index in range(1, len(captures))
        if captures[index]["wave"] == captures[index - 1]["wave"]
        and captures[index]["ts_ms"] > captures[index - 1]["ts_ms"]
    ]
    return {
        "run_id": run_id,
        "summary": summary,
        "captures": captures,
        "counters": counters,
        "median_interval_ms": stats.median(intervals) if intervals else None,
    }


def summary_faults(run: dict) -> list[str]:
    summary = run["summary"]
    expected = {
        "policy_version": POLICY,
        "mod_version": BUILD,
        "character_observed": "character_ranger",
        "danger": 5,
        "requested_danger": 5,
        "weapon": "weapon_pistol_1",
        "danger_ok": True,
        "telemetry_complete": True,
        "clearance_guarded_conversion": True,
        "unlock_pool": ERA,
    }
    faults = [
        f"{key}={summary.get(key)!r} expected={value!r}"
        for key, value in expected.items()
        if summary.get(key) != value
    ]
    for key in ("errors", "hangs", "illegal_actions", "nonfinite_fixed"):
        if int(summary.get(key, 0) or 0) != 0:
            faults.append(f"{key}={summary.get(key)!r}")
    if str(summary.get("result", "")).lower() not in {"victory", "defeat"}:
        faults.append(f"result={summary.get('result')!r}")
    if run["counters"]["parse_errors"]:
        faults.append(f"parse_errors={run['counters']['parse_errors']}")
    return faults


def analyse_episodes(run: dict) -> tuple[list[dict], dict]:
    captures = run["captures"]
    timestamps = [capture["ts_ms"] for capture in captures]
    interval_ms = float(run["median_interval_ms"] or 50.0)
    episodes = split_episodes(captures)
    diagnostics = []
    exclusions = {
        "episode_starts": len(episodes),
        "missing_start_inputs": 0,
        "missing_future_600": 0,
        "matched_future_600": 0,
        "matched_future_200": 0,
        "cohort_bookkeeping_fail": 0,
        "survivor_zero": 0,
    }
    for episode in episodes:
        start = episode[0]
        start_index = start["index"]
        duration = (episode[-1]["ts_ms"] - start["ts_ms"] + interval_ms) / 1000.0
        if (
            start["position"] is None
            or start["action_heading"] is None
            or start["speed"] <= 0
            or start["max_range"] <= 0
            or not start["threats"]
        ):
            exclusions["missing_start_inputs"] += 1
            continue
        future = nearest_future(captures, timestamps, start_index, HORIZON_MS)
        if future is None or future["position"] is None:
            exclusions["missing_future_600"] += 1
            continue
        exclusions["matched_future_600"] += 1
        future_200 = nearest_future(captures, timestamps, start_index, 200)
        if future_200 is not None:
            exclusions["matched_future_200"] += 1
        ux, uy = start["action_heading"]
        dx = future["position"][0] - start["position"][0]
        dy = future["position"][1] - start["position"][1]
        denominator = start["speed"] * (HORIZON_MS / 1000.0)
        forward = (dx * ux + dy * uy) / denominator
        lateral = abs(dx * uy - dy * ux) / denominator
        original = start["threats"]
        future_threats = future["threats"]
        resolved = 0
        survivor_in_range = 0
        survivor_out_range = 0
        for instance_id in original:
            threat = future_threats.get(instance_id)
            if threat is None:
                resolved += 1
                continue
            try:
                distance = math.hypot(
                    float(threat["x"]) - future["position"][0],
                    float(threat["y"]) - future["position"][1],
                )
            except (KeyError, TypeError, ValueError):
                survivor_out_range += 1
                continue
            if distance <= start["max_range"]:
                survivor_in_range += 1
            else:
                survivor_out_range += 1
        cohort_n = len(original)
        if resolved + survivor_in_range + survivor_out_range != cohort_n:
            exclusions["cohort_bookkeeping_fail"] += 1
        survivors = survivor_in_range + survivor_out_range
        if survivors == 0:
            exclusions["survivor_zero"] += 1
        heading_dot_200 = None
        if future_200 is not None and future_200["action_heading"] is not None:
            heading_dot_200 = ux * future_200["action_heading"][0] + uy * future_200["action_heading"][1]
        heading_dot_600 = None
        if future["action_heading"] is not None:
            heading_dot_600 = ux * future["action_heading"][0] + uy * future["action_heading"][1]
        diagnostics.append(
            {
                "run_id": run["run_id"],
                "wave": start["wave"],
                "duration_sec": duration,
                "episode_captures": len(episode),
                "projected_gain": float(start["route"].get("conversion_gain", 0.0)),
                "projected_selected": float(
                    start["route"].get("conversion_selected_inrange", -1.0)
                ),
                "forward_progress": forward,
                "lateral_progress": lateral,
                "heading_dot_200": heading_dot_200,
                "heading_dot_600": heading_dot_600,
                "cohort_n": cohort_n,
                "resolved": resolved,
                "survivor_in_range": survivor_in_range,
                "survivor_out_range": survivor_out_range,
                "resolved_or_in_range": (resolved + survivor_in_range) / cohort_n,
                "survivor_in_range_fraction": (
                    survivor_in_range / survivors if survivors else None
                ),
            }
        )
    return diagnostics, exclusions


def quantiles(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"p10": None, "median": None, "p90": None}
    ordered = sorted(values)
    def percentile(p: float) -> float:
        position = (len(ordered) - 1) * p
        lower = math.floor(position)
        upper = math.ceil(position)
        if lower == upper:
            return ordered[lower]
        return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)
    return {"p10": percentile(0.10), "median": percentile(0.50), "p90": percentile(0.90)}


def gain_by_duration_band(rows: list[dict]) -> dict[str, dict[str, Any]]:
    bands = {
        "lt_030": [row["projected_gain"] for row in rows if row["duration_sec"] < 0.30],
        "ge_030_lt_060": [
            row["projected_gain"]
            for row in rows
            if 0.30 <= row["duration_sec"] < 0.60
        ],
        "ge_060": [row["projected_gain"] for row in rows if row["duration_sec"] >= 0.60],
    }
    return {
        name: {"n": len(values), "gain": quantiles(values)}
        for name, values in bands.items()
    }


def self_test() -> None:
    def row(ts: int, applied: bool, wave: int = 1) -> dict:
        return {"ts_ms": ts, "applied": applied, "wave": wave}
    episodes = split_episodes([row(0, True), row(50, True), row(100, False), row(150, True)])
    assert [len(episode) for episode in episodes] == [2, 1]
    assert [len(episode) for episode in split_episodes([row(0, True), row(101, True)])] == [1, 1]
    assert normalized(3, 4) == (0.6, 0.8)
    captures = [{"ts_ms": 0, "wave": 1}, {"ts_ms": 590, "wave": 1}, {"ts_ms": 620, "wave": 1}]
    assert nearest_future(captures, [0, 590, 620], 0, 600)["ts_ms"] == 590
    counters = {"living_threats": 0, "identified_threats": 0, "missing_instance_id": 0, "duplicate_id_captures": 0}
    payload = {"entities": {"enemies": [{"hp": 1, "instance_id": 7}], "bosses": []}}
    assert set(living_threats(payload, counters)) == {7}
    assert not living_threats({"entities": {}}, {key: 0 for key in counters})
    assert spearman([1, 2, 3], [1, 2, 3]) == 1.0
    assert spearman([1, 2, 3], [3, 2, 1]) == -1.0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("reports/wp2/route_conversion_persistence_result.json"),
    )
    args = parser.parse_args()
    self_test()
    runs = [scan_run(run_id) for run_id in RUN_IDS]

    print("=" * 88)
    print("STEP 1 — VALIDITY AND INSTRUMENT CONTROLS (BEFORE DIAGNOSTICS)")
    print("=" * 88)
    faults: list[str] = []
    for run in runs:
        run_faults = summary_faults(run)
        c = run["counters"]
        if c["applied"] <= 0 or c["nonconversion_routes"] <= 0:
            run_faults.append(
                f"positive/negative route control applied={c['applied']} nonconversion={c['nonconversion_routes']}"
            )
        if c["nonincreasing_ts"]:
            run_faults.append(f"nonincreasing_ts={c['nonincreasing_ts']}")
        faults.extend(f"{run['run_id']}: {fault}" for fault in run_faults)
        print(
            f"{run['run_id']}: raw={c['raw_captures']} fresh={c['fresh_captures']} "
            f"stale={c['stale_captures']} applied={c['applied']} "
            f"nonconversion={c['nonconversion_routes']} median_dt_ms={run['median_interval_ms']} "
            f"faults={len(run_faults)}"
        )
        for fault in run_faults:
            print(f"  FAULT: {fault}")
    counters = {
        key: sum(run["counters"][key] for run in runs)
        for key in runs[0]["counters"]
    }
    heading_rate = counters["heading_match"] / counters["heading_seen"] if counters["heading_seen"] else 0.0
    id_rate = counters["identified_threats"] / counters["living_threats"] if counters["living_threats"] else 0.0
    print(f"emitted/selected heading match: {counters['heading_match']}/{counters['heading_seen']}={heading_rate:.6f} (bar >=0.999)")
    print(f"identified living threats: {counters['identified_threats']}/{counters['living_threats']}={id_rate:.6f} (bar >=0.999)")
    print(f"duplicate-ID captures: {counters['duplicate_id_captures']}/{counters['fresh_captures']}")
    if heading_rate < 0.999:
        faults.append(f"heading match rate={heading_rate}")
    if id_rate < 0.999 or counters["duplicate_id_captures"]:
        faults.append(f"identity control rate={id_rate}, duplicates={counters['duplicate_id_captures']}")

    diagnostics: list[dict] = []
    per_run_exclusions = {}
    for run in runs:
        rows, exclusions = analyse_episodes(run)
        diagnostics.extend(rows)
        per_run_exclusions[run["run_id"]] = exclusions
        coverage_denominator = exclusions["episode_starts"] - exclusions["missing_start_inputs"]
        coverage = exclusions["matched_future_600"] / coverage_denominator if coverage_denominator else 0.0
        print(
            f"{run['run_id']}: episodes={exclusions['episode_starts']} "
            f"start_input_excluded={exclusions['missing_start_inputs']} "
            f"future600={exclusions['matched_future_600']}/{coverage_denominator}={coverage:.6f} "
            f"cohort_fail={exclusions['cohort_bookkeeping_fail']}"
        )
        if coverage < 0.90:
            faults.append(f"{run['run_id']}: future coverage={coverage}")
        if exclusions["cohort_bookkeeping_fail"]:
            faults.append(f"{run['run_id']}: cohort bookkeeping failures")
    total_episode_starts = sum(row["episode_starts"] for row in per_run_exclusions.values())
    total_start_excluded = sum(row["missing_start_inputs"] for row in per_run_exclusions.values())
    total_matched = sum(row["matched_future_600"] for row in per_run_exclusions.values())
    total_coverage_denominator = total_episode_starts - total_start_excluded
    total_coverage = total_matched / total_coverage_denominator if total_coverage_denominator else 0.0
    print(f"pooled future600 coverage: {total_matched}/{total_coverage_denominator}={total_coverage:.6f}")
    if total_coverage < 0.90 or len(diagnostics) < 30:
        faults.append(f"pooled matched episodes={len(diagnostics)}, coverage={total_coverage}")

    print("\n" + "=" * 88)
    print("STEP 2 — TEMPORAL PERSISTENCE")
    print("=" * 88)
    durations = [row["duration_sec"] for row in diagnostics]
    duration_q = quantiles(durations)
    fraction_030 = sum(value >= 0.30 for value in durations) / len(durations) if durations else 0.0
    fraction_060 = sum(value >= 0.60 for value in durations) / len(durations) if durations else 0.0
    print(f"matched episodes n={len(durations)} duration={duration_q}")
    print(f"duration >=0.30s: {sum(v >= 0.30 for v in durations)}/{len(durations)}={fraction_030:.6f}")
    print(f"duration >=0.60s: {sum(v >= 0.60 for v in durations)}/{len(durations)}={fraction_060:.6f}")
    for run_id in RUN_IDS:
        values = [row["duration_sec"] for row in diagnostics if row["run_id"] == run_id]
        print(f"  {run_id}: n={len(values)} duration={quantiles(values)}")
    transient = bool(durations) and (duration_q["median"] < 0.30 or fraction_060 < 0.25)

    print("\n" + "=" * 88)
    print("STEP 3 — EXECUTED DISPLACEMENT AT 0.60 S")
    print("=" * 88)
    forwards = [row["forward_progress"] for row in diagnostics]
    laterals = [row["lateral_progress"] for row in diagnostics]
    forward_q, lateral_q = quantiles(forwards), quantiles(laterals)
    print(f"forward progress n={len(forwards)} {forward_q} (median bar >=0.50)")
    print(f"lateral progress n={len(laterals)} {lateral_q}")
    for run_id in RUN_IDS:
        values = [row["forward_progress"] for row in diagnostics if row["run_id"] == run_id]
        print(f"  {run_id}: n={len(values)} forward={quantiles(values)}")
    reversal = bool(forwards) and forward_q["median"] < 0.50

    print("\n" + "=" * 88)
    print("STEP 4 — ORIGINAL-COHORT PROJECTION CALIBRATION")
    print("=" * 88)
    projected = [row["projected_selected"] for row in diagnostics]
    realised = [row["resolved_or_in_range"] for row in diagnostics]
    absolute_errors = [abs(a - b) for a, b in zip(projected, realised)]
    median_absolute_error = stats.median(absolute_errors) if absolute_errors else None
    rho = spearman(projected, realised)
    survivor_values = [
        row["survivor_in_range_fraction"]
        for row in diagnostics
        if row["survivor_in_range_fraction"] is not None
    ]
    resolved_share = [row["resolved"] / row["cohort_n"] for row in diagnostics]
    print(f"resolved-or-in-range n={len(realised)} median={stats.median(realised) if realised else None}")
    print(f"selected projection n={len(projected)} median={stats.median(projected) if projected else None}")
    print(f"median absolute error={median_absolute_error} (bar <=0.20)")
    print(f"Spearman rho={rho} (bar >=0.30)")
    print(f"resolved share n={len(resolved_share)} {quantiles(resolved_share)}")
    print(f"survivor-only in-range n={len(survivor_values)} {quantiles(survivor_values)}")
    miscalibrated = (
        len(diagnostics) >= 30
        and (
            median_absolute_error is None
            or median_absolute_error > 0.20
            or rho is None
            or rho < 0.30
        )
    )

    print("\n" + "=" * 88)
    print("STEP 4B — REPORTED CONTEXT (NON-DECIDING)")
    print("=" * 88)
    capture_conversion_rate = (
        counters["applied"] / counters["fresh_captures"]
        if counters["fresh_captures"]
        else 0.0
    )
    episode_counts = {
        run_id: per_run_exclusions[run_id]["episode_starts"] for run_id in RUN_IDS
    }
    gain_bands = gain_by_duration_band(diagnostics)
    heading_200 = [
        row["heading_dot_200"]
        for row in diagnostics
        if row["heading_dot_200"] is not None
    ]
    heading_600 = [
        row["heading_dot_600"]
        for row in diagnostics
        if row["heading_dot_600"] is not None
    ]
    cohort_sizes = [float(row["cohort_n"]) for row in diagnostics]
    wave_counts = {
        str(wave): sum(row["wave"] == wave for row in diagnostics)
        for wave in range(1, 12)
    }
    terminal_waves = {
        run["run_id"]: int(run["summary"]["last_wave"]) for run in runs
    }
    print(
        f"all-capture conversion: {counters['applied']}/{counters['fresh_captures']}="
        f"{capture_conversion_rate:.6f}"
    )
    print(f"episode concentration: {episode_counts}")
    print(f"projected gain by duration band: {gain_bands}")
    print(f"heading dot at +0.20s n={len(heading_200)} {quantiles(heading_200)}")
    print(f"heading dot at +0.60s n={len(heading_600)} {quantiles(heading_600)}")
    print(f"original cohort size n={len(cohort_sizes)} {quantiles(cohort_sizes)}")
    print(f"wave distribution: {wave_counts}")
    print(f"terminal waves (context only): {terminal_waves}")

    if faults:
        status = "VOID"
        labels: list[str] = []
    else:
        labels = []
        if transient or reversal:
            labels.append("TRANSIENT_REVERSAL")
        if miscalibrated:
            labels.append("PROJECTION_MISCALIBRATION")
        if not labels:
            labels.append("PERSISTENT_BUT_INSUFFICIENT")
        status = "PASS"
    print("\n" + "=" * 88)
    print("STEP 5 — DIAGNOSTIC DECISION")
    print("=" * 88)
    for fault in faults:
        print(f"CONTROL FAULT: {fault}")
    print(f"transient={transient} reversal={reversal} miscalibrated={miscalibrated}")
    print(f"VERDICT: {status} labels={labels}")

    result = {
        "status": status,
        "labels": labels,
        "control_faults": faults,
        "runs": list(RUN_IDS),
        "controls": {
            "capture_counters": counters,
            "heading_match_rate": heading_rate,
            "instance_id_rate": id_rate,
            "future_coverage": total_coverage,
            "per_run_exclusions": per_run_exclusions,
        },
        "temporal": {
            "episodes": len(durations),
            "duration": duration_q,
            "fraction_ge_030": fraction_030,
            "fraction_ge_060": fraction_060,
            "transient": transient,
        },
        "execution": {
            "forward": forward_q,
            "lateral": lateral_q,
            "reversal": reversal,
        },
        "calibration": {
            "n": len(realised),
            "median_absolute_error": median_absolute_error,
            "spearman": rho,
            "resolved_share": quantiles(resolved_share),
            "survivor_in_range": quantiles(survivor_values),
            "miscalibrated": miscalibrated,
        },
        "reported_context": {
            "all_capture_conversion": {
                "numerator": counters["applied"],
                "denominator": counters["fresh_captures"],
                "rate": capture_conversion_rate,
            },
            "episode_counts": episode_counts,
            "projected_gain_by_duration_band": gain_bands,
            "heading_dot_200": {"n": len(heading_200), "distribution": quantiles(heading_200)},
            "heading_dot_600": {"n": len(heading_600), "distribution": quantiles(heading_600)},
            "cohort_size": {"n": len(cohort_sizes), "distribution": quantiles(cohort_sizes)},
            "wave_counts": wave_counts,
            "terminal_waves_context_only": terminal_waves,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {args.output}")
    return 0 if status == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
