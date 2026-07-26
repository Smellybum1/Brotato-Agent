"""The mod-ready sentinel: positive proof the mod actually installed.

Motivation is recorded in reports/wp2/v127_deploy_record.md. A GDScript parse
error stops ModLoader installing ANY of the mod; the game then launches normally
and sits on the title screen. "Brotato is running" is therefore not evidence that
the agent exists, and a collector that only waits for a run directory will poll a
title screen until its stale timeout. These tests pin the two halves of the fix.
"""
import json
from pathlib import Path

import pytest

from scripts import wp2_collect_teacher as collector


ROOT = Path(__file__).resolve().parents[2]
CONTROLLER = ROOT / "mod/mods-unpacked/Tom-BrotatoAgent/runtime/agent_controller.gd"


# ── mod side ──────────────────────────────────────────────────────────────────

def test_controller_writes_sentinel_from_ready():
    src = CONTROLLER.read_text(encoding="utf-8")
    assert 'const _MOD_READY_PATH := "user://brotato_agent/mod_ready.json"' in src
    assert "_write_mod_ready()" in src
    assert "func _write_mod_ready() -> void:" in src
    # Must be called from _ready, i.e. only once the mod has actually installed.
    ready_body = src[src.index("func _ready() -> void:"):src.index("func _write_mod_ready()")]
    assert "_write_mod_ready()" in ready_body


def test_sentinel_carries_full_identity():
    src = CONTROLLER.read_text(encoding="utf-8")
    body = src[src.index("func _write_mod_ready() -> void:"):]
    body = body[:body.index("\n\nfunc ")] if "\n\nfunc " in body else body
    for key in ('"policy_version"', '"mod_version"', '"capture_schema_hash"'):
        assert key in body, f"sentinel must carry {key} so a wrong build fails loudly"


def test_mod_version_is_single_sourced():
    # The identity in the sentinel and the identity stamped into run meta must be
    # the same constant, or they can drift and the guard silently checks nothing.
    src = CONTROLLER.read_text(encoding="utf-8")
    assert 'const MOD_VERSION := "0.2.38-wp2-capture"' in src
    assert src.count('"0.2.38-wp2-capture"') == 1, "mod version literal must appear once"
    assert '"mod_version": MOD_VERSION,' in src


# ── collector side ────────────────────────────────────────────────────────────

@pytest.fixture
def sentinel(tmp_path, monkeypatch):
    path = tmp_path / "mod_ready.json"
    monkeypatch.setattr(collector, "mod_ready_path", lambda: path)
    return path


def _good_payload():
    return {
        "ready": True,
        "policy_version": collector.POLICY_VERSION,
        "mod_version": collector.MOD_VERSION,
        "capture_schema_hash": collector.CAPTURE_SCHEMA_HASH,
    }


def test_await_accepts_matching_sentinel(sentinel):
    sentinel.write_text(json.dumps(_good_payload()), encoding="utf-8")
    assert collector.await_mod_ready(timeout_sec=1.0, poll_sec=0.01) is None


def test_await_reports_fault_when_sentinel_never_appears(sentinel):
    # THE regression: mod failed to parse, game is up, nothing ever installs.
    fault = collector.await_mod_ready(timeout_sec=0.3, poll_sec=0.05)
    assert fault is not None
    assert "never reported ready" in fault
    assert "modloader" in fault.lower(), "fault must point at the log that explains it"


@pytest.mark.parametrize("field, bad", [
    ("policy_version", "teacher_v1-0.1.125-gun-wp1"),
    ("mod_version", "0.2.34-wp2-capture"),
    ("capture_schema_hash", "95B6444796A21FD44E94113B75BA2097BC381D5F72ED784F9B9A4A99DD46D951"),
])
def test_await_rejects_stale_or_wrong_build(sentinel, field, bad):
    payload = _good_payload()
    payload[field] = bad
    sentinel.write_text(json.dumps(payload), encoding="utf-8")
    fault = collector.await_mod_ready(timeout_sec=0.3, poll_sec=0.05)
    assert fault is not None and "mismatch" in fault


def test_await_tolerates_a_partially_written_sentinel(sentinel):
    # The mod writes this file while the collector is polling; a torn read must
    # retry rather than crash or be treated as a mismatch.
    sentinel.write_text('{"ready": true, "policy_ver', encoding="utf-8")
    fault = collector.await_mod_ready(timeout_sec=0.3, poll_sec=0.05)
    assert fault is not None and "never reported ready" in fault


def test_clear_removes_stale_sentinel_and_tolerates_absence(sentinel):
    sentinel.write_text(json.dumps(_good_payload()), encoding="utf-8")
    collector.clear_mod_ready()
    assert not sentinel.exists()
    collector.clear_mod_ready()  # must not raise when already gone


def test_launch_clears_before_starting():
    # Ordering matters: clearing AFTER launch would delete the real signal, and
    # not clearing at all would let a previous launch's sentinel satisfy the gate.
    src = Path(collector.__file__).read_text(encoding="utf-8")
    body = src[src.index("def launch_game("):]
    body = body[:body.index("\n\ndef ")]
    assert body.index("clear_mod_ready()") < body.index("launch_benchmark.py")
