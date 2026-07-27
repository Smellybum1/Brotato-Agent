# The invoker is a NAVIGATION problem, not a perception one

Measured over **180 damage events in 66 invoker wave-20 fights** (WP2-era
archived full runs; wave-20-only fixture trials excluded via
`duration_ms >= 300000`). No machine time — archive only.

**Why it matters now.** The invoker was written off as the free boss ("5W/5").
It is **0.597** on full runs (`fullrun_derivation_corrected.md`) and the pivot
fix cannot touch it, so it caps the achievable win rate at ~0.71 even with
predator survival perfect. Every finale effort so far aimed at the predator.

## Attribution (HP-drop instrument, all 7 buckets)

| source | events | % | damage | % |
|---|---|---|---|---|
| projectiles | 139 | 77.2 | 2403 | 72.4 |
| bosses (contact) | 31 | 17.2 | 736 | 22.2 |
| enemies | 10 | 5.6 | 182 | 5.5 |
| unexplained | **0** | **0.0** | 0 | 0 |
| materials / consumables / crates / obstacles | 0 | 0 | 0 | 0 |

Victory (85 events): projectiles 65.9%. **Defeat (95 events): projectiles 87.4%
of events, 83.8% of damage.**

**The finding: defeats are entirely static fields.** Of projectile-attributed
hits, **defeats are 83/83 stationary, zero moving**; victories 53/56. Median
surface distance at the causal tick **3.1 u** — the agent is deep inside the
field, not clipped at its edge.

**The damage is FULLY VISIBLE in the captured state.** That is the opposite of
the predator, which was a PERCEPTION defect with 84-91% of damage absent from the
state vector. The agent sees these fields and enters them anyway.

## The fields EXPIRE — this is not a fill-the-arena problem

- **Median persistence 1.00 s** (p90 1.00, max 1.00) on an independent
  position-keyed check; a 48,172-track trace agrees at 97.2% lasting 0.9-1.0 s,
  max 3.65 s.
- Count grows to ~19 over the first 20 s, then **plateaus for 60+ s** — exactly
  what a ~19/s spawn rate against a 1 s lifetime predicts. Two instruments,
  independently derived, agreeing.
- Position-keying was chosen over `instance_id` deliberately: ids are pooled and
  recycled (978,460 stationary observations carry only **2,020 distinct ids**,
  and 4.72% show an id >2 u from its last position while `vx=vy=0`). A stationary
  projectile is *defined* by not moving, so position carries identity and ids
  cannot.

**Consequence: local avoidance is the mechanically-matched class of fix.** A
routing/space-preservation intervention would be solving a problem the data says
does not exist.

## The mean hides a mixture: PULSED VOLLEYS

Stationary count per wave-20 tick:

| state | share of ticks |
|---|---|
| **zero** | ~34% |
| ~10 | 17-25% |
| **30** | 19-33% |

The arena is clean a third of the time; then a volley lands and expires within
~1 s. **A mean of ~19 describes neither state.**

## The 30 is the GAME's cap — the agent sees the whole volley

This nearly went in the record as *our* truncation censoring the agent's world
model, which would have made the invoker a second perception defect. It is not:

- `_WP2_CAPTURE_LIMITS` ships as **0 (unlimited) for every group**; the capture is
  deliberately untruncated and `dropped_counts` is **derived from that limit**,
  not hardcoded — its zero is an honest measured zero.
- The adapter's collection loop appends **every** child of `%EnemyProjectiles`
  with no cap (`SCENE_DUMP_EVERY := 30` is unrelated diagnostic cadence).
- **3,259 wave-20 captures: none exceeds 30, global max exactly 30.**

So the ceiling is upstream in the game — the same pattern the mod already
documents for materials, where the 50-pile is Brotato's own `MAX_GOLDS = 50`. The
specific constant is unverified against this build, since the only decompile on
hand is a different, older one.

**Density claims are therefore NOT censored by our instrument.**

## RETRACTION — an earlier 3.3% unexplained figure was an artifact

A first pass using explicit `player_damage` events reported 6/180 = 3.3%
unexplained, contradicting the committed "invoker control: 0/65 = 0.0%".

**The committed number is right.** `player_damage` events LAG the true damage
tick by one capture interval (~0.05 s), so attributing at the capture before the
EVENT lands one capture too late. Re-running the earlier HP-drop-diff method on
the same 66-run sample gives **0/180 under every variation tried** (3 buckets or
7, with or without the radius term). All six "unexplained" events sit +0.046 to
+0.053 s after their HP-drop counterpart, and at the correct capture the nearest
distance is −14.9 to +27.2 u.

**`player_damage` is the wrong instrument for attribution; use the HP-drop diff.**
The predator's 84-91% was measured with the correct instrument and is unaffected.

## Field notes

- **`wave_time.elapsed_sec` takes exactly one backward step per victory run**
  (18 of 68, always at the end) — the known reset-on-victory behaviour. Do not
  assume monotonicity.
- All attribution is proximity inference: `player_damage` carries only
  `{amount, hp}` — no position, no attacker id.

## Not determined

Arena-wide accumulation *outside* the player's neighbourhood is not excluded by
the count curve alone; the lifetime trace is what rules out monotonic fill, and
it is the load-bearing evidence. An uncapped arena-wide projectile census would
settle it directly, and does not exist in this data.
