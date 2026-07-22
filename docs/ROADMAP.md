# Roadmap (project copy)

See also the director master roadmap. Work Package status:

| Milestone | Status |
|-----------|--------|
| M0 Environment audit | Complete (WP1) |
| M1 Deterministic teacher + telemetry | **Complete** — v72 certified 18W/2L; v92 promoted; repository/safeguard closeout passed |
| M2 Learned combat (WP2) | **In progress** — combat capture validated; v110 hold-horizon qualification and clean collection next |
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
