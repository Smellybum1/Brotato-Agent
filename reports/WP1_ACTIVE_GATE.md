# BrotatoAgent WP1 closeout runbook

Updated: 2026-07-22 08:25 Australia/Brisbane

## Current state

- WP1's statistically certified batch remains v72: exactly 20 valid
  Well-Rounded / SMG / Danger-0 runs, 18 victories and 2 defeats, with zero
  errors, hangs, illegal actions, or APPCRASH evidence.
- Installed teacher candidate: v92 (`0.1.92-gun-wp1`,
  `teacher_v1-0.1.92-gun-wp1`). Its first eligible decision run,
  `run_1784670237_52694`, won and met the DPS, economy, applied-boss-damage, and
  safety criteria. The operator explicitly designated a win as the transition
  to roadmap Step 2, so v92 is the WP2 teacher candidate. This single run is not
  a replacement win-rate certification.
- All exact v92 and temporary v920 watchdog tasks are disabled and stopped.
  Their scoped command/Python process trees and Brotato are stopped.
- Both installed v92 archives are byte-identical at SHA-256
  `A0911C7F56BA8233C48E3B5D60AB4F4AFF4BD00FA2E5FAD070CAC5AA2DFAA639`.
- Exclude partial runs `run_1784671380_41100`, `run_1784671580_93166`, and
  `run_1784671796_43736` from every comparison or certification claim.

## Active roadmap step

Step 2 is WP1 repository/evidence closeout. The 2026-07-22 audit reconfirmed:

- v72 raw telemetry validation, terminal completeness, CSV/Markdown parity,
  and victory/defeat chaining;
- a fresh readable user-data backup and unchanged Steam executable/package
  hashes;
- clean third-party trees at the documented pinned commits and intact license
  notices;
- a clean copied checkout can run `scripts/bootstrap.py` and then pass all
  67 tests using a workspace-local pytest basetemp.

Formal WP1 PASS is now claimable. The operator physically exercised manual
override and emergency stop on excluded v92 run `run_1784677381_46728`;
telemetry recorded the two signals at sequences 728 and 729, followed by a clean
shutdown with auto-start restored to false. The operator explicitly authorized
the prepared initial local commit and local `wp1-baseline` tag. See
`reports/WP1_SAFEGUARD_EXERCISE.md` and `reports/WP1_FINAL_REPORT.md`.

## Next authorized actions

1. Preserve the stopped state; do not start another evaluation campaign.
2. Create the authorized passing baseline commit and local `wp1-baseline` tag.
3. Begin WP2 from that tag under the unchanged WP2 packet and recorded operator
   amendments.

## Guardrails

- Preserve every dirty/untracked/user-owned file. Staging, the initial local
  commit, and the local `wp1-baseline` tag are explicitly authorized; do not
  push, clean, or broadly refactor.
- Do not count interrupted or automatically started partial runs.
- Do not deploy another policy version or start another evaluation campaign as
  part of closeout.
- Before any future live action, re-check exact scheduled tasks, scoped process
  trees, Brotato, telemetry freshness, installed version, and APPCRASH evidence.
