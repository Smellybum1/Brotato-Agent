# Release gate policy

**Status:** adopted 2026-07-26. Replaces "one smoke run + audits report zero
violations", which is the procedure under which this project lost its win rate.

## Why this exists

From roughly policy v0.1.84, a behavioural version shipped if one ~20-minute smoke
run completed and the audits reported zero violations. Reconstructed from the run
archive (`reports/wp2/winrate_history_verdict.md`):

| segment | W/n | rate |
|---|---|---|
| v60-83 | 92/132 | 69.7% |
| v84-103 | 12/53 | **22.6%** |
| v104-128 | 41/76 | 53.9% |

**A 47-point collapse (Fisher p = 8.9e-09) persisted across roughly twenty versions
without anything firing**, and the subsequent recovery never restored the peak.
Neither fact was knowable at the time. A single run has essentially no power against
a 20-point effect, and the audits test internal rule compliance rather than outcomes.

## The three gates

Every behavioural release must pass all three, independently.

```
1. EXECUTABILITY AND DETERMINISM
   parse/load success, telemetry schema conformance, action legality,
   reproducibility, build identity matches what was requested

2. MECHANISTIC CONSTRAINTS
   the intended feature actually activates; known failure fixtures still handled;
   no genuine hard-rule breach

3. OUTCOME
   the candidate is not materially worse than the champion  <-- scripts/wp2_release_gate.py
```

**Gate 2 can never substitute for Gate 3 again.** That substitution is precisely what
happened, and it is why the collapse was invisible.

## Gate 1 vs Gate 2: the distinction that matters

A check belongs in Gate 1 only if violating it means the system is **broken or
non-deterministic regardless of outcome** — the game cannot load the mod, the schema
does not match, the policy emits a command the engine cannot accept, the build is not
the one requested.

Most "movement-safety invariants" in this repo are **not** invariants. They assert
that the policy obeyed a behavioural rule someone added because they believed it aids
survival. That is a *hypothesis*, not a safety property.

> An audit asserting "the density veto was always obeyed" can actively **preserve a
> harmful heuristic** by defining compliance with it as success.

If obeying such a rule reduces win rate, **the rule is wrong and the audit is
enforcing a mistake.** Heuristic-compliance checks are therefore monitored as
diagnostics and reported, but they do not block a release on their own.

This is not hypothetical here. The accumulated movement/safety layer demonstrably
*works* at its stated job — damage taken fell 2.46x between the peak era and now
(mean 295.9 -> 120.3) — and the win rate fell anyway. Rule compliance and the
objective had come apart, and only Gate 3 can see that.

## Gate 3: the champion/challenger sequential test

Implemented by `scripts/wp2_release_gate.py`; operating characteristics by
`scripts/wp2_gate_calibration.py`.

```
REJECT   when P(p_cand <= p_champ - 0.20) >= 0.90
PROMOTE  when P(p_cand >= p_champ - 0.05) >= 0.90
CONTINUE otherwise, minimum 6 runs, cap 30
INCONCLUSIVE at the cap  ->  DO NOT SHIP
```

The champion is a **frozen** policy with a bank of ~30-40 clean runs at that exact
behaviour. Its rate is *estimated, not known*, and the gate integrates over that
uncertainty — treating the champion as known overstates power.

### Measured operating characteristics
Champion truly 50%, 36-run bank, cap 30, 3,000 simulated campaigns per row:

| candidate truth | promote | reject | inconclusive |
|---|---|---|---|
| +10 pp (clearly better) | 0.647 | 0.007 | 0.346 |
| identical | 0.404 | 0.022 | 0.574 |
| −20 pp (unacceptable) | **0.057** | 0.212 | 0.731 |
| −30 pp (badly broken) | 0.009 | 0.463 | 0.528 |

**Read this honestly. The gate is safe, not powerful.** It promotes a truly
20-point-worse candidate only 5.7% of the time — but it promotes a genuinely *good*
one just 40-65% of the time. **"Inconclusive = do not ship" is the entire reason low
power becomes conservatism rather than risk.** The cost is shipping velocity, which
is the right place to pay: this project lost its win rate by shipping freely.

Two findings that constrain expectations:
- **Raising the cap barely helps.** Cap 50 moves rejection of an unacceptable
  candidate from 0.212 to 0.242. The variance of binary outcomes at these rates
  dominates.
- **A stronger champion does NOT make gating cheaper.** Checked directly: at a 75%
  champion the promote-a-bad-candidate rate is 4.3% vs 5.7% at 50% — essentially
  unchanged. Do not expect recovery work to reduce future gate costs.

### Consequences for how work is sequenced
- **Batch behavioural changes.** One gate costs up to 30 runs (~10 h) and often ends
  inconclusive. Two separately-gated versions a week is not affordable. Keep internal
  version numbers, but promote in batches with feature flags and full score/action
  decomposition retained.
- **Refactors claiming to be behaviour-preserving** pay a different price: a
  large action-trace equivalence replay over archived inputs, plus one smoke — not a
  win-rate campaign. A source-text assertion is *not* sufficient evidence of
  equivalence; this repo has a documented case of a source-text pin asserting a fatal
  parse bug as a requirement.
- **Refresh the champion bank** after runtime, telemetry, machine or deployment
  changes — a historical bank is only valid while the environment is stationary.

## Continuous monitoring

Every initiated run enters an append-only attempt ledger automatically, whether or
not a normal summary is written. In the current archive, **186 of 642 attempts have
no recoverable outcome** and 187 of 188 summary-absent streams end with the player
alive mid-wave — process terminations that no procedure was watching. Outcome
monitoring must not depend on the happy path completing.

Report both:
- `end_to_end_success` = wins / all initiated attempts except demonstrable external
  aborts. Technical failures are failures of the deployable system.
- `gameplay_win_rate` = wins / (wins + ordinary gameplay losses). Policy strength
  alone.

Had a rolling deterioration alert existed, the v84-103 collapse could not have
remained invisible for twenty versions.
