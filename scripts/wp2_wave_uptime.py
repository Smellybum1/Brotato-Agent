"""Weapon "targetable uptime" over combat captures.

QUESTION THIS SERVES: are wave-17 deaths driven by weak BUILDS (low nominal
DPS, low defence) or by MOVEMENT that keeps the auto-firing weapons off-target?
The agent controls movement only; weapons fire on their own at whatever is in
range. So the movement-side observable is: on what fraction of ticks did each
weapon actually HAVE something inside its range?

Capture schema (verified, do not guess):
  envelope: schema_version, run_id, seq, ts_ms, event, payload
  capture lines have event == "combat_capture"
  payload.weapons  -> LIST of {type, max_range, damage, cooldown}
  payload.player   -> x, y, hp, max_hp, armor, dodge, lifesteal,
                      hp_regeneration, speed, vx, vy, measured_vx, measured_vy,
                      materials, bonus_materials, hp_ratio
  payload.entities.enemies -> list;  payload.entities.bosses -> SEPARATE list
  entity: x, y, hp, max_hp, health_ratio, type_id, script_path, category,
          speed, armor, radius
  payload.wave, payload.wave_time.{elapsed_sec,...}, payload.valid,
  payload.control_dt_ms, payload.arena{width,height}

KNOWN TRAPS, all handled explicitly below:
  * elapsed_sec RESETS on the final captures of a WON wave (observed 21.87 ->
    0.034, same wave, both valid). We trim with
    wp2_enemy_aggregate.monotonic_prefix so windows never mix two timelines.
    Untrimmed, this biases only VICTORIES -- exactly the comparison at issue.
  * payload.valid false -> capture skipped entirely.
  * control_dt_ms < 10 -> excluded from any VELOCITY/SPEED statistic
    (measured_vx/vy explodes at start-up dt; 11124.9 observed against a real
    speed of 445). We prefer player.speed over measured_* everywhere anyway.
  * instance_id is POOLED AND RECYCLED (46 reappearances after >5-tick absence
    across 37 ids in a single run). NOTHING here tracks an entity across ticks.
  * bosses are NOT in entities.enemies; excluded by default, opt-in only.

DISTANCE CONVENTION -- SURFACE, not centre.
  targetable() measures Euclidean centre-to-centre distance from the player to
  the enemy and SUBTRACTS the enemy's ``radius``, i.e. distance to the enemy's
  near surface. Rationale: the rest of the archive uses surface distance, and a
  weapon that reaches an enemy's hitbox hits it regardless of where the centre
  is. Using centre distance would systematically UNDER-count targetability for
  large enemies. The player's own radius is not in the schema and is not
  subtracted. Surface distance is clamped at 0 (overlapping enemy = distance 0).

NOMINAL DPS UNITS -- ONLY RATIOS ARE MEANINGFUL.
  ``cooldown`` units are UNVERIFIED (frames? ms? seconds?). nominal_dps returns
  sum(damage / cooldown), which is therefore in an arbitrary unit. NEVER quote
  its absolute value as damage-per-second. It is valid only for comparing runs
  to each other, and only if the unit is constant across those runs. The raw
  per-weapon components are returned alongside so a caller can re-scale.
"""

from __future__ import annotations

import math
import os
import sys
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from wp2_enemy_aggregate import (  # noqa: E402
    capture_elapsed_sec,
    enemies_alive,
    enemy_hp_pool,
    iter_wave_payloads,
    monotonic_prefix,
)

__all__ = [
    "nominal_dps",
    "weapon_dps",
    "surface_distance",
    "nearest_enemy_surface_distance",
    "targetable",
    "uptime",
    "window_summary",
    "run_wave_report",
    "prepare_wave_payloads",
    "MIN_CONTROL_DT_MS",
]

# control_dt_ms below this is a start-up tick; measured_* velocities are garbage
# there (11124.9 observed vs a real speed of 445).
MIN_CONTROL_DT_MS = 10.0


def _f(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


# --------------------------------------------------------------------------
# 1. nominal DPS
# --------------------------------------------------------------------------

def weapon_dps(weapon: Dict[str, Any]) -> float:
    """damage / cooldown for one weapon. Arbitrary unit -- see module docstring.

    A non-positive or missing cooldown yields 0.0 rather than an exception or an
    infinity, so a malformed weapon entry cannot dominate a DPS-weighted mean.
    """
    if not isinstance(weapon, dict):
        return 0.0
    cd = _f(weapon.get("cooldown"))
    if cd <= 0.0:
        return 0.0
    return _f(weapon.get("damage")) / cd


def nominal_dps(weapons: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Total nominal DPS plus the raw components.

    Returns {"total": float, "components": [{"index","type","damage",
    "cooldown","max_range","dps"}, ...], "n_weapons": int}.

    UNITS ARE UNVERIFIED. Only RATIOS between runs are meaningful; the absolute
    value is not damage per second and must never be reported as such.
    """
    components: List[Dict[str, Any]] = []
    total = 0.0
    weapons = weapons or []
    for i, w in enumerate(weapons):
        if not isinstance(w, dict):
            continue
        d = weapon_dps(w)
        total += d
        components.append(
            {
                "index": i,
                "type": w.get("type"),
                "damage": _f(w.get("damage")),
                "cooldown": _f(w.get("cooldown")),
                "max_range": _f(w.get("max_range")),
                "dps": d,
            }
        )
    return {"total": total, "components": components, "n_weapons": len(components)}


# --------------------------------------------------------------------------
# 2. targetability
# --------------------------------------------------------------------------

def _live_entities(payload: Dict[str, Any], include_bosses: bool) -> List[Dict[str, Any]]:
    entities = payload.get("entities") or {}
    lists: List[Any] = [entities.get("enemies") or []]
    if include_bosses:  # bosses are a SEPARATE array; opt-in only
        lists.append(entities.get("bosses") or [])
    out: List[Dict[str, Any]] = []
    for lst in lists:
        for ent in lst or []:
            if isinstance(ent, dict) and _f(ent.get("hp"), -1.0) > 0.0:
                out.append(ent)
    return out


def surface_distance(px: float, py: float, entity: Dict[str, Any]) -> float:
    """Distance from the player point to the entity's near SURFACE, clamped >= 0."""
    d = math.hypot(_f(entity.get("x")) - px, _f(entity.get("y")) - py)
    return max(0.0, d - _f(entity.get("radius")))


def nearest_enemy_surface_distance(
    payload: Dict[str, Any], include_bosses: bool = False
) -> Optional[float]:
    player = payload.get("player") or {}
    px, py = _f(player.get("x")), _f(player.get("y"))
    dists = [surface_distance(px, py, e) for e in _live_entities(payload, include_bosses)]
    return min(dists) if dists else None


def targetable(
    payload: Dict[str, Any], weapon: Dict[str, Any], include_bosses: bool = False
) -> bool:
    """True iff at least one LIVE enemy is within ``weapon.max_range``.

    SURFACE distance (see module docstring). Boundary is INCLUSIVE: a surface
    distance exactly equal to max_range counts as targetable.
    """
    rng = _f((weapon or {}).get("max_range"), -1.0)
    if rng < 0.0:
        return False
    player = payload.get("player") or {}
    px, py = _f(player.get("x")), _f(player.get("y"))
    for ent in _live_entities(payload, include_bosses):
        if surface_distance(px, py, ent) <= rng:
            return True
    return False


# --------------------------------------------------------------------------
# 3. uptime
# --------------------------------------------------------------------------

def uptime(
    payloads: Sequence[Dict[str, Any]],
    weapons_key: str = "weapons",
    include_bosses: bool = False,
) -> Dict[str, Any]:
    """DPS-weighted fraction of captures on which each weapon has a target.

    Two figures, both returned:
      ``uptime_all``      -- over ALL supplied captures.
      ``uptime_engaged``  -- over ONLY captures with at least one live enemy
                             anywhere in the arena.
    The second exists because a run that has CLEARED the arena has nothing to
    shoot; scoring it as "low uptime" would confuse winning with missing. The
    engaged figure is the movement-quality measure; the all figure includes
    clear time and is therefore partly an outcome, not a cause.

    Weighting: sum over (capture, weapon) of dps_w * targetable, divided by sum
    of dps_w over the same pairs. Weapons are read per capture from
    ``weapons_key`` (loadout changes between shops, so it is not assumed fixed).
    Captures whose weapons all have dps 0 contribute nothing to either
    numerator or denominator and are counted in ``n_zero_dps``.
    """
    num_all = den_all = 0.0
    num_eng = den_eng = 0.0
    n_all = n_eng = n_zero = 0
    for payload in payloads:
        if not isinstance(payload, dict):
            continue
        weapons = payload.get(weapons_key) or []
        engaged = enemies_alive(payload, include_bosses=include_bosses) > 0
        n_all += 1
        if engaged:
            n_eng += 1
        cap_den = 0.0
        for w in weapons:
            if not isinstance(w, dict):
                continue
            d = weapon_dps(w)
            if d <= 0.0:
                continue
            cap_den += d
            hit = 1.0 if targetable(payload, w, include_bosses=include_bosses) else 0.0
            num_all += d * hit
            den_all += d
            if engaged:
                num_eng += d * hit
                den_eng += d
        if cap_den <= 0.0:
            n_zero += 1
    return {
        "uptime_all": (num_all / den_all) if den_all > 0 else None,
        "uptime_engaged": (num_eng / den_eng) if den_eng > 0 else None,
        "n_captures": n_all,
        "n_captures_engaged": n_eng,
        "n_zero_dps_captures": n_zero,
    }


# --------------------------------------------------------------------------
# 4. windowed summary
# --------------------------------------------------------------------------

def _mean(vals: Sequence[float]) -> Optional[float]:
    return (sum(vals) / len(vals)) if vals else None


def window_summary(
    payloads: Sequence[Dict[str, Any]],
    t_lo: float,
    t_hi: float,
    weapons_key: str = "weapons",
    include_bosses: bool = False,
) -> Dict[str, Any]:
    """Summarise captures with elapsed_sec in [t_lo, t_hi) -- INCLUSIVE lower,
    EXCLUSIVE upper, so adjacent windows tile without double-counting.

    ``payloads`` should already be filtered to one wave and passed through
    ``prepare_wave_payloads`` (valid-only + monotonic_prefix).
    """
    sel = []
    for p in payloads:
        if not isinstance(p, dict):
            continue
        t = capture_elapsed_sec(p)
        if t is None or not (t_lo <= t < t_hi):
            continue
        sel.append(p)

    counts = [enemies_alive(p, include_bosses=include_bosses) for p in sel]
    pools = [enemy_hp_pool(p, include_bosses=include_bosses) for p in sel]
    nearest = [
        d
        for d in (nearest_enemy_surface_distance(p, include_bosses) for p in sel)
        if d is not None
    ]
    # Speed: player.speed (a stat, not a derivative) is used, but the dt guard is
    # still applied so this statistic is comparable to any measured_* variant and
    # never includes start-up ticks.
    speeds = [
        _f(p.get("player", {}).get("speed"))
        for p in sel
        if _f(p.get("control_dt_ms"), 0.0) >= MIN_CONTROL_DT_MS
    ]

    up = uptime(sel, weapons_key=weapons_key, include_bosses=include_bosses)
    return {
        "t_lo": float(t_lo),
        "t_hi": float(t_hi),
        "n_captures": len(sel),
        "n_captures_engaged": up["n_captures_engaged"],
        "uptime_all": up["uptime_all"],
        "uptime_engaged": up["uptime_engaged"],
        "mean_enemies_alive": _mean(counts),
        "max_enemies_alive": max(counts) if counts else None,
        "mean_enemy_hp_pool": _mean(pools),
        "max_enemy_hp_pool": max(pools) if pools else None,
        "mean_nearest_surface_dist": _mean(nearest),
        "mean_player_speed": _mean(speeds),
        "n_speed_samples": len(speeds),
    }


# --------------------------------------------------------------------------
# 5. per-run report
# --------------------------------------------------------------------------

def prepare_wave_payloads(
    payloads: Iterable[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Drop invalid captures, then trim at the elapsed_sec reset.

    The reset trim MUST happen after the valid filter and in capture order --
    see monotonic_prefix's docstring for the 21.87 -> 0.034 observation.
    """
    records: List[Tuple[float, Dict[str, Any]]] = []
    for p in payloads:
        if not isinstance(p, dict):
            continue
        if p.get("valid") is False:
            continue
        wt = p.get("wave_time") or {}
        if wt.get("valid") is False:
            continue
        t = capture_elapsed_sec(p)
        if t is None:
            continue
        records.append((t, p))
    return [p for _, p in monotonic_prefix(records)]


def run_wave_report(
    events_path,
    wave: int,
    windows: Sequence[Tuple[float, float]],
    weapons_key: str = "weapons",
    include_bosses: bool = False,
) -> Dict[str, Any]:
    """Entry state + one window_summary per window for ``wave`` in one run."""
    payloads = prepare_wave_payloads(iter_wave_payloads(events_path, wave))

    entry: Dict[str, Any] = {"found": False}
    if payloads:
        first = payloads[0]
        pl = first.get("player") or {}
        weapons = first.get(weapons_key) or []
        nd = nominal_dps(weapons)
        entry = {
            "found": True,
            "entry_elapsed_sec": capture_elapsed_sec(first),
            "hp": _f(pl.get("hp")),
            "max_hp": _f(pl.get("max_hp")),
            "armor": _f(pl.get("armor")),
            "dodge": _f(pl.get("dodge")),
            "lifesteal": _f(pl.get("lifesteal")),
            "hp_regeneration": _f(pl.get("hp_regeneration")),
            "speed": _f(pl.get("speed")),
            "nominal_dps": nd["total"],  # arbitrary unit; ratios only
            "n_weapons": nd["n_weapons"],
            "weapons": [
                (w.get("type"), _f(w.get("max_range")), _f(w.get("damage")), _f(w.get("cooldown")))
                for w in weapons
                if isinstance(w, dict)
            ],
        }

    return {
        "events_path": str(events_path),
        "wave": wave,
        "n_payloads": len(payloads),
        "entry": entry,
        "windows": [
            window_summary(payloads, lo, hi, weapons_key=weapons_key,
                           include_bosses=include_bosses)
            for lo, hi in windows
        ],
    }
