"""Non-interactive ONNX export for the bc_v1 student policy (packet §14.1).

Loads + sha-verifies the frozen bc_v1 policy from its registry manifest, exports
a static batch-1 ONNX graph to the gitignored model directory, and writes the
tracked ONNX registry manifest (``models/registry/bc_v1_s1_full_onnx.json``) with
a ``parity: {verdict: pending}`` placeholder. Run ``scripts/wp2_onnx_parity.py``
afterward to fill in the parity block.

Exit codes:
    0  export + structural/ORT-load validation succeeded
    1  usage / unexpected error
    2  artifact load, export, or validation failure

Usage:
    .venv/Scripts/python.exe scripts/export_onnx.py
    .venv/Scripts/python.exe scripts/export_onnx.py --opset 18
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from trainer.export.onnx_export import (  # noqa: E402
    DEFAULT_OPSET,
    OnnxExportError,
    build_onnx_registry_manifest,
    export_bc_policy_to_onnx,
)

DEFAULT_REGISTRY = REPO_ROOT / "models" / "registry" / "bc_v1_s1_full.json"
DEFAULT_ONNX_OUT = REPO_ROOT / "models" / "bc_v1" / "bc_v1_s1_full" / "bc_v1_s1_full.onnx"
DEFAULT_ONNX_REGISTRY = REPO_ROOT / "models" / "registry" / "bc_v1_s1_full_onnx.json"


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export the bc_v1 policy to ONNX.")
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY))
    parser.add_argument("--out", default=str(DEFAULT_ONNX_OUT), help="ONNX output path (gitignored dir)")
    parser.add_argument("--onnx-registry", default=str(DEFAULT_ONNX_REGISTRY))
    parser.add_argument("--opset", type=int, default=DEFAULT_OPSET)
    parser.add_argument("--checkpoint", choices=("best", "last"), default="best")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    registry_path = Path(args.registry)
    parent_registry_name = registry_path.name

    try:
        result = export_bc_policy_to_onnx(
            registry_path, Path(args.out), opset=args.opset, checkpoint=args.checkpoint
        )
    except OnnxExportError as exc:
        print(f"export error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # pragma: no cover - unexpected fault
        print(f"unexpected error: {exc}", file=sys.stderr)
        return 1

    manifest = build_onnx_registry_manifest(result, parent_registry_name=parent_registry_name)
    onnx_registry_path = Path(args.onnx_registry)
    onnx_registry_path.parent.mkdir(parents=True, exist_ok=True)
    onnx_registry_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    print(
        f"[export] wrote ONNX {result.onnx_path} "
        f"(sha {result.onnx_sha256[:12]}, opset {result.opset}, exporter {result.exporter})"
    )
    print(
        f"[export] parent best.pt sha {result.parent_model_sha256[:12]} | "
        f"torch {result.torch_version} | onnx {result.onnx_version} | ort {result.onnxruntime_version}"
    )
    print(f"[export] manifest {onnx_registry_path} (parity: pending)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
