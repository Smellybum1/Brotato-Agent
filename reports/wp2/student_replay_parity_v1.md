# Student replay parity — rung 2

Generated 2026-07-24 11:42:33 · mode **full** · runtime 246.07s · overall **PASS**.

Reference actions are the frozen `combat_obs_v1` NPZ rows forwarded through the verified model via the exact `bc_offline` path (CPU, float32, hash-verified normalization manifest, batch-1 to match the sidecar's per-tick serving). Sidecar actions are the same ticks re-encoded live from the RAW `events.jsonl` payloads (READ-ONLY) matched by `capture_seq`, served over protocol v1 on loopback.

## Gates

| gate | status | detail |
|---|---|---|
| max &#124;Δaction&#124; ≤ 1e-06 | PASS | max = 0.000e+00 |
| zero NaN/Inf | PASS | nonfinite = 0 |
| zero sidecar errors | PASS | errors = 0 |
| coverage (all val rows matched) | PASS | compared 81790/81790, unmatched 0 |

Aggregate: 81790 ticks compared, max |Δ| = 0.000e+00, mean over runs. Runtime 246.07s.

## Sidecar identity (`hello_ack`, verbatim)

```json
{
  "backend": "torch-cpu",
  "input_config_sha256": "CF87A0F8D6AB623A99C9FB4A9CB2131677D61F85855DAF0B4F8D0E8CD9505893",
  "model_sha256": "BE7E82326EC8A424A1EDF33134E65A26E06EDA68DA7F22D37705F3C26D6A9F0F",
  "normalization_sha256": "FD3C55F62F210A6588B67787323CCE1E64311C57AF6A2FBFB136C86B6D27D166",
  "observation_schema_hash": "C653D836F3EBC821A51AFC70482D3772FC7B7B927D393A6B9BBADC2718BB9B2A",
  "pid": 19208,
  "protocol": 1,
  "registry_run_name": "bc_v1_s1_full",
  "schema_id": "combat_obs_v1",
  "type": "hello_ack",
  "v": 1
}
```

## Per-run

| run_id | outcome | selected | compared | max &#124;Δ&#124; | mean &#124;Δ&#124; | errors | unmatched |
|---|---|---|---|---|---|---|---|
| run_1784787688_32406 | victory | 21775 | 21775 | 0.000e+00 | 0.000e+00 | 0 | 0 |
| run_1784793833_32034 | defeat | 17399 | 17399 | 0.000e+00 | 0.000e+00 | 0 | 0 |
| run_1784799404_80018 | defeat | 20906 | 20906 | 0.000e+00 | 0.000e+00 | 0 | 0 |
| run_1784804435_39794 | victory | 21710 | 21710 | 0.000e+00 | 0.000e+00 | 0 | 0 |

## Environment

- torch `2.13.0+cu126` · numpy `2.5.1` · python `3.12.5` · threads 1
- Windows-11-10.0.26200-SP0 · AMD64 Family 26 Model 68 Stepping 0, AuthenticAMD
