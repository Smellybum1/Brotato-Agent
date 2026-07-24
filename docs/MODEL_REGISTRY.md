# Model registry

Every trained learned-combat checkpoint writes a self-describing manifest to
`models/registry/<run_name>.json`. The manifest is the authoritative record of
what a checkpoint is, how it was produced, and what it scored — the sidecar
verifies against it at serve time (M3, `reports/wp2/m3_change_record.md`) and the
live handshake echoes its hashes. This file documents the convention.

## Naming

`bc_v<gen>_<variant>_s<seed>[_<suffix>]`

- `gen` — generation / training aggregate:
  - **v1** = M2 behavior-cloning baseline, teacher-only (`combat_obs_v1`,
    387,695 samples).
  - **v2** = DAgger round-1 aggregate (base + `combat_dagger_r1`).
  - **v3** = DAgger round-2 aggregate (base + r1 + r2).
- `variant` — a sweep point (hyperparameters differ; see `resolved_config`).
  For v1 the "full" variant is the shipped baseline.
- `s<seed>` — training seed (seed 1 is primary throughout).
- `_<suffix>` — non-production runs (e.g. `_p0_diag`, a timestamp) are
  diagnostics or seed replicates, not selection candidates.

ONNX exports get a sibling manifest `<run_name>_onnx.json` (Stage G).

## Torch manifest fields (`bc_v*.json`)

Identity / provenance
- `run_name`, `seed`, `split_id`, `timestamp`, `git_commit`, `smoke`.
- `schema_hash` — observation schema (`observation_v1.yaml`); must equal the
  mod's emitted capture schema at handshake.
- `dataset_manifest_hash` — the `combat_obs_v1` build the model trained on.
- `normalization_manifest_hash` — the standardization stats; the sidecar
  hash-verifies this and refuses to serve on mismatch.
- `config_hash` — hash of the resolved training config.

Checkpoints (serving inputs)
- `checkpoints.best` / `checkpoints.last` — `{path, sha256}`. **`best` (best-
  epoch val) is the served/exported checkpoint**; its sha256 is re-verified at
  sidecar startup and echoed in the live `student_session` identity block.

Reproduction
- `resolved_config` — full training config (lr, batch_size, `lambda_mag`,
  `previous_action_dropout_p`, `huber_delta`, early-stopping, dataset/schema/
  split paths, seed, …).
- `environment` — python / torch / numpy / CUDA device.
- `best_epoch`, `epochs_run`, `wall_time_sec`, `device`.

Metrics (frozen `combat_obs_v1` val split, `bc_offline` path)
- `best_val_metrics` / `final_val_metrics` — overall (`val_median_angular_
  error_deg`, `val_mean_cosine`, `val_mean_abs_magnitude_error`,
  `val_saturation_fraction`, `val_loss`, …) plus `by_risk_stratum` and
  `by_wave_band` breakdowns. Teacher-val is a **candidate filter, not a
  deployment-quality claim** — see the copy-through finding in
  `reports/wp2/m4_change_record.md`.
- `baselines` — `copy_previous` and `mean_direction` on the same split, for
  reference (copy_previous is the anti-copy-through yardstick).

DAgger provenance (v2 / v3 only) — `bc_v2_provenance`
- `dagger_dataset_dir` / `multi_corrective.dagger_dataset_dirs` and
  `dagger_manifest_hashes` — the corrective set(s) mixed in.
- `combat_obs_v1_manifest_hash` — the frozen base.
- `achieved_mass_fraction` — realized corrective effective-batch mass (target
  0.15 for f).
- `base_weight_sum` / `dagger_weight_sum`, `n_base_train`, `n_dagger_train`,
  `n_dagger_holdout` — sample-weight and row bookkeeping.
- `aux_base_rates` — aux-head label base rates (heads dropped at serving).
- `serving_export` — how the served state-dict was extracted (BCPolicyV1
  strict-load verified; aux heads stripped).

## ONNX manifest fields (`<run_name>_onnx.json`, Stage G)

`onnx_path`, `onnx_sha256`, `opset` (18), `exporter`, `input_names` (15: globals
+ 7 entity/mask group pairs), `output_name` (`action`), `git_commit_at_export`,
version pins (`torch_version`, `onnx_version`, `onnxruntime_version`), and
`parent_model_sha256` / `parent_registry` linking back to the torch checkpoint.
`parity` = `{max_abs_diff, n_fixtures, report, verdict}` — the §14.1 10k-fixture
gate (threshold 1e-04).

## Current status (2026-07-24)

| run_name | role |
|---|---|
| **`bc_v2_f_s1`** | **PRODUCTION student** — behaviorally validated (M4 paired eval: 6 runs, waves 16–20, one victory). Config pin points here. |
| `bc_v1_s1_full` | M2 BC baseline; the model served in the M3 live smoke and exported in Stage G. Archived (superseded live; still the copy-through reference). |
| `bc_v1_s1_full_onnx` | ONNX export of `bc_v1_s1_full`, 10k-parity PASS (max Δ 1.13e-06). Byte-parity-verified, **not** live-qualified (torch is the sole live backend). |
| `bc_v3_a_s1` | Offline-selected / dominant on the unbiased r2 holdout, but **behaviorally unconfirmed** (lost the paired eval). Archived candidate; folded into the next aggregate. |
| `bc_v3_b_s1` | DAgger r1+r2 sweep candidate; failed the teacher-val median gate. Archived. |
| `bc_v2_a…e,g,h_s1` | DAgger r1 sweep points; each failed ≥1 selection clause. Archived. |
| `bc_v1_s2_full`, `bc_v1_s3_full` | Seed replicates of the baseline. Archived. |
| `bc_v1_s1_20260724_020529`, `bc_v1_s1_p0_diag` | Diagnostics, not candidates. |

Production/archived status is not a manifest field — a checkpoint is production
only by the config pin and the change-record verdicts
(`reports/wp2/m4_change_record.md`). The registry keeps every candidate for
audit and for re-aggregation.
