#!/usr/bin/env python3
"""Finale v2 vs v1 outcome analysis -- the PREDECLARED protocol, nothing more.

Implements exactly reports/wp2/finale_v2_eval_protocol.md:

  primary    victory rate on the 8 ITERATION predator builds, paired by build,
             reported as per-build RAW SERIES plus a mean paired delta with a
             bootstrap CI that resamples BUILDS (not trials);
  secondary  the 3 HELD-OUT predator builds (does v2 regress?);
  control    the 6 invoker builds -- if v2 helps invoker by a comparable margin
             the mechanism story is wrong and the predator result must be
             distrusted. THIS SCRIPT REPORTS; IT DOES NOT DECIDE.
  detectors  boss_hp_ratio_last / stationary_frac / straightness / damage /
             boss_ttk_sec, so a controller that "wins" by not killing the boss
             is visible as such;
  load       control_dt_ms percentiles against the absolute 50 ms standard.

Behavioural metrics are NOT reimplemented here -- they come from
scripts/wp2_finale_metrics.compute_metrics over the STREAMED capture payloads.

Conventions inherited from wp2_finale_metrics.py, all load-bearing:
  * every ratio is emitted with its raw numerator and denominator, and a zero
    denominator yields None -- never 0.0;
  * the size of every candidate set is printed BEFORE any zero is reported;
  * builds are keyed by `fixture_digest`, never by filename;
  * the arm is the row's `finale_v2` field, never inferred from `label`.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import statistics
import sys
from pathlib import Path
from typing import Any, Iterable, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.wp2_finale_metrics import (  # noqa: E402
    MIN_CONTROL_DT_MS,
    compute_metrics,
    iter_capture_payloads,
    load_trials,
    runs_dir,
)

DEFAULT_SEED = 20260727
N_BOOTSTRAP = 10000
N_HOLDOUT = 3  # protocol: the LAST 3 predator fixtures by capture time
Z95 = 1.959963984540054

CONTROL_RULE = (
    "PROTOCOL RULE (verbatim): \"If v2 improves invoker by a comparable margin, "
    "the mechanism story is wrong and the predator result must be distrusted -- "
    "even if it looks good.\" This rule binds regardless of significance."
)

DETECTOR_FIELDS = [
    "boss_hp_ratio_last",
    "stationary_frac",
    "straightness",
    "damage_taken",
    "boss_ttk_sec",
]

ARMS: tuple[bool, bool] = (True, False)


def arm_name(arm: bool) -> str:
    return "v2" if arm else "v1"


# --------------------------------------------------------------------------
# pure helpers (unit-tested)
# --------------------------------------------------------------------------


def _ratio(num: int, den: int) -> float | None:
    """None -- never 0.0 -- when nothing was counted."""
    if den <= 0:
        return None
    return num / den


def load_fixture_lists(path: Path) -> dict[str, list[str]]:
    """The frozen ordered fixture lists. Order defines the holdout roles."""
    data = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, list[str]] = {}
    for boss in ("predator", "invoker"):
        names = data.get(boss) or []
        out[boss] = [str(n) for n in names]
    return out


def fixture_role(fixture_file: str, lists: dict[str, list[str]]) -> tuple[str, str]:
    """(boss, role) for a fixture filename against the frozen lists.

    Predator: the last N_HOLDOUT entries are `holdout`, the rest `iteration`.
    Invoker: every entry is `control`. Anything unlisted is ("unknown", "unlisted")
    and is excluded from the endpoints -- but printed, never dropped silently.
    """
    predator = lists.get("predator") or []
    invoker = lists.get("invoker") or []
    if fixture_file in predator:
        idx = predator.index(fixture_file)
        n_iter = max(len(predator) - N_HOLDOUT, 0)
        return "predator", ("iteration" if idx < n_iter else "holdout")
    if fixture_file in invoker:
        return "invoker", "control"
    return "unknown", "unlisted"


def raw_series(rows: Sequence[dict[str, Any]]) -> str:
    """Ordered win/loss sequence, e.g. 'VLVVL'. Empty string for no trials."""
    return "".join(
        "V" if str(r.get("result", "")).lower() == "victory" else "L" for r in rows
    )


def victory_stats(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """wins / n / rate, rate None when n == 0."""
    n = len(rows)
    wins = sum(1 for r in rows if str(r.get("result", "")).lower() == "victory")
    return {"wins": wins, "n": n, "rate": _ratio(wins, n), "series": raw_series(rows)}


def group_builds(
    rows: Iterable[dict[str, Any]], lists: dict[str, list[str]]
) -> list[dict[str, Any]]:
    """Group VALID trials into builds keyed by `fixture_digest`.

    Ordered by the frozen fixture list so the printed tables match the protocol
    table. Each build carries per-arm row lists (arm read from `finale_v2`).
    """
    builds: dict[str, dict[str, Any]] = {}
    for row in rows:
        digest = str(row.get("fixture_digest") or "")
        fixture_file = str(row.get("fixture_file") or "")
        build = builds.get(digest)
        if build is None:
            boss, role = fixture_role(fixture_file, lists)
            build = {
                "fixture_digest": digest,
                "fixture_file": fixture_file,
                "boss": boss,
                "role": role,
                "arms": {True: [], False: []},
            }
            builds[digest] = build
        build["arms"][bool(row.get("finale_v2"))].append(row)

    order: dict[str, int] = {}
    for i, name in enumerate(lists.get("predator") or []):
        order[name] = i
    base = len(order)
    for i, name in enumerate(lists.get("invoker") or []):
        order[name] = base + i
    return sorted(
        builds.values(),
        key=lambda b: (order.get(b["fixture_file"], 10**6), b["fixture_digest"]),
    )


def paired_deltas(builds: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Per-build p(v2) - p(v1) over builds with trials in BOTH arms.

    A build missing an arm is EXCLUDED and NAMED -- never dropped silently.
    """
    rows: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    for build in builds:
        v2 = victory_stats(build["arms"][True])
        v1 = victory_stats(build["arms"][False])
        entry = {
            "fixture_digest": build["fixture_digest"],
            "fixture_file": build["fixture_file"],
            "role": build["role"],
            "v2": v2,
            "v1": v1,
        }
        if v2["rate"] is None or v1["rate"] is None:
            entry["reason"] = f"n_v2={v2['n']} n_v1={v1['n']} (needs >0 in both arms)"
            excluded.append(entry)
            continue
        entry["delta"] = v2["rate"] - v1["rate"]
        rows.append(entry)
    deltas = [r["delta"] for r in rows]
    return {
        "n_builds_considered": len(builds),
        "n_builds_paired": len(rows),
        "builds": rows,
        "excluded": excluded,
        "mean_delta": statistics.fmean(deltas) if deltas else None,
    }


def bootstrap_mean_ci(
    values: Sequence[float],
    seed: int,
    n_resamples: int = N_BOOTSTRAP,
) -> dict[str, Any] | None:
    """95% percentile bootstrap CI for the mean, resampling the UNITS given.

    Callers pass per-BUILD deltas, so the resampling unit is the build, not the
    trial. Deterministic for a fixed seed.
    """
    k = len(values)
    if k == 0:
        return None
    rng = random.Random(seed)
    means: list[float] = []
    for _ in range(n_resamples):
        means.append(statistics.fmean(rng.choices(values, k=k)))
    means.sort()
    lo = means[int(math.floor(0.025 * (n_resamples - 1)))]
    hi = means[int(math.ceil(0.975 * (n_resamples - 1)))]
    return {
        "mean": statistics.fmean(values),
        "lo": lo,
        "hi": hi,
        "n_units": k,
        "n_resamples": n_resamples,
        "seed": seed,
    }


def _hypergeom_pmf(a: int, row1: int, row2: int, col1: int) -> float:
    total = row1 + row2
    return (
        math.comb(row1, a)
        * math.comb(row2, col1 - a)
        / math.comb(total, col1)
    )


def fisher_exact_two_sided(a: int, b: int, c: int, d: int) -> float | None:
    """Two-sided Fisher exact p for [[a, b], [c, d]]. None if the table is empty."""
    row1, row2, col1 = a + b, c + d, a + c
    total = row1 + row2
    if total <= 0 or row1 <= 0 or row2 <= 0 or col1 <= 0 or col1 >= total:
        return None
    lo = max(0, col1 - row2)
    hi = min(row1, col1)
    p_obs = _hypergeom_pmf(a, row1, row2, col1)
    p = 0.0
    for k in range(lo, hi + 1):
        pk = _hypergeom_pmf(k, row1, row2, col1)
        if pk <= p_obs * (1 + 1e-7):
            p += pk
    return min(p, 1.0)


def wilson_interval(x: int, n: int, z: float = Z95) -> tuple[float, float] | None:
    """Wilson score interval; None for a zero denominator."""
    if n <= 0:
        return None
    p = x / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


def newcombe_diff_ci(
    x2: int, n2: int, x1: int, n1: int, z: float = Z95
) -> tuple[float, float] | None:
    """Newcombe hybrid-score CI for p2 - p1 (arm 2 = v2, arm 1 = v1)."""
    w2 = wilson_interval(x2, n2, z)
    w1 = wilson_interval(x1, n1, z)
    if w2 is None or w1 is None:
        return None
    p2, p1 = x2 / n2, x1 / n1
    l2, u2 = w2
    l1, u1 = w1
    lo = (p2 - p1) - math.sqrt((p2 - l2) ** 2 + (u1 - p1) ** 2)
    hi = (p2 - p1) + math.sqrt((u2 - p2) ** 2 + (p1 - l1) ** 2)
    return max(-1.0, lo), min(1.0, hi)


def pooled_2x2(builds: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Pooled v2-vs-v1 table. SECONDARY view: it IGNORES build clustering."""
    x2 = sum(victory_stats(b["arms"][True])["wins"] for b in builds)
    n2 = sum(len(b["arms"][True]) for b in builds)
    x1 = sum(victory_stats(b["arms"][False])["wins"] for b in builds)
    n1 = sum(len(b["arms"][False]) for b in builds)
    r2 = _ratio(x2, n2)
    r1 = _ratio(x1, n1)
    return {
        "v2_wins": x2,
        "v2_n": n2,
        "v2_rate": r2,
        "v1_wins": x1,
        "v1_n": n1,
        "v1_rate": r1,
        "diff": None if (r2 is None or r1 is None) else r2 - r1,
        "fisher_p_two_sided": fisher_exact_two_sided(x2, n2 - x2, x1, n1 - x1),
        "newcombe_diff_ci": newcombe_diff_ci(x2, n2, x1, n1),
        "note": "pooled -- ignores build clustering; the paired build-level CI is primary",
    }


def control_ratio(invoker_delta: float | None, predator_delta: float | None) -> float | None:
    """invoker_delta / predator_delta. None unless the predator delta is > 0."""
    if invoker_delta is None or predator_delta is None:
        return None
    if predator_delta <= 0:
        return None
    return invoker_delta / predator_delta


def percentiles(values: Sequence[float], qs: Sequence[float]) -> dict[str, float | None]:
    """Nearest-rank percentiles on a sorted copy; all None for an empty set."""
    if not values:
        return {f"p{int(q * 100)}": None for q in qs}
    ordered = sorted(values)
    out: dict[str, float | None] = {}
    for q in qs:
        idx = min(len(ordered) - 1, max(0, int(math.ceil(q * len(ordered))) - 1))
        out[f"p{int(q * 100)}"] = ordered[idx]
    return out


def validity_table(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Per-arm total / valid / invalid-reason breakdown. Nothing is dropped silently."""
    out: dict[str, Any] = {}
    for arm in ARMS:
        arm_rows = [r for r in rows if bool(r.get("finale_v2")) is arm]
        valid = [r for r in arm_rows if r.get("valid") is True]
        reasons: dict[str, int] = {}
        for r in arm_rows:
            if r.get("valid") is True:
                continue
            reason = str(r.get("invalid_reason") or "<blank>")
            reasons[reason] = reasons.get(reason, 0) + 1
        out[arm_name(arm)] = {
            "total": len(arm_rows),
            "valid": len(valid),
            "invalid": len(arm_rows) - len(valid),
            "valid_frac": _ratio(len(valid), len(arm_rows)),
            "invalid_reasons": dict(sorted(reasons.items())),
        }
    return out


# --------------------------------------------------------------------------
# telemetry-backed sections
# --------------------------------------------------------------------------


def trial_telemetry(row: dict[str, Any], rd: Path) -> dict[str, Any]:
    """Behavioural metrics + control_dt_ms samples for one trial, by STREAMING."""
    run_id = str(row.get("run_id") or "")
    events = rd / run_id / "events.jsonl"
    out: dict[str, Any] = {
        "run_id": run_id,
        "events_found": events.exists(),
        "metrics": None,
        "control_dt_ms": [],
    }
    if not events.exists():
        return out
    payloads: list[dict[str, Any]] = []
    dts: list[float] = []
    for payload in iter_capture_payloads(events):
        payloads.append(payload)
        dt = payload.get("control_dt_ms")
        if isinstance(dt, (int, float)) and not isinstance(dt, bool):
            # Start-up captures are not real control intervals.
            if dt >= MIN_CONTROL_DT_MS:
                dts.append(float(dt))
    out["metrics"] = compute_metrics(payloads)
    out["control_dt_ms"] = dts
    return out


def detector_summary(metrics: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """median / p10 / p90 for each freeze detector, with its own n."""
    out: dict[str, Any] = {}
    for field in DETECTOR_FIELDS:
        vals = [
            float(m[field])
            for m in metrics
            if isinstance(m.get(field), (int, float)) and not isinstance(m.get(field), bool)
        ]
        pct = percentiles(vals, (0.10, 0.90))
        out[field] = {
            "n": len(vals),
            "median": statistics.median(vals) if vals else None,
            "p10": pct["p10"],
            "p90": pct["p90"],
        }
    return out


# --------------------------------------------------------------------------
# printing
# --------------------------------------------------------------------------


def _f(value: Any, digits: int = 4) -> str:
    if value is None:
        return "null"
    if isinstance(value, float):
        return f"{value:.{digits}g}"
    return str(value)


def _print_build_table(title: str, result: dict[str, Any]) -> None:
    print(f"\n--- {title} ---")
    print(
        f"candidate builds: {result['n_builds_considered']}, "
        f"paired: {result['n_builds_paired']}, excluded: {len(result['excluded'])}"
    )
    for ex in result["excluded"]:
        print(
            f"  EXCLUDED from paired stats: {ex['fixture_file']} "
            f"digest={ex['fixture_digest']} role={ex['role']} -- {ex['reason']}"
        )
    if not result["builds"]:
        print("  (no paired builds -- no delta reported)")
        return
    print(
        f"{'fixture':<52} {'digest':<18} {'role':<10} "
        f"{'v2 series':<14} {'v2':>9} {'v1 series':<14} {'v1':>9} {'delta':>8}"
    )
    for b in result["builds"]:
        print(
            f"{b['fixture_file']:<52} {b['fixture_digest']:<18} {b['role']:<10} "
            f"{b['v2']['series'] or '-':<14} {b['v2']['wins']:>3}/{b['v2']['n']:<5} "
            f"{b['v1']['series'] or '-':<14} {b['v1']['wins']:>3}/{b['v1']['n']:<5} "
            f"{_f(b['delta']):>8}"
        )


def _print_ci(label: str, ci: dict[str, Any] | None) -> None:
    if ci is None:
        print(f"{label}: null (no paired builds)")
        return
    print(
        f"{label}: mean {_f(ci['mean'])} "
        f"95% bootstrap CI [{_f(ci['lo'])}, {_f(ci['hi'])}] "
        f"(units={ci['n_units']} builds, resamples={ci['n_resamples']}, seed={ci['seed']})"
    )


def analyse_arm_set(
    builds: Sequence[dict[str, Any]], seed: int
) -> dict[str, Any]:
    paired = paired_deltas(builds)
    deltas = [b["delta"] for b in paired["builds"]]
    paired["bootstrap"] = bootstrap_mean_ci(deltas, seed)
    paired["pooled"] = pooled_2x2(builds)
    return paired


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--predator", type=Path, default=None)
    ap.add_argument("--invoker", type=Path, default=None)
    ap.add_argument("--fixtures", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = ap.parse_args()

    lists = load_fixture_lists(args.fixtures)
    print("=== finale v2 evaluation (protocol: reports/wp2/finale_v2_eval_protocol.md) ===")
    print(
        f"frozen fixtures: predator={len(lists['predator'])} "
        f"(iteration={max(len(lists['predator']) - N_HOLDOUT, 0)}, holdout={N_HOLDOUT}), "
        f"invoker={len(lists['invoker'])}"
    )
    print(f"seed={args.seed} bootstrap_resamples={N_BOOTSTRAP}")

    report: dict[str, Any] = {"seed": args.seed, "fixtures": lists, "sets": {}}

    all_rows: dict[str, list[dict[str, Any]]] = {}
    for boss, path in (("predator", args.predator), ("invoker", args.invoker)):
        if path is None:
            print(f"\n[{boss}] no --{boss} file given; section skipped entirely.")
            all_rows[boss] = []
            continue
        if not path.exists():
            print(f"\n[{boss}] MISSING trials file {path}; section skipped entirely.")
            all_rows[boss] = []
            continue
        all_rows[boss] = load_trials(path, label=None, include_invalid=True)

    # ---- 1. validity accounting FIRST -------------------------------------
    print("\n=== 1. validity accounting ===")
    report["validity"] = {}
    for boss in ("predator", "invoker"):
        rows = all_rows[boss]
        table = validity_table(rows)
        report["validity"][boss] = table
        print(f"\n[{boss}] rows on disk: {len(rows)}")
        for arm in ARMS:
            t = table[arm_name(arm)]
            print(
                f"  arm {arm_name(arm)}: total={t['total']} valid={t['valid']} "
                f"invalid={t['invalid']} valid_frac={_f(t['valid_frac'])}"
            )
            for reason, count in t["invalid_reasons"].items():
                print(f"      invalid_reason {reason}: {count}")
            if t["valid"] == 0:
                print(
                    f"  *** ZERO VALID TRIALS for {boss} arm {arm_name(arm)} -- "
                    f"NO downstream statistics are emitted for this arm. ***"
                )

    valid_rows = {
        boss: [r for r in all_rows[boss] if r.get("valid") is True]
        for boss in ("predator", "invoker")
    }
    builds_all = {
        boss: group_builds(valid_rows[boss], lists) for boss in ("predator", "invoker")
    }

    # ---- 2. per-build raw series ------------------------------------------
    print("\n=== 2. per-build raw series (all valid trials) ===")
    for boss in ("predator", "invoker"):
        blds = builds_all[boss]
        print(f"\n[{boss}] builds with >=1 valid trial: {len(blds)}")
        for b in blds:
            for arm in ARMS:
                st = victory_stats(b["arms"][arm])
                print(
                    f"  {b['fixture_file']:<52} digest={b['fixture_digest']:<18} "
                    f"role={b['role']:<10} arm={arm_name(arm)} "
                    f"series={st['series'] or '-':<14} {st['wins']}/{st['n']} "
                    f"rate={_f(st['rate'])}"
                )

    iteration = [b for b in builds_all["predator"] if b["role"] == "iteration"]
    holdout = [b for b in builds_all["predator"] if b["role"] == "holdout"]
    unlisted = [b for b in builds_all["predator"] + builds_all["invoker"]
                if b["role"] == "unlisted"]
    if unlisted:
        print("\nWARNING: builds not in the frozen lists (excluded from all endpoints):")
        for b in unlisted:
            print(f"  {b['fixture_file']} digest={b['fixture_digest']}")

    # ---- 3. PRIMARY: 8 iteration predator builds --------------------------
    print("\n=== 3. PRIMARY endpoint -- iteration predator builds ===")
    print(f"candidate set size: {len(iteration)} builds (protocol expects 8)")
    primary = analyse_arm_set(iteration, args.seed)
    report["sets"]["predator_iteration"] = primary
    _print_build_table("primary per-build paired table", primary)
    _print_ci("mean paired delta (v2 - v1), builds resampled", primary["bootstrap"])
    p = primary["pooled"]
    print(
        f"POOLED (SECONDARY, ignores build clustering): "
        f"v2 {p['v2_wins']}/{p['v2_n']} rate={_f(p['v2_rate'])} vs "
        f"v1 {p['v1_wins']}/{p['v1_n']} rate={_f(p['v1_rate'])}; "
        f"diff={_f(p['diff'])} fisher_p={_f(p['fisher_p_two_sided'])} "
        f"newcombe_ci={_f(p['newcombe_diff_ci'][0]) if p['newcombe_diff_ci'] else 'null'}"
        f"{'' if not p['newcombe_diff_ci'] else ', ' + _f(p['newcombe_diff_ci'][1])}"
    )
    print("Both views are reported; neither replaces the other.")

    # ---- 4. SECONDARY: held-out predator builds ---------------------------
    print("\n=== 4. SECONDARY -- held-out predator builds (does v2 REGRESS?) ===")
    print(f"candidate set size: {len(holdout)} builds (protocol expects 3)")
    hold = analyse_arm_set(holdout, args.seed)
    report["sets"]["predator_holdout"] = hold
    _print_build_table("holdout per-build paired table", hold)
    _print_ci("mean paired delta (v2 - v1), builds resampled", hold["bootstrap"])

    # ---- 5. INTERNAL CONTROL: invoker -------------------------------------
    print("\n=== 5. INTERNAL CONTROL -- invoker builds ===")
    print(f"candidate set size: {len(builds_all['invoker'])} builds (protocol expects 6)")
    control = analyse_arm_set(builds_all["invoker"], args.seed)
    report["sets"]["invoker_control"] = control
    _print_build_table("invoker per-build paired table", control)
    _print_ci("mean paired delta (v2 - v1), builds resampled", control["bootstrap"])

    pred_delta = primary["mean_delta"]
    inv_delta = control["mean_delta"]
    print("\nside by side:")
    _print_ci("  predator (iteration) delta", primary["bootstrap"])
    _print_ci("  invoker  (control)   delta", control["bootstrap"])
    ratio = control_ratio(inv_delta, pred_delta)
    print(f"control_ratio = invoker_delta / predator_delta = {_f(ratio)}")
    if ratio is None:
        print(
            "  (None: the predator delta is <= 0 or a delta is unavailable -- "
            "the ratio is NOT computed rather than silently divided.)"
        )
    print(CONTROL_RULE)
    print("This script REPORTS. It does not decide whether the rule is tripped.")
    report["control_ratio"] = ratio

    # ---- 6/7. freeze detectors + load, from telemetry ---------------------
    rd = runs_dir()
    print("\n=== 6. freeze detectors (valid trials, per boss x arm) ===")
    report["detectors"] = {}
    report["load"] = {}
    for boss in ("predator", "invoker"):
        for arm in ARMS:
            rows = [r for r in valid_rows[boss] if bool(r.get("finale_v2")) is arm]
            tele = [trial_telemetry(r, rd) for r in rows]
            found = [t for t in tele if t["events_found"]]
            metrics = [t["metrics"] for t in found if t["metrics"] is not None]
            print(
                f"\n[{boss} / {arm_name(arm)}] valid trials: {len(rows)}, "
                f"with events.jsonl: {len(found)}"
            )
            summary = detector_summary(metrics)
            report["detectors"][f"{boss}_{arm_name(arm)}"] = summary
            for field, st in summary.items():
                print(
                    f"  {field:<20} n={st['n']:<4} median={_f(st['median'])} "
                    f"p10={_f(st['p10'])} p90={_f(st['p90'])}"
                )
            dts = [d for t in found for d in t["control_dt_ms"]]
            pct = percentiles(dts, (0.5, 0.95, 0.99))
            load = {
                "n_captures": len(dts),
                "median": pct["p50"],
                "p95": pct["p95"],
                "p99": pct["p99"],
                "max": max(dts) if dts else None,
                "standard_ms": 50.0,
                "min_control_dt_ms_excluded_below": MIN_CONTROL_DT_MS,
            }
            report["load"][f"{boss}_{arm_name(arm)}"] = load
            print(
                f"  control_dt_ms (>= {MIN_CONTROL_DT_MS} ms only) n={load['n_captures']} "
                f"median={_f(load['median'])} p95={_f(load['p95'])} "
                f"p99={_f(load['p99'])} max={_f(load['max'])} "
                f"| absolute standard 50 ms"
            )

    print("\n=== 7. load check summarised above, per boss x arm, against the 50 ms standard ===")

    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
        print(f"\nJSON report written to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
