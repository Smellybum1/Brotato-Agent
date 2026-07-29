"""Re-score wave-17 dose trials on TERMINAL outcome and estimate the
between/within source-state variance split for the landmark-continuation endpoint.

Zero machine time: the existing trials already resume at the wave-16 shop and play
through to run end, so only the endpoint read off them changes.

Source state is the inferential unit. K continuations from one save are NOT K
independent builds.

Usage:
    python scripts/wp2_landmark_continuation_pilot.py [--dir .tmp/dose_fixtures]
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

CAMPAIGNS = ("round1_trials", "v2_trials", "v3_trials", "v4_trials")
ARM_RE = re.compile(r"__([A-Z0-9]+)\.json$")

# Natural full-run comparison, shipped build (2x18 runs): 34 reached wave 16, 26 won.
NATURAL_REACHED_W16 = 34
NATURAL_WINS = 26


def load_trials(base: Path, campaigns=CAMPAIGNS) -> list[dict]:
    rows: list[dict] = []
    for name in campaigns:
        path = base / f"{name}.jsonl"
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            fixture = row.get("fixture_file", "")
            match = ARM_RE.search(fixture)
            row["campaign"] = name
            row["arm"] = match.group(1) if match else "?"
            row["state"] = ARM_RE.sub("", fixture)
            waves = row.get("waves") or []
            row["w17_survived"] = int(max(waves) > 17) if waves else 0
            row["win"] = int(row.get("result") == "victory")
            rows.append(row)
    return rows


def decompose(series_by_state: dict[str, list[int]]) -> dict | None:
    """Unbiased between/within decomposition for a balanced binary design."""
    sizes = {len(v) for v in series_by_state.values()}
    if len(sizes) != 1:
        return None
    k = sizes.pop()
    n_states = len(series_by_state)
    if k < 2 or n_states < 2:
        return None
    means = [sum(v) / k for v in series_by_state.values()]
    grand = sum(means) / n_states
    var_means = sum((m - grand) ** 2 for m in means) / (n_states - 1)
    within = sum(k / (k - 1) * m * (1 - m) for m in means) / n_states
    between = var_means - within / k
    total = max(between, 0.0) + within
    return {
        "I": n_states,
        "K": k,
        "grand_mean": grand,
        "var_of_state_means": var_means,
        "sigma2_within": within,
        "sigma2_between": between,
        "icc": (max(between, 0.0) / total) if total else float("nan"),
        "closure": (total, grand * (1 - grand)),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=".tmp/dose_fixtures", type=Path)
    args = ap.parse_args()

    rows = load_trials(args.dir)
    if not rows:
        raise SystemExit(f"no trials found under {args.dir}")

    invalid = [r for r in rows if not r.get("valid")]
    print(f"{len(rows)} trials, {len(rows) - len(invalid)} valid, {len(invalid)} invalid")

    # Controls only: the enemy_scaling edit persists past wave 17 into waves 18-20,
    # so treatment arms cannot serve as a natural-continuation baseline.
    control = [r for r in rows if r["arm"] == "C" and r.get("valid")]
    print(f"control arm, valid: {len(control)} trials\n")

    # Pool the campaigns that share the same 16-state library.
    pooled = [r for r in control if r["campaign"] in ("round1_trials", "v2_trials")]
    by_state: dict[str, list[int]] = defaultdict(list)
    for r in pooled:
        by_state[r["state"]].append(r["win"])

    print("RAW per-source-state terminal-win series")
    for state in sorted(by_state):
        series = by_state[state]
        print(f"  {state[:50]:<50} {''.join(map(str, series))}  {sum(series)}/{len(series)}")

    wins = sum(sum(v) for v in by_state.values())
    total = sum(len(v) for v in by_state.values())
    natural = NATURAL_WINS / NATURAL_REACHED_W16
    print(f"\n  P(win | landmark)          = {wins}/{total} = {wins / total:.4f}")
    print(f"  P(win | reached w16), full = {NATURAL_WINS}/{NATURAL_REACHED_W16} "
          f"= {natural:.4f}   <-- validity comparison")

    for label, key in (("terminal win", "win"), ("wave-17 survival", "w17_survived")):
        for camp in ("pooled", "v2_trials"):
            src = pooled if camp == "pooled" else [r for r in control if r["campaign"] == camp]
            grouped: dict[str, list[int]] = defaultdict(list)
            for r in src:
                grouped[r["state"]].append(r[key])
            res = decompose(grouped)
            if not res:
                continue
            tot, pq = res["closure"]
            print(f"\n[{label} / {camp}] I={res['I']} K={res['K']} "
                  f"mean={res['grand_mean']:.4f}")
            print(f"  sigma2_between = {res['sigma2_between']:.4f}")
            print(f"  sigma2_within  = {res['sigma2_within']:.4f}")
            print(f"  ICC            = {res['icc']:.3f}")
            print(f"  closure: b+w = {tot:.4f} vs p(1-p) = {pq:.4f}")

    walls = sorted(r["trial_wall_sec"] / 60.0 for r in control if r.get("trial_wall_sec"))
    print(f"\ncontinuation wall-clock (min): n={len(walls)} "
          f"mean={sum(walls) / len(walls):.2f} median={walls[len(walls) // 2]:.2f}")


if __name__ == "__main__":
    main()
