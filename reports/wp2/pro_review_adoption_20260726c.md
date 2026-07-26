# Pro consultation — adoption record, 2026-07-26 (third set: win-rate regression)

Brief: `.tmp/pro_consultation_brief_20260726c.md`. Reply fetched via share link.
Selective adoption with reasons, per standing pattern.

---

## THE BLOCKING DISCOVERY: Pro's recommended first experiment is not buildable

Pro's central recommendation — and its single sharpest correction to my proposal —
is: **do not make the first challenger a novel "stripped-back" policy; test exact
v72 behaviour ported into the current harness, qualified by action-trace
equivalence replay.** The reasoning is sound and I accept it in principle: a novel
treatment makes a negative result ambiguous (was the hypothesis wrong, or did I just
build a bad policy?), whereas a known historical anchor answers exactly one question
— *is recoverable performance still present in the old behaviour?*

**It cannot be done. v72 does not exist anywhere.**

Verified this session:
- The repo's **first commit is `9a390f4` (2026-07-22), "Establish WP1 certified
  baseline"** — and the code at that commit is **`0.1.92`**, not v72.
- The **`wp1-baseline` tag points at that same commit**, i.e. the tag named for the
  certified baseline contains a policy the archive scores at **2W/8L = 20%**, twenty
  versions past certification and deep in the collapse band.
- No source backups exist: `backups/` holds game userdata (save files), and every
  `.zip` on disk is a pytest fixture.
- v72's runs cannot supply the parameters either. A v72 run dir holds only
  `events.jsonl` (0.32 MB) + `summary.json`; `combat_tick` fires at 0.5 s (723 per
  run, not the 20 Hz capture stream), and **`run_start` records identity only —
  no policy constants, thresholds or config table.**

**Root cause, worth recording separately:** WP1 certified v72 on 2026-07-21 while the
repo had **zero commits**. Version control was initialised the next day, by which
point the working tree had moved on to v92. **The certified baseline was never
preserved — it was overwritten in place.** This is the single most expensive
process defect in the project's history and it is unrecoverable.

Consequence: there is **no historical anchor arm**, and no fresh run can ever settle
the winner's-curse question about v72's true rate. Everything about the past must
now come from the archive alone.

---

## Adopted in full

**A1. The governance finding is the firm part; the magnitude is not.** Pro
separates four claims and I adopt the split verbatim:

| claim | status |
|---|---|
| post-WP1 qualification did not control win rate | **Established** |
| at least one substantial regression occurred | **Strongly supported** |
| current teacher is truly ~35% and v72 truly 90% | **NOT established** |
| accreted movement layers caused most of it | Plausible first hypothesis only |

**A2. The winner's-curse quantification.** Pro's calculation: if 15 candidates all
shared one true win rate, the chance at least one posts >=18/20 is 0.3% at a true
50%, 16.7% at 65%, **41.8% at 70%**, 59.1% at 72.5%. So v72's 18/20 is entirely
compatible with a **true rate near 70-73%** and quite incompatible with 50%.
**Correct framing: "a policy probably existed near v72 materially better than the
present one, plausibly low-to-mid 70s" — a 20-25 point regression, not 40.** I had
flagged the multiple-comparisons problem but never quantified it; this replaces my
headline number.

**A3. Do not use 34.6% as "the current teacher."** The v125-128 band mixes teacher,
student, residual and random-control runs. The only defensible current figure is the
clean **10/20 = 50%** F2 pure-teacher arm, with wide CI. I used 34.6% in my summary
table; that was wrong and is withdrawn.

**A4. The stopping-rule correction.** The pooled 72.6% for v60-72 is a valid
description of the recorded run population but is **not** an unbiased estimate of a
randomly chosen early version, because strong versions survived longer and therefore
contributed more runs. Fix with three analyses, all adopted: **common-prefix**
(compare the first k runs of every version), **equal-version weighting**, and a
**hierarchical beta-binomial** with shrinkage — preferred over averaging small
per-version rates.

**A5. Missingness must be bounded, not argued.** Adopted with the explicit
sensitivity formula. Pro's illustration: with 20 missing early runs, the current band
would need ~55 missing runs *all wins* to erase the gap; with 50 missing early, ~25.
A mathematical reversal is possible but requires an adversarial distribution.
**Do not impute the 188 as one undifferentiated class.** Adopt the terminal-class
taxonomy: `WIN / GAMEPLAY_LOSS / MOD_OR_POLICY_FAILURE / EXTERNAL_ABORT / UNKNOWN`,
and report **two** metrics — `end_to_end_success` (technical failures count as
failures of the deployable system) and `gameplay_win_rate` (policy strength alone).
Given this project has lost whole deploy cycles to parse errors, that split is not
academic. Unresolved cases stay UNKNOWN and enter a formal sensitivity grid.

**A6. Key on behaviour hash, not version number.** "A nominal v125 run with pure
teacher, noisy residual and deterministic residual are not interchangeable."
Adopted — the attempt ledger keys on a behaviour/commit hash plus explicit
`run_mode`.

**A7. Change-point detection method.** Segmented Bernoulli model at
version/behaviour-hash boundaries, minimum segment size ~20 teacher attempts,
BIC-like penalty, version-level bootstrap, **and consult the code notes only AFTER
the breakpoints are chosen.** That last clause matters — it prevents me fitting
breakpoints to the story I already believe.

**A8. Offline replay cannot reconstruct counterfactual outcomes.** The policy is
deterministic, so once an alternative action is issued the trajectory diverges and
the recorded future is no longer valid. **Offline replay is a prioritisation and
mechanism tool, never a substitute for live A/B.** Adopted emphatically — I spent
this week doing exactly this kind of replay on the shop layer and could easily have
over-extended it here.

**A9. The power correction — this kills my Phase D as written.** I proposed a gate
of "8-12 runs with a Bayesian stopping rule." Pro: against an incumbent at 75% and an
unacceptable candidate at 55%, **12 runs catches the bad candidate only 47% of the
time**; 20 runs 75%; 26 runs 81% — and that is with the incumbent's rate treated as
*known*. A fresh two-arm comparison needs roughly 50/arm for conventional power.
Decisive line: **"A Bayesian stopping rule changes when you stop. It does not create
information."** So 8-12 runs is a **canary, not a qualification**. Adopted:
champion bank of 30-40 clean incumbent runs so no candidate pays for a control arm;
sequential test with an explicit indifference region; cap ~25-30 candidate runs;
**inconclusive at the cap means DO NOT SHIP** — never "passed because audits were
green."

**A10. "Movement-safety invariants" are mostly not invariants.** The sharpest
insight in the reply: *"A movement-safety audit can actively preserve a harmful
heuristic by defining compliance with that heuristic as success."* Hard constraints
are parser/load success, determinism, schema correctness, action legality, no
impossible commands. **"Never violate the density veto" is a hypothesis that a
heuristic improves survival, not a safety property.** This explains mechanically how
audits stayed green through a 40-point collapse. Adopted: demote heuristic-compliance
checks to diagnostics unless they have demonstrated aggregate survival value.

**A11. The three-gate model**, with the line that matters:
`1. EXECUTABILITY AND DETERMINISM / 2. MECHANISTIC CONSTRAINTS / 3. OUTCOME`, and
**Gate 2 can never substitute for Gate 3 again.** Adopted as the process fix.

**A12. Subsystem swap before individual ablation, and NO global binary search.**
Because performance was non-monotonic (collapse -> partial repair -> further
decline), a single bisection over v72-v128 is **invalid**; use archive change points
to define local intervals and split within each. Test coherent, historically ordered
*bundles*, not arbitrary individual switches. Adopted — I would have gotten the
global-bisection part wrong.

**A13. WP2 is not invalidated, only reframed.** The BC result describes imitation of
the degraded teacher distribution; the residual-RL nulls remain null *against the
teacher they ran on* and do **not** establish that residual learning cannot help a
restored champion. The telemetry and audit infrastructure is what made this diagnosis
possible at all. **Freeze WP2, do not discard it.** Adopted, and it is a fairer
reading of the last three weeks than mine was.

**A14. The competing-hypothesis table with discriminating results.** Adopted as the
structure for Phase B, minus the two rows that require the v72 anchor.

**A15. The accretion hypothesis is worth privileging as FIRST hypothesis, not as
conclusion** — and it is more than pattern-matching, because both subsystems share
the same causal *process*: failure observed -> local compensating rule -> validated
against that exemplar + internal audits -> aggregate outcome never remeasured ->
later rules interact -> removing one is inert because others reproduce its effect.
That is a project-level failure mode, not a coincidental code shape. Its falsifiable
telemetry predictions (override activation frequency, final command dominated by
late-stage vetoes, layers cancelling each other, hysteretic modes persisting after
their trigger clears) are adopted as Phase B's measurement targets.

---

## Adapted, because the anchor does not exist

**R1. Pro's Step 2 (v72-behaviour / current-harness arm) is REPLACED, not adopted.**
Nothing to port, and no way to satisfy its action-trace equivalence requirement.

**R2. Replacement for the anchor: characterise v72 instead of running it.** The
v60-72 band holds ~113 archived runs; at 723 `combat_tick` events each that is
~80k ticks of the strong-era policy, plus every level-up, purchase and crate
decision. That cannot produce a win-rate anchor, but it *can* produce a behavioural
signature contrast against the current era — positioning, corner occupancy, movement
magnitude, damage-event timing, decision patterns. **This substitutes mechanism
evidence for the anchor experiment**, and it is offline and free.

Explicitly acknowledged limitation: this weakens the design exactly where Pro said
it matters. Without the anchor, the "runtime/instrumentation drift" hypothesis and
the "archive selection explains everything" hypothesis **cannot be cleanly
discriminated**. Any reduction I build is a novel treatment with an ambiguous
negative — Pro's objection stands and is now unavoidable rather than a choice.

**R3. One usable calibration anchor survives: v92.** It is the earliest source that
exists (at `wp1-baseline`), and the archive scores it 2W/8L. It is a *bad* policy, so
it is useless for recovery — but re-running it now is a direct test of **archive
validity**: if v92 reproduces ~20% under the current harness, the archive's win-rate
measurements are sound and the regression thesis holds; if v92 now scores ~50%, the
archive is measuring something that no longer applies and the whole thesis weakens.
Because the predicted effect is large (20% vs 50%), ~12 runs suffice. **Cheaper and
more decisive than anything else available for testing the environmental-drift
hypothesis.** Caveat: v92's archived 2W/8L is n=10, CI roughly [6%, 51%] — wide, and
that must be carried into the comparison.

**R4. Not adopted: paired/common seeds.** Pro offers it conditionally ("where game
seeds can be controlled"). Already established as unavailable here — Brotato's
wave/offer RNG is not exposed for pinning, which is why the F2 campaign used
alternating arms under matched machine load. Randomised interleaving (A B B A /
B A A B) and the machine-load covariate ARE adopted.

**R5. Deferred: exact saved-state branch replay.** Pro flags it as worthwhile only
if the game already supports sufficiently exact state restoration and warns against
another infrastructure detour. Brotato offers no such facility. Deferred, not
rejected.

---

## Revised plan

**Phase A — archive reconstruction** (offline, free). Attempt-level ledger keyed on
behaviour hash + run_mode; recover the 188 from their event streams; terminal-class
taxonomy; `end_to_end_success` and `gameplay_win_rate`; common-prefix,
equal-version and hierarchical beta-binomial estimates; missingness sensitivity
grid; segmented-Bernoulli change points chosen **before** reading the change notes.

**Phase B — characterise the strong era** (offline, free). Behavioural signature
contrast v60-72 vs current over ~80k old-era ticks, targeting the accretion
hypothesis's falsifiable predictions. Also instrument the *current* decision stack
(base vector -> vector after each layer -> activation reason -> final controlling
layer -> angular change introduced). That is measurement, not feature work.

**Phase C — champion bank** for the current teacher: 30-40 clean teacher-only runs.
Needed by every subsequent comparison, and it replaces the contaminated 34.6%/50%
figures with a properly powered incumbent rate. ~10-13 h, overnight-able.

**Phase D — v92 archive-validity check** (~12 runs). Confirms or breaks the
environmental-drift hypothesis; the one historical anchor still available.

**Phase E — challenger**, designed from B's evidence rather than intuition, tested
against C's champion under the A9 sequential gate.

**Phase F — process fix, ships regardless and does not depend on any of the above.**
Three-gate model; heuristic audits demoted to diagnostics; sequential gate with
indifference region and 25-30 cap; automatic append-only attempt ledger for every
initiated run with rolling deterioration alerting. Pro's line: had that existed,
*"the v84-99 collapse could not have remained invisible for 45 versions."*

**Immediate housekeeping:** the `wp1-baseline` tag is misnamed and is a live trap —
it advertises the certified baseline and contains a 20%-win-rate policy. Annotate or
rename before anyone (including me) trusts it again.
