"""The capture-schema pin is an ACCEPT-LIST, and it is still strict.

Pins that BOTH the pre-v127 and v127 capture hashes are accepted by the encoder
and by the sidecar handshake, and that an unknown hash is still REJECTED in both
places (the guard must not become permissive in general).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from trainer.bridge.sidecar import ServiceIdentity
from trainer.observation.encoder_v1 import (
    ObservationError,
    accepted_capture_hashes,
    load_capture_accept_list,
    load_schema,
)

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "configs" / "wp2" / "observation_v1.yaml"
ACCEPT_PATH = ROOT / "configs" / "wp2" / "capture_schema_accept_v1.yaml"

PRE_V127 = "95B6444796A21FD44E94113B75BA2097BC381D5F72ED784F9B9A4A99DD46D951"
V127 = "2823CB7E7D6A6DDB7F805A76D0CD674BA7A2A908058771B66B4A8FEFF9BC1174"
UNKNOWN = "0" * 64


def test_observation_schema_still_pins_the_pre_v127_hash_as_primary():
    """The dataset manifests read this key; it must NOT have been swapped."""
    schema = load_schema(SCHEMA_PATH)
    assert schema["source_capture_schema_hash"] == PRE_V127


def test_accept_list_file_holds_both_hashes():
    assert ACCEPT_PATH.is_file()
    assert set(load_capture_accept_list(SCHEMA_PATH)) == {PRE_V127, V127}


def test_accepted_capture_hashes_contains_both_and_not_an_unknown():
    accepted = accepted_capture_hashes(load_schema(SCHEMA_PATH))
    assert PRE_V127 in accepted
    assert V127 in accepted
    assert UNKNOWN not in accepted
    assert len(accepted) == 2


def test_accepted_capture_hashes_falls_back_to_the_single_pin():
    """A hand-built schema with no accept-list keeps the old single-hash behaviour."""
    assert accepted_capture_hashes({"source_capture_schema_hash": "PINNED"}) == ("PINNED",)


def test_encoder_accepts_both_hashes_and_rejects_an_unknown_one():
    schema = load_schema(SCHEMA_PATH)
    from trainer.observation import encoder_v1

    seen: list[str] = []

    def fake_globals(payload, schema_, temporal_valid):
        seen.append(payload["capture_schema_hash"])
        raise ObservationError("sentinel: hash gate passed")

    original = encoder_v1._global_values
    encoder_v1._global_values = fake_globals
    try:
        for accepted in (PRE_V127, V127):
            payload = {
                "capture_schema_hash": accepted,
                "player": {},
                "arena": {},
                "teacher": {},
                "entities": {},
                "control_dt_ms": 50,
            }
            with pytest.raises(ObservationError, match="sentinel"):
                encoder_v1.encode_capture(payload, schema)
        payload = {
            "capture_schema_hash": UNKNOWN,
            "player": {},
            "arena": {},
            "teacher": {},
            "entities": {},
            "control_dt_ms": 50,
        }
        with pytest.raises(ObservationError, match="capture schema hash mismatch"):
            encoder_v1.encode_capture(payload, schema)
    finally:
        encoder_v1._global_values = original

    assert seen == [PRE_V127, V127]


def _identity(**kwargs) -> ServiceIdentity:
    base = dict(
        schema_id="combat_obs_v1",
        observation_schema_hash="H",
        input_config_sha256="I",
        model_sha256="M",
        normalization_sha256="N",
        registry_run_name="R",
        source_capture_schema_hash=PRE_V127,
    )
    base.update(kwargs)
    return ServiceIdentity(**base)


def test_service_identity_accepts_both_hashes():
    identity = _identity(accepted_capture_schema_hashes=(PRE_V127, V127))
    assert identity.accepts_capture_hash(PRE_V127)
    assert identity.accepts_capture_hash(V127)
    assert identity.accepts_capture_hash(V127.lower())
    assert not identity.accepts_capture_hash(UNKNOWN)


def test_service_identity_without_accept_list_is_primary_only():
    identity = _identity()
    assert identity.accepts_capture_hash(PRE_V127)
    assert not identity.accepts_capture_hash(V127)


def test_handshake_accepts_both_hashes_and_still_rejects_unknown(tmp_path):
    """End-to-end over the REAL handshake, using the sidecar test harness."""
    from trainer.bridge.protocol import frame_type
    from trainer.bridge import protocol
    from tests.unit.test_student_sidecar import FakeModelService, _Harness, _handshake

    identity = ServiceIdentity(
        schema_id="combat_obs_v1",
        observation_schema_hash="SCHEMA",
        input_config_sha256="INPUT",
        model_sha256="M",
        normalization_sha256="NORM",
        registry_run_name="fake_run",
        source_capture_schema_hash=PRE_V127,
        accepted_capture_schema_hashes=(PRE_V127, V127),
    )
    for accepted in (PRE_V127, V127):
        with _Harness(FakeModelService(identity=identity), tmp_path / accepted[:8]) as h:
            c = h.client()
            ack = _handshake(c, capture_schema_hash=accepted)
            assert frame_type(ack) == protocol.MSG_HELLO_ACK, (accepted, ack)
            c.close()

    with _Harness(FakeModelService(identity=identity), tmp_path / "unknown") as h:
        c = h.client()
        reply = _handshake(c, capture_schema_hash=UNKNOWN)
        assert frame_type(reply) == protocol.MSG_ERROR
        assert reply["reason"] == "capture_schema_hash_mismatch"
        c.close()
