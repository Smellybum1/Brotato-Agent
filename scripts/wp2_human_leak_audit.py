"""Audit every channel of the human_obs_v1 observation for label leakage.

The human label is the keyboard vector; a `human_movement` run's player velocity
is that vector one tick delayed. Masking globals 6,7 (`player_vx`/`player_vy`)
removes the OBVIOUS copy. This script checks whether the SAME quantity survives
elsewhere in the observation, by reconstructing a predictor from candidate
channels and scoring it against the human label with the same 9-way snap.

Reads only; trains nothing, exports nothing.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.wp2_finetune_bc_human import snap9  # noqa: E402

DATASET_DIR = ROOT / "datasets" / "human_obs_v1"
SPLIT = ROOT / "configs" / "wp2" / "human_dataset_split_v1.yaml"
GROUPS = ("enemies", "bosses", "projectiles", "materials", "consumables", "crates", "obstacles")


def main() -> int:
    cfg = yaml.safe_load(SPLIT.read_text(encoding="utf-8"))
    glob, act = [], []
    rel: dict[str, list[np.ndarray]] = {g: [] for g in GROUPS}
    for entry in cfg["validation"]:
        with np.load(DATASET_DIR / entry["shard_file"]) as d:
            glob.append(d["global_features"][:, [6, 7]])
            act.append(d["human_action"])
            for g in GROUPS:
                ent = d[f"entities_{g}"]
                m = d[f"mask_{g}"]
                # channels 2,3 = (entity.v - player.v) / entity_speed_scale
                rv = ent[:, :, 2:4] * m[:, :, None]
                n = m.sum(1)[:, None]
                rel[g].append(np.where(n > 0, rv.sum(1) / np.maximum(n, 1.0), 0.0))
    G = np.concatenate(glob).astype(np.float64)
    A = np.concatenate(act).astype(np.float64)
    lab = snap9(A, 1e-6)
    n = len(lab)
    print(f"val rows: {n}\n")
    print(f"{'channel':40s} {'agree':>8} {'cos':>8} {'rows_used':>10}")

    def rep(name: str, v: np.ndarray) -> None:
        a = int((snap9(v, 0.5) == lab).sum())
        pm = np.linalg.norm(v, axis=1)
        tm = np.linalg.norm(A, axis=1)
        s = (pm > 1e-8) & (tm > 1e-8)
        c = float(((v[s] * A[s]).sum(1) / (pm[s] * tm[s])).mean()) if s.any() else float("nan")
        print(f"{name:40s} {a / n:8.4f} {c:8.4f} {int(s.sum()):10d}")

    rep("globals 6,7 player_vx/vy (MASKED OUT)", G)
    for g in GROUPS:
        rv = np.concatenate(rel[g])
        rep(f"-mean rel_v, {g} (entity ch 2,3)", -rv)
    allrv = -np.mean([np.concatenate(rel[g]) for g in ("materials", "obstacles", "crates")], axis=0)
    rep("-mean rel_v, static groups pooled", allrv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
