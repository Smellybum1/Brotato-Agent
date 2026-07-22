# v106 isolated smoke safety audit

Run `run_1784741387_38832` completed all 20 waves and won with valid, complete
telemetry. It is nevertheless excluded from teacher collection.

The closed replay found ten wave-17--20 decisions where projectile selection
had produced a body-safe route but the final wall-component clamp rotated the
emitted command below the 45-unit body-clearance tier. The affected capture
sequences were 16721, 16722, 17068, 17073, 17076, 17083, 17086, 17452, 17453,
and 17456. Capture 17073 was the clearest case: the emitted route had predicted
body clearance -3.1983 despite a safe sampled route.

The replay also confirmed the operator's pack-entry observation on wave 17.
Immediately before a 15-damage hit, capture 17329 emitted a route with predicted
body clearance 33.3 while nine sampled routes were contact-safe and the best
offered 50.8. Neither projectile safety nor wall recovery was active, proving
that the v106 body checks were confined to two selectors and did not protect the
ordinary final movement path.

The collector's reported failure was a separate infrastructure race. It opened
`summary.json` after the file appeared but while the producer was still writing
it. The closed file is valid and reports a victory, but the collector is being
changed to retry this short partial-write window.

Acceptance decision: **rejected; repair and requalify as v107**.
