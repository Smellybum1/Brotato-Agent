"""§25 — does the profile port generalise beyond Jack? PRE-REGISTERED analysis.

Written 2026-08-01 BEFORE any §25 run existed. Prereg §25c.

  PRIMARY   terminal wave; arm labels permuted WITHIN each character; statistic
            = total ported terminal-wave sum across strata; one-sided
            (ported > bare); alpha = 0.05.
  SECONDARY pooled victories (Fisher one-sided); per-character breakdown,
            reported for all four characters WHATEVER they show.

Stratification is the whole design. Characters differ enormously in baseline
strength; an unstratified permutation would let between-character variance
swamp the treatment. Same reason fixture campaigns here are always paired.

The null is EXACT, not sampled. Per character, DP over (subset size, subset
sum) yields that stratum's exact distribution of the ported sum; the four
strata are then CONVOLVED into the exact distribution of the total. Enumerating
the joint space (12870^4 ~ 2.7e16 assignments) is infeasible; counting it is not.

⛔ Heterogeneity is expected and is NOT a licence to pick. If the pooled test is
null but one character looks strong, that is a hypothesis for a future powered
test, not a finding (§25e).

`--self-test` validates the machinery against brute force before it decides
anything. Importing this module executes nothing.
"""

from __future__ import annotations

import argparse
import json
import os
from fractions import Fraction
from itertools import combinations
from math import comb
from pathlib import Path

# §25f: cyborg -> artificer and fisherman -> ranger, substituted for ERA SAFETY.
# cyborg's and fisherman's challenge rewards are still LOCKED, so a victory would
# unlock an item and move the shop pool mid-campaign. All four below have their
# reward already unlocked, so no §25 outcome can change the era.
CHARACTERS = ["character_artificer", "character_ranger", "character_mutant", "character_arms_dealer"]
PER_CELL = 8  # runs per (character, arm)


def subset_sum_counts(values: list[int], k: int) -> dict[int, int]:
    """Exact count of k-subsets of `values` by sum."""
    dp: list[dict[int, int]] = [{} for _ in range(k + 1)]
    dp[0][0] = 1
    for v in values:
        for j in range(min(k, len(values)) - 1, -1, -1):
            if not dp[j]:
                continue
            tgt = dp[j + 1]
            for s, c in dp[j].items():
                tgt[s + v] = tgt.get(s + v, 0) + c
    return dp[k]


def convolve(a: dict[int, int], b: dict[int, int]) -> dict[int, int]:
    out: dict[int, int] = {}
    for sa, ca in a.items():
        for sb, cb in b.items():
            out[sa + sb] = out.get(sa + sb, 0) + ca * cb
    return out


def stratified_p(strata: list[tuple[list[int], list[int]]]) -> tuple[Fraction, int, int]:
    """Exact one-sided p for the total treatment sum, permuting within strata.

    strata: list of (treatment_values, control_values) per character.
    """
    total_dist: dict[int, int] = {0: 1}
    observed = 0
    for treat, ctrl in strata:
        pooled = list(treat) + list(ctrl)
        observed += sum(treat)
        total_dist = convolve(total_dist, subset_sum_counts(pooled, len(treat)))
    at_least = sum(c for s, c in total_dist.items() if s >= observed)
    total = sum(total_dist.values())
    expected = 1
    for treat, ctrl in strata:
        expected *= comb(len(treat) + len(ctrl), len(treat))
    assert total == expected, "convolution lost mass"
    return Fraction(at_least, total), observed, total


def fisher_one_sided(a: int, b: int, c: int, d: int) -> Fraction:
    """Upper-tail Fisher exact, P(X >= a). Upper tail deliberately (cf. §11c)."""
    row1, row2, col1 = a + b, c + d, a + c
    total = row1 + row2
    hi = min(row1, col1)
    num = sum(comb(row1, x) * comb(row2, col1 - x) for x in range(a, hi + 1))
    return Fraction(num, comb(total, col1))


def self_test() -> None:
    print("Validating the stratified machinery before it decides anything.\n")

    vals = [3, 1, 4, 1, 5, 9]
    for k in range(len(vals) + 1):
        brute: dict[int, int] = {}
        for combo in combinations(vals, k):
            brute[sum(combo)] = brute.get(sum(combo), 0) + 1
        assert subset_sum_counts(vals, k) == brute
    print("  [ok] DP subset-sum counts match brute force")

    # Stratified p vs brute force over the JOINT space of two small strata.
    strata = [([7, 9], [3, 4]), ([10, 8], [6, 5])]
    p, obs, tot = stratified_p(strata)
    hits = 0
    n = 0
    for c0 in combinations(range(4), 2):
        s0 = [([7, 9] + [3, 4])[i] for i in c0]
        for c1 in combinations(range(4), 2):
            s1 = [([10, 8] + [6, 5])[i] for i in c1]
            n += 1
            if sum(s0) + sum(s1) >= obs:
                hits += 1
    assert n == tot, f"space size {n} != {tot}"
    assert p == Fraction(hits, n), f"stratified p {p} != brute {Fraction(hits, n)}"
    print(f"  [ok] stratified p matches joint enumeration: {p} = {float(p):.6g}")

    # Can return the POSITIVE: complete separation in every stratum -> the floor.
    sep = [([100, 101], [1, 2]), ([200, 201], [3, 4])]
    p_sep, _, tot_sep = stratified_p(sep)
    assert p_sep == Fraction(1, tot_sep), f"separation should be 1/{tot_sep}, got {p_sep}"
    print(f"  [ok] complete separation returns the floor 1/{tot_sep} = {float(p_sep):.6g}")

    # Can return the NULL, and the direction is right.
    p_null, _, _ = stratified_p([([5, 5], [5, 5]), ([7, 7], [7, 7])])
    assert p_null == 1, f"identical arms should be 1, got {p_null}"
    p_rev, _, _ = stratified_p([([1, 2], [100, 101]), ([3, 4], [200, 201])])
    assert p_rev == 1, f"reversed should be 1, got {p_rev}"
    print(f"  [ok] identical arms -> {float(p_null):.6g}; reversed -> {float(p_rev):.6g}")

    # Stratification must actually matter: a design where each stratum shows the
    # treatment ahead but the strata have very different levels. Unstratified,
    # the between-character spread hides it; stratified, it is visible.
    strat = [([30, 31], [28, 29]), ([5, 6], [3, 4])]
    p_s, _, _ = stratified_p(strat)
    pooled_t = [30, 31, 5, 6]
    pooled_c = [28, 29, 3, 4]
    all_v = pooled_t + pooled_c
    obs_u = sum(pooled_t)
    cnt = subset_sum_counts(all_v, 4)
    p_u = Fraction(sum(c for s, c in cnt.items() if s >= obs_u), sum(cnt.values()))
    print(f"  [ok] stratified {float(p_s):.4f} vs unstratified {float(p_u):.4f} "
          f"— stratification is {'sharper' if p_s < p_u else 'NOT sharper'} here")
    assert p_s < p_u, "stratification should sharpen this constructed case"

    assert fisher_one_sided(3, 1, 1, 3) == Fraction(17, 70)
    print(f"  [ok] Fisher reproduces the tea table 17/70 = {17/70:.6g}")

    floor = 1
    for _ in CHARACTERS:
        floor *= comb(2 * PER_CELL, PER_CELL)
    print(f"  [ok] design p-floor = 1/{floor:,} = {1/floor:.3g} (<< 0.05)")
    print("\nAll self-tests passed.")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--runs-dir", default=None)
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        self_test()
        return 0

    root = Path(args.root).resolve()
    runs_dir = Path(args.runs_dir) if args.runs_dir else Path(
        os.path.expandvars(r"%APPDATA%\Brotato\brotato_agent\runs"))

    cells: dict[tuple[str, str], list[dict]] = {}
    missing = []
    for arm in ("PORTED", "BARE"):
        for ch in CHARACTERS:
            sf = root / ".tmp" / f"gen_{arm.lower()}_{ch.replace('character_','')}" / "state.json"
            if not sf.exists():
                missing.append(f"{arm}/{ch}: no state file ({sf.name})")
                continue
            ids = json.loads(sf.read_text(encoding="utf-8-sig"))["collected_run_ids"]
            rows = []
            for rid in ids:
                sp = runs_dir / rid / "summary.json"
                if not sp.exists():
                    missing.append(f"{arm}/{ch}: missing summary {rid}")
                    continue
                s = json.loads(sp.read_text(encoding="utf-8-sig"))
                pool = s.get("unlock_pool") or {}
                rows.append({
                    "wave": s.get("last_wave"),
                    "victory": str(s.get("result", "")).lower() == "victory",
                    "build": str(s.get("mod_version")),
                    "char_ok": s.get("character_ok"),
                    "requested": str(s.get("requested_character")),
                    "era": (pool.get("items"), pool.get("weapons"), str(pool.get("items_hash"))),
                })
            if len(rows) != PER_CELL:
                missing.append(f"{arm}/{ch}: {len(rows)}/{PER_CELL} runs")
            cells[(arm, ch)] = rows

    if missing:
        print("REFUSING TO RUN — the pre-registered analysis is defined at 8 runs per cell x 8 cells.")
        for m in missing:
            print("  -", m)
        print("\nAnalysing a prefix and then collecting more is optional stopping.")
        return 2

    print("=" * 76)
    print("VALIDITY — per cell, before any outcome")
    print("=" * 76)
    clean = True
    all_eras, all_builds = set(), {}
    for arm in ("PORTED", "BARE"):
        for ch in CHARACTERS:
            rows = cells[(arm, ch)]
            eras = {r["era"] for r in rows}
            builds = sorted({r["build"] for r in rows})
            ok = sum(1 for r in rows if r["char_ok"])
            wrong = [r["requested"] for r in rows if r["requested"] != ch]
            all_eras |= eras
            all_builds.setdefault(arm, set()).update(builds)
            flag = "" if (ok == len(rows) and not wrong) else "   <-- PROBLEM"
            print(f"  {arm:<7} {ch:<24} n={len(rows)} char_ok={ok}/{len(rows)} builds={builds}{flag}")
            if ok != len(rows) or wrong:
                clean = False
    print(f"\n  ERA IDENTICAL ACROSS ALL RUNS: {len(all_eras)==1}  {sorted(all_eras, key=str)}")
    if len(all_eras) != 1:
        clean = False
        print("  ⛔ POOLING INVALID — runs span more than one shop-pool era.")
    print(f"  builds per arm: {{k: sorted(v) for k, v in all_builds.items()}}".replace("{k: sorted(v) for k, v in all_builds.items()}", str({k: sorted(v) for k, v in all_builds.items()})))

    print("\n" + "=" * 76)
    print("PER-CHARACTER BREAKDOWN — reported for all four whatever they show (§25c)")
    print("=" * 76)
    strata = []
    for ch in CHARACTERS:
        pw = [int(r["wave"]) for r in cells[("PORTED", ch)]]
        bw = [int(r["wave"]) for r in cells[("BARE", ch)]]
        pv = sum(1 for r in cells[("PORTED", ch)] if r["victory"])
        bv = sum(1 for r in cells[("BARE", ch)] if r["victory"])
        strata.append((pw, bw))
        print(f"  {ch:<24} PORTED mean {sum(pw)/len(pw):5.2f} wins {pv}/{len(pw)}   "
              f"BARE mean {sum(bw)/len(bw):5.2f} wins {bv}/{len(bw)}   delta {sum(pw)/len(pw)-sum(bw)/len(bw):+5.2f}")
        print(f"      ported {pw}")
        print(f"      bare   {bw}")

    print("\n" + "=" * 76)
    print("PRIMARY — terminal wave, STRATIFIED exact permutation (within character), one-sided")
    print("=" * 76)
    p, obs, tot = stratified_p(strata)
    tot_p = sum(sum(s[0]) for s in strata)
    tot_b = sum(sum(s[1]) for s in strata)
    print(f"  PORTED total {tot_p} (mean {tot_p/(PER_CELL*len(CHARACTERS)):.3f})")
    print(f"  BARE   total {tot_b} (mean {tot_b/(PER_CELL*len(CHARACTERS)):.3f})")
    print(f"  equally likely within-stratum assignments: {tot:,}")
    print(f"  p (exact, one-sided): {float(p):.6g}   [{p.numerator}/{p.denominator}]")
    print(f"  VERDICT at alpha=0.05: "
          f"{'REJECT null — the port generalises across ranged-capable characters' if p < Fraction(1,20) else 'NULL — no evidence the port generalises beyond Jack'}")

    print("\n" + "=" * 76)
    print("SECONDARY — pooled victories, Fisher exact, one-sided")
    print("=" * 76)
    pv = sum(1 for ch in CHARACTERS for r in cells[("PORTED", ch)] if r["victory"])
    bv = sum(1 for ch in CHARACTERS for r in cells[("BARE", ch)] if r["victory"])
    n_arm = PER_CELL * len(CHARACTERS)
    print(f"  PORTED {pv}/{n_arm}   BARE {bv}/{n_arm}")
    pf = fisher_one_sided(pv, n_arm - pv, bv, n_arm - bv)
    print(f"  p (exact, one-sided): {float(pf):.6g}")

    print("\n" + "=" * 76)
    print("⛔ §25e: if the pooled test is null but one character looks strong, that is a")
    print("   HYPOTHESIS for a future powered test — not a finding. Do not pick the best of four.")
    if not clean:
        print("⛔ VALIDITY PROBLEMS ABOVE — resolve before quoting any number.")
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
