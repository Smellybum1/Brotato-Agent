"""Full-sweep label-leak audit for a human-labelled BC observation.

The narrow audit (``wp2_human_leak_audit.py``) checked the channels we already
suspected. This one sweeps EVERY channel, and adds the test a trivial-copy
cosine cannot do: a held-out LINEAR PROBE.

Three questions, in increasing strength:

  (1) TRIVIAL COPY -- for each 2-channel pair that can express a direction,
      what is cos(pair, human_action) and its 9-way agreement? No fitting; this
      is the statistic that read 0.9857 for the static-group pooled relative
      velocity under the old encoding.

  (2) LABEL PROBE -- ridge regression from a channel SUBSET onto the 2-D human
      action, FIT ON TRAIN, scored on val. A trivial copy cannot see a leak that
      is spread across several scalars, or one that lives in the row ORDER; a
      probe can. This is what makes a claim about channels 11,12,13 (scalars)
      falsifiable rather than asserted.

  (3) RECONSTRUCTION PROBE -- ridge from the STUDENT INPUT onto encoder globals
      6,7 (``player_vx``/``player_vy``) themselves, fit on train, R^2 on val.
      This is the direct question: after the exclusions and the encoder change,
      is the player's velocity still recoverable from what the student sees? If
      R^2 collapses, the leak is closed at the source and every downstream
      channel is closed with it.

Reads only; trains no policy, exports nothing, deploys nothing.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.wp2_finetune_bc_human import snap9  # noqa: E402

GROUPS = ("enemies", "bosses", "projectiles", "materials", "consumables", "crates", "obstacles")
STATIC_GROUPS = ("materials", "obstacles", "crates")
ENTITY_CHANNEL_NAMES = (
    "rel_x", "rel_y", "vx", "vy", "radius", "distance", "bearing_sin", "bearing_cos",
    "health_ratio", "speed", "threat_code", "contact_risk", "time_to_closest",
    "closest_distance", "type_hash",
)
PLAYER_V_IDX = (6, 7)

# Global feature pairs that can express a direction, by encoder index.
GLOBAL_PAIRS = {
    "globals 4,5 player_x/y": (4, 5),
    "globals 6,7 player_vx/vy": (6, 7),
    "globals 15,16 teacher_action": (15, 16),
    "globals 17,18 previous_action": (17, 18),
    "globals 19,20 wall_left/right": (19, 20),
    "globals 21,22 wall_top/bottom": (21, 22),
    "globals 38,39 finale_commit_x/y": (38, 39),
}
# Entity channel pairs that can express a direction.
ENTITY_PAIRS = {"ch 0,1 rel_pos": (0, 1), "ch 2,3 velocity": (2, 3), "ch 6,7 bearing": (6, 7)}


def load_split(dataset_dir: Path, split_path: Path, key: str):
    cfg = yaml.safe_load(split_path.read_text(encoding="utf-8"))
    glob, act, ent, msk = [], [], {g: [] for g in GROUPS}, {g: [] for g in GROUPS}
    for entry in cfg[key]:
        with np.load(dataset_dir / entry["shard_file"]) as d:
            glob.append(d["global_features"].astype(np.float64))
            act.append(d["human_action"].astype(np.float64))
            for g in GROUPS:
                ent[g].append(d[f"entities_{g}"].astype(np.float32))
                msk[g].append(d[f"mask_{g}"].astype(np.float32))
    return (
        np.concatenate(glob),
        np.concatenate(act),
        {g: np.concatenate(v) for g, v in ent.items()},
        {g: np.concatenate(v) for g, v in msk.items()},
    )


def pooled(ent: np.ndarray, msk: np.ndarray, channels: list[int]) -> np.ndarray:
    """Mask-mean pool the given channels over a group's slots -> [N, len(ch)]."""
    sub = ent[:, :, channels] * msk[:, :, None]
    n = msk.sum(1)[:, None]
    return np.where(n > 0, sub.sum(1) / np.maximum(n, 1.0), 0.0).astype(np.float64)


def ridge_fit(X: np.ndarray, Y: np.ndarray, lam: float = 1.0) -> tuple[np.ndarray, np.ndarray]:
    mu, sd = X.mean(0), np.maximum(X.std(0), 1e-8)
    Xs = np.hstack([(X - mu) / sd, np.ones((len(X), 1))])
    d = Xs.shape[1]
    reg = lam * np.eye(d)
    reg[-1, -1] = 0.0
    W = np.linalg.solve(Xs.T @ Xs + reg, Xs.T @ Y)
    return W, np.vstack([mu, sd])


def ridge_apply(X: np.ndarray, W: np.ndarray, ms: np.ndarray) -> np.ndarray:
    Xs = np.hstack([(X - ms[0]) / ms[1], np.ones((len(X), 1))])
    return Xs @ W


def report_direction(name: str, v: np.ndarray, A: np.ndarray, lab: np.ndarray, thr: float = 0.5):
    n = len(lab)
    agree = int((snap9(v, thr) == lab).sum())
    pm, tm = np.linalg.norm(v, axis=1), np.linalg.norm(A, axis=1)
    s = (pm > 1e-8) & (tm > 1e-8)
    c = float(((v[s] * A[s]).sum(1) / (pm[s] * tm[s])).mean()) if s.any() else float("nan")
    print(f"  {name:52s} {agree / n:8.4f} {c:8.4f} {int(s.sum()):9d}")
    return c


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dataset-dir", default=str(ROOT / "datasets" / "human_obs_v1"))
    p.add_argument("--split", default=str(ROOT / "configs" / "wp2" / "human_dataset_split_v1.yaml"))
    p.add_argument("--label", default="OLD (relative entity velocity)")
    p.add_argument("--zero-entity-channels", default="",
                   help="channels ablated by the matching training condition; "
                        "excluded from every probe feature set")
    p.add_argument("--input-config",
                   default=str(ROOT / "configs" / "wp2" / "human_bc_input_v2_novel.yaml"))
    p.add_argument("--ridge", type=float, default=10.0)
    args = p.parse_args(argv)

    ddir, split = Path(args.dataset_dir), Path(args.split)
    zero_ch = {int(c) for c in args.zero_entity_channels.split(",") if c.strip()}
    schema = yaml.safe_load((ROOT / "configs" / "wp2" / "observation_v1.yaml").read_text(encoding="utf-8"))
    gnames = list(schema["global_features"])
    excl = set(yaml.safe_load(Path(args.input_config).read_text(encoding="utf-8"))
               ["excluded_global_features"])
    kept_g = [i for i, n in enumerate(gnames) if n not in excl]

    print("=" * 96)
    print(f"CONDITION: {args.label}")
    print(f"  dataset      {ddir}")
    print(f"  split        {split.name}")
    print(f"  ablated ch   {sorted(zero_ch) if zero_ch else 'none'}")
    print(f"  student globals kept: {len(kept_g)}/48 (excluded {sorted(excl)})")
    print("=" * 96)

    Gtr, Atr, Etr, Mtr = load_split(ddir, split, "train")
    Gva, Ava, Eva, Mva = load_split(ddir, split, "validation")
    lab = snap9(Ava, 1e-6)
    print(f"train rows {len(Atr)}   val rows {len(Ava)}\n")

    # ---------------------------------------------------------------- (1) ----
    print("(1) TRIVIAL COPY -- every direction-capable channel pair, both signs")
    print(f"  {'channel':52s} {'agree':>8} {'cos':>8} {'rows_used':>9}")
    worst: list[tuple[float, str]] = []
    for name, (i, j) in GLOBAL_PAIRS.items():
        for sign, tag in ((1.0, "+"), (-1.0, "-")):
            c = report_direction(f"{tag}{name}", sign * Gva[:, [i, j]], Ava, lab)
            worst.append((abs(c), f"{tag}{name}"))
    for g in GROUPS:
        for pname, (i, j) in ENTITY_PAIRS.items():
            if i in zero_ch or j in zero_ch:
                continue
            v = pooled(Eva[g], Mva[g], [i, j])
            for sign, tag in ((1.0, "+"), (-1.0, "-")):
                c = report_direction(f"{tag}{g}.{pname}", sign * v, Ava, lab)
                worst.append((abs(c), f"{tag}{g}.{pname}"))
    if 2 not in zero_ch:
        pool = np.mean([pooled(Eva[g], Mva[g], [2, 3]) for g in STATIC_GROUPS], axis=0)
        for sign, tag in ((1.0, "+"), (-1.0, "-")):
            c = report_direction(f"{tag}STATIC GROUPS POOLED ch2,3", sign * pool, Ava, lab)
            worst.append((abs(c), f"{tag}static pooled ch2,3"))
    worst.sort(reverse=True)
    print(f"\n  worst |cos| over all trivial copies (excluding globals 6,7 which are "
          f"NOT in the student input):")
    for c, n in [w for w in worst if "6,7" not in w[1]][:5]:
        print(f"    {n:52s} |cos|={c:.4f}")

    # ---------------------------------------------------------------- (2) ----
    print("\n(2) LABEL PROBE -- ridge fit on TRAIN, scored on VAL")
    print(f"  {'feature set':52s} {'agree':>8} {'cos':>8} {'dim':>9}")

    def probe(name: str, ftr, fva):
        W, ms = ridge_fit(ftr, Atr, args.ridge)
        pred = ridge_apply(fva, W, ms)
        report_direction(name, pred, Ava, lab)

    ent_ch_all = [c for c in range(15) if c not in zero_ch]
    sets: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    if 2 not in zero_ch:
        sets["pooled ch2,3 all groups"] = (
            np.hstack([pooled(Etr[g], Mtr[g], [2, 3]) for g in GROUPS]),
            np.hstack([pooled(Eva[g], Mva[g], [2, 3]) for g in GROUPS]))
        sets["pooled ch2,3 STATIC groups"] = (
            np.hstack([pooled(Etr[g], Mtr[g], [2, 3]) for g in STATIC_GROUPS]),
            np.hstack([pooled(Eva[g], Mva[g], [2, 3]) for g in STATIC_GROUPS]))
    d11 = [c for c in (11, 12, 13) if c not in zero_ch]
    if d11:
        sets[f"pooled ch{d11} all groups (derived)"] = (
            np.hstack([pooled(Etr[g], Mtr[g], d11) for g in GROUPS]),
            np.hstack([pooled(Eva[g], Mva[g], d11) for g in GROUPS]))
        sets[f"pooled ch{d11} STATIC groups"] = (
            np.hstack([pooled(Etr[g], Mtr[g], d11) for g in STATIC_GROUPS]),
            np.hstack([pooled(Eva[g], Mva[g], d11) for g in STATIC_GROUPS]))
    # PER-SLOT static block: catches leakage carried by the ROW ORDER, which the
    # sort key induces from relative motion and pooling would average away.
    slot_tr = np.hstack([Etr[g][:, :, ent_ch_all].reshape(len(Atr), -1) for g in STATIC_GROUPS])
    slot_va = np.hstack([Eva[g][:, :, ent_ch_all].reshape(len(Ava), -1) for g in STATIC_GROUPS])
    sets["PER-SLOT static groups, all kept ch (ordering)"] = (slot_tr, slot_va)
    sets["student globals only"] = (Gtr[:, kept_g], Gva[:, kept_g])
    sets["student globals + pooled all ch"] = (
        np.hstack([Gtr[:, kept_g]] + [pooled(Etr[g], Mtr[g], ent_ch_all) for g in GROUPS]),
        np.hstack([Gva[:, kept_g]] + [pooled(Eva[g], Mva[g], ent_ch_all) for g in GROUPS]))
    for name, (a, b) in sets.items():
        probe(f"{name} [{a.shape[1]}d]", a, b)

    # ---------------------------------------------------------------- (3) ----
    print("\n(3) RECONSTRUCTION PROBE -- can the STUDENT INPUT rebuild player_vx/vy?")
    Ytr, Yva = Gtr[:, list(PLAYER_V_IDX)], Gva[:, list(PLAYER_V_IDX)]
    full_tr = sets["student globals + pooled all ch"][0]
    full_va = sets["student globals + pooled all ch"][1]
    for name, (a, b) in (("student globals + pooled all ch", (full_tr, full_va)),
                         ("PER-SLOT static groups", (slot_tr, slot_va))):
        W, ms = ridge_fit(a, Ytr, args.ridge)
        rec = ridge_apply(b, W, ms)
        ss_res = ((Yva - rec) ** 2).sum(0)
        ss_tot = ((Yva - Ytr.mean(0)) ** 2).sum(0)
        r2 = 1.0 - ss_res / np.maximum(ss_tot, 1e-12)
        pm, tm = np.linalg.norm(rec, axis=1), np.linalg.norm(Yva, axis=1)
        s = (pm > 1e-8) & (tm > 1e-8)
        cos = float(((rec[s] * Yva[s]).sum(1) / (pm[s] * tm[s])).mean())
        agree = int((snap9(rec, 0.5 * np.median(tm)) == lab).sum()) / len(lab)
        print(f"  {name:48s} R2(vx)={r2[0]:7.4f} R2(vy)={r2[1]:7.4f} "
              f"cos={cos:7.4f}  ->label agree={agree:.4f}")
    print("\n  (this is the copy-velocity baseline recomputed: the best the student "
          "\n   input can do at reconstructing player velocity, then copying it)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
