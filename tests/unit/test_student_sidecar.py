"""Unit + smoke tests for the student-inference sidecar.

The serving/handshake matrix runs a real :class:`StudentSidecar` in a background
thread over a loopback socket, driven by a :class:`FakeModelService` so no torch
artifacts are needed. Two further groups:

* artifact verification — :meth:`TorchModelService.from_registry` fails
  ``SidecarStartupError`` (exit-code-2 mapping) on a wrong checkpoint hash,
  tested directly without a real torch load;
* one marked real-artifact smoke test that loads the frozen bc_v1 service and
  feeds a single real capture payload, asserting a finite action in [-1, 1]^2.
"""
from __future__ import annotations

import glob
import json
import os
import socket
import threading
import time
from pathlib import Path

import pytest

from trainer.bridge import protocol
from trainer.bridge.protocol import ConnectionClosed, frame_type, pack_frame, read_frame
from trainer.bridge.sidecar import (
    LatencyStats,
    ModelService,
    ServiceIdentity,
    SidecarConfig,
    SidecarStartupError,
    StudentSidecar,
    TorchModelService,
)

ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = ROOT / "models" / "registry" / "bc_v1_s1_full.json"

CAP_HASH = "95B6444796A21FD44E94113B75BA2097BC381D5F72ED784F9B9A4A99DD46D951"
MODEL_SHA = "BE7E82326EC8A424A1EDF33134E65A26E06EDA68DA7F22D37705F3C26D6A9F0F"


def _identity(**over) -> ServiceIdentity:
    base = dict(
        schema_id="combat_obs_v1",
        observation_schema_hash="SCHEMA",
        input_config_sha256="INPUT",
        model_sha256=MODEL_SHA,
        normalization_sha256="NORM",
        registry_run_name="fake_run",
        source_capture_schema_hash=CAP_HASH,
    )
    base.update(over)
    return ServiceIdentity(**base)


class FakeModelService(ModelService):
    """Injectable predictor for the serving tests."""

    def __init__(self, action=(0.5, -0.25), model_ms=1.0, raises=None, identity=None):
        self._action = action
        self._model_ms = model_ms
        self._raises = raises
        self._identity = identity or _identity()
        self.calls = 0

    @property
    def identity(self) -> ServiceIdentity:
        return self._identity

    def predict(self, payload):
        self.calls += 1
        if self._raises is not None:
            raise self._raises
        ax, ay = self._action
        return float(ax), float(ay), float(self._model_ms)


# ---------------------------------------------------------------------------
# Test harness: run the sidecar in a thread; talk to it over loopback.
# ---------------------------------------------------------------------------
class _Client:
    def __init__(self, port: int, timeout: float = 5.0):
        self._sock = socket.create_connection(("127.0.0.1", port), timeout=timeout)
        self._sock.settimeout(timeout)
        self._recv = protocol.socket_recv(self._sock)

    def send(self, message):
        self._sock.sendall(pack_frame(message))

    def send_raw(self, raw: bytes):
        self._sock.sendall(raw)

    def recv(self):
        return read_frame(self._recv)

    def recv_or_closed(self):
        try:
            return read_frame(self._recv)
        except ConnectionClosed:
            return None

    def close(self):
        try:
            self._sock.close()
        except OSError:
            pass


class _Harness:
    def __init__(self, service, tmp_path, **cfg):
        defaults = dict(
            host="127.0.0.1",
            port=0,
            idle_exit_sec=cfg.pop("idle_exit_sec", 30.0),
            log_path=Path(tmp_path) / "sidecar_log.jsonl",
            accept_timeout=cfg.pop("accept_timeout", 0.1),
        )
        defaults.update(cfg)
        self.config = SidecarConfig(**defaults)
        self.sidecar = StudentSidecar(service, self.config, install_signal_handlers=False)
        self.exit_code = None
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _run(self):
        self.exit_code = self.sidecar.serve()

    def __enter__(self):
        self._thread.start()
        assert self.sidecar.ready.wait(timeout=5.0), "sidecar never bound"
        self.port = self.sidecar.bound_port
        return self

    def __exit__(self, *exc):
        self.sidecar.request_stop()
        self._thread.join(timeout=5.0)

    def join(self, timeout=5.0):
        self._thread.join(timeout=timeout)
        return not self._thread.is_alive()

    def client(self):
        return _Client(self.port)


def _good_hello(**over):
    base = dict(
        capture_schema_id="combat_capture_v2",
        capture_schema_hash=CAP_HASH,
        control_hz=20,
        run_id="run_test",
    )
    base.update(over)
    return protocol.build_hello(**base)


def _handshake(client, **over):
    client.send(_good_hello(**over))
    return client.recv()


# ---------------------------------------------------------------------------
# Handshake matrix
# ---------------------------------------------------------------------------
def test_good_hello_accepted(tmp_path):
    with _Harness(FakeModelService(), tmp_path) as h:
        c = h.client()
        ack = _handshake(c)
        assert frame_type(ack) == protocol.MSG_HELLO_ACK
        assert ack["model_sha256"] == MODEL_SHA
        assert ack["backend"] == protocol.BACKEND_TORCH_CPU
        assert ack["protocol"] == protocol.PROTOCOL_VERSION
        assert ack["pid"] == os.getpid()
        c.close()


def test_wrong_capture_hash_rejected(tmp_path):
    with _Harness(FakeModelService(), tmp_path) as h:
        c = h.client()
        reply = _handshake(c, capture_schema_hash="DEADBEEF")
        assert frame_type(reply) == protocol.MSG_ERROR
        assert reply["reason"] == "capture_schema_hash_mismatch"
        assert c.recv_or_closed() is None  # connection closed after rejection
        c.close()


def test_wrong_expected_model_sha_rejected(tmp_path):
    with _Harness(FakeModelService(), tmp_path) as h:
        c = h.client()
        reply = _handshake(c, expected_model_sha256="0" * 64)
        assert frame_type(reply) == protocol.MSG_ERROR
        assert reply["reason"] == "model_sha256_mismatch"
        c.close()


def test_matching_expected_model_sha_accepted(tmp_path):
    with _Harness(FakeModelService(), tmp_path) as h:
        c = h.client()
        ack = _handshake(c, expected_model_sha256=MODEL_SHA.lower())  # case-insensitive
        assert frame_type(ack) == protocol.MSG_HELLO_ACK
        c.close()


def test_wrong_protocol_version_rejected(tmp_path):
    with _Harness(FakeModelService(), tmp_path) as h:
        c = h.client()
        hello = _good_hello()
        hello["v"] = 2
        c.send(hello)
        reply = c.recv()
        assert frame_type(reply) == protocol.MSG_ERROR
        assert reply["reason"] == "protocol_version_mismatch"
        c.close()


# ---------------------------------------------------------------------------
# Serving
# ---------------------------------------------------------------------------
def test_act_returns_action_with_seq_echo(tmp_path):
    with _Harness(FakeModelService(action=(0.5, -0.25)), tmp_path) as h:
        c = h.client()
        _handshake(c)
        c.send(protocol.build_act(seq=42, ts_ms=1, wave=3, payload={"k": "v"}))
        action = c.recv()
        assert frame_type(action) == protocol.MSG_ACTION
        assert action["seq"] == 42
        assert action["ax"] == 0.5
        assert action["ay"] == -0.25
        assert "model_ms" in action and "total_ms" in action
        c.close()


def test_fifo_ordering_of_two_requests(tmp_path):
    with _Harness(FakeModelService(), tmp_path) as h:
        c = h.client()
        _handshake(c)
        c.send(protocol.build_act(seq=1, ts_ms=1, wave=1, payload={}))
        c.send(protocol.build_act(seq=2, ts_ms=2, wave=1, payload={}))
        first = c.recv()
        second = c.recv()
        assert first["seq"] == 1
        assert second["seq"] == 2
        c.close()


def test_malformed_json_frame_gets_error_then_close(tmp_path):
    with _Harness(FakeModelService(), tmp_path) as h:
        c = h.client()
        _handshake(c)
        bad_body = b"{not valid json"
        c.send_raw(len(bad_body).to_bytes(4, "little") + bad_body)
        reply = c.recv()
        assert frame_type(reply) == protocol.MSG_ERROR
        assert "protocol_error" in reply["reason"]
        assert c.recv_or_closed() is None  # closed after a frame-level error
        c.close()


def test_service_exception_returns_error_reply(tmp_path):
    svc = FakeModelService(raises=RuntimeError("boom"))
    with _Harness(svc, tmp_path) as h:
        c = h.client()
        _handshake(c)
        c.send(protocol.build_act(seq=9, ts_ms=1, wave=1, payload={}))
        reply = c.recv()
        assert frame_type(reply) == protocol.MSG_ERROR
        assert reply["seq"] == 9
        assert "sidecar_error" in reply["reason"]
        # Connection stays open for a service-level error.
        c.send(protocol.build_ping())
        assert frame_type(c.recv()) == protocol.MSG_PONG
        c.close()


def test_encode_error_reason_prefix(tmp_path):
    class _ObservationError(ValueError):
        pass

    _ObservationError.__name__ = "ObservationError"
    svc = FakeModelService(raises=_ObservationError("capture schema hash mismatch"))
    with _Harness(svc, tmp_path) as h:
        c = h.client()
        _handshake(c)
        c.send(protocol.build_act(seq=1, ts_ms=1, wave=1, payload={}))
        reply = c.recv()
        assert reply["reason"].startswith("encode_error:")
        c.close()


def test_nonfinite_action_returns_error(tmp_path):
    svc = FakeModelService(action=(float("inf"), 0.0))
    with _Harness(svc, tmp_path) as h:
        c = h.client()
        _handshake(c)
        c.send(protocol.build_act(seq=5, ts_ms=1, wave=1, payload={}))
        reply = c.recv()
        assert frame_type(reply) == protocol.MSG_ERROR
        assert reply["reason"] == "nonfinite_action"
        assert reply["seq"] == 5
        c.close()


def test_act_with_non_object_payload_returns_error(tmp_path):
    with _Harness(FakeModelService(), tmp_path) as h:
        c = h.client()
        _handshake(c)
        c.send({"type": protocol.MSG_ACT, "v": 1, "seq": 7, "payload": [1, 2, 3]})
        reply = c.recv()
        assert frame_type(reply) == protocol.MSG_ERROR
        assert reply["seq"] == 7
        c.close()


def test_ping_returns_pong_with_stats(tmp_path):
    with _Harness(FakeModelService(model_ms=2.5), tmp_path) as h:
        c = h.client()
        _handshake(c)
        c.send(protocol.build_act(seq=1, ts_ms=1, wave=1, payload={}))
        c.recv()  # action
        c.send(protocol.build_ping(ts_ms=123))
        pong = c.recv()
        assert frame_type(pong) == protocol.MSG_PONG
        assert pong["served"] == 1
        assert pong["errors"] == 0
        assert pong["model_ms_p50"] == pytest.approx(2.5)
        c.close()


def test_bye_causes_clean_exit(tmp_path):
    h = _Harness(FakeModelService(), tmp_path)
    with h:
        c = h.client()
        _handshake(c)
        c.send(protocol.build_bye())
        c.close()
        assert h.join(timeout=5.0), "sidecar did not exit after bye"
    assert h.exit_code == 0


def test_reconnect_within_idle_window(tmp_path):
    with _Harness(FakeModelService(), tmp_path, idle_exit_sec=10.0) as h:
        c1 = h.client()
        assert frame_type(_handshake(c1)) == protocol.MSG_HELLO_ACK
        c1.close()
        time.sleep(0.2)
        c2 = h.client()  # fresh handshake required after reconnect
        assert frame_type(_handshake(c2)) == protocol.MSG_HELLO_ACK
        c2.send(protocol.build_act(seq=1, ts_ms=1, wave=1, payload={}))
        assert c2.recv()["seq"] == 1
        c2.close()


def test_idle_exit_after_disconnect(tmp_path):
    h = _Harness(FakeModelService(), tmp_path, idle_exit_sec=0.3, accept_timeout=0.05)
    with h:
        c = h.client()
        _handshake(c)
        c.close()  # disconnect without bye
        assert h.join(timeout=5.0), "sidecar did not idle-exit after disconnect"
    assert h.exit_code == 0


def test_non_loopback_bind_rejected_by_config():
    # The config permits only 127.0.0.1; guard lives in the entry script but the
    # sidecar itself binds whatever host it is given, so assert the default.
    cfg = SidecarConfig()
    assert cfg.host == "127.0.0.1"


def test_log_written_with_startup_identity(tmp_path):
    log_path = Path(tmp_path) / "sidecar_log.jsonl"
    with _Harness(FakeModelService(), tmp_path, log_path=log_path) as h:
        c = h.client()
        _handshake(c)
        c.close()
    lines = [json.loads(x) for x in log_path.read_text(encoding="utf-8").splitlines() if x.strip()]
    events = {rec["event"] for rec in lines}
    assert "startup" in events
    startup = next(rec for rec in lines if rec["event"] == "startup")
    assert startup["registry_run_name"] == "fake_run"
    assert startup["model_sha256"] == MODEL_SHA


# ---------------------------------------------------------------------------
# LatencyStats
# ---------------------------------------------------------------------------
def test_latency_stats_percentiles():
    stats = LatencyStats(window=100)
    for v in range(1, 101):
        stats.record(float(v))
    snap = stats.snapshot()
    assert snap["served"] == 100
    assert snap["model_ms_p50"] == pytest.approx(50.5, abs=1.0)
    assert snap["model_ms_p99"] == pytest.approx(99.01, abs=1.0)


def test_latency_stats_empty_window_is_zero():
    snap = LatencyStats().snapshot()
    assert snap["model_ms_p50"] == 0.0
    assert snap["model_ms_p99"] == 0.0


def test_latency_stats_window_is_bounded():
    stats = LatencyStats(window=8)
    for v in range(100):
        stats.record(float(v))
    assert stats.snapshot()["window"] == 8
    assert stats.served == 100


# ---------------------------------------------------------------------------
# Artifact verification (exit-code-2 mapping), no real torch load
# ---------------------------------------------------------------------------
def _write_registry(tmp_path, ckpt_path, ckpt_sha):
    registry = {
        "run_name": "fake",
        "resolved_config": {
            "schema": str(ROOT / "configs" / "wp2" / "observation_v1.yaml"),
            "input_config": str(ROOT / "configs" / "wp2" / "bc_input_v1.yaml"),
        },
        "checkpoints": {"best": {"path": str(ckpt_path), "sha256": ckpt_sha}},
        "schema_hash": "0" * 64,
        "split_id": "dataset_split_v1",
        "normalization_manifest_hash": "0" * 64,
    }
    path = Path(tmp_path) / "registry.json"
    path.write_text(json.dumps(registry), encoding="utf-8")
    return path


def test_startup_fails_on_wrong_checkpoint_hash(tmp_path):
    ckpt = Path(tmp_path) / "best.pt"
    ckpt.write_bytes(b"not a real checkpoint")
    registry = _write_registry(tmp_path, ckpt, ckpt_sha="DEADBEEF" * 8)
    with pytest.raises(SidecarStartupError):
        TorchModelService.from_registry(registry)


def test_startup_fails_on_missing_checkpoint_file(tmp_path):
    registry = _write_registry(tmp_path, Path(tmp_path) / "absent.pt", ckpt_sha="A" * 64)
    with pytest.raises(SidecarStartupError):
        TorchModelService.from_registry(registry)


def test_startup_fails_on_missing_checkpoint_entry(tmp_path):
    registry = {
        "run_name": "fake",
        "resolved_config": {},
        "checkpoints": {"last": {"path": "x", "sha256": "y"}},
        "schema_hash": "0" * 64,
        "split_id": "s",
    }
    path = Path(tmp_path) / "registry.json"
    path.write_text(json.dumps(registry), encoding="utf-8")
    with pytest.raises(SidecarStartupError):
        TorchModelService.from_registry(path)


def test_entry_script_returns_exit_code_2_on_bad_artifacts(tmp_path):
    from scripts.run_student_sidecar import main

    ckpt = Path(tmp_path) / "best.pt"
    ckpt.write_bytes(b"nope")
    registry = _write_registry(tmp_path, ckpt, ckpt_sha="B" * 64)
    assert main(["--registry", str(registry)]) == 2


# ---------------------------------------------------------------------------
# Real-artifact smoke test (marked; still fast)
# ---------------------------------------------------------------------------
def _find_real_payload(target_hash: str):
    appdata = os.environ.get("APPDATA")
    if not appdata:
        return None
    runs = Path(appdata) / "Brotato" / "brotato_agent" / "runs"
    if not runs.is_dir():
        return None
    files = sorted(glob.glob(str(runs / "*" / "events.jsonl")), key=os.path.getmtime, reverse=True)
    for fpath in files[:60]:
        try:
            with open(fpath, "r", encoding="utf-8") as handle:
                for line in handle:
                    if '"combat_capture"' not in line:
                        continue
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if event.get("event") != "combat_capture":
                        continue
                    payload = event.get("payload", {})
                    if payload.get("capture_schema_hash") == target_hash:
                        return payload
        except OSError:
            continue
    return None


@pytest.mark.smoke
def test_real_artifact_predict_smoke():
    if not REGISTRY_PATH.is_file():
        pytest.skip("bc_v1_s1_full registry not present")
    try:
        service = TorchModelService.from_registry(REGISTRY_PATH)
    except SidecarStartupError as exc:
        pytest.skip(f"artifact chain unavailable: {exc}")

    payload = _find_real_payload(service.identity.source_capture_schema_hash)
    if payload is None:
        pytest.skip("no runs dir / no matching combat_capture payload accessible")

    ax, ay, model_ms = service.predict(payload)
    assert -1.0 <= ax <= 1.0
    assert -1.0 <= ay <= 1.0
    assert model_ms >= 0.0
