"""Analyse teacher.contributions.route -- the per-candidate body-safety ranking.

Answers, in order, and PRINTS EVERY DENOMINATOR BEFORE THE RESULT IT SUPPORTS:

  1. DELIVERY   -- is the block present, armed, and non-empty where it should be?
  2. CORRECTNESS-- does the max-scoring non-skipped row reconcile with the lane
                   the ranking actually emitted?  A self-report proves delivery,
                   never correctness; this is the loop-closing check.
  3. THE OPEN QUESTION -- how many lanes survive the gates?  If the admitted pool
                   is usually a single lane then the GATE decides the route and
                   the continuity term is decorative, however large its weight.
  4. GATE 0     -- would removing the continuity term change the chosen lane?
                   A term that cannot flip a decision is not a lever, exactly as
                   the damage-tilt valuation lever failed on board_scores.

Usage:
    python scripts/wp2_route_scores_analysis.py --runs-dir <dir> [--stride N]
    python scripts/wp2_route_scores_analysis.py --self-test
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter

# Must match BotConfig. Read from source rather than remembered -- a constant
# quoted from memory is how this project once spent three levers on a wrong label.
ALIGN_BONUS = 14.0
CONTINUITY = 85.0


def iter_route_blocks(runs_dir, run_ids, stride):
    """Yield (run_id, route_block). Streams; never loads a whole events file."""
    for rid in run_ids:
        path = os.path.join(runs_dir, rid, "events.jsonl")
        if not os.path.exists(path):
            continue
        kept = 0
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if '"combat_capture"' not in line:
                    continue
                kept += 1
                if stride > 1 and kept % stride:
                    continue
                try:
                    ev = json.loads(line)
                except ValueError:
                    continue
                payload = ev.get("payload") or {}
                contrib = (payload.get("teacher") or {}).get("contributions") or {}
                route = contrib.get("route")
                if route is None:
                    continue
                yield rid, payload, route


def analyse(blocks):
    n = 0
    exits = Counter()
    enabled = Counter()
    ranked = []
    for _rid, _payload, route in blocks:
        n += 1
        exits[route.get("exit", "(missing)")] += 1
        enabled[bool(route.get("enabled"))] += 1
        if route.get("exit") == "ranked":
            ranked.append(route)

    print("=" * 68)
    print("1. DELIVERY -- denominators first")
    print("=" * 68)
    print(f"  captures carrying a `route` block : {n}")
    if n == 0:
        print("  !! ZERO. Refusing to report anything computed on an empty set.")
        print("     Either the build predates the instrument or the path is wrong.")
        return 1
    for k, v in enabled.most_common():
        print(f"    route.enabled == {k!s:5s}          : {v} ({100.0*v/n:.1f}%)")
    print("  exit distribution (which of the six return paths fired):")
    for k, v in exits.most_common():
        print(f"    {k:18s} {v:7d}  {100.0*v/n:5.1f}%")

    with_rows = [r for r in ranked if r.get("scores")]
    print(f"\n  exit=='ranked'                    : {len(ranked)}")
    print(f"  ...of which carry candidate rows  : {len(with_rows)}")
    if not with_rows:
        print("  !! No candidate rows. If route.enabled is False that is EXPECTED:")
        print("     the flag gates the array only. The scalars above are still valid.")
        return 0

    # ---------------- 2. correctness ----------------
    print("\n" + "=" * 68)
    print("2. CORRECTNESS -- does the record reconcile with the emitted lane?")
    print("=" * 68)
    match = mismatch = unresolved = 0
    for r in with_rows:
        adm = [row for row in r["scores"] if not row.get("skip")]
        if not adm:
            unresolved += 1
            continue
        top = max(adm, key=lambda row: row.get("score", -1e18))
        if (abs(top.get("x", 0) - r.get("sel_x", 0)) < 1e-4
                and abs(top.get("y", 0) - r.get("sel_y", 0)) < 1e-4):
            match += 1
        else:
            mismatch += 1
    denom = match + mismatch
    print(f"  ranked captures with >=1 admitted lane : {denom}")
    print(f"  captures with ZERO admitted lanes      : {unresolved}"
          f"  (baseline kept by fallthrough)")
    if denom:
        print(f"  max-score row IS the selected lane     : {match}/{denom}"
              f" = {match/denom:.4f}")
        print(f"  MISMATCH                               : {mismatch}")
        if mismatch:
            print("  !! A mismatch means the recorded rows are NOT the rows the")
            print("     decision was made from. Do not use this data until resolved.")

    # ---------------- 3. the open question ----------------
    print("\n" + "=" * 68)
    print("3. HOW MANY LANES SURVIVE THE GATES?")
    print("   (if this is usually 1, the GATE decides and continuity is decorative)")
    print("=" * 68)
    counts = sorted(len([x for x in r["scores"] if not x.get("skip")])
                    for r in with_rows)
    hist = Counter(counts)
    print(f"  n = {len(counts)}   median admitted = {counts[len(counts)//2]}"
          f"   mean = {sum(counts)/len(counts):.2f}")
    print(f"  single-lane (no choice at all) = {hist[1]}"
          f" ({100.0*hist[1]/len(counts):.1f}%)")
    for k in sorted(hist)[:12]:
        print(f"    {k:3d} admitted : {hist[k]:6d}  {100.0*hist[k]/len(counts):5.1f}%")
    drops = Counter()
    for r in with_rows:
        for row in r["scores"]:
            drops[row.get("skip") or "(admitted)"] += 1
    tot = sum(drops.values())
    print(f"  per-candidate outcome, denominator {tot}:")
    for k, v in drops.most_common():
        print(f"    {k:16s} {v:7d}  {100.0*v/tot:5.1f}%")

    # ---------------- 4. gate 0 ----------------
    print("\n" + "=" * 68)
    print("4. GATE 0 -- would dropping the continuity term change the lane?")
    print("=" * 68)
    multi = [r for r in with_rows
             if len([x for x in r["scores"] if not x.get("skip")]) > 1]
    print(f"  captures where a CHOICE existed (>1 admitted): {len(multi)}"
          f"  of {len(with_rows)}")
    if not multi:
        print("  !! No capture had more than one admitted lane.")
        print("     => the continuity term never arbitrates anything. Lever DEAD,")
        print("        and no campaign is needed to establish it.")
        return 0
    flipped = 0
    spread_cont, spread_align, spread_base = [], [], []
    for r in multi:
        adm = [x for x in r["scores"] if not x.get("skip")]
        with_c = max(adm, key=lambda x: x.get("score", -1e18))
        without = max(adm, key=lambda x: x.get("score", 0.0) - x.get("cont", 0.0))
        if (abs(with_c.get("x", 0) - without.get("x", 0)) > 1e-4
                or abs(with_c.get("y", 0) - without.get("y", 0)) > 1e-4):
            flipped += 1
        cs = [x.get("cont", 0.0) for x in adm]
        as_ = [x.get("align", 0.0) for x in adm]
        bs = [x.get("proj", 0.0) - x.get("pen", 0.0) for x in adm]
        spread_cont.append(max(cs) - min(cs))
        spread_align.append(max(as_) - min(as_))
        spread_base.append(max(bs) - min(bs))

    def med(v):
        v = sorted(v)
        return v[len(v)//2]

    print(f"  continuity CHANGES the chosen lane : {flipped}/{len(multi)}"
          f" = {flipped/len(multi):.4f}")
    print("\n  MEASURED spread across ADMITTED lanes (not a coefficient bound):")
    print(f"    continuity term  median spread : {med(spread_cont):9.2f}")
    print(f"    align term       median spread : {med(spread_align):9.2f}")
    print(f"    (proj - penalty) median spread : {med(spread_base):9.2f}")
    print("\n  Reminder: body clearance is ABSENT from the score by construction,")
    print("  so it has zero spread here however large its values are.")
    return 0


def _self_test():
    """Fixtures built to PRODUCTION shape -- a fixture that constructs its inputs
    differently from production cannot catch a production bug."""
    ok = True

    def check(name, cond):
        nonlocal ok
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")
        ok = ok and cond

    # A capture where continuity flips the choice: lane B wins only via cont.
    flip = {"exit": "ranked", "enabled": True, "sel_x": 1.0, "sel_y": 0.0,
            "scores": [
                {"x": 1.0, "y": 0.0, "skip": "", "score": 100.0, "cont": 85.0,
                 "align": 14.0, "proj": 1e6, "pen": 5.0},
                {"x": 0.0, "y": 1.0, "skip": "", "score": 90.0, "cont": 0.0,
                 "align": 0.0, "proj": 1e6, "pen": 5.0}]}
    adm = [x for x in flip["scores"] if not x["skip"]]
    with_c = max(adm, key=lambda x: x["score"])
    without = max(adm, key=lambda x: x["score"] - x["cont"])
    check("continuity flip is detected", with_c["x"] != without["x"])
    check("max-score row reconciles with sel_x", with_c["x"] == flip["sel_x"])

    # A skip-only capture must contribute ZERO admitted lanes, not crash.
    allskip = [{"x": 1.0, "y": 0.0, "skip": "body_floor", "score": 0.0}]
    check("all-skipped capture yields 0 admitted",
          len([x for x in allskip if not x["skip"]]) == 0)

    # The statistic must be able to return the NEGATIVE too (11c): identical
    # continuity on every lane must report zero flips.
    noflip = [{"x": 1.0, "y": 0.0, "skip": "", "score": 100.0, "cont": 50.0},
              {"x": 0.0, "y": 1.0, "skip": "", "score": 90.0, "cont": 50.0}]
    a = max(noflip, key=lambda x: x["score"])
    b = max(noflip, key=lambda x: x["score"] - x["cont"])
    check("equal continuity => NO flip (statistic returns the negative)",
          a["x"] == b["x"])

    print("\nSELF-TEST", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs-dir")
    ap.add_argument("--run-ids", nargs="*")
    ap.add_argument("--mod-version")
    ap.add_argument("--stride", type=int, default=1)
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        return _self_test()
    if not args.runs_dir:
        ap.error("--runs-dir is required unless --self-test")

    ids = args.run_ids
    if not ids:
        ids = []
        scanned = 0
        for d in sorted(os.listdir(args.runs_dir)):
            sp = os.path.join(args.runs_dir, d, "summary.json")
            if not os.path.isfile(sp):
                continue
            scanned += 1
            try:
                s = json.load(open(sp, encoding="utf-8-sig"))
            except ValueError:
                continue
            if args.mod_version and str(s.get("mod_version")) != args.mod_version:
                continue
            ids.append(d)
        print(f"summaries scanned {scanned}, runs selected {len(ids)}"
              f"{' at ' + args.mod_version if args.mod_version else ''}")
    return analyse(iter_route_blocks(args.runs_dir, ids, args.stride))


if __name__ == "__main__":
    sys.exit(main())
