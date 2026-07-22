# WP2 v110 held-command and body-lane change record

## Trigger

The second v109 exact-20 source, `run_1784754592_59450`, was structurally
complete but failed the mandatory safety audit at capture sequences `20757`,
`20759`, `20932`, and `21233`. Each frozen wave-20 row retained an outward
component whose fresh 300 ms projection crossed the 96-unit hard margin.

The commands had been safe when produced by the 20 Hz finale controller and
were replaced before the player crossed the margin. However, wave 20 holds a
decision across intervening 60 Hz physics ticks. A 300 ms decision-origin
projection therefore did not prove the stronger contract that the current
command remains 300 ms-safe throughout its complete 50 ms hold interval.

The operator also reported that the terminal movement visibly dodged through a
pack despite clearer alternatives. Frozen capture `21282` corroborates that
observation: the emitted lane retained `124.864822` body-clearance units while
another sampled lane inside the same projectile tier retained `182.581696`.
The old ordinary body floor was only 45 units once any contact-safe lane
existed, so that 57.7-unit avoidable concession was legal.

## Reversible repair

v110 changes `BOSS_FINALE_WALL_COMMAND_HORIZON` from `0.30` to `0.35` seconds.
The additional 50 ms equals one complete wave-20 recompute interval
(`3 / 60 Hz`). Projectile, body-clearance, wall-recovery, centering, and shop
policy inputs are unchanged. The existing hard-wall audit remains at 300 ms;
the runtime reserve is deliberately stronger so every intervening tick can
still satisfy that audit horizon. Within the final body-safety pass, an
ordinary wave-20 lane must now retain up to 160 body-clearance units when the
same projectile tier exposes them, staying within 20 units of the best lane
below that cap and never below the existing 45-unit contact-safe floor. The
five-unit emergency rule remains stronger. Waves 17-19 keep their existing
body policy.

Runtime identity is advanced to policy `teacher_v1-0.1.110-gun-wp1` and mod
`0.2.18-wp2-capture`; the compatible combat-capture schema hash is unchanged.
Rollback is the single v110 policy commit.

## Evidence scope

- Rejected v109 events SHA-256:
  `319109C6EB3E4934C0C7B9702FD3C43078C8DA8CACBD831DC6D8019341F95A28`.
- Rejected v109 summary SHA-256:
  `5223F487825AAE4666864FF0AEC838C83C6C27571F450B6AB938E9772047E8C2`.
- Accepted v109 run 1 and rejected v109 run 2 remain immutable diagnostic
  evidence. Partial successor `run_1784755762_71415` is excluded.
- No v109 source may enter the v110 dataset. v110 requires a fresh isolated
  smoke followed by a fresh exact-20 campaign.
