# v87 change record - health-banded finale recovery

- **Date:** 2026-07-22
- **Version:** `0.1.87-gun-wp1`
- **Scope:** one evidence-backed finale movement adjustment plus correction of
  the active runtime boss-telemetry path.

## Evidence

v86 stopped at **0W/2L** despite passing its two-run median DPS targets. Direct
wave-20 telemetry showed that the agents were not disengaged:

- `run_1784652432_11752` stayed within 700 units for 91% of sampled finale
  ticks, dealt 11,998 boss damage in about 22 seconds, and reached 8 HP.
- `run_1784653555_21284` stayed within 700 units for 88% of sampled finale
  ticks, dealt 17,668 boss damage in about 48 seconds, and reached 5 HP.

At critical health, v86 still spent 70–100% of its sampled ticks within 700
units. Its 55% engagement weight therefore did not create a meaningful recovery
lane. The excluded partial third run is `run_1784654708_29918`.

## Focused movement repair

- Above 85% HP: unchanged full boss-range finale controller.
- From 50% through 85% HP: **35% engagement / 65% panic-repulsion survival**.
- At or below 50% HP: **10% engagement / 90% panic-repulsion survival**.
- The blended direction still passes through projectile urgency, reversal
  prevention, corner escape, and displacement commitment; automatic weapon fire
  continues while the agent creates separation.

This is intentionally health-adaptive. It preserves the operator-requested boss
pressure while the build can afford it, then prioritizes enough survival time to
convert already-demonstrated applied damage into a kill.

## Runtime telemetry correction

The v86 adapter carried boss max HP/name and relative coordinates, but the live
controller used its own `_gather_combat_state` snapshot. v87 adds the same boss
fields and player-relative `nx` / `ny` normalization to that active path. This
does not change control inputs; it makes the emitted finale telemetry complete.

## Next gate

Run a four-result focused gate with `-Runs 4 -MinWins 3`, stopping on the second
loss or any safety trigger. Promotion criteria remain those in `docs/ROADMAP.md`.

## Validation and deployment

- Focused source/policy suite: **38 passed**.
- Full repository suite: **67 passed**.
- Both installed archives contain the exact 18 source files with no missing,
  mismatched, or extra entries; both have SHA256
  `31D7A1BEE06823315ABCED37EFB51CAA94B9B4F17A86E6F90C9B9E25DBBA0377`.
- ModLoader smoke reached `Init`, `Ready`, and `AgentController ready`, with no
  post-start APPCRASH evidence.
- Fresh runtime evidence began with `run_1784655193_70481` on policy
  `teacher_v1-0.1.87-gun-wp1`; telemetry was fresh and healthy.
- The focused gate ran under exact tasks `BrotatoAgent-LiveMonitor-v87` and
  `BrotatoAgent-Supervisor-v87`.

## Terminal gate outcome

v87 stopped at its second-loss threshold with **1W/2L**:

- `run_1784655193_70481`: defeat on wave 20; 15,075 sampled boss damage in
  33 seconds, minimum 7 HP.
- `run_1784656326_81110`: victory on wave 20; the sampled boss trajectory fell
  from 29,250 to 195 HP before the kill.
- `run_1784657506_7787`: defeat on wave 20; 17,884 sampled boss damage in
  16.5 seconds, minimum 9 HP.

The briefly re-armed `run_1784658637_9821` is excluded. The exact v87 tasks,
their scoped process trees, and Brotato were stopped. All three complete runs
passed isolated telemetry validation, with no errors, hangs, illegal actions,
APPCRASH, or invariant failure. RSI remained diagnostic and non-separating.

v87 proved that lowering a scalar engagement weight is the wrong abstraction:
generic flee repeatedly contributed a radial component that carried the agent
away from the weapon-range ring. The losses still applied substantial damage,
but did not survive long enough to finish the boss. v87 is superseded by v88's
ring-preserving tangential recovery controller.
