#!/usr/bin/env python3
"""Deploy Tom-BrotatoAgent using the verified Brotato 1.1.15.4 ModLoader path.

Working rules (discovered 2026-07-17):
  - Workshop zip under steamapps/workshop/content/1942280/<subscribed_id>/
  - Profile entry shape: {"is_active": true, "zip_path": "C:/.../Mod.zip"}
    (bare `true` crashes ModLoader)
  - Local `<install>/mods/*.zip` is NOT scanned by this build
  - Temporary "Mods are currently disabled" is cleared by archiving/clearing
    %AppData%/Brotato/logs
  - version_number must be strict semver (e.g. 0.1.0), no prerelease suffix
  - Park BlackTriangle-FullAutoBot.zip while agent is active to avoid dual bots
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path


SUBSCRIBED_WORKSHOP_ID = "3737864106"  # Full Auto Bot workshop item (host folder)


def discover_game() -> Path:
    script = Path(__file__).resolve().parent / "discover_install.py"
    subprocess.check_call([sys.executable, str(script)])
    report = Path(__file__).resolve().parents[1] / "reports" / "discover_install.json"
    data = json.loads(report.read_text(encoding="utf-8"))
    install = data.get("brotato_install")
    if not install:
        raise SystemExit("Brotato install not found")
    return Path(install)


def steam_workshop_content() -> Path:
    game = discover_game()
    steamapps = game.parent.parent
    return steamapps / "workshop" / "content" / "1942280"


def close_brotato(timeout_s: float = 5.0) -> None:
    try:
        import psutil  # optional
    except ImportError:
        psutil = None
    # Prefer taskkill/CloseMainWindow via PowerShell-less approach
    subprocess.call(
        ["powershell", "-NoProfile", "-Command",
         "Get-Process Brotato -EA SilentlyContinue | ForEach-Object { $_.CloseMainWindow() | Out-Null }; "
         f"Start-Sleep -Seconds {int(timeout_s)}; "
         "Get-Process Brotato -EA SilentlyContinue | Stop-Process -Force"],
        shell=False,
    )


def clear_mods_disabled_latch(root: Path) -> None:
    log_dir = Path(os.environ["APPDATA"]) / "Brotato" / "logs"
    if not log_dir.exists():
        return
    arch = root / "reports" / f"logs_archive_{time.strftime('%Y%m%d_%H%M%S')}"
    arch.mkdir(parents=True, exist_ok=True)
    for p in log_dir.iterdir():
        if p.is_file():
            shutil.copy2(p, arch / p.name)
            p.unlink()
    print(f"Cleared mods-disabled latch; archived logs to {arch}")


def make_mod_zip(source_mod_dir: Path, zip_path: Path, mod_folder_name: str) -> Path:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for f in source_mod_dir.rglob("*"):
            if not f.is_file():
                continue
            if f.suffix in {".pyc", ".pyo"} or f.name.startswith("."):
                continue
            arc = f"mods-unpacked/{mod_folder_name}/" + f.relative_to(source_mod_dir).as_posix()
            zf.write(f, arcname=arc)
    print(f"Wrote zip {zip_path} ({zip_path.stat().st_size} bytes)")
    return zip_path


def write_profile_agent(zip_path: Path) -> None:
    profile = Path(os.environ["APPDATA"]) / "Brotato" / "mod_user_profiles.json"
    z = str(zip_path.resolve()).replace("\\", "/")
    data = {
        "current_profile": "default",
        "profiles": {
            "default": {
                "mod_list": {
                    "Tom-BrotatoAgent": {"is_active": True, "zip_path": z},
                    "BlackTriangle-FullAutoBot": {
                        "is_active": False,
                        "zip_path": str(
                            (steam_workshop_content() / SUBSCRIBED_WORKSHOP_ID / "BlackTriangle-FullAutoBot.zip")
                        ).replace("\\", "/"),
                    },
                }
            }
        },
    }
    profile.write_text(json.dumps(data, indent="\t") + "\n", encoding="utf-8")
    print(f"Wrote {profile}")


def write_agent_config(auto_start: bool = True) -> None:
    cfg_dir = Path(os.environ["APPDATA"]) / "Brotato" / "brotato_agent"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    cfg = {
        "auto_start": auto_start,
        "character": "character_well_rounded",
        "danger": 0,
        "weapon_prefixes": ["weapon_smg", "weapon_stick"],
    }
    path = cfg_dir / "agent_config.json"
    path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    print(f"Wrote {path}")


def deploy_agent(root: Path, auto_start: bool, clear_latch: bool) -> Path:
    if clear_latch:
        clear_mods_disabled_latch(root)
    src = root / "mod" / "mods-unpacked" / "Tom-BrotatoAgent"
    ws = steam_workshop_content() / SUBSCRIBED_WORKSHOP_ID
    ws.mkdir(parents=True, exist_ok=True)
    zip_path = ws / "Tom-BrotatoAgent.zip"
    make_mod_zip(src, zip_path, "Tom-BrotatoAgent")
    # Park upstream zip so Workshop scan loads only the agent.
    upstream = ws / "BlackTriangle-FullAutoBot.zip"
    parked = ws / "BlackTriangle-FullAutoBot.zip.disabled"
    if upstream.exists():
        if parked.exists():
            parked.unlink()
        upstream.rename(parked)
        print(f"Parked {upstream.name} -> {parked.name}")
    game = discover_game()
    mods = game / "mods"
    mods.mkdir(exist_ok=True)
    shutil.copy2(zip_path, mods / "Tom-BrotatoAgent.zip")
    write_profile_agent(zip_path)
    write_agent_config(auto_start=auto_start)
    return zip_path


def restore_upstream() -> Path:
    ws = steam_workshop_content() / SUBSCRIBED_WORKSHOP_ID
    upstream = ws / "BlackTriangle-FullAutoBot.zip"
    parked = ws / "BlackTriangle-FullAutoBot.zip.disabled"
    agent = ws / "Tom-BrotatoAgent.zip"
    if agent.exists():
        agent.unlink()
    if parked.exists() and not upstream.exists():
        parked.rename(upstream)
    z = upstream if upstream.exists() else parked
    profile = Path(os.environ["APPDATA"]) / "Brotato" / "mod_user_profiles.json"
    data = {
        "current_profile": "default",
        "profiles": {
            "default": {
                "mod_list": {
                    "BlackTriangle-FullAutoBot": {
                        "is_active": True,
                        "zip_path": str(z.resolve()).replace("\\", "/"),
                    }
                }
            }
        },
    }
    profile.write_text(json.dumps(data, indent="\t") + "\n", encoding="utf-8")
    print("Restored upstream Full Auto Bot")
    return z


def repair_launch(root: Path) -> Path:
    """Make the INSTALLED build loadable again without redeploying it.

    An unclean shutdown (a force-kill, a crash) makes ModLoader latch "Mods are
    currently disabled" AND empty the profile's mod_list, so the next launch runs
    vanilla and the game idles on the title screen with a stale mod_ready.json.
    A normal deploy happens to fix both, which is why this never needed its own
    path before --no-deploy existed.

    Deliberately does NOT rezip and does NOT touch agent_config.json: a campaign
    that freezes the installed build must be repairable without changing either
    the build or the arm.
    """
    zip_path = steam_workshop_content() / SUBSCRIBED_WORKSHOP_ID / "Tom-BrotatoAgent.zip"
    if not zip_path.is_file():
        raise SystemExit(f"repair-launch: no installed mod zip at {zip_path}; deploy first")
    clear_mods_disabled_latch(root)
    write_profile_agent(zip_path)
    print(f"Repaired launch state for installed zip {zip_path}")
    return zip_path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", choices=["agent", "upstream"], default="agent")
    ap.add_argument("--no-auto-start", action="store_true")
    ap.add_argument("--no-clear-latch", action="store_true")
    ap.add_argument("--close-game", action="store_true", help="Close Brotato before deploy")
    ap.add_argument(
        "--repair-launch",
        action="store_true",
        help="Clear the mods-disabled latch and restore the mod profile for the "
        "already-installed zip, then exit. Does not rezip and does not rewrite "
        "agent_config.json, so it is safe mid-campaign.",
    )
    args = ap.parse_args()
    root = Path(__file__).resolve().parents[1]
    if args.close_game:
        close_brotato()
    if args.repair_launch:
        repair_launch(root)
        return 0
    if args.target == "upstream":
        z = restore_upstream()
    else:
        z = deploy_agent(root, auto_start=not args.no_auto_start, clear_latch=not args.no_clear_latch)
    stamp = {"target": args.target, "zip": str(z)}
    (root / ".deploy_stamp").write_text(json.dumps(stamp, indent=2), encoding="utf-8")
    print(json.dumps(stamp, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
