# Student latency benchmark — rung 3

Generated 2026-07-24 13:11:35 · mode **smoke** · backend **onnx** · runtime 26.82s · gate cadence 20 Hz · overall **PASS**.

> Latency is Python-client -> loopback -> sidecar. Godot-side JSON serialization is NOT included here; it is measured live via the mod's student_tick latency_ms telemetry during the isolated smoke.

## Gates (at 20 Hz, worst band)

| gate | status | value | threshold | worst band |
|---|---|---|---|---|
| model p99 | PASS | 1.29 ms | ≤ 10.0 ms | early |
| end-to-end p99 | PASS | 2.66 ms | ≤ 25.0 ms | late |
| within 50 ms | PASS | 100.000% | ≥ 99.9% | early |
| ≤ 2 consecutive 40 ms-deadline misses | PASS | 0 | ≤ 2 | early |

## Per-band x per-cadence

| band | Hz | n | model p50 | model p95 | model p99 | model max | e2e p50 | e2e p95 | e2e p99 | e2e max | miss | max consec | within 50ms |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| early | 20 | 150 | 0.68 | 1.00 | 1.29 | 1.42 | 1.55 | 2.15 | 2.45 | 2.59 | 0 | 0 | 100.000% |
| late | 20 | 150 | 0.67 | 0.92 | 1.02 | 1.12 | 1.67 | 2.19 | 2.66 | 2.88 | 0 | 0 | 100.000% |
| boss | 20 | 150 | 0.65 | 0.94 | 1.07 | 1.26 | 1.55 | 2.19 | 2.41 | 2.61 | 0 | 0 | 100.000% |
| peak | 20 | 33 | 0.63 | 0.98 | 1.02 | 1.03 | 1.65 | 2.36 | 2.48 | 2.51 | 0 | 0 | 100.000% |

## Corpus

Per-band target 150 · contributing runs {'early': 2, 'late': 2, 'boss': 1} · per-run intake cap {'early': 113, 'late': 113, 'boss': 226}. Peak band = top 5% by enemies+projectiles (load range 9..12).

| band | payloads |
|---|---|
| early | 150 |
| late | 150 |
| boss | 150 |
| peak | 33 |

## Sidecar identity (`hello_ack`, verbatim)

```json
{
  "backend": "onnxruntime-cpu",
  "input_config_sha256": "CF87A0F8D6AB623A99C9FB4A9CB2131677D61F85855DAF0B4F8D0E8CD9505893",
  "model_sha256": "1DF7E70A1483D152B3AE0ABFD63F2CD17C1F270B4766D87E34D95C1AC0673940",
  "normalization_sha256": "FD3C55F62F210A6588B67787323CCE1E64311C57AF6A2FBFB136C86B6D27D166",
  "observation_schema_hash": "C653D836F3EBC821A51AFC70482D3772FC7B7B927D393A6B9BBADC2718BB9B2A",
  "pid": 11780,
  "protocol": 1,
  "registry_run_name": "bc_v1_s1_full",
  "schema_id": "combat_obs_v1",
  "type": "hello_ack",
  "v": 1
}
```

## Machine + environment

- CPU: AMD Ryzen 7 9800X3D 8-Core Processor (16 logical cores) · plugged-in: unknown
- torch `2.13.0+cu126` · numpy `2.5.1` · python `3.12.5`
- Windows-11-10.0.26200-SP0
