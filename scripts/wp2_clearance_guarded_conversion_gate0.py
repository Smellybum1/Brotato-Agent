"""§41 Gate 0: apply the preregistered clearance guard to §40 conversion.

Implements reports/wp2/clearance_guarded_conversion_prereg.md. Imports §40's
validated production reconstruction so the only new mechanism is the fixed
per-decision body-clearance guard.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter

import wp2_joint_route_conversion_gate0 as base

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

RETENTION = 0.80


def body_guard_ok(candidate_body, recorded_body):
    if recorded_body >= base.CRITICAL:
        return candidate_body >= max(base.CRITICAL, RETENTION * recorded_body)
    return candidate_body >= recorded_body


def guarded_candidates(admitted, current):
    old_body = float(current.get("body", 0))
    return [
        row
        for row in admitted
        if body_guard_ok(float(row.get("body", 0)), old_body)
    ]


def control_rate(counter, ok, fail):
    total = counter[ok] + counter[fail]
    return (counter[ok] / total if total else 0.0), total


def pack80_pool(capture):
    admitted, _ = base.admitted_at(
        capture["rows"],
        base.PACK_PRIMARY,
        capture["projectile_floor"],
        capture["wave"],
        capture["loot_dash"],
    )
    return admitted or []


def choose(capture, candidates, enabled=True):
    return base.choose_joint(
        candidates,
        capture["current"],
        capture["inrange"],
        capture["baseline"],
        capture["previous"],
        enabled,
    )


def evaluate(captures):
    flips = []
    guarded_by_run = Counter()
    guarded_by_wave = Counter()
    analysis_by_wave = Counter(capture["wave"] for capture in captures)
    unguarded_flips = 0

    for capture in captures:
        admitted = pack80_pool(capture)
        guarded = guarded_candidates(admitted, capture["current"])
        if not guarded:
            raise RuntimeError("recorded lane disappeared from its own clearance guard")

        unguarded = choose(capture, admitted)
        if base.key(unguarded) != base.key(capture["current"]):
            unguarded_flips += 1

        selected = choose(capture, guarded)
        if base.key(selected) == base.key(capture["current"]):
            continue

        current = capture["current"]
        old_body = float(current.get("body", 0))
        new_body = float(selected.get("body", 0))
        gain = (
            capture["inrange"][base.key(selected)]
            - capture["inrange"][base.key(current)]
        )
        projectile_ok = (
            float(selected.get("proj", -1e18)) >= capture["projectile_floor"]
        )
        guard_ok = body_guard_ok(new_body, old_body)
        subcritical_ok = new_body >= base.CRITICAL or new_body >= old_body
        flips.append(
            {
                "run_id": capture["run_id"],
                "wave": capture["wave"],
                "gain": gain,
                "old_body": old_body,
                "new_body": new_body,
                "body_ratio": new_body / old_body if old_body > 0 else None,
                "projectile_ok": projectile_ok,
                "guard_ok": guard_ok,
                "subcritical_ok": subcritical_ok,
            }
        )
        guarded_by_run[capture["run_id"]] += 1
        guarded_by_wave[capture["wave"]] += 1

    return flips, guarded_by_run, guarded_by_wave, analysis_by_wave, unguarded_flips


def analyse(runs_dir, output):
    scanned, summaries, arm_errors = base.select_runs(runs_dir)
    captures, controls, excluded, per_run, route_total, ranked_total = base.collect(
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

    guard_counts = Counter()
    for capture in captures:
        admitted = pack80_pool(capture)
        guarded = guarded_candidates(admitted, capture["current"])
        vetoed = len(admitted) - len(guarded)
        guard_counts["candidate_total"] += len(admitted)
        guard_counts["candidate_vetoed"] += vetoed
        guard_counts["capture_veto"] += vetoed > 0
        guard_counts["capture_noop"] += vetoed == 0
        disabled = choose(capture, guarded, enabled=False)
        guard_counts["disabled_changes"] += (
            base.key(disabled) != base.key(capture["current"])
        )

    control_json = {
        "summaries_scanned": scanned,
        "selected_runs": sorted(summaries),
        "arm_errors": arm_errors,
        "route_total_waves_1_11": route_total,
        "ranked_total": ranked_total,
        "analysis_set": len(captures),
        "per_run_analysis_set": dict(sorted(per_run.items())),
        "excluded": dict(excluded),
        "vector_recovery": {
            "ok": controls["vector_ok"],
            "n": vector_n,
            "rate": vector_rate,
        },
        "floor_model": {
            "ok": controls["floor_ok"],
            "n": floor_n,
            "rate": floor_rate,
            "bar": 0.99,
        },
        "admission_reproduction": {
            "ok": controls["admission_ok"],
            "n": admission_n,
            "rate": admission_rate,
            "bar": 0.99,
        },
        "selection_reproduction": {
            "ok": controls["selection_ok"],
            "n": selection_n,
            "rate": selection_rate,
            "bar": 0.99,
        },
        "base_disabled_changes": controls["disabled_changes"],
        "guard_disabled_changes": guard_counts["disabled_changes"],
        "pack80_adds_lanes": controls["primary_adds_lanes"],
        "pack80_adds_none": controls["primary_adds_none"],
        "guard_candidate_total": guard_counts["candidate_total"],
        "guard_candidate_vetoed": guard_counts["candidate_vetoed"],
        "guard_capture_veto": guard_counts["capture_veto"],
        "guard_capture_noop": guard_counts["capture_noop"],
        "rounded_key_collision_captures": controls[
            "rounded_key_collision_captures"
        ],
    }

    print("=" * 78)
    print("DENOMINATORS AND CONTROLS — BEFORE GUARDED RESULTS")
    print("=" * 78)
    print(f"  expected/selected runs              : 8/{len(summaries)}")
    print(f"  arm errors                          : {arm_errors}")
    print(f"  route blocks, waves 1-11            : {route_total}")
    print(f"  ranked route blocks                 : {ranked_total}")
    print(f"  analysis set                        : {len(captures)}")
    print(f"  exclusions                          : {dict(excluded)}")
    print(f"  vector recovery <=0.01              : {controls['vector_ok']}/{vector_n} = {vector_rate:.4f}")
    print(f"  floor model reproduction            : {controls['floor_ok']}/{floor_n} = {floor_rate:.4f}")
    print(f"  admission(160) reproduction         : {controls['admission_ok']}/{admission_n} = {admission_rate:.4f}")
    print(f"  selection(160) reproduction         : {controls['selection_ok']}/{selection_n} = {selection_rate:.4f}")
    print(f"  disabled changes, base/guard        : {controls['disabled_changes']}/{guard_counts['disabled_changes']}")
    print(f"  PACK80 adds / does not add lanes    : {controls['primary_adds_lanes']}/{controls['primary_adds_none']}")
    print(f"  guard veto/no-op captures           : {guard_counts['capture_veto']}/{guard_counts['capture_noop']}")
    print(f"  guard vetoed candidates             : {guard_counts['candidate_vetoed']}/{guard_counts['candidate_total']}")

    controls_pass = (
        len(summaries) == 8
        and not arm_errors
        and len(captures) > 0
        and floor_rate >= 0.99
        and admission_rate >= 0.99
        and selection_rate >= 0.99
        and controls["disabled_changes"] == 0
        and guard_counts["disabled_changes"] == 0
        and controls["primary_adds_lanes"] > 0
        and controls["primary_adds_none"] > 0
        and guard_counts["capture_veto"] > 0
        and guard_counts["capture_noop"] > 0
    )
    if not controls_pass:
        result = {
            "status": "VOID",
            "reason": "control_failure",
            "controls": control_json,
        }
        if output:
            with open(output, "w", encoding="utf-8") as handle:
                json.dump(result, handle, indent=2)
                handle.write("\n")
        print("\nVERDICT: VOID — control failure; guarded result not computed")
        return 2
    print("  CONTROL VERDICT                     : PASS")

    flips, by_run, by_wave, analysis_by_wave, unguarded_flips = evaluate(captures)
    gains = [row["gain"] for row in flips]
    ratios = [row["body_ratio"] for row in flips if row["body_ratio"] is not None]
    flip_rate = len(flips) / len(captures)
    contributing_runs = sum(1 for run_id in summaries if by_run[run_id] > 0)
    loo = []
    for run_id in sorted(summaries):
        denom = len(captures) - per_run[run_id]
        numer = len(flips) - by_run[run_id]
        loo.append(
            {
                "left_out_run": run_id,
                "flips": numer,
                "denom": denom,
                "rate": numer / denom if denom else 0.0,
            }
        )
    loo_values = [row["rate"] for row in loo]
    max_run_share = max(by_run.values(), default=0) / len(flips) if flips else 0.0
    gain_sum = sum(gains)
    integrated_gain = gain_sum / route_total if route_total else 0.0
    projectile_rate = sum(row["projectile_ok"] for row in flips) / len(flips) if flips else 0.0
    guard_rate = sum(row["guard_ok"] for row in flips) / len(flips) if flips else 0.0
    subcritical_rate = sum(row["subcritical_ok"] for row in flips) / len(flips) if flips else 0.0

    bars = {
        "flip_rate": {"value": flip_rate, "bar": 0.20, "pass": flip_rate >= 0.20},
        "run_coverage": {"value": contributing_runs, "bar": 7, "pass": contributing_runs >= 7},
        "loo_min": {"value": min(loo_values), "bar": 0.18, "pass": min(loo_values) >= 0.18},
        "loo_median": {"value": base.quantile(loo_values, 0.5), "bar": 0.20, "pass": base.quantile(loo_values, 0.5) >= 0.20},
        "max_run_share": {"value": max_run_share, "cap": 0.25, "pass": max_run_share <= 0.25},
        "conditional_gain_median": {"value": base.quantile(gains, 0.5), "bar": 0.10, "pass": bool(gains) and base.quantile(gains, 0.5) >= 0.10},
        "integrated_gain": {"value": integrated_gain, "bar": 0.02, "pass": integrated_gain >= 0.02},
        "projectile_preserved": {"value": projectile_rate, "bar": 1.0, "pass": projectile_rate == 1.0},
        "body_guard_satisfied": {"value": guard_rate, "bar": 1.0, "pass": guard_rate == 1.0},
        "subcritical_nonworsening": {"value": subcritical_rate, "bar": 1.0, "pass": subcritical_rate == 1.0},
    }
    status = "PASS" if all(bar["pass"] for bar in bars.values()) else "FAIL"

    per_wave = {}
    for wave in sorted(analysis_by_wave):
        wave_gains = [row["gain"] for row in flips if row["wave"] == wave]
        per_wave[str(wave)] = {
            "analysis_set": analysis_by_wave[wave],
            "flips": by_wave[wave],
            "flip_rate": by_wave[wave] / analysis_by_wave[wave],
            "gain_sum": sum(wave_gains),
            "gain_median": base.quantile(wave_gains, 0.5),
        }

    retained_rate = len(flips) / unguarded_flips if unguarded_flips else 0.0
    print("\n" + "=" * 78)
    print("PREREGISTERED GUARDED RESULT")
    print("=" * 78)
    print(f"  guarded flips                       : {len(flips)}/{len(captures)} = {flip_rate:.4f}")
    print(f"  unguarded flips reproduced          : {unguarded_flips}/15274")
    print(f"  guarded / unguarded flips retained  : {len(flips)}/{unguarded_flips} = {retained_rate:.4f}")
    print(f"  contributing runs                   : {contributing_runs}/8")
    print(f"  LOO min / median                    : {min(loo_values):.4f} / {base.quantile(loo_values, 0.5):.4f}")
    print(f"  largest run share                   : {max_run_share:.4f}")
    print(f"  conditional gain median             : {base.quantile(gains, 0.5):.4f}")
    print(f"  integrated gain / all route ticks   : {integrated_gain:.4f}")
    print(f"  body ratio p10 / median              : {base.quantile(ratios, 0.1):.4f} / {base.quantile(ratios, 0.5):.4f}")
    print(f"  projectile / guard / subcritical    : {projectile_rate:.4f} / {guard_rate:.4f} / {subcritical_rate:.4f}")
    print("\n  BAR VERDICTS")
    for name, bar in bars.items():
        print(f"    {name:30s} {'PASS' if bar['pass'] else 'FAIL'}  value={bar['value']}")
    print("\n  PER-WAVE")
    for wave, row in per_wave.items():
        print(
            f"    w{wave:>2}: {row['flips']:>4}/{row['analysis_set']:<4} "
            f"= {row['flip_rate']:.4f}, gain_sum={row['gain_sum']:.2f}"
        )

    result = {
        "status": status,
        "reason": "+".join(name for name, bar in bars.items() if not bar["pass"]),
        "policy": {
            "pack": base.PACK_PRIMARY,
            "body_retention": RETENTION,
            "critical": base.CRITICAL,
            "horizon": base.HORIZON,
            "gain_deadband": base.GAIN_DEADBAND,
            "wave_min": 1,
            "wave_max": 11,
        },
        "controls": control_json,
        "primary": {
            "flips": len(flips),
            "analysis_set": len(captures),
            "flip_rate": flip_rate,
            "unguarded_flips_reproduced": unguarded_flips,
            "unguarded_reference": 15274,
            "guarded_fraction_of_unguarded": retained_rate,
            "by_run": dict(sorted(by_run.items())),
            "gain": {
                "sum": gain_sum,
                "median": base.quantile(gains, 0.5),
                "p10": base.quantile(gains, 0.1),
                "p90": base.quantile(gains, 0.9),
            },
            "body_ratio": {
                "n": len(ratios),
                "p10": base.quantile(ratios, 0.1),
                "median": base.quantile(ratios, 0.5),
            },
            "projectile_preserved": sum(row["projectile_ok"] for row in flips),
            "body_guard_satisfied": sum(row["guard_ok"] for row in flips),
            "subcritical_nonworsening": sum(row["subcritical_ok"] for row in flips),
        },
        "stability": {
            "contributing_runs": contributing_runs,
            "leave_one_run_out": loo,
            "loo_min": min(loo_values),
            "loo_median": base.quantile(loo_values, 0.5),
            "max_run_share": max_run_share,
        },
        "integrated_gain": {
            "sum": gain_sum,
            "route_denom": route_total,
            "rate": integrated_gain,
        },
        "per_wave": per_wave,
        "bars": bars,
    }
    if output:
        with open(output, "w", encoding="utf-8") as handle:
            json.dump(result, handle, indent=2)
            handle.write("\n")
    print("\n" + "=" * 78)
    print(f"VERDICT: {status}")
    print("=" * 78)
    return 0


def self_test():
    inherited_ok = base.self_test() == 0
    checks = [("inherited §40 controls", inherited_ok)]

    current = {"x": 1.0, "y": 0.0, "body": 200.0, "proj": 1000.0, "pen": 0.0}
    unsafe = {"x": 0.0, "y": 1.0, "body": 100.0, "proj": 1000.0, "pen": 0.0}
    safe = {"x": -1.0, "y": 0.0, "body": 170.0, "proj": 1000.0, "pen": 0.0}
    candidates = [current, unsafe, safe]
    inrange = {base.key(current): 0.2, base.key(unsafe): 0.9, base.key(safe): 0.7}
    guarded = guarded_candidates(candidates, current)
    selected = base.choose_joint(guarded, current, inrange, (1.0, 0.0), (1.0, 0.0))
    checks.append(("unsafe high-gain lane is vetoed", unsafe not in guarded))
    checks.append(("safe improving lane survives and is selected", base.key(selected) == base.key(safe)))

    no_gain = dict(inrange)
    no_gain[base.key(safe)] = 0.25
    retained = base.choose_joint(guarded, current, no_gain, (1.0, 0.0), (1.0, 0.0))
    checks.append(("safe no-gain lane does not pass deadband", base.key(retained) == base.key(current)))

    sub_current = {"x": 1.0, "y": 0.0, "body": 40.0}
    worse = {"x": 0.0, "y": 1.0, "body": 35.0}
    better = {"x": -1.0, "y": 0.0, "body": 42.0}
    sub_guarded = guarded_candidates([sub_current, worse, better], sub_current)
    checks.append(("subcritical worsening is vetoed", worse not in sub_guarded))
    checks.append(("subcritical non-worsening remains eligible", better in sub_guarded))

    for name, passed in checks:
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}")
    ok = all(passed for _, passed in checks)
    print(f"\n§41 self-test {'PASS' if ok else 'FAIL'} ({sum(p for _, p in checks)}/{len(checks)})")
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
