# §42 — Clearance-guarded route conversion live screen verdict

**Verdict: INERT OR TOO SMALL. No survival campaign is licensed.**

The exact §41 policy was delivered, changed the final movement command in every treatment run, and
preserved its live body-clearance guard. It did **not** produce the preregistered realised engagement
shift. This is a dynamics-limited null, not an arm failure and not a safety rejection.

## Design and controls — passed before outcomes

Pre-registration: `clearance_guarded_conversion_screen_prereg.md`, committed as `869ee4c` before
deployment or data. Implementation: `71c0694`. Collector/analyzer: `8b652db`. Fixed order
`C,T,T,C,T,C,C,T`; Ranger, nominal Danger 5, pistol opener; 4 valid trials per arm.

- **8/8 unique terminal summaries**, exactly 4/arm; no top-ups or optional stopping.
- Character, requested/observed danger, pistol opener, `danger_ok`, policy, build
  `0.2.80-wp2-capture`, and exact era `179/48/2018397571/1530875081`: **8/8**.
- Errors, hangs, illegal actions and summary non-finite fixes: **0/8**, each over the printed
  denominator.
- Installed mod/source content: **21/21 files byte-identical**; profile port inert.
- `conversion_enabled` present on every wave-1–11 route block: control **33,341/33,341 false**;
  treatment **26,346/26,346 true**.
- Control conversions: **0/12,698 ranked opportunities**. This zero has both its denominator and the
  treatment positive control.
- Treatment conversions: **1,715/9,026 = 19.00%**, with at least one in **4/4 runs**.
- Guard engaged: **22,965/104,067 = 22.07%** admitted candidates vetoed; ranked non-conversions also
  occurred.
- Applied projected gain: median **0.1538**, with **0/1,715** deadband violations.
- Applied body clearance: **0/1,715** guard violations after the predeclared telemetry tolerance.

The build loaded on every fresh sentinel and the enabled branch ran. A self-report alone would not
have been enough; the 1,715 final-command changes are the behavioural delivery proof.

## Primary mediator — failed decisively

Per-trial realised in-range fraction over wave-1–11 captures with a living threat and usable weapon
range:

| arm | raw per-trial values | mean |
|---|---|---:|
| control | 0.339052, 0.317528, 0.405246, 0.395874 | **0.364425** |
| treatment | 0.532697, 0.293602, 0.388927, 0.281369 | **0.374149** |

Treatment minus control = **+0.009724**, failing the fixed **+0.05** bar. Exact two-sided permutation
was **66/70 = 0.942857**, failing the fixed **p ≤ 0.05** bar. An independent enumeration reproduced
the same 66/70 result and arm means.

The positive movement actions therefore do not accumulate into materially different realised
engagement geometry. One treatment trial was high, but the other three overlap or trail control;
the preregistered trial-level analysis correctly prevents that one run from becoming the result.

## Safety veto — clean, but cannot rescue the primary

| endpoint | control mean | treatment mean | T − C | rule |
|---|---:|---:|---:|---|
| captures below 70% HP | 0.035664 | 0.017290 | **−0.018373** | ≤ 0, pass |
| HP-deficit AUC/capture | 0.023762 | 0.011733 | **−0.012029** | ≤ 0, pass |

The policy did not buy its small realised gain by spending low-HP exposure. This excludes the
predeclared `UNSAFE` verdict, but safety cleanliness cannot rescue a failed mediator.

## Context only

All eight runs were defeats. Terminal waves were control `[10, 12, 11, 7]` and treatment
`[11, 6, 10, 6]`. At n=4/arm these are context only and support no survival comparison.

## What the null closes, and why

The exact PACK-80 / 0.80-retention / 0.05-deadband / 0.60-second projected-in-range controller is
closed as a D5 survival candidate. Its offline one-step counterfactual was correct on the decision it
priced and its live implementation obeyed that policy; the failure is that those local gains are
mostly cancelled by subsequent dynamics. More trials cannot fix a +0.0097 effect against the
predeclared +0.05 mediator bar, and a survival campaign is not justified.

Do **not** respond by lowering the deadband, retention ratio, PACK floor, or primary bar on these
runs. Those are post-result dose changes on the same mechanism. A viable fork must be mechanism-
distinct: it must price persistence over a trajectory or a direct combat/clearance consequence,
rather than another one-step in-range maximum. Such a fork needs its own offline falsifier or a new
instrument before machine time.

Machine-readable result: `clearance_guarded_conversion_screen_result.json`.
