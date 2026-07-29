# Audit of the human-handover wave-17 claim

**Date:** 2026-07-29. Triggered by noticing the archive holds **more human fixture trials than the
5 on record**. No machine time.

## Headline: the recorded claim is VERIFIED and reproduces exactly

Matched on the full entry fingerprint (max_hp, speed, armor, materials, dodge, regen, and all six
weapons' damage/cooldown/max_range) **and** on the enemy-health dose:

> **agent 4/21 = 0.190 vs human 5/5 = 1.000, Fisher exact one-sided p = 0.00192**

against the recorded p = 0.0019. Nothing about the headline needs changing.

---

## The trap I nearly published — pooling across an invisible treatment

Matching only on the **player** entry fingerprint returns **67** agent trials on that fixture with
**38 survivals (0.567)**, which looks like it demolishes the 4/21 figure. It does not. Those 67
trials span the **`enemy_scaling` dose ladder**, and that dial changes enemy health **without
touching any player stat**, so it is invisible to an entry-build fingerprint.

Stratifying by baseline enemy health (`buffer` `max_hp`, the readback the lever is verified by):

| buffer max_hp | agent survived / n | human |
|---|---|---|
| 34 | 13/13 | — |
| 51 | 9/9 | — |
| 58 | 4/8 | — |
| 61 | 3/8 | — |
| 65 | 5/8 | — |
| **68 (undiluted)** | **4/21** | **5/5** |
| pooled | 38/67 | |

**The human trials are all at buffer 68**, the undiluted setting. The pooled 0.567 is a mixture of
six treatment arms; the matched figure is 0.190. A **3.0x error**, produced by a fingerprint that
was complete on every field it covered and silently blind to the one that mattered.

The ladder is also a clean monotone dose-response in its own right (13/13 → 9/9 → 4/8 → 3/8 → 5/8
→ 4/21), corroborating the `enemy_scaling` lever.

**Rule to carry forward: an entry-build fingerprint does NOT identify a fixture trial's ARM.**
Any pooling of fixture trials must condition on the treatment readback, not on the entry state.
This is the same shape as the two same-named `damage`/`cooldown` fields that were 3.40x apart —
matching on the fields you can see is not matching on the source.

---

## What IS new and belongs in the record

The human ran **three different fixtures**, not one. Nine handover trials exist (plus one 12-capture
aborted launch), all resuming at wave 17:

| fixture (max_hp/speed/armor/mats) | human | agent at the same dose | note |
|---|---|---|---|
| **A** 48/468/1/79 | **0/1 — DIED** | **no agent trials exist** | the human's **first ever attempt** |
| **B** 39/526/3/4 | 2/2 | 11/11 | fixture is non-discriminating — the agent never fails it |
| **C** 53/544/4/36 | 5/5 | 4/21 | the headline comparison |

Chronological order was **A, B, B, C, C(abort), C, C, C, C**.

Three consequences, none of which overturn the headline but all of which bound it:

1. **The human's first attempt died.** It was on fixture A, for which no agent control exists, so it
   cannot be scored against anything — but "the human never failed" is not a true statement about
   the session, and should not be said.
2. **The five counted trials were preceded by three others.** The practice/learning confound already
   flagged as "sequential, learning effects unrecorded" can now be quantified: **3 prior trials**
   before the first counted one. The 5/5 is a *post-practice* figure.
3. **Fixture B is uninformative** and should not be cited as support: the agent goes 11/11 on it.

## Status of the claim after this audit

**Unchanged:** on the one fixture where a matched comparison exists at the undiluted dose, the human
rescued a build the agent loses 17 of 21 times, p = 0.0019.

**Still exploratory**, for the reason already on record: the predeclared endpoint was terminal win
and it **failed at 1/5**. Wave-17 survival was the exploratory endpoint.

**Newly bounded:** post-practice, n=5, on 1 of 3 fixtures attempted, with the human's only naive
attempt being a death on a fixture with no control arm.
