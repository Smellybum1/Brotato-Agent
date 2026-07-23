# Training Environment Lock — PyTorch + CUDA

Recorded: 2026-07-24
Venv: `C:\Codex\Brotato Agent\.venv` (Python 3.12.5, Windows 11)

## Summary (machine-readable)

```json
{
  "torch_version": "2.13.0+cu126",
  "cuda_runtime_version": "12.6",
  "wheel_index_url": "https://download.pytorch.org/whl/cu126",
  "pip_command": ".venv/Scripts/python.exe -m pip install torch --index-url https://download.pytorch.org/whl/cu126",
  "cuda_available": true,
  "gpu_name": "NVIDIA GeForce RTX 4090",
  "gpu_compute_capability": "sm_89",
  "nvidia_driver_version": "610.52",
  "numpy_version": "2.5.1",
  "numpy_changed": false,
  "torch_license": "BSD-3-Clause",
  "cuda_matmul_finite": true,
  "cpu_matmul_finite": true,
  "test_suite": "229 passed, 0 failed"
}
```

## Details

- **torch**: 2.13.0+cu126 (latest stable at install time), CUDA runtime 12.6.
- **Wheel index**: official PyTorch cu126 index. torch-only install (no torchvision/torchaudio/SB3/gymnasium/onnx).
- **GPU**: NVIDIA GeForce RTX 4090, compute capability sm_89 (Ada), driver 610.52. `torch.cuda.is_available()` returns True.
- **Verification**: 256x256 matmul on `cuda:0` and on CPU both completed and are finite.
- **numpy**: unchanged at 2.5.1 (torch 2.13 supports numpy 2.x; no down/upgrade occurred).
- **License**: torch is BSD-3-Clause.
- **Tests**: `python -m pytest tests -x -q --basetemp=.tmp/pytest-basetemp` -> 229 passed in ~0.83s (no regressions from torch install).

## pip freeze delta (new packages only)

```
torch==2.13.0+cu126
filelock==3.29.0
fsspec==2026.4.0
Jinja2==3.1.6
MarkupSafe==3.0.3
mpmath==1.3.0
networkx==3.6.1
setuptools==78.1.0
sympy==1.14.0
typing_extensions==4.15.0
```

Pre-existing packages (numpy 2.5.1, pytest 9.1.1, pyyaml) were not modified.
