# WP2 bc_v3 aggregate training report (round-2 DAgger: r1 + r2 corrective)

Generated 2026-07-24 18:07:38. Two BCPolicyV1 candidates trained on the frozen combat_obs_v1 base pooled with BOTH corrective datasets (combat_dagger_r1 + combat_dagger_r2). Findings only.

## Recipe (F's, applied to both candidates)

- Architecture: BCPolicyV1 (no aux head; candidate A)
- Seed: 1; previous_action_dropout_p 0.4; lambda_mag 1.0
- Base hyperparams: bc_v2_a defaults (lr 3e-4, batch 4096, weight_decay 1e-4, huber_delta 0.5, mag_eps 0.01, early_stopping_patience 5, max_epochs 50, cosine schedule)
- Corrective pooling: combat_dagger_r1 + combat_dagger_r2, each keeping its own build-time event weights, pooled proportional to TRAIN row counts within a single total corrective mass; r1 and r2 each carve their own deterministic 10% holdout (seed 20260724) excluded from ALL training

## Candidates

| candidate | total corrective mass | r1 n_train | r2 n_train | composite train | best_epoch | epochs_run | wall (s) | tv median deg | tv |mag err| | tv sat |
|---|---|---|---|---|---|---|---|---|---|---|
| bc_v3_a_s1 | 0.15 | 70987 | 104642 | 481534 | 7 | 13 | 40.4 | 8.6988 | 0.0756 | 0.000171 |
| bc_v3_b_s1 | 0.20 | 70987 | 104642 | 481534 | 5 | 11 | 35.6 | 9.2519 | 0.0809 | 0.000098 |

## Per-set corrective breakdown (pooled proportional to row counts)

| candidate | set | n_train | n_holdout (excluded) | event_weight_sum | scaled weight_sum | s scalar | mass share | rowcount share |
|---|---|---|---|---|---|---|---|---|
| bc_v3_a_s1 | combat_dagger_r1 | 70987 | 7887 | 71005.8 | 21819.3 | 0.307290 | 0.404187 | 0.404187 |
| bc_v3_a_s1 | combat_dagger_r2 | 104642 | 11627 | 104704.6 | 32163.9 | 0.307187 | 0.595813 | 0.595813 |
| bc_v3_b_s1 | combat_dagger_r1 | 70987 | 7887 | 71005.8 | 30910.7 | 0.435327 | 0.404187 | 0.404187 |
| bc_v3_b_s1 | combat_dagger_r2 | 104642 | 11627 | 104704.6 | 45565.5 | 0.435182 | 0.595813 | 0.595813 |

Mass share equals rowcount share by construction (total corrective mass split proportional to per-set training row counts; within each set distributed by that set's own build-time event weights). Achieved total corrective mass fraction matches the target exactly (bc_v3_a 0.15, bc_v3_b 0.20).

## Provenance

| candidate | checkpoint sha256 | normalization manifest hash | r1 manifest hash | r2 manifest hash |
|---|---|---|---|---|
| bc_v3_a_s1 | `2979C36A4A6D833C...` | `B3CBDBF6007E4AE4...` | `7AF8403FD4C39CAF...` | `9B2C1E9184926716...` |
| bc_v3_b_s1 | `8AD4656D7E3393B7...` | `B3CBDBF6007E4AE4...` | `7AF8403FD4C39CAF...` | `9B2C1E9184926716...` |

Base (combat_obs_v1) manifest hash: `6E7FAB14DD0614FD...` (identical for both). n_base_train 305905; each candidate excludes 7,887 r1 + 11,627 r2 = 19,514 holdout rows from training.

Environment: python 3.12.5, torch 2.13.0+cu126, numpy 2.5.1, cuda NVIDIA GeForce RTX 4090. git_commit 5682ba38a47b.

