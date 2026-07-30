#!/usr/bin/env python3
"""Validate telemetry JSONL sequences and summarize completeness."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


REQUIRED_EVENTS = {
    "run_start",
    "run_end",
}
CAPTURE_SCHEMA_VERSION = "2.0.0"
CAPTURE_SCHEMA_ID = "combat_capture_v2"


def _capture_schema_hash() -> str:
    root = Path(__file__).resolve().parents[1]
    path = root / "configs" / "wp2" / "combat_capture_v2.schema.json"
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _validate_combat_capture(payload: object, line_number: int) -> list[str]:
    prefix = f"line {line_number}: combat_capture"
    if not isinstance(payload, dict):
        return [f"{prefix} payload is not an object"]
    required = {
        "capture_schema_id",
        "capture_schema_hash",
        "capture_seq",
        "observation_ts_ms",
        "observation_age_ms",
        "control_dt_ms",
        "valid",
        "wave",
        "wave_time",
        "player",
        "teacher",
        "entities",
        "weapons",
        "arena",
        "invalid_counts",
        "dropped_counts",
    }
    errors = [f"{prefix} missing {key}" for key in sorted(required - payload.keys())]
    if payload.get("capture_schema_id") != CAPTURE_SCHEMA_ID:
        errors.append(f"{prefix} has unknown capture_schema_id")
    if payload.get("capture_schema_hash") != _capture_schema_hash():
        errors.append(f"{prefix} schema hash mismatch")
    entities = payload.get("entities")
    groups = {"enemies", "bosses", "projectiles", "materials", "consumables", "crates", "obstacles"}
    if not isinstance(entities, dict):
        errors.append(f"{prefix} entities is not an object")
    else:
        for group in sorted(groups):
            if not isinstance(entities.get(group), list):
                errors.append(f"{prefix} entities.{group} is not an array")
    teacher = payload.get("teacher")
    if not isinstance(teacher, dict):
        errors.append(f"{prefix} teacher is not an object")
    else:
        for action_name in ("action", "previous_action"):
            action = teacher.get(action_name)
            if not isinstance(action, dict) or not {"x", "y"} <= action.keys():
                errors.append(f"{prefix} teacher.{action_name} is not a vector")
    return errors


def validate_run(events_path: Path) -> dict:
    errors: list[str] = []
    events = []
    if not events_path.exists():
        return {"ok": False, "errors": ["missing events.jsonl"], "path": str(events_path)}
    prev_seq = 0
    seen = set()
    for i, line in enumerate(events_path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError as e:
            errors.append(f"line {i}: malformed JSON ({e})")
            continue
        for field in ("schema_version", "run_id", "seq", "ts_ms", "event"):
            if field not in ev:
                errors.append(f"line {i}: missing {field}")
        seq = int(ev.get("seq", -1))
        if seq <= prev_seq:
            errors.append(f"line {i}: non-monotonic seq {seq} after {prev_seq}")
        prev_seq = seq
        seen.add(ev.get("event"))
        if ev.get("event") == "combat_capture":
            if ev.get("schema_version") != CAPTURE_SCHEMA_VERSION:
                errors.append(
                    f"line {i}: combat_capture requires schema_version {CAPTURE_SCHEMA_VERSION}"
                )
            errors.extend(_validate_combat_capture(ev.get("payload"), i))
        events.append(ev)
    for req in REQUIRED_EVENTS:
        if req not in seen:
            errors.append(f"missing required event {req}")
    if events and events[-1].get("event") != "run_end":
        errors.append("last event is not run_end")
    return {
        "ok": not errors,
        "errors": errors,
        "event_count": len(events),
        "events_seen": sorted(x for x in seen if x),
        "path": str(events_path),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs-dir", type=Path, default=None)
    ap.add_argument(
        "--run-ids-file",
        type=Path,
        default=None,
        help="Validate ONLY these run ids (one per line, or a JSON list, or a state "
        "file with collected_run_ids). Without it every run in --runs-dir is walked, "
        "which is the whole archive and takes hours.",
    )
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    root = Path(__file__).resolve().parents[1]
    runs_dir = args.runs_dir or (root / "runs")

    run_ids: list[str] | None = None
    if args.run_ids_file:
        raw = args.run_ids_file.read_text(encoding="utf-8-sig")
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            run_ids = [ln.strip() for ln in raw.splitlines() if ln.strip()]
        else:
            if isinstance(parsed, dict):
                run_ids = [str(x) for x in parsed.get("collected_run_ids", [])]
            elif isinstance(parsed, list):
                run_ids = [str(x) for x in parsed]
            else:
                raise SystemExit(f"--run-ids-file: unsupported shape {type(parsed).__name__}")
        if not run_ids:
            raise SystemExit(f"--run-ids-file {args.run_ids_file} yielded no run ids")

    results = []
    if run_ids is None:
        for events in runs_dir.glob("*/events.jsonl"):
            results.append(validate_run(events))
    else:
        for rid in run_ids:
            results.append(validate_run(runs_dir / rid / "events.jsonl"))
    out = args.out or (root / "reports" / "telemetry_validation.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "runs": len(results),
        "passed": sum(1 for r in results if r["ok"]),
        "failed": sum(1 for r in results if not r["ok"]),
        "scope": "run_ids_file" if run_ids is not None else "whole_runs_dir",
        "runs_dir": str(runs_dir),
        "details": results,
    }
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0 if payload["failed"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
