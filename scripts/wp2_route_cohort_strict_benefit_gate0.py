#!/usr/bin/env python3
"""§47 sealed equal-run Gate 0 for strict-benefit cohort commitment."""
from __future__ import annotations

import argparse
from collections import Counter
import json
import math
from pathlib import Path
import statistics as stats
import sys

import wp2_joint_route_conversion_gate0 as base
import wp2_route_cohort_commitment_gate0 as s46
import wp2_route_latch_revalidation_analysis as s45


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DEADBAND = 0.05
TOLERANCE = 1e-12
EXPECTED_SLOTS = (1, 2, 3, 4, 5, 6)


def strict_benefit(selected_value: float, recorded_value: float) -> bool:
    return selected_value - recorded_value + TOLERANCE >= DEADBAND


def simulate_run(stream: list[dict]) -> dict:
    counters = Counter()
    releases = Counter()
    episodes = []
    rows = []
    interval_ms = s46.median_interval_ms(stream)
    active = None

    def close(reason: str) -> None:
        nonlocal active
        if active is None:
            return
        active["release_reason"] = reason
        active["duration_sec"] = min(
            s46.HORIZON_MS / 1000.0,
            max(
                0.0,
                (active["last_retained_ts"] - active["start_ts"] + interval_ms) / 1000.0,
            ),
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
            if elapsed > s46.HORIZON_MS + s46.FUTURE_TOLERANCE_MS:
                close("missing_future_window")
                continue
            counters["active_future_steps"] += 1
            fault = s46.capture_fault(capture)
            if fault:
                close(fault)
                continue
            if capture["trigger"]:
                counters["suppressed_triggers"] += 1
            selected, selected_value, recorded_value, complete = s46.select_candidate(
                capture, active["original_ids"]
            )
            if selected is None and not complete:
                close("no_safe_candidate")
                continue
            counters["retained_steps"] += 1
            active["last_retained_ts"] = capture["ts_ms"]
            active["retained_steps"] += 1
            advantage = selected_value - recorded_value
            if complete:
                expected_override = False
                strict_override = False
                counters["objective_complete_steps"] += 1
                advantage = 0.0
            else:
                counters["candidate_steps"] += 1
                expected_override = strict_benefit(selected_value, recorded_value)
                strict_override = expected_override
                if strict_override:
                    counters["strict_overrides"] += 1
                    counters["projectile_ok"] += selected["proj"] >= capture["projectile_floor"]
                    counters["body_ok"] += s46.guard.body_guard_ok(
                        selected["body"], capture["reference_body"]
                    )
                    counters["subcritical_ok"] += (
                        selected["body"] >= base.CRITICAL
                        or selected["body"] >= capture["reference_body"]
                    )
                    admitted = {
                        s46.heading_key((row["x"], row["y"]))
                        for row in s46.safe_candidates(capture)
                    }
                    counters["enemy_ok"] += (
                        s46.heading_key((selected["x"], selected["y"])) in admitted
                    )
                else:
                    counters["deadband_retained"] += 1
            counters["deadband_correct"] += strict_override == expected_override
            counters["decision_steps"] += 1
            rows.append(
                {
                    "run_id": capture["run_id"],
                    "wave": capture["wave"],
                    "strict_override": strict_override,
                    "objective_complete": complete,
                    "advantage": advantage if strict_override else 0.0,
                    "raw_advantage": selected_value - recorded_value,
                }
            )
            if (
                elapsed >= s46.HORIZON_MS
                and abs(elapsed - s46.HORIZON_MS) <= s46.FUTURE_TOLERANCE_MS
            ):
                active["reached_horizon"] = True
                close("horizon")
            continue

        if not capture["trigger"]:
            continue
        counters["trigger_captures"] += 1
        fault = s46.capture_fault(capture, require_cohort=True)
        if fault:
            counters[f"trigger_exclusion:{fault}"] += 1
            continue
        if not s46.has_matched_future(stream, index):
            counters["trigger_exclusion:no_matched_future"] += 1
            continue
        counters["eligible_episodes"] += 1
        active = {
            "run_id": capture["run_id"],
            "wave": capture["wave"],
            "start_ts": capture["ts_ms"],
            "last_retained_ts": capture["ts_ms"],
            "original_ids": frozenset(capture["threats"]),
            "original_cohort_size": len(capture["threats"]),
            "retained_steps": 0,
            "reached_horizon": False,
        }

    close("stream_end")
    return {"episodes": episodes, "rows": rows, "counters": counters, "releases": releases}


def validate_archive(manifest: dict, root: Path) -> tuple[list[str], dict, dict, dict, dict]:
    faults = []
    slots = manifest.get("slots") or []
    slot_numbers = tuple(slot.get("slot") for slot in slots)
    run_ids = tuple(str(slot.get("run_id")) for slot in slots)
    if manifest.get("fixed_slots") != list(EXPECTED_SLOTS) or slot_numbers != EXPECTED_SLOTS:
        faults.append(f"manifest slots={slot_numbers!r}")
    if len(run_ids) != 6 or len(set(run_ids)) != 6:
        faults.append(f"run count/uniqueness={len(run_ids)}/{len(set(run_ids))}")
    if manifest.get("mod_version") != s45.BUILD or manifest.get("policy_version") != s45.POLICY:
        faults.append("manifest build/policy identity")

    streams, scan_counters, identity, summaries = {}, {}, {}, {}
    for run_id in run_ids:
        summary = json.loads((root / run_id / "summary.json").read_text(encoding="utf-8"))
        summaries[run_id] = summary
        faults.extend(f"{run_id}: {fault}" for fault in s45.summary_faults(summary))
        scanned = s45.scan_run(root, run_id)
        scan_counters[run_id] = scanned["counters"]
        streams[run_id], identity[run_id] = s46.scan_stream(root, run_id)

        c = scan_counters[run_id]
        if c["raw"] != c["fresh"] or c["instrument_enabled"] != c["fresh"]:
            faults.append(f"{run_id}: raw/fresh/enabled={c['raw']}/{c['fresh']}/{c['instrument_enabled']}")
        if c["parse_errors"] or c["stale"] or c["nonincreasing_ts"]:
            faults.append(f"{run_id}: parse/stale/nonincreasing={c['parse_errors']}/{c['stale']}/{c['nonincreasing_ts']}")
        if not c["ready"] or not c["not_ready"]:
            faults.append(f"{run_id}: ready/not_ready={c['ready']}/{c['not_ready']}")
        parity_rows = c["parity_rows_matched"] / c["parity_rows"] if c["parity_rows"] else 0.0
        parity_captures = c["parity_capture_exact"] / c["parity_captures"] if c["parity_captures"] else 0.0
        baseline = c["baseline_living_ready"] / c["baseline_living"] if c["baseline_living"] else 0.0
        delivery = c["heading_match"] / c["heading_seen"] if c["heading_seen"] else 0.0
        if parity_rows < 0.999 or parity_captures < 0.999:
            faults.append(f"{run_id}: row parity={parity_rows:.6f}/{parity_captures:.6f}")
        if baseline < 0.99:
            faults.append(f"{run_id}: baseline readiness={baseline:.6f}")
        if delivery < 0.999:
            faults.append(f"{run_id}: delivery={delivery:.6f}")
        if not c["applied"] or any(c[key] != c["applied"] for key in ("gain_ok", "body_ok", "subcritical_ok")):
            faults.append(
                f"{run_id}: conversion guards={c['gain_ok']}/{c['body_ok']}/{c['subcritical_ok']}/{c['applied']}"
            )
        ids = identity[run_id]
        denominator = ids["living_captures"]
        rate = min(ids["identity_complete"], ids["identity_unique"]) / denominator if denominator else 0.0
        ids["rate"] = rate
        if rate < 0.999:
            faults.append(f"{run_id}: identity={min(ids['identity_complete'], ids['identity_unique'])}/{denominator}")
    return faults, streams, scan_counters, identity, summaries


def run_result(run_id: str, simulation: dict) -> dict:
    episodes = simulation["episodes"]
    rows = simulation["rows"]
    counters = simulation["counters"]
    eligible = len(episodes)
    reached = sum(episode["reached_horizon"] for episode in episodes)
    strict_rows = [row for row in rows if row["strict_override"]]
    retained = len(rows)
    strict = len(strict_rows)
    strict_advantages = [row["advantage"] for row in strict_rows]
    selected = counters["strict_overrides"]
    invariants = {
        key: counters[key]
        for key in ("projectile_ok", "body_ok", "subcritical_ok", "enemy_ok")
    }
    return {
        "run_id": run_id,
        "eligible_episodes": eligible,
        "retained_steps": retained,
        "duration": s46.quantiles([episode["duration_sec"] for episode in episodes]),
        "reached_horizon": reached,
        "horizon_rate": reached / eligible if eligible else None,
        "strict_overrides": strict,
        "strict_override_rate": strict / retained if retained else None,
        "integrated_strict_advantage": sum(strict_advantages) / retained if retained else None,
        "median_strict_advantage": stats.median(strict_advantages) if strict_advantages else None,
        "deadband_correct": counters["deadband_correct"],
        "decision_steps": counters["decision_steps"],
        "invariants": invariants,
        "selected_steps": selected,
        "releases": dict(simulation["releases"]),
        "trigger_exclusions": {
            key: value for key, value in counters.items() if key.startswith("trigger_exclusion:")
        },
    }


def branch_summary(run_id: str, simulation: dict) -> dict:
    counters = simulation["counters"]
    return {
        "run_id": run_id,
        "eligible_episodes": counters["eligible_episodes"],
        "retained_steps": counters["retained_steps"],
        "strict_overrides": counters["strict_overrides"],
        "deadband_retained": counters["deadband_retained"],
        "objective_complete_steps": counters["objective_complete_steps"],
        "deadband_correct": counters["deadband_correct"],
        "decision_steps": counters["decision_steps"],
        "trigger_exclusions": {
            key: value for key, value in counters.items() if key.startswith("trigger_exclusion:")
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--manifest", type=Path, default=Path(".tmp/s47_route_cohort_strict_benefit/manifest.json")
    )
    parser.add_argument("--runs-dir", type=Path, default=s46.default_runs_dir())
    parser.add_argument(
        "--output", type=Path, default=Path("reports/wp2/route_cohort_strict_benefit_result.json")
    )
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8-sig"))

    print("=" * 88)
    print("STEP 1 — SEALED RUN, INSTRUMENT, DELIVERY, AND IDENTITY CONTROLS")
    print("=" * 88)
    faults, streams, controls, identity, summaries = validate_archive(manifest, args.runs_dir)
    for run_id in streams:
        c, ids = controls[run_id], identity[run_id]
        print(
            f"{run_id}: raw/fresh/enabled={c['raw']}/{c['fresh']}/{c['instrument_enabled']} "
            f"ready/not={c['ready']}/{c['not_ready']} parity={c['parity_rows_matched']}/{c['parity_rows']} "
            f"baseline={c['baseline_living_ready']}/{c['baseline_living']} delivery={c['heading_match']}/{c['heading_seen']} "
            f"applied={c['applied']} identity={min(ids['identity_complete'], ids['identity_unique'])}/{ids['living_captures']}"
        )
    print(f"ARCHIVE CONTROL VERDICT: {'PASS' if not faults else 'VOID'} faults={faults}")
    if faults:
        result = {"status": "VOID", "stage": "archive_controls", "faults": faults}
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        return 2

    simulations = {run_id: simulate_run(stream) for run_id, stream in streams.items()}
    branch_by_run = {
        run_id: branch_summary(run_id, simulations[run_id]) for run_id in streams
    }
    branch_faults = []
    print("\n" + "=" * 88)
    print("STEP 2 — EPISODE, STEP, AND BRANCH CONTROLS")
    print("=" * 88)
    for run_id, result in branch_by_run.items():
        sim = simulations[run_id]
        counters = sim["counters"]
        print(
            f"{run_id}: eligible={result['eligible_episodes']} retained={result['retained_steps']} "
            f"strict/deadband/resolved={counters['strict_overrides']}/{counters['deadband_retained']}/{counters['objective_complete_steps']} "
            f"correct={result['deadband_correct']}/{result['decision_steps']} exclusions={result['trigger_exclusions']}"
        )
        if result["eligible_episodes"] < 50:
            branch_faults.append(f"{run_id}: eligible={result['eligible_episodes']} < 50")
        if result["retained_steps"] < 500:
            branch_faults.append(f"{run_id}: retained={result['retained_steps']} < 500")
        if not counters["strict_overrides"]:
            branch_faults.append(f"{run_id}: zero strict overrides")
        if not counters["deadband_retained"]:
            branch_faults.append(f"{run_id}: zero deadband retentions")
        if result["deadband_correct"] != result["decision_steps"]:
            branch_faults.append(
                f"{run_id}: deadband correctness={result['deadband_correct']}/{result['decision_steps']}"
            )
    print(f"BRANCH CONTROL VERDICT: {'PASS' if not branch_faults else 'VOID'} faults={branch_faults}")
    if branch_faults:
        result = {
            "status": "VOID",
            "stage": "branch_controls",
            "faults": branch_faults,
            "runs": branch_by_run,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        return 2

    per_run = {run_id: run_result(run_id, simulations[run_id]) for run_id in streams}
    duration_bars = [result["duration"]["median"] >= 0.30 for result in per_run.values()]
    horizon_bars = [result["horizon_rate"] >= 0.25 for result in per_run.values()]
    strict_rates = [result["strict_override_rate"] for result in per_run.values()]
    integrated = [result["integrated_strict_advantage"] for result in per_run.values()]
    conditional = [result["median_strict_advantage"] for result in per_run.values()]
    safety_bars = [
        result["selected_steps"] > 0
        and all(value == result["selected_steps"] for value in result["invariants"].values())
        for result in per_run.values()
    ]
    bars = {
        "duration_every_run": all(duration_bars),
        "horizon_every_run": all(horizon_bars)
        and all(result["reached_horizon"] > 0 for result in per_run.values()),
        "safety_and_deadband_every_run": all(safety_bars)
        and all(result["deadband_correct"] == result["decision_steps"] for result in per_run.values()),
        "strict_rate_every_run": all(value >= 0.20 for value in strict_rates),
        "strict_rate_equal_run_median": stats.median(strict_rates) >= 0.25,
        "integrated_every_run": all(value >= 0.02 for value in integrated),
        "integrated_equal_run_median": stats.median(integrated) >= 0.03,
        "conditional_every_run": all(value >= 0.05 for value in conditional),
    }
    status = "PASS" if all(bars.values()) else "FAIL"
    pooled_retained = sum(result["retained_steps"] for result in per_run.values())
    pooled_strict = sum(result["strict_overrides"] for result in per_run.values())
    pooled_advantage = sum(
        row["advantage"]
        for simulation in simulations.values()
        for row in simulation["rows"]
    )
    equal_run = {
        "strict_override_rate_median": stats.median(strict_rates),
        "integrated_strict_advantage_median": stats.median(integrated),
        "median_strict_advantage_median": stats.median(conditional),
    }
    pooled = {
        "retained_steps": pooled_retained,
        "strict_overrides": pooled_strict,
        "strict_override_rate": pooled_strict / pooled_retained,
        "integrated_strict_advantage": pooled_advantage / pooled_retained,
    }
    print("\n" + "=" * 88)
    print("STEP 3 — FROZEN §47 EQUAL-RUN RESULT")
    print("=" * 88)
    for run_id, result in per_run.items():
        print(
            f"{run_id}: duration={result['duration']['median']:.3f} horizon={result['reached_horizon']}/{result['eligible_episodes']}={result['horizon_rate']:.6f} "
            f"strict={result['strict_overrides']}/{result['retained_steps']}={result['strict_override_rate']:.6f} "
            f"integrated={result['integrated_strict_advantage']:.6f} conditional_median={result['median_strict_advantage']:.6f} "
            f"safety={result['invariants']}"
        )
    print(f"equal_run={equal_run}")
    print(f"pooled_descriptive={pooled}")
    print(f"bars={bars}")
    print(f"VERDICT: {status}")
    result = {
        "status": status,
        "deadband": DEADBAND,
        "runs": per_run,
        "equal_run": equal_run,
        "pooled_descriptive": pooled,
        "bars": bars,
        "terminal_context": {
            run_id: {
                "result": summaries[run_id].get("result"),
                "last_wave": summaries[run_id].get("last_wave"),
            }
            for run_id in streams
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
