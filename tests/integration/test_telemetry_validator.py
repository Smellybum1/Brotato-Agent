import json
from pathlib import Path

from scripts.validate_telemetry import validate_run


def _tmp(name: str) -> Path:
    root = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "_tmp"
    root.mkdir(parents=True, exist_ok=True)
    d = root / name
    d.mkdir(exist_ok=True)
    return d


def test_validate_monotonic_and_terminal():
    d = _tmp("ok")
    p = d / "events.jsonl"
    lines = []
    for i, ev in enumerate(["run_start", "phase_transition", "run_end"], 1):
        lines.append(
            json.dumps(
                {
                    "schema_version": "1.0.0",
                    "run_id": "r1",
                    "seq": i,
                    "ts_ms": i * 10,
                    "event": ev,
                    "payload": {},
                }
            )
        )
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    res = validate_run(p)
    assert res["ok"]


def test_validate_rejects_non_monotonic():
    d = _tmp("bad")
    p = d / "events.jsonl"
    p.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "schema_version": "1.0.0",
                        "run_id": "r",
                        "seq": 2,
                        "ts_ms": 1,
                        "event": "run_start",
                        "payload": {},
                    }
                ),
                json.dumps(
                    {
                        "schema_version": "1.0.0",
                        "run_id": "r",
                        "seq": 1,
                        "ts_ms": 2,
                        "event": "run_end",
                        "payload": {},
                    }
                ),
            ]
        ),
        encoding="utf-8",
    )
    res = validate_run(p)
    assert not res["ok"]
