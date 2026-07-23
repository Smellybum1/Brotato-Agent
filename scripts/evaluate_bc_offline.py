"""Thin CLI for WP2 M2 offline BC evaluation (Stage D, architecture §8).

All logic lives in ``trainer/evaluation/bc_offline.py``; this script only parses
arguments and calls :func:`run_offline_eval`. Metrics are recomputed
independently from the frozen dataset and each run's saved checkpoint /
normalization manifest — ``metrics.jsonl`` is never trusted.

Usage:
    .venv/Scripts/python.exe scripts/evaluate_bc_offline.py \
        models/registry/bc_v1_s1_20260724_020529.json --out-tag smoke_demo
    .venv/Scripts/python.exe scripts/evaluate_bc_offline.py \
        bc_v1_s1_full bc_v1_s2_full bc_v1_s3_full --checkpoint best --out-tag bc_v1_seeds

Writes reports/wp2/bc_offline_eval_<tag>.json and .md. Exit 0 on success.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from trainer.evaluation.bc_offline import (  # noqa: E402
    BCOfflineEvalError,
    run_offline_eval,
)


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Offline-evaluate WP2 BC run(s).")
    parser.add_argument(
        "registries",
        nargs="+",
        help="one or more registry manifest paths, or bare run names under models/registry/",
    )
    parser.add_argument(
        "--checkpoint", choices=("best", "last"), default="best",
        help="which checkpoint to evaluate (default: best)",
    )
    parser.add_argument("--device", default="auto", help="torch device (auto|cpu|cuda)")
    parser.add_argument("--out-tag", default="eval", help="output filename tag")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        payload = run_offline_eval(
            args.registries,
            checkpoint=args.checkpoint,
            device=args.device,
            out_tag=args.out_tag,
        )
    except (BCOfflineEvalError, FileNotFoundError, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # pragma: no cover - unexpected
        print(f"unexpected error: {exc}", file=sys.stderr)
        return 2

    for r in payload["runs"]:
        g = r["gates"]
        print(
            f"done: {r['run_name']} checkpoint={r['checkpoint']} "
            f"mean_dir_gate={'PASS' if g['mean_direction_gate'] else 'FAIL'} "
            f"copy_prev_gate={'PASS' if g['copy_previous_gate'] else 'FAIL'} "
            f"overall={'PASS' if g['overall_pass'] else 'FAIL'} "
            f"(model med={g['model_median_deg']:.2f}° mean={g['model_mean_deg']:.2f}° | "
            f"change≥1° model med={g['model_change_median_deg']:.2f}° "
            f"copy med={g['copy_previous_change_median_deg']:.2f}°)"
        )
    print(f"reports: {payload['json_path']} | {payload['md_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
