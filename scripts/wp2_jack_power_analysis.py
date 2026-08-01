"""§24 profile-port powered test — the PRE-REGISTERED analysis.

Written 2026-08-01 while block A2 was still collecting and block B2 had not
started, i.e. BLIND to half the data. That is deliberate: the endpoint, the
statistic and the direction are fixed in code before they can be chosen to
suit an outcome.

PRE-REGISTERED (character_unlock_prereg.md §24c), do not edit after unblinding:

  PRIMARY    terminal wave; exact permutation test on the PORTED arm's sum;
             one-sided (H1: ported > bare); alpha = 0.05.
  SECONDARY  victory count; Fisher exact, one-sided, same direction.
  ARMS       PORTED = A1 + A2 (n=32);  BARE = B1 + B2 (n=32).

Validity counts are reported PER ARM *before* any outcome statistic, because a
guard evaluated on post-hoc data can select on the outcome (measurement-
discipline instance 11b). Nothing here rejects a run; divergences are reported
and the operator decides.

The permutation p-value is EXACT, not Monte Carlo: terminal waves are small
integers, so the null distribution of the arm sum is computed by dynamic
programming over (subset size, subset sum) with exact integer arithmetic.
C(64,32) is ~1.8e18 subsets — enumerating them is infeasible, counting them is
not.

Run `--self-test` to validate the machinery against brute-force enumeration and
against cases whose answers are known by construction. Importing this module
executes nothing.
"""

from __future__ import annotations

import argparse
import json
import os
from fractions import Fraction
from itertools import combinations
from math import comb
from pathlib import Path

BLOCKS = {"A1": "PORTED", "A2": "PORTED", "B1": "BARE", "B2": "BARE"}
STATE_TEMPLATE = ".tmp/jack_power_{block}/state.json"
EXPECTED_PER_BLOCK = 16


# ---------------------------------------------------------------- statistics


def subset_sum_counts(values: list[int], k: int) -> dict[int, int]:
    """Exact count of k-subsets of `values` by sum. Keys are sums, values counts.

    dp[j][s] = number of j-subsets summing to s. Integer arithmetic throughout,
    so the counts are exact however large they get.
    """
    dp: list[dict[int, int]] = [{} for _ in range(k + 1)]
    dp[0][0] = 1
    for v in values:
        # descend so each element is used at most once
        for j in range(min(k, len(values)) - 1, -1, -1):
            if not dp[j]:
                continue
            target = dp[j + 1]
            for s, c in dp[j].items():
                target[s + v] = target.get(s + v, 0) + c
    return dp[k]


def permutation_p_one_sided(treatment: list[int], control: list[int]) -> tuple[Fraction, int, int]:
    """P(sum of a random n_t-subset >= observed treatment sum), exactly.

    Under the sharp null the arm label is arbitrary, so every way of splitting
    the pooled values into arms of the observed sizes is equally likely. One
    sided in the direction H1: treatment > control.

    Returns (p, observed_sum, total_splits).
    """
    pooled = list(treatment) + list(control)
    n_t = len(treatment)
    observed = sum(treatment)
    counts = subset_sum_counts(pooled, n_t)
    at_least = sum(c for s, c in counts.items() if s >= observed)
    total = sum(counts.values())
    assert total == comb(len(pooled), n_t), "DP lost subsets"
    return Fraction(at_least, total), observed, total


def fisher_one_sided(a: int, b: int, c: int, d: int) -> Fraction:
    """One-sided Fisher exact, P(X >= a) for the 2x2 [[a,b],[c,d]].

    Upper tail deliberately: the hypothesis is that the treatment (row 1) wins
    MORE. Summing the wrong tail returns a confidently wrong number and makes
    the positive branch unreachable (measurement-discipline instance 11c).
    """
    row1, row2 = a + b, c + d
    col1 = a + c
    total = row1 + row2
    hi = min(row1, col1)
    num = sum(comb(row1, x) * comb(row2, col1 - x) for x in range(a, hi + 1))
    return Fraction(num, comb(total, col1))


# ---------------------------------------------------------------- data access


def load_block(root: Path, block: str, runs_dir: Path) -> list[dict]:
    state_path = root / STATE_TEMPLATE.format(block=block)
    if not state_path.exists():
        raise FileNotFoundError(f"missing state file for block {block}: {state_path}")
    ids = json.loads(state_path.read_text(encoding="utf-8-sig"))["collected_run_ids"]
    rows = []
    for rid in ids:
        summary = runs_dir / rid / "summary.json"
        if not summary.exists():
            raise FileNotFoundError(f"{block}: state references a missing summary: {rid}")
        s = json.loads(summary.read_text(encoding="utf-8-sig"))
        pool = s.get("unlock_pool") or {}
        rows.append(
            {
                "block": block,
                "arm": BLOCKS[block],
                "run_id": rid,
                "wave": s.get("last_wave"),
                "victory": str(s.get("result", "")).lower() == "victory",
                "mod_version": str(s.get("mod_version")),
                "character_ok": s.get("character_ok"),
                "requested": str(s.get("requested_character")),
                "observed": str(s.get("character_observed")),
                "era": (pool.get("items"), pool.get("weapons"), str(pool.get("items_hash"))),
            }
        )
    return rows


def report_validity(rows: list[dict]) -> bool:
    """Print per-arm validity BEFORE any outcome. Returns True if all clean."""
    print("=" * 72)
    print("VALIDITY (reported per arm, before any outcome statistic)")
    print("=" * 72)
    clean = True
    for arm in ("PORTED", "BARE"):
        arm_rows = [r for r in rows if r["arm"] == arm]
        builds = sorted({r["mod_version"] for r in arm_rows})
        eras = sorted({r["era"] for r in arm_rows}, key=str)
        bad_char = [r["run_id"] for r in arm_rows if not r["character_ok"]]
        wrong_char = [r["run_id"] for r in arm_rows if r["requested"] != "character_jack"]
        print(f"\n{arm}  n={len(arm_rows)}")
        print(f"  builds        : {builds}")
        print(f"  era stamps    : {eras}")
        print(f"  character_ok  : {len(arm_rows) - len(bad_char)}/{len(arm_rows)}"
              + (f"  FAILURES: {bad_char}" if bad_char else ""))
        if bad_char or wrong_char:
            clean = False
    all_eras = {r["era"] for r in rows}
    print(f"\nERA IDENTICAL ACROSS ALL {len(rows)} RUNS: {len(all_eras) == 1}  {sorted(all_eras, key=str)}")
    if len(all_eras) != 1:
        clean = False
        print("  ⛔ POOLING IS INVALID — runs span more than one shop-pool era.")

    # ---- WITHIN-ARM BLOCK DIAGNOSTIC -------------------------------------
    # PROVENANCE, stated because it matters: this diagnostic was added
    # 2026-08-01 with B2 at 6/16, prompted by noticing B2 running warmer than
    # B1 (2 victories in 6 vs 1 in 16). It is therefore NOT blind, unlike the
    # primary. It is a VALIDITY DIAGNOSTIC and deliberately carries no test and
    # no threshold: the four blocks ran SEQUENTIALLY and the primary POOLS
    # A1+A2 and B1+B2, so a large within-arm block gap would mean the pooled
    # arm difference is partly drift over time rather than treatment. Reporting
    # it cannot change the primary; concealing it could make the primary
    # unreadable.
    print("\nWITHIN-ARM BLOCK DIAGNOSTIC (blocks ran sequentially; the primary pools by arm)")
    print("  reported, not tested — a large gap means the pooled contrast carries drift")
    for arm in ("PORTED", "BARE"):
        parts = []
        for block in ("A1", "A2", "B1", "B2"):
            if BLOCKS[block] != arm:
                continue
            br = [r for r in rows if r["block"] == block]
            if not br:
                continue
            waves = [int(r["wave"]) for r in br]
            wins = sum(1 for r in br if r["victory"])
            parts.append(f"{block}: n={len(br)} sum={sum(waves)} mean={sum(waves)/len(waves):.2f} wins={wins}")
        print(f"    {arm:<7} " + "   |   ".join(parts))
    return clean


# ---------------------------------------------------------------- self-test


def self_test() -> None:
    print("Validating the machinery before it decides anything.\n")

    # 1. DP subset counts vs brute-force enumeration.
    vals = [3, 1, 4, 1, 5, 9, 2, 6]
    for k in range(len(vals) + 1):
        brute: dict[int, int] = {}
        for combo in combinations(vals, k):
            brute[sum(combo)] = brute.get(sum(combo), 0) + 1
        assert subset_sum_counts(vals, k) == brute, f"DP != brute force at k={k}"
    print(f"  [ok] DP subset-sum counts match brute force for all k over {len(vals)} values")

    # 2. Permutation p by DP vs brute force over every split.
    t, c = [7, 9, 8, 10], [3, 4, 6, 5]
    p_dp, obs, total = permutation_p_one_sided(t, c)
    pooled = t + c
    hits = sum(1 for combo in combinations(range(len(pooled)), len(t))
               if sum(pooled[i] for i in combo) >= obs)
    assert p_dp == Fraction(hits, total), "permutation p disagrees with enumeration"
    print(f"  [ok] permutation p matches full enumeration: {p_dp} = {float(p_dp):.6g}")

    # 3. It can return the POSITIVE. Complete separation must give the minimum
    #    attainable p, namely 1 / C(n, k).
    p_sep, _, tot_sep = permutation_p_one_sided([100, 101, 102, 103], [1, 2, 3, 4])
    assert p_sep == Fraction(1, tot_sep), f"complete separation should give 1/{tot_sep}, got {p_sep}"
    print(f"  [ok] complete separation returns the floor 1/{tot_sep} = {float(p_sep):.6g}")

    # 4. It can return the NULL. Identical arms must give p ~ 0.5, never tiny.
    p_null, _, _ = permutation_p_one_sided([5, 5, 5, 5], [5, 5, 5, 5])
    assert p_null == 1, f"identical arms should give p=1, got {p_null}"
    print(f"  [ok] identical arms return p = {float(p_null):.6g}")

    # 5. Direction: swapping the arms of a separated case must give ~1, not ~0.
    p_rev, _, _ = permutation_p_one_sided([1, 2, 3, 4], [100, 101, 102, 103])
    assert p_rev == 1, f"reversed separation should give p=1, got {p_rev}"
    print(f"  [ok] reversed arms return p = {float(p_rev):.6g} (one-sided, correct tail)")

    # 6. Fisher against its own canonical answer: Fisher's tea table is 17/70.
    tea = fisher_one_sided(3, 1, 1, 3)
    assert tea == Fraction(17, 70), f"tea table should be 17/70, got {tea}"
    print(f"  [ok] Fisher exact reproduces the tea table {tea} = {float(tea):.6g}")

    # 7. Fisher can return the positive and the null.
    assert fisher_one_sided(0, 4, 4, 0) == 1, "no-effect direction must give 1"
    p_fpos = fisher_one_sided(4, 0, 0, 4)
    assert p_fpos == Fraction(1, comb(8, 4)), "complete separation should be 1/70"
    print(f"  [ok] Fisher floor {p_fpos} = {float(p_fpos):.6g}, reversed = 1")

    # 8. Scale check at the real design size, and confirm the floor is well
    #    below alpha so the test is capable of significance at n=32/arm.
    floor = Fraction(1, comb(64, 32))
    print(f"  [ok] at 32 v 32 the p-value floor is 1/C(64,32) = {float(floor):.3g} (<< 0.05)")
    print("\nAll self-tests passed.")


# ---------------------------------------------------------------- main


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=".", help="repo root")
    ap.add_argument("--runs-dir", default=None, help="run archive (default: %%APPDATA%%/Brotato/brotato_agent/runs)")
    ap.add_argument("--self-test", action="store_true", help="validate the statistics and exit")
    ap.add_argument("--allow-incomplete", action="store_true",
                    help="analyse before all four blocks are full. NOT the pre-registered analysis; "
                         "prints a loud banner and is for plumbing checks only.")
    args = ap.parse_args()

    if args.self_test:
        self_test()
        return 0

    root = Path(args.root).resolve()
    runs_dir = Path(args.runs_dir) if args.runs_dir else Path(
        os.path.expandvars(r"%APPDATA%\Brotato\brotato_agent\runs"))

    rows: list[dict] = []
    incomplete = []
    for block in ("A1", "A2", "B1", "B2"):
        try:
            block_rows = load_block(root, block, runs_dir)
        except FileNotFoundError as exc:
            incomplete.append(f"{block}: {exc}")
            continue
        if len(block_rows) != EXPECTED_PER_BLOCK:
            incomplete.append(f"{block}: {len(block_rows)}/{EXPECTED_PER_BLOCK} runs")
        rows.extend(block_rows)

    if incomplete and not args.allow_incomplete:
        print("REFUSING TO RUN — the pre-registered analysis is defined at n=32 per arm.")
        for line in incomplete:
            print("  -", line)
        print("\nAnalysing a prefix and then collecting more is optional stopping, which is")
        print("exactly what made an earlier campaign on this project look real when it was not.")
        print("Pass --allow-incomplete only for plumbing checks; it is not the pre-registered test.")
        return 2
    if incomplete:
        print("!" * 72)
        print("!! INCOMPLETE DATA — THIS IS NOT THE PRE-REGISTERED ANALYSIS.")
        for line in incomplete:
            print("!!  -", line)
        print("!" * 72 + "\n")

    clean = report_validity(rows)

    ported = [r for r in rows if r["arm"] == "PORTED"]
    bare = [r for r in rows if r["arm"] == "BARE"]
    pw = [int(r["wave"]) for r in ported]
    bw = [int(r["wave"]) for r in bare]

    print("\n" + "=" * 72)
    print("PRIMARY — terminal wave, exact permutation on the arm sum, one-sided")
    print("=" * 72)
    print(f"  PORTED n={len(pw)} sum={sum(pw)} mean={sum(pw)/len(pw):.3f}  {pw}")
    print(f"  BARE   n={len(bw)} sum={sum(bw)} mean={sum(bw)/len(bw):.3f}  {bw}")
    p, obs, total = permutation_p_one_sided(pw, bw)
    print(f"\n  observed ported sum : {obs}")
    print(f"  equally likely splits: {total:,}")
    print(f"  p (exact, one-sided) : {float(p):.6g}   [{p.numerator}/{p.denominator}]")
    print(f"  VERDICT at alpha=0.05: {'REJECT null — port improves terminal wave' if p < Fraction(1,20) else 'NULL — no evidence the port improves terminal wave'}")

    print("\n" + "=" * 72)
    print("SECONDARY — victories, Fisher exact, one-sided")
    print("=" * 72)
    pv = sum(1 for r in ported if r["victory"])
    bv = sum(1 for r in bare if r["victory"])
    print(f"  PORTED {pv}/{len(ported)}   BARE {bv}/{len(bare)}")
    pf = fisher_one_sided(pv, len(ported) - pv, bv, len(bare) - bv)
    print(f"  p (exact, one-sided) : {float(pf):.6g}   [{pf.numerator}/{pf.denominator}]")

    print("\n" + "=" * 72)
    if not clean:
        print("⛔ VALIDITY PROBLEMS ABOVE — resolve before quoting any number.")
        return 3
    if incomplete:
        print("Reminder: incomplete data, NOT the pre-registered result.")
        return 1
    print("Pre-registered analysis complete at n=32 per arm.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
