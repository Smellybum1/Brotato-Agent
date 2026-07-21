#!/usr/bin/env python3
"""Bootstrap local Python env and verify discovery."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    venv = root / ".venv"
    if not venv.exists():
        subprocess.check_call([sys.executable, "-m", "venv", str(venv)])
    py = venv / "Scripts" / "python.exe"
    if not py.exists():
        py = venv / "bin" / "python"
    subprocess.check_call([str(py), "-m", "pip", "install", "-U", "pip"])
    subprocess.check_call([str(py), "-m", "pip", "install", "-e", str(root)])
    subprocess.check_call([str(py), str(root / "scripts" / "discover_install.py")])
    print("Bootstrap complete. Activate .venv and use scripts/deploy_mod.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
