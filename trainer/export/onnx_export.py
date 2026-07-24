"""Classic ``torch.onnx.export`` of the bc_v1 policy (packet §14.1).

Exports a sha-verified :class:`BCPolicyV1` (loaded from a registry manifest) to a
static batch-1 ONNX graph. The model's ``forward`` takes a globals tensor plus
two ``dict[name -> Tensor]`` (entities, masks); ONNX graphs take positional
tensor inputs only, so a thin :class:`_FlatBCPolicy` wrapper re-packs a flat
positional argument list into those dicts. The wrapper changes no math.

Input contract (static shapes, batch 1), in ``cfg.group_specs`` order:

    globals        [1, global_dim]  float32
    ent_<name>     [1, cap, 15]     float32   (per group, interleaved with mask)
    mask_<name>    [1, cap]         float32

Single output ``action`` [1, 2] in [-1, 1]. Nothing here duplicates the
verified artifact-chain load — that is reused from
:meth:`trainer.bridge.sidecar.TorchModelService.from_registry`.
"""
from __future__ import annotations

import hashlib
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

OUTPUT_NAME = "action"
DEFAULT_OPSET = 18


class OnnxExportError(RuntimeError):
    """Raised when ONNX export or its post-export validation fails."""


@dataclass(frozen=True)
class ExportResult:
    """Everything needed to write the tracked ONNX registry manifest."""

    parent_registry: str
    parent_model_sha256: str
    onnx_path: str
    onnx_sha256: str
    opset: int
    torch_version: str
    onnx_version: str
    onnxruntime_version: str
    export_timestamp: str
    git_commit_at_export: str
    input_names: list[str]
    output_name: str
    exporter: str


def output_name() -> str:
    """The single graph output name."""
    return OUTPUT_NAME


def input_names_for(group_names: tuple[str, ...]) -> list[str]:
    """Ordered ONNX input names: ``globals`` then ``ent_/mask_`` per group.

    The per-group inputs are interleaved (``ent_<g>`` immediately followed by
    ``mask_<g>``) in ``group_names`` order — this order is the graph's input
    contract and must match the positional argument order the wrapper is traced
    with and the order the sidecar feeds ONNX Runtime.
    """
    names = ["globals"]
    for name in group_names:
        names.append(f"ent_{name}")
        names.append(f"mask_{name}")
    return names


def example_inputs(policy_config: Any) -> tuple[Any, ...]:
    """Build a positional example-input tuple matching :func:`input_names_for`.

    Deterministic small values with the first entity of every group present, so
    the traced graph exercises the populated pooling path (empty-group pooling is
    a data-dependent branchless op, captured either way).
    """
    import numpy as np
    import torch

    rng = np.random.default_rng(0)
    cfg = policy_config
    args: list[Any] = [
        torch.from_numpy(rng.standard_normal((1, cfg.global_dim)).astype(np.float32))
    ]
    for spec in cfg.group_specs:
        ent = rng.standard_normal((1, spec.capacity, cfg.entity_feature_dim)).astype(np.float32)
        mask = np.zeros((1, spec.capacity), dtype=np.float32)
        mask[0, 0] = 1.0  # at least one present row so mean/max pooling is populated
        args.append(torch.from_numpy(ent))
        args.append(torch.from_numpy(mask))
    return tuple(args)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _git_commit() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=str(Path(__file__).resolve().parents[2]),
        )
        commit = out.stdout.strip()
        return commit or "unknown"
    except Exception:
        return "unknown"


def _build_flat_wrapper(model: Any, group_names: tuple[str, ...]) -> Any:
    import torch
    from torch import nn

    class _FlatBCPolicy(nn.Module):
        """Adapts BCPolicyV1's dict inputs to a flat positional ONNX signature."""

        def __init__(self, inner: nn.Module, names: tuple[str, ...]) -> None:
            super().__init__()
            self.inner = inner
            self._names = names

        def forward(self, globals_t: torch.Tensor, *group_tensors: torch.Tensor) -> torch.Tensor:
            entities: dict[str, torch.Tensor] = {}
            masks: dict[str, torch.Tensor] = {}
            for i, name in enumerate(self._names):
                entities[name] = group_tensors[2 * i]
                masks[name] = group_tensors[2 * i + 1]
            return self.inner(globals_t, entities, masks)

    wrapper = _FlatBCPolicy(model, group_names)
    wrapper.eval()
    return wrapper


def export_bc_policy_to_onnx(
    registry_path: str | Path,
    onnx_path: str | Path,
    *,
    opset: int = DEFAULT_OPSET,
    checkpoint: str = "best",
) -> ExportResult:
    """Load + sha-verify the policy from ``registry_path`` and export it to ONNX.

    Uses the classic (TorchScript-tracing) exporter with static batch-1 inputs.
    After export the graph is structurally checked (``onnx.checker``) and loaded
    into an ONNX Runtime CPU session as a smoke test; either failing raises
    :class:`OnnxExportError`. Returns an :class:`ExportResult` for the manifest.
    """
    import onnx
    import onnxruntime as ort
    import torch

    from trainer.bridge.sidecar import SidecarStartupError, TorchModelService

    registry_path = Path(registry_path)
    onnx_path = Path(onnx_path)
    onnx_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        service = TorchModelService.from_registry(registry_path, checkpoint=checkpoint)
    except SidecarStartupError as exc:
        raise OnnxExportError(f"artifact chain failed to load/verify: {exc}") from exc

    model = service._model
    group_names = service._group_names
    policy_config = model.config

    model.eval()
    torch.set_num_threads(1)
    wrapper = _build_flat_wrapper(model, group_names)
    args = example_inputs(policy_config)
    names = input_names_for(group_names)

    exporter = "classic"
    try:
        with torch.no_grad():
            torch.onnx.export(
                wrapper,
                args,
                str(onnx_path),
                input_names=names,
                output_names=[OUTPUT_NAME],
                opset_version=opset,
                do_constant_folding=True,
                dynamo=False,
            )
    except Exception as exc:  # classic exporter fault — surface loudly
        raise OnnxExportError(f"torch.onnx.export (classic, opset {opset}) failed: {exc}") from exc

    # Structural validation + ORT load smoke test.
    try:
        onnx_model = onnx.load(str(onnx_path))
        onnx.checker.check_model(onnx_model)
    except Exception as exc:
        raise OnnxExportError(f"onnx.checker rejected the exported graph: {exc}") from exc

    try:
        so = ort.SessionOptions()
        so.intra_op_num_threads = 1
        session = ort.InferenceSession(
            str(onnx_path), sess_options=so, providers=["CPUExecutionProvider"]
        )
        got_inputs = [i.name for i in session.get_inputs()]
        got_outputs = [o.name for o in session.get_outputs()]
    except Exception as exc:
        raise OnnxExportError(f"onnxruntime could not load the exported graph: {exc}") from exc

    if got_inputs != names:
        raise OnnxExportError(
            f"exported input names {got_inputs} != expected {names}"
        )
    if got_outputs != [OUTPUT_NAME]:
        raise OnnxExportError(
            f"exported output names {got_outputs} != expected {[OUTPUT_NAME]}"
        )

    onnx_sha = _sha256_file(onnx_path)
    return ExportResult(
        parent_registry=str(registry_path),
        parent_model_sha256=service.identity.model_sha256,
        onnx_path=str(onnx_path),
        onnx_sha256=onnx_sha,
        opset=int(opset),
        torch_version=str(torch.__version__),
        onnx_version=str(onnx.__version__),
        onnxruntime_version=str(ort.__version__),
        export_timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
        git_commit_at_export=_git_commit(),
        input_names=names,
        output_name=OUTPUT_NAME,
        exporter=exporter,
    )


def build_onnx_registry_manifest(
    result: ExportResult,
    *,
    parent_registry_name: str,
    parity: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Assemble the tracked ONNX registry manifest dict from an export result.

    ``parity`` is filled by the parity harness after it runs; a pending
    placeholder is written at export time.
    """
    return {
        "parent_registry": parent_registry_name,
        "parent_model_sha256": result.parent_model_sha256,
        "onnx_path": result.onnx_path,
        "onnx_sha256": result.onnx_sha256,
        "opset": result.opset,
        "exporter": result.exporter,
        "torch_version": result.torch_version,
        "onnx_version": result.onnx_version,
        "onnxruntime_version": result.onnxruntime_version,
        "export_timestamp": result.export_timestamp,
        "git_commit_at_export": result.git_commit_at_export,
        "input_names": list(result.input_names),
        "output_name": result.output_name,
        "parity": parity if parity is not None else {
            "report": "reports/wp2/onnx_parity_v1.json",
            "max_abs_diff": None,
            "n_fixtures": None,
            "verdict": "pending",
        },
    }
