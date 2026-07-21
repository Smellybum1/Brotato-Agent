#!/usr/bin/env python3
"""Discover Steam libraries and Brotato install without assuming drive letters."""
from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import sys
import winreg
from pathlib import Path


APP_ID = "1942280"


def steam_roots() -> list[Path]:
    roots: list[Path] = []
    for hive, sub in (
        (winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam"),
    ):
        try:
            with winreg.OpenKey(hive, sub) as key:
                for name in ("SteamPath", "InstallPath"):
                    try:
                        val, _ = winreg.QueryValueEx(key, name)
                        if val:
                            roots.append(Path(val))
                    except OSError:
                        pass
        except OSError:
            pass
    # de-dupe
    out: list[Path] = []
    seen = set()
    for r in roots:
        rp = r.resolve()
        if rp not in seen and rp.exists():
            seen.add(rp)
            out.append(rp)
    return out


def parse_library_folders(vdf: Path) -> list[Path]:
    text = vdf.read_text(encoding="utf-8", errors="ignore")
    paths = re.findall(r'"path"\s+"([^"]+)"', text)
    libs = []
    for p in paths:
        libs.append(Path(p.replace("\\\\", "\\")))
    return libs


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def find_brotato(libraries: list[Path]) -> Path | None:
    for lib in libraries:
        candidates = [
            lib / "steamapps" / "common" / "Brotato" / "Brotato.exe",
            lib / "common" / "Brotato" / "Brotato.exe",
        ]
        for c in candidates:
            if c.exists():
                return c.parent
    return None


def main() -> int:
    roots = steam_roots()
    libraries: list[Path] = []
    for root in roots:
        vdf = root / "steamapps" / "libraryfolders.vdf"
        if vdf.exists():
            libraries.extend(parse_library_folders(vdf))
        libraries.append(root)
    # unique
    uniq: list[Path] = []
    seen = set()
    for lib in libraries:
        try:
            rp = lib.resolve()
        except OSError:
            continue
        if rp not in seen:
            seen.add(rp)
            uniq.append(rp)

    game = find_brotato(uniq)
    userdata = Path(os.environ.get("APPDATA", "")) / "Brotato"
    report = {
        "os": platform.platform(),
        "python": sys.version,
        "steam_roots": [str(p) for p in roots],
        "libraries": [str(p) for p in uniq],
        "brotato_install": str(game) if game else None,
        "userdata": str(userdata) if userdata.exists() else None,
        "app_id": APP_ID,
    }
    if game:
        exe = game / "Brotato.exe"
        pck = game / "Brotato.pck"
        report["exe_sha256"] = sha256(exe) if exe.exists() else None
        report["pck_sha256"] = sha256(pck) if pck.exists() else None
        report["exe_version"] = None
        try:
            import ctypes
            from ctypes import wintypes

            # lightweight: rely on docs ENVIRONMENT for ProductVersion; keep hash here
        except Exception:
            pass
        acf = None
        for lib in uniq:
            cand = lib / "steamapps" / f"appmanifest_{APP_ID}.acf"
            if cand.exists():
                acf = cand
                break
        if acf:
            report["appmanifest"] = str(acf)
            report["appmanifest_text"] = acf.read_text(encoding="utf-8", errors="ignore")

    out = Path(__file__).resolve().parents[1] / "reports" / "discover_install.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"Wrote {out}")
    return 0 if game else 2


if __name__ == "__main__":
    raise SystemExit(main())
