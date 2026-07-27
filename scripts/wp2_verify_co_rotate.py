"""Validation gate for the finale_co_rotate arm.

Signature: the fraction of wave-20 ticks on which the PLAYER's angular velocity
about the boss shares a sign with the projectile RING's angular velocity.

This gate is STATISTICAL, not structural. The projectile-collection gate was
structural -- `enemy_projectile_rotating.gd` simply cannot appear with the flag
off. Here a flag-off agent will co-rotate roughly half the time by chance, so a
single arm proves nothing and the number is only meaningful against a paired
control. Pass BOTH arms' run directories.

Usage:
    python scripts/wp2_verify_co_rotate.py --on <run_dir>... -- --off <run_dir>...
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path


def ring_and_player_omega(prev: dict, cur: dict):
    """(ring omega, player omega) about the boss, or None if not computable."""
    ents = cur.get("entities") or {}
    bosses = ents.get("bosses") or []
    if not bosses:
        return None
    bx, by = bosses[0].get("x"), bosses[0].get("y")

    spin, n = 0.0, 0
    for pr in ents.get("projectiles") or []:
        if "rotating" not in str(pr.get("type_id", "")):
            continue
        rx, ry = pr.get("x") - bx, pr.get("y") - by
        rl = math.hypot(rx, ry)
        if rl < 1.0:
            continue
        vx, vy = pr.get("vx") or 0.0, pr.get("vy") or 0.0
        spin += (rx * vy - ry * vx) / (rl * rl)
        n += 1
    if n == 0:
        return None
    ring = spin / n

    # Player angular velocity from its own captured velocity about the boss.
    p = cur.get("player") or {}
    rx, ry = p.get("x") - bx, p.get("y") - by
    rl = math.hypot(rx, ry)
    if rl < 1.0:
        return None
    vx, vy = p.get("vx") or 0.0, p.get("vy") or 0.0
    player = (rx * vy - ry * vx) / (rl * rl)
    return ring, player


def measure(run_dirs: list[str]) -> dict:
    agree = 0
    total = 0
    ring_missing = 0
    for arg in run_dirs:
        run = Path(arg)
        ev = run / "events.jsonl" if run.is_dir() else run
        if not ev.exists():
            print(f"MISSING {ev}", file=sys.stderr)
            continue
        prev = None
        with ev.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if '"combat_capture"' not in line:
                    continue
                try:
                    e = json.loads(line)
                except json.JSONDecodeError:
                    continue
                pl = e.get("payload") or {}
                if pl.get("wave") != 20 or not pl.get("valid"):
                    continue
                if prev is not None:
                    r = ring_and_player_omega(prev, pl)
                    if r is None:
                        ring_missing += 1
                    else:
                        ring, player = r
                        # Ignore ticks where either is essentially still: a sign
                        # on a near-zero quantity is noise, and the controller
                        # itself ignores rings below its own omega floor.
                        if abs(ring) >= 0.25 and abs(player) >= 0.05:
                            total += 1
                            if (ring > 0) == (player > 0):
                                agree += 1
                prev = pl
    return {"agree": agree, "total": total, "ring_missing": ring_missing}


def main(argv: list[str]) -> int:
    if "--on" not in argv:
        print(__doc__)
        return 2
    on_idx = argv.index("--on")
    off_idx = argv.index("--off") if "--off" in argv else len(argv)
    on_runs = [a for a in argv[on_idx + 1:off_idx] if not a.startswith("--")]
    off_runs = [a for a in argv[off_idx + 1:] if not a.startswith("--")] if off_idx < len(argv) else []

    on = measure(on_runs)
    print(f"ARM ON : co-rotating ticks {on['agree']}/{on['total']} = "
          f"{on['agree']/on['total']:.1%}" if on["total"] else "ARM ON : no usable ticks")
    if on["ring_missing"]:
        print(f"  ticks with no ring in state: {on['ring_missing']} "
              f"(expected 0 if finale_pivot_projectiles is also on)")
    if not off_runs:
        print()
        print("NO CONTROL ARM SUPPLIED -- this number alone proves nothing.")
        print("A flag-off agent co-rotates ~50% of the time by chance.")
        return 0
    off = measure(off_runs)
    print(f"ARM OFF: co-rotating ticks {off['agree']}/{off['total']} = "
          f"{off['agree']/off['total']:.1%}" if off["total"] else "ARM OFF: no usable ticks")
    if on["total"] and off["total"]:
        lift = on["agree"] / on["total"] - off["agree"] / off["total"]
        print()
        print(f"LIFT: {lift:+.1%}")
        if lift < 0.05:
            print("GATE FAILED: the arm did not measurably change steering.")
            return 1
        print("GATE PASSED: the arm measurably co-rotates more than the control.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
