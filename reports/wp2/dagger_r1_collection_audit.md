# DAgger round-1 collection audit (Stage A)

- campaign policy: `teacher_v1-0.1.125-gun-wp1`
- mod version: `0.2.34-wp2-capture`
- expected capture schema hash: `95B6444796A21FD44E94113B75BA2097BC381D5F72ED784F9B9A4A99DD46D951`
- expected model sha256: `BE7E82326EC8A424A1EDF33134E65A26E06EDA68DA7F22D37705F3C26D6A9F0F`
- student-control inclusion gate: >= 0.95
- smoke: False

## Sidecar identity

- identity_ok: **True** | backend: `torch-cpu`
- model_sha256: `BE7E82326EC8A424A1EDF33134E65A26E06EDA68DA7F22D37705F3C26D6A9F0F`
- checks: {'model_sha256': True, 'normalization_sha256': True, 'observation_schema_hash': True, 'registry_run_name': True}
- handshake run_ids: ['run_1784863478_12397']
- serving: {'stats_events': 145, 'errors_total': 0, 'served_max': 78571, 'model_ms_p99_max': 3.196}

## Per-run verdicts

| run_id | verdict | ctrl_frac | student | fallback | clamp | lat p50/p99/max | captures | wave | result | errors | hangs | teacher.action miss | schema mismatch |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| run_1784863478_12397 | include | 0.9985 | 14795 | 22 | 5545 | 15.0/20.0/197.0 | 14817 | 15 | defeat | 0 | 0 | 0 | 0 |
| run_1784864302_38172 | include | 0.9985 | 20690 | 31 | 8605 | 15.0/19.0/189.0 | 20721 | 20 | defeat | 0 | 0 | 0 | 0 |
| run_1784865437_64140 | include | 0.9978 | 20225 | 44 | 7047 | 15.0/18.0/286.0 | 20269 | 20 | defeat | 0 | 0 | 0 | 0 |
| run_1784866560_35665 | include | 0.9979 | 14480 | 30 | 5271 | 15.0/20.0/212.0 | 14510 | 15 | defeat | 0 | 0 | 0 | 0 |
| run_1784867357_2622 | include | 0.9980 | 8621 | 17 | 3084 | 15.0/19.0/196.0 | 8638 | 10 | defeat | 0 | 0 | 0 | 0 |


Included runs (5): ['run_1784863478_12397', 'run_1784864302_38172', 'run_1784865437_64140', 'run_1784866560_35665', 'run_1784867357_2622']
Excluded runs (0): []

Overall: **PASS**
