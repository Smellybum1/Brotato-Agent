# Adoption record — Pro's Danger 5 strategy answer, 2026-07-30

Answer: `pro_answer_20260730_danger5.md`. Brief: `pro_brief_20260730_danger5.md`.

Pro converges with my own recommendation on the main call — **characterise Danger 5 before optimising
anything else** — and sharpens it in four ways I am adopting outright. It also contains two things I
am NOT carrying forward, recorded here so they cannot be cited back as established.

## ADOPTED — four genuine sharpenings

### 1. Fixing the hardcoded `0` is NOT sufficient qualification (adopted, highest value)
My plan was "change the literal 0, then run". Pro is right that this is an arming step without a
readback — the exact failure mode this project has on record. **A D5 run is technically valid only
when requested, selected and observed difficulty all agree.** Required per-run readback before
combat: `requested_danger`, `selected_ui_danger`, `save_difficulty_value`, the live multiplier block
(`enemy_health`/`enemy_damage`/`enemy_speed`/`nightmare_proj`), plus policy/mod version and config
hash. Preferably an **entity-level** confirmation (enemy `max_hp` by type) rather than trusting the
menu or save field — we already have that instrument from the `enemy_scaling` work.

A technical mismatch is a **technical failure, not a gameplay loss**, stays in the attempt ledger,
and is never silently retried.

### 2. Channel removal on GENUINE D5 saves beats building a D0→D5 ladder (adopted; better than my idea)
My brief proposed synthesising D5-like pressure upward from D0. Pro's design is strictly better:
collect **real D5 saves** from the dominant failure wave, then run arms `control` / `H-off` / `D-off`
/ `S-off` / `HDS-off` with **`nightmare_proj` left at its real D5 value in every arm**. This
preserves the true D5 context and asks which exposed channel is *necessary*, and how much difficulty
remains when all three are removed — which also directly measures how much of D5 the dial cannot
reach. The ladder stays, but demoted to a screening bench, explicitly **not** a D5 simulator.

### 3. Sample rule: 12 minimum, 20 maximum, extension pre-registered (adopted)
I said "~20 runs". Pro is right that an undifferentiated 20 is wasteful and that the stopping rule
must be written first or I will stop when the first 12 tell an attractive story. Extension triggers:
losses not concentrated in a two-wave band, no phenotype ≥2/3 of losses, fewer than four independent
usable saves in the dominant band.

### 4. "Offense is causal" ≠ "offense is actionable" (adopted as a standing check)
For any rescue-by-dose result, immediately compute the **required** improvement against the **maximum
plausible** gain from real shop/level/collection decisions. If a build needs +30% clearance and every
realistic policy change yields 3-5%, the mechanism is causal and **not actionable** — that closes the
path rather than justifying another scoring layer. This is the same protection that should have
stopped the v128 shop fix, which was mathematically correct and behaviourally inert.

Also adopted: **fixture-clustered inference** (fresh-RNG continuations from one save are repeated
measures of that build, not independent builds — report source count, repeats per source, per-source
rates); and the **architectural reframe** that the problem is not hand-written vs learned but
"sum a desire, then let an ordered tail overwrite it", with a hierarchical
maneuver-selector + minimal safety shield as the next policy class *if* movement is confirmed binding.

## ⚠️ NOT ADOPTED — two corrections

### A. Pro's cost table applies 2.0x acceleration to steps that may serve a learned policy
Steps 4, 5, 7 and 8 are costed at 2.0x. **2.0x is invalid for any arm that serves a policy through
the sidecar**: the inference deadline is 40 ms of REAL time against a 50 ms control period, so at
2.0x the deadline exceeds the period and the treated arm silently becomes partly untreated. This is
stated in the brief and the answer's plan does not carry it through.

**Rule:** 2.0x is fine for paired fixture campaigns whose arms are pure GDScript/save-edit changes
(with achieved/nominal ≥0.95 verified). Any served-policy arm runs at **1.0x**, and the cost doubles.

### B. One "established" bullet is fabricated
Pro's established-facts list contains: *"a maximum ±5° rotation that the teacher tends to cancel
within roughly 10-20 ticks."* **The "cancels within 10-20 ticks" clause was never measured and was
not in the brief.** The ±5° cap and the near-zero action diversity are real; the cancellation
timescale is an invention. It is plausible and worth measuring — but it is a hypothesis, and it must
not be quoted as established. Everything else in that section checks out against the brief.

## ⛔ CORRECTION TO MY OWN BRIEF — "all 1,873 runs were at Danger 0" was NOT a measurement

Found while implementing Step 0, and it invalidates the *evidence* for the headline fact I gave Pro
(which Pro then listed first under "established by the supplied evidence").

**`agent_controller.gd` built the run meta with `"danger": 0` — a hardcoded literal.** The telemetry
writer then copied it into the summary. So the summary field could not have reported anything else,
and my audit of 1,873 summaries was reading a constant. This is the structurally-uninformative-field
trap already on record three times in `brotato-measurement-discipline`.

I checked for any independent runtime read and there is **none in the historical record**:
`combat_capture` carries no danger field, and neither does `combat_tick`. (`game_adapter.gd` does
compute a real `_danger()` from `RunData`, but its result never reaches a serialized payload.)

**The conclusion still stands, on CODE-PATH grounds rather than measurement:** both fresh-run
selection paths called `_activate_and_select_danger(0)` with a literal, there is no other path that
selects a difficulty for a fresh run, and `agent_config.json` carried `"danger": 0`. Three
independent hardcodes agreeing is strong — but it is inspection, not telemetry, and it should have
been labelled that way.

**Fixed from `0.2.58`:** the summary's `danger` is the value latched from `RunData` on the first
combat tick, `requested_danger` is recorded beside it, and both default to **-1, never 0**, so
"unknown" can no longer masquerade as a genuine Danger 0 run.

## Cost caveat carried forward
Pro's fixture costs assume a wave-17-like 4.3 min trial. **The dominant D5 failure wave is unknown**;
if D5 kills the agent early, trials are cheaper and the whole plan gets faster. Pro acknowledges this.

## Next action
**Step 0**: replace the hardcoded danger selection and land the fail-closed readback, then two launch
smokes. Nothing else starts until a run can be *proven* to have executed at Danger 5.
