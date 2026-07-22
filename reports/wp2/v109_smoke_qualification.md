# WP2 v109 isolated smoke qualification

The isolated v109 smoke is **qualified** for a fresh exact-20 campaign.

## Scope

- Runtime identity: capture schema `95B6444796A21FD44E94113B75BA2097BC381D5F72ED784F9B9A4A99DD46D951`, policy `teacher_v1-0.1.109-gun-wp1`, mod `0.2.17-wp2-capture`.
- Deployed archive SHA-256: `7154D0E4D571435AB8592BCFA5B6BCC11B8CCDF2F0C49823924D0018C217B197` in both workshop and local locations.
- Accepted diagnostic source: `run_1784751818_75406` only.
- The initial zero-run launch with mods disabled created no source and is excluded.
- This accepted smoke is diagnostic evidence only and remains excluded from the exact-20 dataset.

## Result

- Victory through wave 20 with 21,545 combat captures and all waves represented.
- Terminal summary complete; zero telemetry errors, hangs, illegal actions, malformed lines, schema mismatches, invalid captures, invalid actions, or dropped/invalid entities.
- Zero body-tier, body-repair, body-diagnostic, sampled-action, wall-recovery, hard-wall, projectile-floor, or avoidable-damage violations.
- Wave 20 contained no `body_emergency_active` decision; the ordinary body safety tier and emitted-action replay checks remained clean.
- Three late damage events were retained for review, with zero avoidable damage-path violations; the run still won.

## Audit clarification

The first safety-audit pass treated 40 `body_selected_projectile_clearance == -1` sentinels as selected-lane floor failures. Raw evidence showed the body layer had no eligible sampled lane in every case, made no body repair, and preserved its incoming command unchanged: input, best, and selected body clearance were identical. The audit now records this exact no-choice fallback separately and continues to reject any activated repair, changed body lane, emergency, or non-sentinel selected projectile clearance below its floor. Focused regression tests cover those distinctions.

## Integrity

- Events SHA-256: `CD53D5B3FEB21503EBD0CFBA12997BDE6D3298C5124CBA3F9AA874E34B7857F6`.
- Summary SHA-256: `2CAA03CC3B3BE4A6173FB0F46D87DC2C18723C7981D5701E974E2FFA54D402D4`.
- Collector and scoped Brotato process stopped; auto-start false after completion.
