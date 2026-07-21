# Environment Audit (WP1)

Recorded: 2026-07-17 (Australia/Brisbane)

## Host

| Field | Value |
|------|-------|
| OS | Windows 10/11 NT 10.0.26200 |
| Computer | TOM |
| User | moxhe |
| CPU | AMD Ryzen 7 9800X3D 8-Core Processor |
| GPU | NVIDIA GeForce RTX 4090 (+ AMD Radeon iGPU) |

## Steam

| Field | Value |
|------|-------|
| Steam root | `C:\Games\Steam` |
| libraryfolders.vdf | `C:\Games\Steam\steamapps\libraryfolders.vdf` |
| Libraries | `C:\Games\Steam` only |

## Brotato install

| Field | Value |
|------|-------|
| App ID | 1942280 |
| Install dir | `C:\Games\Steam\steamapps\common\Brotato` |
| Executable | `Brotato.exe` |
| Product version | **1.1.15.4** |
| Steam buildid | 23429717 |
| Depot | 1942281 / manifest 5289220193624029472 |
| Brotato.exe SHA256 | `F69A1217FD15DAF46300CC6224DD34F7ECD4F56288FC71E95ED6344EFF753AE4` |
| Brotato.pck SHA256 | `BE303F0A320CB099001FDC39C3B807CDD657E93426DC09867CEE1D36F5385ACF` |
| Engine (from log) | Godot Engine v3.7.dev.custom_build.74e86be54 |
| ModLoader | Bundled with game; loads Workshop + `res://mods-unpacked/` |
| ModLoader versions declared compatible by upstream | 6.0.0 / 6.1.0 / 6.3.0 |
| DLC | No separate Abyssal Terrors depot in libraryfolders; `deactivated_dlcs: []` in settings |
| Workshop content path | `C:\Games\Steam\steamapps\workshop\content\1942280` (missing / empty — Error 31 in logs) |

## User data

| Field | Value |
|------|-------|
| AppData | `C:\Users\moxhe\AppData\Roaming\Brotato` |
| Profile saves | `...\76561198030888875\` (`save_v3_0.json`, `run_v3_0.json`, `settings.json`) |
| Steam userdata | `C:\Games\Steam\userdata\70623147\1942280` |
| Initial verified backup | `backups/userdata_20260717_223406` (37 files, 877805 bytes, JSON readable) |
| WP1 closeout backup | `backups/userdata_20260722_081559` (776 files, 355794972 bytes; active v3 saves/settings JSON readable; Steam userdata included) |

## Relevant settings (pre-mod)

- `endless_mode_toggled`: false
- `retry_wave`: false
- `enemy_scaling`: damage/health/speed = 1
- `play_mode`: 0 (solo)

## Mod loading (verified)

| Mechanism | Result on this install |
|-----------|------------------------|
| `res://mods-unpacked/` on disk | Not visible to exported game |
| `<install>/mods/*.zip` | Not scanned |
| Workshop folder `.../workshop/content/1942280/<subscribed_id>/*.zip` | **Works** |
| Profile `"ModId": true` | Crashes ModLoader init |
| Profile `"ModId": {"is_active": true, "zip_path": "..."}` | **Works** |
| Temporary "Mods are currently disabled" | Clear `%AppData%/Brotato/logs` |

Stage B: Official Workshop item **3737864106** (Full Auto Bot) subscribed and confirmed playing in-game by Tom.

Stage C deploy: `Tom-BrotatoAgent.zip` placed in that Workshop content folder; upstream zip parked as `.disabled` while agent is active.
