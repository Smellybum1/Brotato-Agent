"""Thin CLI for the WP2 M2 behavior-cloning training loop (Stage D).

All logic lives in ``trainer/imitation/bc_training.py``; this script only parses
arguments, applies overrides, and calls :func:`run_training`.

Usage:
    .venv/Scripts/python.exe scripts/train_bc.py --config configs/wp2/bc_train_v1.yaml
    .venv/Scripts/python.exe scripts/train_bc.py --smoke        # 2-epoch pipeline check

Exit codes: 0 on success (including a clean early stop), non-zero on failure.
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from pathlib import Path

# Ensure the repo root is importable when run as a script.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from trainer.imitation.bc_training import (  # noqa: E402
    BCTrainingError,
    load_train_config,
    run_training,
)

DEFAULT_CONFIG = REPO_ROOT / "configs" / "wp2" / "bc_train_v1.yaml"


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train the WP2 BC policy (v1).")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="training config YAML")
    parser.add_argument("--seed", type=int, default=None, help="override config seed")
    parser.add_argument("--max-epochs", type=int, default=None, help="override config max_epochs")
    parser.add_argument("--run-name", default=None, help="override the auto run name")
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="pipeline check: small sample subset + 2 epochs",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        config, config_hash = load_train_config(args.config)
        if args.seed is not None:
            config = replace(config, seed=args.seed)
        if args.max_epochs is not None:
            config = replace(config, max_epochs=args.max_epochs)
        summary = run_training(
            config,
            config_hash,
            run_name=args.run_name,
            smoke=args.smoke,
        )
    except (BCTrainingError, FileNotFoundError, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # pragma: no cover - unexpected
        print(f"unexpected error: {exc}", file=sys.stderr)
        return 2

    print(
        f"done: run_name={summary['run_name']} "
        f"epochs={summary['epochs_run']} best_epoch={summary['best_epoch']} "
        f"wall={summary['wall_time_sec']:.1f}s "
        f"registry={summary['registry_path']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
