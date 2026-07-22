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
HARD_WALL_MARGIN = 96.0
COMMAND_HORIZON_SEC = 0.30
WALL_LOOKAHEAD = 260.0
WALL_RECOVERY_RELEASE = 520.0
ESCAPE_HORIZON_SEC = 0.60
ESCAPE_TIME_SAMPLES = 6
ESCAPE_DIRECTIONS = 24
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


def _body_clearance(payload: dict[str, Any]) -> float:
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


def _late_damage_rows(events: list[dict[str, Any]], first_late_ts: int | None) -> list[dict[str, Any]]:
    if first_late_ts is None:
        return []
    captures = [event for event in events if event.get("event") == "combat_capture"]
    rows: list[dict[str, Any]] = []
    for event in events:
        if event.get("event") != "player_damage" or int(event.get("ts_ms", -1)) < first_late_ts:
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
                }
            )
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
        if escape >= 0.0 and final < escape - 60.0 - FLOAT_TOLERANCE:
            reasons.append("projectile concession exceeds 60 units")
        if body_best >= BODY_TIER and body_selected < BODY_TIER - FLOAT_TOLERANCE:
            reasons.append("selected body path missed available 45-unit tier")
        if reasons:
            violations.append({**row, "reasons": reasons})
    return violations


def audit_run(
    run_dir: Path,
    expected_policy: str | None = None,
    expected_mod: str | None = None,
    expected_schema_hash: str | None = None,
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
    fresh = [payload for payload in late if payload["teacher"].get("action_fresh", False)]
    body_tier_violations: list[dict[str, Any]] = []
    body_repair_violations: list[dict[str, Any]] = []
    body_diagnostic_mismatches: list[dict[str, Any]] = []
    projectile_floor_violations: list[dict[str, Any]] = []
    sampled_action_violations: list[int] = []
    wall_recovery_violations: list[dict[str, Any]] = []
    hard_wall_violations: list[dict[str, Any]] = []
    active_body_repairs = 0
    active_projectile_safety = 0
    active_wall_recovery = 0
    body_diagnostic_captures = 0
    for payload in late:
        faults = _hard_wall_faults(payload)
        if faults:
            hard_wall_violations.append(
                {"capture_seq": payload["capture_seq"], "walls": faults}
            )
    for payload in fresh:
        debug = payload["teacher"]["contributions"]["finale_translation"]
        active_projectile_safety += bool(debug.get("projectile_safety_active", False))
        active_wall_recovery += bool(debug.get("wall_recovery_active", False))
        if float(debug.get("body_selected_clearance", -1.0)) == -1.0:
            continue
        body_diagnostic_captures += 1
        input_clearance = float(debug["body_input_clearance"])
        best_clearance = float(debug["body_best_clearance"])
        selected_clearance = float(debug["body_selected_clearance"])
        body_floor = BODY_TIER if best_clearance >= BODY_TIER else best_clearance - BODY_SLACK
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
        if selected_projectile < projectile_floor - FLOAT_TOLERANCE:
            projectile_floor_violations.append(
                {
                    "capture_seq": payload["capture_seq"],
                    "floor": projectile_floor,
                    "selected": selected_projectile,
                }
            )
        recomputed = _body_clearance(payload)
        if abs(recomputed - selected_clearance) > FLOAT_TOLERANCE:
            body_diagnostic_mismatches.append(
                {
                    "capture_seq": payload["capture_seq"],
                    "diagnostic": selected_clearance,
                    "recomputed": recomputed,
                }
            )
        if active and bool(debug.get("wall_recovery_active", False)):
            current_wall, future_wall = _wall_distances(payload)
            if (
                current_wall < WALL_RECOVERY_RELEASE
                and future_wall <= current_wall + FLOAT_TOLERANCE
            ):
                wall_recovery_violations.append(
                    {
                        "capture_seq": payload["capture_seq"],
                        "current": current_wall,
                        "future": future_wall,
                    }
                )
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
    first_late_ts = min((int(payload["observation_ts_ms"]) for payload in late), default=None)
    late_damage_events = _late_damage_rows(events, first_late_ts)
    avoidable_damage_violations = _avoidable_damage_violations(late_damage_events)
    violations = (
        len(malformed_lines)
        + len(identity_violations)
        + len(summary_violations)
        + len(body_tier_violations)
        + len(body_repair_violations)
        + len(body_diagnostic_mismatches)
        + len(projectile_floor_violations)
        + len(sampled_action_violations)
        + len(wall_recovery_violations)
        + len(hard_wall_violations)
        + len(avoidable_damage_violations)
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
        "fresh_late_capture_count": len(fresh),
        "body_diagnostic_capture_count": body_diagnostic_captures,
        "active_body_repairs": active_body_repairs,
        "active_projectile_safety": active_projectile_safety,
        "active_wall_recovery": active_wall_recovery,
        "malformed_lines": malformed_lines,
        "identity_violations": identity_violations,
        "summary_violations": summary_violations,
        "telemetry_error_events": telemetry_error_events,
        "body_tier_violations": body_tier_violations,
        "body_repair_violations": body_repair_violations,
        "body_diagnostic_mismatches": body_diagnostic_mismatches,
        "projectile_floor_violations": projectile_floor_violations,
        "sampled_action_violations": sampled_action_violations,
        "wall_recovery_violations": wall_recovery_violations,
        "hard_wall_violations": hard_wall_violations,
        "late_damage_events": late_damage_events,
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
                f"- Captures: {run['capture_count']} total; {run['late_capture_count']} late; "
                f"{run['fresh_late_capture_count']} fresh late decisions.",
                f"- Safety activations: {run['active_body_repairs']} body, "
                f"{run['active_projectile_safety']} projectile, "
                f"{run['active_wall_recovery']} wall.",
                f"- Violations: **{run['violation_count']}**.",
                f"- Late damage events retained for review: {len(run['late_damage_events'])}.",
                f"- Avoidable damage-path violations: "
                f"{len(run['avoidable_damage_violations'])}.",
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
) -> dict[str, Any]:
    runs = [
        audit_run(runs_dir / run_id, expected_policy, expected_mod, expected_schema_hash)
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
    args = parser.parse_args()
    audit = audit_runs(
        args.runs_dir,
        args.run_id,
        args.expected_policy,
        args.expected_mod,
        args.expected_schema_hash,
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
