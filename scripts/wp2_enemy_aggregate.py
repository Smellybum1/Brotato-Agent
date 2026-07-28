"""Enemy-population aggregates over combat captures.

Primary outcome metrics for wave-level death attribution:
  * number of enemies alive at a given elapsed time in a wave
  * total current-HP pool alive at that time

These were previously computed ad hoc. This module is the committed, tested
version. All aggregation logic is pure (dict in, number out); the only I/O is
``iter_wave_payloads``, which streams.

Capture schema (verified, do not guess):
  envelope: schema_version, run_id, seq, ts_ms, event, payload
  capture lines have event == "combat_capture"
  payload.entities.enemies  -> list
  payload.entities.bosses   -> list   (SEPARATE from enemies)
  entity: hp, max_hp, health_ratio, type_id, script_path, name, category,
          speed, armor, radius
  payload.wave              -> int
  payload.wave_time.{elapsed_sec, remaining_sec, duration_sec, valid}
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Iterator, List, Optional, Sequence, Tuple

__all__ = [
    "CensoredCaptureError",
    "WaveAggregate",
    "enemies_alive",
    "enemy_hp_pool",
    "capture_is_censored",
    "capture_elapsed_sec",
    "monotonic_prefix",
    "aggregate_at",
    "iter_wave_payloads",
]


class CensoredCaptureError(ValueError):
    """Raised when an aggregate is requested from a capture that dropped entities."""


def _entity_lists(payload: Dict[str, Any], include_bosses: bool) -> List[Sequence[Any]]:
    entities = payload.get("entities") or {}
    lists: List[Sequence[Any]] = [entities.get("enemies") or []]
    # Bosses live in their own array. Folding them into "enemies" silently would
    # change the meaning of the metric between pre-finale and finale waves, so it
    # is opt-in only.
    if include_bosses:
        lists.append(entities.get("bosses") or [])
    return lists


def _is_alive(entity: Dict[str, Any]) -> bool:
    hp = entity.get("hp")
    if hp is None:
        # No hp field: treat presence in the live-entity array as alive.
        return True
    try:
        return float(hp) > 0.0
    except (TypeError, ValueError):
        return False


def enemies_alive(payload: Dict[str, Any], include_bosses: bool = False) -> int:
    """Count live enemies in one capture payload. Bosses excluded by default."""
    total = 0
    for lst in _entity_lists(payload, include_bosses):
        for ent in lst:
            if isinstance(ent, dict) and _is_alive(ent):
                total += 1
    return total


def enemy_hp_pool(payload: Dict[str, Any], include_bosses: bool = False) -> float:
    """Sum current ``hp`` over live entities. Bosses excluded by default."""
    total = 0.0
    for lst in _entity_lists(payload, include_bosses):
        for ent in lst:
            if not isinstance(ent, dict) or not _is_alive(ent):
                continue
            try:
                total += float(ent.get("hp") or 0.0)
            except (TypeError, ValueError):
                continue
    return total


def _sum_counts(value: Any) -> int:
    """dropped_counts / invalid_counts may be an int, a list, or a dict of ints."""
    if value is None:
        return 0
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, dict):
        return sum(_sum_counts(v) for v in value.values())
    if isinstance(value, (list, tuple)):
        return sum(_sum_counts(v) for v in value)
    return 0


def capture_is_censored(payload: Dict[str, Any]) -> bool:
    """True when the capture reports dropped/invalid entities.

    Such a capture's entity arrays are incomplete, so enemies_alive /
    enemy_hp_pool would be silently too LOW. We never mask this: the aggregate
    is surfaced with a censored flag (and ``aggregate_at`` refuses to return it
    as a clean value unless the caller opts in).
    """
    return _sum_counts(payload.get("dropped_counts")) > 0 or _sum_counts(
        payload.get("invalid_counts")
    ) > 0


def _payload_valid(payload: Dict[str, Any]) -> bool:
    if payload.get("valid") is False:
        return False
    wt = payload.get("wave_time") or {}
    return wt.get("valid") is not False


def capture_elapsed_sec(payload: Dict[str, Any]) -> Optional[float]:
    wt = payload.get("wave_time") or {}
    val = wt.get("elapsed_sec")
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class WaveAggregate:
    """Aggregate at one selected capture."""

    enemies_alive: int
    enemy_hp_pool: float
    elapsed_sec: float          # the elapsed time actually matched
    requested_sec: float
    censored: bool              # this capture reported dropped/invalid entities
    n_candidates: int           # captures considered after filtering

    @property
    def time_error_sec(self) -> float:
        return abs(self.elapsed_sec - self.requested_sec)


def monotonic_prefix(
    records: Sequence[Tuple[float, Dict[str, Any]]]
) -> List[Tuple[float, Dict[str, Any]]]:
    """Trim the captures to the leading non-decreasing run of ``elapsed_sec``.

    TRAP: on a WON wave the final captures RESET ``elapsed_sec`` (observed:
    21.87 then 0.034, same wave, both flagged valid) as the next wave's timer
    arms while the wave field still reads the old wave. A naive nearest-time
    search would then match the tail 0.034 capture for a request of t=0, and a
    naive last-minus-first would mix two different quantities -- and only on
    victories, which biases exactly the comparison we care about.

    RULE CHOSEN: keep captures in sequence order up to (and excluding) the first
    strict DECREASE in elapsed_sec. Rationale: within a wave the timer is
    non-decreasing, so the first decrease is the reset boundary; everything after
    it belongs to the next wave's timeline. This is order-preserving and needs no
    threshold tuning, unlike "drop small values at the end" heuristics.
    """
    kept: List[Tuple[float, Dict[str, Any]]] = []
    prev: Optional[float] = None
    for t, payload in records:
        if prev is not None and t < prev:
            break
        kept.append((t, payload))
        prev = t
    return kept


def aggregate_at(
    payloads: Iterable[Dict[str, Any]],
    wave: int,
    t_sec: float,
    tolerance_sec: Optional[float] = None,
    include_bosses: bool = False,
    allow_censored: bool = False,
) -> Optional[WaveAggregate]:
    """Aggregate at the capture nearest ``t_sec`` within one wave.

    ``payloads`` must be in capture order (as read from events.jsonl). Payloads
    for other waves, invalid payloads, and payloads without an elapsed time are
    skipped. Returns None if nothing survives filtering or if the nearest
    capture is farther than ``tolerance_sec`` (when given).

    Censoring: if the selected capture reported dropped/invalid entities its
    counts are too low. By default this raises CensoredCaptureError rather than
    returning a silently-wrong number; pass ``allow_censored=True`` to receive
    the value with ``WaveAggregate.censored`` set True.
    """
    records: List[Tuple[float, Dict[str, Any]]] = []
    for payload in payloads:
        if not isinstance(payload, dict):
            continue
        if payload.get("wave") != wave:
            continue
        if not _payload_valid(payload):
            continue
        t = capture_elapsed_sec(payload)
        if t is None:
            continue
        records.append((t, payload))

    records = monotonic_prefix(records)
    if not records:
        return None

    # Nearest by absolute time; ties resolved toward the EARLIER capture so the
    # selection is deterministic.
    best_idx = min(range(len(records)), key=lambda i: (abs(records[i][0] - t_sec), i))
    best_t, best_payload = records[best_idx]

    if tolerance_sec is not None and abs(best_t - t_sec) > tolerance_sec:
        return None

    censored = capture_is_censored(best_payload)
    if censored and not allow_censored:
        raise CensoredCaptureError(
            "capture at elapsed_sec=%r (wave %r) reports dropped/invalid entities; "
            "aggregate would be too low. Pass allow_censored=True to accept it."
            % (best_t, wave)
        )

    return WaveAggregate(
        enemies_alive=enemies_alive(best_payload, include_bosses=include_bosses),
        enemy_hp_pool=enemy_hp_pool(best_payload, include_bosses=include_bosses),
        elapsed_sec=best_t,
        requested_sec=float(t_sec),
        censored=censored,
        n_candidates=len(records),
    )


def iter_wave_payloads(events_path, wave: int) -> Iterator[Dict[str, Any]]:
    """Stream ``combat_capture`` payloads for ``wave`` from an events.jsonl.

    Reads line by line -- these files reach hundreds of MB, so the whole file is
    never materialized. Malformed lines are skipped.
    """
    with open(events_path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except (ValueError, TypeError):
                continue
            if not isinstance(rec, dict) or rec.get("event") != "combat_capture":
                continue
            payload = rec.get("payload")
            if isinstance(payload, dict) and payload.get("wave") == wave:
                yield payload
