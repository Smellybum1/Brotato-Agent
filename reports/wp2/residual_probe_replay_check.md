# Residual-probe replay check - rung 2

Generated 2026-07-24 20:45:52 - mode **full** - runtime 1.15s - overall **PASS**.

Seed 20260724, theta_max 5.0 deg. 2500 ticks verified (2459 perturbed, 41 zero-vector passthrough) against the sidecar per-act log.

Frozen `combat_capture` payloads from the v122 exact-20 teacher campaign `events.jsonl` runs (READ-ONLY) streamed through the torch-free residual-probe sidecar over protocol v1 on loopback.

## Gates

| gate | status | detail |
|---|---|---|
| rotation match <= 1e-06 | PASS | max err = 8.691e-09 |
| magnitude preserved <= 1e-06 | PASS | max err = 2.220e-16 |
| zero-vector passthrough | PASS | count = 41 |
| delta ~ Uniform(-5, +5) | PASS | n=2459, mean=0.0498, var=8.3845 (exp 8.3333), range=[-4.9996, 4.9948], KS=0.0136 |
| no errors / all logged | PASS | errors=0, unmatched=0 |

## Sidecar identity (`hello_ack`, verbatim)

```json
{
  "backend": "residual-probe",
  "input_config_sha256": "residual-probe",
  "model_sha256": "residual-probe-v1",
  "normalization_sha256": "residual-probe",
  "observation_schema_hash": "residual-probe",
  "pid": 39684,
  "protocol": 1,
  "registry_run_name": "residual_probe_theta5_seed20260724",
  "schema_id": "combat_obs_v1",
  "type": "hello_ack",
  "v": 1
}
```

## Worst rotation tick

- seq 1309 wave 3 delta 0.020859 deg
- teacher [0.999128, -0.041755] -> reply [0.999143, -0.041391] (expected [0.999143, -0.041391], err 8.691e-09)
