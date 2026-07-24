# DAgger round-2 collection audit (Stage A)

- campaign policy: `teacher_v1-0.1.125-gun-wp1`
- mod version: `0.2.34-wp2-capture`
- student policy: `bc_v2_f_s1`
- expected capture schema hash: `95B6444796A21FD44E94113B75BA2097BC381D5F72ED784F9B9A4A99DD46D951`
- expected model sha256: `1AD517B04843B69966841C7B795B927AE86B2727789456224321FC091F29F331`
- student-control inclusion gate: >= 0.95
- smoke: False

## Sidecar identity

- identity_ok: **True** | backend: `torch-cpu`
- model_sha256: `1AD517B04843B69966841C7B795B927AE86B2727789456224321FC091F29F331`
- checks: {'model_sha256': True, 'normalization_sha256': True, 'observation_schema_hash': True, 'registry_run_name': True}
- handshake run_ids: ['run_1784872256_15901', 'run_1784873462_1600']
- serving: {'stats_events': 211, 'errors_total': 0, 'served_max': 115928, 'model_ms_p99_max': 4.4651, 'total_acts': 116384}

## Per-run verdicts

| run_id | smoke | verdict | ctrl_frac | student | fallback | clamp | lat p50/p99/max | captures | wave | result | errors | hangs | tchr.act miss | schema mism |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| run_1784873462_1600 | False | include | 0.9982 | 15954 | 28 | 6307 | 15.0/19.0/239.0 | 15982 | 16 | defeat | 0 | 0 | 0 | 0 |
| run_1784874327_52508 | False | include | 0.9980 | 20797 | 41 | 8524 | 15.0/17.0/179.0 | 20838 | 20 | defeat | 0 | 0 | 0 | 0 |
| run_1784875463_98163 | False | include | 0.9986 | 21467 | 30 | 8219 | 15.0/18.0/211.0 | 21497 | 20 | victory | 0 | 0 | 0 | 0 |
| run_1784876633_43940 | False | include | 0.9984 | 17131 | 27 | 7756 | 15.0/18.0/197.0 | 17158 | 17 | defeat | 0 | 0 | 0 | 0 |
| run_1784877573_54783 | False | include | 0.9981 | 20546 | 39 | 8013 | 15.0/19.0/163.0 | 20585 | 20 | defeat | 0 | 0 | 0 | 0 |
| run_1784872256_15901 | True | include | 0.9981 | 20287 | 39 | 9389 | 14.0/20.0/280.0 | 20326 | 20 | defeat | 0 | 0 | 0 | 0 |

## Triple reconciliation (proposal / executed / intervention)

| run_id | conn | join_cov | ok_ticks | ok_maxD | ok_viol | clamp_ticks | clamp_dirD | clamp_magErr | clamp_viol | tmout(act) | miss | recon_ok |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| run_1784873462_1600 | 1 | 1.0000 | 9647 | 0.00e+00 | 0 | 6307 | 1.01e-06 | 6.85e-07 | 0 | 27(27) | 0 | True |
| run_1784874327_52508 | 1 | 1.0000 | 12273 | 0.00e+00 | 0 | 8524 | 1.03e-06 | 7.16e-07 | 0 | 41(41) | 0 | True |
| run_1784875463_98163 | 1 | 1.0000 | 13248 | 0.00e+00 | 0 | 8219 | 1.05e-06 | 7.03e-07 | 0 | 30(30) | 0 | True |
| run_1784876633_43940 | 1 | 1.0000 | 9375 | 0.00e+00 | 0 | 7756 | 1.05e-06 | 7.20e-07 | 0 | 27(27) | 0 | True |
| run_1784877573_54783 | 1 | 1.0000 | 12533 | 0.00e+00 | 0 | 8013 | 9.59e-07 | 7.02e-07 | 0 | 39(39) | 0 | True |
| run_1784872256_15901 | 0 | 1.0000 | 10898 | 0.00e+00 | 0 | 9389 | 1.05e-06 | 7.07e-07 | 0 | 38(38) | 0 | True |

## Connection-level act accounting

| connection | handshake run | acts_total | applied | timeout_not_applied | orphan_no_tick |
| --- | --- | --- | --- | --- | --- |
| 0 | run_1784872256_15901 | 20325 | 20287 | 38 | 0 |
| 1 | run_1784873462_1600 | 96059 | 95895 | 164 | 0 |


Included runs (6): ['run_1784873462_1600', 'run_1784874327_52508', 'run_1784875463_98163', 'run_1784876633_43940', 'run_1784877573_54783', 'run_1784872256_15901']
Excluded runs (0): []

Overall: **PASS**
