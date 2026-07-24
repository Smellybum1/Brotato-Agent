"""Unit tests for the protocol-v1 frame codec + message schema.

Covers frame round-trip, split/partial reads, oversize rejection, explicit
little-endian on-wire bytes, and the message builders. Pure in-memory byte
streams — no sockets.
"""
from __future__ import annotations

import json
import struct

import pytest

from trainer.bridge import protocol
from trainer.bridge.protocol import (
    ConnectionClosed,
    MAX_FRAME_BYTES,
    PROTOCOL_VERSION,
    ProtocolError,
    frame_type,
    pack_frame,
    read_exactly,
    read_frame,
)


def _recv_from(data: bytes, chunk: int | None = None):
    """A ``recv(n)`` callable over an in-memory buffer.

    ``chunk`` caps how many bytes each call may return (to simulate the OS
    handing back short reads); ``None`` means "up to n".
    """
    buf = bytearray(data)

    def _recv(n: int) -> bytes:
        take = n if chunk is None else min(n, chunk)
        out = bytes(buf[:take])
        del buf[:take]
        return out

    return _recv


# ---------------------------------------------------------------------------
# Frame codec
# ---------------------------------------------------------------------------
def test_round_trip_preserves_message():
    msg = protocol.build_action(seq=7, ax=0.25, ay=-0.5, model_ms=1.2, total_ms=3.4)
    frame = pack_frame(msg)
    decoded = read_frame(_recv_from(frame))
    assert decoded == msg


def test_length_prefix_is_little_endian_on_wire():
    # 260-byte body -> LE prefix b"\x04\x01\x00\x00"; big-endian would be \x00\x00\x01\x04.
    body = {"type": "x", "pad": "a" * 239}
    raw = json.dumps(body, separators=(",", ":"), allow_nan=False).encode("utf-8")
    assert len(raw) == 260
    frame = pack_frame(body)
    prefix = frame[:4]
    assert prefix == struct.pack("<I", 260)
    assert prefix == b"\x04\x01\x00\x00"
    assert prefix != struct.pack(">I", 260)
    # And the declared length matches the body length exactly.
    (declared,) = struct.unpack("<I", prefix)
    assert declared == len(frame) - 4


def test_split_reads_reassemble_frame():
    frame = pack_frame(protocol.build_ping(ts_ms=99))
    # One byte at a time — exercises the read_exactly loop over the prefix and body.
    decoded = read_frame(_recv_from(frame, chunk=1))
    assert frame_type(decoded) == protocol.MSG_PING
    assert decoded["ts_ms"] == 99


def test_partial_prefix_then_eof_is_truncation_error():
    with pytest.raises(ProtocolError):
        read_exactly(_recv_from(b"\x04\x01"), 4)


def test_eof_at_frame_boundary_is_connection_closed():
    with pytest.raises(ConnectionClosed):
        read_frame(_recv_from(b""))


def test_truncated_body_raises_protocol_error():
    frame = pack_frame(protocol.build_bye())
    with pytest.raises(ProtocolError):
        read_frame(_recv_from(frame[:-1]))  # drop last body byte


def test_oversize_declared_length_rejected_on_decode():
    # A hand-built prefix declaring > 1 MiB must be rejected before reading a body.
    prefix = struct.pack("<I", MAX_FRAME_BYTES + 1)
    with pytest.raises(ProtocolError):
        read_frame(_recv_from(prefix + b"{}"))


def test_oversize_payload_rejected_on_encode():
    huge = {"type": "act", "v": 1, "payload": {"blob": "x" * (MAX_FRAME_BYTES + 10)}}
    with pytest.raises(ProtocolError):
        pack_frame(huge)


def test_non_object_frame_rejected():
    raw = b"[1,2,3]"
    frame = struct.pack("<I", len(raw)) + raw
    with pytest.raises(ProtocolError):
        read_frame(_recv_from(frame))


def test_invalid_json_frame_rejected():
    raw = b"{not json"
    frame = struct.pack("<I", len(raw)) + raw
    with pytest.raises(ProtocolError):
        read_frame(_recv_from(frame))


def test_nan_action_refused_on_encode():
    with pytest.raises(ProtocolError):
        pack_frame(protocol.build_action(seq=1, ax=float("nan"), ay=0.0, model_ms=1.0, total_ms=1.0))


def test_read_exactly_zero_returns_empty():
    assert read_exactly(_recv_from(b""), 0) == b""


# ---------------------------------------------------------------------------
# Message builders
# ---------------------------------------------------------------------------
def test_hello_includes_expected_model_only_when_given():
    without = protocol.build_hello(
        capture_schema_id="combat_capture_v2",
        capture_schema_hash="ABC",
        control_hz=20,
        run_id="run_x",
    )
    assert "expected_model_sha256" not in without
    assert without["v"] == PROTOCOL_VERSION
    assert without["type"] == protocol.MSG_HELLO

    with_pin = protocol.build_hello(
        capture_schema_id="combat_capture_v2",
        capture_schema_hash="ABC",
        control_hz=20,
        run_id="run_x",
        expected_model_sha256="DEAD",
    )
    assert with_pin["expected_model_sha256"] == "DEAD"


def test_hello_ack_carries_full_identity_block():
    ack = protocol.build_hello_ack(
        schema_id="combat_obs_v1",
        observation_schema_hash="SCHEMA",
        input_config_sha256="INPUT",
        model_sha256="MODEL",
        normalization_sha256="NORM",
        registry_run_name="bc_v1_s1_full",
        pid=1234,
    )
    for key in (
        "schema_id",
        "observation_schema_hash",
        "input_config_sha256",
        "model_sha256",
        "normalization_sha256",
        "registry_run_name",
        "backend",
        "pid",
    ):
        assert key in ack
    assert ack["backend"] == protocol.BACKEND_TORCH_CPU
    assert ack["protocol"] == PROTOCOL_VERSION
    assert ack["v"] == PROTOCOL_VERSION


def test_error_seq_may_be_none():
    err = protocol.build_error(seq=None, reason="handshake")
    assert err["seq"] is None
    assert err["reason"] == "handshake"


def test_pong_carries_health_stats():
    pong = protocol.build_pong(served=10, errors=1, model_ms_p50=1.5, model_ms_p99=9.0)
    assert pong["served"] == 10
    assert pong["errors"] == 1
    assert pong["model_ms_p50"] == 1.5
    assert pong["model_ms_p99"] == 9.0


def test_act_round_trip_carries_payload():
    payload = {"capture_schema_hash": "H", "player": {"x": 1.0}}
    act = protocol.build_act(seq=3, ts_ms=1000, wave=5, payload=payload)
    decoded = read_frame(_recv_from(pack_frame(act)))
    assert decoded["payload"] == payload
    assert decoded["seq"] == 3
    assert decoded["wave"] == 5
