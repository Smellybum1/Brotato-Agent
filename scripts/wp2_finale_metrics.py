#!/usr/bin/env python3
"""Per-trial wave-20 behavioural metrics from the capture stream.

The finale baseline must be measured on BEHAVIOUR, not just win/lose: two
controllers can share a win rate while differing wildly in how much they stand
still, how often they reverse, and how long the boss lives.

Input is the JSONL written by scripts/wp2_finale_loop.py (fields: run_id, label,
fixture_file, valid, result, ...). Telemetry is read by STREAMING
%APPDATA%/Brotato/brotato_agent/runs/<run_id>/events.jsonl -- never read_text():
a resume-failed full run is up to ~330 MB.

VERIFIED CAPTURE SHAPES (run_1785040079_20403, wave 20, predator, victory):
  payload["teacher"]["action"]         -> {"x": 1, "y": 0}     (DICT, not a list)
  payload["teacher"]["previous_action"]-> {"x": 1, "y": 0}
  payload["teacher"]["action_fresh"]   -> true
  payload["player"]                    -> {..., "hp": 56, "measured_vx": 3708.31,
                                           "measured_vy": 0.0, "x":.., "y":..}
  payload["wave_time"]                 -> {"elapsed_sec": 0.008469, ...}
  payload["entities"]["bosses"][0]     -> {"hp":29250,"max_hp":29250,
                                           "health_ratio":1,"x":..,"y":..,...}
_vec() still accepts the 2-element-list form defensively, but the real shape on
disk is the dict.

EVERY ratio is emitted with its raw numerator and denominator, and a zero
denominator yields None -- never 0.0. This project has repeatedly been burned by
a ratio silently computed over an empty or wrongly-filtered denominator.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import sys
from pathlib import Path
from typing import Any, Iterable, Iterator

WAVE = 20
STATIONARY_SPEED = 1.0
ZERO_ACTION_EPS = 1e-6
# `measured_vx/vy` are a displacement/dt derivative, so at start-up dt they blow up:
# measured (11124.9, 0.0) at control_dt_ms=2 against a real `speed` of 445. Velocity
# metrics therefore run only over captures whose dt is a real control interval
# (steady state is ~50 ms). Excluded captures are reported, never silently dropped.
MIN_CONTROL_DT_MS = 10

RATIO_METRICS = [
    ("stationary_frac", "n_stationary", "n_velocity_captures"),
    ("action_zero_frac", "n_action_zero", "n_captures_w20"),
    ("reversal_rate", "n_reversals", "n_reversal_pairs"),
    ("action_fresh_frac", "n_action_fresh", "n_captures_w20"),
]

METRIC_FIELDS = [
    "n_captures_w20",
    "duration_sec",
    "damage_taken",
    "n_hit_events",
    "hp_start",
    "hp_end",
    "hp_min",
    "boss_ttk_sec",
    "boss_hp_ratio_last",
    "n_trailing_timer_reset",
    "stationary_frac",
    "n_stationary",
    "n_velocity_captures",
    "action_zero_frac",
    "n_action_zero",
    "reversal_rate",
    "n_reversals",
    "n_reversal_pairs",
    "straightness",
    "net_displacement",
    "path_length",
    "action_fresh_frac",
    "n_action_fresh",
]


# --------------------------------------------------------------------------
# pure helpers (unit-tested)
# --------------------------------------------------------------------------


def _num(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _vec(action: Any) -> tuple[float, float]:
    """(x, y) from the commanded action. Dict on disk; list tolerated."""
    if isinstance(action, dict):
        x = _num(action.get("x")) or 0.0
        y = _num(action.get("y")) or 0.0
        return x, y
    if isinstance(action, (list, tuple)) and len(action) == 2:
        return (_num(action[0]) or 0.0, _num(action[1]) or 0.0)
    return 0.0, 0.0


def _ratio(num: int, den: int) -> float | None:
    """None -- never 0.0 -- when nothing was counted."""
    if den <= 0:
        return None
    return num / den


def compute_metrics(captures: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Wave-20 metrics from an iterable of combat_capture PAYLOADS.

    Only `wave == 20` payloads are considered; they are sorted by capture_seq.
    """
    rows = [c for c in captures if c.get("wave") == WAVE]
    rows.sort(key=lambda c: (c.get("capture_seq") or 0))

    out: dict[str, Any] = {k: None for k in METRIC_FIELDS}
    out["n_captures_w20"] = len(rows)
    for key in ("n_stationary", "n_action_zero", "n_reversals", "n_reversal_pairs",
                "n_action_fresh", "n_hit_events", "n_velocity_captures",
                "n_trailing_timer_reset"):
        out[key] = 0
    out["damage_taken"] = 0.0
    if not rows:
        # Every ratio stays None: zero captures must not read as "0.0 of it happened".
        return out

    elapsed = [_num((c.get("wave_time") or {}).get("elapsed_sec")) for c in rows]
    known_t = [t for t in elapsed if t is not None]
    first_t = known_t[0] if known_t else None
    # `wave_time.elapsed_sec` RESETS TO ~0 on the last capture or two of a won wave
    # (measured: seq 438 -> 21.870, seq 439 -> 0.034, still wave==20, still
    # wave_time.valid). Last-minus-first therefore reported 0.076 s for a 21.9 s
    # wave, and only on victories -- a death has no reset, so the metric silently
    # mixed two different quantities across arms. Use the max, and count the
    # post-reset captures so the reset stays visible instead of being papered over.
    if known_t:
        peak_t = max(known_t)
        out["duration_sec"] = peak_t - first_t
        peak_idx = max(i for i, t in enumerate(elapsed) if t == peak_t)
        out["n_trailing_timer_reset"] = len(rows) - 1 - peak_idx

    hps = [_num((c.get("player") or {}).get("hp")) for c in rows]
    known_hp = [h for h in hps if h is not None]
    if known_hp:
        out["hp_start"] = known_hp[0]
        out["hp_end"] = known_hp[-1]
        out["hp_min"] = min(known_hp)
    damage = 0.0
    hits = 0
    for prev, cur in zip(known_hp, known_hp[1:]):
        if cur < prev:
            damage += prev - cur
            hits += 1
    out["damage_taken"] = damage
    out["n_hit_events"] = hits

    # boss ttk: last capture that still HAS a boss, relative to the first w20 capture
    last_boss_idx = -1
    boss_hp_ratio_last: float | None = None
    for i, c in enumerate(rows):
        bosses = (c.get("entities") or {}).get("bosses") or []
        if bosses:
            last_boss_idx = i
            first = bosses[0]
            if isinstance(first, dict):
                boss_hp_ratio_last = _num(first.get("health_ratio"))
    if last_boss_idx >= 0:
        t_last = elapsed[last_boss_idx]
        if t_last is not None and first_t is not None:
            out["boss_ttk_sec"] = t_last - first_t
        out["boss_hp_ratio_last"] = boss_hp_ratio_last

    n_stationary = 0
    n_velocity = 0
    n_action_zero = 0
    n_fresh = 0
    mags: list[float] = []
    vecs: list[tuple[float, float]] = []
    for c in rows:
        player = c.get("player") or {}
        dt_ms = _num(c.get("control_dt_ms"))
        if dt_ms is not None and dt_ms >= MIN_CONTROL_DT_MS:
            n_velocity += 1
            vx = _num(player.get("measured_vx")) or 0.0
            vy = _num(player.get("measured_vy")) or 0.0
            if math.hypot(vx, vy) < STATIONARY_SPEED:
                n_stationary += 1
        teacher = c.get("teacher") or {}
        ax, ay = _vec(teacher.get("action"))
        mag = math.hypot(ax, ay)
        mags.append(mag)
        vecs.append((ax, ay))
        if mag < ZERO_ACTION_EPS:
            n_action_zero += 1
        if teacher.get("action_fresh") is True:
            n_fresh += 1
    out["n_stationary"] = n_stationary
    out["n_velocity_captures"] = n_velocity
    out["n_action_zero"] = n_action_zero
    out["n_action_fresh"] = n_fresh

    n_pairs = 0
    n_rev = 0
    for i in range(1, len(vecs)):
        m0, m1 = mags[i - 1], mags[i]
        if m0 <= ZERO_ACTION_EPS or m1 <= ZERO_ACTION_EPS:
            continue
        n_pairs += 1
        dot = (vecs[i - 1][0] * vecs[i][0] + vecs[i - 1][1] * vecs[i][1]) / (m0 * m1)
        if dot < 0:
            n_rev += 1
    out["n_reversal_pairs"] = n_pairs
    out["n_reversals"] = n_rev

    pts = [
        ((_num((c.get("player") or {}).get("x")), _num((c.get("player") or {}).get("y"))))
        for c in rows
    ]
    pts = [(x, y) for x, y in pts if x is not None and y is not None]
    path = 0.0
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        path += math.hypot(x1 - x0, y1 - y0)
    out["path_length"] = path
    if len(pts) >= 2:
        out["net_displacement"] = math.hypot(pts[-1][0] - pts[0][0], pts[-1][1] - pts[0][1])
    elif pts:
        out["net_displacement"] = 0.0
    if path > 0 and out["net_displacement"] is not None:
        out["straightness"] = out["net_displacement"] / path
    else:
        out["straightness"] = None  # explicit: no path -> null, not 0.0

    for name, num_key, den_key in RATIO_METRICS:
        out[name] = _ratio(int(out[num_key]), int(out[den_key]))
    return out


def iter_capture_payloads(events_path: Path) -> Iterator[dict[str, Any]]:
    """Stream combat_capture payloads. NEVER read_text() -- files reach ~330 MB."""
    try:
        handle = events_path.open("r", encoding="utf-8", errors="replace")
    except OSError:
        return
    with handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("event") != "combat_capture":
                continue
            payload = event.get("payload")
            if isinstance(payload, dict):
                yield payload


def load_trials(path: Path, label: str | None, include_invalid: bool) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    # Read once; tolerate the loop appending (a torn final line is skipped).
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(row, dict):
                continue
            if label is not None and row.get("label") != label:
                continue
            if not include_invalid and row.get("valid") is not True:
                continue
            rows.append(row)
    return rows


def runs_dir() -> Path:
    return Path(os.environ["APPDATA"]) / "Brotato" / "brotato_agent" / "runs"


def _fmt(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, float):
        return f"{value:.4g}"
    return str(value)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=Path, required=True)
    ap.add_argument("--label", type=str, default=None)
    ap.add_argument("--include-invalid", action="store_true")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    if not args.trials.exists():
        raise SystemExit(f"missing trials file: {args.trials}")

    trials = load_trials(args.trials, args.label, args.include_invalid)
    rd = runs_dir()

    out_rows: list[dict[str, Any]] = []
    for trial in trials:
        run_id = str(trial.get("run_id") or "")
        events = rd / run_id / "events.jsonl"
        row: dict[str, Any] = {
            "run_id": run_id,
            "label": trial.get("label"),
            "fixture_file": trial.get("fixture_file"),
            "valid": trial.get("valid"),
            "result": trial.get("result"),
            "summary_damage_taken": trial.get("damage_taken"),
            "events_found": events.exists(),
        }
        if events.exists():
            row.update(compute_metrics(iter_capture_payloads(events)))
        else:
            row.update({k: None for k in METRIC_FIELDS})
        out_rows.append(row)

    # Raw rows FIRST, always. An aggregate without its rows is not evidence.
    print("--- raw per-trial metrics ---")
    header = ["run_id", "result", "valid"] + METRIC_FIELDS
    widths = {h: max(len(h), 9) for h in header}
    widths["run_id"] = 24
    print("  ".join(h.ljust(widths[h]) for h in header))
    for row in out_rows:
        print("  ".join(_fmt(row.get(h)).ljust(widths[h]) for h in header))

    print("\n--- aggregate ---")
    print(f"trials: {len(out_rows)} (label={args.label} include_invalid={args.include_invalid})")
    wins = sum(1 for r in out_rows if str(r.get("result", "")).lower() == "victory")
    print(f"victories: {wins}/{len(out_rows)}")
    print(f"{'metric':<20} {'n':>4} {'median':>12} {'mean':>12} {'min':>12} {'max':>12}")
    for name in METRIC_FIELDS:
        vals = [
            float(r[name]) for r in out_rows
            if isinstance(r.get(name), (int, float)) and not isinstance(r.get(name), bool)
        ]
        if not vals:
            print(f"{name:<20} {0:>4} {'null':>12} {'null':>12} {'null':>12} {'null':>12}")
            continue
        print(
            f"{name:<20} {len(vals):>4} {statistics.median(vals):>12.4g} "
            f"{statistics.fmean(vals):>12.4g} {min(vals):>12.4g} {max(vals):>12.4g}"
        )

    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("w", encoding="utf-8", newline="\n") as fh:
            for row in out_rows:
                fh.write(json.dumps(row) + "\n")
        print(f"\nper-trial rows written to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
