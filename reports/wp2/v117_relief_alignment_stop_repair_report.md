# WP2 v117 relief/alignment stop-repair report

The one-run v116 qualification smoke `run_1784771165_61226` ended in a
wave-20 defeat and is rejected (8 violations under the v116 audit). It is
frozen qualification evidence and was never dataset-eligible.

## What v116 proved

The continuous-clearance repair worked as designed: 0 diagnostic mismatches
across 20,565 captures, 0 route-crossing damage, 0 body-tier or
projectile-floor violations, and waves 1–19 took only 5 damage events
(v115: 8 by wave 19 with a 52→1 HP chain on wave 20). All violations
cluster on the fatal wave 20 in the wall-body-relief family.

## Two root causes (frozen captures 20360–20565)

1. **Capture/decision phase misalignment (latent since finale hold was
   introduced).** Finale decisions recompute when
   `_finale_move_tick % 3 == 1`; captures emitted when the independent
   `_combat_tick_counter % 3 == 0`. The relative phase at wave-20 entry is
   luck: v115 drew aligned (1800/1800 fresh), v116 drew offset (0/496
   fresh). Every fresh-gated audit check silently skipped the fatal wave,
   and wave-20 capture labels paired stale diagnostics with held actions.
2. **Knife-edge relief trigger.** At captures 20390/20464/20468/20527 the
   wall-recovery selector degraded body clearance to 141–176 (score prefers
   wall progress and continuity) while hard-wall-safe lanes offered
   215–370. Relief required reference < 140; the references were
   140.7–151.1. Lane replay at 20527: progress-filtered pool best 176 vs
   hard-safe lanes at 359. The run then died through 17-damage boss
   contacts, the last route predicting −0.4 clearance.

## Repair (policy v117, mod 0.2.25)

- Finale captures are emitted on the recompute tick itself
  (`emit_capture = recompute_move` when wave ≥ finale), making wave-20
  freshness deterministic at the same 20 Hz cadence.
- `BOSS_FINALE_WALL_BODY_RELIEF_TRIGGER` 140 → 200 (audit mirror updated):
  covers the observed 140.7–151.1 references plus ~45 units of intra-hold
  decay at wave-20 relative speeds; the 60-unit minimum gain and hard-wall
  safety of every relief lane are unchanged.
- New audit gate: any non-fresh finale capture rejects the run (exempt
  under `--legacy-sampled-diagnostics` for pre-v117 frozen evidence).

## Verification

- Full suite: 128 passed (2 new v117 tests, incl. a fixture-run audit test).
- Replaying the v117 audit on the frozen v116 smoke: 43 violations —
  nonfresh-finale gate fires (496 captures), relief violations rise 6 → 40
  under the extended trigger, diagnostic parity still 0 mismatches.

## Decisions

- v116 smoke: rejected; v116 continuous-clearance metric retained.
- Dataset inclusion list: still empty.
- Next: deploy v117, one isolated qualification smoke under
  `.tmp/wp2_v117_smoke_monitor_contract.md`, then the exact-20 campaign
  only if every gate passes.
