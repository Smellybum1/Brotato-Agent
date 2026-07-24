# combat_dagger_r3 corrective dataset report

- student policy: `bc_v3_a_s1`
- schema hash: `C653D836F3EBC821A51AFC70482D3772FC7B7B927D393A6B9BBADC2718BB9B2A`
- encoder: `trainer/observation/encoder_v1.py` (frozen, reused build_run)
- builder: `scripts/wp2_build_combat_dagger_r3.py` @ `3eab510927bd246db2aef17174cf3788c6a70dad`
- runs: 6 | build wall: 44.7s
- dataset bytes: 86,211,685
- manifest sha256: `F8DC2ED0842246B624F771AC629ADEB3DE0B8050E041652E2BFE9432B4CD9B2A`

## Sidecar identity (both v3a logs)

- smoke (`dagger_r3`): identity_ok **True** | backend `torch-cpu` | run `bc_v3_a_s1` | handshakes ['run_1784880640_76087'] | serving {'stats_events': 23, 'errors_total': 0, 'served_max': 12095, 'model_ms_p99_max': 1.6045, 'total_acts': 12415}
- paired (`paired_eval`): identity_ok **True** | backend `torch-cpu` | run `bc_v3_a_s1` | handshakes ['run_1784882794_20877'] | serving {'stats_events': 148, 'errors_total': 0, 'served_max': 80449, 'model_ms_p99_max': 5.2609, 'total_acts': 80882}

## Gates

| gate | status | value | threshold | detail |
| --- | --- | --- | --- | --- |
| all_shards_written | PASS | 6 | 6 | 6/6 shards + aux + weights written |
| zero_encoding_faults | PASS | 0 | 0 | 0 ObservationError faults |
| valid_and_temporal_positive | PASS | 93203 | 1 | 93203 training-eligible rows |
| aux_weights_aligned | PASS | 6 | 6 | aux/weight arrays length == shard rows for every run |
| triple_reconciliation_ok | PASS | 1.0 | 1.0 | join_cov=1.0, ok_viol=0, clamp_viol=0, missing_act=0 |

Overall: **PASS**

## Aggregate

- total rows: 93,299
- valid: 93,299
- valid AND temporal_valid (training-eligible): 93,203
- encoding faults: 0
- risk episodes: 2,833

## Triple reconciliation (aggregate over both logs)

- join coverage: 1.0 (93,123/93,123 student ticks)
- ok ticks: 62,020 | violations (>1e-4): 0 | max|delta|: 0.00e+00
- clamped ticks: 31,103 | violations: 0 | max dir diff: 1.04e-06 | max |mag-1|: 7.14e-07
- timeout ticks: 174 (with act: 174) | not_connected: 2
- student ticks missing act: 0 | all reconciliation ok: True

Per-log breakdown:

| sidecar log | student ticks | join_cov | ok_viol | clamp_viol | missing | all_ok |
| --- | --- | --- | --- | --- | --- | --- |
| dagger_r3 | 12,392 | 1.0 | 0 | 0 | 0 | True |
| paired_eval | 80,731 | 1.0 | 0 | 0 | 0 | True |

## Aux label base rates (over horizon-valid rows)

- horizon-valid rows: 92,339
- aux_damage base rate (P hp-drop within 10 ticks): 0.012378
- aux_margin mean (1 - max future contact_risk): 0.715869

## Segment distribution (eligible rows)

Target 45/30/15/10 is on WEIGHT MASS (achieved via per-row weights), not row counts.

| segment | rows | row_fraction | mass_fraction (target) |
| --- | --- | --- | --- |
| background | 38,476 | 0.4128 | 0.45 (0.45) |
| precursor | 21,935 | 0.2353 | 0.3 (0.3) |
| onset_episode | 8,832 | 0.0948 | 0.15 (0.15) |
| recovery | 23,960 | 0.2571 | 0.1 (0.1) |

## Per-run

| run_id | smoke | log | rows | valid&temporal | episodes | dmg_rate | ctrl_frac | join_cov | wave | result | shard sha (16) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| run_1784880640_76087 | True | dagger_r3 | 12,416 | 12,403 | 357 | 0.011314 | 0.998067 | 1.0 | 13 | defeat | F9408385CD085CAE |
| run_1784882794_20877 | False | paired_eval | 20,702 | 20,680 | 589 | 0.011571 | 0.997923 | 1.0 | 20 | defeat | EEE83865B2FC47B5 |
| run_1784883926_57395 | False | paired_eval | 8,727 | 8,717 | 243 | 0.01391 | 0.998052 | 1.0 | 10 | defeat | EC282A3832E90B22 |
| run_1784884408_98596 | False | paired_eval | 9,913 | 9,902 | 334 | 0.019076 | 0.997882 | 1.0 | 11 | defeat | 0F3261F66D96F7EE |
| run_1784884958_1046 | False | paired_eval | 21,094 | 21,074 | 636 | 0.01723 | 0.998246 | 1.0 | 20 | defeat | F8C2AA086EE23AF6 |
| run_1784886119_60496 | False | paired_eval | 20,447 | 20,427 | 674 | 0.004939 | 0.998337 | 1.0 | 20 | defeat | FD638955C49A31DE |
