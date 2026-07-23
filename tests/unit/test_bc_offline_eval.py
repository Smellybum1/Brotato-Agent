"""CPU-only unit tests for the WP2 offline BC evaluation (trainer/evaluation/bc_offline).

Tiny synthetic tests — no real dataset, no GPU. They exercise the pure pieces:
checkpoint-hash verification, registry->model config reconstruction (prev-action
indices honored by name), the sanity-gate boolean logic, pairwise inter-seed
agreement math (a known rotation is recovered), seed-variance aggregation, and
the JSON/Markdown writers (parseable output).
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest
import torch

from trainer.evaluation.bc_offline import (
    BCOfflineEvalError,
    build_policy_config_from_registry,
    compute_gates,
    load_normalization_from_manifest,
    pairwise_pred_agreement,
    seed_variance_summary,
    verify_sha256,
    write_json_report,
    write_markdown_report,
)
from trainer.imitation.bc_training import _sha256_file
from trainer.models.bc_policy_v1 import BCPolicyV1


GLOBAL_DIM = 40
PREV_X, PREV_Y = 15, 16
ENTITY_DIM = 15


def _feature_names(prev_x: int = PREV_X, prev_y: int = PREV_Y, n: int = GLOBAL_DIM) -> list[str]:
    names = [f"g{i}" for i in range(n)]
    names[prev_x] = "previous_action_x"
    names[prev_y] = "previous_action_y"
    return names


# ---------------------------------------------------------------------------
# Checkpoint-hash verification
# ---------------------------------------------------------------------------
def test_verify_sha256_accepts_matching_and_rejects_mismatch(tmp_path):
    f = tmp_path / "blob.bin"
    f.write_bytes(b"behavior cloning bytes")
    good = _sha256_file(f)
    assert verify_sha256(f, good, "blob") == good
    assert verify_sha256(f, good.lower(), "blob") == good  # case-insensitive expected
    with pytest.raises(BCOfflineEvalError):
        verify_sha256(f, "0" * 64, "blob")


def test_verify_sha256_missing_file_errors(tmp_path):
    with pytest.raises(BCOfflineEvalError):
        verify_sha256(tmp_path / "nope.bin", "0" * 64, "blob")


# ---------------------------------------------------------------------------
# Registry -> model config reconstruction
# ---------------------------------------------------------------------------
def test_build_policy_config_reconstructs_dim_and_dropout():
    names = _feature_names()
    cfg = build_policy_config_from_registry({"previous_action_dropout_p": 0.1}, names)
    assert cfg.global_dim == GLOBAL_DIM
    assert cfg.prev_action_indices == (PREV_X, PREV_Y)
    assert cfg.previous_action_dropout_p == 0.1
    # The reconstructed model actually builds and runs at the resolved dim.
    model = BCPolicyV1(cfg).eval()
    g = torch.zeros(2, GLOBAL_DIM)
    ent = {s.name: torch.zeros(2, s.capacity, ENTITY_DIM) for s in cfg.group_specs}
    msk = {s.name: torch.ones(2, s.capacity) for s in cfg.group_specs}
    out = model(g, ent, msk)
    assert out.shape == (2, 2)


def test_build_policy_config_honors_prev_action_indices_by_name():
    # Place the prev-action columns off the model default (15,16); they must be
    # honored from the resolved feature names, not hardcoded.
    names = _feature_names(prev_x=3, prev_y=4)
    cfg = build_policy_config_from_registry({"previous_action_dropout_p": 0.0}, names)
    assert cfg.prev_action_indices == (3, 4)


def test_build_policy_config_missing_prev_action_errors():
    names = [f"g{i}" for i in range(GLOBAL_DIM)]  # no previous_action_x/y
    with pytest.raises(BCOfflineEvalError):
        build_policy_config_from_registry({}, names)


# ---------------------------------------------------------------------------
# Normalization manifest loading + hash verification
# ---------------------------------------------------------------------------
def test_load_normalization_from_manifest_verifies_hash(tmp_path):
    names = _feature_names()
    manifest = {
        "global_feature_names": names,
        "mean": [0.0] * GLOBAL_DIM,
        "std": [1.0] * GLOBAL_DIM,
        "split_id": "synth",
        "schema_hash": "X",
        "input_config_hash": "X",
        "split_config_hash": "X",
    }
    path = tmp_path / "normalization_manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    good = _sha256_file(path)
    norm = load_normalization_from_manifest(path, good, names)
    assert norm.mean.shape == (GLOBAL_DIM,)
    with pytest.raises(BCOfflineEvalError):
        load_normalization_from_manifest(path, "0" * 64, names)
    # Feature-name disagreement is a hard error even with a correct hash.
    with pytest.raises(BCOfflineEvalError):
        load_normalization_from_manifest(path, good, names[:-1] + ["different"])


# ---------------------------------------------------------------------------
# Sanity-gate boolean logic
# ---------------------------------------------------------------------------
def _m(median, mean):
    return {"median_angular_error_deg": median, "mean_angular_error_deg": mean}


def _gates(model, copy_overall, mean_dir, model_change, copy_change):
    return compute_gates(model, copy_overall, mean_dir, model_change, copy_change)


def test_gates_pass_when_model_loses_overall_median_but_wins_change_frames():
    # §7 case: model LOSES overall median to copy-previous (12 vs 4, persistence
    # artifact — not a gate), beats copy-previous on overall MEAN (20 vs 25) and
    # on change-frame median AND mean (7/9 vs 15/22), and beats mean-direction on
    # overall median AND mean. -> overall PASS.
    g = _gates(
        model=_m(12.0, 20.0),
        copy_overall=_m(4.0, 25.0),
        mean_dir=_m(86.0, 88.0),
        model_change=_m(7.0, 9.0),
        copy_change=_m(15.0, 22.0),
    )
    assert g["mean_direction_gate"] is True
    assert g["copy_previous_gate"] is True
    assert g["overall_pass"] is True
    # Overall-median loss to copy-previous is recorded but is NOT a gate.
    assert "beats_copy_previous_overall_median" not in g
    info = g["informational_overall_median"]
    assert info["model_median_deg"] == 12.0 and info["copy_previous_median_deg"] == 4.0
    assert "not a gate" in info["note"]


def test_gates_fail_when_model_loses_change_frame_mean():
    # Model wins change-frame median (7 < 15) but LOSES change-frame mean
    # (23 > 22) -> copy-previous gate fails -> overall FAIL, even though the
    # mean-direction gate passes and overall mean beats copy-previous.
    g = _gates(
        model=_m(12.0, 20.0),
        copy_overall=_m(4.0, 25.0),
        mean_dir=_m(86.0, 88.0),
        model_change=_m(7.0, 23.0),
        copy_change=_m(15.0, 22.0),
    )
    assert g["beats_copy_previous_median_change"] is True
    assert g["beats_copy_previous_mean_change"] is False
    assert g["copy_previous_gate"] is False
    assert g["mean_direction_gate"] is True
    assert g["overall_pass"] is False


def test_gates_fail_when_model_loses_overall_mean_to_copy_previous():
    # Overall MEAN vs copy-previous IS a gate: model 26 > copy 25 -> fail.
    g = _gates(
        model=_m(12.0, 26.0),
        copy_overall=_m(4.0, 25.0),
        mean_dir=_m(86.0, 88.0),
        model_change=_m(7.0, 9.0),
        copy_change=_m(15.0, 22.0),
    )
    assert g["beats_copy_previous_mean_overall"] is False
    assert g["copy_previous_gate"] is False
    assert g["overall_pass"] is False


def test_gates_fail_when_model_loses_to_mean_direction():
    # Loses mean-direction on mean (89 > 88) -> mean-direction gate fails.
    g = _gates(
        model=_m(12.0, 89.0),
        copy_overall=_m(4.0, 95.0),
        mean_dir=_m(86.0, 88.0),
        model_change=_m(7.0, 9.0),
        copy_change=_m(15.0, 22.0),
    )
    assert g["beats_mean_direction_mean"] is False
    assert g["mean_direction_gate"] is False
    assert g["overall_pass"] is False


def test_gates_are_strict_no_tie_on_change_frames():
    # Equal change-frame median is NOT beating (strict <).
    g = _gates(
        model=_m(12.0, 20.0),
        copy_overall=_m(4.0, 25.0),
        mean_dir=_m(86.0, 88.0),
        model_change=_m(15.0, 9.0),
        copy_change=_m(15.0, 22.0),
    )
    assert g["beats_copy_previous_median_change"] is False
    assert g["copy_previous_gate"] is False


# ---------------------------------------------------------------------------
# Pairwise inter-seed agreement math
# ---------------------------------------------------------------------------
def _rotate(vectors: torch.Tensor, deg: float) -> torch.Tensor:
    r = math.radians(deg)
    rot = torch.tensor([[math.cos(r), -math.sin(r)], [math.sin(r), math.cos(r)]], dtype=vectors.dtype)
    return vectors @ rot.T


def test_pairwise_agreement_recovers_known_rotation():
    g = torch.Generator().manual_seed(3)
    base = torch.randn(500, 2, generator=g)
    base = base / base.norm(dim=-1, keepdim=True)  # unit vectors, all "moving"
    rotated = _rotate(base, 12.0)
    out = pairwise_pred_agreement(base, rotated)
    assert out["n"] == 500
    assert math.isclose(out["median_angular_diff_deg"], 12.0, abs_tol=1e-3)
    assert math.isclose(out["mean_angular_diff_deg"], 12.0, abs_tol=1e-3)


def test_pairwise_agreement_identical_predictions_zero():
    g = torch.Generator().manual_seed(9)
    base = torch.randn(64, 2, generator=g)
    base = base / base.norm(dim=-1, keepdim=True)
    out = pairwise_pred_agreement(base, base.clone())
    assert math.isclose(out["median_angular_diff_deg"], 0.0, abs_tol=1e-4)


def test_pairwise_agreement_excludes_degenerate_predictions():
    a = torch.tensor([[1.0, 0.0], [0.0, 0.0], [0.0, 1.0]])
    b = torch.tensor([[1.0, 0.0], [1.0, 0.0], [0.0, 0.0]])
    # Sample 0: both moving, 0°. Sample 1: a degenerate. Sample 2: b degenerate.
    out = pairwise_pred_agreement(a, b, mag_eps=0.01)
    assert out["n"] == 1
    assert math.isclose(out["median_angular_diff_deg"], 0.0, abs_tol=1e-4)


def test_pairwise_agreement_valid_mask_restricts_samples():
    g = torch.Generator().manual_seed(1)
    base = torch.randn(10, 2, generator=g)
    base = base / base.norm(dim=-1, keepdim=True)
    rotated = _rotate(base, 5.0)
    mask = torch.zeros(10, dtype=torch.bool)
    mask[:4] = True
    out = pairwise_pred_agreement(base, rotated, valid_mask=mask)
    assert out["n"] == 4


# ---------------------------------------------------------------------------
# Seed variance
# ---------------------------------------------------------------------------
def test_seed_variance_summary_stats():
    runs = [
        {"median_angular_error_deg": 10.0, "mean_angular_error_deg": 20.0, "mean_cosine": 0.9,
         "mean_abs_magnitude_error": 0.1, "saturation_fraction": 0.0, "val_loss": 0.2},
        {"median_angular_error_deg": 14.0, "mean_angular_error_deg": 24.0, "mean_cosine": 0.8,
         "mean_abs_magnitude_error": 0.2, "saturation_fraction": 0.0, "val_loss": 0.3},
    ]
    summary = seed_variance_summary(runs)
    assert math.isclose(summary["median_angular_error_deg"]["mean"], 12.0)
    assert math.isclose(summary["median_angular_error_deg"]["min"], 10.0)
    assert math.isclose(summary["median_angular_error_deg"]["max"], 14.0)
    assert math.isclose(summary["median_angular_error_deg"]["std"], 2.0)  # population std
    assert summary["median_angular_error_deg"]["n"] == 2


def test_seed_variance_ignores_nan():
    runs = [
        {"median_angular_error_deg": 10.0},
        {"median_angular_error_deg": float("nan")},
    ]
    summary = seed_variance_summary(runs, keys=("median_angular_error_deg",))
    assert summary["median_angular_error_deg"]["n"] == 1
    assert math.isclose(summary["median_angular_error_deg"]["mean"], 10.0)


# ---------------------------------------------------------------------------
# Report writers
# ---------------------------------------------------------------------------
def _synthetic_run(name: str, seed: int, median: float, mean: float) -> dict:
    strat = {
        "n": 100, "n_direction": 100, "median_angular_error_deg": median,
        "mean_angular_error_deg": mean, "mean_cosine": 0.85,
        "mean_abs_magnitude_error": 0.12, "saturation_fraction": 0.0,
    }
    overall = dict(strat, val_loss=0.2, val_direction_term=0.18, val_magnitude_term=0.02)
    change_1 = {
        "n": 60, "threshold_deg": 1.0,
        "model_median_deg": 7.0, "model_mean_deg": 12.0,
        "copy_previous_median_deg": 15.0, "copy_previous_mean_deg": 22.0,
    }
    change_15 = {
        "n": 20, "threshold_deg": 15.0,
        "model_median_deg": 22.0, "model_mean_deg": 30.0,
        "copy_previous_median_deg": 105.0, "copy_previous_mean_deg": 100.0,
    }
    gates = compute_gates(
        overall,
        {"median_angular_error_deg": 4.0, "mean_angular_error_deg": 25.0},
        {"median_angular_error_deg": 80.0, "mean_angular_error_deg": 85.0},
        {"median_angular_error_deg": 7.0, "mean_angular_error_deg": 12.0},
        {"median_angular_error_deg": 15.0, "mean_angular_error_deg": 22.0},
    )
    return {
        "run_name": name, "seed": seed, "checkpoint": "best",
        "overall": overall,
        "by_wave_band": {"1-5": strat, "20": {"n": 0}},
        "by_risk_stratum": {"0.00-0.25": strat},
        "by_val_run": {"run_x": dict(strat, outcome="victory", last_wave=20)},
        "baselines": {
            "mean_direction": dict(strat, median_angular_error_deg=80.0, mean_angular_error_deg=85.0),
            "copy_previous": dict(strat, median_angular_error_deg=4.0, mean_angular_error_deg=25.0),
        },
        "change_frames": {"threshold_1deg": change_1, "threshold_15deg": change_15},
        "gates": gates,
    }


def _payload(runs: list[dict]) -> dict:
    variance = seed_variance_summary([r["overall"] for r in runs]) if len(runs) > 1 else None
    return {
        "report": "bc_offline_eval", "out_tag": "unit", "generated": "2026-07-24 00:00:00",
        "checkpoint": "best", "device": "cpu", "n_runs": len(runs), "runs": runs,
        "seed_variance": variance, "inter_seed_agreement": [],
    }


def test_json_writer_roundtrips(tmp_path):
    payload = _payload([_synthetic_run("r1", 1, 10.0, 20.0)])
    path = tmp_path / "eval.json"
    write_json_report(path, payload)
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded["runs"][0]["run_name"] == "r1"
    assert loaded["runs"][0]["gates"]["overall_pass"] is True


def test_markdown_writer_produces_expected_sections(tmp_path):
    runs = [_synthetic_run("r1", 1, 10.0, 20.0), _synthetic_run("r2", 2, 12.0, 22.0)]
    payload = _payload(runs)
    payload["inter_seed_agreement"] = [
        {"run_a": "r1", "run_b": "r2", "n": 100, "median_angular_diff_deg": 3.0, "mean_angular_diff_deg": 4.0}
    ]
    path = tmp_path / "eval.md"
    write_markdown_report(path, payload)
    text = path.read_text(encoding="utf-8")
    assert "# BC offline evaluation" in text
    assert "## Sanity gates" in text
    assert "## Direction-change frames" in text
    assert "≥1° (gate)" in text
    assert "≥15° (diag)" in text
    assert "not a gate (persistence artifact" in text
    assert "## Overall validation metrics" in text
    assert "## Seed variance" in text
    assert "## Inter-seed agreement" in text
    assert "By validation run" in text
    assert "PASS" in text
    # Every table row is pipe-delimited and non-empty.
    for line in text.splitlines():
        if line.startswith("|"):
            assert line.rstrip().endswith("|")
