# §24 — Profile port to Jack, powered test. RESULT

**Verdict: the pre-registered primary REJECTS the null. p = 0.0186, one-sided, α = 0.05.**

Campaign 2026-07-31 → 2026-08-01. 64 runs, 32 per arm, four blocks of 16.
Prereg `character_unlock_prereg.md` §24; analysis `scripts/wp2_jack_power_analysis.py`
(written blind, §24c-i).

---

## Validity — reported per arm, before any outcome

| | PORTED | BARE |
|---|---|---|
| n | 32 | 32 |
| builds | `0.2.67`, `0.2.69` | `0.2.68`, `0.2.70` |
| era stamp | 177/46 `2286319327` | 177/46 `2286319327` |
| `character_ok` | 32/32 | 32/32 |

**Era identical across all 64 runs.** Each block shipped its own version because identical
version strings over differing content is the one divergence the identity gate cannot see;
within an arm the builds differ only by those strings, which do not affect behaviour.

**Engagement readback, bidirectional and non-vacuous:** PORTED **0 / 875** melee weapon buys,
BARE **120 / 707 = 0.1697**. The control proves the instrument registers melee for this exact
character, so the zero is informative.

### Within-arm block diagnostic (blocks ran sequentially; the primary pools by arm)

| arm | block | mean wave | wins |
|---|---|---|---|
| PORTED | A1 | 18.75 | 9 |
| PORTED | A2 | 18.50 | 8 |
| BARE | B1 | 17.19 | 1 |
| BARE | B2 | 18.00 | 3 |

**The arms do not overlap at block level** — PORTED spans [18.50, 18.75], BARE [17.19, 18.00].
The ordering holds in both matched pairs (A1 > B1, A2 > B2), so the pooled contrast is not an
artefact of drift across the sequential blocks. The bare blocks are the more variable pair.

---

## PRIMARY — terminal wave, exact permutation on the arm sum, one-sided

| | n | sum | mean |
|---|---|---|---|
| PORTED | 32 | **596** | **18.625** |
| BARE | 32 | 563 | 17.594 |

- Equally likely splits: **1,832,624,140,942,590,534** — counted exactly by DP, not sampled.
- **p = 0.0186067** (exact). Independent Monte-Carlo cross-check at N = 400,000:
  **0.018405 ± 0.000417**, agreeing.
- **REJECT at α = 0.05.**

⚠️ **The endpoint is CENSORED at 20 and the effect is therefore UNDERSTATED.** A victory ends the
run at wave 20, so 20 is a hard ceiling, and **17 of 32 ported runs sit on it**. The measured
1.03-wave separation is a floor on the true separation, not an estimate of it.

## SECONDARY — victories, Fisher exact, one-sided

**PORTED 17/32 (53.1%) vs BARE 4/32 (12.5%), p = 0.000556.**

Reported as secondary and **not substituted for the primary**, per §24c. It is the less censored
view of the same effect, which is consistent with the ceiling above.

---

## Mechanism — EXPLORATORY (`scripts/wp2_jack_port_mechanism.py`, also written blind)

No verdict is issued here and none of it rescues or modifies the primary.

**M1 OFFENSE.** The clean comparison is **wave 10, where both arms are 32/32 and nothing is
survivor-selected**: entry weapon damage **182.0 vs 167.5**. Wave-15 and wave-17 figures
(299 vs 258; 345.5 vs 290) are survivor-selected on one or both arms and are weaker evidence.

**M2 CLEARANCE — the readback that makes M1 mean something.** Standing enemies at wave 15:
**PORTED 7.5 vs BARE 11.0**. Converting with the external simulated spawn flow (λ = 7.2/s, from
the decompiled wave composition — *not* our measurement), mean enemy lifetime is
**1.04 s vs 1.53 s**. The offense converted into clearance; it did not go somewhere that failed
to kill anything.

**M4 SURVIVAL — rules out the defensive story.** HP-deficit exposure is **0.008 PORTED vs 0.006
BARE**: the ported arm is very slightly *worse*, not better. **The port does not work by taking
less damage. It works by killing faster.**

This is coherent with the strongest existing finding on this project — wave-17 deaths separate on
**offense** (rank-biserial 0.188, doomed runs entering with half the weapon damage) while max_hp
and armor do not separate at all. Two independent lines now tell one story.

---

## What this does and does not establish

**Established:** porting the tuned `well_rounded` profile to Jack improves terminal wave
(p = 0.0186) and victory rate (17/32 vs 4/32). The profile, not the character, carries a large
part of the win rate — **for Jack**.

**NOT established, and stated because it is the obvious over-read:**
- **It generalises no further than Jack.** One character, pre-registered as such in §24e.
- ⚠️ **This bare arm is NOT the historical bare Jack.** Both arms here run the corrected
  gun-first `weapon_prefixes`; the historical Jack 0/8 started on a melee knife its own shop
  scores −1e9. So **4/32 = 12.5% must not be compared to the "non-`well_rounded` 4.9%" durable
  number** — that comparison spans a fixed defect as well as the treatment.
- The ported 53.1% likewise must not be read against `well_rounded`'s historical 38.4%, which is
  era-mixed. **Era-match before pooling anything.**
- Mechanism is exploratory. M1's clean estimate rests on a ~9% wave-10 damage difference.

**Next decision (not taken here):** §23b option 1 (fix capability) is now live rather than
speculative — the port is a real lever. Whether it transfers to other characters is a new
experiment, and the §22 lesson applies: run to a fixed n with no `--stop-on-win`.
