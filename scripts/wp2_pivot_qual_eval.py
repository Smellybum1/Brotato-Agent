"""Evaluate the pre-registered pivot-fix qualification campaign.

Protocol: reports/wp2/pivot_fix_qualification_protocol.md, committed BEFORE trial 1.

Decision rule, fixed in advance:
  primary metric = VICTORY RATE (not damage -- unlike the co-rotation and
  ring-radius campaigns, the control arm here is the agent WITHOUT the fix and
  is nowhere near the ceiling, so win rate has room and is what matters)
  PASS requires pooled Fisher exact p < 0.05 AND treatment win rate > control

If it passes, finale_pivot_projectiles flips to DEFAULT-ON.

Usage:
    python scripts/wp2_pivot_qual_eval.py --control .tmp/pivot_qual/control.jsonl \
                                          --treatment .tmp/pivot_qual/treatment.jsonl
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path


def load(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.open(encoding="utf-8") if line.strip()]


def fisher_exact_greater(a: int, b: int, c: int, d: int) -> float:
    """One-sided Fisher exact p for treatment > control.

    Table is [[treat_win, treat_loss], [ctl_win, ctl_loss]]. Sums the
    hypergeometric probability of tables at least as extreme.
    """
    n = a + b + c + d
    row1, col1 = a + b, a + c

    def logc(n_, k_):
        return math.lgamma(n_ + 1) - math.lgamma(k_ + 1) - math.lgamma(n_ - k_ + 1)

    total = logc(n, col1)
    p = 0.0
    lo = max(0, col1 - (c + d))
    hi = min(row1, col1)
    for x in range(a, hi + 1):
        if x < lo:
            continue
        p += math.exp(logc(row1, x) + logc(n - row1, col1 - x) - total)
    return min(1.0, p)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--control", type=Path, required=True)
    ap.add_argument("--treatment", type=Path, required=True)
    args = ap.parse_args()
    ctl_all, trt_all = load(args.control), load(args.treatment)

    print("=" * 78)
    print("VALIDITY GATE (checked first; failure VOIDS the campaign)")
    print("=" * 78)
    ok = True
    lost = []
    for name, rows, expect in (("control", ctl_all, False), ("treatment", trt_all, True)):
        invalid = [r for r in rows if not r.get("valid")]
        mismatch = [r for r in invalid if "mismatch" in str(r.get("invalid_reason", ""))]
        infra = [r for r in invalid if r not in mismatch]
        wrong = [r for r in rows if bool(r.get("finale_pivot_projectiles")) != expect]
        print(f"  {name:<10} n={len(rows):<4} arm-mismatch={len(mismatch)} "
              f"infra-invalid={len(infra)} pivot-flag-wrong={len(wrong)}")
        if infra:
            print(f"      infrastructure losses: {[r.get('invalid_reason') for r in infra]}")
        lost.extend(infra)
        if mismatch or wrong:
            ok = False
    if not ok:
        print("\nGATE FAILED -- campaign is VOID.")
        return 1
    print("  gate passed: 0 arm mismatches -- every trial ran on its requested arm")
    print()
    print("  NOTE: the STRUCTURAL signature (rotating projectiles present in the")
    print("  treatment capture stream, absent in control) must be checked separately")
    print("  with scripts/wp2_verify_pivot_arm.py. It is the claim this campaign")
    print("  rests on and it is not verifiable from these summary rows.")

    ctl = [r for r in ctl_all if r.get("valid")]
    trt = [r for r in trt_all if r.get("valid")]

    cw = sum(1 for r in ctl if r["result"] == "victory")
    tw = sum(1 for r in trt if r["result"] == "victory")
    cr, tr = cw / len(ctl), tw / len(trt)
    p = fisher_exact_greater(tw, len(trt) - tw, cw, len(ctl) - cw)

    print()
    print("PRIMARY: victory rate")
    print(f"  control   {cw}/{len(ctl)} = {cr:.3f}")
    print(f"  treatment {tw}/{len(trt)} = {tr:.3f}")
    print(f"  difference {tr - cr:+.3f}   one-sided Fisher exact p = {p:.6g}")

    print()
    print("PER FIXTURE (paired)")
    bc, bt = defaultdict(list), defaultdict(list)
    for r in ctl:
        bc[r["fixture_digest"]].append(1 if r["result"] == "victory" else 0)
    for r in trt:
        bt[r["fixture_digest"]].append(1 if r["result"] == "victory" else 0)
    print(f"  {'fixture':<20}{'control':>12}{'treatment':>12}")
    for f in sorted(set(bc) & set(bt)):
        print(f"  {f[:18]:<20}{sum(bc[f])}/{len(bc[f]):<10}{sum(bt[f])}/{len(bt[f]):<10}")

    dc = [r["damage_taken"] for r in ctl]
    dt = [r["damage_taken"] for r in trt]
    print()
    print("SECONDARY: damage taken")
    print(f"  control   mean {statistics.mean(dc):6.1f}  median {statistics.median(dc):6.1f}")
    print(f"  treatment mean {statistics.mean(dt):6.1f}  median {statistics.median(dt):6.1f}")

    print()
    print("PRE-REGISTERED SURPRISE CHECK")
    print(f"  control win rate {cr:.3f} vs its historical ~0.65-0.70.")
    if cr > 0.90:
        print("  !! CONTROL IS NEAR CEILING. Something other than the fix improved the")
        print("  !! agent between builds, and the 111/111 attribution is WRONG.")
        print("  !! Do not ship on this campaign; investigate the discrepancy first.")
    else:
        print("  in line with history -- the historical baseline is not confounded.")

    print()
    print("=" * 78)
    if p < 0.05 and tr > cr:
        print("VERDICT: PASS -- Fisher p < 0.05 AND treatment > control.")
        print("ACTION: flip finale_pivot_projectiles to DEFAULT-ON and ship it.")
    else:
        why = []
        if p >= 0.05:
            why.append(f"p={p:.4g} is not < 0.05")
        if tr <= cr:
            why.append("treatment win rate is not above control")
        print(f"VERDICT: NOT CONFIRMED -- {'; '.join(why)}.")
        print("The flag stays default-OFF and the 111/111 result must be treated as")
        print("build-confounded, however implausible that looks.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
