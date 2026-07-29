"""Fine-tune the production BC checkpoint on the HUMAN keyboard labels.

Warm-start from ``models/bc_v1/bc_v1_s1_full/best.pt`` (43.8k human rows against
the teacher run's 305k means a cold start would overfit), lower LR, SAME loss
(``bc_loss``), early-stop on val loss.

The parent run's normalization stats are REUSED verbatim -- recomputing mean/std
on the human split would shift the input distribution the pretrained weights were
fitted to, and the metric would then confound a fine-tune with a rescale.

Reports direction agreement over the 9 keyboard classes for BOTH the student and
the TEACHER's own action on the same val rows (the baseline that says how much of
the human's behaviour the teacher already reproduces).

Exports nothing, deploys nothing, serves nothing.
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import torch  # noqa: E402

from trainer.data.bc_dataset import NormalizationStats, load_human_bc_dataset  # noqa: E402
from trainer.imitation.bc_training import (  # noqa: E402
    BCTrainer,
    BCTrainConfig,
    EarlyStopper,
    load_checkpoint,
    load_train_config,
    save_checkpoint,
)

DATASET_DIR = ROOT / "datasets" / "human_obs_v1"
SPLIT_CONFIG = ROOT / "configs" / "wp2" / "human_dataset_split_v1.yaml"
INPUT_CONFIG = ROOT / "configs" / "wp2" / "human_bc_input_v1.yaml"
SCHEMA = ROOT / "configs" / "wp2" / "observation_v1.yaml"
BASE_TRAIN_CONFIG = ROOT / "configs" / "wp2" / "bc_train_v1.yaml"
PARENT_DIR = ROOT / "models" / "bc_v1" / "bc_v1_s1_full"

# Encoder global_features indices (48-wide, pre input-mask).
TEACHER_ACTION_IDX = (15, 16)

DIRECTIONS: tuple[tuple[str, float, float], ...] = (
    ("E", 1.0, 0.0),
    ("NE", 0.707, -0.707),
    ("N", 0.0, -1.0),
    ("NW", -0.707, -0.707),
    ("W", -1.0, 0.0),
    ("SW", -0.707, 0.707),
    ("S", 0.0, 1.0),
    ("SE", 0.707, 0.707),
)
CLASS_NAMES = ("ZERO",) + tuple(d[0] for d in DIRECTIONS)


def snap9(vecs: np.ndarray, zero_threshold: float) -> np.ndarray:
    """Nearest of the 9 keyboard classes; index 0 == ZERO (standing still)."""
    mag = np.linalg.norm(vecs, axis=1)
    unit = np.array([[dx, dy] for _, dx, dy in DIRECTIONS], dtype=np.float64)
    unit /= np.linalg.norm(unit, axis=1, keepdims=True)
    dots = vecs @ unit.T
    out = np.argmax(dots, axis=1) + 1
    out[mag <= zero_threshold] = 0
    return out


def load_parent_normalization(feature_names: list[str], parent_dir: Path) -> NormalizationStats:
    """Parent mean/std, SUBSET to the dataset's kept features (order-checked).

    The velocity-masked input config keeps a strict subset of the parent's 40
    features. Reusing the parent stats verbatim on the surviving columns keeps
    each retained feature's normalisation bit-identical to what the pretrained
    weights were fitted to; recomputing on the human split would confound the
    fine-tune with a rescale.
    """
    manifest = json.loads((parent_dir / "normalization_manifest.json").read_text(encoding="utf-8"))
    names = [str(n) for n in manifest["global_feature_names"]]
    want = list(feature_names)
    if names == want:
        keep = list(range(len(names)))
    else:
        pos = {n: i for i, n in enumerate(names)}
        missing = [n for n in want if n not in pos]
        if missing:
            raise SystemExit(f"dataset features absent from parent normalization: {missing}")
        keep = [pos[n] for n in want]
        if keep != sorted(keep):
            raise SystemExit("dataset feature order is not a subsequence of the parent's -- refusing")
        print(f"normalization: parent has {len(names)} features, dataset keeps {len(want)}; "
              f"dropped {[n for n in names if n not in set(want)]}")
    return NormalizationStats(
        feature_names=want,
        mean=np.asarray(manifest["mean"], dtype=np.float32)[keep],
        std=np.asarray(manifest["std"], dtype=np.float32)[keep],
        split_id=str(manifest.get("split_id", "parent")),
        schema_hash=str(manifest.get("schema_hash", "")),
        input_config_hash=str(manifest.get("input_config_hash", "")),
        split_config_hash=str(manifest.get("split_config_hash", "")),
    )


def warm_start(model, ckpt_path: Path, dataset_names: list[str], parent_dir: Path) -> dict:
    """Load parent weights, slicing the trunk's first layer if globals shrank.

    ``BCPolicyV2.export_base_state_dict`` ships only the V1 base, so serving is
    BCPolicyV1 either way; a bc_v2 ``best.pt`` holds a full BCPolicyV2 state
    dict whose keys are ``base.*``, which we strip to load into a BCPolicyV1.

    The trunk input is ``concat(pooled_entity_groups, globals)`` with globals
    LAST, so dropping global feature k removes trunk.0.weight column
    ``trunk_in - global_dim_parent + k``. Every other parameter transfers
    unchanged; the dropped columns' weights are discarded (there is no
    principled way to redistribute them, and zeroing vs deleting is identical
    for a Linear layer whose input is gone).
    """
    payload = torch.load(str(ckpt_path), map_location="cpu", weights_only=False)
    state = dict(payload["model_state_dict"])
    if any(k.startswith("base.") for k in state):
        state = {k[len("base."):]: v for k, v in state.items() if k.startswith("base.")}
        print("warm start: stripped BCPolicyV2 'base.' prefix (serving class is BCPolicyV1)")

    parent_names = [
        str(n) for n in json.loads(
            (parent_dir / "normalization_manifest.json").read_text(encoding="utf-8")
        )["global_feature_names"]
    ]
    w = state["trunk.0.weight"]
    trunk_in = w.shape[1]
    if len(parent_names) != len(dataset_names):
        keep_names = set(dataset_names)
        offset = trunk_in - len(parent_names)
        cols = [offset + i for i, n in enumerate(parent_names) if n in keep_names]
        cols = list(range(offset)) + cols
        dropped = [n for n in parent_names if n not in keep_names]
        state["trunk.0.weight"] = w[:, cols].clone()
        print(f"warm start: trunk.0.weight {tuple(w.shape)} -> "
              f"{tuple(state['trunk.0.weight'].shape)}; dropped global columns for {dropped} "
              f"(entity-pool block of width {offset} untouched)")
    model.load_state_dict(state)
    return payload


def val_globals_columns(split_config_path: Path, cols: tuple[int, int]) -> np.ndarray:
    """Two raw encoder-global columns for the val rows, in split order."""
    import yaml

    cfg = yaml.safe_load(split_config_path.read_text(encoding="utf-8"))
    chunks = []
    for entry in cfg["validation"]:
        with np.load(DATASET_DIR / entry["shard_file"]) as data:
            chunks.append(data["global_features"][:, list(cols)].astype(np.float64))
    return np.concatenate(chunks, axis=0)


def val_teacher_actions(split_config_path: Path) -> np.ndarray:
    """teacher_action_x/y for the val rows (excluded from the student input)."""
    return val_globals_columns(split_config_path, TEACHER_ACTION_IDX)


def agreement_report(name: str, pred: np.ndarray, label_cls: np.ndarray, zero_threshold: float):
    pred_cls = snap9(pred, zero_threshold)
    n = len(label_cls)
    agree = int((pred_cls == label_cls).sum())
    print(f"\n[{name}] direction agreement: {agree}/{n} = {agree / n:.4f} "
          f"(zero_threshold={zero_threshold})")
    print(f"[{name}] predicted-class distribution: "
          f"{ {CLASS_NAMES[c]: int(v) for c, v in sorted(Counter(pred_cls).items())} }")
    print(f"[{name}] per-class (label class -> recall):")
    print(f"    {'class':6} {'label_n':>8} {'agree':>7} {'recall':>8} {'pred_n':>8} {'prec':>8}")
    for c, cname in enumerate(CLASS_NAMES):
        label_n = int((label_cls == c).sum())
        pred_n = int((pred_cls == c).sum())
        hit = int(((label_cls == c) & (pred_cls == c)).sum())
        recall = hit / label_n if label_n else float("nan")
        prec = hit / pred_n if pred_n else float("nan")
        print(f"    {cname:6} {label_n:8d} {hit:7d} {recall:8.4f} {pred_n:8d} {prec:8.4f}")
    return {"agreement": agree / n, "n": n}


def mean_cosine(pred: np.ndarray, target: np.ndarray) -> tuple[float, int]:
    pm = np.linalg.norm(pred, axis=1)
    tm = np.linalg.norm(target, axis=1)
    sel = (pm > 1e-8) & (tm > 1e-8)
    cos = (pred[sel] * target[sel]).sum(axis=1) / (pm[sel] * tm[sel])
    return float(cos.mean()), int(sel.sum())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lr", type=float, default=5.0e-5)
    parser.add_argument("--max-epochs", type=int, default=40)
    parser.add_argument("--batch-size", type=int, default=1024)
    parser.add_argument("--patience", type=int, default=5)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--zero-threshold", type=float, default=0.5)
    parser.add_argument("--out-dir", default=str(ROOT / ".tmp" / "bc_human_ft"))
    parser.add_argument("--input-config", default=str(INPUT_CONFIG),
                        help="student input mask (default: human_bc_input_v1.yaml)")
    parser.add_argument("--zero-entity-channels", default="",
                        help="comma-separated entity feature channels to zero in BOTH "
                             "splits, e.g. '2,3,11,12,13' to ablate the relative-velocity "
                             "leak (ch 2,3 are entity.v MINUS player.v; ch 11,12,13 are "
                             "contact_risk/time_sec/closest, all derived from it)")
    parser.add_argument("--parent-dir", default=str(PARENT_DIR),
                        help="warm-start checkpoint dir (must hold best.pt + "
                             "normalization_manifest.json)")
    args = parser.parse_args(argv)

    input_config = Path(args.input_config)
    parent_dir = Path(args.parent_dir)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    base_config, _ = load_train_config(BASE_TRAIN_CONFIG)
    config = dataclasses.replace(
        base_config,
        seed=args.seed,
        lr=args.lr,
        batch_size=args.batch_size,
        max_epochs=args.max_epochs,
        early_stopping_patience=args.patience,
        device="cpu",
        data_on_device=True,
        dataset_dir=DATASET_DIR,
        split_config=SPLIT_CONFIG,
        input_config=input_config,
        schema=SCHEMA,
        output_root=out_dir,
    )

    dataset = load_human_bc_dataset(DATASET_DIR, SPLIT_CONFIG, input_config, SCHEMA)
    print(f"input config: {input_config.name}")
    print(f"human dataset: train={dataset.train.size} val={dataset.val.size} "
          f"total={dataset.train.size + dataset.val.size} "
          f"global_dim={len(dataset.global_feature_names)}")
    print(f"train runs={len(dataset.train.run_ids)} val runs={len(dataset.val.run_ids)}")

    zero_ch = [int(c) for c in args.zero_entity_channels.split(",") if c.strip()]
    if zero_ch:
        # The encoder writes entity channels 2,3 as (entity.v - player.v) and
        # 11,12,13 as contact_risk / time_to_closest / closest_distance, all
        # computed from that same relative velocity. In a human_movement run
        # player.v IS the label one tick delayed, so these channels re-admit the
        # leak that masking globals 6,7 removed. Zeroing is an ABLATION for
        # measurement, not a schema change: nothing is deployed from this run.
        for split in (dataset.train, dataset.val):
            for name, arr in split.entities.items():
                arr[:, :, zero_ch] = 0.0
        print(f"ABLATION: zeroed entity channels {zero_ch} in train+val "
              f"(groups: {sorted(dataset.train.entities)})")

    parent_norm = load_parent_normalization(dataset.global_feature_names, parent_dir)
    dataset = dataclasses.replace(dataset, normalization=parent_norm)
    print(f"normalization: REUSED from parent {parent_dir.name} "
          f"(split_id={parent_norm.split_id})")

    trainer = BCTrainer(dataset, config, torch.device("cpu"))
    payload = warm_start(trainer.model, parent_dir / "best.pt",
                         dataset.global_feature_names, parent_dir)
    print(f"warm start: {parent_dir / 'best.pt'} (parent epoch {payload.get('epoch')})")
    print(f"lr={config.lr} batch={config.batch_size} max_epochs={config.max_epochs} "
          f"patience={config.early_stopping_patience} device=cpu")

    pre = trainer.evaluate()
    print(f"\nepoch  -1 (parent, no fine-tune): val_loss={pre['val_loss']:.6f} "
          f"val_mean_cosine={pre.get('val_mean_cosine', float('nan')):.4f}")

    stopper = EarlyStopper(patience=config.early_stopping_patience)
    history = []
    best_path = out_dir / "best.pt"
    for epoch in range(config.max_epochs):
        tr = trainer.train_epoch(epoch)
        ev = trainer.evaluate()
        improved = stopper.update(ev["val_loss"], epoch)
        history.append({"epoch": epoch, **{k: v for k, v in tr.items()},
                        "val_loss": ev["val_loss"],
                        "val_mean_cosine": ev.get("val_mean_cosine")})
        print(f"epoch {epoch:3d}  train_loss={tr['train_loss']:.6f}  "
              f"val_loss={ev['val_loss']:.6f}  val_mean_cos={ev.get('val_mean_cosine', float('nan')):.4f}"
              f"  lr={tr['lr']:.2e}{'  *best' if improved else ''}")
        if improved:
            save_checkpoint(best_path, trainer.model, config.as_dict(), epoch, ev)
        trainer.step_scheduler()
        if stopper.should_stop:
            print(f"early stop at epoch {epoch} (patience {config.early_stopping_patience})")
            break

    print(f"\nselected epoch: {stopper.best_epoch}  best val_loss={stopper.best:.6f}")
    load_checkpoint(best_path, trainer.model)

    # --- metrics on val -----------------------------------------------------
    with torch.no_grad():
        pred = trainer._predict(trainer.val_split).cpu().numpy().astype(np.float64)
    label = trainer.val_split.actions.cpu().numpy().astype(np.float64)
    teacher = val_teacher_actions(SPLIT_CONFIG)
    if teacher.shape[0] != label.shape[0]:
        raise SystemExit(f"teacher rows {teacher.shape[0]} != val rows {label.shape[0]}")

    label_cls = snap9(label, zero_threshold=1e-6)  # labels are exact unit/zero vectors
    print(f"\nval rows: {len(label_cls)}")
    print(f"label class distribution: "
          f"{ {CLASS_NAMES[c]: int(v) for c, v in sorted(Counter(label_cls).items())} }")

    # ---------------------------------------------------------------- LEAK --
    # player_vx/vy (encoder globals 6,7) are IN the student input, and during a
    # human_movement run the player's actual velocity IS the human's action one
    # tick later. Reported as a baseline so the student's score can be read
    # against the trivial copy-velocity predictor it can reach without learning
    # anything about the human's policy.
    velocity = val_globals_columns(SPLIT_CONFIG, (6, 7))

    agreement_report("student", pred, label_cls, args.zero_threshold)
    agreement_report("teacher", teacher, label_cls, args.zero_threshold)
    agreement_report("copy-velocity (leak baseline)", velocity, label_cls, args.zero_threshold)

    for thr in (0.25, 0.5, 0.75):
        s = int((snap9(pred, thr) == label_cls).sum())
        t = int((snap9(teacher, thr) == label_cls).sum())
        print(f"sensitivity zero_threshold={thr}: student {s / len(label_cls):.4f}  "
              f"teacher {t / len(label_cls):.4f}")

    sc, sn = mean_cosine(pred, label)
    tc, tn = mean_cosine(teacher, label)
    vc, vn = mean_cosine(velocity, label)
    print(f"\nmean cosine to human label (nonzero pairs only):")
    print(f"  student        {sc:.4f}  over {sn}/{len(label)} rows")
    print(f"  teacher        {tc:.4f}  over {tn}/{len(label)} rows")
    print(f"  copy-velocity  {vc:.4f}  over {vn}/{len(label)} rows")

    (out_dir / "history.json").write_text(json.dumps(history, indent=1), encoding="utf-8")
    print(f"\nartifacts (NOT exported/deployed): {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
