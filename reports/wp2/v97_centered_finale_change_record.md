# v97 centered-finale change record

Date: 2026-07-22

## Scope and rationale

The operator directed two wave-20 policy changes after observing that the
center-biased behavior naturally kept the boss within useful automatic-fire range:

1. Remove the rule that orbits the boss at weapon range.
2. Amend low-health survival so it does not restore or maintain a boss-range ring.

The v96 collector and its scoped Brotato process were positively identified and
stopped before editing. Auto-start was disabled. Four completed v96 runs remain
immutable diagnostic evidence; partial run `run_1784713077_45927` is excluded.

## Reversible implementation

- Wave 20 now starts from the existing pure-repulsion, center-biased survival field.
- Low-health wave-20 movement uses panic dodge, falling back to the same
  pure-repulsion field, without radial boss-distance projection.
- The boss-range spring, orbit strafe, recovery ring, and their configuration
  constants were removed.
- Direct boss-contact escape, projectile lane sampling, reversal handling,
  commitment, corner recovery, final projectile safety, and predictive hard-wall
  enforcement remain in force.
- Policy identity advances to `teacher_v1-0.1.97-gun-wp1`; capture mod identity
  advances to `0.2.5-wp2-capture` without changing the capture schema.

The policy change is committed separately before deployment so it can be undone
with a normal `git revert`.

## Verification and deployment

- Focused policy/capture/collector/monitor tests: `70 passed`.
- Full repository suite: `93 passed`.
- Workshop and local installed archives are byte-identical, contain 18 entries,
  and have SHA-256
  `473657D46D0E11ADFAF593C9A90A2941773142C092CC3B99AF2693A323E8DFE1`.
- The deployed manifest reports `0.2.5` and the v97 teacher description.
- Stopped smoke launch reached `AgentController ready` with zero script/parse
  errors and zero post-start APPCRASH events.
- Brotato was stopped after smoke and auto-start remained false.
