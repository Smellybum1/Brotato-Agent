#!/usr/bin/env python3
"""Batch runner: launch successive runs, collect, and write CSV/Markdown report.

For WP1 the in-game agent auto-starts configured runs. This harness waits for
new summary files, relaunches the game if it exits, and restarts if a run stalls.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path


def wilson_interval(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = successes / n
    denom = 1 + z * z / n
    centre = p + z * z / (2 * n)
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((centre - margin) / denom, (centre + margin) / denom)


def list_summaries(src: Path) -> dict[str, Path]:
    out = {}
    if not src.exists():
        return out
    for p in src.glob("*/summary.json"):
        out[p.parent.name] = p
    return out


def game_running() -> bool:
    try:
        r = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq Brotato.exe"],
            capture_output=True,
            text=True,
            check=False,
        )
        return "Brotato.exe" in (r.stdout or "")
    except OSError:
        return False


def kill_game() -> None:
    subprocess.call(
        ["taskkill", "/IM", "Brotato.exe", "/F"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def launch_game(root: Path) -> None:
    subprocess.check_call([sys.executable, str(root / "scripts" / "launch_benchmark.py")])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=20)
    ap.add_argument("--timeout-per-run-sec", type=int, default=2400)
    ap.add_argument("--poll-sec", type=int, default=15)
    ap.add_argument("--launch", action="store_true", help="Launch game at start")
    ap.add_argument("--report-prefix", default="batch_wp1", help="reports/<prefix>.csv|.md")
    ap.add_argument("--min-wins", type=int, default=None, help="Pass threshold (default ceil(0.9*runs))")
    args = ap.parse_args()

    root = Path(__file__).resolve().parents[1]
    src = Path(os.environ["APPDATA"]) / "Brotato" / "brotato_agent" / "runs"
    before = list_summaries(src)

    if args.launch:
        if game_running():
            kill_game()
            time.sleep(2)
        launch_game(root)

    print(f"Waiting for {args.runs} new run summaries under {src}", flush=True)
    collected: list[dict] = []
    last_progress = time.time()
    while len(collected) < args.runs:
        now = list_summaries(src)
        new_found = False
        for rid, path in now.items():
            if rid in before:
                continue
            if any(c.get("run_id") == rid for c in collected):
                continue
            data = json.loads(path.read_text(encoding="utf-8"))
            collected.append(data)
            new_found = True
            last_progress = time.time()
            print(
                f"[{len(collected)}/{args.runs}] {rid} -> {data.get('result')} "
                f"wave={data.get('last_wave')}",
                flush=True,
            )
            if len(collected) >= args.runs:
                break
        if new_found:
            continue
        if not game_running():
            print("Game not running; relaunching...", flush=True)
            launch_game(root)
            last_progress = time.time()
            time.sleep(20)
            continue
        if time.time() - last_progress > args.timeout_per_run_sec:
            print(
                f"No new summary for {args.timeout_per_run_sec}s; restarting game...",
                flush=True,
            )
            kill_game()
            time.sleep(3)
            launch_game(root)
            last_progress = time.time()
            time.sleep(20)
            continue
        time.sleep(args.poll_sec)

    subprocess.call([sys.executable, str(root / "scripts" / "collect_results.py")])
    subprocess.call([sys.executable, str(root / "scripts" / "validate_telemetry.py")])

    wins = sum(1 for r in collected if str(r.get("result", "")).lower() == "victory")
    n = len(collected)
    lo, hi = wilson_interval(wins, n)
    hangs = sum(1 for r in collected if r.get("hangs", 0))
    illegal = sum(1 for r in collected if r.get("illegal_actions", 0))
    complete = sum(1 for r in collected if r.get("telemetry_complete"))

    reports = root / "reports"
    reports.mkdir(exist_ok=True)
    prefix = args.report_prefix
    csv_path = reports / f"{prefix}.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "run_id",
                "result",
                "last_wave",
                "duration_ms",
                "recoveries",
                "errors",
                "hangs",
                "failure_category",
            ],
        )
        w.writeheader()
        for r in collected:
            w.writerow(
                {
                    "run_id": r.get("run_id"),
                    "result": r.get("result"),
                    "last_wave": r.get("last_wave"),
                    "duration_ms": r.get("duration_ms"),
                    "recoveries": r.get("recoveries", 0),
                    "errors": r.get("errors", 0),
                    "hangs": r.get("hangs", 0),
                    "failure_category": r.get("failure_category", ""),
                }
            )

    md = reports / f"{prefix}.md"
    lines = [
        f"# WP1 Batch Report ({prefix})",
        "",
        f"- Runs: {n}",
        f"- Victories: {wins}",
        f"- Win rate: {wins / n if n else 0:.3f} (Wilson 95% CI {lo:.3f}–{hi:.3f})",
        f"- Hangs: {hangs}",
        f"- Illegal actions: {illegal}",
        f"- Telemetry complete: {complete}/{n}",
        "",
        "| run_id | result | last_wave | duration_ms | recoveries | failure |",
        "|---|---|---:|---:|---:|---|",
    ]
    for r in collected:
        lines.append(
            f"| {r.get('run_id')} | {r.get('result')} | {r.get('last_wave')} | "
            f"{r.get('duration_ms')} | {r.get('recoveries', 0)} | {r.get('failure_category', '')} |"
        )
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {csv_path} and {md}", flush=True)
    min_wins = args.min_wins if args.min_wins is not None else max(1, int(math.ceil(0.9 * args.runs)))
    return 0 if n == args.runs and wins >= min_wins else 1


if __name__ == "__main__":
    raise SystemExit(main())
