# v108 final projectile-floor repair

## Trigger

The first v107 exact-20 source, `run_1784745549_60836`, completed a wave-20
victory with 21,836 structurally valid captures, exact identity, every wave,
and zero telemetry faults. It was rejected by the independent safety audit.
At capture 20609, projectile safety had selected 98.0783 units of predicted
clearance, but active wall recovery restricted the final body pass's sampled
pool to a 73.623917-unit maximum. The body pass therefore derived a 13.623917
floor and emitted a 20.587204-clearance lane immediately before 20 damage.
That 77.491096-unit concession exceeded the ordinary 60-unit bound. The emitted
lane also had only 33.194206 units of predicted body clearance while another
admissible wall-recovery lane had 41.602264, matching the observed dodge through
the enemy pack.

The automatically started successor `run_1784746726_60383` was interrupted at
wave 3. Both runs are immutable diagnostic evidence and are excluded from the
primary dataset.

## Narrow repair

The final body pass now computes the projectile clearance of its actual
post-wall baseline before selecting any body lane. When projectile safety is
active, its ordinary bounded-concession reference is the maximum of the
wall-filtered sampled pool, that emitted baseline, and the earlier projectile
escape. The existing safe/panic tier remains intact.

That strict floor is not allowed to turn an immediate body collision into the
fallback. If every strictly projectile-bounded lane predicts body overlap and
the original bounded tier offers at least 20 units more body clearance, the
selector enters a body emergency. It may then broaden back to the original
projectile tier, but continuity and soft crowd scoring can choose only lanes
within five units of the best available body clearance. In the frozen v107
decision this rejects the 33.194206 pack lane and admits the 41.602264 best
escape instead.

All wall, enemy-penalty, continuity, hard-margin, and sampling rules remain
unchanged. The independent damage audit preserves the ordinary 60-unit
projectile bound and recognizes a larger concession only when the final body
lane is within the same five-unit emergency tier. Policy identity advances to
`teacher_v1-0.1.108-gun-wp1`; mod identity advances to
`0.2.16-wp2-capture`; the compatible capture schema hash is unchanged.

## Reversibility and qualification

The behavioral diff is confined to final body-safety floor derivation, plus
identity declarations, tests, documentation, and this record. Reverting the
v108 repair commit restores v107 behavior; raw telemetry is never rewritten.

Before any new dataset collection, focused and full tests must pass, the mod
must be redeployed with a verified archive identity, and a fresh isolated
v108 smoke must complete and pass both structural capture and independent
safety audits. Only then may a clean exactly-20-run v108 collection begin.
