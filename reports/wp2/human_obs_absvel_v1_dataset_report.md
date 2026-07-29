# human_obs_v1 dataset build report

- schema_id: `human_obs_absvel_v1`
- observation schema hash: `19078CB750D1B79B1FD8890BCE5CAC043328B10950FE7E5A6206F22D68E1EC80`
- encoder: `trainer/observation/encoder_v1.py` @ `a84c69520fd909ec4d0014431edbc6e810f76279` (UNCHANGED)
- label: `payload.teacher.contributions.human` (x, y) — NOT teacher.action
- human_movement runs found: 22 | contributing: 12 | zero-row (excluded): 10

## Per-run (every denominator shown)

| run_id | mod | fixture | boss | captures | no human block | samples==0 | invalid | !temporal_valid | kept | aliased kept | zero kept |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| run_1785292468_624 | 0.2.50-wp2-capture | — | — | 579 | 579 | 0 | 0 | 0 | 0 | 0 | 0 |
| run_1785293060_85066 | 0.2.50-wp2-capture | — | — | 4,708 | 4,708 | 0 | 0 | 0 | 0 | 0 | 0 |
| run_1785293349_67067 | 0.2.50-wp2-capture | — | — | 4,552 | 4,552 | 0 | 0 | 0 | 0 | 0 | 0 |
| run_1785293625_21570 | 0.2.50-wp2-capture | — | — | 4,392 | 4,392 | 0 | 0 | 0 | 0 | 0 | 0 |
| run_1785294095_28250 | 0.2.50-wp2-capture | — | — | 4,972 | 4,972 | 0 | 0 | 0 | 0 | 0 | 0 |
| run_1785294383_41236 | 0.2.50-wp2-capture | — | — | 3,624 | 3,624 | 0 | 0 | 0 | 0 | 0 | 0 |
| run_1785294604_91856 | 0.2.50-wp2-capture | — | — | 3,574 | 3,574 | 0 | 0 | 0 | 0 | 0 | 0 |
| run_1785294826_52730 | 0.2.50-wp2-capture | — | — | 2,025 | 2,025 | 0 | 0 | 0 | 0 | 0 | 0 |
| run_1785296333_7237 | 0.2.50-wp2-capture | — | — | 20,576 | 20,576 | 0 | 0 | 0 | 0 | 0 | 0 |
| run_1785322980_39550 | 0.2.55-wp2-capture | 7f124906e6bb49cb | unknown | 3,348 | 3,348 | 0 | 0 | 0 | 0 | 0 | 0 |
| run_1785329874_94751 | 0.2.56-wp2-capture | 7f124906e6bb49cb | predator | 4,994 | 0 | 137 | 0 | 4 | 4,853 | 790 | 218 |
| run_1785330160_33134 | 0.2.56-wp2-capture | 7f124906e6bb49cb | predator | 4,478 | 0 | 136 | 0 | 4 | 4,338 | 677 | 220 |
| run_1785330775_74275 | 0.2.56-wp2-capture | 7f124906e6bb49cb | predator | 4,591 | 0 | 142 | 0 | 5 | 4,444 | 628 | 148 |
| run_1785331111_60809 | 0.2.56-wp2-capture | 7f124906e6bb49cb | predator | 4,322 | 0 | 146 | 0 | 4 | 4,172 | 598 | 172 |
| run_1785331403_7981 | 0.2.56-wp2-capture | 7f124906e6bb49cb | predator | 4,532 | 0 | 143 | 0 | 3 | 4,386 | 659 | 254 |
| run_1785331666_82193 | 0.2.56-wp2-capture | 7f124906e6bb49cb | predator | 4,590 | 0 | 136 | 0 | 4 | 4,450 | 644 | 108 |
| run_1785332630_89699 | 0.2.56-wp2-capture | ea8e819957f83f3b | predator | 4,439 | 0 | 141 | 0 | 6 | 4,292 | 589 | 190 |
| run_1785333345_28303 | 0.2.56-wp2-capture | fd3db2b0a5d75e35 | predator | 4,162 | 0 | 131 | 0 | 6 | 4,025 | 649 | 223 |
| run_1785334012_15712 | 0.2.56-wp2-capture | a6227734c5850b25 | predator | 4,438 | 0 | 136 | 0 | 3 | 4,299 | 697 | 309 |
| run_1785334264_36513 | 0.2.56-wp2-capture | 881b35244be74181 | invoker | 4,112 | 0 | 136 | 0 | 3 | 3,973 | 574 | 234 |
| run_1785334499_75976 | 0.2.56-wp2-capture | 359e272ac1d603cb | invoker | 4,135 | 0 | 125 | 0 | 4 | 4,006 | 548 | 269 |
| run_1785334810_44476 | 0.2.56-wp2-capture | 112a331720633b8a | invoker | 4,704 | 0 | 131 | 0 | 3 | 4,570 | 749 | 475 |

### Runs contributing ZERO rows (named, never vanished)

| run_id | mod | captures | reason |
| --- | --- | --- | --- |
| run_1785292468_624 | 0.2.50-wp2-capture | 579 | every capture lacked the teacher.contributions.human block (579/579 captures) -- pre-0.2.56 build |
| run_1785293060_85066 | 0.2.50-wp2-capture | 4,708 | every capture lacked the teacher.contributions.human block (4,708/4,708 captures) -- pre-0.2.56 build |
| run_1785293349_67067 | 0.2.50-wp2-capture | 4,552 | every capture lacked the teacher.contributions.human block (4,552/4,552 captures) -- pre-0.2.56 build |
| run_1785293625_21570 | 0.2.50-wp2-capture | 4,392 | every capture lacked the teacher.contributions.human block (4,392/4,392 captures) -- pre-0.2.56 build |
| run_1785294095_28250 | 0.2.50-wp2-capture | 4,972 | every capture lacked the teacher.contributions.human block (4,972/4,972 captures) -- pre-0.2.56 build |
| run_1785294383_41236 | 0.2.50-wp2-capture | 3,624 | every capture lacked the teacher.contributions.human block (3,624/3,624 captures) -- pre-0.2.56 build |
| run_1785294604_91856 | 0.2.50-wp2-capture | 3,574 | every capture lacked the teacher.contributions.human block (3,574/3,574 captures) -- pre-0.2.56 build |
| run_1785294826_52730 | 0.2.50-wp2-capture | 2,025 | every capture lacked the teacher.contributions.human block (2,025/2,025 captures) -- pre-0.2.56 build |
| run_1785296333_7237 | 0.2.50-wp2-capture | 20,576 | every capture lacked the teacher.contributions.human block (20,576/20,576 captures) -- pre-0.2.56 build |
| run_1785322980_39550 | 0.2.55-wp2-capture | 3,348 | every capture lacked the teacher.contributions.human block (3,348/3,348 captures) -- pre-0.2.56 build |

## Fixture-held-out split

- selection rule: explicit --val-fixture
- NO fixture appears in both sides (asserted at build time)
- train fixtures: 112a331720633b8a, 359e272ac1d603cb, 7f124906e6bb49cb, a6227734c5850b25, ea8e819957f83f3b
- val fixtures: 881b35244be74181, fd3db2b0a5d75e35
- train bosses: invoker, predator | val bosses: invoker, predator

| fixture | boss | split | runs | rows |
| --- | --- | --- | --- | --- |
| `112a331720633b8a` | invoker | train | 1 | 4,570 |
| `359e272ac1d603cb` | invoker | train | 1 | 4,006 |
| `881b35244be74181` | invoker | validation | 1 | 3,973 |
| `7f124906e6bb49cb` | predator | train | 6 | 26,643 |
| `a6227734c5850b25` | predator | train | 1 | 4,299 |
| `ea8e819957f83f3b` | predator | train | 1 | 4,292 |
| `fd3db2b0a5d75e35` | predator | validation | 1 | 4,025 |

- train runs: ['run_1785334810_44476', 'run_1785334499_75976', 'run_1785329874_94751', 'run_1785330160_33134', 'run_1785330775_74275', 'run_1785331111_60809', 'run_1785331403_7981', 'run_1785331666_82193', 'run_1785334012_15712', 'run_1785332630_89699'] (43,810 rows)
- val runs: ['run_1785334264_36513', 'run_1785333345_28303'] (7,998 rows)
- val row fraction: 0.1544 | val run fraction: 0.1667
- normalization stats: computed on the TRAIN split ONLY

## Label distribution (kept rows)

| direction | train | val | total | share |
| --- | --- | --- | --- | --- |
| E | 5,242 | 965 | 6,207 | 0.1198 |
| W | 5,158 | 920 | 6,078 | 0.1173 |
| S | 3,811 | 632 | 4,443 | 0.0858 |
| N | 3,440 | 614 | 4,054 | 0.0783 |
| SE | 5,848 | 1,047 | 6,895 | 0.1331 |
| SW | 5,791 | 1,159 | 6,950 | 0.1341 |
| NE | 5,874 | 1,081 | 6,955 | 0.1342 |
| NW | 6,283 | 1,123 | 7,406 | 0.1430 |
| ZERO | 2,363 | 457 | 2,820 | 0.0544 |
| OTHER | 0 | 0 | 0 | 0.0000 |

## Label statistics by `mod_version`

A build (or batch) change should be INERT for labels. If it is not,
that must be known BEFORE anything is trained on the pooled corpus.

| mod_version | runs | captures | kept | no-label rate | samples==0 rate | aliasing rate | zero-vector rate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0.2.56-wp2-capture | 12 | 53,497 | 51,808 | 0.0307 | 0.0307 | 0.1506 | 0.0544 |

- only ONE `mod_version` group is present, so there is nothing to compare across; the single group's rates are above.

## Label statistics by `trials_file`

A build (or batch) change should be INERT for labels. If it is not,
that must be known BEFORE anything is trained on the pooled corpus.

| trials_file | runs | captures | kept | no-label rate | samples==0 rate | aliasing rate | zero-vector rate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| human_bc2_v256.jsonl | 6 | 25,990 | 25,165 | 0.0308 | 0.0308 | 0.1512 | 0.0676 |
| human_bc_v256.jsonl | 6 | 27,507 | 26,643 | 0.0305 | 0.0305 | 0.1500 | 0.0420 |

| direction share | human_bc2_v256.jsonl | human_bc_v256.jsonl |
| --- | --- | --- |
| E | 0.1137 | 0.1256 |
| W | 0.1121 | 0.1223 |
| S | 0.0838 | 0.0876 |
| N | 0.0747 | 0.0816 |
| SE | 0.1346 | 0.1317 |
| SW | 0.1349 | 0.1334 |
| NE | 0.1374 | 0.1313 |
| NW | 0.1413 | 0.1445 |
| ZERO | 0.0676 | 0.0420 |
