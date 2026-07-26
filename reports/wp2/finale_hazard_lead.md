# Finale hazard: the localisation, and the leading candidate mechanism

**Status 2026-07-26: HYPOTHESIS, not a finding.** Gated on the running 36-run
champion bank. Do not act on it before that lands.

## The localisation

Conditional hazard — of teacher runs that *reached* wave w, the fraction that died
there. Conditioning matters: raw defeat counts confound with how many runs got that
far.

| wave | STRONG v60-72 | CURRENT v125 | Fisher p |
|---|---|---|---|
| 16 | 6/108 = 5.6% | 1/19 = 5.3% | 1.00 |
| 17 | 8/102 = 7.8% | 4/18 = 22.2% | 0.081 |
| 19 | 8/94 = 8.5% | 0/14 = 0.0% | 0.59 |
| **20** | **4/86 = 4.7%** | **4/14 = 28.6%** | **0.0126** |

Wave 20 is the only wave that separates — a **6x increase in conditional finale
failure**. Reaching the finale at all is comparable (76.1% vs 66.7%), so runs are not
arriving in worse shape; they arrive and then die. Wave 19 actually *improved*.

**THE CORRECTION THAT MATTERS: this does not survive multiple-comparison correction.**
Thirteen wave comparisons were run. Bonferroni gives alpha = 0.0038 and
Benjamini-Hochberg gives 0.0038 at rank 1; **p = 0.0126 clears neither**. It rests on
**4 deaths in 14 runs**. This is the strongest signal in the archive and a
well-localised hypothesis. It is not an established finding, and the champion bank
(~24 additional finale observations) is what settles it.

## Leading candidate mechanism: the finale recompute divisor

`runtime/agent_controller.gd:267-273`, `teacher/config.gd:116,131`:

```gdscript
var recompute_move := true
if wave >= _CONFIG_SCRIPT.BOSS_FINALE_WAVE:          # 20
    _finale_move_tick += 1
    recompute_move = (_finale_move_tick % _CONFIG_SCRIPT.BOSS_FINALE_RECOMPUTE_DIVISOR) == 1   # 3
else:
    _finale_move_tick = 0
if recompute_move:
    var mv = choose_movement(state)
    current_move_vector = mv.get("vector", Vector2.ZERO)
```

`_physics_process` runs at 60 Hz, so outside the finale the movement vector is
recomputed every tick. **At wave 20 and only at wave 20 it is recomputed on 1 tick in
3** — the commanded vector is held stale for ~33 ms at a time.

Why this is the leading suspect:
1. It is gated on **exactly** the wave where the hazard concentrates, and nowhere else.
2. It is the same failure *class* that v116 identified as the systemic root cause of
   the v84-103 era: the clearance primitives sampled time discretely (6 samples /
   0.6 s) and could not see threats crossing the commanded path *between* samples.
   The divisor is that defect moved from **sensing** to **actuation** — the policy
   cannot *respond* between recomputes even when it sees correctly.
3. Scale check, stated honestly: at a charging-bruiser speed of ~940 u/s a 33 ms hold
   is ~31 units of travel. Non-trivial against a player hitbox of tens of units, but
   **not obviously decisive** — this is a plausible contributor, not a proven cause.

### Why it cannot be dated
`BOSS_FINALE_RECOMPUTE_DIVISOR := 3` is present **at the repo's first commit**
(`9a390f4`, policy 0.1.92) with the identical value and identical gate logic.
`git log -S` finds no earlier introduction because there is no earlier history.
**So whether the strong era (v60-72) had this subsystem at all is unknowable** — the
same lost-baseline problem that makes the v72 anchor experiment impossible.

Weak, confounded supporting hint: the wave-19-to-20 reversal-rate drop is much larger
in the current era (0.4309 -> 0.2979) than in the strong era (0.3949 -> 0.3700),
which is what a finale hold would produce if the strong era lacked one. n=14,
confounded, and the metric is itself suspect at wave 20 precisely *because* of the
hold. Not evidence.

## A second, independently interesting find

The v117 comment at `agent_controller.gd:281-286` records that wave-20 captures and
movement decisions ran on *different tick phases*, so whether wave-20 captures landed
on recompute ticks depended on the counter phase at wave entry:

> "the v115 smoke drew the aligned phase (all fresh), the v116 smoke drew an offset
> (0/496 fresh) and **every fresh-gated audit silently skipped the death sequence**."

So for some period the audits were **structurally blind to the wave-20 death
sequence** — the exact place the hazard now appears. Fixed in v117 by emitting finale
captures on the recompute tick. Worth carrying as a caution: absence of wave-20
violations in any pre-v117 audit is not evidence of wave-20 health.

## The test, if the bank confirms the hazard

Single-constant A/B: `BOSS_FINALE_RECOMPUTE_DIVISOR` 3 -> 1, changing nothing else.
Clean because it is one constant, gated to one wave, and predicted to affect only
wave-20 outcomes — so wave <20 hazards act as an internal control. Gate it through
`docs/RELEASE_GATE.md` against the champion bank; do **not** qualify it on a smoke.

Predeclare before running: if the finale hazard in the bank comes back near the
strong era's 4.7%, this whole lead dissolves and should be dropped without a
follow-up experiment.
