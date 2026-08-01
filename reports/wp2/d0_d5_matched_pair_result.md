# §26 — Matched D0-vs-D5 pair, RESULT

**Verdict: the deliverable is DELIVERED — the first era-stamped, build-matched, character-matched,
opener-matched D0/D5 pair in existence. The pre-registered secondary (§26d) is NULL, p = 0.269 to
0.947 across all seven landmarks.**

Campaign 2026-08-02. 32 runs: `character_mutant`, 16 × danger 0 and 16 × danger 5, fixed n per arm.
Prereg `reports/wp2/d0_d5_matched_pair_prereg.md`; analysis `scripts/wp2_d0d5_pair_analysis.py`
(no arguments, defaults to the APPDATA runs dir). All figures below were re-run and reproduced
before writing.

**The headline is the infrastructure, not a p-value.** See "What this establishes".

---

## Validity — reported per arm, before any outcome (§26e)

| | D0 arm | D5 arm |
|---|---|---|
| n | **16** | **16** |
| `character_ok` | **16/16** | **16/16** |
| `danger_ok` | **16/16** | **16/16** |
| era tuple | **(177, 46, `2286319327`)** — one only | **(177, 46, `2286319327`)** — one only |
| build | **`0.2.73-wp2-capture`** — one only | **`0.2.73-wp2-capture`** — one only |
| danger observed | **0** (expected 0) | **5** (expected 5) |
| opener weapon | **`weapon_smg_1`**, all 16 | **`weapon_smg_1`**, all 16 |
| `estop_suppressed` | **0** | **0** |

**CLEAN: True.** No run was excluded for any reason.

The two arms are matched on **era, build, character AND opener**. The same era tuple, the same single
build string, the same character, and the same resolved starting weapon on all 32 runs.
**Danger is the only difference between the arms.** The `danger` field is no longer hardcoded —
it is `_danger_observed_latched` from `RunData.current_difficulty` — so `danger_ok` is a genuine
readback, not a restatement of the request.

---

## PRIMARY (§26c) — terminal wave, descriptive, full raw series

```
D0 raw terminal waves: [10, 10, 13, 16, 16, 16, 17, 17, 17, 17, 20, 20, 20, 20, 20, 20]
D5 raw terminal waves: [ 8,  9,  9,  9, 10, 10, 10, 11, 11, 11, 11, 11, 11, 11, 12, 15]
```

| | n | mean | median | sd | min | max | victories |
|---|---|---|---|---|---|---|---|
| **D0** | 16 | **16.812** | 17.0 | 3.371 | 10 | 20 | **5/16 = 0.3125** |
| **D5** | 16 | **10.562** | 11.0 | 1.590 | 8 | 15 | **0/16 = 0.0000** |

- Observed mean difference (D0 − D5) = **+6.2500**.
- Assignment space **C(32,16) = 601,080,390**, computed **EXACTLY** by a subset-sum DP — the
  statistic is monotone in `sum(D0)`, so the null is *counted*, not sampled or enumerated.
- **Exact two-sided permutation p = 2.50216e-06** [752/300540195].

⛔ **Per §26f: THIS GAP IS EXPECTED AND IS NOT A FINDING.** D5 is harder than D0 by construction; a
significant difference here would be alarming only by its absence. The p-value is a sanity check on
the data, not a result, and is not dressed up as one. **The deliverable is the matched, poolable
pair.**

---

## SECONDARY (§26d) — offense at landmark vs terminal wave, EXPLORATORY

Offense = `sum(weapon.damage)` at the **first `combat_capture` of wave k**, taken from the
**capture payload** (`payload.weapons`), not the save's `weapons[i].stats`. Exclusion count is
reported **before** every rho, as pre-registered. Statistic is Spearman rho within each arm; the
comparison is the between-arm **difference**, by permutation on arm labels (200,000 resamples,
seed 20260802, floor 4.99998e-06).

| wave k | D0 n | D0 excl | D0 rho | D5 n | D5 excl | D5 rho | diff | p |
|---|---|---|---|---|---|---|---|---|
| 2 | 16 | **0** | −0.2039 | 16 | **0** | +0.1563 | −0.3602 | 0.361778 |
| 3 | 16 | **0** | −0.0625 | 16 | **0** | +0.2284 | −0.2909 | 0.468573 |
| 4 | 16 | **0** | −0.0085 | 16 | **0** | +0.4417 | −0.4502 | 0.269474 |
| **5** ⭐ | 16 | **0** | **+0.1011** | 16 | **0** | **+0.4920** | **−0.3908** | **0.335823** |
| 6 | 16 | **0** | +0.1057 | 16 | **0** | +0.4487 | −0.3431 | 0.397268 |
| 8 | 16 | **0** | +0.4110 | 16 | **0** | +0.0557 | +0.3553 | 0.375533 |
| 10 | 16 | **0** | +0.3453 | **12** | **4** | +0.3147 | +0.0306 | 0.946625 |

⭐ = the **pre-registered primary landmark** (wave 5).

**§26d IS NULL.** No landmark reaches significance; p ranges 0.269 to 0.947.

### The landmark problem did not bite — and that is a genuine methodological result

The pre-registration warned that the landmark constraint is **structural**: any wave late enough to
carry build variance would exclude the earliest D5 deaths, which is selection on the outcome.

**In fact waves 2, 3, 4, 5, 6 and 8 have ZERO exclusions in BOTH arms**, because the D5 arm's
minimum terminal wave was **8**. The pre-registered primary landmark (wave 5) is reached by 16/16 in
both arms. Only wave 10 excludes anything (4 D5 runs), and it is a sensitivity, not the primary.

⇒ Unlike the **retracted** `rho = −0.117`, which was survivor-selected at waves 10/15/17 — landmarks
reached by **0/20** of the old D5 runs — **this analysis is NOT survivor-selected at the
pre-registered landmark.** The condition the prereg feared would invalidate the design did not occur,
and the exclusion counts prove it rather than assuming it.

### Direction, reported honestly

The retracted claim asserted that **entry offense does not predict D5 survival**. Here the D5 rho is
**POSITIVE and LARGER than D0's** at the pre-registered landmark: **+0.4920 vs +0.1011**. It is
positive in D5 at waves 2, 3, 4, 5, 6 and 10, and larger than D0 at 3, 4, 5 and 6.

**That is the opposite direction to the retracted claim.**

⛔ **It is NOT significant (p = 0.336) and must NOT be reported as a finding.** But it is equally a
reason **not to keep asserting the old claim** — the only data that ever supported it is retracted,
and the first valid data points the other way.

### Confound — the D0 arm is CEILING-CENSORED

**6 of 16 D0 runs are pinned at exactly wave 20**, the run-ending ceiling. That mechanically
compresses D0's outcome variance (sd 3.371 with a hard cap, against D5's 1.590 with no cap) and
**attenuates D0's rho toward zero**. The D0-vs-D5 rho comparison is therefore confounded by
censoring, **independent of any real effect**. A larger D5 rho is exactly what censoring alone would
produce.

### Power limit

At **n = 16 per arm**, a rho difference of **~0.39 yields p = 0.336**. This design **cannot resolve
differences of that size**. ⛔ **Do not present this null as evidence of no difference.** It is an
underpowered observational comparison on a censored endpoint, and it is reported as such.

---

## What this establishes

**Established: the first valid, poolable D0/D5 pair exists.** Before this campaign there was
**no era-stamped D5 data in existence** — all 35 archived D5 runs predate `unlock_pool`, which first
appears at build `0.2.63` — and **no matched D0 set on the same character and build**. Every prior
D5 statement rested on unpoolable data. This pair is era-stamped (177/46/`2286319327`), single-build
(`0.2.73-wp2-capture`), single-character, single-opener, fixed n, no `--stop-on-win`.

**Established: §26d is null**, at every landmark, including the pre-registered one, with zero
exclusions where it matters.

**Established, methodologically: the landmark problem did not bite at this design's landmark.** The
D5 arm's floor of wave 8 put waves 2–8 above every run in both arms. That is a property of *this*
population, measured, not assumed — it does not license reusing late landmarks elsewhere.

**NOT established:**

- ⛔ **That D5 failure is survival-limited rather than offense-limited.** The prereg pre-declared
  this and it binds: a §26d null does **not** establish it. An observational correlation on a
  compressed, censored endpoint has low power and the landmark constraint biases it. Establishing
  this requires an **INTERVENTION** — e.g. the `enemy_scaling` save-file dial, whose readback is
  **`max_hp` by type** — not a correlation.
- That offense *does* predict D5 survival. The positive D5 rho is not significant and is confounded
  by D0 ceiling censoring.
- Anything about characters other than `mutant`, or about builds other than `0.2.73-wp2-capture`.

⛔ **Do NOT pool these runs with the 35 archived D5 runs.** Different build, different character,
and those runs carry **no era stamp at all**.

---

## What this unblocks

- **This pair is now the era-stamped reference for any future D5 work.** Future D5 runs on
  `character_mutant` at era 177/46/`2286319327` can be pooled with it; the matched D0 arm is the
  within-design control for anything that manipulates difficulty.
- **The natural next step is an INTERVENTION at D5, not more correlation.** §26d's power limit is
  structural at this n, and the ceiling censoring in D0 will not go away by collecting more of the
  same. The `enemy_scaling` dial (readback = `max_hp` by type) is the named candidate: it changes the
  quantity in question rather than observing it, and it has a readback that proves the manipulation
  arrived — which the correlational design cannot have.
- The D5 arm's floor of wave 8 is now a **measured** fact, which lets a future D5 design choose a
  landmark with a known exclusion profile instead of guessing.

---

## Instrument notes

- `scripts/wp2_d0d5_pair_analysis.py` takes no arguments and defaults to the APPDATA runs dir.
- Run with `PYTHONIOENCODING=utf-8` (the report's figures were reproduced this way, exit 0).
- The primary permutation is **exact by DP**, not resampled: the statistic is monotone in `sum(D0)`,
  so the whole `C(32,16)` space is counted. The §26d between-arm permutation *is* resampled
  (200,000, seed 20260802), giving it a p-floor of 4.99998e-06 — well below anything it returned.
