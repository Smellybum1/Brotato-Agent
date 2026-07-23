# combat_obs_v1 dataset build report

- schema_id: `combat_obs_v1`
- observation schema hash: `C653D836F3EBC821A51AFC70482D3772FC7B7B927D393A6B9BBADC2718BB9B2A`
- source capture schema hash: `95B6444796A21FD44E94113B75BA2097BC381D5F72ED784F9B9A4A99DD46D951`
- encoder: `trainer/observation/encoder_v1.py` @ `0be6c80875b5e729e099d5d3384628e57de7de4c`
- runs: 20 | build wall time: 228.3s
- dataset size on disk: 400,773,981 bytes

## Gates

| gate | status | value | threshold | detail |
| --- | --- | --- | --- | --- |
| valid_and_temporal_valid_min | PASS | 387695 | 200000 | 387695 >= 200000 |
| all_waves_1_20_represented | PASS | 20 | 20 | all waves 1-20 present among valid samples |
| zero_encoding_faults | PASS | 0 | 0 | 0 ObservationError faults |
| all_shards_written | PASS | 20 | 20 | 20/20 shards written with checksums |
| capacity_overflow | REPORT | see below | n/a | report-only, primary decides |

Overall: **PASS** (overflow gate is report-only)

## Aggregate counts

- total samples: 388,067
- valid: 388,067
- temporal_valid: 387,695
- valid AND temporal_valid: 387,695
- encoding faults: 0

## Per-wave valid sample counts (aggregate)

| wave | valid samples |
| --- | --- |
| 1 | 8,800 |
| 2 | 10,909 |
| 3 | 12,841 |
| 4 | 14,849 |
| 5 | 16,919 |
| 6 | 18,869 |
| 7 | 20,876 |
| 8 | 22,912 |
| 9 | 25,004 |
| 10 | 24,379 |
| 11 | 22,442 |
| 12 | 22,422 |
| 13 | 22,397 |
| 14 | 22,399 |
| 15 | 22,398 |
| 16 | 22,428 |
| 17 | 21,993 |
| 18 | 18,642 |
| 19 | 18,679 |
| 20 | 17,909 |

Waves 17-20 tail: 77,223 valid (0.1990 of valid samples)

## Capacity overflow (REPORT-ONLY)

| group | capacity | overflow samples | max raw entity count |
| --- | --- | --- | --- |
| enemies | 64 | 0 | 61 |
| bosses | 2 | 0 | 1 |
| projectiles | 32 | 0 | 32 |
| materials | 64 | 0 | 54 |
| consumables | 24 | 0 | 18 |
| crates | 2 | 263 | 4 |
| obstacles | 8 | 0 | 5 |

## Per-run shards

| run_id | samples | valid&temporal | faults | shard sha256 (first 16) |
| --- | --- | --- | --- | --- |
| run_1784785556_51395 | 21,061 | 21,041 | 0 | CB1C99EB90FE5EAF |
| run_1784786723_17546 | 17,341 | 17,323 | 0 | 14F164D6E95FA514 |
| run_1784787688_32406 | 21,795 | 21,775 | 0 | CB8D965D26C7DAB0 |
| run_1784788917_7315 | 21,013 | 20,993 | 0 | A53940859CA05E76 |
| run_1784790063_90333 | 20,835 | 20,815 | 0 | 78E8BD1ECF1A0112 |
| run_1784791214_74323 | 17,478 | 17,461 | 0 | 39D333E8BF87D4A1 |
| run_1784792179_82981 | 8,638 | 8,628 | 0 | 501DA5ECED7EA145 |
| run_1784792652_7723 | 21,852 | 21,832 | 0 | F5C9613379CC34FD |
| run_1784793833_32034 | 17,416 | 17,399 | 0 | 79F07FA0A97A59CD |
| run_1784794784_69267 | 20,860 | 20,840 | 0 | 30416D586A22171A |
| run_1784795927_93597 | 21,059 | 21,039 | 0 | 38156018591DA1EA |
| run_1784797082_83949 | 21,616 | 21,596 | 0 | 7E4782C9E2E38F4D |
| run_1784798249_41022 | 21,111 | 21,091 | 0 | 8C0D96A71E6382CC |
| run_1784799404_80018 | 20,926 | 20,906 | 0 | 60680F5C112CABD0 |
| run_1784800561_47448 | 21,313 | 21,293 | 0 | 5B22DFBC43E01F7E |
| run_1784801716_88465 | 8,550 | 8,540 | 0 | FC9D754C16DA83C8 |
| run_1784802191_76892 | 20,568 | 20,548 | 0 | E5DE81C3C37C6276 |
| run_1784803299_7195 | 21,060 | 21,040 | 0 | 4F3B0864DA6E3936 |
| run_1784804435_39794 | 21,730 | 21,710 | 0 | 656018B37B745D87 |
| run_1784805636_10804 | 21,845 | 21,825 | 0 | EBCD92A8C1EFB72B |
