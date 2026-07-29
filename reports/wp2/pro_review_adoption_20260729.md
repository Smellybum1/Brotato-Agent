# Adoption record: Pro consultation 2026-07-29 ("where next")

Assessment of the external review returned against `.tmp/pro_brief_20260729_where_next.md`.
Structure follows prior adoption records: what is accepted, what is rejected with reasons,
what changes in our own record, and the resulting critical path.

**Headline:** the review is substantively strong and lands five corrections on our record
that I accept. Its **top-line recommendation does not survive the variance-cost arithmetic
for the purpose it is offered for**, but the same instrument is excellent for a purpose the
review under-emphasises. The net effect is a real change of plan.

---

> ## ⚠️ SUPERSEDED IN PART — Step 0 ran the same day and refuted §1's central claim
>
> §1 below predicted `sigma2_between` would dominate, making Pro's estimator worthless
> (1.00x). **Measured on 80 existing control trials it is the opposite: ICC = 0.225,
> within-variance dominates, and the unpaired gain is 1.73x, not 1.00x.**
>
> My prediction used the "a doomed build replays as doomed" evidence, which is measured on
> **wave-17 survival** (ICC 0.538) and does not carry to **terminal win** (ICC 0.225) —
> waves 18-20 inject fresh RNG including the boss draw. That is the project's own
> stopping-one-step-short failure mode: reading which component dominates one aggregate
> and carrying it to a different one.
>
> **What survives:** the *conclusion* that the estimator does not rescue full-run win-rate
> measurement (1.73x turns 294 h into ~170 h), and the reframing that its real value is as
> the **paired fixture endpoint** (~7x). **What does not:** the arithmetic and the claim
> that the gain is zero. Full result: `reports/wp2/landmark_continuation_pilot.md`.

## 1. The one place the review is wrong: the continuation estimator as a win-rate instrument

Pro's Priority 1 is a landmark conditional-continuation estimator: restore a complete save
at a landmark, run `K` fresh-RNG continuations to run end, set `Y_i = mean_j(W_ij)`, and
estimate `P(win) = E[I(reach landmark) x P(win | landmark state)]`.

The **estimator is mathematically correct** — it is textbook Rao-Blackwellisation, and the
identity holds. The question Pro asserts rather than computes is whether it is *cheaper per
unit of information*.

Computed here. Full run: `p = 0.722`, variance `0.2007`, cost 19 min, so variance x cost =
**3.81**. Continuation cost is **4.3 min** (our wave-17 trial already resumes at the wave-16
shop and plays through to run end), so an independent prefix costs `19 - 4.3 = 14.7` min.
By the law of total variance `sigma2_between + sigma2_within = 0.2007`.

**Unpaired, estimating the overall win rate (prefix must be paid every time):**

| `sigma2_between` | `sigma2_within` | best `K` | variance x cost | gain vs full run |
|---|---|---|---|---|
| 0.15 | 0.051 | 1 | 3.81 | **1.00x — no gain at all** |
| 0.10 | 0.101 | 2 | 3.50 | 1.09x |
| 0.05 | 0.151 | 3 | 2.77 | 1.38x |
| 0.02 | 0.181 | 6 | 2.03 | 1.88x |

**Our own evidence puts us in the top row.** "A doomed build replays as doomed" —
`run_1785214891_49265` failed 4/4, 6/8 and 6/8 as control across three independent
experiments — and 12 of 16 fixtures never failed in either arm of the v2 campaign. That is
the signature of large between-state variance and small within-state variance, which is
exactly the regime where averaging continuations buys nothing. Pro notices the direction
("the optimum may be only a few repeats") but does not follow it through to the conclusion
that the gain collapses to 1.00x.

Even in the most favourable regime the gain is 1.9x, which turns a 294-hour experiment into
155 hours. **It does not rescue the full-run win-rate instrument.** Reject Priority 1 as
stated.

### The same instrument, used the way Pro under-emphasises, is very good

Restore the **same** source states into **both arms** and the between-state term — the one
that dominates — **cancels**. And because the fixture library already exists (73 snapshots),
the prefix cost is **sunk, not repaid**:

| `sigma2_within` | `K` | variance/state | cost/state | variance x cost |
|---|---|---|---|---|
| 0.05 | 2 | 0.050 | 17.2 min | **0.86** |
| 0.10 | 2 | 0.100 | 17.2 min | 1.72 |
| 0.15 | 2 | 0.150 | 17.2 min | 2.58 |

Against 3.81 for full runs that is a **1.5x to 4.4x** efficiency gain, on top of which the
prefix is free rather than costing 14.7 min per source. More importantly it changes *what*
the fixture harness measures: today its binary outcome is **saturated at 1.000** and we are
forced onto damage-taken as a proxy. **Terminal win, scored from a wave-16 landmark, is not
saturated** — `P(win | reached wave 16)` is about 26/34 = 0.765 — so it restores a
non-degenerate outcome that is the actual objective rather than a surrogate.

**ADOPTED, reframed:** not as a replacement for the full-run win-rate instrument, but as
the **outcome endpoint of the existing paired fixture harness**.

### The limitation neither the brief nor the review stated

The paired-landmark trick only avoids the prefix cost for interventions acting **at or
after the landmark**. A build-allocation change acts from wave 1, so it changes the prefix
too, and generating treated landmark states means replaying prefixes at 14.7 min each — at
which point the efficiency gain disappears (variance x cost 4.08 vs 3.81, i.e. *worse* than
full runs).

Pro's own chain does resolve this, and it is worth stating explicitly because it is the
load-bearing step: the counterfactual build is **instantiated by save-edit into existing
wave-16 states**, not produced by replaying a policy. That keeps the library reusable and
the pairing intact. The price, which Pro correctly flags, is that a save-edited build is a
**mechanism probe, not a deployable-policy counterfactual**. Accepted with that label
attached.

---

## 2. Corrections to our own record — all five accepted

1. **"Minimum dose is above 25%" is over-claimed.** The `0.95 / 0.90 / 0.85` arms were
   noisy and non-monotone (3/8, 5/8, 4/8) with overlapping intervals; pooled they give
   12/24 vs 0.75, p = 0.207. Absence of significance is not a demonstrated zero. The
   defensible statement is that the experiment **brackets a large sufficient dose**, not
   that it **locates a threshold**. This materially weakens the wave-17 closure argument,
   which was phrased as "the required intervention size is now known" — it is not known,
   only bounded above.
2. **"Movement is refuted" is too broad.** Stage A refutes one specific mechanism — the
   agent keeping enemies outside weapon range and therefore failing to fire. It does not
   refute escape-corridor collapse, high-speed overshoot, dithering at the wrong scale, or
   an earlier positioning choice that makes later headings impossible. Our own record
   already conceded that the sweep "contains no measured-velocity metric at all, so movement
   EXECUTION remains unmeasured"; the headline did not carry that caveat. **An agent can
   hold target uptime at 1.0 and still move catastrophically.**
3. **0.806 and ~0.79 are fixed-policy projections, not ceilings**, and they assume
   transportability that probably fails: runs rescued from a pre-wave-20 death are
   systematically weaker builds than runs that currently reach the boss, so applying the
   survivors' 26/30 downstream rate to them is optimistic. I had already corrected 0.80 to
   0.79 for this reason but did not go far enough.
4. **Zero unexplained damage is narrower than zero perception defect.** Our 0/115 (wave 17)
   and 0/180 (invoker) establish **attacker attribution at the hit tick**. They do not
   establish that the state carried enough information *before the position became
   unrecoverable* — correct collision geometry, telegraph phase, future occupancy,
   stale-sample age, effective-vs-base weapon values.
5. **The "doomed runs' boards were marginally better" argument is partly circular** for the
   valuation hypothesis. If board quality was scored by the incumbent scorer, then using it
   to rule out offer luck assumes the correctness of the very weights under question. This
   needs checking against how that comparison was actually computed.

**Not accepted as a correction:** Pro's 8.7 ("the full-run instrument can no longer resolve
any effect" is too absolute) is fair as literal wording, but the brief's surrounding table
made the quantitative claim precisely. Noted, not a substantive change.

---

## 3. The structural critique: "Gate 0"

Pro's sharpest process point is about **sequencing, not rigour**: several candidates reached
expensive pre-registered confirmation before answering cheaper questions — does this change
a real decision, how often, what is the maximum possible contribution, is the dose reachable
by a deployable policy, is the positive branch of the statistic reachable at all.

**Accepted.** We have done this well twice (the invoker gate no-go saved a whole campaign;
the v128 mispricing fix was withdrawn when it changed no ordering) and poorly elsewhere.

One partial defence worth recording: the wave-17 dose ladder used a lever the policy cannot
spend (enemy health), which looks like a Gate 0 violation, but its explicit purpose *was*
the actionability question — "how large must the intervention be?" — and no offline route to
that answer existed. It returned "large". That is Gate 0 reasoning executed with machine
time because it could not be executed offline.

---

## 4. Where Pro is clearly right and it changes the plan

- **"Which wave did it die on" is the wrong primary decomposition.** The terminal wave is
  where an accumulated deficit becomes fatal, not where it began. Classify runs by
  **earliest divergence** along opportunity → allocation → clearance margin → backlog →
  escape margin → damage. This directly explains why our loss budget looks diffuse: deaths
  at 15, 17 and 19 may be one upstream tempo failure wearing three hats.
- **The speed-vs-damage valuation hypothesis is genuinely untested and well identified.**
  The policy is deterministic and complete choice sets are logged, so the counterfactual can
  be computed **entirely offline with zero machine time**, and it has a clean NO-GO: if the
  best legal re-ranking of the actual offers cannot materially move the wave-17 build, the
  hypothesis closes for real rather than by aggregate proxy.
- **The perception result is a triage prior, not a law.** One success, on an exceptionally
  large defect (84-91% of a damage channel absent). Justifies **one bounded census**, not an
  indefinite hunt.
- **The freeze should become conditional rather than permanent** — staged unfreeze of waves
  15-19 for candidates that have already passed an actionability gate, with the champion
  frozen by behaviour hash as a concurrent control, plus shadow execution before live
  control. This preserves the control's function while unfencing the region holding 80% of
  the loss.

---

## 5. What Pro could not know

**Human movement takeover (its Phase E) cannot be automated.** Synthetic keyboard input does
not reach Brotato in fullscreen — `keybd_event` with both VK and scancode fails, which is
why override and E-stop tests have always needed physical operator keys. So the 2x2 ceiling
benchmark is an **operator-time** cost, not a machine-time cost.

That does not weaken the idea; it is arguably the highest information-per-hour item on the
entire list. Movement headroom on a fixed build is precisely what the uptime analysis could
not settle, and a session of ~10 restored wave-17 fixtures would settle it directly. It just
needs the operator's hands.

---

## 6. Resulting critical path

Ordered by information per hour, not by Pro's phase lettering.

**Step 0 — FREE, no machine time. Re-score the 232 existing wave-17 trials on terminal
outcome.** Those trials already play through to run end. Scoring the control arms on
eventual win yields (a) `P(win | wave-16 state)` per fixture, (b) the
`sigma2_between / sigma2_within` split that decides whether §1's estimator is worth anything
at all, and (c) an immediate readout on whether terminal win is a usable non-saturated
endpoint. This *is* Pro's Phase A pilot, already paid for. Treatment arms are contaminated
beyond wave 17 (the `enemy_scaling` edit persists), so only control arms are clean.

**Step 1 — offline, no machine time. The legal-decision frontier audit.** Replay every shop
and level-up screen through wave 16 under the incumbent scorer, a speed-vs-damage
reweighting, an offense-first rule, and a best-legal-clearance oracle. Report decision flips,
wave of first divergence, cumulative build delta, and a strict upper bound. **NO-GO closes
the valuation hypothesis honestly; GO produces a reachable dose to test.**

**Step 2 — operator time, ~1-2 h. Human movement takeover** on 8-10 restored wave-17
fixtures, build held fixed. Settles movement headroom directly.

**Step 3 — conditional on Step 1 GO. The 2x2 save-edit factorial** (offense up / speed down /
both) on enriched low-clearance wave-16 states, scored on terminal outcome, paired,
source-state clustered.

**Deprioritised:** the predictive-state census — worth doing, but scoped to wave-17 melee
crowding rather than a whole-game registry, and only after Steps 0-2. Everything Pro itself
declined stays declined.

**Also adopted as standing practice:** source state is the inferential unit and all analysis
is source-state clustered; `K` continuations from one save are not `K` independent builds.

---

## 7. Verdict

The review earns its keep. It does not overturn the wave-17 result, but it correctly
demotes it from "closed" to "bounded above, with the natural cause not attributed", and it
identifies one genuinely open substantive hypothesis inside what we had recorded as a
closed null. Its instrument proposal needs the reframing in §1 to be worth adopting; with
that reframing it is the most useful thing in the document, because it replaces a saturated
binary and a proxy endpoint with the actual objective.

**Nothing here requires a deploy, a version bump, or spending the internal control.** Steps
0 and 1 are both zero machine time.
