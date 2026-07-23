#!/usr/bin/env python3
"""Audit closed WP2 teacher runs against the late-wave movement safety gates."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
LATE_WAVE = 17
BODY_TIER = 45.0
BODY_SLACK = 20.0
# v123: near-best body slack is wave-indexed (config body_clearance_slack). Early
# waves (<= EARLY_GREED_MAX_WAVE) use 35; the mid-late band and waves 19/20 use 20.
BODY_SLACK_EARLY = 35.0                 # config body_clearance_slack(wave <= 12)
EARLY_GREED_MAX_WAVE = 12               # config EARLY_GREED_MAX_WAVE
FINAL_SHOP_WAVE = 19                    # config FINAL_SHOP_WAVE
BODY_PACK_CLEARANCE = 160.0
BODY_EMERGENCY_SLACK = 5.0
# v123 strength tiers (config STRENGTH_*). Hysteresis: a recorded tier constrains
# the recorded smoothed strength S to a necessary single-sample band.
STRENGTH_MIN = 0.0
STRENGTH_MAX = 2.0
STRENGTH_ENTER_STRONG = 1.25            # config STRENGTH_ENTER_STRONG
STRENGTH_EXIT_STRONG = 1.15            # config STRENGTH_EXIT_STRONG
STRENGTH_ENTER_WEAK = 0.75            # config STRENGTH_ENTER_WEAK
STRENGTH_EXIT_WEAK = 0.85            # config STRENGTH_EXIT_WEAK
# v123 dash arm HP floor (config loot_dash_arm_hp_floor + strength delta, clamped).
DASH_ARM_FLOOR_EARLY = 0.35            # config loot_dash_arm_hp_floor(wave <= 12)
DASH_ARM_FLOOR_LATE = 0.5             # config loot_dash_arm_hp_floor(otherwise)
DASH_ARM_FLOOR_MIN = 0.30            # config LOOT_DASH_ARM_FLOOR_MIN
DASH_ARM_STRONG_DELTA = -0.05           # config STRENGTH_STRONG_DASH_HP_FLOOR_DELTA
DASH_ARM_WEAK_DELTA = 0.05           # config STRENGTH_WEAK_DASH_HP_FLOOR_DELTA
# The runtime aborts an active dash below abort = 0.8 x effective arm; the audit
# floor keeps the historical 0.05 margin below the abort (today 0.40 -> 0.35).
DASH_ABORT_ARM_FRACTION = 0.8
DASH_AUDIT_FLOOR_MARGIN = 0.05
# v117: extended from 140 after the v116 smoke died with references at
# 140.7-151.1 while hard-safe lanes offered 75-212 more units.
WALL_BODY_RELIEF_TRIGGER = 200.0
# v118 loot-dash bounds (mirror LOOT_DASH_MAX_TICKS 72 at 60 Hz -> ~24
# captures at 20 Hz, +2 margin; runtime aborts below 0.4 hp_ratio).
LOOT_DASH_MAX_CAPTURES = 26
# Legacy (pre-v123) dash-active HP floor. v122 and earlier captures carry no
# strength diagnostics and MUST be audited with the exact v122 flat floor so a
# v122-campaign audit reproduces v122 strictness. v123 captures instead derive the
# floor per capture from the wave and recorded strength tier (_dash_audit_hp_floor).
LEGACY_LOOT_DASH_MIN_HP_RATIO = 0.35
WALL_BODY_RELIEF_MIN_GAIN = 60.0
HARD_WALL_MARGIN = 96.0
COMMAND_HORIZON_SEC = 0.30
WALL_LOOKAHEAD = 260.0
WALL_RECOVERY_RELEASE = 520.0
ESCAPE_HORIZON_SEC = 0.60
ESCAPE_TIME_SAMPLES = 6
ESCAPE_DIRECTIONS = 24
# v116: clearances are the continuous closest approach over the hold, starting
# one decision interval out (mirrors ESCAPE_CLEARANCE_MIN_TIME in config.gd).
ESCAPE_CLEARANCE_MIN_TIME = 0.05
# v116 damage-route gates: a damage event whose emitted route passed within
# ROUTE_PROJ_CONTACT units of a projectile centre (or ROUTE_BODY_CONTACT of an
# enemy body) is avoidable when a sampled hard-wall-safe lane offered at least
# ROUTE_MIN_GAIN more of the violated clearance without giving up the other.
ROUTE_PROJ_CONTACT = 12.0
ROUTE_BODY_CONTACT = 15.0
ROUTE_MIN_GAIN = 20.0
FLOAT_TOLERANCE = 0.002


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _normalise(action: dict[str, Any]) -> tuple[float, float] | None:
    x = float(action.get("x", 0.0))
    y = float(action.get("y", 0.0))
    magnitude = math.hypot(x, y)
    if magnitude < 0.1:
        return None
    return x / magnitude, y / magnitude


def _is_v123_capture(debug: dict[str, Any]) -> bool:
    """True only when the capture actually carries the v123 strength diagnostics.

    Legacy (v122 and earlier) captures have no build_strength, so every v123
    audit loosening (wave-indexed body slack, wave/tier dash floor) is withheld
    from them and they are audited with the exact prior strictness.
    """
    return debug.get("build_strength") is not None


def _body_slack_for_wave(wave: Any) -> float:
    """Near-best body slack: 35 for early waves (<= 12), 20 otherwise (incl. 19/20)."""
    if wave is not None and int(wave) <= EARLY_GREED_MAX_WAVE:
        return BODY_SLACK_EARLY
    return BODY_SLACK


def _required_body_floor(
    debug: dict[str, Any], enforce_pack_clearance: bool = False, wave: Any = None
) -> float:
    best_clearance = float(debug["body_best_clearance"])
    if bool(debug.get("body_emergency_active", False)):
        return best_clearance - BODY_EMERGENCY_SLACK
    # v118: an active loot dash deliberately trades the near-best pack tier
    # for collection; only the contact-safe floor applies while it runs.
    if bool(debug.get("loot_dash_active", False)):
        enforce_pack_clearance = False
    # v123: the wider early-wave slack applies ONLY to captures that carry the
    # v123 strength diagnostics. Legacy captures keep the flat 20 slack at every
    # wave so a v122-campaign audit reproduces v122 strictness exactly.
    if wave is None:
        wave = debug.get("wave")
    slack = _body_slack_for_wave(wave) if _is_v123_capture(debug) else BODY_SLACK
    if enforce_pack_clearance and best_clearance >= BODY_TIER:
        return max(BODY_TIER, min(BODY_PACK_CLEARANCE, best_clearance - slack))
    if best_clearance >= BODY_TIER:
        return BODY_TIER
    return best_clearance - slack


def _effective_dash_arm_floor(wave: Any, tier: Any) -> float:
    """Runtime effective dash arm HP floor: wave-indexed base + strength delta, clamped."""
    base = (
        DASH_ARM_FLOOR_EARLY
        if wave is not None and int(wave) <= EARLY_GREED_MAX_WAVE
        else DASH_ARM_FLOOR_LATE
    )
    if tier == "strong":
        base += DASH_ARM_STRONG_DELTA
    elif tier == "weak":
        base += DASH_ARM_WEAK_DELTA
    return max(base, DASH_ARM_FLOOR_MIN)


def _dash_audit_hp_floor(wave: Any, tier: Any) -> float:
    """Audit HP floor for an active dash: abort (0.8 x effective arm) minus 0.05."""
    return _effective_dash_arm_floor(wave, tier) * DASH_ABORT_ARM_FRACTION - DASH_AUDIT_FLOOR_MARGIN


def _strength_tier_consistent(tier: str, strength: float) -> bool:
    """Necessary single-sample band that a recorded hysteretic tier must satisfy."""
    if tier == "strong":
        return strength > STRENGTH_EXIT_STRONG - FLOAT_TOLERANCE
    if tier == "weak":
        return strength < STRENGTH_EXIT_WEAK + FLOAT_TOLERANCE
    if tier == "neutral":
        return (
            STRENGTH_ENTER_WEAK - FLOAT_TOLERANCE
            < strength
            < STRENGTH_ENTER_STRONG + FLOAT_TOLERANCE
        )
    return False


def _strength_violation(payload: dict[str, Any]) -> dict[str, Any] | None:
    """Flag out-of-range recorded strength or a tier inconsistent with it.

    Inert on legacy captures that predate the v123 strength diagnostics.
    """
    debug = payload["teacher"]["contributions"]["finale_translation"]
    if "build_strength" not in debug and "strength_tier" not in debug:
        return None
    reasons: list[str] = []
    strength = float(debug.get("build_strength", 1.0))
    if not (STRENGTH_MIN - FLOAT_TOLERANCE <= strength <= STRENGTH_MAX + FLOAT_TOLERANCE):
        reasons.append("recorded build_strength outside [0, 2]")
    tier = debug.get("strength_tier")
    if tier not in ("strong", "neutral", "weak"):
        reasons.append("unknown strength_tier")
    elif not _strength_tier_consistent(tier, strength):
        reasons.append("strength_tier inconsistent with recorded strength")
    if reasons:
        return {
            "capture_seq": payload.get("capture_seq"),
            "wave": payload.get("wave"),
            "build_strength": strength,
            "strength_tier": tier,
            "reasons": reasons,
        }
    return None


def _body_projectile_floor_unavailable(debug: dict[str, Any]) -> bool:
    """Identify the no-eligible-sample fallback without forgiving a body choice.

    The runtime preserves its incoming projectile-safe command when none of the
    body layer's sampled directions meets the projectile floor. That branch
    reports identical input/best/selected body clearance, leaves the selected
    projectile diagnostic at its -1 sentinel, and does not activate a repair.
    """
    if bool(debug.get("body_safety_active", False)):
        return False
    if bool(debug.get("body_emergency_active", False)):
        return False
    if float(debug.get("body_projectile_floor", -1.0e18)) <= -1.0e17:
        return False
    if float(debug.get("body_selected_projectile_clearance", -1.0)) != -1.0:
        return False
    input_clearance = float(debug.get("body_input_clearance", -1.0))
    best_clearance = float(debug.get("body_best_clearance", -1.0))
    selected_clearance = float(debug.get("body_selected_clearance", -1.0))
    if (
        abs(input_clearance - best_clearance) <= FLOAT_TOLERANCE
        and abs(input_clearance - selected_clearance) <= FLOAT_TOLERANCE
    ):
        return True
    # v121: active wall-body relief whose 45-unit floor exceeds every sampled
    # lane keeps the (clearer) incoming command; selected mirrors the input
    # while best reports the tighter sampled pool.
    return (
        bool(debug.get("wall_body_relief_active", False))
        and abs(input_clearance - selected_clearance) <= FLOAT_TOLERANCE
        and best_clearance < BODY_TIER - FLOAT_TOLERANCE
    )


def _continuous_min_distance(
    rel_x: float,
    rel_y: float,
    rel_vx: float,
    rel_vy: float,
    t_lo: float,
    t_hi: float,
) -> float:
    """Minimum of |rel + rel_v * t| over [t_lo, t_hi] (motion is linear)."""
    speed_sq = rel_vx * rel_vx + rel_vy * rel_vy
    closest = t_lo
    if speed_sq > 1.0e-9:
        closest = min(t_hi, max(t_lo, -(rel_x * rel_vx + rel_y * rel_vy) / speed_sq))
    return min(
        math.hypot(rel_x + rel_vx * closest, rel_y + rel_vy * closest),
        math.hypot(rel_x + rel_vx * t_hi, rel_y + rel_vy * t_hi),
    )


def _body_clearance(payload: dict[str, Any], legacy_sampled: bool = False) -> float:
    direction = _normalise(payload["teacher"]["action"])
    if direction is None:
        return -1.0e18
    player = payload["player"]
    x = float(player["x"])
    y = float(player["y"])
    speed = max(float(player.get("speed", 0.0)), 1.0)
    threats = payload["entities"]["enemies"] + payload["entities"]["bosses"]
    if not threats:
        return 1_000_000.0
    result = 1_000_000.0
    if legacy_sampled:
        # v107-v115 recorded diagnostics used the discrete sample grid. Frozen
        # evidence replays keep parity with that formula; it must not audit new
        # runs because 120 ms steps hide fast crossings (v115 captures 19557,
        # 20505).
        for index in range(1, ESCAPE_TIME_SAMPLES):
            future_sec = index / (ESCAPE_TIME_SAMPLES - 1) * ESCAPE_HORIZON_SEC
            player_x = x + direction[0] * speed * future_sec
            player_y = y + direction[1] * speed * future_sec
            for threat in threats:
                threat_x = float(threat.get("x", 0.0)) + float(threat.get("vx", 0.0)) * future_sec
                threat_y = float(threat.get("y", 0.0)) + float(threat.get("vy", 0.0)) * future_sec
                radius = max(float(threat.get("radius", 18.0)), 0.0)
                result = min(result, math.hypot(player_x - threat_x, player_y - threat_y) - radius)
        return result
    for threat in threats:
        radius = max(float(threat.get("radius", 18.0)), 0.0)
        distance = _continuous_min_distance(
            x - float(threat.get("x", 0.0)),
            y - float(threat.get("y", 0.0)),
            direction[0] * speed - float(threat.get("vx", 0.0)),
            direction[1] * speed - float(threat.get("vy", 0.0)),
            ESCAPE_CLEARANCE_MIN_TIME,
            ESCAPE_HORIZON_SEC,
        )
        result = min(result, distance - radius)
    return result


def _projectile_route_clearance(
    payload: dict[str, Any], direction: tuple[float, float] | None = None
) -> float:
    """Continuous minimum centre distance to any projectile along the route."""
    if direction is None:
        direction = _normalise(payload["teacher"]["action"])
    if direction is None:
        return -1.0e18
    projectiles = payload["entities"].get("projectiles", [])
    if not projectiles:
        return 1_000_000.0
    player = payload["player"]
    x = float(player["x"])
    y = float(player["y"])
    speed = max(float(player.get("speed", 0.0)), 1.0)
    result = 1_000_000.0
    for projectile in projectiles:
        result = min(
            result,
            _continuous_min_distance(
                x - float(projectile.get("x", 0.0)),
                y - float(projectile.get("y", 0.0)),
                direction[0] * speed - float(projectile.get("vx", 0.0)),
                direction[1] * speed - float(projectile.get("vy", 0.0)),
                0.0,
                ESCAPE_HORIZON_SEC,
            ),
        )
    return result


def _body_clearance_for_direction(
    payload: dict[str, Any],
    direction: tuple[float, float],
    legacy_sampled: bool = False,
) -> float:
    replay = {
        **payload,
        "teacher": {
            **payload["teacher"],
            "action": {"x": direction[0], "y": direction[1]},
        },
    }
    return _body_clearance(replay, legacy_sampled)


def _hard_safe_directions(payload: dict[str, Any]) -> list[tuple[float, float]]:
    player = payload["player"]
    arena = payload["arena"]
    x = float(player["x"])
    y = float(player["y"])
    width = float(arena.get("width", 2048.0))
    height = float(arena.get("height", 1536.0))
    directions: list[tuple[float, float]] = []
    for index in range(ESCAPE_DIRECTIONS):
        angle = math.tau * index / ESCAPE_DIRECTIONS
        direction = (math.cos(angle), math.sin(angle))
        future_x = x + direction[0] * WALL_LOOKAHEAD
        future_y = y + direction[1] * WALL_LOOKAHEAD
        future_wall = min(future_x, width - future_x, future_y, height - future_y)
        if future_wall >= HARD_WALL_MARGIN:
            directions.append(direction)
    return directions


def _best_hard_safe_body_clearance(
    payload: dict[str, Any], legacy_sampled: bool = False
) -> tuple[float, tuple[float, float] | None]:
    """Replay the best sampled body lane that respects the projected hard wall."""
    best = -1.0e18
    best_direction: tuple[float, float] | None = None
    for direction in _hard_safe_directions(payload):
        clearance = _body_clearance_for_direction(payload, direction, legacy_sampled)
        if clearance > best:
            best = clearance
            best_direction = direction
    return best, best_direction


def _route_replay(payload: dict[str, Any]) -> dict[str, Any] | None:
    """Continuous replay of the emitted route and the best sampled alternative.

    Always uses the continuous closest-approach clearances, even on frozen
    legacy runs: this gate exists precisely because the sampled diagnostics
    could not see fast crossings.
    """
    if "player" not in payload or "arena" not in payload or "entities" not in payload:
        return None
    if _normalise(payload.get("teacher", {}).get("action", {})) is None:
        return None
    emitted_body = _body_clearance(payload)
    emitted_projectile = _projectile_route_clearance(payload)
    best_body = -1.0e18
    best_projectile = -1.0e18
    for direction in _hard_safe_directions(payload):
        body = _body_clearance_for_direction(payload, direction)
        projectile = _projectile_route_clearance(payload, direction)
        # A safer lane must not trade one clearance family for the other.
        if projectile >= min(emitted_projectile, ROUTE_PROJ_CONTACT):
            best_body = max(best_body, body)
        if body >= min(emitted_body, BODY_TIER):
            best_projectile = max(best_projectile, projectile)
    return {
        "emitted_body_clearance": emitted_body,
        "emitted_projectile_clearance": emitted_projectile,
        "best_body_clearance": best_body,
        "best_projectile_clearance": best_projectile,
    }


def _wall_body_relief_violation(
    payload: dict[str, Any], legacy_sampled: bool = False
) -> dict[str, Any] | None:
    """Find a hard-safe body escape hidden by the strict wall-progress pool."""
    if int(payload.get("wave", 0)) < 20:
        return None
    debug = payload["teacher"]["contributions"]["finale_translation"]
    if not bool(debug.get("wall_recovery_active", False)):
        return None
    if bool(debug.get("projectile_safety_active", False)):
        return None
    if bool(debug.get("loot_dash_active", False)):
        return None
    if payload["entities"].get("projectiles", []):
        return None
    # Recompute the clearance of the action carried by this capture. Held
    # captures can legitimately retain diagnostics from the preceding policy
    # update while the player and threats continue to move.
    selected = _body_clearance(payload, legacy_sampled)
    if selected >= WALL_BODY_RELIEF_TRIGGER:
        return None
    best, best_direction = _best_hard_safe_body_clearance(payload, legacy_sampled)
    if best < selected + WALL_BODY_RELIEF_MIN_GAIN - FLOAT_TOLERANCE:
        return None
    return {
        "capture_seq": payload["capture_seq"],
        "selected": selected,
        "relief_best": best,
        "required_gain": WALL_BODY_RELIEF_MIN_GAIN,
        "relief_direction": {
            "x": best_direction[0],
            "y": best_direction[1],
        },
    }


def _wall_distances(payload: dict[str, Any]) -> tuple[float, float]:
    direction = _normalise(payload["teacher"]["action"])
    if direction is None:
        return -1.0e18, -1.0e18
    player = payload["player"]
    arena = payload["arena"]
    x = float(player["x"])
    y = float(player["y"])
    width = float(arena.get("width", 2048.0))
    height = float(arena.get("height", 1536.0))
    current = min(x, width - x, y, height - y)
    end_x = x + direction[0] * WALL_LOOKAHEAD
    end_y = y + direction[1] * WALL_LOOKAHEAD
    future = min(end_x, width - end_x, end_y, height - end_y)
    return current, future


def _wall_recovery_progress_violation(
    payload: dict[str, Any],
) -> dict[str, Any] | None:
    """Require inward progress unless the bounded body-relief exception is active."""
    debug = payload["teacher"]["contributions"]["finale_translation"]
    if not bool(debug.get("body_safety_active", False)):
        return None
    if not bool(debug.get("wall_recovery_active", False)):
        return None
    if bool(debug.get("wall_body_relief_active", False)):
        return None
    current_wall, future_wall = _wall_distances(payload)
    if (
        current_wall < WALL_RECOVERY_RELEASE
        and future_wall <= current_wall + FLOAT_TOLERANCE
    ):
        return {
            "capture_seq": payload["capture_seq"],
            "current": current_wall,
            "future": future_wall,
        }
    return None


def _hard_wall_faults(payload: dict[str, Any]) -> list[str]:
    direction = _normalise(payload["teacher"]["action"])
    if direction is None:
        return ["zero final action"]
    player = payload["player"]
    arena = payload["arena"]
    x = float(player["x"])
    y = float(player["y"])
    speed = max(float(player.get("speed", 0.0)), 0.0)
    width = float(arena.get("width", 2048.0))
    height = float(arena.get("height", 1536.0))
    projected_x = x + direction[0] * speed * COMMAND_HORIZON_SEC
    projected_y = y + direction[1] * speed * COMMAND_HORIZON_SEC
    faults: list[str] = []
    if direction[0] < 0.0 and min(x, projected_x) <= HARD_WALL_MARGIN - FLOAT_TOLERANCE:
        faults.append("left")
    if direction[0] > 0.0 and max(x, projected_x) >= width - HARD_WALL_MARGIN + FLOAT_TOLERANCE:
        faults.append("right")
    if direction[1] < 0.0 and min(y, projected_y) <= HARD_WALL_MARGIN - FLOAT_TOLERANCE:
        faults.append("top")
    if direction[1] > 0.0 and max(y, projected_y) >= height - HARD_WALL_MARGIN + FLOAT_TOLERANCE:
        faults.append("bottom")
    return faults


def _is_sampled_direction(payload: dict[str, Any]) -> bool:
    direction = _normalise(payload["teacher"]["action"])
    if direction is None:
        return False
    best_dot = max(
        direction[0] * math.cos(math.tau * index / ESCAPE_DIRECTIONS)
        + direction[1] * math.sin(math.tau * index / ESCAPE_DIRECTIONS)
        for index in range(ESCAPE_DIRECTIONS)
    )
    return best_dot >= 0.99999


def _damage_rows(events: list[dict[str, Any]], first_capture_ts: int | None) -> list[dict[str, Any]]:
    if first_capture_ts is None:
        return []
    captures = [event for event in events if event.get("event") == "combat_capture"]
    rows: list[dict[str, Any]] = []
    for event in events:
        if event.get("event") != "player_damage" or int(event.get("ts_ms", -1)) < first_capture_ts:
            continue
        prior = next(
            (candidate for candidate in reversed(captures) if candidate.get("ts_ms", 0) <= event["ts_ms"]),
            None,
        )
        row: dict[str, Any] = {
            "event_seq": event.get("seq"),
            "ts_ms": event.get("ts_ms"),
            "amount": event.get("payload", {}).get("amount"),
            "hp": event.get("payload", {}).get("hp"),
        }
        if prior is not None:
            payload = prior["payload"]
            debug = payload["teacher"]["contributions"]["finale_translation"]
            row.update(
                {
                    "capture_seq": payload.get("capture_seq"),
                    "wave": payload.get("wave"),
                    "projectile_safety_active": debug.get("projectile_safety_active"),
                    "projectile_escape_clearance": debug.get("projectile_escape_clearance"),
                    "projectile_final_clearance": debug.get("projectile_final_clearance"),
                    "body_best_clearance": debug.get("body_best_clearance"),
                    "body_selected_clearance": debug.get("body_selected_clearance"),
                    "body_emergency_active": debug.get("body_emergency_active", False),
                    "loot_dash_active": debug.get("loot_dash_active", False),
                    # Carry the v123 strength diagnostics so the damage-review
                    # body floor applies the wider early slack only to v123
                    # captures (None on legacy -> treated as pre-v123).
                    "build_strength": debug.get("build_strength"),
                    "strength_tier": debug.get("strength_tier"),
                }
            )
            replay = _route_replay(payload)
            if replay is not None:
                row["route_replay"] = replay
        rows.append(row)
    return rows


def _avoidable_damage_violations(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    violations: list[dict[str, Any]] = []
    for row in rows:
        escape = float(row.get("projectile_escape_clearance", -1.0))
        final = float(row.get("projectile_final_clearance", -1.0))
        body_best = float(row.get("body_best_clearance", -1.0))
        body_selected = float(row.get("body_selected_clearance", -1.0))
        reasons: list[str] = []
        body_emergency_is_best_available = (
            body_best >= 0.0
            and body_selected >= body_best - BODY_EMERGENCY_SLACK - FLOAT_TOLERANCE
        )
        if (
            escape >= 0.0
            # v122: -1 is the no-bullets-in-reach sentinel of the final pass,
            # not a clearance; comparing it against a recorded escape fired a
            # spurious concession on v121 smoke capture 17514 (replayed
            # emitted clearance 681 vs best 685 — no concession occurred).
            and final >= 0.0
            and final < escape - 60.0 - FLOAT_TOLERANCE
            and not body_emergency_is_best_available
        ):
            reasons.append("projectile concession exceeds 60 units")
        if body_best >= 0.0:
            required_body = _required_body_floor(row, True)
            if body_selected < required_body - FLOAT_TOLERANCE:
                reasons.append("selected body path missed the required near-best tier")
        replay = row.get("route_replay")
        if replay is not None:
            # v116: continuous-route gates. The recorded diagnostics above came
            # from the sampled grid and could not see fast crossings; these two
            # checks replay the emitted command against raw entity motion.
            if (
                replay["emitted_projectile_clearance"] < ROUTE_PROJ_CONTACT
                and replay["best_projectile_clearance"]
                >= replay["emitted_projectile_clearance"] + ROUTE_MIN_GAIN - FLOAT_TOLERANCE
            ):
                reasons.append(
                    "emitted route crossed a projectile path while a clearer sampled lane existed"
                )
            if (
                replay["emitted_body_clearance"] < ROUTE_BODY_CONTACT
                and replay["best_body_clearance"]
                >= max(BODY_TIER, replay["emitted_body_clearance"] + ROUTE_MIN_GAIN)
                - FLOAT_TOLERANCE
            ):
                reasons.append(
                    "emitted route crossed an enemy body while a clearer sampled lane existed"
                )
        if reasons:
            violations.append({**row, "reasons": reasons})
    return violations


def audit_run(
    run_dir: Path,
    expected_policy: str | None = None,
    expected_mod: str | None = None,
    expected_schema_hash: str | None = None,
    legacy_sampled: bool = False,
) -> dict[str, Any]:
    events_path = run_dir / "events.jsonl"
    summary_path = run_dir / "summary.json"
    events: list[dict[str, Any]] = []
    malformed_lines: list[int] = []
    for line_number, line in enumerate(events_path.read_text(encoding="utf-8").splitlines(), 1):
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            malformed_lines.append(line_number)
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    captures = [event["payload"] for event in events if event.get("event") == "combat_capture"]
    late = [payload for payload in captures if int(payload.get("wave", 0)) >= LATE_WAVE]
    fresh = [payload for payload in captures if payload["teacher"].get("action_fresh", False)]
    fresh_late = [payload for payload in late if payload["teacher"].get("action_fresh", False)]
    body_tier_violations: list[dict[str, Any]] = []
    body_repair_violations: list[dict[str, Any]] = []
    body_diagnostic_mismatches: list[dict[str, Any]] = []
    missing_body_diagnostic_captures: list[int] = []
    projectile_floor_violations: list[dict[str, Any]] = []
    unavailable_projectile_floor_samples: list[dict[str, Any]] = []
    sampled_action_violations: list[int] = []
    wall_recovery_violations: list[dict[str, Any]] = []
    wall_body_relief_violations: list[dict[str, Any]] = []
    wall_body_relief_selection_violations: list[dict[str, Any]] = []
    hard_wall_violations: list[dict[str, Any]] = []
    active_body_repairs = 0
    active_body_emergencies = 0
    active_projectile_safety = 0
    active_wall_recovery = 0
    active_wall_body_relief = 0
    body_diagnostic_captures = 0
    # v117: finale captures must land on recompute ticks. The v116 smoke drew
    # an unlucky capture/decision phase (0 of 496 wave-20 captures fresh), so
    # every fresh-gated check silently skipped the fatal wave. Legacy replays
    # predate the alignment and are exempt.
    nonfresh_finale_captures: list[int] = []
    if not legacy_sampled:
        nonfresh_finale_captures = [
            payload["capture_seq"]
            for payload in captures
            if int(payload.get("wave", 0)) >= 20
            and not payload["teacher"].get("action_fresh", False)
        ]
    for payload in late:
        faults = _hard_wall_faults(payload)
        if faults:
            hard_wall_violations.append(
                {"capture_seq": payload["capture_seq"], "walls": faults}
            )
        relief_fault = _wall_body_relief_violation(payload, legacy_sampled)
        if relief_fault is not None:
            wall_body_relief_violations.append(relief_fault)
        debug = payload["teacher"]["contributions"]["finale_translation"]
        if bool(debug.get("wall_body_relief_active", False)):
            if bool(debug.get("loot_dash_active", False)):
                # v118: a dash deliberately accepts crowd pressure; the relief
                # near-best tier does not apply while it runs. The dash gates
                # below still bound its duration and HP floor.
                continue
            active_wall_body_relief += 1
            projectiles = payload["entities"].get("projectiles", [])
            if projectiles and not payload["teacher"].get("action_fresh", False):
                # A held diagnostic does not contain the current projectile-tier
                # candidate set. Projectile-specific audits cover that interval.
                continue
            if projectiles:
                selected = float(debug.get("body_selected_clearance", -1.0))
                relief_best = float(debug.get("wall_relief_best_body_clearance", -1.0))
            else:
                selected = _body_clearance(payload, legacy_sampled)
                relief_best, _ = _best_hard_safe_body_clearance(payload, legacy_sampled)
            required = relief_best - BODY_SLACK
            if relief_best < 0.0 or selected < required - FLOAT_TOLERANCE:
                wall_body_relief_selection_violations.append(
                    {
                        "capture_seq": payload["capture_seq"],
                        "selected": selected,
                        "relief_best": relief_best,
                        "required": required,
                    }
                )
    # v118 loot-dash gates: episodes must stay within the runtime commit bound
    # (72 decision ticks at 60 Hz ~ 24 captures at 20 Hz) and must not run at
    # critically low HP (runtime aborts below 40% of max).
    loot_dash_violations: list[dict[str, Any]] = []
    loot_dash_capture_count = 0
    dash_streak = 0
    # v123: strength diagnostics are audited on every capture (inert on legacy).
    strength_violations: list[dict[str, Any]] = []
    for payload in captures:
        debug = payload["teacher"]["contributions"]["finale_translation"]
        strength_fault = _strength_violation(payload)
        if strength_fault is not None:
            strength_violations.append(strength_fault)
        if bool(debug.get("loot_dash_active", False)):
            loot_dash_capture_count += 1
            dash_streak += 1
            if dash_streak == LOOT_DASH_MAX_CAPTURES + 1:
                loot_dash_violations.append(
                    {
                        "capture_seq": payload["capture_seq"],
                        "reason": "dash episode exceeded the runtime commit bound",
                    }
                )
            player = payload.get("player", {})
            max_hp = max(float(player.get("max_hp", 0.0)), 1.0)
            hp_ratio = float(player.get("hp", 0.0)) / max_hp
            # v123 captures use the wave-indexed, strength-shifted floor
            # (abort = 0.8 x effective arm; audit floor = abort - 0.05). Legacy
            # captures keep the flat v122 floor.
            if _is_v123_capture(debug):
                dash_floor = _dash_audit_hp_floor(
                    payload.get("wave"), debug.get("strength_tier")
                )
            else:
                dash_floor = LEGACY_LOOT_DASH_MIN_HP_RATIO
            if hp_ratio < dash_floor - FLOAT_TOLERANCE:
                loot_dash_violations.append(
                    {
                        "capture_seq": payload["capture_seq"],
                        "reason": "dash active below the HP floor",
                        "hp_ratio": hp_ratio,
                        "required": dash_floor,
                    }
                )
        else:
            dash_streak = 0
    for payload in fresh:
        debug = payload["teacher"]["contributions"]["finale_translation"]
        active_projectile_safety += bool(debug.get("projectile_safety_active", False))
        active_wall_recovery += bool(debug.get("wall_recovery_active", False))
        if float(debug.get("body_selected_clearance", -1.0)) == -1.0:
            if payload["entities"].get("enemies") or payload["entities"].get("bosses"):
                missing_body_diagnostic_captures.append(payload["capture_seq"])
            continue
        body_diagnostic_captures += 1
        input_clearance = float(debug["body_input_clearance"])
        best_clearance = float(debug["body_best_clearance"])
        selected_clearance = float(debug["body_selected_clearance"])
        body_floor = _required_body_floor(debug, True, int(payload.get("wave", 0)))
        active_body_emergencies += bool(debug.get("body_emergency_active", False))
        if selected_clearance < body_floor - FLOAT_TOLERANCE:
            body_tier_violations.append(
                {
                    "capture_seq": payload["capture_seq"],
                    "input": input_clearance,
                    "best": best_clearance,
                    "selected": selected_clearance,
                    "required": body_floor,
                }
            )
        active = bool(debug.get("body_safety_active", False))
        if active:
            active_body_repairs += 1
            if not _is_sampled_direction(payload):
                sampled_action_violations.append(payload["capture_seq"])
        if input_clearance < BODY_TIER and best_clearance >= BODY_TIER:
            if not active or selected_clearance < BODY_TIER - FLOAT_TOLERANCE:
                body_repair_violations.append(
                    {
                        "capture_seq": payload["capture_seq"],
                        "input": input_clearance,
                        "best": best_clearance,
                        "selected": selected_clearance,
                        "active": active,
                    }
                )
        projectile_floor = float(debug.get("body_projectile_floor", -1.0e18))
        selected_projectile = float(debug.get("body_selected_projectile_clearance", -1.0))
        if _body_projectile_floor_unavailable(debug):
            unavailable_projectile_floor_samples.append(
                {
                    "capture_seq": payload["capture_seq"],
                    "floor": projectile_floor,
                    "preserved_body_clearance": selected_clearance,
                }
            )
        elif selected_projectile < projectile_floor - FLOAT_TOLERANCE:
            projectile_floor_violations.append(
                {
                    "capture_seq": payload["capture_seq"],
                    "floor": projectile_floor,
                    "selected": selected_projectile,
                }
            )
        recomputed = _body_clearance(payload, legacy_sampled)
        if abs(recomputed - selected_clearance) > FLOAT_TOLERANCE:
            body_diagnostic_mismatches.append(
                {
                    "capture_seq": payload["capture_seq"],
                    "diagnostic": selected_clearance,
                    "recomputed": recomputed,
                }
            )
        wall_progress_fault = _wall_recovery_progress_violation(payload)
        if wall_progress_fault is not None:
            wall_recovery_violations.append(wall_progress_fault)
    identity_violations: list[str] = []
    if expected_policy and summary.get("policy_version") != expected_policy:
        identity_violations.append("summary policy mismatch")
    if expected_mod and summary.get("mod_version") != expected_mod:
        identity_violations.append("summary mod mismatch")
    if expected_schema_hash:
        mismatches = sum(
            payload.get("capture_schema_hash") != expected_schema_hash for payload in captures
        )
        if mismatches:
            identity_violations.append(f"{mismatches} capture schema mismatches")
    terminal_valid = bool(events) and events[-1].get("event") == "run_end"
    telemetry_error_events = sum(event.get("event") == "error" for event in events)
    summary_violations: list[str] = []
    if not summary.get("telemetry_complete", False):
        summary_violations.append("telemetry_complete is false")
    for field in ("errors", "hangs", "illegal_actions"):
        if int(summary.get(field, 0)) != 0:
            summary_violations.append(f"summary {field} is nonzero")
    first_capture_ts = min(
        (int(payload["observation_ts_ms"]) for payload in captures), default=None
    )
    damage_events = _damage_rows(events, first_capture_ts)
    avoidable_damage_violations = _avoidable_damage_violations(damage_events)
    violations = (
        len(malformed_lines)
        + len(identity_violations)
        + len(summary_violations)
        + len(body_tier_violations)
        + len(body_repair_violations)
        + len(body_diagnostic_mismatches)
        + len(missing_body_diagnostic_captures)
        + len(projectile_floor_violations)
        + len(sampled_action_violations)
        + len(wall_recovery_violations)
        + len(wall_body_relief_violations)
        + len(wall_body_relief_selection_violations)
        + len(hard_wall_violations)
        + len(avoidable_damage_violations)
        + len(loot_dash_violations)
        + len(strength_violations)
        + (1 if nonfresh_finale_captures else 0)
        + telemetry_error_events
        + (0 if terminal_valid else 1)
    )
    return {
        "run_id": run_dir.name,
        "policy_version": summary.get("policy_version"),
        "mod_version": summary.get("mod_version"),
        "result": summary.get("result"),
        "last_wave": summary.get("last_wave"),
        "telemetry_complete": summary.get("telemetry_complete"),
        "summary_errors": summary.get("errors"),
        "summary_hangs": summary.get("hangs"),
        "summary_illegal_actions": summary.get("illegal_actions"),
        "terminal_valid": terminal_valid,
        "event_count": len(events),
        "capture_count": len(captures),
        "waves_represented": sorted({int(payload["wave"]) for payload in captures}),
        "late_capture_count": len(late),
        "fresh_capture_count": len(fresh),
        "fresh_late_capture_count": len(fresh_late),
        "body_diagnostic_capture_count": body_diagnostic_captures,
        "active_body_repairs": active_body_repairs,
        "active_body_emergencies": active_body_emergencies,
        "active_projectile_safety": active_projectile_safety,
        "active_wall_recovery": active_wall_recovery,
        "active_wall_body_relief": active_wall_body_relief,
        "malformed_lines": malformed_lines,
        "identity_violations": identity_violations,
        "summary_violations": summary_violations,
        "telemetry_error_events": telemetry_error_events,
        "body_tier_violations": body_tier_violations,
        "body_repair_violations": body_repair_violations,
        "body_diagnostic_mismatches": body_diagnostic_mismatches,
        "missing_body_diagnostic_captures": missing_body_diagnostic_captures,
        "unavailable_projectile_floor_samples": unavailable_projectile_floor_samples,
        "projectile_floor_violations": projectile_floor_violations,
        "sampled_action_violations": sampled_action_violations,
        "wall_recovery_violations": wall_recovery_violations,
        "wall_body_relief_violations": wall_body_relief_violations,
        "wall_body_relief_selection_violations": wall_body_relief_selection_violations,
        "hard_wall_violations": hard_wall_violations,
        "nonfresh_finale_capture_count": len(nonfresh_finale_captures),
        "nonfresh_finale_capture_sample": nonfresh_finale_captures[:20],
        "loot_dash_capture_count": loot_dash_capture_count,
        "loot_dash_violations": loot_dash_violations,
        "strength_violations": strength_violations,
        "damage_events": damage_events,
        "avoidable_damage_violations": avoidable_damage_violations,
        "events_sha256": _sha256(events_path),
        "summary_sha256": _sha256(summary_path),
        "violation_count": violations,
        "accepted": violations == 0,
    }


def render_markdown(audit: dict[str, Any]) -> str:
    lines = ["# WP2 teacher safety audit", ""]
    lines.append(f"Runs: **{audit['run_count']}**; accepted: **{audit['accepted_run_count']}**.")
    lines.append("")
    for run in audit["runs"]:
        status = "accepted" if run["accepted"] else "rejected"
        lines.extend(
            [
                f"## `{run['run_id']}` -- {status}",
                "",
                f"- Result: `{run['result']}` through wave {run['last_wave']}.",
                f"- Captures: {run['capture_count']} total; "
                f"{run['fresh_capture_count']} fresh decisions; "
                f"{run['late_capture_count']} late; "
                f"{run['fresh_late_capture_count']} fresh late decisions.",
                f"- Safety activations: {run['active_body_repairs']} body, "
                f"{run['active_projectile_safety']} projectile, "
                f"{run['active_wall_recovery']} wall, "
                f"{run['active_wall_body_relief']} wall-body relief.",
                f"- Violations: **{run['violation_count']}**.",
                f"- Damage events retained for all-wave review: {len(run['damage_events'])}.",
                f"- Avoidable damage-path violations: "
                f"{len(run['avoidable_damage_violations'])}.",
                f"- Hidden wall-relief body lanes: "
                f"{len(run['wall_body_relief_violations'])}.",
                f"- Preserved-command body fallbacks with no eligible projectile-floor "
                f"sample: {len(run['unavailable_projectile_floor_samples'])}.",
                f"- Events SHA-256: `{run['events_sha256']}`.",
                f"- Summary SHA-256: `{run['summary_sha256']}`.",
                "",
            ]
        )
    return "\n".join(lines)


def audit_runs(
    runs_dir: Path,
    run_ids: Iterable[str],
    expected_policy: str | None,
    expected_mod: str | None,
    expected_schema_hash: str | None,
    legacy_sampled: bool = False,
) -> dict[str, Any]:
    runs = [
        audit_run(
            runs_dir / run_id,
            expected_policy,
            expected_mod,
            expected_schema_hash,
            legacy_sampled,
        )
        for run_id in run_ids
    ]
    return {
        "run_count": len(runs),
        "accepted_run_count": sum(run["accepted"] for run in runs),
        "violation_count": sum(int(run["violation_count"]) for run in runs),
        "runs": runs,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--runs-dir",
        type=Path,
        default=Path(os.environ.get("APPDATA", "")) / "Brotato" / "brotato_agent" / "runs",
    )
    parser.add_argument("--run-id", action="append", required=True)
    parser.add_argument("--expected-policy")
    parser.add_argument("--expected-mod")
    parser.add_argument("--expected-schema-hash")
    parser.add_argument("--output-prefix", default="wp2_teacher_safety_audit")
    parser.add_argument(
        "--legacy-sampled-diagnostics",
        action="store_true",
        help=(
            "Replay frozen v107-v115 evidence whose recorded diagnostics used "
            "the discrete sample grid. Diagnostic-parity and tier checks use "
            "the legacy formula; the continuous damage-route gates still run."
        ),
    )
    args = parser.parse_args()
    audit = audit_runs(
        args.runs_dir,
        args.run_id,
        args.expected_policy,
        args.expected_mod,
        args.expected_schema_hash,
        args.legacy_sampled_diagnostics,
    )
    output_dir = ROOT / "reports" / "wp2"
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{args.output_prefix}.json"
    markdown_path = output_dir / f"{args.output_prefix}.md"
    json_path.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(render_markdown(audit), encoding="utf-8")
    print(json.dumps({"json": str(json_path), "markdown": str(markdown_path), **audit}, indent=2))
    return 0 if audit["violation_count"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
