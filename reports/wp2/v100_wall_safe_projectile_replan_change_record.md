# v100 wall-safe projectile-replan change record

Date: 2026-07-22

## Trigger

The first v99 collection run, `run_1784717615_58915`, completed as a wave-17
defeat. Its 1,046 wave-17 combat captures had zero invalid/schema/drop findings,
zero outward commands inside the 96-unit hard margin, zero 300 ms projected
hard-margin crossings, and zero corner visits. The wall geometry repair itself
was working.

The combined projectile/wall audit exposed a different defect. Projectile
safety was active in 557 captures. In 19 captures, the sampler exposed a
materially safer projectile lane but the unconditional hard component clamp
zeroed one axis and renormalized the other, turning a safe diagonal into a
clearly hazardous cardinal command. Representative input/escape/final
clearances were 173.317/242.971/67.537 at seq 18741 and
222.373/291.654/7.073 at seq 19072.

Collection stopped during partial successor `run_1784718564_7093`. Only the
verified collector PIDs 16792/44100 and scoped Brotato PID 8012 were stopped;
auto-start was set false and all raw telemetry was preserved.

## Reversible repair

- Keep the final ordering: projectile safety first, hard predictive wall safety
  last.
- Detect only an active projectile-safe command that the hard clamp materially
  rotated and whose post-clamp clearance is below the finale panic threshold.
- Resample the existing projectile/enemy objective over the 24 directions after
  each direction passes the same hard 300 ms component clamp.
- Accept a replacement only when its final projectile clearance is at least 20
  units better than the clamped baseline.
- Use the ordinary 120-unit enemy path threshold for this narrow physical-safety
  arbitration; the projectile caution multiplier remains unchanged.
- Expose final emitted-command clearance and wall-safe replan activation in
  `finale_translation` for direct runtime audit.
- Advance policy identity to `teacher_v1-0.1.100-gun-wp1` and mod identity to
  `0.2.8-wp2-capture`; the combat-capture schema hash remains unchanged.

## Verification and deployment

- Focused policy and collector tests: 50 passed.
- Full repository suite: 96 passed.
- Offline replay of all 19 v99 regression states repaired all 19; every selected
  command gained at least 20 final-clearance units. The panic-only gate avoids
  altering already-safe clamp outcomes.
- Workshop and local deployment archives match byte-for-byte: SHA-256
  `05FF645D3545DDFBDA70E037DB029AA5C41411B209614D90EEA50911D69B94EA`.
- Stopped smoke launch loaded the v100 controller successfully
  (`AgentController ready`) with no agent script/parse/load error and no
  post-start APPCRASH evidence. The verified smoke PID 22788 was stopped and
  auto-start remained false.
