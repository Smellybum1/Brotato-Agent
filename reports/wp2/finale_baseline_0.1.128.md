# Wave-20 finale baseline — policy 0.1.128 / mod 0.2.38

**Status: COMPLETE 2026-07-26.** This is the fixture-measured baseline for the
CURRENT finale stack, required by `finale_clean_slate_design.md` step 3 before any
replacement controller may be claimed better. Tools: `scripts/wp2_finale_loop.py`
(commit `835735c`), `scripts/wp2_finale_metrics.py` (commit `639a74d`).
Raw data `.tmp/finale_loop/trials.jsonl`, metrics `.tmp/finale_loop/metrics.jsonl`.

## Headline

**28 victories / 40 trials = 0.700, 95% Wilson CI [0.546, 0.819].**
40/40 trials valid — every one confirmed `waves == [20]` with exactly one boss
script path, `predator`.

| fixture | n | wins | rate | 95% CI | median damage |
|---|---|---|---|---|---|
| `756e6461` (pre-shop, gold 619, 5 weapons) | 20 | 14 | 0.700 | [0.481, 0.855] | 54 |
| `4ab34bff` (post-shop, gold 53, 6 weapons) | 20 | 14 | 0.700 | [0.481, 0.855] | 68 |
| **combined** | **40** | **28** | **0.700** | **[0.546, 0.819]** | 52.5 |

Raw chronological series (V=victory, D=defeat), so the aggregate is auditable:

```
V D V V V V V V D V V V V D V D D V V V D V V V D D V D V D V V D V D V V V V V
```

## THE SCOPE LIMIT — read before using this number

**This is ONE BUILD's finale survival rate, not the policy's.** The two fixtures
were captured **6 seconds apart** from the same run at identical HP (56) and level
(21), differing only in gold (619 -> 53) and weapons (5 -> 6): they are one build
either side of its wave-19 shop, not two independent builds. That the two arms land
on *exactly* 14/20 each is consistent with them being the same build.

So this baseline is valid as the **paired reference** for a like-for-like comparison
— run a replacement controller on these same fixtures and compare — and is NOT a
population estimate of finale survival. A controller that beats it has been shown
better on one build. `finale_clean_slate_design.md` names overfitting to a single
fixture as the main risk, with history on this project.

## Behavioural baseline (40 trials, medians)

| metric | median | min | max |
|---|---|---|---|
| captures at w20 | 605.5 | 262 | 881 |
| duration / boss TTK (s) | 30.2 | 13.1 | 43.9 |
| damage taken | 52.5 | 0 | 85 |
| hit events | 3 | 0 | 5 |
| boss hp ratio at last sight | 0.0027 | 3.4e-05 | 0.647 |
| **reversal rate** | **0.111** | 0.064 | 0.166 |
| **straightness** | **0.059** | 0.028 | 0.122 |
| stationary fraction | **0.000** (0 / 602 captures) | 0 | 0 |
| action-zero fraction | 0.000 | 0 | 0 |

## HARNESS VALIDITY — checked, and it passes

Fixture trials could in principle behave differently from a naturally-reached wave
20 (restore might not reproduce runtime state), which would invalidate the proxy for
everything downstream. Tested against the fixtures' **own source run**
`run_1785036448_61774` — same build, natural arrival instead of restored:

| | reversal rate | straightness |
|---|---|---|
| source run, natural w20 | 0.1282 | 0.0754 |
| fixture trials (n=40) | 0.111 median, 0.064-0.166 | 0.059 median, 0.028-0.122 |

The source run sits inside the trial distribution on both. An earlier apparent gap
(natural runs at 0.23-0.34 vs trials at ~0.11) was **build variation between natural
runs**, not a harness artifact — the four natural 0.1.128 runs that reached wave 20
themselves span reversal 0.109-0.336:

| run | result | n_w20 | reversal | straightness | damage |
|---|---|---|---|---|---|
| `run_1785028909_68538` | victory | 657 | 0.2317 | 0.0051 | 23 |
| `run_1785034096_90520` | victory | 1800 | 0.3363 | 0.0158 | 116 |
| `run_1785035304_56612` | defeat | 925 | 0.1093 | 0.0346 | 138 |
| `run_1785036448_61774` | defeat | 547 | 0.1282 | 0.0754 | 68 |

Caveat: the same-build comparison rests on ONE source run.

## THE PREMISE OF THE CLEAN-SLATE DESIGN IS NOT SUPPORTED

`finale_clean_slate_design.md` argues the finale's ~22 constants exist to paper over
**vector-cancellation freezing** ("two symmetric projectiles produce opposing forces
that cancel to zero, and the agent sits still"), with `BOSS_FINALE_RECOMPUTE_DIVISOR`
as dead time bought to damp the resulting oscillation. Two measurements contradict
the freezing half outright and weaken the wave-20 attribution:

**1. The agent never freezes.** `stationary_frac` is **0.000 over 40 trials**
(0 of ~602 velocity-eligible captures per trial), and `action_zero_frac` is 0.000 —
the commanded vector is never zero. Whatever the finale's failure mode is, it is not
standing still. It oscillates.

**2. Oscillation is not wave-20-specific.** Per-wave reversal rate over two full
runs (raw series):

| wave | 1-9 | 10 | 13 | 14-15 | 16 | 17 | 18 | 19 | **20** |
|---|---|---|---|---|---|---|---|---|---|
| `..._90520` | 0.000-0.005 | 0.022 | 0.024 | 0.073/0.075 | 0.018 | 0.269 | 0.306 | 0.380 | **0.336** |
| `..._68538` | 0.002-0.014 | 0.105 | 0.027 | 0.130/0.110 | 0.004 | 0.102 | 0.252 | 0.258 | **0.232** |

Waves 17-19 reverse **as much or more** than wave 20 — and they run at 60 Hz while
wave 20 runs at 20 Hz. Straightness is ~0.03 at every wave, so the path is ~30x net
displacement throughout; that is not a finale pathology either.

**Caveat that stops this being decisive:** at waves 1-19 the teacher recomputes at
60 Hz but captures land at 20 Hz, so we observe every third decision; at wave 20 the
recompute IS 20 Hz, so we observe every decision. Reversals can alias at waves 1-19.
The comparison is not apples-to-apples in exactly the direction that would matter.

**Implication for the 60 Hz work:** the operator directive scoped oscillation to the
boss wave. The data says the phenomenon begins around wave 17. A heading-selection
controller confined to wave 20 would leave waves 17-19 — which carry 4 of 11 current
defeats and the only wave where current damage matches the strong era — untouched.

## Telemetry fields that are structurally uninformative (add to the running list)

- **`teacher.action_fresh` is 1.000 on EVERY capture, by construction.** The capture
  divisor (`_WP2_CAPTURE_DIVISOR := 3`) and the finale recompute divisor
  (`BOSS_FINALE_RECOMPUTE_DIVISOR := 3`) are both 3, so they are phase-aligned. It
  **cannot** detect the 20 Hz throttle and is not evidence of freshness.
- **`player.measured_vx/vy` is displacement/dt** and blows up at start-up dt
  (measured 11124.9 at `control_dt_ms=2` against a real `speed` of 445). Velocity
  metrics must exclude sub-10 ms captures; `wp2_finale_metrics` does, and reports
  `n_velocity_captures` as the denominator.
- **`wave_time.elapsed_sec` RESETS on the final captures of a WON wave** (seq 438 ->
  21.870, seq 439 -> 0.034, both still `wave == 20`). Last-minus-first gave 0.076 s
  for a 21.9 s wave, and only on victories — a death has no reset — so a naive
  duration metric mixes two different quantities across arms.

## What this baseline does and does not license

- **Licensed:** comparing a replacement finale controller on these same two fixtures
  against 0.700 [0.546, 0.819]. At ~45 s/trial this is cheap to extend.
- **Not licensed:** any claim about finale survival across builds, or any claim that
  a controller improves the policy's win rate. That needs the fixture library
  (design step 3) and then full-run confirmation through `docs/RELEASE_GATE.md`.
- **Power note:** at n=40 per arm the CI half-width is ~14 pp. Detecting the kind of
  lift the finale line is chasing (0.70 -> 0.90) is feasible; detecting 5 pp is not.
