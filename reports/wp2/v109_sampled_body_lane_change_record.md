# WP2 v109 sampled body-lane change record

## Scope

v109 is a reversible teacher-policy revision over v108. It does not rewrite or
admit any v108 telemetry. It changes only final body-lane qualification and the
audit evidence needed to verify that qualification.

## Trigger evidence

- Source: `run_1784749223_5710` (v108 exact-20 source 1, rejected).
- Source events SHA-256: `DAED690E1BAF3A785DFA7E244B808ECB4AC230566D5C58D7983A495B5E4DCE4F`.
- Source summary SHA-256: `2BB20F23E973C3BCDBD87F7C04CA742DEADDBCDDB6893F6889CEA7D3C520DA97`.
- Mandatory audit failure: active body repair at capture 20755 emitted the
  arena-center clamp fallback at 26.615 degrees, outside the 15-degree sample
  grid.
- Operator-observed pack-through evidence at capture 20604: the strict-safe
  150-degree lane had projectile clearance 223.323166 and body clearance
  61.504105. A 195-degree lane retained approximately 177.7 projectile
  clearance (above the 72.6 panic threshold), gained approximately 25 body
  clearance units to 86.5, and cost less than the existing 60-unit concession.

## v109 invariants

1. A candidate reported as a sampled final body repair must remain one of the
   24 sampled directions after hard-wall clamping.
2. A bounded body escape may relax the strict projectile tier only when it
   gains at least 20 predicted body-clearance units.
3. The relaxation may cost at most 60 projectile-clearance units and may not
   cross below panic while any panic-safe lane exists.
4. Once relaxed, the emitted lane must remain within five units of the best
   available body-clearance lane in that relaxed tier.
5. Hard-wall projection and active projectile safety remain mandatory.

## Exclusions and rollback

`run_1784749223_5710` and interrupted successor `run_1784750348_75123` remain
excluded from the training dataset. Rollback is the single v109 policy commit;
the immutable v108 raw evidence and its reports remain available for comparison.
