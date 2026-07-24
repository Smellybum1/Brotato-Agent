"""ONNX export tooling for WP2 Stage G (packet §14.1).

Exports the frozen bc_v1 :class:`~trainer.models.bc_policy_v1.BCPolicyV1` policy
to a static batch-1 ONNX graph and records a tracked registry manifest linking
the ONNX artifact to its parent ``best.pt`` checkpoint. The parity harness
(:mod:`scripts.wp2_onnx_parity`) fills in the manifest ``parity`` block.
"""
from __future__ import annotations

from trainer.export.onnx_export import (
    ExportResult,
    OnnxExportError,
    build_onnx_registry_manifest,
    example_inputs,
    export_bc_policy_to_onnx,
    input_names_for,
    output_name,
)

__all__ = [
    "ExportResult",
    "OnnxExportError",
    "build_onnx_registry_manifest",
    "example_inputs",
    "export_bc_policy_to_onnx",
    "input_names_for",
    "output_name",
]
