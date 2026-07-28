"""Stage A step 1: cheap classification of every run from summary.json only.

Writes .tmp/stageA/run_index.jsonl. Never opens events.jsonl.
"""
from __future__ import annotations

import json
import os
import sys

RUNS = os.environ.get("RUNS_DIR") or os.path.join(
    os.environ.get("APPDATA", r"C:\Users\moxhe\AppData\Roaming"), "Brotato", "brotato_agent", "runs"
)
OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".tmp", "stageA")


def _get(d, *keys):
    for k in keys:
        if isinstance(d, dict) and k in d:
            return d[k]
    return None


def main() -> int:
    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = os.path.join(OUT_DIR, "run_index.jsonl")
    n_dirs = n_ok = n_missing = n_bad = 0
    with open(out_path, "w", encoding="utf-8") as out:
        for name in sorted(os.listdir(RUNS)):
            d = os.path.join(RUNS, name)
            if not os.path.isdir(d):
                continue
            n_dirs += 1
            sp = os.path.join(d, "summary.json")
            if not os.path.exists(sp):
                n_missing += 1
                continue
            try:
                with open(sp, "r", encoding="utf-8", errors="replace") as fh:
                    s = json.load(fh)
            except Exception as exc:  # noqa: BLE001
                n_bad += 1
                print("BADJSON %s %s" % (name, exc), file=sys.stderr)
                continue
            if not isinstance(s, dict):
                n_bad += 1
                continue
            row = {
                "run_id": s.get("run_id") or name,
                "dir": name,
                "result": _get(s, "result", "outcome"),
                "last_wave": _get(s, "last_wave", "wave"),
                "duration_ms": _get(s, "duration_ms"),
                "policy_version": _get(s, "policy_version"),
                "mod_version": _get(s, "mod_version"),
                "has_events": os.path.exists(os.path.join(d, "events.jsonl")),
                "events_bytes": (
                    os.path.getsize(os.path.join(d, "events.jsonl"))
                    if os.path.exists(os.path.join(d, "events.jsonl"))
                    else 0
                ),
                "keys": sorted(s.keys()) if n_ok == 0 else None,
            }
            out.write(json.dumps(row) + "\n")
            n_ok += 1
    print("dirs=%d ok=%d missing_summary=%d bad=%d -> %s" % (n_dirs, n_ok, n_missing, n_bad, out_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
