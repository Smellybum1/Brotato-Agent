# WP2 M2 — Behavior-cloning baseline: training report and qualification (bc_v1)

Author: Claude Fable (primary), 2026-07-24.
Design authority: `.tmp/wp2_m2_training_architecture.md` (final).
Independent evaluation evidence: `reports/wp2/bc_offline_eval_bc_v1_full.{json,md}`.

## Verdict

**QUALIFIED (offline).** The bc_v1 behavior-cloning baseline passes both
sanity gates (architecture note §7 operationalization) on all 3 seeds plus
the p=0 diagnostic, with independently recomputed metrics that match the
training-time numbers exactly. **Selected candidate: `bc_v1_s1_full`
(best.pt, epoch 22)** — best val loss of the seed family; seeds are
statistically interchangeable. Offline qualification only: no in-game
claim is made — the student-inference path (bridge/sidecar) does not exist
yet and is the next design decision.

## What was trained

- Model: masked entity-set encoder (7 per-group MLP encoders 15→64→64,
  masked mean⊕max pooling, trunk 936→512→256, tanh 2-D head); 651,202
  params; CPU inference p99 ≈ 1.3 ms (budget 10 ms).
- Input: 40 of 48 global features (8 teacher-privileged excluded per
  `configs/wp2/bc_input_v1.yaml`) + all 7 entity groups with masks.
- Loss: masked cosine direction + Huber magnitude (λ=0.5, δ=0.5),
  previous-action dropout p=0.1. Grounded in the teacher action
  distribution analysis (`reports/wp2/teacher_action_distribution.md`):
  99.99% unit-norm labels, direction is the only signal, 37% off-grid
  tail → continuous regression, no discrete head.
- Data: frozen `combat_obs_v1` (v122 teacher, 387,695 valid∧temporal
  samples), run-level split 16 train / 4 val
  (`configs/wp2/dataset_split_v1.yaml`), normalization from train split
  only. All hashes verified at load and again at eval.
- Protocol: AdamW 3e-4 → cosine to 1e-5, batch 4096, early stop patience
  5, seeds 1/2/3, GPU (RTX 4090), 47–65 s per run.

## Results (validation = 81,790 held-out-run samples)

| run | best epoch | val loss | med ang | mean ang | cos | gates |
|---|---|---|---|---|---|---|
| bc_v1_s1_full | 22 | 0.0981 | 4.80° | 13.73° | 0.904 | PASS |
| bc_v1_s2_full | 14 | 0.0999 | 5.30° | 14.17° | 0.902 | PASS |
| bc_v1_s3_full | 24 | 0.0984 | 4.91° | 13.80° | 0.903 | PASS |
| bc_v1_s1_p0_diag | 12 | 0.0968 | 5.00° | 13.67° | 0.905 | PASS |

Baselines: mean-direction 86.93°/87.99° (med/mean); copy-previous
4.32°/21.20°. Gate stratum (direction-change frames, Δ≥1°, 61% of moving
frames): model median 6.6–7.2° vs copier 15.0°; at Δ≥45°: ~22° vs 105°.
The copier's overall-median advantage (4.32° vs 4.80°) is the persistence
artifact ruled out of the gate in note §7 — the model near-copies where
copying is correct (~3.4° on persist frames) and dominates everywhere the
action actually changes.

- Seed stability: val-loss std 0.0011; median-angular std 0.19°.
  Inter-seed policy agreement: 3.2–4.2° median pairwise angular
  difference on identical val inputs.
- Saturation ≈ 0; mean |magnitude error| ≈ 0.05.
- Per-val-run (seed 1): victories 4.87°/5.38° median, defeats 4.38°/4.62°
  — no outcome-conditional cloning gap.
- p=0 diagnostic: indistinguishable from p=0.1 → no over-reliance on the
  previous-action input; p=0.1 retained as free deployment insurance.

## Known weaknesses (targets for DAgger, Stage E)

Stratified errors rise sharply exactly where the teacher's hardest
logic lives:

- Wave 20 (finale): median 15–18°, mean ~42°.
- High-risk states: risk ∈ [0.5,0.75) median 18.2°, ≥0.75 median 31.0°
  (n=196 — rare but they are the states that kill runs).

These strata are where corrective collection should focus; offline BC on
frozen data cannot resolve them further without new interaction data.

## Deferred (documented, not silently dropped)

- **MSE-diagnostic variant** (note §4): requires a loss-variant switch in
  the training config; deferred — low information value now that the
  chosen loss already dominates both frozen baselines, and the packet
  fixes the loss family regardless. Revisit only if a Stage-E ablation
  needs it.
- **Student-inference path in-game** (bridge + sidecar, packet Stages
  B/G): next milestone; nothing in bc_v1 blocks it — the input is a
  named subset of the frozen schema and the sidecar can reuse
  `encoder_v1` output with the mask config.
- Teacher chain (v126, item-conditioned movement, obs_v2): out of scope
  per session directive.

## Artifacts

- Checkpoints: `models/bc_v1/bc_v1_s{1,2,3}_full/`, `bc_v1_s1_p0_diag/`
  (gitignored; best+last, with per-run `metrics.jsonl` and
  `normalization_manifest.json`).
- Registry manifests (tracked): `models/registry/bc_v1_s*_full.json`,
  `bc_v1_s1_p0_diag.json` — config/dataset/normalization/checkpoint
  hashes, git commit, baselines, metrics.
- Configs: `configs/wp2/bc_input_v1.yaml`, `dataset_split_v1.yaml`,
  `bc_train_v1.yaml`, `bc_train_v1_p0.yaml`.
- Code: `trainer/data/bc_dataset.py`, `trainer/models/bc_policy_v1.py`,
  `trainer/imitation/bc_training.py`, `trainer/evaluation/bc_offline.py`,
  `scripts/train_bc.py`, `scripts/evaluate_bc_offline.py`,
  `scripts/wp2_analyze_teacher_actions.py`; 294 tests green.
- Environment: `reports/wp2/training_env_lock.md` (torch 2.13.0+cu126).

## Delegation record (per AGENTS.md)

Bounded slices (dataset loader, model, training loop, eval script,
action-distribution analysis, torch install) were implemented by Opus 4.8
subagents. The primary reviewed every material diff in source, fixed the
tensor/gate contracts, made all loss/split/gate/qualification rulings,
ran the change-frame analysis and the full training runs, and verified
the independent eval numbers against the registries before this verdict.
