# Pro director judgment (2026-07-18)

Source thread: https://chatgpt.com/c/6a5a1819-fbf4-83ec-bbb3-a2c4287b9d06  
Captured after overnight-autonomy status update from Grok.

## Director judgment on WP1

WP1 is **not yet formally PASS-ready** from the status update alone, although it appears very close. The current 20-run supervisor is the final major live-play gate. No additional 20-run batch is required if that batch passes cleanly, but the wrap-up must still provide:

1. **Final batch integrity:** exactly 20 valid Well-Rounded/SMG/D0 runs, at least 18 victories, normal settings, Endless off, no retries, no manual rescue, zero hangs, and zero illegal meta-game actions.
2. **Complete terminal evidence:** every run must have a `run_end` event and summary. Victory-to-next-run and defeat-to-next-run chaining must both be demonstrated. If the batch finishes 20/20, run a separate controlled defeat-path test rather than leave the death-screen repair unverified.
3. **Telemetry validation:** raw JSONL passes schema, sequence-number, required-field, and terminal-completeness checks; CSV and Markdown batch reports agree with raw events.
4. **Operational safeguards:** manual override and emergency stop actually exercised, including clean recovery or shutdown afterward.
5. **Reproducibility and integrity:** documented bootstrap/deploy/launch/test commands, verified user-data backup, intact Steam installation and saves, pinned third-party revisions, and licensing notices.
6. **Repository closeout:** tests pass from documented clean local-bootstrap state, working tree clean, exact passing commit locally tagged `wp1-baseline`.

The final 12-section WP1 report should contain those proofs and the complete 20-run table. Provided they are present, Grok may immediately branch into WP2 without another director consultation.

## Work Package 2 packet

- File: `Grok_4.5_Brotato_Work_Package_2_Prompt.md`
- SHA-256: `efadf505ed05bf760e55fee7ca0379842f93a783d53c565eb29164c9cf971399`
- Local copies:
  - `C:\Codex\Brotato Agent\docs\pro\Grok_4.5_Brotato_Work_Package_2_Prompt.md`
  - `C:\Tools\Downloads\Grok_4.5_Brotato_Work_Package_2_Prompt.md`

**Directive:** Give the file to Grok unchanged once WP1 report says PASS; if the current batch misses the gate, continue repairing WP1 rather than starting WP2 or returning a routine update.

WP2 scope summary: combat movement only (freeze economy/orchestration), combat lab, entity-centric obs encoder, ≥200k teacher transitions, BC (3 seeds), ≥2 DAgger rounds, bounded residual PPO, ONNX + loopback Python sidecar, latency/fallback tests, 2 ablations, sealed paired 100-episode teacher-vs-learned benchmark, new 20-run full-game gate (≥18 wins), local tag `wp2-learned-combat`, no-push/no-publish.
