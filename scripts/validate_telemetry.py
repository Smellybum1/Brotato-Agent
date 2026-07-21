#!/usr/bin/env python3
"""Validate telemetry JSONL sequences and summarize completeness."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


REQUIRED_EVENTS = {
    "run_start",
    "run_end",
}


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
    args = ap.parse_args()
    root = Path(__file__).resolve().parents[1]
    runs_dir = args.runs_dir or (root / "runs")
    results = []
    for events in runs_dir.glob("*/events.jsonl"):
        results.append(validate_run(events))
    out = root / "reports" / "telemetry_validation.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "runs": len(results),
        "passed": sum(1 for r in results if r["ok"]),
        "failed": sum(1 for r in results if not r["ok"]),
        "details": results,
    }
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0 if payload["failed"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
