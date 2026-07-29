"""Paired STUDENT vs CONTROL confinement screen driver.

Pre-registered in ``reports/wp2/student_bd_confinement_prereg.md``.

Runs one trial at a time, alternating arms, so drift over the campaign cannot
align with the arm. The only difference between arms is ``student_enabled`` in
``agent_config.json``; the build, flags and fixture are identical.

Three rules this driver enforces because past campaigns died on them:

* **Every step that ARMS a trial is verified by READBACK**, not by its own exit
  code. ``student_enabled`` is written, re-read from disk, and the trial is
  skipped on mismatch. For the student arm the sidecar port is probed too --
  a dead sidecar produces a run that looks perfectly healthy and silently
  measures the teacher.
* **Abort on a dead experiment.** Consecutive invalid trials stop the campaign
  instead of burning the night logging "no valid trials".
* **Never deploy.** The installed build must not move for the campaign's
  duration; this driver only toggles a config key.
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = Path(os.environ["APPDATA"]) / "Brotato" / "brotato_agent" / "agent_config.json"
MAX_CONSECUTIVE_INVALID = 3


def set_student(enabled: bool, port: int) -> bool:
    """Write student_enabled and PROVE it from disk. Returns False on mismatch."""
    try:
        cfg = json.loads(CONFIG.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"  !! cannot read agent_config.json: {exc}")
        return False
    cfg["student_enabled"] = bool(enabled)
    cfg["student_port"] = int(port)
    CONFIG.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    try:
        back = json.loads(CONFIG.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"  !! readback failed: {exc}")
        return False
    if bool(back.get("student_enabled")) is not bool(enabled):
        print(f"  !! READBACK MISMATCH: wanted {enabled}, disk says {back.get('student_enabled')}")
        return False
    return True


def sidecar_alive(port: int) -> bool:
    """A listening socket on the sidecar port. Cheap, and the alternative is a
    student arm that silently ran the teacher."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(2.0)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def run_trial(fixture: Path, label: str, out: Path, target_wave: int,
              timeout_sec: int, stale_sec: int) -> int:
    cmd = [
        sys.executable, str(ROOT / "scripts" / "wp2_finale_loop.py"),
        "--fixture", str(fixture),
        "--target-wave", str(target_wave),
        "--trials", "1",
        "--label", label,
        "--out", str(out),
        "--timeout-sec", str(timeout_sec),
        "--stale-sec", str(stale_sec),
    ]
    return subprocess.run(cmd, cwd=str(ROOT)).returncode


def tail_valid(out: Path) -> tuple[bool, str]:
    try:
        lines = [ln for ln in out.read_text(encoding="utf-8").splitlines() if ln.strip()]
    except OSError:
        return False, "no trials file"
    if not lines:
        return False, "empty trials file"
    try:
        rec = json.loads(lines[-1])
    except json.JSONDecodeError:
        return False, "unparseable last row"
    return bool(rec.get("valid")), str(rec.get("invalid_reason") or "")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixture-a", required=True)
    ap.add_argument("--fixture-b", default=None)
    ap.add_argument("--n-a", type=int, default=10, help="trials PER ARM on fixture A")
    ap.add_argument("--n-b", type=int, default=6, help="trials PER ARM on fixture B")
    ap.add_argument("--out", required=True)
    ap.add_argument("--port", type=int, default=51888)
    ap.add_argument("--target-wave", type=int, default=17)
    ap.add_argument("--timeout-sec", type=int, default=900)
    ap.add_argument("--stale-sec", type=int, default=300)
    args = ap.parse_args()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    plan: list[tuple[str, Path, str]] = []
    for arm_pairs, fixture_arg, tag in (
        (args.n_a, args.fixture_a, "A"),
        (args.n_b, args.fixture_b, "B"),
    ):
        if not fixture_arg or arm_pairs <= 0:
            continue
        fixture = Path(fixture_arg)
        if not fixture.is_file():
            print(f"!! fixture missing: {fixture}")
            return 2
        for i in range(arm_pairs):
            # Interleave within each pair; flip which arm leads on odd pairs so
            # the arm order itself is not confounded with time.
            arms = ("student", "control") if i % 2 == 0 else ("control", "student")
            for arm in arms:
                plan.append((arm, fixture, tag))

    print(f"planned trials: {len(plan)}  "
          f"(student {sum(1 for a, _, _ in plan if a == 'student')}, "
          f"control {sum(1 for a, _, _ in plan if a == 'control')})")
    print(f"out: {out}\n")

    consecutive_invalid = 0
    done = 0
    started = time.time()

    for idx, (arm, fixture, tag) in enumerate(plan, 1):
        elapsed = (time.time() - started) / 60.0
        print(f"[{idx}/{len(plan)}] arm={arm} fixture={tag} "
              f"({elapsed:.0f} min elapsed)", flush=True)

        if not set_student(arm == "student", args.port):
            print("  !! arming readback failed -- ABORT")
            return 3
        if arm == "student" and not sidecar_alive(args.port):
            print(f"  !! sidecar not listening on {args.port} -- ABORT "
                  "(a student arm without a sidecar silently measures the teacher)")
            return 4

        label = f"{arm}_bd_{tag}"
        rc = run_trial(fixture, label, out, args.target_wave,
                       args.timeout_sec, args.stale_sec)
        valid, reason = tail_valid(out)
        print(f"  rc={rc} valid={valid} {reason}", flush=True)

        if valid:
            consecutive_invalid = 0
            done += 1
        else:
            consecutive_invalid += 1
            if consecutive_invalid >= MAX_CONSECUTIVE_INVALID:
                print(f"\n!! {consecutive_invalid} consecutive invalid trials -- ABORT. "
                      "The experiment is dead, not unlucky.")
                return 5

    # Leave the machine disarmed.
    set_student(False, args.port)
    print(f"\ncampaign complete: {done}/{len(plan)} valid, "
          f"{(time.time() - started) / 60.0:.0f} min")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
