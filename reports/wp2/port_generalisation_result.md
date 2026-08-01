# §25 — Does the profile port generalise beyond Jack? RESULT

**Verdict: the pre-registered primary FAILS TO REJECT. p = 0.791347, one-sided, α = 0.05. NULL.**

Campaign 2026-08-01 → 2026-08-02. 64 runs: 4 characters × 8 runs × 2 arms, fixed n per cell.
Prereg `character_unlock_prereg.md` §25 + §25f; analysis `scripts/wp2_port_generalisation_analysis.py`.

This is a **strong** null, not a failed delivery. See "What this establishes".

---

## Validity — reported per cell, before any outcome

| arm | character | n | `character_ok` | build |
|---|---|---|---|---|
| PORTED | artificer | 8 | 8/8 | `0.2.72-wp2-capture` |
| PORTED | ranger | 8 | 8/8 | `0.2.72-wp2-capture` |
| PORTED | mutant | 8 | 8/8 | `0.2.72-wp2-capture` |
| PORTED | arms_dealer | 8 | 8/8 | `0.2.72-wp2-capture` |
| BARE | artificer | 8 | 8/8 | `0.2.71-wp2-capture` |
| BARE | ranger | 8 | 8/8 | `0.2.71-wp2-capture` |
| BARE | mutant | 8 | 8/8 | `0.2.71-wp2-capture` |
| BARE | arms_dealer | 8 | 8/8 | `0.2.71-wp2-capture` |

- **Era identical across all 64 runs:** items **177** / weapons **46** / hash **`2286319327`**.
- **`character_ok` 64/64.** One build per arm, no version mixing within an arm.
- **Fixed n = 8 per cell, no `--stop-on-win` anywhere** — the §22 optional-stopping defect is
  absent by construction; the driver ran every cell to its declared n.

---

## MANIPULATION CHECK — the treatment provably reached the policy

Non-`set_gun` share of shop weapon buys, PORTED vs BARE, from `scripts/wp2_engagement_control.py`.
The port sets `allow_melee=false` and `allowed_weapon_sets=["set_gun"]`, so a ported zero is only
informative where the bare rate is provably non-zero for the **same character**.

| character | PORTED non-`set_gun` | BARE non-`set_gun` | P(0 \| bare rate) |
|---|---|---|---|
| artificer | 0 / 90 | 20 / 129 = 0.1550 | 2.6e-7 |
| ranger | 0 / 232 | 22 / 211 = 0.1043 | 8.0e-12 |
| mutant | 0 / 168 | 38 / 126 = 0.3016 | 6.5e-27 |
| arms_dealer | 0 / 133 | 306 / 410 = 0.7463 | 5.8e-80 |

Melee, where the bare control is non-vacuous:

| character | PORTED melee | BARE melee | P(0 \| bare rate) |
|---|---|---|---|
| mutant | 0 / 168 | 30 / 126 = 0.2381 | 1.4e-20 |
| arms_dealer | 0 / 133 | 233 / 410 = 0.5683 | 3.0e-49 |

⚠️ Melee is **VACUOUS** as a signature on artificer (bare 0/129) and ranger (bare 0/211) — those
characters never buy melee un-ported, so a ported melee zero would mean nothing. The non-`set_gun`
share is the valid signature on all four.

Diagnostics clean on every cell: `unjoined_buys=0`, offers missing `sets` = 0, offers missing
`weapon_type` = 0, runs without events = 0, run dirs missing = 0.

**The port engaged, at every character, with margin.** ⚠️ **ENGAGEMENT IS NOT BENEFIT.**

---

## PRIMARY — terminal wave, STRATIFIED exact permutation within character, one-sided

| | n | total | mean |
|---|---|---|---|
| PORTED | 32 | **432** | **13.500** |
| BARE | 32 | 456 | 14.250 |

- Equally likely within-stratum assignments: **27,435,582,641,610,000** — enumerated exactly by DP.
- **p = 0.791347** (exact, `2811584812097/3552911505000`).
- **FAIL TO REJECT at α = 0.05.** The pooled point estimate is **directionally WORSE** for the port.

## SECONDARY — pooled victories, Fisher exact, one-sided

**PORTED 9/32 vs BARE 6/32, p = 0.278064.** Secondary, not substituted for the primary. It agrees
with the primary in failing to reject.

---

## Per character — reported for all four whatever they show (§25c)

| character | PORTED mean | BARE mean | delta | PORTED wins | BARE wins |
|---|---|---|---|---|---|
| artificer | 9.88 | 12.00 | **−2.12** | 0/8 | 0/8 |
| ranger | 19.88 | 17.75 | **+2.12** | 6/8 | 5/8 |
| mutant | 18.25 | 16.25 | **+2.00** | 3/8 | 1/8 |
| arms_dealer | 6.00 | 11.00 | **−5.00** | 0/8 | 0/8 |

Raw terminal-wave series:

```
artificer    ported [7, 11, 7, 17, 10, 10, 8, 9]       bare [10, 7, 12, 10, 20, 12, 17, 8]
ranger       ported [20, 20, 20, 20, 20, 19, 20, 20]   bare [20, 9, 20, 20, 20, 13, 20, 20]
mutant       ported [17, 13, 19, 17, 20, 20, 20, 20]   bare [15, 19, 17, 20, 15, 19, 10, 15]
arms_dealer  ported [9, 6, 3, 5, 2, 9, 7, 7]           bare [14, 17, 11, 10, 18, 1, 10, 7]
```

⛔ **§25e binds: two positive deltas out of four, inside a null, are a HYPOTHESIS for a future
powered test — not a finding. Do not pick the best of four.**

**Ranger and mutant sit at the wave-20 CEILING and therefore carry little information.** Ranger
PORTED is 7/8 at exactly 20; a victory ends the run at 20, so those cells have almost no dynamic
range left in which a treatment could show itself. Their +2.12 and +2.00 are largely the bare arm's
two or three short runs moving, not a demonstrated lift.

### arms_dealer −5.00 — a candidate mechanism, labelled HYPOTHESIS, not a finding

arms_dealer's bare arm buys melee on **56.8%** of weapon buys and non-`set_gun` on **74.6%**. The
port sets `allow_melee=false` and `set_gun`-only, removing most of its weapon options. Its shop
weapon buys collapsed **410 → 133**.

⚠️ **Confound, stated because it is fatal to the naive reading:** the ported runs are also much
shorter (mean wave 6.00 vs 11.00), and shorter runs visit fewer shops. Buy count alone therefore
**cannot** separate "the policy refuses weapons it is offered" from "the run died earlier". Testing
this needs a per-shop offer-conditional refusal rate, which was not measured here.

---

## SECONDARY FINDING (incidental) — the BARE arm is the baseline the project lacked

The bare arm is era-matched (177/46/`2286319327`), single-build (`0.2.71-wp2-capture`), fixed n,
post-`weapon_prefixes`-fix, four characters × 8. Per-character victories:

| character | bare victories |
|---|---|
| ranger | 5/8 = 0.625 |
| mutant | 1/8 = 0.125 |
| artificer | 0/8 |
| arms_dealer | 0/8 |

Three things must be said about it explicitly:

1. ⛔ **Do NOT quote the pooled 6/32 = 0.1875.** The per-character spread is **0.000 – 0.625**; the
   pool is a mixture and its mean describes no character.
2. ⛔ **A 0/8 is not a proven zero.** Rule of three gives an upper bound of ≈ **0.31** on the true
   rate at 95%.
3. ⛔ **It is NOT comparable to the historical non-`well_rounded` 4.9% (3/61).** Different
   characters, different eras, and that figure predates the gun-first `weapon_prefixes` fix, so it
   mixes a defect with the character effect. This **replaces** it; it does not contradict it.

---

## What this establishes

**Established: the profile port does not generalise beyond Jack.** The pre-registered primary is
null at p = 0.791, and the pooled direction is against the port.

**This is a STRONG null, not a failed delivery**, on two independent grounds:

- **The design could return the positive.** `--self-test` passes 7/7, including "complete separation
  returns the floor", "identical arms → 1 and reversed → 1", the DP-vs-brute-force count check, and
  Fisher reproducing the tea table 17/70. Design **p-floor = 3.64e-17**, far below α.
- **The treatment provably reached the policy.** Engagement zeros run down to **P = 5.8e-80**. This
  is not a manipulation that failed to arrive.

**ENGAGEMENT IS NOT BENEFIT.** This is the **second** demonstration of that on this project; the
fisherman was the first. A treatment can be shown to have changed the policy's behaviour and still
produce nothing at the endpoint.

**The pre-declared rule now binds: the port is JACK-SPECIFIC ⇒ accept the surface (prereg §23b
option 2).** §24's Jack result (p = 0.0186) stands; it is a lever on one character, not a general
capability fix. The acquisition branch stays as §23b left it.

**Not established:**
- That ranger or mutant benefit. See §25e above.
- That the port *harms* arms_dealer or artificer through any named mechanism. The −5.00 mechanism is
  a hypothesis with a live confound.
- Anything about characters outside the four tested.

---

## Instrument notes

- `scripts/wp2_port_generalisation_analysis.py` takes no arguments (defaults to the APPDATA runs
  dir) and refuses to report below 8 runs × 8 cells (exit 2), so it is blind until the campaign is
  complete.
- **Defect, cosmetic:** on a cp1252 console the script crashes with
  `UnicodeEncodeError: 'charmap' codec can't encode character '⛔'` while printing the trailing
  §25e caveat — i.e. **after** the verdict, exit 1. Run with `PYTHONIOENCODING=utf-8` for exit 0.
  No number is affected. Reproduced both ways during this write-up.
- Engagement figures re-derived per cell with
  `scripts/wp2_engagement_control.py --runs-dir <APPDATA runs> --state-file .tmp/gen_<arm>_<char>/state.json`.
  Weapon metadata (`weapon_type`, `sets`) lives on the `purchase_offer` event, not on the buy; the
  script joins each buy to the most recent preceding offer board in the same run, and reports
  `unjoined_buys` so a silent join failure cannot read as a zero.
- All figures in this report were re-run and reproduced before writing.
