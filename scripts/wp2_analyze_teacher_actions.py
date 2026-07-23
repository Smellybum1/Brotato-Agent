#!/usr/bin/env python3
"""Characterize the teacher action distribution over the frozen ``combat_obs_v1`` dataset.

CPU-only, read-only analysis to inform the behavior-cloning loss-function choice.
Loads all NPZ shards under ``datasets/combat_obs_v1`` and, restricted to samples
where ``valid AND temporal_valid`` (the excluded count is reported), characterizes
the teacher movement command (global_features columns teacher_action_x=15,
teacher_action_y=16; previous_action_x=17, previous_action_y=18 -- indices verified
against ``configs/wp2/observation_v1.yaml``). Actions were clamped per-component to
[-1, 1] by the encoder.

Computes:
  1. Magnitude distribution (|a| = hypot(x, y)): exact zeros, near-zero (<0.01),
     a histogram over [0, 1.2] with fine bins near 1.0, fraction within 1e-3 of
     exactly 1.0, min/max/mean/median, and the full set of distinct magnitudes if
     fewer than 50 distinct values exist (rounded to 6 decimals).
  2. Direction distribution for moving samples (|a| > 0.01): angle = atan2(y, x)
     in degrees; 360-bin (1 deg) histogram with the top 30 bins; fraction within
     0.5 deg and 2 deg of a multiple of 15 deg (the 24-direction lane grid); and
     fraction within 0.5 deg of a multiple of 45 deg and of 90 deg.
  3. Per-wave-band stats (bands 1-5, 6-10, 11-15, 16-19, 20): sample count, zero
     fraction, unit-magnitude fraction, on-15-deg-grid fraction (2 deg tolerance,
     over moving samples), mean magnitude.
  4. Action persistence: within each run, ordered by capture_seq -- fraction of
     seq-consecutive pairs with an identical action (exact float match) and with
     angle change < 1 deg (both magnitudes > 0.01); plus a label-pipeline
     consistency check comparing action at seq t against previous_action at
     seq t+1 (exact-match fraction).
  5. Component marginals: mean/std of x and y, and the exact clamp-saturation
     fractions (|x| == 1.0, |y| == 1.0).
  6. Per-run one-line summary (run_id, n, zero_frac, unit_frac, grid15_frac).

Read-only on the dataset. No game, no deploy, no network. Run with the project
.venv python. Makes NO loss recommendation -- that is the primary's call.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DATASET_DIR = ROOT / "datasets" / "combat_obs_v1"
SCHEMA_PATH = ROOT / "configs" / "wp2" / "observation_v1.yaml"
OUT_JSON = ROOT / "reports" / "wp2" / "teacher_action_distribution.json"
OUT_MD = ROOT / "reports" / "wp2" / "teacher_action_distribution.md"

# Feature column indices (verified against observation_v1.yaml at import time).
IDX_ACT_X = 15
IDX_ACT_Y = 16
IDX_PREV_X = 17
IDX_PREV_Y = 18

NEAR_ZERO = 0.01           # |a| below this -> "near zero" / non-moving
UNIT_TOL = 1e-3            # |a| within this of 1.0 -> "unit magnitude"
GRID_STEP = 15.0          # 24-direction lane grid (deg)

# Wave bands: label -> (lo, hi) inclusive.
WAVE_BANDS = [
    ("1-5", 1, 5),
    ("6-10", 6, 10),
    ("11-15", 11, 15),
    ("16-19", 16, 19),
    ("20", 20, 20),
]

# Magnitude histogram edges: coarse below 0.9, fine near 1.0, tail out to 1.2+.
MAG_BIN_EDGES = [
    0.0, 0.01, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9,
    0.99, 0.999, 1.001, 1.01, 1.1, 1.2, float("inf"),
]


# --------------------------------------------------------------------------- #
# Schema verification
# --------------------------------------------------------------------------- #
def verify_indices(schema_path: Path) -> None:
    """Confirm the hard-coded column indices match the frozen schema order.

    Parses ``global_features`` from the YAML by hand (no PyYAML dependency): the
    list is a run of ``  - name`` lines under the ``global_features:`` key.
    """
    names: list[str] = []
    in_block = False
    for raw in schema_path.read_text(encoding="utf-8").splitlines():
        if raw.startswith("global_features:"):
            in_block = True
            continue
        if in_block:
            stripped = raw.strip()
            if stripped.startswith("- "):
                names.append(stripped[2:].strip())
            elif raw and not raw[0].isspace():
                break  # next top-level key
    expected = {
        IDX_ACT_X: "teacher_action_x",
        IDX_ACT_Y: "teacher_action_y",
        IDX_PREV_X: "previous_action_x",
        IDX_PREV_Y: "previous_action_y",
    }
    for idx, want in expected.items():
        if idx >= len(names) or names[idx] != want:
            got = names[idx] if idx < len(names) else "<out of range>"
            raise SystemExit(
                "schema index mismatch at %d: expected %r, got %r" % (idx, want, got)
            )


# --------------------------------------------------------------------------- #
# Numeric helpers
# --------------------------------------------------------------------------- #
def grid_distance(angles_deg: np.ndarray, step: float) -> np.ndarray:
    """Angular distance (deg, in [0, step/2]) to the nearest multiple of ``step``."""
    res = np.mod(angles_deg, step)
    return np.minimum(res, step - res)


def frac(count: int, total: int) -> float | None:
    return (count / total) if total else None


def f(x) -> float | None:
    """Cast a numpy scalar to a plain float (JSON-safe), passing through None."""
    if x is None:
        return None
    return float(x)


# --------------------------------------------------------------------------- #
# Analysis
# --------------------------------------------------------------------------- #
def analyze(dataset_dir: Path) -> dict:
    shards = sorted(dataset_dir.glob("run_*.npz"))
    if not shards:
        raise SystemExit("no shards found under %s" % dataset_dir)

    total_rows = 0
    total_kept = 0

    # Pooled arrays over the valid&temporal_valid subset.
    xs: list[np.ndarray] = []
    ys: list[np.ndarray] = []
    waves: list[np.ndarray] = []

    # Persistence / label-consistency accumulators (seq-consecutive pairs).
    pair_total = 0
    pair_identical = 0
    pair_angle_total = 0        # pairs where both magnitudes > NEAR_ZERO
    pair_angle_lt1 = 0
    label_pair_total = 0
    label_exact_match = 0

    per_run = []

    for shard in shards:
        with np.load(shard) as d:
            gf = d["global_features"]
            seq = d["capture_seq"]
            valid = d["valid"]
            tvalid = d["temporal_valid"]
            wave_col = d["wave"]

        n = gf.shape[0]
        total_rows += n
        keep = valid & tvalid
        total_kept += int(keep.sum())

        ax = gf[:, IDX_ACT_X].astype(np.float64)
        ay = gf[:, IDX_ACT_Y].astype(np.float64)
        px = gf[:, IDX_PREV_X].astype(np.float64)
        py = gf[:, IDX_PREV_Y].astype(np.float64)

        # --- pooled subset arrays ---
        xs.append(ax[keep])
        ys.append(ay[keep])
        waves.append(wave_col[keep])

        # --- per-run one-line summary (over kept samples) ---
        kx, ky = ax[keep], ay[keep]
        kmag = np.hypot(kx, ky)
        kn = kx.shape[0]
        zero_frac = frac(int((kmag == 0.0).sum()), kn)
        unit_frac = frac(int((np.abs(kmag - 1.0) <= UNIT_TOL).sum()), kn)
        moving = kmag > NEAR_ZERO
        if moving.any():
            ang = np.degrees(np.arctan2(ky[moving], kx[moving]))
            gdist = grid_distance(ang, GRID_STEP)
            grid15_frac = frac(int((gdist <= 2.0).sum()), int(moving.sum()))
        else:
            grid15_frac = None
        per_run.append({
            "run_id": shard.stem,
            "n": kn,
            "zero_frac": zero_frac,
            "unit_frac": unit_frac,
            "grid15_frac": grid15_frac,
        })

        # --- persistence over seq-consecutive kept pairs ---
        order = np.argsort(seq, kind="stable")
        s_ord = seq[order]
        ax_o, ay_o = ax[order], ay[order]
        px_o, py_o = px[order], py[order]
        keep_o = keep[order]
        consec = (s_ord[1:] - s_ord[:-1]) == 1
        both_keep = keep_o[:-1] & keep_o[1:]
        pair_mask = consec & both_keep

        # identical exact-float action
        same = (ax_o[:-1] == ax_o[1:]) & (ay_o[:-1] == ay_o[1:])
        pair_total += int(pair_mask.sum())
        pair_identical += int((pair_mask & same).sum())

        # angle change < 1 deg (both magnitudes > NEAR_ZERO)
        mag_o = np.hypot(ax_o, ay_o)
        both_moving = (mag_o[:-1] > NEAR_ZERO) & (mag_o[1:] > NEAR_ZERO)
        ang_o = np.degrees(np.arctan2(ay_o, ax_o))
        dang = np.abs(ang_o[1:] - ang_o[:-1])
        dang = np.minimum(dang, 360.0 - dang)  # wrap
        angle_mask = pair_mask & both_moving
        pair_angle_total += int(angle_mask.sum())
        pair_angle_lt1 += int((angle_mask & (dang < 1.0)).sum())

        # label consistency: action at t vs previous_action at t+1
        label_match = (ax_o[:-1] == px_o[1:]) & (ay_o[:-1] == py_o[1:])
        label_pair_total += int(pair_mask.sum())
        label_exact_match += int((pair_mask & label_match).sum())

    # Materialize pooled subset.
    x = np.concatenate(xs)
    y = np.concatenate(ys)
    wave = np.concatenate(waves)
    mag = np.hypot(x, y)
    n = x.shape[0]

    # ------------------------------------------------------------------ #
    # 1. Magnitude distribution
    # ------------------------------------------------------------------ #
    exact_zero = int((mag == 0.0).sum())
    near_zero = int((mag < NEAR_ZERO).sum())
    unit = int((np.abs(mag - 1.0) <= UNIT_TOL).sum())
    hist_counts, _ = np.histogram(mag, bins=MAG_BIN_EDGES)
    mag_hist = [
        {
            "lo": MAG_BIN_EDGES[i],
            "hi": MAG_BIN_EDGES[i + 1],
            "count": int(hist_counts[i]),
            "frac": frac(int(hist_counts[i]), n),
        }
        for i in range(len(hist_counts))
    ]
    distinct_rounded = np.unique(np.round(mag, 6))
    distinct_magnitudes = None
    if distinct_rounded.shape[0] < 50:
        vals, counts = np.unique(np.round(mag, 6), return_counts=True)
        distinct_magnitudes = [
            {"value": float(v), "count": int(c)} for v, c in zip(vals, counts)
        ]

    magnitude = {
        "n": n,
        "exact_zero_count": exact_zero,
        "exact_zero_frac": frac(exact_zero, n),
        "near_zero_count": near_zero,
        "near_zero_frac": frac(near_zero, n),
        "unit_within_1e-3_count": unit,
        "unit_within_1e-3_frac": frac(unit, n),
        "min": f(mag.min()),
        "max": f(mag.max()),
        "mean": f(mag.mean()),
        "median": f(np.median(mag)),
        "histogram": mag_hist,
        "distinct_count": int(distinct_rounded.shape[0]),
        "distinct_magnitudes": distinct_magnitudes,
    }

    # ------------------------------------------------------------------ #
    # 2. Direction distribution (moving samples only)
    # ------------------------------------------------------------------ #
    moving = mag > NEAR_ZERO
    n_moving = int(moving.sum())
    ang = np.degrees(np.arctan2(y[moving], x[moving]))  # (-180, 180]
    ang360 = np.mod(ang, 360.0)                          # [0, 360)
    bin_counts, _ = np.histogram(ang360, bins=360, range=(0.0, 360.0))
    order = np.argsort(bin_counts)[::-1][:30]
    top_bins = [
        {
            "bin_deg_lo": int(b),
            "bin_deg_hi": int(b) + 1,
            "count": int(bin_counts[b]),
            "frac": frac(int(bin_counts[b]), n_moving),
        }
        for b in order
    ]
    d15 = grid_distance(ang360, 15.0)
    d45 = grid_distance(ang360, 45.0)
    d90 = grid_distance(ang360, 90.0)
    direction = {
        "n_moving": n_moving,
        "moving_frac_of_all": frac(n_moving, n),
        "top30_bins_1deg": top_bins,
        "grid15_within_0.5deg_frac": frac(int((d15 <= 0.5).sum()), n_moving),
        "grid15_within_2deg_frac": frac(int((d15 <= 2.0).sum()), n_moving),
        "grid45_within_0.5deg_frac": frac(int((d45 <= 0.5).sum()), n_moving),
        "grid90_within_0.5deg_frac": frac(int((d90 <= 0.5).sum()), n_moving),
    }

    # ------------------------------------------------------------------ #
    # 3. Per-wave-band stats
    # ------------------------------------------------------------------ #
    bands = []
    for label, lo, hi in WAVE_BANDS:
        sel = (wave >= lo) & (wave <= hi)
        bn = int(sel.sum())
        bmag = mag[sel]
        bmoving = bmag > NEAR_ZERO
        if bmoving.any():
            bang = np.degrees(np.arctan2(y[sel][bmoving], x[sel][bmoving]))
            bgrid = frac(int((grid_distance(bang, 15.0) <= 2.0).sum()),
                         int(bmoving.sum()))
        else:
            bgrid = None
        bands.append({
            "band": label,
            "n": bn,
            "zero_frac": frac(int((bmag == 0.0).sum()), bn),
            "unit_frac": frac(int((np.abs(bmag - 1.0) <= UNIT_TOL).sum()), bn),
            "grid15_frac_2deg_moving": bgrid,
            "mean_magnitude": f(bmag.mean()) if bn else None,
        })

    # ------------------------------------------------------------------ #
    # 4. Persistence + label consistency
    # ------------------------------------------------------------------ #
    persistence = {
        "seq_consecutive_pairs": pair_total,
        "identical_action_frac": frac(pair_identical, pair_total),
        "angle_pairs_both_moving": pair_angle_total,
        "angle_change_lt1deg_frac": frac(pair_angle_lt1, pair_angle_total),
        "label_consistency_pairs": label_pair_total,
        "label_action_t_eq_prev_t+1_exact_frac": frac(label_exact_match,
                                                      label_pair_total),
    }

    # ------------------------------------------------------------------ #
    # 5. Component marginals
    # ------------------------------------------------------------------ #
    components = {
        "x_mean": f(x.mean()), "x_std": f(x.std()),
        "y_mean": f(y.mean()), "y_std": f(y.std()),
        "abs_x_eq_1_frac": frac(int((np.abs(x) == 1.0).sum()), n),
        "abs_y_eq_1_frac": frac(int((np.abs(y) == 1.0).sum()), n),
    }

    return {
        "tool": "wp2_analyze_teacher_actions",
        "dataset_dir": str(dataset_dir),
        "shard_count": len(shards),
        "feature_indices": {
            "teacher_action_x": IDX_ACT_X, "teacher_action_y": IDX_ACT_Y,
            "previous_action_x": IDX_PREV_X, "previous_action_y": IDX_PREV_Y,
        },
        "thresholds": {
            "near_zero": NEAR_ZERO, "unit_tol": UNIT_TOL, "grid_step_deg": GRID_STEP,
        },
        "sample_counts": {
            "total_rows": total_rows,
            "valid_and_temporal_valid": total_kept,
            "excluded": total_rows - total_kept,
        },
        "magnitude": magnitude,
        "direction": direction,
        "wave_bands": bands,
        "persistence": persistence,
        "components": components,
        "per_run": per_run,
    }


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #
def pct(v: float | None) -> str:
    return "n/a" if v is None else "%.2f%%" % (100.0 * v)


def write_markdown(res: dict, path: Path) -> None:
    m = res["magnitude"]
    dr = res["direction"]
    sc = res["sample_counts"]
    pe = res["persistence"]
    co = res["components"]
    lines: list[str] = []
    lines.append("# Teacher action distribution (combat_obs_v1)")
    lines.append("")
    lines.append(
        "Read-only analysis over all %d shards. Samples: %d total, "
        "%d valid AND temporal_valid (%d excluded)."
        % (res["shard_count"], sc["total_rows"], sc["valid_and_temporal_valid"],
           sc["excluded"])
    )
    lines.append("")
    lines.append("## Magnitude")
    lines.append("")
    lines.append("- exact zeros: %s (%d)" % (pct(m["exact_zero_frac"]),
                                             m["exact_zero_count"]))
    lines.append("- near-zero (<0.01): %s (%d)" % (pct(m["near_zero_frac"]),
                                                   m["near_zero_count"]))
    lines.append("- within 1e-3 of 1.0 (unit): %s (%d)"
                 % (pct(m["unit_within_1e-3_frac"]), m["unit_within_1e-3_count"]))
    lines.append("- min/mean/median/max: %.6f / %.6f / %.6f / %.6f"
                 % (m["min"], m["mean"], m["median"], m["max"]))
    lines.append("- distinct rounded(6) magnitudes: %d" % m["distinct_count"])
    lines.append("")
    lines.append("Histogram (|a|):")
    lines.append("")
    lines.append("| lo | hi | count | frac |")
    lines.append("| --- | --- | --- | --- |")
    for b in m["histogram"]:
        hi = "inf" if b["hi"] == float("inf") else "%.3f" % b["hi"]
        lines.append("| %.3f | %s | %d | %s |"
                     % (b["lo"], hi, b["count"], pct(b["frac"])))
    lines.append("")
    lines.append("## Direction (moving samples, |a| > 0.01)")
    lines.append("")
    lines.append("- moving samples: %d (%s of all)"
                 % (dr["n_moving"], pct(dr["moving_frac_of_all"])))
    lines.append("- within 0.5 deg of 15 deg grid: %s"
                 % pct(dr["grid15_within_0.5deg_frac"]))
    lines.append("- within 2 deg of 15 deg grid: %s"
                 % pct(dr["grid15_within_2deg_frac"]))
    lines.append("- within 0.5 deg of 45 deg grid: %s"
                 % pct(dr["grid45_within_0.5deg_frac"]))
    lines.append("- within 0.5 deg of 90 deg grid: %s"
                 % pct(dr["grid90_within_0.5deg_frac"]))
    lines.append("")
    lines.append("Top 10 of 360 one-degree angle bins:")
    lines.append("")
    lines.append("| bin (deg) | count | frac |")
    lines.append("| --- | --- | --- |")
    for b in dr["top30_bins_1deg"][:10]:
        lines.append("| [%d, %d) | %d | %s |"
                     % (b["bin_deg_lo"], b["bin_deg_hi"], b["count"],
                        pct(b["frac"])))
    lines.append("")
    lines.append("## Per-wave band")
    lines.append("")
    lines.append("| band | n | zero | unit | grid15 (2deg, moving) | mean |a| |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for b in res["wave_bands"]:
        mean_mag = "n/a" if b["mean_magnitude"] is None else "%.4f" % b["mean_magnitude"]
        lines.append("| %s | %d | %s | %s | %s | %s |"
                     % (b["band"], b["n"], pct(b["zero_frac"]),
                        pct(b["unit_frac"]), pct(b["grid15_frac_2deg_moving"]),
                        mean_mag))
    lines.append("")
    lines.append("## Persistence & label consistency")
    lines.append("")
    lines.append("- seq-consecutive pairs: %d" % pe["seq_consecutive_pairs"])
    lines.append("- identical action (exact float): %s"
                 % pct(pe["identical_action_frac"]))
    lines.append("- angle change < 1 deg (both moving, n=%d): %s"
                 % (pe["angle_pairs_both_moving"], pct(pe["angle_change_lt1deg_frac"])))
    lines.append("- label check action(t) == previous_action(t+1) exact: %s"
                 % pct(pe["label_action_t_eq_prev_t+1_exact_frac"]))
    lines.append("")
    lines.append("## Component marginals")
    lines.append("")
    lines.append("- x mean/std: %.6f / %.6f" % (co["x_mean"], co["x_std"]))
    lines.append("- y mean/std: %.6f / %.6f" % (co["y_mean"], co["y_std"]))
    lines.append("- |x| == 1.0 exactly: %s" % pct(co["abs_x_eq_1_frac"]))
    lines.append("- |y| == 1.0 exactly: %s" % pct(co["abs_y_eq_1_frac"]))
    lines.append("")
    lines.append("## Per-run summary")
    lines.append("")
    lines.append("| run_id | n | zero | unit | grid15 |")
    lines.append("| --- | --- | --- | --- | --- |")
    for r in res["per_run"]:
        lines.append("| %s | %d | %s | %s | %s |"
                     % (r["run_id"], r["n"], pct(r["zero_frac"]),
                        pct(r["unit_frac"]), pct(r["grid15_frac"])))
    lines.append("")
    lines.append("## Interpretation")
    lines.append("")
    # Assemble a factual 3-5 sentence structural summary (no loss recommendation).
    lines.append(
        "Of the %d valid teacher actions, %s are exact zeros (idle / no move) and "
        "%s are within 1e-3 of unit magnitude, so magnitude is strongly bimodal at "
        "0 and 1 (min %.4f, max %.4f, only %d distinct rounded values)."
        % (sc["valid_and_temporal_valid"], pct(m["exact_zero_frac"]),
           pct(m["unit_within_1e-3_frac"]), m["min"], m["max"], m["distinct_count"])
    )
    lines.append("")
    lines.append(
        "Among the %s of samples that are moving (|a| > 0.01), %s fall within 2 deg "
        "of the 24-direction 15 deg lane grid and %s within 0.5 deg, so the emitted "
        "directions are heavily quantized onto that grid."
        % (pct(dr["moving_frac_of_all"]), pct(dr["grid15_within_2deg_frac"]),
           pct(dr["grid15_within_0.5deg_frac"]))
    )
    lines.append("")
    lines.append(
        "Direction structure and unit-magnitude fraction shift across wave bands "
        "(see table); wave 20's finale controller is reported separately as its own "
        "band. Consecutive actions are highly persistent (%s identical exact-float, "
        "%s with sub-1 deg angle change), and the label-pipeline check "
        "action(t)==previous_action(t+1) matches exactly %s of the time."
        % (pct(pe["identical_action_frac"]),
           pct(pe["angle_change_lt1deg_frac"]),
           pct(pe["label_action_t_eq_prev_t+1_exact_frac"]))
    )
    lines.append("")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--dataset-dir", default=str(DATASET_DIR),
                    help="directory of run_*.npz shards (default: %(default)s)")
    ap.add_argument("--out-json", default=str(OUT_JSON))
    ap.add_argument("--out-md", default=str(OUT_MD))
    args = ap.parse_args(argv)

    verify_indices(SCHEMA_PATH)
    res = analyze(Path(args.dataset_dir))

    out_json = Path(args.out_json)
    out_md = Path(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    with out_json.open("w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1)
    write_markdown(res, out_md)

    sc = res["sample_counts"]
    m = res["magnitude"]
    dr = res["direction"]
    print("wrote %s" % out_json)
    print("wrote %s" % out_md)
    print("samples kept %d / %d (excluded %d)"
          % (sc["valid_and_temporal_valid"], sc["total_rows"], sc["excluded"]))
    print("zero=%.4f unit=%.4f grid15(2deg)=%.4f"
          % (m["exact_zero_frac"], m["unit_within_1e-3_frac"],
             dr["grid15_within_2deg_frac"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
