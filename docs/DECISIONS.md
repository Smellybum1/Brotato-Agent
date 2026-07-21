# Decisions (WP1)

## D1 — Derive teacher from full-autobot under GPL-3.0

**Decision:** Fast path uses `brotato-full-autobot` (GPL-3.0). `Tom-BrotatoAgent` is a derived work under GPL-3.0 with attribution.

**Rejected:** Clean-room rewrite for WP1 (too slow); claiming MIT for derived teacher code.

## D2 — ModLoader GDScript path; no Godot install for WP1

**Decision:** Deploy unpacked GDScript mods to the installed Steam game. Do not install Godot unless extraction becomes necessary.

## D3 — Benchmark Danger 0, not upstream Danger 6

**Decision:** Difficulty robot button / auto-start selects **Danger 0**. Upstream defaulted to Danger 6.

## D4 — Project lives outside the game install

**Decision:** Source of truth is `C:\Codex\Brotato Agent`. Deploy copies into `mods-unpacked` only.

## D5 — Instrumented track only for WP1

**Decision:** Exact in-engine state. Do not claim human-observation parity.

## D6 — Telemetry under `user://brotato_agent/`

**Decision:** JSONL written inside Godot user data, then collected into repo `runs/` by scripts (gitignored raw data).

## D7 — Auto menu navigation best-effort

**Decision:** Orchestrator clicks character/weapon/start via scene-tree heuristics; difficulty auto-start is explicit. Failures are repaired from logs, not by editing saves.

## D8 — Mod deploy uses Workshop zip + profile object form

**Decision (verified 2026-07-17):** On Brotato 1.1.15.4 + bundled ModLoader:

- Bare `mod_list` values like `"ModId": true` crash/exit during ModLoader init.
- Working profile entry shape:

```json
"ModId": {
  "is_active": true,
  "zip_path": "C:/Games/Steam/steamapps/workshop/content/1942280/<id>/ModId.zip"
}
```

- Local `mods-unpacked/` next to the exe is **not** visible as `res://mods-unpacked/` on the exported build.
- Reliable discovery is Steam Workshop content under `steamapps/workshop/content/1942280/<subscribed_id>/` (subscribed items listed in `appworkshop_1942280.acf`).
- Stage B baseline: official Workshop item `3737864106` (Full Auto Bot) subscribed and enabled in-game.
- `Tom-BrotatoAgent` is packaged as a zip with top-level `mods-unpacked/Tom-BrotatoAgent/...` and placed beside the subscribed Workshop content (or referenced by absolute `zip_path`). Upstream is set `is_active: false` while the agent is active.

## D9 — Rogue Ranker items-only shop allowlist (reversible)

**Decision (2026-07-19):** When `BotConfig.EXPERIMENT_ROGUERANKER_ITEMS_ONLY` is true, non-weapon shop buys and crate takes must be ids present in `ROGUERANKER_ITEM_TIERS` (S–D). Off-list items score `-1e9` / crate discard. Weapons are unchanged.

**Revert:** set `EXPERIMENT_ROGUERANKER_ITEMS_ONLY := false` (restores soft RR bonus only).
