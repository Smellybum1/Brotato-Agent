# combat_dagger_r1 corrective dataset report

- schema hash: `C653D836F3EBC821A51AFC70482D3772FC7B7B927D393A6B9BBADC2718BB9B2A`
- encoder: `trainer/observation/encoder_v1.py` (frozen, reused build_run)
- builder: `scripts/wp2_build_combat_dagger_r1.py` @ `a29fc8a0cf8e146c6e042f63bfd2124d9503c136`
- runs: 5 | build wall: 42.4s
- dataset bytes: 82,901,982
- manifest sha256: `7AF8403FD4C39CAFCEA19CAF9CAEFB05AF7DD5418DDF5A4AEDF01CBBCD35EE84`

## Gates

| gate | status | value | threshold | detail |
| --- | --- | --- | --- | --- |
| all_shards_written | PASS | 5 | 5 | 5/5 shards + aux + weights written |
| zero_encoding_faults | PASS | 0 | 0 | 0 ObservationError faults |
| valid_and_temporal_positive | PASS | 78874 | 1 | 78874 training-eligible rows |
| aux_weights_aligned | PASS | 5 | 5 | aux/weight arrays length == shard rows for every run |

Overall: **PASS**

## Aggregate

- total rows: 78,955
- valid: 78,955
- valid AND temporal_valid (training-eligible): 78,874
- encoding faults: 0
- risk episodes: 1,599

## Aux label base rates (over horizon-valid rows)

- horizon-valid rows: 78,145
- aux_damage base rate (P hp-drop within 10 ticks): 0.018363
- aux_margin mean (1 - max future contact_risk): 0.760549

## Segment distribution (eligible rows)

Target 45/30/15/10 is on WEIGHT MASS (achieved via per-row weights), not row counts.

| segment | rows | row_fraction | mass_fraction (target) |
| --- | --- | --- | --- |
| background | 41,735 | 0.5291 | 0.45 (0.45) |
| precursor | 13,055 | 0.1655 | 0.3 (0.3) |
| onset_episode | 7,764 | 0.0984 | 0.15 (0.15) |
| recovery | 16,320 | 0.2069 | 0.1 (0.1) |

## Per-run

| run_id | rows | valid&temporal | episodes | dmg_rate | ctrl_frac | wave | result | shard sha (16) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| run_1784863478_12397 | 14,817 | 14,802 | 287 | 0.02884 | 0.998515 | 15 | defeat | 307E7A45267233B4 |
| run_1784864302_38172 | 20,721 | 20,700 | 471 | 0.015455 | 0.998504 | 20 | defeat | 704B97D60214821D |
| run_1784865437_64140 | 20,269 | 20,249 | 385 | 0.007474 | 0.997829 | 20 | defeat | EA08165217DE352F |
| run_1784866560_35665 | 14,510 | 14,495 | 313 | 0.019081 | 0.997932 | 15 | defeat | A7464900B2EC4534 |
| run_1784867357_2622 | 8,638 | 8,628 | 143 | 0.03174 | 0.998032 | 10 | defeat | 55D7FC850FAEDC08 |
