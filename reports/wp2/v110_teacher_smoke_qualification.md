# WP2 v110 teacher smoke qualification

## Result

Accepted isolated smoke `run_1784756811_72945`: victory through wave 20 with
21,244 valid combat captures and every wave represented. This smoke is
qualification evidence only and is excluded from the future exact-20 dataset.

## Identity and deployment

- Policy: `teacher_v1-0.1.110-gun-wp1`
- Mod: `0.2.18-wp2-capture`
- Capture schema SHA-256:
  `95B6444796A21FD44E94113B75BA2097BC381D5F72ED784F9B9A4A99DD46D951`
- Matching workshop/local deployed ZIP SHA-256:
  `71FFFA6152B55D59B9CDE4E30A46EE794D823EE1D3B335F4BEF640893DD82446`

## Gates

- Capture audit: zero schema mismatches and zero invalid captures/actions.
- Safety audit: zero violations across 4,940 late captures and 3,738 fresh
  late decisions.
- Safety exercise: 1,067 body repairs, 438 projectile-safety activations, and
  1,189 wall-recovery activations.
- Three late damage events were retained; none exposed an avoidable final
  command under the v110 projectile/body contract.
- Zero telemetry error events, zero collector stderr, and zero post-start
  Brotato Application Error events.
- Collector and scoped Brotato exited; auto-start was verified false.

Events SHA-256:
`D80ABF0CE58E7706966DA83C2657C82C5D86283C3D37FB93AB284C37A2D34B2C`

Summary SHA-256:
`3D059A1F42D1ABE7B2864EB25B128A5309AAFFF066A7D1764D15FC7170999D76`
