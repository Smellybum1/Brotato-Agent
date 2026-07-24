# Model registry

Every trained learned-combat checkpoint writes a self-describing manifest to
`models/registry/<run_name>.json`. The manifest is the authoritative record of
what a checkpoint is, how it was produced, and what it scored — the sidecar
verifies against it at serve time (M3, `reports/wp2/m3_change_record.md`) and the
live handshake echoes its hashes. This file documents the convention.

## Naming

`bc_v<gen>_<variant>_s<seed>[_<suffix>]`

(Applies to BC/DAgger student checkpoints only. Stage F residual actors use
`residual_pi<n>` with a different manifest kind — see their section below.)

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

## Current status (2026-07-25)

| run_name | role |
|---|---|
| **`bc_v2_f_s1`** | **PRODUCTION student** — behaviorally validated (M4 paired eval: 6 runs, waves 16–20, one victory). Config pin points here; **unchanged by Stage F**. |
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

## Stage F residual actors (`residual_pi*.json`) — a different manifest kind

Stage F Phase 2 checkpoints are **not** BC checkpoints and do **not** follow the
`bc_v*` naming or torch-manifest schema above. Each is a `kind: "residual_actor"`
/ `format: "residual_actor_v1"` manifest describing a bounded **angular residual**
learned on top of the frozen `bc_v2_f_s1` trunk — `executed_dir =
rotate(teacher_dir, θ_max·tanh(z))`, `theta_max_deg = 5.0`, `parent_model_sha256`
= `bc_v2_f_s1` best.pt (`1AD517B0…F29F331`). They serve by rotating the teacher's
movement action; **every residual run is residual-teacher-base control (§14.3),
not an independent student**. They are **NOT production candidates** — the config
pin never left `bc_v2_f_s1`. See `reports/wp2/stage_f_phase2_change_record.md`.

| run_name | role |
|---|---|
| `residual_pi3` | Stage F Phase 2 iteration 3, arm A (`λ₀ = 0.001`; actor sha `689C1C64…AD26F`). **Arm-selection ruling** (`reports/wp2/residual_pi3_arm_selection.md`): chosen over arm B (`λ₀ = 0.0003`) on stratified \|δ\| — concentrates residual mass 7.0× in wave 20 / 7.5× in risk ≥ 0.75 (the critic-advantaged strata). Offline gates PASS (p99 \|z\| 0.139, serving determinism exact, no θ saturation). Live: smoke PASS (defeat w17); batch-1 runs w19 / w13 (w13 tripped the wave-15 bar → aborted → investigation cleared the mechanism, training-valid) / w20-victory → **1/4 victories**. Residual-teacher-base control; archived. |
| `residual_pi4` | Stage F Phase 2 iteration 4 (`λ₀ = 0.001`, seed 4; actor sha `16414822…497A4`). Retrained on the 14-run / **247,510-state** pool (incl. the first pi3 victory). Offline gates PASS (p99 \|z\| 0.172, serving determinism exact). Live: batch-2 **3/3 victories** (damage 107 / 135 / **22** — cleanest 20-wave run in the project). Residual-teacher-base control; archived. |

**Stage F Phase 2 verdict (§6 checkpoint, 2026-07-25): NULL.** Learned residual
(7 runs, pi3+pi4) vs matched Phase-1 random control (6 runs): every predeclared-
surface CI straddles zero (victory +0.238, overall damage +0.00004, wave-20
damage −0.00039). Not shown to beat random perturbation; growing-batch iteration
stopped per the predeclared rule. `bc_v2_f_s1` remains production
(`reports/wp2/residual_checkpoint_verdict.md`).
