# v123 calibration from campaign run-5 telemetry

Read-only analysis of the first 5 completed v122 exact-20 campaign runs, to
calibrate the three v123 levers (strength tiers, early/wave-19 greed budget,
edge-rail traversal drift) before deploy. Source:
`C:/Users/moxhe/AppData/Roaming/Brotato/brotato_agent/runs/<run_id>/`
(events.jsonl + summary.json), streamed line-by-line.

## Run roster

| # | run_id | result | last wave | dmg taken | tier profile |
|---|--------|--------|-----------|-----------|--------------|
| 1 | run_1784785556_51395 | victory | 20 | 105 | strong build (S climbs to ~1.95) |
| 2 | run_1784786723_17546 | defeat | 17 | 222 | weak build, died mid-run |
| 3 | run_1784787688_32406 | victory | 20 | 166 | steady-neutral build |
| 4 | run_1784788917_7315 | defeat | 20 | 237 | weak build, lost at boss |
| 5 | run_1784790063_90333 | defeat | 20 | 55 | strong build, lost boss DPS check |

Method notes / caveats:
- S = clamp(weapon_dps / dps_target, 0, 2) from every `combat_tick`
  build_metrics.offense (0.5 s cadence; ~2100 ticks/run). Hysteresis applied
  as a state machine over the ordered per-run tick series with the exact v123
  thresholds (enter strong ≥1.25 / exit ≤1.15; enter weak ≤0.75 / exit ≥0.85).
- Corner occupancy = fraction of `combat_capture` (higher-rate control loop,
  ~21 k caps/run) with player within **280** of **two adjacent** walls
  (mirrors LATE_CORNER_GUARD_MARGIN 280). Arena is 2048×1536 per capture.
- "Edge occupancy" added = within 280 of **any single** wall (the wall-hug
  metric; see finding below on why the two-wall metric is the wrong yardstick).
- Damage taken = sum of `player_damage.amount`, attributed to the wave of the
  most recent tick. Gold entering shop N = first `gold_before` at a wave-N
  `purchase_decision`. Ground-loot count = tick `loot` (materials on field);
  saturation = fraction of ticks with ≥45 (cap is ~50; dropped_counts.materials
  = 0, so 50 is a real field ceiling, not telemetry truncation).
- Only 5 runs; run 2 has no waves 18–20. Treat all correlations as directional.

---

## 1. Strength distribution S per wave

**Median S per wave, per run** (— = wave not reached):

| wave | run1 | run2 | run3 | run4 | run5 |
|---|---|---|---|---|---|
| 1 | 1.01 | 1.01 | 1.01 | 1.01 | 1.01 |
| 2 | 1.42 | 0.93 | 1.06 | 1.01 | 0.86 |
| 3 | 0.98 | 1.17 | 1.15 | 0.76 | 1.37 |
| 4 | 0.96 | 0.82 | 1.20 | 0.80 | 1.28 |
| 5 | 0.65 | 0.57 | 1.25 | 0.72 | 1.27 |
| 6 | 0.68 | 0.81 | 1.15 | 0.80 | 1.44 |
| 7 | 0.74 | 0.75 | 1.15 | 0.72 | 1.30 |
| 8 | 0.72 | 0.75 | 1.15 | 0.56 | 1.22 |
| 9 | 0.88 | 0.63 | 1.07 | 0.53 | 1.24 |
| 10 | 0.97 | 0.68 | 1.22 | 0.55 | 1.23 |
| 11 | 1.07 | 0.73 | 1.12 | 0.49 | 1.13 |
| 12 | 1.34 | 0.67 | 1.14 | 0.65 | 0.98 |
| 13 | 1.39 | 0.89 | 1.15 | 0.68 | 1.29 |
| 14 | 1.34 | 0.83 | 1.25 | 0.87 | 1.30 |
| 15 | 1.39 | 0.99 | 1.09 | 0.85 | 1.13 |
| 16 | 1.63 | 0.80 | 1.23 | 0.75 | 0.96 |
| 17 | 1.66 | 0.91 | 1.18 | 0.85 | 1.04 |
| 18 | 1.95 | — | 1.29 | 0.76 | 0.98 |
| 19 | 1.94 | — | 1.33 | 0.82 | 1.08 |
| 20 | 1.95 | — | 1.34 | 1.16 | 1.15 |

Within a wave, weapon_dps/dps_target is piecewise-constant (updates at shops),
so per-wave p10/p90 collapse onto the median for most waves — the meaningful
spread is *between* waves and *between* runs, shown above. Global spread of the
97 wave-medians: **min 0.487, max 1.952, median 1.005**.

**Tier occupancy under v123 hysteresis** (tick-time weighted):

| run | result | strong ≥1.25 | neutral | weak ≤0.75 |
|---|---|---|---|---|
| run1 | victory | 54.6% | 26.4% | 19.0% |
| run2 | defeat | 0.0% | 48.4% | 51.6% |
| run3 | victory | 19.3% | 80.7% | 0.0% |
| run4 | defeat | 0.0% | 51.5% | 48.5% |
| run5 | defeat | 49.7% | 50.3% | 0.0% |
| **pooled** | | **25.5%** | **51.8%** | **22.7%** |

Wave-median distribution vs the thresholds: **21% of wave-medians ≥1.25, 19%
≤0.75, 61% in-band [0.75,1.25]**. 1.25 sits at ≈p79, 0.75 at ≈p19 of the
wave-median distribution — near-symmetric around the 1.005 median.

Structural note: S is dominated by **build quality (between-run)** and **run
progression (rises with wave)**, not by within-run flapping. run3 never enters
weak; runs 2 & 4 never enter strong; run5 never enters weak. The weak tier
therefore fires mostly in the mid-game ramp (waves 5–12, before the build comes
online) and strong fires late (waves 13–20). Consequence: the weak tier will
frequently **co-occur with the early-greed window (waves ≤12)** — caution and
greed stacking — which the C-section clamps (arm floor ≥0.30, window ≥20.0) are
there to bound.

## 2. Corner vs edge occupancy (waves 14–19 emphasis)

**Two-wall corner occupancy (280, mirrors corner guard) — pooled per wave:**

| wave | 10 | 11 | 12 | 13 | 14 | 15 | 16 | 17 | 18 | 19 | 20 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| pooled | 13.4% | 1.6% | 1.4% | 1.6% | 0.3% | 0.9% | 3.4% | 2.5% | 2.6% | **2.6%** | 0.6% |

The strict corner metric is **near-zero at wave 19 (2.6% pooled, max 3.8% in
run1)**. The only real corner hotspot is **wave 10 (13.4% pooled, up to 26.9%
run4 / 22.5% run2)** — the first elite/horde wave. The design's stated target
"<40% wave-19 corner occupancy" is therefore already trivially met and is the
**wrong yardstick**.

**Single-wall edge occupancy (280) — the actual wall-hug signal, pooled:**

| wave | 13 | 14 | 15 | 16 | 17 | 18 | 19 | 20 |
|---|---|---|---|---|---|---|---|---|
| run1 | 28% | 29% | 45% | 20% | 59% | 61% | **73%** | 42% |
| run3 | 23% | 25% | 29% | 9% | 44% | 38% | 55% | 34% |
| run4 | 50% | 33% | 33% | 30% | 47% | 61% | 47% | 25% |
| run5 | 16% | 21% | 37% | 12% | 29% | 55% | 47% | 30% |

Edge dwell **climbs steadily through the late game and peaks at wave 19
(47–73%)**. This — not literal corner-parking — is what the operator saw as
"corner-parking" in run 1 (73% wall-hug, but only 3.8% true corner).

**Correlations (per-wave rows, pooled):** corner_occ↔median_S = −0.18;
corner_occ↔wave_dmg = +0.13; median_S↔wave_dmg = +0.07. Restricted to waves
14–19: **corner_occ↔wave_dmg = +0.48** (n=28) — but on a base of only ~2%
corner occupancy, so low leverage. Edge dwell does **not** track damage: wave-19
damage was 3–34 across runs despite 47–73% edge dwell. There is headroom to add
traversal without a safety cost.

## 3. Collection: gold at shops, ground-loot saturation, assist items

**Gold entering shop per wave** (first gold_before; there is no wave-20 shop):

| wave | run1 | run2 | run3 | run4 | run5 |
|---|---|---|---|---|---|
| 16 | 620 | 699 | 695 | 644 | 865 |
| 17 | 603 | — | 629 | 646 | 510 |
| 18 | 556 | — | 535 | 534 | 609 |
| 19 | **722** | — | **947** | **765** | **1022** |

Wave 19 funds the richest shop of every run — **gold is not zero**. The
starvation is at the **ground-loot level**: mean ground loot and saturation
(fraction of ticks ≥45 of the ~50 cap):

| wave | run1 mean/max/sat | run3 | run4 | run5 |
|---|---|---|---|---|
| 14 | 17.2/50/16% | 11.8/26/– | 12.5/39/– | 26.0/50/– |
| 18 | 34.5/50/– | 16.3/30/– | 12.2/29/– | 37.6/50/– |
| 19 | **40.0/50/70%** | 22.0/47/3% | 28.6/50/23% | 29.2/50/22% |

Pooled loot-saturation fraction climbs 14:16% → 15:29% → 18:24% → **19:29%**,
and in run 1 (the operator's run) **70% of wave-19 ticks sat at the field cap** —
loot is generated by kills faster than it is collected, and the surplus caps
out / is wasted.

**Collection-assist item purchases (item_id @ wave bought):**

| run | items |
|---|---|
| run1 | lootworm@10 |
| run2 | baby_gecko@5 |
| run3 | lootworm@7, baby_gecko@10, baby_gecko@12, baby_gecko@18 |
| run4 | lootworm@11, baby_gecko@11 |
| run5 | baby_gecko@16, lootworm@18 |

Every run bought at least one pickup-range assist; run3 (a clean victory)
bought the most (4). No obvious cap-saturation avoidance from these — even run1
with a lootworm saturated wave 19.

## 4. Dash uptake

**loot_dash active-capture fraction, pooled per wave:** rises from ~0% (w1–4)
to a wave-9 spike (17.3%), settles ~5–9% mid-game, and **peaks late: w17 9.1%,
w18 11.3%, w19 12.5%**. By band:

| band | episodes | active-cap fraction |
|---|---|---|
| waves 1–6 | 14 | 1.2% |
| waves 7–12 | 157 | 9.5% |
| waves 13–16 | 71 | 5.9% |
| waves 17–19 | 77 | 10.8% |
| wave 20 (boss) | 0 | 0.0% |

Typical episode length is ~20–24 captures (≈ the dash duration). Dash is **not
under-firing at wave 19** — run1 fired 10 episodes / 240 active caps, run5 9 /
196 — yet loot still saturated. Cheap material-delta check: ground-loot count
does not fall across wave-19 dash episodes in run1 (stays pinned near the cap),
consistent with the agent dashing *from a fixed edge position* into a loot field
too large to clear from there.

## 5. Wave-19 focus (the operator-flagged wave)

| run | result | corner / edge | med S | dmg | loot mean/max/sat | dash | gold→shop19 |
|---|---|---|---|---|---|---|---|
| run1 | victory | 3.8% / **73%** | 1.94 | 9 | 40.0/50/**70%** | 10ep/240c | 722 |
| run3 | victory | 2.0% / 55% | 1.33 | 11 | 22.0/47/3% | 6ep/142c | 947 |
| run4 | defeat | 1.5% / 47% | 0.82 | 34 | 28.6/50/23% | 2ep/48c | 765 |
| run5 | defeat | 3.0% / 47% | 1.08 | 3 | 29.2/50/22% | 9ep/196c | 1022 |

Wave-19 signature: **very low true-corner, very high wall-hug, strong build,
low damage, saturated loot field, plenty of dash.** The pickup shortfall is a
**coverage/geometry problem (wall-dwell + spread loot), not a dash-gating or a
gold problem.**

---

## RECOMMENDATION

### (a) Do the strength tiers reach ≥1.25 / ≤0.75 often enough to matter?

**Yes — keep the 1.25 / 0.75 thresholds.** Under the exact v123 hysteresis the
pooled tick-time split is strong 25.5% / neutral 51.8% / weak 22.7%; nearly half
of combat time is in a non-neutral tier, and 40% of wave-medians fall outside
the band (21% ≥1.25, 19% ≤0.75). The thresholds sit near ≈p79 / ≈p19 of the
observed wave-median distribution (median 1.005, range 0.49–1.95) — well-placed
and near-symmetric. **No retune needed.** One structural caveat to carry into
review: S is almost entirely a *between-run build-quality* and *within-run
progression* signal (run3 never weak; runs 2/4 never strong; weak fires in the
w5–12 ramp, strong fires w13–20). So the weak tier will routinely overlap the
early-greed window (waves ≤12); rely on the C-section stacking clamps (arm floor
≥0.30, window ≥20.0) — they are load-bearing here, not cosmetic.

### (b) Is EDGE_RAIL_DRIFT 0.45 enough vs the observed corner dwell?

**The premise needs re-aiming, and 0.45 is a reasonable but likely low starting
value.** True two-wall corner dwell is already ~2.6% at wave 19 (max 3.8%) — the
"<40% corner occupancy" target is already met and is the wrong metric. The real
late-game pattern is **single-wall dwell: 47–73% at wave 19, rising steadily
from ~25% at wave 14.** The rail drift acts tangentially along the wall (only
when no enemy within RAIL_CLEAR_RADIUS 240 on the rail), so it correctly targets
edge-dwell *traversal*. At 0.45 it is ~39% of EDGE_ORBIT (1.15) and ~53% of
EDGE_BIAS (0.85) on the same tangential axis — enough to bias slide direction
and break stagnation, but modest against a 60–73% edge-dwell wave. **Deploy at
0.45, but (i) re-target the calibration metric to single-wall-280 occupancy
(goal: wave-19 < 40%, currently 47–73%), and (ii) be prepared to raise toward
~0.6–0.7 at run-20 review if edge dwell doesn't drop — staying below EDGE_BIAS
0.85 so it augments rather than overrides the orbit/bias tangential field.**
Damage is decoupled from edge dwell (wave-19 dmg 3–34 across runs), so raising
the drift carries little safety risk.

### (c) Does the wave-19 greed window (strafe 0.6, stall 8, cooldown 90) target
### the right lever?

**Partially — right direction, but it is the secondary lever; the wave-19
shortfall is coverage, not dash-gating or gold.** Wave-19 gold is the richest
shop of every run (722–1022), so the greed-window framing "starvation" is really
**surplus-loot waste**: the ground field saturates at the ~50 cap (70% of
wave-19 ticks in run1) while the agent wall-hugs and dashes from a fixed edge.
Of the three greed levers, the **strafe-loot cap raise (0.35→0.6) is the most
relevant**, because it lets the agent path toward spread-out loot while
engaging; **stall 8 / cooldown 90 are low-yield** since dash is already firing
heavily at wave 19 (12.5% active-cap fraction, 9–10 episodes/run) yet loot still
caps out. Keep the greed window, but expect the **EDGE_RAIL_DRIFT traversal
(part D) to do the heavy lifting** on wave-19 pickup, and instrument the real
success metric — **wave-19 loot-saturation fraction (currently 29% pooled / 70%
run1) and single-wall edge occupancy** — rather than gold, which is already
healthy. Validate all three at run-20 with the same script.
