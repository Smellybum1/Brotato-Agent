"""Read-only live telemetry aggregation for BrotatoAgent.

The game writes append-only JSONL.  This module turns that detailed stream into
a compact, stable snapshot suitable for a human dashboard or an unattended
supervisor without touching game state.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
import json
from pathlib import Path
from typing import Any, Iterable


SLOW_OR_OFF_PLAN_GUNS = {
    "weapon_laser_gun",
    "weapon_pistol",
    "weapon_shredder",
}


def read_events(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    """Read valid events and return parse warnings separately."""
    events: list[dict[str, Any]] = []
    warnings: list[str] = []
    if not path.exists():
        return events, [f"missing telemetry: {path}"]
    with path.open("r", encoding="utf-8") as stream:
        for line_no, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                warnings.append(f"line {line_no}: invalid JSON ({exc.msg})")
                continue
            if isinstance(value, dict):
                events.append(value)
            else:
                warnings.append(f"line {line_no}: event is not an object")
    return events, warnings


def newest_events_path(runs_dir: Path) -> Path | None:
    candidates = list(runs_dir.glob("*/events.jsonl")) if runs_dir.exists() else []
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def _weapon_family(item_id: str) -> str:
    parts = item_id.rsplit("_", 1)
    if len(parts) == 2 and parts[1].isdigit():
        return parts[0]
    return item_id


def _wave_rows(events: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    waves: dict[int, dict[str, Any]] = {}
    active_wave = 0
    for event in events:
        kind = str(event.get("event", ""))
        payload = event.get("payload", {}) or {}
        if kind == "combat_tick":
            active_wave = int(payload.get("wave", active_wave) or active_wave)
            row = waves.setdefault(
                active_wave,
                {
                    "wave": active_wave,
                    "first_ts_ms": event.get("ts_ms", 0),
                    "last_ts_ms": event.get("ts_ms", 0),
                    "ticks": 0,
                    "first_hp": payload.get("hp"),
                    "last_hp": payload.get("hp"),
                    "min_hp": payload.get("hp"),
                    "max_enemies": 0,
                    "max_projectiles": 0,
                    "max_loot": 0,
                    "damage_taken": 0.0,
                },
            )
            hp = payload.get("hp")
            debug = payload.get("debug", {}) or {}
            row["last_ts_ms"] = event.get("ts_ms", row["last_ts_ms"])
            row["ticks"] += 1
            row["last_hp"] = hp
            if hp is not None:
                row["min_hp"] = hp if row["min_hp"] is None else min(row["min_hp"], hp)
            row["max_enemies"] = max(row["max_enemies"], int(debug.get("enemies", 0) or 0))
            row["max_projectiles"] = max(
                row["max_projectiles"], int(debug.get("projectiles", 0) or 0)
            )
            row["max_loot"] = max(row["max_loot"], int(payload.get("loot", 0) or 0))
        elif kind == "player_damage" and active_wave in waves:
            waves[active_wave]["damage_taken"] += float(payload.get("amount", 0) or 0)
    return [waves[key] for key in sorted(waves)]


def build_run_snapshot(
    events: list[dict[str, Any]],
    *,
    telemetry_age_sec: float | None = None,
    parse_warnings: list[str] | None = None,
) -> dict[str, Any]:
    """Aggregate a current run without making assumptions about game internals."""
    warnings = list(parse_warnings or [])
    if not events:
        return {"active": False, "event_count": 0, "alerts": warnings or ["no telemetry events"]}

    start = next((event for event in events if event.get("event") == "run_start"), events[0])
    meta = start.get("payload", {}) or {}
    last = events[-1]
    last_payload = last.get("payload", {}) or {}
    combat = [event for event in events if event.get("event") == "combat_tick"]
    last_combat = combat[-1] if combat else None
    combat_payload = (last_combat or {}).get("payload", {}) or {}
    combat_debug = combat_payload.get("debug", {}) or {}

    counts: defaultdict[str, int] = defaultdict(int)
    weapon_buys: list[str] = []
    item_buys: list[str] = []
    shop_timeline: list[dict[str, Any]] = []
    active_lock_episodes: dict[str, set[int]] = {}
    completed_lock_episodes: list[tuple[str, set[int]]] = []
    observed_wave = 0
    damage_taken = 0.0
    recoveries = 0
    terminal_result: str | None = None
    for event in events:
        kind = str(event.get("event", ""))
        payload = event.get("payload", {}) or {}
        if kind == "combat_tick":
            observed_wave = int(payload.get("wave", observed_wave) or observed_wave)
        elif kind == "player_damage":
            damage_taken += float(payload.get("amount", 0) or 0)
        elif kind == "recovery_attempt":
            recoveries += 1
        elif kind == "run_end":
            terminal_result = str(payload.get("result", "")) or None
        elif kind == "purchase_decision":
            observed_wave = int(payload.get("wave", observed_wave) or observed_wave)
            action = payload.get("action", {}) or {}
            action_type = str(action.get("type", "unknown"))
            counts[action_type] += 1
            item_id = str(action.get("item_id", ""))
            if action_type == "shop_buy" and item_id.startswith("weapon_"):
                weapon_buys.append(item_id)
            elif action_type == "shop_buy" and item_id:
                item_buys.append(item_id)
            shop_timeline.append(
                {
                    "seq": event.get("seq"),
                    "type": action_type,
                    "item_id": item_id or None,
                    "score": action.get("score"),
                    "wave": payload.get("wave"),
                    "gold_before": payload.get("gold_before"),
                    "reroll_price": payload.get("reroll_price"),
                    "lock_expired": bool(action.get("lock_expired", False)),
                }
            )
        elif kind == "purchase_offer":
            currently_locked: set[str] = set()
            for item in payload.get("items", []) or []:
                if item.get("locked"):
                    item_id = str(item.get("id", "unknown"))
                    currently_locked.add(item_id)
                    active_lock_episodes.setdefault(item_id, set()).add(observed_wave)
            for item_id in list(active_lock_episodes):
                if item_id not in currently_locked:
                    completed_lock_episodes.append(
                        (item_id, active_lock_episodes.pop(item_id))
                    )

    wave_rows = _wave_rows(events)
    max_projectiles = max((row["max_projectiles"] for row in wave_rows), default=0)
    current_wave = int(combat_payload.get("wave", 0) or 0)
    alerts = warnings
    severity = "ok"

    if telemetry_age_sec is not None and telemetry_age_sec > 120:
        alerts.append(f"telemetry stale for {telemetry_age_sec:.0f}s")
        severity = "error"
    if current_wave >= 5 and len(combat) >= 60 and max_projectiles == 0:
        alerts.append("projectile sensor has reported zero throughout the run")
        severity = "warning" if severity == "ok" else severity

    first_combine_position = next(
        (index for index, action in enumerate(shop_timeline) if action["type"] == "shop_combine"),
        None,
    )
    if first_combine_position is not None:
        buys_before = sum(
            1
            for action in shop_timeline[:first_combine_position]
            if action["type"] == "shop_buy" and str(action.get("item_id") or "").startswith("weapon_")
        )
        # The starting weapon is not a shop buy, hence five buys establish six slots.
        if buys_before < 5:
            alerts.append(f"weapon combined before six-slot fill ({buys_before + 1} weapons acquired)")
            severity = "error" if any(
                version in str(meta.get("policy_version", ""))
            for version in ("0.1.59", "0.1.60", "0.1.61", "0.1.62", "0.1.63", "0.1.64", "0.1.65", "0.1.66", "0.1.67", "0.1.68", "0.1.69", "0.1.70", "0.1.71", "0.1.72", "0.1.73", "0.1.74", "0.1.75", "0.1.76", "0.1.77", "0.1.78", "0.1.79", "0.1.80", "0.1.81", "0.1.82", "0.1.83", "0.1.84", "0.1.85", "0.1.86", "0.1.87", "0.1.88", "0.1.89", "0.1.90", "0.1.91", "0.1.92", "0.1.93", "0.1.94", "0.1.95", "0.1.96", "0.1.97", "0.1.98", "0.1.99", "0.1.100", "0.1.101")
            ) else (
                "warning" if severity == "ok" else severity
            )

    combines_by_wave: defaultdict[int, int] = defaultdict(int)
    for action in shop_timeline:
        if action["type"] != "shop_combine" or action.get("wave") is None:
            continue
        combines_by_wave[int(action["wave"])] += 1
    repeated_combine_waves = sorted(
        wave for wave, count in combines_by_wave.items() if count > 1
    )
    if repeated_combine_waves:
        alerts.append(
            "combine safety violated in shop wave(s): "
            + ", ".join(map(str, repeated_combine_waves))
        )
        severity = "error"
    policy_version = str(meta.get("policy_version", ""))
    if any(
        version in policy_version
        for version in ("0.1.48", "0.1.49", "0.1.50", "0.1.56", "0.1.57", "0.1.58")
    ) and combines_by_wave:
        alerts.append("zero-combine safety violated")
        severity = "error"
    if any(version in policy_version for version in ("0.1.57", "0.1.58", "0.1.59", "0.1.60", "0.1.61", "0.1.62", "0.1.63", "0.1.64", "0.1.65", "0.1.66", "0.1.67", "0.1.68", "0.1.69", "0.1.70", "0.1.71", "0.1.72", "0.1.73", "0.1.74", "0.1.75", "0.1.76", "0.1.77", "0.1.78", "0.1.79", "0.1.80", "0.1.81", "0.1.82", "0.1.83", "0.1.84", "0.1.85", "0.1.86", "0.1.87", "0.1.88", "0.1.89", "0.1.90", "0.1.91", "0.1.92", "0.1.93", "0.1.94", "0.1.95", "0.1.96", "0.1.97", "0.1.98", "0.1.99", "0.1.100", "0.1.101")):
        cooldown_floor_buys = sorted(
            {
                str(action.get("item_id"))
                for action in shop_timeline
                if action["type"] == "shop_buy"
                and action.get("item_id") == "item_ball_and_chain"
            }
        )
        if cooldown_floor_buys:
            alerts.append("cooldown-floor item purchased: " + ", ".join(cooldown_floor_buys))
            severity = "error"
    if any(
        version in policy_version
        for version in ("0.1.51", "0.1.52", "0.1.53", "0.1.54", "0.1.55", "0.1.59", "0.1.60", "0.1.61", "0.1.62", "0.1.63", "0.1.64", "0.1.65", "0.1.66", "0.1.67", "0.1.68", "0.1.69", "0.1.70", "0.1.71", "0.1.72", "0.1.73", "0.1.74", "0.1.75", "0.1.76", "0.1.77", "0.1.78", "0.1.79", "0.1.80", "0.1.81", "0.1.82", "0.1.83", "0.1.84", "0.1.85", "0.1.86", "0.1.87", "0.1.88", "0.1.89", "0.1.90", "0.1.91", "0.1.92", "0.1.93", "0.1.94", "0.1.95", "0.1.96", "0.1.97", "0.1.98", "0.1.99", "0.1.100", "0.1.101")
    ):
        paced_combine_errors: list[str] = []
        combine_timeouts = [
            event
            for event in events
            if event.get("event") == "shop_combine_confirmation_timeout"
        ]
        if combine_timeouts:
            timeout_waves = ", ".join(
                str((event.get("payload", {}) or {}).get("wave", "?"))
                for event in combine_timeouts
            )
            paced_combine_errors.append(
                f"combine confirmation timed out in wave(s): {timeout_waves}"
            )
        for index, event in enumerate(events):
            payload = event.get("payload", {}) or {}
            action = payload.get("action", {}) or {}
            if event.get("event") != "purchase_decision" or action.get("type") != "shop_combine":
                continue
            wave = int(payload.get("wave", 0) or 0)
            dispatch = None
            confirmation = None
            next_action_before_confirmation = False
            for later in events[index + 1 :]:
                if later.get("event") == "shop_combine_dispatched" and dispatch is None:
                    dispatch = later
                    continue
                if later.get("event") == "shop_combine_confirmed":
                    confirmation = later
                    break
                if later.get("event") == "purchase_decision":
                    next_action_before_confirmation = True
                    break
            if any(version in policy_version for version in ("0.1.59", "0.1.60", "0.1.61", "0.1.62", "0.1.63", "0.1.64", "0.1.65", "0.1.66", "0.1.67", "0.1.68", "0.1.69", "0.1.70", "0.1.71", "0.1.72", "0.1.73", "0.1.74", "0.1.75", "0.1.76", "0.1.77", "0.1.78", "0.1.79", "0.1.80", "0.1.81", "0.1.82", "0.1.83", "0.1.84", "0.1.85", "0.1.86", "0.1.87", "0.1.88", "0.1.89", "0.1.90", "0.1.91", "0.1.92", "0.1.93", "0.1.94", "0.1.95", "0.1.96", "0.1.97", "0.1.98", "0.1.99", "0.1.100", "0.1.101")):
                if dispatch is None:
                    paced_combine_errors.append(f"wave {wave} combine lacked safe dispatch")
                    continue
                dispatch_payload = dispatch.get("payload", {}) or {}
                if (
                    dispatch_payload.get("executor") != "deferred_core_combine"
                    or dispatch_payload.get("mouse_mode") != "visible"
                ):
                    paced_combine_errors.append(f"wave {wave} combine dispatch was unsafe")
                    continue
            if next_action_before_confirmation:
                paced_combine_errors.append(f"wave {wave} acted before combine confirmation")
                continue
            if confirmation is None:
                event_age_ms = int(last.get("ts_ms", 0) or 0) - int(event.get("ts_ms", 0) or 0)
                if terminal_result is not None or event_age_ms > 5000:
                    paced_combine_errors.append(f"wave {wave} combine was not confirmed")
                continue
            confirmation_payload = confirmation.get("payload", {}) or {}
            if (
                not confirmation_payload.get("state_changed", False)
                or int(confirmation_payload.get("wait_ms", 0) or 0) < 1000
                or (
                    any(version in policy_version for version in ("0.1.59", "0.1.60", "0.1.61", "0.1.62", "0.1.63", "0.1.64", "0.1.65", "0.1.66", "0.1.67", "0.1.68", "0.1.69", "0.1.70", "0.1.71", "0.1.72", "0.1.73", "0.1.74", "0.1.75", "0.1.76", "0.1.77", "0.1.78", "0.1.79", "0.1.80", "0.1.81", "0.1.82", "0.1.83", "0.1.84", "0.1.85", "0.1.86", "0.1.87", "0.1.88", "0.1.89", "0.1.90", "0.1.91", "0.1.92", "0.1.93", "0.1.94", "0.1.95", "0.1.96", "0.1.97", "0.1.98", "0.1.99", "0.1.100", "0.1.101"))
                    and (
                        confirmation_payload.get("executor") != "deferred_core_combine"
                        or not confirmation_payload.get("mouse_mode_restored", False)
                    )
                )
            ):
                paced_combine_errors.append(f"wave {wave} combine confirmation was unsafe")
        if paced_combine_errors:
            alerts.append("paced combine safety violated: " + "; ".join(paced_combine_errors))
            severity = "error"
    if any(version in policy_version for version in ("0.1.55", "0.1.59", "0.1.60", "0.1.61", "0.1.62", "0.1.63", "0.1.64")) and combines_by_wave.get(19, 0):
        alerts.append("final-shop combine safety violated")
        severity = "error"

    off_plan = sorted(
        {
            family
            for family in map(_weapon_family, weapon_buys)
            if family in SLOW_OR_OFF_PLAN_GUNS
        }
    )
    if off_plan:
        alerts.append("off-plan gun families bought: " + ", ".join(off_plan))
        severity = "warning" if severity == "ok" else severity

    all_lock_episodes = completed_lock_episodes + list(active_lock_episodes.items())
    lock_expiry_policy = any(
        version in policy_version
        for version in (
            "0.1.49",
            "0.1.50",
            "0.1.51",
            "0.1.52",
            "0.1.53",
            "0.1.54",
            "0.1.55",
            "0.1.56",
            "0.1.57",
            "0.1.58",
            "0.1.59",
            "0.1.60",
            "0.1.61",
            "0.1.62",
            "0.1.63",
            "0.1.64",
            "0.1.65",
            "0.1.66",
            "0.1.67",
            "0.1.68",
            "0.1.69",
            "0.1.70",
            "0.1.71",
            "0.1.72",
            "0.1.73",
            "0.1.74",
            "0.1.75",
            "0.1.76",
            "0.1.77",
            "0.1.78",
            "0.1.79",
            "0.1.80",
            "0.1.81",
            "0.1.82",
            "0.1.83",
            "0.1.84",
            "0.1.85",
            "0.1.86",
            "0.1.87", "0.1.88", "0.1.89", "0.1.90", "0.1.91", "0.1.92", "0.1.93", "0.1.94", "0.1.95", "0.1.96", "0.1.97", "0.1.98", "0.1.99", "0.1.100", "0.1.101",
        )
    )
    allowed_lock_wave_span = 1 if lock_expiry_policy else 0
    stale_locks = [
        (item_id, sorted(waves))
        for item_id, waves in all_lock_episodes
        if waves and max(waves) - min(waves) > allowed_lock_wave_span
    ]
    if stale_locks:
        details = ", ".join(
            f"{item_id} (waves {waves[0]}-{waves[-1]})"
            for item_id, waves in sorted(stale_locks)
        )
        alerts.append("shop lock persisted across visits: " + details)
        severity = "error" if lock_expiry_policy else (
            "warning" if severity == "ok" else severity
        )

    expired_unlocks = {
        (int(action.get("wave") or 0), str(action.get("item_id") or "")): int(
            action.get("seq") or 0
        )
        for action in shop_timeline
        if action["type"] == "shop_unlock" and action.get("lock_expired")
    }
    same_visit_relocks = sorted(
        {
            (int(action.get("wave") or 0), str(action.get("item_id") or ""))
            for action in shop_timeline
            if action["type"] == "shop_lock"
            and (int(action.get("wave") or 0), str(action.get("item_id") or ""))
            in expired_unlocks
            and int(action.get("seq") or 0)
            > expired_unlocks[
                (int(action.get("wave") or 0), str(action.get("item_id") or ""))
            ]
        }
    )
    if same_visit_relocks:
        details = ", ".join(f"{item_id} (wave {wave})" for wave, item_id in same_visit_relocks)
        alerts.append("expired shop lock immediately re-locked: " + details)
        severity = "error"

    final_shop_go = next(
        (
            action
            for action in reversed(shop_timeline)
            if action["type"] == "shop_go" and int(action.get("wave") or 0) >= 19
        ),
        None,
    )
    if final_shop_go is not None and int(final_shop_go.get("gold_before") or 0) > 0:
        alerts.append(
            f"final shop exited with {int(final_shop_go['gold_before'])} unspent materials"
        )
        severity = "warning" if severity == "ok" else severity

    current_hp = combat_payload.get("hp")
    recent_min_hp = min(
        (row["min_hp"] for row in wave_rows[-3:] if row["min_hp"] is not None),
        default=current_hp,
    )
    return {
        "active": terminal_result is None,
        "terminal_result": terminal_result,
        "run_id": str(start.get("run_id", meta.get("run_id", ""))),
        "policy_version": meta.get("policy_version"),
        "mod_version": meta.get("mod_version"),
        "character": meta.get("character"),
        "starting_weapon": meta.get("weapon"),
        "danger": meta.get("danger"),
        "event_count": len(events),
        "latest_seq": last.get("seq"),
        "latest_event": last.get("event"),
        "elapsed_ms": last.get("ts_ms", 0),
        "telemetry_age_sec": telemetry_age_sec,
        "wave": current_wave,
        "hp": current_hp,
        "recent_min_hp": recent_min_hp,
        "enemies": combat_debug.get("enemies", 0),
        "projectiles": combat_debug.get("projectiles", 0),
        "loot": combat_payload.get("loot", 0),
        "consumables": combat_payload.get("consumables", 0),
        "damage_taken": damage_taken,
        "recoveries": recoveries,
        "build_metrics": combat_payload.get("build_metrics", {}),
        "shop_counts": dict(sorted(counts.items())),
        "weapon_buys": weapon_buys,
        "item_buys": item_buys,
        "last_shop_actions": shop_timeline[-10:],
        "waves": wave_rows,
        "severity": severity,
        "alerts": alerts,
    }


def render_markdown(snapshot: dict[str, Any]) -> str:
    run = snapshot.get("run", {}) or {}
    hud = snapshot.get("hud", {}) or {}
    lines = [
        "# BrotatoAgent Live Monitor",
        "",
        f"Updated: {snapshot.get('updated_at', '?')}",
        "",
        f"- Game: {'running' if snapshot.get('game_running') else 'stopped'}",
        f"- Gate record: {hud.get('wins', 0)}W / {hud.get('runs', 0)}R",
        f"- Run: {run.get('run_id', 'none')}",
        f"- Policy: {run.get('policy_version', '?')}",
        f"- Wave: {run.get('wave', 0)}",
        f"- HP: {run.get('hp', '?')} (recent minimum {run.get('recent_min_hp', '?')})",
        f"- Offense: {json.dumps((run.get('build_metrics', {}) or {}).get('offense', {}), sort_keys=True)}",
        f"- Defense: {json.dumps((run.get('build_metrics', {}) or {}).get('defense', {}), sort_keys=True)}",
        f"- Threats: {run.get('enemies', 0)} enemies / {run.get('projectiles', 0)} projectiles",
        f"- Telemetry age: {run.get('telemetry_age_sec', '?')}s",
        f"- Status: {str(run.get('severity', 'unknown')).upper()}",
        "",
        "## Alerts",
        "",
    ]
    alerts = run.get("alerts", []) or []
    lines.extend(f"- {alert}" for alert in alerts)
    if not alerts:
        lines.append("- None")
    lines.extend(
        [
            "",
            "## Shop readout",
            "",
            f"- Weapon buys: {', '.join(run.get('weapon_buys', [])) or 'none'}",
            f"- Actions: {json.dumps(run.get('shop_counts', {}), sort_keys=True)}",
            "",
            "## Recent waves",
            "",
            "| Wave | HP start | HP last | HP min | Damage | Max enemies | Max projectiles |",
            "|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in (run.get("waves", []) or [])[-8:]:
        lines.append(
            f"| {row['wave']} | {row['first_hp']} | {row['last_hp']} | {row['min_hp']} | "
            f"{row['damage_taken']:.0f} | {row['max_enemies']} | {row['max_projectiles']} |"
        )
    return "\n".join(lines) + "\n"


def timestamp_now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")
