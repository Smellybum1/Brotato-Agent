#!/usr/bin/env python3
"""Collect run summaries from Godot user:// into repo runs/summaries/.

The per-run events mirror under runs/<run_id>/ is OFF by default (--mirror-events
restores it). %APPDATA%\\Brotato\\brotato_agent\\runs is the authoritative archive;
the mirror was written by this script and read by nothing (validate_telemetry and
every analysis take --runs-dir pointing at APPDATA). Because the copy loop below is
unconditional rmtree+copytree over EVERY run, mirroring cost a full re-copy of the
entire archive on every call -- 112 GB as of 2026-08-01, once per campaign block.
The mirror is reconstructible at any time with --mirror-events.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--mirror-events", action="store_true",
                    help="Also mirror each run's full directory (events.jsonl) into out/. "
                         "Off by default: see the module docstring.")
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
    mirrored = 0
    for run_dir in src.iterdir():
        if not run_dir.is_dir():
            continue
        summary = run_dir / "summary.json"
        if summary.exists():
            shutil.copy2(summary, summaries / f"{run_dir.name}.json")
            copied += 1
        if args.mirror_events:
            dest = out / run_dir.name
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(run_dir, dest)
            mirrored += 1
    if args.mirror_events:
        print(f"Collected {copied} summaries into {summaries} "
              f"and mirrored {mirrored} full run dirs into {out}")
    else:
        print(f"Collected {copied} summaries into {summaries} "
              f"(events mirror off; {src} is authoritative)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
