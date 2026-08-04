#!/usr/bin/env python3
"""§44 offline shadow gate for a safety-revalidated conversion latch."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
import math
import os
from pathlib import Path
import statistics as stats
import sys
from typing import Any

import wp2_clearance_guarded_conversion_gate0 as guard
import wp2_joint_route_conversion_gate0 as base


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HORIZON_MS = 600
FUTURE_TOLERANCE_MS = 75
ANGLE_LIMIT_DEG = 15.1
OBSERVABILITY_BAR = 0.90


def runs_dir() -> Path:
    return Path(os.environ["APPDATA"]) / "Brotato" / "brotato_agent" / "runs"


def quantiles(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"p10": None, "median": None, "p90": None}
    ordered = sorted(float(value) for value in values)

    def percentile(p: float) -> float:
        position = (len(ordered) - 1) * p
        lower, upper = math.floor(position), math.ceil(position)
        if lower == upper:
            return ordered[lower]
        return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)

    return {"p10": percentile(0.10), "median": percentile(0.50), "p90": percentile(0.90)}


def unit(row: dict) -> tuple[float, float] | None:
    x, y = float(row.get("x", 0)), float(row.get("y", 0))
    length = math.hypot(x, y)
    return (x / length, y / length) if length > 1e-12 else None


def angular_distance_deg(a: tuple[float, float], b: tuple[float, float]) -> float:
    dot = max(-1.0, min(1.0, a[0] * b[0] + a[1] * b[1]))
    return math.degrees(math.acos(dot))


def choose_near_heading(
    candidates: list[dict], heading: tuple[float, float]
) -> tuple[dict | None, float | None]:
    choices = []
    for candidate in candidates:
        candidate_heading = unit(candidate)
        if candidate_heading is None:
            continue
        choices.append((angular_distance_deg(candidate_heading, heading), candidate))
    if not choices:
        return None, None
    angle, candidate = min(choices, key=lambda value: (value[0], base.key(value[1])))
    return candidate, angle


def stateless_selected(capture: dict) -> dict:
    if capture.get("trigger_evaluated"):
        return capture.get("trigger_selected", capture["current"])
    admitted = guard.pack80_pool(capture)
    guarded = guard.guarded_candidates(admitted, capture["current"])
    return guard.choose(capture, guarded)


def retained_candidate(
    capture: dict, heading: tuple[float, float]
) -> tuple[dict | None, float | None, list[dict]]:
    admitted = capture.get("revalidation_admitted")
    if admitted is None:
        admitted = guard.pack80_pool(capture)
    guarded = guard.guarded_candidates(admitted, capture["current"])
    candidate, angle = choose_near_heading(guarded, heading)
    if candidate is None or angle is None or angle > ANGLE_LIMIT_DEG:
        return None, angle, guarded
    return candidate, angle, guarded


def scan_fresh_streams(root: Path, analysis_captures: list[dict]) -> tuple[dict, Counter]:
    analysis_map = {
        (row["run_id"], int(row["capture_seq"])): row
        for row in analysis_captures
        if isinstance(row.get("capture_seq"), int)
    }
    streams: dict[str, list[dict]] = defaultdict(list)
    counters = Counter()
    for run_id in sorted(base.EXPECTED_RUNS):
        last_seq: int | None = None
        last_ts: int | None = None
        path = root / run_id / "events.jsonl"
        with path.open(encoding="utf-8", errors="replace") as handle:
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
                counters["raw"] += 1
                capture_seq, ts_ms = payload.get("capture_seq"), event.get("ts_ms")
                if not isinstance(capture_seq, int) or not isinstance(ts_ms, int):
                    counters["stale"] += 1
                    continue
                if last_seq is not None and capture_seq <= last_seq:
                    counters["stale"] += 1
                    continue
                if last_ts is not None and ts_ms <= last_ts:
                    counters["nonincreasing_ts"] += 1
                    continue
                last_seq, last_ts = capture_seq, ts_ms
                counters["fresh"] += 1
                route = (((payload.get("teacher") or {}).get("contributions") or {}).get("route") or {})
                streams[run_id].append(
                    {
                        "run_id": run_id,
                        "capture_seq": capture_seq,
                        "ts_ms": ts_ms,
                        "wave": wave,
                        "route_exit": route.get("exit", "missing"),
                        "analysis": analysis_map.get((run_id, capture_seq)),
                    }
                )
    return dict(streams), counters


def median_intervals(stream: list[dict]) -> float:
    values = [
        stream[index]["ts_ms"] - stream[index - 1]["ts_ms"]
        for index in range(1, len(stream))
        if stream[index]["wave"] == stream[index - 1]["wave"]
        and stream[index]["ts_ms"] > stream[index - 1]["ts_ms"]
    ]
    return float(stats.median(values)) if values else 50.0


def has_matched_future(stream: list[dict], start_index: int) -> bool:
    start = stream[start_index]
    target = start["ts_ms"] + HORIZON_MS
    return any(
        row["wave"] == start["wave"]
        and abs(row["ts_ms"] - target) <= FUTURE_TOLERANCE_MS
        for row in stream[start_index + 1 :]
    )


def simulate_run(stream: list[dict]) -> dict:
    interval_ms = median_intervals(stream)
    counters = Counter()
    releases = Counter()
    retained_rows: list[dict] = []
    episodes: list[dict] = []
    suppressed_by_wave = Counter()
    active: dict | None = None

    def close(reason: str) -> None:
        nonlocal active
        if active is None:
            return
        active["release_reason"] = reason
        active["duration_sec"] = min(
            HORIZON_MS / 1000.0,
            (active["last_retained_ts"] - active["start_ts"] + interval_ms) / 1000.0,
        )
        releases[reason] += 1
        episodes.append(active)
        active = None

    for index, row in enumerate(stream):
        capture = row["analysis"]
        if active is not None:
            if row["wave"] != active["wave"]:
                close("wave_change")
                continue
            elapsed = row["ts_ms"] - active["start_ts"]
            if elapsed > HORIZON_MS + FUTURE_TOLERANCE_MS:
                close("missing_future_window")
                continue
            counters["active_future_captures"] += 1
            counters[f"active_exit:{row['route_exit']}"] += 1
            if capture is None:
                counters["unobservable_future_captures"] += 1
                close(f"unobservable_{row['route_exit']}")
                continue
            counters["observable_future_captures"] += 1
            counters[f"observable_exit:{row['route_exit']}"] += 1
            selected_now = stateless_selected(capture)
            if base.key(selected_now) != base.key(capture["current"]):
                counters["suppressed_overlapping_triggers"] += 1
                suppressed_by_wave[row["wave"]] += 1
            candidate, angle, guarded = retained_candidate(capture, active["heading"])
            if candidate is None:
                counters["no_near_safe_candidate"] += 1
                close("no_near_safe_candidate")
                continue
            old_body = float(capture["current"].get("body", 0))
            new_body = float(candidate.get("body", 0))
            projectile_ok = float(candidate.get("proj", -1e18)) >= capture["projectile_floor"]
            body_ok = guard.body_guard_ok(new_body, old_body)
            subcritical_ok = new_body >= base.CRITICAL or new_body >= old_body
            admitted_for_check = capture.get("revalidation_admitted")
            if admitted_for_check is None:
                admitted_for_check = guard.pack80_pool(capture)
            enemy_ok = base.key(candidate) in {
                base.key(item) for item in admitted_for_check
            }
            angle_ok = angle is not None and angle <= ANGLE_LIMIT_DEG
            counters["retained_steps"] += 1
            counters["projectile_ok"] += projectile_ok
            counters["body_ok"] += body_ok
            counters["subcritical_ok"] += subcritical_ok
            counters["enemy_ok"] += enemy_ok
            counters["angle_ok"] += angle_ok
            changed = base.key(candidate) != base.key(capture["current"])
            counters["override_steps"] += changed
            active["last_retained_ts"] = row["ts_ms"]
            active["retained_future_steps"] += 1
            retained_rows.append(
                {
                    "run_id": row["run_id"],
                    "wave": row["wave"],
                    "angle_deg": angle,
                    "body_ratio": new_body / old_body if old_body > 0 else None,
                    "projected_inrange_delta": (
                        capture["inrange"][base.key(candidate)]
                        - capture["inrange"][base.key(capture["current"])]
                    ),
                    "recorded_command_angle_deg": angular_distance_deg(
                        unit(candidate), unit(capture["current"])
                    ),
                    "override": changed,
                }
            )
            if (
                elapsed >= HORIZON_MS
                and abs(elapsed - HORIZON_MS) <= FUTURE_TOLERANCE_MS
            ):
                active["reached_horizon"] = True
                close("horizon")
            continue

        if capture is None:
            continue
        selected = stateless_selected(capture)
        if base.key(selected) == base.key(capture["current"]):
            counters["stateful_nontriggers"] += 1
            continue
        heading = unit(selected)
        if heading is None:
            counters["degenerate_trigger"] += 1
            continue
        counters["stateful_triggers"] += 1
        active = {
            "run_id": row["run_id"],
            "wave": row["wave"],
            "start_index": index,
            "start_ts": row["ts_ms"],
            "last_retained_ts": row["ts_ms"],
            "heading": heading,
            "initial_gain": (
                capture["inrange"][base.key(selected)]
                - capture["inrange"][base.key(capture["current"])]
            ),
            "retained_future_steps": 0,
            "future_matched": has_matched_future(stream, index),
            "reached_horizon": False,
        }

    close("stream_end")
    return {
        "episodes": episodes,
        "retained_rows": retained_rows,
        "counters": counters,
        "releases": releases,
        "suppressed_by_wave": suppressed_by_wave,
        "median_interval_ms": interval_ms,
    }


def synthetic_capture(
    ts_ms: int,
    *,
    trigger: bool = False,
    candidate_angle: float = 90.0,
    candidate_body: float = 100.0,
) -> dict:
    current = {"x": 1.0, "y": 0.0, "body": 100.0, "proj": 100.0, "pen": 0.0}
    radians = math.radians(candidate_angle)
    candidate = {
        "x": math.cos(radians),
        "y": math.sin(radians),
        "body": candidate_body,
        "proj": 100.0,
        "pen": 0.0,
    }
    rows = [current, candidate]
    inrange = {base.key(current): 0.0, base.key(candidate): 0.2 if trigger else 0.0}
    analysis = {
        "run_id": "synthetic",
        "wave": 1,
        "rows": rows,
        "projectile_floor": 0.0,
        "loot_dash": False,
        "baseline": (1.0, 0.0),
        "previous": (1.0, 0.0),
        "current": current,
        "inrange": inrange,
    }
    return {
        "run_id": "synthetic",
        "capture_seq": ts_ms // 50,
        "ts_ms": ts_ms,
        "wave": 1,
        "route_exit": "ranked",
        "analysis": analysis,
    }


def self_test() -> None:
    assert angular_distance_deg((1, 0), (0, 1)) == 90.0
    c15 = {"x": math.cos(math.radians(15)), "y": math.sin(math.radians(15))}
    c16 = {"x": math.cos(math.radians(16)), "y": math.sin(math.radians(16))}
    assert choose_near_heading([c15], (1, 0))[1] <= ANGLE_LIMIT_DEG
    assert choose_near_heading([c16], (1, 0))[1] > ANGLE_LIMIT_DEG

    stream = [synthetic_capture(0, trigger=True)]
    stream.extend(synthetic_capture(ts, candidate_angle=90) for ts in range(50, 601, 50))
    result = simulate_run(stream)
    assert result["counters"]["stateful_triggers"] == 1
    assert result["counters"]["suppressed_overlapping_triggers"] == 0
    assert result["episodes"][0]["reached_horizon"] is True
    assert result["episodes"][0]["duration_sec"] == 0.6

    overlap = [synthetic_capture(0, trigger=True)]
    overlap.extend(synthetic_capture(ts, trigger=True) for ts in range(50, 601, 50))
    overlap_result = simulate_run(overlap)
    assert overlap_result["counters"]["suppressed_overlapping_triggers"] == 12

    unsafe = [synthetic_capture(0, trigger=True), synthetic_capture(50, candidate_body=40)]
    unsafe_result = simulate_run(unsafe)
    assert unsafe_result["episodes"][0]["release_reason"] == "no_near_safe_candidate"

    missing = [synthetic_capture(0, trigger=True), synthetic_capture(50)]
    missing[1]["analysis"] = None
    missing[1]["route_exit"] = "baseline_kept"
    missing_result = simulate_run(missing)
    assert missing_result["episodes"][0]["release_reason"] == "unobservable_baseline_kept"
    assert missing_result["episodes"][0]["future_matched"] is False

    wave = [synthetic_capture(0, trigger=True), synthetic_capture(50)]
    wave[1]["wave"] = 2
    wave_result = simulate_run(wave)
    assert wave_result["episodes"][0]["release_reason"] == "wave_change"


def control_rate(counter: Counter, ok: str, fail: str) -> tuple[float, int]:
    denominator = counter[ok] + counter[fail]
    return (counter[ok] / denominator if denominator else 0.0), denominator


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs-dir", type=Path, default=runs_dir())
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("reports/wp2/route_conversion_latch_gate0_result.json"),
    )
    args = parser.parse_args()
    self_test()

    scanned, summaries, arm_errors = base.select_runs(str(args.runs_dir))
    captures, base_controls, excluded, per_run, route_total, ranked_total = base.collect(
        str(args.runs_dir), summaries
    )
    floor_rate, floor_n = control_rate(base_controls, "floor_ok", "floor_fail")
    admission_rate, admission_n = control_rate(base_controls, "admission_ok", "admission_fail")
    selection_rate, selection_n = control_rate(base_controls, "selection_ok", "selection_fail")
    vector_rate, vector_n = control_rate(base_controls, "vector_ok", "vector_fail")
    flips, guarded_by_run, _, _, unguarded_flips = guard.evaluate(captures)
    streams, stream_controls = scan_fresh_streams(args.runs_dir, captures)

    disabled_changes = 0
    stateless_nontriggers = Counter()
    for capture in captures:
        admitted = guard.guarded_candidates(guard.pack80_pool(capture), capture["current"])
        disabled = guard.choose(capture, admitted, enabled=False)
        disabled_changes += base.key(disabled) != base.key(capture["current"])
        if base.key(guard.choose(capture, admitted)) == base.key(capture["current"]):
            stateless_nontriggers[capture["run_id"]] += 1

    print("=" * 88)
    print("STEP 1 — DENOMINATORS AND CONTROLS (BEFORE LATCH RESULTS)")
    print("=" * 88)
    print(f"expected/selected runs: 8/{len(summaries)} scanned={scanned} arm_errors={arm_errors}")
    print(f"route blocks={route_total} ranked={ranked_total} analysis={len(captures)} exclusions={dict(excluded)}")
    print(f"fresh stream={stream_controls['fresh']}/{stream_controls['raw']} stale={stream_controls['stale']} nonincreasing_ts={stream_controls['nonincreasing_ts']} parse_errors={stream_controls['parse_errors']}")
    print(f"vector={base_controls['vector_ok']}/{vector_n}={vector_rate:.6f}")
    print(f"floor={base_controls['floor_ok']}/{floor_n}={floor_rate:.6f}")
    print(f"admission={base_controls['admission_ok']}/{admission_n}={admission_rate:.6f}")
    print(f"selection={base_controls['selection_ok']}/{selection_n}={selection_rate:.6f}")
    print(f"stateless guarded flips={len(flips)}/{len(captures)} expected=11457/23501; unguarded={unguarded_flips} expected=15274; disabled={disabled_changes}")

    control_faults = []
    if len(summaries) != 8 or arm_errors:
        control_faults.append("run validity")
    if stream_controls["stale"] or stream_controls["nonincreasing_ts"] or stream_controls["parse_errors"]:
        control_faults.append("fresh sequence")
    if min(floor_rate, admission_rate, selection_rate, vector_rate) < 0.99:
        control_faults.append("production reconstruction")
    if len(captures) != 23501 or len(flips) != 11457 or unguarded_flips != 15274 or disabled_changes:
        control_faults.append("stateless §41 reproduction")

    simulations = {run_id: simulate_run(stream) for run_id, stream in streams.items()}
    episodes = [episode for result in simulations.values() for episode in result["episodes"]]
    retained = [row for result in simulations.values() for row in result["retained_rows"]]
    state_counters = sum((result["counters"] for result in simulations.values()), Counter())
    releases = sum((result["releases"] for result in simulations.values()), Counter())
    suppressed_by_wave = sum(
        (result["suppressed_by_wave"] for result in simulations.values()), Counter()
    )
    trigger_by_run = {run_id: result["counters"]["stateful_triggers"] for run_id, result in simulations.items()}
    nontrigger_by_run = {
        run_id: result["counters"]["stateful_nontriggers"] for run_id, result in simulations.items()
    }
    suppressed_by_run = {
        run_id: result["counters"]["suppressed_overlapping_triggers"]
        for run_id, result in simulations.items()
    }
    for run_id in sorted(base.EXPECTED_RUNS):
        print(f"{run_id}: stateful triggers={trigger_by_run.get(run_id, 0)} nontriggers={nontrigger_by_run.get(run_id, 0)} suppressed={suppressed_by_run.get(run_id, 0)} stateless_guarded={guarded_by_run[run_id]}")
        if trigger_by_run.get(run_id, 0) <= 0 or nontrigger_by_run.get(run_id, 0) <= 0:
            control_faults.append(f"{run_id}: missing trigger/nontrigger")

    retained_n = state_counters["retained_steps"]
    invariant_keys = ("projectile_ok", "body_ok", "subcritical_ok", "enemy_ok", "angle_ok")
    for key in invariant_keys:
        if state_counters[key] != retained_n:
            control_faults.append(f"{key}={state_counters[key]}/{retained_n}")
    print(f"retained safety projectile/body/subcritical/enemy/angle: " + "/".join(str(state_counters[key]) for key in invariant_keys) + f" / denominator={retained_n}")
    print(f"CONTROL VERDICT: {'PASS' if not control_faults else 'VOID'} faults={control_faults}")

    if control_faults:
        result = {"status": "VOID", "control_faults": control_faults}
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        return 2

    print("\n" + "=" * 88)
    print("STEP 2 — ARCHIVE OBSERVABILITY")
    print("=" * 88)
    active_future = state_counters["active_future_captures"]
    observable = state_counters["observable_future_captures"]
    observability = observable / active_future if active_future else 0.0
    print(f"reconstructable active futures: {observable}/{active_future}={observability:.6f} (adequacy bar >=0.90 for closing failure)")
    print(f"release reasons: {dict(releases)}")
    observability_by_run = {}
    for run_id, sim in simulations.items():
        denominator = sim["counters"]["active_future_captures"]
        numerator = sim["counters"]["observable_future_captures"]
        rate = numerator / denominator if denominator else 0.0
        observability_by_run[run_id] = {
            "reconstructable": numerator,
            "active_future": denominator,
            "rate": rate,
        }
        print(f"  {run_id}: {numerator}/{denominator}={rate:.6f}")

    print("\n" + "=" * 88)
    print("STEP 3 — TEMPORAL AVAILABILITY")
    print("=" * 88)
    durations = [episode["duration_sec"] for episode in episodes]
    eligible = [episode for episode in episodes if episode["future_matched"]]
    reached = [episode for episode in eligible if episode["reached_horizon"]]
    duration_q = quantiles(durations)
    fraction_030 = sum(value >= 0.30 for value in durations) / len(durations) if durations else 0.0
    horizon_rate = len(reached) / len(eligible) if eligible else 0.0
    reached_by_run = Counter(episode["run_id"] for episode in reached)
    eligible_by_run = Counter(episode["run_id"] for episode in eligible)
    trigger_by_wave = Counter(episode["wave"] for episode in episodes)
    loo = []
    for run_id in sorted(base.EXPECTED_RUNS):
        numerator = len(reached) - reached_by_run[run_id]
        denominator = len(eligible) - eligible_by_run[run_id]
        loo.append({"left_out_run": run_id, "reached": numerator, "eligible": denominator, "rate": numerator / denominator if denominator else 0.0})
    loo_rates = [row["rate"] for row in loo]
    contributing_runs = sum(reached_by_run[run_id] > 0 for run_id in base.EXPECTED_RUNS)
    largest_share = max(reached_by_run.values(), default=0) / len(reached) if reached else 0.0
    print(f"episodes n={len(episodes)} duration={duration_q}; >=0.30s {sum(v >= 0.30 for v in durations)}/{len(durations)}={fraction_030:.6f}")
    print(f"horizon reached: {len(reached)}/{len(eligible)}={horizon_rate:.6f}; missing future={len(episodes)-len(eligible)}/{len(episodes)}")
    print(f"runs contributing={contributing_runs}/8; LOO min/median={min(loo_rates) if loo_rates else 0.0:.6f}/{stats.median(loo_rates) if loo_rates else 0.0:.6f}; largest share={largest_share:.6f}")
    print(f"stateful triggers by wave: {dict(sorted(trigger_by_wave.items()))}")
    print(f"suppressed overlapping triggers by wave: {dict(sorted(suppressed_by_wave.items()))}")

    print("\n" + "=" * 88)
    print("STEP 4 — SAFETY AND COUNTERFACTUAL AUTHORITY")
    print("=" * 88)
    override_rate = state_counters["override_steps"] / retained_n if retained_n else 0.0
    print(f"retained future overrides: {state_counters['override_steps']}/{retained_n}={override_rate:.6f} (bar >=0.20)")
    print(f"angle={quantiles([row['angle_deg'] for row in retained])}")
    print(f"body ratio={quantiles([row['body_ratio'] for row in retained if row['body_ratio'] is not None])}")
    print(f"current projected in-range delta={quantiles([row['projected_inrange_delta'] for row in retained])}")
    print(f"recorded-command angular difference={quantiles([row['recorded_command_angle_deg'] for row in retained])}")
    initial_gain = quantiles([episode["initial_gain"] for episode in episodes])
    terminal_context = {
        run_id: int(summary.get("last_wave", 0))
        for run_id, summary in summaries.items()
    }
    print(f"first-trigger projected gain={initial_gain}")
    print(f"terminal waves (context only)={terminal_context}")

    bars = {
        "median_duration": duration_q["median"] is not None and duration_q["median"] >= 0.30,
        "horizon_rate": horizon_rate >= 0.25,
        "contributing_runs": contributing_runs >= 7,
        "loo_min": bool(loo_rates) and min(loo_rates) >= 0.20,
        "loo_median": bool(loo_rates) and stats.median(loo_rates) >= 0.25,
        "largest_run_share": largest_share <= 0.25,
        "safety_invariants": all(state_counters[key] == retained_n for key in invariant_keys),
        "override_rate": override_rate >= 0.20,
    }
    mechanism_pass = all(bars.values())
    status = "PASS" if mechanism_pass else ("DATA_LIMITED" if observability < OBSERVABILITY_BAR else "FAIL")
    print("\n" + "=" * 88)
    print("STEP 5 — GATE DECISION")
    print("=" * 88)
    print(f"bars={bars}")
    print(f"VERDICT: {status}")

    result: dict[str, Any] = {
        "status": status,
        "control_faults": [],
        "policy": {"horizon_ms": HORIZON_MS, "future_tolerance_ms": FUTURE_TOLERANCE_MS, "angle_limit_deg": ANGLE_LIMIT_DEG, "body_retention": guard.RETENTION},
        "controls": {
            "selected_runs": sorted(summaries),
            "route_total": route_total,
            "ranked_total": ranked_total,
            "analysis_set": len(captures),
            "stream": dict(stream_controls),
            "reproduction": {"guarded_flips": len(flips), "unguarded_flips": unguarded_flips, "disabled_changes": disabled_changes},
            "rates": {"vector": vector_rate, "floor": floor_rate, "admission": admission_rate, "selection": selection_rate},
            "trigger_by_run": trigger_by_run,
            "nontrigger_by_run": nontrigger_by_run,
            "retained_invariants": {key: {"ok": state_counters[key], "n": retained_n} for key in invariant_keys},
        },
        "observability": {"reconstructable": observable, "active_future": active_future, "rate": observability, "bar": OBSERVABILITY_BAR, "by_run": observability_by_run, "releases": dict(releases)},
        "temporal": {"episodes": len(episodes), "duration": duration_q, "fraction_ge_030": fraction_030, "future_eligible": len(eligible), "reached_horizon": len(reached), "horizon_rate": horizon_rate, "contributing_runs": contributing_runs, "leave_one_run_out": loo, "largest_run_share": largest_share},
        "authority": {"retained_steps": retained_n, "override_steps": state_counters["override_steps"], "override_rate": override_rate, "suppressed_overlapping_triggers": state_counters["suppressed_overlapping_triggers"], "angle": quantiles([row["angle_deg"] for row in retained]), "body_ratio": quantiles([row["body_ratio"] for row in retained if row["body_ratio"] is not None]), "projected_inrange_delta": quantiles([row["projected_inrange_delta"] for row in retained]), "recorded_command_angle": quantiles([row["recorded_command_angle_deg"] for row in retained])},
        "reported_context": {"trigger_by_wave": dict(sorted(trigger_by_wave.items())), "suppressed_by_run": suppressed_by_run, "suppressed_by_wave": dict(sorted(suppressed_by_wave.items())), "initial_gain": initial_gain, "terminal_waves_context_only": terminal_context},
        "bars": bars,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
