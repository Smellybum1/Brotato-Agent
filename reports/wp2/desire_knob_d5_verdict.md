# §34 — Re-pricing the `_build_desire` knobs at Danger 5

**VERDICT: BOTH KNOBS FAIL. DO NOT IMPLEMENT.**
`calm_threat_mult` and `engage_distance_scale` are the only two runtime config scalars that reach
`_build_desire`. Both act solely on terms whose median leave-one-out command rotation is **≤ 0.11°**
(p90 ≤ 4.93°). Deleting `enemy_engagement` **entirely** rotates the emitted command **0.11° at the
median**. No dose can act.

Written after the analysis, from an offline scan of already-collected data. **Zero new runs.**

## §34a — Provenance and denominators

- Sample: the **8 D5 ranger runs** of the §32 campaign, mod **`0.2.76-wp2-capture`**,
  `route_scores_enabled` true, era **179/48/2018397571**.
- **76,543 `combat_capture` lines, full scan, no striding.**
- Endpoint set for the verdict (§34e): wave ≤ 11, `route.exit ∈ {baseline_kept, no_threats}`,
  **n = 35,255**.
- Angular set (§34d): wave ≤ 11, **n = 61,043 measured**; **53** stale-seq captures excluded,
  **5,097** degenerate-desire captures excluded. Both counts printed, never silently dropped.
- Per-run wall/projectile split (§34c) is over all 8 runs, all waves.

## §34b — CONTROLS. The sum-reproduction control, which the FIRST MODEL FAILED.

⭐ **State it plainly: the initial model failed this control, and that failure is how the instrument
defect below was found.** It was not found by reading source first.

**Control 1 — term-sum reproduction.** `teacher.contributions.desire` records 12 terms. The naive
model `sum(12 terms) == (total_x, total_y)` reproduces the recorded total on only

> **11,540 / 35,255 = 0.3273** (p50 rel err 3.38e-03, p90 8.89e-02, **max 2.65e+01**)

That is a FAILED control. A 67% miss is not rounding.

**Root cause, read from source** (`teacher/potential_field.gd`): `enemy_engagement` is latched at
**:2087-2088**, and the `early`/`loot_safe` branch then executes
`force *= BotConfig.EARLY_LOOT_VS_HUNT` (**0.38**) at **:2098** — **AFTER the record**. It is the
**only** post-record mutation in the function. The realised contribution is
`early_force_mult * enemy_engagement`, where `_d_early_force_mult` defaults 1.0 (decl :549, reset
:587, set :2099); the recovery is documented in-source at **:546-548**.

**Corrected model: 35,255 / 35,255 = 1.0000** (p50 rel err 2.68e-08, p90 6.45e-08, max 7.04e-05).

⛔ The multiplier is **ACTIVE on 32,706 / 35,255 = 92.8%** of target-band captures. **Any prior
reading of `enemy_engagement`'s share of the desire is wrong by `1/0.38 = 2.63x` there.**

**Control 2 — sign convention.** `inward_damp` IS correctly recorded signed-as-subtracted
(**:2136-2139**) and needs no sign handling. Verified, not assumed.

**Control 3 — pipeline norms (§34d).** `||teacher.action|| == 1.0000` on **76,502/76,502**;
`||_prev_move||` unit on **26,847/26,847**; `||baseline||` unit on **0.9969**. The pipeline transmits
**DIRECTION ONLY**, so every endpoint in this report is **angular**. A magnitude endpoint would have
been vacuous.

## §34c — SCOPE CORRECTION: the "safety tail is absent at D5" claim is a POOLED MIXTURE

Recorded in memory: `wall_recovery_active` **1.17%** at D5, "~50x lower than D0 wave 17's
0.370-0.869". **That 1.17% is pooled and it is a mixture.**

Per run: **all 892 `wall_recovery` trues and all 373 `projectile_safety` trues come from ONE run**
(`run_1785754965_28036`, 17,882 captures, the only run reaching wave 18) at **0.0499**. The other
**seven runs are exactly 0/0**.

Per wave, pooled over all 8 runs:

| waves | wall_recovery | projectile_safety |
|---|---|---|
| 1-16 | **0 / 66,796 = 0.0000** | **0 / 66,796 = 0.0000** |
| 17 | **672 / 1,240 = 0.5419** | 164 / 1,240 = 0.1323 |
| 18 | **220 / 332 = 0.6627** | 209 / 332 = 0.6295 |

⭐ **CONCLUSION: the wall path is a WAVE-17+ phenomenon at BOTH danger tiers, not a danger-tier
effect.** D5 wave 17 (**0.5419**) sits **inside** the D0 wave-17 band (0.370-0.869). It looked
"absent at D5" only because D5 runs die at **median wave 11**. This is the *pooled statistic over a
population that is bimodal by outcome* error, again.

`body_safety_active` by contrast is **LIVE throughout the target band: 0.22-0.55 across waves 1-16.**

## §34d — TRANSMISSIVITY: at D5 the desire DOES reach the command

Angles at wave ≤ 11 (n = 61,043):

| exit | n | share | median angle(action, desire) |
|---|---|---|---|
| `baseline_kept` | 31,781 | 52.1% | **11.29°** (p10 0.47, p25 2.35, p75 45.05) |
| `no_threats` | 3,474 | 5.7% | **2.84°** |
| `ranked` | 25,788 | 42.2% | **88.57°** |

On the `ranked` path, median `angle(action, prev_action) = 0.00°` (p25 0.00, p75 15.00).

⇒ On **~58%** of target-band ticks **the desire essentially IS the command**; on the `ranked` path it
is **orthogonal** to the command and the command simply **repeats the previous action**.

D0 wave-17 reference for contrast: pooled median `angle(final, desire)` **54.7°**.

So the D0 excuse does not apply here. The desire layer at D5 waves ≤ 11 is **live**.

## §34e — THE VERDICT: leave-one-out angular leverage

Restricted to ticks where the desire IS the command (wave ≤ 11, exit ∈ {`baseline_kept`,
`no_threats`}), **n = 35,255**. **`early` is TRUE on 35,255/35,255 = 1.0000** — the early branch is
the **only** regime in the band.

Statistic: `rot(t) = angle(total, total − t)` — the rotation of the emitted desire if term `t` were
removed **entirely**. This is an upper bound on what any finite dose on `t` can do.

| term | nonzero rate | median \|t\| | p90 \|t\| | rot p50 | rot p75 | rot p90 |
|---|---|---|---|---|---|---|
| **loot** | 0.9226 | **111.111** | **403.981** | **65.91** | **119.93** | **168.21** |
| enemy_engagement | 0.9015 | 0.261 | 6.852 | **0.11** | 0.78 | 4.93 |
| early_hunt | 0.9015 | 0.369 | 0.409 | 0.07 | 0.23 | 0.63 |
| consumable | 0.4722 | 0.000 | 0.039 | 0.00 | 0.00 | 0.01 |
| circling | 0.4703 | 0.000 | 0.113 | 0.00 | 0.02 | 0.10 |
| engage_strafe | 0.4309 | 0.000 | 1.215 | 0.00 | 0.18 | 0.63 |
| tree | 0.1977 | 0.000 | 20.109 | 0.00 | 0.00 | 3.95 |
| inward_damp | 0.0277 | 0.000 | 0.000 | 0.00 | 0.00 | 0.00 |
| wall | 0.0066 | 0.000 | 0.000 | 0.00 | 0.00 | 0.00 |
| edge_kite | 0.0000 | 0 | 0 | 0.00 | 0.00 | 0.00 |
| pack_density | 0.0000 | 0 | 0 | 0.00 | 0.00 | 0.00 |
| center | 0.0000 | 0 | 0 | 0.00 | 0.00 | 0.00 |

Branch flags on the analysis set: `early` **1.0000**, `edge_kite_branch` 0.0000, `out_of_range`
0.6354, `at_weapon_range` 0.4309.

### The two knobs, and what each one can touch

Exactly **two** runtime config scalars reach `_build_desire`; both verified plumbed end-to-end:

- **`calm_threat_mult`** (default 1.0) — per-enemy weight inside `_enemy_engagement_force`
  (**:2512 / :2521**). Moves the **`enemy_engagement` term ONLY**.
- **`engage_distance_scale`** (default 1.0) — scales `engage` at **:2062** (feeding
  `_enemy_engagement_force`) and moves the `at_weapon_range` gate at **:2078**, which switches
  `engage_strafe` + `inward_damp` against `circling`.

Every term either knob can touch has **rot p50 ≤ 0.11°** and **rot p90 ≤ 4.93°**.
**Deleting `enemy_engagement` entirely rotates the command 0.11° at the median.** No dose can act.

### Escape routes checked and CLOSED

Raising `engage_distance_scale` flips `out_of_range`, which gates `pack_density` (via
`elif not out_of_range`) and `center`. **Both are dead via the `early` clause instead**: the
`if early:` branch is taken on **100%** of the band, making the `elif edge_kite` and
`elif not out_of_range` arms **UNREACHABLE**, and `center`'s guard at **:2184** excludes
`early and (loot or enemies non-empty)`. The knob **cannot revive them**. `loot` does not depend on
`engage`.

## §34f — WHY THIS MATTERS BEYOND THE NULL

The recorded explanation for the D0 `calm_threat_mult` null (desire **+0.216**, command **+0.003**,
~**72x**, sign inverted) was **"the safety tail owns the command."**

**In the D5 target band the tail is ABSENT (§34c/§34d) and the knob is STILL inert** — because the
term it moves is **~425x smaller in magnitude than `loot`** (median |enemy_engagement| 0.261 vs
median |loot| 111.111).

⭐ **Same null, different mechanism.** The D0 explanation was correct for D0 and **does not
generalise**. Carrying it forward as the reason would have been a right answer for a wrong reason —
and would have licensed the wrong next lever.

## §34g — OPEN LEAD. ⛔ NOT YET TESTED. Needs its own pre-registration.

**At D5 waves ≤ 11 the movement desire is essentially the LOOT vector, and no config knob exists on
it.** `loot` is nonzero on 92.3% of the band, median |loot| 111.111, rot p50 **65.91°** — it is the
only term with command authority in the entire desire layer.

⛔ **Honest hazard, stated before anyone designs the ladder: with |loot| ~111 against a residual of
~0.6, a loot-scaling knob is a CLIFF, not a dose.** It does nothing until `loot` is scaled down to
the residual's order (~**0.005-0.05**), then flips wholesale. **A naive dose ladder (0.5, 0.75, 1.5,
2.0) would read as a clean null** and would close the branch falsely. Any prereg must place its doses
on a log scale reaching the residual's order, and must declare that in advance.

⭐⭐ **THE LEVER FORM SHOULD BE THE FALLOFF EXPONENT, NOT A SCALE.** Read from source,
`_loot_attraction` (**:3551-3585**) sums over every loot item:
`force += (diff/dist) * LOOT_ATTRACTION * greed * safety * clear_mult / falloff`, and in early waves
`falloff = pow(dist, 0.65)` (**:3580**) rather than `dist`. At 500 u that decays ~**8.6x** more weakly
than a `1/d` law, so **distant loot pulls almost as hard as near loot** — which is why |loot| reaches
111 with ~10 materials on the ground, with no anomaly required.

A **scale** multiplies the whole resultant and therefore cannot rotate it; the pipeline is
direction-only (§34d Control 3), so a scale is inert until the cliff. **Changing the exponent
reweights WHICH items dominate the sum**, so it rotates the resultant **continuously and
monotonically** in the dose. That is a real dose where a scale is a step function.
⇒ The pre-registered ladder should be on the **exponent** (e.g. 0.65 → 0.9 → 1.2 → 1.6), with a scale
ladder, if run at all, on a log scale reaching ~0.005.

⚠️ Note the term already carries its own vetoes that a lever must not silently duplicate:
`nearby >= PACK_DENSITY_SOFT (8)` returns **ZERO** outright (**:3559-3560**), and blockers
`> LOOT_PACK_ALLOW (2)` skip an item (**:3574**).

⭐ **This is a DISJOINT tick set from every closed movement lever.** All four previously-closed levers
— §31 `body_slack`, continuity-removal, §32 positional term, §33 PACK floor — acted on the
**ROUTE / body-safety** layer and were analysed on **`ranked`** captures. The desire layer on
**`baseline_kept`** ticks (52.1% of the band) is a tick set **none of them touched**. The
movement-lever class being "closed" does not close this.

## §34h — NOT MEASURED

- Any survival or terminal-wave consequence of altering `loot`. Nothing here is a survival claim.
- Whether the wave-17+ wall-path finding replicates at D5 with n > 1 run reaching wave 17
  (**all 892 wall trues come from a single run** — the per-wave rates in §34c rest on n = 1 run).
- The behaviour of any `_build_desire` term at waves > 18 at D5.
- Whether the 2.63x correction in §34b changes any previously published `enemy_engagement` figure —
  the affected prior readings have **NOT** been enumerated or re-run.
