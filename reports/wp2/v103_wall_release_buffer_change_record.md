# WP2 v103 wall-release buffer change record

## Trigger

The stopped v102 run `run_1784724979_66888` contains two intact wave-19
threshold-chatter clusters before its unrelated telemetry gap. After wall
recovery released at roughly 425-429 units, a dense 24-37 enemy pack pulled the
teacher back into a 285-310 unit wall band. Rolling two-second windows reached
11 and 16 major action reversals with only 5.9 and 73.3 units of net movement.
The latch correctly re-entered below 280 and then produced stable inward motion,
so the defect is insufficient release clearance rather than a broken latch.

That run is excluded from teacher data because a monitor full-file read denied
the live writer for 16.204 seconds, leaving one 356-sequence gap and
`telemetry_complete=false`. The behavioral evidence cited above precedes that
gap and has no JSON parse, schema, validity, invalid-count, or capacity-drop
faults.

## Reversible repair

- Keep the v102 entry threshold at 280 units.
- Raise only `BOSS_FINALE_WALL_RECOVERY_RELEASE` from 420 to 520 units.
- Preserve projectile-safety priority, predictive hard-wall clamping, centered
  finale behavior, and automatic boss targeting without a range ring.
- Advance policy identity to `teacher_v1-0.1.103-gun-wp1` and mod identity to
  `0.2.11-wp2-capture`; the combat-capture schema hash is unchanged.

Reversion is a one-constant rollback to the v102 420-unit release threshold plus
the corresponding version identifiers.

## Verification

- Focused policy/collector tests: `52 passed`.
- Full suite: `98 passed`.
- Deployment ZIP SHA-256:
  `51998FDD361A2F5C3EC0EEA2C9D94E7EA4A538CB487D9E78E91BAD646CBE15AF`.
- Smoke launch: `1/1`; mod ready, zero loader fault matches, zero recent
  Brotato/Godot WER reports, Brotato stopped, and auto-start restored to false.
- Live proof remains required before accepting v103 teacher data: zero
  260-520-unit threshold-chatter windows, zero false latch drops below 520, and
  all existing projectile, hard-wall, centered-finale, telemetry, and schema
  gates must pass.

## Monitoring correction

Live raw telemetry must be opened with explicit read/write/delete sharing.
Long-lived `Get-Content`, `File.ReadLines`, or default .NET read handles are
forbidden while Brotato is writing. Full-file audits run only after a run closes;
live checks use short shared reads and collector state freshness.
