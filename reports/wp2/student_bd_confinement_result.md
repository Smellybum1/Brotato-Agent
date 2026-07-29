# RESULT — the B′ human-BC student plays WORSE. The line closes.

Pre-registered in `student_bd_confinement_prereg.md`. Campaign ran 2026-07-30, **32/32 trials
valid, 126 min**, mod `0.2.57`, 1.0x time scale, arms interleaved trial-by-trial.

## ⛔ VERDICT: **NO-GO** — close the human-BC line

Primary (fixture A, pre-registered): **d = −3.50 cells** against a NO-GO bar of ≤ +2.21.
The student is **not** less confined; on the primary fixture it is **more** confined.

**And the reason the primary is messy is itself the finding: the student dies.**

## ⭐⭐⭐ THE HEADLINE — a safety collapse, exactly as the prereg risk predicted

| fixture A | survived wave 17 |
|---|---|
| **CONTROL (shipped teacher)** | **10 / 10** |
| **STUDENT (B′)** | **4 / 10** |

**Fisher one-sided p = 0.0054.** (Hand-rolled Fisher verified against the tea table in both
directions: 0.0142857 and 0.242857, exact.)

The student **bypasses the entire safety tail** (`agent_controller.gd:581-593` replaces
`current_move_vector`). That is what made this line worth trying, and it is what killed it. A policy
cloned from a human's *direction choices* does not inherit the human's *survival*.

Gross damage, the reported component (never subtracts healing, so it carries no verdict on its own):
- **fixture B: student median 126 vs control 40 = 3.16x** — clean, all 12 trials full-length and
  all survived, nothing conditioned.
- fixture A survivors only: 118 vs 66 = 1.77x.

## The confinement endpoint does NOT replicate across fixtures

Restricting to **full-length** trials (≥1238 wave-17 captures, i.e. the whole wave) removes the
truncation confound:

| | student | control | d |
|---|---|---|---|
| **fixture A** (survivors only — conditions on an OUTCOME, post-hoc) | 4.25 (n=4) | 11.20 (n=10) | **−6.95** (−1.83 sd) |
| **fixture B** (CLEAN: all 12 full-length, all survived) | 14.83 (n=6) | 7.83 (n=6) | **+7.00** (+3.02 sd) |

**Opposite signs, both beyond 1.8 control sd.** The human-vs-agent confinement gap was
*fixture-invariant* (human 27.5 on one fixture, 29.0 across six others). **The student's effect is
not.** Whatever B′ learned, it is not a stable shift toward the human's roaming.

And even at its best — fixture B, 14.83 cells — the student remains far below the **human's
27.5-29**. It does not reach human-like movement even where it moves in the right direction.

## Validity and arming — all clean

- **32/32 trials valid.** Arm assigned from the **treatment readback**, never the label; label and
  readback agreed on every trial. Control emitted **zero** `student_tick` events.
- **Serving health: connected-only fraction min/median/max = 0.996 / 1.000 / 1.000.** Whenever a
  connection existed the student drove essentially every tick — no timeouts, stale replies or errors.
  The all-tick figure (median 0.859) is entirely reconnect gaps.
- **The encoding was proven**, not assumed: 838/838 served actions reproduce an offline replay
  through the training encoder + checkpoint to **≤1e-6**. See [[brotato-student-serving]].
- **Control reproduces the archived baseline**: 11.20 (n=10, mod 0.2.57) vs the archived 13.00
  (n=6, mod 0.2.55), well inside noise (sd ~3.8-4.4). The harness and endpoint are sound; it is the
  treatment that failed.

## Where my own design was wrong, and what it cost

Both were caught before any outcome was computed, and both are recorded in the prereg.

1. **The truncation confound was real and material.** Wave 17 is a fixed ~1240-1250 captures.
   **6 of 10 fixture-A student trials were truncated** (161-1191 captures) because the student died,
   so the primary silently compared full-length control trials against partial student ones.
2. **My serving guard could have REJECTED BY OUTCOME.** Connection gaps cost a roughly fixed tick
   count, so `frac_all = (N−185)/N` falls as a trial shortens — and short trials are deaths. Measured
   after the fact, that abandoned gate **would have dropped 5 student trials of which 2/5 survived,
   keeping 11 of which 8/11 survived** — i.e. it would have discarded the student's worst runs and
   flattered the arm. Replaced pre-hoc with intention-to-treat + a per-protocol sensitivity.
3. **The common-prefix sensitivity was uninformative, and that is my design's fault.** K was set to
   the minimum captures across all trials = **161** — hostage to a single catastrophic student trial.
   At 161 captures the metric has almost no dynamic range (every arm reads 4-7 cells), so it neither
   confirms nor refutes. Per the pre-declared asymmetric rule it could not upgrade a NO-GO anyway.
   A fixed, wave-fraction-based K would have been the better design.

## Artifacts

- Trials: `reports/wp2/student_bd_confinement_trials.jsonl` (32 rows, copied out of gitignored
  `.tmp/`). Analysis: `scripts/wp2_student_screen_analysis.py`. Driver:
  `scripts/wp2_student_confinement_campaign.py`.
- Registry `models/registry/human_bd_s1.json` is tracked; the checkpoint it points at,
  `models/bc_human/human_bd_s1/best.pt` (**sha256 `B77C47894CDB94FFC14795097F7FA13BF22C35D1F88A3BA57E0853EF888B0AB3`**),
  is **not** — `models/bc_human/` is gitignored, matching the existing `models/bc_v1|v2|v3`
  convention. It was moved out of `.tmp/` so it survives scratch cleanup.
- Reproduce a serving run: start `scripts/run_student_sidecar.py --registry
  models/registry/human_bd_s1.json --idle-exit-sec 21600`, then set `student_enabled` in
  `agent_config.json` AFTER any deploy.

## What this closes, and what it does not

**Closes:** behaviour cloning from human *actions* as a route to fixing confinement. The operator
approved one more step past the 0.2669 direction-agreement proxy precisely because *"whether the
policy WINS has never been asked."* It has now been asked and the answer is no — decisively, on
survival, not on a proxy.

**Does not close:** the confinement *finding* itself (human 27.5-29 vs agent 13, 4.52 sd) stands
untouched, and remains the best endpoint on the project with no lever found. The gap is real; BC on
human actions is not the way to reach it.

**A concrete signal for whoever picks this up:** on fixture B the student roamed substantially more
(+3.02 sd) while surviving 6/6 — and paid 3.16x damage for it. That is the shape of a policy that
has learned *where* to go but not *when*, consistent with the standing hypothesis that the human's
edge is **temporal** and a single-frame observation with no history cannot express it.
