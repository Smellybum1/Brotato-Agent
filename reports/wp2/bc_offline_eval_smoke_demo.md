# BC offline evaluation — `smoke_demo`

Generated 2026-07-24 02:16:36 · checkpoint `best` · 1 run(s). Metrics recomputed independently from the frozen dataset + saved checkpoints (metrics.jsonl not trusted). Findings only.

## Sanity gates

Model must beat BOTH baselines (copy-previous, mean-direction) on median AND mean validation angular error.

| run | median gate | mean gate | overall | model med° | copy med° | mean-dir med° | model mean° | copy mean° | mean-dir mean° |
|---|---|---|---|---|---|---|---|---|---|
| bc_v1_s1_20260724_020529 | FAIL | FAIL | FAIL | 12.87 | 4.32 | 86.93 | 24.65 | 21.20 | 87.99 |

## Overall validation metrics

| run | seed | n | val_loss | median ang° | mean ang° | cosine | |mag err| | sat frac |
|---|---|---|---|---|---|---|---|---|
| bc_v1_s1_20260724_020529 | 1 | 81790 | 0.1943 | 12.87 | 24.65 | 0.817 | 0.158 | 0.0000 |

## Baselines (per run)

### bc_v1_s1_20260724_020529

| stratum | n | median ang° | mean ang° | cosine | |mag err| | sat frac |
|---|---|---|---|---|---|---|
| mean-direction | 81790 | 86.93 | 87.99 | 0.023 | 0.000 | 0.0000 |
| copy-previous | 81790 | 4.32 | 21.20 | 0.814 | 0.000 | 0.0784 |

## Strata — bc_v1_s1_20260724_020529

### By wave band

| stratum | n | median ang° | mean ang° | cosine | |mag err| | sat frac |
|---|---|---|---|---|---|---|
| 1-5 | 12828 | 11.39 | 15.55 | 0.932 | 0.147 | 0.0000 |
| 6-10 | 22470 | 11.39 | 18.05 | 0.897 | 0.123 | 0.0000 |
| 11-15 | 24925 | 12.05 | 20.94 | 0.863 | 0.145 | 0.0000 |
| 16-19 | 17324 | 17.16 | 40.02 | 0.625 | 0.218 | 0.0000 |
| 20 | 4243 | 22.17 | 46.18 | 0.559 | 0.209 | 0.0000 |

### By risk stratum

| stratum | n | median ang° | mean ang° | cosine | |mag err| | sat frac |
|---|---|---|---|---|---|---|
| 0.00-0.25 | 71206 | 12.61 | 23.16 | 0.836 | 0.160 | 0.0000 |
| 0.25-0.50 | 8004 | 12.99 | 28.40 | 0.767 | 0.140 | 0.0000 |
| 0.50-0.75 | 2384 | 26.14 | 53.42 | 0.466 | 0.164 | 0.0000 |
| 0.75-inf | 196 | 50.56 | 65.95 | 0.313 | 0.207 | 0.0000 |

### By validation run

| run_id | outcome | last_wave | n | median ang° | mean ang° | cosine | |mag err| | sat frac |
|---|---|---|---|---|---|---|---|---|
| run_1784787688_32406 | victory | 20 | 21775 | 12.46 | 24.20 | 0.822 | 0.165 | 0.0000 |
| run_1784793833_32034 | defeat | 17 | 17399 | 12.58 | 22.83 | 0.840 | 0.140 | 0.0000 |
| run_1784799404_80018 | defeat | 20 | 20906 | 13.81 | 25.17 | 0.815 | 0.159 | 0.0000 |
| run_1784804435_39794 | victory | 20 | 21710 | 12.61 | 26.08 | 0.797 | 0.163 | 0.0000 |

