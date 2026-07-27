"""Analyse `scene_dump` diagnostic events from a wave-20 trial.

Answers one question: which damage-carrying nodes are PRESENT in the live scene
tree but ABSENT from the state the controller built on the same tick -- and why.

The two candidate mechanisms produce different signatures:
  * wrong parent node  -> missing nodes sit under a path that is not `Main/Projectiles`
  * the `visible` filter -> missing nodes sit under `Main/Projectiles` with visible=false

Usage:
    python scripts/wp2_scene_dump_analysis.py <run_dir> [<run_dir> ...]
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path


def parent_of(path: str) -> str:
    return path.rsplit("/", 1)[0] if "/" in path else path


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2

    n_dumps = 0
    visited = []
    truncated = 0
    main_children: Counter[str] = Counter()
    # (parent path, script, visible, collected?) -> count
    breakdown: Counter[tuple] = Counter()
    missing_examples: dict[tuple, dict] = {}
    per_dump_missing = []
    collected_per_dump = []

    for arg in argv:
        run = Path(arg)
        ev = run / "events.jsonl" if run.is_dir() else run
        if not ev.exists():
            print(f"MISSING {ev}", file=sys.stderr)
            continue
        with ev.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if '"scene_dump"' not in line:
                    continue
                try:
                    e = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if e.get("event") != "scene_dump":
                    continue
                p = e.get("payload") or {}
                n_dumps += 1
                visited.append(p.get("nodes_visited", 0))
                if p.get("truncated"):
                    truncated += 1
                for c in p.get("main_children") or []:
                    main_children[str(c)] += 1
                collected = set(p.get("collected_iids") or [])
                collected_per_dump.append(len(collected))
                miss = 0
                for cand in p.get("candidates") or []:
                    par = parent_of(str(cand.get("path", "")))
                    script = str(cand.get("script", "")).split("/")[-1] or "(no script)"
                    vis = bool(cand.get("visible", True))
                    seen = cand.get("iid") in collected
                    key = (par, script, vis, seen)
                    breakdown[key] += 1
                    if not seen:
                        miss += 1
                        missing_examples.setdefault(key, cand)
                per_dump_missing.append(miss)

    if n_dumps == 0:
        print("NO scene_dump EVENTS FOUND.")
        print("The flag did not take effect, or the trial never reached wave 20.")
        return 1

    def q(v, frac):
        v = sorted(v)
        return v[min(len(v) - 1, max(0, int(frac * (len(v) - 1))))] if v else float("nan")

    print(f"scene_dump events: {n_dumps}")
    print(f"nodes visited per dump: p50={q(visited,.5)} min={min(visited)} max={max(visited)}")
    print(f"dumps hitting the node cap (truncated): {truncated}"
          + ("   <-- RAISE SCENE_DUMP_MAX_NODES, counts below are floors" if truncated else ""))
    print(f"collected projectiles per dump: p50={q(collected_per_dump,.5)} max={max(collected_per_dump)}")
    print(f"UNCOLLECTED damage-carrying nodes per dump: "
          f"p50={q(per_dump_missing,.5)} p90={q(per_dump_missing,.9)} max={max(per_dump_missing)}")
    print()
    print("main's direct children (where things live):")
    print("  " + ", ".join(sorted(main_children)))
    print()

    hdr = f"{'parent path':<52}{'script':<34}{'vis':>5}{'inState':>9}{'count':>8}"
    print(hdr)
    print("-" * len(hdr))
    for (par, script, vis, seen), n in sorted(breakdown.items(), key=lambda kv: -kv[1]):
        print(f"{par[:51]:<52}{script[:33]:<34}{str(vis):>5}{str(seen):>9}{n:>8}")

    print()
    print("=" * 78)
    missing = {k: v for k, v in breakdown.items() if not k[3]}
    tot_missing = sum(missing.values())
    tot = sum(breakdown.values())
    print(f"VERDICT: {tot_missing}/{tot} damage-carrying node observations were NOT in the state")
    if tot_missing:
        by_parent = defaultdict(int)
        for (par, _script, _vis, _seen), n in missing.items():
            by_parent[par] += n
        print()
        print("  uncollected, by parent path:")
        for par, n in sorted(by_parent.items(), key=lambda kv: -kv[1]):
            print(f"    {n:>7}  {par}")
        invis = sum(n for (_p, _s, vis, _seen), n in missing.items() if not vis)
        print()
        print(f"  of the uncollected, invisible (would be dropped by the `visible` filter): {invis}")
        print(f"  of the uncollected, VISIBLE (so parenting, not the filter, is the cause): "
              f"{tot_missing - invis}")
        print()
        print("  one example per distinct (parent, script, visible) group:")
        for key, cand in list(missing_examples.items())[:12]:
            print(f"    {json.dumps(cand)[:200]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
