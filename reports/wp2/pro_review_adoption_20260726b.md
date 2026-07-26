# Pro consultation — adoption record, 2026-07-26 (second set)

Briefs: `.tmp/pro_consultation_briefs_20260726b.md`. Reply received via share link,
fetched 2026-07-26. Selective adoption with reasons, per standing pattern.

---

## Two corrections I accept outright

### C1. The 6.4x is a PER-POINT ratio; the PER-DECISION ratio is ~1.4x

This is the correction that changes what the finding means.

My worked wave-12 case offered `+2 ranged_damage` (18.21% theoretical DPS gain) vs
`+15 attack_speed` (13.04%). The real decision margin is **18.21/13.04 = 1.396x**,
not 6.4x. Boards deliver attack_speed in much larger numeric chunks, which very
nearly cancels the per-point advantage.

Both statements are true and I must keep them separate:

- **The scoring defect is large.** Raw points say +15 attack_speed beats +2 ranged
  by 7.5x; true DPS says ranged wins by 1.40x. The scorer is wrong by an order of
  magnitude *in the quantity it ranks on*.
- **The corrected decision is fragile.** A 1.40x margin flips if the ranged option
  realises less than **71.6%** as much of its theoretical gain as the attack_speed
  option does (`q_R/q_A > 0.716`). A ~28% relative wastage penalty on ranged
  reverses it. In a trash-heavy swarm wave that is entirely plausible.

Consequence: **"the policy under-values the most DPS-efficient stat by ~6x at the
point of choice" is WRONG as written** and is corrected in memory. The 6x is real
per point; it is not the decision margin.

Pro's operational version of this — *"calculate the break-even ratio for every
historical ranged-versus-attack-speed decision"* — is adopted and is now the
primary measurement (M2 below).

### C2. My stated mechanism ("compounds six times") is wrong

I wrote that ranged_damage compounds through six weapons while attack_speed does
not. Algebraically that does not hold: contributions are **additive** across
weapons,

    ΔD/D = Σ(K_i · c_i) / Σ(D_i)

so adding similar weapons raises numerator and denominator together and does not
by itself produce a sixfold percentage advantage. The same applies to
`nb_projectiles` and the crowd multipliers — they multiply the ranged gain and the
attack_speed gain alike, so they carry no algebraic bias.

The real driver is per-weapon magnitudes: each weapon's `flat` damage is small
(~20-25), so +1 ranged is ~4% of it, while +1 attack_speed is `1/(100+A)` ≈
0.53-0.61% at A = 64-88. That reproduces ~6-7x with no reference to weapon count.

**The measured 6.4x survives; the explanation attached to it does not.** Being
wrong about the mechanism while right about the number is exactly the failure that
made me over-trust the finding, so this is being written into memory rather than
quietly fixed. Empirical check commissioned (M4): if the six-weapon story were
right, weapon COUNT would correlate strongly with the ratio. Prediction: it does
not.

---

## Adopted, with reasons

**A1. Do not ship a 6.4x corrective coefficient.** Already the standing position —
v128 was withdrawn as inert. Pro independently reaches it from a different
direction (the ratio is not transferable to survival value), which strengthens it.

**A2. Do not add a fifth corrective term.** Adopted. Pro's framing is the one I
want on record: *preserve each historical failure as a fixture or invariant; do not
preserve every historical patch as an additive score term.* Terms B, C and D each
encode a real failure mode; none of them needs to keep encoding it as a raw-points
price.

**A3. Collapse B/C/D as ONE atomic migration, not one term at a time.** Adopted,
and it resolves the problem that killed v128. Every single-term intermediate is
incoherent: removing D alone is inert (measured — that IS v128), removing B alone
leaves C dominant, changing C alone leaves the other duplicate prices. The correct
experimental unit is *legacy additive stack vs collapsed scorer*, behind a runtime
`scorer_version = legacy | collapsed_v1` switch with the legacy scorer running in
shadow. The switch also gives rollback without a code revert — worth a lot at
~20 min per smoke.

Target architecture: hard vetoes → offense-deficiency **gate** (D's role, as
eligibility not as price) → **one** offense cardinalizer (A's role, with a
validated metric) → orthogonal terms only → deterministic tie-break. C's wave-tiered
urgency survives as a single **category scalar** `offense_weight = f(wave, gap)`
applied uniformly to all offense stats, which preserves "offense matters more at
wave 9-14 below the floor" without repricing ranged vs attack_speed against each
other.

**A4. The fixture corpus + the inert-change test.** Adopted, high value. Every
current pin on this path is a source-text assertion, and **no test executes
`decide_levelup` at all** — so behaviour can change with a fully green suite. The
replacement is a decision-fixture corpus asserting *decision + reason code + score
decomposition*, seeded with: the wave-12 case, and every historical failure that
originally motivated B, C and D.

Pro's "inert-change test" is my own binding rule turned into a test artifact:
*the collapsed scorer must produce the intended changed ranking on the fixture that
motivated the migration.* This is the check whose absence cost the v128 cycle.
It must pin whatever the validated metric says is correct — not force ranged to win.

**A5. Metamorphic invariants.** Adopted, cheap and durable. The two that matter
most here:
- **Stat-label neutrality** — two options with equal marginal combat utility and
  equal non-offense effects must not score differently because one is labelled
  `ranged_damage` and the other `attack_speed`. This defect is precisely a
  violation of it, so the invariant would have caught it.
- **No hidden raw pricing** — a static guard rejecting any new additive offense
  term based on raw stat magnitude unless explicitly registered as an orthogonal
  quantity. This is the guard that stops the stack re-accreting.
Plus monotonicity, dominance, gate correctness, scope preservation, determinism.

**A6. Shared JSON coefficient table — adopted WITH its stated boundary.** It
prevents *parameter* drift between the Python reimplementation and the shipped
GDScript. It does **not** prevent *logic* divergence (formula order, caps, null
handling, eligibility, rounding, tie-breaking). Adopting it as a real improvement
that is not a substitute for executing the real code.

**A7. The Godot 3.5 fixture harness is upgraded from DEFERRED to WANTED.** This is
the same proposal Pro made on 2026-07-25 (pinned Godot 3.5.x binary + stub-autoload
harness), which the operator deferred for parse-gating alone. It now earns its keep
twice: it parse-gates mod GDScript (the failure that cost a full deploy cycle on
v127, and the risk the unparsed sentinel still carries) **and** it runs scorer
fixtures against the actually-shipped GDScript in seconds. Precondition Pro names:
make the GDScript scorer a pure function over normalized dicts. Not a blocker for
the sentinel deploy — do not couple them.

---

## Rejected or resequenced, with reasons

**R1. Stage 0 telemetry (per-hit effective damage, overkill, target availability,
attack cadence) is NOT adopted as a prerequisite — it is deferred behind a gate.**

Pro's shots-to-kill correction is principled and I accept the model:

    η_ie = H_e / (d_i · ceil(H_e / d_i))
    U_iwe = m_iwe · d_i · r_i · η_ie

as is the point that overkill can cut *both* ways — near a kill threshold, one
ranged point that turns a two-shot kill into a one-shot kill is worth *more* than
sustained DPS predicts, not less. And the critical-hit DP for exact expected
shots-to-kill is right that `ceil(H/E[damage])` is not a valid substitute.

But the whole package requires a mod change, a version bump, a deploy, a smoke, and
instrumented runs. **The measured level-up surface is 0.45 rankable decisions per
run** (40.5% of boards offer zero offense options, 50.1% exactly one). Paying a
telemetry program to price a decision that fires twice per three runs is not
justified *yet*.

**What justifies it is the shop-path flip count, which I have never measured.**

**R2. Resequenced: Pro's Stage 3 (offline differential replay) is pulled forward to
be Stage 0.** This is the substantive departure from Pro's plan and the reason for
it is a defect Pro could not see from the brief.

Term D is level-up-only, but terms B and C **also price shop stat-item purchases**,
and the shop path sees ~1,037 offense-deficient buys across these 20 runs — roughly
**52 per run against the level-up path's 0.45**. My earlier "selection is clean:
0 gate misses, 0 soft misses over 1,037 buys" result was computed in **raw-point
units**, which is circular with respect to this exact defect: it asked whether a
gate-clearing item was passed over, not whether the higher-DPS item was chosen.

So the shop path is a surface ~100x larger than the one I measured, and it has
never been scored in DPS units. Measuring it costs hours of offline compute on data
already on disk — no deploy, no campaign. It is commissioned now (M3).

This is the same "check which component dominates before concluding about the
aggregate" discipline that the v128 verdict already needed once. Declaring the
migration justified — or not — on the level-up surface alone would repeat it.

**Gate, predeclared before seeing the numbers:** if the shop path yields a
materially larger flip count than the level-up path's 9/425, the collapsed-scorer
migration is worth its program cost and R1's telemetry becomes worth pricing. If
the shop path also flips only a handful of decisions, then the entire raw-points
defect is a real but low-yield uniform mispricing, and the correct action is to
record it and redirect effort off this layer rather than fund a five-stage program
for it.

**R3. Not adopted: pairing legacy and collapsed runs on the same seeds.** Pro
offers it conditionally ("where deterministic seed control is available"). It is
not — Brotato's wave/offer RNG is not exposed for pinning here. The alternating-arms
under-matched-conditions fallback is what the F2 campaign already used, and the
machine-load confound recorded there says matching must include machine load.

**R4. Noted, not yet actionable: "uptime does not automatically favour attack
speed."** Good catch against my own Brief-1 worry #2. I asserted a slow weapon can
waste cooldown while nothing is targetable; whether Brotato's weapons hold a ready
cooldown or continue losing firing opportunities with no target is a mechanic I did
not verify. It is readable from the decompiled game source, which is cheaper than
the telemetry. Do before pricing attack_speed's realisation factor.

---

## Commissioned now (offline, no deploy)

- **M1** per-decision theoretical gain ratio across the ~40 rankable level-ups,
  raw table, plus how many of the 9 mispicks clear 1.4x.
- **M2** break-even realisation ratio for every board offering both a
  ranged_damage and an attack_speed option.
- **M3** shop-path flip count — the gate in R2.
- **M4** empirical refutation of the six-weapon mechanism (C2).

## Standing obligations unaffected by this consultation

- The **sentinel-only deploy** (`b98fb4d`) is still owed and is independent of all
  of the above. Its GDScript has never been parsed; read
  `%APPDATA%/Brotato/logs/modloader*.log` first if the game idles on the title
  screen.
