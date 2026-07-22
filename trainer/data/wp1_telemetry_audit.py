"""Read-only WP1 combat telemetry audit used to freeze WP2 interface needs."""

from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


REQUIRED_WP2_FIELDS = {
    "player_position": (("player", "x"), ("player", "y")),
    "player_velocity": (("player", "vx"), ("player", "vy")),
    "wave_timer": (("wave_elapsed_ms",), ("wave_remaining_ms",)),
    "enemy_entities": (("enemies",),),
    "projectile_entities": (("projectiles",),),
    "material_entities": (("materials",),),
    "consumable_entities": (("consumable_entities",),),
    "crate_entities": (("crates",),),
    "obstacle_entities": (("obstacles",),),
    "teacher_action": (("move", "x"), ("move", "y")),
    "previous_action": (("previous_move", "x"), ("previous_move", "y")),
    "teacher_contributions": (("debug", "field_contributions"),),
    "observation_age": (("observation_age_ms",),),
}


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return float(ordered[lower])
    fraction = position - lower
    return float(ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction)


def _percentiles(values: list[float]) -> dict[str, float | None]:
    return {
        "min": min(values) if values else None,
        "p50": percentile(values, 0.50),
        "p90": percentile(values, 0.90),
        "p95": percentile(values, 0.95),
        "p99": percentile(values, 0.99),
        "max": max(values) if values else None,
    }


def _nested_present(payload: dict[str, Any], path: tuple[str, ...]) -> bool:
    current: Any = payload
    for part in path:
        if not isinstance(current, dict) or part not in current:
            return False
        current = current[part]
    return current is not None


def _load_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: {exc}") from exc


def audit_runs(runs_dir: Path, run_ids: set[str] | None = None) -> dict[str, Any]:
    run_paths = sorted(path for path in runs_dir.iterdir() if path.is_dir())
    if run_ids is not None:
        run_paths = [path for path in run_paths if path.name in run_ids]

    gaps: list[float] = []
    action_magnitudes: list[float] = []
    entity_counts: dict[str, list[float]] = defaultdict(list)
    field_hits: Counter[str] = Counter()
    wave_ticks: Counter[int] = Counter()
    results: Counter[str] = Counter()
    signatures: Counter[tuple[Any, ...]] = Counter()
    invalid_actions = 0
    malformed_events = 0
    damage_events = 0
    low_health_ticks = 0
    low_health_observable_ticks = 0
    terminal_runs = 0
    total_ticks = 0
    cleaned_ticks = 0
    per_run: list[dict[str, Any]] = []

    for run_path in run_paths:
        events_path = run_path / "events.jsonl"
        if not events_path.exists():
            malformed_events += 1
            continue
        previous_tick_ms: int | None = None
        run_ticks = 0
        run_terminal = False
        run_result = "unknown"
        for event in _load_jsonl(events_path):
            event_type = event.get("event")
            payload = event.get("payload", {})
            if event_type == "player_damage":
                damage_events += 1
            if event_type == "run_end":
                run_terminal = True
                run_result = str(payload.get("result", "unknown"))
                results[run_result] += 1
            if event_type != "combat_tick" or not isinstance(payload, dict):
                continue

            total_ticks += 1
            run_ticks += 1
            timestamp = int(event.get("ts_ms", 0))
            if previous_tick_ms is not None and timestamp >= previous_tick_ms:
                gaps.append(float(timestamp - previous_tick_ms))
            previous_tick_ms = timestamp

            for name, required_paths in REQUIRED_WP2_FIELDS.items():
                if all(_nested_present(payload, path) for path in required_paths):
                    field_hits[name] += 1

            debug = payload.get("debug", {}) if isinstance(payload.get("debug"), dict) else {}
            counts = {
                "enemies": debug.get("enemies"),
                "projectiles": debug.get("projectiles"),
                "materials": payload.get("loot"),
                "consumables": payload.get("consumables"),
            }
            for name, value in counts.items():
                if isinstance(value, (int, float)) and math.isfinite(float(value)):
                    entity_counts[name].append(float(value))

            move = payload.get("move", {}) if isinstance(payload.get("move"), dict) else {}
            x = move.get("x")
            y = move.get("y")
            valid_action = (
                isinstance(x, (int, float))
                and isinstance(y, (int, float))
                and math.isfinite(float(x))
                and math.isfinite(float(y))
            )
            if valid_action:
                magnitude = math.hypot(float(x), float(y))
                action_magnitudes.append(magnitude)
                cleaned_ticks += 1
            else:
                invalid_actions += 1

            wave = int(payload.get("wave", 0))
            wave_ticks[wave] += 1
            hp = payload.get("hp")
            player = payload.get("player", {}) if isinstance(payload.get("player"), dict) else {}
            max_hp = player.get("max_hp")
            if isinstance(hp, (int, float)) and isinstance(max_hp, (int, float)) and max_hp > 0:
                low_health_observable_ticks += 1
                if float(hp) / float(max_hp) < 0.35:
                    low_health_ticks += 1

            signatures[(wave, round(float(x), 3) if valid_action else None,
                        round(float(y), 3) if valid_action else None,
                        counts["enemies"], counts["projectiles"], hp,
                        counts["materials"], counts["consumables"])] += 1

        if run_terminal:
            terminal_runs += 1
        per_run.append({
            "run_id": run_path.name,
            "combat_ticks": run_ticks,
            "terminal": run_terminal,
            "result": run_result,
        })

    duplicate_ticks = sum(count - 1 for count in signatures.values() if count > 1)
    gap_over_750 = sum(1 for gap in gaps if gap > 750.0)
    gap_over_1000 = sum(1 for gap in gaps if gap > 1000.0)
    field_availability = {
        name: {
            "ticks_present": field_hits[name],
            "fraction": field_hits[name] / total_ticks if total_ticks else 0.0,
        }
        for name in REQUIRED_WP2_FIELDS
    }

    return {
        "schema_version": "wp1_telemetry_audit_v1",
        "runs_dir": str(runs_dir),
        "runs": len(run_paths),
        "terminal_runs": terminal_runs,
        "results": dict(sorted(results.items())),
        "combat_ticks": total_ticks,
        "cleaned_transition_estimate": cleaned_ticks,
        "target_transition_gap": max(0, 200_000 - cleaned_ticks),
        "malformed_events": malformed_events,
        "invalid_or_nonfinite_actions": invalid_actions,
        "tick_gap_ms": _percentiles(gaps),
        "tick_gaps_over_750ms": gap_over_750,
        "tick_gaps_over_1000ms": gap_over_1000,
        "action_magnitude": _percentiles(action_magnitudes),
        "entity_count_percentiles": {
            name: _percentiles(values) for name, values in sorted(entity_counts.items())
        },
        "field_availability": field_availability,
        "damage_events": damage_events,
        "low_health_ticks": low_health_ticks,
        "low_health_observable_ticks": low_health_observable_ticks,
        "wave_tick_counts": {str(key): wave_ticks[key] for key in sorted(wave_ticks)},
        "exact_signature_duplicate_ticks": duplicate_ticks,
        "exact_signature_duplicate_fraction": duplicate_ticks / total_ticks if total_ticks else 0.0,
        "capacity_blockers": [
            "Per-entity enemy arrays are absent; count percentiles cannot define a threat-aware capacity.",
            "Per-entity hostile projectile arrays are absent.",
            "Materials and consumables are counts only; positions and velocities are absent.",
            "Crate and obstacle counts/entities are absent.",
        ],
        "semantic_blockers": [
            "Player position/velocity and wave timer are absent from the certified v72 corpus.",
            "Observation-to-action delay and observation age are not recorded.",
            "Previous action and teacher field contributions are absent.",
            "Enemy/projectile identity, position, velocity, radius, health, and threat features are absent.",
            "Charger/elite/boss categories cannot be derived reliably from v72 ticks.",
            "Invalid/freed-object incidence is not explicitly observable in v72 telemetry.",
        ],
        "per_run": per_run,
    }


def render_markdown(audit: dict[str, Any]) -> str:
    gaps = audit["tick_gap_ms"]
    actions = audit["action_magnitude"]
    lines = [
        "# WP2 Stage-A WP1 telemetry audit",
        "",
        f"Result: **{'PASS FOR INTERFACE REPAIR' if audit['runs'] else 'FAIL'}**",
        "",
        f"- Runs: {audit['runs']} ({audit['terminal_runs']} terminal)",
        f"- Combat ticks: {audit['combat_ticks']}",
        f"- Valid transition estimate: {audit['cleaned_transition_estimate']}",
        f"- Gap to 200,000-transition minimum: {audit['target_transition_gap']}",
        f"- Tick gap p50/p99/max: {gaps['p50']} / {gaps['p99']} / {gaps['max']} ms",
        f"- Action magnitude p50/p99/max: {actions['p50']} / {actions['p99']} / {actions['max']}",
        f"- Exact reduced-signature duplicate fraction: {audit['exact_signature_duplicate_fraction']:.4f}",
        f"- Invalid/non-finite actions: {audit['invalid_or_nonfinite_actions']}",
        "",
        "## Count percentiles",
        "",
        "These are aggregate counts only and are insufficient to select entity-array capacities.",
        "",
        "| Group | p50 | p90 | p95 | p99 | max |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for name, values in audit["entity_count_percentiles"].items():
        lines.append(
            f"| {name} | {values['p50']} | {values['p90']} | {values['p95']} | "
            f"{values['p99']} | {values['max']} |"
        )
    lines.extend(["", "## Required field availability", "", "| Field | Ticks | Fraction |", "|---|---:|---:|"])
    for name, values in audit["field_availability"].items():
        lines.append(f"| {name} | {values['ticks_present']} | {values['fraction']:.4f} |")
    lines.extend(["", "## Blocking telemetry repairs", ""])
    for blocker in audit["semantic_blockers"] + audit["capacity_blockers"]:
        lines.append(f"- {blocker}")
    lines.extend([
        "",
        "The certified v72 corpus remains valid WP1 evidence, but it cannot directly produce",
        "`combat_obs_v1` or the mandatory 200k transition dataset. Add a compatible new",
        "combat-telemetry schema, validate it in focused live teacher runs, and compute",
        "capacities from those per-entity distributions before dataset harvesting.",
        "",
    ])
    return "\n".join(lines)
