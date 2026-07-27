"""Analyse `scene_dump` diagnostic events from a wave-20 trial.

Answers: which damage-carrying nodes are PRESENT in the live scene tree but
ABSENT from the state the controller built on the same tick -- and why.

EACH CANDIDATE IS COMPARED AGAINST THE RIGHT ID SET. The first version of this
script compared everything against the projectile ids alone, so enemy and weapon
hitboxes read "not in state" by construction and the headline count was vacuous.
Nodes are now classified first, and anything we cannot meaningfully compare is
reported as UNCOMPARABLE rather than silently counted as missing.

Usage:
    python scripts/wp2_scene_dump_analysis.py <run_dir> [<run_dir> ...]
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

PROJECTILE = "enemy projectile"
UNIT = "unit"
PLAYER_PROJ = "player projectile"
OTHER = "other"


def classify(script: str, path: str) -> str:
    """Which collected id set, if any, this node should appear in.

    Deliberately NARROW. The controller's projectile state holds ENEMY projectiles
    only, so counting the agent's own bullets -- or a pause-menu button whose
    script happens to be named `constant_projectile_button.gd` -- as "missing"
    inflates the headline with nodes that are absent for good reason.
    """
    s = script.lower()
    p = path.lower()
    if "/ui/" in p or "menu" in p:
        return OTHER
    if "player_projectile" in s or p.startswith("main/playerprojectiles"):
        return PLAYER_PROJ
    if "projectile" in s:
        return PROJECTILE
    # A real unit is a DIRECT child of Main/Entities. Behaviour components
    # (`follow_target_movement_behavior.gd`, `boss_state.gd`, `pivot.gd`,
    # `weapons_container.gd`) also live under entities/units/ but sit deeper in
    # the tree and were never going to be entities -- counting them as "missing"
    # is the same vacuous-denominator mistake as the first version of this script.
    if "entities/units/" in s and parent_of(path) == "Main/Entities":
        if s.endswith("/player.gd"):
            return OTHER  # collected into state["players"], not the enemy list
        return UNIT
    # Scriptless hitbox children, weapon sprites, behaviour components: the
    # controller never collects these as entities in their own right.
    return OTHER


def parent_of(path: str) -> str:
    return path.rsplit("/", 1)[0] if "/" in path else path


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2

    n_dumps = 0
    visited: list[int] = []
    truncated = 0
    main_children: Counter[str] = Counter()
    # (kind, parent path, script, visible, in_state) -> count
    breakdown: Counter[tuple] = Counter()
    examples: dict[tuple, dict] = {}
    per_dump_missing: dict[str, list[int]] = defaultdict(list)
    saw_unit_ids = False

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

                proj_ids = set(p.get("collected_iids") or [])
                if "collected_unit_iids" in p:
                    saw_unit_ids = True
                unit_ids = set(p.get("collected_unit_iids") or [])
                miss: Counter[str] = Counter()
                for cand in p.get("candidates") or []:
                    path = str(cand.get("path", ""))
                    script = str(cand.get("script", ""))
                    kind = classify(script, path)
                    if kind == PROJECTILE:
                        in_state = cand.get("iid") in proj_ids
                    elif kind == UNIT and saw_unit_ids:
                        in_state = cand.get("iid") in unit_ids
                    else:
                        in_state = None  # uncomparable
                    key = (kind, parent_of(path), script.split("/")[-1] or "(no script)",
                           bool(cand.get("visible", True)), in_state)
                    breakdown[key] += 1
                    examples.setdefault(key, cand)
                    if in_state is False:
                        miss[kind] += 1
                for kind in (PROJECTILE, UNIT):
                    per_dump_missing[kind].append(miss.get(kind, 0))

    if n_dumps == 0:
        print("NO scene_dump EVENTS FOUND.")
        print("The flag did not take effect, or the trial never reached wave 20.")
        return 1

    def q(v, frac):
        v = sorted(v)
        return v[min(len(v) - 1, max(0, int(frac * (len(v) - 1))))] if v else float("nan")

    print(f"scene_dump events: {n_dumps}")
    print(f"nodes visited per dump: p50={q(visited,.5)} min={min(visited)} max={max(visited)}")
    print(f"dumps hitting the node cap: {truncated}"
          + ("   <-- RAISE SCENE_DUMP_MAX_NODES; counts below are FLOORS" if truncated else ""))
    if not saw_unit_ids:
        print()
        print("!! `collected_unit_iids` ABSENT -- this run predates the unit-id extension.")
        print("!! Unit rows cannot be judged; they are reported as UNCOMPARABLE.")
    print()
    print("main's direct children:")
    print("  " + ", ".join(sorted(main_children)))
    print()

    for kind in (PROJECTILE, UNIT, PLAYER_PROJ, OTHER):
        rows = {k: v for k, v in breakdown.items() if k[0] == kind}
        if not rows:
            continue
        total = sum(rows.values())
        missing = sum(v for k, v in rows.items() if k[4] is False)
        present = sum(v for k, v in rows.items() if k[4] is True)
        uncomp = sum(v for k, v in rows.items() if k[4] is None)
        print("=" * 100)
        head = f"{kind.upper()} nodes: {total} observations"
        if uncomp == total:
            head += "   (UNCOMPARABLE -- the controller collects no id set for these)"
        else:
            head += f"   in-state {present}   MISSING {missing}"
            if total - uncomp:
                head += f" = {missing/(total-uncomp):.1%}"
        print(head)
        if kind in per_dump_missing and per_dump_missing[kind] and uncomp != total:
            v = per_dump_missing[kind]
            print(f"  missing per dump: p50={q(v,.5)} p90={q(v,.9)} max={max(v)}")
        print("-" * 100)
        print(f"{'parent path':<50}{'script':<32}{'vis':>5}{'inState':>9}{'count':>7}")
        for (_k, par, script, vis, in_state), n in sorted(rows.items(), key=lambda kv: -kv[1])[:25]:
            st = "n/a" if in_state is None else str(in_state)
            print(f"{par[:49]:<50}{script[:31]:<32}{str(vis):>5}{st:>9}{n:>7}")
        print()

    # A dead-but-still-in-tree enemy is CORRECTLY absent (collection skips
    # `if e.dead: continue`). Without splitting on it, a clean result and a real
    # blind spot look identical.
    print("=" * 100)
    print("UNCOLLECTED UNITS, split by `dead` -- dead ones are correctly absent:")
    dead_split: Counter[tuple] = Counter()
    has_dead_field = False
    for arg in argv:
        run = Path(arg)
        ev = run / "events.jsonl" if run.is_dir() else run
        if not ev.exists():
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
                unit_ids = set(p.get("collected_unit_iids") or [])
                for cand in p.get("candidates") or []:
                    if classify(str(cand.get("script", "")), str(cand.get("path", ""))) != UNIT:
                        continue
                    if cand.get("iid") in unit_ids:
                        continue
                    if "has_dead" in cand:
                        has_dead_field = True
                    script = str(cand.get("script", "")).split("/")[-1]
                    dead_split[(script, bool(cand.get("dead", False)),
                                bool(cand.get("has_dead", False)))] += 1
    if not has_dead_field:
        print("  !! `dead` field ABSENT -- this run predates the dead-flag extension.")
        print("  !! Uncollected-unit rows below CANNOT be called a blind spot yet.")
    print(f"  {'script':<28}{'dead':>7}{'has_dead':>10}{'count':>8}")
    for (script, dead, has_dead), n in sorted(dead_split.items(), key=lambda kv: -kv[1]):
        print(f"  {script[:27]:<28}{str(dead):>7}{str(has_dead):>10}{n:>8}")
    live_missing = sum(n for (_s, dead, hd), n in dead_split.items() if hd and not dead)
    print()
    print(f"  ALIVE units present in the tree but NOT in the state: {live_missing}")
    print("  (that number, and only that number, is a genuine unit blind spot)")

    print()
    print("=" * 100)
    print("MISSING nodes -- one example per distinct group:")
    for key, cand in examples.items():
        if key[4] is False:
            print(f"  [{key[0]}] {json.dumps(cand)[:220]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
