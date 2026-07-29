# Human vs agent over a full run: currency collected and enemies killed

**Date:** 2026-07-29. Operator-requested comparison. No machine time; computed from the archive.
Scripts kept in the session scratchpad (`networth.py`, `kills.py`); both were run and verified in
the primary session, raw series printed.

**Arms.** Human movement-only handover run `run_1785296333_7237` (mod `0.2.50`, `human_movement`
true, `time_scale` 1.0) against **31 era-matched agent full runs** (mod `0.2.49`, policy
`0.1.129`, `time_scale` 1.0, `duration_ms >= 600000`, `last_wave == 20`).

**Run selection matters here:** 1,553 archived runs read `last_wave == 20`. Only 31 are full runs
in this era; the rest are wave-20 fixture trials. Separating on `duration_ms` is mandatory — this
is the contamination that once corrupted the headline win rate for weeks.

**Note on attribution for both results below:** in the human arm the agent still made every shop
and level-up decision. The handover was movement only. So these compare collection-and-combat
*by movement*, on an agent-chosen build.

---

## 1. Currency collected — the human is NOT richer

**Method.** Materials ledger from `payload.player.materials` over valid `combat_capture` rows in
seq order. Positive deltas are income (pickups + wave-end sweep); negative deltas are spending
(shops fall between waves, when no captures are emitted).

**Two validations, both clean on all 32 runs:**
- `start + income − spend − final == 0` **exactly**, every run.
- **Zero** negative deltas occurring inside a wave, every run — so income and spending never
  contaminate each other.

| | human | agent median | agent range |
|---|---|---|---|
| **Waves 1-19 income** | **5380** | **5328** | 4462 - 6376 |
| Wave 20 income | 57 | 233 | 44 - 408 |
| Full-run income | 5437 | 5691 | 4807 - 6660 |
| Spend | 5378 | 5307 | 4483 - 6363 |
| Final gold | 89 | 256 | 55 - 867 |

**Waves 1-19 is the fair comparison and it is a tie: ratio 1.010, with 16 of 31 agent runs below
the human** (~52nd percentile). The full-run gap is entirely wave 20, where the human died at 27 s.
Wave-20 income is essentially a survival-time readout: agent victories survived 37-90 s and
collected 102-408; the 4 agent defeats survived 21-37 s and collected 44-167, exactly where the
human sits.

Per wave the human is ahead early (8 of waves 1-10, and ahead of *every* agent run at wave 1) and
slightly behind mid-late (w11 344 vs 377, w13 320 vs 354, w16 416 vs 523), then well ahead at w19
(584 vs 461, beating 22 of 31).

### Why this matters

**It cuts against the economic-rescue arm (item 6 of the plan).** That arm asks "would a richer
build have helped?" The one human trajectory that *did* rescue wave 17 in the fixture did not
accumulate more currency over a full run.

It also reconciles the bag-drain finding rather than contradicting it. The human strands far less
material at wave end (bag drained 20/20 vs the agent's 76.7% on w17-20), yet total income is
identical — consistent with the wave-end sweep crediting ground material as bonus gold either way.
**Stranding costs timing, not totals.**

---

## 2. Enemies killed — the human clears more, but the cause is confounded

**`instance_id` is unusable and was discarded.** Wave 5 of the human run shows only **22 distinct
enemy `instance_id`s across 845 captures**, and all 22 disappear and reappear. The pool recycles
ids across different enemies; identity tracking would have produced a confident wrong number.

**Method used instead — count deltas, no identity required.** Per consecutive capture pair, a fall
in `len(entities.enemies)` counts as removals and a rise counts as spawns, restricted to
`remaining_sec > 0` so the wave-end mass clear (not a player kill) is excluded.

**Known bias, stated up front:** captures are ~150 ms apart, so an enemy that spawns and dies
inside one interval is invisible. These are **lower bounds**.

**The instrument validates.** The waves 1-19 spawn schedule is game-determined, and it reproduces:

| | human | agent median | agent range |
|---|---|---|---|
| **Spawns detected, w1-19** | **3752** | **3750** | 3591 - 4037 |
| in-timer captures, w1-19 | 19193 | 19196 | 19190 - 19200 |

Ratio 1.001 on spawns and near-identical denominators — both arms are sampled identically, so the
aliasing cancels in the comparison.

### Result

| | human | agent median | agent range |
|---|---|---|---|
| **Kills (removals), w1-19** | **3563** | **3484** | 3309 - 3720 |
| **Clearance fraction** | **0.9496** | **0.9277** | 0.8946 - 0.9564 |

The human killed 2.3% more, with 25 of 31 agent runs below. The sharper measure is **clearance
fraction** (kills ÷ spawns, which normalises away spawn-count noise): the human cleared 94.96% of
what spawned against an agent median of 92.77%, and **only one of 31 agent runs beat it.**

The gap is concentrated late and shows up as enemies left alive at the timer:

| wave | human left alive | agent median left alive |
|---|---|---|
| 15 | 13 | 29 |
| 16 | 9 | 17 |
| 17 | 17 | 26 |
| 18 | 12 | 23 |
| 19 | 24 | 36 |

Peak simultaneous enemies is correspondingly lower for the human in those waves (w15 29 vs 39,
w18 23 vs 33) — a *consequence* of clearing faster, not an independent effect, so the two measures
are self-consistent.

### What must NOT be claimed from this

- **It cannot be attributed to movement.** The agent's build draw in the human run was a strong one
  (58.78 against a died-median of 28.26), already on the record as a known-weak point. A stronger
  build clears more. Build and movement are confounded and this data cannot separate them.
- **It is n=1.** Treating the human run as exchangeable with the 31 agent runs, its clearance
  fraction ranks 31st of 32 — **p ≈ 0.06 one-sided**. Suggestive, not established. The kill *count*
  alone is weaker still: 26th of 32, p ≈ 0.22.
- More kills did **not** convert into more income (ratio 1.010 on w1-19), which is the same
  sweep-credits-anyway conclusion as section 1.

---

## 3. Currency SPENT at shops 1-19 — equal outlay, different composition

**Shop N is the shop AFTER wave N** (confirmed: the first `purchase_decision` carries `wave == 1`
with `gold_before == start_gold + wave-1 income`). "Up to and including the wave-19 shop" is
therefore shops 1-19, and every run in both arms reached wave 20, so all 19 are observable.

**Two methods were computed and they disagreed — the disagreement was the finding.**
- **A, materials ledger:** the negative delta in `player.materials` across the wave boundary.
- **B, prices paid:** the `price` of each bought slot from the matching `purchase_offer`, plus
  `reroll_price` per reroll.

B exceeds A on **every one of 32 runs** (agent gap −92 to −1178, median −369). Cause: **gold is
GAINED around the later shops** — a percentage-of-gold item effect. In `run_1785212557_51318`
shop 13, gold goes 568 → 594 *while 73 is spent*, an implied gain of ~99; the implied gain is 0 at
every early shop and grows with wealth. So **method A measures spend net of that bonus and
undercounts. Method B is the true outlay** and is used below.

| shops 1-19 | human | agent median | agent range | agents below human |
|---|---|---|---|---|
| **Total spent** | **5804** | **5718** | 4760 - 7500 | 17/31 |
| on items | 4936 | 5197 | 4267 - 6725 | 10/31 |
| **on rerolls** | **868** | **521** | 248 - 994 | **30/31** |
| items bought | 59 | 64 | 54 - 78 | 7/31 |
| rerolls taken | 46 | 40 | 29 - 57 | 25/31 |
| **reroll share of spend** | **0.1496** | **0.0936** | 0.0445 - 0.1497 | **30/31** |

**Total outlay is level (ratio 1.015). The composition is not:** the human run spent ~5% less on
items and **67% more on rerolls**, with a reroll share of spend beaten by only one of 31 agent runs
(0.1497, a virtual tie).

### The confound that makes this hard to interpret

**The handover was movement only — the agent made every purchase and reroll decision in the human
run.** This is not human-vs-agent shopping. It is the *same* shop policy reacting to a different
gold-and-board trajectory. The mechanism is visible in the per-shop table: at shop 18 the human run
spent 197 against an agent median of 423 and carried 171 gold out, arriving at shop 19 with 755
(agent median 575) and spending 834 there. Surplus gold triggers the surplus-reroll path
(`shop_surplus_reroll_confirmed`, 13 in the human run), so a lumpier income stream mechanically
buys more rerolls.

n = 1 human run: at rank 31 of 32 on reroll share, p ≈ 0.06 one-sided. Suggestive, not established.

## Telemetry defect found while doing this

**`summary.json`'s `materials_spent` reads 0** for a run whose true spend is **5378**. Add it to
the standing list of structurally uninformative fields.
