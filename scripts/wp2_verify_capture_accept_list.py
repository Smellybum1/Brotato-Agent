"""Empirical proof for the combat_obs_v1 capture-schema ACCEPT-LIST.

Four checks, all with printed denominators:

1. v127 additive-inertness: for N real v127 (2823CB7E...) captures, strip
   ``player.materials``, ``player.bonus_materials`` and
   ``entities.materials[].value``, re-encode, and require an identical
   ``canonical_digest``.
2. Both directions encode: one pre-v127 (95B64447...) capture and one v127
   capture, through the SAME pinned schema.
3. An unknown capture hash is still REJECTED.
4. ``datasets/combat_obs_v1`` still loads (observation schema hash unchanged).

Read-only. Never launches the game.
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from trainer.observation.encoder_v1 import (  # noqa: E402
    ObservationError,
    accepted_capture_hashes,
    canonical_digest,
    encode_capture,
    load_schema,
)

SCHEMA_PATH = ROOT / "configs" / "wp2" / "observation_v1.yaml"
PRE_V127_HASH = "95B6444796A21FD44E94113B75BA2097BC381D5F72ED784F9B9A4A99DD46D951"
V127_HASH = "2823CB7E7D6A6DDB7F805A76D0CD674BA7A2A908058771B66B4A8FEFF9BC1174"
SPOT_CHECKS = 8000
SEED = 20260730


def strip_v127_additions(payload: dict) -> dict:
    import copy

    out = copy.deepcopy(payload)
    player = out.get("player")
    if isinstance(player, dict):
        player.pop("materials", None)
        player.pop("bonus_materials", None)
    for material in ((out.get("entities") or {}).get("materials") or []):
        if isinstance(material, dict):
            material.pop("value", None)
    return out


def iter_captures(events_path: Path):
    with open(events_path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("event") == "combat_capture":
                yield event["payload"]


def collect(runs_root: Path, run_ids: list[str], want_hash: str, limit: int) -> list[dict]:
    out: list[dict] = []
    for run_id in run_ids:
        path = runs_root / run_id / "events.jsonl"
        if not path.is_file():
            continue
        for payload in iter_captures(path):
            if str(payload.get("capture_schema_hash", "")).upper() == want_hash:
                out.append(payload)
                if len(out) >= limit:
                    return out
    return out


def main() -> int:
    schema = load_schema(SCHEMA_PATH)
    accepted = accepted_capture_hashes(schema)
    print(f"schema file: {SCHEMA_PATH}")
    print(f"observation schema hash: {schema['_schema_hash']}")
    print(f"pinned source_capture_schema_hash: {schema['source_capture_schema_hash']}")
    print(f"accept-list ({len(accepted)}): {list(accepted)}")

    human_manifest = json.loads((ROOT / "datasets" / "human_obs_v1" / "manifest.json").read_text())
    teacher_manifest = json.loads((ROOT / "datasets" / "combat_obs_v1" / "manifest.json").read_text())
    runs_root = Path(human_manifest["runs_root"])
    v127_runs = [r["run_id"] for r in human_manifest["runs"]]
    pre_runs = [r["run_id"] for r in teacher_manifest["runs"]]

    # --- 1. inertness -------------------------------------------------------
    pool = collect(runs_root, v127_runs, V127_HASH, SPOT_CHECKS * 3)
    print(f"\n[1] v127 capture pool collected: {len(pool)}")
    rng = random.Random(SEED)
    sample = pool if len(pool) <= SPOT_CHECKS else rng.sample(pool, SPOT_CHECKS)
    checked = mismatches = encode_faults = 0
    for payload in sample:
        try:
            with_fields = encode_capture(payload, schema)
            without = strip_v127_additions(payload)
            without["capture_schema_hash"] = payload.get("capture_schema_hash")
            other = encode_capture(without, schema)
        except ObservationError:
            encode_faults += 1
            continue
        checked += 1
        if canonical_digest(with_fields) != canonical_digest(other):
            mismatches += 1
    print(f"[1] spot-checks attempted: {len(sample)}  encoded: {checked}  "
          f"encode faults: {encode_faults}  DIGEST MISMATCHES: {mismatches}")

    # --- 2. both directions encode -----------------------------------------
    pre = collect(runs_root, pre_runs, PRE_V127_HASH, 1)
    print(f"\n[2] pre-v127 captures found: {len(pre)} (searched {len(pre_runs)} runs)")
    ok_pre = ok_v127 = False
    if pre:
        enc = encode_capture(pre[0], schema)
        ok_pre = True
        print(f"[2] pre-v127 encoded OK: globals={len(enc.global_features)} "
              f"valid={enc.valid} digest={canonical_digest(enc)[:16]}")
    if pool:
        enc = encode_capture(pool[0], schema)
        ok_v127 = True
        print(f"[2] v127     encoded OK: globals={len(enc.global_features)} "
              f"valid={enc.valid} digest={canonical_digest(enc)[:16]}")

    # --- 3. unknown hash still rejected ------------------------------------
    rejected = False
    if pool:
        bad = dict(pool[0])
        bad["capture_schema_hash"] = "0" * 64
        try:
            encode_capture(bad, schema)
        except ObservationError as exc:
            rejected = True
            print(f"\n[3] unknown hash rejected: {exc}")
    if not rejected:
        print("\n[3] FAIL: unknown hash was NOT rejected")

    # --- 4. frozen teacher dataset still loads ------------------------------
    from trainer.data.bc_dataset import load_bc_dataset  # noqa: E402

    ds_ok = False
    try:
        ds = load_bc_dataset(
            ROOT / "datasets" / "combat_obs_v1",
            ROOT / "configs" / "wp2" / "dataset_split_v1.yaml",
            ROOT / "configs" / "wp2" / "bc_input_v1.yaml",
            SCHEMA_PATH,
        )
        ds_ok = True
        print(f"\n[4] datasets/combat_obs_v1 loaded: schema_hash={ds.schema_hash} "
              f"train={ds.train.size} val={ds.val.size} total={ds.train.size + ds.val.size}")
    except Exception as exc:  # noqa: BLE001 - report verbatim
        print(f"\n[4] datasets/combat_obs_v1 load raised {type(exc).__name__}: {exc}")

    all_ok = mismatches == 0 and checked > 0 and ok_pre and ok_v127 and rejected and ds_ok
    print(f"\nRESULT: {'PASS' if all_ok else 'FAIL'}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
