"""Unit tests for the HUMAN-labelled BC dataset: label extraction + each filter.

Covers ``trainer/data/human_labels.py`` and the filter/split/normalization
machinery in ``scripts/wp2_build_human_obs_v1.py`` +
``trainer.data.bc_dataset.load_human_bc_dataset``. No runs directory, no game.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from trainer.data.human_labels import (  # noqa: E402
    DROP_NO_BLOCK,
    DROP_NO_SAMPLES,
    HumanLabelError,
    extract_human_label,
    get_human_block,
)


def _load_builder():
    spec = importlib.util.spec_from_file_location(
        "wp2_build_human_obs_v1", ROOT / "scripts" / "wp2_build_human_obs_v1.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


BUILDER = _load_builder()


def _payload(human: dict | None = None, **extra) -> dict:
    payload: dict = {"capture_seq": 1, "valid": True, "wave": 17}
    if human is not None:
        payload["teacher"] = {"contributions": {"human": human}}
    payload.update(extra)
    return payload


# --------------------------------------------------------------------------- #
# Label extraction
# --------------------------------------------------------------------------- #
def test_label_is_the_human_block_not_teacher_action():
    payload = _payload({"x": -0.707, "y": 0.707, "samples": 3, "all_identical": True})
    payload["teacher"]["action"] = {"x": 1.0, "y": 0.0}
    label, reason = extract_human_label(payload)
    assert reason is None
    assert (label.x, label.y) == (-0.707, 0.707)
    assert label.samples == 3
    assert label.all_identical is True


def test_get_human_block_returns_none_without_the_path():
    assert get_human_block({"teacher": {"contributions": {}}}) is None
    assert get_human_block({"teacher": {}}) is None
    assert get_human_block({}) is None


def test_get_human_block_returns_none_when_not_a_mapping():
    assert get_human_block({"teacher": {"contributions": {"human": [1, 2]}}}) is None


# --------------------------------------------------------------------------- #
# Filter: no human block (pre-0.2.56 runs)
# --------------------------------------------------------------------------- #
def test_filter_drops_rows_with_no_human_block():
    label, reason = extract_human_label(_payload(None))
    assert label is None and reason == DROP_NO_BLOCK


def test_filter_drops_when_contributions_has_other_keys_only():
    payload = _payload(None)
    payload["teacher"] = {"contributions": {"finale_translation": {"a": 1}}}
    assert extract_human_label(payload)[1] == DROP_NO_BLOCK


# --------------------------------------------------------------------------- #
# Filter: samples == 0
# --------------------------------------------------------------------------- #
def test_filter_drops_zero_samples():
    label, reason = extract_human_label(
        _payload({"x": 1.0, "y": 0.0, "samples": 0, "all_identical": True})
    )
    assert label is None and reason == DROP_NO_SAMPLES


def test_zero_samples_drops_even_with_a_nonzero_vector():
    """samples==0 means no input was sampled: any x/y present is not a label."""
    assert extract_human_label(
        _payload({"x": 0.707, "y": -0.707, "samples": 0, "all_identical": False})
    )[1] == DROP_NO_SAMPLES


def test_missing_samples_key_is_treated_as_zero():
    assert extract_human_label(_payload({"x": 1.0, "y": 0.0}))[1] == DROP_NO_SAMPLES


# --------------------------------------------------------------------------- #
# Filter: aliased rows are KEPT, with the flag recorded
# --------------------------------------------------------------------------- #
def test_aliased_rows_are_kept_and_flagged():
    label, reason = extract_human_label(
        _payload({"x": 1.0, "y": 0.0, "samples": 3, "all_identical": False})
    )
    assert reason is None
    assert label.all_identical is False


def test_all_identical_must_be_a_bool():
    with pytest.raises(HumanLabelError):
        extract_human_label(_payload({"x": 1.0, "y": 0.0, "samples": 3, "all_identical": "no"}))


# --------------------------------------------------------------------------- #
# Filter: zero vector KEPT, counted separately
# --------------------------------------------------------------------------- #
def test_zero_vector_with_samples_is_kept_as_a_real_action():
    label, reason = extract_human_label(
        _payload({"x": 0.0, "y": 0.0, "samples": 3, "all_identical": True})
    )
    assert reason is None
    assert label.is_zero is True


def test_nonzero_vector_is_not_flagged_zero():
    label, _ = extract_human_label(
        _payload({"x": 1.0, "y": 0.0, "samples": 3, "all_identical": True})
    )
    assert label.is_zero is False


# --------------------------------------------------------------------------- #
# Malformed blocks hard-error rather than silently dropping
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "block",
    [
        {"x": float("inf"), "y": 0.0, "samples": 3, "all_identical": True},
        {"x": float("nan"), "y": 0.0, "samples": 3, "all_identical": True},
        {"y": 0.0, "samples": 3, "all_identical": True},
        {"x": "left", "y": 0.0, "samples": 3, "all_identical": True},
        {"x": 1.0, "y": 0.0, "samples": -1, "all_identical": True},
    ],
)
def test_malformed_human_block_raises(block):
    with pytest.raises(HumanLabelError):
        extract_human_label(_payload(block))


# --------------------------------------------------------------------------- #
# Direction classification (label distribution reporting)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "vec,name",
    [
        ((1.0, 0.0), "E"),
        ((-1.0, 0.0), "W"),
        ((0.0, 1.0), "S"),
        ((0.0, -1.0), "N"),
        ((0.707, 0.707), "SE"),
        ((-0.707, 0.707), "SW"),
        ((0.707, -0.707), "NE"),
        ((-0.707, -0.707), "NW"),
        ((0.0, 0.0), "ZERO"),
        ((0.4, 0.3), "OTHER"),
    ],
)
def test_direction_name(vec, name):
    assert BUILDER.direction_name(*vec) == name


# --------------------------------------------------------------------------- #
# Capture-schema accept-list
# --------------------------------------------------------------------------- #
def test_schema_for_capture_passes_pinned_hash_through_unchanged():
    schema = {"source_capture_schema_hash": "PINNED"}
    assert BUILDER.schema_for_capture(schema, "PINNED", ("OTHER",)) is schema


def test_schema_for_capture_overrides_only_the_hash_for_accepted():
    schema = {"source_capture_schema_hash": "PINNED", "groups": {"enemies": 1}}
    out = BUILDER.schema_for_capture(schema, "NEWHASH", ("NEWHASH",))
    assert out is not schema
    assert out["source_capture_schema_hash"] == "NEWHASH"
    assert out["groups"] is schema["groups"]
    assert schema["source_capture_schema_hash"] == "PINNED"


def test_schema_for_capture_rejects_unknown_hash():
    with pytest.raises(RuntimeError, match="accept-list"):
        BUILDER.schema_for_capture({"source_capture_schema_hash": "PINNED"}, "ROGUE", ())


def test_strip_v127_additions_removes_exactly_the_three_added_fields():
    payload = {
        "player": {"materials": 5, "bonus_materials": 1, "hp": 10},
        "entities": {"materials": [{"x": 1.0, "value": 3}], "enemies": [{"x": 2.0}]},
    }
    out = BUILDER.strip_v127_additions(payload)
    assert out["player"] == {"hp": 10}
    assert out["entities"]["materials"] == [{"x": 1.0}]
    assert out["entities"]["enemies"] == [{"x": 2.0}]
    # original untouched
    assert payload["player"]["materials"] == 5


# --------------------------------------------------------------------------- #
# Split is by whole run, never by row
# --------------------------------------------------------------------------- #
def _entry(run_id: str, rows: int = 100, aliased: int = 0, zero: int = 0):
    return {
        "run_id": run_id,
        "counts": {
            "captures": rows,
            "unparseable_lines": 0,
            "dropped_no_human_block": 0,
            "dropped_zero_samples": 0,
            "dropped_encoding_fault": 0,
            "dropped_invalid": 0,
            "dropped_temporal_invalid": 0,
            "kept": rows,
            "kept_aliased": aliased,
            "kept_zero_vector": zero,
        },
        "direction_counts": {"E": rows},
    }


def _meta(mapping: dict[str, tuple[str, str]]):
    return {
        run_id: {"fixture_digest": fx, "fixture_file": f"{fx}.json",
                 "boss_entity": boss, "trials_file": "t.jsonl"}
        for run_id, (fx, boss) in mapping.items()
    }


def test_split_holds_out_whole_fixtures():
    """The defect this rebuild exists to fix: a fixture on BOTH sides."""
    entries = [_entry(f"r{i}") for i in range(6)]
    meta = _meta({
        "r0": ("fixA", "predator"), "r1": ("fixA", "predator"),
        "r2": ("fixA", "predator"), "r3": ("fixB", "predator"),
        "r4": ("fixC", "invoker"), "r5": ("fixD", "invoker"),
    })
    split = BUILDER.choose_split_by_fixture(entries, meta, val_fraction=0.15)
    assert not set(split["train_fixtures"]) & set(split["val_fixtures"])
    assert not set(split["train_ids"]) & set(split["val_ids"])
    assert set(split["train_ids"]) | set(split["val_ids"]) == {
        e["run_id"] for e in entries}
    # every val run's fixture appears NOWHERE in train
    train_fx = set(split["train_fixtures"])
    for run_id in split["val_ids"]:
        assert meta[run_id]["fixture_digest"] not in train_fx


def test_split_never_holds_out_the_largest_fixture():
    entries = [_entry(f"r{i}") for i in range(6)]
    meta = _meta({
        "r0": ("fixA", "predator"), "r1": ("fixA", "predator"),
        "r2": ("fixA", "predator"), "r3": ("fixB", "predator"),
        "r4": ("fixC", "invoker"), "r5": ("fixD", "invoker"),
    })
    split = BUILDER.choose_split_by_fixture(entries, meta, val_fraction=0.15)
    assert "fixA" in split["train_fixtures"]
    assert "fixA" not in split["val_fixtures"]


def test_split_keeps_every_boss_in_train():
    entries = [_entry(f"r{i}") for i in range(4)]
    meta = _meta({
        "r0": ("fixA", "predator"), "r1": ("fixB", "predator"),
        "r2": ("fixC", "invoker"), "r3": ("fixD", "invoker"),
    })
    split = BUILDER.choose_split_by_fixture(entries, meta, val_fraction=0.99)
    assert set(split["train_bosses"]) == {"invoker", "predator"}


def test_split_requires_fixture_provenance():
    entries = [_entry("r0"), _entry("r1")]
    meta = _meta({"r0": ("fixA", "predator")})  # r1 has none
    with pytest.raises(RuntimeError, match="NO fixture_digest"):
        BUILDER.choose_split_by_fixture(entries, meta)


def test_split_refuses_a_single_fixture_corpus():
    """Six runs of ONE fixture is exactly the old, useless split."""
    entries = [_entry(f"r{i}") for i in range(6)]
    meta = _meta({f"r{i}": ("fixA", "predator") for i in range(6)})
    with pytest.raises(RuntimeError, match="distinct fixture"):
        BUILDER.choose_split_by_fixture(entries, meta)


def test_forced_val_fixture_is_honoured_and_bounded():
    entries = [_entry(f"r{i}") for i in range(3)]
    meta = _meta({"r0": ("fixA", "p"), "r1": ("fixB", "p"), "r2": ("fixC", "p")})
    split = BUILDER.choose_split_by_fixture(
        entries, meta, forced_val_fixtures=["fixB"])
    assert split["val_fixtures"] == ["fixB"]
    assert split["val_ids"] == ["r1"]
    with pytest.raises(RuntimeError, match="not among contributing"):
        BUILDER.choose_split_by_fixture(entries, meta, forced_val_fixtures=["nope"])
    with pytest.raises(RuntimeError, match="no fixtures"):
        BUILDER.choose_split_by_fixture(
            entries, meta, forced_val_fixtures=["fixA", "fixB", "fixC"])


def test_group_label_stats_prints_every_denominator():
    entries = [
        dict(_entry("r0", rows=100, aliased=10, zero=5), mod_version="0.2.56"),
        dict(_entry("r1", rows=100, aliased=20, zero=5), mod_version="0.2.57"),
    ]
    stats = BUILDER.build_group_label_stats(
        entries, lambda e: e["mod_version"], "mod_version")
    assert [g["mod_version"] for g in stats] == ["0.2.56", "0.2.57"]
    assert stats[0]["kept"] == 100 and stats[0]["aliasing_rate"] == 0.10
    assert stats[1]["aliasing_rate"] == 0.20
    for g in stats:
        assert g["captures"] > 0 and g["runs"] == 1
        assert g["no_label_rate"] is not None


def test_load_trial_meta_rejects_conflicting_fixture(tmp_path):
    a = tmp_path / "a.jsonl"
    b = tmp_path / "b.jsonl"
    a.write_text(json.dumps({"run_id": "r0", "fixture_digest": "x"}) + "\n",
                 encoding="utf-8")
    b.write_text(json.dumps({"run_id": "r0", "fixture_digest": "y"}) + "\n",
                 encoding="utf-8")
    with pytest.raises(RuntimeError, match="conflicting fixture_digest"):
        BUILDER.load_trial_meta([a, b])
    assert BUILDER.load_trial_meta([a])["r0"]["fixture_digest"] == "x"


# --------------------------------------------------------------------------- #
# Loader: invariants + TRAIN-ONLY normalization
# --------------------------------------------------------------------------- #
SCHEMA_PATH = ROOT / "configs" / "wp2" / "observation_v1.yaml"
INPUT_CONFIG = ROOT / "configs" / "wp2" / "human_bc_input_v1.yaml"


def _write_shard(path: Path, n: int, fill: float, samples: int = 3) -> str:
    import yaml

    schema = yaml.safe_load(SCHEMA_PATH.read_text(encoding="utf-8"))
    arrays = {
        "global_features": np.full((n, 48), fill, dtype=np.float32),
        "capture_seq": np.arange(n, dtype=np.int32),
        "wave": np.full(n, 17, dtype=np.int32),
        "human_action": np.tile(np.array([[1.0, 0.0]], np.float32), (n, 1)),
        "human_samples": np.full(n, samples, dtype=np.int32),
        "human_aliased": np.zeros(n, dtype=bool),
    }
    for group, cfg in schema["groups"].items():
        cap = int(cfg["capacity"])
        arrays[f"entities_{group}"] = np.zeros((n, cap, 15), dtype=np.float32)
        arrays[f"mask_{group}"] = np.zeros((n, cap), dtype=np.float32)
    np.savez_compressed(path, **arrays)
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _build_fixture(tmp_path: Path, val_fill: float = 100.0, samples: int = 3) -> tuple[Path, Path]:
    import yaml

    schema_hash = hashlib.sha256(SCHEMA_PATH.read_bytes()).hexdigest().upper()
    dataset_dir = tmp_path / "ds"
    dataset_dir.mkdir()
    specs = [("r_train_a", 8, 1.0, 3), ("r_train_b", 6, 3.0, 3), ("r_val", 5, val_fill, samples)]
    hashes = {}
    for run_id, n, fill, smp in specs:
        hashes[run_id] = _write_shard(dataset_dir / f"{run_id}.npz", n, fill, smp)
    (dataset_dir / "manifest.json").write_text(
        json.dumps(
            {
                "observation_schema_hash": schema_hash,
                "runs": [
                    {"run_id": r, "shard_file": f"{r}.npz", "shard_sha256": hashes[r]}
                    for r, _, _, _ in specs
                ],
            }
        ),
        encoding="utf-8",
    )
    split_path = tmp_path / "split.yaml"
    split_path.write_text(
        yaml.safe_dump(
            {
                "split_id": "test_split",
                "observation_schema_hash": schema_hash,
                "split_by": "run",
                "train": [
                    {"run_id": r, "shard_file": f"{r}.npz", "shard_sha256": hashes[r]}
                    for r in ("r_train_a", "r_train_b")
                ],
                "validation": [
                    {"run_id": "r_val", "shard_file": "r_val.npz", "shard_sha256": hashes["r_val"]}
                ],
            }
        ),
        encoding="utf-8",
    )
    return dataset_dir, split_path


def test_loader_labels_come_from_human_action_and_dims_match():
    from trainer.data.bc_dataset import load_human_bc_dataset

    import tempfile

    with tempfile.TemporaryDirectory() as td:
        dataset_dir, split_path = _build_fixture(Path(td))
        ds = load_human_bc_dataset(dataset_dir, split_path, INPUT_CONFIG, SCHEMA_PATH)
        assert ds.train.size == 14 and ds.val.size == 5
        assert ds.train.globals.shape[1] == 40  # 48 - 8 excluded
        assert ds.train.actions.shape == (14, 2)
        assert np.allclose(ds.train.actions[:, 0], 1.0)
        assert ds.train.aliased.shape == (14,)
        assert ds.train.samples.shape == (14,)


def test_normalization_is_computed_on_train_only():
    from trainer.data.bc_dataset import load_human_bc_dataset

    import tempfile

    with tempfile.TemporaryDirectory() as td:
        # val is filled with 100.0; if it leaked into the stats the mean would
        # be pulled far above the train values (1.0 and 3.0).
        dataset_dir, split_path = _build_fixture(Path(td), val_fill=100.0)
        ds = load_human_bc_dataset(dataset_dir, split_path, INPUT_CONFIG, SCHEMA_PATH)
        expected_mean = (8 * 1.0 + 6 * 3.0) / 14
        assert np.allclose(ds.normalization.mean, expected_mean)
        assert not np.allclose(ds.normalization.mean, (8 + 18 + 500) / 19)
        assert (ds.normalization.std >= 1e-6).all()


def test_loader_rejects_a_shard_with_zero_sample_rows():
    from trainer.data.bc_dataset import BCDatasetError, load_human_bc_dataset

    import tempfile

    with tempfile.TemporaryDirectory() as td:
        dataset_dir, split_path = _build_fixture(Path(td), samples=0)
        with pytest.raises(BCDatasetError, match="samples <= 0"):
            load_human_bc_dataset(dataset_dir, split_path, INPUT_CONFIG, SCHEMA_PATH)


def test_loader_rejects_overlapping_train_val_runs():
    from trainer.data.bc_dataset import BCDatasetError, load_human_bc_dataset

    import tempfile
    import yaml

    with tempfile.TemporaryDirectory() as td:
        dataset_dir, split_path = _build_fixture(Path(td))
        cfg = yaml.safe_load(split_path.read_text(encoding="utf-8"))
        cfg["validation"].append(cfg["train"][0])
        split_path.write_text(yaml.safe_dump(cfg), encoding="utf-8")
        with pytest.raises(BCDatasetError, match="overlap"):
            load_human_bc_dataset(dataset_dir, split_path, INPUT_CONFIG, SCHEMA_PATH)


def test_loader_rejects_a_tampered_shard():
    from trainer.data.bc_dataset import BCDatasetError, load_human_bc_dataset

    import tempfile

    with tempfile.TemporaryDirectory() as td:
        dataset_dir, split_path = _build_fixture(Path(td))
        _write_shard(dataset_dir / "r_val.npz", 5, 999.0)
        with pytest.raises(BCDatasetError, match="sha256 mismatch"):
            load_human_bc_dataset(dataset_dir, split_path, INPUT_CONFIG, SCHEMA_PATH)


def test_input_config_excludes_teacher_action_and_names_the_human_label():
    import yaml

    cfg = yaml.safe_load(INPUT_CONFIG.read_text(encoding="utf-8"))
    assert cfg["label_source"] == "human_action"
    assert "teacher_action_x" in cfg["excluded_global_features"]
    assert "teacher_action_y" in cfg["excluded_global_features"]
    bc_v1 = yaml.safe_load((ROOT / "configs" / "wp2" / "bc_input_v1.yaml").read_text(encoding="utf-8"))
    # Identical observation, different label — the whole point of the variant.
    assert cfg["excluded_global_features"] == bc_v1["excluded_global_features"]
    assert cfg["observation_schema_hash"] == bc_v1["observation_schema_hash"]
