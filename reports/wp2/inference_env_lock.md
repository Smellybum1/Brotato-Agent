# Inference Environment Lock — ONNX Runtime + ONNX

Recorded: 2026-07-24
Venv: `C:\Codex\Brotato Agent\.venv` (Python 3.12.5, Windows 11)

Adds the CPU inference stack (ONNX Runtime + ONNX) on top of the training lock
(`reports/wp2/training_env_lock.md`). Installed with:

```
.venv/Scripts/python.exe -m pip install onnxruntime onnx
```

Latest stable CPU wheels at install time; no index-url override (default PyPI).
No other new runtime dependencies were added.

## Summary (machine-readable)

```json
{
  "onnxruntime_version": "1.27.0",
  "onnxruntime_provider": "CPUExecutionProvider",
  "onnxruntime_license": "MIT",
  "onnx_version": "1.22.0",
  "onnx_license": "Apache-2.0",
  "onnx_opset": 18,
  "exporter": "classic (torch.onnx.export, TorchScript-tracing, dynamo=False)",
  "torch_version": "2.13.0+cu126",
  "numpy_version": "2.5.1",
  "numpy_changed": false,
  "parity_max_abs_diff": 1.1324882507324219e-06,
  "parity_n_fixtures": 10000,
  "parity_verdict": "PASS",
  "model_p99_ms_onnx_cpu": 1.29,
  "test_suite": "349 passed, 0 failed"
}
```

## Details

- **onnxruntime**: 1.27.0, CPU build (`CPUExecutionProvider`). Sessions are built
  with `intra_op_num_threads = 1` and `inter_op_num_threads = 1` for
  deterministic single-thread serving, matching the torch CPU path.
- **onnx**: 1.22.0 — used only for `onnx.load` + `onnx.checker.check_model`
  structural validation of the exported graph at export time.
- **Opset**: 18 (mature, supported by both the torch 2.13 legacy exporter and
  ORT 1.27). Classic export at opset 18 succeeded on the first attempt; no op
  was rejected, so the dynamo exporter was not needed. (The legacy exporter
  emits a `DeprecationWarning` under torch 2.13; it remains functional and is
  the documented reference path here.)
- **numpy**: unchanged at 2.5.1 (ORT requires `numpy>=1.21.6`; the existing 2.5.1
  satisfied it — no up/downgrade).
- **Parity**: 10,000 batch-1 fixtures, PyTorch (CPU, 1 thread) vs ONNX Runtime
  (CPU, intra_op 1). Max abs action diff `1.13e-6` (gate `<= 1e-4`, ~88x margin),
  p99 `5.2e-7`, zero NaN/Inf on either backend. See
  `reports/wp2/onnx_parity_v1.json` / `.md`.
- **Latency**: ONNX CPU model p99 `1.29 ms` (gate `<= 10 ms`), end-to-end p99
  `2.66 ms` at 20 Hz over loopback. See
  `reports/wp2/student_latency_bench_onnx_v1.json` / `.md`.

## Licenses (added packages)

| package | version | license | GPL-compatible |
|---|---|---|---|
| onnxruntime | 1.27.0 | MIT | yes |
| onnx | 1.22.0 | Apache-2.0 | yes |
| ml_dtypes | 0.5.4 | Apache-2.0 | yes |
| flatbuffers | 25.12.19 | Apache-2.0 | yes |
| protobuf | 7.35.1 | BSD-3-Clause | yes |

Note: the binding brief anticipated both onnxruntime and onnx as MIT; the actual
licenses are onnxruntime = MIT and onnx = Apache-2.0. Both, and all transitive
additions, are permissive and GPL-compatible, so there is no licensing conflict
with the derived GPL mod.

## pip freeze delta (new packages only)

```
onnxruntime==1.27.0
onnx==1.22.0
ml_dtypes==0.5.4
flatbuffers==25.12.19
protobuf==7.35.1
```

Pre-existing packages (torch 2.13.0+cu126, numpy 2.5.1, pytest 9.1.1, pyyaml,
packaging, typing_extensions) were not modified. `protobuf` and `flatbuffers`
are transitive requirements of onnxruntime; `ml_dtypes` is a transitive
requirement of onnx.

## Tests

`.venv/Scripts/python.exe -m pytest tests -q --basetemp=.tmp/pytest-basetemp`
-> **349 passed** in ~9.5s (was 337; +12: 7 ONNX-export unit tests, 5
OnnxModelService sidecar tests). No regressions.
