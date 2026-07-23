# WP2 v122 exact-20 teacher safety audit

Campaign: 20 fresh version-matched runs, policy `teacher_v1-0.1.122-gun-wp1`, mod `0.2.30-wp2-capture`, schema `95B6444796A21FD44E94113B75BA2097BC381D5F72ED784F9B9A4A99DD46D951`.

Runs: **20**; accepted (zero-violation): **17**; rejected: **3**; aggregate violations: **3**.
Total captures across 20 runs: **388067**. Captures in the 17-run inclusion set: **322697** (>= 200,000 floor).

## Inclusion / exclusion

- INCLUSION (17): pass safety + capture audits, zero violations.
  - `run_1784785556_51395` (victory w20, 21061 captures)
  - `run_1784786723_17546` (defeat w17, 17341 captures)
  - `run_1784788917_7315` (defeat w20, 21013 captures)
  - `run_1784790063_90333` (defeat w20, 20835 captures)
  - `run_1784791214_74323` (defeat w17, 17478 captures)
  - `run_1784792179_82981` (defeat w10, 8638 captures)
  - `run_1784792652_7723` (victory w20, 21852 captures)
  - `run_1784793833_32034` (defeat w17, 17416 captures)
  - `run_1784794784_69267` (victory w20, 20860 captures)
  - `run_1784795927_93597` (victory w20, 21059 captures)
  - `run_1784797082_83949` (victory w20, 21616 captures)
  - `run_1784798249_41022` (victory w20, 21111 captures)
  - `run_1784799404_80018` (defeat w20, 20926 captures)
  - `run_1784800561_47448` (victory w20, 21313 captures)
  - `run_1784801716_88465` (defeat w10, 8550 captures)
  - `run_1784802191_76892` (defeat w20, 20568 captures)
  - `run_1784803299_7195` (victory w20, 21060 captures)
- EXCLUSION (3): one safety violation each (raw detail below; primary agent decides).
  - `run_1784787688_32406` (victory w20, 21795 captures)
  - `run_1784804435_39794` (victory w20, 21730 captures)
  - `run_1784805636_10804` (victory w20, 21845 captures)

## Per-run one-line summary

| # | run_id | result | wv | captures | fresh | late | violations | accepted |
|--:|---|---|--:|--:|--:|--:|--:|:--|
| 1 | run_1784785556_51395 | victory | 20 | 21061 | 21061 | 4721 | 0 | yes |
| 2 | run_1784786723_17546 | defeat | 17 | 17341 | 17341 | 1060 | 0 | yes |
| 3 | run_1784787688_32406 | victory | 20 | 21795 | 21795 | 5455 | 1 | NO |
| 4 | run_1784788917_7315 | defeat | 20 | 21013 | 21013 | 4716 | 0 | yes |
| 5 | run_1784790063_90333 | defeat | 20 | 20835 | 20835 | 4526 | 0 | yes |
| 6 | run_1784791214_74323 | defeat | 17 | 17478 | 17478 | 1163 | 0 | yes |
| 7 | run_1784792179_82981 | defeat | 10 | 8638 | 8638 | 0 | 0 | yes |
| 8 | run_1784792652_7723 | victory | 20 | 21852 | 21852 | 5521 | 0 | yes |
| 9 | run_1784793833_32034 | defeat | 17 | 17416 | 17416 | 1134 | 0 | yes |
| 10 | run_1784794784_69267 | victory | 20 | 20860 | 20860 | 4540 | 0 | yes |
| 11 | run_1784795927_93597 | victory | 20 | 21059 | 21059 | 4750 | 0 | yes |
| 12 | run_1784797082_83949 | victory | 20 | 21616 | 21616 | 5301 | 0 | yes |
| 13 | run_1784798249_41022 | victory | 20 | 21111 | 21111 | 4769 | 0 | yes |
| 14 | run_1784799404_80018 | defeat | 20 | 20926 | 20926 | 4601 | 0 | yes |
| 15 | run_1784800561_47448 | victory | 20 | 21313 | 21313 | 5008 | 0 | yes |
| 16 | run_1784801716_88465 | defeat | 10 | 8550 | 8550 | 0 | 0 | yes |
| 17 | run_1784802191_76892 | defeat | 20 | 20568 | 20568 | 4265 | 0 | yes |
| 18 | run_1784803299_7195 | victory | 20 | 21060 | 21060 | 4757 | 0 | yes |
| 19 | run_1784804435_39794 | victory | 20 | 21730 | 21730 | 5410 | 1 | NO |
| 20 | run_1784805636_10804 | victory | 20 | 21845 | 21845 | 5526 | 1 | NO |

## Raw violation details

### `run_1784787688_32406` -- 1 violation
- `wall_body_relief_selection_violations`:
  - {"capture_seq": 18676, "selected": 131.635452, "relief_best": -21.009933, "required": -41.009933000000004}

### `run_1784804435_39794` -- 1 violation
- `body_tier_violations`:
  - {"capture_seq": 17442, "input": 19.031828, "best": 43.438971, "selected": 19.031828, "required": 23.438971000000002}

### `run_1784805636_10804` -- 1 violation
- `body_repair_violations`:
  - {"capture_seq": 9722, "input": 44.944609, "best": 45.668119, "selected": 45.668119, "active": false}

## Per-run detail

### `run_1784785556_51395` -- accepted

- Result: `victory` through wave 20.
- Captures: 21061 total; 21061 fresh; 4721 late; 4721 fresh late.
- Safety activations: 8404 body, 994 projectile, 4095 wall, 1963 wall-body relief.
- Violations: **0**. Avoidable damage-path: 0. Hidden wall-relief lanes: 0.
- Damage events retained for review: 13. Preserved-command body fallbacks w/o projectile-floor sample: 186.
- Events SHA-256: `7BF0B7E68148D25DB89E35A77745C2923DFB648E0CD71633A31DE2412F8A50D2`.
- Summary SHA-256: `8E543ED4C14526CF93731A2F747588742DADE64A0BF86F5E0DDD56E8D2C5BDC0`.

### `run_1784786723_17546` -- accepted

- Result: `defeat` through wave 17.
- Captures: 17341 total; 17341 fresh; 1060 late; 1060 fresh late.
- Safety activations: 7788 body, 557 projectile, 781 wall, 183 wall-body relief.
- Violations: **0**. Avoidable damage-path: 0. Hidden wall-relief lanes: 0.
- Damage events retained for review: 19. Preserved-command body fallbacks w/o projectile-floor sample: 107.
- Events SHA-256: `A982E2A6AE2D4B746161E524B60BE65870EEE6E17F7074E098AABD7DC066F407`.
- Summary SHA-256: `FB7C0B972B663D1C3D465B8AD26B59EE329C7AFECFC7787DDC7A2A73DE5B3CD2`.

### `run_1784787688_32406` -- rejected

- Result: `victory` through wave 20.
- Captures: 21795 total; 21795 fresh; 5455 late; 5455 fresh late.
- Safety activations: 7907 body, 1443 projectile, 3892 wall, 1621 wall-body relief.
- Violations: **1**. Avoidable damage-path: 0. Hidden wall-relief lanes: 0.
- Damage events retained for review: 15. Preserved-command body fallbacks w/o projectile-floor sample: 337.
- Events SHA-256: `B8C96D24C2146A46328BF0FD8A0E1850D2609EC1B6408519540D15DE2BFBAC18`.
- Summary SHA-256: `16090B0A07EF9979C0357F59E2292E23669E9645D9D73691052483B1E814AA85`.

### `run_1784788917_7315` -- accepted

- Result: `defeat` through wave 20.
- Captures: 21013 total; 21013 fresh; 4716 late; 4716 fresh late.
- Safety activations: 8873 body, 830 projectile, 3561 wall, 1827 wall-body relief.
- Violations: **0**. Avoidable damage-path: 0. Hidden wall-relief lanes: 0.
- Damage events retained for review: 22. Preserved-command body fallbacks w/o projectile-floor sample: 231.
- Events SHA-256: `AA57907B96B0A34B949CC576530212A7F5BAE362BCB0457A4535085F8D3EEC8A`.
- Summary SHA-256: `1FD4279D867EFC257BA37ABCD820CF6FD4E4D4CBC4B26F964F95BCEC46B98204`.

### `run_1784790063_90333` -- accepted

- Result: `defeat` through wave 20.
- Captures: 20835 total; 20835 fresh; 4526 late; 4526 fresh late.
- Safety activations: 7598 body, 1363 projectile, 3302 wall, 1253 wall-body relief.
- Violations: **0**. Avoidable damage-path: 0. Hidden wall-relief lanes: 0.
- Damage events retained for review: 4. Preserved-command body fallbacks w/o projectile-floor sample: 185.
- Events SHA-256: `5D4548AC13D96BC1A28A3608C280980B9A549CF67F81BCEA13F63617FC79BD10`.
- Summary SHA-256: `1968E57600D0E8A8DB6FFEBBAA178A6B3E5466C939D4715063834CEBC9A5AFB9`.

### `run_1784791214_74323` -- accepted

- Result: `defeat` through wave 17.
- Captures: 17478 total; 17478 fresh; 1163 late; 1163 fresh late.
- Safety activations: 6007 body, 236 projectile, 781 wall, 415 wall-body relief.
- Violations: **0**. Avoidable damage-path: 0. Hidden wall-relief lanes: 0.
- Damage events retained for review: 3. Preserved-command body fallbacks w/o projectile-floor sample: 54.
- Events SHA-256: `DBB5AAA498254ADE0B99FBAEE61B40B88846E8D8ACB388240B9FCCD3CECAFDD5`.
- Summary SHA-256: `4EFAE699258C9CE24C22F5D77FD063D59B5867D9D9569D3787EE6218AB731BC9`.

### `run_1784792179_82981` -- accepted

- Result: `defeat` through wave 10.
- Captures: 8638 total; 8638 fresh; 0 late; 0 fresh late.
- Safety activations: 3386 body, 0 projectile, 0 wall, 0 wall-body relief.
- Violations: **0**. Avoidable damage-path: 0. Hidden wall-relief lanes: 0.
- Damage events retained for review: 9. Preserved-command body fallbacks w/o projectile-floor sample: 0.
- Events SHA-256: `C7EFF555BB3AFB2F44859860D613153BCD6F2D92F6D2A8974146A73C0CD64AD4`.
- Summary SHA-256: `DB23AB416743DBE684CADDF45D14DA180E0947C15951589E50D4D64871ECCFD0`.

### `run_1784792652_7723` -- accepted

- Result: `victory` through wave 20.
- Captures: 21852 total; 21852 fresh; 5521 late; 5521 fresh late.
- Safety activations: 8758 body, 2011 projectile, 4600 wall, 1855 wall-body relief.
- Violations: **0**. Avoidable damage-path: 0. Hidden wall-relief lanes: 0.
- Damage events retained for review: 5. Preserved-command body fallbacks w/o projectile-floor sample: 135.
- Events SHA-256: `800C87BB4FA31DEC64E0FFFE223FE6FA6533D0342A52A04F22EBDDA4F15E1567`.
- Summary SHA-256: `53FAA8F0C2762D617818F3EBCE96585672006A6784E041DCAF7BF0443529184C`.

### `run_1784793833_32034` -- accepted

- Result: `defeat` through wave 17.
- Captures: 17416 total; 17416 fresh; 1134 late; 1134 fresh late.
- Safety activations: 8173 body, 321 projectile, 727 wall, 273 wall-body relief.
- Violations: **0**. Avoidable damage-path: 0. Hidden wall-relief lanes: 0.
- Damage events retained for review: 15. Preserved-command body fallbacks w/o projectile-floor sample: 110.
- Events SHA-256: `5416EBF273E97BA8E77682E29353D7367D7D3553FD922673A072240F3A2FCEA0`.
- Summary SHA-256: `BCA2F3EEBF535CAEE6CA32D31450222874C957DC2D5D4839A25CA57DF815BD02`.

### `run_1784794784_69267` -- accepted

- Result: `victory` through wave 20.
- Captures: 20860 total; 20860 fresh; 4540 late; 4540 fresh late.
- Safety activations: 7814 body, 772 projectile, 2077 wall, 787 wall-body relief.
- Violations: **0**. Avoidable damage-path: 0. Hidden wall-relief lanes: 0.
- Damage events retained for review: 2. Preserved-command body fallbacks w/o projectile-floor sample: 60.
- Events SHA-256: `EDFFB67968D0A0A539452E96687037719A97E8ED6EBFD0C22AB4879CB970D30B`.
- Summary SHA-256: `288B0E567A2211DAEED3AA6DF574577A99B3B1FA043D2588BEE8B24ADCF94E67`.

### `run_1784795927_93597` -- accepted

- Result: `victory` through wave 20.
- Captures: 21059 total; 21059 fresh; 4750 late; 4750 fresh late.
- Safety activations: 9481 body, 1508 projectile, 3604 wall, 1423 wall-body relief.
- Violations: **0**. Avoidable damage-path: 0. Hidden wall-relief lanes: 0.
- Damage events retained for review: 15. Preserved-command body fallbacks w/o projectile-floor sample: 317.
- Events SHA-256: `033DA593165B960176CE781200DD33F6F682C69E4D664EF3D590DE602ADD2DB5`.
- Summary SHA-256: `B9ADD8782BFA37336AE1405E2B487F247D5490E3C47CA6BCB7F846928863EEFD`.

### `run_1784797082_83949` -- accepted

- Result: `victory` through wave 20.
- Captures: 21616 total; 21616 fresh; 5301 late; 5301 fresh late.
- Safety activations: 8234 body, 1480 projectile, 4101 wall, 1977 wall-body relief.
- Violations: **0**. Avoidable damage-path: 0. Hidden wall-relief lanes: 0.
- Damage events retained for review: 11. Preserved-command body fallbacks w/o projectile-floor sample: 101.
- Events SHA-256: `7B8624C98186DC4339115FCCDB1E1433AFBF1AAA15C8ADB7E66AD2A246A35E7B`.
- Summary SHA-256: `7A8E9821B578D3F42ED95BE6BDBB52593F4DAC0FBE69F64F3F42396FF74F19F3`.

### `run_1784798249_41022` -- accepted

- Result: `victory` through wave 20.
- Captures: 21111 total; 21111 fresh; 4769 late; 4769 fresh late.
- Safety activations: 8229 body, 1120 projectile, 3218 wall, 1503 wall-body relief.
- Violations: **0**. Avoidable damage-path: 0. Hidden wall-relief lanes: 0.
- Damage events retained for review: 6. Preserved-command body fallbacks w/o projectile-floor sample: 123.
- Events SHA-256: `BC1321CE5F0395D8CCF09101E26A4A294D9375C4B030A9F035A135F9A5B7B074`.
- Summary SHA-256: `E458CBD008347ABA36A14BE31CE6317B4465A762CA73AB8D234A5E3A9CD20249`.

### `run_1784799404_80018` -- accepted

- Result: `defeat` through wave 20.
- Captures: 20926 total; 20926 fresh; 4601 late; 4601 fresh late.
- Safety activations: 8464 body, 1276 projectile, 3560 wall, 1535 wall-body relief.
- Violations: **0**. Avoidable damage-path: 0. Hidden wall-relief lanes: 0.
- Damage events retained for review: 7. Preserved-command body fallbacks w/o projectile-floor sample: 248.
- Events SHA-256: `7D24D67B74CF065605832D75F54C39147CF68220A1122A1551B336E293F2291C`.
- Summary SHA-256: `7CEC671A812999953B9763A01A28799D4F8562488523B30E043530DFF7ECF0D7`.

### `run_1784800561_47448` -- accepted

- Result: `victory` through wave 20.
- Captures: 21313 total; 21313 fresh; 5008 late; 5008 fresh late.
- Safety activations: 7768 body, 1787 projectile, 4181 wall, 1673 wall-body relief.
- Violations: **0**. Avoidable damage-path: 0. Hidden wall-relief lanes: 0.
- Damage events retained for review: 2. Preserved-command body fallbacks w/o projectile-floor sample: 251.
- Events SHA-256: `98D37A50A0B8102670EA3506517B595CE829C8FEB162478F54BF0DBFA42F0DC8`.
- Summary SHA-256: `31B48C29E37A9528735FDECC93302DB4F4042FBCCB8ECA290CF01BE4108803A1`.

### `run_1784801716_88465` -- accepted

- Result: `defeat` through wave 10.
- Captures: 8550 total; 8550 fresh; 0 late; 0 fresh late.
- Safety activations: 3508 body, 0 projectile, 0 wall, 0 wall-body relief.
- Violations: **0**. Avoidable damage-path: 0. Hidden wall-relief lanes: 0.
- Damage events retained for review: 8. Preserved-command body fallbacks w/o projectile-floor sample: 0.
- Events SHA-256: `5582A3985853C2BD776BF9461586F2F35B2A5EFC8A48B40A6D32E6F17E804C45`.
- Summary SHA-256: `11C70D53C5DC89914BA7259A5C2FE725739763CBC44DC986F0D81C544DA19E54`.

### `run_1784802191_76892` -- accepted

- Result: `defeat` through wave 20.
- Captures: 20568 total; 20568 fresh; 4265 late; 4265 fresh late.
- Safety activations: 8641 body, 1183 projectile, 3728 wall, 1704 wall-body relief.
- Violations: **0**. Avoidable damage-path: 0. Hidden wall-relief lanes: 0.
- Damage events retained for review: 12. Preserved-command body fallbacks w/o projectile-floor sample: 313.
- Events SHA-256: `063388137B82B50E8BEF9CBCC10CDE49D678BDF6C6CA38B3AAAEF4837BC9313F`.
- Summary SHA-256: `E80230616B67456D8A68DA5380F74EEE3C2EFA21610A9E8CCE32F6E33ED92C7E`.

### `run_1784803299_7195` -- accepted

- Result: `victory` through wave 20.
- Captures: 21060 total; 21060 fresh; 4757 late; 4757 fresh late.
- Safety activations: 7142 body, 1473 projectile, 3700 wall, 1590 wall-body relief.
- Violations: **0**. Avoidable damage-path: 0. Hidden wall-relief lanes: 0.
- Damage events retained for review: 4. Preserved-command body fallbacks w/o projectile-floor sample: 204.
- Events SHA-256: `EFADE5A280358328F5CF1683A195D7CEBBD8CE9C265596DB36F9C7794AE18D5D`.
- Summary SHA-256: `CFB0CD1DB5C4FCDBD6E659B26EC11B7B668E9793D1421856DA78093842CF5C61`.

### `run_1784804435_39794` -- rejected

- Result: `victory` through wave 20.
- Captures: 21730 total; 21730 fresh; 5410 late; 5410 fresh late.
- Safety activations: 8817 body, 1821 projectile, 3462 wall, 1545 wall-body relief.
- Violations: **1**. Avoidable damage-path: 0. Hidden wall-relief lanes: 0.
- Damage events retained for review: 8. Preserved-command body fallbacks w/o projectile-floor sample: 168.
- Events SHA-256: `053CC349010866C52222F9F02D129ADCCEB9812F21648928BE991F9A36FA1002`.
- Summary SHA-256: `4DF75A89623B61E40E817A8E9AE5789CA864A7B452C50B80AD0F53109C6C4C68`.

### `run_1784805636_10804` -- rejected

- Result: `victory` through wave 20.
- Captures: 21845 total; 21845 fresh; 5526 late; 5526 fresh late.
- Safety activations: 9278 body, 2326 projectile, 4569 wall, 1566 wall-body relief.
- Violations: **1**. Avoidable damage-path: 0. Hidden wall-relief lanes: 0.
- Damage events retained for review: 7. Preserved-command body fallbacks w/o projectile-floor sample: 259.
- Events SHA-256: `817D8696201EB32799445626291539F04DB7D5D59DB1ECE1E4BCEFCAA12AC702`.
- Summary SHA-256: `EE82B7EA5D35C8C45AF15ADAD07F7E22CD014F7897E63DDFDA9EFBAF937E951A`.
