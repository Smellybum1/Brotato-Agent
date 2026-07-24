# ONNX parity — WP2 Stage G

Generated 2026-07-24 13:12:54 · mode **full** · runtime 14.6s · verdict **PASS**.

PyTorch (CPU, 1 thread) vs exported ONNX graph (ONNX Runtime, CPU, intra_op 1), batch-1, on validation-split fixtures only (no training-split contamination).

## Gates

| gate | status | value | threshold |
|---|---|---|---|
| max &#124;Δaction&#124; | PASS | 1.132e-06 | <= 1e-04 |
| zero NaN/Inf (both backends) | PASS | torch=0, onnx=0 | 0 |

Overall: 10000/10000 fixtures compared · max |Δ| = 1.132e-06 · mean |Δ| = 1.587e-07 · p99 |Δ| = 5.246e-07.

## Per-category

| category | n | compared | nonfinite | max &#124;Δ&#124; | mean &#124;Δ&#124; | p99 &#124;Δ&#124; |
|---|---|---|---|---|---|---|
| stratified | 8000 | 8000 | 0 | 1.132e-06 | 1.551e-07 | 5.066e-07 |
| empty_group | 1000 | 1000 | 0 | 7.525e-07 | 1.531e-07 | 5.364e-07 |
| capacity_overflow | 500 | 500 | 0 | 7.451e-07 | 2.277e-07 | 6.483e-07 |
| edge_norm | 500 | 500 | 0 | 4.470e-07 | 1.587e-07 | 3.576e-07 |

Worst fixture: category **stratified**, |Δ| = 1.132e-06, torch = [0.177317, -0.274087], onnx = [0.177317, -0.274088].

## Fixture recipe

Seed 20260724 · 81790 validation rows available · counts {'stratified': 8000, 'empty_group': 1000, 'capacity_overflow': 500, 'edge_norm': 500}.

- (a) stratified: proportional over wave-band x risk-bin strata; indices sha256 `965E272DA0C0719C...`.
- (b) empty-group: each group's mask+entities zeroed one-at-a-time and all-at-once from 125 base rows.
- (c) capacity-overflow: every mask forced all-ones from 500 base rows.
- (d) edge-normalization: standardized globals at +/-6.0 sigma and present entity features at per-feature validation bounds, from 250 base rows (2 variants each).

## ONNX identity

- onnx sha256 `1DF7E70A1483D152B3AE0ABFD63F2CD17C1F270B4766D87E34D95C1AC0673940`
- parent best.pt sha256 `BE7E82326EC8A424A1EDF33134E65A26E06EDA68DA7F22D37705F3C26D6A9F0F`
- opset 18 · exporter classic · torch 2.13.0+cu126 · onnx 1.22.0 · onnxruntime 1.27.0

## Latency (secondary — ONNX backend sidecar)

Source `student_latency_bench_onnx_v1.json` · backend onnx · mode smoke · gate cadence 20 Hz.

| gate | status | value | threshold |
|---|---|---|---|
| model p99 | PASS | 1.29 ms | <= 10.0 ms |
| end-to-end p99 | PASS | 2.66 ms | <= 25.0 ms |

## Environment

- torch `2.13.0+cu126` · onnx `1.22.0` · onnxruntime `1.27.0` · numpy `2.5.1` · python `3.12.5` · threads 1
- Windows-11-10.0.26200-SP0 · AMD64 Family 26 Model 68 Stepping 0, AuthenticAMD
