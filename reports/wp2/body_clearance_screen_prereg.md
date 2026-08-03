# §31 — Gate 0 screen: does `body_clearance_scale` move engagement geometry at D5?

**Pre-registration. Written 2026-08-03, BEFORE any §31 run exists.**

## 31a. What this is, and what it is NOT

A **Gate 0 SCREEN on a MEDIATOR**, not an outcome campaign. It asks one question:

> Does relaxing the body-safety clearance requirement actually change the emitted movement command
> and move the in-range fraction toward the human band, **without** buying those targets with safety?

⛔ **A pass LICENSES a survival campaign. It never substitutes for one.** `in_range_fraction_mediator.md`
states this explicitly, and this project already has the general form on record: a defect being real
does not make it load-bearing.
⛔ **Terminal wave is NOT an endpoint here.** n=4/arm cannot resolve it (D5 within-arm sd 1.59-2.63
needs an effect ≳2.6 waves at n=16). It is reported as CONTEXT ONLY, and no outcome claim may be made
from it whatever it shows.

## 31b. Why this lever and not another

- §28: D5 failure is **CLEARANCE-limited**. Cutting incoming damage did **not** help (D75 null, D50
  ambiguous, **both damage arms 0/8 victories**) while cutting enemy health did.
  ⇒ A safety layer that costs clearance is spending on a channel measured not to pay. **Motivation,
  not a result.**
- Every previous movement lever was **structurally inert**: the safety tail owns the final command on
  50-88% of ticks, `calm_threat_mult` moved the desire +0.216 and the command +0.003, and a **6.7x**
  dose on `engage_distance_scale` moved the standoff **2.2%**, non-monotone.
- `_finale_body_safety` is the layer that **owns** the command — at D5, 67.0% of ticks. Read from
  source: its v114 comment records that it was deliberately un-gated from waves 17-20 to **"apply the
  last body arbiter on every combat wave."** ⇒ Structurally different from every dead lever.
- Endpoint already validated: human **0.4417 ± 0.0187** vs agent **0.2801 ± 0.0535**, perfectly
  separated, **d = 4.03**, on identical enemy presence (21.4 vs 20.8) — a CONVERSION gap.

## 31c. Arm and doses — fixed before data

`ranger`, danger **5**, build `0.2.75-wp2-capture`, port INERT, era **179/48/2018397571** (ranger is
era-safe: reward `item_night_goggles` already unlocked, re-verified in-save with +/− controls).
`weapon_prefixes` **pistol-first**; opener certified from `run_start.weapon`, not from disk.

| arm | `body_clearance_scale` | effective `body_slack` at wave ≤ 12 | direction |
|---|---|---|---|
| **R05** | 0.5 | 17.5 | MORE restrictive (negative control) |
| **C10** | 1.0 | 35.0 | control, inert |
| **P20** | 2.0 | 70.0 | more permissive |
| **P30** | 3.0 | 105.0 | more permissive, saturating |

**n = 4 per arm, 16 trials, fixed.** No stop-on-win, no extension, no top-up.
⭐ **The 0.5 arm is deliberate**: a dose-response that moves in BOTH directions is far stronger
evidence than one that only moves one way, and it is the cheapest guard against reading noise as
signal.
✅ **Bounded by construction:** `BOSS_FINALE_BODY_CRITICAL_CLEARANCE` (45.0) sits in the outer `max()`
and is **never scaled**, so **no dose can drive the agent inside the hard contact floor.**
⚠️ The dose rides on **`body_slack` ALONE**. Scaling the pack term too would push the two halves of the
same `min()` in opposite directions and make the dose **non-monotone** — caught in review before data.

## 31d. Endpoints, fixed in advance

**PRIMARY (mediator): per-trial in-range fraction** = mean over captures of
`(enemies within max weapon `max_range`) / (enemies alive)`, computed only on captures with ≥1 enemy
alive. Raw per-trial series printed; arms compared by exact permutation on arm means.
⚠️ Agent within-arm sd is **0.0535**, so this design sees roughly a **≥0.05** shift and nothing finer.
⚠️ `nearest_d` goes **INF (≥1e17)** on ~9.7% of captures (no target) — filter, never average.

**GATE-0 DELIVERY CHECK (mandatory, reported first):** does the dose actually reach the FINAL command?
⛔ **Not assumed.** `calm_threat_mult` self-reported fine and moved the command 0.003. Report, per arm,
the distribution of emitted `teacher.action` headings and the fraction of ticks where
`body_safety_active` is true. **If the dosed arms are indistinguishable from control on the emitted
command, the knob is INERT and the primary endpoint is not interpretable** — report that and stop.

**SAFETY VETO (pre-declared rejection rule):** fraction of captures below 70% HP, and HP-deficit AUC.
⛔ **Any arm that raises in-range fraction while ALSO raising low-HP exposure is REJECTED**, not
reported as a win. Buying targets with safety is the failure mode this screen exists to catch.

## 31e. Decision rule, fixed before data

- **INERT** — no detectable command change ⇒ the lever joins the dead list. No campaign.
- **MOVES GEOMETRY, SAFETY CLEAN** — monotone in-range gain across doses, no low-HP rise ⇒ **licenses**
  a pre-registered survival campaign at the best dose. Does **not** claim survival improves.
- **MOVES GEOMETRY, SAFETY WORSE** ⇒ REJECTED.
- **NON-MONOTONE** (e.g. 0.5 and 2.0 both above control) ⇒ treated as noise, NOT as a partial success.

## 31f. Validity gates, reported per arm BEFORE any outcome

`character_observed == character_ranger`; observed danger 5; `danger_ok` present; one build; era
constant; opener `weapon_pistol_1`; and **`body_clearance_scale` read back per trial from the run's own
meta** — the arm must be certified from the run's record, not from the config file on disk.
⚠️ `character_ok` is CONSTANT True archive-wide ⇒ **VACUOUS as a filter**; assert the observed value.
⚠️ The supervisor kills whatever run is in flight when it stops, so expect exactly one extra run
directory per arm; account for each excess individually (HP > 0 and started after the last collected
run ⇒ benign), never require a zero count — see §29f's corrected rule.
