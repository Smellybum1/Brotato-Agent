# The successor lead: the agent edge-kites, the human fights close and central

**Date:** 2026-07-29. Opened after the collection line closed
(`reports/wp2/collection_line_closure.md`). No machine time — this uses the handover triples that
already exist.

**The asset.** The `human_movement` instrument logs the agent's intended vector every tick *while
the human drives*, so each tick of a human trial is a triple **(state, agent intent, human action)
on the same state**. That removes the build confound entirely: this is not human-run vs agent-run,
it is two decisions evaluated on one state.

**Arms.** The 5 matched fixture-C human trials (16,317 usable ticks) and 5 agent trials on the same
fixture at the same enemy dose (23,341 ticks), waves 17-20. Captures with `control_dt_ms < 10` are
excluded — measured velocity is displacement/dt and explodes at start-up dt.

---

## ⚠️ Read the instrument limit first

**The human's action space is 8-way, the agent's is continuous.** Measured on realised heading:

| | on the 45° grid | off-grid | stationary |
|---|---|---|---|
| human | 0.8589 | **0.0000** | 0.1411 |
| agent | 0.2842 | 0.6859 | 0.0299 |

So the raw intent-vs-action divergence angle is heavily confounded — its quantiles land exactly on
45.0 / 90.0 / 135.0, which is the keyboard, not a finding. **Do not quote the divergence angle.**

The findings below are chosen because quantization cannot manufacture them: a ≤22.5° snap cannot
flip the sign of a radial component or double an exposure fraction.

Worth noting on its own: **the human is stationary on 14.1% of ticks, the agent on 3.0%.** Standing
still is a tactic the agent essentially never uses.

---

## Finding 1 — exposure: the human fights at half the range

Fraction of ticks by distance to the nearest threat:

| nearest threat (u) | human | agent | ratio |
|---|---|---|---|
| 0-130 (inside contact danger) | 0.1143 | 0.0585 | **1.95** |
| 130-200 | 0.1634 | 0.0780 | **2.09** |
| 200-280 | 0.2369 | 0.1254 | **1.89** |
| 280-400 | 0.2703 | 0.2487 | 1.09 |
| 400-600 | 0.1644 | 0.3930 | **0.42** |
| 600+ | 0.0506 | 0.0964 | 0.53 |

Median nearest-threat distance **275 u (human) vs 395 u (agent)**. The agent spends 2.4x more time
in the 400-600 band; the human spends ~2x more time inside 280.

## Finding 2 — position: the agent hugs the edge

Median distance from arena centre: **human 535, agent 810** (p90 785 vs 907). The agent's late-wave
edge-kiting is visible as a standing positional bias, not an occasional manoeuvre.

## Finding 3 — the agent's field wants to FLEE the states the human chooses

Median radial component of the movement command w.r.t. the nearest threat (+1 = straight at it,
−1 = straight away), matched on nearest-threat distance:

| td bin | agent intent, on human states | human action | diff | agent intent, on its OWN states |
|---|---|---|---|---|
| 0-130 | −0.486 | −0.290 | +0.196 | −0.155 |
| 130-200 | −0.650 | +0.029 | +0.679 | −0.113 |
| 200-280 | −0.630 | +0.206 | +0.836 | −0.195 |
| 280-400 | −0.602 | +0.230 | +0.832 | −0.164 |
| 400-600 | −0.423 | +0.228 | +0.652 | −0.123 |

Two things, and the second is the interesting one:

1. **On human-visited states the agent would retreat hard** (−0.42 to −0.65) where the human holds
   or closes (+0.03 to +0.23).
2. **Matching on distance does NOT reconcile the agent's two intents.** Its intent on its own states
   is only −0.11 to −0.20 in the *same* distance bins. So the difference is not "the human is
   closer"; the human-visited states are qualitatively ones the agent's field treats as dangerous
   even at equal range.

**Reading:** the agent has settled into a **long-range, edge-hugging attractor**. It rarely visits
close-central states, so its behaviour there is effectively untested — and when placed in them it
wants to flee rather than fight through.

---

## Why this is the most promising lead we have

It reconciles five previously disconnected observations at once:

- The human took **1.95x MORE** gross damage on this fixture — expected, at half the engagement range.
- The human's clearance fraction is **0.9496 vs 0.9277** (beaten by 1 of 31 agent runs) and it leaves
  far fewer enemies alive at the timer on waves 15-19 — expected, from more DPS applied at range.
- The wave-17 separator is **OFFENSE, not defense** (`nominal_dps` 28.3 vs 35.3) — a kill-rate story.
- The human survives wave 17 where the agent dies 17/21 times — clear the crowd before it clears you.
- The human's HP floor is nonetheless healthier — because the wave *ends*.

The through-line: **the agent buys safety per-tick and loses the wave; the human spends HP and wins
it.** Note this is exactly the failure mode that a gross-damage endpoint would have scored backwards
— which is why `damage_taken` was retired.

## What must NOT be done with this yet

**Do not ship an engagement-distance rebalance.** Repulsion weights, `SAFETY_DISTANCE` and the
late-wave edge-kite bias are a whole-desire-field change, and that class of change is what produced
the **47-point win-rate collapse that ran ~20 versions invisibly**. It gets a preregistered campaign
or it does not happen.

**And that campaign is currently blocked on fixture supply.** Only **7 of 72** wave-17 states
discriminate on terminal survival (`campaign_sizing_v2.md`); the rest sit at 0% or 100% and cannot
move the endpoint at any n. **Building more discriminating fixtures is the prerequisite**, and it is
the cheapest useful thing to do next.

## Honest limits

- **n = 5 human trials on one fixture**, post-practice, 8-way action space.
- **Off-policy.** The agent's intent on human-visited states is a counterfactual on states it would
  never have reached. It is valid as "these two policies differ here"; it is not a prediction of how
  the agent would perform if placed there, because its own dynamics would carry it elsewhere.
- **Direction of causation is not established.** The human may fight close *because* an 8-way
  keyboard cannot kite precisely, rather than by choice. That the coarser action space still wins on
  this fixture is suggestive, not proof that closing distance is the cause.
- Distance-matching is a single-variable control. Crowd geometry (how surrounded the player is) is
  the obvious next covariate and is not controlled here.
