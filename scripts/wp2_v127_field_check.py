#!/usr/bin/env python3
"""Verify the v127 telemetry additions on a live run (deploy-smoke checklist item 5).

Three changes shipped in v127 and each needs a different kind of confirmation:

  materials    `player.materials` / `player.bonus_materials` must be present and
               ACTUALLY POPULATED. Both use -1 for "accessor unavailable on this
               build", so a run where `bonus_materials` is uniformly -1 means the
               probe missed and the Model A/B question is still unanswered.
  material     `entities.materials[].value` must exceed 1 at least once: the whole
  value        point is that materials are not unit-valued, and a run where every
               value is 1 has not exercised the boosting/absorption paths.
  loot_dash    the new `active` field and the legacy
               `finale_translation.loot_dash_active` are THE SAME VARIABLE, so any
               per-capture disagreement means the block is wired wrong. `seq` must
               be non-decreasing and must advance only on edge states.

The wave-boundary table is the measurement this build was shipped to make, so it
prints the raw per-boundary series, not a summary. The instant that matters is the
last capture with `wave_time.remaining_sec > 0`: captures keep coming for ~40-55
ticks after the timer expires and the end-of-wave sweep happens inside that window,
so sampling "the last capture of the wave" reads the state AFTER the sweep and
silently answers a different question.

Usage:
  python scripts/wp2_v127_field_check.py --run-dir <dir> [--json out.json]
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


# Edge states advance `seq`; per-tick blocking reasons must not, or the transition
# count is meaningless (potential_field.gd::LOOT_DASH_STATES).
EDGE_PREFIXES = ("armed", "aborted_", "suppressed_")
NON_EDGE = ("idle", "active")

MOD_FIELD = (Path(__file__).resolve().parents[1]
             / "mod/mods-unpacked/Tom-BrotatoAgent/teacher/potential_field.gd")


def declared_states() -> set[str]:
    """The LOOT_DASH_STATES list from the mod source.

    Read from source rather than duplicated here: a capture carrying a state the
    mod does not declare would mean the block is emitting something unaccounted
    for, and a hardcoded copy would drift and stop detecting that.
    """
    text = MOD_FIELD.read_text(encoding="utf-8")
    start = text.index("const LOOT_DASH_STATES")
    body = text[start:text.index("]", start)]
    return set(re.findall(r'"([a-z_]+)"', body))


def load_events(run_dir: Path) -> tuple[list[dict], list[dict]]:
    captures: list[dict] = []
    others: list[dict] = []
    path = run_dir / "events.jsonl"
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                evt = json.loads(line)
            except json.JSONDecodeError:
                others.append({"event": "_malformed_line"})
                continue
            if evt.get("event") == "combat_capture":
                captures.append(evt)
            else:
                others.append(evt)
    return captures, others


def dig(obj: Any, *keys, default=None):
    for key in keys:
        if not isinstance(obj, dict):
            return default
        obj = obj.get(key)
        if obj is None:
            return default
    return obj


def check_presence(caps: list[dict]) -> dict:
    n = len(caps)
    have_mat = have_bonus = have_dash = 0
    mat_sentinel = bonus_sentinel = 0
    materials_vals: list[int] = []
    bonus_vals: list[int] = []
    for c in caps:
        p = c.get("payload", {})
        player = p.get("player", {})
        if "materials" in player:
            have_mat += 1
            materials_vals.append(int(player["materials"]))
            if player["materials"] == -1:
                mat_sentinel += 1
        if "bonus_materials" in player:
            have_bonus += 1
            bonus_vals.append(int(player["bonus_materials"]))
            if player["bonus_materials"] == -1:
                bonus_sentinel += 1
        if dig(p, "teacher", "contributions", "loot_dash") is not None:
            have_dash += 1
    return {
        "captures": n,
        "materials_coverage": have_mat / n if n else 0.0,
        "bonus_materials_coverage": have_bonus / n if n else 0.0,
        "loot_dash_coverage": have_dash / n if n else 0.0,
        "materials_sentinel_count": mat_sentinel,
        "bonus_materials_sentinel_count": bonus_sentinel,
        "materials_range": [min(materials_vals), max(materials_vals)] if materials_vals else None,
        "bonus_materials_range": [min(bonus_vals), max(bonus_vals)] if bonus_vals else None,
        "bonus_materials_distinct": len(set(bonus_vals)),
    }


def check_material_values(caps: list[dict]) -> dict:
    counts: Counter = Counter()
    max_value = 0
    max_at = None
    gt1_by_wave: Counter = Counter()
    for c in caps:
        p = c.get("payload", {})
        wave = p.get("wave")
        for m in dig(p, "entities", "materials", default=[]) or []:
            value = int(m.get("value", 1))
            counts[value] += 1
            if value > 1:
                gt1_by_wave[wave] += 1
            if value > max_value:
                max_value = value
                max_at = wave
    return {
        "value_histogram": dict(sorted(counts.items())),
        "max_value": max_value,
        "max_value_wave": max_at,
        "entities_with_value_gt1": sum(v for k, v in counts.items() if k > 1),
        "gt1_by_wave": dict(sorted(gt1_by_wave.items())),
    }


def check_loot_dash(caps: list[dict]) -> dict:
    states: Counter = Counter()
    seq_prev = None
    seq_regressions = 0
    seq_advances_on_non_edge = 0
    seq_static_on_edge = 0
    legacy_disagreements = 0
    disagreement_examples: list[dict] = []
    active_ticks = 0
    scanned = 0
    for c in caps:
        p = c.get("payload", {})
        dash = dig(p, "teacher", "contributions", "loot_dash")
        if dash is None:
            continue
        scanned += 1
        state = str(dash.get("state", ""))
        states[state] += 1
        seq = int(dash.get("seq", 0))
        active = bool(dash.get("active", False))
        if active:
            active_ticks += 1
        legacy = dig(p, "teacher", "contributions", "finale_translation", "loot_dash_active")
        if legacy is not None and bool(legacy) != active:
            legacy_disagreements += 1
            if len(disagreement_examples) < 5:
                disagreement_examples.append(
                    {"capture_seq": p.get("capture_seq"), "wave": p.get("wave"),
                     "active": active, "legacy": bool(legacy), "state": state})
        if seq_prev is not None:
            is_edge = state.startswith(EDGE_PREFIXES)
            if seq < seq_prev:
                seq_regressions += 1
            elif seq > seq_prev and not is_edge:
                # ALIASING, not a defect. The dash state updates on the 60 Hz
                # movement decision; captures sample it at 20 Hz. A seq advance
                # therefore often lands on a capture whose `state` has already been
                # overwritten by a later decision tick, and a one-tick `armed` can be
                # missed entirely. "seq advances only on edges" is a property of the
                # VARIABLE and is pinned at source level by
                # tests/unit/test_wp2_loot_dash_telemetry.py (mutation-checked); it is
                # not recoverable from subsampled captures. Reported, not gated.
                seq_advances_on_non_edge += 1
        seq_prev = seq
    return {
        "captures_with_block": scanned,
        "state_histogram": dict(states.most_common()),
        "saw_armed": states.get("armed", 0) > 0,
        "aborted_states_seen": sorted(s for s in states if s.startswith("aborted_")),
        "suppressed_states_seen": sorted(s for s in states if s.startswith("suppressed_")),
        "seq_total": seq_prev,
        "seq_regressions": seq_regressions,
        "seq_advances_aliased_by_20hz_sampling": seq_advances_on_non_edge,
        "undeclared_states": sorted(s for s in states if s not in declared_states()),
        "legacy_flag_disagreements": legacy_disagreements,
        "legacy_disagreement_examples": disagreement_examples,
        "uptime_from_active": active_ticks / scanned if scanned else 0.0,
    }


def check_dropped_counts(caps: list[dict]) -> dict:
    nonzero: Counter = Counter()
    groups_seen: set[str] = set()
    for c in caps:
        dc = c.get("payload", {}).get("dropped_counts", {}) or {}
        for group, value in dc.items():
            groups_seen.add(group)
            if int(value) != 0:
                nonzero[group] += 1
    return {
        "groups": sorted(groups_seen),
        "captures_with_nonzero_drop": dict(nonzero),
        "all_zero": not nonzero,
    }


def wave_boundaries(caps: list[dict]) -> list[dict]:
    """Last capture with remaining_sec > 0 in wave W vs first capture of wave W+1.

    Model A: `materials` jumps across the boundary, `bonus_materials` stays flat.
    Model B: `bonus_materials` jumps by ~the ground pile's summed value instead.
    """
    last_live: dict[int, dict] = {}
    first_of_wave: dict[int, dict] = {}
    for c in caps:
        p = c.get("payload", {})
        wave = p.get("wave")
        if wave is None:
            continue
        remaining = dig(p, "wave_time", "remaining_sec")
        if wave not in first_of_wave:
            first_of_wave[wave] = p
        if remaining is not None and float(remaining) > 0:
            last_live[wave] = p

    rows = []
    for wave in sorted(last_live):
        nxt = first_of_wave.get(wave + 1)
        if nxt is None:
            continue
        end = last_live[wave]
        pile = dig(end, "entities", "materials", default=[]) or []
        pile_value = sum(int(m.get("value", 1)) for m in pile)
        d_bonus = _delta(dig(nxt, "player", "bonus_materials"),
                         dig(end, "player", "bonus_materials"))
        rows.append({
            "wave": wave,
            "end_remaining_sec": dig(end, "wave_time", "remaining_sec"),
            "ground_entities": len(pile),
            "ground_value": pile_value,
            # Model B predicts the floor pile lands in bonus_materials intact.
            # d_materials is NOT the comparison: the shop sits between these two
            # captures, so materials moves for reasons that have nothing to do
            # with crediting.
            "bonus_matches_ground": d_bonus == pile_value if d_bonus is not None else None,
            "materials_before": dig(end, "player", "materials"),
            "materials_after": dig(nxt, "player", "materials"),
            "d_materials": _delta(dig(nxt, "player", "materials"), dig(end, "player", "materials")),
            "bonus_before": dig(end, "player", "bonus_materials"),
            "bonus_after": dig(nxt, "player", "bonus_materials"),
            "d_bonus": _delta(dig(nxt, "player", "bonus_materials"), dig(end, "player", "bonus_materials")),
        })
    return rows


def _delta(after, before):
    if after is None or before is None:
        return None
    return int(after) - int(before)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True, type=Path)
    ap.add_argument("--json", type=Path)
    args = ap.parse_args()

    caps, others = load_events(args.run_dir)
    if not caps:
        print("FAIL: no combat_capture events in run")
        return 2

    presence = check_presence(caps)
    values = check_material_values(caps)
    dash = check_loot_dash(caps)
    drops = check_dropped_counts(caps)
    rows = wave_boundaries(caps)

    hashes = {c["payload"].get("capture_schema_hash") for c in caps}

    print(f"run_dir: {args.run_dir}")
    print(f"captures: {presence['captures']}   other events: {len(others)}")
    print(f"capture_schema_hash(es): {sorted(h for h in hashes if h)}")
    print()
    print("== field presence ==")
    for key, value in presence.items():
        print(f"  {key}: {value}")
    print()
    print("== material values ==")
    for key, value in values.items():
        print(f"  {key}: {value}")
    print()
    print("== loot dash ==")
    for key, value in dash.items():
        print(f"  {key}: {value}")
    print()
    print("== dropped_counts ==")
    for key, value in drops.items():
        print(f"  {key}: {value}")
    print()
    print("== wave boundaries (RAW SERIES — last capture with remaining_sec>0 -> first of next wave) ==")
    print("  (dmat spans the shop and is NOT evidence either way; the discriminator")
    print("   is whether dbon equals gval — Model B — or dmat does — Model A.)")
    header = (f"{'wave':>4} {'rem':>8} {'ents':>5} {'gval':>6} "
              f"{'mat_b':>6} {'mat_a':>6} {'dmat':>6} {'bon_b':>6} {'bon_a':>6} {'dbon':>6} {'B?':>4}")
    print(header)
    for r in rows:
        print(f"{r['wave']:>4} {float(r['end_remaining_sec']):>8.3f} {r['ground_entities']:>5} "
              f"{r['ground_value']:>6} {str(r['materials_before']):>6} {str(r['materials_after']):>6} "
              f"{str(r['d_materials']):>6} {str(r['bonus_before']):>6} {str(r['bonus_after']):>6} "
              f"{str(r['d_bonus']):>6} {('Y' if r['bonus_matches_ground'] else 'n'):>4}")
    matches = sum(1 for r in rows if r["bonus_matches_ground"])
    print(f"  boundaries where d_bonus == ground_value: {matches}/{len(rows)}")
    print()

    # Verdict lines mirror the deploy checklist, one per shipped change.
    checks = {
        "materials present on every capture": presence["materials_coverage"] == 1.0,
        "materials never sentinel": presence["materials_sentinel_count"] == 0,
        "bonus_materials present on every capture": presence["bonus_materials_coverage"] == 1.0,
        "bonus_materials NOT stuck at -1": presence["bonus_materials_sentinel_count"] == 0,
        "material value > 1 observed": values["entities_with_value_gt1"] > 0,
        "loot_dash block on every capture": dash["captures_with_block"] == presence["captures"],
        "loot_dash saw 'armed'": dash["saw_armed"],
        "loot_dash saw an 'aborted_*'": bool(dash["aborted_states_seen"]),
        "loot_dash seq non-decreasing": dash["seq_regressions"] == 0,
        "loot_dash states all declared in source": not dash["undeclared_states"],
        "loot_dash active == legacy flag": dash["legacy_flag_disagreements"] == 0,
        "dropped_counts all zero": drops["all_zero"],
    }
    print("== checklist ==")
    for name, ok in checks.items():
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    failed = [k for k, v in checks.items() if not v]
    print()
    print("VERDICT:", "PASS" if not failed else f"FAIL ({len(failed)}): {failed}")

    if args.json:
        args.json.write_text(json.dumps({
            "run_dir": str(args.run_dir),
            "capture_schema_hashes": sorted(h for h in hashes if h),
            "presence": presence,
            "material_values": values,
            "loot_dash": dash,
            "dropped_counts": drops,
            "wave_boundaries": rows,
            "checks": checks,
            "verdict": "PASS" if not failed else "FAIL",
        }, indent=2), encoding="utf-8")
        print(f"wrote {args.json}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
