# WP2 v114 smoke stop-and-repair report

The one-run v114 qualification smoke completed with a wave-20 victory, but it
is rejected and excluded from the training dataset. Capture structure and
identity were clean across 21,144 captures and all 20 waves; the collector and
Brotato exited, auto-start is false, and no post-start APPCRASH was found.

The terminal teacher-safety audit found two adjacent boss-wave wall/body relief
violations at captures 20467 and 20468. The emitted routes had predicted body
clearance 18.9 and -2.6, while hard-wall-safe sampled lanes offered 79.4 and
57.7. Each alternative improved clearance by just over the required 60 units.

The final arbiter used the restricted wall-progress pool's best clearance as
its relief reference. Continuity selected a slightly worse command than that
reference, which hid the qualifying gain over the route actually emitted.
v115 instead compares the hard-safe lane with the more dangerous of the strict
pool best and the incoming final-body command. The frozen captures now exercise
this boundary in a regression test.

Verification after the repair: 96 focused tests and all 122 repository tests
passed. A new v115 qualification smoke is required before any exact-20 dataset
collection begins.
