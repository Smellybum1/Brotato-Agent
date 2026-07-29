# PRE-REGISTRATION — `tail_calm_clearance_mult` screen on the confinement endpoint

**Written BEFORE any treatment trial was run.** Mod `0.2.55`, wave 17,
fixture `w16_predator_20260728_112824_7f124906e6bb49cb` (the same fixture as the existing
2 controls and the human trial, so every comparison is matched).

## Why this endpoint and not the previous one

The charging-vs-walking differentiation is **retired**: two controls on this fixture read −0.087 and
+0.021, a within-arm spread of **0.108** that exceeds the effect it must detect
(`tail_gate0_and_endpoint_instability.md` §2). Sizing anything on it is impossible.

**Primary endpoint: occupancy concentration** — the number of 128 u cells (of 192) containing 50% of
wave-17 player-position captures. Higher = roams more = more human-like.

Observed so far: **human 33**, agent controls **10** and **12**.

## Design

- **Arms:** control (`tail_calm_clearance_mult = 1.0`, exactly inert) and treatment (**0.0**).
- **n:** 4 fresh control + 4 treatment. The 2 existing controls are reported but the spread is
  estimated from the **6** controls pooled.
- **Dose rationale — MAX, deliberately.** At 0.0 a non-charging enemy is fully discounted against
  the 45 u contact floor (credit = 45 u). This is a **Gate 0 screen**: if the maximum dose cannot
  move the endpoint, the knob is dead and no titration is warranted. If it moves it, titrate later.
- **Blinding:** none possible, so the decision rule below is fixed in advance instead.

## Predeclared decision rule

Read the **effect size only. No p-value. This is a SCREEN — it cannot ship anything.**

Let `sd_ctrl` = standard deviation of the 6 control cell-counts.

- **GO** to a confirm campaign iff the treatment mean **exceeds the control mean by ≥ 2 × sd_ctrl**
  *and* moves toward the human value of 33, **and** the safety guards below are not tripped.
- **NO-GO** otherwise, including any effect in the wrong direction.

## Safety guards — a NO-GO regardless of the primary endpoint

This dose **relaxes a collision-avoidance floor**, so a confinement improvement bought with deaths is
not a win:

1. treatment survival (wave-17 trials reaching wave 18) **below** control survival, **or**
2. treatment median gross damage **more than 1.5x** control median.

Gross damage is a **reported component only** — it is a gross counter that never subtracts healing
(`brotato-measurement-discipline`, 12th) — but a 1.5x blowout on a floor-relaxing treatment is a
mechanism signal, not a healing artifact.

## Also recorded (secondary, not decision-bearing)
- cells visited, corner occupancy vs uniform baseline, radius of gyration
- pooled approach velocity to the nearest pursuer (~5x separation, the backup endpoint)
- **NOT** the charging/walking differentiation — retired above.
- **NOT** any body-clearance diagnostic: `tail_calm_clearance_mult != 1.0` deliberately inflates what
  `_predictive_body_path_clearance` returns, so those fields change scale between arms and are not
  comparable. This is stated in the knob's own source comment.

## Known limits, stated up front
One fixture, n=4 per arm. This screens a mechanism; it does not generalise. Per
`campaign_sizing_v2.md` the generalisation unit is **distinct fixtures**, so any GO leads to a
multi-fixture confirm with a fresh sample, never to a top-up of this one.
