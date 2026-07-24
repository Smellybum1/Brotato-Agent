# bc_v2 training report (WP2 M4, DAgger round 1)

Two candidates trained on CUDA (RTX 4090), seed 1, bc_v1 hyper-parameters
(`configs/wp2/bc_train_v1.yaml`, AdamW lr 3e-4, cosine, early stopping patience
5). The full selection verdict is in `reports/wp2/bc_v2_offline_eval.md`.

## Composite training corpus

Base `combat_obs_v1` train (dataset_split_v1, unchanged) + all valid&temporal
`combat_dagger_r1` rows. A deterministic 10% of the dagger rows (seed 20260724)
is held out for candidate-B aux scoring and EXCLUDED from training for both
candidates, so A and B train on identical data.

| quantity | value |
|---|---|
| base train rows | 305,905 |
| dagger valid&temporal rows | 78,874 |
| dagger train rows (90%) | 70,987 |
| dagger aux-holdout rows (10%) | 7,887 |
| composite train rows | 376,892 |
| frozen val rows (combat_obs_v1) | 81,790 |
| corrective mass scalar s | 1.436057 |
| achieved dagger mass fraction | 0.2500 |

Per-row weights: base rows 1.0; dagger row r weight = event_weight_r * s, with a
single s solved so sum(dagger weights) = (0.25/0.75) * sum(base weights). The
weighted loss reduces as sum(w * per_sample) / sum(w), which makes the dagger
set carry exactly 25% of the effective batch (and expected epoch) mass.

Normalization follows bc_v1 (train-only, globals standardized, entities identity)
but recomputed over the COMPOSITE train set; the per-run
`normalization_manifest.json` is written and hash-pinned in each registry. The
val split is the frozen combat_obs_v1 val, unchanged.

## Candidate A - BCPolicyV1, composite weighted training

| field | value |
|---|---|
| params | 651,202 |
| epochs run / best epoch | 23 / 17 |
| wall time | 56.7 s |
| best val median / mean | 10.15 / 20.53 deg |
| best val_loss | 0.1502 |
| serving export | native BCPolicyV1 checkpoint |
| best checkpoint sha256 | 6D49095BD44CACE9... |

## Candidate B - BCPolicyV2 (base trunk + 2 aux heads)

Aux heads on the trunk penultimate hidden (256-d): `aux_damage`
(Linear->1, BCE-with-logits) and `aux_margin` (Linear->1 sigmoid, Huber delta
0.5), each weighted lambda_aux 0.05, computed on dagger rows only. Serving export
is the base state_dict only; strict-load compatibility with a fresh `BCPolicyV1`
is verified at export time AND end-to-end (the unchanged bc_offline path loaded
the exported base natively).

| field | value |
|---|---|
| params (base) | 651,716 (651,202) |
| aux params | 514 = 2 * (256 + 1) |
| lambda_aux | 0.05 per head |
| epochs run / best epoch | 16 / 10 |
| wall time | 55.1 s |
| best val median / mean | 9.25 / 19.71 deg |
| best val_loss | 0.1449 |
| serving export | base_state_dict (BCPolicyV1 strict-load verified) |
| best checkpoint sha256 | B261BF65CA8A75A5... |

### Candidate B aux-head metrics (held-out dagger rows, best epoch)

| head | metric | value |
|---|---|---|
| aux_damage | ROC-AUC | 0.964 |
| | BCE / base rate | 0.048 / 0.0193 |
| | pred mean pos / neg | 0.335 / 0.017 |
| aux_margin | MAE / RMSE | 0.172 / 0.217 |
| | Pearson r | 0.667 |
| | label mean / pred mean | 0.761 / 0.750 |

## Provenance

- combat_obs_v1 manifest hash (reloaded + verified by bc_offline): `6E7FAB14DD0614FD...`
- combat_dagger_r1 manifest hash: `7AF8403FD4C39CAF...`
- schema hash: `C653D836F3EBC821...`, split_id `dataset_split_v1`
- env: python 3.12, torch 2.13.0+cu126, numpy 2.5.1, CUDA RTX 4090

## Selection outcome

Both candidates FAIL all four design section-5 gates and regress on every
stratum (root cause in `bc_v2_offline_eval.md`: the corrective set's clamped
student `previous_action` is near-orthogonal to the teacher label, inverting the
copy-through channel bc_v1 relied on). Neither qualifies; round 2 indicated.

## Tests

Full suite: 372 passed (349 baseline + 23 new bc_v2 tests). New tests cover the
composite loader (weights, achieved mass fraction, val purity = zero dagger rows
in val, aux alignment, deterministic holdout), BCPolicyV2
(forward/aux/export-compat/base-equivalence), and the weighted + aux losses and
AUC helper.
