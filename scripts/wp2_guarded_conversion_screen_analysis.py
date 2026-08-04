#!/usr/bin/env python3
"""Analyze §42 in the exact preregistered order: validity, delivery, outcomes."""
from __future__ import annotations

import argparse
from itertools import combinations
import json
import math
import os
from pathlib import Path
import statistics as stats


ORDER = ("C", "T", "T", "C", "T", "C", "C", "T")
BUILD = "0.2.80-wp2-capture"
POLICY = "teacher_v1-0.1.129-gun-wp1"
ERA = {"items": 179, "weapons": 48, "items_hash": "2018397571", "weapons_hash": "1530875081"}
EPS_GAIN = 0.0001
EPS_BODY = 0.02


def exact_permutation(a: list[float], b: list[float]) -> float:
    pooled = a + b
    n = len(a)
    observed = abs(stats.mean(a) - stats.mean(b))
    hit = total = 0
    for chosen in combinations(range(len(pooled)), n):
        selected = set(chosen)
        x = [value for i, value in enumerate(pooled) if i in selected]
        y = [value for i, value in enumerate(pooled) if i not in selected]
        total += 1
        hit += abs(stats.mean(x) - stats.mean(y)) >= observed - 1e-12
    return hit / total if total else 1.0


def runs_dir() -> Path:
    return Path(os.environ["APPDATA"]) / "Brotato" / "brotato_agent" / "runs"


def mean(values: list[float]) -> float | None:
    return stats.mean(values) if values else None


def scan(run_id: str) -> dict:
    run = runs_dir() / run_id
    summary = json.loads((run / "summary.json").read_text(encoding="utf-8"))
    out = {
        "run_id": run_id,
        "summary": summary,
        "run_start": None,
        "captures_1_11": 0,
        "route_blocks": 0,
        "conversion_enabled_seen": 0,
        "conversion_enabled_true": 0,
        "ranked_opportunities": 0,
        "conversions_applied": 0,
        "nonconversion_ranked": 0,
        "guard_vetoed_candidates": 0,
        "guard_veto_captures": 0,
        "conversion_admitted_candidates": 0,
        "gains": [],
        "body_pairs": [],
        "threat_eligible": 0,
        "threat_excluded": 0,
        "in_range_values": [],
        "zero_in_range": 0,
        "hp_seen": 0,
        "hp_low": 0,
        "hp_deficit": 0.0,
        "wave11_captures": 0,
        "parse_errors": 0,
    }
    with (run / "events.jsonl").open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if '"run_start"' not in line and '"combat_capture"' not in line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                out["parse_errors"] += 1
                continue
            if event.get("event") == "run_start" and out["run_start"] is None:
                out["run_start"] = event.get("payload") or {}
                continue
            if event.get("event") != "combat_capture":
                continue
            payload = event.get("payload") or {}
            wave = payload.get("wave")
            if not isinstance(wave, int) or not 1 <= wave <= 11:
                continue
            out["captures_1_11"] += 1
            out["wave11_captures"] += wave == 11
            player = payload.get("player") or {}
            hp, maximum = player.get("hp"), player.get("max_hp")
            if isinstance(hp, (int, float)) and isinstance(maximum, (int, float)) and maximum > 0:
                ratio = hp / maximum
                out["hp_seen"] += 1
                out["hp_low"] += ratio < 0.70
                out["hp_deficit"] += max(0.0, 1.0 - ratio)

            route = (((payload.get("teacher") or {}).get("contributions") or {}).get("route") or {})
            if route:
                out["route_blocks"] += 1
                if "conversion_enabled" in route:
                    out["conversion_enabled_seen"] += 1
                    out["conversion_enabled_true"] += bool(route["conversion_enabled"])
                ranked = route.get("exit") in {"ranked", "conversion"}
                applied = bool(route.get("conversion_applied", False))
                out["ranked_opportunities"] += ranked
                out["conversions_applied"] += applied
                out["nonconversion_ranked"] += ranked and not applied
                vetoed = int(route.get("conversion_guard_vetoed", 0) or 0)
                admitted = int(route.get("conversion_admitted", 0) or 0)
                out["guard_vetoed_candidates"] += vetoed
                out["guard_veto_captures"] += vetoed > 0
                out["conversion_admitted_candidates"] += admitted
                if applied:
                    out["gains"].append(float(route.get("conversion_gain", -1e18)))
                    out["body_pairs"].append(
                        (
                            float(route.get("conversion_input_body", -1e18)),
                            float(route.get("conversion_selected_body", -1e18)),
                        )
                    )

            entities = payload.get("entities") or {}
            threats = []
            for entity in (entities.get("enemies") or []) + (entities.get("bosses") or []):
                try:
                    if float(entity.get("hp", 1.0)) > 0:
                        threats.append(entity)
                except (TypeError, ValueError):
                    continue
            ranges = []
            for weapon in payload.get("weapons") or []:
                try:
                    value = float(weapon.get("max_range", 0) or 0)
                except (TypeError, ValueError):
                    continue
                if value > 0:
                    ranges.append(value)
            try:
                px, py = float(player["x"]), float(player["y"])
            except (KeyError, TypeError, ValueError):
                threats = []
            if not threats or not ranges:
                out["threat_excluded"] += 1
                continue
            longest = max(ranges)
            in_range = 0
            for threat in threats:
                try:
                    distance = math.hypot(float(threat["x"]) - px, float(threat["y"]) - py)
                except (KeyError, TypeError, ValueError):
                    continue
                in_range += distance <= longest
            value = in_range / len(threats)
            out["threat_eligible"] += 1
            out["in_range_values"].append(value)
            out["zero_in_range"] += value == 0.0
    return out


def run_value(row: dict, key: str) -> float:
    if key == "in_range":
        return stats.mean(row["in_range_values"])
    if key == "low_hp":
        return row["hp_low"] / row["hp_seen"]
    if key == "hp_auc":
        return row["hp_deficit"] / row["hp_seen"]
    raise KeyError(key)


def validate(row: dict, arm: str) -> list[str]:
    summary = row["summary"]
    start = row["run_start"] or {}
    faults = []
    expected = {
        "policy_version": POLICY,
        "mod_version": BUILD,
        "character_observed": "character_ranger",
        "character": "character_ranger",
        "requested_character": "character_ranger",
        "danger": 5,
        "requested_danger": 5,
        "weapon": "weapon_pistol_1",
        "danger_ok": True,
        "telemetry_complete": True,
        "clearance_guarded_conversion": arm == "T",
        "route_scores_enabled": False,
        "body_clearance_scale": 1,
        "engage_distance_scale": 1,
        "calm_threat_mult": 1,
        "tail_calm_penalty_mult": 1,
        "tail_calm_clearance_mult": 1,
        "human_movement": False,
        "rare_gun_lock_persist": False,
        "movement_estop_enabled": False,
        "finale_v2": False,
        "finale_rate_full": False,
        "finale_no_panic": False,
        "finale_heal_seek": False,
        "finale_range_keep": False,
        "finale_projectile_priority": False,
        "finale_pivot_projectiles": True,
        "finale_co_rotate": False,
        "finale_ring_radius": False,
    }
    for key, value in expected.items():
        if summary.get(key) != value:
            faults.append(f"summary.{key}={summary.get(key)!r} expected={value!r}")
    for key in ("errors", "hangs", "illegal_actions", "nonfinite_fixed"):
        if int(summary.get(key, 0) or 0) != 0:
            faults.append(f"summary.{key}={summary.get(key)!r}")
    if str(summary.get("result", "")).lower() not in {"victory", "defeat"}:
        faults.append(f"summary.result={summary.get('result')!r}")
    if summary.get("unlock_pool") != ERA:
        faults.append(f"summary.unlock_pool={summary.get('unlock_pool')!r}")
    if not start:
        faults.append("run_start absent")
    elif start.get("clearance_guarded_conversion") != (arm == "T"):
        faults.append(
            "run_start.clearance_guarded_conversion="
            f"{start.get('clearance_guarded_conversion')!r}"
        )
    if row["parse_errors"]:
        faults.append(f"parse_errors={row['parse_errors']}")
    if row["captures_1_11"] <= 0 or row["hp_seen"] <= 0 or row["threat_eligible"] <= 0:
        faults.append("zero required capture denominator")
    return faults


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=Path(".tmp/s42_guarded_conversion/manifest.json"))
    parser.add_argument("--output", type=Path, default=Path("reports/wp2/clearance_guarded_conversion_screen_result.json"))
    args = parser.parse_args()

    # Statistic and guard self-tests before either can decide the result.
    assert exact_permutation([1, 1, 1], [1, 1, 1]) == 1.0
    assert exact_permutation([10, 11, 12], [1, 2, 3]) <= 0.10
    assert 80 >= max(45, 0.8 * 100) and 79.9 < max(45, 0.8 * 100)
    manifest = json.loads(args.manifest.read_text(encoding="utf-8-sig"))
    slots = manifest.get("slots") or []
    if len(slots) != 8 or tuple(row.get("arm") for row in slots) != ORDER:
        raise SystemExit("VOID: manifest is incomplete or violates fixed order")
    ids = [str(row.get("run_id")) for row in slots]
    if len(set(ids)) != 8:
        raise SystemExit("VOID: run IDs are not unique")
    rows = [{"slot": slot["slot"], "arm": slot["arm"], **scan(slot["run_id"])} for slot in slots]

    print("=" * 80)
    print("STEP 1 — VALIDITY (BEFORE OUTCOMES)")
    print("=" * 80)
    all_faults = []
    for row in rows:
        faults = validate(row, row["arm"])
        all_faults.extend((row["run_id"], fault) for fault in faults)
        summary = row["summary"]
        print(
            f"slot={row['slot']} arm={row['arm']} run={row['run_id']} "
            f"captures1-11={row['captures_1_11']} hp={row['hp_seen']} "
            f"threat={row['threat_eligible']} faults={len(faults)}"
        )
        for fault in faults:
            print(f"  FAULT: {fault}")
    print(f"unique runs 8/8; terminal summaries {sum(not validate(r, r['arm']) for r in rows)}/8")
    print(f"zero errors/hangs/illegal/nonfinite fixes: {8 - len({rid for rid, _ in all_faults if any(k in _ for k in ('errors=', 'hangs=', 'illegal_actions=', 'nonfinite_fixed='))})}/8")

    print("\n" + "=" * 80)
    print("STEP 2 — DELIVERY AND LIVE GUARD INVARIANTS")
    print("=" * 80)
    delivery_faults = []
    for arm in ("C", "T"):
        arm_rows = [row for row in rows if row["arm"] == arm]
        route = sum(row["route_blocks"] for row in arm_rows)
        enabled_seen = sum(row["conversion_enabled_seen"] for row in arm_rows)
        enabled_true = sum(row["conversion_enabled_true"] for row in arm_rows)
        ranked = sum(row["ranked_opportunities"] for row in arm_rows)
        applied = sum(row["conversions_applied"] for row in arm_rows)
        vetoed = sum(row["guard_vetoed_candidates"] for row in arm_rows)
        admitted = sum(row["conversion_admitted_candidates"] for row in arm_rows)
        print(
            f"arm={arm} route={route} enabled_seen={enabled_seen}/{route} "
            f"enabled_true={enabled_true}/{enabled_seen} ranked={ranked} "
            f"applied={applied}/{ranked} guard_vetoed={vetoed}/{admitted}"
        )
        for row in arm_rows:
            print(
                f"  {row['run_id']}: ranked={row['ranked_opportunities']} "
                f"applied={row['conversions_applied']} veto_candidates="
                f"{row['guard_vetoed_candidates']}/{row['conversion_admitted_candidates']}"
            )
        if route <= 0 or enabled_seen != route:
            delivery_faults.append(f"arm {arm}: conversion_enabled coverage {enabled_seen}/{route}")
        if arm == "C" and (enabled_true != 0 or applied != 0 or ranked <= 0):
            delivery_faults.append(f"control positive or denominator zero: true={enabled_true} applied={applied} ranked={ranked}")
        if arm == "T" and enabled_true != enabled_seen:
            delivery_faults.append(f"treatment enable readback {enabled_true}/{enabled_seen}")
    treatment = [row for row in rows if row["arm"] == "T"]
    treatment_applied = sum(row["conversions_applied"] for row in treatment)
    if any(row["conversions_applied"] <= 0 for row in treatment) or treatment_applied <= 0:
        delivery_faults.append("not every treatment trial applied a conversion")
    if sum(row["guard_vetoed_candidates"] for row in treatment) <= 0:
        delivery_faults.append("treatment guard never vetoed a candidate")
    if sum(row["nonconversion_ranked"] for row in treatment) <= 0:
        delivery_faults.append("treatment has no ranked non-conversion negative control")
    gains = [gain for row in treatment for gain in row["gains"]]
    bad_gains = sum(gain + EPS_GAIN <= 0.05 for gain in gains)
    bad_bodies = 0
    for row in treatment:
        for incumbent, selected in row["body_pairs"]:
            floor = max(45.0, 0.8 * incumbent) if incumbent >= 45 else incumbent
            bad_bodies += selected + EPS_BODY < floor
    if bad_gains:
        delivery_faults.append(f"applied gain violations={bad_gains}/{len(gains)}")
    if bad_bodies:
        delivery_faults.append(f"body guard violations={bad_bodies}/{len(gains)}")
    print(f"applied projected gains: n={len(gains)} median={stats.median(gains) if gains else None} violations={bad_gains}/{len(gains)}")
    print(f"applied body guard: violations={bad_bodies}/{len(gains)}")
    for fault in delivery_faults:
        print(f"  DELIVERY FAULT: {fault}")

    print("\n" + "=" * 80)
    print("STEP 3 — PRIMARY REALISED IN-RANGE MEDIATOR")
    print("=" * 80)
    series = {arm: [run_value(row, "in_range") for row in rows if row["arm"] == arm] for arm in ("C", "T")}
    for arm in ("C", "T"):
        print(f"arm={arm} n={len(series[arm])} raw={[round(x, 6) for x in series[arm]]} mean={stats.mean(series[arm]):.6f}")
        for row in [r for r in rows if r["arm"] == arm]:
            print(
                f"  {row['run_id']}: eligible={row['threat_eligible']} "
                f"excluded={row['threat_excluded']} zero={row['zero_in_range']}/"
                f"{row['threat_eligible']} median={stats.median(row['in_range_values']):.6f}"
            )
    delta = stats.mean(series["T"]) - stats.mean(series["C"])
    p_value = exact_permutation(series["T"], series["C"])
    primary_pass = delta >= 0.05 and p_value <= 0.05
    print(f"treatment-control delta={delta:+.6f} (bar >= +0.05); exact two-sided p={p_value:.6f} (bar <= 0.05)")

    print("\n" + "=" * 80)
    print("STEP 4 — LOW-HP SAFETY VETO")
    print("=" * 80)
    safety = {}
    for metric in ("low_hp", "hp_auc"):
        safety[metric] = {arm: [run_value(row, metric) for row in rows if row["arm"] == arm] for arm in ("C", "T")}
        for arm in ("C", "T"):
            print(f"{metric} arm={arm} n=4 raw={[round(x, 6) for x in safety[metric][arm]]} mean={stats.mean(safety[metric][arm]):.6f}")
        print(f"{metric} treatment-control={stats.mean(safety[metric]['T']) - stats.mean(safety[metric]['C']):+.6f} (must be <= 0)")
    safety_pass = all(stats.mean(safety[m]["T"]) <= stats.mean(safety[m]["C"]) for m in safety)

    print("\n" + "=" * 80)
    print("STEP 5 — CONTEXT ONLY; NO SURVIVAL CLAIM")
    print("=" * 80)
    context = []
    for row in rows:
        summary = row["summary"]
        record = {
            "slot": row["slot"], "arm": row["arm"], "run_id": row["run_id"],
            "result": summary.get("result"), "last_wave": summary.get("last_wave"),
            "duration_ms": summary.get("duration_ms"), "damage_taken": summary.get("damage_taken"),
            "wave11_captures": row["wave11_captures"],
        }
        context.append(record)
        print(record)

    if all_faults:
        status, reason = "VOID", "run validity failed"
    elif delivery_faults:
        status, reason = "VOID", "delivery or live guard invariant failed"
    elif not primary_pass:
        status, reason = "INERT_OR_TOO_SMALL", "realised in-range primary failed"
    elif not safety_pass:
        status, reason = "UNSAFE", "low-HP safety veto failed"
    else:
        status, reason = "PASS", "survival campaign licensed"
    result = {
        "status": status,
        "reason": reason,
        "validity_faults": all_faults,
        "delivery_faults": delivery_faults,
        "primary": {"control": series["C"], "treatment": series["T"], "delta": delta, "permutation_p": p_value, "pass": primary_pass},
        "safety": {
            metric: {"control": values["C"], "treatment": values["T"], "delta": stats.mean(values["T"]) - stats.mean(values["C"])}
            for metric, values in safety.items()
        },
        "safety_pass": safety_pass,
        "delivery": {"applied": treatment_applied, "gain_n": len(gains), "gain_median": stats.median(gains) if gains else None, "gain_violations": bad_gains, "body_violations": bad_bodies},
        "context": context,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"\nVERDICT: {status} — {reason}")
    print(f"Wrote {args.output}")
    return 0 if status == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
