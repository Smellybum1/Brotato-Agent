# v107 final body-safety repair

## Evidence

The winning v106 isolated smoke still emitted ten projectile-safe commands that
became body-unsafe after final wall projection. It also took an avoidable
wave-17 hit after ordinary movement chose 33.3 units of predicted body clearance
while nine sampled lanes cleared the 45-unit contact tier.

## Change

Every wave-17--20 command now passes a final body-safety selector after
projectile selection and wall projection, including the low-health survival
return. Candidate commands are hard-wall clamped before evaluation. While wall
recovery is active, only wall-improving candidates remain eligible. Projectile
clearance is preserved lexically at the safe tier, then the panic tier, or—only
when every sampled lane is below panic—within the existing bounded 60-unit
concession. Inside that admissible set, the selector requires 45 units of body
clearance when available and then rejects materially denser pack routes.

The final diagnostic now records whether the body repair activated and reports
input, best, selected, and projectile-floor clearances for closed replay audit.

The collection helper also retries a briefly missing or partial `summary.json`
for two seconds, fixing the non-atomic producer-write race seen after the v106
victory.

## Identity and rollback

Policy identity advances to `teacher_v1-0.1.107-gun-wp1`; mod identity advances
to `0.2.15-wp2-capture`. The combat-capture schema hash is unchanged. The repair
is isolated in the final late-wave safety tail and can be reverted independently
by reverting this versioned change.
