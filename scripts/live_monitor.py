#!/usr/bin/env python3
"""Continuously write a compact live WP1 status snapshot.

This process is deliberately read-only with respect to Brotato.  It can run
beside an active gate without changing the candidate under evaluation.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from trainer.evaluation.live_monitor import (
    build_run_snapshot,
    newest_events_path,
    read_events,
    render_markdown,
    timestamp_now,
)


def read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def game_running() -> bool:
    try:
        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq Brotato.exe"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return False
    return "Brotato.exe" in (result.stdout or "")


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False, newline=""
    ) as stream:
        stream.write(content)
        temp_path = Path(stream.name)
    temp_path.replace(path)


def collect_snapshot(runs_dir: Path, hud_path: Path) -> dict:
    events_path = newest_events_path(runs_dir)
    if events_path is None:
        run = {"active": False, "event_count": 0, "alerts": ["no run telemetry found"]}
    else:
        events, warnings = read_events(events_path)
        age = max(0.0, time.time() - events_path.stat().st_mtime)
        run = build_run_snapshot(events, telemetry_age_sec=round(age, 1), parse_warnings=warnings)
        run["events_path"] = str(events_path)
    return {
        "schema_version": "1.0.0",
        "updated_at": timestamp_now(),
        "game_running": game_running(),
        "hud": read_json(hud_path),
        "run": run,
    }


def main() -> int:
    root = ROOT
    default_runs = Path(os.environ["APPDATA"]) / "Brotato" / "brotato_agent" / "runs"
    default_hud = Path(os.environ["APPDATA"]) / "Brotato" / "brotato_agent" / "batch_hud.json"
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs-dir", type=Path, default=default_runs)
    parser.add_argument("--hud", type=Path, default=default_hud)
    parser.add_argument("--json-out", type=Path, default=root / "reports" / "live_monitor.json")
    parser.add_argument("--markdown-out", type=Path, default=root / "reports" / "live_monitor.md")
    parser.add_argument("--interval", type=float, default=5.0)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()

    while True:
        snapshot = collect_snapshot(args.runs_dir, args.hud)
        atomic_write(args.json_out, json.dumps(snapshot, indent=2) + "\n")
        atomic_write(args.markdown_out, render_markdown(snapshot))
        run = snapshot["run"]
        print(
            f"{snapshot['updated_at']} game={snapshot['game_running']} "
            f"run={run.get('run_id', 'none')} wave={run.get('wave', 0)} "
            f"hp={run.get('hp', '?')} status={run.get('severity', 'unknown')}",
            flush=True,
        )
        if args.once:
            return 0
        time.sleep(max(1.0, args.interval))


if __name__ == "__main__":
    raise SystemExit(main())
