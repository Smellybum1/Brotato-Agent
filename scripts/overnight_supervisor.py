#!/usr/bin/env python3
"""Overnight unattended supervisor for WP1 D0 batches.

More aggressive than run_batch.py:
- Relaunches if the game dies
- Restarts if telemetry stalls (no event growth)
- Restarts if a summary appears but no new run starts within a grace window
- Collects N new summaries and writes a report
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
    out: dict[str, Path] = {}
    if not src.exists():
        return out
    for p in src.glob("*/summary.json"):
        out[p.parent.name] = p
    return out


def save_gate_state(path: Path, baseline: set[str], collected: list[dict]) -> None:
    """Persist enough evidence to resume the same gate after a watchdog relaunch."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "baseline_run_ids": sorted(baseline),
        "collected_run_ids": [str(row.get("run_id", "")) for row in collected],
    }
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary.replace(path)


def load_gate_state(path: Path, summaries: dict[str, Path]) -> tuple[set[str], list[dict]] | None:
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise RuntimeError(f"Unsupported gate state schema in {path}")
    baseline = {str(run_id) for run_id in payload.get("baseline_run_ids", [])}
    collected: list[dict] = []
    for run_id in payload.get("collected_run_ids", []):
        run_id = str(run_id)
        summary_path = summaries.get(run_id)
        if summary_path is None:
            raise RuntimeError(f"Gate state references missing summary: {run_id}")
        collected.append(json.loads(summary_path.read_text(encoding="utf-8")))
    return baseline, collected


def newest_events(src: Path) -> tuple[Path | None, int, float]:
    """Return (events_path, line_count, mtime)."""
    best = None
    best_mtime = -1.0
    if not src.exists():
        return None, 0, -1.0
    for p in src.glob("*/events.jsonl"):
        try:
            m = p.stat().st_mtime
        except OSError:
            continue
        if m > best_mtime:
            best_mtime = m
            best = p
    if best is None:
        return None, 0, -1.0
    try:
        n = sum(1 for _ in best.open("r", encoding="utf-8") if _.strip())
    except OSError:
        n = 0
    return best, n, best_mtime


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
    time.sleep(2)


def deploy_and_launch(root: Path, deploy: bool = True) -> None:
    """Relaunch the game, optionally redeploying the mod first.

    `deploy=False` is for campaigns that freeze the installed build: deploy_mod.py
    rewrites agent_config.json from a hardcoded dict (danger 0, and no
    movement_estop_enabled key at all), so redeploying mid-campaign silently
    changes the arm as well as the build.
    """
    kill_game()
    if deploy:
        subprocess.check_call(
            [sys.executable, str(root / "scripts" / "deploy_mod.py"), "--target", "agent", "--close-game"]
        )
        time.sleep(2)
    subprocess.check_call([sys.executable, str(root / "scripts" / "launch_benchmark.py")])
    time.sleep(15)


def write_report(root: Path, prefix: str, collected: list[dict], min_wins: int) -> int:
    wins = sum(1 for r in collected if str(r.get("result", "")).lower() == "victory")
    n = len(collected)
    lo, hi = wilson_interval(wins, n)
    reports = root / "reports"
    reports.mkdir(exist_ok=True)
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
        f"# Overnight Batch ({prefix})",
        "",
        f"- Runs: {n}",
        f"- Victories: {wins}",
        f"- Win rate: {wins / n if n else 0:.3f} (Wilson 95% CI {lo:.3f}–{hi:.3f})",
        f"- Min wins gate: {min_wins}",
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
    return 0 if n >= min_wins and wins >= min_wins or (n == len(collected) and wins >= min_wins) else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=20)
    ap.add_argument("--min-wins", type=int, default=18)
    ap.add_argument("--stall-sec", type=int, default=180, help="No event growth => restart")
    ap.add_argument("--rearm-sec", type=int, default=120, help="Summary but no new run => restart")
    ap.add_argument("--run-timeout-sec", type=int, default=2700)
    ap.add_argument("--report-prefix", default="batch_overnight")
    ap.add_argument("--state-file", type=Path)
    ap.add_argument("--redeploy", action="store_true")
    ap.add_argument(
        "--no-deploy",
        action="store_true",
        help="Never run deploy_mod.py; relaunch only. Required for campaigns that "
        "freeze the installed build, since deploying rewrites agent_config.json "
        "(danger -> 0, movement_estop_enabled dropped).",
    )
    ap.add_argument(
        "--stop-on-win",
        action="store_true",
        help="Stop as soon as one run is a victory. For acquisition tasks where the "
        "reward is granted by the first win and further runs only cost time and "
        "drift the unlock pool.",
    )
    args = ap.parse_args()
    if args.redeploy and args.no_deploy:
        ap.error("--redeploy and --no-deploy are mutually exclusive")

    root = Path(__file__).resolve().parents[1]

    def relaunch() -> None:
        deploy_and_launch(root, deploy=not args.no_deploy)

    src = Path(os.environ["APPDATA"]) / "Brotato" / "brotato_agent" / "runs"
    current_summaries = list_summaries(src)
    resumed = False
    if args.state_file:
        restored = load_gate_state(args.state_file, current_summaries)
    else:
        restored = None
    if restored is None:
        before = current_summaries
        baseline_ids = set(before)
        collected: list[dict] = []
        if args.state_file:
            save_gate_state(args.state_file, baseline_ids, collected)
    else:
        baseline_ids, collected = restored
        before = {run_id: current_summaries[run_id] for run_id in baseline_ids if run_id in current_summaries}
        resumed = True
        print(
            f"Resumed gate state from {args.state_file} ({len(collected)}/{args.runs} summaries)",
            flush=True,
        )

    restored_wins = sum(
        1 for row in collected if str(row.get("result", "")).lower() == "victory"
    )
    restored_losses = len(collected) - restored_wins
    if restored_losses > args.runs - args.min_wins:
        print(
            f"GATE IMPOSSIBLE remains recorded after resume: "
            f"{restored_wins}W / {restored_losses}L",
            flush=True,
        )
        write_report(root, args.report_prefix, collected, args.min_wins)
        return 2

    if (args.redeploy and not resumed) or not game_running():
        print("Launch..." if args.no_deploy else "Deploy + launch...", flush=True)
        relaunch()

    # Fresh overlay counter for this overnight gate attempt.
    hud = Path(os.environ["APPDATA"]) / "Brotato" / "brotato_agent" / "batch_hud.json"
    try:
        hud.parent.mkdir(parents=True, exist_ok=True)
        if not resumed:
            hud.write_text(
                json.dumps({"wins": 0, "runs": 0, "policy_version": "overnight_reset"}, indent=0),
                encoding="utf-8",
            )
            print(f"Reset batch HUD overlay at {hud}", flush=True)
    except OSError as exc:
        print(f"WARN: could not reset batch HUD: {exc}", flush=True)

    last_event_count = -1
    last_event_path: Path | None = None
    last_progress = time.time()
    last_summary_at: float | None = None
    run_started_after_summary = True

    print(f"Overnight supervisor targeting {args.runs} new summaries", flush=True)
    won_and_stopping = False
    while len(collected) < args.runs and not won_and_stopping:
        # Collect new summaries
        now_sums = list_summaries(src)
        for rid, path in now_sums.items():
            if rid in before:
                continue
            if any(c.get("run_id") == rid for c in collected):
                continue
            data = json.loads(path.read_text(encoding="utf-8"))
            collected.append(data)
            if args.state_file:
                save_gate_state(args.state_file, baseline_ids, collected)
            last_progress = time.time()
            last_summary_at = time.time()
            run_started_after_summary = False
            print(
                f"[{len(collected)}/{args.runs}] {rid} -> {data.get('result')} "
                f"wave={data.get('last_wave')} fail={data.get('failure_category', '')}",
                flush=True,
            )
            if args.stop_on_win and str(data.get("result", "")).lower() == "victory":
                # The reward is granted by the first win; further runs only cost
                # time and drift the unlock pool, which every later run samples from.
                print(f"STOP ON WIN: {rid} was a victory after {len(collected)} runs", flush=True)
                won_and_stopping = True
                break
            # Early abort: too many losses to hit min_wins in remaining runs.
            # e.g. 20 runs / 18 wins → max 2 losses; 3rd loss makes gate impossible.
            wins_so_far = sum(
                1 for r in collected if str(r.get("result", "")).lower() == "victory"
            )
            losses_so_far = len(collected) - wins_so_far
            max_losses = args.runs - args.min_wins
            print(
                f"  record {wins_so_far}W / {losses_so_far}L "
                f"(max losses for gate: {max_losses})",
                flush=True,
            )
            if losses_so_far > max_losses:
                print(
                    f"GATE IMPOSSIBLE: {losses_so_far} losses > {max_losses} allowed; "
                    f"shutting down overnight batch",
                    flush=True,
                )
                kill_game()
                write_report(root, args.report_prefix, collected, args.min_wins)
                abort_note = root / "reports" / f"{args.report_prefix}_aborted.md"
                abort_note.write_text(
                    f"# Overnight aborted ({args.report_prefix})\n\n"
                    f"- Reason: gate impossible ({losses_so_far} losses, "
                    f"need ≥{args.min_wins}/{args.runs})\n"
                    f"- Record: {wins_so_far}W / {losses_so_far}L "
                    f"after {len(collected)} runs\n",
                    encoding="utf-8",
                )
                print(f"Wrote {abort_note}", flush=True)
                return 2

        # Detect new run folder (re-arm success)
        ev_path, ev_n, _mtime = newest_events(src)
        if ev_path is not None:
            rid = ev_path.parent.name
            if rid not in before and not any(c.get("run_id") == rid for c in collected):
                # Live run in progress
                if not run_started_after_summary:
                    run_started_after_summary = True
                    print(f"  re-armed live run {rid} (events={ev_n})", flush=True)
                if ev_path != last_event_path:
                    last_event_path = ev_path
                    last_event_count = ev_n
                    last_progress = time.time()
                elif ev_n > last_event_count:
                    last_event_count = ev_n
                    last_progress = time.time()

        if not game_running():
            print("Game exited; redeploy+launch", flush=True)
            relaunch()
            last_progress = time.time()
            continue

        # After a summary, if no new run starts, force restart
        if last_summary_at is not None and not run_started_after_summary:
            if time.time() - last_summary_at > args.rearm_sec:
                print(f"No re-arm within {args.rearm_sec}s; restarting", flush=True)
                relaunch()
                last_summary_at = time.time()
                last_progress = time.time()
                continue

        # Stall: events not growing, OR death-stuck (hp=0 combat ticks with no summary)
        dead_stuck = False
        if ev_path is not None and ev_path.exists():
            try:
                lines = ev_path.read_text(encoding="utf-8").splitlines()
                if lines:
                    last = json.loads(lines[-1])
                    if last.get("event") == "combat_tick":
                        hp = last.get("payload", {}).get("hp")
                        if hp == 0 and (time.time() - last_progress > 45):
                            dead_stuck = True
            except (OSError, json.JSONDecodeError, TypeError):
                pass
        if dead_stuck:
            print("Death screen stuck (hp=0); restarting", flush=True)
            relaunch()
            last_progress = time.time()
            last_summary_at = time.time()
            run_started_after_summary = False
            continue

        if time.time() - last_progress > args.stall_sec:
            print(f"Telemetry stall {args.stall_sec}s; restarting", flush=True)
            relaunch()
            last_progress = time.time()
            last_summary_at = time.time()
            run_started_after_summary = False
            continue

        # Hard per-run timeout from last progress
        if time.time() - last_progress > args.run_timeout_sec:
            print(f"Run timeout {args.run_timeout_sec}s; restarting", flush=True)
            relaunch()
            last_progress = time.time()
            continue

        time.sleep(10)

    # Validate + report
    subprocess.call([sys.executable, str(root / "scripts" / "collect_results.py")])
    subprocess.call([sys.executable, str(root / "scripts" / "validate_telemetry.py")])
    code = write_report(root, args.report_prefix, collected, args.min_wins)
    wins = sum(1 for r in collected if str(r.get("result", "")).lower() == "victory")
    print(f"DONE runs={len(collected)} wins={wins} gate={args.min_wins} exit={code}", flush=True)
    return 0 if wins >= args.min_wins and len(collected) >= args.runs else 1


if __name__ == "__main__":
    raise SystemExit(main())
