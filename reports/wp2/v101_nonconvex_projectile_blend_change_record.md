# v101 non-convex projectile-blend repair

Date: 2026-07-22

## Trigger

The first v100-only collection run, `run_1784719744_89481`, completed as a
wave-20 defeat. Its 4,208 wave-17-through-20 captures had zero invalid/schema/
drop/error findings, zero fresh 300 ms hard-margin projection failures, zero
observed hard-margin entries, and no clearly avoidable wave-20 projectile-hit
chain.

A full command audit nevertheless found one fresh wave-18 regression at capture
18590 (event seq 20828). Projectile safety saw 456.283447 input clearance and a
555.295715 sampled escape, but the 0.55 urgency blend emitted direction
`(0.998698, 0.051023)` with only 160.604614 clearance. That is below the exact
204.6 panic threshold. Clearance over direction space is non-convex, so blending
two safer endpoints is not itself safety preserving.

The exact v100 collector and Brotato processes were stopped during partial
successor `run_1784720888_8829`; auto-start was disabled and raw telemetry was
left unchanged. Both v100 runs are excluded from the replacement collection.

## Reversible repair

- Preserve the existing urgency calculation and sampled escape selector.
- Evaluate the actual normalized blended direction in the same projectile
  context before returning it.
- If the blend is below the profile-adjusted panic threshold and the sampled
  escape has at least 20 more clearance units, return the sampled escape.
- Keep the final predictive wall pass after this decision. The v100 wall-safe
  replan still handles any later wall-clamp rotation.
- Expose blended clearance and blend-repair activation in
  `finale_translation` for direct runtime auditing.
- Advance policy identity to `teacher_v1-0.1.101-gun-wp1` and mod identity to
  `0.2.9-wp2-capture`; the capture schema remains unchanged.

The change is isolated in a dedicated commit so it can be reverted normally.

## Verification

- Focused policy/collector tests: 51 passed.
- Full repository suite: 97 passed.
- Offline replay of capture 18590 identifies sampled escape
  `(0.866025, 0.5)`. Its clearance is 555.295801 (rounding-equivalent to the
  recorded 555.295715), and its 300 ms projection remains outside every
  96-unit hard margin. The v101 gate replaces the 160.604614-clearance blend
  with that sampled escape.
- Workshop and local deployment archives are byte-identical, contain 18 files,
  and have SHA-256
  `3687E49F5B6FBD50521137F8EA3ABF44B977990CEDF9620ECFC352D35B40FE99`.
- The deployed manifest reports version `0.2.9` and the v101 teacher.
- A stopped smoke launch reached `AgentController ready` with zero agent
  parse/load errors and zero post-start APPCRASH evidence. The positively
  identified smoke PID 28252 was stopped; Brotato is no longer running and
  auto-start remains false.
