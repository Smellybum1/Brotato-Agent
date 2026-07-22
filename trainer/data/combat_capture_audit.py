"""Audit raw WP2 combat-capture telemetry without mutating source runs."""
from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable


CAPTURE_EVENT = "combat_capture"
CAPTURE_ENVELOPE_VERSION = "2.0.0"
GROUPS = ("enemies", "bosses", "projectiles", "materials", "consumables", "crates", "obstacles")
WAVE_BANDS = ((1, 5), (6, 10), (11, 15), (16, 19), (20, 20))


def percentile(values: Iterable[float], quantile: float) -> float | None:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return None
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * quantile
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _distribution(values: Iterable[float]) -> dict[str, float | int | None]:
    materialized = list(values)
    return {
        "count": len(materialized),
        "p50": percentile(materialized, 0.50),
        "p90": percentile(materialized, 0.90),
        "p95": percentile(materialized, 0.95),
        "p99": percentile(materialized, 0.99),
        "max": max(materialized) if materialized else None,
    }


def _wave_band(wave: int) -> str:
    for lower, upper in WAVE_BANDS:
        if lower <= wave <= upper:
            return f"{lower}-{upper}"
    return "other"


def _finite_vector(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    try:
        return math.isfinite(float(value["x"])) and math.isfinite(float(value["y"]))
    except (KeyError, TypeError, ValueError):
        return False


def _flatten_numeric(prefix: str, value: Any, output: dict[str, list[float]]) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            _flatten_numeric(f"{prefix}.{key}" if prefix else str(key), child, output)
    elif isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value)):
        output[prefix].append(float(value))


def _schema_hash(schema_path: Path) -> str:
    return hashlib.sha256(schema_path.read_bytes()).hexdigest().upper()


def _iter_run_dirs(runs_dir: Path, run_ids: set[str] | None) -> Iterable[Path]:
    if run_ids:
        for run_id in sorted(run_ids):
            path = runs_dir / run_id
            if path.is_dir():
                yield path
        return
    for path in sorted(runs_dir.iterdir() if runs_dir.exists() else []):
        if path.is_dir() and (path / "events.jsonl").exists():
            yield path


def audit_capture_runs(
    runs_dir: Path,
    schema_path: Path,
    run_ids: set[str] | None = None,
) -> dict[str, Any]:
    expected_hash = _schema_hash(schema_path)
    run_summaries: list[dict[str, Any]] = []
    captures: list[dict[str, Any]] = []
    count_values: dict[str, list[int]] = defaultdict(list)
    band_counts: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
    invalid_totals: Counter[str] = Counter()
    dropped_totals: Counter[str] = Counter()
    contribution_values: dict[str, list[float]] = defaultdict(list)
    wave_capture_counts: Counter[int] = Counter()
    severe_counts: Counter[str] = Counter()
    signatures: Counter[tuple[Any, ...]] = Counter()
    dt_values: list[float] = []
    age_values: list[float] = []
    action_magnitudes: list[float] = []
    malformed_lines = 0
    schema_mismatches = 0
    invalid_actions = 0
    invalid_captures = 0

    for run_dir in _iter_run_dirs(runs_dir, run_ids):
        path = run_dir / "events.jsonl"
        terminal = False
        errors = 0
        damage_events = 0
        run_captures = 0
        run_bytes = path.stat().st_size
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                malformed_lines += 1
                continue
            event_type = event.get("event")
            terminal = terminal or event_type == "run_end"
            errors += int(event_type == "error")
            damage_events += int(event_type == "player_damage")
            if event_type != CAPTURE_EVENT:
                continue
            payload = event.get("payload")
            if not isinstance(payload, dict):
                invalid_captures += 1
                continue
            if (
                event.get("schema_version") != CAPTURE_ENVELOPE_VERSION
                or payload.get("capture_schema_hash") != expected_hash
            ):
                schema_mismatches += 1
                continue
            run_captures += 1
            captures.append(payload)
            wave = int(payload.get("wave", 0))
            wave_capture_counts[wave] += 1
            band = _wave_band(wave)
            entities = payload.get("entities", {})
            if not isinstance(entities, dict):
                invalid_captures += 1
                continue
            group_sizes: dict[str, int] = {}
            for group in GROUPS:
                members = entities.get(group, [])
                size = len(members) if isinstance(members, list) else 0
                group_sizes[group] = size
                count_values[group].append(size)
                band_counts[band][group].append(size)
            for key, value in (payload.get("invalid_counts") or {}).items():
                invalid_totals[str(key)] += int(value)
            for key, value in (payload.get("dropped_counts") or {}).items():
                dropped_totals[str(key)] += int(value)

            dt = float(payload.get("control_dt_ms", 0))
            age = float(payload.get("observation_age_ms", 0))
            if dt > 0:
                dt_values.append(dt)
            age_values.append(age)
            valid = bool(payload.get("valid", False))
            action = (payload.get("teacher") or {}).get("action")
            if not valid:
                invalid_captures += 1
            if not _finite_vector(action):
                invalid_actions += 1
                action_x = action_y = 0.0
            else:
                action_x, action_y = float(action["x"]), float(action["y"])
                action_magnitudes.append(math.hypot(action_x, action_y))
            _flatten_numeric(
                "teacher",
                (payload.get("teacher") or {}).get("contributions", {}),
                contribution_values,
            )

            player = payload.get("player") or {}
            hp_ratio = float(player.get("hp_ratio", 1.0))
            if hp_ratio <= 0.35:
                severe_counts["low_health"] += 1
            arena = payload.get("arena") or {}
            width, height = float(arena.get("width", 0)), float(arena.get("height", 0))
            x, y = float(player.get("x", 0)), float(player.get("y", 0))
            if width > 0 and height > 0:
                clearances = (x, width - x, y, height - y)
                if min(clearances) <= 128:
                    severe_counts["near_wall"] += 1
                if sum(clearance <= 192 for clearance in clearances) >= 2:
                    severe_counts["corner"] += 1
            if group_sizes["projectiles"] >= 10:
                severe_counts["dense_projectiles"] += 1
            if group_sizes["bosses"]:
                severe_counts["boss"] += 1
            enemy_records = list(entities.get("enemies", [])) + list(entities.get("bosses", []))
            text = " ".join(
                str(enemy.get(key, "")).lower()
                for enemy in enemy_records
                if isinstance(enemy, dict)
                for key in ("name", "type_id", "script_path", "attack_path")
            )
            if "elite" in text:
                severe_counts["elite"] += 1
            if "charg" in text:
                severe_counts["charger"] += 1
            signatures[
                (
                    wave,
                    round(x / 16),
                    round(y / 16),
                    round(hp_ratio, 2),
                    *(group_sizes[group] for group in GROUPS),
                    round(action_x, 2),
                    round(action_y, 2),
                )
            ] += 1

        if run_captures:
            run_summaries.append(
                {
                    "run_id": run_dir.name,
                    "captures": run_captures,
                    "terminal": terminal,
                    "errors": errors,
                    "damage_events": damage_events,
                    "bytes": run_bytes,
                }
            )

    duplicate_rows = sum(max(count - 1, 0) for count in signatures.values())
    valid_transition_estimate = max(
        0,
        len(captures) - invalid_captures - invalid_actions - schema_mismatches,
    )
    band_distributions = {
        band: {group: _distribution(values) for group, values in groups.items()}
        for band, groups in sorted(band_counts.items())
    }
    return {
        "capture_schema_hash": expected_hash,
        "runs": run_summaries,
        "run_count": len(run_summaries),
        "terminal_run_count": sum(run["terminal"] for run in run_summaries),
        "capture_count": len(captures),
        "valid_transition_estimate": valid_transition_estimate,
        "gap_to_200000": max(200_000 - valid_transition_estimate, 0),
        "malformed_lines": malformed_lines,
        "schema_mismatches": schema_mismatches,
        "invalid_captures": invalid_captures,
        "invalid_actions": invalid_actions,
        "timing_ms": {"control_dt": _distribution(dt_values), "observation_age": _distribution(age_values)},
        "action_magnitude": _distribution(action_magnitudes),
        "entity_counts": {group: _distribution(count_values[group]) for group in GROUPS},
        "entity_counts_by_wave_band": band_distributions,
        "invalid_entity_totals": dict(sorted(invalid_totals.items())),
        "dropped_entity_totals": dict(sorted(dropped_totals.items())),
        "wave_capture_counts": {str(key): value for key, value in sorted(wave_capture_counts.items())},
        "severe_state_counts": dict(sorted(severe_counts.items())),
        "teacher_contributions": {
            key: _distribution(values) for key, values in sorted(contribution_values.items())
        },
        "near_duplicate_fraction": duplicate_rows / len(captures) if captures else 0.0,
    }


def render_markdown(audit: dict[str, Any]) -> str:
    lines = [
        "# WP2 combat-capture audit",
        "",
        f"- Runs with captures: {audit['run_count']} ({audit['terminal_run_count']} terminal)",
        f"- Captures: {audit['capture_count']}",
        f"- Valid transition estimate: {audit['valid_transition_estimate']}",
        f"- Gap to 200,000: {audit['gap_to_200000']}",
        f"- Schema mismatches: {audit['schema_mismatches']}",
        f"- Invalid captures/actions: {audit['invalid_captures']} / {audit['invalid_actions']}",
        f"- Near-duplicate fraction: {audit['near_duplicate_fraction']:.4f}",
        "",
        "## Entity count percentiles",
        "",
        "| Group | p50 | p90 | p95 | p99 | max |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for group, distribution in audit["entity_counts"].items():
        lines.append(
            f"| {group} | {distribution['p50']} | {distribution['p90']} | "
            f"{distribution['p95']} | {distribution['p99']} | {distribution['max']} |"
        )
    lines += ["", "## Severe-state capture counts", ""]
    for key, value in audit["severe_state_counts"].items():
        lines.append(f"- {key}: {value}")
    if not audit["severe_state_counts"]:
        lines.append("- none observed")
    lines += [
        "",
        "Capacities remain provisional until complete runs cover every wave band,",
        "including representative late-projectile and wave-20 boss states.",
        "",
    ]
    return "\n".join(lines)
