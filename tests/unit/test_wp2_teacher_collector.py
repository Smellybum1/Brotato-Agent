import json
import sys
from pathlib import Path

from scripts.wp2_collect_teacher import (
    atomic_json,
    latest_capture,
    launch_game,
    read_json_when_ready,
    summary_fault,
    tail_lines,
)


def test_atomic_json_and_tail_lines(tmp_path: Path):
    path = tmp_path / "state.json"
    atomic_json(path, {"status": "running"})
    assert json.loads(path.read_text(encoding="utf-8")) == {"status": "running"}
    events = tmp_path / "events.jsonl"
    events.write_text("\n".join(str(index) for index in range(100)) + "\n", encoding="utf-8")
    assert tail_lines(events, 3) == ["97", "98", "99"]


def test_atomic_json_retries_transient_windows_replace_denial(tmp_path: Path, monkeypatch):
    path = tmp_path / "state.json"
    path.write_text('{"status":"old"}\n', encoding="utf-8")
    real_replace = Path.replace
    attempts = 0

    def flaky_replace(source: Path, target: Path):
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise PermissionError(5, "Access is denied", str(target))
        return real_replace(source, target)

    monkeypatch.setattr(Path, "replace", flaky_replace)
    atomic_json(path, {"status": "running"})

    assert attempts == 3
    assert json.loads(path.read_text(encoding="utf-8")) == {"status": "running"}


def test_latest_capture_skips_partial_tail_line():
    complete = json.dumps({"event": "combat_capture", "payload": {"wave": 3}})
    assert latest_capture([complete, '{"event":"combat_capture"']) == {
        "event": "combat_capture",
        "payload": {"wave": 3},
    }


def test_read_json_when_ready_retries_partial_summary(tmp_path: Path, monkeypatch):
    path = tmp_path / "summary.json"
    path.write_text("", encoding="utf-8")
    real_read_text = Path.read_text
    reads = 0

    def completing_read_text(source: Path, *args, **kwargs):
        nonlocal reads
        reads += 1
        if source == path and reads == 2:
            source.write_text('{"result":"victory"}\n', encoding="utf-8")
        return real_read_text(source, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", completing_read_text)

    assert read_json_when_ready(path, timeout_sec=0.2, poll_sec=0.001) == {
        "result": "victory"
    }
    assert reads == 2


def test_launch_game_uses_steam_route(tmp_path: Path, monkeypatch):
    calls: list[list[str]] = []
    monkeypatch.setattr(
        "scripts.wp2_collect_teacher.subprocess.check_call",
        lambda command: calls.append(command),
    )

    launch_game(tmp_path)

    assert calls == [
        [
            sys.executable,
            str(tmp_path / "scripts" / "launch_benchmark.py"),
        ]
    ]


def test_summary_fault_accepts_clean_current_terminal_summary():
    summary = {
        "policy_version": "teacher_v1-0.1.110-gun-wp1",
        "mod_version": "0.2.18-wp2-capture",
        "telemetry_complete": True,
        "errors": 0,
        "hangs": 0,
        "illegal_actions": 0,
        "result": "defeat",
    }
    assert summary_fault(summary) is None
    summary["errors"] = 1
    assert summary_fault(summary) == "errors=1"
