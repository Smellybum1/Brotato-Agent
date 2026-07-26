# Finale v2 outcome evaluation — VERDICT (146/146 trials complete)

Date: 2026-07-27. Binding protocol: `reports/wp2/finale_v2_eval_protocol.md`
(predeclared before trial 1). Build: policy `0.1.128` / mod `0.2.39`, commit
`4930e44` — **the same build in both arms**, arm selected only by the `finale_v2`
flag. Raw data: `.tmp/finale_v2_eval/predator.jsonl`,
`.tmp/finale_v2_eval/invoker.jsonl`. Machine report:
`.tmp/finale_v2_eval/verdict.json`.

## VERDICT: PROMISING BUT NOT ESTABLISHED — the flag stays default-OFF

v2 moved the predator win rate in the predicted direction, on the predeclared
primary, and it survived the internal control that was written to kill it. That
is real and it is worth following. It is **not** a demonstration.

The only view of the primary that excludes zero is the percentile bootstrap over
**8 units** — the least reliable estimator available at that n — and it stops
excluding zero the moment the 2 invalid v2 trials are charged as losses. **No
test clears p<0.05**: exact Wilcoxon p=0.125, sign test p=0.375, pooled Fisher
p=0.102.

Per `docs/RELEASE_GATE.md`, **inconclusive means DO NOT SHIP**. That rule is what
makes a low-powered gate safe rather than dangerous, and its cost here is
shipping velocity, not risk: `finale_v2` remains default-FALSE and flag-off
behaviour is byte-identical to v1.

The next step was predeclared before this verdict was written: the fresh-sample
confirmation in `reports/wp2/finale_v2_confirmation_protocol.md`.

## Campaign integrity

**146/146 trials, 0 failed passes.** Both arms on one build; arms alternated pass
by pass as the protocol required.

| arm | valid | invalid |
|---|---|---|
| predator v2 | 53/55 | 2 |
| predator v1 | 55/55 | 0 |
| invoker v2 | 18/18 | 0 |
| invoker v1 | 18/18 | 0 |

The 2 invalid trials are `boss_path_count:0` (x1) and `telemetry_stale_45.2s`
(x1). **Both fell in the v2 arm and both on iteration builds** — 2/55 vs 0/55,
Fisher p~0.50. Not significant, but the asymmetry is recorded rather than waved
off, and it is carried into the worst-case sensitivity below because it lands
entirely on the arm being promoted.

### Load — settled by measurement, not hedged

`control_dt_ms` (excluding sub-10 ms start-up captures), in **all four** boss x
arm cells: median **51**, p95 52-53, p99 **58** ms, against the absolute **50 ms**
standard. Real-time 60 Hz held throughout both arms; there is no load confound in
either direction. One max of 376 ms in predator/v2 against a p99 of 58 is a rare
spike, not a material contamination.

## PRIMARY — 8 iteration predator builds, paired by build

Per-build raw series, as the protocol requires (V = victory, L = loss):

| build | v2 series | v2 | v1 series | v1 | delta |
|---|---|---|---|---|---|
| `4ab34bff` | VVVV | 4/4 | VVVVV | 5/5 | 0 |
| `fc24b6eb` | VVVVV | 5/5 | VLLLV | 2/5 | **+0.6** |
| `7149d1b7` | VLVLV | 3/5 | LLVLL | 1/5 | **+0.4** |
| `6c32fe3d` | LVLVL | 2/5 | LLLVL | 1/5 | +0.2 |
| `cab349ba` | VVLL | 2/4 | VVVLL | 3/5 | -0.1 |
| `a00d393a` | VLVVL | 3/5 | LLVLL | 1/5 | **+0.4** |
| `b02ffbef` | VVVVV | 5/5 | VVVVV | 5/5 | 0 |
| `56e65a95` | LVVVV | 4/5 | VLVVV | 4/5 | 0 |

**Mean paired delta +0.1875**, 95% percentile bootstrap over builds
**[0.0375, 0.35]** (10,000 resamples, seed 20260727).

Pooled 2x2, **secondary — it ignores build clustering and is not the primary**:
v2 **28/38 = 0.7368** vs v1 **22/40 = 0.5500**, difference +0.1868, **Fisher
exact two-sided p = 0.1024**, Newcombe CI [-0.0254, 0.3763].

### Robustness

| check | result |
|---|---|
| exact Wilcoxon signed-rank, 8 pairs (5 non-tied) | W-=1.0, W+=14.0, **two-sided p = 0.1250** |
| sign test | 4/5 non-tied favour v2, **two-sided p = 0.3750** |
| leave-one-build-out means | 0.2143, 0.1286, 0.1571, 0.1857, 0.2286, 0.1571, 0.2143, 0.2143 |
| **worst case: both invalid v2 trials charged as LOSSES** | deltas [-0.2, +0.6, +0.4, +0.2, -0.2, +0.4, 0, 0], mean **+0.15**, bootstrap CI **[-0.05, 0.35]** |

The leave-one-out spread (0.129 to 0.229) shows the effect is **not carried by a
single build** — no build's removal collapses it. That is the strongest thing the
paired analysis says.

The worst case is the thing that decides the verdict. Charging the 2 invalid v2
trials as losses is a defensible handling, not a hostile one — they occurred in
the promoted arm and nowhere else — and under it the interval includes zero. A
headline that depends on which of two defensible handlings is chosen is not an
established result.

## SECONDARY 1 — 3 held-out predator builds

| build | v2 series | v2 | v1 series | v1 | delta |
|---|---|---|---|---|---|
| `d4cdd651` | VVVVV | 5/5 | LVLVV | 3/5 | +0.4 |
| `835dcfbe` | LLLLL | 0/5 | LLLLL | 0/5 | 0 |
| `e76f1773` | LVVLL | 2/5 | VVVLV | 4/5 | -0.4 |

**Mean paired delta 0.0**, bootstrap CI **[-0.4, 0.4]**.

The predeclared bar was "v2 must not regress". The mean does not regress. But
**n=3 builds is nearly uninformative** — the CI spans the entire plausible range
and the three deltas are +0.4, 0, -0.4. This neither supports nor undermines the
primary and should not be quoted as if it did either.

`835dcfbe` floored at 0/5 in **both** arms. That is the 9-HP wave-19 build, and
the protocol anticipated exactly this ("may floor near 0% in both arms... it stays
in: dropping a build after seeing its rate is exactly the selection this protocol
exists to prevent"). It stayed in.

## SECONDARY 2 — INTERNAL CONTROL, 6 invoker builds

Per-build deltas: **-0.3333, -0.3333, -1.0, -0.3333, +0.6667, +0.3333**.
**Mean paired delta -0.1667**, bootstrap CI **[-0.5556, 0.2778]**.
**`control_ratio` = -0.8889.**

The predeclared refutation condition was: *if v2 improves invoker by a comparable
margin, the mechanism story is wrong and the predator result must be distrusted —
even if it looks good.* That rule bound regardless of significance, and it was
written before any trial ran.

**v2 did not improve invoker. It moved slightly the other way. The mechanism
story survived its refutation test.** This is the strongest single element of the
whole result: the effect is **boss-specific in the predicted direction** —
predator projectiles are 0% stationary, invoker projectiles 96.3% stationary, and
heading selection against moving projectiles is the entire premise of v2. A
generic "v2 just plays better" explanation predicts improvement on both bosses and
is not what the data show.

Two honest limits on that:

- The invoker CI **[-0.5556, 0.2778] is wide and straddles zero**, so "no
  improvement on invoker" is **weakly** established. The control passed; it did
  not pass decisively.
- A **small negative effect on invoker is not excluded**, and it would matter if
  v2 were ever enabled unconditionally on wave 20 rather than being routed by boss
  identity. Wave 20 draws predator or invoker, so this is not hypothetical.

## SECONDARY 3 — freeze detectors

Median (p10-p90 as noted):

| metric | predator/v2 (n=53) | predator/v1 (n=55) |
|---|---|---|
| `stationary_frac` | 0 (p90 0.001938) | 0 (p90 0) |
| `straightness` | 0.03734 | 0.03258 |
| `damage_taken` | 64 | 64 |
| `boss_ttk_sec` | 42.83 | 39.14 |
| `boss_hp_ratio_last` | 0.008444 | 0.03986 |

**v2 is not winning by standing still.** `stationary_frac` is 0 in both arms
(v2's p90 of 0.0019 is noise), which is the clean freeze check and it passes.
Damage taken is identical at the median.

**Caveat, stated explicitly because the number invites the wrong reading:**
`boss_hp_ratio_last` is measured at **trial END**, so more victories mechanically
drive it toward zero. It is **confounded with the outcome** and is **not
independent evidence** that v2 kills the boss rather than turtles. The
lower v2 value is largely a restatement of the higher v2 win rate. `boss_ttk_sec`
is descriptive only, and v2's is slightly longer, not shorter.

## What is established, and what is not

**Established:**

- The direction is **consistent**: 4 of 5 non-tied builds favour v2, the single
  adverse build is only -0.1, and leave-one-out is stable.
- The **boss-specific internal control passed** on its predeclared terms.
- v2 is **not freezing or turtling** — `stationary_frac` 0, damage taken
  unchanged.
- **No load confound**; 60 Hz held in all four cells.

**Not established:**

- That the effect is real at any conventional evidence bar. Every hypothesis test
  run on the primary returns p > 0.10.
- Any specific magnitude. The protocol declared in advance that this experiment
  resolves ~0.70 -> 0.90 and not a 5 pp shift, and no small effect is claimed here
  in either direction.
- That the holdout builds say anything at all (n=3).

Per the protocol's own refutation list, v2 did not fail outright on any clause:
it beat v1 on the iteration builds, did not regress on the holdouts, the control
did not move with it, and the freeze detectors are clean. It simply did not beat
v1 by enough to be sure.

## What happens next

1. **`finale_v2` stays default-FALSE.** Nothing ships on this result. Flag-off
   behaviour is unchanged.
2. **Run the predeclared confirmation campaign**:
   `reports/wp2/finale_v2_confirmation_protocol.md` — 8 iteration predator builds,
   **8 trials per build per arm** (64/arm, 128 total), same frozen fixture list,
   arms alternating pass by pass. Decision rule, fixed in advance: **v2 is
   CONFIRMED iff pooled Fisher exact two-sided p < 0.05 AND mean paired delta > 0,
   on that sample ALONE.** Anything else is NOT CONFIRMED and the flag stays off.
3. **Why a fresh sample rather than extending this one.** Deciding to collect more
   trials *after* seeing a favourable result is **optional stopping**, and any test
   run on the combined data would have an inflated type-I error rate. The first
   campaign's numbers are the **hypothesis**; they are not pooled into the
   confirmation's primary test. This project has already seen the alternative work:
   the wave-20 finale hazard became a finding precisely because it was tested on a
   fresh pre-registered sample rather than re-analysed.
4. **The 3 holdout builds are not re-run** by the confirmation. They stay reserved
   for a final check if and only if v2 is confirmed.
5. **The invoker control is not re-run.** It was pre-registered, it passed, and
   re-running it would cost 36 trials to answer nothing new. The open question is
   the predator magnitude alone.
6. The confirmation campaign **reports the same worst-case sensitivity** — every
   invalid v2 trial charged as a loss. If a headline conclusion depends on how
   invalid trials are handled, it will again be reported as depending on it.
