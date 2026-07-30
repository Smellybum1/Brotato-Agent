# Danger 5 characterisation campaign — results

Date: 2026-07-30. Pre-registration: `danger5_baseline_prereg.md` (amended §2b, dated before collection).
Sample: **20 valid gameplay attempts on mod `0.2.61-wp2-capture`.**
Analysis outputs: `.tmp/d5_analysis_v261_n20/report.txt`, `.tmp/d5_failure_channels_n20/report.txt`.
Attribution lag reused from `d5_damage_lag_result.md`.

**No verdict. No mechanism is declared causal** (prereg §9). This is a phenotype record and a fixture
library, not a test of a treatment.

---

## 1. Validity (prereg §4) — evaluated on arming/identity only

```
runs considered              20
valid gameplay attempts      20
technical failures            0
```

All 20: `requested_danger = 5`, `observed_danger = 5`, `danger_ok = true`, capture stream parses to
EOF, `mod_ready` sentinel observed. The independent cross-check
(`run_v3_0.json → current_run_state.current_difficulty`) reads **5 on all 20** — zero disagreements to
report.

Frozen arm, constant across all 20 runs (Block E field-variation audit):

```
mod_version             0.2.61-wp2-capture
policy_version          teacher_v1-0.1.129-gun-wp1
game_version            1.1.15.4
character               character_well_rounded
config_id               well_rounded_d0_anyranged
danger                  5
movement_estop_enabled  false
time_scale              1.0
human_movement          false ·  endless false ·  wave_retry false
```

Collected in two blocks on the **same frozen build**: the first 12 (median terminal wave 10.5) and a
later 8 (median 11.0). No drift between blocks.

The 9 attempts on `0.2.60` remain a **separate era-matched sample and are never pooled here**
(prereg §2b).

## 2. Primary report (prereg §6)

```
victories / valid attempts       0 / 20
result counts                    {defeat: 20}
```

⚠️ **0/20 is NOT quoted as a win rate.** Prereg §10: 12 attempts is a characterisation sample; a 0/20
and a 2/20 are not meaningfully distinguishable at this n.

**Terminal-wave distribution**

| wave | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 |
|---|---|---|---|---|---|---|---|---|---|
| runs | 1 | 2 | 2 | 1 | 3 | **8** | 1 | 0 | 2 |

```
n = 20   median 11.0   mean 10.15   sd 2.134   range [6, 14]
```

Wave 11 is modal at **8/20 (40%)**.

**Time within the terminal wave** (robust: maximum `elapsed_sec` before the first >1.0 s drop in the
wave):

```
n = 20   median 38.19 s   mean 38.48 s   sd 13.02   range [12.43, 59.02]
```

The naive last-minus-first figure agrees to <0.01 s on every run. No `elapsed_sec` reset was observed
in any of the 20 runs (`reset = F`, 20/20) — the won-wave reset path remains **unexercised**, since
there were no victories.

## 3. Failure channels (prereg §7 head) — multi-label, on the HP-drop diff

Attribution uses **lag 0 against `entities.enemies`**, derived on D5 waves 6-15 in
`d5_damage_lag_result.md` and reused, not re-derived. Threshold 40 u surface distance.
**Boss lag was never established and is not inherited** — boss-bearing terminal waves (4/20) are
flagged, not asserted.

**Drop-level share — denominator 91 terminal-wave HP drops across 20 runs**

| channel | count | share |
|---|---|---|
| melee_body | **74 / 91** | **81.3%** |
| stationary_projectile | 10 / 91 | 11.0% |
| unexplained | 7 / 91 | 7.7% |
| moving_projectile | 4 / 91 | 4.4% |
| other_visible_hazard | 4 / 91 | 4.4% |

Multi-label: shares sum above 100% by construction. The largest single co-occurrence class is
melee_body alone, 70/91.

**Any-drop-level count:** **19 of 20 runs carry at least one melee-labelled drop.** The sole exception
is `run_1785397385_70537` (terminal wave 12, boss present), which has zero melee-labelled drops; its
three drops label `stationary_projectile` (2) and `other_visible_hazard` (2).

**Last-captured-drop level — denominator 20 runs:** melee_body 15/20 (75.0%), stationary_projectile
3/20, other_visible_hazard 2/20, unexplained 2/20, moving_projectile 0/20.
**This run-level figure is NOT quotable — see §4.2.**

**Negative control.** The filter fields vary and the zeros are not from dead fields: `d_enemies` is
present on 208-1141 captures per run with near-fully-distinct values, and the random-tick
false-positive rate at the same 40 u threshold is **0.0076-0.0739 per run** — far below the observed
melee share.

## 4. Limitations — none of these is soft

### 4.1 The killing blow is never captured, 20/20

Every run's last `combat_capture` shows the player **alive** (`hp > 0`); `run_end` follows
**72-200 ms later (median 109 ms, n=20)** — roughly 2-4 ticks at the 50 ms control period. Every
channel figure above is therefore computed on the **last CAPTURED drop, a PROXY for the fatal hazard**.

*Provenance note.* An earlier draft of the channel instrument stated this gap as "~90-210 ms" in its
docstring and report text. **That range was hardcoded prose, never computed** — the loader did not read
`ts_ms` or the `run_end` event at all, so no code could have produced it. It is now measured per run
into `capture_to_run_end_gap_ms` and printed from the data; the instrument and this report agree at
72-200 / median 109. Recorded because a constant that reads like a measurement is the failure mode of
`danger5_baseline_prereg` §18, and it was caught only by an independent recomputation.

**Consequence: prereg §8's first question — "was the causal hazard represented in the observation?" —
is structurally unanswerable for the fatal hazard in this dataset.** The §8 tree is not run to a
conclusion here.

### 4.2 The run-level statistic is threshold-sensitive and flips across the 2/3 bar

"Last captured drop is melee", measured at n=12: **7/12 at 10 u, 7/12 at 20 u, 9/12 at 40 u, 10/12 at
80 u.** That crosses prereg §5's 2/3 criterion depending on an analyst-chosen threshold. The same
sweep at n=20 reads 12/20, 12/20, 15/20, 16/20 — the flip is not an artefact of the smaller sample,
and the criterion is threshold-dependent either way.

- **Quotable:** the drop-level share (81.3% of 91 drops) and the any-drop-level count (19/20 runs) —
  both stable across 10/20/40/80 u.
- **NOT quotable as a phenotype rate:** the last-captured-drop run-level fraction, at any threshold.

### 4.3 Dodged hits produce no HP drop

They are **structurally invisible** to this instrument. The agent's `dodge` is non-zero
(`d5_defensive_stats_result.md`).

### 4.4 `unexplained` is an UPPER bound

It absorbs self-damage, burn/DoT, and any two hits merged into a single capture interval. 7/91 is a
ceiling on "absent from the observation", not a perception-defect count.

### 4.5 A proximity label is an OPPORTUNITY, not proof of causation

And projectile `instance_id` is pooled/reused, so it is not a stable identity.

### 4.6 `d_obstacles` is live but inert

It varies (present on 0-704 captures per run, hundreds of distinct values) yet produced **0 labels**
across all 91 drops. A live channel with no attributions — recorded, not explained.

## 5. ⚠️ The §5 stopping rule was unreachable by construction — a pre-registration defect

Prereg §5 condition 1 asks whether **two adjacent waves contain ≥75% of the losses**. The best adjacent
pair in this sample is waves 10+11 = **11/20 = 55%**. Even a perfect continuation of the remaining
attempts could only have reached **70%** — the criterion **could not return the positive** at n=20 for
any achievable data.

This is the same family as the pre-registration's own §11(c) warning ("a statistic that cannot return
the positive"), committed inside the document that names it.

**The campaign therefore ended by CAP (20), not by criterion.** The conclusion this forces is the
substantive one: **D5 failure is DIFFUSE across waves 6-14**, not concentrated in an adjacent pair.
Any downstream fixture choice must be justified on its own terms and not by a claimed dominant band.
Wave 11 at 8/20 is modal, not dominant.

## 6. Economy / collection (prereg §7b) — the operator's named phenotype

Measurement instant is the **last capture with `remaining_sec > 0`** (`leftAUTH`). The post-sweep
final capture (`leftLAST`) is reported alongside and is **not authoritative** — it reads **exactly
0.000 on 139/139 non-terminal waves**, reproducing the 1-versus-28 error as structure rather than as
noise.

Pooled per-wave medians (denominator = number of runs reaching that wave):

| wave | n | spawned (LB) | left on ground AUTH | at lead-1s | collected (bank Δ) | bank at last capture | shop outflow | ground count max |
|---|---|---|---|---|---|---|---|---|
| 1 | 20 | 5.0 | 1.0 | 2.0 | 32.0 | 62.0 | 41.0 | 5.0 |
| 2 | 20 | 8.0 | 6.0 | 5.0 | 49.0 | 72.5 | 51.0 | 8.0 |
| 3 | 20 | 19.0 | 11.5 | 11.0 | 81.0 | 99.5 | 83.0 | 19.0 |
| 4 | 20 | 24.5 | 16.0 | 16.0 | 114.0 | 132.0 | 108.5 | 24.5 |
| 5 | 20 | 29.0 | 20.0 | 21.0 | 158.0 | 186.0 | 162.0 | 29.0 |
| 6 | 20 | 46.0 | 38.5 | 39.0 | 158.5 | 188.5 | 168.0 | 46.0 |
| 7 | 19 | 33.0 | 29.0 | 29.0 | 243.0 | 267.0 | 250.0 | 33.0 |
| 8 | 17 | 34.0 | 26.0 | 27.0 | 219.0 | 243.0 | 230.0 | 33.0 |
| 9 | 15 | 50.0 | 30.0 | 26.0 | 481.0 | 497.0 | 476.0 | 50.0 |
| 10 | 14 | 44.5 | 38.0 | 38.0 | 393.5 | 396.5 | 357.5 | 42.5 |
| 11 | 11 | 43.0 | 26.0 | 28.0 | 169.0 | 206.0 | 0.0 | 40.0 |
| 12 | 3 | 35.0 | 27.0 | 21.0 | 500.0 | 514.0 | 503.0 | 34.0 |
| 13 | 2 | 22.0 | 22.0 | 21.0 | 446.5 | 518.5 | 515.5 | 36.5 |
| 14 | 2 | 52.5 | 35.5 | 35.5 | 339.5 | 355.0 | 0.0 | 46.0 |

Notes carried from the instrument:

- `materials_spawned_value` is the sum over **distinct** ground `instance_id`s observed; captures are
  sampled, so a pickup between two captures is not counted. It is a **LOWER BOUND on spawn**, not a
  spawn ledger. Consequently `spawned − left` is not a clean collection figure.
- Terminal-wave rows (`shop outflow = 0`, `post_timer_zero_captures = 0`) reflect runs that ended
  inside the wave, and their `leftAUTH`/`leftLAST` coincide. Waves 12-14 sit at n = 3/2/2 — **below the
  n ≥ 6 bar for quoting a spread**, so no dispersion is quoted for them.
- Material left on the ground at wave end is **non-trivial and persistent**: median 20-38.5 across
  waves 5-11, on a lower-bound spawn denominator.

**⚠️ `materials_spent` co-moves with terminal wave** — a longer life *means* more income and more
shops. **CONFOUNDED, not a finding.** Same structure as the dodge-at-death confound in
`d5_defensive_stats_result.md` §4.

**⚠️ `gndMax` exceeded 50** in six run-waves: 51 at `run_1785382862_21852` w10,
`run_1785384559_65882` w14, `run_1785385329_48378` w9, `run_1785396854_69358` w10; 52 at
`run_1785394913_16985` w9; 53 at `run_1785386153_33481` w9 — **above the game's `MAX_GOLDS = 50`**. Prereg §7b assumed 50 was a hard game cap and therefore not a
censored instrument. The excess reproduces across runs and **is unresolved**. Open question; it means
either the cap is not what we believe or the ground-entity count is being over-counted. Do not build a
saturation argument on `gndMax` until this is closed.

## 7. Components — no verdict attached (prereg §7b tail)

| component | n | median | mean | sd | range |
|---|---|---|---|---|---|
| `damage_taken` GROSS | 20 | 78.5 | 103.25 | 73.79 | 20-351 |
| `materials_spent` | 20 | 1724.0 | 1695.25 | 847.54 | 399-3595 |
| rerolls | 20 | 13.5 | 14.50 | 7.19 | 1-32 |
| locks | 20 | 5.0 | 4.90 | 2.55 | 1-11 |
| hp-increase proxy | 20 | 49.0 | 73.60 | 61.46 | 8-288 |

`damage_taken` is a **GROSS** counter that never subtracts healing; it is retired as a primary
endpoint. The hp-increase proxy also absorbs `max_hp` growth and is not a healing measurement.

`nonfinite_total` varies 1038-1248 per run (the `nearest_d` INF sentinel on `n_enemies == 0` captures).
`summary.nonfinite_fixed` reads 0 for all 20 and is the summary-dict-only counter, not the run total.

## 8. Not delivered by this report

- Prereg §7's **pressure/clearance panel** (enemies alive, total enemy HP alive, spawn rate, kill rate,
  effective damage output, fraction of ticks with a valid target, damaging-contact count) —
  `TODO(primary): pressure/clearance panel over the 10 s before death, per run`.
- Prereg §7's **controller-state panel** (safety-tail activation, wall-recovery activation,
  angle(desire, final command), owning layer, cells holding 50% of the wave, distance to walls,
  heading reversals) — `TODO(primary): controller-state panel for the terminal wave`.
- The clearance / survival / no-local-solution trichotomy is therefore **not resolved**.
- Prereg §5's fixture asset: `TODO(primary): count of independent usable saves archived per reached
  wave`.
- Prereg §7 asks that the lag be **re-derived on the 0.2.61 set** and confirmed unchanged; that
  confirmation has not been run. `TODO(primary): re-run scripts/wp2_d5_damage_lag.py on the n=20
  0.2.61 sample`.

## 9. What this selects next — candidates, none endorsed

Each needs its own pre-registration; §9's causal-vs-actionable check applies to every one of them.

1. **Dosed dodge/armor grant at a D5 wave-10 fixture.** Tests whether defence is causal at D5 at all.
   Already priced as likely **causal-but-not-actionable** (`d5_defensive_stats_result.md` §3: median
   affordable ceiling 22 points, ~16 by wave 10, against a 20-30 target). Needs its own prereg.
2. **Dosed materials grant at a D5 fixture**, per prereg §7b — asks whether the same states are rescued
   by economy alone, and separates "died because it collected less" from "collected less because it was
   losing", which this campaign cannot separate. Needs its own prereg.
3. **A melee-contact-specific movement or threat intervention**, selected by the 81.3% drop-level melee
   share. ⚠️ Blocked on prereg §9 and the [DESIRE] finding: any `_build_desire` change must be assumed
   inert until a readback on the **final command** proves otherwise. Needs a Gate-0 decision-flip check
   before spend.
4. **Closing the capture gap before the fatal blow** — a telemetry change (higher capture rate near
   death, or a death-tick capture) that would make §8's first question answerable. This is instrument
   work, not an experiment, but every attribution above is proxied without it.
5. **Resolving `gndMax` > `MAX_GOLDS`.** Cheap, and it gates any future saturation argument.
6. **A wave-6-14 fixture ladder rather than a single dominant-band fixture**, since §5's diffuseness
   conclusion denies us a single band.

Related: [[brotato-danger5-first-observations]], `d5_damage_lag_result.md`,
`d5_defensive_stats_result.md`, `danger5_baseline_prereg.md`.
