# WP2 v106 body-clearance change record

## Trigger

The isolated v105 smoke `run_1784738604_58496` reached wave 20 but failed its
behavioral audit. The run ended as a timer defeat rather than an HP death, yet
two 21-damage contacts followed commands through the boss:

- captures 20226-20229 held `(-0.866025,-0.5)` while boss-edge clearance fell
  from 92.2 to -2.9 units. The chosen wall-improving path predicted only 8.1
  units of future body clearance at capture 20226; another wall-improving
  sampled lane predicted 59.1;
- captures 20432-20434 emitted projectile-safety commands toward and through
  the boss. At capture 20433, another sampled lane retained comparable
  projectile clearance (71.8 versus the 81.6 maximum) while increasing
  predicted body clearance from 2.2 to 61.4 units.

The v105 aggregate enemy penalty was soft. Wall gain or the projectile-clearance
tier could therefore purchase a predicted collision even when a materially
safer body path existed. The smoke is preserved as diagnostic evidence and is
not eligible for the primary dataset.

## Narrow repair

v106 leaves the boss-range-ring removal, central-map preference, 280/520 wall
hysteresis, 96-unit hard projection, and v105 predictive crowd penalties intact.
It adds one ordered invariant to every late safety selector:

1. Predict minimum future edge-to-edge body clearance against moving ordinary
   enemies and bosses, including entity radii and excluding the shared current
   overlap sample.
2. If any eligible lane offers at least 45 units, reject predicted-contact lanes.
   If every lane is contact-dangerous, keep candidates within 20 units of the
   best available body clearance.
3. Preserve the existing projectile-clearance tier whenever it contains a
   contact-safe lane. Only when every projectile lane is below panic may the
   selector concede at most 60 clearance units to avoid a predicted body impact.
4. Apply the same body tier to hard-wall projectile replanning and expose
   input/best/selected/final body-clearance diagnostics for closed-run auditing.

Policy identity advances to `teacher_v1-0.1.106-gun-wp1` and mod identity to
`0.2.14-wp2-capture`. The compatible capture schema hash remains
`95B6444796A21FD44E94113B75BA2097BC381D5F72ED784F9B9A4A99DD46D951`.

## Reversibility and qualification

The behavioral change is confined to late safety candidate filtering plus
diagnostics, version declarations, tests, and records. Reverting the v106 repair
commit restores v105 behavior; no raw telemetry is rewritten.

Qualification requires focused frozen-evidence tests, the full suite, exact
deployment identity verification, and a fresh isolated v106 smoke reaching the
late safety path without an avoidable body-contact command. Only then may an
exactly-20-run v106 collection begin.

Pre-deployment verification: **55 focused tests passed** and the **101-test full
suite passed**. Deployment identity and runtime smoke remain pending.
