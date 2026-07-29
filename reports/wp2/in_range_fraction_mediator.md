# The agent converts fewer enemies into targets — and that gives us a cheap Gate 0 endpoint

**Date:** 2026-07-29. Follow-on to `engagement_distance_lead.md`. No new machine time.

## The check that nearly refuted my own lead

I had claimed the agent's clearance deficit comes from fighting at longer range. But its weapons
reach **470-692 u** and it sits at a median **405 u** from the nearest enemy — **already in range**.
On that reading the lead should have died.

It survives, because *nearest*-enemy distance is the wrong quantity. The right one is **what fraction
of the pack the agent can actually shoot.**

## Result — the agent engages ~half as much of the pack

Waves 17-20, matched fixture C, 5 human trials (17,414 ticks) vs 5 agent trials (23,264 ticks):

| | human | agent |
|---|---|---|
| enemies **on map** (median / mean) | 15.0 / 21.4 | 17.0 / 20.8 |
| enemies **in weapon range** (median / mean) | 5.0 / **9.0** | 4.0 / **5.8** |
| **fraction of pack in range** (median) | **0.385** | **0.224** |
| ticks with **ZERO** enemies in range | **0.0675** | **0.1415** |

**Enemy presence is essentially identical** (means 21.4 vs 20.8) — this is not an exposure
difference, it is a conversion difference. The agent turns **1.7x less** of the same pack into
targets, and spends **one tick in seven with nothing it can shoot at**, twice the human's rate.

That is the offense deficit the wave-17 work identified (`nominal_dps` as the separator), now
localised to **positioning rather than build**.

## The endpoint: per-trial in-range fraction, wave 17 only

| arm | n | mean | SD | range |
|---|---|---|---|---|
| human | 5 | **0.4417** | 0.0187 | 0.4095 - 0.4558 |
| agent | 10 | **0.2801** | 0.0535 | 0.2021 - 0.3784 |

**Perfectly separated — every human trial exceeds every agent trial.** Difference 0.1616, pooled SD
0.0401, **Cohen's d = 4.03**.

Compare what the outcome endpoints cost on the same fixtures (`campaign_sizing_v2.md`): terminal
survival and HP-deficit AUC both need **64 paired trials** to see a 50% effect, and AUC is 59.8%
zero-inflated. This endpoint is dense, continuous, non-zero-inflated, and has an enormous
signal-to-noise ratio.

**So it is the Gate 0 instrument the engagement-distance line was missing.** A candidate treatment
can be screened for whether it actually moves engagement geometry toward the human's, on a handful
of trials, *before* anyone commissions a survival campaign.

## ⚠️ It is a MEDIATOR, not an OUTCOME — do not confuse them

**Moving in-range fraction does not prove survival improves.** A treatment could raise it by walking
into the pack and get the agent killed faster. This endpoint answers "did the intervention change
the geometry it was designed to change?" — it does **not** answer "did it help?"

The project already has the general form of this mistake on record: a defect being real does not make
it load-bearing. The surrogate version is the same error one level up. **A screen on this endpoint
licenses a survival campaign; it never substitutes for one.**

Three further limits:

1. **The d = 4.03 is a human-vs-agent gap, not a treatment effect.** These are two very different
   policies. Any parameter change will move this endpoint far less, so the "n ≈ 2 per arm"
   extrapolation is *not* a campaign size — it means the endpoint has headroom, nothing more.
2. **"In range" uses the max over the six weapons**, i.e. "at least one weapon could hit". It is a
   proxy for DPS opportunity, not DPS. A weighted version (how many weapons cover the target) would
   be strictly better and is not computed here.
3. Weapon `max_range` sets differ slightly between arms (human 522-667, agent 470-692) because
   builds evolve across waves 18-20. The human's maxima are *lower* on average and it still converts
   more of the pack, which cuts against this being a range-of-build artifact.

## What this makes possible next

The practical path is now three-staged and front-loads the cheap parts:

1. **Identify candidate engagement-distance knobs** and prove offline that each changes the final
   command at a reachable dose. Still the unbuilt piece — no offline replay of `compute_movement`
   exists.
2. **Screen on in-range fraction** (cheap, ~8-16 trials per arm) for whether the knob moves geometry
   into the human band *without* raising low-HP exposure. Reject anything that buys targets with
   safety.
3. **Only then** run the preregistered survival campaign, using titrated fixtures
   (`overdose_instrument_check.md`) for the screen and **baseline** doses for confirmation.

Stage 2 is what did not exist before today, and it is why the line is now cheap to test rather than
expensive to guess at.
