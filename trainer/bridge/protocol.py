"""Protocol v1 frame codec + message schema for the student-inference bridge.

Wire format (architecture note §3.2), fixed by the Godot ``StreamPeer`` default
endianness:

    +-----------------------------+------------------------------------------+
    | 4-byte little-endian u32 N  | N bytes UTF-8 JSON object                 |
    +-----------------------------+------------------------------------------+

A frame is a single JSON object carrying at least ``{"type": <str>, "v": 1}``.
Frames larger than :data:`MAX_FRAME_BYTES` (1 MiB) are a protocol error on both
encode and decode. The codec is transport-agnostic: :func:`read_frame` drives an
arbitrary ``recv(n) -> bytes`` callable so it can be exercised on split /
partial reads without a socket.

Message types (all carry ``"v": PROTOCOL_VERSION``):

* ``hello``     mod -> side: handshake request + mod-side identity pins.
* ``hello_ack`` side -> mod: sidecar identity block.
* ``act``       mod -> side: one control-tick inference request (raw payload).
* ``action``    side -> mod: the inferred movement action.
* ``error``     side -> mod: a per-request or handshake failure with a reason.
* ``ping``/``pong`` heartbeat with rolling health stats.
* ``bye``       either direction: clean-shutdown notice.

This module owns *only* framing + the message dict shapes; all serving policy
lives in :mod:`trainer.bridge.sidecar`.
"""
from __future__ import annotations

import json
import struct
from typing import Any, Callable, Mapping

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
PROTOCOL_VERSION = 1
MAX_FRAME_BYTES = 1 << 20  # 1 MiB payload ceiling (oversize => protocol error)
LENGTH_PREFIX_BYTES = 4
#: Little-endian u32 length prefix, matching Godot StreamPeer default endianness.
LENGTH_STRUCT = struct.Struct("<I")
BACKEND_TORCH_CPU = "torch-cpu"

# Message type tags.
MSG_HELLO = "hello"
MSG_HELLO_ACK = "hello_ack"
MSG_ACT = "act"
MSG_ACTION = "action"
MSG_ERROR = "error"
MSG_PING = "ping"
MSG_PONG = "pong"
MSG_BYE = "bye"

Recv = Callable[[int], bytes]


class ProtocolError(RuntimeError):
    """Raised on a malformed, oversize, or non-conforming frame."""


class ConnectionClosed(ProtocolError):
    """Raised by :func:`read_frame` when the peer closes at a frame boundary.

    A subclass of :class:`ProtocolError` so callers may catch either, but
    distinguished so a clean disconnect (EOF before any byte of a new frame) is
    not confused with a corrupt/truncated frame mid-stream.
    """


# ---------------------------------------------------------------------------
# Frame codec
# ---------------------------------------------------------------------------
def pack_frame(message: Mapping[str, Any]) -> bytes:
    """Encode a message dict to a length-prefixed UTF-8 JSON frame.

    ``allow_nan=False`` keeps non-finite floats off the wire; oversize payloads
    raise :class:`ProtocolError` rather than emitting an unreadable frame.
    """
    try:
        body = json.dumps(message, separators=(",", ":"), allow_nan=False).encode("utf-8")
    except ValueError as exc:  # NaN/Inf or non-serializable content
        raise ProtocolError(f"frame not serializable: {exc}") from exc
    if len(body) > MAX_FRAME_BYTES:
        raise ProtocolError(
            f"frame of {len(body)} bytes exceeds max {MAX_FRAME_BYTES}"
        )
    return LENGTH_STRUCT.pack(len(body)) + body


def read_exactly(recv: Recv, count: int) -> bytes:
    """Read exactly ``count`` bytes from ``recv``, looping over partial reads.

    ``recv(n)`` must return up to ``n`` bytes, or ``b""`` at EOF. An EOF before
    the first byte raises :class:`ConnectionClosed`; an EOF mid-read raises
    :class:`ProtocolError` (truncated frame).
    """
    if count == 0:
        return b""
    chunks: list[bytes] = []
    remaining = count
    while remaining > 0:
        chunk = recv(remaining)
        if not chunk:
            if not chunks:
                raise ConnectionClosed("peer closed at frame boundary")
            raise ProtocolError(
                f"truncated frame: wanted {count} bytes, got {count - remaining}"
            )
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def read_frame(recv: Recv) -> dict[str, Any]:
    """Read and decode one frame from ``recv``.

    Raises :class:`ConnectionClosed` on a clean EOF, :class:`ProtocolError` on an
    oversize length prefix, truncation, invalid UTF-8/JSON, or a non-object
    payload.
    """
    prefix = read_exactly(recv, LENGTH_PREFIX_BYTES)
    (length,) = LENGTH_STRUCT.unpack(prefix)
    if length > MAX_FRAME_BYTES:
        raise ProtocolError(f"frame length {length} exceeds max {MAX_FRAME_BYTES}")
    body = read_exactly(recv, length)
    try:
        message = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProtocolError(f"invalid JSON frame: {exc}") from exc
    if not isinstance(message, dict):
        raise ProtocolError("frame payload is not a JSON object")
    return message


def socket_recv(sock: Any) -> Recv:
    """Adapt a socket to the ``recv(n) -> bytes`` callable :func:`read_frame` wants."""

    def _recv(count: int) -> bytes:
        return sock.recv(count)

    return _recv


def frame_type(message: Mapping[str, Any]) -> str:
    """Return a frame's ``type`` tag (``""`` if absent)."""
    return str(message.get("type", ""))


# ---------------------------------------------------------------------------
# Message builders (protocol v1)
# ---------------------------------------------------------------------------
def build_hello(
    *,
    capture_schema_id: str,
    capture_schema_hash: str,
    control_hz: int,
    run_id: str,
    expected_model_sha256: str | None = None,
) -> dict[str, Any]:
    """mod -> side handshake request. ``expected_model_sha256`` pins the deploy."""
    msg: dict[str, Any] = {
        "type": MSG_HELLO,
        "v": PROTOCOL_VERSION,
        "protocol": PROTOCOL_VERSION,
        "capture_schema_id": capture_schema_id,
        "capture_schema_hash": capture_schema_hash,
        "control_hz": int(control_hz),
        "run_id": run_id,
    }
    if expected_model_sha256:
        msg["expected_model_sha256"] = expected_model_sha256
    return msg


def build_hello_ack(
    *,
    schema_id: str,
    observation_schema_hash: str,
    input_config_sha256: str,
    model_sha256: str,
    normalization_sha256: str,
    registry_run_name: str,
    pid: int,
    backend: str = BACKEND_TORCH_CPU,
) -> dict[str, Any]:
    """side -> mod handshake acceptance carrying the full sidecar identity block."""
    return {
        "type": MSG_HELLO_ACK,
        "v": PROTOCOL_VERSION,
        "protocol": PROTOCOL_VERSION,
        "schema_id": schema_id,
        "observation_schema_hash": observation_schema_hash,
        "input_config_sha256": input_config_sha256,
        "model_sha256": model_sha256,
        "normalization_sha256": normalization_sha256,
        "registry_run_name": registry_run_name,
        "backend": backend,
        "pid": int(pid),
    }


def build_act(
    *, seq: int, ts_ms: int, wave: int, payload: Mapping[str, Any]
) -> dict[str, Any]:
    """mod -> side inference request for control tick ``seq``."""
    return {
        "type": MSG_ACT,
        "v": PROTOCOL_VERSION,
        "seq": int(seq),
        "ts_ms": int(ts_ms),
        "wave": int(wave),
        "payload": payload,
    }


def build_action(
    *, seq: int, ax: float, ay: float, model_ms: float, total_ms: float
) -> dict[str, Any]:
    """side -> mod inferred action for control tick ``seq``."""
    return {
        "type": MSG_ACTION,
        "v": PROTOCOL_VERSION,
        "seq": int(seq),
        "ax": float(ax),
        "ay": float(ay),
        "model_ms": float(model_ms),
        "total_ms": float(total_ms),
    }


def build_error(*, seq: int | None, reason: str) -> dict[str, Any]:
    """side -> mod failure notice. ``seq`` is ``None`` for handshake/frame errors."""
    return {
        "type": MSG_ERROR,
        "v": PROTOCOL_VERSION,
        "seq": seq,
        "reason": reason,
    }


def build_ping(*, ts_ms: int | None = None) -> dict[str, Any]:
    """mod -> side heartbeat."""
    msg: dict[str, Any] = {"type": MSG_PING, "v": PROTOCOL_VERSION}
    if ts_ms is not None:
        msg["ts_ms"] = int(ts_ms)
    return msg


def build_pong(
    *, served: int, errors: int, model_ms_p50: float, model_ms_p99: float
) -> dict[str, Any]:
    """side -> mod heartbeat reply carrying rolling health stats."""
    return {
        "type": MSG_PONG,
        "v": PROTOCOL_VERSION,
        "served": int(served),
        "errors": int(errors),
        "model_ms_p50": float(model_ms_p50),
        "model_ms_p99": float(model_ms_p99),
    }


def build_bye(*, reason: str = "shutdown") -> dict[str, Any]:
    """Clean-shutdown notice (either direction)."""
    return {"type": MSG_BYE, "v": PROTOCOL_VERSION, "reason": reason}
