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


def _mod_environment(tmp_path: Path, monkeypatch) -> Path:
    """Deployed-agent fixture: APPDATA tree, deploy stamp, and mod zip."""
    appdata = tmp_path / "appdata"
    (appdata / "Brotato" / "logs").mkdir(parents=True)
    monkeypatch.setenv("APPDATA", str(appdata))
    zip_path = tmp_path / "Tom-BrotatoAgent.zip"
    zip_path.write_bytes(b"zip")
    (tmp_path / ".deploy_stamp").write_text(
        json.dumps({"target": "agent", "zip": str(zip_path)}), encoding="utf-8"
    )
    return appdata / "Brotato"


def test_launch_game_uses_steam_route(tmp_path: Path, monkeypatch):
    _mod_environment(tmp_path, monkeypatch)
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


def test_launch_clears_modloader_latch_and_restores_wiped_profile(
    tmp_path: Path, monkeypatch
):
    # Frozen 2026-07-23 campaign incident: the collector's forced stop trips
    # ModLoader's "Mods are currently disabled" latch on the next boot, and
    # that disabled boot wipes mod_user_profiles.json's mod_list. The first
    # launch without a preceding deploy left Brotato modless on the title
    # screen with the collector waiting forever.
    brotato = _mod_environment(tmp_path, monkeypatch)
    (brotato / "logs" / "godot.log").write_text("stale", encoding="utf-8")
    profile_path = brotato / "mod_user_profiles.json"
    profile_path.write_text(
        json.dumps({"current_profile": "default", "profiles": {"default": {"mod_list": {}}}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "scripts.wp2_collect_teacher.subprocess.check_call", lambda command: None
    )

    launch_game(tmp_path)

    assert list((brotato / "logs").iterdir()) == []
    archives = list((tmp_path / "reports").glob("logs_archive_*"))
    assert archives and (archives[0] / "godot.log").read_text(encoding="utf-8") == "stale"
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    entry = profile["profiles"]["default"]["mod_list"]["Tom-BrotatoAgent"]
    assert entry["is_active"] is True
    assert entry["zip_path"].endswith("Tom-BrotatoAgent.zip")


def test_launch_preserves_healthy_profile(tmp_path: Path, monkeypatch):
    brotato = _mod_environment(tmp_path, monkeypatch)
    profile_path = brotato / "mod_user_profiles.json"
    healthy = {
        "current_profile": "default",
        "profiles": {
            "default": {
                "mod_list": {
                    "Tom-BrotatoAgent": {"is_active": True, "zip_path": "keep/me.zip"},
                    "Other-Mod": {"is_active": False, "zip_path": "other.zip"},
                }
            }
        },
    }
    profile_path.write_text(json.dumps(healthy), encoding="utf-8")
    monkeypatch.setattr(
        "scripts.wp2_collect_teacher.subprocess.check_call", lambda command: None
    )

    launch_game(tmp_path)

    assert json.loads(profile_path.read_text(encoding="utf-8")) == healthy


def test_summary_fault_accepts_clean_current_terminal_summary():
    summary = {
        "policy_version": "teacher_v1-0.1.129-gun-wp1",
        "mod_version": "0.2.79-wp2-capture",
        "telemetry_complete": True,
        "errors": 0,
        "hangs": 0,
        "illegal_actions": 0,
        "result": "defeat",
    }
    assert summary_fault(summary) is None
    summary["errors"] = 1
    assert summary_fault(summary) == "errors=1"
