"""Loopback IPC bridge for the WP2 M3 student-inference path (packet §9.1).

Two modules, one concern each:

* :mod:`trainer.bridge.protocol` — the versioned, length-prefixed JSON frame
  codec plus the protocol-v1 message schema (hello / hello_ack / act / action /
  error / ping / pong / bye). Pure and transport-agnostic; unit-testable on
  in-memory byte streams.
* :mod:`trainer.bridge.sidecar` — the single-client loopback TCP server that
  loads/verifies the frozen bc_v1 artifact chain, performs the handshake, and
  serves ``act`` requests through an injectable model service.

The Godot side (``learned/combat_bridge.gd`` et al.) is owned by another agent
and only shares the wire contract documented in ``docs/IPC_PROTOCOL.md``.
"""
from __future__ import annotations

from trainer.bridge.protocol import (
    ConnectionClosed,
    PROTOCOL_VERSION,
    ProtocolError,
    frame_type,
)

__all__ = [
    "ConnectionClosed",
    "PROTOCOL_VERSION",
    "ProtocolError",
    "frame_type",
]
