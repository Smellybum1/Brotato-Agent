#!/usr/bin/env python3
"""Collect run summaries/events from Godot user:// into repo runs/."""
from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    root = Path(__file__).resolve().parents[1]
    out = args.out or (root / "runs")
    src = Path(os.environ["APPDATA"]) / "Brotato" / "brotato_agent" / "runs"
    if not src.exists():
        print(f"No telemetry yet at {src}")
        return 0
    out.mkdir(parents=True, exist_ok=True)
    summaries = out / "summaries"
    summaries.mkdir(exist_ok=True)
    copied = 0
    for run_dir in src.iterdir():
        if not run_dir.is_dir():
            continue
        dest = out / run_dir.name
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(run_dir, dest)
        summary = run_dir / "summary.json"
        if summary.exists():
            shutil.copy2(summary, summaries / f"{run_dir.name}.json")
        copied += 1
    print(f"Collected {copied} runs into {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
