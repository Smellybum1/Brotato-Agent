# §26 — Matched D0-vs-D5 pair, pre-registration

Written **before** collection, 2026-08-02. Supersedes nothing; §25 is closed.

## §26a Why this exists

The recorded claim *"entry offense does not predict D5 survival (rho = −0.117, p = 0.62), a
dissociation from wave 17"* is **retracted as unreproducible** — verified in the primary session:

- `-0.117` occurs nowhere in the repo; no script, no command line, no landmark definition.
- The one committed offense definition (`wp2_jack_port_mechanism.py:119-134`) samples at the first
  capture of wave 10/15/17 and is **explicitly survivor-selected**. D5 terminal waves span 6-14, so
  waves 15 and 17 are reached by **0/20** runs.
- **All 35 D5 runs in the archive predate `unlock_pool`** (builds 0.2.59/0.2.60/0.2.61; the stamp
  first appears at 0.2.63). Scanned all 2,113 summaries: danger distribution {0: 2078, 5: 35},
  **D5 runs with an era stamp: 0**.

⇒ There is **no era-stamped D5 data in existence** and **no matched D0 set on the same
character+build**. This campaign is the first valid measurement, not a refinement of one.

## §26b Design

| | |
|---|---|
| character | **`character_mutant`**, both arms |
| arms | **danger 0** and **danger 5** |
| n | **16 per arm**, fixed |
| build | **`0.2.73-wp2-capture`**, port **INERT** (`EXPERIMENT_PORT_WR_PROFILE_TO := ""`) |
| era | **177 / 46 / `2286319327`**, asserted per run |
| prefixes | `[weapon_pistol, weapon_smg, weapon_revolver, weapon_shredder, weapon_crossbow, weapon_laser_gun, weapon_]` — the §25 list, which resolved mutant to `weapon_smg_1` (RANGED) on all 16 §25 runs |
| `movement_estop_enabled` | **false** |
| stopping | **fixed n; NO `--stop-on-win` anywhere** (§22) |

**Why mutant.** Era safety is *empirically proven*, not assumed (§24's 24th lesson: a safety property
belongs to a population, not a design). §25 collected 16 mutant runs including **3 victories** and all
64 runs of that experiment stayed on `177/46/2286319327`. Its D0 terminal waves were
`[15,19,17,20,15,19,10,15]` — **spread 10-20 with only one at the ceiling**, which is the outcome
variance this design needs. Ranger wins more (5/8) but pins **6 of 8 at wave 20**, leaving nothing to
correlate against. `well_rounded` was the obvious match to the old D5 baseline but has **zero
era-stamped runs**, so its era safety cannot be verified at all.

## §26c PRIMARY — descriptive, and deliberately not a correlation

**Terminal-wave distribution and victory rate per arm**, reported with the full raw series.
Comparison by exact permutation on terminal wave, two-sided.

This is the whole point of the campaign: an era-stamped, build-matched, character-matched D0/D5 pair
that can be pooled with future work. It does not depend on resolving §26d.

## §26d SECONDARY / EXPLORATORY — the offense question, with its limitation stated up front

⛔ **The landmark problem is STRUCTURAL and collecting fresh data does not fix it.** Any offense
covariate needs a wave reached by 100% of runs in BOTH arms; any wave late enough to carry build
variance excludes the earliest D5 deaths, which is **selection on the outcome** (11(b)).

Pre-declared, so no choice is made after seeing the relationship:
- **Primary landmark: first capture of wave 5.** Offense = `sum(weapon.damage)` from the **capture's
  `payload.weapons`** (NOT the save's `weapons[i].stats` — same field names, ~3.4x apart).
- **Report the per-arm exclusion count BEFORE any relationship.** If either arm excludes >0 runs at
  wave 5, the wave-5 result is reported as **contaminated** and the verdict falls to the sensitivity.
- **Sensitivity: k = 2,3,4,6,8,10**, each with its own exclusion count. A relationship that only
  appears at landmarks with exclusions is not a finding.
- Statistic: Spearman rho within each arm; the comparison is the **difference between arms**, by
  permutation. **Report both arms' n and rho, never a difference alone.**

⚠️ **This is NOT comparable to the wave-17 result** (`wave17_death_attribution.md:45-59`), which is a
**rank-biserial 0.188** on a **binary** died-at-17 vs survived-past-17 endpoint, at D0, with the
covariate at a landmark every sampled run reached by construction. Do not report §26d as confirming or
refuting it.

## §26e Validity, asserted per run before any outcome

`character_ok`, `danger_ok` (`summary.danger` is **no longer hardcoded** — `agent_controller.gd:2628`
writes `_danger_observed_latched` from `RunData.current_difficulty` via `game_adapter.gd:202`), one
era stamp, one build, `movement_estop_suppressed`, and the opener weapon id per run.
**Any run failing character_ok or danger_ok is excluded and COUNTED in the report.**

## §26f Pre-declared interpretation

- The D0/D5 terminal-wave gap is **expected and is not a finding** — D5 is harder by construction.
  The deliverable is the matched, poolable pair.
- ⛔ **A §26d null does NOT establish that D5 failure is survival-limited rather than offense-limited.**
  An observational correlation on a compressed, censored endpoint has low power, and the landmark
  constraint biases it. Establishing that requires an **intervention** (e.g. the `enemy_scaling` dial,
  whose readback is `max_hp` by type), not a correlation. Say so rather than over-reading a null.
- ⛔ Do not pool these runs with the 35 archived D5 runs: different build, different character, and
  **those runs carry no era stamp at all**.
