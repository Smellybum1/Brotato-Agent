"""Build ``human_obs_v1`` — the HUMAN-labelled behaviour-cloning dataset.

Same observation encoding as ``combat_obs_v1`` (``trainer/observation/encoder_v1.py``
``encode_capture``, used UNCHANGED), but the regression target is the human
player's real keyboard vector logged by mod 0.2.56 at
``payload.teacher.contributions.human`` rather than ``teacher.action``.

Source runs are enumerated from the runs directory: every run whose
``summary.json`` has ``human_movement: true``. Runs built before mod 0.2.56
carry NO ``human`` block and therefore contribute zero labelled rows; they are
reported and excluded.

Outputs (mirroring the ``combat_obs_v1`` conventions exactly):
  * ``datasets/human_obs_v1/<run_id>.npz``   one shard per contributing run
  * ``datasets/human_obs_v1/manifest.json``  run ids, sha256 pins, row counts
  * ``configs/wp2/human_dataset_split_v1.yaml``  whole-FIXTURE train/val split
  * ``datasets/human_obs_v1/normalization.json`` TRAIN-split-only stats
  * ``reports/wp2/human_obs_v1_dataset_report.{json,md}``

NPZ shards are gitignored by the existing ``datasets/**/*.npz`` rule.

No game, no deploy, no commit. Run with the project ``.venv`` python.
"""
from __future__ import annotations

import argparse
import gc
import hashlib
import json
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any, Iterator

import numpy as np

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from trainer.data.human_labels import (  # noqa: E402
    DROP_NO_BLOCK,
    DROP_NO_SAMPLES,
    extract_human_label,
)
from trainer.observation.encoder_v1 import (  # noqa: E402
    ObservationError,
    canonical_digest,
    encode_capture,
    load_schema,
)

ROOT = _REPO_ROOT
SCHEMA_PATH = ROOT / "configs" / "wp2" / "observation_v1.yaml"
ENCODER_REL = "trainer/observation/encoder_v1.py"
RUNS_ROOT = Path("C:/Users/moxhe/AppData/Roaming/Brotato/brotato_agent/runs")
DATASET_DIR = ROOT / "datasets" / "human_obs_v1"
SPLIT_CONFIG = ROOT / "configs" / "wp2" / "human_dataset_split_v1.yaml"
REPORT_MD = ROOT / "reports" / "wp2" / "human_obs_v1_dataset_report.md"
REPORT_JSON = ROOT / "reports" / "wp2" / "human_obs_v1_dataset_report.json"

SPLIT_ID = "human_dataset_split_v1"
SCHEMA_ID = "human_obs_v1"

# --- Fixture provenance -------------------------------------------------------
# A run's FIXTURE is not in its summary.json; it is in the wp2_finale_loop trials
# row that launched it (``fixture_file`` / ``fixture_digest``). The split is by
# fixture, so a contributing run whose fixture cannot be resolved is a HARD
# ERROR -- guessing it would silently re-create the leak this rebuild exists to
# remove.
TRIALS_GLOB_DEFAULT = ".tmp/gate0/*.jsonl"
DEFAULT_VAL_ROW_FRACTION = 0.15

# --- Capture-schema compatibility --------------------------------------------
# ``configs/wp2/observation_v1.yaml`` pins source_capture_schema_hash to the
# PRE-v127 value 95B64447..., and ``encode_capture`` hard-errors on any other
# value. EVERY human_movement run on disk is v127+ (2823CB7E...), so with the
# pin alone this dataset is EMPTY.
#
# v127's move was purely ADDITIVE: player.materials, player.bonus_materials and
# entities.materials[].value. None is read by the encoder. This build proves it
# per-run rather than asserting it (see ``verify_v127_additive_inertness``):
# strip the three added fields, re-encode, and require an identical canonical
# digest. Only hashes in this accept-list are ever encoded, the accepted hash is
# recorded in the manifest, and encoder_v1.py is NOT modified.
V127_CAPTURE_SCHEMA_HASH = "2823CB7E7D6A6DDB7F805A76D0CD674BA7A2A908058771B66B4A8FEFF9BC1174"
ACCEPTED_CAPTURE_SCHEMA_HASHES: tuple[str, ...] = (V127_CAPTURE_SCHEMA_HASH,)
V127_ADDED_FIELDS = ("player.materials", "player.bonus_materials", "entities.materials[].value")
INERTNESS_SPOT_CHECK = 500

# The 8 keyboard directions plus the standing-still vector, as the mod emits
# them (normalized; diagonals are 1/sqrt(2) rounded to 3 dp by the mod).
DIRECTION_NAMES: tuple[tuple[str, float, float], ...] = (
    ("E", 1.0, 0.0),
    ("W", -1.0, 0.0),
    ("S", 0.0, 1.0),
    ("N", 0.0, -1.0),
    ("SE", 0.707, 0.707),
    ("SW", -0.707, 0.707),
    ("NE", 0.707, -0.707),
    ("NW", -0.707, -0.707),
    ("ZERO", 0.0, 0.0),
)


# --------------------------------------------------------------------------- #
# Helpers (mirrored from wp2_build_combat_obs_v1.py)
# --------------------------------------------------------------------------- #
def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(chunk), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def git_head_commit(root: Path) -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(root),
            capture_output=True,
            text=True,
            check=True,
        )
        return out.stdout.strip()
    except Exception:  # pragma: no cover
        return "unknown"


def iter_capture_payloads(events_path: Path) -> Iterator[dict[str, Any]]:
    """Stream ``combat_capture`` payloads; count unparseable lines separately."""
    with open(events_path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                yield {"__unparseable__": True}
                continue
            if event.get("event") == "combat_capture":
                yield event["payload"]


def direction_name(x: float, y: float, tol: float = 1e-3) -> str:
    """Snap a label vector to one of the 9 keyboard classes, or ``OTHER``."""
    for name, dx, dy in DIRECTION_NAMES:
        if abs(x - dx) <= tol and abs(y - dy) <= tol:
            return name
    return "OTHER"


def strip_v127_additions(payload: dict[str, Any]) -> dict[str, Any]:
    """Deep-copy ``payload`` with the three v127-added capture fields removed."""
    import copy

    out = copy.deepcopy(payload)
    player = out.get("player")
    if isinstance(player, dict):
        player.pop("materials", None)
        player.pop("bonus_materials", None)
    for material in ((out.get("entities") or {}).get("materials") or []):
        if isinstance(material, dict):
            material.pop("value", None)
    return out


def verify_v127_additive_inertness(
    payload: dict[str, Any], schema: dict[str, Any]
) -> None:
    """Hard-error unless removing the v127 additions leaves the encoding identical.

    This is the evidence that accepting the v127 capture-schema hash does not
    change the observation the deployed student sees.
    """
    with_fields = encode_capture(payload, schema)
    without = strip_v127_additions(payload)
    without["capture_schema_hash"] = payload.get("capture_schema_hash")
    if canonical_digest(with_fields) != canonical_digest(encode_capture(without, schema)):
        raise RuntimeError(
            "v127 capture-schema additions are NOT inert for the encoder "
            f"(capture_seq={payload.get('capture_seq')}); refusing to build"
        )


def schema_for_capture(
    schema: dict[str, Any], capture_hash: str | None, accepted: tuple[str, ...]
) -> dict[str, Any]:
    """Return the schema to encode with, or raise if the capture hash is unknown.

    The pinned hash passes through untouched; an ACCEPTED newer hash yields a
    shallow copy with only ``source_capture_schema_hash`` overridden. Anything
    else is a hard error — no silent acceptance.
    """
    pinned = schema.get("source_capture_schema_hash")
    if capture_hash == pinned:
        return schema
    if capture_hash in accepted:
        relaxed = dict(schema)
        relaxed["source_capture_schema_hash"] = capture_hash
        return relaxed
    raise RuntimeError(
        f"capture_schema_hash {capture_hash!r} is neither the pinned {pinned!r} "
        f"nor in the accept-list {accepted!r}"
    )


def discover_human_runs(runs_root: Path) -> list[dict[str, Any]]:
    """Every run whose ``summary.json`` has ``human_movement: true``, time-ordered."""
    found: list[dict[str, Any]] = []
    for run_dir in sorted(runs_root.iterdir()):
        summary_path = run_dir / "summary.json"
        if not summary_path.is_file():
            continue
        try:
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if summary.get("human_movement") is not True:
            continue
        found.append(
            {
                "run_id": str(summary.get("run_id", run_dir.name)),
                "run_dir": run_dir,
                "mod_version": str(summary.get("mod_version", "unknown")),
                "policy_version": str(summary.get("policy_version", "unknown")),
                "last_wave": summary.get("last_wave"),
                "result": summary.get("result"),
            }
        )
    return found


# --------------------------------------------------------------------------- #
# Per-run scan / build
# --------------------------------------------------------------------------- #
def scan_run(
    run_id: str,
    events_path: Path,
    schema: dict[str, Any],
    dataset_dir: Path | None,
) -> dict[str, Any]:
    """Encode one run and (if ``dataset_dir``) write its human-labelled shard.

    Rows kept satisfy ALL of:
      human block present, samples > 0, encoder ``valid``, encoder
      ``temporal_valid``.
    Aliased (``all_identical == false``) and zero-vector rows are KEPT; both are
    recorded as per-row columns / counted separately.
    """
    groups: list[str] = list(schema["groups"].keys())

    globals_rows: list[np.ndarray] = []
    ent_rows: dict[str, list[np.ndarray]] = {g: [] for g in groups}
    mask_rows: dict[str, list[np.ndarray]] = {g: [] for g in groups}
    seq_list: list[int] = []
    wave_list: list[int] = []
    label_rows: list[tuple[float, float]] = []
    samples_list: list[int] = []
    alias_list: list[bool] = []

    counts = Counter()
    dir_counts: Counter = Counter()
    faults: list[dict[str, Any]] = []
    accepted_hashes: Counter = Counter()

    for payload in iter_capture_payloads(events_path):
        if payload.get("__unparseable__"):
            counts["unparseable_lines"] += 1
            continue
        counts["captures"] += 1
        cseq = payload.get("capture_seq")

        capture_hash = payload.get("capture_schema_hash")
        enc_schema = schema_for_capture(schema, capture_hash, ACCEPTED_CAPTURE_SCHEMA_HASHES)
        if enc_schema is not schema and accepted_hashes[capture_hash] < INERTNESS_SPOT_CHECK:
            verify_v127_additive_inertness(payload, enc_schema)
        accepted_hashes[capture_hash] += 1

        label, reason = extract_human_label(payload)
        if reason == DROP_NO_BLOCK:
            counts["dropped_no_human_block"] += 1
            continue
        if reason == DROP_NO_SAMPLES:
            counts["dropped_zero_samples"] += 1
            continue
        assert label is not None
        counts["with_label"] += 1

        try:
            encoded = encode_capture(payload, enc_schema)
        except ObservationError as exc:
            counts["dropped_encoding_fault"] += 1
            faults.append({"run_id": run_id, "capture_seq": cseq, "error": str(exc)})
            continue

        if not encoded.valid:
            counts["dropped_invalid"] += 1
            continue
        if not encoded.temporal_valid:
            counts["dropped_temporal_invalid"] += 1
            continue

        counts["kept"] += 1
        if not label.all_identical:
            counts["kept_aliased"] += 1
        if label.is_zero:
            counts["kept_zero_vector"] += 1
        dir_counts[direction_name(label.x, label.y)] += 1

        globals_rows.append(np.asarray(encoded.global_features, dtype=np.float32))
        for group in groups:
            ent_rows[group].append(np.asarray(encoded.entities[group], dtype=np.float32))
            mask_rows[group].append(np.asarray(encoded.masks[group], dtype=np.float32))
        seq_list.append(int(cseq) if cseq is not None else -1)
        wave_list.append(int(payload.get("wave") or 0))
        label_rows.append((label.x, label.y))
        samples_list.append(label.samples)
        alias_list.append(not label.all_identical)

    entry: dict[str, Any] = {
        "run_id": run_id,
        "counts": {
            "captures": int(counts["captures"]),
            "unparseable_lines": int(counts["unparseable_lines"]),
            "dropped_no_human_block": int(counts["dropped_no_human_block"]),
            "dropped_zero_samples": int(counts["dropped_zero_samples"]),
            "dropped_encoding_fault": int(counts["dropped_encoding_fault"]),
            "dropped_invalid": int(counts["dropped_invalid"]),
            "dropped_temporal_invalid": int(counts["dropped_temporal_invalid"]),
            "kept": int(counts["kept"]),
            "kept_aliased": int(counts["kept_aliased"]),
            "kept_zero_vector": int(counts["kept_zero_vector"]),
        },
        "direction_counts": dict(dir_counts),
        "capture_schema_hashes": {str(k): int(v) for k, v in accepted_hashes.items()},
        "inertness_spot_checks": int(
            sum(min(v, INERTNESS_SPOT_CHECK) for k, v in accepted_hashes.items()
                if k != schema.get("source_capture_schema_hash"))
        ),
        "fault_count": len(faults),
        "faults": faults,
    }

    if counts["kept"] == 0 or dataset_dir is None:
        return entry

    seq = np.asarray(seq_list, dtype=np.int64)
    order = np.argsort(seq, kind="stable")
    arrays: dict[str, np.ndarray] = {
        "global_features": np.stack(globals_rows, axis=0)[order],
        "capture_seq": seq.astype(np.int32)[order],
        "wave": np.asarray(wave_list, dtype=np.int32)[order],
        "human_action": np.asarray(label_rows, dtype=np.float32)[order],
        "human_samples": np.asarray(samples_list, dtype=np.int32)[order],
        "human_aliased": np.asarray(alias_list, dtype=bool)[order],
    }
    del globals_rows
    for group in groups:
        arrays[f"entities_{group}"] = np.stack(ent_rows[group], axis=0)[order]
        ent_rows[group] = []
        arrays[f"mask_{group}"] = np.stack(mask_rows[group], axis=0)[order]
        mask_rows[group] = []
    gc.collect()

    dataset_dir.mkdir(parents=True, exist_ok=True)
    shard_name = f"{run_id}.npz"
    shard_path = dataset_dir / shard_name
    np.savez_compressed(shard_path, **arrays)
    entry["shard_file"] = shard_name
    entry["shard_sha256"] = sha256_file(shard_path)
    entry["shard_bytes"] = int(shard_path.stat().st_size)

    wave_arr = arrays["wave"]
    entry["per_wave_kept"] = {
        str(int(w)): int((wave_arr == w).sum()) for w in sorted(set(int(v) for v in np.unique(wave_arr)))
    }
    del arrays
    gc.collect()
    return entry


# --------------------------------------------------------------------------- #
# Split
# --------------------------------------------------------------------------- #
def load_trial_meta(paths: list[Path]) -> dict[str, dict[str, Any]]:
    """run_id -> fixture / boss / campaign-label, read from trials jsonl rows.

    Later rows win only if they carry a fixture the earlier row lacked; a
    CONFLICTING fixture for the same run_id is a hard error.
    """
    meta: dict[str, dict[str, Any]] = {}
    for path in sorted(paths):
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            run_id = row.get("run_id")
            if not isinstance(run_id, str) or not run_id:
                continue
            info = {
                "fixture_file": row.get("fixture_file"),
                "fixture_digest": row.get("fixture_digest"),
                "boss_entity": row.get("boss_entity") or "unknown",
                "trial_label": row.get("label"),
                "trials_file": path.name,
                "trial_mod_version": row.get("mod_version"),
            }
            prior = meta.get(run_id)
            if prior is not None:
                pd_, nd_ = prior.get("fixture_digest"), info.get("fixture_digest")
                if pd_ and nd_ and pd_ != nd_:
                    raise RuntimeError(
                        f"conflicting fixture_digest for {run_id}: "
                        f"{pd_!r} ({prior['trials_file']}) vs {nd_!r} ({path.name})"
                    )
                if pd_ and not nd_:
                    continue
            meta[run_id] = info
    return meta


def choose_split_by_fixture(
    entries: list[dict[str, Any]],
    trial_meta: dict[str, dict[str, Any]],
    val_fraction: float = DEFAULT_VAL_ROW_FRACTION,
    forced_val_fixtures: list[str] | None = None,
) -> dict[str, Any]:
    """Whole-FIXTURE split: no fixture may appear in BOTH train and val.

    WHY THIS CHANGED. The previous split was whole-RUN, and all six runs then
    on disk came from ONE fixture -- so the 2 val runs shared their fixture
    (and its enemy layout, boss and shop rolls) with the 4 train runs. Val loss
    measured memorisation of a single fixture, not generalisation. Whole-run is
    necessary (adjacent captures are 50 ms apart) but NOT sufficient.

    Selection rule, deterministic and stated:
      * candidate val fixtures are the SMALLEST first, ordered by
        (n_runs, rows, digest) -- holding out a 6-run fixture would cost half
        the corpus;
      * candidates are taken ROUND-ROBIN over bosses (sorted) so val contains
        every boss it can, rather than three fixtures of one boss;
      * stop once val rows >= ``val_fraction`` of all rows;
      * a fixture is NEVER taken if it is the last one of its boss in train.

    Fixture separation beats hitting a target percentage: whatever ratio falls
    out is reported, not tuned.
    """
    by_fixture: dict[str, list[dict[str, Any]]] = {}
    for entry in entries:
        info = trial_meta.get(entry["run_id"])
        digest = (info or {}).get("fixture_digest")
        if not digest:
            raise RuntimeError(
                f"contributing run {entry['run_id']} has NO fixture_digest in any "
                "trials jsonl; the split is by fixture, so this cannot be guessed. "
                "Pass the right --trials file(s)."
            )
        by_fixture.setdefault(str(digest), []).append(entry)

    rows_of = {f: sum(e["counts"]["kept"] for e in es) for f, es in by_fixture.items()}
    boss_of = {
        f: str((trial_meta.get(es[0]["run_id"]) or {}).get("boss_entity") or "unknown")
        for f, es in by_fixture.items()
    }
    total_rows = sum(rows_of.values())
    if len(by_fixture) < 2:
        raise RuntimeError(
            f"only {len(by_fixture)} distinct fixture(s); a fixture-held-out split "
            "is impossible -- do not fall back to a run split, it cannot measure "
            "generalisation"
        )

    val_fixtures: list[str] = []
    if forced_val_fixtures:
        unknown = [f for f in forced_val_fixtures if f not in by_fixture]
        if unknown:
            raise RuntimeError(f"--val-fixture not among contributing fixtures: {unknown}")
        if len(forced_val_fixtures) >= len(by_fixture):
            raise RuntimeError("--val-fixture would leave train with no fixtures")
        val_fixtures = list(dict.fromkeys(forced_val_fixtures))
        rule = "explicit --val-fixture"
    else:
        rule = (f"smallest-first, round-robin over bosses, stop at "
                f"val_rows >= {val_fraction:.2f} of rows")
        candidates = sorted(
            by_fixture, key=lambda f: (len(by_fixture[f]), rows_of[f], f)
        )
        bosses = sorted({boss_of[f] for f in by_fixture})
        remaining_per_boss = Counter(boss_of[f] for f in by_fixture)
        val_rows = 0
        progressed = True
        while progressed and val_rows < val_fraction * total_rows:
            progressed = False
            for boss in bosses:
                if val_rows >= val_fraction * total_rows:
                    break
                for fixture in candidates:
                    if fixture in val_fixtures or boss_of[fixture] != boss:
                        continue
                    if remaining_per_boss[boss] <= 1:
                        break  # last fixture of this boss must stay in train
                    if len(val_fixtures) + 1 >= len(by_fixture):
                        break
                    val_fixtures.append(fixture)
                    remaining_per_boss[boss] -= 1
                    val_rows += rows_of[fixture]
                    progressed = True
                    break
    val_fixtures = sorted(val_fixtures)
    train_fixtures = sorted(f for f in by_fixture if f not in val_fixtures)
    if not train_fixtures or not val_fixtures:
        raise RuntimeError("fixture split produced an empty side")

    train_ids = [e["run_id"] for f in train_fixtures for e in by_fixture[f]]
    val_ids = [e["run_id"] for f in val_fixtures for e in by_fixture[f]]

    # HARD INVARIANT: this is the whole point of the rebuild.
    overlap = set(train_fixtures) & set(val_fixtures)
    if overlap:
        raise RuntimeError(f"fixture appears in BOTH splits: {sorted(overlap)}")
    if set(train_ids) & set(val_ids):
        raise RuntimeError("run appears in both splits")

    train_rows = sum(rows_of[f] for f in train_fixtures)
    val_rows = sum(rows_of[f] for f in val_fixtures)
    return {
        "train_ids": train_ids,
        "val_ids": val_ids,
        "train_fixtures": train_fixtures,
        "val_fixtures": val_fixtures,
        "selection_rule": rule,
        "fixture_table": [
            {
                "fixture_digest": f,
                "fixture_file": (trial_meta.get(by_fixture[f][0]["run_id"]) or {}).get(
                    "fixture_file"
                ),
                "boss_entity": boss_of[f],
                "split": "validation" if f in val_fixtures else "train",
                "run_count": len(by_fixture[f]),
                "run_ids": [e["run_id"] for e in by_fixture[f]],
                "rows": rows_of[f],
            }
            for f in sorted(by_fixture, key=lambda f: (boss_of[f], f))
        ],
        "total_rows": total_rows,
        "train_rows": train_rows,
        "val_rows": val_rows,
        "val_row_fraction": (val_rows / total_rows) if total_rows else None,
        "val_run_fraction": len(val_ids) / max(1, len(train_ids) + len(val_ids)),
        "train_bosses": sorted({boss_of[f] for f in train_fixtures}),
        "val_bosses": sorted({boss_of[f] for f in val_fixtures}),
    }


def build_group_label_stats(
    entries: list[dict[str, Any]], key_of, key_name: str
) -> list[dict[str, Any]]:
    """Aliasing / no-label / direction stats per group, EVERY denominator printed.

    Used to check that a build (or campaign-batch) change is INERT for labels
    before anything is trained on the pooled corpus.
    """
    groups: dict[str, list[dict[str, Any]]] = {}
    for entry in entries:
        groups.setdefault(str(key_of(entry)), []).append(entry)
    out: list[dict[str, Any]] = []
    for name in sorted(groups):
        rows = groups[name]
        agg = Counter()
        for e in rows:
            agg.update(e["counts"])
        dirs: Counter = Counter()
        for e in rows:
            dirs.update(e["direction_counts"])
        kept = int(agg["kept"])
        captures = int(agg["captures"])
        no_label = int(agg["dropped_no_human_block"]) + int(agg["dropped_zero_samples"])
        out.append(
            {
                key_name: name,
                "runs": len(rows),
                "run_ids": [e["run_id"] for e in rows],
                "captures": captures,
                "kept": kept,
                "no_label": no_label,
                "no_label_rate": (no_label / captures) if captures else None,
                "dropped_no_human_block": int(agg["dropped_no_human_block"]),
                "dropped_zero_samples": int(agg["dropped_zero_samples"]),
                "zero_samples_rate": (
                    int(agg["dropped_zero_samples"]) / captures if captures else None
                ),
                "kept_aliased": int(agg["kept_aliased"]),
                "aliasing_rate": (int(agg["kept_aliased"]) / kept) if kept else None,
                "kept_zero_vector": int(agg["kept_zero_vector"]),
                "zero_vector_rate": (
                    int(agg["kept_zero_vector"]) / kept if kept else None
                ),
                "direction_counts": dict(dirs),
                "direction_shares": {
                    d: (dirs.get(d, 0) / kept if kept else None)
                    for d, _, _ in DIRECTION_NAMES
                },
            }
        )
    return out


def render_split_yaml(
    entries: list[dict[str, Any]],
    split: dict[str, Any],
    schema_hash: str,
    meta: dict[str, dict[str, Any]],
    trial_meta: dict[str, dict[str, Any]],
) -> str:
    by_id = {e["run_id"]: e for e in entries}
    lines = [
        "# WP2 — HUMAN-labelled BC dataset split (human_obs_v1)",
        "#",
        "# Split by FIXTURE, at whole-run granularity.",
        "#",
        "# Whole-run is NECESSARY: adjacent captures are 50 ms apart and nearly",
        "# identical, so a row-level split leaks train into val and makes val loss",
        "# meaningless.  It is NOT SUFFICIENT: the previous split held out 2 runs",
        "# of the SAME fixture the 4 train runs came from, so val measured",
        "# memorisation of one enemy layout, not generalisation.  No fixture may",
        "# now appear on both sides.",
        "#",
        f"# selection rule: {split['selection_rule']}",
        f"# train fixtures: {', '.join(split['train_fixtures'])}",
        f"# val   fixtures: {', '.join(split['val_fixtures'])}",
        f"# train bosses: {', '.join(split['train_bosses'])}"
        f" | val bosses: {', '.join(split['val_bosses'])}",
        f"# rows train/val: {split['train_rows']}/{split['val_rows']}"
        f"  (val row fraction {split['val_row_fraction']:.4f})",
        "#",
        "# Per-run shard_sha256 is copied from datasets/human_obs_v1/manifest.json;",
        "# the loader hard-errors if any shard on disk disagrees.",
        f"split_id: {SPLIT_ID}",
        f"schema_id: {SCHEMA_ID}",
        f"observation_schema_hash: {schema_hash}",
        "split_by: fixture",
        "split_granularity: run",
        "",
    ]
    for key, ids in (("validation", split["val_ids"]), ("train", split["train_ids"])):
        lines.append(f"{key}:")
        for run_id in ids:
            entry = by_id[run_id]
            info = meta.get(run_id, {})
            tinfo = trial_meta.get(run_id, {})
            lines.append(f"  - run_id: {run_id}")
            lines.append(f"    shard_file: {entry['shard_file']}")
            lines.append(f"    shard_sha256: {entry['shard_sha256']}")
            lines.append(f"    mod_version: {info.get('mod_version', 'unknown')}")
            lines.append(f"    fixture_digest: {tinfo.get('fixture_digest')}")
            lines.append(f"    fixture_file: {tinfo.get('fixture_file')}")
            lines.append(f"    boss_entity: {tinfo.get('boss_entity')}")
            lines.append(f"    last_wave: {info.get('last_wave')}")
            lines.append(f"    rows: {entry['counts']['kept']}")
        lines.append("")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Report
# --------------------------------------------------------------------------- #
def render_report_md(report: dict[str, Any]) -> str:
    lines = [
        "# human_obs_v1 dataset build report",
        "",
        f"- schema_id: `{report['schema_id']}`",
        f"- observation schema hash: `{report['observation_schema_hash']}`",
        f"- encoder: `{report['encoder_path']}` @ `{report['repo_head_commit']}` (UNCHANGED)",
        f"- label: `payload.teacher.contributions.human` (x, y) — NOT teacher.action",
        f"- human_movement runs found: {report['human_runs_found']}"
        f" | contributing: {report['contributing_run_count']}"
        f" | zero-row (excluded): {report['zero_row_run_count']}",
        "",
        "## Per-run (every denominator shown)",
        "",
        "| run_id | mod | fixture | boss | captures | no human block | samples==0 | invalid | !temporal_valid | kept | aliased kept | zero kept |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in report["runs"]:
        c = row["counts"]
        lines.append(
            f"| {row['run_id']} | {row['mod_version']} | "
            f"{row.get('fixture_digest') or '—'} | {row.get('boss_entity') or '—'} | "
            f"{c['captures']:,} | "
            f"{c['dropped_no_human_block']:,} | {c['dropped_zero_samples']:,} | "
            f"{c['dropped_invalid']:,} | {c['dropped_temporal_invalid']:,} | "
            f"{c['kept']:,} | {c['kept_aliased']:,} | {c['kept_zero_vector']:,} |"
        )
    if report["zero_row_runs"]:
        lines += [
            "",
            "### Runs contributing ZERO rows (named, never vanished)",
            "",
            "| run_id | mod | captures | reason |",
            "| --- | --- | --- | --- |",
        ]
        for row in report["zero_row_runs"]:
            lines.append(
                f"| {row['run_id']} | {row['mod_version']} | {row['captures']:,} | "
                f"{row['reason']} |"
            )
    lines += [
        "",
        "## Fixture-held-out split",
        "",
        f"- selection rule: {report['split']['selection_rule']}",
        f"- NO fixture appears in both sides (asserted at build time)",
        f"- train fixtures: {', '.join(report['split']['train_fixtures'])}",
        f"- val fixtures: {', '.join(report['split']['val_fixtures'])}",
        f"- train bosses: {', '.join(report['split']['train_bosses'])}"
        f" | val bosses: {', '.join(report['split']['val_bosses'])}",
        "",
        "| fixture | boss | split | runs | rows |",
        "| --- | --- | --- | --- | --- |",
    ]
    for f in report["split"]["fixture_table"]:
        lines.append(
            f"| `{f['fixture_digest']}` | {f['boss_entity']} | {f['split']} | "
            f"{f['run_count']} | {f['rows']:,} |"
        )
    lines += [
        "",
        f"- train runs: {report['train_runs']} ({report['train_rows']:,} rows)",
        f"- val runs: {report['val_runs']} ({report['val_rows']:,} rows)",
        f"- val row fraction: {report['split']['val_row_fraction']:.4f}"
        f" | val run fraction: {report['split']['val_run_fraction']:.4f}",
        "- normalization stats: computed on the TRAIN split ONLY",
        "",
        "## Label distribution (kept rows)",
        "",
        "| direction | train | val | total | share |",
        "| --- | --- | --- | --- | --- |",
    ]
    total = max(1, report["train_rows"] + report["val_rows"])
    for name, _, _ in DIRECTION_NAMES:
        t = report["direction_counts"]["train"].get(name, 0)
        v = report["direction_counts"]["validation"].get(name, 0)
        lines.append(f"| {name} | {t:,} | {v:,} | {t + v:,} | {(t + v) / total:.4f} |")
    other_t = report["direction_counts"]["train"].get("OTHER", 0)
    other_v = report["direction_counts"]["validation"].get("OTHER", 0)
    lines.append(f"| OTHER | {other_t:,} | {other_v:,} | {other_t + other_v:,} | "
                 f"{(other_t + other_v) / total:.4f} |")

    for section, key_name in (("build_comparison", "mod_version"),
                              ("batch_comparison", "trials_file")):
        groups = report.get(section) or []
        lines += [
            "",
            f"## Label statistics by `{key_name}`",
            "",
            "A build (or batch) change should be INERT for labels. If it is not,",
            "that must be known BEFORE anything is trained on the pooled corpus.",
            "",
            f"| {key_name} | runs | captures | kept | no-label rate | samples==0 rate | aliasing rate | zero-vector rate |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
        for g in groups:
            def _p(v):
                return "n/a" if v is None else f"{v:.4f}"
            lines.append(
                f"| {g[key_name]} | {g['runs']} | {g['captures']:,} | {g['kept']:,} | "
                f"{_p(g['no_label_rate'])} | {_p(g['zero_samples_rate'])} | "
                f"{_p(g['aliasing_rate'])} | {_p(g['zero_vector_rate'])} |"
            )
        if len(groups) > 1:
            lines += [
                "",
                f"| direction share | {' | '.join(str(g[key_name]) for g in groups)} |",
                "| --- |" + " --- |" * len(groups),
            ]
            for name, _, _ in DIRECTION_NAMES:
                cells = " | ".join(
                    ("n/a" if g["direction_shares"].get(name) is None
                     else f"{g['direction_shares'][name]:.4f}")
                    for g in groups
                )
                lines.append(f"| {name} | {cells} |")
        else:
            lines.append("")
            lines.append(f"- only ONE `{key_name}` group is present, so there is "
                         "nothing to compare across; the single group's rates are "
                         "above.")
    lines.append("")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the human-labelled BC dataset")
    parser.add_argument("--runs-root", type=Path, default=RUNS_ROOT)
    parser.add_argument("--dataset-dir", type=Path, default=DATASET_DIR)
    parser.add_argument("--split-config", type=Path, default=SPLIT_CONFIG)
    parser.add_argument(
        "--trials", type=Path, action="append", default=[],
        help="wp2_finale_loop trials jsonl carrying fixture_file/fixture_digest "
             "(repeatable); defaults to " + TRIALS_GLOB_DEFAULT,
    )
    parser.add_argument("--val-fraction", type=float, default=DEFAULT_VAL_ROW_FRACTION)
    parser.add_argument(
        "--val-fixture", action="append", default=[],
        help="force these fixture digests into val (repeatable)",
    )
    args = parser.parse_args(argv)

    trials_paths = list(args.trials) or sorted(ROOT.glob(TRIALS_GLOB_DEFAULT))
    trial_meta = load_trial_meta([Path(p) for p in trials_paths])
    print(f"trials files: {len(trials_paths)} -> "
          f"{[Path(p).name for p in trials_paths]}", flush=True)
    print(f"run_ids with fixture provenance: {len(trial_meta)}", flush=True)

    schema = load_schema(SCHEMA_PATH)
    discovered = discover_human_runs(args.runs_root)
    print(f"human_movement runs: {len(discovered)}", flush=True)

    start = time.time()
    all_entries: list[dict[str, Any]] = []
    contributing: list[dict[str, Any]] = []
    meta: dict[str, dict[str, Any]] = {}
    for info in discovered:
        run_id = info["run_id"]
        meta[run_id] = info
        events_path = info["run_dir"] / "events.jsonl"
        if not events_path.is_file():
            raise FileNotFoundError(f"missing events.jsonl for {run_id}: {events_path}")
        entry = scan_run(run_id, events_path, schema, args.dataset_dir)
        entry["mod_version"] = info["mod_version"]
        entry["last_wave"] = info["last_wave"]
        tinfo = trial_meta.get(run_id, {})
        entry["fixture_digest"] = tinfo.get("fixture_digest")
        entry["fixture_file"] = tinfo.get("fixture_file")
        entry["boss_entity"] = tinfo.get("boss_entity")
        entry["trials_file"] = tinfo.get("trials_file") or "unknown"
        all_entries.append(entry)
        c = entry["counts"]
        print(
            f"  {run_id} [{info['mod_version']}] "
            f"fixture={entry['fixture_digest']} boss={entry['boss_entity']}: "
            f"captures={c['captures']} "
            f"no_block={c['dropped_no_human_block']} s0={c['dropped_zero_samples']} "
            f"invalid={c['dropped_invalid']} !tvalid={c['dropped_temporal_invalid']} "
            f"kept={c['kept']}",
            flush=True,
        )
        if c["kept"] > 0:
            contributing.append(entry)
    wall = time.time() - start

    if len(contributing) < 2:
        print("error: fewer than 2 contributing runs; cannot split by run", file=sys.stderr)
        return 1

    zero_row_runs = [
        {
            "run_id": e["run_id"],
            "mod_version": e["mod_version"],
            "captures": e["counts"]["captures"],
            "reason": (
                "every capture lacked the teacher.contributions.human block "
                f"({e['counts']['dropped_no_human_block']:,}/"
                f"{e['counts']['captures']:,} captures) -- pre-0.2.56 build"
                if e["counts"]["dropped_no_human_block"] == e["counts"]["captures"]
                and e["counts"]["captures"] > 0
                else "no rows survived the filters; see per-run counts"
            ),
        }
        for e in all_entries
        if e["counts"]["kept"] == 0
    ]
    print(f"\ncontributing runs: {len(contributing)} of {len(all_entries)} "
          f"human_movement runs; zero-row runs: {len(zero_row_runs)}", flush=True)
    for z in zero_row_runs:
        print(f"  ZERO ROWS  {z['run_id']} [{z['mod_version']}]: {z['reason']}",
              flush=True)

    split = choose_split_by_fixture(
        contributing, trial_meta, args.val_fraction, args.val_fixture or None
    )
    train_ids, val_ids = split["train_ids"], split["val_ids"]
    by_id = {e["run_id"]: e for e in contributing}
    print(f"\nfixtures: {len(split['fixture_table'])} "
          f"(train {len(split['train_fixtures'])}, val {len(split['val_fixtures'])})",
          flush=True)
    for f in split["fixture_table"]:
        print(f"  {f['fixture_digest']}  boss={f['boss_entity']:<9} "
              f"{f['split']:<10} runs={f['run_count']} rows={f['rows']}", flush=True)

    args.split_config.parent.mkdir(parents=True, exist_ok=True)
    args.split_config.write_text(
        render_split_yaml(contributing, split, schema["_schema_hash"], meta, trial_meta),
        encoding="utf-8",
    )

    manifest = {
        "schema_id": SCHEMA_ID,
        "observation_schema_hash": schema["_schema_hash"],
        "source_capture_schema_hash": schema["source_capture_schema_hash"],
        "encoder_path": ENCODER_REL,
        "repo_head_commit": git_head_commit(ROOT),
        "runs_root": str(args.runs_root),
        "capture_schema_compatibility": {
            "pinned_hash": schema["source_capture_schema_hash"],
            "accepted_hashes": list(ACCEPTED_CAPTURE_SCHEMA_HASHES),
            "observed_hashes": sorted(
                {h for e in all_entries for h in e["capture_schema_hashes"]}
            ),
            "reason": (
                "every human_movement run is v127+; v127's capture-schema move is "
                "purely additive (%s), none of which the encoder reads. Proven "
                "per-run at build time by re-encoding with the fields stripped and "
                "requiring an identical canonical digest. encoder_v1.py is UNCHANGED."
                % ", ".join(V127_ADDED_FIELDS)
            ),
            "inertness_spot_checks": sum(e["inertness_spot_checks"] for e in all_entries),
        },
        "label_path": "payload.teacher.contributions.human",
        "label_fields": ["x", "y"],
        "run_count": len(contributing),
        "human_runs_found": len(discovered),
        "excluded_runs": zero_row_runs,
        "split": split,
        "aggregate": {
            key: sum(e["counts"][key] for e in all_entries)
            for key in all_entries[0]["counts"]
        },
        "runs": [
            {
                "run_id": e["run_id"],
                "mod_version": e["mod_version"],
                "fixture_digest": e["fixture_digest"],
                "fixture_file": e["fixture_file"],
                "boss_entity": e["boss_entity"],
                "split": "validation" if e["run_id"] in set(val_ids) else "train",
                "shard_file": e["shard_file"],
                "shard_sha256": e["shard_sha256"],
                "shard_bytes": e["shard_bytes"],
                "counts": e["counts"],
                "per_wave_kept": e["per_wave_kept"],
                "direction_counts": e["direction_counts"],
                "fault_count": e["fault_count"],
            }
            for e in contributing
        ],
    }
    args.dataset_dir.mkdir(parents=True, exist_ok=True)
    (args.dataset_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )

    def dir_totals(ids: list[str]) -> dict[str, int]:
        agg: Counter = Counter()
        for run_id in ids:
            agg.update(by_id[run_id]["direction_counts"])
        return dict(agg)

    report = {
        "schema_id": SCHEMA_ID,
        "observation_schema_hash": schema["_schema_hash"],
        "encoder_path": ENCODER_REL,
        "repo_head_commit": manifest["repo_head_commit"],
        "human_runs_found": len(discovered),
        "contributing_run_count": len(contributing),
        "zero_row_run_count": len(zero_row_runs),
        "zero_row_runs": zero_row_runs,
        "build_wall_seconds": round(wall, 2),
        "split": split,
        "build_comparison": build_group_label_stats(
            contributing, lambda e: e["mod_version"], "mod_version"
        ),
        "batch_comparison": build_group_label_stats(
            contributing, lambda e: e["trials_file"], "trials_file"
        ),
        "train_runs": train_ids,
        "val_runs": val_ids,
        "train_rows": sum(by_id[r]["counts"]["kept"] for r in train_ids),
        "val_rows": sum(by_id[r]["counts"]["kept"] for r in val_ids),
        "direction_counts": {
            "train": dir_totals(train_ids),
            "validation": dir_totals(val_ids),
        },
        "runs": [
            {
                "run_id": e["run_id"],
                "mod_version": e["mod_version"],
                "fixture_digest": e["fixture_digest"],
                "boss_entity": e["boss_entity"],
                "trials_file": e["trials_file"],
                "counts": e["counts"],
                "direction_counts": e["direction_counts"],
            }
            for e in all_entries
        ],
    }
    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")
    REPORT_MD.write_text(render_report_md(report), encoding="utf-8")

    # Load back through the real loader (verifies sha256 pins, schema-hash
    # agreement and the whole-run split) and emit TRAIN-ONLY norm stats.
    from trainer.data.bc_dataset import load_human_bc_dataset

    dataset = load_human_bc_dataset(
        args.dataset_dir,
        args.split_config,
        ROOT / "configs" / "wp2" / "human_bc_input_v1.yaml",
        SCHEMA_PATH,
    )
    if dataset.train.size != report["train_rows"] or dataset.val.size != report["val_rows"]:
        raise RuntimeError("loader row counts disagree with the build report")
    dataset.save_normalization_manifest(args.dataset_dir / "normalization.json")
    report["loader_train_rows"] = dataset.train.size
    report["loader_val_rows"] = dataset.val.size
    report["global_dim"] = int(dataset.train.globals.shape[1])
    REPORT_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"\ntrain runs={len(train_ids)} rows={report['train_rows']:,} "
          f"fixtures={split['train_fixtures']}", flush=True)
    print(f"val   runs={len(val_ids)} rows={report['val_rows']:,} "
          f"fixtures={split['val_fixtures']}", flush=True)
    print(f"val row fraction={split['val_row_fraction']:.4f} "
          f"run fraction={split['val_run_fraction']:.4f}", flush=True)
    print(f"manifest -> {args.dataset_dir / 'manifest.json'}", flush=True)
    print(f"split    -> {args.split_config}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
