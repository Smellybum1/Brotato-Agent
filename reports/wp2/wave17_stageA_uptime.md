# Stage A archive sweep — wave 17: BUILD-limited or MOVEMENT-limited?

Archive-only sweep (no game launched, nothing deployed). Sources:
`%APPDATA%\Brotato\brotato_agent\runs\<run_id>\{summary.json,events.jsonl}`, read-only.

Scripts: `scripts/wp2_stagea_scan.py`, `scripts/wp2_stagea_metrics.py`,
`scripts/wp2_stagea_analyze.py`. Per-run output: `.tmp/stageA/wave17_metrics.jsonl`.

> ## ⚠️ CORRECTION 2026-07-29 — the measurements stand, the verdict line does not
>
> **What was claimed:** "BUILD-limited, not movement-limited"; the movement hypothesis is
> refuted on its own sign.
>
> **What is now known:** an interventional test beats this observational one. A human
> given **movement only** rescued the same doomed entry build **5/5 vs the agent's 4/21,
> p=0.0019** — so wave 17 IS movement-actionable. **Exploratory only:** the predeclared
> endpoint was terminal win and it **FAILED at 1/5**.
>
> Why both can be true: this sweep's proxies are **coverage and uptime_engaged**, and the
> file already records that it contains **no measured-velocity metric**. The defect the
> human exposed is in *movement/arbitration under crowd pressure*, which coverage and
> uptime do not measure. The build separator (`nominal_dps` 28.26 vs 35.25) is unaffected
> and still holds — the model is an **interaction**: weak build → higher crowd pressure →
> the movement defect becomes consequential.
>
> **Evidence:** `reports/wp2/NEXT_SESSION_PLAN.md`, `reports/wp2/wave17_conclusion.md`.

## Verdict

**BUILD-limited, not movement-limited** — with the caveat below.

The naive comparison reproduces the 3-run pilot: dying runs have *higher* raw
uptime_engaged in every window (P(died>surv) 0.74–0.80). Controlling for crowding
destroys that signal: **within every enemy-count bin, coverage is inside the null
band, and uptime is either inside the band or still HIGHER in dying runs. In no bin,
in no window, is dying-run coverage or uptime LOWER.** The movement hypothesis
predicts the opposite sign and does not survive the control.

The one entry-state metric that separates is **nominal DPS: median 28.3 (died) vs
35.3 (survived), P=0.291, outside the null band [0.338, 0.662]**. Every defensive
entry stat (hp, max_hp, armor, dodge, lifesteal, hp_regeneration, weapon count) is
null. This is a clean out-of-sample corroboration of the archive's "the wave-17
separator is OFFENSE, not defense" finding, computed here from entry state rather
than from shop decisions.

## Step 1 — run inventory

1767 run directories; **213 had no summary.json** (aborted/in-progress) and were
skipped. 1554 summaries parsed, 0 unparseable.

| filter | died-at-17 | survivors (last_wave>=18) |
|---|---|---|
| raw (`result==defeat & last_wave==17` / `last_wave>=18`) | 49 | 1399 |
| after full-run filter `duration_ms >= 900000` | **41** | 367 |
| with `events.jsonl` present | 41 | 367 |
| **with >=1 valid wave-17 capture** | **25** | 25 |

`duration_ms` removed 8 died-at-17 and 1032 survivors — the survivor pool is
overwhelmingly wave-20 **fixture trials**, exactly the contamination the brief warned
about. All 1358 `last_wave==20` runs; only 408 runs in the whole archive are full runs.

**Died-at-17 count is 41 full runs, not 22.** The memory index's n=22 is a smaller,
presumably recent-era subset. Only 25 of the 41 are analysable (below).

## The killer attrition: 32 of 82 selected runs have ZERO wave-17 captures

Not a bug and not a vacuous filter to be reported as "0" — **combat_capture
telemetry does not exist before the wp2-capture era**. Every empty run is
policy <= 0.1.73 / mod <= 0.1.73. Candidate set sizes are printed, not hidden:

- died17 empty: 16 runs (policies 0.1.14, 0.1.26, 0.1.28, 0.1.38, 0.1.50, 0.1.58 x2, 0.1.61, 0.1.64 x2, 0.1.65 x2, 0.1.66 x3, 0.1.73)
- survivor empty: 16 runs (same era)

So the entire pre-0.1.92 era is **structurally unmeasurable** for this question. The
analysis is confined to the capture era, n=25 vs 25.

## Step 1/2 — version distribution (LOUD, per the brief)

Survivors were sampled by walking the died runs in run_id order and taking the
unused survivor with the **nearest policy minor number** (deterministic, cap 45).
That produced 41 pairs, of which 25 pairs survive the capture-availability filter.

Version distribution of the **25 usable runs per class**:

| policy | died17 | survivor |
|---|---|---|
| 0.1.125 | 9 | 9 |
| 0.1.128 | 6 | 6 |
| 0.1.122 | 3 | 3 |
| 0.1.129 | 3 | 3 |
| 0.1.96 / 0.1.97 | 0 / 1 | 1 / 0 |
| 0.1.99 / 0.1.100 | 1 / 0 | 0 / 1 |
| 0.1.104 | 1 | 1 |
| 0.1.123 / 0.1.124 | 0 / 1 | 1 / 0 |

**21/25 pairs are exact policy-version matches**; the remaining 4 differ by one
minor version. Era mixing is therefore *not* a live confound for the usable sample —
but only because the matcher happened to find exact partners, and only after the
pre-capture era was dropped wholesale. The dropped era is a real coverage hole, not a
balanced exclusion.

## Step 5 — null band

n1 = n2 = 25 → SE = sqrt((25+25+1)/(12*25*25)) = 0.0825.
**Null band = 0.5 +- 1.96*0.0825 = [0.338, 0.662].** Crowding bins have smaller n and
their own wider bands, printed per row below. No band is reused from prior analyses.

## Primary window [15,25) — unmatched

`*` = outside the null band.

| metric | med died | med surv | P(died>surv) |
|---|---|---|---|
| uptime_engaged | 0.8138 | 0.6483 | **0.794*** |
| coverage | 0.2259 | 0.2389 | 0.570 |
| mean_enemies_alive | 10.67 | 6.58 | **0.800*** |
| max_enemies_alive | 14 | 11 | **0.731*** |
| mean_enemy_hp_pool | 1936 | 1329 | **0.758*** |
| mean_nearest_surface_dist | 371.2 | 487.3 | **0.195*** |
| mean_player_speed | 531 | 499 | **0.734*** |
| entry hp / max_hp | 48 | 49 | 0.464 |
| entry armor | 3 | 4 | 0.411 |
| entry dodge | 0.13 | 0.10 | 0.649 |
| entry lifesteal | 2 | 2 | 0.498 |
| entry hp_regeneration | 6 | 6 | 0.482 |
| entry speed | 531 | 499 | **0.734*** |
| **entry nominal_dps** | **28.26** | **35.25** | **0.291*** |
| entry n_weapons | 6 | 6 | 0.360 |

nominal_dps is in an arbitrary unit (damage/cooldown, cooldown units unverified) —
the ratio is meaningful, the absolute value is not.

## Step 4 — MATCHED BY CROWDING, window [15,25)

| enemies alive | nD | nS | uptime D | uptime S | P(D>S) | band | cov D | cov S | P(D>S) | band |
|---|---|---|---|---|---|---|---|---|---|---|
| 0-4 | 10 | 19 | 0.792 | 0.523 | 0.629 | [0.28,0.72] | 0.291 | 0.207 | 0.579 | [0.28,0.72] |
| 5-9 | 24 | 25 | 0.792 | 0.645 | **0.713*** | [0.34,0.66] | 0.194 | 0.195 | 0.555 | [0.34,0.66] |
| 10-14 | 23 | 19 | 0.930 | 0.906 | 0.513 | [0.32,0.68] | 0.242 | 0.213 | 0.568 | [0.32,0.68] |
| 15-19 | 12 | 3 | 0.987 | 1.000 | 0.361 | [0.12,0.88] | 0.216 | 0.436 | 0.306 | [0.12,0.88] |
| 20+ | 1 | 0 | — | — | DEGENERATE | — | — | — | — | — |

Read the direction, not just the stars: the only surviving significant cell (5-9) has
dying runs **above** survivors. Coverage — the crowd-normalised measure — is null in
all four evaluable bins. The 15-19 bin is the only cell pointing the movement way and
it is nowhere near its (very wide) band, with nS=3.

## Landmark correction — [15,25) is NOT pre-divergence

The brief cites the archive's "crowd gap opens ~25 s". It does not, in this sample:

| window | med enemies D | med enemies S | P(D>S) |
|---|---|---|---|
| [0,10) | 3.19 | 2.52 | 0.651 (in band) |
| [10,20) | 7.98 | 5.34 | **0.754*** |
| [15,25) | 10.67 | 6.58 | **0.800*** |
| [20,30) | 11.27 | 7.80 | **0.839*** |
| [30,40) | 17.24 | 10.46 | **0.877*** |

The gap is already significant by **[10,20)** and is fully open at [15,25). So
[15,25) is a mid-divergence window, not a pre-divergence one. Crowd-matched [0,10),
the genuinely pre-divergence window, is null everywhere it is evaluable:

| enemies alive | nD | nS | uptime P(D>S) | coverage P(D>S) | band |
|---|---|---|---|---|---|
| 0-4 | 25 | 25 | 0.648 | 0.613 | [0.34,0.66] |
| 5-9 | 25 | 24 | 0.543 | 0.517 | [0.34,0.66] |
| 10-14 | 7 | 2 | 0.214 | 0.643 | [0.02,0.98] |
| 15-19 / 20+ | 0 | 0 | DEGENERATE | DEGENERATE | — |

Same conclusion from the earlier landmark: at equal crowd size, dying runs are not
worse at keeping enemies in range.

## Secondary windows (descriptive)

Raw uptime_engaged is above the band in [10,20), [15,25), [20,30), [30,40)
(P = 0.798, 0.794, 0.795, 0.740) and inside it at [0,10) (0.658). Raw coverage is
inside the band everywhere except [10,20) (0.662, marginal, exactly on the boundary).
The uptime signal grows as the crowd gap grows — which is the endogeneity the brief
predicted, and is why the matched table is the one that decides.

## What is ambiguous / could not be established

- **Sample is 25 vs 25, not 41 vs 45.** Power is modest; a coverage deficit smaller
  than roughly 0.16 in rank-biserial terms would not be detected here.
- **`mean_player_speed` == `entry_speed` exactly** (same P, same medians). Player
  `speed` is a *stat*, not a measured velocity, and it does not change within a wave.
  So this row is a **build** difference (dying builds took more speed), not evidence
  about how the agent moved. This sweep contains **no measured-velocity metric** —
  the archived `measured_vx/vy` were not used because of the known dt blow-up, so
  actual movement *execution* remains unmeasured. The verdict rests on
  coverage/uptime as movement proxies only.
- **Nearest-surface-distance is much lower in dying runs (371 vs 487, P=0.195\*).**
  That is consistent with crowding (more enemies ⇒ closer nearest one) and with the
  archive's melee-crowding death mechanism; it is not independently informative about
  movement quality, and this sweep did not disentangle it.
- The dying runs' higher raw uptime and higher coverage-at-low-crowd could also be
  read as **dying runs choosing to stay engaged**, a policy difference rather than a
  build one. This sweep cannot separate "shorter effective range forces closer
  fighting" from "the agent chose to fight closer".
- Whether the nominal-DPS gap is *causal* is untested. It is an entry-state
  correlation on n=25 pairs, and prior work found every shop-side proxy null.
