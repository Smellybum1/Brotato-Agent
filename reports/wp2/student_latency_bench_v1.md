# Student latency benchmark — rung 3

Generated 2026-07-24 12:17:16 · mode **full** · runtime 968.89s · gate cadence 20 Hz · overall **PASS**.

> Latency is Python-client -> loopback -> sidecar. Godot-side JSON serialization is NOT included here; it is measured live via the mod's student_tick latency_ms telemetry during the isolated smoke.

## Gates (at 20 Hz, worst band)

| gate | status | value | threshold | worst band |
|---|---|---|---|---|
| model p99 | PASS | 2.07 ms | ≤ 10.0 ms | peak |
| end-to-end p99 | PASS | 3.48 ms | ≤ 25.0 ms | peak |
| within 50 ms | PASS | 100.000% | ≥ 99.9% | early |
| ≤ 2 consecutive 40 ms-deadline misses | PASS | 0 | ≤ 2 | early |

## Per-band x per-cadence

| band | Hz | n | model p50 | model p95 | model p99 | model max | e2e p50 | e2e p95 | e2e p99 | e2e max | miss | max consec | within 50ms |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| early | 15 | 2000 | 0.80 | 1.21 | 1.67 | 3.62 | 1.48 | 2.15 | 2.80 | 4.91 | 0 | 0 | 100.000% |
| early | 20 | 2000 | 0.82 | 1.28 | 1.74 | 2.73 | 1.49 | 2.14 | 2.78 | 3.98 | 0 | 0 | 100.000% |
| early | 30 | 2000 | 0.84 | 1.36 | 1.74 | 3.67 | 1.51 | 2.32 | 2.74 | 4.76 | 0 | 0 | 100.000% |
| late | 15 | 2000 | 1.00 | 1.64 | 2.26 | 3.20 | 1.80 | 2.69 | 3.30 | 4.78 | 0 | 0 | 100.000% |
| late | 20 | 2000 | 1.06 | 1.60 | 1.87 | 2.74 | 1.89 | 2.67 | 3.05 | 3.86 | 0 | 0 | 100.000% |
| late | 30 | 2000 | 1.13 | 1.71 | 2.19 | 5.16 | 1.98 | 2.78 | 3.36 | 7.66 | 0 | 0 | 100.000% |
| boss | 15 | 2000 | 1.04 | 1.62 | 1.90 | 2.41 | 1.90 | 2.63 | 2.97 | 4.13 | 0 | 0 | 100.000% |
| boss | 20 | 2000 | 0.92 | 1.52 | 1.82 | 3.07 | 1.66 | 2.47 | 2.94 | 4.36 | 0 | 0 | 100.000% |
| boss | 30 | 2000 | 0.88 | 1.46 | 1.72 | 3.41 | 1.63 | 2.51 | 2.90 | 4.43 | 0 | 0 | 100.000% |
| peak | 15 | 452 | 1.08 | 1.54 | 1.85 | 2.70 | 2.10 | 2.91 | 3.25 | 4.23 | 0 | 0 | 100.000% |
| peak | 20 | 452 | 1.17 | 1.72 | 2.07 | 2.72 | 2.23 | 3.10 | 3.48 | 4.01 | 0 | 0 | 100.000% |
| peak | 30 | 452 | 1.03 | 1.53 | 1.72 | 2.30 | 2.03 | 2.72 | 3.13 | 3.61 | 0 | 0 | 100.000% |

## Corpus

Per-band target 2000 · contributing runs {'early': 20, 'late': 18, 'boss': 15} · per-run intake cap {'early': 151, 'late': 167, 'boss': 201}. Peak band = top 5% by enemies+projectiles (load range 14..36).

| band | payloads |
|---|---|
| early | 2000 |
| late | 2000 |
| boss | 2000 |
| peak | 452 |

## Sidecar identity (`hello_ack`, verbatim)

```json
{
  "backend": "torch-cpu",
  "input_config_sha256": "CF87A0F8D6AB623A99C9FB4A9CB2131677D61F85855DAF0B4F8D0E8CD9505893",
  "model_sha256": "BE7E82326EC8A424A1EDF33134E65A26E06EDA68DA7F22D37705F3C26D6A9F0F",
  "normalization_sha256": "FD3C55F62F210A6588B67787323CCE1E64311C57AF6A2FBFB136C86B6D27D166",
  "observation_schema_hash": "C653D836F3EBC821A51AFC70482D3772FC7B7B927D393A6B9BBADC2718BB9B2A",
  "pid": 33808,
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
