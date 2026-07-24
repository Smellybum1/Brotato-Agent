"""Thin CLI for the WP2 M4 bc_v2 training loop (DAgger round 1).

All logic lives in ``trainer/imitation/bc_v2_training.py``; this script parses
arguments and calls :func:`run_bc_v2_training` for one candidate.

Usage:
    .venv/Scripts/python.exe scripts/train_bc_v2.py --candidate A --run-name bc_v2_a_s1
    .venv/Scripts/python.exe scripts/train_bc_v2.py --candidate B --run-name bc_v2_b_s1
    .venv/Scripts/python.exe scripts/train_bc_v2.py --candidate A --run-name smoke --smoke

Exit codes: 0 on success, non-zero on failure.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from trainer.imitation.bc_v2_training import (  # noqa: E402
    DEFAULT_DAGGER_DIR,
    DEFAULT_LAMBDA_AUX,
    BCV2TrainingError,
    load_bc_v2_config,
    run_bc_v2_training,
)

DEFAULT_CONFIG = REPO_ROOT / "configs" / "wp2" / "bc_train_v1.yaml"


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train a WP2 bc_v2 candidate (A or B).")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="training config YAML (bc_v1)")
    parser.add_argument("--candidate", required=True, choices=("A", "B", "a", "b"))
    parser.add_argument("--run-name", required=True, help="run name (also the registry stem)")
    parser.add_argument("--seed", type=int, default=None, help="override config seed")
    parser.add_argument("--max-epochs", type=int, default=None, help="override config max_epochs")
    parser.add_argument("--dagger-dir", default=str(DEFAULT_DAGGER_DIR), help="dagger dataset dir (single-set path)")
    parser.add_argument(
        "--dagger-dirs",
        default=None,
        help=(
            "comma-separated list of TWO+ corrective dataset dirs; routes through "
            "the multi-corrective loader (each set keeps its own event weights and "
            "carves its own deterministic holdout; --corrective-mass sets the TOTAL "
            "corrective mass split proportional to row counts). Omit for the "
            "single-set path (--dagger-dir)."
        ),
    )
    parser.add_argument("--lambda-aux", type=float, default=DEFAULT_LAMBDA_AUX, help="aux head weight (candidate B)")
    parser.add_argument(
        "--corrective-mass",
        type=float,
        default=None,
        help=(
            "target corrective (dagger) effective-mass FRACTION in [0,1); "
            "converted to the loader's dagger:base ratio m/(1-m). Omit to keep "
            "the bc_v2_a default (0.25)."
        ),
    )
    parser.add_argument(
        "--prev-action-dropout",
        type=float,
        default=None,
        help="override config previous_action_dropout_p (default keeps config's 0.1)",
    )
    parser.add_argument(
        "--lambda-mag",
        type=float,
        default=None,
        help="override config loss.lambda_mag (default keeps config's 0.5)",
    )
    parser.add_argument(
        "--lr",
        type=float,
        default=None,
        help="override config optimizer.lr (default keeps config's 3e-4)",
    )
    parser.add_argument(
        "--early-stopping-patience",
        type=int,
        default=None,
        help="override config early_stopping_patience (default keeps config's 5)",
    )
    parser.add_argument(
        "--init-checkpoint",
        default=None,
        help=(
            "curriculum init (candidate A only): path to a BCPolicyV1-loadable "
            "base .pt whose weights seed the model before fine-tuning. Omit for "
            "the default fresh random init (backward compatible)."
        ),
    )
    parser.add_argument(
        "--init-registry",
        default=None,
        help=(
            "registry name or path whose checkpoints.best supplies the sha256 to "
            "VERIFY --init-checkpoint against (and, if --init-checkpoint is "
            "omitted, the checkpoint path itself). A bare name resolves to "
            "models/registry/<name>.json."
        ),
    )
    parser.add_argument(
        "--output-root",
        default=None,
        help="checkpoint output root (default models/bc_v2). Registry still writes to models/registry.",
    )
    parser.add_argument("--smoke", action="store_true", help="2-epoch pipeline check")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        if args.output_root is not None:
            config, config_hash = load_bc_v2_config(args.config, output_root=args.output_root)
        else:
            config, config_hash = load_bc_v2_config(args.config)
        if args.seed is not None:
            config = replace(config, seed=args.seed)
        if args.max_epochs is not None:
            config = replace(config, max_epochs=args.max_epochs)
        if args.prev_action_dropout is not None:
            config = replace(config, previous_action_dropout_p=args.prev_action_dropout)
        if args.lambda_mag is not None:
            config = replace(config, lambda_mag=args.lambda_mag)
        if args.lr is not None:
            config = replace(config, lr=args.lr)
        if args.early_stopping_patience is not None:
            config = replace(config, early_stopping_patience=args.early_stopping_patience)

        # -- resolve/verify curriculum init checkpoint against a registry -----
        init_checkpoint = args.init_checkpoint
        init_checkpoint_sha256 = None
        if args.init_registry is not None:
            reg_arg = Path(args.init_registry)
            reg_path = reg_arg if reg_arg.suffix == ".json" else (
                REPO_ROOT / "models" / "registry" / f"{args.init_registry}.json"
            )
            if not reg_path.is_file():
                raise BCV2TrainingError(f"init registry not found: {reg_path}")
            reg = json.loads(reg_path.read_text(encoding="utf-8"))
            best = reg["checkpoints"]["best"]
            init_checkpoint_sha256 = best["sha256"]
            if init_checkpoint is None:
                init_checkpoint = best["path"]

        target_mass_ratio = None
        if args.corrective_mass is not None:
            m = args.corrective_mass
            if not (0.0 <= m < 1.0):
                raise BCV2TrainingError(
                    f"--corrective-mass must be in [0, 1), got {m}"
                )
            target_mass_ratio = m / (1.0 - m)

        dagger_dataset_dirs = None
        if args.dagger_dirs is not None:
            dagger_dataset_dirs = [d.strip() for d in args.dagger_dirs.split(",") if d.strip()]
            if not dagger_dataset_dirs:
                raise BCV2TrainingError("--dagger-dirs was empty after parsing")

        summary = run_bc_v2_training(
            config,
            config_hash,
            candidate=args.candidate,
            run_name=args.run_name,
            dagger_dataset_dir=args.dagger_dir,
            dagger_dataset_dirs=dagger_dataset_dirs,
            lambda_aux=args.lambda_aux,
            target_mass_ratio=target_mass_ratio,
            init_checkpoint=init_checkpoint,
            init_checkpoint_sha256=init_checkpoint_sha256,
            smoke=args.smoke,
        )
    except (BCV2TrainingError, FileNotFoundError, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # pragma: no cover - unexpected
        print(f"unexpected error: {exc}", file=sys.stderr)
        return 2

    bv = summary["best_val_metrics"]
    print(
        f"done: run_name={summary['run_name']} candidate={summary['candidate']} "
        f"epochs={summary['epochs_run']} best_epoch={summary['best_epoch']} "
        f"val_med_ang={bv.get('val_median_angular_error_deg', float('nan')):.2f}deg "
        f"wall={summary['wall_time_sec']:.1f}s registry={summary['registry_path']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
