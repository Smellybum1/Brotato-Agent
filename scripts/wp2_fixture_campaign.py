#!/usr/bin/env python3
"""Unattended FULL-RUN driver used overnight to build the wave-20 fixture library.

It plays complete runs from wave 1 (auto_start on, resume_from_save OFF) and keeps
going through faults, so a snapshot collector running alongside it accumulates
wave-19 saves across MANY independent builds. It NEVER deploys.

Why not the tools that already exist:

- `scripts/overnight_supervisor.py` calls `deploy_mod.py` on every watchdog
  relaunch, and `deploy_mod.write_agent_config()` writes a FIXED dict that drops
  any key not in it (this is how the v128 deploy silently dropped the
  student_enabled / student_port / student_model_sha256 pins). It also predates the
  mod-ready sentinel, so a mod that fails to install leaves it polling a title
  screen indefinitely.
- `scripts/wp2_collect_teacher.py` is WP2-aware -- sentinel gate plus policy /
  mod / schema identity gates -- but ABORTS on the first fault. Overnight that
  throws away the rest of the window on a single stale run.

This script is collect_teacher's safety with a RESTART instead of an abort. The one
fault it will not retry is a missing mod-ready sentinel: that means a broken build,
and relaunching a broken build only burns the window.

`resume_from_save` MUST be False here. This driver plays full runs; resuming a
leftover save would produce single-wave "runs" that look like runs in the summary
and would silently poison both the fixture library and any run statistics.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.wp2_collect_teacher import (  # noqa: E402
    CAPTURE_SCHEMA_HASH,
    MOD_VERSION,
    POLICY_VERSION,
    atomic_json,
    await_mod_ready,
    game_running,
    launch_game,
    list_summaries,
    newest_run,
    read_json_when_ready,
    stop_game,
    summary_fault,
    tail_lines,
    utc_now,
)
from scripts.wp2_finale_loop import agent_config_path, write_agent_config  # noqa: E402


# --------------------------------------------------------------------------
# pure helpers (unit-tested)
# --------------------------------------------------------------------------


def runs_dir() -> Path:
    return Path(os.environ["APPDATA"]) / "Brotato" / "brotato_agent" / "runs"


def build_row(run_id: str, summary: dict[str, Any]) -> dict[str, Any]:
    """One report row from a completed run's summary.

    The fault string is RECORDED but is not disqualifying: a defeat, or a run with
    a telemetry fault, still produced wave-19 save states, and those fixtures are
    the point of the campaign. Dropping them would bias the library toward runs
    that happened to go well.
    """
    fault = summary_fault(summary)
    return {
        "run_id": run_id,
        "result": summary.get("result"),
        "last_wave": summary.get("last_wave"),
        "damage_taken": summary.get("damage_taken"),
        "duration_ms": summary.get("duration_ms"),
        "fault": fault or "",
    }


def should_restart(
    running: bool,
    telemetry_age_sec: float | None,
    run_elapsed_sec: float | None,
    stall_sec: float,
    run_timeout_sec: float,
    has_live_run: bool = True,
    rearm_sec: float | None = None,
) -> str:
    """Watchdog decision. Returns a reason code, or "" for keep going."""
    if not running:
        return "game_not_running"
    if telemetry_age_sec is not None and telemetry_age_sec > stall_sec:
        return f"telemetry_stale_{telemetry_age_sec:.1f}s"
    # "Summary written but the next run never starts" is its own failure mode: with
    # no live run directory there is no events.jsonl to go stale, so the stall
    # detector above is blind to it and only the (deliberately long) run timeout
    # would fire -- wasting up to 45 min of an unattended window on a stuck menu.
    if (
        not has_live_run
        and rearm_sec is not None
        and run_elapsed_sec is not None
        and run_elapsed_sec > rearm_sec
    ):
        return f"no_new_run_{run_elapsed_sec:.0f}s"
    if run_elapsed_sec is not None and run_elapsed_sec > run_timeout_sec:
        return f"run_timeout_{run_elapsed_sec:.0f}s"
    return ""


def restart_budget_exhausted(restarts_used: int, max_restarts: int) -> bool:
    """True once the NEXT restart would exceed the budget."""
    return restarts_used >= max_restarts


def current_wave_from_tail(lines: list[str]) -> int | None:
    for line in reversed(lines):
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("event") == "combat_capture":
            wave = (event.get("payload") or {}).get("wave")
            return wave if isinstance(wave, int) else None
    return None


def write_state(path: Path, state: dict[str, Any], **updates: Any) -> None:
    state.update(updates)
    state["updated_at"] = utc_now()
    atomic_json(path, state)


# --------------------------------------------------------------------------
# driver
# --------------------------------------------------------------------------


def start_game(root: Path) -> None:
    """Launch and gate on the mod-ready sentinel. Raises on a broken build."""
    # launch_game() already does prepare_mod_environment() + clear_mod_ready().
    launch_game(root)
    deadline = time.time() + 90.0
    while not game_running() and time.time() < deadline:
        time.sleep(0.25)
    if not game_running():
        raise RuntimeError(
            "Brotato did not start within 90s. Check "
            "%APPDATA%/Brotato/logs/modloader*.log"
        )
    fault = await_mod_ready()
    if fault is not None:
        raise BrokenBuild(
            f"{fault} -- BROKEN BUILD, not retrying. Check "
            "%APPDATA%/Brotato/logs/modloader*.log for a GDScript parse error."
        )


class BrokenBuild(RuntimeError):
    """The mod failed to install; restarting cannot fix it."""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, required=True)
    ap.add_argument("--state-file", type=Path, required=True)
    ap.add_argument("--report-file", type=Path, required=True)
    ap.add_argument("--max-restarts", type=int, default=20)
    ap.add_argument("--stall-sec", type=float, default=180.0)
    ap.add_argument("--rearm-sec", type=float, default=180.0,
                    help="Summary written but no new run started => restart")
    ap.add_argument("--run-timeout-sec", type=float, default=2700.0)
    ap.add_argument("--poll-sec", type=float, default=1.0)
    args = ap.parse_args()
    if args.runs < 1:
        raise SystemExit("--runs must be positive")

    root = Path(__file__).resolve().parents[1]
    rd = runs_dir()
    baseline = {p.name for p in rd.iterdir() if p.is_dir()} if rd.exists() else set()

    rows: list[dict[str, Any]] = []
    restarts_used = 0
    state: dict[str, Any] = {
        "schema_version": 1,
        "driver": "wp2_fixture_campaign",
        "pid": os.getpid(),
        "status": "starting",
        "target_runs": args.runs,
        "completed_runs": 0,
        "restarts_used": 0,
        "baseline_run_ids": sorted(baseline),
        "current_run_id": None,
        "current_wave": None,
        "telemetry_age_sec": None,
        "last_result": None,
        "capture_schema_hash": CAPTURE_SCHEMA_HASH,
        "policy_version": POLICY_VERSION,
        "mod_version": MOD_VERSION,
        "started_at": utc_now(),
        "stop_reason": "",
    }
    args.state_file.parent.mkdir(parents=True, exist_ok=True)
    args.report_file.parent.mkdir(parents=True, exist_ok=True)
    write_state(args.state_file, state)

    exit_code = 0
    stop_reason = "target reached"
    try:
        stop_game()
        # Full runs from wave 1 -- resume_from_save MUST be off (see module docstring).
        write_agent_config(agent_config_path(), auto_start=True, resume_from_save=False)
        start_game(root)
        write_state(args.state_file, state, status="running")

        run_started = time.time()
        last_mtime = time.time()
        current_run: Path | None = None
        seen: set[str] = set()

        while len(rows) < args.runs:
            summaries = list_summaries(rd)
            for run_id in sorted(set(summaries) - baseline - seen):
                summary = read_json_when_ready(summaries[run_id])
                seen.add(run_id)
                row = build_row(run_id, summary)
                rows.append(row)
                print(
                    f"[{len(rows)}/{args.runs}] {row['run_id']} result={row['result']} "
                    f"last_wave={row['last_wave']} damage_taken={row['damage_taken']} "
                    f"duration_ms={row['duration_ms']} fault={row['fault']!r}",
                    flush=True,
                )
                write_state(
                    args.state_file,
                    state,
                    completed_runs=len(rows),
                    last_result=row,
                )
                # A finished run means the next one starts now.
                run_started = time.time()
                current_run = None
                if len(rows) >= args.runs:
                    break
            if len(rows) >= args.runs:
                break

            live = newest_run(rd, baseline | seen)
            if live is not None and live != current_run:
                current_run = live
                run_started = time.time()
            age: float | None = None
            wave: int | None = None
            if current_run is not None:
                events_path = current_run / "events.jsonl"
                try:
                    mtime = events_path.stat().st_mtime
                except OSError:
                    mtime = last_mtime
                if mtime > last_mtime:
                    last_mtime = mtime
                age = time.time() - mtime
                wave = current_wave_from_tail(tail_lines(events_path))
            write_state(
                args.state_file,
                state,
                current_run_id=current_run.name if current_run is not None else None,
                current_wave=wave,
                telemetry_age_sec=None if age is None else round(age, 3),
            )

            reason = should_restart(
                running=game_running(),
                telemetry_age_sec=age,
                run_elapsed_sec=time.time() - run_started,
                stall_sec=args.stall_sec,
                run_timeout_sec=args.run_timeout_sec,
                has_live_run=current_run is not None,
                rearm_sec=args.rearm_sec,
            )
            if reason:
                if restart_budget_exhausted(restarts_used, args.max_restarts):
                    stop_reason = f"restart budget exhausted ({reason})"
                    exit_code = 2
                    break
                restarts_used += 1
                print(
                    f"RESTART {restarts_used}/{args.max_restarts}: {reason}",
                    flush=True,
                )
                stop_game()
                time.sleep(2.0)
                # Never deploy here: a watchdog relaunch must not change the build
                # under test, and deploy_mod rewrites agent_config wholesale.
                start_game(root)
                run_started = time.time()
                last_mtime = time.time()
                current_run = None
                write_state(args.state_file, state, restarts_used=restarts_used)
                continue

            time.sleep(args.poll_sec)
    except BrokenBuild as exc:
        stop_reason = str(exc)
        exit_code = 3
        print(f"ABORT: {exc}", file=sys.stderr, flush=True)
    except Exception as exc:  # noqa: BLE001
        stop_reason = str(exc)
        exit_code = 2
        print(f"ABORT: {exc}", file=sys.stderr, flush=True)
    finally:
        stop_game()
        try:
            write_agent_config(agent_config_path(), auto_start=False, resume_from_save=False)
        except Exception as exc:  # noqa: BLE001
            print(f"WARNING: could not restore agent_config: {exc}", file=sys.stderr)
        write_state(
            args.state_file,
            state,
            status="complete" if exit_code == 0 else "failed",
            completed_runs=len(rows),
            restarts_used=restarts_used,
            stop_reason=stop_reason,
            brotato_running=game_running(),
        )

    victories = [r for r in rows if str(r["result"]).lower() == "victory"]
    report = {
        "schema_version": 1,
        "driver": "wp2_fixture_campaign",
        "status": "complete" if exit_code == 0 else "failed",
        "target_runs": args.runs,
        "completed_runs": len(rows),
        "victories": len(victories),
        "restarts_used": restarts_used,
        "stop_reason": stop_reason,
        "capture_schema_hash": CAPTURE_SCHEMA_HASH,
        "policy_version": POLICY_VERSION,
        "mod_version": MOD_VERSION,
        "runs": rows,
        "completed_at": utc_now(),
    }
    atomic_json(args.report_file, report)

    # Raw rows FIRST, always -- an aggregate without its rows is not evidence.
    print("\n--- raw runs ---")
    print(f"{'#':>3}  {'run_id':<26} {'result':<8} {'wave':>4} {'dmg':>5} {'ms':>8}  fault")
    for i, row in enumerate(rows, 1):
        print(
            f"{i:>3}  {str(row['run_id']):<26} {str(row['result']):<8} "
            f"{str(row['last_wave']):>4} {str(row['damage_taken']):>5} "
            f"{str(row['duration_ms']):>8}  {row['fault']}"
        )
    print("\n--- totals ---")
    print(f"completed={len(rows)}/{args.runs} victories={len(victories)} restarts_used={restarts_used}")
    print(f"stop_reason={stop_reason}")
    print(f"report written to {args.report_file}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
