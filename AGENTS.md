# BrotatoAgent collaboration workflow

These instructions apply to the entire repository. This is a Claude-specific
workflow (operator directive, 2026-07-23): the primary agent is Claude Fable,
and Fable tokens are limited — the primary agent does only the work that
genuinely needs its judgment and delegates everything else.

## North stars

1. **Win a Danger 5 run.**
2. **Win a Danger 5 run with every character.** (Operator, 2026-08-03 — supersedes the earlier
   *"get good with every character"*, which had no pass condition.)

Both are the game's own definition of success: binary, terminal, un-gameable.

**Current status: 0 Danger 5 victories, any character**; median D5 terminal wave **11 of 20**.
§28 established that D5 failure is **clearance-limited, not survival-limited** — the agent dies
because it kills too slowly, not because it is fragile. A defensive lever justified by *"D5 kills
us"* is **not licensed**.

**Sequencing:** pursue (1) first. The operator's expectation is that what it takes to win one D5
run transfers substantially to (2). ⚠️ That transfer is a **directive, not a measured finding** —
§25 is a strong null on cross-character generalisation (p = 0.791, treatment provably engaged) and
§27 measured `cyborg` at 0/16 despite the closest profile to `well_rounded`. Do not cite it as
established.

Full statement, measured distance, and what binds each: **`docs/ROADMAP.md`**.

## Primary-agent responsibilities

The primary agent (Claude Fable) owns the work that benefits most from full
project context and judgment:

- define objectives, success criteria, roadmap sequencing, and stop conditions;
- make architecture, policy, safety, deployment, and evidence-quality decisions;
- investigate ambiguous or high-risk failures and choose the repair strategy;
- integrate concurrent work, review every material diff, and resolve conflicts;
- perform the final requirement-by-requirement audit and report conclusions;
- retain direct control of destructive actions, live campaign stop/redeploy
  decisions, commits, external publication, and other consequential mutations.

The primary agent must not outsource final judgment or treat a subagent's claim
as proof. It reviews the relevant source, diff, tests, and runtime evidence
itself before accepting work.

## Default delegation policy

Delegate most other concrete, bounded work to subagents by default, including:

- repository/file discovery and focused evidence extraction;
- independent telemetry or failure-mode analyses;
- mechanical or well-specified implementation slices;
- focused tests, fixtures, validation scripts, and regression runs;
- documentation, change records, reports, and parity checks;
- routine monitoring/audit calculations that can run independently.

Required subagent configuration: **Claude Opus 5 at LOW reasoning effort**
(operator directive 2026-07-25 — Opus 5 is capable enough at low effort;
use the project agent definition `.claude/agents/opus-delegate.md`, i.e.
`subagent_type: "opus-delegate"` on the Agent tool). Delegate
by default to conserve Fable tokens; reserve the Fable primary for
architecture, safety, evidence-quality judgment, final diff review, and
qualification decisions. Never mislabel a different model as Opus.

Use parallel Opus subagents when
two or more independent bounded slices can make useful progress concurrently.
Give each subagent explicit scope, evidence, guardrails, expected deliverables,
and file ownership. Avoid parallel edits to the same file unless the primary
agent intentionally coordinates them.

## Integration and safety

- Preserve all user-owned dirty and untracked files.
- Do not clean, prune, push, or perform destructive repository operations
  without explicit authorization.
- Subagents share the working tree. The primary agent checks current state
  before integration and reviews the combined diff for accidental overlap.
- Applicable project/user guardrails and live-campaign stop conditions always
  override delegation convenience.
- The primary agent reads and interprets required skills/instructions itself;
  subagents may execute task slices only after those requirements are set.
- Run the narrowest relevant check first, then broaden in proportion to risk.
  A green subagent check does not replace primary-agent final verification.

## Communication

The primary agent tells the user when delegation materially affects timing,
scope, model availability, or confidence. Routine subagent coordination need
not create noise, but final reports identify delegated work that materially
influenced the result and the primary verification that accepted it.
