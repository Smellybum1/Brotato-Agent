# VERDICT — `time_scale` acceleration FAILS. Campaigns run at 1.0x.

Protocol: `reports/wp2/timescale_equivalence_protocol.md`, committed before trial 1
(`75bad99`) and amended (A1-A6) before any outcome data was read. Build mod
`0.2.49-wp2-capture`, policy `teacher_v1-0.1.129-gun-wp1`, verified identical on
all 64 trials. 8 predator fixtures x 4 rounds x 2 arms, **32 pairs, 64/64 valid.**

## Result

| measure | 1.0x | 8.0x (nominal) | |
|---|---|---|---|
| mean damage taken | 22.06 | **45.22** | +105% |
| mean paired difference | — | **+23.16** | 95% CI **[+10.53, +35.78]**, excludes 0 |
| victories | **32/32** | **26/32** | Fisher p = 0.024 |
| zero-damage trials | **16/32** | **6/32** | Fisher p = 0.017 |
| pairs fast-worse / fast-better | — | **23 / 5** (4 tied) | sign test p = 0.0009 |
| achieved speedup | 1.0x | **6.20x median** (5.00-6.91) | |

**Verdict: FAIL.** Acceleration roughly doubles damage taken and converts a
pinned 1.000 win rate into 0.813. The pre-declared consequence applies:
acceleration stays a dev convenience and **real campaigns run at 1.0x**.

**It replicated.** Rounds 1-2 gave +11.69 (CI straddling zero, nothing
significant — a proper screen result). The pre-registered escalation, a fresh
sample under a rule fixed in advance, gave **+34.62 with 13/16 pairs worse**.
This is the opposite of the finale-v2 pattern, where a promising campaign 1
reversed on fresh data.

## Two readings of the rule, one answer

The literal verdict is **FAIL by rule 1** — G1 failed. But G1 is a gate I
mis-specified, so it should not carry the decision alone:

**G1 was wrong and I am recording that rather than quietly rebanding it.** I
required the fast/slow capture-rate ratio to land in `[6.5, 9.5]`, which
conflates *acceleration took effect* (the gate's stated purpose) with
*acceleration achieved exactly 8x* (a throughput fact about this machine). The
observed 6.20 proves the former decisively — the slow arm sits at 1.00 — while
failing a band built on the latter. Had G1 been written to its own stated
purpose it would have PASSED.

It does not matter. With G1 passing, the CI `[+10.53, +35.78]` excludes zero and
its point estimate exceeds the equivalence margin of 19, so the rules give
INCONCLUSIVE with the single escalation already spent. No branch of this protocol
approves acceleration, and no honest reading of the data does either. **This is
not "equivalence was not established" — it is non-equivalence established in the
harmful direction.**

## Two spurious gate failures, caught only by computing the table independently

The evaluator's first run reported three failures. Two were artifacts:

- **G2** tested `isinstance(boss_paths, list)`. `boss_paths` is a **dict**
  `{script_path: count}`, so the check flagged all 32 clean rows. **A gate that
  cannot pass carries no information** — the same shape as the `can_buy` vacuous
  filter and the sub-1st-percentile proximity threshold.
- **G3** expected `policy_version == "0.1.129"`; the field carries
  `teacher_v1-0.1.129-gun-wp1`. My protocol wrote the expected value wrong.

Both were found because the raw pair table was computed in the primary session
BEFORE the evaluator ran, and the two disagreed. A single confident FAIL from a
competent-looking tool is exactly what that habit exists to catch.

## THE MECHANISM IS UNIDENTIFIED — and the standing validity check is blind to it

**Do not record a cause. Three candidates were checked and all three are
refuted:**

1. **Decision starvation — REFUTED.** A full-length wave 20 is a fixed amount of
   game time and records **1800 captures at 1.0x and 1802 at 8.0x**. That is 20
   captures and 60 physics ticks per GAME second in both arms. No physics steps
   are dropped in game time.
2. **Orbiter velocity inflation — REFUTED.** `agent_controller.gd:783` already
   derives `game_dt` from `Engine.time_scale / iterations_per_second`, with a
   comment recording that this exact bug was found and fixed (864 u/s at 1x
   inflating to 6000 at 4x).
3. **Real-time gates in the control path — REFUTED.** The four remaining
   `OS.get_ticks_msec()` sites are shop cadence (1227), level-up/crate UI
   cadence (1867), end-run forcing (2461), and telemetry (923). **None gates
   combat movement.**

**The lesson that generalises past this campaign:** the standing acceleration
validity check — *captures per game-second must read 20.0* — **PASSED CLEANLY IN
BOTH ARMS** and would have certified acceleration as safe. It cannot fail for
anything that scales captures and decisions together, which is nearly every
timing defect worth worrying about. **An internal consistency check is not an
outcome check**, and only the outcome comparison caught a doubling of damage
taken.

## Secondary finding — a live real-time bug in the capture payload

`agent_controller.gd:928-930` computes `control_dt_ms` from
`OS.get_ticks_msec()` and derives `player.measured_vx/vy` as game displacement
divided by that REAL dt. Under acceleration real dt shrinks ~6.2x while
displacement does not, so **`measured_vx/vy` is inflated ~6.2x in any capture
recorded at `time_scale > 1`.** It is the same defect already fixed for the
mounted projectiles at line 783, still live here.

It is **telemetry-only** — grep confirms the value is consumed at lines 978-979
and nowhere else, so **it does not explain the degraded play** and must not be
cited as the cause. Its significance is that it gives the mechanism for the
existing rule that **dataset collection must stay at 1.0x**.

## What would reopen this

Not more trials at 8x — that question is settled. The open question is whether a
LOWER scale is safe, which is a dose-response design (1x / 2x / 4x), not a
repeat. Worth it only if someone wants the ~6x back badly enough to fund finding
the mechanism first; a scale that changes outcomes is not made safe by being
smaller, only harder to detect.
