#!/usr/bin/env python3
"""Archive Brotato mid-run saves as reusable wave-20 test fixtures.

Brotato continuously writes `%APPDATA%/Brotato/<steamid>/run_v3_0.json`, a complete
mid-run state: current_wave, the player's weapons/items/effects/gold/HP, shop state,
enemy scaling, and -- critically -- `bosses_spawn`, which PREDETERMINES the wave-20
boss. Snapshotting that file at wave 19 gives a restartable fixture: the same build,
against a known boss, replayable in the length of one wave instead of a full ~20
minute run.

Why this matters: a single wave-20 Predator observation currently costs ~42 min of
wall clock (20 min/run / 0.67 reaching w20 / 0.71 drawing Predator). From a fixture
it costs the length of one wave.

Why a LIBRARY and not one fixture: a controller tuned against a single build will
overfit to it. This project has a documented history of exactly that failure --
gates tuned to a single observed death. Collect many wave-19 states across many runs
so a finale controller is evaluated on a distribution of builds, not an anecdote.

READ-ONLY with respect to the game. This copies files; it never writes into the game's
save directory, never launches or stops anything, and is safe to run alongside a live
collector campaign.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import time
from pathlib import Path


# The save file's boss ids do NOT match the entity script paths seen in combat
# telemetry. Verified 2026-07-26 against run_1785036448_61774, which carried
# bosses_spawn ["boss_crab"] at wave 19 and then 526 captures of
# res://entities/units/enemies/predator/ at wave 20.
#
# This matters: "predator" is the boss the agent actually loses to (0% stationary
# projectiles, all moving at 500 u/s), while "invoker" is 96.3% stationary and has
# never beaten the agent. Selecting fixtures by the wrong id would silently build a
# library of the easy boss.
BOSS_ID_TO_ENTITY = {
    "boss_crab": "predator",
}


def boss_label(bosses_spawn) -> str:
    """Familiar entity name where known, else the raw save id (never guess)."""
    raw = (bosses_spawn or ["unknown"])[0]
    return BOSS_ID_TO_ENTITY.get(raw, raw)


def runs_dir() -> Path:
    return Path(os.environ["APPDATA"]) / "Brotato" / "brotato_agent" / "runs"


def newest_telemetry_run_id(runs_root: Path | None = None) -> str | None:
    """Name of the run directory whose events.jsonl was written most recently.

    That directory is the LIVE run, so it is the run whose save file we are
    snapshotting. Returns None -- never a guess -- when no candidate exists.

    WHY this field exists: on 2026-07-26 two fixtures captured 6 s apart from the
    SAME run were mistaken for two independent builds, because nothing in the index
    linked a fixture back to its source run. Recording the run id lets the library
    be built one-build-per-run (see select_library).
    """
    root = runs_dir() if runs_root is None else runs_root
    try:
        candidates = [
            p for p in root.iterdir() if p.is_dir() and (p / "events.jsonl").exists()
        ]
    except OSError:
        return None
    if not candidates:
        return None
    try:
        newest = max(candidates, key=lambda p: (p / "events.jsonl").stat().st_mtime)
    except OSError:
        return None
    return newest.name


def select_library(index_rows, boss: str, one_per_run: bool = True) -> list[dict]:
    """Fixture rows for `boss`, at most one per source run when one_per_run.

    Two fixtures from the same run are the SAME build and do not constitute
    independent evidence about a controller; grouping by source_run_id is what
    makes the library a distribution of builds rather than an anecdote repeated.

    Within a run the LOWEST-gold row wins: gold is spent in the wave-19 shop, so the
    low-gold state is the POST-shop one. Resuming from it starts the trial at the
    finale rather than re-running the shop, which both costs wall clock and lets
    shop policy vary between trials that are meant to differ only in the controller.

    Rows with a null/absent source_run_id are each their own group -- they predate
    the field, and merging them would silently drop evidence.
    """
    selected: dict[object, dict] = {}
    out: list[dict] = []
    for i, row in enumerate(index_rows):
        label = row.get("boss")
        if label is None:
            label = boss_label(row.get("bosses_spawn"))
        if label != boss:
            continue
        if not one_per_run:
            out.append(row)
            continue
        run_id = row.get("source_run_id")
        key: object = run_id if run_id else ("__nogroup__", i)
        current = selected.get(key)
        if current is None or _gold_key(row) < _gold_key(current):
            selected[key] = row
    if not one_per_run:
        return out
    return list(selected.values())


def _gold_key(row: dict) -> float:
    gold = row.get("gold")
    if isinstance(gold, (int, float)):
        return float(gold)
    return float("inf")  # unknown gold never beats a known one


def save_dir() -> Path:
    base = Path(os.environ["APPDATA"]) / "Brotato"
    cands = [p for p in base.iterdir() if p.is_dir() and p.name.isdigit()]
    if not cands:
        raise SystemExit(f"no steam-id save dir under {base}")
    return cands[0]


def read_state(path: Path) -> dict | None:
    """Tolerant read -- the game rewrites this file continuously, so torn reads happen."""
    try:
        raw = path.read_text(encoding="utf-8")
        return json.loads(raw).get("current_run_state")
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return None


def describe(state: dict) -> dict:
    players = state.get("players_data") or [{}]
    p0 = players[0] if players else {}
    return {
        "current_wave": state.get("current_wave"),
        "bosses_spawn": state.get("bosses_spawn"),
        "nb_of_waves": state.get("nb_of_waves"),
        "difficulty": state.get("current_difficulty"),
        "character": p0.get("current_character"),
        "hp": p0.get("current_health"),
        "level": p0.get("current_level"),
        "gold": p0.get("gold"),
        "n_weapons": len(p0.get("weapons") or []),
        "n_items": len(p0.get("items") or []),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path(".tmp/snapshots"))
    ap.add_argument("--waves", type=str, default="19,20",
                    help="comma-separated waves to archive")
    ap.add_argument("--poll-sec", type=float, default=2.0)
    ap.add_argument("--max-hours", type=float, default=14.0)
    args = ap.parse_args()

    waves = {int(w) for w in args.waves.split(",") if w.strip()}
    src = save_dir() / "run_v3_0.json"
    args.out.mkdir(parents=True, exist_ok=True)
    index = args.out / "index.jsonl"

    print(f"watching {src}")
    print(f"archiving waves {sorted(waves)} -> {args.out}")

    seen: set[str] = set()
    for line in (index.read_text(encoding="utf-8").splitlines()
                 if index.exists() else []):
        try:
            seen.add(json.loads(line)["digest"])
        except Exception:
            pass
    print(f"{len(seen)} snapshots already archived\n")

    deadline = time.time() + args.max_hours * 3600
    while time.time() < deadline:
        state = read_state(src)
        if state is not None and state.get("current_wave") in waves:
            meta = describe(state)
            # Digest the STATE, not the file bytes: the game rewrites constantly and
            # byte-level churn (timers, counters) would create near-duplicate fixtures.
            key = json.dumps(
                [meta["current_wave"], meta["bosses_spawn"], meta["hp"],
                 meta["gold"], meta["level"], meta["n_items"], meta["n_weapons"]],
                sort_keys=True,
            )
            digest = hashlib.sha256(key.encode()).hexdigest()[:16]
            if digest not in seen:
                seen.add(digest)
                stamp = time.strftime("%Y%m%d_%H%M%S")
                boss = boss_label(meta["bosses_spawn"])
                meta["boss"] = boss
                meta["boss_raw"] = (meta["bosses_spawn"] or ["unknown"])[0]
                name = f"w{meta['current_wave']}_{boss}_{stamp}_{digest}.json"
                dest = args.out / name
                shutil.copy2(src, dest)
                # Verify the copy parses -- a torn copy is worthless as a fixture.
                if read_state(dest) is None:
                    dest.unlink(missing_ok=True)
                    seen.discard(digest)
                    print(f"  [torn copy discarded, will retry] wave {meta['current_wave']}")
                else:
                    rec = {
                        "digest": digest,
                        "file": name,
                        "captured_at": stamp,
                        # Link back to the run that produced this build; see
                        # newest_telemetry_run_id for why.
                        "source_run_id": newest_telemetry_run_id(),
                        **meta,
                    }
                    with index.open("a", encoding="utf-8") as fh:
                        fh.write(json.dumps(rec) + "\n")
                    print(f"  + {name}  boss={boss} hp={meta['hp']} "
                          f"lvl={meta['level']} items={meta['n_items']} "
                          f"gold={meta['gold']} src={rec['source_run_id']}")
        time.sleep(args.poll_sec)

    print("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
