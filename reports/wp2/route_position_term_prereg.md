# §32 — Gate 0 for a POSITIONAL PREFERENCE term in the body-safety lane score

**Written 2026-08-03, BEFORE the data exists.** The 8-run collection campaign was launched minutes
earlier and no route/in-range number from it has been seen. Authored blind, deliberately.

## What is established (do not re-litigate here)

`_finale_body_safety` (`teacher/potential_field.gd`) is the last movement arbiter and runs on every
combat wave. Its lane score is, in full:

```
score = projectile_clearance − enemy_penalty
      + 14.0 * dot(cand, baseline)      # ESCAPE_ALIGN_BONUS
      + 85.0 * dot(cand, _prev_move)    # BOSS_FINALE_ESCAPE_CONTINUITY
```

**Body clearance appears nowhere in it** — it is read into a local and used only in a `continue`, i.e.
an ADMISSION GATE, never a preference. Verified from source and pinned by
`tests/unit/test_route_scores_source.py::test_body_clearance_is_a_gate_never_a_preference`.

From the `0.2.76` smoke (**n=1 run, 177 ranked captures — a SMOKE, not a measurement**): 58.2% of
candidates are admitted, median **15** admitted lanes, `enemy_slack` drops only 0.8%, and the measured
spread of `(proj − pen)` across admitted lanes is **0.00**. Removing the continuity term flips only
9.1% of ranked decisions, so **"weaken continuity" already failed Gate 0** — `baseline` and
`_prev_move` mostly agree, and dropping one just hands the choice to the other.

⇒ The hypothesis under test is NOT "continuity is too strong". It is: **nothing in the score prefers a
better POSITION, and there are ~15 free lanes in which to express such a preference.**

## The proposed term

```
score += w * inrange_after(cand, h)
```

`inrange_after` = fraction of LIVING enemies within weapon range after advancing the player along
`cand` at `player.speed` for horizon `h`, **and advancing each enemy by its own recorded `(vx, vy)`
for the same `h`.** Fixed in advance, not tunable at analysis time:

- **`h` = 0.60 s = `BotConfig.ESCAPE_HORIZON`** — the horizon this function's own clearance sampling
  already uses. Not a free parameter picked to make a result.
- **"in range" = at least one weapon's `max_range` covers the enemy** (max over weapons). This matches
  the validated in-range endpoint definition exactly (`in_range_fraction_mediator.md`), so the term
  optimises the quantity the deficit was measured in.
- **living = `hp > 0`.**
- ⭐ Enemies MOVE in this counterfactual. The `in_range_headroom` analysis was explicitly an upper
  bound because it froze them; enemy `vx/vy` is in the capture, so that caveat is removed here.

**Why the safety argument holds by construction:** the term only reorders lanes that have ALREADY
passed `body_floor` and `projectile_floor`. It cannot select a lane the current gates reject, so it
cannot walk the agent into a pack that today's policy would refuse. (Same structural bound that made
`BOSS_FINALE_BODY_CRITICAL_CLEARANCE` unscalable in §31.)

## Analysis set — denominators printed BEFORE any result

Ranked captures (`route.exit == "ranked"`) with **≥2 admitted lanes** and **≥1 living enemy**.
Captures with zero living enemies are excluded: the fraction is 0/0 and undefined. That count is
reported, never silently dropped.

**Sample: the ≥6 completed D5 ranger runs at `0.2.76`, era 179/48, `route_scores_enabled` true, one
build.** ⛔ The `0.2.76` smoke run `run_1785754086_12860` is **EXCLUDED — it was force-killed
mid-run and is truncated.** That reason is outcome-independent and is stated here, before the data.

## GATE 0a — WEIGHT-FREE HEADROOM (necessary; cannot be tuned into passing)

```
headroom = max over ADMITTED lanes of inrange_after  −  inrange_after(the lane actually chosen)
```

**BARS: median headroom ≥ 0.05 AND the share of captures with headroom > 0.01 must be ≥ 50%.**

If the lane the agent already picks is at or near the best in-range available *among lanes it was
allowed to take*, then **no weight on any positional term can help** and the lever is dead without a
single further run. This is the cheapest possible Gate 0 and it takes no weight parameter, so there is
no knob to turn until it passes.

## GATE 0b — FLIP RATE AND REALISED GAIN

For **w ∈ {10, 25, 50, 85, 150, 300}** (85 = the continuity weight, so the ladder brackets a term of
comparable authority; 300 is the "even a dominant term" end):

- `flip_rate` = share of analysis-set captures where `argmax(score + w·inrange)` ≠ `argmax(score)`
- `realised_gain` = **median (in-range of the new pick − in-range of the old pick), over FLIPPED
  captures only**

**BARS: some w ≤ 300 must give flip_rate ≥ 0.20 AND realised_gain ≥ 0.05.**

⛔ **Flipping a decision is not improving it.** The damage-tilt valuation lever flipped boards and
still failed because several flips swapped a strong item for a marginal one. `realised_gain` exists
precisely to catch that, and it is why flip_rate alone is not sufficient.

⛔ **MONOTONICITY, declared now (the §31 trap):** `realised_gain` must be **non-decreasing in w** up to
its maximum across the ladder. A non-monotone gain curve is **NOISE, not partial success** — that is
verbatim what killed `body_clearance_scale`, where the negative control scored highest.

## Reported, not barred

- **Reach:** ranked captures are a minority of ticks (`baseline_kept` was 56.8% in the smoke). Report
  `flip_rate × ranked_share` as the share of ALL captures the term could move. A term that passes both
  gates but moves <2% of all captures is reported as such rather than advanced.
- **Safety:** median body clearance of the flipped-to lane vs the original. Bounded below by the gate
  by construction, but a drop >20% is flagged and would require the §31 low-HP-exposure veto in any
  subsequent screen.
- Distribution of admitted-lane counts and the exit mix, per run, so heterogeneity is visible.

## What passing means, and what it does not

Passing Gate 0 licenses **implementing and screening** the term on the in-range mediator. It does
**NOT** license a survival claim. The in-range fraction is a MEDIATOR: a treatment can raise it by
walking into the pack and dying faster. Any screen that passes still requires the §31 safety veto
(reject any dose that buys targets with low-HP exposure), and only a terminal-win campaign can speak
to north star 1.

Failing either gate closes the "positional preference term" branch at a cost of one collection
campaign and **zero implementation**, which is what Gate 0 is for.
