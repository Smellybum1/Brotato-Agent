"""Validation gate for the finale_pivot_projectiles arm.

A flag's SELF-REPORT is not evidence it took effect. The behavioural signature
here is structurally impossible for the control arm: across 426,116 control-arm
projectile observations, `enemy_projectile_rotating.gd` appeared ZERO times and
every projectile had speed exactly 500. If the arm ran, the rotating script must
appear in the captured stream with non-500 speeds.

Also checks the two things most likely to be silently wrong:
  * radius -- _collision_radius falls back to 8.0 if the node has no
    `Collision` / `Hitbox/Collision` child. The burst projectiles read 17.03.
  * velocity -- must be NON-ZERO. The nodes expose `velocity` and it reads 0;
    the whole point of the fix is deriving it from the transform instead.

Usage: python verify_pivot_arm.py <run_dir> [<run_dir> ...]
"""
import json
import math
import sys
from collections import Counter
from pathlib import Path

by_type = Counter()
speed_by_type = {}
radius_by_type = {}
zero_vel = Counter()
per_capture_rotating = []
schema_hashes = Counter()

for arg in sys.argv[1:]:
    run = Path(arg)
    ev = run / "events.jsonl" if run.is_dir() else run
    if not ev.exists():
        print(f"MISSING {ev}", file=sys.stderr)
        continue
    with ev.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if '"combat_capture"' not in line:
                continue
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            p = e.get("payload") or {}
            if p.get("wave") != 20:
                continue
            schema_hashes[str(p.get("capture_schema_hash"))] += 1
            n_rot = 0
            for pr in (p.get("entities") or {}).get("projectiles") or []:
                t = str(pr.get("type_id", "")).split("/")[-1]
                by_type[t] += 1
                sp = math.hypot(pr.get("vx") or 0.0, pr.get("vy") or 0.0)
                speed_by_type.setdefault(t, []).append(sp)
                radius_by_type.setdefault(t, []).append(round(float(pr.get("radius") or 0), 2))
                if sp < 1e-9:
                    zero_vel[t] += 1
                if "rotating" in t:
                    n_rot += 1
            per_capture_rotating.append(n_rot)


def q(v, f):
    v = sorted(v)
    return v[min(len(v) - 1, max(0, int(f * (len(v) - 1))))] if v else float("nan")


print(f"wave-20 captures: {len(per_capture_rotating)}")
print(f"capture_schema_hash values seen: {dict(schema_hashes) if len(schema_hashes)!=1 else list(schema_hashes)[0]}")
print()
print(f"{'type_id':<36}{'n':>8}{'zeroV':>7}{'|v| p05':>9}{'|v| p50':>9}{'|v| p95':>9}  radii")
for t, n in by_type.most_common():
    v = speed_by_type[t]
    r = Counter(radius_by_type[t])
    print(f"{t:<36}{n:>8}{zero_vel.get(t,0):>7}{q(v,.05):>9.1f}{q(v,.50):>9.1f}{q(v,.95):>9.1f}  "
          f"{dict(r.most_common(3))}")

rot = sum(n for t, n in by_type.items() if "rotating" in t)
print()
print("=" * 78)
if rot == 0:
    print("GATE FAILED: zero rotating projectiles in the capture stream.")
    print("The arm did NOT take effect. Do not spend trials on this build.")
    sys.exit(1)
present = sum(1 for n in per_capture_rotating if n > 0)
print(f"GATE PASSED: {rot} rotating-projectile observations "
      f"(control arm: 0 in 426,116).")
print(f"  captures containing >=1: {present}/{len(per_capture_rotating)} = "
      f"{present/len(per_capture_rotating):.1%}")
print(f"  count per capture when present: p05={q([n for n in per_capture_rotating if n],.05)} "
      f"p50={q([n for n in per_capture_rotating if n],.5)} "
      f"max={max(per_capture_rotating)}")
zv = sum(v for t, v in zero_vel.items() if "rotating" in t)
print()
print(f"  rotating observations with ZERO derived velocity: {zv}/{rot} = {zv/rot:.1%}")
print("  (a high share means the finite-difference velocity is NOT working --")
print("   the node's own `velocity` property reads 0, so zeros mean we gained")
print("   position but not motion)")
