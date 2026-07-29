# Pre-registration — does the B′ human-BC student escape the confinement basin?

**Written 2026-07-30, BEFORE any outcome data from the screen was computed.**
Operator directive: serve the B′ student and measure ACTUAL PLAY. Direction agreement (0.2669 vs
the teacher's 0.1167) is a PROXY; whether the policy *plays* well has never been asked.

Author: primary session, under the standing unattended-autonomy grant (2026-07-27). Pre-declared
bars are binding and are not mine to relax overnight.

---

## 0. What is already established (not re-litigated here)

| fact | value | source |
|---|---|---|
| student B′ 9-way direction agreement | **0.2669**, cos **+0.5232** | `brotato-teacher-human-divergence` |
| teacher agreement with human | **0.1167**, cos **−0.0995** | same |
| agent control confinement, fixture A, n=6, mod 0.2.55 | **[7, 19, 13, 17, 10, 12]**, mean **13.00**, sd **4.427** | `brotato-spatial-confinement` |
| human confinement, fixture A, n=6 | mean **27.50**, sd **1.871** | same |
| human/agent gap | **14.5 cells = 4.27 pooled sd** | same |

B′ is the ONLY training condition ever audited clean for label leakage (`player_v` R² 0.05).

## 1. Arming readbacks — ALREADY PASSED before this screen was written

These are recorded here because an experiment that is armed without a readback measures nothing,
and because `student_tick.source == "student"` alone does **not** prove the encoding was right.

1. **Encoder selection landed.** `trainer/bridge/sidecar.py` hard-coded `encoder_v1`; B′ trains on
   `encoder_v1_absvel` (absolute entity velocity + `entity_sort: distance`). Serving through the old
   path would have fed the student the exact label-leak encoding the variant exists to close, while
   every hash, the handshake and `student_tick.source` all still read healthy.
   Quantified on 300 real captures: **median action deviation 23.1°, p95 91.2°, mean cosine 0.7796**,
   only 9/300 identical. The fix is not cosmetic.
2. **`select_encoder` hard-errors** rather than falling back, and fails at STARTUP, so an
   unhonourable schema cannot degrade into a 20 Hz flood of silent teacher fallbacks.
3. **End-to-end encoding proof on live data.** 838/838 served actions in the smoke trial reproduce
   an offline replay through the training encoder + checkpoint to **≤ 1e-6 (max 6.99e-07** — the
   floor set by 6-decimal JSON logging). Two seq offsets, one change point, matching the one
   reconnect: a genuine alignment, not a nearest-neighbour coincidence.
4. **Serving health**, smoke trial: 838/962 ticks `source=="student"` (87.1%); the 124 fallbacks are
   almost entirely `not_connected` during the pre-handshake startup window. Sidecar latency
   p50 1.32 ms / p99 2.67 ms model time, mod-observed p99 20 ms against a 40 ms deadline.

**The smoke trial `run_1785341600_26819` is EXCLUDED from this screen.** Its confinement was
deliberately not computed before this document was written.

## 2. Design

- **Build:** mod `0.2.57` (installed = repo, unchanged; **no deploy** is performed for this screen,
  so the version-bump-mid-campaign trap does not apply). Policy `0.1.129`.
- **Registry served:** `models/registry/human_bd_s1.json` → `models/bc_human/human_bd_s1/best.pt`
  (sha256 `B77C4789…`), schema `observation_v1_absvel_dsort.yaml` (`773D650D…`).
- **Arms, interleaved trial-by-trial** (never blocked, so drift cannot align with arm):
  - **STUDENT** — `student_enabled=true`, sidecar serving `human_bd_s1`.
  - **CONTROL** — `student_enabled=false`, shipped teacher, identical build and flags.
- **Fixtures:** A = `w16_predator_20260728_112824_7f124906e6bb49cb` (the fixture carrying the n=6
  control and human baselines); B = a second w16 predator fixture for generalisation.
- **n:** fixture A 10+10, fixture B 6+6 → **32 trials**, ~2.3 h.
- **`--target-wave 17`** (a wave-17 run needs this explicitly or every trial is rejected).

### Time scale is 1.0x, deliberately

2.0x is approved for paired fixture campaigns, and this qualifies. It is **declined here**: the
learned path has a **40 ms real-time deadline** against a 50 ms control period. At 2.0x the period
falls to ~25 ms real and the deadline would EXCEED it, converting the treatment arm into a partial
teacher arm. Halving the wall-clock is not worth corrupting the thing being measured.

## 3. Endpoints

**Primary — occupancy concentration:** number of 128 u cells holding ≥50% of wave-17 captures
(`scripts/wp2_confinement.py`, `concentration.cells_50pct`). Higher = roams more = human-like.
Chosen because it is the only endpoint on this project with a measured within-arm spread at n≥6
(sd 4.427) and 4.52 sd separation between human and agent.

**Secondary — terminal win.** Reported, **never quoted as significant**: on fixture A the archived
human 6/6 vs agent 2/4 is Fisher p=0.133, underpowered by construction.

**Guards, reported per arm, not gating the primary:**
- survival / terminal win per arm;
- gross damage — a **GROSS counter that never subtracts healing**, so it is a reported COMPONENT
  only and cannot carry a verdict;
- **safety:** the student **bypasses the entire safety tail** (`agent_controller.gd:581-593`
  replaces `current_move_vector`). If the student arm's survival is materially worse than control,
  that is a first-class finding and gets reported prominently **even if confinement improves**.

## 4. Validity, evaluated BEFORE any outcome

Each guard is computed on the serving/telemetry stream, never on the result, so none of them can
reject by outcome. **Validity counts are reported per arm before any outcome number.**

- trial marked valid by `wp2_finale_loop`, and wave-17 captures present;
- **arm is assigned from the TREATMENT READBACK, not from the label**: a trial counts as STUDENT
  only if ≥80% of its wave-17 `student_tick` events carry `source=="student"`, and as CONTROL only
  if it has **zero** such events. Anything else is reported as a third bucket and excluded.
  (An entry-build fingerprint or a run label does not identify a trial's arm.)

## 5. Decision rule — fixed now

Primary comparison is **fixture A**, student vs control, on `cells_50pct`.
Let `d = mean(student) − mean(control)`, and let `sd_c` be the control arm's own sd measured in
THIS campaign (the archived 4.427 is the sizing prior only).

- **GO** — proceed to a fresh, larger confirmatory campaign — if **d ≥ +8.85 cells** (2 × 4.427)
  and the serving readback passes on ≥90% of student trials.
- **NO-GO — close the line** if **d ≤ +2.21 cells** (0.5 × 4.427). The student would then not
  meaningfully escape the basin, and the human-BC line closes **on the outcome that matters rather
  than on a proxy**, which is the stated purpose of running this at all.
- **AMBIGUOUS** in between: report the effect size and stop. Do not top up and re-test.

This is a **SCREEN**: read the effect size, not a p-value. No shipping decision follows from it.
**No optional stopping** — all 32 trials run, analysis happens once. If the campaign dies early,
the partial data is reported as partial and does not license a "collect a bit more" loop.

Fixture B is a **generalisation check only**, reported separately; it does not enter the primary
rule and cannot rescue or overturn it.

## 5b. ADDENDUM — duration confound, declared mid-campaign

**Added 2026-07-30 after 2 of 32 trials had run, and BEFORE any campaign outcome was computed.**
Motivated by a design concern, not by data. The primary rule in §5 is **UNCHANGED**.

**The concern.** `cells_50pct` is computed over a trial's wave-17 captures. A trial that ends early
has fewer captures, so the two arms may be measured at different sample sizes — the shape of the
"outcome the treatment mechanically rescales" trap.

**Measured on the EXCLUDED smoke run** (961 wave-17 captures), recomputing the endpoint on growing
prefixes of the same run:

| captures | 96 | 240 | 480 | 720 | 961 |
|---|---|---|---|---|---|
| `cells_50pct` | 1 | 8 | 12 | 8 | **3** |

The relationship is **NOT monotonic** — it rises then falls, because time spent heavily concentrated
late in a wave pulls the statistic back down. So the endpoint is not a simple proxy for duration.
But it is clearly **sensitive to where in the wave the sample ends**, which is enough to matter when
one arm dies earlier than the other.

**Therefore, additionally reported (not replacing the primary):**
1. `captures_used` per trial and its distribution per arm.
2. **Common-prefix sensitivity:** the primary recomputed on the first **K** wave-17 captures of every
   included trial, where K = the minimum `captures_used` across all included trials, so both arms are
   measured at an identical sample size.

**Binding, in the conservative direction only:** if the full-length primary and the common-prefix
sensitivity **disagree in sign**, the screen is declared **AMBIGUOUS** regardless of what the
full-length number says. A GO may be downgraded this way; a NO-GO may not be upgraded by it.

## 5c. CORRECTION — the serving guard in §4 could REJECT BY OUTCOME

**Added 2026-07-30 after 2 of 32 trials, on discovering a defect in my own guard.**
Disclosure: at the moment of writing this I had seen the win/loss result of exactly two trials
(one per arm) while verifying that the arm toggle worked. I had computed **no** confinement number
from the campaign.

**The defect.** §4 admits a STUDENT trial only if ≥80% of its wave-17 `student_tick` events carry
`source=="student"`. The fallbacks are almost entirely a **fixed-size prefix** of
`cause="not_connected"` ticks before the handshake completes (~190 ticks). So the fraction is
`(N − 190) / N`, which **falls as the trial gets shorter**:

| wave-17 ticks N | serve fraction |
|---|---|
| 1000 | 0.81 |
| 800 | 0.76 ❌ excluded |
| 600 | 0.68 ❌ excluded |

Short trials are **deaths**. The guard would therefore preferentially exclude the student arm's
WORST trials and flatter that arm — a validity check evaluated on data produced after the measured
event, selecting on the outcome. This is the exact failure mode already on record.

**A first attempted fix was itself wrong, and is recorded rather than quietly replaced.** I assumed
the `not_connected` ticks were a single leading prefix and stripped it. Run-length encoding the
cause stream shows they are not:

```
not_connected(1), disconnect(1), not_connected(61), ok/clamped(~20),
disconnect(1), not_connected(60), ok(64), ...
```

The mod **reconnects 2-3 times per run** (matching the 3 `handshake_ok` events in the sidecar log),
each gap costing ~61 ticks (~3 s). The strip removed exactly ONE tick and changed the fraction from
0.871 to 0.872 — a fix that did nothing, which is the same shape of failure as a knob that reads as
applied and is inert.

**The actual resolution: the primary stops excluding on serving fraction at all.**

- **Primary arm assignment is INTENTION-TO-TREAT.** A trial is STUDENT if `student_enabled` was true
  AND the run contains ≥1 student-sourced tick (which proves the config took effect and the sidecar
  served); CONTROL if it contains **zero** `student_tick` events. Neither condition can be moved by
  how the trial turned out. No trial is dropped for serving *less*.
- **Serving fraction is REPORTED, never a filter** — both all-tick and connected-only
  (denominator excludes `not_connected`/`disconnect` ticks, so it is invariant to the number of
  reconnect gaps and to trial length).
- **Per-protocol SENSITIVITY:** the primary repeated on student trials with connected-only fraction
  ≥0.80. Reported beside the intention-to-treat result. If they disagree in sign, the screen is
  **AMBIGUOUS** — same conservative, downgrade-only rule as §5b.
- A student trial with **zero** student ticks is an arming failure, not a result; it is reported
  explicitly and excluded, and the driver already aborts if the sidecar is not listening.

This is intention-to-treat as the primary with per-protocol as a sensitivity, which is the standard
way to keep a treatment-adherence measure from selecting on the outcome.

## 6. Pre-declared threats to this result

- **Goodharting confinement.** It correlates with the human winning; it has never been shown to
  cause it. A student that roams more but dies more has not been shown to be better.
- **A student with no safety net.** Bypassing the tail is the mechanism that makes this line worth
  trying AND the main risk of it.
- **`entity_sort: distance` is a semantic change**, not just a permutation — it changes which
  entities survive the per-group capacity cap. Fine for a measurement, not a shipping path.
- The served observation is **non-production** by construction; nothing here is a deploy candidate.
