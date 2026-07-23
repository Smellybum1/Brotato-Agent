"""Unit tests for the combat_obs_v1 dataset build pipeline.

Uses the frozen v122 exact-20 violation fixture as a real payload source and
builds a tiny synthetic run dir (events.jsonl) to exercise shard round-trip,
manifest checksums, gate arithmetic, and fault propagation.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import numpy as np
import pytest

from trainer.observation.encoder_v1 import encode_capture, load_schema
from scripts.wp2_build_combat_obs_v1 import (
    ALL_WAVES,
    VALID_MIN,
    build_run,
    evaluate_gates,
    iter_capture_payloads,
    sha256_file,
)

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "configs" / "wp2" / "observation_v1.yaml"
FIXTURE_PATH = ROOT / "tests" / "fixtures" / "wp2" / "v122_exact20_viol_a_1784787688.json"


@pytest.fixture
def schema():
    return load_schema(SCHEMA_PATH)


@pytest.fixture
def fixture_payloads():
    """Real combat_capture payloads (event-wrapped) from the frozen fixture, in capture_seq order."""
    data = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    captures = data["captures"]
    return [captures[key]["payload"] for key in sorted(captures, key=int)]


def _write_events(events_path: Path, payloads) -> None:
    """Write a synthetic events.jsonl: a run_start line, the capture lines, a non-capture line."""
    lines = [json.dumps({"event": "run_start", "run_id": "syn"})]
    for payload in payloads:
        lines.append(
            json.dumps(
                {
                    "schema_version": 1,
                    "run_id": "syn",
                    "seq": payload.get("capture_seq"),
                    "ts_ms": 0,
                    "event": "combat_capture",
                    "payload": payload,
                }
            )
        )
    lines.append(json.dumps({"event": "combat_tick"}))
    events_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_iter_capture_payloads_filters_non_captures(tmp_path, fixture_payloads):
    events = tmp_path / "events.jsonl"
    _write_events(events, fixture_payloads)
    got = list(iter_capture_payloads(events))
    assert len(got) == len(fixture_payloads)
    assert all(p.get("capture_seq") is not None for p in got)


def test_shard_round_trip_matches_encoder(tmp_path, schema, fixture_payloads):
    run_dir = tmp_path / "run_syn"
    run_dir.mkdir()
    _write_events(run_dir / "events.jsonl", fixture_payloads)

    dataset_dir = tmp_path / "ds"
    entry = build_run("run_syn", run_dir / "events.jsonl", schema, dataset_dir)

    shard = dataset_dir / entry["shard_file"]
    assert shard.exists()
    npz = np.load(shard)

    # Shard rows are in capture_seq order. Encode each payload directly and compare.
    ordered = sorted(fixture_payloads, key=lambda p: int(p["capture_seq"]))
    assert list(npz["capture_seq"]) == [int(p["capture_seq"]) for p in ordered]

    for i, payload in enumerate(ordered):
        enc = encode_capture(payload, schema)
        np.testing.assert_array_equal(
            npz["global_features"][i], np.asarray(enc.global_features, dtype=np.float32)
        )
        for group in schema["groups"]:
            np.testing.assert_array_equal(
                npz[f"entities_{group}"][i], np.asarray(enc.entities[group], dtype=np.float32)
            )
            np.testing.assert_array_equal(
                npz[f"mask_{group}"][i], np.asarray(enc.masks[group], dtype=np.float32)
            )
            assert npz[f"dropped_{group}"][i] == enc.dropped_counts[group]
        assert bool(npz["valid"][i]) == enc.valid
        assert bool(npz["temporal_valid"][i]) == enc.temporal_valid


def test_manifest_checksum_correctness(tmp_path, schema, fixture_payloads):
    run_dir = tmp_path / "run_syn"
    run_dir.mkdir()
    _write_events(run_dir / "events.jsonl", fixture_payloads)
    dataset_dir = tmp_path / "ds"
    entry = build_run("run_syn", run_dir / "events.jsonl", schema, dataset_dir)

    shard = dataset_dir / entry["shard_file"]
    assert entry["shard_sha256"] == sha256_file(shard)
    assert entry["shard_bytes"] == shard.stat().st_size
    assert entry["counts"]["total"] == len(fixture_payloads)
    # Determinism spot-check present and re-runnable: first entry position 0.
    assert entry["determinism_spot_check"][0]["position"] == 0


def test_fault_propagation_records_and_skips(tmp_path, schema, fixture_payloads):
    payloads = copy.deepcopy(fixture_payloads)
    # Corrupt one payload's capture schema hash -> encoder raises ObservationError.
    corrupt_seq = int(payloads[1]["capture_seq"])
    payloads[1]["capture_schema_hash"] = "0" * 64

    run_dir = tmp_path / "run_syn"
    run_dir.mkdir()
    _write_events(run_dir / "events.jsonl", payloads)
    dataset_dir = tmp_path / "ds"
    entry = build_run("run_syn", run_dir / "events.jsonl", schema, dataset_dir)

    assert entry["fault_count"] == 1
    fault = entry["faults"][0]
    assert fault["capture_seq"] == corrupt_seq
    assert "schema hash mismatch" in fault["error"]
    # Faulted sample is skipped: total is one fewer than input.
    assert entry["counts"]["total"] == len(payloads) - 1
    npz = np.load(dataset_dir / entry["shard_file"])
    assert corrupt_seq not in list(npz["capture_seq"])


def test_gate_arithmetic_threshold_and_wave_coverage():
    full_waves = {w: 100 for w in ALL_WAVES}

    # PASS case: at/above 200k, all waves present, no faults, all shards.
    gates = evaluate_gates(VALID_MIN, full_waves, fault_count=0, shards_written=20, shards_expected=20)
    by_name = {g["name"]: g for g in gates}
    assert by_name["valid_and_temporal_valid_min"]["status"] == "PASS"
    assert by_name["all_waves_1_20_represented"]["status"] == "PASS"
    assert by_name["zero_encoding_faults"]["status"] == "PASS"
    assert by_name["all_shards_written"]["status"] == "PASS"

    # FAIL: one under threshold, missing a wave, a fault, a missing shard.
    missing = dict(full_waves)
    del missing[13]
    gates = evaluate_gates(VALID_MIN - 1, missing, fault_count=2, shards_written=19, shards_expected=20)
    by_name = {g["name"]: g for g in gates}
    assert by_name["valid_and_temporal_valid_min"]["status"] == "FAIL"
    assert by_name["all_waves_1_20_represented"]["status"] == "FAIL"
    assert by_name["all_waves_1_20_represented"]["missing_waves"] == [13]
    assert by_name["zero_encoding_faults"]["status"] == "FAIL"
    assert by_name["all_shards_written"]["status"] == "FAIL"


def test_gate_tail_fraction_arithmetic():
    # 4 tail waves at 25 each = 100 valid in tail; other 16 waves at 50 = 800; total 900.
    waves = {w: (25 if w >= 17 else 50) for w in ALL_WAVES}
    gates = evaluate_gates(300_000, waves, fault_count=0, shards_written=20, shards_expected=20)
    wave_gate = next(g for g in gates if g["name"] == "all_waves_1_20_represented")
    total_valid = sum(waves.values())
    assert wave_gate["tail_waves_17_20_valid"] == 100
    assert wave_gate["tail_fraction"] == pytest.approx(100 / total_valid, rel=1e-6)
