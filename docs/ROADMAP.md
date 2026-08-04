# Roadmap (project copy)

## North stars

Two terminal objectives, in order. Both are the game's own definition of success — binary and
un-gameable, not proxies this project invented. That property is the point: this project's
documented failure mode is over-reading its own metrics, and a win is not a metric you can
select your way into.

**North star 1 — win a Danger 5 run.** (Stated 2026-07-30, `reports/wp2/pro_brief_20260730_danger5.md`.)

**North star 2 — win a Danger 5 run with every character.** (Sharpened by the operator
2026-08-03, from the earlier and vaguer *"get good with every character"* — that wording had no
pass condition; this one does.)

### Distance to them, measured

| | status |
|---|---|
| D5 victories, any character | **0** |
| D5 terminal wave (`mutant`, n=16, era-stamped) | median **11 of 20** |
| D0 victories off `well_rounded` | **0/24** formal attempts across 3 characters; plus `cyborg` **0/16** |
| Characters that have ever won a run at all | **2** — `well_rounded` .395, `ranger` .625, both at **D0** |
| Roster reachable today | **43 of 50** — 7 characters locked |

### What binds each

**NS1 is clearance-limited, and that is measured** (§28, 40/40 trials, 0 censored, 0 invalid):
halving enemy health moved terminal wave **+7.375**; cutting enemy damage 25% did nothing
(−0.375) and halving it was ambiguous. Both dials were verified engaged, so the damage null is
interpretable. **The agent does not die at D5 because it is fragile — it dies because it kills
too slowly.** A defensive lever justified by *"D5 kills us"* is therefore **not licensed**.

**Latest NS1 Gate 0 (§37, 2026-08-04):** a target-free danger-aware marginal-DPS shop override has
enough structural surface (**100/409 = 24.45%**) but weak additive doses through `lambda = 4` flip
only **63/409 = 15.40%**, below the fixed 20% intervention bar. All flips improve immediate DPS and
the magnitude/planning proxies pass, so this is **score-margin-limited**, unlike the surface ceilings
in §§30/36. No campaign is licensed. A mechanism-distinct constraint/lexicographic version remains
an offline fork; simply extending lambda post hoc does not. **§38 then tested that fork:** making DPS
lexicographically decisive among incumbent-positive candidates reached **78/409 = 19.07%**, four
decisions short; median leave-one-run-out exposure was 19.04%. Every other bar passed, but relaxing
the boundary after seeing the shortfall would be threshold fishing. Return to the explicit bootstrap
fork before spending live trials. **§39 completed that bootstrap:** the documented low-dose planning
curve is `1.75×` the D0 target, but target-backed extra search at shop exit fails broadly—only
**22/133 = 16.54%** actionable exits, **18.71%** useful observed reroll yield, and median/p90 cost
**39%/98%** of remaining gold. The `2.63×` sensitivity exposes no additional exits. No live screen is
licensed; liquidity and search yield bind before target scale.

**§40 returned to the open combat-conversion gap with a genuinely joint route mechanism.** PACK 80
plus lexicographic projected in-range selection flips **15,274/23,501 = 64.99%** of analysable
wave-1–11 ranked decisions, with median conditional gain **0.25** and integrated gain **0.065** across
all route ticks. It nevertheless fails the predeclared geometry veto: median/p10 body-clearance
retention **0.726/0.516**, plus 10 newly worse subcritical choices. The unsafe controller is closed;
conversion authority is measured in the recorded action surface. The next offline gate is the fixed
0.80 clearance-retention/subcritical guard already declared by §40, not another dose sweep.

**§41 passes that fixed guarded gate.** It retains **11,457/23,501 = 48.75%** flips and
**11,457/15,274 = 75.01%** of the unguarded conversion actions, with median conditional gain
**0.2222**, integrated gain **0.0461**, and 100% preservation of projectile, body-retention and
subcritical rules. Every wave 1–11 retains a nontrivial surface, including **540/1,387 = 38.93%** at
wave 11. Exact implementation plus an in-range/low-HP mediator screen is licensed; survival benefit
is not yet measured.

**§42 rejects the live policy at the mediator screen.** Delivery was strong and interpretable:
**1,715/9,026 = 19.00%** live ranked opportunities changed across **4/4** treatment runs, median
projected gain was **0.1538**, and the live guard had **0/1,715** violations. Nevertheless realised
wave-1–11 in-range fraction moved only **+0.0097** against the fixed +0.05 bar (exact permutation
**p = 0.9429**). Low-HP exposure and HP-deficit AUC both decreased, so the policy is not rejected as
unsafe; its one-step gains simply do not persist into realised engagement geometry. No survival
campaign is licensed. Retuning PACK, retention or deadband on these runs is closed; any next combat
fork must price trajectory persistence or a direct clearance consequence with a new instrument.

**§43 identifies trajectory persistence as the failed mechanism.** Across the four fixed §42
treatment runs, 1,715 applied changes formed 1,241 episodes; **1,238/1,241** had a matched +0.60 s
future. Median episode duration was **0.051 s**, only **1/1,238** persisted for 0.60 s, and median
forward execution along the initial heading was **0.377** against the frozen ≥0.50 bar. The
one-step projection passed its separate calibration bars (median absolute error **0.071**, Spearman
**0.685**). Verdict: `TRANSIENT_REVERSAL`. The next combat fork is a bounded temporal conversion
latch with current-tick projectile/body/enemy-slack revalidation. It must first pass a separately
preregistered offline availability and safety gate; §43 licenses neither implementation nor live
trials.

**§44 cannot yet qualify or close the temporal latch because the archive instrument is incomplete.**
The stateful replay exactly reproduces §41 and keeps **8,469/8,469** visible retained steps inside all
five safety rules, with **7,548/8,469 = 89.13%** materially overriding the recorded route. But only
**9,400/12,429 = 75.63%** of active future captures are reconstructable: `baseline_kept` returns
before candidate rows are recorded and forces **2,854/4,039** conservative releases. The lower bound
reaches 0.60 s only **73/3,985** times, but the preregistered <90% rule makes this `DATA_LIMITED`, not
a policy null. The next licensed step is an observational, default-inert all-exit candidate instrument
and fixed acquisition protocol. Latch implementation and live treatment remain unlicensed.

**§45 fixes the instrument but stops on its preregistered sample-sufficiency bar.** Build 0.2.81
records all-exit revalidation geometry without changing actions: ranked-row parity is
**215,901/215,901**, living `baseline_kept` readiness **15,457/15,457**, action delivery
**9,079/9,079**, and active-future observability **6,242/6,248 = 99.904%**. The fixed four runs,
however, contain only **885** non-overlapping stateful episodes versus the declared 1,000 minimum.
Verdict `INSUFFICIENT_INSTRUMENT`; the analyzer did not compute the latch endpoints. The fixed
acquisition cannot be extended post hoc, and latch implementation/live treatment remain unlicensed.

**§46 makes the persistence mechanism objective-based and fails Gate 0.** It retains the original
threat identities for 0.60 seconds but recomputes the safest current heading every tick; no heading
or angular window persists. Archive, identity, branch, and safety controls all pass. This repairs
the temporal defect—**690/708 = 97.46%** of eligible episodes reach the horizon, with 97.34–97.59%
leave-one-run-out rates—but two frozen bars fail. The largest run contributes **275/708 = 38.84%**
against ≤35%, and median projected cohort advantage across **6,351/8,529** override steps is exactly
**0.000** against ≥0.05. A post-result denominator check finds 2,420 positive, 3,805 zero, and 126
negative override advantages. The coarse cohort objective plus safety-grid tie rule changes heading
too often without improving engagement. The exact selector is closed; no implementation or live
treatment is licensed. A strict-positive deadband would be mechanism-distinct but is now a
discovery-derived hypothesis requiring new preregistered sealed evidence.

**§47's sealed strict-benefit confirmation is `VOID`; it does not rescue §46.** Six new fixed
instrument runs completed at waves 14/3/7/10/12/10. All archive controls pass: **43,690/43,690**
fresh and instrument-enabled captures, **333,666/333,666** ranked rows, **24,171/24,171** living
`baseline_kept` rows, **14,102/14,102** delivered headings, **2,594/2,594** live conversion guards,
and **38,273/38,273** complete unique threat identities. But the valid wave-3 run supplies only
**31 eligible episodes** and **365 retained steps** against the frozen per-run minima 50/500. The
analyzer stopped at branch controls; result bars were not adjudicated, and replacement/top-up is
forbidden. An audit caught and repaired an analyzer ordering leak that had serialized endpoints
before the control return; those leaked values are not interpreted. The strict-benefit mechanism
remains unresolved and no implementation or live screen is licensed.

**NS2 additionally contains a bootstrap.** D5 is *not* difficulty-gated —
`max_selectable_difficulty` reads 5 for every character. But 7 characters are locked and every
remaining unlock is behind *"win a run with character X"* (the stat gates are measured dead), so
**characters must be won in order to be obtained** — at a measured off-`well_rounded` win rate of
0/24 on the *easiest* tier. Sequencing is load-bearing here, not incidental.

### Sequencing, and the assumption inside it

**Operator directive, 2026-08-03: pursue NS1 first — what it takes to win one D5 run is expected
to transfer substantially to NS2.**

⚠️ **Recorded as a directive, not as a finding.** This project's measured evidence on
cross-character transfer is currently **negative**, and NS2 should test it rather than inherit it:

- **§25 is a strong null** — the `well_rounded` profile port did **not** generalise beyond Jack
  (p = 0.791), with the treatment provably engaged (P 5.8e-80). Not a weak or underpowered null.
- **§27** — `cyborg` went **0/16** despite the closest profile to `well_rounded` ⇒ profile
  similarity does not predict win rate.
- **§24** worked on Jack, and Jack only (p = 0.0186).

The directive is sound as *sequencing* regardless of how that resolves: NS1 is a strict
sub-problem of NS2, it is far cheaper to measure, and it is the only one of the two with an
identified binding constraint. What is unestablished is the **size** of the transfer, not the
order of the work. Treat *"D5 capability generalises across characters"* as an open question NS2
must answer, not a premise it starts from.

⚠️ **64 build profiles covering all 50 roster characters is evidence a profile EXISTS, not that
the character plays well.** That line was carried as capability for weeks and is measured false.

---

See also the director master roadmap. Work Package status:

| Milestone | Status |
|-----------|--------|
| M0 Environment audit | Complete (WP1) |
| M1 Deterministic teacher + telemetry | **Complete** — v72 certified 18W/2L; v92 promoted; repository/safeguard closeout passed |
| M2 Learned combat (WP2) | **In progress** — teacher qualified through v125 (buy-before-reroll gate); `combat_obs_v1` shipped (387,695 samples); BC baseline `bc_v1_s1_full` qualified (4.80° teacher-val median); live student-inference path qualified (M3 smoke PASS) + Stage G ONNX byte-parity; DAgger arc complete, production student **`bc_v2_f_s1`**; residual-RL (Stage F) Phase 1 GO, Phase 2 concluded **NULL** (learned residual not shown to beat random control; iteration stopped per predeclared rule, operator fork pending). See Step 4. |
| M3 Economy planner | Reframe pending (see note 3 below) |
| M4 Robust D0 agent | Not started |
| M5–M7 Danger curriculum / expert / characters | Not started |

## Path forward (agreed with operator, 2026-07-21)

### Step 1 — Validate v92 and crown the teacher (focused repair campaign)

v84 stopped at **2W/2L** after the operator designated its fourth run as the
decision point. Both losses were wave-20 failures with ample estimated DPS. In
the timeout loss, the agent survived at 19 HP but spent 74% of the sampled
finale below the generic low-health flee threshold; the fourth run entered wave
20 at 13/59 HP, spent 100% of its 17-second finale in that path, and died. The
generic wave-17+ escape returned before the dedicated boss-range controller.

v85 then proved the dedicated finale path was active, but stopped at **0W/2L**:
both agents died within 30 seconds despite 4490/5020 estimated DPS. v86 keeps
full boss-range control while healthy and blends 55% engagement with 45% of the
proven panic/repulsion path below 85% HP. It also records boss HP and relative
position so applied damage can be measured directly.

v86 also stopped at **0W/2L**, but its new boss telemetry resolved the ambiguity:
both agents stayed within 700 units for 88–91% of their sampled finales and
dealt 11,998 / 17,668 boss damage, yet died at 8 / 5 minimum HP. Its median DPS
targets passed, so the blocking defect is finale survival rather than shopping.
v87 keeps full boss-range pressure above 85% HP, uses 35% engagement from
50–85% HP, and only 10% engagement below 50% so panic/repulsion can establish a
real recovery lane while automatic fire continues. It also fixes the active
controller snapshot to emit boss max HP, identity, and relative position.

v87 then stopped at **1W/2L**. All three runs passed the DPS/economy and safety
checks, but the two losses died on wave 20 after applying 15,075 / 17,884 boss
damage. Direct movement telemetry showed that blending the complete generic
flee vector created radial range excursions. v88 keeps the boss-range spring as
the radial authority and projects low-health threat avoidance onto the orbit
tangent, so survival chooses a safer flank without abandoning gun range.

v88 also stopped at **1W/2L**, although applied damage improved to 19,897 /
26,282 in its losses and its win killed the boss in eight sampled seconds. The
remaining range excursions occurred after the ring controller: the later
projectile-escape blend could reintroduce a full radial flee direction. v89
reprojects that final blended safe direction onto the boss ring, retaining its
safe tangent without surrendering firing range.

v89 stopped at **0W/2L** but proved the post-projectile projection held: median
boss distance was 470/480 and 87.5–98% of samples stayed within 700. The losses
then isolated a 53-range boss-contact hit under stale displacement commitment
and repeated projectile hits while orbiting near the outer firing boundary.
v90 tightens the ring, increases lateral dodge authority, and bypasses
commitment only for an immediate close-boss escape.

v90 also stopped at **0W/2L**, but it achieved the requested firing geometry:
one loss held a 433 median boss distance with 83.3% of samples inside 500. Its
180-unit emergency threshold still activated too late for measured hit chains
at 337/349/296 and 407/202 units. v91 raises that threshold to 320—inside the
firing ring—so the outward correction begins before contact without abandoning
gun range.

v91's first eligible run then lost despite 3,722 estimated DPS and 19,321 boss
damage in 30.5 sampled seconds. The firing geometry held (404 median boss
distance; 75.8% inside 500), and the override moved outward on three of four
samples inside 320. Three lethal 16-damage hits were instead sampled at roughly
350-406 boss distance, outside the trigger. v92 raises only the emergency floor
to 420, just beyond that measured charge envelope while remaining in live gun
range.

The first eligible v92 decision run, `run_1784670237_52694`, won after applying
28,745 sampled boss damage and passing both DPS bands (2,510.59 at wave 15;
3,784.59 at wave 18), economy, and safety checks. The operator's explicit
decision rule was failure -> repair/redeploy, success -> advance the roadmap.
Accordingly, v92 is promoted as the **WP2 teacher candidate** and Step 1 is
complete. The originally planned 3/4 focused campaign was not completed, so
this is an operator-designated acceptance result, not a new win-rate estimate.
The terminal HUD snapshot was overwritten by an excluded automatic successor;
runtime HUD parity is therefore unavailable, although its source assertions
pass.

The originally planned campaign was **4 runs with at least 3 wins**. v92
retains the v80/v82 impactful-offense band gate
with the recalibrated 41-win curve and ΔDPS impact test, the v83 item-allowlist
audit — 2 additions, 4 retiers — and the v84 conditional-effect guardrails;
see `reports/v83_change_record.md` through `reports/v92_change_record.md`; plus
v81 RSI telemetry. Operator chose focused
repair evidence over a full 20-run
certification for time reasons. The earlier v81 campaign was stopped at run 1
to fold in Codex's review (tier proxy → ΔDPS gate; n=8 curve → n=41
recalibration); see `reports/v82_change_record.md`.

Promotion criteria (all required):
- ≥ 3/4 wins with no new failure mode (no cycle-guard increase, no early deaths
  from over-banking or reroll starvation);
- median estimated DPS at waves 15 / 18 ≥ **1620 / 2400** (the recalibrated
  winner-median targets);
- no wave-13–16 shop exit with > 400 gold unspent while below the DPS band;
- HUD `off_dps` / `def_ehp` / `rsi` lines render correctly and match telemetry.
- RSI is **diagnostic only**, not a promotion gate (the v82 recalibration showed
  run-level RSI no longer cleanly separates wins from losses; per-wave
  components remain the postmortem tool).

If passed, v92 becomes the **teacher baseline for WP2**. Statistical honesty:
4 runs cannot certify a win-rate claim — v72 remains the formally *certified*
baseline unless a full 20-run campaign is run later; v92's promotion is on
acceptance metrics plus non-inferiority, not on a new certification.

### Step 2 — WP1 repository closeout (complete)

Per `docs/pro/Pro_WP1_judgment_and_WP2_handoff_2026-07-18.md`:
git init + initial commit, tag `wp1-baseline` (and tag the Step-1 result),
controlled defeat-path test, manual-override/emergency-stop exercise,
telemetry validation, and the 12-section WP1 report.

Closeout audit on 2026-07-22 reconfirmed the v72 certification (20 valid runs,
18W/2L, raw/CSV/Markdown parity, complete terminals, and both natural
defeat-to-next-run paths), refreshed the user-data backup and install hashes,
verified clean pinned third-party revisions, and fixed a clean-bootstrap
packaging defect. A fresh copied checkout now bootstraps successfully and runs
67/67 tests with a workspace-local pytest basetemp. On 2026-07-22 the operator
physically exercised manual override and Ctrl+Shift+Q on excluded v92 run
`run_1784677381_46728`; telemetry emitted the expected events at sequences 728
and 729 and shutdown was clean. The operator then explicitly authorized the
prepared initial local commit and local `wp1-baseline` tag. WP1 is PASS.

### Step 3 — Start WP2 (learned combat), with three packet modifications

Implementation is now in the telemetry/data-collection prerequisite. The
compatible `combat_capture` v2 envelope and provisional `combat_obs_v1`
capacities are implemented and load-tested. Captures from v92-v104 exposed and
repaired teacher-label defects including voluntary finale corner stalls, a late
transform overriding projectile avoidance, soft wall recovery replacing the final
projectile-safe command, held movement crossing the hard wall margin between
decisions, the wave-17–19 low-health early return bypassing the final
projectile/wall safety stack, the ordinary full-health wave-17 path bypassing
the same predictive wall tail, wall-recovery hysteresis that released before
opening usable space, recovery lanes that failed to improve the limiting wall,
and wall recovery overriding crowd avoidance because its lane scorer omitted
ordinary enemies. The operator stopped v96 after four accepted runs and
requested that wave 20 no longer preserve a boss-range ring. The first v97 run
then exposed the low-health late-wave wall bypass and was excluded together with
its partial successor. The first v98 run exposed the remaining full-health path.
Subsequent v99-v104 runs iteratively qualified the ordered projectile, hard-wall,
and recovery constraints; v104 then stopped at 5/20 when a wave-17 defeat proved
that its wall-improving selector could still choose a denser enemy path over a
safer wall-compatible lane. v105 added predictive ordinary-enemy lane filtering,
but its isolated smoke exposed two avoidable boss-contact paths because wall and
projectile clearance remained lexically above predicted body clearance. v106
added contact-clearance tiers inside the wall and projectile selectors, but its
winning isolated smoke proved that the final wall clamp could reintroduce an
unsafe body path and that ordinary late movement still lacked a final body gate.
v107 added a post-clamp body-safety pass that preserves projectile tiers and
active wall recovery while rejecting avoidable pack entry. Its first exact-20
run passed every body and wall invariant but exposed a remaining ordering gap:
active wall recovery reduced the projectile reference used by final body repair,
allowing a 77.5-unit clearance concession immediately before 20 damage. The
same frozen decision also chose a body lane 8.4 units worse than the best
available escape, matching the observed path through the pack. v108 anchors
the ordinary projectile concession to the already-emitted escape. If that
strict tier predicts body overlap, it may broaden only as a body emergency and
must stay within five units of the best available body lane. The first v108
exact-20 source reached wave 20 with complete telemetry, but its mandatory audit
rejected one active body repair: a doubly clamped outward sample silently used
the generic arena-center fallback, producing a 26.6-degree command outside the
24-direction sample grid. The same source also confirmed an operator-observed
pack-through decision: the only strict-safe projectile lane offered 61.5 body
clearance, while a lane costing 45.6 projectile-clearance units remained above
panic and opened 86.5 body clearance. v109 removes non-sampled clamp fallbacks
and permits that bounded body escape only for a gain of at least 20 units,
requiring the final choice to stay within five units of the best body lane. A
The second v109 exact-20 source then exposed four wave-20 captures where a
command that was safe at its 20 Hz decision origin no longer passed a fresh
300 ms projection on the intervening 60 Hz ticks. The player did not cross the
hard margin, but the stronger continuous hold contract correctly rejected the
source. v110 extends the decision-time projection by one full 50 ms recompute
interval, preserving a 300 ms safety reserve throughout the hold. Operator
review of that terminal sequence also identified a route through the pack;
frozen capture 21282 retained only 124.9 body-clearance units despite a
same-projectile-tier sampled lane with 182.6. v110 therefore requires ordinary
wave-20 body lanes to retain up to 160 clearance units when the same projectile
tier exposes them, staying within 20 units of the best lane below that cap and
preserving the existing 45-unit contact-safe floor. Waves 17-19 remain
unchanged. A fresh v110-only 20-run capture set is the primary dataset source;
earlier captures remain immutable diagnostic evidence and are not silently
mixed into it.

v110 then lost its own smokes and the qualification chain continued: v111's
smoke won but its successor v112 died on wave 20 through an operator-observed
pack route (relief activating too late; `run_1784763667_57757`). v113 started
wall-body relief at 140 clearance and applied the final body gate to every
wave, but its smoke exposed that gate missing outside waves 17-20 and was
stopped mid-run. v114 extended the gate campaign-wide; its winning smoke was
rejected for two relief-reference faults, which v115 repaired by comparing
hard-safe lanes against the more dangerous of the strict-pool best and the
emitted baseline. The v115 smoke (`run_1784768114_34909`) won wave 20 with
zero violations under the then-current audit. A 2026-07-23 stewardship review
of that "clean" run proved both clearance primitives sampled time discretely
(120 ms steps) and therefore could not see fast threats crossing the
commanded path between samples: every wave-17/19 contact hit and all four
wave-20 projectile hits in the smoke trace to this blindness, and the audit
mirrored the same formula, which is why it passed. v116 replaces both
primitives with the continuous closed-form closest approach, mirrors the
audit, adds continuous damage-route gates, and revokes the v115
qualification; see `reports/wp2/v116_route_quality_stop_repair_report.md`.
The exact-20 dataset campaign starts only after a v116 isolated smoke passes
the new gates.

The v116 smoke (`run_1784771165_61226`) validated the continuous metric
(perfect diagnostic parity, no route-crossing damage, cleaner waves 1-19)
but died on wave 20 and was rejected. Two defects: finale capture/decision
phase misalignment made wave-20 freshness a per-run coin flip (v116 drew
0/496 fresh, silently skipping fresh-gated audits on the fatal wave), and
the 140-unit wall-body-relief trigger was a knife edge (references
140.7-151.1 while hard-safe lanes offered 75-212 more). v117 emits finale
captures on the recompute tick, extends the relief trigger to 200, and adds
an audit gate rejecting any non-fresh finale capture; see
`reports/wp2/v117_relief_alignment_stop_repair_report.md`. A v117 isolated
smoke gates the exact-20 campaign.

The v117 smoke passed every gate (first fully clean smoke under honest
metrics; its wave-20 defeat is acceptable demonstration evidence) and the
exact-20 campaign began. It was halted after run 2/20: run 1 won, but the
operator observed run 2 starving — over-cautious movement leaving currency
uncollected — and it died on wave 16 at 79% of the DPS target. Economy
comparison across v110-v117 confirmed a danger-conditional starvation loop
(density suppression zeroes loot attraction; safety lanes carry no loot
term) predating v116. v118 adds the operator-directed bounded loot dash
(window-tested, HP-gated, time-boxed, hard-wall/projectile floors never
waived) with dash-aware audit gates; see
`reports/wp2/v118_loot_dash_change_record.md`. All v117 runs are excluded;
a v118 smoke gates the fresh exact-20 campaign.

Evidence-driven modifications to `Grok_4.5_Brotato_Work_Package_2_Prompt.md`
(operator/director approval required — the directive says "unchanged", so these
are recorded here as the operator's amendments):

1. **Telemetry prerequisite (blocking):** add player/enemy/projectile positions,
   boss HP/IDs, wave timer, and net displacement to telemetry and validate them
   BEFORE harvesting the ≥200k teacher transitions — current telemetry records
   no positions, so the transition dataset cannot be built as specified.
2. **D0 gate expectation reset:** v77–v81 evidence shows movement is not the
   dominant D0 loss cause (shopping/DPS is), so learned combat should target
   **parity** on the 20-run D0 gate; add a small non-gating Danger-1 probe
   (~10 paired episodes) to the sealed benchmark to measure WP2's value where
   it actually lives (projectile-dense higher dangers).
3. **RSI integration:** the paired teacher-vs-learned benchmark reports RSI
   components (Control at fixed Power isolates movement quality), and RSI is
   available as the dense shaping reward for the bounded residual-PPO stage
   (terminal win/loss remains the true objective; see
   `reports/v81_change_record.md` for Goodhart caveats).

Note on M3: WP1's v73–v81 shop-policy work plus RSI partially covers the old
"economy planner" scope; reframe M3 as a learned shop *ranker* (shadow-mode
first) over the existing deterministic safety rails.

### Danger-level policy

No danger tuning until M5. One exception after Step 1: a **5–10 run Danger-1
diagnostic batch with zero tuning**, purely to measure teacher generalization
and failure modes — input for the WP2 benchmark design and the M5 curriculum.
D0 winner-trajectory curves (`OFFENSE_DPS_TARGETS_BY_WAVE`,
`DEFENSE_EHP_TARGETS_BY_WAVE`, RSI) are D0-calibrated and must be re-derived
per danger level when the curriculum starts.

### Step 4 — WP2 learned combat: capture → BC → live inference → DAgger (2026-07-24)

This is the model-side continuation of Step 3, all still within the top-table
milestone **M2 (Learned combat, WP2)**. It carries its own internal
sub-milestone numbering — **M2 BC baseline / M3 student inference / M4 DAgger /
Stage F residual RL** — which is orthogonal to the top-table M-numbers and is
used in the design notes and commit history.

**Teacher frozen (v118 → v125).** The deterministic teacher continued its
stop-repair chain past the v118 loot dash: v119–v122 closed loot-stall and
crossing-tier route defects, and v123–v125 settled the shop ordering rule. v125
adds a hard reroll gate — while offense-deficient with a gate-clearing offense
item affordable on the board, the reroll action is disallowed outright (paid and
free) — and qualified with zero safety violations and zero rerolls past a
qualifying offense item (`reports/wp2/v125_change_record.md`). Policy
`teacher_v1-0.1.125-gun-wp1`, mod `0.2.33`. This is the frozen expert whose
20 Hz movement was captured.

**M2 — behavior-cloning baseline.** The `combat_obs_v1` transition dataset
(387,695 samples) was harvested from v122-era teacher runs and the BC policy
(`BCPolicyV1`, 651,202 params) trained offline. `bc_v1_s1_full` qualified as the
baseline: **4.80° teacher-val median angular error** (`models/registry/
bc_v1_s1_full.json`). Selection was made on a change-frame gate; see the memory
note. Weak spots at qualification: wave-20 / high-risk strata (median 18–31°).

**M3 — student inference (QUALIFIED; `reports/wp2/m3_change_record.md`).** A
loopback Python torch-CPU sidecar serves `bc_v1_s1_full` over a versioned
length-prefixed protocol; a Godot bridge (`learned/*.gd`, mod `0.2.34`,
`student_enabled` default-off) sends the raw capture payload per 20 Hz tick,
polls with a 40 ms deadline, and falls back to the teacher on any fault. The
validation ladder passed end to end: 337 unit tests; replay parity **exact 0.0
over 81,790 val ticks**; latency p99 model 2.07 ms / e2e 3.48 ms offline
(19.3 ms live); one isolated live smoke (`run_1784859783_62364`) **infra PASS** —
97 % student control, kill/reconnect, manual override and E-stop all verified
live, zero nonfinite/malformed, full label integrity. Behavioral quality was
explicitly out of scope, deferred to M4.

**Stage G — ONNX path (`a29fc8a`).** `bc_v1_s1_full` exported to opset-18 ONNX;
§14.1 parity gate **max |Δ| 1.13e-06 over 10,000 fixtures** (~88× margin) behind
the unchanged protocol. Torch-CPU remains the default and sole live-qualified
backend; a live ONNX smoke is deferred pending operator authorization. ORT
1.27.0 / onnx 1.22.0 pinned.

**M4 — DAgger arc (CLOSED; `reports/wp2/m4_change_record.md`).** Three
corrective rounds, zero mod changes (the capture stream already yields the
`(student-state, teacher-counterfactual)` pair):

- *Round 1* discovered the central negative result: on its own visited states
  `bc_v1` scores median **71.5°** (≈ `copy_previous` 74.6°, negative high-risk
  cosine) — the 4.80° offline figure was **copy-through-inflated**. Selection
  gates were revised (operator-delegated) to a dual-distribution form and then
  frontier-adjusted on 8 trained points; sole qualifier **`bc_v2_f_s1`**
  (`combat_dagger_r1`, 78,874 rows).
- *Round 2* produced the **first student victory** (wave 20) under `bc_v2_f`;
  gates were made **relative** (beat predecessor median ≥25 %, beat
  copy_previous ≥1.5×, cosine >0 every stratum); `bc_v3_a_s1` was offline-
  selected, dominant on the unbiased r2 holdout (`combat_dagger_r2`, 116,269
  rows).
- *Paired eval* settled promotion: `bc_v3_a`'s offline dominance did **not**
  translate live (median wave 16.5 / 0 victories vs `bc_v2_f` 20.0 / 1 victory)
  → **RETAIN `bc_v2_f_s1`** as the production student. Mechanism (telemetry-
  only): **risk-exposure attrition, not imitation error** — `bc_v3_a` is a
  smoother, less-evasive mover that agrees with the teacher *more* while losing,
  a ~45× higher low-HP rate in waves 6–10. Lesson banked: live behavioral
  screens must enter selection earlier. `bc_v3_a`'s runs seeded
  `combat_dagger_r3` (93,203 rows) for the next aggregate.

**Stage F — bounded residual RL, Phase 1 design adopted (operator-approved
2026-07-24; `.tmp/wp2_stage_f_residual_design.md`).** Two packet amendments
approved ("your recommendations for both"):

- **F-1 (geometry):** replace the radial-clamp residual with a **bounded angular
  correction** — `executed_dir = rotate(teacher_dir, θ_max·tanh(z))`, magnitude
  preserved (unit-or-zero). Basis: the M4 mechanism finding located the live
  failure axis in magnitude/sluggishness; angular-only correction removes that
  axis by construction and eliminates the magnitude-clamp intervention class.
- **F-2 (learner):** replace the PPO-first mandate with an **off-policy residual
  actor-critic (RLPD-style, replay + teacher-data mixing) primary**, PPO at most
  a final fine-tuner. Basis: single real-time instance, ~1M transitions ≈ 14 h
  wall clock; on-policy sample hunger would burn that budget.

Phase 1 is symmetric micro-residual (±5°) support collection under the shield —
**no training, no improvement claims** — to create residual-support data,
measure local effect estimability, validate the angular geometry live, and
produce the matched random-residual control required by later comparisons. A
go/no-go gate (250–300k live steps) precedes any Phase 2 critic/actor training.

**Stage F — Phase 1 complete, GO (`3ac0dc4` probe sidecar, `e459623` verdict).**
The residual-probe sidecar mode applied the Amendment F-1 bounded-angular geometry
(`executed_dir = rotate(teacher_dir, θ_max·tanh(z))`, θ_max = 5°) as a symmetric
uniform random perturbation under the teacher shield — no learning. Six probe runs
produced the residual-support dataset and, critically, the **matched random-residual
control** every later comparison is scored against. The go/no-go gate returned **GO**:
the angular geometry was validated live (magnitude preserved, bounded, no saturation
pathology), local effect was estimable, and the ±5° dose-response was monotone —
evidence that headroom exists at the bound. `bc_v2_f_s1` continued as the live student
throughout (probe rotates the teacher's action; it is not an independent policy).

**Stage F — Phase 2 (bounded residual actor-critic; CONCLUDED NULL 2026-07-25;
`reports/wp2/stage_f_phase2_change_record.md`).** An off-policy TD3-style residual
actor-critic (F-2 learner) trained on a growing replay pool assembled from the
telemetry joins, learning a state-conditional residual `δ = 5°·tanh(z)` on top of the
frozen `bc_v2_f_s1` trunk (zero-init: the untrained actor reproduces the teacher
exactly). The predeclared design fixed a single decision surface: at ~250–300k
cumulative residual ticks the learned residual must **beat the matched Phase-1 random
control** on damage-taken and wave outcomes, else stop and report.

- **Infra + rungs 1–3 (`b644be2`).** Twin-critic TD3, `reward_v2`, replay assembly
  (n-step-5, recovery exclusion, teacher-`δ`=0 mixing for the actor regularizer),
  actor serving mode. Critic converged on 107,340 probe transitions but the
  state-averaged Q dose-response was ~0 (−0.0019) — no constant directional bias,
  consistent with teacher cancellation; value is state-conditional, decided live.
  Zero-init serving reproduced the teacher exactly over 1,200 payloads. 425 tests.
- **Iterations 1–2 + null diagnostics (`c6dee5e`).** pi1 (smoke w19 + batch
  w20 / w20-victory / w19) and pi2 trained on the 183k-transition pool were gate-clean
  but their residuals **collapsed toward zero**. Diagnostics implicated the regularizer,
  not a value null: the `λ₀ = 0.01` L2-to-zero drove the collapse (`λ`→0 restores ~2°
  residuals), while the critic's small state-conditional advantage (p99 0.018 vs |Q|
  0.075) was concentrated precisely in `bc_v2`'s weak strata (wave 20: 37 % of states
  advantaged; risk ≥ 0.75: 38 %) — coherent with the M4 mechanism finding. Offline
  cannot separate real improvement from critic error; the live control decides.
- **pi3 two-arm selection (`67d1d29`).** A backward-compatible `--actor-l2` knob
  retrained two arms differing only in `λ₀`. Both passed all offline gates; **stratified
  |δ| decided**: arm A (`λ₀ = 0.001`, sha `689C1C64…`) concentrates residual mass **7.0×
  in wave 20 / 7.5× in risk ≥ 0.75** (the critic-advantaged strata) with near-zero
  residual on the low-risk early manifold, while arm B's extra magnitude is off-target
  baseline drift. **pi3 = arm A**, state-selective where the advantage lives.
- **Checkpoint tooling (`770e5d8`).** Comparison tool with **full capture-stream damage
  accounting** as primary (every hp-drop between consecutive captures, heal-clamped,
  wave/risk-stratified, 10k bootstrap CIs) after the RL-usability filter was shown to
  zero the damage of a recovery-heavy 18-damage victory run; the filtered view is
  retained only as a labeled `rl_usable_view` diagnostic. Full-stream matches the mod's
  `player_damage` ground truth on all 10 pool runs; a 3v3 control-vs-control validation
  straddled zero on every readable stratum. Plus an auditable `wp2_set_student_pin.py`.
- **Live evidence (`24a0027`).** pi3 **smoke PASS** (defeat w17, ≥15 bar, serving clean).
  Batch-1: r1 w19 (operator-observed rich shop exits w10/w17/w18 → teacher-owned v126
  evidence, `v126_evidence_rich_exit_w10.json`); r2 w13 **tripped the predeclared
  wave-15 bar → campaign aborted**. The abort investigation
  (`residual_pi3_wave13_abort_investigation.json`) cleared the pi3 mechanism (serving
  clean at |δ| p50 1.01°, economy fully converted, and the corner pattern present in the
  random control too), ruling the run training-valid and **not** disqualifying on n=1;
  it also set the escalation rule: **any further sub-wave-15 run stops iteration**. A
  machine-load covariate was recorded (STS2 12→8 workers;
  `residual_checkpoint_load_covariate.json`) — the learned arm was collected loaded, the
  control unloaded.
- **pi4 iteration 4 (`f92b514`).** Batch-1 finished w20-victory (damage 76, cleanest
  student-path win to that point). pi4 (`λ₀ = 0.001`, seed 4, sha `16414822…`) retrained
  on the 14-run / **247,510-state** pool; all offline gates pass. Batch-2 served pi4 and
  went **3/3 victories** (damage 107 / 135 / **22** — the cleanest 20-wave run ever
  recorded in this project).
- **§6 checkpoint — NULL verdict (`e9b358a`; `reports/wp2/residual_checkpoint_verdict.md`,
  `residual_checkpoint_compare_v1.md`).** Learned (7 runs) vs matched random control
  (6 runs) on the predeclared full-stream surface: **every CI straddles zero** — victory
  rate +0.238 [−0.262, +0.714], final wave +0.26 [−2.41, +2.76], overall damage rate
  +0.00004 [−0.00002, +0.00010], wave-20 damage −0.00039 [−0.00171, +0.00076],
  risk ≥ 0.5 damage +0.00024 [−0.00135, +0.00187]. **The learned residual is not shown to
  beat random perturbation.** Per the predeclared rule, growing-batch iteration **stops at
  this checkpoint**. Honestly recorded but not adjudicated: point estimates favor the
  learned arm (4/7 vs 2/6 victories) and the within-arm pi4 3/3 trend and the load
  confound both argue the test was underpowered — none resolved at this n.

All 13 checkpoint runs are **residual-teacher-base control (§14.3)** — the teacher policy
with bounded angular rotation of its combat-movement action, shop/economy fully
teacher-owned; **no independent-policy claims**, and **no production change**:
`bc_v2_f_s1` remains the qualified live student, machine restored idle.

**Fork pending (operator decision; iteration halted meanwhile).** Four options recorded
in the verdict doc: (1) extend n under a new predeclared, load-matched design with
victory-rate as the primary endpoint (the pi4 trend + load confound argue underpower);
(2) a larger θ (Amendment F-1 revision — 5° may bound the effect below detectability,
and the dose-response was monotone); (3) temporally-extended / state-dependent sustained
residuals (single-tick rotation is capped by the ~10–20-tick teacher-cancellation decay
the probe measured); or (4) redirect effort to the **shop layer**, where this session's
live observations (rich exits w10/w17/w18, ~1,200 g banked into a w19 death — the classic
WP1-era offense-starved loss signature) show large, legible, deterministically-fixable
headroom (v126 candidate).

**Next:** operator selects among the four Stage F forks (or redirects to the shop layer);
`bc_v2_f_s1` remains the live student in the interim.
