"""Unit tests for the Stage F residual-probe serving mode (design §2, F-1).

Covers the rotation math (angle, magnitude preservation, zero-vector passthrough),
seeded delta reproducibility, the extended per-act log fields, entry-script mode
selection, and the no-torch-import guarantee for probe construction/inference.

The probe is pure numpy/stdlib: none of these tests load torch or a registry.
"""
from __future__ import annotations

import builtins
import json
import math
import socket
import threading
import time
from pathlib import Path

import pytest

from trainer.bridge import protocol
from trainer.bridge.protocol import frame_type, pack_frame, read_frame
from trainer.bridge.sidecar import (
    BACKEND_RESIDUAL_PROBE,
    RESIDUAL_PROBE_MODEL_SHA256,
    ResidualProbeService,
    SidecarConfig,
    StudentSidecar,
)

CAP_HASH = "95B6444796A21FD44E94113B75BA2097BC381D5F72ED784F9B9A4A99DD46D951"


def _payload(x: float, y: float) -> dict:
    return {"teacher": {"action": {"x": x, "y": y}}}


def _probe(seed: int = 1, theta_max_deg: float = 5.0) -> ResidualProbeService:
    return ResidualProbeService(
        theta_max_deg=theta_max_deg, seed=seed, capture_schema_hash=CAP_HASH
    )


# ---------------------------------------------------------------------------
# Rotation math
# ---------------------------------------------------------------------------
def test_reply_equals_rotation_by_logged_delta():
    svc = _probe(seed=7)
    tx, ty = 0.6, -0.8
    ax, ay, _ = svc.predict(_payload(tx, ty))
    delta_deg = svc.act_log_extra()["delta_deg"]
    theta = math.radians(delta_deg)
    ex = tx * math.cos(theta) - ty * math.sin(theta)
    ey = tx * math.sin(theta) + ty * math.cos(theta)
    # Reply is computed from the full-precision delta; the log rounds delta to 6
    # decimal degrees, so reconstruction matches to the replay-check tolerance.
    assert abs(ax - ex) <= 1e-6
    assert abs(ay - ey) <= 1e-6


def test_magnitude_preserved_unit_vector():
    svc = _probe(seed=3)
    for _ in range(200):
        ax, ay, _ = svc.predict(_payload(1.0, 0.0))
        assert abs(math.hypot(ax, ay) - 1.0) <= 1e-6


def test_magnitude_preserved_non_unit_vector():
    svc = _probe(seed=11)
    tx, ty = 3.0, 4.0  # magnitude 5
    for _ in range(200):
        ax, ay, _ = svc.predict(_payload(tx, ty))
        assert abs(math.hypot(ax, ay) - 5.0) <= 1e-6


def test_delta_within_theta_max_bound():
    svc = _probe(seed=5, theta_max_deg=5.0)
    for _ in range(5000):
        svc.predict(_payload(1.0, 0.0))
        d = svc.act_log_extra()["delta_deg"]
        assert -5.0 <= d <= 5.0


def test_zero_teacher_vector_passthrough():
    svc = _probe(seed=9)
    ax, ay, ms = svc.predict(_payload(0.0, 0.0))
    assert ax == 0.0 and ay == 0.0
    assert ms >= 0.0
    extra = svc.act_log_extra()
    assert extra["delta_deg"] is None
    assert extra["teacher_x"] == 0.0 and extra["teacher_y"] == 0.0


def test_zero_vector_consumes_no_random_draw():
    # A zero tick between two non-zero ticks must not advance the delta stream:
    # the sequence of non-zero deltas is identical whether or not a zero tick
    # is interleaved.
    a = _probe(seed=42)
    b = _probe(seed=42)
    a.predict(_payload(1.0, 0.0))
    d_a1 = a.act_log_extra()["delta_deg"]
    b.predict(_payload(1.0, 0.0))
    b.predict(_payload(0.0, 0.0))  # zero tick — must draw nothing
    d_b1 = b.act_log_extra()["delta_deg"]  # this is the zero-tick extra (None)
    assert d_b1 is None
    a.predict(_payload(1.0, 0.0))
    d_a2 = a.act_log_extra()["delta_deg"]
    b.predict(_payload(1.0, 0.0))
    d_b2 = b.act_log_extra()["delta_deg"]
    assert d_a1 == pytest.approx(d_b1 if d_b1 is not None else d_a1)
    assert d_a2 == pytest.approx(d_b2)


def test_malformed_teacher_raises():
    svc = _probe()
    with pytest.raises(ValueError):
        svc.predict({"teacher": {}})
    with pytest.raises(ValueError):
        svc.predict({})
    with pytest.raises(ValueError):
        svc.predict({"teacher": {"action": {"x": 1.0}}})


# ---------------------------------------------------------------------------
# Seeded reproducibility / determinism
# ---------------------------------------------------------------------------
def test_same_seed_reproduces_delta_stream():
    a = _probe(seed=1234)
    b = _probe(seed=1234)
    seq = [(0.6, -0.8), (1.0, 0.0), (-0.3, 0.95), (0.0, 0.0), (0.7, 0.7)]
    for tx, ty in seq:
        oa = a.predict(_payload(tx, ty))
        ob = b.predict(_payload(tx, ty))
        assert oa[0] == pytest.approx(ob[0], abs=0.0)
        assert oa[1] == pytest.approx(ob[1], abs=0.0)
        assert a.act_log_extra()["delta_deg"] == b.act_log_extra()["delta_deg"]


def test_different_seed_diverges():
    a = _probe(seed=1)
    b = _probe(seed=2)
    a.predict(_payload(1.0, 0.0))
    b.predict(_payload(1.0, 0.0))
    assert a.act_log_extra()["delta_deg"] != b.act_log_extra()["delta_deg"]


# ---------------------------------------------------------------------------
# Identity block
# ---------------------------------------------------------------------------
def test_identity_block():
    svc = _probe(seed=77, theta_max_deg=5.0)
    ident = svc.identity
    assert ident.backend == BACKEND_RESIDUAL_PROBE
    assert ident.model_sha256 == RESIDUAL_PROBE_MODEL_SHA256
    assert ident.source_capture_schema_hash == CAP_HASH.upper()
    assert "theta5" in ident.registry_run_name
    assert "seed77" in ident.registry_run_name
    # hello_ack carries the deterministic pin the mod matches case-insensitively.
    ack = ident.hello_ack(pid=1)
    assert ack["model_sha256"] == RESIDUAL_PROBE_MODEL_SHA256
    assert ack["backend"] == BACKEND_RESIDUAL_PROBE


# ---------------------------------------------------------------------------
# Extended act-log fields (served over a real loopback sidecar)
# ---------------------------------------------------------------------------
class _Harness:
    def __init__(self, service, tmp_path):
        self.log_path = Path(tmp_path) / "probe_log.jsonl"
        self.config = SidecarConfig(
            host="127.0.0.1", port=0, idle_exit_sec=30.0,
            log_path=self.log_path, accept_timeout=0.1,
        )
        self.sidecar = StudentSidecar(service, self.config, install_signal_handlers=False)
        self._thread = threading.Thread(target=self.sidecar.serve, daemon=True)

    def __enter__(self):
        self._thread.start()
        assert self.sidecar.ready.wait(timeout=5.0), "sidecar never bound"
        self.port = self.sidecar.bound_port
        return self

    def __exit__(self, *exc):
        self.sidecar.request_stop()
        self._thread.join(timeout=5.0)


def _handshake(sock, recv):
    sock.sendall(pack_frame(protocol.build_hello(
        capture_schema_id="combat_capture_v2", capture_schema_hash=CAP_HASH,
        control_hz=20, run_id="probe_test",
    )))
    return read_frame(recv)


def test_act_log_has_probe_fields(tmp_path):
    with _Harness(_probe(seed=21), tmp_path) as h:
        sock = socket.create_connection(("127.0.0.1", h.port), timeout=5.0)
        sock.settimeout(5.0)
        recv = protocol.socket_recv(sock)
        assert frame_type(_handshake(sock, recv)) == protocol.MSG_HELLO_ACK
        sock.sendall(pack_frame(protocol.build_act(
            seq=1, ts_ms=1, wave=3, payload=_payload(0.6, -0.8))))
        reply = read_frame(recv)
        assert frame_type(reply) == protocol.MSG_ACTION
        # zero-vector tick too
        sock.sendall(pack_frame(protocol.build_act(
            seq=2, ts_ms=2, wave=3, payload=_payload(0.0, 0.0))))
        assert frame_type(read_frame(recv)) == protocol.MSG_ACTION
        sock.close()
    lines = [json.loads(x) for x in h.log_path.read_text(encoding="utf-8").splitlines() if x.strip()]
    acts = [e for e in lines if e.get("event") == "act"]
    assert len(acts) == 2
    a1 = next(a for a in acts if a["seq"] == 1)
    assert "delta_deg" in a1 and "teacher_x" in a1 and "teacher_y" in a1
    assert a1["teacher_x"] == 0.6 and a1["teacher_y"] == -0.8
    assert -5.0 <= a1["delta_deg"] <= 5.0
    # reply == rotate(teacher, logged delta)
    theta = math.radians(a1["delta_deg"])
    ex = 0.6 * math.cos(theta) - (-0.8) * math.sin(theta)
    ey = 0.6 * math.sin(theta) + (-0.8) * math.cos(theta)
    assert abs(reply["ax"] - ex) <= 1e-5 and abs(reply["ay"] - ey) <= 1e-5
    a2 = next(a for a in acts if a["seq"] == 2)
    assert a2["delta_deg"] is None  # zero vector: no perturbation


# ---------------------------------------------------------------------------
# No torch import for probe mode
# ---------------------------------------------------------------------------
def test_probe_constructible_and_serves_without_torch(monkeypatch):
    real_import = builtins.__import__

    def blocked(name, *args, **kwargs):
        if name == "torch" or name.startswith("torch."):
            raise ImportError("torch is blocked for this test")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", blocked)
    # Prove torch is genuinely unimportable in this context.
    with pytest.raises(ImportError):
        __import__("torch")
    svc = _probe(seed=99)
    ax, ay, ms = svc.predict(_payload(1.0, 0.0))
    assert math.isfinite(ax) and math.isfinite(ay) and ms >= 0.0
    assert abs(math.hypot(ax, ay) - 1.0) <= 1e-6


# ---------------------------------------------------------------------------
# Entry-script mode selection (no torch / no registry in probe mode)
# ---------------------------------------------------------------------------
def test_entry_probe_mode_builds_residual_probe(monkeypatch):
    from scripts import run_student_sidecar as entry

    captured = {}

    class _FakeSidecar:
        def __init__(self, service, config):
            captured["service"] = service

        def serve(self):
            return 0

        def request_stop(self):
            pass

    monkeypatch.setattr(entry, "StudentSidecar", _FakeSidecar)
    rc = entry.main([
        "--mode", "residual-probe", "--probe-seed", "5",
        "--theta-max-deg", "5.0", "--port", "0",
    ])
    assert rc == 0
    svc = captured["service"]
    assert isinstance(svc, ResidualProbeService)
    assert svc.identity.backend == BACKEND_RESIDUAL_PROBE
    assert svc.identity.source_capture_schema_hash == CAP_HASH.upper()


def test_entry_probe_mode_requires_seed():
    from scripts.run_student_sidecar import main

    assert main(["--mode", "residual-probe", "--port", "0"]) == 1


def test_entry_default_mode_is_student():
    from scripts.run_student_sidecar import _parse_args

    args = _parse_args([])
    assert args.mode == "student"
    assert args.theta_max_deg == 5.0
    assert args.probe_seed is None
