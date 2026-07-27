"""Evaluate the pre-registered co-rotation campaign.

Protocol: reports/wp2/co_rotate_eval_protocol.md, committed BEFORE trial 1.

Decision rule, fixed in advance and NOT negotiable here:
  primary metric = damage taken
  unit of analysis = FIXTURE (n=8), not trial -- trials in a fixture share a build
  d_f = mean(damage | treatment, f) - mean(damage | control, f)
  PASS requires exact Wilcoxon signed-rank p < 0.05 AND mean d_f < 0

Win rate is SECONDARY and is explicitly not the decision variable: the control arm
sits near the ceiling, so it has almost no room to move.

Usage:
    python scripts/wp2_co_rotate_eval.py --control .tmp/co_rotate/control.jsonl \
                                         --treatment .tmp/co_rotate/treatment.jsonl
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from itertools import product
from pathlib import Path


def load(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.open(encoding="utf-8") if line.strip()]


def exact_wilcoxon(diffs: list[float]) -> tuple[float, float]:
    """Exact two-sided Wilcoxon signed-rank. Returns (W, p).

    Enumerates all 2^n sign assignments -- fine for n<=20 and avoids depending on
    scipy's version-dependent handling of zeros and ties.
    """
    nz = [d for d in diffs if d != 0.0]
    n = len(nz)
    if n == 0:
        return 0.0, 1.0
    order = sorted(range(n), key=lambda i: abs(nz[i]))
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and abs(nz[order[j + 1]]) == abs(nz[order[i]]):
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    w_plus = sum(ranks[i] for i in range(n) if nz[i] > 0)
    w_minus = sum(ranks[i] for i in range(n) if nz[i] < 0)
    observed = min(w_plus, w_minus)
    count = 0
    total = 0
    for signs in product([1, -1], repeat=n):
        total += 1
        wp = sum(ranks[i] for i in range(n) if signs[i] > 0)
        wm = sum(ranks) - wp
        if min(wp, wm) <= observed + 1e-9:
            count += 1
    return observed, count / total


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--control", type=Path, required=True)
    ap.add_argument("--treatment", type=Path, required=True)
    args = ap.parse_args()

    ctl, trt = load(args.control), load(args.treatment)

    print("=" * 78)
    print("VALIDITY GATE (checked first; failure VOIDS the campaign)")
    print("=" * 78)
    ok = True
    for name, rows, expect_corot in (("control", ctl, False), ("treatment", trt, True)):
        invalid = [r for r in rows if not r.get("valid")]
        wrong_pivot = [r for r in rows if not r.get("finale_pivot_projectiles")]
        wrong_corot = [r for r in rows if bool(r.get("finale_co_rotate")) != expect_corot]
        print(f"  {name:<10} n={len(rows):<4} invalid={len(invalid)} "
              f"pivot-flag-wrong={len(wrong_pivot)} corotate-flag-wrong={len(wrong_corot)}")
        if invalid:
            print(f"      invalid reasons: {[r.get('invalid_reason') for r in invalid][:5]}")
        if invalid or wrong_pivot or wrong_corot:
            ok = False
    if not ok:
        print()
        print("GATE FAILED -- campaign is VOID. A flag that did not take effect must")
        print("invalidate the experiment, not quietly produce a null.")
        return 1
    print("  gate passed: every trial valid and on its requested arm")

    by_fix_c: dict[str, list[float]] = defaultdict(list)
    by_fix_t: dict[str, list[float]] = defaultdict(list)
    win_c: dict[str, list[int]] = defaultdict(list)
    win_t: dict[str, list[int]] = defaultdict(list)
    for r in ctl:
        by_fix_c[r["fixture_digest"]].append(float(r["damage_taken"]))
        win_c[r["fixture_digest"]].append(1 if r["result"] == "victory" else 0)
    for r in trt:
        by_fix_t[r["fixture_digest"]].append(float(r["damage_taken"]))
        win_t[r["fixture_digest"]].append(1 if r["result"] == "victory" else 0)

    fixtures = sorted(set(by_fix_c) & set(by_fix_t))
    dropped = sorted((set(by_fix_c) | set(by_fix_t)) - set(fixtures))
    print()
    print(f"paired fixtures: {len(fixtures)} (protocol expects 8)")
    if dropped:
        print(f"  DROPPED, present in only one arm: {dropped}")
    if len(fixtures) != 8:
        print("  !! fixture count differs from the protocol -- report this, do not")
        print("     silently analyse a different design than the one registered.")

    print()
    print("PRIMARY: damage taken, per fixture")
    print(f"  {'fixture':<20}{'n_ctl':>6}{'n_trt':>6}{'ctl mean':>10}{'trt mean':>10}{'diff':>9}")
    diffs = []
    for f in fixtures:
        c = sum(by_fix_c[f]) / len(by_fix_c[f])
        t = sum(by_fix_t[f]) / len(by_fix_t[f])
        d = t - c
        diffs.append(d)
        print(f"  {f[:18]:<20}{len(by_fix_c[f]):>6}{len(by_fix_t[f]):>6}"
              f"{c:>10.1f}{t:>10.1f}{d:>+9.1f}")
    mean_d = sum(diffs) / len(diffs)
    w, p = exact_wilcoxon(diffs)
    favour = sum(1 for d in diffs if d < 0)
    print()
    print(f"  mean paired difference: {mean_d:+.2f} damage  (negative = co-rotation helped)")
    print(f"  exact Wilcoxon W={w:.1f}  p={p:.4f}")
    print(f"  fixtures favouring treatment: {favour}/{len(diffs)}")

    all_c = [x for v in by_fix_c.values() for x in v]
    all_t = [x for v in by_fix_t.values() for x in v]
    print(f"  pooled mean damage: control {sum(all_c)/len(all_c):.1f}  "
          f"treatment {sum(all_t)/len(all_t):.1f}")

    wc = [x for v in win_c.values() for x in v]
    wt = [x for v in win_t.values() for x in v]
    print()
    print(f"SECONDARY (not the decision variable): win rate "
          f"control {sum(wc)}/{len(wc)} = {sum(wc)/len(wc):.3f}, "
          f"treatment {sum(wt)}/{len(wt)} = {sum(wt)/len(wt):.3f}")

    print()
    print("=" * 78)
    passed = (p < 0.05) and (mean_d < 0)
    if passed:
        print("VERDICT: PASS -- p < 0.05 AND mean difference negative.")
        print("Promotes to CANDIDATE ONLY. Requires a fresh-sample confirmation")
        print("before shipping; the flag stays default-OFF until then.")
    else:
        why = []
        if p >= 0.05:
            why.append(f"p={p:.4f} is not < 0.05")
        if mean_d >= 0:
            why.append(f"mean difference {mean_d:+.2f} is not negative")
        print(f"VERDICT: NOT CONFIRMED -- {'; '.join(why)}.")
        print("The flag stays default-OFF. Do not re-analyse with another metric,")
        print("do not add trials and re-test: both are optional stopping.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
