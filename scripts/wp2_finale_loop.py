#!/usr/bin/env python3
"""Wave-20 finale trial loop: restore a wave-19 fixture, run ONE resumed wave, record it.

A full run costs ~20 min and only ~2/3 reach wave 20, of which ~70% draw the
Predator -- ~42 min of wall clock per Predator observation. Restoring a wave-19
save and resuming gives the same observation in ~110 s. This script is the loop
around that: restore -> launch -> wait for run_end -> validate -> record -> repeat.

The validation is not decoration. If `resume_from_save` fails for any reason the
mod starts a FRESH run, which walks waves 1..20 and produces a summary that looks
exactly like a normal run. Counting one of those as a finale trial would silently
poison the arm. Hence: waves must be exactly [20].

Never edits mod source; always restores the operator's own save and turns
auto_start/resume_from_save back off in a finally block.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from collections import Counter
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
    read_json_when_ready,
    stop_game,
    utc_now,
)
from scripts.wp2_snapshot_collector import boss_label, save_dir  # noqa: E402


BACKUP_DIR = Path(".tmp/finale_loop")
BACKUP_NAME = "run_v3_0.original.json"


# --------------------------------------------------------------------------
# pure helpers (unit-tested)
# --------------------------------------------------------------------------


def agent_config_path() -> Path:
    return Path(os.environ["APPDATA"]) / "Brotato" / "brotato_agent" / "agent_config.json"


def runs_dir() -> Path:
    return Path(os.environ["APPDATA"]) / "Brotato" / "brotato_agent" / "runs"


def boss_entity_from_path(script_path: str) -> str:
    """Entity folder name from a boss script path, else the raw path.

    'res://entities/units/enemies/predator/predator.gd' -> 'predator'.
    Deliberately does NOT guess when the pattern does not match: an unexpected
    path shape must show up in the record as itself, not as a plausible-looking
    entity name.
    """
    if not isinstance(script_path, str):
        return str(script_path)
    marker = "enemies/"
    idx = script_path.find(marker)
    if idx < 0:
        return script_path
    rest = script_path[idx + len(marker):]
    segment = rest.split("/")[0]
    if not segment or "/" not in rest:
        return script_path
    return segment


def write_agent_config(
    path: Path,
    auto_start: bool,
    resume_from_save: bool,
    finale_v2: bool = False,
    finale_rate_full: bool = False,
    finale_no_panic: bool = False,
    finale_heal_seek: bool = False,
    finale_range_keep: bool = False,
    finale_projectile_priority: bool = False,
    # TRACKS THE SHIPPED DEFAULT, which is ON. Every other flag here is an
    # experimental arm and defaults OFF; this one shipped, so a caller that does
    # not mention it must get the build that is actually deployed. With the old
    # False default, wp2_fixture_campaign.py would have played full runs WITHOUT
    # the shipped fix while looking like an ordinary run.
    finale_pivot_projectiles: bool = True,
    finale_co_rotate: bool = False,
    finale_ring_radius: bool = False,
) -> None:
    """Set auto_start/resume_from_save and the finale arm flags, PRESERVING other keys.

    Same read-modify-write contract as wp2_collect_teacher.set_auto_start: the
    student keys (student_enabled / student_port / student_model_sha256) live in
    this file and a fixed-dict overwrite would silently strip them.
    """
    payload: dict[str, Any] = {}
    try:
        existing = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(existing, dict):
            payload = existing
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    payload.setdefault("character", "character_well_rounded")
    payload.setdefault("danger", 0)
    payload.setdefault("weapon_prefixes", ["weapon_smg", "weapon_stick"])
    payload["auto_start"] = auto_start
    payload["resume_from_save"] = resume_from_save
    # Written EVERY time, never setdefault: deploy_mod.py rewrites this file from a
    # fixed dict, so a stale/absent flag would silently run the wrong arm.
    payload["finale_v2"] = finale_v2
    payload["finale_rate_full"] = finale_rate_full
    payload["finale_no_panic"] = finale_no_panic
    payload["finale_heal_seek"] = finale_heal_seek
    payload["finale_range_keep"] = finale_range_keep
    payload["finale_projectile_priority"] = finale_projectile_priority
    payload["finale_pivot_projectiles"] = finale_pivot_projectiles
    payload["finale_co_rotate"] = finale_co_rotate
    payload["finale_ring_radius"] = finale_ring_radius
    atomic_json(path, payload)


def analyse_events(events_path: Path) -> dict[str, Any]:
    """Waves / capture count / boss script paths from a run's events.jsonl."""
    waves: set[int] = set()
    n_captures = 0
    boss_paths: Counter[str] = Counter()
    # STREAM, never read_text(). A valid fixture trial's events.jsonl is ~8 MB, but
    # the case this analysis exists to catch -- resume failed, so the mod played a
    # FULL run -- produces up to ~330 MB (measured across 650 archived runs). The
    # diagnostic path must not be the one that blows up memory.
    try:
        handle = events_path.open("r", encoding="utf-8", errors="replace")
    except OSError:
        handle = None
    if handle is None:
        return {
            "waves": [], "n_captures": 0, "boss_paths": {},
            "boss_entity": "", "boss_capture_count": 0,
        }
    with handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("event") != "combat_capture":
                continue
            payload = event.get("payload") or {}
            n_captures += 1
            wave = payload.get("wave")
            if isinstance(wave, int):
                waves.add(wave)
            bosses = (payload.get("entities") or {}).get("bosses") or []
            for boss in bosses:
                if isinstance(boss, dict):
                    boss_paths[str(boss.get("script_path"))] += 1
    entities = sorted({boss_entity_from_path(p) for p in boss_paths})
    return {
        "waves": sorted(waves),
        "n_captures": n_captures,
        "boss_paths": dict(boss_paths),
        "boss_entity": entities[0] if len(entities) == 1 else (";".join(entities) if entities else ""),
        "boss_capture_count": int(sum(boss_paths.values())),
    }


def validate_trial(
    analysis: dict[str, Any],
    summary: dict[str, Any],
    expected_boss: str,
    expected_finale_v2: bool,
    expected_finale_rate_full: bool = False,
    expected_finale_no_panic: bool = False,
    expected_finale_heal_seek: bool = False,
    expected_finale_range_keep: bool = False,
    expected_finale_projectile_priority: bool = False,
    expected_finale_pivot_projectiles: bool = False,
    expected_finale_co_rotate: bool = False,
    expected_finale_ring_radius: bool = False,
    target_wave: int = 20,
) -> str:
    """Return "" when the trial is a valid finale observation, else a reason code.

    The wave guard exists because a FAILED fixture resume produces a full run
    from wave 1 whose summary.json is indistinguishable from a valid trial. So
    the run must START at target_wave and continue contiguously; any wave below
    the target is the signature of the mod walking waves 1..N after a bad
    resume. Wave 20 ends the run, so a target of 20 admits exactly [20]; a
    lower target also admits the survival tail (e.g. [17, 18, 19, 20]).
    """
    waves = list(analysis.get("waves") or [])
    if not waves:
        return "no_combat_captures"
    if any(w < target_wave for w in waves):
        # The resume failed and the mod started a FRESH run from wave 1. Without
        # this check a full run would be recorded as a finale trial.
        return "resume_failed_fresh_run"
    if target_wave not in waves:
        return f"unexpected_waves:{waves}"
    if waves != list(range(target_wave, max(waves) + 1)):
        # A hole in the wave sequence means captures went missing.
        return f"wave_gap:{waves}"
    boss_paths = analysis.get("boss_paths") or {}
    if 20 in waves:
        if target_wave == 20:
            # The boss fight IS the measurement: identity must match the arm.
            if len(boss_paths) != 1:
                return f"boss_path_count:{len(boss_paths)}"
            entity = analysis.get("boss_entity")
            if entity != expected_boss:
                return f"boss_mismatch:{entity}"
        else:
            # target_wave < 20: wave 20 is only the SURVIVAL TAIL of a lower-wave
            # trial, run over a fixture set with mixed bosses. Enforcing boss
            # identity here would reject exactly the trials that SURVIVED -- a
            # non-random subset -- and bias the primary outcome. Only structural
            # sanity is checked: more than one distinct boss path means the
            # capture stream is confused. The observed entity is recorded on the
            # trial row (analysis["boss_entity"]) so the data stays self-describing.
            if len(boss_paths) > 1:
                return f"boss_path_count:{len(boss_paths)}"
    elif boss_paths:
        # Bosses only exist at wave 20; one here means something is wrong.
        return f"unexpected_boss:{sorted(boss_paths)}"
    result = str(summary.get("result", "")).lower()
    if result not in {"victory", "defeat"}:
        return f"unexpected_result:{summary.get('result')}"
    if summary.get("policy_version") != POLICY_VERSION:
        return f"policy_mismatch:{summary.get('policy_version')}"
    if summary.get("mod_version") != MOD_VERSION:
        return f"mod_mismatch:{summary.get('mod_version')}"
    # The mod reports which controller actually ran. If the flag were lost (see
    # write_agent_config) the trial would otherwise be recorded under the wrong arm.
    if bool(summary.get("finale_v2", False)) != expected_finale_v2:
        return f"finale_arm_mismatch:{summary.get('finale_v2')}"
    if bool(summary.get("finale_rate_full", False)) != expected_finale_rate_full:
        return f"finale_rate_arm_mismatch:{summary.get('finale_rate_full')}"
    if bool(summary.get("finale_no_panic", False)) != expected_finale_no_panic:
        return f"finale_no_panic_mismatch:{summary.get('finale_no_panic')}"
    if bool(summary.get("finale_heal_seek", False)) != expected_finale_heal_seek:
        return f"finale_heal_seek_mismatch:{summary.get('finale_heal_seek')}"
    if bool(summary.get("finale_range_keep", False)) != expected_finale_range_keep:
        return f"finale_range_keep_mismatch:{summary.get('finale_range_keep')}"
    if bool(summary.get("finale_projectile_priority", False)) != expected_finale_projectile_priority:
        return f"finale_projectile_priority_mismatch:{summary.get('finale_projectile_priority')}"
    if bool(summary.get("finale_pivot_projectiles", False)) != expected_finale_pivot_projectiles:
        return f"finale_pivot_projectiles_mismatch:{summary.get('finale_pivot_projectiles')}"
    if bool(summary.get("finale_co_rotate", False)) != expected_finale_co_rotate:
        return f"finale_co_rotate_mismatch:{summary.get('finale_co_rotate')}"
    if bool(summary.get("finale_ring_radius", False)) != expected_finale_ring_radius:
        return f"finale_ring_radius_mismatch:{summary.get('finale_ring_radius')}"
    return ""


def load_index(fixture_dir: Path) -> list[dict[str, Any]]:
    index = fixture_dir / "index.jsonl"
    rows: list[dict[str, Any]] = []
    if not index.exists():
        return rows
    for line in index.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def select_fixtures(fixture_dir: Path, boss: str) -> list[tuple[Path, str]]:
    """(path, digest) for index rows whose boss matches and whose file exists."""
    out: list[tuple[Path, str]] = []
    for row in load_index(fixture_dir):
        # The two fixtures that exist today were indexed BEFORE the collector
        # started writing a `boss` field, so their rows carry only the raw
        # `bosses_spawn` save id. Fall back to the collector's own authoritative
        # id->entity mapping rather than dropping them.
        label = row.get("boss")
        if label is None:
            label = boss_label(row.get("bosses_spawn"))
        if label != boss:
            continue
        path = fixture_dir / str(row.get("file"))
        if path.exists():
            out.append((path, str(row.get("digest", ""))))
    return out


def digest_for(fixture_dir: Path, path: Path) -> str:
    for row in load_index(fixture_dir):
        if str(row.get("file")) == path.name:
            return str(row.get("digest", ""))
    return ""


# --------------------------------------------------------------------------
# loop
# --------------------------------------------------------------------------


def run_trial(
    root: Path,
    fixture: Path,
    fixture_digest: str,
    args: argparse.Namespace,
) -> dict[str, Any]:
    """One trial. Returns the record row. Raises RuntimeError only for loop-fatal faults."""
    started = time.time()
    live_save = save_dir() / "run_v3_0.json"

    stop_game()
    deadline = time.time() + 10.0
    while game_running() and time.time() < deadline:
        time.sleep(0.25)
    if game_running():
        raise RuntimeError("Brotato still running after stop_game(); aborting loop")

    shutil.copy2(fixture, live_save)
    write_agent_config(
        agent_config_path(),
        auto_start=True,
        resume_from_save=True,
        finale_v2=args.finale_v2,
        finale_rate_full=args.finale_rate_full,
        finale_no_panic=args.finale_no_panic,
        finale_heal_seek=args.finale_heal_seek,
        finale_range_keep=args.finale_range_keep,
        finale_projectile_priority=args.finale_projectile_priority,
        finale_pivot_projectiles=args.finale_pivot_projectiles,
        finale_co_rotate=args.finale_co_rotate,
        finale_ring_radius=args.finale_ring_radius,
    )

    rd = runs_dir()
    baseline = {p.name for p in rd.iterdir() if p.is_dir()} if rd.exists() else set()

    # launch_game() already calls prepare_mod_environment() + clear_mod_ready().
    launch_game(root)

    launch_deadline = time.time() + 90.0
    while not game_running() and time.time() < launch_deadline:
        time.sleep(0.25)
    if not game_running():
        raise RuntimeError(
            "Brotato did not start within 90s; aborting loop. Check "
            "%APPDATA%/Brotato/logs/modloader*.log"
        )
    ready_fault = await_mod_ready()
    if ready_fault is not None:
        raise RuntimeError(
            f"{ready_fault} (aborting loop -- a broken build must not be retried). "
            "Check %APPDATA%/Brotato/logs/modloader*.log"
        )

    row: dict[str, Any] = {
        "ts": utc_now(),
        "label": args.label,
        # The arm this trial was ARMED for; validate_trial cross-checks it against
        # the controller the mod reports it actually ran.
        "finale_v2": bool(args.finale_v2),
        "finale_rate_full": bool(args.finale_rate_full),
        "finale_no_panic": bool(args.finale_no_panic),
        "finale_heal_seek": bool(args.finale_heal_seek),
        "finale_range_keep": bool(args.finale_range_keep),
        "finale_projectile_priority": bool(args.finale_projectile_priority),
        "finale_pivot_projectiles": bool(args.finale_pivot_projectiles),
        "finale_co_rotate": bool(args.finale_co_rotate),
        "finale_ring_radius": bool(args.finale_ring_radius),
        # Which wave this trial measured; makes trials.jsonl self-describing.
        "target_wave": int(getattr(args, "target_wave", 20)),
        "fixture_file": fixture.name,
        "fixture_digest": fixture_digest,
        "run_id": "",
        "result": "",
        "last_wave": None,
        "damage_taken": None,
        "duration_ms": None,
        "n_captures": 0,
        "waves": [],
        "boss_entity": "",
        "boss_capture_count": 0,
        "boss_paths": {},
        "valid": False,
        "invalid_reason": "",
        "policy_version": POLICY_VERSION,
        "mod_version": MOD_VERSION,
        "capture_schema_hash": CAPTURE_SCHEMA_HASH,
        "trial_wall_sec": None,
    }

    trial_deadline = time.time() + args.timeout_sec
    last_mtime = time.time()
    summary_path: Path | None = None
    run_dir: Path | None = None
    while True:
        new_dirs = (
            [p for p in rd.iterdir() if p.is_dir() and p.name not in baseline]
            if rd.exists()
            else []
        )
        done = [p for p in new_dirs if (p / "summary.json").exists()]
        if done:
            run_dir = max(done, key=lambda p: (p / "summary.json").stat().st_mtime)
            summary_path = run_dir / "summary.json"
            break
        live = [p for p in new_dirs if (p / "events.jsonl").exists()]
        if live:
            newest = max(live, key=lambda p: (p / "events.jsonl").stat().st_mtime)
            mtime = (newest / "events.jsonl").stat().st_mtime
            if mtime > last_mtime:
                last_mtime = mtime
            age = time.time() - mtime
            if age > args.stale_sec:
                row["run_id"] = newest.name
                row["invalid_reason"] = f"telemetry_stale_{age:.1f}s"
                break
        if time.time() > trial_deadline:
            row["invalid_reason"] = f"timeout_{args.timeout_sec:.0f}s"
            if new_dirs:
                row["run_id"] = max(new_dirs, key=lambda p: p.stat().st_mtime).name
            break
        if not game_running():
            row["invalid_reason"] = "game_exited_before_summary"
            break
        time.sleep(args.poll_sec)

    summary: dict[str, Any] = {}
    if summary_path is not None:
        summary = read_json_when_ready(summary_path)

    # Stop the game IMMEDIATELY after reading summary.json and BEFORE any
    # events.jsonl analysis: with auto_start=true the mod chains straight into a
    # fresh run, which would overwrite the fixture-restored save and burn wall
    # clock. Analysis is on files already on disk, so it can wait.
    stop_game()

    if run_dir is not None:
        analysis = analyse_events(run_dir / "events.jsonl")
        row.update(
            {
                "run_id": run_dir.name,
                "result": summary.get("result", ""),
                "last_wave": summary.get("last_wave"),
                "damage_taken": summary.get("damage_taken"),
                "duration_ms": summary.get("duration_ms"),
                "n_captures": analysis["n_captures"],
                "waves": analysis["waves"],
                "boss_entity": analysis["boss_entity"],
                "boss_capture_count": analysis["boss_capture_count"],
                "boss_paths": analysis["boss_paths"],
                "policy_version": summary.get("policy_version"),
                "mod_version": summary.get("mod_version"),
            }
        )
        reason = validate_trial(
            analysis,
            summary,
            args.boss,
            bool(args.finale_v2),
            bool(args.finale_rate_full),
            bool(args.finale_no_panic),
            bool(args.finale_heal_seek),
            bool(args.finale_range_keep),
            bool(args.finale_projectile_priority),
            bool(args.finale_pivot_projectiles),
            bool(args.finale_co_rotate),
            bool(args.finale_ring_radius),
            target_wave=int(getattr(args, "target_wave", 20)),
        )
        row["valid"] = reason == ""
        row["invalid_reason"] = reason

    row["trial_wall_sec"] = round(time.time() - started, 1)
    return row


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixture", type=Path, action="append", default=None)
    ap.add_argument("--fixture-dir", type=Path, default=Path(".tmp/snapshots"))
    ap.add_argument("--boss", type=str, default="predator")
    ap.add_argument("--target-wave", type=int, default=20)
    ap.add_argument("--trials", type=int, required=True)
    ap.add_argument("--label", type=str, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--timeout-sec", type=float, default=900.0)
    ap.add_argument("--stale-sec", type=float, default=45.0)
    ap.add_argument("--poll-sec", type=float, default=0.5)
    ap.add_argument("--finale-v2", action="store_true")
    ap.add_argument("--finale-rate-full", action="store_true")
    ap.add_argument("--finale-no-panic", action="store_true")
    ap.add_argument("--finale-heal-seek", action="store_true")
    ap.add_argument("--finale-range-keep", action="store_true")
    ap.add_argument("--finale-projectile-priority", action="store_true")
    # DEFAULT-ON since mod 0.2.49 (qualified: 0.688 -> 1.000, Fisher p=0.000426).
    # write_agent_config writes this key on EVERY trial, so leaving the loop's
    # default at False would have silently disabled the SHIPPED behaviour on every
    # future trial -- and produced a "baseline" that looks legitimate while running
    # a build nobody ships. Kept for explicitness; --no-finale-pivot-projectiles is
    # how a control arm turns it off.
    ap.add_argument("--finale-pivot-projectiles", action="store_true")
    ap.add_argument("--no-finale-pivot-projectiles", action="store_true",
                    help="disable the shipped default (control arms only)")
    ap.add_argument("--finale-co-rotate", action="store_true")
    ap.add_argument("--finale-ring-radius", action="store_true")
    args = ap.parse_args()

    # Resolve the shipped default ONCE, here, so every downstream use (config
    # write, per-trial row, arm validation, summary prints) agrees. The arm
    # recorded in telemetry is checked against this, so a mismatch still
    # invalidates the trial.
    args.finale_pivot_projectiles = not args.no_finale_pivot_projectiles

    if args.trials < 1:
        raise SystemExit("--trials must be positive")

    root = Path(__file__).resolve().parents[1]
    if args.fixture:
        fixtures = [(Path(f), digest_for(args.fixture_dir, Path(f))) for f in args.fixture]
        missing = [str(f) for f, _ in fixtures if not f.exists()]
        if missing:
            raise SystemExit(f"missing fixture(s): {missing}")
    else:
        fixtures = select_fixtures(args.fixture_dir, args.boss)
    if not fixtures:
        raise SystemExit(f"no fixtures selected (dir={args.fixture_dir} boss={args.boss})")

    print(
        f"{len(fixtures)} fixture(s) selected, boss={args.boss}, "
        f"trials={args.trials}, finale_v2={bool(args.finale_v2)}, "
        f"finale_rate_full={bool(args.finale_rate_full)}, "
        f"finale_no_panic={bool(args.finale_no_panic)}, "
        f"finale_heal_seek={bool(args.finale_heal_seek)}, "
        f"finale_range_keep={bool(args.finale_range_keep)}, "
        f"finale_projectile_priority={bool(args.finale_projectile_priority)}, "
        f"finale_pivot_projectiles={bool(args.finale_pivot_projectiles)}, "
        f"finale_co_rotate={bool(args.finale_co_rotate)}, "
        f"finale_ring_radius={bool(args.finale_ring_radius)}"
    )
    for path, digest in fixtures:
        print(f"  fixture {path.name} digest={digest}")

    live_save = save_dir() / "run_v3_0.json"
    backup_dir = root / BACKUP_DIR
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup = backup_dir / BACKUP_NAME
    had_original = live_save.exists()
    # Back up ONCE: a crashed prior loop may have left a fixture in place, and
    # overwriting the backup with that fixture would destroy the operator's save.
    if had_original and not backup.exists():
        shutil.copy2(live_save, backup)

    rows: list[dict[str, Any]] = []
    args.out.parent.mkdir(parents=True, exist_ok=True)
    exit_code = 0
    try:
        with args.out.open("a", encoding="utf-8", newline="\n") as fh:
            for i in range(args.trials):
                fixture, digest = fixtures[i % len(fixtures)]
                row = run_trial(root, fixture, digest, args)
                rows.append(row)
                fh.write(json.dumps(row) + "\n")
                fh.flush()
                print(
                    f"[{i + 1}/{args.trials}] {row['run_id']} waves={row['waves']} "
                    f"boss={row['boss_entity']} captures={row['n_captures']} "
                    f"result={row['result']} valid={row['valid']} "
                    f"reason={row['invalid_reason']!r} wall={row['trial_wall_sec']}s "
                    f"fixture={row['fixture_file']}",
                    flush=True,
                )
    except Exception as exc:  # loop-fatal: report and stop, do not retry
        print(f"ABORT: {exc}", file=sys.stderr, flush=True)
        exit_code = 2
    finally:
        stop_game()
        try:
            # Experimental flags False: an interrupted loop must never leave the
            # machine armed. finale_pivot_projectiles is the EXCEPTION -- it is a
            # SHIPPED DEFAULT, not an arm, so disarming to False would leave the
            # machine running WITHOUT the shipped fix and misrepresent the build
            # for any later manual run or dataset collection.
            write_agent_config(
                agent_config_path(),
                auto_start=False,
                resume_from_save=False,
                finale_v2=False,
                finale_rate_full=False,
                finale_no_panic=False,
                finale_heal_seek=False,
                finale_range_keep=False,
                finale_projectile_priority=False,
                finale_pivot_projectiles=True,
                finale_co_rotate=False,
                finale_ring_radius=False,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"WARNING: could not restore agent_config: {exc}", file=sys.stderr)
        try:
            if backup.exists():
                shutil.copy2(backup, live_save)
                print(f"restored original save from {backup}")
            elif not had_original:
                live_save.unlink(missing_ok=True)
                print("no original save existed; removed fixture copy")
        except Exception as exc:  # noqa: BLE001
            print(f"WARNING: could not restore save: {exc}", file=sys.stderr)

    # Raw rows FIRST, always -- an aggregate without its rows is not evidence.
    print("\n--- raw trials ---")
    print(
        f"{'#':>2}  {'run_id':<24} {'fixture':<40} {'waves':<10} {'boss':<12} "
        f"{'caps':>6} {'result':<8} {'dmg':>5} {'ms':>7} {'valid':<5} reason"
    )
    for i, row in enumerate(rows, 1):
        print(
            f"{i:>2}  {str(row['run_id']):<24} {row['fixture_file']:<40} "
            f"{str(row['waves']):<10} {str(row['boss_entity']):<12} "
            f"{row['n_captures']:>6} {str(row['result']):<8} "
            f"{str(row['damage_taken']):>5} {str(row['duration_ms']):>7} "
            f"{str(row['valid']):<5} {row['invalid_reason']}"
        )
    valid = [r for r in rows if r["valid"]]
    wins = [r for r in valid if str(r["result"]).lower() == "victory"]
    print("\n--- aggregate ---")
    print(
        f"label={args.label} boss={args.boss} finale_v2={bool(args.finale_v2)} "
        f"finale_rate_full={bool(args.finale_rate_full)} "
        f"finale_no_panic={bool(args.finale_no_panic)} "
        f"finale_heal_seek={bool(args.finale_heal_seek)} "
        f"finale_range_keep={bool(args.finale_range_keep)}, "
        f"finale_projectile_priority={bool(args.finale_projectile_priority)}, "
        f"finale_pivot_projectiles={bool(args.finale_pivot_projectiles)}, "
        f"finale_co_rotate={bool(args.finale_co_rotate)}, "
        f"finale_ring_radius={bool(args.finale_ring_radius)}"
    )
    print(f"valid trials: {len(valid)}/{len(rows)}")
    if valid:
        print(f"victories:    {len(wins)}/{len(valid)} = {len(wins) / len(valid):.3f}")
    else:
        print("victories:    n/a (no valid trials)")
    print(f"results appended to {args.out}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
