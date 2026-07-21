#!/usr/bin/env python3
"""Backup Brotato AppData + Steam userdata; verify readability."""
from __future__ import annotations

import json
import os
import shutil
import time
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    ts = time.strftime("%Y%m%d_%H%M%S")
    backup = root / "backups" / f"userdata_{ts}"
    backup.mkdir(parents=True, exist_ok=True)

    appdata = Path(os.environ["APPDATA"]) / "Brotato"
    if appdata.exists():
        shutil.copytree(appdata, backup / "AppData_Brotato")

    steam_ud = Path(r"C:\Games\Steam\userdata")
    # discover any 1942280 folders
    copied = []
    if steam_ud.exists():
        for p in steam_ud.glob("*/1942280"):
            dest = backup / f"Steam_userdata_{p.parent.name}_1942280"
            shutil.copytree(p, dest)
            copied.append(str(p))

    files = [p for p in backup.rglob("*") if p.is_file()]
    sample = backup / "AppData_Brotato"
    readable = False
    sample_path = None
    for cand in sample.rglob("save_v3_0.json") if sample.exists() else []:
        sample_path = cand
        json.loads(cand.read_text(encoding="utf-8"))
        readable = True
        break

    manifest = {
        "timestamp": ts,
        "file_count": len(files),
        "total_bytes": sum(f.stat().st_size for f in files),
        "sample_readable": readable,
        "sample_path": str(sample_path) if sample_path else None,
        "steam_userdata_copied": copied,
        "appdata_source": str(appdata),
    }
    (backup / "BACKUP_MANIFEST.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return 0 if readable else 2


if __name__ == "__main__":
    raise SystemExit(main())
