#!/usr/bin/env python3
"""§46 offline Gate 0 for current-tick-safe original-cohort commitment."""
from __future__ import annotations

import argparse
from collections import Counter
import json
import math
import os
from pathlib import Path
import statistics as stats
import sys

import wp2_clearance_guarded_conversion_gate0 as guard
import wp2_joint_route_conversion_gate0 as base
import wp2_route_latch_revalidation_analysis as s45


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HORIZON_MS = 600
FUTURE_TOLERANCE_MS = 75
IDENTITY_RATE_BAR = 0.999
EXPECTED_RUNS = (
    "run_1785826116_89378",
    "run_1785826737_53506",
    "run_1785827267_71832",
    "run_1785827488_46830",
)
EXPECTED_CONTROL_COUNTS = {
    "raw": 28173,
    "fresh": 28173,
    "instrument_enabled": 28173,
    "parity_rows": 215901,
    "parity_rows_matched": 215901,
    "parity_captures": 9079,
    "parity_capture_exact": 9079,
    "baseline_living": 15457,
    "baseline_living_ready": 15457,
    "heading_seen": 9079,
    "heading_match": 9079,
    "applied": 1824,
    "gain_ok": 1824,
    "body_ok": 1824,
    "subcritical_ok": 1824,
}


def default_runs_dir() -> Path:
    return Path(os.environ["APPDATA"]) / "Brotato" / "brotato_agent" / "runs"


def quantiles(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"p10": None, "median": None, "p90": None}
    ordered = sorted(float(value) for value in values)

    def percentile(fraction: float) -> float:
        position = (len(ordered) - 1) * fraction
        lower, upper = math.floor(position), math.ceil(position)
        if lower == upper:
            return ordered[lower]
        return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)

    return {"p10": percentile(0.10), "median": percentile(0.50), "p90": percentile(0.90)}


def finite_float(value: object) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def unit_heading(x: object, y: object) -> tuple[float, float] | None:
    x_value, y_value = finite_float(x), finite_float(y)
    if x_value is None or y_value is None:
        return None
    length = math.hypot(x_value, y_value)
    return (x_value / length, y_value / length) if length > 1e-12 else None


def heading_key(heading: tuple[float, float]) -> tuple[float, float]:
    return round(heading[0], 4), round(heading[1], 4)


def parse_threats(payload: dict) -> tuple[dict[object, dict], bool, bool]:
    living = []
    entities = payload.get("entities") or {}
    for threat in (entities.get("enemies") or []) + (entities.get("bosses") or []):
        hp = finite_float(threat.get("hp"))
        if hp is not None and hp > 0:
            living.append(threat)
    identities = [threat.get("instance_id") for threat in living]
    complete = all(identity is not None for identity in identities)
    unique = complete and len(set(identities)) == len(identities)
    parsed: dict[object, dict] = {}
    if unique:
        for threat in living:
            values = {key: finite_float(threat.get(key)) for key in ("x", "y", "vx", "vy")}
            if all(value is not None for value in values.values()):
                parsed[threat["instance_id"]] = values
            else:
                complete = False
    return parsed, complete, unique


def parse_capture(run_id: str, event: dict) -> dict:
    payload = event.get("payload") or {}
    teacher = payload.get("teacher") or {}
    action = teacher.get("action") or {}
    route = ((teacher.get("contributions") or {}).get("route") or {})
    revalidation = route.get("revalidation") or {}
    player = payload.get("player") or {}
    ranges = [
        value
        for weapon in (payload.get("weapons") or [])
        if (value := finite_float(weapon.get("max_range"))) is not None and value > 0
    ]
    threats, identity_complete, identity_unique = parse_threats(payload)
    return {
        "run_id": run_id,
        "capture_seq": payload.get("capture_seq"),
        "ts_ms": event.get("ts_ms"),
        "wave": payload.get("wave"),
        "route_exit": route.get("exit", "missing"),
        "trigger": route.get("conversion_applied") is True,
        "action": unit_heading(action.get("x"), action.get("y")),
        "player_x": finite_float(player.get("x")),
        "player_y": finite_float(player.get("y")),
        "player_speed": finite_float(player.get("speed")),
        "weapon_range": max(ranges) if ranges else None,
        "threats": threats,
        "living_count": len(
            [
                threat
                for threat in ((payload.get("entities") or {}).get("enemies") or [])
                + ((payload.get("entities") or {}).get("bosses") or [])
                if (finite_float(threat.get("hp")) or 0) > 0
            ]
        ),
        "identity_complete": identity_complete,
        "identity_unique": identity_unique,
        "revalidation_ready": revalidation.get("ready") is True,
        "rows": list(revalidation.get("rows") or []),
        "projectile_floor": finite_float(revalidation.get("projectile_floor")),
        "body_floor": finite_float(revalidation.get("body_floor")),
        "lowest_penalty": finite_float(revalidation.get("lowest_penalty")),
        "reference_body": finite_float(revalidation.get("reference_body")),
    }


def capture_fault(capture: dict, *, require_cohort: bool = False) -> str | None:
    if not capture["revalidation_ready"]:
        return "revalidation_not_ready"
    if not capture["identity_complete"] or not capture["identity_unique"]:
        return "threat_identity"
    if require_cohort and not capture["threats"]:
        return "empty_original_cohort"
    if capture["action"] is None:
        return "action"
    for key in ("player_x", "player_y", "player_speed", "weapon_range"):
        value = capture[key]
        if value is None or (key in {"player_speed", "weapon_range"} and value <= 0):
            return f"missing_{key}"
    for key in ("projectile_floor", "body_floor", "lowest_penalty", "reference_body"):
        if capture[key] is None:
            return f"missing_{key}"
    if not capture["rows"]:
        return "missing_rows"
    return None


def safe_candidates(capture: dict) -> list[dict]:
    candidates = []
    for raw in capture["rows"]:
        heading = unit_heading(raw.get("x"), raw.get("y"))
        body = finite_float(raw.get("body"))
        projectile = finite_float(raw.get("proj"))
        penalty = finite_float(raw.get("pen"))
        if heading is None or body is None or projectile is None or penalty is None:
            continue
        if projectile < capture["projectile_floor"]:
            continue
        if body < capture["body_floor"]:
            continue
        if penalty > capture["lowest_penalty"] + base.ENEMY_SLACK:
            continue
        if not guard.body_guard_ok(body, capture["reference_body"]):
            continue
        candidates.append({"x": heading[0], "y": heading[1], "body": body, "proj": projectile, "pen": penalty})
    return candidates


def cohort_value(capture: dict, original_ids: frozenset, heading: tuple[float, float]) -> float:
    px = capture["player_x"] + heading[0] * capture["player_speed"] * HORIZON_MS / 1000.0
    py = capture["player_y"] + heading[1] * capture["player_speed"] * HORIZON_MS / 1000.0
    score = 0
    for identity in original_ids:
        threat = capture["threats"].get(identity)
        if threat is None:
            score += 1
            continue
        tx = threat["x"] + threat["vx"] * HORIZON_MS / 1000.0
        ty = threat["y"] + threat["vy"] * HORIZON_MS / 1000.0
        score += math.hypot(tx - px, ty - py) <= capture["weapon_range"]
    return score / len(original_ids)


def select_candidate(capture: dict, original_ids: frozenset) -> tuple[dict | None, float, float, bool]:
    unresolved = original_ids.intersection(capture["threats"])
    recorded_value = cohort_value(capture, original_ids, capture["action"])
    if not unresolved:
        return None, recorded_value, recorded_value, True
    candidates = safe_candidates(capture)
    if not candidates:
        return None, recorded_value, recorded_value, False
    scored = [(cohort_value(capture, original_ids, (row["x"], row["y"])), row) for row in candidates]
    selected_value, selected = min(
        scored,
        key=lambda item: (
            -item[0], -item[1]["body"], -item[1]["proj"], item[1]["pen"],
            heading_key((item[1]["x"], item[1]["y"])),
        ),
    )
    return selected, selected_value, recorded_value, False


def median_interval_ms(stream: list[dict]) -> float:
    intervals = [
        stream[index]["ts_ms"] - stream[index - 1]["ts_ms"]
        for index in range(1, len(stream))
        if stream[index]["wave"] == stream[index - 1]["wave"]
        and stream[index]["ts_ms"] > stream[index - 1]["ts_ms"]
    ]
    return float(stats.median(intervals)) if intervals else 50.0


def has_matched_future(stream: list[dict], start_index: int) -> bool:
    start = stream[start_index]
    target = start["ts_ms"] + HORIZON_MS
    return any(
        row["wave"] == start["wave"] and abs(row["ts_ms"] - target) <= FUTURE_TOLERANCE_MS
        for row in stream[start_index + 1 :]
    )


def simulate_run(stream: list[dict]) -> dict:
    counters = Counter()
    releases = Counter()
    episodes = []
    rows = []
    interval_ms = median_interval_ms(stream)
    active = None

    def close(reason: str) -> None:
        nonlocal active
        if active is None:
            return
        active["release_reason"] = reason
        active["duration_sec"] = min(
            HORIZON_MS / 1000.0,
            max(0.0, (active["last_retained_ts"] - active["start_ts"] + interval_ms) / 1000.0),
        )
        releases[reason] += 1
        episodes.append(active)
        active = None

    for index, capture in enumerate(stream):
        if active is not None:
            if capture["wave"] != active["wave"]:
                close("wave_change")
                continue
            elapsed = capture["ts_ms"] - active["start_ts"]
            if elapsed > HORIZON_MS + FUTURE_TOLERANCE_MS:
                close("missing_future_window")
                continue
            counters["active_future_steps"] += 1
            fault = capture_fault(capture)
            if fault:
                close(fault)
                continue
            if capture["trigger"]:
                counters["suppressed_triggers"] += 1
            selected, selected_value, recorded_value, complete = select_candidate(
                capture, active["original_ids"]
            )
            if selected is None and not complete:
                close("no_safe_candidate")
                continue
            counters["retained_steps"] += 1
            active["last_retained_ts"] = capture["ts_ms"]
            active["retained_steps"] += 1
            if complete:
                counters["objective_complete_steps"] += 1
                override = False
                advantage = 0.0
            else:
                counters["selected_steps"] += 1
                counters["projectile_ok"] += selected["proj"] >= capture["projectile_floor"]
                counters["body_ok"] += guard.body_guard_ok(selected["body"], capture["reference_body"])
                counters["subcritical_ok"] += (
                    selected["body"] >= base.CRITICAL or selected["body"] >= capture["reference_body"]
                )
                admitted_keys = {heading_key((row["x"], row["y"])) for row in safe_candidates(capture)}
                counters["enemy_ok"] += heading_key((selected["x"], selected["y"])) in admitted_keys
                override = heading_key((selected["x"], selected["y"])) != heading_key(capture["action"])
                advantage = selected_value - recorded_value
            counters["override_steps"] += override
            counters["no_override_steps"] += not override
            rows.append(
                {
                    "run_id": capture["run_id"], "wave": capture["wave"],
                    "override": override, "objective_complete": complete,
                    "selected_value": selected_value, "recorded_value": recorded_value,
                    "advantage": advantage,
                }
            )
            if elapsed >= HORIZON_MS and abs(elapsed - HORIZON_MS) <= FUTURE_TOLERANCE_MS:
                active["reached_horizon"] = True
                close("horizon")
            continue

        if not capture["trigger"]:
            continue
        counters["trigger_captures"] += 1
        fault = capture_fault(capture, require_cohort=True)
        if fault:
            counters[f"trigger_exclusion:{fault}"] += 1
            continue
        if not has_matched_future(stream, index):
            counters["trigger_exclusion:no_matched_future"] += 1
            continue
        counters["eligible_episodes"] += 1
        active = {
            "run_id": capture["run_id"], "wave": capture["wave"],
            "start_ts": capture["ts_ms"], "last_retained_ts": capture["ts_ms"],
            "original_ids": frozenset(capture["threats"]), "original_cohort_size": len(capture["threats"]),
            "retained_steps": 0, "reached_horizon": False,
        }

    close("stream_end")
    return {"episodes": episodes, "rows": rows, "counters": counters, "releases": releases}


def scan_stream(root: Path, run_id: str) -> tuple[list[dict], Counter]:
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
            wave, seq, ts_ms = payload.get("wave"), payload.get("capture_seq"), event.get("ts_ms")
            if not isinstance(wave, int) or not 1 <= wave <= 11:
                continue
            if not isinstance(seq, int) or not isinstance(ts_ms, int):
                counters["stale"] += 1
                continue
            if last_seq is not None and seq <= last_seq:
                counters["stale"] += 1
                continue
            if last_ts is not None and ts_ms <= last_ts:
                counters["nonincreasing_ts"] += 1
                continue
            last_seq, last_ts = seq, ts_ms
            capture = parse_capture(run_id, event)
            stream.append(capture)
            if capture["living_count"]:
                counters["living_captures"] += 1
                counters["identity_complete"] += capture["identity_complete"]
                counters["identity_unique"] += capture["identity_unique"]
    return stream, counters


def control_gate(manifest: dict, root: Path) -> tuple[list[str], dict, dict, dict]:
    faults = []
    slots = manifest.get("slots") or []
    run_ids = tuple(str(slot.get("run_id")) for slot in slots)
    if run_ids != EXPECTED_RUNS or len(set(run_ids)) != 4:
        faults.append(f"manifest identity/order={run_ids!r}")
    s45_scans, streams, identities = {}, {}, {}
    summaries = {}
    for run_id in EXPECTED_RUNS:
        summary = json.loads((root / run_id / "summary.json").read_text(encoding="utf-8"))
        summaries[run_id] = summary
        faults.extend(f"{run_id}: {fault}" for fault in s45.summary_faults(summary))
        s45_scans[run_id] = s45.scan_run(root, run_id)
        streams[run_id], identities[run_id] = scan_stream(root, run_id)
    pooled = sum((scan["counters"] for scan in s45_scans.values()), Counter())
    for key, expected in EXPECTED_CONTROL_COUNTS.items():
        if pooled[key] != expected:
            faults.append(f"{key}={pooled[key]} expected={expected}")
    for key in ("parse_errors", "stale", "nonincreasing_ts"):
        if pooled[key]:
            faults.append(f"{key}={pooled[key]}")
    identity_rates = {}
    for run_id, values in identities.items():
        denominator = values["living_captures"]
        complete = values["identity_complete"]
        unique = values["identity_unique"]
        rate = min(complete, unique) / denominator if denominator else 0.0
        identity_rates[run_id] = {"complete": complete, "unique": unique, "denominator": denominator, "rate": rate}
        if not denominator or rate < IDENTITY_RATE_BAR:
            faults.append(f"{run_id}: identity={min(complete, unique)}/{denominator}")
    return faults, streams, identity_rates, summaries


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=Path(".tmp/s45_route_latch_revalidation/manifest.json"))
    parser.add_argument("--runs-dir", type=Path, default=default_runs_dir())
    parser.add_argument("--output", type=Path, default=Path("reports/wp2/route_cohort_commitment_gate0_result.json"))
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8-sig"))

    print("=" * 88)
    print("STEP 1 — FROZEN ARCHIVE, DELIVERY, AND IDENTITY CONTROLS")
    print("=" * 88)
    faults, streams, identity_rates, summaries = control_gate(manifest, args.runs_dir)
    for run_id in EXPECTED_RUNS:
        values = identity_rates[run_id]
        print(f"{run_id}: identity complete/unique/living={values['complete']}/{values['unique']}/{values['denominator']} rate={values['rate']:.6f}")
    print(f"CONTROL VERDICT: {'PASS' if not faults else 'VOID'} faults={faults}")
    if faults:
        result = {"status": "VOID", "stage": "archive_controls", "faults": faults, "identity": identity_rates}
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        return 2

    simulations = {run_id: simulate_run(streams[run_id]) for run_id in EXPECTED_RUNS}
    mechanism_faults = []
    eligible_by_run = Counter()
    horizons_by_run = Counter()
    overrides_by_run = Counter()
    no_overrides_by_run = Counter()
    all_episodes, all_rows = [], []
    state = Counter()
    releases = Counter()
    for run_id, simulation in simulations.items():
        all_episodes.extend(simulation["episodes"])
        all_rows.extend(simulation["rows"])
        state += simulation["counters"]
        releases += simulation["releases"]
        eligible_by_run[run_id] = simulation["counters"]["eligible_episodes"]
        horizons_by_run[run_id] = sum(episode["reached_horizon"] for episode in simulation["episodes"])
        overrides_by_run[run_id] = sum(row["override"] for row in simulation["rows"])
        no_overrides_by_run[run_id] = sum(not row["override"] for row in simulation["rows"])
        if not eligible_by_run[run_id]:
            mechanism_faults.append(f"{run_id}: zero eligible episodes")
        if not overrides_by_run[run_id]:
            mechanism_faults.append(f"{run_id}: zero overrides")
        if not no_overrides_by_run[run_id]:
            mechanism_faults.append(f"{run_id}: zero no-override steps")

    print("\n" + "=" * 88)
    print("STEP 2 — STATE-MACHINE BRANCH AND DENOMINATOR CONTROLS")
    print("=" * 88)
    print(f"eligible={dict(eligible_by_run)} overrides={dict(overrides_by_run)} no_override={dict(no_overrides_by_run)}")
    print(f"trigger exclusions={{{', '.join(f'{key}: {value}' for key, value in state.items() if key.startswith('trigger_exclusion:'))}}}")
    print(f"BRANCH VERDICT: {'PASS' if not mechanism_faults else 'VOID'} faults={mechanism_faults}")
    if mechanism_faults:
        result = {"status": "VOID", "stage": "mechanism_controls", "faults": mechanism_faults, "identity": identity_rates, "state": dict(state)}
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        return 2

    eligible = len(all_episodes)
    reached = sum(episode["reached_horizon"] for episode in all_episodes)
    durations = [episode["duration_sec"] for episode in all_episodes]
    duration_q = quantiles(durations)
    horizon_rate = reached / eligible if eligible else 0.0
    loo = []
    for run_id in EXPECTED_RUNS:
        denominator = eligible - eligible_by_run[run_id]
        numerator = reached - horizons_by_run[run_id]
        loo.append(numerator / denominator if denominator else 0.0)
    largest_share = max(eligible_by_run.values(), default=0) / eligible if eligible else 0.0
    retained = state["retained_steps"]
    selected_steps = state["selected_steps"]
    overrides = state["override_steps"]
    override_rows = [row for row in all_rows if row["override"]]
    override_advantages = [row["advantage"] for row in override_rows]
    override_rate = overrides / retained if retained else 0.0
    median_override_advantage = stats.median(override_advantages) if override_advantages else None
    mean_all_advantage = stats.mean(row["advantage"] for row in all_rows) if all_rows else None
    invariant_keys = ("projectile_ok", "body_ok", "subcritical_ok", "enemy_ok")
    bars = {
        "median_duration": duration_q["median"] is not None and duration_q["median"] >= 0.30,
        "horizon_rate": horizon_rate >= 0.25,
        "all_runs_contribute": all(horizons_by_run[run_id] > 0 for run_id in EXPECTED_RUNS),
        "loo_min": min(loo) >= 0.20,
        "loo_median": stats.median(loo) >= 0.25,
        "largest_run_share": largest_share <= 0.35,
        "safety": selected_steps > 0 and all(state[key] == selected_steps for key in invariant_keys),
        "override_rate": override_rate >= 0.20,
        "median_override_advantage": median_override_advantage is not None and median_override_advantage >= 0.05,
        "mean_all_advantage": mean_all_advantage is not None and mean_all_advantage >= 0.02,
    }
    status = "PASS" if all(bars.values()) else "FAIL"
    print("\n" + "=" * 88)
    print("STEP 3 — FROZEN §46 COHORT-COMMITMENT RESULT")
    print("=" * 88)
    print(f"duration={duration_q}; horizon={reached}/{eligible}={horizon_rate:.6f}; by_run={dict(horizons_by_run)}")
    print(f"LOO={loo}; largest eligible share={largest_share:.6f}; releases={dict(releases)}")
    print(f"overrides={overrides}/{retained}={override_rate:.6f}; median override advantage={median_override_advantage}; mean all-step advantage={mean_all_advantage}")
    print(f"invariants=" + "/".join(f"{key}:{state[key]}/{selected_steps}" for key in invariant_keys))
    print(f"bars={bars}")
    print(f"VERDICT: {status}")
    result = {
        "status": status, "runs": list(EXPECTED_RUNS), "identity": identity_rates,
        "state": dict(state), "releases": dict(releases),
        "temporal": {"episodes": eligible, "duration": duration_q, "reached": reached, "horizon_rate": horizon_rate, "by_run": dict(horizons_by_run), "loo": loo, "largest_share": largest_share},
        "authority": {"retained": retained, "selected_steps": selected_steps, "overrides": overrides, "override_rate": override_rate, "median_override_advantage": median_override_advantage, "mean_all_advantage": mean_all_advantage, "invariants": {key: state[key] for key in invariant_keys}},
        "bars": bars, "terminal_context": {run_id: summaries[run_id].get("last_wave") for run_id in EXPECTED_RUNS},
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
