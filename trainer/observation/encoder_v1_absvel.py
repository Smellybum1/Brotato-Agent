"""``combat_obs_v1`` encoder variant: ABSOLUTE entity velocity.

WHY THIS EXISTS -- the human-label leak, third attempt.

In a ``human_movement`` run the player's measured velocity IS the human's
keyboard vector one control tick delayed. ``encoder_v1`` writes entity channels
2,3 as velocity RELATIVE to the player::

    rvx = entity.vx - player.vx          # encoder_v1.py:161-162

For a STATIC object (material, crate, obstacle) ``entity.vx == 0``, so channel 2
is exactly ``-player.vx / entity_speed`` -- a verbatim copy of the label, sitting
in the entity block after globals 6,7 were masked out. Measured: the static-group
pooled channel scored cosine **0.9857** against the human action.

The previous remedy was to ABLATE channels {2,3,11,12,13}. That closed the leak
but also destroyed genuine state: enemy relative velocity is real, decision-
relevant information, so the resulting 0.2689 agreement is a LOWER bound.

This variant closes the leak WITHOUT destroying that information, because
absolute entity velocity is recoverable from quantities the encoder already
holds::

    entity.v = relative.v + player.v

Channels 2,3 become ``entity.vx / entity_speed`` and ``entity.vy / entity_speed``.
A static object now reads exactly ``0.0`` instead of ``-player.v`` -- which is
precisely the leak channel closing -- while a moving enemy still reports its own
motion.

NORMALISATION / SCALE (checked, not assumed)
--------------------------------------------
Entity channels 2,3 are divided by ``normalization.entity_speed`` (1000.0, a
schema constant). Globals 6,7 are divided by ``player.speed`` (a PER-ROW stat,
base 472 for the human runs). The two terms therefore do NOT share a scale, and
they are 2.1x apart.

This matters only for the tempting shortcut of reconstructing absolute velocity
POST HOC from an existing shard by adding globals 6,7 back into channels 2,3.
That shortcut is wrong twice over: the per-row ``player.speed`` divisor is not
recoverable from the kept columns, and BOTH terms are ``_clamp``ed to [-1,1]
before storage, so the sum is lossy exactly where velocities are large.

This module instead re-encodes from the raw capture, where ``entity.vx`` is
present verbatim. No rescaling is applied and no reconciliation is needed:
channels 2,3 keep the SAME ``entity_speed`` divisor they always had; only the
numerator loses its ``- player.v`` term. Every other channel, the clamp bounds,
the capacities and the sort key are byte-for-byte the ``encoder_v1`` behaviour.

WHAT IS DELIBERATELY *NOT* CHANGED
----------------------------------
Channels 11,12,13 (``contact_risk`` / ``time_to_closest`` / ``closest_distance``)
and the per-group SORT KEY are still computed from RELATIVE motion. That is
physically correct -- closest approach is a relative-motion quantity -- but it
means those three scalars, and the row ORDER they induce, still carry a weak
image of the player's velocity. They are the bracket: condition A keeps them,
condition B ablates them, and the residual ordering channel is audited
explicitly rather than assumed inert.

``configs/wp2/observation_v1.yaml`` is NOT touched: ``load_schema`` hashes that
file's bytes and every frozen ``combat_obs_v1`` manifest pins the result, so any
edit -- even a comment -- would make those datasets unloadable. This variant
pairs with the sibling ``configs/wp2/observation_v1_absvel.yaml``, whose only
content difference is the two renamed ``entity_features`` labels.

Nothing here is deployed, exported or served. It exists to measure.
"""
from __future__ import annotations

import math
from typing import Any

from trainer.observation.encoder_v1 import (  # noqa: F401  (re-exported)
    CAPTURE_ACCEPT_FILENAME,
    EncodedObservation,
    ObservationError,
    _clamp,
    _closest_approach,
    _number,
    _stable_type_hash,
    accepted_capture_hashes,
    canonical_digest,
    load_capture_accept_list,
    load_schema,
)
from trainer.observation import encoder_v1 as _base

#: Entity feature names this variant redefines, and what they become.
ABSOLUTE_VELOCITY_CHANNELS: dict[int, tuple[str, str]] = {
    2: ("relative_vx", "entity_vx"),
    3: ("relative_vy", "entity_vy"),
}


def _entity_row(
    entity: dict[str, Any],
    group: str,
    payload: dict[str, Any],
    schema: dict[str, Any],
) -> tuple[tuple[Any, ...], list[float]]:
    """``encoder_v1._entity_row`` with channels 2,3 as ABSOLUTE entity velocity.

    Line-for-line the original except for the two ``row`` entries marked below.
    The relative velocity is still computed, because channels 11,12,13 and the
    sort key legitimately depend on it.
    """
    player = payload["player"]
    arena = payload["arena"]
    width = max(_number(arena.get("width"), "arena.width"), 1.0)
    height = max(_number(arena.get("height"), "arena.height"), 1.0)
    diagonal = math.hypot(width, height)
    px = _number(player.get("x"), "player.x")
    py = _number(player.get("y"), "player.y")
    pvx = _number(player.get("measured_vx", player.get("vx", 0)), "player.vx")
    pvy = _number(player.get("measured_vy", player.get("vy", 0)), "player.vy")
    rx = _number(entity.get("x"), f"{group}.x") - px
    ry = _number(entity.get("y"), f"{group}.y") - py
    evx = _number(entity.get("vx", 0), f"{group}.vx")
    evy = _number(entity.get("vy", 0), f"{group}.vy")
    rvx = evx - pvx
    rvy = evy - pvy
    distance = math.hypot(rx, ry)
    horizon = _number(schema["closest_approach_horizon_sec"], "closest_approach_horizon_sec")
    time_sec, closest = _closest_approach(rx, ry, rvx, rvy, horizon)
    radius = max(_number(entity.get("radius", 0), f"{group}.radius"), 0.0)
    contact_distance = radius + _number(schema["player_radius"], "player_radius") + 20.0
    proximity = 1.0 - _clamp(closest / max(contact_distance * 2.0, 1.0), 0.0, 1.0)
    urgency = 1.0 - _clamp(time_sec / max(horizon, 1e-6), 0.0, 1.0)
    contact_risk = proximity * max(urgency, 0.25)
    norm = schema["normalization"]
    speed_scale = max(_number(norm["entity_speed"], "normalization.entity_speed"), 1.0)
    radius_scale = max(_number(norm["entity_radius"], "normalization.entity_radius"), 1.0)
    health_ratio = _clamp(_number(entity.get("health_ratio", 0), f"{group}.health_ratio"), 0.0, 1.0)
    bearing_sin = ry / distance if distance > 1e-9 else 0.0
    bearing_cos = rx / distance if distance > 1e-9 else 0.0
    threat_code = _number(schema["groups"][group]["threat_code"], f"groups.{group}.threat_code")
    row = [
        _clamp(rx / width),
        _clamp(ry / height),
        _clamp(evx / speed_scale),  # <-- ABSOLUTE (was (evx - pvx) / speed_scale)
        _clamp(evy / speed_scale),  # <-- ABSOLUTE (was (evy - pvy) / speed_scale)
        _clamp(radius / radius_scale, 0.0, 1.0),
        _clamp(distance / diagonal, 0.0, 1.0),
        bearing_sin,
        bearing_cos,
        health_ratio,
        _clamp(_number(entity.get("speed", 0), f"{group}.speed") / speed_scale, -1.0, 1.0),
        threat_code,
        contact_risk,
        _clamp(time_sec / max(horizon, 1e-6), 0.0, 1.0),
        _clamp(closest / diagonal, 0.0, 1.0),
        _stable_type_hash(entity),
    ]
    instance_id = int(_number(entity.get("instance_id", 0), f"{group}.instance_id"))
    if str(schema.get("entity_sort", "contact_risk")) == "distance":
        # VELOCITY-FREE ranking. The default key below is
        # (-contact_risk, time_sec, closest, distance, ...) and all three leading
        # terms are computed from RELATIVE motion, which for a static object is
        # exactly -player.v. So WHICH SLOT each object lands in is a function of
        # the player's velocity direction: a leak carried by the PERMUTATION, not
        # by any channel value, and therefore untouched by zeroing channels
        # 2,3,11,12,13. Measured on the val split, a probe over static per-slot
        # channels that contains no velocity-derived channel at all still scored
        # 0.2791 9-way agreement / 0.5130 cosine under the default ordering, and
        # 0.1249 / 0.4232 once the slots were re-sorted by distance.
        #
        # This is a SEMANTIC change, not just a permutation: it also changes which
        # entities survive the per-group capacity cap (nearest-N instead of
        # highest-contact-risk-N). That is the price of a velocity-free ranking
        # and it is stated rather than hidden.
        sort_key = (distance, instance_id, _stable_type_hash(entity))
    else:
        sort_key = (-contact_risk, time_sec, closest, distance, instance_id,
                    _stable_type_hash(entity))
    return sort_key, row


def encode_capture(payload: dict[str, Any], schema: dict[str, Any]) -> EncodedObservation:
    """``encoder_v1.encode_capture`` with this module's ``_entity_row``.

    The base function reads ``_entity_row`` from its own module globals, so the
    variant is injected for the duration of the call rather than duplicating 40
    lines of masking/capacity logic that must stay identical.
    """
    original = _base._entity_row
    _base._entity_row = _entity_row
    try:
        return _base.encode_capture(payload, schema)
    finally:
        _base._entity_row = original
