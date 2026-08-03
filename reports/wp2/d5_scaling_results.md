# §28 Results — D5 failure is CLEARANCE-limited

**Campaign complete 2026-08-03, 40/40 trials.** Pre-registration:
`d5_scaling_intervention_prereg.md` (§28a-h, plus the §28i corrections recorded at 22/40 **before any
outcome statistic existed**). Analysis: `scripts/wp2_d5_scaling_analysis.py`; dose readback:
`scripts/wp2_d5_scaling_manipcheck.py`. Raw output: `.tmp/d5_scaling/results.txt`.

## 1. Validity counts — reported before any outcome, per §28f(b)/§28g

| arm | n | valid | censored | invalid | unrecoverable | @wave 20 |
|---|---|---|---|---|---|---|
| control | 8 | 8 | 0 | 0 | 0 | 0 |
| H75 | 8 | 8 | 0 | 0 | 0 | 1 |
| H50 | 8 | 8 | 0 | 0 | 0 | 3 |
| D75 | 8 | 8 | 0 | 0 | 0 | 0 |
| D50 | 8 | 8 | 0 | 0 | 0 | 0 |

**Zero technical failures across the whole campaign.** No arm reaches the §28g ceiling bar (H50 is
3/8 = 37.5% at wave 20, below 50%), so effects are reported as point estimates, not bounds.

**Apparatus certified 40/40**: `character_mutant`, `danger 5`, `mod_version 0.2.73-wp2-capture`, era
**179/48/2018397571 constant — no drift**, `movement_estop_enabled false`. Certification is taken from
proven-varying primitives (`danger` reads 0 and 5 across 441 archived runs; `character_observed` takes
12 distinct values), **not** from `danger_ok`/`character_ok`, which are never observed FALSE anywhere
in the archive and therefore carry no independent evidence.

## 2. Dose readback — both dials verified ENGAGED

**Health (effect, per-trial):** per-entity `max_hp` at matched (wave, type) cells, large-HP types.
13 of 14 health-arm trials are flat at nominal at **every** wave — H75 **0.745-0.756**, H50
**0.489-0.505**. Exact where rounding vanishes: bruiser 136→102→68, horned_bruiser 258→193→129.

**Damage (effect, per-arm aggregate):** median player HP-DROP SIZE at matched waves 2-11.

| arm | matched drops | median | mean |
|---|---|---|---|
| control | 81 | **9** | 9.47 |
| D75 | 122 | **6.0** | 6.08 |
| D50 | 169 | **5** | 5.07 |

Lower per wave at nearly every matched wave (w8: 11 / 8 / 6; w11: 15.5 / 12 / 8), and both channels
agree. ⚠️ **D50 took 314 all-wave drops against control's 84** — more hits, each smaller. This is why
gross `damage_taken` is invalid as a readback here and drop SIZE is the confound-resistant statistic.

⇒ **§28c row 4 ("dose too weak") is EXCLUDED for the damage dial.** It did mechanically what it was
built to do. The damage null below is therefore interpretable.

**Delivery, both dials:** `difficulty_readback.rundata_current_run_accessibility_settings` matches the
configured arm **exactly on all 40 trials**, `observed_danger` 5 throughout.

## 3. Primary outcome — terminal wave

Raw per-fixture series (§28e requires it printed):

| arm | f01 | f02 | f03 | f04 | f05 | f06 | f07 | f08 | mean |
|---|---|---|---|---|---|---|---|---|---|
| control | 12 | 10 | 10 | 10 | 9 | 11 | 8 | 7 | 9.625 |
| H75 | 15 | 13 | 14 | 20 | 11 | 9 | 11 | 12 | 13.125 |
| H50 | 20 | 17 | 18 | 20 | 20 | 11 | 18 | 12 | 17.000 |
| D75 | 7 | 6 | 11 | 10 | 9 | 11 | 10 | 10 | 9.250 |
| D50 | 13 | 17 | 11 | 14 | 8 | 11 | 14 | 13 | 12.625 |

Both pre-registered forms, equal standing, two-sided α = 0.05 (§28i(i)):

| arm | mean Δ | p paired (exact, 256) | p unpaired (exact, 12870) | verdict |
|---|---|---|---|---|
| **H75** | **+3.500** | 0.02344 | 0.01461 | **significant, both forms** |
| **H50** | **+7.375** | 0.01562 | 0.00078 | **significant, both forms** |
| D75 | −0.375 | 0.81250 | 0.77343 | not significant, both forms |
| D50 | +3.000 | 0.06250 | 0.02238 | **FRAGILE TO PAIRING CHOICE — not a significant finding** |

The test statistic was verified against closed forms **in both directions** before it decided anything,
independently re-derived in the primary session (17/17 against fresh brute-force enumeration).

## 4. Verdict — CLEARANCE-LIMITED, by the table fixed before data

§28c, row 1: *"`health` moves the endpoint, `damage` does not → **CLEARANCE-limited, and this is
CLEAN**. If health's benefit ran through its defensive side-effect, then reducing damage directly would
also have worked. It did not, so the benefit must be the clearance channel."*

The health ladder is **monotone and significant at both doses** (+3.5 at 0.75, +7.375 at 0.50). The
damage ladder is a **clean null at 0.75** and, at 0.50, a result the pre-registered rule classes as not
significant. This is the asymmetric cell §28c identified in advance as the informative one — and it is
the cell that makes the inference clean rather than confounded, precisely because `damage` is the
CLEAN defensive lever while `health` is not a clean offensive one.

**⇒ At Danger 5 the agent does not die because it is too fragile. It dies because it does not kill fast
enough.**

## 5. Caveats — every one of these binds

- ⚠️ **D50 is not a clean zero.** Its mean is **+3.000** with p_unpaired 0.02238; only the paired form
  (0.06250) puts it above α. The pre-registered rule classes a paired/unpaired disagreement as *not a
  significant finding*, and that rule was fixed before data — but the honest statement is *"the damage
  ladder is flat at 0.75 and ambiguous at 0.50"*, not *"damage does nothing."*
- ⛔ **The dials are NOT unit-commensurable.** `health 0.5` and `damage 0.5` are not equal-strength
  interventions. **No claim of the form "clearance matters N times more than survival" is licensed** —
  only flat-vs-steep.
- ⚠️ **H75's unpaired p (0.01461) would not survive a Bonferroni correction across the 4 arms**
  (0.0125). **No correction was pre-registered**, so the table above is reported as specified and this
  is noted rather than applied post hoc. H50 survives any correction.
- ⚠️ **One trial's effective dose drifted mid-run.** `f06_H75` read a correct 0.756 at w5 then stepped
  to ~0.825 for w6-w9 — a clean ×1.10, **mechanism UNRESOLVED** (not the dial, not the fixture, and no
  shop item can modify enemy health). It is **retained** under intention-to-treat. Per-protocol
  sensitivity excluding it: mean Δ **4.286**, p_paired 0.01562, p_unpaired 0.00408 — i.e. **excluding it
  would have STRENGTHENED the result**, so ITT is the conservative choice and §28f's literal "exclude a
  mismatching trial" rule would have been reject-by-outcome.
- ⛔ **One character, one danger tier, one build, wave-1 entry.** Nothing here generalises to other
  characters, and this control is **not poolable with §26's** (different era, different entry).
  *External consistency only:* this control's mean 9.625 sits near §26's independent D5 mutant baseline
  of 10.56 — reassuring for the apparatus, not evidence, and the two must not be pooled.
- ⛔ **This measures WHERE THE BINDING CONSTRAINT IS, not what to build.** A dissociation identifies a
  channel; it does not identify a reachable lever. **Gate 0 still applies to anything proposed next** —
  prove a candidate flips a real decision at a reachable dose before spending.
- ⚠️ `last_wave` for the first 22 trials was seen mid-campaign while establishing cadence (disclosed in
  §28i). No analysis choice was made from it: the paired/unpaired contradiction resolves to *report
  both*, and the censoring rule was fixed by §28f's own prior text.

## 6. What this does and does not license next

**Licensed:** work aimed at CLEARANCE at D5 — killing faster, not surviving harder. The wave-17 line
already identifies OFFENSE as the separator ([[brotato-wave17-offense]]), and
[[brotato-arena-population]] records D5 clearance as uniformly deficient rather than progressively
collapsing; this result is the causal version of both.

**Not licensed:** any defensive lever justified by "D5 kills us". Reducing incoming damage by 25% did
nothing measurable to terminal wave, and halving it produced an ambiguous result — while the same
intervention verifiably shrank every hit taken.
