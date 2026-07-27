# Co-rotation eval protocol — PRE-REGISTERED

**Written and committed BEFORE trial 1.** That sequencing is the whole point: finale v2's
campaign 1 produced +0.1875 with a CI excluding zero and it reversed on a fresh sample.
What stopped it shipping was a decision rule fixed before the data existed. Same here.

## The question

Does co-rotating with the boss's projectile ring reduce damage taken on wave 20, *given
that the agent can already see the ring*?

**Both arms have `finale_pivot_projectiles` ON.** Co-rotation is the ONLY difference.
This deliberately does not measure the pivot fix — that is already established
(unexplained damage 86.8%/83.8% -> 0.0%) and folding it in would confound the two.

| arm | flags |
|---|---|
| control | `--finale-pivot-projectiles` |
| treatment | `--finale-pivot-projectiles --finale-co-rotate` |

## Primary metric: DAMAGE TAKEN — chosen before seeing campaign data

Not win rate. The pivot fix alone ran 12/12 victories, so the win rate is pinned near
the ceiling and has almost no room to move; a null there would be uninformative about
the mechanism. Damage taken is continuous and has visible spread (observed 0–57 across
12 pivot-only trials), so it carries far more power at the same trial count.

Win rate is recorded as a SECONDARY metric and is explicitly NOT the decision variable.

## Design

- 8 predator fixtures x 8 trials x 2 arms = **128 trials**, ~2–2.5 h.
- **Paired by fixture**: both arms run the same 8 fixtures, so build variation cannot
  masquerade as an arm effect. This is what campaign 1 of v2 got right and it is
  non-negotiable.
- Unit of analysis is the **FIXTURE** (n=8), not the trial. Trials within a fixture are
  not independent — they share a build. Per-fixture mean damage, then a paired test.
- Same mod build (0.2.46) for both arms. The 12 earlier pivot-only trials ran on 0.2.45
  and are **NOT** reused as the control; they are a reference only.

## Decision rule — FIXED NOW

Let d_f = mean(damage | treatment, fixture f) − mean(damage | control, fixture f).
Negative d_f means co-rotation helped.

**PASS requires BOTH:**
1. Exact Wilcoxon signed-rank over the 8 per-fixture d_f, **p < 0.05**
2. Mean d_f **< 0** (i.e. less damage)

Anything else is **NOT CONFIRMED** and the flag stays default-OFF. No re-analysis with a
different metric, no adding trials and re-testing (that is optional stopping), no
switching to win rate if damage comes back null.

A PASS promotes to **candidate only**. It must then survive a fresh-sample confirmation
before shipping. The invoker is reserved as an untouched control and is NOT spent here.

## Validity gate — checked FIRST, and it can VOID the campaign

A flag's self-report is not evidence it took effect. Before any outcome analysis:

- **Arm recording:** `wp2_finale_loop.py` invalidates any trial whose recorded
  `finale_co_rotate` disagrees with the requested arm. Require 0 invalid trials.
- **Steering signature:** `scripts/wp2_verify_co_rotate.py` must show the treatment arm
  co-rotating **more** than the control. Measured at weight 0.50 on smoke: 74.4% vs
  67.6%, lift +6.8 pp.
- **Ring present:** the treatment arm must show ~0 ticks with no ring in state.

**If the steering signature does not separate, the campaign is VOID** — a flag that did
not take effect must invalidate the experiment, not quietly produce a null.

## Stated in advance: two reasons this may well come back null

1. **The control already co-rotates 67.6% of the time**, far above the 50% chance
   baseline — repulsion from the ring already pushes the agent mostly the right way. The
   intervention adds only ~7 pp of steering, so there is little headroom.
2. **The control arm is already near-perfect on these fixtures** (12/12, 0% unexplained
   damage). If the remaining damage is mostly from the visible burst and enemy contact
   rather than the ring, co-rotation cannot touch it.

Recording these now so that a null is read as informative rather than disappointing, and
so a positive result cannot be narrated as having been obvious.

## Weight was tuned before pre-registration, and only on the STEERING metric

`BOSS_FINALE_CO_ROTATE_WEIGHT` = 0.50. 1.00 was tried and was worse (65.2% co-rotating,
below the control) because at full weight the tangential term replaces the combined
vector and the anti-reversal guard fights it. That selection used the steering
signature, NOT damage or win rate, so it does not contaminate the outcome metric.
`BOSS_FINALE_CO_ROTATE_MIN_OMEGA` = 0.25 rad/s, well below the measured working range of
~1.4–1.55.
