# v79 change record

Date: 2026-07-21 Australia/Brisbane

v79 is a focused repair of the two failures observed in the stopped v78
comparison. It retains v78's weapon-aware offense metric, hard sustain veto,
utility-lock policy, and finale displacement commitment.

## Shop safety repair

- Weapons are no longer passed through the generic-effect utility-lock veto.
  Their offensive value is evaluated by the weapon-aware DPS model.
- Affordable usable weapons can satisfy the offense-first path when offense is
  materially below target.
- An unlocked deficient-offense utility item is expired for the current shop
  visit so it cannot immediately re-enter a premium lock path.
- Both the strategy and controller enforce a maximum of two lock-state
  transitions for the same item in a wave. A third attempted transition ends
  the shop with `shop_cycle_guard` telemetry instead of looping.

## Crowd-clear calibration

- Late-wave offense target margin increased from 10 to 25.
- Prior-wave p90 density pressure increased from 4 to 7 offense points per
  enemy above the goal, capped at 90 rather than 45.
- Prior-wave peak density is now retained and displayed. Peaks above 25 add
  two offense points each, capped at 30.
- This makes the v78 wave-19 failure's preceding pressure demand an offense
  target of about 215 rather than accepting its displayed 199.9 as adequate.

## Verification

- Python/source suite: 60 passed.
- Real Steam/Godot launch: mod loaded, initialized, became ready, and created
  the AgentController without parse or script errors.
- Workshop and local archives are byte-identical at SHA-256
  `7C19D613046A40170E0DEB013A44F72AB0BACFFAE8030BD19D5F527C4CAA61F5`.

