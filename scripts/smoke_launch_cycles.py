#!/usr/bin/env python3
"""WP1 smoke: launch / load mod / exit cycles."""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path


def _kill_game() -> None:
    subprocess.call(
        ["taskkill", "/IM", "Brotato.exe", "/F"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _wait_mod_ready(log: Path, timeout: float) -> bool:
    deadline = time.time() + timeout
    needle = "Tom:BrotatoAgent:Runner: AgentController ready"
    while time.time() < deadline:
        if log.exists():
            try:
                text = log.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                text = ""
            if needle in text:
                return True
        time.sleep(1.0)
    return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cycles", type=int, default=5)
    ap.add_argument("--ready-timeout", type=int, default=90)
    args = ap.parse_args()

    root = Path(__file__).resolve().parents[1]
    log = Path.home() / "AppData" / "Roaming" / "Brotato" / "logs" / "modloader.log"
    ok = 0
    for i in range(1, args.cycles + 1):
        print(f"=== smoke cycle {i}/{args.cycles} ===")
        _kill_game()
        time.sleep(2)
        # Clear latch + ensure deploy is current on first cycle only if needed
        if i == 1:
            subprocess.check_call(
                [sys.executable, str(root / "scripts" / "deploy_mod.py"), "--target", "agent", "--close-game"]
            )
        else:
            # Clear mods-disabled latch between launches
            subprocess.check_call(
                [sys.executable, str(root / "scripts" / "deploy_mod.py"), "--target", "agent", "--close-game"]
            )
        time.sleep(1)
        if log.exists():
            log.write_text("", encoding="utf-8")
        subprocess.check_call([sys.executable, str(root / "scripts" / "launch_benchmark.py")])
        ready = _wait_mod_ready(log, args.ready_timeout)
        print(f"  mod_ready={ready}")
        _kill_game()
        time.sleep(2)
        if ready:
            ok += 1
        else:
            print("  FAIL: AgentController ready not seen in modloader.log")
    print(f"Smoke result: {ok}/{args.cycles}")
    return 0 if ok == args.cycles else 1


if __name__ == "__main__":
    raise SystemExit(main())
