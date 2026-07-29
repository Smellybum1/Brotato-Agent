#!/usr/bin/env python3
"""Read the safety tail's lane-score decomposition (mod 0.2.55) -- Gate 0 for a
charge-aware lever in the tail.

Two questions, both over WAVE-17 ticks only:

PART 1  Which tail term binds?
        `_best_finale_interior_lane` publishes a per-tick block at capture path
        ``payload.teacher.contributions.tail`` (a SIBLING of ``desire``; it is
        NOT under a ``debug`` sub-key -- verified against
        runtime/agent_controller.gd:2260 and a real capture).  The block carries
        the selected lane's and the runner-up's seven score terms, the candidate
        pool statistics, and the binding body floor + its regime.

PART 2  The readback endpoint, recomputed from scratch: charging-vs-walking
        radial velocity w.r.t. the nearest pursuer within 600 u, measured on the
        FINAL command (``teacher.action``), not on the desire.

Discipline built into the output, all of them recorded failure modes:

  * `seq` FRESHNESS IS CHECKED FIRST.  The interior lane does not run every
    tick; a repeated `seq` across consecutive captures means the block is STALE
    and the tick is DROPPED, never averaged.  Every later statistic runs on
    fresh ticks only.
  * An empty ``selected`` dict is a CENTER-FALLBACK tick.  Counted separately,
    never treated as a lane whose terms are zero.
  * `pool` -- never `sampled` -- is the denominator for `body_floor_passed` and
    `enemy_filter_passed`.  `sampled` is a constant 24 while the counters
    iterate the smaller candidate pool.
  * Every ratio is printed next to its denominator; a constant field is called
    out explicitly as carrying no information.
  * Captures with ``control_dt_ms < 10`` are excluded from velocity-derived
    quantities.
  * When the arm's dose is not 1.0 the body-clearance diagnostics are on a
    different scale than a control arm's and the output says so.

No gameplay is run; nothing is written to the runs dir.

Usage (repo root, venv python):

    set APPDATA=C:\\Users\\moxhe\\AppData\\Roaming
    .venv\\Scripts\\python.exe scripts\\wp2_tail_decomposition.py \\
        --trials .tmp/gate0/tail_control_v255.jsonl

    .venv\\Scripts\\python.exe scripts\\wp2_tail_decomposition.py \\
        --run-id run_1785313331_32565 [--run-id ...] [--runs-dir DIR] \\
        [--wave 17] [--raw-rows 40] [--json out.json]
"""
from __future__ import annotations

import argparse
import json
import math
import os
import statistics
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Sequence, Tuple

# ---------------------------------------------------------------------------
# constants (all echoed in the output so nothing is hidden)
# ---------------------------------------------------------------------------

DEFAULT_WAVE = 17
CHARGE_RATIO_THRESH = 1.5      # shipped constant, potential_field.gd 0.2.54
PURSUER_RADIUS = 600.0         # readback gate: nearest pursuer within 600 u
MIN_CONTROL_DT_MS = 10.0       # below this, measured_v* explodes at start-up
LANE_TERMS = (
    "wall", "boss", "projectile", "center", "desire", "continuity",
    "enemy_penalty_term",
)
DOSE_KEYS = ("tail_calm_penalty_mult", "tail_calm_clearance_mult")


# ---------------------------------------------------------------------------
# locating runs / captures -- same convention as scripts/wp2_finale_loop.py
# (runs_dir) and scripts/wp2_v127_field_check.py (events.jsonl streaming).
# ---------------------------------------------------------------------------


def runs_dir(override: Optional[str] = None) -> Path:
    if override:
        return Path(override)
    env = os.environ.get("WP2_RUNS_DIR")
    if env:
        return Path(env)
    return Path(os.environ["APPDATA"]) / "Brotato" / "brotato_agent" / "runs"


def run_ids_from_trials(path: Path) -> List[str]:
    """Run ids from a wp2_finale_loop trials jsonl, in file order, deduped."""
    ids: List[str] = []
    seen = set()
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            rid = rec.get("run_id")
            if isinstance(rid, str) and rid and rid not in seen:
                seen.add(rid)
                ids.append(rid)
    return ids


def load_summary(run_dir: Path) -> Dict[str, Any]:
    path = run_dir / "summary.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def iter_captures(run_dir: Path) -> Iterator[Dict[str, Any]]:
    """Yield ``payload`` dicts of combat_capture events, in file order."""
    path = run_dir / "events.jsonl"
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                evt = json.loads(line)
            except json.JSONDecodeError:
                continue           # malformed/truncated line, counted by caller
            if evt.get("event") != "combat_capture":
                continue
            payload = evt.get("payload")
            if isinstance(payload, dict):
                yield payload


def dig(obj: Any, *keys, default=None):
    for key in keys:
        if not isinstance(obj, dict):
            return default
        obj = obj.get(key)
        if obj is None:
            return default
    return obj


def tail_block(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """The per-tick tail block, or None when the build did not emit one.

    Path VERIFIED against agent_controller.gd (``contributions`` is
    ``last_move_debug["debug"]``, whose keys are profile/enemies/projectiles/
    finale_translation/loot_dash/desire/tail).  ``tail`` is a sibling of
    ``desire``, not nested under a ``debug`` key.
    """
    return dig(payload, "teacher", "contributions", "tail")


# ---------------------------------------------------------------------------
# PART 1 -- freshness, then everything else
# ---------------------------------------------------------------------------


def split_fresh(payloads: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Drop stale-seq ticks; classify fresh ticks into lane vs center-fallback.

    A tick is fresh when its `seq` differs from the previously SEEN seq (per
    run).  The first capture of a run is fresh by construction.  Blocks that are
    absent entirely are counted separately -- they are not stale, they are a
    build that never emitted the instrument.
    """
    total = len(payloads)
    missing = 0
    stale = 0
    fresh: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []   # (payload, block)
    prev_seq: Any = object()
    for payload in payloads:
        block = tail_block(payload)
        if not isinstance(block, dict) or "seq" not in block:
            missing += 1
            continue
        seq = block.get("seq")
        if seq == prev_seq:
            stale += 1
            continue
        prev_seq = seq
        fresh.append((payload, block))
    lane: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []
    fallback = 0
    for payload, block in fresh:
        selected = block.get("selected")
        if isinstance(selected, dict) and selected:
            lane.append((payload, block))
        else:
            fallback += 1
    return {
        "captures_total": total,
        "blocks_missing": missing,
        "distinct_seq": len({b.get("seq") for _, b in fresh}),
        "stale_dropped": stale,
        "fresh": fresh,
        "fresh_n": len(fresh),
        "center_fallback_n": fallback,
        "lane_ticks": lane,
        "lane_n": len(lane),
    }


def quantiles(values: Sequence[float]) -> Dict[str, Optional[float]]:
    if not values:
        return {"n": 0, "min": None, "p25": None, "median": None,
                "p75": None, "max": None, "mean": None}
    ordered = sorted(values)

    def pct(p: float) -> float:
        if len(ordered) == 1:
            return ordered[0]
        idx = p * (len(ordered) - 1)
        lo = int(math.floor(idx))
        hi = int(math.ceil(idx))
        if lo == hi:
            return ordered[lo]
        return ordered[lo] + (ordered[hi] - ordered[lo]) * (idx - lo)

    return {
        "n": len(ordered),
        "min": ordered[0],
        "p25": pct(0.25),
        "median": pct(0.50),
        "p75": pct(0.75),
        "max": ordered[-1],
        "mean": statistics.fmean(ordered),
    }


def term_magnitudes(lane_ticks: Sequence[Tuple[Dict[str, Any], Dict[str, Any]]]
                    ) -> Dict[str, Any]:
    """Distribution of each selected-lane term and its share of |total|."""
    series: Dict[str, List[float]] = {t: [] for t in LANE_TERMS}
    totals: List[float] = []
    share_sums: Dict[str, float] = {t: 0.0 for t in LANE_TERMS}
    share_n = 0
    for _payload, block in lane_ticks:
        sel = block.get("selected") or {}
        total = float(sel.get("total", 0.0))
        totals.append(total)
        for term in LANE_TERMS:
            series[term].append(float(sel.get(term, 0.0)))
        if abs(total) > 0.0:
            share_n += 1
            for term in LANE_TERMS:
                share_sums[term] += abs(float(sel.get(term, 0.0))) / abs(total)
    out = {
        "n": len(lane_ticks),
        "total": quantiles(totals),
        "terms": {t: quantiles(series[t]) for t in LANE_TERMS},
        "share_denominator": share_n,
        "mean_abs_share_of_total": {
            t: (share_sums[t] / share_n if share_n else None) for t in LANE_TERMS
        },
        "constant_terms": [t for t in LANE_TERMS
                           if series[t] and len(set(series[t])) == 1],
    }
    if share_n:
        out["dominant_term"] = max(
            LANE_TERMS, key=lambda t: share_sums[t] / share_n)
    else:
        out["dominant_term"] = None
    return out


def margin_vs_penalty(lane_ticks: Sequence[Tuple[Dict[str, Any], Dict[str, Any]]]
                      ) -> Dict[str, Any]:
    """HEADLINE: can the enemy-penalty term flip the argmax?

    margin = selected.total - alt.total; the comparison is
    |selected.enemy_penalty_term| > margin.  Ticks with no runner-up (`alt`
    empty) have no margin and are reported as their own bucket, never folded in
    as a zero margin.
    """
    rows: List[Dict[str, Any]] = []
    no_alt = 0
    flippable = 0
    for payload, block in lane_ticks:
        sel = block.get("selected") or {}
        alt = block.get("alt") or {}
        if not alt:
            no_alt += 1
            continue
        margin = float(sel.get("total", 0.0)) - float(alt.get("total", 0.0))
        pen = float(sel.get("enemy_penalty_term", 0.0))
        flip = abs(pen) > margin
        flippable += 1 if flip else 0
        rows.append({
            "seq": block.get("seq"),
            "wave": payload.get("wave"),
            "margin": margin,
            "enemy_penalty_term": pen,
            "alt_penalty_term": float(alt.get("enemy_penalty_term", 0.0)),
            "flippable": flip,
        })
    return {
        "denominator_with_alt": len(rows),
        "ticks_without_alt": no_alt,
        "flippable": flippable,
        "flippable_fraction": (flippable / len(rows)) if rows else None,
        "margin": quantiles([r["margin"] for r in rows]),
        "abs_penalty": quantiles([abs(r["enemy_penalty_term"]) for r in rows]),
        "rows": rows,
    }


def binding_constraint(lane_and_fallback: Sequence[Tuple[Dict[str, Any], Dict[str, Any]]]
                       ) -> Dict[str, Any]:
    """Regime mix and the two pass counters, both over `pool` as denominator."""
    regimes: Dict[str, int] = {}
    pool_sum = 0
    body_pass_sum = 0
    enemy_pass_sum = 0
    pool_zero = 0
    pools: List[float] = []
    sampled_vals: List[float] = []
    body_floor: List[float] = []
    highest: List[float] = []
    lowest_pen: List[float] = []
    for _payload, block in lane_and_fallback:
        regime = block.get("body_floor_regime")
        key = regime if isinstance(regime, str) and regime else "<empty>"
        regimes[key] = regimes.get(key, 0) + 1
        pool = int(block.get("pool", 0) or 0)
        pools.append(float(pool))
        sampled_vals.append(float(block.get("sampled", 0) or 0))
        if pool <= 0:
            pool_zero += 1
        else:
            pool_sum += pool
            body_pass_sum += int(block.get("body_floor_passed", 0) or 0)
            enemy_pass_sum += int(block.get("enemy_filter_passed", 0) or 0)
        body_floor.append(float(block.get("body_floor", 0.0)))
        highest.append(float(block.get("highest_body_clearance", 0.0)))
        lowest_pen.append(float(block.get("lowest_enemy_penalty", 0.0)))
    n = len(lane_and_fallback)
    return {
        "n": n,
        "regime_counts": regimes,
        "regime_fractions": {k: v / n for k, v in regimes.items()} if n else {},
        "pool": quantiles(pools),
        "sampled": quantiles(sampled_vals),
        "sampled_is_constant": len(set(sampled_vals)) <= 1 and bool(sampled_vals),
        "pool_zero_ticks": pool_zero,
        "pool_sum_denominator": pool_sum,
        "body_floor_passed_sum": body_pass_sum,
        "body_floor_pass_rate_over_pool": (
            body_pass_sum / pool_sum if pool_sum else None),
        "enemy_filter_passed_sum": enemy_pass_sum,
        "enemy_filter_pass_rate_over_pool": (
            enemy_pass_sum / pool_sum if pool_sum else None),
        "body_floor": quantiles(body_floor),
        "highest_body_clearance": quantiles(highest),
        "lowest_enemy_penalty": quantiles(lowest_pen),
    }


# ---------------------------------------------------------------------------
# PART 2 -- the readback endpoint, recomputed
# ---------------------------------------------------------------------------


def is_pursuer(enemy: Dict[str, Any]) -> bool:
    """The `pursuer` entity class.

    UNIFIED with scripts/wp2_confinement.py -- one definition of the entity
    class across both scripts, or the two eventually give two different answers
    to the same question.  A plain substring test for "pursuer" was REJECTED:
    it would also match any future type whose name merely contains the word
    (e.g. a hypothetical "pursuer_spawner" or "anti_pursuer").
    """
    text = f"{enemy.get('type_id', '')}|{enemy.get('script_path', '')}"
    return "/pursuer/" in text or "pursuer_stats" in text


def nearest_pursuer(payload: Dict[str, Any],
                    radius: float = PURSUER_RADIUS) -> Optional[Dict[str, Any]]:
    px = float(dig(payload, "player", "x", default=0.0))
    py = float(dig(payload, "player", "y", default=0.0))
    best = None
    best_d = radius
    for enemy in (dig(payload, "entities", "enemies", default=[]) or []):
        if not isinstance(enemy, dict) or not is_pursuer(enemy):
            continue
        dx = float(enemy.get("x", 0.0)) - px
        dy = float(enemy.get("y", 0.0)) - py
        dist = math.hypot(dx, dy)
        if dist <= best_d and dist > 0.0:
            best_d = dist
            best = enemy
    return best


def is_charging(enemy: Dict[str, Any],
                thresh: float = CHARGE_RATIO_THRESH) -> bool:
    """|v| / speed > thresh.  A MISSING or zero speed counts as CHARGING --
    the shipped 0.2.54 defensive rule: an absent signal must never make the
    agent (or this analysis) read calmer than reality."""
    speed = enemy.get("speed")
    if speed is None:
        return True
    try:
        speed = float(speed)
    except (TypeError, ValueError):
        return True
    if speed <= 0.0:
        return True
    v = math.hypot(float(enemy.get("vx", 0.0)), float(enemy.get("vy", 0.0)))
    return (v / speed) > thresh


def radial_velocity(payload: Dict[str, Any], enemy: Dict[str, Any]
                    ) -> Optional[float]:
    """FINAL command dotted with the unit player->enemy vector, NEGATED, so
    +1 = moving straight away from the pursuer."""
    px = float(dig(payload, "player", "x", default=0.0))
    py = float(dig(payload, "player", "y", default=0.0))
    dx = float(enemy.get("x", 0.0)) - px
    dy = float(enemy.get("y", 0.0)) - py
    dist = math.hypot(dx, dy)
    if dist <= 0.0:
        return None
    ax = float(dig(payload, "teacher", "action", "x", default=0.0))
    ay = float(dig(payload, "teacher", "action", "y", default=0.0))
    amag = math.hypot(ax, ay)
    if amag <= 0.0:
        return 0.0
    ax, ay = ax / amag, ay / amag
    return -((ax * dx + ay * dy) / dist)


def charge_readback(payloads: Sequence[Dict[str, Any]],
                    radius: float = PURSUER_RADIUS) -> Dict[str, Any]:
    charging: List[float] = []
    walking: List[float] = []
    ratios_charge: List[float] = []
    ratios_walk: List[float] = []
    no_pursuer = 0
    dt_excluded = 0
    for payload in payloads:
        dt = payload.get("control_dt_ms")
        if dt is not None and float(dt) < MIN_CONTROL_DT_MS:
            dt_excluded += 1
            continue
        enemy = nearest_pursuer(payload, radius)
        if enemy is None:
            no_pursuer += 1
            continue
        rv = radial_velocity(payload, enemy)
        if rv is None:
            continue
        speed = float(enemy.get("speed", 0.0) or 0.0)
        v = math.hypot(float(enemy.get("vx", 0.0)), float(enemy.get("vy", 0.0)))
        ratio = (v / speed) if speed > 0 else float("inf")
        if is_charging(enemy):
            charging.append(rv)
            ratios_charge.append(ratio)
        else:
            walking.append(rv)
            ratios_walk.append(ratio)
    mc = statistics.fmean(charging) if charging else None
    mw = statistics.fmean(walking) if walking else None
    return {
        "captures_considered": len(payloads),
        "excluded_low_control_dt": dt_excluded,
        "no_pursuer_within_radius": no_pursuer,
        "radius": radius,
        "charge_ratio_thresh": CHARGE_RATIO_THRESH,
        "charging_n": len(charging),
        "walking_n": len(walking),
        "charging_mean_radial": mc,
        "walking_mean_radial": mw,
        "differentiation": (mc - mw) if (mc is not None and mw is not None) else None,
        "charging_radial": quantiles(charging),
        "walking_radial": quantiles(walking),
        "charge_ratio_charging": quantiles(ratios_charge),
        "charge_ratio_walking": quantiles(ratios_walk),
    }


# ---------------------------------------------------------------------------
# driver
# ---------------------------------------------------------------------------


def analyze_run(run_dir: Path, wave: int) -> Dict[str, Any]:
    summary = load_summary(run_dir)
    payloads = [p for p in iter_captures(run_dir) if int(p.get("wave", 0)) == wave]
    freshness = split_fresh(payloads)
    lane = freshness["lane_ticks"]
    fresh = freshness["fresh"]
    return {
        "run_id": run_dir.name,
        "mod_version": summary.get("mod_version"),
        "policy_version": summary.get("policy_version"),
        "result": summary.get("result"),
        "last_wave": summary.get("last_wave"),
        "dose": {k: summary.get(k) for k in DOSE_KEYS},
        "wave": wave,
        "freshness": {k: v for k, v in freshness.items()
                      if k not in ("fresh", "lane_ticks")},
        "terms": term_magnitudes(lane),
        "margin": margin_vs_penalty(lane),
        "binding": binding_constraint(fresh),
        "readback": charge_readback(payloads),
        "_payloads_wave": payloads,
    }


def _fmt(x: Optional[float], nd: int = 4) -> str:
    if x is None:
        return "n/a"
    if isinstance(x, float) and (math.isinf(x) or math.isnan(x)):
        return str(x)
    return f"{x:.{nd}f}"


def _print_quantiles(label: str, q: Dict[str, Any]) -> None:
    print(f"  {label:<22} n={q['n']:<6} min={_fmt(q['min'],3):>12} "
          f"p25={_fmt(q['p25'],3):>12} med={_fmt(q['median'],3):>12} "
          f"p75={_fmt(q['p75'],3):>12} max={_fmt(q['max'],3):>12}")


def report(results: Sequence[Dict[str, Any]], wave: int, raw_rows: int) -> Dict[str, Any]:
    print("=" * 78)
    print(f"WP2 SAFETY-TAIL DECOMPOSITION  --  wave {wave} only")
    print("=" * 78)
    for res in results:
        print(f"  run {res['run_id']}  mod={res['mod_version']} "
              f"result={res['result']} last_wave={res['last_wave']} "
              f"dose={res['dose']}")
    dosed = [r for r in results
             if any(r["dose"].get(k) not in (None, 1.0, 1) for k in DOSE_KEYS)]
    if dosed:
        print()
        print("  !! WARNING: at least one run has a NON-UNIT dose "
              f"({[r['run_id'] for r in dosed]}).")
        print("     tail_calm_clearance_mult != 1.0 deliberately INFLATES what")
        print("     _predictive_body_path_clearance returns, so body_floor /")
        print("     highest_body_clearance / penalty diagnostics are on a")
        print("     DIFFERENT SCALE than a control arm's.  Do NOT compare them")
        print("     across arms.")
    if any(r["dose"].get(k) is None for r in results for k in DOSE_KEYS):
        print("  note: one or more runs' summary.json lacks the dose keys "
              f"{DOSE_KEYS} -- dose UNKNOWN for those, not assumed 1.0.")

    # ---- pooled freshness (item 1, first) --------------------------------
    tot = sum(r["freshness"]["captures_total"] for r in results)
    missing = sum(r["freshness"]["blocks_missing"] for r in results)
    stale = sum(r["freshness"]["stale_dropped"] for r in results)
    freshn = sum(r["freshness"]["fresh_n"] for r in results)
    distinct = sum(r["freshness"]["distinct_seq"] for r in results)
    fallback = sum(r["freshness"]["center_fallback_n"] for r in results)
    lane_n = sum(r["freshness"]["lane_n"] for r in results)
    print()
    print("-- 1. SEQ FRESHNESS (checked before anything else) ---------------")
    print(f"  wave-{wave} captures total            : {tot}")
    print(f"  captures with NO tail block          : {missing}")
    print(f"  distinct seq (sum over runs)         : {distinct}")
    print(f"  DROPPED as stale (repeated seq)      : {stale}"
          f"   ({stale/tot:.4f} of {tot})" if tot else "")
    print(f"  FRESH ticks (all later stats use these): {freshn}")
    print(f"    of which center-fallback (selected=={{}}): {fallback}")
    print(f"    of which scored lane ticks           : {lane_n}")

    # ---- pooled helpers ---------------------------------------------------
    lane_all: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []
    fresh_all: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []
    payloads_all: List[Dict[str, Any]] = []
    for res in results:
        payloads_all.extend(res["_payloads_wave"])
    for res in results:
        fr = split_fresh(res["_payloads_wave"])
        lane_all.extend(fr["lane_ticks"])
        fresh_all.extend(fr["fresh"])

    terms = term_magnitudes(lane_all)
    print()
    print("-- 2. SELECTED-LANE TERM MAGNITUDES ------------------------------")
    print(f"  lane ticks (denominator)             : {terms['n']}")
    _print_quantiles("total", terms["total"])
    for t in LANE_TERMS:
        _print_quantiles(t, terms["terms"][t])
    print(f"  mean |term| / |total|   (denominator = {terms['share_denominator']}"
          " ticks with |total|>0):")
    for t in LANE_TERMS:
        print(f"    {t:<22} {_fmt(terms['mean_abs_share_of_total'][t])}")
    print(f"  DOMINANT TERM: {terms['dominant_term']}")
    if terms["constant_terms"]:
        print(f"  CONSTANT ACROSS ALL TICKS (carries no information): "
              f"{terms['constant_terms']}")

    marg = margin_vs_penalty(lane_all)
    print()
    print("-- 3. HEADLINE: can enemy_penalty_term flip the argmax? ----------")
    print(f"  lane ticks with a runner-up (denominator): {marg['denominator_with_alt']}")
    print(f"  lane ticks with NO alt (excluded)        : {marg['ticks_without_alt']}")
    print(f"  |enemy_penalty_term| > margin            : {marg['flippable']}")
    print(f"  FLIPPABLE FRACTION                       : "
          f"{_fmt(marg['flippable_fraction'])}  "
          f"({marg['flippable']}/{marg['denominator_with_alt']})")
    _print_quantiles("margin", marg["margin"])
    _print_quantiles("|enemy_penalty_term|", marg["abs_penalty"])
    print(f"  RAW SERIES (first {raw_rows} lane ticks):")
    print(f"    {'seq':>8} {'margin':>14} {'enemy_penalty':>14} "
          f"{'alt_penalty':>14} flip")
    for row in marg["rows"][:raw_rows]:
        print(f"    {str(row['seq']):>8} {row['margin']:>14.4f} "
              f"{row['enemy_penalty_term']:>14.4f} "
              f"{row['alt_penalty_term']:>14.4f} "
              f"{'YES' if row['flippable'] else 'no'}")

    bind = binding_constraint(fresh_all)
    print()
    print("-- 4. WHICH CONSTRAINT BINDS -------------------------------------")
    print(f"  fresh ticks (denominator)            : {bind['n']}")
    for k, v in sorted(bind["regime_counts"].items(), key=lambda kv: -kv[1]):
        frac = v / bind["n"] if bind["n"] else 0.0
        print(f"    body_floor_regime {k:<12} {v:>7}  ({frac:.4f} of {bind['n']})")
    _print_quantiles("pool", bind["pool"])
    _print_quantiles("sampled", bind["sampled"])
    if bind["sampled_is_constant"]:
        print("    NOTE: `sampled` is CONSTANT -> carries no information; it is "
              "NOT used as a denominator.")
    print(f"  pool==0 ticks (excluded from rates)   : {bind['pool_zero_ticks']}")
    print(f"  POOL SUM (denominator for both rates) : {bind['pool_sum_denominator']}")
    print(f"    body_floor_passed  {bind['body_floor_passed_sum']:>8}  rate="
          f"{_fmt(bind['body_floor_pass_rate_over_pool'])}")
    print(f"    enemy_filter_passed{bind['enemy_filter_passed_sum']:>8}  rate="
          f"{_fmt(bind['enemy_filter_pass_rate_over_pool'])}")
    _print_quantiles("body_floor", bind["body_floor"])
    _print_quantiles("highest_body_clear", bind["highest_body_clearance"])
    _print_quantiles("lowest_enemy_penalty", bind["lowest_enemy_penalty"])

    rb = charge_readback(payloads_all)
    print()
    print("-- PART 2. READBACK: charging vs walking on the FINAL command ----")
    print(f"  wave-{wave} captures considered       : {rb['captures_considered']}")
    print(f"  excluded control_dt_ms < {MIN_CONTROL_DT_MS:g}        : "
          f"{rb['excluded_low_control_dt']}")
    print(f"  no pursuer within {rb['radius']:g} u         : "
          f"{rb['no_pursuer_within_radius']}")
    print(f"  CHARGING  n={rb['charging_n']:<6} mean radial = "
          f"{_fmt(rb['charging_mean_radial'])}")
    print(f"  WALKING   n={rb['walking_n']:<6} mean radial = "
          f"{_fmt(rb['walking_mean_radial'])}")
    print(f"  DIFFERENTIATION (charging - walking) = "
          f"{_fmt(rb['differentiation'])}")
    _print_quantiles("radial charging", rb["charging_radial"])
    _print_quantiles("radial walking", rb["walking_radial"])
    _print_quantiles("|v|/speed charging", rb["charge_ratio_charging"])
    _print_quantiles("|v|/speed walking", rb["charge_ratio_walking"])
    print("  (prior control values to reproduce: charging +0.091, "
          "walking +0.055, differentiation +0.036)")

    return {
        "wave": wave,
        "runs": [{k: v for k, v in r.items() if not k.startswith("_")}
                 for r in results],
        "pooled": {
            "freshness": {
                "captures_total": tot, "blocks_missing": missing,
                "stale_dropped": stale, "fresh_n": freshn,
                "center_fallback_n": fallback, "lane_n": lane_n,
            },
            "terms": terms,
            "margin": marg,
            "binding": bind,
            "readback": rb,
        },
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--trials", help="wp2_finale_loop trials jsonl to read run ids from")
    ap.add_argument("--run-id", action="append", default=[], help="repeatable")
    ap.add_argument("--runs-dir", default=None)
    ap.add_argument("--wave", type=int, default=DEFAULT_WAVE)
    ap.add_argument("--raw-rows", type=int, default=40,
                    help="per-tick (margin, enemy_penalty) rows to dump")
    ap.add_argument("--json", default=None, help="write the full result dict here")
    args = ap.parse_args(argv)

    ids: List[str] = list(args.run_id)
    if args.trials:
        ids.extend(r for r in run_ids_from_trials(Path(args.trials)) if r not in ids)
    if not ids:
        ap.error("no run ids: pass --trials and/or --run-id")

    base = runs_dir(args.runs_dir)
    results = []
    for rid in ids:
        rdir = base / rid
        if not (rdir / "events.jsonl").exists():
            print(f"  SKIP {rid}: no events.jsonl under {base}")
            continue
        results.append(analyze_run(rdir, args.wave))
    if not results:
        print("no runs analysed")
        return 1

    out = report(results, args.wave, args.raw_rows)
    if args.json:
        Path(args.json).write_text(json.dumps(out, indent=2, default=str),
                                   encoding="utf-8")
        print(f"\nwrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
