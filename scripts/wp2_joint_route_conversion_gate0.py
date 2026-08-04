"""§40 Gate 0: joint PACK admission plus lexicographic in-range selection.

Implements reports/wp2/joint_route_conversion_prereg.md. The primary policy is
fixed at PACK=80. PACK 120/45 are sensitivities and cannot rescue a primary
failure. Controls are printed and barred before policy results are computed.

Usage:
    python scripts/wp2_joint_route_conversion_gate0.py --runs-dir <dir> --output <json>
    python scripts/wp2_joint_route_conversion_gate0.py --self-test
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from collections import Counter, defaultdict

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

VERSION = "0.2.76-wp2-capture"
EXPECTED_RUNS = {
    "run_1785754965_28036",
    "run_1785755965_44537",
    "run_1785756364_37779",
    "run_1785756664_17215",
    "run_1785757198_83975",
    "run_1785757742_9445",
    "run_1785758500_77660",
    "run_1785758909_7977",
}
EXCLUDED_SMOKE = "run_1785754086_12860"

HORIZON = 0.60
ALIGN_BONUS = 14.0
CONTINUITY = 85.0
ENEMY_SLACK = 20.0
CRITICAL = 45.0
PACK_ACTUAL = 160.0
PACK_PRIMARY = 80.0
PACK_SENSITIVITIES = (120.0, 45.0)
GAIN_DEADBAND = 0.05
VECTOR_TOL = 1e-2


def key(row):
    return (round(float(row.get("x", 0)), 4), round(float(row.get("y", 0)), 4))


def quantile(values, q):
    vals = sorted(float(v) for v in values)
    if not vals:
        return None
    if len(vals) == 1:
        return vals[0]
    pos = (len(vals) - 1) * q
    lo, hi = int(math.floor(pos)), int(math.ceil(pos))
    if lo == hi:
        return vals[lo]
    return vals[lo] + (vals[hi] - vals[lo]) * (pos - lo)


def recover_vector(admitted, field, coefficient):
    """Recover a direction vector from quantised per-lane dot-product terms."""
    sxx = sxy = syy = sxa = sya = 0.0
    for row in admitted:
        x, y = float(row.get("x", 0)), float(row.get("y", 0))
        term = float(row.get(field, 0)) / coefficient
        sxx += x * x
        sxy += x * y
        syy += y * y
        sxa += x * term
        sya += y * term
    det = sxx * syy - sxy * sxy
    if abs(det) < 1e-9:
        return None, None
    vx = (syy * sxa - sxy * sya) / det
    vy = (-sxy * sxa + sxx * sya) / det
    error = max(
        abs(
            coefficient * (float(r.get("x", 0)) * vx + float(r.get("y", 0)) * vy)
            - float(r.get(field, 0))
        )
        for r in admitted
    )
    return (vx, vy), error


def score_of(row, baseline, previous):
    x, y = float(row.get("x", 0)), float(row.get("y", 0))
    return (
        float(row.get("proj", 0))
        - float(row.get("pen", 0))
        + ALIGN_BONUS * (x * baseline[0] + y * baseline[1])
        + CONTINUITY * (x * previous[0] + y * previous[1])
    )


def slack_for(wave):
    return 35.0 if int(wave) <= 12 else 20.0


def highest_body(rows, projectile_floor):
    return max(
        (
            float(r.get("body", -1e18))
            for r in rows
            if float(r.get("proj", -1e18)) >= projectile_floor
        ),
        default=None,
    )


def floor_at(highest, pack, wave, loot_dash):
    if highest >= CRITICAL:
        if loot_dash:
            return CRITICAL
        return max(CRITICAL, min(pack, highest - slack_for(wave)))
    return highest - slack_for(wave)


def admitted_at(rows, pack, projectile_floor, wave, loot_dash=False):
    highest = highest_body(rows, projectile_floor)
    if highest is None:
        return None, None
    floor = floor_at(highest, pack, wave, loot_dash)
    through_floors = [
        r
        for r in rows
        if float(r.get("proj", -1e18)) >= projectile_floor
        and float(r.get("body", -1e18)) >= floor
    ]
    if not through_floors:
        return [], floor
    lowest_penalty = min(float(r.get("pen", 0)) for r in through_floors)
    admitted = [
        r
        for r in through_floors
        if float(r.get("pen", 0)) <= lowest_penalty + ENEMY_SLACK
    ]
    return admitted, floor


def inrange_after(px, py, speed, ux, uy, threats, max_range, horizon=HORIZON):
    norm = math.hypot(ux, uy)
    if norm <= 1e-9 or not threats:
        return None
    nx = px + ux / norm * speed * horizon
    ny = py + uy / norm * speed * horizon
    hits = 0
    for threat in threats:
        ex = float(threat.get("x", 0)) + float(threat.get("vx", 0)) * horizon
        ey = float(threat.get("y", 0)) + float(threat.get("vy", 0)) * horizon
        if math.hypot(ex - nx, ey - ny) <= max_range:
            hits += 1
    return hits / float(len(threats))


def choose_joint(admitted, current, inrange, baseline, previous, enabled=True):
    if not enabled:
        return current
    best = max(
        admitted,
        key=lambda r: (inrange[key(r)], score_of(r, baseline, previous)),
    )
    if inrange[key(best)] - inrange[key(current)] > GAIN_DEADBAND:
        return best
    return current


def validate_summary(run_id, summary):
    errors = []

    def require(name, condition):
        if not condition:
            errors.append(name)

    require("expected_run_id", run_id in EXPECTED_RUNS)
    require("mod_version", summary.get("mod_version") == VERSION)
    require("route_scores_enabled", summary.get("route_scores_enabled") is True)
    require("result_terminal", summary.get("result") in {"defeat", "victory"})
    require("telemetry_complete", summary.get("telemetry_complete") is True)
    require("character", summary.get("character") == "character_ranger")
    require("requested_character", summary.get("requested_character") == "character_ranger")
    require("character_ok", summary.get("character_ok") is True)
    require("danger", int(summary.get("danger", -1)) == 5)
    require("requested_danger", int(summary.get("requested_danger", -1)) == 5)
    require("danger_ok", summary.get("danger_ok") is True)
    require("opener", summary.get("weapon") == "weapon_pistol_1")
    pool = summary.get("unlock_pool") or {}
    require("era_items", int(pool.get("items", -1)) == 179)
    require("era_weapons", int(pool.get("weapons", -1)) == 48)
    require("era_hash", str(pool.get("items_hash")) == "2018397571")
    return errors


def select_runs(runs_dir):
    scanned = 0
    summaries = {}
    arm_errors = {}
    for run_id in sorted(EXPECTED_RUNS):
        path = os.path.join(runs_dir, run_id, "summary.json")
        if not os.path.isfile(path):
            arm_errors[run_id] = ["missing_summary"]
            continue
        scanned += 1
        try:
            with open(path, encoding="utf-8-sig") as handle:
                summary = json.load(handle)
        except (OSError, ValueError):
            arm_errors[run_id] = ["unreadable_summary"]
            continue
        errors = validate_summary(run_id, summary)
        if errors:
            arm_errors[run_id] = errors
        else:
            summaries[run_id] = summary
    return scanned, summaries, arm_errors


def control_rate(counter, ok, fail):
    total = counter[ok] + counter[fail]
    return (counter[ok] / total if total else 0.0), total


def collect(runs_dir, run_ids):
    controls = Counter()
    excluded = Counter()
    per_run = Counter()
    captures = []
    route_total = 0
    ranked_total = 0

    for run_id in sorted(run_ids):
        path = os.path.join(runs_dir, run_id, "events.jsonl")
        if not os.path.isfile(path):
            excluded["missing_events"] += 1
            continue
        with open(path, encoding="utf-8", errors="replace") as handle:
            for line in handle:
                if '"combat_capture"' not in line:
                    continue
                try:
                    event = json.loads(line)
                except ValueError:
                    excluded["unparseable"] += 1
                    continue
                payload = event.get("payload") or {}
                wave = int(payload.get("wave", 0))
                if wave < 1 or wave > 11:
                    continue
                route = (
                    ((payload.get("teacher") or {}).get("contributions") or {}).get("route")
                )
                if not route:
                    excluded["missing_route"] += 1
                    continue
                route_total += 1
                rows = route.get("scores") or []
                if route.get("exit") != "ranked" or not rows:
                    excluded[f"route_exit_{route.get('exit', 'missing')}"] += 1
                    continue
                ranked_total += 1
                recorded_admitted = [r for r in rows if not r.get("skip")]
                if len(recorded_admitted) < 2:
                    excluded["fewer_than_2_recorded_admitted"] += 1
                    continue

                projectile_floor = float(route.get("projectile_floor", -1e18))
                translation = (
                    ((payload.get("teacher") or {}).get("contributions") or {}).get(
                        "finale_translation"
                    )
                    or {}
                )
                loot_dash = bool(translation.get("loot_dash_active"))
                highest = highest_body(rows, projectile_floor)
                recorded_floor = float(route.get("body_floor", -1e18))
                if highest is None or recorded_floor <= -1e17:
                    controls["floor_fail"] += 1
                    excluded["floor_unavailable"] += 1
                    continue
                if abs(floor_at(highest, PACK_ACTUAL, wave, loot_dash) - recorded_floor) <= 0.02:
                    controls["floor_ok"] += 1
                else:
                    controls["floor_fail"] += 1
                    excluded["floor_model_mismatch"] += 1
                    continue

                baseline, baseline_error = recover_vector(
                    recorded_admitted, "align", ALIGN_BONUS
                )
                previous, previous_error = recover_vector(
                    recorded_admitted, "cont", CONTINUITY
                )
                if (
                    baseline is None
                    or previous is None
                    or baseline_error > VECTOR_TOL
                    or previous_error > VECTOR_TOL
                ):
                    controls["vector_fail"] += 1
                    excluded["vector_unrecoverable"] += 1
                    continue
                controls["vector_ok"] += 1

                simulated, _ = admitted_at(
                    rows, PACK_ACTUAL, projectile_floor, wave, loot_dash
                )
                if simulated is None or {key(r) for r in simulated} != {
                    key(r) for r in recorded_admitted
                }:
                    controls["admission_fail"] += 1
                    excluded["admission_mismatch"] += 1
                    continue
                controls["admission_ok"] += 1

                current = max(
                    simulated, key=lambda r: score_of(r, baseline, previous)
                )
                selected_key = (
                    round(float(route.get("sel_x", 1e9)), 4),
                    round(float(route.get("sel_y", 1e9)), 4),
                )
                if key(current) != selected_key:
                    controls["selection_fail"] += 1
                    excluded["selection_mismatch"] += 1
                    continue
                controls["selection_ok"] += 1

                entities = payload.get("entities") or {}
                threats = [
                    e
                    for e in (entities.get("enemies") or [])
                    + (entities.get("bosses") or [])
                    if float(e.get("hp", 0)) > 0
                ]
                ranges = [
                    float(w.get("max_range", 0))
                    for w in (payload.get("weapons") or [])
                    if float(w.get("max_range", 0)) > 0
                ]
                player = payload.get("player") or {}
                speed = float(player.get("speed", 0))
                if not threats or not ranges or speed <= 0:
                    excluded["missing_threat_range_or_speed"] += 1
                    continue

                px, py = float(player.get("x", 0)), float(player.get("y", 0))
                inrange = {}
                lane_value_missing = False
                for row in rows:
                    value = inrange_after(
                        px,
                        py,
                        speed,
                        float(row.get("x", 0)),
                        float(row.get("y", 0)),
                        threats,
                        max(ranges),
                    )
                    if value is None:
                        lane_value_missing = True
                    else:
                        inrange[key(row)] = value
                # Candidate headings can repeat after four-decimal telemetry
                # quantisation. Equal headings have equal in-range values, so a
                # key collision is not a missing counterfactual. The initial
                # analyzer incorrectly required one distinct key per row and
                # excluded 4,231 valid captures; §40a records that correction.
                if len({key(row) for row in rows}) != len(rows):
                    controls["rounded_key_collision_captures"] += 1
                if lane_value_missing or key(current) not in inrange:
                    excluded["degenerate_lane"] += 1
                    continue

                primary_admitted, _ = admitted_at(
                    rows, PACK_PRIMARY, projectile_floor, wave, loot_dash
                )
                if not primary_admitted:
                    excluded["empty_primary_admission"] += 1
                    continue
                added = {key(r) for r in primary_admitted} - {key(r) for r in simulated}
                controls["primary_adds_lanes" if added else "primary_adds_none"] += 1
                if key(choose_joint(primary_admitted, current, inrange, baseline, previous, False)) != key(current):
                    controls["disabled_changes"] += 1

                captures.append(
                    {
                        "run_id": run_id,
                        # §44 sequence analysis needs stable joins back to the
                        # full fresh capture stream. These observational fields
                        # do not participate in any §40 calculation.
                        "capture_seq": payload.get("capture_seq"),
                        "ts_ms": event.get("ts_ms"),
                        "wave": wave,
                        "rows": rows,
                        "projectile_floor": projectile_floor,
                        "loot_dash": loot_dash,
                        "baseline": baseline,
                        "previous": previous,
                        "current": current,
                        "inrange": inrange,
                    }
                )
                per_run[run_id] += 1

    return captures, controls, excluded, per_run, route_total, ranked_total


def evaluate_pack(captures, pack):
    flips = []
    by_run = Counter()
    for capture in captures:
        admitted, _ = admitted_at(
            capture["rows"],
            pack,
            capture["projectile_floor"],
            capture["wave"],
            capture["loot_dash"],
        )
        if not admitted:
            continue
        new = choose_joint(
            admitted,
            capture["current"],
            capture["inrange"],
            capture["baseline"],
            capture["previous"],
        )
        if key(new) == key(capture["current"]):
            continue
        old = capture["current"]
        gain = capture["inrange"][key(new)] - capture["inrange"][key(old)]
        old_body = float(old.get("body", 0))
        new_body = float(new.get("body", 0))
        ratio = new_body / old_body if old_body > 0 else None
        projectile_ok = float(new.get("proj", -1e18)) >= capture["projectile_floor"]
        subcritical_ok = new_body >= CRITICAL or new_body >= old_body
        flips.append(
            {
                "run_id": capture["run_id"],
                "wave": capture["wave"],
                "gain": gain,
                "old_body": old_body,
                "new_body": new_body,
                "body_ratio": ratio,
                "projectile_ok": projectile_ok,
                "subcritical_ok": subcritical_ok,
            }
        )
        by_run[capture["run_id"]] += 1
    return flips, by_run


def analyse(runs_dir, output):
    scanned, summaries, arm_errors = select_runs(runs_dir)
    captures, controls, excluded, per_run, route_total, ranked_total = collect(
        runs_dir, summaries
    )

    floor_rate, floor_n = control_rate(controls, "floor_ok", "floor_fail")
    admission_rate, admission_n = control_rate(
        controls, "admission_ok", "admission_fail"
    )
    selection_rate, selection_n = control_rate(
        controls, "selection_ok", "selection_fail"
    )
    vector_rate, vector_n = control_rate(controls, "vector_ok", "vector_fail")
    control_json = {
        "summaries_scanned": scanned,
        "selected_runs": sorted(summaries),
        "arm_errors": arm_errors,
        "route_total_waves_1_11": route_total,
        "ranked_total": ranked_total,
        "analysis_set": len(captures),
        "per_run_analysis_set": dict(sorted(per_run.items())),
        "excluded": dict(excluded),
        "vector_recovery": {"ok": controls["vector_ok"], "n": vector_n, "rate": vector_rate},
        "floor_model": {"ok": controls["floor_ok"], "n": floor_n, "rate": floor_rate, "bar": 0.99},
        "admission_reproduction": {"ok": controls["admission_ok"], "n": admission_n, "rate": admission_rate, "bar": 0.99},
        "selection_reproduction": {"ok": controls["selection_ok"], "n": selection_n, "rate": selection_rate, "bar": 0.99},
        "disabled_changes": controls["disabled_changes"],
        "primary_adds_lanes": controls["primary_adds_lanes"],
        "primary_adds_none": controls["primary_adds_none"],
        "rounded_key_collision_captures": controls["rounded_key_collision_captures"],
    }

    print("=" * 76)
    print("DENOMINATORS AND CONTROLS — BEFORE POLICY RESULTS")
    print("=" * 76)
    print(f"  expected/selected runs              : 8/{len(summaries)}")
    print(f"  arm errors                          : {arm_errors}")
    print(f"  route blocks, waves 1-11            : {route_total}")
    print(f"  ranked route blocks                 : {ranked_total}")
    print(f"  analysis set                        : {len(captures)}")
    print(f"  per-run analysis set                : {dict(sorted(per_run.items()))}")
    print(f"  exclusions                          : {dict(excluded)}")
    print(f"  vector recovery <=0.01              : {controls['vector_ok']}/{vector_n} = {vector_rate:.4f}")
    print(f"  floor model reproduction            : {controls['floor_ok']}/{floor_n} = {floor_rate:.4f}")
    print(f"  admission(160) reproduction         : {controls['admission_ok']}/{admission_n} = {admission_rate:.4f}")
    print(f"  selection(160) reproduction         : {controls['selection_ok']}/{selection_n} = {selection_rate:.4f}")
    print(f"  disabled-policy changes             : {controls['disabled_changes']}/{len(captures)}")
    print(f"  PACK80 adds / does not add lanes    : {controls['primary_adds_lanes']}/{controls['primary_adds_none']}")
    print(f"  rounded-key collision captures      : {controls['rounded_key_collision_captures']} (reported, not excluded)")

    controls_pass = (
        len(summaries) == 8
        and not arm_errors
        and len(captures) > 0
        and floor_rate >= 0.99
        and admission_rate >= 0.99
        and selection_rate >= 0.99
        and controls["disabled_changes"] == 0
        and controls["primary_adds_lanes"] > 0
        and controls["primary_adds_none"] > 0
    )
    if not controls_pass:
        result = {"status": "VOID", "reason": "control_failure", "controls": control_json}
        if output:
            with open(output, "w", encoding="utf-8") as handle:
                json.dump(result, handle, indent=2, sort_keys=False)
                handle.write("\n")
        print("\nVERDICT: VOID — a preregistered control failed; no policy result computed")
        return 2

    print("  CONTROL VERDICT                     : PASS")

    pack_results = {}
    evaluated = (PACK_PRIMARY,) + PACK_SENSITIVITIES
    for pack in evaluated:
        flips, by_run = evaluate_pack(captures, pack)
        gains = [f["gain"] for f in flips]
        ratios = [f["body_ratio"] for f in flips if f["body_ratio"] is not None]
        pack_results[str(int(pack))] = {
            "flips": len(flips),
            "analysis_set": len(captures),
            "flip_rate": len(flips) / len(captures),
            "by_run": dict(sorted(by_run.items())),
            "gain": {
                "median": quantile(gains, 0.5),
                "p10": quantile(gains, 0.1),
                "p90": quantile(gains, 0.9),
                "sum": sum(gains),
            },
            "body_ratio": {
                "n": len(ratios),
                "median": quantile(ratios, 0.5),
                "p10": quantile(ratios, 0.1),
            },
            "projectile_preserved": sum(1 for f in flips if f["projectile_ok"]),
            "subcritical_nonworsening": sum(1 for f in flips if f["subcritical_ok"]),
        }

    primary = pack_results[str(int(PACK_PRIMARY))]
    primary_by_run = Counter(primary["by_run"])
    contributing_runs = sum(1 for run_id in summaries if primary_by_run[run_id] > 0)
    loo_rates = []
    for run_id in sorted(summaries):
        denom = len(captures) - per_run[run_id]
        numer = primary["flips"] - primary_by_run[run_id]
        loo_rates.append({"left_out_run": run_id, "flips": numer, "denom": denom, "rate": numer / denom if denom else 0.0})
    loo_values = [row["rate"] for row in loo_rates]
    max_run_share = (
        max(primary_by_run.values(), default=0) / primary["flips"]
        if primary["flips"]
        else 0.0
    )
    integrated_gain = primary["gain"]["sum"] / route_total if route_total else 0.0
    projectile_rate = (
        primary["projectile_preserved"] / primary["flips"] if primary["flips"] else 0.0
    )
    subcritical_rate = (
        primary["subcritical_nonworsening"] / primary["flips"] if primary["flips"] else 0.0
    )

    bars = {
        "flip_rate": {"value": primary["flip_rate"], "bar": 0.20, "pass": primary["flip_rate"] >= 0.20},
        "run_coverage": {"value": contributing_runs, "bar": 7, "pass": contributing_runs >= 7},
        "loo_min": {"value": min(loo_values), "bar": 0.18, "pass": min(loo_values) >= 0.18},
        "loo_median": {"value": quantile(loo_values, 0.5), "bar": 0.20, "pass": quantile(loo_values, 0.5) >= 0.20},
        "max_run_share": {"value": max_run_share, "cap": 0.25, "pass": max_run_share <= 0.25},
        "conditional_gain_median": {"value": primary["gain"]["median"], "bar": 0.10, "pass": primary["gain"]["median"] is not None and primary["gain"]["median"] >= 0.10},
        "integrated_gain": {"value": integrated_gain, "bar": 0.02, "pass": integrated_gain >= 0.02},
        "body_ratio_median": {"value": primary["body_ratio"]["median"], "bar": 0.80, "pass": primary["body_ratio"]["median"] is not None and primary["body_ratio"]["median"] >= 0.80},
        "body_ratio_p10": {"value": primary["body_ratio"]["p10"], "bar": 0.60, "pass": primary["body_ratio"]["p10"] is not None and primary["body_ratio"]["p10"] >= 0.60},
        "projectile_preserved": {"value": projectile_rate, "bar": 1.0, "pass": projectile_rate == 1.0},
        "subcritical_nonworsening": {"value": subcritical_rate, "bar": 1.0, "pass": subcritical_rate == 1.0},
    }
    status = "PASS" if all(item["pass"] for item in bars.values()) else "FAIL"

    print("\n" + "=" * 76)
    print("PREREGISTERED PRIMARY RESULT — PACK 80")
    print("=" * 76)
    print(f"  flips                              : {primary['flips']}/{len(captures)} = {primary['flip_rate']:.4f}")
    print(f"  contributing runs                  : {contributing_runs}/8")
    print(f"  LOO min / median                   : {min(loo_values):.4f} / {quantile(loo_values, 0.5):.4f}")
    print(f"  largest run share                  : {max_run_share:.4f}")
    print(f"  conditional gain median            : {primary['gain']['median']:.4f}")
    print(f"  integrated gain / all route ticks  : {integrated_gain:.4f}")
    print(f"  body ratio p10 / median             : {primary['body_ratio']['p10']:.4f} / {primary['body_ratio']['median']:.4f}")
    print(f"  projectile preserved               : {primary['projectile_preserved']}/{primary['flips']}")
    print(f"  subcritical nonworsening            : {primary['subcritical_nonworsening']}/{primary['flips']}")
    print("\n  BAR VERDICTS")
    for name, bar in bars.items():
        print(f"    {name:30s} {'PASS' if bar['pass'] else 'FAIL'}  value={bar['value']}")

    print("\n  SENSITIVITIES (cannot rescue primary)")
    for pack in PACK_SENSITIVITIES:
        row = pack_results[str(int(pack))]
        print(
            f"    PACK {pack:3.0f}: flips {row['flips']}/{len(captures)}={row['flip_rate']:.4f}, "
            f"median gain={row['gain']['median']:.4f}, body ratio median={row['body_ratio']['median']:.4f}"
        )

    result = {
        "status": status,
        "reason": "+".join(name for name, bar in bars.items() if not bar["pass"]),
        "policy": {
            "pack_primary": PACK_PRIMARY,
            "pack_sensitivities": list(PACK_SENSITIVITIES),
            "horizon": HORIZON,
            "gain_deadband": GAIN_DEADBAND,
            "wave_min": 1,
            "wave_max": 11,
        },
        "controls": control_json,
        "primary": primary,
        "stability": {
            "contributing_runs": contributing_runs,
            "leave_one_run_out": loo_rates,
            "loo_min": min(loo_values),
            "loo_median": quantile(loo_values, 0.5),
            "max_run_share": max_run_share,
        },
        "integrated_gain": {"sum": primary["gain"]["sum"], "route_denom": route_total, "rate": integrated_gain},
        "sensitivities": {str(int(p)): pack_results[str(int(p))] for p in PACK_SENSITIVITIES},
        "bars": bars,
    }
    if output:
        with open(output, "w", encoding="utf-8") as handle:
            json.dump(result, handle, indent=2, sort_keys=False)
            handle.write("\n")
    print("\n" + "=" * 76)
    print(f"VERDICT: {status}")
    print("=" * 76)
    return 0


def self_test():
    checks = []

    def check(name, condition):
        checks.append((name, bool(condition)))

    rows = [
        {"x": 1.0, "y": 0.0, "body": 200.0, "proj": 1000.0, "pen": 0.0},
        {"x": 0.0, "y": 1.0, "body": 100.0, "proj": 1000.0, "pen": 0.0},
        {"x": -1.0, "y": 0.0, "body": 44.0, "proj": 1000.0, "pen": 0.0},
        {"x": 0.0, "y": -1.0, "body": 300.0, "proj": 10.0, "pen": 0.0},
    ]
    actual, _ = admitted_at(rows, 160.0, 100.0, 5)
    primary, _ = admitted_at(rows, 80.0, 100.0, 5)
    critical, _ = admitted_at(rows, 0.0, 100.0, 5)
    check("PACK falls monotonically admit more lanes", len(actual) <= len(primary) <= len(critical))
    check("projectile floor is preserved", all(r["proj"] >= 100.0 for r in critical))
    check("critical floor excludes body clearance 44", all(r["body"] >= CRITICAL for r in critical))

    current = rows[0]
    inrange = {key(rows[0]): 0.2, key(rows[1]): 0.7, key(rows[2]): 1.0, key(rows[3]): 1.0}
    baseline = previous = (1.0, 0.0)
    current_score_pick = max(primary, key=lambda r: score_of(r, baseline, previous))
    joint_pick = choose_joint(primary, current, inrange, baseline, previous)
    check("floor alone retains the old high-score lane", key(current_score_pick) == key(current))
    check("ranking alone cannot see the gated good lane", key(max(actual, key=lambda r: inrange[key(r)])) == key(current))
    check("joint policy selects the newly admitted good lane", key(joint_pick) == key(rows[1]))
    check("disabled policy is an exact null", key(choose_joint(primary, current, inrange, baseline, previous, False)) == key(current))

    duplicate = dict(rows[1])
    primary_with_duplicate = primary + [duplicate]
    check(
        "duplicate rounded heading remains analysable",
        key(choose_joint(primary_with_duplicate, current, inrange, baseline, previous))
        == key(rows[1]),
    )

    no_gain = dict(inrange)
    no_gain[key(rows[1])] = 0.25
    check("deadband retains current on a no-gain case", key(choose_joint(primary, current, no_gain, baseline, previous)) == key(current))

    threat = [{"x": 500.0, "y": 0.0, "vx": 0.0, "vy": 0.0}]
    fleeing = [{"x": 500.0, "y": 0.0, "vx": 900.0, "vy": 0.0}]
    check("approach puts static enemy in range", inrange_after(0, 0, 450, 1, 0, threat, 460) == 1.0)
    check("enemy velocity changes the result", inrange_after(0, 0, 450, 1, 0, fleeing, 460) == 0.0)

    base = (0.6, -0.8)
    observed = []
    for x, y in ((1, 0), (0, 1), (0.7071, 0.7071)):
        observed.append({"x": x, "y": y, "align": ALIGN_BONUS * (x * base[0] + y * base[1])})
    recovered, error = recover_vector(observed, "align", ALIGN_BONUS)
    check("direction vector recovery is exact on synthetic data", recovered is not None and error < 1e-9 and abs(recovered[0] - base[0]) < 1e-9 and abs(recovered[1] - base[1]) < 1e-9)

    for name, passed in checks:
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}")
    ok = all(passed for _, passed in checks)
    print(f"\nself-test {'PASS' if ok else 'FAIL'} ({sum(p for _, p in checks)}/{len(checks)})")
    return 0 if ok else 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs-dir")
    parser.add_argument("--output")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        return self_test()
    if not args.runs_dir:
        parser.error("--runs-dir required unless --self-test")
    return analyse(args.runs_dir, args.output)


if __name__ == "__main__":
    sys.exit(main())
