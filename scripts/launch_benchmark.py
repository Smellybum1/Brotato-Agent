#!/usr/bin/env python3
"""Launch Brotato via Steam or direct exe for benchmark runs."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path


APP_ID = "1942280"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--via", choices=["steam", "exe"], default="steam")
    ap.add_argument("--wait-secs", type=int, default=0)
    args = ap.parse_args()
    root = Path(__file__).resolve().parents[1]
    report = root / "reports" / "discover_install.json"
    if not report.exists():
        subprocess.check_call([sys.executable, str(root / "scripts" / "discover_install.py")])
    data = json.loads(report.read_text(encoding="utf-8"))
    install = Path(data["brotato_install"])
    steam = Path(r"C:\Games\Steam\steam.exe")
    if args.via == "steam" and steam.exists():
        subprocess.Popen([str(steam), "-applaunch", APP_ID])
        print(f"Launched via Steam appid {APP_ID}")
    else:
        exe = install / "Brotato.exe"
        subprocess.Popen([str(exe)], cwd=str(install))
        print(f"Launched {exe}")
    if args.wait_secs > 0:
        time.sleep(args.wait_secs)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
