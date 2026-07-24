# combat_dagger_r2 corrective dataset report

- student policy: `bc_v2_f_s1`
- schema hash: `C653D836F3EBC821A51AFC70482D3772FC7B7B927D393A6B9BBADC2718BB9B2A`
- encoder: `trainer/observation/encoder_v1.py` (frozen, reused build_run)
- builder: `scripts/wp2_build_combat_dagger_r2.py` @ `5682ba38a47b9045ce2f0acb8b80d5d3f4606356`
- runs: 6 | build wall: 102.3s
- dataset bytes: 137,902,727
- manifest sha256: `9B2C1E9184926716C361DB752237AC7F83AF4082CDF1DED03EDA6E2C65332A0B`

## Gates

| gate | status | value | threshold | detail |
| --- | --- | --- | --- | --- |
| all_shards_written | PASS | 6 | 6 | 6/6 shards + aux + weights written |
| zero_encoding_faults | PASS | 0 | 0 | 0 ObservationError faults |
| valid_and_temporal_positive | PASS | 116269 | 1 | 116269 training-eligible rows |
| aux_weights_aligned | PASS | 6 | 6 | aux/weight arrays length == shard rows for every run |
| triple_reconciliation_ok | PASS | 1.0 | 1.0 | join_cov=1.0, ok_viol=0, clamp_viol=0, missing_act=0 |

Overall: **PASS**

## Aggregate

- total rows: 116,386
- valid: 116,386
- valid AND temporal_valid (training-eligible): 116,269
- encoding faults: 0
- risk episodes: 3,614

## Triple reconciliation (aggregate)

- join coverage: 1.0 (116,182/116,182 student ticks)
- ok ticks: 67,974 | violations (>1e-4): 0 | max|delta|: 0.00e+00
- clamped ticks: 48,208 | violations: 0 | max dir diff: 1.05e-06 | max |mag-1|: 7.20e-07
- timeout ticks: 202 (with act: 202) | not_connected: 2
- student ticks missing act: 0 | all reconciliation ok: True

## Aux label base rates (over horizon-valid rows)

- horizon-valid rows: 115,216
- aux_damage base rate (P hp-drop within 10 ticks): 0.010346
- aux_margin mean (1 - max future contact_risk): 0.719785

## Segment distribution (eligible rows)

Target 45/30/15/10 is on WEIGHT MASS (achieved via per-row weights), not row counts.

| segment | rows | row_fraction | mass_fraction (target) |
| --- | --- | --- | --- |
| background | 50,563 | 0.4349 | 0.45 (0.45) |
| precursor | 26,727 | 0.2299 | 0.3 (0.3) |
| onset_episode | 10,284 | 0.0885 | 0.15 (0.15) |
| recovery | 28,695 | 0.2468 | 0.1 (0.1) |

## Per-run

| run_id | smoke | rows | valid&temporal | episodes | dmg_rate | ctrl_frac | join_cov | wave | result | shard sha (16) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| run_1784873462_1600 | False | 15,982 | 15,963 | 537 | 0.01811 | 0.998248 | 1.0 | 16 | defeat | D0EAE91BE5F35B83 |
| run_1784874327_52508 | False | 20,838 | 20,818 | 611 | 0.007753 | 0.998032 | 1.0 | 20 | defeat | F96B289AD42B1739 |
| run_1784875463_98163 | False | 21,497 | 21,477 | 734 | 0.010706 | 0.998604 | 1.0 | 20 | victory | 1C3322114DB0458A |
| run_1784876633_43940 | False | 17,158 | 17,141 | 427 | 0.007005 | 0.998426 | 1.0 | 17 | defeat | 220D4E152E850E90 |
| run_1784877573_54783 | False | 20,585 | 20,565 | 699 | 0.012264 | 0.998105 | 1.0 | 20 | defeat | CB9D59F247717364 |
| run_1784872256_15901 | True | 20,326 | 20,305 | 606 | 0.007407 | 0.998081 | 1.0 | 20 | defeat | 7A05BBE871528EED |
