# Prompt for Fable: improve BrotatoAgent beyond v79

You are taking over a read-only evidence and design review of BrotatoAgent in
`C:\Codex\Brotato Agent`. The game and evaluation are deliberately stopped.
Do not edit code, deploy, launch Brotato, enable scheduled tasks, start another
campaign, begin WP2, or commit. Your job is to explain how to make the current
agent materially better and recommend one focused, testable v80 change for
Codex and the operator to consider.

## Where your previous handoff ended

The last Fable review received evidence through v68 and produced v69. Treat
v69 as the handoff boundary. Your v69 diagnosis was that the dominant remaining
failure was general offense/kill-rate rather than effective HP, and you added a
below-target offense floor. That diagnosis continued to be supported, but the
implementation lineage since then exposed scoring, integration, measurement,
shop-safety, and finale-movement limitations.

WP1 itself is already certified: v72 completed exactly 20 runs at **18W/2L**
with complete telemetry and zero errors, hangs, or APPCRASH events. Versions
v73-v79 are post-pass improvement experiments, not a revocation of that result.

## Read these first

1. `reports\WP1_ACTIVE_GATE.md`
2. `reports\FABLE_WP1_WIN_RATE_REVIEW_PROMPT.md`
3. `reports\v69_change_record.md`
4. `reports\v70_change_record.md`
5. `reports\v71_change_record.md`
6. `reports\v72_change_record.md`
7. `reports\v72_campaign_analysis.md`
8. `reports\v73_change_record.md` and `reports\v73_comparison_analysis.md`
9. `reports\v74_change_record.md`
10. `reports\v75_change_record.md` and `reports\v75_comparison_analysis.md`
11. `reports\v76_change_record.md` and `reports\v76_comparison_analysis.md`
12. `reports\v77_change_record.md` and `reports\v77_comparison_analysis.md`
13. `reports\v78_change_record.md` and `reports\v78_comparison_analysis.md`
14. `reports\v79_change_record.md` and `reports\v79_pause_hud_fix.md`
15. `reports\batch_overnight_20_v72.csv` and `.md`
16. The relevant `%APPDATA%\Brotato\brotato_agent\runs\run_*\summary.json`
    and `events.jsonl`, especially the four completed v79 runs listed below.

Relevant current code is primarily:

- `mod\mods-unpacked\Tom-BrotatoAgent\teacher\config.gd`
- `mod\mods-unpacked\Tom-BrotatoAgent\teacher\shop_strategy.gd`
- `mod\mods-unpacked\Tom-BrotatoAgent\teacher\combat_model.gd`
- `mod\mods-unpacked\Tom-BrotatoAgent\teacher\potential_field.gd`
- `mod\mods-unpacked\Tom-BrotatoAgent\runtime\agent_controller.gd`
- `mod\mods-unpacked\Tom-BrotatoAgent\telemetry\telemetry_writer.gd`
- `mod\mods-unpacked\Tom-BrotatoAgent\ui\agent_hud.gd`
- `trainer\evaluation\live_monitor.py`
- `tests\unit\test_shop_policy_source.py`

`reports\live_monitor.json` now describes an intentionally interrupted fifth
v79 run and reports stale telemetry because Brotato is stopped. Do not treat
that expected stopped-state staleness as a runtime failure or score the partial
run as a win/loss.

## What Codex changed after v69

### v69 outcome

Your offense-floor repair was directionally correct, but its gate became
impossible at 6W/3L. The third loss still had offense only 43 versus the late
target of 120 despite ample durability; enemy density reached 111. The scoring
boost did not reliably prevent defensive/utility spending from winning the
decision competition.

### v70: adequate-defense offense pivot

Codex added a wave-15+ mode that suppressed pure defense when max HP >=65,
armor >=10, sustain >=12, and offense <120. It was shared by shops, level-ups,
and crates. The gameplay evidence began 2W/0L, but both watchdog roots vanished
together during run 3, so the comparison could not continue safely.

### v71: resumable triggered watchdogs

Gameplay stayed identical to v70. Scheduled tasks gained one-minute repeating
triggers, atomic supervisor checkpoints, safe resume behavior, overlap
protection, and stronger status validation. V71 reached 11W/3L after 14 runs.
Its late losses showed that requiring all three defense layers to be adequate
was too strict; heavy sustain/HP builds could remain offense-starved because
one layer, usually armor, was below threshold.

### v72: layer-local defense saturation (certified baseline)

Codex replaced the conjunction with independent marginal caps: suppress more
HP at 65, armor at 10, and sustain at 12; suppress dodge/control only when two
layers are adequate. V72 achieved the certified **18W/2L**.

Post-campaign analysis established the primary strength metric as the mean of
each wave's p90 observed enemy count. Across 18 v72 victories it was **15.26**.
The five strongest low-density wins averaged 12.5 and combined 68% more
telemetry-derived offense with 37% less added HP than the other wins, while
sustain was nearly unchanged. Four Minigun purchases all won. The dominant
remaining loss was still a general-DPS/density failure.

### v73: stronger defense veto, crowd-clear weights, rare-gun workflow

V73 hard-rejected defense-only investment in already adequate layers while
late offense was below target, raised piercing/explosion/death-projectile and
burning-spread valuation, delayed Silver Bullet until the final shop, and added
explicit Minigun III+ / Chain Gun IV buy-save-replace behavior.

It stopped at **1W/2L**. Both losses were offense-starved (65 and 67 offense
added) with late density surges. The rare-gun lock/save/buy path worked safely,
but arrived too late to repair ordinary-wave clearing. The lone victory had
mean p90 density 31.45, far worse than v72.

### v74: wave-10 offense pivot and lower defense thresholds

The offense pivot moved to wave 10; defense adequacy dropped to 45/5/8 in the
midgame and 60/8/10 late; below-target offense scoring and reroll pressure were
increased. The first run lost on wave 16 with offense only 36 while mixed
sustain remained eligible and utility could still be locked ahead of direct
offense. Score changes alone were not enforcing the intended priority.

### v75: affordable-offense guarantee

V75 classified mixed sustain as defense unless it also added measurable direct
offense, used prospective defense caps, required affordable policy-safe
net-positive offense while below target, gave the same priority to level-ups,
blocked non-rare utility locks ahead of affordable offense, and vetoed pure
enemy-density additions.

Its only run lost on wave 19. The offense-first path did activate, but the hard
sustain cap failed live: Blood Leech, Butterfly, Mushroom, and Fresh Meat were
still bought while offense remained below target. The cause was an integration
bug in live stat extraction, not an absent policy helper.

### v76: hard-cap integration fix and observable metrics

V76 removed the fail-open dependency on profile/offense context and fixed a
boolean-fallback bug that collapsed any nonzero regeneration/lifesteal value to
1. It made prospective HP/armor/sustain caps unconditional from wave 10 and
added HUD/telemetry offense and defense components, totals, and wave targets.

The 1W/1L comparison exposed two measurement/control problems:

- wave-20 commands repeatedly reversed, producing rapid micro-movement with
  only 3.7%-9.8% net/path movement;
- the offense score ignored equipped gun tiers and therefore understated builds
  that cleared well despite modest raw ranged/%damage/attack-speed stats.

### v77: weapon-aware offense and first finale stabilization

V77 added a shared weapon-aware estimator using weapon tier, base damage,
cooldown, scaling, crit, projectile count, piercing, bounce, explosions, and
burning. The historic score became `max(stat score, estimated DPS / 15)`.
Telemetry/HUD exposed both representations and weapon tier/count.

Wave-20 direction was recomputed at 20 Hz, held between decisions, biased
toward lane continuity, and converted direct reversals into perpendicular turns.

The result was **5W/2L**, with victory mean p90 density 17.04 (worse than
v72's 15.26). The strongest win was highly instructive: offense 367, estimated
DPS 5,509, defense only 167, sustain 8, and mean p90 density 14.36. The most
defensive loss had defense 404 and sustain 27 but only 1,995 DPS and died to
crowd overwhelm. The other loss was wave 20 with adequate ordinary-wave clear
but only 4.18% commanded net/path movement. V77 also still skipped affordable
offense, allowed pre-pivot sustain accumulation, and retained utility locks.

### v78: earlier hard pivot, adaptive target, utility veto, displacement commit

V78 moved the offense pivot to wave 9 and sustain cap to wave 8; required
affordable net-positive direct offense until a 15-point security margin;
applied the cap to mixed and indirect sustain; cleared ordinary utility locks;
and raised the target from prior-wave p90 density. It also replaced finale
direction-only continuity with a 120-pixel/16-tick displacement commitment.

The completed run lost on wave 19 despite displayed offense 199.9/159 and
2,998 estimated DPS; p90 density reached 59.5 and peak 71. This showed that the
scalar DPS model and one-wave-lagged p90 target could still overrate practical
clear and miss abrupt density changes.

The second run entered a deterministic Revolver lock/unlock loop: the generic
utility veto saw zero direct effects, while the weapon-aware premium path saw a
valuable weapon and relocked it. There were 120 locks, 112 unlocks, and 224
adjacent alternations before the safety stop.

### v79: weapon-aware lock safety and stronger density calibration

V79 excludes weapons from the generic utility-lock veto, lets affordable usable
weapons satisfy offense-first, expires unlocked deficient-offense utility for
the current visit, and limits the same item's lock transitions to two per wave.
A third attempt safely exits the shop with `shop_cycle_guard` telemetry.

The late offense margin rose to 25. Prior-wave p90 pressure rose to seven target
points per enemy over goal (cap 90), and prior-wave peak above 25 adds two points
per enemy (cap 30). The v78 wave-19 failure would therefore demand about 215
offense rather than accepting 199.9.

The user stopped v79 after four completed runs at **3W/1L** because the agent
was in a good state and the HUD needed layout correction. Run 5 was interrupted
on wave 5 and must not be scored. No completed v79 run had an error, hang,
illegal action, watchdog failure, or APPCRASH. The v78 lock loop did not recur;
one Wheelbarrow/Catling lock pair expired normally, Wheelbarrow was dropped,
and Catling Gun was immediately bought.

The HUD was subsequently moved into a bounded bottom-left viewport column with
wrapping and clipping. This changes observability only, not policy. The game
was not relaunched for visual confirmation because the user explicitly wanted
the run stopped.

## Current v79 evidence

| Run | Result | Mean p90 | Late p90 | Peak | Offense/target | Est. DPS | Tier sum | Defense | Sustain | Rare acquisitions |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `run_1784631177_68132` | Win | 13.20 | 18.00 | 38 | 440/261 | 6,605 | 20 | 279 | 12 | 1 `item_catling_gun` |
| `run_1784632327_16396` | Win | 12.30 | 14.33 | 28 | 459/173 | 6,878 | 22 | 212 | 9 | 3 Minigun buys, 1 Catling |
| `run_1784633480_66139` | Loss, wave 20 | 16.30 | 27.83 | 56 | 240/265 | 3,595 | 18 | 256 | 9 | 1 Catling |
| `run_1784634616_90494` | Win | 14.55 | 22.00 | 42 | 350/265 | 5,256 | 20 | 238 | 8 | 2 Catling |

All three v79 victories individually beat the v72 victory-density baseline of
15.26; their mean is **13.35**. Their mean estimated DPS is about **6,246**.
The sole loss is the only completed run that finished below its adaptive target.
That is encouraging evidence that v79's target is more meaningful than the old
fixed 120 threshold, but four runs are far too few to claim a win-rate gain.

The wave-20 loss ended with observed HP 13 and 17 enemies still present. Its
finale commitment was active on 43 of 48 sampled ticks and reached about 99
pixels, but offense remained 240/265. The best current inference is failure to
finish the boss/wave in time rather than a simple zero-HP death or recurrence of
the original stationary cancellation bug. Verify this from raw evidence and
label it as inference: current telemetry does not expose boss HP, exact timer,
kill throughput, or terminal reason beyond `defeat`.

Commanded net/path movement on the four v79 finales remained only 1.19%-5.29%.
Three runs exercised displacement commitment, with maximum sampled commitment
distance 78-99 pixels; one victory did not need it. Because three of these runs
won, low command-vector net/path alone is not a reliable movement-failure label.
The telemetry needs actual position/displacement, danger context, boss HP, and
time-to-kill before another movement repair is justified.

## Current strengths

1. **High-offense builds are genuinely strong.** V79's three victories paired
   5.3k-6.9k estimated DPS with controlled sustained density. The strongest
   v72/v77/v79 evidence consistently favors offense margin over excess defense.
2. **Defense can be modest without being the binding failure.** Successful
   builds often sit well below the display-only 300 defense target. Defense
   score itself does not separate v79 wins from the loss.
3. **Sustain overspending is substantially controlled.** V79 completed runs
   finished at sustain 8-12 rather than the 18-27 pre-pivot failure shapes.
4. **Weapon upgrades are finally visible to policy and telemetry.** Tiered SMG,
   revolver, shotgun, Laser Gun, Shredder, Minigun, and Catling contributions
   are no longer invisible to the offense threshold.
5. **Rare acquisition is operational and safe.** Minigun/Catling locking,
   banking, lower-tier replacement, expiry, and purchase paths work without the
   v78 loop. Rare weapons are accelerators, not the whole strategy.
6. **Operational reliability is mature.** Repeating watchdog triggers,
   checkpoint/resume, scoped process ownership, telemetry completeness, crash
   checks, and shop/combine safeguards have remained clean.
7. **The policy is auditable.** HUD and event telemetry now expose offense
   components, weapon DPS/tiers, defense layers, adaptive target inputs, shop
   decisions, and finale commitment state.

## Current weaknesses and uncertainty

1. **Practical clear is still modeled by a scalar estimate.** Estimated DPS can
   overrate slow/single-target/mixed weapon sets and does not fully capture
   range, accuracy, overkill, projectile geometry, targeting uptime, enemy
   distribution, or ordinary-wave versus boss damage.
2. **The adaptive target is reactive and one wave late.** P90 and peak pressure
   help, but abrupt wave-19 density changes can arrive after a deceptively calm
   prior wave. Trend/acceleration and composition risk are not modeled.
3. **The remaining v79 loss was still offense-deficient.** Determine why the
   mandatory offense path failed to close 240/265: lack of offers, materials,
   low-value purchases, weapon replacement logic, level-up choices, or target
   rising faster than attainable offense.
4. **Wave-20 observability is inadequate.** We cannot cleanly distinguish boss
   timeout, boss HP remaining, crowd timeout, low damage uptime, or movement
   exposure. Add evidence before tuning the controller again.
5. **Movement translation remains suspicious but not proven causal.** Actual
   displacement commitment improved the old reversal bug, yet measured
   distances remain below 120 pixels and low-HP finales still occur. Wins show
   this is not sufficient evidence for a broad movement rewrite.
6. **The shop policy has accumulated interacting layers.** Scoring, mandatory
   offense, hard caps, utility expiry, premium weapon locks, rare workflows,
   and cycle guards are safe now but difficult to reason about. Look for a
   simpler invariant or decision ordering that preserves behavior and reduces
   edge-case surface.
7. **The any-ranged-gun pool can dilute synergy.** Off-plan Laser Gun, Pistol,
   and Shredder warnings are intentionally informational. Do not recommend
   narrowing the pool merely because a family is off-plan; prove whether
   composition dilution, rather than valuation/upgrading, predicts failures.
8. **The sample is small.** V79's 3W/1L and 13.35 victory-density mean are
   promising but not a replacement certification. Separate signal from luck.

## Analysis requested

1. Reconstruct a compact v69-v79 outcome/lesson table and verify the lineage
   above against reports and raw events.
2. Compare certified v72 victories/defeats, v77's seven completed runs, and the
   four completed v79 runs. Focus on offense margin relative to the current
   adaptive target, practical density, weapon composition/tier progression,
   materials and reroll reach, defense layers, hit chains, and finale behavior.
3. Perform a decision-level postmortem on `run_1784633480_66139`. Explain why it
   failed to meet 265 offense, identify the highest-cost missed opportunities,
   and determine whether the terminal result is best explained by boss-clear
   damage, ordinary density, movement exposure, or another measurable cause.
4. Evaluate whether v79's adaptive target should be retained, recalibrated, or
   replaced. Consider density trend/acceleration, recent clear rate, weapon
   crowd-clear topology, boss-specific DPS, and uncertainty. Avoid inventing
   precision that current telemetry cannot support.
5. Specify the smallest telemetry additions that would most improve the next
   decision: boss HP/IDs, wave time remaining, kills or spawn-minus-living
   throughput, player position/net displacement, damage dealt by weapon, target
   uptime, or other fields. Rank them by diagnostic value and implementation
   risk.
6. Review the shop decision architecture for conflicting layers. Determine
   whether a simpler ordered policy (hard safety -> sustain caps -> rare weapon
   opportunity -> mandatory offense -> ordinary score/utility) would be safer
   and more effective than more coefficients, or whether the current ordering
   should remain.
7. Rank 3-5 possible improvements by expected win-rate impact, evidence
   strength, implementation risk, and overlap with existing policy dimensions.
8. Recommend **exactly one focused v80 change**. Give precise rationale, code
   touchpoints, tests, telemetry fields, acceptance metrics, and rollback or
   falsification evidence. Do not implement it.
9. State whether the next evaluation should be a short A/B comparison or a full
   certification-scale run, and justify the minimum useful sample.
10. Cite run IDs and event sequences wherever possible. Clearly distinguish
    direct evidence, reconstruction, and inference.

## Guardrails

- Analysis only. Do not edit files or external state.
- Do not restart v79, create v80, launch Brotato, enable watchdogs, start WP2,
  or commit.
- Preserve v72 as the certified baseline unless a future full campaign proves
  a replacement.
- Do not score `run_1784635773_172`; it was intentionally interrupted.
- Preserve the any-gun experiment unless evidence strongly supports a pool
  change; separate pool dilution from scoring/upgrade errors.
- Blood Donation and Ball and Chain remain vetoed.
- Sharp Bullet is net-positive for this zero-piercing baseline and is not a trap.
- Preserve combine invariants: six slots before combining, upgradeable
  non-max-tier pair, at most one combine per shop visit, deferred dispatch,
  visible mouse, at least 1000 ms before confirmed state change, mouse restore,
  and never combine equal max-tier IDs.
- Preserve the bounded lock-transition guard even if you recommend simplifying
  shop policy.
- Treat off-plan gun-family and early zero-projectile warnings as informational
  when telemetry is otherwise healthy.
- Do not claim the HUD fix is visually proven; source tests, package parity, and
  deployment passed, but live visual confirmation is deferred until the next
  authorized launch.

Return: (a) a concise evidence table, (b) your diagnosis of the current agent,
(c) telemetry gaps, (d) ranked improvement options, and (e) the single
recommended v80 change with acceptance and falsification criteria.
