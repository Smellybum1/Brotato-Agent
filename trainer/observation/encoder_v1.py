"""Deterministic, masked encoder for ``combat_obs_v1``."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import yaml


class ObservationError(ValueError):
    """Raised when a capture cannot be encoded safely."""


@dataclass(frozen=True)
class EncodedObservation:
    schema_id: str
    schema_hash: str
    global_features: list[float]
    entities: dict[str, list[list[float]]]
    masks: dict[str, list[float]]
    dropped_counts: dict[str, int]
    valid: bool
    temporal_valid: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_hash": self.schema_hash,
            "global_features": self.global_features,
            "entities": self.entities,
            "masks": self.masks,
            "dropped_counts": self.dropped_counts,
            "valid": self.valid,
            "temporal_valid": self.temporal_valid,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "EncodedObservation":
        return cls(
            schema_id=str(value["schema_id"]),
            schema_hash=str(value["schema_hash"]),
            global_features=[float(item) for item in value["global_features"]],
            entities={
                str(group): [[float(item) for item in row] for row in rows]
                for group, rows in value["entities"].items()
            },
            masks={
                str(group): [float(item) for item in mask]
                for group, mask in value["masks"].items()
            },
            dropped_counts={str(group): int(count) for group, count in value["dropped_counts"].items()},
            valid=bool(value["valid"]),
            temporal_valid=bool(value["temporal_valid"]),
        )


def load_schema(path: Path) -> dict[str, Any]:
    schema = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(schema, dict) or schema.get("schema_id") != "combat_obs_v1":
        raise ObservationError("expected combat_obs_v1 schema")
    schema["_schema_hash"] = hashlib.sha256(path.read_bytes()).hexdigest().upper()
    return schema


def _number(value: Any, field: str, default: float = 0.0) -> float:
    if value is None:
        value = default
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ObservationError(f"{field} is not numeric") from exc
    if not math.isfinite(result):
        raise ObservationError(f"{field} is not finite")
    return result


def _clamp(value: float, lower: float = -1.0, upper: float = 1.0) -> float:
    return min(max(value, lower), upper)


def _stable_type_hash(entity: dict[str, Any]) -> float:
    text = "|".join(str(entity.get(key, "")) for key in ("type_id", "script_path", "attack_path", "id"))
    if not text.strip("|"):
        return 0.0
    value = int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:4], "big")
    return value / 0xFFFFFFFF


def _closest_approach(rx: float, ry: float, rvx: float, rvy: float, horizon: float) -> tuple[float, float]:
    velocity_sq = rvx * rvx + rvy * rvy
    if velocity_sq <= 1e-9:
        return 0.0, math.hypot(rx, ry)
    time_sec = _clamp(-(rx * rvx + ry * rvy) / velocity_sq, 0.0, horizon)
    return time_sec, math.hypot(rx + rvx * time_sec, ry + rvy * time_sec)


def _entity_row(
    entity: dict[str, Any],
    group: str,
    payload: dict[str, Any],
    schema: dict[str, Any],
) -> tuple[tuple[Any, ...], list[float]]:
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
    rvx = _number(entity.get("vx", 0), f"{group}.vx") - pvx
    rvy = _number(entity.get("vy", 0), f"{group}.vy") - pvy
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
        _clamp(rvx / speed_scale),
        _clamp(rvy / speed_scale),
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
    sort_key = (-contact_risk, time_sec, closest, distance, instance_id, _stable_type_hash(entity))
    return sort_key, row


def _global_values(payload: dict[str, Any], schema: dict[str, Any], temporal_valid: bool) -> dict[str, float]:
    player = payload["player"]
    arena = payload["arena"]
    teacher = payload["teacher"]
    width = max(_number(arena.get("width"), "arena.width"), 1.0)
    height = max(_number(arena.get("height"), "arena.height"), 1.0)
    x = _number(player.get("x"), "player.x")
    y = _number(player.get("y"), "player.y")
    speed = max(_number(player.get("speed", 0), "player.speed"), 1.0)
    current = teacher.get("action", {})
    previous = teacher.get("previous_action", {})
    time = payload.get("wave_time", {})
    duration = max(_number(time.get("duration_sec", 0), "wave_time.duration_sec"), 1.0)
    norm = schema["normalization"]
    weapons = payload.get("weapons", [])
    if not isinstance(weapons, list):
        raise ObservationError("weapons is not an array")
    ranges = [_number(item.get("max_range", 0), "weapon.max_range") for item in weapons]
    cooldowns = [_number(item.get("cooldown", 0), "weapon.cooldown") for item in weapons]
    damages = [_number(item.get("damage", 0), "weapon.damage") for item in weapons]
    ranged = sum(str(item.get("type", "")) == "ranged" for item in weapons)
    contributions = teacher.get("contributions", {}) or {}
    finale = contributions.get("finale_translation", {}) or {}
    invalid_total = sum(int(value) for value in (payload.get("invalid_counts", {}) or {}).values())
    source_dropped = sum(int(value) for value in (payload.get("dropped_counts", {}) or {}).values())
    entities = payload["entities"]
    values = {
        "wave": _clamp(_number(payload.get("wave"), "wave") / _number(norm["wave"], "normalization.wave"), 0.0, 2.0),
        "wave_elapsed": _clamp(_number(time.get("elapsed_sec", 0), "wave_time.elapsed_sec") / duration, 0.0, 1.0),
        "wave_remaining": _clamp(_number(time.get("remaining_sec", 0), "wave_time.remaining_sec") / duration, 0.0, 1.0),
        "control_dt": _clamp(_number(payload.get("control_dt_ms", 0), "control_dt_ms") / 50.0, 0.0, 5.0),
        "player_x": _clamp((x / width) * 2.0 - 1.0),
        "player_y": _clamp((y / height) * 2.0 - 1.0),
        "player_vx": _clamp(_number(player.get("measured_vx", player.get("vx", 0)), "player.vx") / speed),
        "player_vy": _clamp(_number(player.get("measured_vy", player.get("vy", 0)), "player.vy") / speed),
        "hp_ratio": _clamp(_number(player.get("hp_ratio", 0), "player.hp_ratio"), 0.0, 1.0),
        "max_hp": _clamp(_number(player.get("max_hp", 0), "player.max_hp") / _number(norm["max_hp"], "normalization.max_hp"), 0.0, 2.0),
        "movement_speed": _clamp(speed / _number(norm["speed"], "normalization.speed"), 0.0, 2.0),
        "armor": _clamp(_number(player.get("armor", 0), "player.armor") / _number(norm["armor"], "normalization.armor"), -1.0, 2.0),
        "dodge": _clamp(_number(player.get("dodge", 0), "player.dodge") / _number(norm["dodge"], "normalization.dodge"), 0.0, 1.0),
        "hp_regeneration": _clamp(_number(player.get("hp_regeneration", 0), "player.hp_regeneration") / _number(norm["hp_regeneration"], "normalization.hp_regeneration"), -1.0, 2.0),
        "lifesteal": _clamp(_number(player.get("lifesteal", 0), "player.lifesteal") / _number(norm["lifesteal"], "normalization.lifesteal"), -1.0, 2.0),
        "teacher_action_x": _clamp(_number(current.get("x"), "teacher.action.x")),
        "teacher_action_y": _clamp(_number(current.get("y"), "teacher.action.y")),
        "previous_action_x": _clamp(_number(previous.get("x"), "teacher.previous_action.x")),
        "previous_action_y": _clamp(_number(previous.get("y"), "teacher.previous_action.y")),
        "wall_left": _clamp(x / width, 0.0, 1.0),
        "wall_right": _clamp((width - x) / width, 0.0, 1.0),
        "wall_top": _clamp(y / height, 0.0, 1.0),
        "wall_bottom": _clamp((height - y) / height, 0.0, 1.0),
        "weapon_count": _clamp(len(weapons) / 6.0, 0.0, 1.0),
        "ranged_fraction": ranged / len(weapons) if weapons else 0.0,
        "weapon_min_range": min(ranges, default=0.0) / _number(norm["weapon_range"], "normalization.weapon_range"),
        "weapon_max_range": max(ranges, default=0.0) / _number(norm["weapon_range"], "normalization.weapon_range"),
        "weapon_mean_range": (sum(ranges) / len(ranges) if ranges else 0.0) / _number(norm["weapon_range"], "normalization.weapon_range"),
        "weapon_mean_cooldown": (sum(cooldowns) / len(cooldowns) if cooldowns else 0.0) / _number(norm["weapon_cooldown"], "normalization.weapon_cooldown"),
        "weapon_total_damage": sum(damages) / (_number(norm["weapon_damage"], "normalization.weapon_damage") * 6.0),
        "weapon_damage_rate": sum(damage / max(cooldown, 1.0) for damage, cooldown in zip(damages, cooldowns)) / _number(norm["weapon_damage"], "normalization.weapon_damage"),
        "observation_age": _clamp(_number(payload.get("observation_age_ms", 0), "observation_age_ms") / 50.0, 0.0, 5.0),
        "temporal_valid": float(temporal_valid),
        "invalid_entity_count": _clamp(invalid_total / 10.0, 0.0, 1.0),
        "source_dropped_count": _clamp(source_dropped / 10.0, 0.0, 1.0),
        "teacher_enemy_count": _clamp(_number(contributions.get("enemies", 0), "teacher.enemies") / 64.0, 0.0, 2.0),
        "teacher_projectile_count": _clamp(_number(contributions.get("projectiles", 0), "teacher.projectiles") / 32.0, 0.0, 2.0),
        "finale_commit_distance": _clamp(_number(finale.get("commit_distance", 0), "teacher.finale.commit_distance") / 256.0, 0.0, 2.0),
        "finale_commit_ticks": _clamp(_number(finale.get("commit_ticks", 0), "teacher.finale.commit_ticks") / 10.0, 0.0, 2.0),
        "finale_commit_x": _clamp(_number(finale.get("commit_x", 0), "teacher.finale.commit_x")),
        "finale_commit_y": _clamp(_number(finale.get("commit_y", 0), "teacher.finale.commit_y")),
    }
    count_names = {
        "enemies": "enemy_count",
        "bosses": "boss_count",
        "projectiles": "projectile_count",
        "materials": "material_count",
        "consumables": "consumable_count",
        "crates": "crate_count",
        "obstacles": "obstacle_count",
    }
    for group, feature_name in count_names.items():
        values[feature_name] = _clamp(
            len(entities.get(group, [])) / float(schema["groups"][group]["capacity"]),
            0.0,
            2.0,
        )
    return values


def encode_capture(payload: dict[str, Any], schema: dict[str, Any]) -> EncodedObservation:
    if payload.get("capture_schema_hash") != schema.get("source_capture_schema_hash"):
        raise ObservationError("capture schema hash mismatch")
    for field in ("player", "arena", "teacher", "entities"):
        if not isinstance(payload.get(field), dict):
            raise ObservationError(f"{field} is not an object")
    control_dt = _number(payload.get("control_dt_ms", 0), "control_dt_ms")
    temporal_valid = 0.0 < control_dt <= _number(schema["max_transition_gap_ms"], "max_transition_gap_ms")
    values = _global_values(payload, schema, temporal_valid)
    try:
        global_features = [float(values[name]) for name in schema["global_features"]]
    except KeyError as exc:
        raise ObservationError(f"unknown global feature {exc.args[0]}") from exc
    entities_out: dict[str, list[list[float]]] = {}
    masks: dict[str, list[float]] = {}
    dropped_counts: dict[str, int] = {}
    feature_count = len(schema["entity_features"])
    source_entities = payload["entities"]
    for group, group_config in schema["groups"].items():
        raw = source_entities.get(group, [])
        if not isinstance(raw, list):
            raise ObservationError(f"entities.{group} is not an array")
        ranked = sorted(_entity_row(entity, group, payload, schema) for entity in raw)
        capacity = int(group_config["capacity"])
        selected = [row for _, row in ranked[:capacity]]
        mask = [1.0] * len(selected)
        selected.extend([[0.0] * feature_count for _ in range(capacity - len(selected))])
        mask.extend([0.0] * (capacity - len(mask)))
        entities_out[group] = selected
        masks[group] = mask
        source_dropped = int((payload.get("dropped_counts", {}) or {}).get(group, 0))
        dropped_counts[group] = max(len(raw) - capacity, 0) + source_dropped
    valid = bool(payload.get("valid", False)) and all(math.isfinite(value) for value in global_features)
    return EncodedObservation(
        schema_id=str(schema["schema_id"]),
        schema_hash=str(schema["_schema_hash"]),
        global_features=global_features,
        entities=entities_out,
        masks=masks,
        dropped_counts=dropped_counts,
        valid=valid,
        temporal_valid=temporal_valid,
    )


def canonical_digest(observation: EncodedObservation) -> str:
    encoded = json.dumps(observation.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest().upper()
