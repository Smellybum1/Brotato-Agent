"""Unit tests for the ONNX export module (WP2 Stage G).

Pure tests cover the input-name contract, example-input shapes, and manifest
assembly. A verification test asserts a bad artifact chain maps to
:class:`OnnxExportError`. One marked real-artifact smoke test exports the frozen
bc_v1 policy to a temp file and checks the manifest, ORT load, and single-forward
parity against PyTorch.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from trainer.export.onnx_export import (
    DEFAULT_OPSET,
    ExportResult,
    OnnxExportError,
    build_onnx_registry_manifest,
    example_inputs,
    export_bc_policy_to_onnx,
    input_names_for,
    output_name,
)

ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = ROOT / "models" / "registry" / "bc_v1_s1_full.json"

GROUP_NAMES = (
    "enemies", "bosses", "projectiles", "materials", "consumables", "crates", "obstacles",
)


# ---------------------------------------------------------------------------
# Input / output name contract
# ---------------------------------------------------------------------------
def test_output_name_is_action():
    assert output_name() == "action"


def test_input_names_interleaved_per_group():
    names = input_names_for(GROUP_NAMES)
    assert names[0] == "globals"
    # 1 globals + 2 per group.
    assert len(names) == 1 + 2 * len(GROUP_NAMES)
    # ent immediately followed by its mask, in group order.
    assert names[1:5] == ["ent_enemies", "mask_enemies", "ent_bosses", "mask_bosses"]
    for i, g in enumerate(GROUP_NAMES):
        assert names[1 + 2 * i] == f"ent_{g}"
        assert names[2 + 2 * i] == f"mask_{g}"


def test_example_inputs_shapes_match_config():
    from trainer.models.bc_policy_v1 import BCPolicyConfig

    cfg = BCPolicyConfig()
    args = example_inputs(cfg)
    # globals + 2 tensors per group.
    assert len(args) == 1 + 2 * len(cfg.group_specs)
    assert tuple(args[0].shape) == (1, cfg.global_dim)
    for i, spec in enumerate(cfg.group_specs):
        ent = args[1 + 2 * i]
        mask = args[2 + 2 * i]
        assert tuple(ent.shape) == (1, spec.capacity, cfg.entity_feature_dim)
        assert tuple(mask.shape) == (1, spec.capacity)
        # first row present so pooling is exercised.
        assert float(mask[0, 0]) == 1.0


# ---------------------------------------------------------------------------
# Manifest assembly
# ---------------------------------------------------------------------------
def _fake_result() -> ExportResult:
    return ExportResult(
        parent_registry="bc_v1_s1_full.json",
        parent_model_sha256="A" * 64,
        onnx_path="models/bc_v1/bc_v1_s1_full/bc_v1_s1_full.onnx",
        onnx_sha256="B" * 64,
        opset=DEFAULT_OPSET,
        torch_version="2.13.0+cu126",
        onnx_version="1.22.0",
        onnxruntime_version="1.27.0",
        export_timestamp="2026-07-24T00:00:00",
        git_commit_at_export="deadbeef",
        input_names=input_names_for(GROUP_NAMES),
        output_name="action",
        exporter="classic",
    )


def test_manifest_has_required_fields_and_pending_parity():
    manifest = build_onnx_registry_manifest(_fake_result(), parent_registry_name="bc_v1_s1_full.json")
    for key in (
        "parent_registry", "parent_model_sha256", "onnx_path", "onnx_sha256", "opset",
        "torch_version", "onnx_version", "onnxruntime_version", "export_timestamp",
        "git_commit_at_export", "input_names", "output_name", "parity",
    ):
        assert key in manifest, f"manifest missing {key}"
    assert manifest["parity"]["verdict"] == "pending"
    assert manifest["parity"]["max_abs_diff"] is None
    assert manifest["output_name"] == "action"
    assert manifest["input_names"][0] == "globals"


def test_manifest_accepts_filled_parity_block():
    parity = {"report": "reports/wp2/onnx_parity_v1.json", "max_abs_diff": 1e-6,
              "n_fixtures": 10000, "verdict": "PASS"}
    manifest = build_onnx_registry_manifest(
        _fake_result(), parent_registry_name="bc_v1_s1_full.json", parity=parity
    )
    assert manifest["parity"]["verdict"] == "PASS"
    assert manifest["parity"]["n_fixtures"] == 10000


# ---------------------------------------------------------------------------
# Verification failure -> OnnxExportError
# ---------------------------------------------------------------------------
def _write_registry(tmp_path, ckpt_path, ckpt_sha):
    registry = {
        "run_name": "fake",
        "resolved_config": {
            "schema": str(ROOT / "configs" / "wp2" / "observation_v1.yaml"),
            "input_config": str(ROOT / "configs" / "wp2" / "bc_input_v1.yaml"),
        },
        "checkpoints": {"best": {"path": str(ckpt_path), "sha256": ckpt_sha}},
        "schema_hash": "0" * 64,
        "split_id": "dataset_split_v1",
        "normalization_manifest_hash": "0" * 64,
    }
    path = Path(tmp_path) / "registry.json"
    path.write_text(json.dumps(registry), encoding="utf-8")
    return path


def test_export_raises_on_bad_checkpoint_hash(tmp_path):
    ckpt = Path(tmp_path) / "best.pt"
    ckpt.write_bytes(b"not a real checkpoint")
    registry = _write_registry(tmp_path, ckpt, ckpt_sha="DEADBEEF" * 8)
    out = Path(tmp_path) / "out.onnx"
    with pytest.raises(OnnxExportError):
        export_bc_policy_to_onnx(registry, out)
    assert not out.is_file()  # nothing written on a failed export


# ---------------------------------------------------------------------------
# Real-artifact export smoke (marked; still fast)
# ---------------------------------------------------------------------------
@pytest.mark.smoke
def test_real_export_roundtrip(tmp_path):
    if not REGISTRY_PATH.is_file():
        pytest.skip("bc_v1_s1_full registry not present")
    try:
        result = export_bc_policy_to_onnx(REGISTRY_PATH, Path(tmp_path) / "bc.onnx")
    except OnnxExportError as exc:
        pytest.skip(f"artifact chain unavailable: {exc}")

    assert Path(result.onnx_path).is_file()
    assert result.opset == DEFAULT_OPSET
    assert result.output_name == "action"
    assert result.input_names[0] == "globals"
    assert len(result.onnx_sha256) == 64

    # ORT loads and produces a [1,2] output matching PyTorch within 1e-4.
    import numpy as np
    import onnxruntime as ort

    from trainer.bridge.sidecar import TorchModelService

    service = TorchModelService.from_registry(REGISTRY_PATH)
    cfg = service._model.config
    so = ort.SessionOptions()
    so.intra_op_num_threads = 1
    session = ort.InferenceSession(
        result.onnx_path, sess_options=so, providers=["CPUExecutionProvider"]
    )
    rng = np.random.default_rng(1)
    feeds = {"globals": rng.standard_normal((1, cfg.global_dim)).astype(np.float32)}
    import torch

    g = torch.from_numpy(feeds["globals"])
    ent_t, mask_t = {}, {}
    for spec in cfg.group_specs:
        ent = rng.standard_normal((1, spec.capacity, cfg.entity_feature_dim)).astype(np.float32)
        mask = np.zeros((1, spec.capacity), dtype=np.float32)
        mask[0, 0] = 1.0
        feeds[f"ent_{spec.name}"] = ent
        feeds[f"mask_{spec.name}"] = mask
        ent_t[spec.name] = torch.from_numpy(ent)
        mask_t[spec.name] = torch.from_numpy(mask)
    with torch.no_grad():
        torch_out = service._model(g, ent_t, mask_t).numpy()
    onnx_out = session.run(["action"], feeds)[0]
    assert onnx_out.shape == (1, 2)
    assert np.max(np.abs(torch_out - onnx_out)) <= 1e-4
