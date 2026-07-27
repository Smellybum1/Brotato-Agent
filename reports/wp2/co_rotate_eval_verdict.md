# Co-rotation eval verdict — **NOT CONFIRMED**. Flag stays default-OFF.

Protocol: `reports/wp2/co_rotate_eval_protocol.md`, committed `8d19d06` **before trial 1**.
Evaluator: `scripts/wp2_co_rotate_eval.py`. Build 0.2.47, 128 trials, 8 fixtures x 8 x 2 arms.

## Result

| | |
|---|---|
| mean paired difference | **−3.05 damage** (negative = co-rotation helped) |
| exact Wilcoxon | **W=7.0, p = 0.1484** |
| fixtures favouring treatment | 6/8 |
| pooled mean damage | control **20.7**, treatment **17.9** |
| win rate (SECONDARY) | control 64/64 = 1.000, treatment 62/63 = 0.984 |

**The predeclared rule was: exact Wilcoxon p < 0.05 AND mean difference < 0. The
direction passes, the p-value does not. NOT CONFIRMED.**

Per-fixture differences: −7.9, −7.6, −4.6, −4.2, −3.5, −3.4, +0.5, +6.4.

**Do not read the favourable direction as encouraging.** Finale v2's campaign 1 gave
+0.1875 with 4 of 5 non-tied builds favouring it and a CI excluding zero, and it
REVERSED on a fresh sample. A consistent-looking direction at p=0.15 is exactly that
shape. See [[brotato-finale-v2]].

## Validity gate — passed on the thing it exists to catch

**0 arm mismatches in both arms**: every trial ran on the flag it was asked to run.
That is the failure the gate exists for — a flag that silently reverts would compare an
arm against itself and manufacture a null.

**One deviation from a literal reading of the protocol, stated plainly.** The protocol
says "require 0 invalid trials". One treatment trial was invalid with reason
`game_exited_before_summary` — an infrastructure crash, not an arm compromise. I
distinguished the two rather than voiding 127 good trials on a technicality the gate was
not designed to catch, following the precedent set when finale v2's campaign handled its
2 invalid trials by sensitivity rather than by voiding.

**Charged worst case, the verdict does not change**: giving the lost trial the worst
damage observed anywhere (109) gives mean difference −1.42, p = 0.6406. The missing
trial is not what produced this result — it only ever made it weaker.

## What was predicted in advance, and held

The protocol recorded two reasons this could come back null, before the data existed:

1. **The control already co-rotates 67.6% of the time**, far above the 50% chance
   baseline — repulsion from the ring was already steering the agent mostly the right
   way. The intervention adds only ~7 pp (74.4%).
2. **The control arm is near-perfect on these fixtures.** It came in at **64/64
   victories**, confirming the win rate is pinned at the ceiling — which is exactly why
   damage was pre-registered as the primary metric rather than win rate. Had win rate
   been the decision variable this campaign would have been uninformative by
   construction.

Both held. The null is informative rather than disappointing.

## Also worth recording: how much the pivot fix moved the floor

Control-arm pooled mean damage is **20.7**, against a pre-fix wave-20 baseline whose
median damage was ~52. The control here is not a weak baseline — it is the agent with
the blind spot closed, and it wins every trial. Co-rotation had to beat that.

## What this does and does not close

**Closes:** co-rotation as a standalone steering change, at weight 0.50, on these 8
fixtures. Do not re-run it, do not add trials to this sample and re-test, and do not
re-analyse with a different metric — all three are optional stopping.

**Does NOT close:** the outrun mechanism. A prediction was registered BEFORE this
campaign reported: co-rotating cannot outrun anything at the agent's usual 566 u, where
it out-rotates the ring only 7% of the time. Direction without radius is not the
mechanism. That is tested separately and pre-registered in
`reports/wp2/ring_radius_eval_protocol.md`, whose treatment arm carries BOTH terms.

**This verdict is not evidence for that campaign.** It is a null, and the ring-radius
campaign must clear its own predeclared bar on its own fresh sample.
