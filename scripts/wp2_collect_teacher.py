#!/usr/bin/env python3
"""Collect a bounded set of complete WP2 teacher-capture runs.

The collector never edits source, never retries a failed/stale run, and always
stops Brotato plus restores auto-start off before exit. Defeats are valid
demonstration evidence; telemetry/safety faults are not.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any


CAPTURE_SCHEMA_HASH = "95B6444796A21FD44E94113B75BA2097BC381D5F72ED784F9B9A4A99DD46D951"
POLICY_VERSION = "teacher_v1-0.1.113-gun-wp1"
MOD_VERSION = "0.2.21-wp2-capture"
ATOMIC_REPLACE_ATTEMPTS = 10
ATOMIC_REPLACE_BASE_DELAY_SEC = 0.02
SUMMARY_READ_TIMEOUT_SEC = 2.0
SUMMARY_READ_POLL_SEC = 0.02


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    for attempt in range(ATOMIC_REPLACE_ATTEMPTS):
        try:
            temporary.replace(path)
            return
        except PermissionError:
            if attempt + 1 == ATOMIC_REPLACE_ATTEMPTS:
                raise
            delay = min(ATOMIC_REPLACE_BASE_DELAY_SEC * (2**attempt), 0.2)
            time.sleep(delay)


def list_summaries(runs_dir: Path) -> dict[str, Path]:
    return {path.parent.name: path for path in runs_dir.glob("*/summary.json")}


def read_json_when_ready(
    path: Path,
    timeout_sec: float = SUMMARY_READ_TIMEOUT_SEC,
    poll_sec: float = SUMMARY_READ_POLL_SEC,
) -> dict[str, Any]:
    """Read a summary after the producer has finished its non-atomic write."""
    deadline = time.monotonic() + timeout_sec
    last_error: json.JSONDecodeError | None = None
    while True:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise TypeError(f"expected JSON object in {path}")
            return payload
        except json.JSONDecodeError as exc:
            last_error = exc
        except FileNotFoundError:
            pass
        if time.monotonic() >= deadline:
            if last_error is not None:
                raise last_error
            raise FileNotFoundError(path)
        time.sleep(poll_sec)


def newest_run(runs_dir: Path, excluded: set[str]) -> Path | None:
    candidates = [
        path
        for path in runs_dir.iterdir()
        if path.is_dir() and path.name not in excluded and (path / "events.jsonl").exists()
    ] if runs_dir.exists() else []
    return max(candidates, key=lambda path: (path / "events.jsonl").stat().st_mtime, default=None)


def tail_lines(path: Path, count: int = 64, max_bytes: int = 2_000_000) -> list[str]:
    if not path.exists():
        return []
    size = path.stat().st_size
    read_size = min(size, max_bytes)
    with path.open("rb") as handle:
        handle.seek(size - read_size)
        data = handle.read(read_size)
    lines = data.decode("utf-8", errors="replace").splitlines()
    return lines[-count:]


def latest_capture(lines: list[str]) -> dict[str, Any] | None:
    for line in reversed(lines):
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("event") == "combat_capture":
            return event
    return None


def game_running() -> bool:
    result = subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq Brotato.exe"],
        capture_output=True,
        text=True,
        check=False,
    )
    return "Brotato.exe" in (result.stdout or "")


def stop_game() -> None:
    subprocess.run(
        ["powershell", "-NoProfile", "-Command", "Get-Process Brotato -ErrorAction SilentlyContinue | Stop-Process -Force"],
        capture_output=True,
        check=False,
    )


def set_auto_start(enabled: bool) -> None:
    path = Path(os.environ["APPDATA"]) / "Brotato" / "brotato_agent" / "agent_config.json"
    payload = {
        "auto_start": enabled,
        "character": "character_well_rounded",
        "danger": 0,
        "weapon_prefixes": ["weapon_smg", "weapon_stick"],
    }
    atomic_json(path, payload)


def launch_game(root: Path) -> None:
    # Use the proven Steam route so ModLoader can enumerate subscribed ZIPs.
    # Direct EXE launches may restart through Steam without an initialized UGC
    # interface, leaving the capture mod unloaded even though the ZIP is valid.
    subprocess.check_call([sys.executable, str(root / "scripts" / "launch_benchmark.py")])


def summary_fault(summary: dict[str, Any]) -> str | None:
    if summary.get("policy_version") != POLICY_VERSION:
        return f"policy mismatch: {summary.get('policy_version')}"
    if summary.get("mod_version") != MOD_VERSION:
        return f"mod mismatch: {summary.get('mod_version')}"
    if not summary.get("telemetry_complete", False):
        return "telemetry_complete is false"
    for field in ("errors", "hangs", "illegal_actions"):
        if int(summary.get(field, 0)) != 0:
            return f"{field}={summary.get(field)}"
    if str(summary.get("result", "")).lower() not in {"victory", "defeat"}:
        return f"unexpected result: {summary.get('result')}"
    return None


def write_state(path: Path, state: dict[str, Any], **updates: Any) -> None:
    state.update(updates)
    state["updated_at"] = utc_now()
    atomic_json(path, state)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, required=True)
    parser.add_argument("--state-file", type=Path, required=True)
    parser.add_argument("--report-file", type=Path, required=True)
    parser.add_argument("--stale-sec", type=float, default=45.0)
    parser.add_argument("--poll-sec", type=float, default=0.5)
    parser.add_argument("--launch", action="store_true")
    args = parser.parse_args()
    if args.runs < 1:
        raise SystemExit("--runs must be positive")
    root = Path(__file__).resolve().parents[1]
    runs_dir = Path(os.environ["APPDATA"]) / "Brotato" / "brotato_agent" / "runs"
    baseline = {path.name for path in runs_dir.iterdir() if path.is_dir()} if runs_dir.exists() else set()
    collected: list[dict[str, Any]] = []
    state: dict[str, Any] = {
        "schema_version": 1,
        "collector_pid": os.getpid(),
        "status": "starting",
        "target_runs": args.runs,
        "completed_runs": 0,
        "baseline_run_ids": sorted(baseline),
        "collected_run_ids": [],
        "capture_schema_hash": CAPTURE_SCHEMA_HASH,
        "policy_version": POLICY_VERSION,
        "mod_version": MOD_VERSION,
        "started_at": utc_now(),
        "stop_reason": "",
    }
    write_state(args.state_file, state)
    exit_code = 1
    try:
        if game_running():
            raise RuntimeError("Brotato is already running")
        set_auto_start(True)
        if args.launch:
            launch_game(root)
        else:
            raise RuntimeError("collector requires --launch when Brotato is stopped")
        launch_deadline = time.time() + 90.0
        while not game_running() and time.time() < launch_deadline:
            time.sleep(0.25)
        if not game_running():
            raise RuntimeError("Brotato did not start")
        write_state(args.state_file, state, status="running")
        current_run: Path | None = None
        last_mtime = time.time()
        while len(collected) < args.runs:
            if not game_running():
                raise RuntimeError("Brotato exited before collection completed")
            summaries = list_summaries(runs_dir)
            for run_id in sorted(set(summaries) - baseline - {row["run_id"] for row in collected}):
                summary = read_json_when_ready(summaries[run_id])
                fault = summary_fault(summary)
                if fault:
                    raise RuntimeError(f"run {run_id}: {fault}")
                collected.append(summary)
                write_state(
                    args.state_file,
                    state,
                    completed_runs=len(collected),
                    collected_run_ids=[row["run_id"] for row in collected],
                    last_result={
                        "run_id": run_id,
                        "result": summary.get("result"),
                        "last_wave": summary.get("last_wave"),
                        "duration_ms": summary.get("duration_ms"),
                    },
                )
                print(
                    f"[{len(collected)}/{args.runs}] {run_id} {summary.get('result')} wave={summary.get('last_wave')}",
                    flush=True,
                )
                if len(collected) >= args.runs:
                    break
            if len(collected) >= args.runs:
                break
            excluded = baseline | {row["run_id"] for row in collected}
            live = newest_run(runs_dir, excluded)
            if live != current_run:
                current_run = live
                if current_run is not None:
                    last_mtime = (current_run / "events.jsonl").stat().st_mtime
                    write_state(args.state_file, state, current_run_id=current_run.name)
            if current_run is not None:
                events_path = current_run / "events.jsonl"
                mtime = events_path.stat().st_mtime
                if mtime > last_mtime:
                    last_mtime = mtime
                age = time.time() - mtime
                lines = tail_lines(events_path)
                for line in lines:
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if event.get("event") == "error":
                        raise RuntimeError(f"run {current_run.name}: error event {event.get('payload')}")
                capture = latest_capture(lines)
                progress = {
                    "current_run_id": current_run.name,
                    "telemetry_age_sec": round(age, 3),
                }
                if capture:
                    progress.update(
                        {
                            "current_wave": capture["payload"].get("wave"),
                            "current_capture_seq": capture["payload"].get("capture_seq"),
                            "current_hp": capture["payload"].get("player", {}).get("hp"),
                        }
                    )
                write_state(args.state_file, state, **progress)
                if age > args.stale_sec:
                    raise RuntimeError(f"run {current_run.name}: telemetry stale for {age:.1f}s")
            time.sleep(args.poll_sec)
        stop_game()
        report = {
            "schema_version": 1,
            "status": "complete",
            "target_runs": args.runs,
            "completed_runs": len(collected),
            "capture_schema_hash": CAPTURE_SCHEMA_HASH,
            "policy_version": POLICY_VERSION,
            "mod_version": MOD_VERSION,
            "results": [
                {
                    "run_id": row.get("run_id"),
                    "result": row.get("result"),
                    "last_wave": row.get("last_wave"),
                    "duration_ms": row.get("duration_ms"),
                    "damage_taken": row.get("damage_taken"),
                }
                for row in collected
            ],
            "completed_at": utc_now(),
        }
        atomic_json(args.report_file, report)
        write_state(args.state_file, state, status="complete", stop_reason="target reached")
        exit_code = 0
    except Exception as exc:  # safety boundary: all faults stop collection
        stop_game()
        write_state(args.state_file, state, status="failed", stop_reason=str(exc))
        print(f"STOP: {exc}", file=sys.stderr, flush=True)
        exit_code = 2
    finally:
        set_auto_start(False)
        stop_game()
        write_state(args.state_file, state, auto_start=False, brotato_running=game_running())
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
