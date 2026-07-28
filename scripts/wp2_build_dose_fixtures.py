"""Build the enemy-health dose-response arms for the wave-17 experiment.

Reads the wave-17 snapshot index, selects ONE fixture per source run (the
current_wave==16 row with the LOWEST gold, i.e. post-shop, so the trial does not
re-run the shop), and emits three arms per fixture: control (health 1.00),
H75 (0.75) and H50 (0.50).

METHOD REQUIREMENT: every arm -- INCLUDING the control -- is produced by the same
json.load -> mutate -> json.dump round trip. A byte-copied control would confound
"the dial did nothing" with "re-serialisation broke the save": only the edited arms
would fail, which reads exactly like a null result.

Every written file is RE-READ FROM DISK and asserted against the intended dose and
against the source's invariant fields. An arming step verified only by its own exit
code is how this project previously ran a campaign that measured nothing.
"""

from __future__ import annotations

import argparse
import io
import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INDEX = REPO_ROOT / ".tmp" / "snapshots_w17" / "index.jsonl"
DEFAULT_OUT = REPO_ROOT / ".tmp" / "dose_fixtures"

# A save at current_wave N resumes into the wave-N shop and plays wave N+1.
SOURCE_WAVE = 16
TARGET_WAVE = 17

ARMS: list[tuple[str, float]] = [("C", 1.00), ("H75", 0.75), ("H50", 0.50)]


def read_json(path: Path) -> Any:
    with io.open(path, "r", encoding="utf-8-sig") as fh:
        return json.load(fh)


def write_json(path: Path, payload: Any) -> None:
    """UTF-8, no BOM, LF newlines -- the game's loader is byte-sensitive."""
    with io.open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(payload, fh)


def load_index(index_path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with io.open(index_path, "r", encoding="utf-8-sig") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def select_fixtures(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One row per source_run_id: wave-16 rows only, lowest gold wins.

    Lowest gold = the save was taken AFTER the shop was spent, so resuming it does
    not re-run the shop and re-randomise the loadout under us.
    """
    best: dict[str, dict[str, Any]] = {}
    for row in rows:
        if int(row.get("current_wave", -1)) != SOURCE_WAVE:
            continue
        run_id = str(row.get("source_run_id", ""))
        cur = best.get(run_id)
        if cur is None or int(row.get("gold", 0)) < int(cur.get("gold", 0)):
            best[run_id] = row
    return [best[k] for k in sorted(best)]


def weapon_ids(state: dict[str, Any]) -> list[list[str]]:
    out: list[list[str]] = []
    for player in state.get("players_data") or []:
        out.append([str(w.get("my_id", "")) for w in (player.get("weapons") or [])])
    return out


def build_arm(src_path: Path, out_path: Path, dose: float) -> None:
    """Round-trip the save with the dose applied, then read it back and verify."""
    payload = read_json(src_path)
    state = payload["current_run_state"]

    src_wave = int(state.get("current_wave", -1))
    src_bosses = list(state.get("bosses_spawn") or [])
    src_weapons = weapon_ids(state)
    scaling = state.get("enemy_scaling")
    if not isinstance(scaling, dict):
        raise SystemExit(f"ABORT: {src_path.name} has no enemy_scaling dict")
    src_damage = scaling.get("damage")
    src_speed = scaling.get("speed")

    scaling["health"] = dose

    write_json(out_path, payload)

    # READBACK -- from disk, not from the in-memory object we just wrote.
    back = read_json(out_path)
    bstate = back["current_run_state"]
    bscale = bstate.get("enemy_scaling") or {}
    problems: list[str] = []
    if bscale.get("health") != dose:
        problems.append(f"health={bscale.get('health')!r} expected {dose!r}")
    if bscale.get("damage") != src_damage:
        problems.append(f"damage={bscale.get('damage')!r} expected {src_damage!r}")
    if bscale.get("speed") != src_speed:
        problems.append(f"speed={bscale.get('speed')!r} expected {src_speed!r}")
    if int(bstate.get("current_wave", -1)) != src_wave:
        problems.append(f"current_wave={bstate.get('current_wave')!r} expected {src_wave!r}")
    if list(bstate.get("bosses_spawn") or []) != src_bosses:
        problems.append(f"bosses_spawn={bstate.get('bosses_spawn')!r} expected {src_bosses!r}")
    if weapon_ids(bstate) != src_weapons:
        problems.append(f"weapons={weapon_ids(bstate)!r} expected {src_weapons!r}")
    if problems:
        raise SystemExit(
            "ABORT: readback mismatch for %s:\n  %s" % (out_path, "\n  ".join(problems))
        )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--index", type=Path, default=DEFAULT_INDEX)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args(argv)

    index_path: Path = args.index
    out_dir: Path = args.out_dir
    snap_dir = index_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = load_index(index_path)
    selected = select_fixtures(rows)

    print(f"index rows: {len(rows)}  wave-{SOURCE_WAVE} selected: {len(selected)}")
    print("")
    hdr = (
        f"{'source_run_id':<22} {'boss':<9} {'digest':<17} {'gold':>5} "
        f"{'hp':>4} {'lvl':>4} {'wpn':>4} {'itm':>4}"
    )
    print(hdr)
    print("-" * len(hdr))
    for row in selected:
        print(
            f"{row.get('source_run_id',''):<22} {str(row.get('boss','')):<9} "
            f"{str(row.get('digest','')):<17} {int(row.get('gold',0)):>5} "
            f"{int(row.get('hp',0)):>4} {int(row.get('level',0)):>4} "
            f"{int(row.get('n_weapons',0)):>4} {int(row.get('n_items',0)):>4}"
        )
    print("")

    boss_mix: dict[str, int] = {}
    for row in selected:
        key = str(row.get("boss", ""))
        boss_mix[key] = boss_mix.get(key, 0) + 1
    print("boss mix: " + ", ".join(f"{k}={v}" for k, v in sorted(boss_mix.items())))

    manifest_rows: list[dict[str, Any]] = []
    per_arm: dict[str, int] = {arm: 0 for arm, _ in ARMS}
    for row in selected:
        src_path = snap_dir / str(row["file"])
        base = src_path.stem
        for arm, dose in ARMS:
            out_path = out_dir / f"{base}__{arm}.json"
            build_arm(src_path, out_path, dose)
            per_arm[arm] += 1
            manifest_rows.append(
                {
                    "source_run_id": row.get("source_run_id"),
                    "arm": arm,
                    "dose": dose,
                    "path": str(out_path),
                    "source_digest": row.get("digest"),
                    "source_file": row.get("file"),
                    "boss": row.get("boss"),
                    "boss_raw": row.get("boss_raw"),
                    "source_wave": SOURCE_WAVE,
                    "target_wave": TARGET_WAVE,
                    "hp": row.get("hp"),
                    "level": row.get("level"),
                    "gold": row.get("gold"),
                    "n_weapons": row.get("n_weapons"),
                    "n_items": row.get("n_items"),
                }
            )

    manifest_path = out_dir / "manifest.jsonl"
    with io.open(manifest_path, "w", encoding="utf-8", newline="\n") as fh:
        for mrow in manifest_rows:
            fh.write(json.dumps(mrow) + "\n")

    print("")
    print(f"manifest: {manifest_path}  rows={len(manifest_rows)}")
    for arm, dose in ARMS:
        print(f"  arm {arm:<4} health={dose:<5} files={per_arm[arm]}")
    print(f"readback: PASSED on all {len(manifest_rows)} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
