# Wave-17 v2: `NEAR_TOTAL_RESCUE`, and it rests on ONE fixture

Preregistration: `reports/wp2/wave17_dose_response_prereg_v2.md`, frozen 2026-07-28
20:45 before any v2 trial. Predecessor pilot: `wave17_round1_ceiling.md`.

**Verdict by the frozen rule: `NEAR_TOTAL_RESCUE`.** All three bars met.
**But 4 of the 7 control failures came from a single fixture, and without it the design
is uninformative.** That belongs in the headline, not a footnote.

## What ran

128 trials (16 fixtures x 4 reps x {C health 1.00, H50 health 0.50}), 64 per arm,
20:34-05:28 on 2026-07-28/29, 16 blocks all exit 0. **128/128 valid, 0 invalid in either
arm.** Arm order randomised within fixture, seed `202607282045`. Round-1 data NOT pooled.

## Result

| arm | wave-17 failure |
|---|---|
| `C` (health 1.00) | **7/64 = 0.109** |
| `H50` (health 0.50) | **0/64 = 0.000** |

Fisher one-sided **p = 0.0066**. Fixture-clustered 95% CI on the rate difference
**[-0.250, -0.016]**, excluding zero. Frozen bars: control failures 7 >= 4 ✓,
H50 rate 0.000 <= 0.02 ✓, p < 0.05 ✓.

The control rate **0.109 replicates round 1's 0.125** on an independent sample — the
wave-17 per-attempt failure rate is real and stable at ~11-12%.

## ⚠️ What actually carries it

| fixture | C | H50 | p |
|---|---|---|---|
| **run_1785214891_49265** | **4/4** | **0/4** | **0.0143** |
| run_1785205890_26468 | 1/4 | 0/4 | 0.50 |
| run_1785211397_60764 | 1/4 | 0/4 | 0.50 |
| run_1785213741_10128 | 1/4 | 0/4 | 0.50 |
| the other 12 fixtures | 0/4 each | 0/4 each | — |

Leave-one-fixture-out: the verdict survives 15 of 16 drops at p 0.0065-0.0137. Dropping
**run_1785214891_49265** leaves C 3/60, H50 0/60, **p = 0.122**, control failures 3 — which
is `UNINFORMATIVE_CONTROL` under the same frozen rule.

**So the defensible claim is narrow:**

> On a build that RELIABLY dies at wave 17, halving enemy health eliminated the deaths:
> 4/4 -> 0/4 within that fixture, p = 0.0143.

That single-fixture result is significant on its own and is not an artifact of pooling.
The broader claim — that clear-rate demand governs wave-17 failure *in general* — rests
on one fixture and is **weak**. Twelve of sixteen fixtures never failed in either arm and
contributed no information at all.

## The fixture that matters, and where to get more

`run_1785214891_49265` is the fixture taken from the ONE collection run that itself died
at wave 17. It reproduced that death **4/4 under control** — so a doomed build replays as
doomed, with fresh spawn RNG each time. Its entry `nominal_dps` is **22.10**, below Stage
A's died median of 28.26.

**Reliably-failing fixtures are the scarce resource, and this is the whole cost driver.**
Yield measured here: **1 of 16** fixtures drawn from arbitrary runs; **1 of 1** drawn from
a run that died at wave 17. Wave-17 deaths run ~9-12% of full runs, so ~10 such fixtures
costs ~90-110 full runs, roughly 30-36 h of collection.

Archive runs **cannot** be converted: the mid-run save must be snapshotted while the run
is live, and the 41 historical died-at-17 runs have no saves.

## What this does NOT establish

- **Not that a MODEST clearance gain helps.** The `H75` arm was dropped; that question
  needs ~48 h (340 trials/arm at a 0.125 base rate) and is unanswered.
- **Not that the player weapon-damage sum is causal.** This manipulates the DEMAND side.
- **Not a licence for movement-side work.** Stage A already refuted the movement/uptime
  story on its own sign; nothing here revives it.
- **Not a general law about wave 17** — see above; one fixture.

## Recommended next step

Do NOT spend 30+ h collecting failing fixtures on the strength of one. Cheaper and more
informative: take `run_1785214891_49265` plus any further reliably-failing fixtures found
incidentally, and run the **dose ladder** (C / H75 / H50) *within* them. Within-fixture,
a 4/4 control gives usable power at 8 trials, so the modest-dose question that was
unaffordable across a mixed library becomes affordable inside a fixture that actually
fails. That directly attacks the actionability question a rescue result cannot answer.
